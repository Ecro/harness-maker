"""S1–S6 integration of the shared feedback procedure, not a real-task outcome trial.

Tests inspect named owning blocks of synthesized output. Independent scenario
review supplies the behavioral oracle; these checks only prevent wiring regressions.
Each assertion has a new positive block requirement, so omissions are RED.
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
def test_s1_three_triggers_load_the_protocol(roots: dict[str, Path], host: str) -> None:
    root = roots[host]
    for stage in ("research", "spec", "execute", "review", "verify", "wrapup"):
        p = root / (f"skills/hm-{stage}/SKILL.md" if host == "codex" else f"commands/hm/{stage}.md")
        body = p.read_text()
        entry = body.split("<!-- @hm:feedback-entry -->")[1].split("<!-- @hm:/feedback-entry -->")[
            0
        ]
        assert "At stage entry/resume and each material observation, read and follow" in entry
        assert "skills/intent-layer/SKILL.md` → Workflow feedback" in entry
        close = body.split("<!-- @hm:feedback-close -->")[1].split("<!-- @hm:/feedback-close -->")[
            0
        ]
        assert "Before close-out or stage handoff, apply Workflow feedback" in close
        assert "record the next action or stop reason in PLAN Feedback" in close


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
    path = roots[host] / (
        "skills/hm-execute/SKILL.md" if host == "codex" else "commands/hm/execute.md"
    )
    authoring = _section(path.read_text(), "### Step 0 — Author the PLAN")
    assert "Add a Feedback section using the intent-layer record map" in authoring
    assert "link the SPEC, intent, evidence and next decision" in authoring
    assert "Do not copy shared current state into the PLAN" in authoring


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_s6_trial_includes_failed_rows_and_concurrent_completion(
    roots: dict[str, Path], host: str
) -> None:
    skill = _protocol(roots[host])
    block = _section(skill, "## Real-task trial")
    for obligation in (
        "typed `trial` frontmatter is authoritative for activation",
        "one stable event ID per fact",
        "terminal event records the actual task closeout, including failure or abort",
        "Intermediate stage handoff is not terminal",
        "cohort is chronological by first start, includes failures/aborts",
        "excludes administrative/synthetic work under its original policy",
        "Never reset members, close the intent or declare trial success",
        "Never derive a pass/fail from task success",
    ):
        assert obligation in " ".join(block.split())


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_s3_measure_before_intent_closure(roots: dict[str, Path], host: str) -> None:
    p = roots[host] / ("skills/hm-wrapup/SKILL.md" if host == "codex" else "commands/hm/wrapup.md")
    block = _section(p.read_text(), "#### 5.7 Intent state")
    assert "Feedback" in block
    assert block.index("@hm:answer-gated:outcome-measure") < block.index(
        "@hm:answer-gated:objective-close"
    )


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_s6_trial_hooks_run_without_intent_and_keep_operator_choice_local(
    roots: dict[str, Path], host: str
) -> None:
    root = roots[host]
    for stage in ("research", "spec", "execute", "review", "verify", "wrapup"):
        path = root / (
            f"skills/hm-{stage}/SKILL.md" if host == "codex" else f"commands/hm/{stage}.md"
        )
        body = path.read_text()
        entry = body.split("<!-- @hm:feedback-entry -->")[1].split("<!-- @hm:/feedback-entry -->")[
            0
        ]
        close = body.split("<!-- @hm:feedback-close -->")[1].split("<!-- @hm:/feedback-close -->")[
            0
        ]
        assert (
            "Independently of intent availability, check for an explicitly activated trial PLAN"
            in entry
        )
        assert (
            "apply Real-task trial at entry/resume and on any terminal exit, "
            "including failure or abort" in " ".join(entry.split())
        )
        assert "update its existing row with terminal/evidence disposition" in " ".join(
            close.split()
        )
    protocol = _protocol(root)
    trial = _section(protocol, "## Real-task trial")
    assert "If none is active, do nothing and ask no trial question" in " ".join(trial.split())
    assert "inspect `work-docs/PLAN-*.md` for an explicit trial activation" in " ".join(
        trial.split()
    )
    assert "the operator selected this" not in trial
    assert "WORLD-INTENT-CLOSED-LOOP" not in trial


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_trial_uses_session_independent_base_writer_and_no_worktree_enrollment_race(
    roots: dict[str, Path], host: str
) -> None:
    trial = " ".join(_section(_protocol(roots[host]), "## Real-task trial").split())
    for rule in (
        "Any session may perform this mechanical update under the recorded active policy",
        "It does not need a previous collector's acknowledgment",
        "A worktree copy is never the authoritative trial PLAN",
        "all trial commands resolve the base root",
        "A user accepted historical population is recorded through",
        "do not infer acceptance from readable logs, silence or a model summary",
    ):
        assert rule in trial
