"""Phase 4 contract: the rendered /hm:metrics carries the economics section.

These are render-GREP tests over the artifact actually written to disk. They prove the
instruction is PRESENT — they cannot prove the interpreting LLM obeys it. That asymmetry
is ADR-002's stated position: the data layer is enforced (schema test), the prose layer is
instructed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def metrics_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    fake_home = tmp_path_factory.mktemp("hm-home")
    out = tmp_path_factory.mktemp("hm-out")
    monkey = pytest.MonkeyPatch()
    monkey.setattr(Path, "home", lambda: fake_home)
    try:
        fix_dir = Path(__file__).parent.parent / "fixtures" / "prod-tauri-app"
        p = profile(fix_dir)
        a = interview(p, autoloop_mode=True)
        bp = synthesize(p, a)
        render(bp, out, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    finally:
        monkey.undo()
    rendered = out / "commands" / "hm" / "metrics.md"
    if not rendered.is_file():
        pytest.fail(f"metrics.md was not rendered at {rendered}")
    return rendered.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "needle",
    [
        "harness_maker.economics report",
        "Economics: where the tokens went",
        "ingestion.coverage",
        "(unattributed)",
        "estimator_coverage",
        "price_table_version",
        "list-price",
        "carry",
        "rework_coverage",
    ],
)
def test_cost_section_contains(metrics_body: str, needle: str) -> None:
    assert needle in metrics_body


def test_ratio_prohibition_block_is_present(metrics_body: str) -> None:
    """ADR-002 prose layer. A render-grep is the only mechanical hold on it."""
    assert "@hm:economics:no-ratio" in metrics_body
    assert "@hm:/economics:no-ratio" in metrics_body
    assert "Do NOT divide cost by any delivery count" in metrics_body


def test_verify_spend_is_declared_legitimate(metrics_body: str) -> None:
    assert "legitimate category" in metrics_body
    assert "review-driven fixes are counted as `PRODUCE`" in metrics_body


def test_external_model_cost_is_annotated_as_unmeasured(metrics_body: str) -> None:
    """ADR-008 — the incompleteness must be visible, not implied."""
    assert "NOT included" in metrics_body
    assert "codex" in metrics_body
    assert "antigravity" in metrics_body


def test_non_gate_framing_is_inherited(metrics_body: str) -> None:
    assert "never a gate" in metrics_body


def test_the_existing_cfr_and_churn_sections_survive(metrics_body: str) -> None:
    """Phase 4's scope is additive — it must not disturb delivery-metrics content."""
    assert "delivery_metrics candidates" in metrics_body
    assert "CFR" in metrics_body
    assert "churn" in metrics_body
