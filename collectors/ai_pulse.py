"""AI-synthesized social pulse (DeepSeek).

Replacement for the disabled Telegram / VK collectors while real
credentials aren't available. Given the last 24h of real news + appeals
for a city, asks DeepSeek to produce 5 plausible citizen-voice posts
("what would people on local chats be saying right now?"). The posts are
clearly marked `source_kind="ai_pulse"` and tagged in their enrichment
with `ai_synth=True`, so the dashboard UI can render a chip labelling
them as AI-синтез rather than passing them off as real social posts.

Behaviour is fail-safe:
- no DeepSeek key / disabled cache  → returns []
- no reference items                 → returns []
- API error / malformed response     → returns []

The synthesized items skip the regular `NewsEnricher` path (their
sentiment / category / severity come straight from the same LLM call to
avoid a double-trip) and go into the DB alongside real news, feeding
reputation-guard, crisis_predictor, and metric snapshots with richer
signal when external sources are sparse.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import List, Optional, Sequence

from ai.cache import ResponseCache
from ai.deepseek_client import DeepSeekClient, DeepSeekError
from ai.prompts import CATEGORIES

from .base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)


_DEFAULT_POSTS = 5
_REFERENCE_CAP = 20  # don't overload the prompt with every single item


_SYSTEM = """Ты — аналитик городской администрации.
По реальной выборке новостей и обращений за последние 24 часа в городе
синтезируешь 5 вероятных постов местных чатов и форумов — как если бы
реальные горожане делились впечатлениями. Пиши по-русски, без угроз и
оскорблений, без имён и персональных данных. Не выдумывай факты вне
заданного контекста.

Отвечаешь строго одним JSON-объектом, без какого-либо другого текста.
""".strip()


_USER_TEMPLATE = """Город: {city}
Реальные события за 24ч:
{context}

Синтезируй ровно {n} постов. Для каждого верни:
- title: до 80 символов, тон как у обычного жителя
- content: 1–3 предложения реплики
- sentiment: число от -1.0 до 1.0
- category: одна из {categories}
- severity: число от 0.0 до 1.0

Формат ответа:
{{"posts": [{{"title": "...", "content": "...", "sentiment": 0.0, "category": "...", "severity": 0.0}}]}}
""".strip()


class AIPulseCollector(BaseCollector):
    """Synthesize social-pulse posts from a reference news window."""

    def __init__(
        self,
        city_name: str,
        *,
        reference_items: Optional[Sequence[CollectedItem]] = None,
        client: Optional[DeepSeekClient] = None,
        posts: int = _DEFAULT_POSTS,
    ):
        super().__init__(city_name)
        self.reference_items = list(reference_items or [])
        if client is None:
            cache = ResponseCache.from_settings()
            client = DeepSeekClient(cache=cache)
        self.client = client
        self.posts = int(posts)

    async def collect(self, since=None) -> List[CollectedItem]:
        if not self.client.enabled:
            logger.info("AIPulseCollector %s: DeepSeek disabled, skipping", self.city_name)
            return []
        reference = self.reference_items[:_REFERENCE_CAP]
        if not reference:
            logger.debug("AIPulseCollector %s: no reference items, skipping", self.city_name)
            return []

        context_lines: List[str] = []
        for it in reference:
            enr = it.enrichment or {}
            sent = enr.get("sentiment")
            cat = enr.get("category") or it.category or "news"
            title = (it.title or it.content or "")[:140].replace("\n", " ")
            sent_str = f" sentiment={sent:.2f}" if isinstance(sent, (int, float)) else ""
            context_lines.append(f"- [{cat}]{sent_str} {title}")

        user = _USER_TEMPLATE.format(
            city=self.city_name,
            n=self.posts,
            context="\n".join(context_lines) or "(пусто)",
            categories=" | ".join(CATEGORIES),
        )

        try:
            data = await self.client.chat_json(_SYSTEM, user)
        except DeepSeekError as exc:
            logger.warning("AIPulseCollector %s: DeepSeek failed (%s)", self.city_name, exc)
            return []

        return self._build_items(data)

    # -----------------------------------------------------------------

    def _build_items(self, data) -> List[CollectedItem]:
        posts = []
        if isinstance(data, dict):
            posts = data.get("posts") or []
        if not isinstance(posts, list):
            return []

        now = self._now()
        items: List[CollectedItem] = []
        for idx, post in enumerate(posts[: self.posts]):
            if not isinstance(post, dict):
                continue
            title = _clip(post.get("title") or "", 200)
            content = _clip(post.get("content") or title, 2000)
            if not (title or content):
                continue
            sentiment = _coerce_float(post.get("sentiment"))
            severity = _coerce_float(post.get("severity"))
            category = str(post.get("category") or "other").strip() or "other"
            if category not in CATEGORIES:
                category = "other"
            # Stagger pseudo-timestamps so we don't insert 5 items with the
            # exact same minute — dedup by (source, handle, url) still works.
            published_at = now - timedelta(minutes=idx * 3)

            items.append(
                CollectedItem(
                    source_kind="ai_pulse",
                    source_handle=f"ai_pulse:{self.city_name}",
                    title=title or content[:80],
                    content=content,
                    url=None,
                    author="AI-синтез",
                    category=category,
                    published_at=published_at,
                    raw={
                        "ai_synth": True,
                        "model": self.client.model,
                        "sentiment": sentiment,
                        "severity": severity,
                    },
                    enrichment={
                        "ai_synth": True,
                        "sentiment": sentiment,
                        "severity": severity,
                        "category": category,
                        "summary": title,
                    },
                )
            )
        return items


def _coerce_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return max(-1.0, min(1.0, float(v))) if isinstance(v, (int, float)) else float(v)
    except (TypeError, ValueError):
        return None


def _clip(s: str, max_len: int) -> str:
    s = str(s or "").strip()
    return s[: max_len - 1] + "…" if len(s) > max_len else s
