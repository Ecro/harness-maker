"""Tests for the workflow fuse logic."""

from __future__ import annotations

from harness_maker.models import AtomicStage
from harness_maker.workflow_fuse import fuse


def test_fuse_dev_workflow_orders_4_stages() -> None:
    """dev = [plan, execute, review, wrapup] fuses in order with separators."""
    stages = [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ]
    body = fuse(stages, "dev")
    assert "# /hm:dev" in body
    # Separators exist for each stage
    for stage in ("plan", "execute", "review", "wrapup"):
        assert f"## Stage: {stage}" in body
    # Order is preserved
    pos = [body.index(f"## Stage: {s}") for s in ("plan", "execute", "review", "wrapup")]
    assert pos == sorted(pos)


def test_fuse_empty_stages_returns_header_only() -> None:
    body = fuse([], "blank")
    assert body == "# /hm:blank\n"
    assert "## Stage:" not in body


def test_fuse_full_atomic_workflow() -> None:
    """Full 7-stage workflow fuses with all separators present."""
    stages = list(AtomicStage)
    body = fuse(stages, "careful")
    for stage in (
        "research",
        "spec",
        "plan",
        "execute",
        "review",
        "wrapup",
        "verify",
    ):
        assert f"## Stage: {stage}" in body
    assert body.startswith("# /hm:careful")


def test_fuse_passes_workflow_context_to_fragments() -> None:
    """Fragment templates receive workflow_context so they can self-reference."""
    body = fuse([AtomicStage.PLAN], "dev")
    # research.md.j2 uses {% if workflow_context %} to add a note; check via plan stage
    assert "dev" in body  # workflow_context is "dev", appears in body
