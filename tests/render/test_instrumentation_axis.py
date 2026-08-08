"""ADR-011 — harness-maker's own telemetry is a config axis, not an unconditional tax.

The `stage_agent_ledger emit` rows in plan/execute and the `persist-payload` capture in
review answer *harness-maker's* questions. Shipping them into every third-party harness
charges that project's context budget for a question it never asked.

Two greps, in opposite directions. The OFF grep alone is satisfied by a `{% if %}` that
swallowed the block at every level, so the ON grep pins that the default render is
unchanged. Both scan the whole rendered tree — `.codex/` carries the same prose through a
separate synthesis path, and a scan of `.claude/` alone would call that shipped.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    InstrumentationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

# The two command surfaces the axis owns. `/hm:health`, `/hm:metrics` and
# `delivery_metrics` are deliberately NOT here — they are the user's own observability.
_NEEDLES = ("stage_agent_ledger emit", "persist-payload")


def _render(tmp_path: Path, *, on: bool) -> Path:
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE, Target.CODEX],
            instrumentation=InstrumentationConfig(stage_agent_ledger=on),
        ),
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _hits(root: Path) -> list[str]:
    hits: list[str] = []
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for needle in _NEEDLES:
            if needle in text:
                hits.append(f"{f.relative_to(root)}: {needle}")
    return hits


def test_off_render_ships_no_ledger_instruction(tmp_path: Path) -> None:
    assert not _hits(_render(tmp_path, on=False))


def test_on_render_still_ships_both(tmp_path: Path) -> None:
    """The guard against an OFF-shaped ON. Both stages and review must survive."""
    hits = _hits(_render(tmp_path, on=True))
    joined = "\n".join(hits)
    assert "stage_agent_ledger emit" in joined
    assert "persist-payload" in joined
    # Named files, not just a count: a gate that collapsed plan into execute would keep
    # the count and lose a stage.
    assert any("plan.md" in h and "emit" in h for h in hits), hits
    assert any("execute.md" in h and "emit" in h for h in hits), hits
    assert any("review.md" in h and "persist-payload" in h for h in hits), hits


def test_harness_yaml_records_the_axis_both_ways(tmp_path: Path) -> None:
    """The written key is what `answers_from_harness_yaml` reads back on re-render."""
    off = (_render(tmp_path / "off", on=False) / ".claude" / "harness.yaml").read_text()
    on = (_render(tmp_path / "on", on=True) / ".claude" / "harness.yaml").read_text()
    assert "stage_agent_ledger: false" in off
    assert "stage_agent_ledger: true" in on
