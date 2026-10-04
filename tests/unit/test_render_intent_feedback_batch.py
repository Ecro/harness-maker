"""SPEC-intent-layer-improvements AC-001..004, AC-007, AC-011, AC-012 — rendered wrapup/stage prose.

Every assertion is scoped to its owning block (a marker pair or a heading-bounded section) of the
synthesized output, never to the whole file, and every clause has a deletion control: the same
predicate applied to a copy of the block with that clause removed must turn false. A predicate
that stays true on the mutated copy is the assertion-invariant defect this module exists to avoid.

AC-002 (feedback blocks) and AC-011 (spec Step 4.9 id derivation) were retired by
SPEC-intent-surface-diet, which removed that prose; the 5.7 record-batch, verdict and close
tests below are kept as that SPEC's AC-003 guard oracle.
"""

from __future__ import annotations

import re
from functools import cache
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

STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")
ARMS = [(p, h) for p in (Preset.PRODUCTION, Preset.SIDE) for h in ("claude", "codex")]
ARM_IDS = [f"{p.value}-{h}" for p, h in ARMS]


@cache
def _root(preset: Preset) -> Path:
    import tempfile

    root = Path(tempfile.mkdtemp(prefix=f"hm-feedback-batch-{preset.value}-"))
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=preset,
                targets=[Target.CLAUDE_CODE, Target.CODEX],
                # Delegation on, as in this repo: only then does wrapup render the Step 0.5
                # jump that AC-001 is about. With it off there is no jump to misroute.
                delegation=DelegationConfig(stages=["wrapup", "verify"]),
            ),
        ),
        root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return root


def _stage(preset: Preset, host: str, stage: str) -> str:
    root = _root(preset)
    rel = (
        f".claude/commands/hm/{stage}.md"
        if host == "claude"
        else f".agents/skills/hm-{stage}/SKILL.md"
    )
    return (root / rel).read_text(encoding="utf-8")


def _block(text: str, name: str) -> str:
    m = re.search(
        rf"<!-- @hm:{re.escape(name)} -->(.*?)<!-- @hm:/{re.escape(name)} -->", text, re.S
    )
    return m.group(1) if m else ""


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^#+ {re.escape(heading)}.*?(?=^#{{2,4}} )", text, re.S | re.M)
    return m.group(0) if m else ""


def _gated(section: str, name: str) -> str:
    m = re.search(
        rf"<!-- @hm:answer-gated:{re.escape(name)} -->(.*?)<!-- /@hm:answer-gated -->",
        section,
        re.S,
    )
    return m.group(1) if m else ""


def _without(text: str, clause: str) -> str:
    assert clause in text, clause
    return text.replace(clause, "")


# ── AC-001 ───────────────────────────────────────────────────────────────────

_RESUME = re.compile(
    r"(?:proceed|skip straight|skip|continue|go|resume|jump)(?: straight)? "
    r"(?:to|at) Step (\d+(?:\.\d+)?)",
    re.I,
)


def resumes_at_5_7(region: str) -> bool:
    """At least one routing directive, every one names 5.7, and Step 6 is never named at all."""
    targets = _RESUME.findall(region)
    return bool(targets) and all(t == "5.7" for t in targets) and "Step 6" not in region


def _wrapup_regions(preset: Preset, host: str) -> tuple[str, str]:
    text = _stage(preset, host, "wrapup")
    assert "#### 5.7" in text
    delegated = _section(text, "Step 0.5")
    inline = _section(text, "Steps 1–5.6 — inline body")
    return delegated, inline


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_wrapup_delegated_path_resumes_at_5_7(preset: Preset, host: str) -> None:
    delegated, inline = _wrapup_regions(preset, host)
    # Delegation is on in this render, so BOTH regions must exist: an empty one would mean a
    # heading rename silently dropped a path from the check.
    assert delegated
    assert inline
    assert resumes_at_5_7(delegated)
    assert resumes_at_5_7(inline)


