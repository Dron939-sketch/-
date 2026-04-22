"""News enricher: LLM-based sentiment / category / severity / summary.

The enricher is best-effort by design — if DeepSeek is disabled, slow, or
returns malformed JSON, the original items flow through unchanged. Every
call is idempotent-safe: an item already carrying `enrichment` is skipped.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from collectors.base import CollectedItem
from config.settings import settings

from .cache import ResponseCache
from .deepseek_client import DeepSeekClient, DeepSeekError
from .prompts import CATEGORIES, build_enrichment_prompt

logger = logging.getLogger(__name__)


class NewsEnricher:
    def __init__(
        self,
        client: Optional[DeepSeekClient] = None,
        batch_size: Optional[int] = None,
        max_items: Optional[int] = None,
    ):
        if client is None:
            cache = ResponseCache.from_settings()
            client = DeepSeekClient(cache=cache)
        self.client = client
        self.batch_size = batch_size or settings.enrichment_batch_size
        self.max_items = max_items or settings.enrichment_max_items

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    async def enrich(self, items: Sequence[CollectedItem]) -> List[CollectedItem]:
        """Annotate the most recent `max_items` with sentiment/category/etc."""
        if not items:
            return list(items)
        if not self.enabled:
            logger.info("NewsEnricher: DeepSeek disabled, skipping enrichment")
            return list(items)

        targets = [it for it in items if it.enrichment is None][: self.max_items]
        if not targets:
            return list(items)

        by_id = {it.id: it for it in targets}
        for batch in _chunks(targets, self.batch_size):
            payload = _serialise_batch(batch)
            system, user = build_enrichment_prompt(payload)
            try:
                response = await self.client.chat_json(system, user)
            except DeepSeekError as exc:
                logger.warning("enrichment batch failed: %s", exc)
                continue
            _apply_response(response, by_id)

        return list(items)


def _chunks(seq: Sequence[CollectedItem], size: int) -> List[List[CollectedItem]]:
    return [list(seq[i : i + size]) for i in range(0, len(seq), size)]


def _serialise_batch(batch: Sequence[CollectedItem]) -> str:
    """Compact JSON payload for the user prompt.

    We only pass id / title / preview / source to keep prompts small.
    DeepSeek prices input tokens ~$0.14/M so a 20-item batch is fractions of
    a cent even with generous previews.
    """
    rows = []
    for it in batch:
        preview = (it.content or "").strip().replace("\n", " ")
        if len(preview) > 350:
            preview = preview[:350] + "…"
        rows.append(
            {
                "id": it.id,
                "source": f"{it.source_kind}:{it.source_handle}",
                "title": it.title,
                "preview": preview,
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def _apply_response(
    response: Dict[str, Any], by_id: Dict[str, CollectedItem]
) -> None:
    raw_items = response.get("items") if isinstance(response, dict) else None
    if raw_items is None and isinstance(response, list):
        raw_items = response
    if not isinstance(raw_items, list):
        logger.warning("enrichment response missing 'items' array: %r", response)
        return

    for row in raw_items:
        if not isinstance(row, dict):
            continue
        item_id = row.get("id")
        target = by_id.get(item_id)
        if target is None:
            continue
        target.enrichment = {
            "sentiment": _clamp(row.get("sentiment"), -1.0, 1.0),
            "category": _normalise_category(row.get("category")),
            "severity": _clamp(row.get("severity"), 0.0, 1.0),
            "summary": _clip_summary(row.get("summary")),
        }


def _clamp(value: Any, lo: float, hi: float) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f < lo:
        return lo
    if f > hi:
        return hi
    return f


def _normalise_category(raw: Any) -> str:
    if not isinstance(raw, str):
        return "other"
    cleaned = raw.strip().lower()
    return cleaned if cleaned in CATEGORIES else "other"


def _clip_summary(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    return text[:120]
