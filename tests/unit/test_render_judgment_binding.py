"""Render assertions for judgment AC binding (PLAN-judgment-ac-binding).

- The independent `judgment-reviewer` agent renders with valid frontmatter + variant.
- wrapup dispatches the reviewer, records via mark-judged, runs the Production find-unjudged
  gate (Production) / advisory (Side), and the report retires the "judgment, deferred" bucket.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(tmp_path: Path, preset: Preset) -> Path:
    bp = synthesize(ProjectProfile(), InterviewAnswers(preset=preset, targets=[Target.CLAUDE_CODE]))
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _read(tmp_path: Path, suffix: str) -> str:
    return next(f.read_text(encoding="utf-8") for f in tmp_path.rglob(suffix))


def test_judgment_reviewer_agent_renders(tmp_path: Path) -> None:
    _render(tmp_path, Preset.PRODUCTION)
    body = _read(tmp_path, "agents/judgment-reviewer.md")
    assert "name: judgment-reviewer" in body
    assert "communication_variant: reframe" in body
    # read-only: no Write/Edit tool
    assert "tools: Read, Grep, Glob" in body
    # untrusted-data framing (prompt-injection guard, ADR-006)
    assert "untrusted DATA" in body


def test_wrapup_dispatches_independent_reviewer(tmp_path: Path) -> None:
    _render(tmp_path, Preset.PRODUCTION)
    body = _read(tmp_path, "stages/wrapup.md")
    assert "judgment-reviewer" in body
    assert "mark-judged" in body
    # the deferred-bucket REPORT bullet is retired (the prose may still name it)
    assert "**judgment, deferred**" not in body
    assert "RETIRED" in body


def test_wrapup_production_renders_find_unjudged_gate(tmp_path: Path) -> None:
    body = _read(_render(tmp_path, Preset.PRODUCTION), "stages/wrapup.md")
    assert "find-unjudged" in body
    assert "Production judgment gate" in body
    assert "STALE = unbound" in body


def test_wrapup_side_judgment_advisory_not_gate(tmp_path: Path) -> None:
    body = _read(_render(tmp_path, Preset.SIDE), "stages/wrapup.md")
    assert "find-unjudged" in body  # named for listing
    assert "Production judgment gate" not in body