def test_resume_predicate_controls() -> None:
    assert resumes_at_5_7("- exit 0 → proceed to Step 5.7.")
    assert not resumes_at_5_7("- exit 0 → proceed to Step 6.")
    assert not resumes_at_5_7("skip straight to Step 5.7, then jump to Step 6")
    assert not resumes_at_5_7("proceed to Step 5.7. exit 1 → fix the gap before Step 6")
    assert not resumes_at_5_7("no directive at all")


# ── AC-002 (retired) ─────────────────────────────────────────────────────────
#
# The per-stage feedback-entry/close blocks were removed by SPEC-intent-surface-diet (AC-001):
# no stage collects Feedback rows before wrapup any more, and 5.7 derives candidates itself.
# tests/unit/test_intent_surface_diet.py owns the absence check.


# ── AC-003 / AC-004 / AC-012 ─────────────────────────────────────────────────


def _step_5_7(preset: Preset, host: str) -> str:
    section = _section(_stage(preset, host, "wrapup"), "5.7")
    assert section
    return section


_RECORD_CLAUSES = (
    "each with its exact arguments",
    "`pending` rows",
    "previous attempt failed",
    "that bears on a metric",
    "`## Feedback`",
    "PLAN, SPEC and RESEARCH",
    "Read `hm intent status --json` once",
    "only the selected",
    "read status back",
    "`declined`",
    "`failed`",
    "do not retry",
    "ask nothing",
)
_CODEX_CLAUSES = ("numbered list", "one reply", "`none`")


def record_batch_ok(section: str, host: str) -> bool:
    if section.count("<!-- @hm:answer-gated:record-batch -->") != 1:
        return False
    block = _gated(section, "record-batch")
    if not all(c in block for c in _RECORD_CLAUSES):
        return False
    # The exact arguments are the consent: they must be shown before the operator is asked.
    ask = "AskUserQuestion" if host == "claude" else "numbered list"
    if not 0 <= block.find("each with its exact arguments") < block.find(ask):
        return False
    if host == "claude":
        # AskUserQuestion caps one call at 4 questions x 4 options; Codex's reply has no cap.
        return "multiSelect" in block and "at most 16 items" in block
    return all(c in block for c in _CODEX_CLAUSES) and "multiSelect" not in block


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_wrapup_5_7_record_batch(preset: Preset, host: str) -> None:
    section = _step_5_7(preset, host)
    assert record_batch_ok(section, host)
    assert section.count("<!-- @hm:answer-gated:") == 2


@pytest.mark.parametrize("clause", [*_RECORD_CLAUSES, "multiSelect", "at most 16 items"])
def test_record_batch_controls_claude(clause: str) -> None:
    section = _step_5_7(Preset.PRODUCTION, "claude")
    block = _gated(section, "record-batch")
    assert not record_batch_ok(section.replace(block, _without(block, clause)), "claude")


@pytest.mark.parametrize("clause", _CODEX_CLAUSES)
def test_record_batch_controls_codex(clause: str) -> None:
    section = _step_5_7(Preset.PRODUCTION, "codex")
    block = _gated(section, "record-batch")
    assert not record_batch_ok(section.replace(block, _without(block, clause)), "codex")
    assert not record_batch_ok(section.replace(block, block + " multiSelect"), "codex")


_VERDICT_CLAUSES = (
    "measure: false",
    "`how_measured`",
    "proposing a value from its `last`",
    "names this task's slug",
    "that is the verdict row the skip rule above reads",
    "hm intent metric record",
    "only when selected",
    "already has a `recorded` verdict row",
)


def verdict_item_ok(section: str) -> bool:
    block = _gated(section, "record-batch")
    return all(c in block for c in _VERDICT_CLAUSES)


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_wrapup_5_7_judgment_verdict_item(preset: Preset, host: str) -> None:
    assert verdict_item_ok(_step_5_7(preset, host))


@pytest.mark.parametrize("clause", _VERDICT_CLAUSES)
def test_verdict_item_controls(clause: str) -> None:
    section = _step_5_7(Preset.PRODUCTION, "claude")
    block = _gated(section, "record-batch")
    mutated = section.replace(block, _without(block, clause))
    assert not verdict_item_ok(mutated)
    # Moving the clause outside the gated block must also fail.
    assert not verdict_item_ok(mutated + "\n" + clause)


