"""Тесты планировщика Джарвиса (chain-of-actions)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from ai.jarvis_planner import (
    MAX_STEPS, _fallback_synth, is_multistep_question, plan_steps, run_plan,
    synthesize,
)


# ---------------------------------------------------------------------------
# is_multistep_question — эвристика
# ---------------------------------------------------------------------------

def test_multistep_full_analysis():
    assert is_multistep_question("дай полный анализ города")
    assert is_multistep_question("Сделай обзор за неделю")
    assert is_multistep_question("Что не так в городе?")
    assert is_multistep_question("Как поднять УБ?")
    assert is_multistep_question("где беда сейчас?")


def test_multistep_short_simple_no():
    assert not is_multistep_question("привет")
    assert not is_multistep_question("?")
    assert not is_multistep_question("какая погода")


def test_multistep_empty():
    assert not is_multistep_question("")


# ---------------------------------------------------------------------------
# plan_steps
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, response, enabled=True):
        self.response = response
        self.enabled = enabled

    async def chat_json(self, system, user, **kw):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_plan_steps_returns_whitelisted():
    cli = _FakeClient({"steps": ["run_pulse", "run_forecast"]})
    out = asyncio.run(plan_steps("дай обзор", client=cli))
    assert out == ["run_pulse", "run_forecast"]


def test_plan_steps_strips_unknown_actions():
    cli = _FakeClient({"steps": ["run_pulse", "run_evil", "open_admin", "run_crisis"]})
    out = asyncio.run(plan_steps("обзор", client=cli))
    # open_admin и run_evil не в RUN_ACTIONS — выкинуты
    assert "run_pulse" in out
    assert "run_crisis" in out
    assert "run_evil" not in out
    assert "open_admin" not in out


def test_plan_steps_dedups():
    cli = _FakeClient({"steps": ["run_pulse", "run_pulse", "run_pulse"]})
    out = asyncio.run(plan_steps("?", client=cli))
    assert out == ["run_pulse"]


def test_plan_steps_caps_at_max():
    cli = _FakeClient({"steps": [
        "run_pulse", "run_forecast", "run_crisis",
        "run_loops", "run_benchmark",
    ]})
    out = asyncio.run(plan_steps("?", client=cli))
    assert len(out) <= MAX_STEPS


def test_plan_steps_disabled_client_returns_empty():
    cli = _FakeClient({"steps": ["run_pulse"]}, enabled=False)
    out = asyncio.run(plan_steps("?", client=cli))
    assert out == []


def test_plan_steps_invalid_response_returns_empty():
    cli = _FakeClient({"steps": "not-a-list"})
    out = asyncio.run(plan_steps("?", client=cli))
    assert out == []


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------

def test_synthesize_uses_llm_text():
    cli = _FakeClient({"text": "Город в норме, но УБ просел."})
    out = asyncio.run(synthesize(
        "обзор", [{"step": "run_pulse", "text": "пульс 72"}], client=cli,
    ))
    assert out == "Город в норме, но УБ просел."


def test_synthesize_falls_back_when_llm_disabled():
    cli = _FakeClient({"text": "wont be used"}, enabled=False)
    results = [
        {"step": "run_pulse", "text": "пульс 72"},
        {"step": "run_crisis", "text": "алертов нет"},
    ]
    out = asyncio.run(synthesize("обзор", results, client=cli))
    assert "пульс 72" in out
    assert "алертов нет" in out


def test_synthesize_empty_results():
    out = asyncio.run(synthesize("?", [], client=_FakeClient({"text": ""})))
    assert out == "Я ничего не выяснил."


def test_fallback_synth_caps_length():
    big = [{"step": "run_x", "text": "а" * 1000}]
    out = _fallback_synth(big)
    assert len(out) <= 700


# ---------------------------------------------------------------------------
# run_plan — полный цикл
# ---------------------------------------------------------------------------

def test_run_plan_full_cycle():
    plan_response = {"steps": ["run_pulse", "run_forecast"]}
    synth_response = {"text": "Пульс 72, прогноз стабильный."}

    class _Cli:
        enabled = True
        def __init__(self): self.calls = 0

        async def chat_json(self, system, user, **kw):
            self.calls += 1
            if self.calls == 1:
                return plan_response
            return synth_response

    async def fake_executor(action: str) -> Dict[str, Any]:
        return {"text": f"result of {action}", "sources": [action]}

    cli = _Cli()
    out = asyncio.run(run_plan("дай обзор", fake_executor, client=cli))
    assert out["steps"] == ["run_pulse", "run_forecast"]
    assert len(out["results"]) == 2
    assert out["results"][0]["text"] == "result of run_pulse"
    assert out["summary"] == "Пульс 72, прогноз стабильный."


def test_run_plan_no_steps_returns_empty():
    cli = _FakeClient({"steps": []})
    async def exec_fn(_): return {"text": "x"}
    out = asyncio.run(run_plan("привет", exec_fn, client=cli))
    assert out["steps"] == []
    assert out["results"] == []
    assert out["summary"] == ""
