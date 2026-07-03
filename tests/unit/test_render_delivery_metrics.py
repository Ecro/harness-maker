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


def test_metrics_command_full_when_enabled_stub_when_disabled(tmp_path: Path) -> None:
    """ADR-002 (amended — visibility follow-up): /hm:metrics is ALWAYS rendered
    for discoverability, but the template branches on enabled.

    Enabled: the full CFR+churn command — trend-display, raw-counts,
    baseline-delta, LLM-interpretation (the machine oracle's fixed marker set),
    two-pass adjudication flow, maturation-lag disclaimer, untrusted-data framing.
    Disabled: the command file STILL exists but is a stub — no module invocation
    (compute stays opt-in), and it points the user at /hm:configure to enable.
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

    # Disabled: the command STILL renders (discoverability) but as an inert stub.
    disabled_files = _render(tmp_path / "off", enabled=False)
    stub = _file(disabled_files, "commands/hm/metrics.md")
    assert "Delivery metrics are OFF" in stub
    assert "configure" in stub  # points at /hm:configure to enable
    # AC-009 (opt-in compute): the disabled stub must NOT instruct the module to run.
    assert "harness_maker.delivery_metrics" not in stub
    for path, disabled_body in disabled_files.items():
        if path.endswith("commands/hm/metrics.md"):
            continue  # the stub is the only place the feature name may appear
        assert "harness_maker.delivery_metrics" not in disabled_body, path


def test_health_narrative_block_gated(tmp_path: Path) -> None:
    """ADR-002: /hm:health gains a marker-fenced delivery-metrics narrative
    when enabled; disabled renders keep health byte-free of the feature
    (the narrative needs ledger data that only exists once enabled)."""
    enabled = _file(_render(tmp_path / "on", enabled=True), "commands/hm/health.md")
    assert "@hm:delivery-metrics" in enabled
    assert "harness_maker.delivery_metrics trend" in enabled
    disabled = _file(_render(tmp_path / "off", enabled=False), "commands/hm/health.md")
    assert "delivery-metrics" not in disabled
    assert "delivery_metrics" not in disabled


def test_help_always_lists_metrics(tmp_path: Path) -> None:
    """ADR-002 (amended): /hm:metrics always exists on the surface, so /hm:help
    always advertises it; disabled adds an opt-in hint pointing at configure."""
    on = _file(_render(tmp_path / "on", enabled=True), "commands/hm/help.md")
    assert "metrics" in on
    off = _file(_render(tmp_path / "off", enabled=False), "commands/hm/help.md")
    assert "metrics" in off  # listed even when disabled (discoverability)
    assert "opt-in" in off  # with the enable hint
