"""Unit tests for ai.deepseek_pricing.compute_cost_usd()."""

from __future__ import annotations

import os
from typing import Iterator

import pytest

from ai.deepseek_pricing import compute_cost_usd, get_pricing


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch) -> Iterator[None]:
    """Гарантируем, что env-переопределения не утекают между тестами."""
    for k in (
        "DEEPSEEK_PRICE_INPUT_HIT",
        "DEEPSEEK_PRICE_INPUT_MISS",
        "DEEPSEEK_PRICE_OUTPUT",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


def test_zero_tokens_zero_cost():
    assert compute_cost_usd(model="deepseek-chat") == 0.0


def test_chat_default_pricing_basic():
    # 1M output tokens × $0.42 = $0.42
    cost = compute_cost_usd(
        model="deepseek-chat", prompt_tokens=0, completion_tokens=1_000_000,
    )
    assert cost == 0.42


def test_chat_full_cache_miss_when_split_unknown():
    # Если cache_hit/miss не передан — весь промпт = miss (worst-case).
    # 1M prompt × $0.28 + 0 output = $0.28
    cost = compute_cost_usd(
        model="deepseek-chat", prompt_tokens=1_000_000, completion_tokens=0,
    )
    assert cost == 0.28


def test_chat_with_cache_split():
    # 800k cache_hit × $0.028 = $0.0224
    # 200k cache_miss × $0.28 = $0.056
    # 100k output × $0.42 = $0.042
    # total = 0.1204
    cost = compute_cost_usd(
        model="deepseek-chat",
        prompt_tokens=1_000_000,
        completion_tokens=100_000,
        prompt_cache_hit_tokens=800_000,
        prompt_cache_miss_tokens=200_000,
    )
    assert cost == pytest.approx(0.1204, abs=1e-6)


def test_reasoner_more_expensive_than_chat():
    args = dict(prompt_tokens=1_000_000, completion_tokens=500_000,
                prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=1_000_000)
    chat_cost = compute_cost_usd(model="deepseek-chat", **args)
    reasoner_cost = compute_cost_usd(model="deepseek-reasoner", **args)
    assert reasoner_cost > chat_cost


def test_unknown_model_falls_back_to_chat_pricing():
    chat_cost = compute_cost_usd(
        model="deepseek-chat", prompt_tokens=0, completion_tokens=1_000_000,
    )
    fallback_cost = compute_cost_usd(
        model="some-unknown-model", prompt_tokens=0, completion_tokens=1_000_000,
    )
    assert chat_cost == fallback_cost


def test_env_override_takes_effect(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_PRICE_OUTPUT", "1.00")
    cost = compute_cost_usd(
        model="deepseek-chat", prompt_tokens=0, completion_tokens=1_000_000,
    )
    assert cost == 1.00


def test_pricing_dict_shape():
    p = get_pricing("deepseek-chat")
    assert set(p.keys()) == {"input_hit_per_m", "input_miss_per_m", "output_per_m"}
    assert all(isinstance(v, float) and v > 0 for v in p.values())


def test_implicit_cache_miss_when_only_hit_passed():
    # 1M prompt; 300k hit; miss = 700k неявно
    cost = compute_cost_usd(
        model="deepseek-chat",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        prompt_cache_hit_tokens=300_000,
    )
    expected = 300_000/1_000_000 * 0.028 + 700_000/1_000_000 * 0.28
    assert cost == pytest.approx(expected, abs=1e-6)


def test_negative_inputs_treated_as_zero():
    # Не должен крашить, даже если API вернёт что-то кривое.
    cost = compute_cost_usd(
        model="deepseek-chat",
        prompt_tokens=-100, completion_tokens=-100,
    )
    assert cost >= 0
