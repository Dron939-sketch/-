"""Поиск в интернете для Джарвиса (без API-ключа).

Использует DuckDuckGo HTML endpoint (https://html.duckduckgo.com/html?q=)
— возвращает страничку с результатами, которую парсим простыми regex.
DuckDuckGo не требует регистрации и работает прямо из России без VPN.

Если HTML-формат ddg.com поменяется — функция вернёт пустой список,
caller получит «найти ничего не удалось» и не сломается.
"""

from __future__ import annotations

import asyncio
import logging
import re
from html import unescape
from typing import Dict, List, Optional
from urllib.parse import unquote

import aiohttp

logger = logging.getLogger(__name__)


_DDG_HTML_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# DuckDuckGo HTML рендерит результаты в виде:
#   <a class="result__a" href="//duckduckgo.com/l/?uddg=...&...">Title</a>
#   <a class="result__snippet" href="...">snippet</a>
_RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_RESULT_SNIPPET_RE = re.compile(
    r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _decode_ddg_link(href: str) -> str:
    """DDG оборачивает реальные URL в редирект /l/?uddg=<urlencoded>."""
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        try:
            return unquote(m.group(1))
        except Exception:  # noqa: BLE001
            return href
    if href.startswith("//"):
        return "https:" + href
    return href


async def search(query: str, *, limit: int = 5) -> List[Dict[str, str]]:
    """Веб-поиск через DuckDuckGo HTML. Возвращает до `limit` результатов
    с {title, snippet, url}. На любую ошибку — [] (caller fallback'ится).
    """
    q = (query or "").strip()
    if not q:
        return []
    try:
        from config.settings import settings as _settings
        if _settings.demo_mode:
            return []
    except Exception:  # noqa: BLE001
        pass
    payload = {"q": q, "kl": "ru-ru"}
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                _DDG_HTML_URL,
                data=payload,
                headers={"User-Agent": _USER_AGENT},
            ) as resp:
                if resp.status != 200:
                    logger.warning("DDG HTTP %s for %r", resp.status, q)
                    return []
                html = await resp.text()
    except asyncio.TimeoutError:
        logger.warning("DDG timeout for %r", q)
        return []
    except Exception:  # noqa: BLE001
        logger.warning("DDG fetch failed for %r", q, exc_info=False)
        return []

    return _parse_html(html, limit=limit)


def _parse_html(html: str, *, limit: int) -> List[Dict[str, str]]:
    if not html:
        return []
    titles = _RESULT_LINK_RE.findall(html)
    snippets = _RESULT_SNIPPET_RE.findall(html)
    out: List[Dict[str, str]] = []
    for i, (href, raw_title) in enumerate(titles):
        if i >= limit:
            break
        title = unescape(_strip_tags(raw_title))[:200]
        snippet = ""
        if i < len(snippets):
            snippet = unescape(_strip_tags(snippets[i]))[:300]
        url = _decode_ddg_link(href)
        if not title or not url:
            continue
        out.append({"title": title, "snippet": snippet, "url": url})
    return out
