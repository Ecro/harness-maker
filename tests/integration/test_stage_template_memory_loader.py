"""Integration tests for memory_retrieve invocation in research/plan/spec stage templates.

PLAN-memory-md-operations Phase 2 — verify all three stage templates carry the
new helper invocation and have dropped the legacy "first 60 lines" / rg "<key
terms>" memory-loading patterns.

These read the `.j2` source directly because the invocation appears in plain
text on both `is_codex` branches (substring presence is independent of
render-time context). Full render path is exercised separately via snapshot
tests.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "src" / "harness_maker" / "templates" / "stages"


@pytest.fixture
def stage_source() -> dict[str, str]:
    """Read the three stage `.j2` source bodies."""
    out: dict[str, str] = {}
    for stage in ("research", "plan", "spec"):
        path = _TEMPLATES_DIR / f"{stage}.md.j2"
        assert path.is_file(), f"missing template: {path}"
        out[stage] = path.read_text(encoding="utf-8")
    return out


def test_research_template_invokes_memory_retrieve(stage_source: dict[str, str]) -> None:
    body = stage_source["research"]
    assert "harness_maker.memory_retrieve" in body, (
        "research stage must invoke memory_retrieve helper"
    )


def test_research_template_drops_first_60_lines_pattern(stage_source: dict[str, str]) -> None:
    body = stage_source["research"]
    assert "first 60 lines" not in body, (
        "research stage must no longer reference 'first 60 lines' skim pattern"
    )


def test_plan_template_invokes_memory_retrieve(stage_source: dict[str, str]) -> None:
    body = stage_source["plan"]
    assert "harness_maker.memory_retrieve" in body, "plan stage must invoke memory_retrieve helper"


def test_spec_template_invokes_memory_retrieve(stage_source: dict[str, str]) -> None:
    body = stage_source["spec"]
    assert "harness_maker.memory_retrieve" in body, "spec stage must invoke memory_retrieve helper"


def test_spec_template_drops_rg_key_terms_memory_pattern(stage_source: dict[str, str]) -> None:
    """The legacy `rg "<key terms>" .claude/memory/...` lines must be replaced."""
    body = stage_source["spec"]
    legacy_pattern = re.compile(r"""rg\s+"<key terms>"\s+\.claude/memory/(failures|wiki)\.md""")
    assert not legacy_pattern.search(body), (
        'spec stage must drop the legacy `rg "<key terms>" .claude/memory/...` memory pattern'
    )


def test_session_hot_tier_dropped_in_research(stage_source: dict[str, str]) -> None:
    """session-tier-slim ADR-001: research no longer reads the session tier.

    The decision journal is gone; only wiki + failures load (via the helper).
    """
    body = stage_source["research"]
    assert ".claude/memory/session" not in body, (
        "research stage must NOT read the session tier (checkpoint-only now — ADR-001)"
    )


def test_session_hot_tier_dropped_in_plan_and_review() -> None:
    """plan + review are decision-journal consumers → session read removed (ADR-001)."""
    for stage in ("plan", "review"):
        body = (_TEMPLATES_DIR / f"{stage}.md.j2").read_text(encoding="utf-8")
        assert ".claude/memory/session" not in body, (
            f"{stage} stage must NOT read the session tier (ADR-001)"
        )


def test_execute_keeps_checkpoint_and_ignores_legacy() -> None:
    """execute is the checkpoint consumer → keeps the read but scopes it to
    checkpoint:compaction and ignores legacy [decision:*] blocks (ADR-001, C3)."""
    body = (_TEMPLATES_DIR / "execute.md.j2").read_text(encoding="utf-8")
    assert "checkpoint:compaction" in body, "execute must keep the compaction-checkpoint read"
    assert "legacy" in body, "execute must call the [decision:*] blocks legacy"
    assert "[decision:*]" in body, (
        "execute must instruct ignoring legacy [decision:*] blocks (K=2 second-opinion consensus)"
    )


def test_workflow_command_keeps_checkpoint_and_ignores_legacy() -> None:
    """The fused-workflow shared preamble keeps checkpoint resume + ignores legacy decisions."""
    path = (
        _REPO_ROOT
        / "src"
        / "harness_maker"
        / "templates"
        / "commands"
        / "hm"
        / "workflow_command.md.j2"
    )
    body = path.read_text(encoding="utf-8")
    assert "checkpoint:compaction" in body
    assert "legacy" in body
    assert "[decision:*]" in body


def test_all_three_templates_use_is_codex_branch_for_invocation(
    stage_source: dict[str, str],
) -> None:
    """All three templates must wrap the helper invocation in the is_codex branch
    so Codex gets `Bash("...")` form and Claude Code/Cursor get `!...` form
    (matches existing harness_maker.second_brain pattern)."""
    for stage in ("research", "plan", "spec"):
        body = stage_source[stage]
        # Find the memory_retrieve invocation context. The block should sit
        # inside a `{% if is_codex %}` ... `{% endif %}` region.
        # Heuristic: find the substring and check that an `is_codex` token
        # appears within 200 chars before it.
        idx = body.find("harness_maker.memory_retrieve")
        assert idx >= 0, f"{stage}: no memory_retrieve invocation"
        window = body[max(0, idx - 400) : idx]
        assert "is_codex" in window, (
            f"{stage}: memory_retrieve invocation not guarded by is_codex branch; "
            f"window:\n{window!r}"
        )
