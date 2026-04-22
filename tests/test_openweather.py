"""Offline tests for the OpenWeatherMap parser.

We feed `parse_current` a realistic JSON payload and check the shape,
emoji mapping, comfort index clamping and graceful handling of missing
fields. No network.
"""

from __future__ import annotations

from metrics.openweather import parse_current


def _raw_payload(main: str = "Clear", description: str = "ясно") -> dict:
    return {
        "weather": [{"main": main, "description": description}],
        "main": {"temp": 21.4, "feels_like": 20.1, "humidity": 55},
        "wind": {"speed": 3.2, "deg": 180},
        "clouds": {"all": 5},
    }


def test_parse_clear_weather_maps_to_sun_emoji():
    out = parse_current(_raw_payload())
    assert out["condition_emoji"] == "☀️"
    assert out["temperature"] == 21.4
    assert out["feels_like"] == 20.1
    assert out["humidity"] == 55
    assert out["wind_speed"] == 3.2
    assert out["condition"] == "Ясно"
    # Comfort should be near peak (21°C, 55%, 3 m/s)
    assert 0.85 <= out["comfort_index"] <= 1.0


def test_parse_rain_maps_to_rain_emoji():
    out = parse_current(_raw_payload(main="Rain", description="дождь"))
    assert out["condition_emoji"] == "🌧️"
    assert out["condition"] == "Дождь"


def test_parse_unknown_main_falls_back_to_thermometer():
    out = parse_current(_raw_payload(main="Tsunami", description=""))
    assert out["condition_emoji"] == "🌡️"


def test_parse_missing_fields_does_not_raise():
    out = parse_current({})
    assert out["temperature"] == 0.0
    assert out["humidity"] == 0
    # comfort near worst case
    assert 0.0 <= out["comfort_index"] <= 0.6
    assert out["condition_emoji"] == "🌡️"


def test_comfort_drops_with_extreme_temperature():
    hot = parse_current(
        {
            "weather": [{"main": "Clear", "description": "жарко"}],
            "main": {"temp": 40.0, "feels_like": 42.0, "humidity": 55},
            "wind": {"speed": 3.0},
        }
    )
    cold = parse_current(
        {
            "weather": [{"main": "Snow", "description": "мороз"}],
            "main": {"temp": -20.0, "feels_like": -28.0, "humidity": 60},
            "wind": {"speed": 3.0},
        }
    )
    assert hot["comfort_index"] < 0.65
    assert cold["comfort_index"] < 0.5


def test_raw_payload_is_passed_through():
    raw = _raw_payload()
    out = parse_current(raw)
    assert out["raw"] == raw
