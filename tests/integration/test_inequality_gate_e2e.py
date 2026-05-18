"""E2E gate smoke test (PLAN F7, INTEGRATION=1 gated).

Skipped by default in CI per CLAUDE.md test policy — run with
`INTEGRATION=1 uv run pytest tests/integration/test_inequality_gate_e2e.py`
to exercise the gate against realistic candidate distributions.

Note: this test uses a deterministic mock mechanism even under INTEGRATION=1
because the real LLM wiring (F6 + downstream slash-command level) is invoked
by the interview agent at runtime, not directly from a pytest harness. The
test's value is in catching cross-module breakage between F2/F3/F4 (config,
common_ground, EIG, inequality_gate) when callers wire them end-to-end.
"""

from __future__ import annotations

import os

import pytest

from harness_maker.eig import ScoringContext, clear_eig_cache
from harness_maker.inequality_gate import Candidate, GateConfig, apply_inequality_gate

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="requires Claude subscription; gate with INTEGRATION=1",
)


def test_e2e_full_inequality_pipeline() -> None:
    """End-to-end gate evaluation across all 5 terms with a mock mechanism."""
    clear_eig_cache()

    def importance_proxy(q: str, ctx: ScoringContext) -> float:
        # Realistic shape: high EIG for novel slots, low for trivial ones.
        return 0.75 if "important" in q.lower() else 0.25

    candidates = [
        Candidate(
            slot="ImportantSetting",
            question="What is the important constraint here?",
            is_open_ended=True,
        ),
        Candidate(slot="TrivialSetting", question="What database engine?"),
    ]
    sources = {
        "CLAUDE.md": "no relevant slot info",
    }

    results = apply_inequality_gate(
        candidates,
        sources,
        GateConfig(),
        eig_mechanism=importance_proxy,
    )
    assert results, "gate returned empty result list"
    important = next(r for r in results if r.candidate.slot == "ImportantSetting")
    assert important.overall_pass is True, "high-EIG novel candidate should pass"
    trivial = next(r for r in results if r.candidate.slot == "TrivialSetting")
    assert trivial.overall_pass is False, "low-EIG candidate should fail EIG term"


def test_e2e_kill_switch_disables_llm_inference_path() -> None:
    """Setting llm_inference_enabled=false bypasses LLM common-ground inference."""
    clear_eig_cache()
    cfg = GateConfig(llm_inference_enabled=False)
    candidate = Candidate(slot="Engine", question="Which engine?")
    sources = {"CLAUDE.md": "we use postgres but it's flexible"}

    llm_calls: list[str] = []

    def must_not_be_called(slot: str, ctx: dict) -> float:  # type: ignore[type-arg]
        llm_calls.append(slot)
        return 0.99

    apply_inequality_gate(
        [candidate],
        sources,
        cfg,
        eig_mechanism=lambda q, c: 0.7,
        cg_llm_fn=must_not_be_called,
    )
    assert llm_calls == [], (
        "kill-switch must prevent LLM-inference call when llm_inference_enabled=False"
    )
