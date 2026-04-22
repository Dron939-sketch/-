"""Shared primitives for all collectors."""

from __future__ import annotations

import abc
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CollectedItem:
    """Normalised record emitted by every collector.

    The `id` is a deterministic hash of (source, external_id|url|text) so
    re-running a collector against the same source is idempotent at the
    storage layer.
    """

    source_kind: str
    source_handle: str
    title: str
    content: str
    published_at: datetime
    url: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        basis = f"{self.source_kind}:{self.source_handle}:{self.url or self.title}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_kind": self.source_kind,
            "source_handle": self.source_handle,
            "title": self.title,
            "content": self.content,
            "published_at": self.published_at.isoformat(),
            "url": self.url,
            "author": self.author,
            "category": self.category,
        }


class BaseCollector(abc.ABC):
    """Abstract async collector.

    Subclasses implement `collect()` and (optionally) `close()` for cleanup.
    """

    def __init__(self, city_name: str):
        self.city_name = city_name

    @abc.abstractmethod
    async def collect(self, since: Optional[datetime] = None) -> List[CollectedItem]:
        ...

    async def close(self) -> None:
        return None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=timezone.utc)
