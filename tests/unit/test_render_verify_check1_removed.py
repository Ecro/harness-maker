"""SPEC S5 / AC-005 (PLAN-workflow-steps-vs-model-capability ADR-003): `/hm:verify` keeps its
deterministic checks and its drift-verdict read (Check 1a), and no longer carries the LLM
"PLAN/SPEC satisfaction" coverage judgement (Check 1b).

Negative golden: the 0.55.0 Check 1 title and the 1b body markers. Positive goldens: the check
titles fixed from the pre-change render — Checks 1–5 on BOTH dev_mode arms, Check 6 on the
spec-driven arm only (`verify.md.j2` gates it), with the task-driven arm asserted NOT to carry
`spec_need`, mirroring `test_instruction_preservation.py`'s arm-distinguishing check. A single
tuple asserted over both arms would fail on task-driven where Check 6 is legitimately absent.

Phase A.4 justification: `test_check_1_still_leads_the_numbered_procedure` PASSES against the
unmodified template — it is a preservation invariant (over-deletion guard) that goes red the
moment the Check 1 heading or the `Run Check 1.` step is removed, and its RED positive sibling
`test_verify_has_no_llm_satisfaction_check` forces the edit into existence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
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
SPEC_DRIVEN_ONLY_TITLES = ("### Check 6 — SPEC requirement",)
ARMS = [(p, d) for p in Preset for d in DevMode]


def _verify(tmp: Path, preset: Preset, dev_mode: DevMode) -> str:
    answers = InterviewAnswers(preset=preset, dev_mode=dev_mode, targets=[Target.CLAUDE_CODE])
    render(
        synthesize(ProjectProfile(), answers, preset=preset), tmp, freeze_time=DEFAULT_FREEZE_TIME
    )
    return (tmp / "commands" / "hm" / "verify.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("preset", "dev_mode"), ARMS, ids=[f"{p.value}-{d.value}" for p, d in ARMS]
)
def test_verify_has_no_llm_satisfaction_check(
    tmp_path: Path, preset: Preset, dev_mode: DevMode
) -> None:
    body = _verify(tmp_path, preset, dev_mode)
    for marker in REMOVED:
        assert marker not in body, f"{marker!r} survived the Check 1b deletion"
    for title in COMMON_CHECK_TITLES:
        assert title in body, f"deterministic check dropped: {title}"
    assert "drift_verdict" in body, "Check 1a's REVIEW frontmatter read must survive"
    assert "run /hm:review first" in body
    if dev_mode is DevMode.SPEC_DRIVEN:
        for title in SPEC_DRIVEN_ONLY_TITLES:
            assert title in body
    else:
        assert "spec_need" not in body
        for title in SPEC_DRIVEN_ONLY_TITLES:
            assert title not in body


def test_check_1_still_leads_the_numbered_procedure(tmp_path: Path) -> None:
    """The `Check 1 —` prefix and the `Run Check 1` step survive (test_verify_delegation pins
    the heading's position; ADR-003 keeps the numbering 2–6 untouched)."""
    body = _verify(tmp_path, Preset.PRODUCTION, DevMode.SPEC_DRIVEN)
    assert body.index("### Check 1 —") < body.index("### Check 2 —")
    assert "Run Check 1." in body
