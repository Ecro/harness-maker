"""Contract render test for the review-grade-criteria surfacing hardening.

Why a contract-style render test (not a bare grep): the /hm:review grade and
the consensus filter are PROSE executed by an LLM — no Python computes them, so
the only enforceable guarantee is that the rendered command SHIPS a coherent,
non-contradictory rule set. A plain presence-grep cannot catch prompt-level
contradictions (e.g. an unconditional "ready for wrapup" sitting next to a
"human_review_needed → STOP" gate), nor prove the grade table stayed
byte-unchanged. This renders the full harness through the real pipeline
(interview → synthesize → render) — same defense as
`test_render_stage_receipts` — and asserts the three ADR guarantees:

- ADR-001: manual-only / weak-consensus P0/P1 set human_review_needed even at
  grade >= threshold, without changing the grade letter (grade table invariant).
- ADR-003: path-differentiated halt — interactive/autopilot STOPs, loop proceeds.
- ADR-002: 4a/4c hard-seal — no cross-tier severity resolution remains that
  contradicts the "No tier bridging" hard rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


@pytest.fixture(scope="module")
def rendered_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render the full harness once per module (slow setup, fast asserts)."""
    out = tmp_path_factory.mktemp("rendered")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


@pytest.fixture(scope="module")
def review_body(rendered_root: Path) -> str:
    f = rendered_root / "commands" / "hm" / "review.md"
    assert f.is_file(), f"missing rendered command file: {f}"
    return f.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def arbiter_body(rendered_root: Path) -> str:
    f = rendered_root / "agents" / "consensus-arbiter.md"
    assert f.is_file(), f"missing rendered agent file: {f}"
    return f.read_text(encoding="utf-8")


# ── ADR-001: grade table byte-invariance (non-breaking) ─────────────────────

# Every row of the deterministic grade table must render verbatim — the whole
# point of "grade-letter non-breaking" is that these bytes never move.
_GRADE_ROWS = (
    "| 0 | 0 | **A** |",
    "| 0 | 1–2 | B |",
    "| 0 | ≥3 | C |",
    "| 1–2 | * | D |",
    "| ≥3 | * | F |",
)


@pytest.mark.parametrize("row", _GRADE_ROWS)
def test_grade_table_unchanged(review_body: str, row: str) -> None:
    assert row in review_body, f"grade table row drifted (non-breaking violated): {row!r}"


# ── ADR-001: surfacing rule present ─────────────────────────────────────────


def test_surfacing_rule_present(review_body: str) -> None:
    # The rule must reference the excluded-from-grade tags AND the flag it sets.
    assert "unverified severe" in review_body, "surfacing callout text missing"
    # Both excluded-from-grade tags must be named as the trigger.
    assert "manual-only" in review_body, "surfacing rule must name manual-only trigger"
    assert "weak-consensus" in review_body, "surfacing rule must name weak-consensus trigger"
    # It must be tied to human_review_needed, and explicitly fire at APPROVED.
    assert "human_review_needed" in review_body


# ── ADR-003: path-differentiated halt (interactive STOPs, loop proceeds) ────


def test_interactive_stop_is_conditional(review_body: str) -> None:
    # The OLD unconditional line must be gone — it silently told humans a
    # flagged-APPROVED review was wrapup-ready (the C1 critical).
    assert "`APPROVED` → ready for wrapup." not in review_body, (
        "unconditional 'ready for wrapup' still present adjacent to APPROVED"
    )
    # Interactive/autopilot path stops for a human on a flagged-APPROVED.
    assert "STOP for human review" in review_body


def test_loop_path_proceeds(review_body: str) -> None:
    # Loop mode must be explicitly documented as non-halting on the flag.
    assert "Loop mode: proceed" in review_body


def test_gate0_pass_names_third_state(review_body: str) -> None:
    # The Gate 0 receipt pass string must acknowledge the APPROVED +
    # human_review_needed=true state, or it re-hides the surfaced risk. Assert
    # the receipt-specific bytes (not a body-wide 'human_review_needed', which
    # appears in four other sections and would pass even if gate0_pass reverted).
    assert "## Emit Gate 0 receipt" in review_body, "Gate 0 receipt section missing"
    # This phrase is unique to the edited gate0_pass string.
    assert "still records `pass`" in review_body, (
        "gate0_pass no longer names the APPROVED+human_review_needed third state"
    )


# ── ADR-002: 4a/4c hard-seal (no cross-tier severity resolution) ────────────


def test_arbiter_keeps_no_tier_bridging(arbiter_body: str) -> None:
    assert "No tier bridging" in arbiter_body


def test_arbiter_removes_dead_cross_tier_resolution(arbiter_body: str) -> None:
    # The unreachable cross-tier rows must be gone — leaving them lets the LLM
    # synthesize a "middle" severity across tiers → tier bridging → grade change.
    assert "Middle of the scale" not in arbiter_body, (
        "dead 4c cross-tier 'Middle of the scale' row still present"
    )
    assert "when consensus has differing severities" not in arbiter_body, (
        "contradictory 4c 'differing severities' heading still present"
    )


def test_review_stage_4c_hard_sealed(review_body: str) -> None:
    # Same hard-seal in the review-stage copy of the consensus filter — parity
    # with the arbiter-side test (reject BOTH the dead row and the contradictory
    # heading, else a partial regression slips through one of the two copies).
    assert "Middle of the scale" not in review_body, (
        "review.md still carries the dead 4c 'Middle of the scale' row"
    )
    assert "when consensus has differing severities" not in review_body, (
        "review.md still carries the contradictory 4c 'differing severities' heading"
    )
