"""S1–S6 integration of the shared feedback procedure, not a real-task outcome trial.

Tests inspect named owning blocks of synthesized output. Independent scenario
review supplies the behavioral oracle; these checks only prevent wiring regressions.
Each assertion has a new positive block requirement, so omissions are RED.

Superseded by SPEC-intent-layer-improvements (2026-09-29): the S1 "three triggers load the
protocol" test and the three Real-task trial tests asserted prose that the approved SPEC removes
(stages now only collect `pending` rows; the trial is frozen and its duty prose is gone). Their
replacements are AC-002 and AC-007 in `test_render_intent_feedback_batch.py`.

SPEC-intent-surface-diet (2026-10-04) removed execute's PLAN Feedback-section instruction: wrapup
5.7 now creates the table when it records a disposition, so the execute-authoring assertions in
the S5 test were retired; the reference's record map and disposition table are still pinned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def roots(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("feedback")
    render(
        synthesize(ProjectProfile(), InterviewAnswers(targets=[Target.CODEX, Target.CLAUDE_CODE])),
        root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return {"codex": root / ".agents", "claude": root / ".claude"}


def _section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def _protocol(root: Path) -> str:
    skill = (root / "skills/intent-layer/SKILL.md").read_text()
    assert "Workflow feedback: read and follow `references/workflow-feedback.md`" in skill
    return (root / "skills/intent-layer/references/workflow-feedback.md").read_text()


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_s2_s3_s4_feedback_authority_and_evidence(roots: dict[str, Path], host: str) -> None:
    skill = _protocol(roots[host])
    block = _section(skill, "## Workflow feedback")
    for obligation in (
        "If status is not_filled_in, skip feedback; if invalid, report the error",
        "If consent is pending or declined, write nothing and mark the update pending or declined",
        "Reuse existing authorization only for the same operation and agreed scope",
        "After an authorized write, read back status; use that readback in the next decision",
        "For missing, stale or conflicting evidence, diagnose within "
        "scope before the dependent decision",
        "If the observation window is open, record its closing date and "
        "next eligible trigger; do not retry now",
        "On replay, link the existing disposition and follow-up; do not create duplicate work",
        "Never rewrite terminal intent records; link delayed evidence to a consented new proposal",
        "When no authorized work remains, record the stop reason and stop",
    ):
        assert obligation in " ".join(block.split())


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_s5_authoritative_map_and_plan_feedback(roots: dict[str, Path], host: str) -> None:
    skill = _protocol(roots[host])
    block = _section(skill, "## Workflow feedback")
    for row in (
        "Intent scope/lifecycle | `intent/<ID>.md`",
        "Questions/metric definitions | `.claude/intent.yaml`",
        "Measured values | `.claude/intent/metrics.yaml`",
        "Domain facts | `.claude/memory/wiki.md`",
    ):
        assert row in block
    assert (
        "Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action"
        in block
    )


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_s3_measure_before_intent_closure(roots: dict[str, Path], host: str) -> None:
    p = roots[host] / ("skills/hm-wrapup/SKILL.md" if host == "codex" else "commands/hm/wrapup.md")
    block = _section(p.read_text(), "#### 5.7 Intent state")
    assert "Feedback" in block
    record = block.index("@hm:answer-gated:record-batch")
    assert (
        record
        < block.index("hm intent metric measure --all")
        < block.index("@hm:answer-gated:intent-close")
    )
