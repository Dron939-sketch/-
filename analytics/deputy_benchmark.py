"""Бенчмарк коллег — сравниваем депутата с другими у кого есть VK.

На вход — текущий депутат + список всех в городе. Выбираем тех, у
кого привязан vk_handle, считаем для каждого:
- posts_per_week
- avg_likes
- alignment_score (по своему архетипу)
- composite_rating (тот же что для main)

Возвращаем:
- ranking — таблица всех с метриками, текущий депутат подсвечен
- best_posts — top-3 поста от коллег (high engagement) — для вдохновения

Все вызовы fail-safe: если VK недоступно — пустые блоки.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_LOOKBACK_DAYS = 30


async def build_benchmark(
    current_deputy: Dict[str, Any],
    all_deputies: List[Dict[str, Any]],
    current_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Собирает бенчмарк по коллегам с VK. Возвращает {ranking, best_posts, state}.

    current_metrics — уже посчитанные для текущего депутата (из audit), чтобы
    не делать второй запрос wall.get. Если None — рассчитаем заново.
    Peers с ошибкой fetch'а попадают в ranking с пометкой error — их видно
    что страница приватная / API недоступен; ranking не пустеет.
    """
    peers = [
        d for d in all_deputies
        if d.get("vk") and d.get("external_id") != current_deputy.get("external_id")
    ]
    ranking: List[Dict[str, Any]] = []
    all_posts_with_meta: List[Dict[str, Any]] = []

    # Текущий депутат — всегда в ranking
    if current_metrics is None:
        cur_res = await _fetch_metrics(current_deputy)
        cur_res = cur_res or {}
    else:
        cur_res = current_metrics
    ranking.append({
        "external_id":     current_deputy.get("external_id"),
        "name":            current_deputy.get("name"),
        "vk":              current_deputy.get("vk"),
        "vk_url":          f"https://vk.com/{current_deputy.get('vk')}" if current_deputy.get("vk") else None,
        "district":        current_deputy.get("district"),
        "is_me":           True,
        "posts_per_week":  cur_res.get("posts_per_week", 0),
        "avg_likes":       cur_res.get("avg_likes", 0),
        "alignment_pct":   cur_res.get("alignment_pct", 0),
        "composite":       cur_res.get("composite", 0),
        "error":           None,
    })
    for p in cur_res.get("posts", []):
        all_posts_with_meta.append({
            **p,
            "deputy_name":  current_deputy.get("name"),
            "deputy_short": (current_deputy.get("name") or "").split(" ")[0],
            "vk_url":       f"https://vk.com/{current_deputy.get('vk')}" if current_deputy.get("vk") else None,
            "is_me":        True,
        })

    if not peers:
        return {
            "ranking":    [{**ranking[0], "position": 1}],
            "best_posts": [],
            "state":      "no_peers",
        }

    # Параллельно тянем метрики для peers
    results = await asyncio.gather(
        *[_fetch_metrics(d) for d in peers],
        return_exceptions=True,
    )
    for peer, res in zip(peers, results):
        if isinstance(res, Exception) or res is None:
            # Peer есть в списке, но fetch не получился (стена закрыта, токен
            # без прав, rate-limit). Показываем строку с пометкой.
            ranking.append({
                "external_id":    peer.get("external_id"),
                "name":           peer.get("name"),
                "vk":             peer.get("vk"),
                "vk_url":         f"https://vk.com/{peer.get('vk')}" if peer.get("vk") else None,
                "district":       peer.get("district"),
                "is_me":          False,
                "posts_per_week": None,
                "avg_likes":      None,
                "alignment_pct":  None,
                "composite":      None,
                "error":          "unreachable",
            })
            continue
        ranking.append({
            "external_id":    peer.get("external_id"),
            "name":           peer.get("name"),
            "vk":             peer.get("vk"),
            "vk_url":         f"https://vk.com/{peer.get('vk')}" if peer.get("vk") else None,
            "district":       peer.get("district"),
            "is_me":          False,
            "posts_per_week": res.get("posts_per_week", 0),
            "avg_likes":      res.get("avg_likes", 0),
            "alignment_pct":  res.get("alignment_pct", 0),
            "composite":      res.get("composite", 0),
            "error":          None,
        })
        for p in res.get("posts", []):
            all_posts_with_meta.append({
                **p,
                "deputy_name":  peer.get("name"),
                "deputy_short": (peer.get("name") or "").split(" ")[0],
                "vk_url":       f"https://vk.com/{peer.get('vk')}" if peer.get("vk") else None,
                "is_me":        False,
            })

    # Sort: сначала те у кого есть composite, потом «недоступные» в конец
    ranking.sort(key=lambda r: (r["composite"] is None, -(r["composite"] or 0)))
    for i, r in enumerate(ranking):
        r["position"] = i + 1

    # Top-3 поста от коллег
    peer_posts = [p for p in all_posts_with_meta if not p.get("is_me")]
    peer_posts.sort(key=lambda p: -(p.get("likes", 0) + p.get("reposts", 0) * 2))
    best_posts = peer_posts[:3]

    return {
        "ranking":    ranking,
        "best_posts": best_posts,
        "state":      "ok",
    }


