"""CityMind configuration package.

Exposes application settings, city-specific data and source lists.
"""

from .settings import settings
from .cities import CITIES, KOLOMNA, get_city
from .sources import get_sources_for_city

__all__ = ["settings", "CITIES", "KOLOMNA", "get_city", "get_sources_for_city"]