_CLOSE_CLAUSES = (
    "`met`",
    "`missed`",
    "`no_data`",
    "keep open",
    "one single-choice question",
    "PLAN frontmatter",
    "`intent: <id>`",
)
_READBACK = "read status back"
_RECORD_MARK = "<!-- @hm:answer-gated:record-batch -->"
_CLOSE_MARK = "<!-- @hm:answer-gated:intent-close -->"


def close_after_readback(section: str) -> bool:
    """record-batch start < the record block's own readback < intent-close start."""
    record = section.find(_RECORD_MARK)
    close = section.find(_CLOSE_MARK)
    rel = _gated(section, "record-batch").find(_READBACK)
    if record < 0 or close < 0 or rel < 0:
        return False
    readback = record + len(_RECORD_MARK) + rel
    if not record < readback < close:
        return False
    block = _gated(section, "intent-close")
    return all(c in block for c in _CLOSE_CLAUSES)


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_wrapup_5_7_close_after_readback(preset: Preset, host: str) -> None:
    assert close_after_readback(_step_5_7(preset, host))


def _whole(section: str, name: str, mark: str) -> str:
    return mark + _gated(section, name) + "<!-- /@hm:answer-gated -->"


def test_close_after_readback_controls() -> None:
    section = _step_5_7(Preset.PRODUCTION, "claude")
    close = _whole(section, "intent-close", _CLOSE_MARK)
    record = _whole(section, "record-batch", _RECORD_MARK)
    # Close hoisted above the record block, even with the readback phrase left in a preamble.
    hoisted = section.replace(close, "")
    hoisted = hoisted.replace(record, _READBACK + "\n" + close + record)
    assert not close_after_readback(hoisted)
    # Readback removed from the record block but kept elsewhere in the section.
    rb = _gated(section, "record-batch")
    assert not close_after_readback(section.replace(rb, _without(rb, _READBACK)) + _READBACK)
    block = _gated(section, "intent-close")
    for clause in _CLOSE_CLAUSES:
        assert not close_after_readback(section.replace(block, _without(block, clause)))


# ── AC-007 ───────────────────────────────────────────────────────────────────


def _trial_duty_files(preset: Preset) -> list[Path]:
    root = _root(preset)
    files = [*sorted((root / ".claude/commands/hm").glob("*.md"))]
    files += sorted((root / ".agents/skills").glob("hm-*/SKILL.md"))
    for base in (root / ".claude/skills/intent-layer", root / ".agents/skills/intent-layer"):
        files += [base / "SKILL.md", *sorted((base / "references").glob("*"))]
    return files


_TRIAL_DUTY = re.compile(
    r"real-task trial|trial\s+status|trial\s+plan|activated\s+trial|trial\s+reconcile"
    r"|record-decision|trial_feedback",
    re.I,
)


def has_trial_duty(text: str) -> bool:
    return bool(_TRIAL_DUTY.search(text))


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE], ids=lambda p: p.value)
def test_no_trial_duty_in_rendered_prose(preset: Preset) -> None:
    files = _trial_duty_files(preset)
    assert any("references" in f.parts for f in files)
    offenders = [str(f) for f in files if has_trial_duty(f.read_text(encoding="utf-8"))]
    assert not offenders, offenders


def test_trial_duty_control() -> None:
    assert has_trial_duty("## Real-task trial\n")
    assert has_trial_duty("run hm intent trial  status x --json")
    assert has_trial_duty("check for an explicitly activated trial PLAN")
    assert has_trial_duty("hm intent --root <base> trial reconcile x --json")
    assert has_trial_duty("record it through record-decision")
    assert has_trial_duty("as trial_feedback frontmatter events")
    assert not has_trial_duty("a pending row in the Feedback table of the PLAN")
    assert not has_trial_duty("record the close decision after readback")


# ── AC-011 (retired) ─────────────────────────────────────────────────────────
#
# spec Step 4.9 (intent draft) was removed by SPEC-intent-surface-diet (AC-002): intents are
# created only through Maker / the intent-layer skill, so there is no id derivation to pin.
