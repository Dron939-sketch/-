"""Minimal OpenWeatherMap async client.

Returns a dict in the exact shape that `db.queries.upsert_weather`
expects (plus a `ts` timestamp). The legacy `weather_collector.py` is
still imported by a few bits of the old core, so we don't touch it —
this module is the one the scheduler talks to.

If `OPENWEATHER_API_KEY` is missing or the network call fails, we
return None and callers skip the DB write.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)

_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)


_EMOJI_BY_MAIN = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Haze": "🌫️",
    "Smoke": "🌫️",
    "Dust": "🌫️",
    "Sand": "🌫️",
    "Ash": "🌫️",
    "Squall": "💨",
    "Tornado": "🌪️",
}


def _emoji_for(main: str) -> str:
    return _EMOJI_BY_MAIN.get(main, "🌡️")


def _comfort_index(temp: float, humidity: float, wind: float) -> float:
    """Crude 0..1 comfort heuristic. Peaks at 21°C, 50%, 3 m/s."""
    temp_s = 1.0 - min(abs(temp - 21.0) / 20.0, 1.0)
    hum_s = 1.0 - min(abs(humidity - 50.0) / 30.0, 1.0)
    wind_s = 1.0 - min(abs(wind - 3.0) / 8.0, 1.0)
    return round(temp_s * 0.5 + hum_s * 0.3 + wind_s * 0.2, 3)


async def fetch_current(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Fetch current weather for coordinates. Returns a DB-ready dict."""
    if getattr(settings, "demo_mode", False):
        return None
    api_key = settings.openweather_api_key
    if not api_key:
        logger.info("OPENWEATHER_API_KEY not set — skipping weather fetch")
        return None

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "lang": "ru",
    }

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_CURRENT_URL, params=params) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:160]
                    logger.warning("OWM %s: %s", resp.status, body)
                    return None
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("OpenWeatherMap call failed", exc_info=False)
        return None

    return parse_current(data)


def parse_current(data: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a raw OWM payload into the dict we store. Pure, testable."""
    main_block = data.get("main") or {}
    wind_block = data.get("wind") or {}
    weather_list = data.get("weather") or [{}]
    first = weather_list[0] if weather_list else {}

    main = first.get("main", "")
    description = first.get("description") or main
    temp = float(main_block.get("temp", 0.0))
    feels = float(main_block.get("feels_like", temp))
    humidity = int(main_block.get("humidity", 0))
    wind_speed = float(wind_block.get("speed", 0.0))

    return {
        "ts": datetime.now(tz=timezone.utc),
        "temperature": round(temp, 1),
        "feels_like": round(feels, 1),
        "humidity": humidity,
        "wind_speed": round(wind_speed, 1),
        "condition": description.capitalize() if description else main,
        "condition_emoji": _emoji_for(main),
        "comfort_index": _comfort_index(temp, humidity, wind_speed),
        "raw": data,
    }
