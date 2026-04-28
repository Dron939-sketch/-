"""Тарифы DeepSeek API + расчёт стоимости.

Источники:
  - https://api-docs.deepseek.com/quick_start/pricing  (официально)
  - https://www.tldl.io/resources/deepseek-api-pricing  (mirror на 2026)
  - https://venturebeat.com/ai/deepseeks-new-v3-2-exp-model-cuts-api-pricing
    (анонс снижения V3.2-Exp до $0.028 / $0.28 / $0.42)

По умолчанию стоит V3.2-Exp pricing (актуально на апрель 2026).
Поскольку DeepSeek пересматривает цены раз в полгода-год, переменные
вынесены в env: DEEPSEEK_PRICE_INPUT_HIT, DEEPSEEK_PRICE_INPUT_MISS,
DEEPSEEK_PRICE_OUTPUT (значения в USD за 1M токенов).

`compute_cost_usd()` принимает usage dict из API ответа
({prompt_tokens, completion_tokens, prompt_cache_hit_tokens,
prompt_cache_miss_tokens}) и возвращает стоимость в долларах с
6 знаками после запятой.
"""

from __future__ import annotations

import os
from typing import Dict, Optional


# Default pricing — DeepSeek V3.2-Exp (USD per 1M tokens).
_DEFAULT_INPUT_HIT_USD_PER_M = 0.028
_DEFAULT_INPUT_MISS_USD_PER_M = 0.28
_DEFAULT_OUTPUT_USD_PER_M = 0.42

# Per-model overrides — если в env стоит deepseek-reasoner, цена выше.
_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "deepseek-chat": {
        "input_hit_per_m":  _DEFAULT_INPUT_HIT_USD_PER_M,
        "input_miss_per_m": _DEFAULT_INPUT_MISS_USD_PER_M,
        "output_per_m":     _DEFAULT_OUTPUT_USD_PER_M,
    },
    "deepseek-reasoner": {
        "input_hit_per_m":  0.14,
        "input_miss_per_m": 0.55,
        "output_per_m":     2.19,
    },
}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_pricing(model: str) -> Dict[str, float]:
    """Возвращает {input_hit_per_m, input_miss_per_m, output_per_m} в USD."""
    base = _MODEL_PRICING.get(model, _MODEL_PRICING["deepseek-chat"])
    return {
        "input_hit_per_m":  _env_float("DEEPSEEK_PRICE_INPUT_HIT",  base["input_hit_per_m"]),
        "input_miss_per_m": _env_float("DEEPSEEK_PRICE_INPUT_MISS", base["input_miss_per_m"]),
        "output_per_m":     _env_float("DEEPSEEK_PRICE_OUTPUT",     base["output_per_m"]),
    }


def compute_cost_usd(
    *,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    prompt_cache_hit_tokens: Optional[int] = None,
    prompt_cache_miss_tokens: Optional[int] = None,
) -> float:
    """Стоимость одного вызова.

    Если переданы только prompt_tokens (без cache_hit/miss) — считаем
    весь prompt как cache miss (worst-case, чтобы не занижать стоимость).
    """
    p = get_pricing(model)
    # Любая отрицательная цифра — артефакт кривого ответа, считаем как 0.
    cache_hit = max(0, int(prompt_cache_hit_tokens or 0))
    cache_miss = (
        max(0, int(prompt_cache_miss_tokens))
        if prompt_cache_miss_tokens is not None else None
    )
    total_prompt = max(0, int(prompt_tokens or 0))

    if cache_miss is None:
        # Если cache_hit известен, оставшийся prompt — это miss.
        cache_miss = max(0, total_prompt - cache_hit)

    completion = max(0, int(completion_tokens or 0))

    cost = (
        cache_hit  / 1_000_000 * p["input_hit_per_m"]
        + cache_miss / 1_000_000 * p["input_miss_per_m"]
        + completion / 1_000_000 * p["output_per_m"]
    )
    return round(cost, 6)
