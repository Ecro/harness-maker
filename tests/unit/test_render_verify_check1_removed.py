"""SPEC S5 / AC-005 (PLAN-workflow-steps-vs-model-capability ADR-003): `/hm:verify` keeps its
deterministic checks and its drift-verdict read (Check 1a), and no longer carries the LLM
"PLAN/SPEC satisfaction" coverage judgement (Check 1b).

Negative golden: the 0.55.0 Check 1 title and the 1b body markers. Positive goldens: the check
titles fixed from the pre-change render — Checks 1–6 on BOTH strictness arms. Check 6 used to be
gated to the strict arm; SPEC-dev-mode-removal ADR-005 renders it everywhere (it reports without
stopping at `warn`), so both arms now carry its title and the `spec_need` calls. What differs
between the arms is the STOP language, which `test_render_strictness_surface.py` pins
differentially.

Phase A.4 justification: `test_check_1_still_leads_the_numbered_procedure` PASSES against the
unmodified template — it is a preservation invariant (over-deletion guard) that goes red the
moment the Check 1 heading or the `Run Check 1.` step is removed, and its RED positive sibling
`test_verify_has_no_llm_satisfaction_check` forces the edit into existence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.strictness import Strictness
from harness_maker.synthesize import synthesize

REMOVED = (
    "### Check 1 — PLAN/SPEC satisfaction + drift verdict",
    "1b. PLAN/SPEC coverage",
    "proceed to 1b",
    "FAIL when: any scenario lacks coverage AND lacks waiver",
    "PLAN/SPEC satisfaction",  # bare phrase — the worked-example stdout carried it after the rename
    "+ JSON record",  # the retired verify JSONL ledger
    "record_path",
)
COMMON_CHECK_TITLES = (
    "### Check 1 — Drift verdict (REVIEW present)",
    "### Check 2 — Regression smoke",
    "### Check 3 — Structural delta",
    "### Check 4 — Security",
    "### Check 5 — Worktree merge cleanliness",
)
CHECK_6_TITLE = "### Check 6 — SPEC requirement"
ARMS = [(p, d) for p in Preset for d in ("warn", "block")]


def _verify(tmp: Path, preset: Preset, strictness: Strictness) -> str:
    answers = InterviewAnswers(preset=preset, strictness=strictness, targets=[Target.CLAUDE_CODE])
    render(
        synthesize(ProjectProfile(), answers, preset=preset), tmp, freeze_time=DEFAULT_FREEZE_TIME
    )
    return (tmp / "commands" / "hm" / "verify.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(("preset", "strictness"), ARMS, ids=[f"{p.value}-{d}" for p, d in ARMS])
def test_verify_has_no_llm_satisfaction_check(
    tmp_path: Path, preset: Preset, strictness: Strictness
) -> None:
    body = _verify(tmp_path, preset, strictness)
    for marker in REMOVED:
        assert marker not in body, f"{marker!r} survived the Check 1b deletion"
    for title in COMMON_CHECK_TITLES:
        assert title in body, f"deterministic check dropped: {title}"
    assert "drift_verdict" in body, "Check 1a's REVIEW frontmatter read must survive"
    assert "run /hm:review first" in body
    assert CHECK_6_TITLE in body, f"Check 6 must render at {strictness}"
    assert "spec_need op-check" in body
    assert "spec_need waiver-check" in body


def test_check_1_still_leads_the_numbered_procedure(tmp_path: Path) -> None:
    """The `Check 1 —` prefix and the `Run Check 1` step survive (test_verify_delegation pins
    the heading's position; ADR-003 keeps the numbering 2–6 untouched)."""
    body = _verify(tmp_path, Preset.PRODUCTION, "block")
    assert body.index("### Check 1 —") < body.index("### Check 2 —")
    assert "Run Check 1." in body