async def _fetch_metrics(deputy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Грузит wall.get + считает метрики + alignment для одного депутата."""
    handle = (deputy.get("vk") or "").strip()
    if not handle:
        return None
    try:
        import aiohttp
        from config.archetypes import archetype_match_score, suggest_for_deputy
        from config.settings import settings
    except Exception:  # noqa: BLE001
        return None
    if settings.demo_mode:
        return None
    token = settings.vk_api_token
    if not token:
        return None

    is_numeric = handle.lstrip("id").lstrip("-").isdigit()
    params: Dict[str, Any] = {
        "count":        25,
        "access_token": token,
        "v":            "5.199",
    }
    if is_numeric:
        params["owner_id"] = handle.lstrip("id")
    else:
        params["domain"] = handle
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.vk.com/method/wall.get",
                params=params, timeout=12,
            ) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.debug("benchmark wall.get failed for %s", handle, exc_info=False)
        return None
    if "error" in data:
        return None
    items = (data.get("response") or {}).get("items") or []
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).timestamp()
    posts: List[Dict[str, Any]] = []
    for p in items:
        ts = int(p.get("date") or 0)
        if ts < cutoff:
            continue
        text = (p.get("text") or "").strip()
        if not text:
            continue
        posts.append({
            "text":         text[:200],
            "published_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "likes":        int((p.get("likes") or {}).get("count") or 0),
            "reposts":      int((p.get("reposts") or {}).get("count") or 0),
            "views":        int((p.get("views") or {}).get("count") or 0),
            "url":          f"https://vk.com/wall{p.get('owner_id') or p.get('from_id')}_{p.get('id')}",
        })
    if not posts:
        return {"posts_per_week": 0, "avg_likes": 0, "alignment_pct": 0, "composite": 0, "posts": []}

    archetype = suggest_for_deputy(deputy)
    align_scores = [archetype_match_score(p["text"], archetype) for p in posts]
    alignment_pct = round(mean(align_scores) * 100, 1) if align_scores else 0
    avg_likes = round(mean(int(p["likes"]) for p in posts), 1)
    span_days = (
        datetime.fromisoformat(max(p["published_at"] for p in posts).replace("Z", "+00:00"))
        - datetime.fromisoformat(min(p["published_at"] for p in posts).replace("Z", "+00:00"))
    ).days or 1
    posts_per_week = round(len(posts) * 7 / max(span_days, 1), 1)

    rating_align    = min(alignment_pct / 100, 1.0)
    rating_freq     = min(posts_per_week / 3.0, 1.0)
    rating_engage   = min(avg_likes / 50.0, 1.0)
    composite = round((rating_align * 0.4 + rating_freq * 0.35 + rating_engage * 0.25) * 5, 1)

    return {
        "posts_per_week": posts_per_week,
        "avg_likes":      avg_likes,
        "alignment_pct":  alignment_pct,
        "composite":      composite,
        "posts":          posts,
    }
