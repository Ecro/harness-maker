"""SPEC-understanding-handoff — rendered prose for the Understanding block and ADR provenance.

Every anchor is asserted inside the section that owns it, on rendered text, across all four
arms (Production/Side × worktree on/off): an anchor found anywhere in the file would pass a
render that put the instruction in the delegated span, where it never reaches the commit
(`[fail:test] assertion-invariant-over-named-dimension`). The anchors are copied from the
SPEC's AC headings, not from the template.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

MAIN_LOOP_HEADING = "### Steps 6 "
ARMS = [
    (Preset.PRODUCTION, True),
    (Preset.PRODUCTION, False),
    (Preset.SIDE, True),
    (Preset.SIDE, False),
]
ARM_IDS = [f"{p.value}-wt_{'on' if w else 'off'}" for p, w in ARMS]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _render(tmp_path: Path, preset: Preset, wt_on: bool, stages: list[str] | None = None) -> Path:
    answers = InterviewAnswers(
        preset=preset,
        targets=[Target.CLAUDE_CODE],
        delegation=DelegationConfig(stages=stages or []),
        worktree={"enabled": wt_on},
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _step6(body: str) -> str:
    start = body.index(MAIN_LOOP_HEADING)
    end = body.index("\n### ", start + len(MAIN_LOOP_HEADING))
    return body[start:end]


def _wrapup(tmp_path: Path, preset: Preset, wt_on: bool, stages: list[str] | None = None) -> str:
    root = _render(tmp_path, preset, wt_on, stages)
    return (root / "commands/hm/wrapup.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(("preset", "wt_on"), ARMS, ids=ARM_IDS)
def test_ac_001_step6_instructs_the_understanding_block(
    tmp_path: Path, preset: Preset, wt_on: bool
) -> None:
    section = _flat(_step6(_wrapup(tmp_path, preset, wt_on)))
    for anchor in (
        "Understanding:",
        "Understanding: none",
        "at most 5 bullets",
        "before -> after",
        "unknown:",
        "English",
        "Do not list files",
        "before the trailers",
    ):
        assert anchor in section, f"Step 6 lacks {anchor!r}"


def test_ac_001_block_instruction_is_not_in_the_delegated_span(tmp_path: Path) -> None:
    body = _wrapup(tmp_path, Preset.PRODUCTION, True, stages=["wrapup"])
    delegate = body.index("### Step 0.5")
    section = body.index(MAIN_LOOP_HEADING)
    assert "Understanding:" in body[section:], "positive control: the block is rendered"
    assert "Understanding:" not in body[delegate:section], "the delegate must not generate it"


@pytest.mark.parametrize(("preset", "wt_on"), ARMS, ids=ARM_IDS)
def test_ac_005_closing_output_repeats_the_block(
    tmp_path: Path, preset: Preset, wt_on: bool
) -> None:
    body = _wrapup(tmp_path, preset, wt_on)
    done = [ln for ln in body.splitlines() if ln.startswith("> ✅ **Done:**")]
    assert len(done) == 1, "exactly one closing Done line"
    assert "`Understanding:` block verbatim" in done[0]

    # The instruction that produces the repeat, not only the Done-line phrase pointing at it:
    # it sits after Step 8 and before the banner, prints the receipt's landed text (review:
    # a bare HEAD races a peer land; the message file can differ from HEAD on a resume), has
    # a branch for the warn-only statuses, and one for a receipt that predates the key.
    start = body.index("### Step 8")
    closing = _flat(body[start : body.index("> ✅ **Done:**")])
    for anchor in (
        "steps.understanding_block",
        "steps.understanding.status",
        "never from memory, the message file or `HEAD`",
        "`[wrapup_land] understanding:` warning",
        "has no `understanding` key",
    ):
        assert anchor in closing, f"closing instruction lacks {anchor!r}"
    assert "re-read from the file you passed as `--message-file`" not in closing


@pytest.mark.parametrize(("preset", "wt_on"), ARMS, ids=ARM_IDS)
def test_ac_006_execute_adr_section_requires_decided_by(
    tmp_path: Path, preset: Preset, wt_on: bool
) -> None:
    body = (_render(tmp_path, preset, wt_on) / "commands/hm/execute.md").read_text(encoding="utf-8")
    start = body.index("**📐 Architecture Decision Records**")
    end = body.index("**🏗️ Technical Design**", start)
    item = _flat(body[start:end])
    for anchor in ("**Decided by:** user (source:", "**Decided by:** agent"):
        assert anchor in item, f"ADR section lacks {anchor!r}"


@pytest.mark.parametrize(("preset", "wt_on"), ARMS, ids=ARM_IDS)
def test_ac_007_step6_reports_agent_decided_and_unmarked(
    tmp_path: Path, preset: Preset, wt_on: bool
) -> None:
    section = _flat(_step6(_wrapup(tmp_path, preset, wt_on)))
    for anchor in ("- agent-decided:", "**Decided by:** agent", "(unmarked: N)"):
        assert anchor in section, f"Step 6 lacks {anchor!r}"
