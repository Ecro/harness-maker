"""PLAN-autopilot-advance-noop Phase 4 — render gates for the prompt-layer fixes.

Every assertion here exists because the corresponding defect is INVISIBLE without it:
a missing picker branch, a missing precedence clause, or a re-introduced dead-module
invocation all render as perfectly well-formed markdown. Nothing else would fail.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATES = Path(__file__).parents[2] / "src" / "harness_maker" / "templates"
STAGES = TEMPLATES / "stages"
SHARED = TEMPLATES / "hm" / "autopilot-advance.md.j2"

# Only these four stage bodies carry a terminal STOP paragraph that CONTRADICTS the
# auto-advance block. execute/review have no such paragraph, and wrapup's STOPs are
# AC-gate stops in a stage the chain is structurally forbidden to auto-enter
# (`_HUMAN_GATED_STAGES`). The PLAN said "all 7"; the source says four.
STAGES_WITH_TERMINAL_STOP = ("research", "spec", "verify")

PRECEDENCE_MARKER = "auto-advance check below returning `proceed: true`"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")










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
