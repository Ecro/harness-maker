"""Tests for context_lint."""

from __future__ import annotations

from pathlib import Path

from harness_maker.context_lint import THRESHOLDS, lint, lint_mcp_server_count, lint_window_usage
from harness_maker.models import Preset


def _write(path: Path, body: str, with_fm: bool = False) -> Path:
    if with_fm:
        path.write_text("---\nname: x\n---\n" + body, encoding="utf-8")
    else:
        path.write_text(body, encoding="utf-8")
    return path


def test_under_threshold_returns_no_warnings(tmp_path: Path) -> None:
    body = "\n".join(["line"] * 10) + "\n"
    f = _write(tmp_path / "CLAUDE.md", body)
    assert lint(f, "CLAUDE.md", Preset.SIDE) == []


def test_at_threshold_returns_no_warnings(tmp_path: Path) -> None:
    limit = THRESHOLDS[("agent", Preset.SIDE.value)]
    body = "\n".join(["line"] * limit) + "\n"
    f = _write(tmp_path / "agent.md", body)
    assert lint(f, "agent", Preset.SIDE) == []


def test_over_threshold_returns_warning(tmp_path: Path) -> None:
    limit = THRESHOLDS[("skill", Preset.SIDE.value)]
    body = "\n".join(["line"] * (limit + 25)) + "\n"
    f = _write(tmp_path / "SKILL.md", body)
    warnings = lint(f, "skill", Preset.SIDE)
    assert len(warnings) == 1
    assert "skill" in warnings[0]
    assert "Side" in warnings[0]
    assert "trim" in warnings[0]


def test_frontmatter_excluded_from_count(tmp_path: Path) -> None:
    # 50 frontmatter lines + 5 body lines should be well under skill/Side (100)
    fm_block = "---\n" + "\n".join([f"k{i}: v" for i in range(50)]) + "\n---\n"
    body = "\n".join(["line"] * 5) + "\n"
    f = tmp_path / "SKILL.md"
    f.write_text(fm_block + body, encoding="utf-8")
    assert lint(f, "skill", Preset.SIDE) == []


def test_production_thresholds_are_not_lower(tmp_path: Path) -> None:
    """Production is never stricter than Side, for every asset type.

    `agent` and `skill` are deliberately EQUAL across presets since 0.45.0 — a
    normative contract in an agent body costs the same either way — so the
    invariant is ≥, not >. CLAUDE.md still differentiates, and the concrete case
    below keeps that exercised rather than asserted only in the table.
    """
    for asset in {a for a, _ in THRESHOLDS}:
        side = THRESHOLDS.get((asset, Preset.SIDE.value))
        prod = THRESHOLDS.get((asset, Preset.PRODUCTION.value))
        if side is not None and prod is not None:
            assert prod >= side, f"{asset}: Production({prod}) stricter than Side({side})"

    # 300-line CLAUDE.md: over Side(200), under Production(500) ✓
    body = "\n".join(["line"] * 300) + "\n"
    f = _write(tmp_path / "CLAUDE.md", body)
    assert len(lint(f, "CLAUDE.md", Preset.SIDE)) == 1
    assert lint(f, "CLAUDE.md", Preset.PRODUCTION) == []


def test_workflow_threshold(tmp_path: Path) -> None:
    body = "\n".join(["line"] * 350) + "\n"
    f = _write(tmp_path / "execute.md", body)
    assert len(lint(f, "workflow", Preset.SIDE)) == 1
    assert lint(f, "workflow", Preset.PRODUCTION) == []


def test_other_asset_type_no_limit(tmp_path: Path) -> None:
    body = "\n".join(["line"] * 10000) + "\n"
    f = _write(tmp_path / "data.json", body)
    assert lint(f, "other", Preset.SIDE) == []


def test_unknown_asset_type_no_limit(tmp_path: Path) -> None:
    body = "\n".join(["line"] * 10000) + "\n"
    f = _write(tmp_path / "x.md", body)
    assert lint(f, "totally-unknown", Preset.SIDE) == []


def test_warning_message_includes_path_and_excess(tmp_path: Path) -> None:
    limit = THRESHOLDS[("skill", Preset.SIDE.value)]
    count = limit + 30
    body = "\n".join(["line"] * count) + "\n"
    f = _write(tmp_path / "S.md", body)
    warnings = lint(f, "skill", Preset.SIDE)
    assert str(f) in warnings[0]
    assert str(count) in warnings[0]
    assert str(limit) in warnings[0]


# ── Phase 1: window % hard-cap ──────────────────────────────────────────


def test_lint_window_usage_under_threshold_no_warning() -> None:
    assert lint_window_usage(50_000, model="sonnet") == []


def test_lint_window_usage_over_threshold_warns() -> None:
    warnings = lint_window_usage(100_000, model="sonnet")
    assert len(warnings) == 1
    assert "50%" in warnings[0]
    assert "40%" in warnings[0]


def test_lint_window_usage_at_40_percent_no_warning() -> None:
    assert lint_window_usage(80_000, model="sonnet") == []


def test_lint_window_usage_just_above_40_percent_warns() -> None:
    warnings = lint_window_usage(80_001, model="sonnet")
    assert len(warnings) == 1


def test_lint_window_usage_custom_threshold() -> None:
    assert lint_window_usage(120_000, model="sonnet", threshold=0.7) == []
    warnings = lint_window_usage(150_000, model="sonnet", threshold=0.7)
    assert len(warnings) == 1


# ── Phase 10: MCP server budget warn ─────────────────────────────────────


def test_mcp_under_threshold_no_warning() -> None:
    assert lint_mcp_server_count(3) == []


def test_mcp_at_threshold_no_warning() -> None:
    assert lint_mcp_server_count(6) == []


def test_mcp_over_threshold_warns() -> None:
    warnings = lint_mcp_server_count(7)
    assert len(warnings) == 1
    assert "7" in warnings[0]
    assert "6" in warnings[0]


def test_mcp_custom_threshold() -> None:
    assert lint_mcp_server_count(4, threshold=5) == []
    warnings = lint_mcp_server_count(6, threshold=5)
    assert len(warnings) == 1


def test_mcp_zero_servers_no_warning() -> None:
    assert lint_mcp_server_count(0) == []


def test_agents_md_html_comment_excluded_from_count(tmp_path: Path) -> None:
    """HTML-comment metadata line must not count toward AGENTS.md body line count."""
    # 10 body lines + metadata comment — only body lines count
    body = "\n".join(["line"] * 10) + "\n"
    metadata = "<!-- harness-maker: content_hash=abc version=0.9.0 generated_at=2026-01-01 -->\n"
    f = tmp_path / "AGENTS.md"
    f.write_text(metadata + body, encoding="utf-8")
    warnings = lint(f, "CLAUDE.md", Preset.SIDE)
    assert warnings == []
