"""Phase 5 — /hm:metrics command surface + health narrative rendering (AC-009/010, ADR-002)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    DeliveryMetricsConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(tmp_path: Path, *, enabled: bool) -> dict[str, str]:
    answers = InterviewAnswers(
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE],
        delivery_metrics=DeliveryMetricsConfig(enabled=enabled),
    )
    blueprint = synthesize(ProjectProfile(), answers)
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        str(f.relative_to(tmp_path)): f.read_text(encoding="utf-8") for f in tmp_path.rglob("*.md")
    }


def _file(files: dict[str, str], suffix: str) -> str:
    return next(t for p, t in files.items() if p.endswith(suffix))


def test_metrics_command_blocks_when_enabled_and_absent_when_disabled(tmp_path: Path) -> None:
    """AC-010 + AC-009 (render half), paired positive/negative in one function
    (test-reviewer R1: a lone negative check is vacuously true pre-implementation).

    Enabled: the rendered command carries the trend-display, raw-counts,
    baseline-delta, and LLM-interpretation instruction blocks (the machine
    oracle's fixed 5-marker set) plus the two-pass adjudication flow and the
    maturation-lag disclaimer. Disabled: the command file is NOT rendered and
    no rendered file invokes the module.
    """
    enabled_files = _render(tmp_path / "on", enabled=True)
    body = _file(enabled_files, "commands/hm/metrics.md")
    required_metrics_markers = [
        "harness_maker.delivery_metrics candidates",
        "harness_maker.delivery_metrics adjudicate",
        "harness_maker.delivery_metrics compute",
        "harness_maker.delivery_metrics trend",
        "failed/total",  # raw counts, never percentage alone (SPEC Outcomes)
        "baseline delta",
        "Interpret the trend",  # LLM-interpretation instruction block (AC-010)
        "improvement suggestions",
        "maturation",  # churn lag disclaimer (ADR-004 consequence)
        "Untrusted data",  # REVIEW security P1: prompt-injection framing for commit content
    ]
    assert all(marker in body for marker in required_metrics_markers), [
        m for m in required_metrics_markers if m not in body
    ]
    # Two-pass ordering: candidates → adjudicate → compute (ADR-006).
    assert body.index("delivery_metrics candidates") < body.index("delivery_metrics compute")

    disabled_files = _render(tmp_path / "off", enabled=False)
    assert not any(p.endswith("commands/hm/metrics.md") for p in disabled_files)
    for path, disabled_body in disabled_files.items():
        assert "harness_maker.delivery_metrics" not in disabled_body, path


def test_health_narrative_block_gated(tmp_path: Path) -> None:
    """ADR-002: /hm:health gains a marker-fenced delivery-metrics narrative
    when enabled; disabled renders keep health byte-free of the feature."""
    enabled = _file(_render(tmp_path / "on", enabled=True), "commands/hm/health.md")
    assert "@hm:delivery-metrics" in enabled
    assert "harness_maker.delivery_metrics trend" in enabled
    disabled = _file(_render(tmp_path / "off", enabled=False), "commands/hm/health.md")
    assert "delivery-metrics" not in disabled
    assert "delivery_metrics" not in disabled


def test_help_lists_metrics_only_when_enabled(tmp_path: Path) -> None:
    """ADR-002 + 0.34.0 command-surface parity: /hm:help advertises the
    command iff it exists on disk."""
    on = _file(_render(tmp_path / "on", enabled=True), "commands/hm/help.md")
    assert "metrics" in on
    off = _file(_render(tmp_path / "off", enabled=False), "commands/hm/help.md")
    assert "metrics" not in off
