"""AI-powered enrichment layer.

Uses DeepSeek (OpenAI-compatible Chat Completions API) to tag collected
news items with sentiment, category, severity and a short summary.
"""

from .deepseek_client import DeepSeekClient, DeepSeekError
from .enricher import NewsEnricher

__all__ = ["DeepSeekClient", "DeepSeekError", "NewsEnricher"]
