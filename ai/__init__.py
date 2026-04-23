"""AI-powered enrichment layer."""

from .cache import ResponseCache, make_cache_key
from .deepseek_client import DeepSeekClient, DeepSeekError
from .enricher import NewsEnricher
from .narratives import NarrativeSet, Variant, generate as generate_narratives

__all__ = [
    "DeepSeekClient",
    "DeepSeekError",
    "NewsEnricher",
    "NarrativeSet",
    "Variant",
    "generate_narratives",
    "ResponseCache",
    "make_cache_key",
]
