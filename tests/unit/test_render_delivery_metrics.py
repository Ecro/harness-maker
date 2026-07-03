"""Phase 5 — /hm:metrics command surface + health narrative rendering (AC-010, ADR-002).

0.36.0: the feature has no enable flag — /hm:metrics always renders the full
command; /hm:health always carries the narrative block.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(tmp_path: Path) -> dict[str, str]:
    answers = InterviewAnswers(preset=Preset.SIDE, targets=[Target.CLAUDE_CODE])
    blueprint = synthesize(ProjectProfile(), answers)
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        str(f.relative_to(tmp_path)): f.read_text(encoding="utf-8") for f in tmp_path.rglob("*.md")
    }


def _file(files: dict[str, str], suffix: str) -> str:
    return next(t for p, t in files.items() if p.endswith(suffix))


def test_metrics_command_always_full(tmp_path: Path) -> None:
    """AC-010 (0.36.0): /hm:metrics always renders the full CFR+churn command —
    trend-display, raw-counts, baseline-delta, LLM-interpretation (the machine
    oracle's fixed marker set), two-pass adjudication flow, maturation-lag
    disclaimer, untrusted-data framing — with no enable gate and no stub."""
    body = _file(_render(tmp_path), "commands/hm/metrics.md")
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
    # No enable/disable stub text survives.
    assert "Delivery metrics are OFF" not in body


def test_health_narrative_always_present(tmp_path: Path) -> None:
    """AC-010 (0.36.0): /hm:health always carries the marker-fenced
    delivery-metrics narrative; its empty-ledger branch handles the never-run
    case at runtime (no render-time enable gate)."""
    health = _file(_render(tmp_path), "commands/hm/health.md")
    assert "@hm:delivery-metrics" in health
    assert "harness_maker.delivery_metrics trend" in health
    assert "Empty ledger" in health  # the runtime never-run branch


def test_help_lists_metrics(tmp_path: Path) -> None:
    """0.36.0: /hm:metrics always exists, so /hm:help always advertises it as a
    manual read-only command (no opt-in/enable hint)."""
    help_body = _file(_render(tmp_path), "commands/hm/help.md")
    assert "metrics" in help_body
    assert "read-only" in help_body
    assert "opt-in" not in help_body  # no enable gate to advertise
