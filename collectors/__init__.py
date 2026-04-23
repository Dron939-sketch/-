"""Data collectors package.

Heavy transports (aiohttp, telethon, feedparser) are imported lazily so
that `from collectors.base import CollectedItem` works even in minimal
environments (CI / tests) that don't install the full dependency set.
"""

from .base import CollectedItem, BaseCollector

__all__ = [
    "CollectedItem",
    "BaseCollector",
    "TelegramCollector",
    "VKCollector",
    "NewsCollector",
    "AppealsCollector",
    "AIPulseCollector",
]


def __getattr__(name):  # PEP 562
    if name == "TelegramCollector":
        from .telegram_collector import TelegramCollector
        return TelegramCollector
    if name == "VKCollector":
        from .vk_collector import VKCollector
        return VKCollector
    if name == "NewsCollector":
        from .news_collector import NewsCollector
        return NewsCollector
    if name == "AppealsCollector":
        from .appeals_collector import AppealsCollector
        return AppealsCollector
    if name == "AIPulseCollector":
        from .ai_pulse import AIPulseCollector
        return AIPulseCollector
    raise AttributeError(f"module 'collectors' has no attribute {name!r}")
