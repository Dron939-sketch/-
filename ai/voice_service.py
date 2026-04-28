"""Голосовой сервис: STT (Deepgram) + TTS (Yandex SpeechKit).

Адаптация из проекта Frederick — оставлена только синхронная HTTP-часть
для MVP «Душа города»: запрос через POST, ответ — текст + base64-MP3.
WebSocket-стриминг и VAD добавим Phase 2, если будет нужно.

Конфигурация — через env:
  DEEPGRAM_API_KEY  — STT (https://deepgram.com)
  YANDEX_API_KEY    — TTS (https://cloud.yandex.ru/services/speechkit)
  CITY_SOUL_VOICE   — голос Yandex (default: filipp; альтернативы:
                      ermil, alena, jane, omazh, zahar, oksana, marina)
  CITY_SOUL_SPEED   — скорость 0.5..2.0 (default 0.95)
  CITY_SOUL_EMOTION — neutral / good / evil (default neutral)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"
YANDEX_TTS_API_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

# Пред-настройки голоса. Можно переопределить через env CITY_SOUL_VOICE и т.д.
DEFAULT_VOICE = os.getenv("CITY_SOUL_VOICE", "filipp")
DEFAULT_SPEED = float(os.getenv("CITY_SOUL_SPEED", "0.95"))
DEFAULT_EMOTION = os.getenv("CITY_SOUL_EMOTION", "neutral")


# ---------------------------------------------------------------------------
# Текстовая нормализация перед TTS
# ---------------------------------------------------------------------------

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


_TEMP_RE = re.compile(r"([+\-−]?)\s*(\d+)\s*°\s*[CС]", re.IGNORECASE)


def expand_temperatures(text: str) -> str:
    """Раскрыть `+12°C` → `плюс 12 градусов Цельсия` для голоса.
    Применяется как к Fish Audio TTS, так и к финальному text-ответу,
    который потом озвучивается speechSynthesis на фронте.
    Если text пустой/без °C — возвращает без изменений."""
    if not text:
        return text
    return _TEMP_RE.sub(_expand_temperature, text)


# ---------------------------------------------------------------------------
# Расширение единиц измерения для голоса
# ---------------------------------------------------------------------------

def _decline_ru(n: int, forms: tuple) -> str:
    """Склонение по русским правилам: forms = (один, два, пять).

    Примеры:
      _decline_ru(1, ('рубль', 'рубля', 'рублей')) → 'рубль'
      _decline_ru(3, ...)  → 'рубля'
      _decline_ru(11, ...) → 'рублей'
      _decline_ru(21, ...) → 'рубль'
    """
    last = abs(n) % 10
    last_two = abs(n) % 100
    if 11 <= last_two <= 14:
        return forms[2]
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


# Единицы измерения: regex → (число-группа, формы склонения)
_UNIT_RULES = [
    # «25%» → «25 процентов»
    (re.compile(r"(\d+)\s*%"),                          ("процент", "процента", "процентов")),
    # «10 руб», «10 руб.», «10 рубля» — нормализуем все в правильное склонение
    (re.compile(r"(\d+)\s*руб\b\.?",   re.IGNORECASE),  ("рубль", "рубля", "рублей")),
    # Скорость «10 км/ч»
    (re.compile(r"(\d+)\s*км/ч",       re.IGNORECASE),  ("километр в час", "километра в час", "километров в час")),
    # Скорость ветра «3 м/с»
    (re.compile(r"(\d+)\s*м/с",        re.IGNORECASE),  ("метр в секунду", "метра в секунду", "метров в секунду")),
    # «5 млн» → миллионов
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*млн\b", re.IGNORECASE),
     ("миллион", "миллиона", "миллионов")),
    # «3 млрд»
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*млрд\b", re.IGNORECASE),
     ("миллиард", "миллиарда", "миллиардов")),
    # «10 тыс»
    (re.compile(r"(\d+(?:[.,]\d+)?)\s*тыс\b\.?", re.IGNORECASE),
     ("тысяча", "тысячи", "тысяч")),
]


def expand_units(text: str) -> str:
    """Раскрыть короткие единицы в человеческие слова: «25%» → «25 процентов»,
    «10 руб» → «10 рублей», «3 м/с» → «3 метра в секунду» и т.п.

    Пробелы между числом и единицей могут быть или отсутствовать. Регистр
    игнорируется. Дробные числа («1,5 млн») для млн/млрд/тыс — берём
    integer part для склонения, чтобы не ошибиться (1.5 → как «много» →
    миллионов, что правильно)."""
    if not text:
        return text

    def replace(match: "re.Match[str]", forms: tuple) -> str:
        raw = match.group(1)
        # Парсим число — для дробных берём максимальный сегмент
        try:
            n = int(float(raw.replace(",", ".")))
        except ValueError:
            n = 0
        # Если дробь (1.5) — в речи это «полтора», но мы упрощаем:
        # выбираем форму как для 5+ чтобы было нейтрально.
        if "." in raw or "," in raw:
            n = 5  # форсируем "много"-форму ("полтора миллиона" — миллионОВ нет, но "полтора миллионА" не нейтр.; компромисс)
        word = _decline_ru(n, forms)
        return f"{raw} {word}"

    out = text
    for rx, forms in _UNIT_RULES:
        out = rx.sub(lambda m, f=forms: replace(m, f), out)
    return out


def _expand_temperature(match: "re.Match[str]") -> str:
    """+12°C  → плюс 12 градусов Цельсия
       -3°C   → минус 3 градуса Цельсия
       0°C    → 0 градусов Цельсия
       12°C   → 12 градусов Цельсия

    Склонение «градус/градуса/градусов» делаем по правилам русского:
      1, 21, 31, ... → градус
      2-4, 22-24, … → градуса
      все остальные (включая 11-14) → градусов
    """
    sign_raw = match.group(1) or ""
    n = int(match.group(2))
    if sign_raw in ("-", "−"):
        sign = "минус "
    elif sign_raw == "+":
        sign = "плюс "
    else:
        sign = ""
    # Склонение
    last = n % 10
    last_two = n % 100
    if 11 <= last_two <= 14:
        word = "градусов"
    elif last == 1:
        word = "градус"
    elif 2 <= last <= 4:
        word = "градуса"
    else:
        word = "градусов"
    return f"{sign}{n} {word} Цельсия"


def normalize_for_tts(text: str) -> str:
    """Чистим текст для Yandex TTS: убираем эмодзи / спецсимволы / Markdown,
    раскрываем «°C» в «градусов Цельсия», добавляем точку в конце."""
    if not text:
        return "Я тут. Расскажите ещё."
    t = _EMOJI_RE.sub("", text)
    # Markdown bold/italic/code
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    # Скобки-ремарки (вздыхает) (с улыбкой) — содержат кириллицу
    t = re.sub(r"\([^)]*[а-яёА-ЯЁ][^)]*\)\s*", "", t)
    # «+12°C» → «плюс 12 градусов Цельсия» — иначе TTS читает «12 С».
    t = _TEMP_RE.sub(_expand_temperature, t)
    # «25%», «10 руб», «3 м/с» → словами с правильным склонением.
    t = expand_units(t)
    # Спецсимволы, которые TTS не любит
    t = re.sub(r"[#_`~<>|@$%^&+={}\\]", "", t)
    # Кириллица строчная + заглавная подряд → пробел между ними
    t = re.sub(r"([а-яё])([А-ЯЁ])", r"\1 \2", t)
    # Пунктуация без пробела за ней
    t = re.sub(r"([.!?,;:])([^\s\d\)\]\}])", r"\1 \2", t)
    # Множественные пробелы
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return "Я тут. Расскажите ещё."
    if t[-1] not in ".!?":
        t += "."
    if len(t) > 4500:
        t = t[:4500] + "..."
    return t


# ---------------------------------------------------------------------------
# HTTP client (singleton)
# ---------------------------------------------------------------------------

_http_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        async with _client_lock:
            if _http_client is None:
                _http_client = httpx.AsyncClient(
                    limits=httpx.Limits(
                        max_keepalive_connections=10, max_connections=50,
                    ),
                    timeout=httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=None),
                    follow_redirects=True,
                )
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# STT — Deepgram
# ---------------------------------------------------------------------------

_DEEPGRAM_MIME = {
    "webm": "audio/webm",
    "ogg":  "audio/ogg",
    "wav":  "audio/wav",
    "mp3":  "audio/mpeg",
    "mp4":  "audio/mp4",
    "m4a":  "audio/mp4",
}


async def speech_to_text(
    audio_bytes: bytes, audio_format: str = "webm",
) -> Optional[str]:
    """Распознать аудио через Deepgram nova-2. Возвращает чистый текст
    или None при ошибке/пустом результате. Не бросает исключений.
    """
    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not api_key:
        logger.warning("DEEPGRAM_API_KEY не настроен — STT отключён")
        return None
    if not audio_bytes or len(audio_bytes) < 500:
        return None
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": _DEEPGRAM_MIME.get(audio_format, "audio/webm"),
    }
    params = {
        "model": "nova-2",
        "language": "ru",
        "punctuate": "true",
        "smart_format": "true",
    }
    try:
        client = await _get_http_client()
        resp = await client.post(
            DEEPGRAM_API_URL, headers=headers, params=params, content=audio_bytes,
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning("Deepgram %s: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        transcript = (
            data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "") or ""
        )
        return transcript.strip() or None
    except Exception:  # noqa: BLE001
        logger.exception("Deepgram STT failed")
        return None


# ---------------------------------------------------------------------------
# TTS — Yandex SpeechKit
# ---------------------------------------------------------------------------

async def text_to_speech(
    text: str,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    emotion: Optional[str] = None,
) -> Optional[bytes]:
    """Синтез речи через Yandex. Возвращает MP3-bytes или None.
    Не бросает исключений — все ошибки логируются.
    """
    api_key = os.getenv("YANDEX_API_KEY", "").strip()
    if not api_key:
        logger.warning("YANDEX_API_KEY не настроен — TTS отключён")
        return None
    cleaned = normalize_for_tts(text)
    if not cleaned:
        return None
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data: Dict[str, Any] = {
        "text":    cleaned,
        "lang":    "ru-RU",
        "voice":   voice or DEFAULT_VOICE,
        "speed":   str(speed if speed is not None else DEFAULT_SPEED),
        "emotion": emotion or DEFAULT_EMOTION,
        "format":  "mp3",
    }
    try:
        client = await _get_http_client()
        resp = await client.post(
            YANDEX_TTS_API_URL, headers=headers, data=data, timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning("Yandex TTS %s: %s", resp.status_code, resp.text[:200])
            return None
        return resp.content
    except Exception:  # noqa: BLE001
        logger.exception("Yandex TTS failed")
        return None
