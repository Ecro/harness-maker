"""PLAN-autopilot-advance-noop Phase 4 — render gates for the prompt-layer fixes.

Every assertion here exists because the corresponding defect is INVISIBLE without it:
a missing picker branch, a missing precedence clause, or a re-introduced dead-module
invocation all render as perfectly well-formed markdown. Nothing else would fail.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).parents[2] / "src" / "harness_maker" / "templates"
STAGES = TEMPLATES / "stages"

# Only these four stage bodies carry a terminal STOP paragraph that CONTRADICTS the
# auto-advance block. execute/review have no such paragraph, and wrapup's STOPs are
# AC-gate stops in a stage the chain is structurally forbidden to auto-enter
# (`_HUMAN_GATED_STAGES`). The PLAN said "all 7"; the source says four.
STAGES_WITH_TERMINAL_STOP = ("research", "spec", "plan", "verify")

PRECEDENCE_MARKER = "auto-advance check below returning `proceed: true`"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.mark.parametrize("stage", STAGES_WITH_TERMINAL_STOP)
def test_terminal_stop_names_the_auto_advance_exception(stage: str) -> None:
    """ADR-006, half one. The unconditional STOP appears EARLIER in the body and reads
    stronger than the auto-advance block; a model resolving the conflict conservatively
    prints the banner and stops — the reported symptom."""
    body = _read(STAGES / f"{stage}.md.j2")
    terminal = [ln for ln in body.splitlines() if "Stage terminal" in ln]
    assert terminal, f"{stage}: no Stage-terminal line to gate"
    assert any(PRECEDENCE_MARKER in ln for ln in terminal), (
        f"{stage}: Stage-terminal STOP does not name the auto-advance exception"
    )


def test_auto_advance_block_claims_precedence() -> None:
    """ADR-006, half two — both sides must name each other. A one-sided override is
    exactly what shipped, and it lost."""
    partial = _read(TEMPLATES / "agents" / "_partials" / "stage_end_summary.md.j2")
    assert "supersedes this" in partial
    assert "Stage terminal" in partial


def test_auto_advance_passes_the_task_slug() -> None:
    """ADR-003 — an argument-less Skill call stalls argument-parsing stages, which reads
    to the user as 'announced but did nothing'."""
    partial = _read(TEMPLATES / "agents" / "_partials" / "stage_end_summary.md.j2")
    assert "task_slug" in partial
    assert "task_slug_source" in partial, "an inherited slug must be announced, not silent"
    assert "bad_slug" in partial, "the halt it can cause must be in the halt list it reads"

    # Gate the EXECUTED line, not just the prose around it. The previous version asserted
    # only `"--slug" in partial`, which a mention anywhere satisfies — so it stayed green
    # both when the flag was pre-rendered with a placeholder (which always fails the
    # allowlist, and after the halt landed stopped the chain at every stage) and when the
    # append instruction was inert. Neither state is distinguishable from a working one by
    # a whole-file substring match.
    boundary = [ln for ln in partial.splitlines() if "autopilot_caps boundary" in ln]
    assert len(boundary) == 1, boundary
    assert "--slug" not in boundary[0], (
        "the flag must NOT ship pre-rendered — any placeholder value fails the slug "
        "allowlist and now halts the boundary"
    )

    # And the instruction that replaces it must not itself show a bracketed placeholder:
    # a model copying `--slug <it>` reproduces the exact defect this removed.
    assert not re.search(r"--slug\s*<", partial), "append instruction shows a placeholder token"


def test_slug_line_uses_no_positional_parameter() -> None:
    """CLAUDE.md section 2 — the host replaces shell positional parameters in a command
    body BEFORE the model sees it. The disk file would look correct; only the executed
    text differs. (The repo-wide gate `test_no_positional_params_in_commands` covers the
    whole rendered surface — including, as this change found out, explanatory prose that
    merely QUOTES such a token.)"""
    partial = _read(TEMPLATES / "agents" / "_partials" / "stage_end_summary.md.j2")
    slug_lines = [ln for ln in partial.splitlines() if "--slug" in ln]
    assert slug_lines
    for line in slug_lines:
        assert not re.search(r"\$[0-9]", line), f"positional parameter in: {line}"


def test_picker_branches_on_status_not_file_existence() -> None:
    """ADR-002 — the dominant failure path. With no command to ask, the model checks
    whether the marker FILE exists; a stale marker then suppresses arming indefinitely."""
    manifest = _read(TEMPLATES / "agents" / "_partials" / "step_manifest.md.j2")
    assert "hm autopilot status" in manifest
    assert "never decide this from" in manifest


def test_picker_defers_the_takeover_decision_to_the_user() -> None:
    """ADR-010 / validator CR2, as revised by round 4.

    `status` returns active:false for a foreign marker, so a picker branching on the
    boolean ALONE offers arming and clobbers a live peer. The first fix was a flat "do NOT
    arm", which then wedged the project for the full TTL whenever the owning session had
    simply ended — nothing clears the marker at session end. Neither a blanket refusal nor
    a "probably yours, --force it" guess is right, because the prompt genuinely cannot
    distinguish the two states.

    So the contract this gate pins is: name both reasons, state `idle_minutes` as a fact,
    refuse to guess, and put the one question that settles it to the user — who is the only
    party that knows whether another session is open. None of this is detectable on disk by
    any other means.
    """
    manifest = _read(TEMPLATES / "agents" / "_partials" / "step_manifest.md.j2")
    # Collapse the markdown line wrapping — the prose is hard-wrapped inside a blockquote,
    # so a phrase spanning a line break is interrupted by the `>` marker on disk while
    # still being one instruction to the model reading it. Strip the markers, then flatten.
    flat = " ".join(" ".join(ln.lstrip().removeprefix(">").split()) for ln in manifest.splitlines())
    assert '`reason: "foreign"`' in flat
    assert '"degraded-idless"' in flat
    assert "idle_minutes" in flat
    assert "do not guess" in flat
    assert "is another Claude session open in this project?" in flat
    assert "--force" in flat


def test_no_template_invokes_the_deleted_autopilot_guard() -> None:
    """The module was deleted in 539f05a9. An invocation of a non-existent module is worse
    than no invocation — it looks like a wired safety net."""
    offenders = [
        p.relative_to(TEMPLATES).as_posix()
        for p in TEMPLATES.rglob("*")
        if p.is_file() and "harness_maker.hooks.autopilot_guard" in _read(p)
    ]
    assert offenders == []
