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


def test_no_template_invokes_the_deleted_autopilot_guard() -> None:
    """The module was deleted in 539f05a9. An invocation of a non-existent module is worse
    than no invocation — it looks like a wired safety net."""
    offenders = [
        p.relative_to(TEMPLATES).as_posix()
        for p in TEMPLATES.rglob("*")
        if p.is_file() and "harness_maker.hooks.autopilot_guard" in _read(p)
    ]
    assert offenders == []
