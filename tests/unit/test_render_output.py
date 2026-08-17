"""Unit tests for make render-output: dry-run KEEP/MERGE + severity-aware fresh-install health."""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from harness_maker import ai_readiness, cli
from harness_maker.improvement import ActionItem, ImprovementPlan
from harness_maker.models import Preset


def _bp(*rel_paths: str) -> types.SimpleNamespace:
    """Minimal Blueprint stand-in — _emit_dry_run_summary only reads .files[].path."""
    return types.SimpleNamespace(files=[types.SimpleNamespace(path=Path(p)) for p in rel_paths])


def _action(priority: str) -> ActionItem:
    return ActionItem(
        priority=priority,
        dimension="context",
        target="CLAUDE.md",
        summary=f"{priority} gap here",
        detail="evidence",
        suggestion="fix it",
        source="layer1:test",
    )


def _plan(*priorities: str) -> ImprovementPlan:
    return ImprovementPlan(
        composite_score=80,
        # keys render_terminal_summary reads on the re-render (full-scan) path
        layer_scores={"readiness": 80, "llm_judge": 80, "cache": 80},
        actions=[_action(p) for p in priorities],
    )


# ── dry-run KEEP/MERGE ────────────────────────────────────────────────────


def test_dry_run_summary_includes_keep_merge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """KEEP/MERGE are surfaced, and are now derived from PATHS rather than free counts.

    The old signature took bare integers, so this test could — and did — assert `keep_count=2,
    merge_count=1` against a two-file blueprint: three decisions over two files. Passing the
    reconcile paths makes that unrepresentable, and it is what lets the summary subtract them
    from REPLACE instead of double-counting.

    The `"2" in out` / `"1" in out` assertions were also substring matches against the whole
    block, which a `Total: 2` line satisfies on its own; they are anchored to their labels now.
    """
    cli._emit_dry_run_summary(
        # Duck-typed stand-in: `_emit_dry_run_summary` reads only `.files[].path`. The ignore is
        # localised HERE rather than widened into `_bp`'s return type, so a signature change on
        # the function under test still surfaces statically.
        _bp("commands/hm/x.md", "agents/a.md"),  # type: ignore[arg-type]
        tmp_path,
        keep_paths=frozenset({Path("commands/hm/x.md")}),
        merge_paths=frozenset({Path("agents/a.md")}),
    )
    out = capsys.readouterr().out
    assert "KEEP:    1" in out
    assert "MERGE:   1" in out


# ── severity-aware fresh-install health (ADR-005) ─────────────────────────


def test_fresh_install_quiet_when_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_readiness, "run_ai_readiness", lambda *a, **k: _plan("P2", "P2"))
    cli._emit_post_make_readiness(tmp_path, Preset.SIDE, is_fresh=True)
    out = capsys.readouterr().out
    assert "clean" in out
    assert "P0/P1 finding" not in out  # not the loud path
    assert "─" * 64 not in out  # no loud separator


def test_fresh_install_loud_on_p0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_readiness, "run_ai_readiness", lambda *a, **k: _plan("P0", "P2"))
    cli._emit_post_make_readiness(tmp_path, Preset.SIDE, is_fresh=True)
    out = capsys.readouterr().out
    assert "P0/P1 finding" in out  # loud count, not buried
    assert "P0 gap here" in out  # the actual finding surfaced
    assert "clean" not in out


def test_rerender_keeps_full_scan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_readiness, "run_ai_readiness", lambda *a, **k: _plan("P2"))
    cli._emit_post_make_readiness(tmp_path, Preset.SIDE, is_fresh=False)
    out = capsys.readouterr().out
    assert "Initial structural-health scan" in out  # full re-render path unchanged
