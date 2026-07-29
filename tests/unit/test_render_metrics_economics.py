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
        "hm economics report",
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


# ------------------------------------------------------ Phase 3: retroactive classification


@pytest.mark.parametrize(
    "needle",
    [
        "hm run_classify boundaries",
        "hm run_classify record",
        "--boundary-uuid",
        "turns_by_attribution_source",
        "usd_by_attribution_source",
        "capped_turns",
        "classification_cache_misses",
        "ledger_ground_truth_disagreements",
        "ambiguous_session_join",
    ],
)
def test_classification_step_contains(metrics_body: str, needle: str) -> None:
    """The command surface and the fields it produces must both be named, or the
    prose layer cannot invoke the one or report the other."""
    assert needle in metrics_body


def test_the_classification_step_precedes_the_report_command(metrics_body: str) -> None:
    """Order is load-bearing, not cosmetic: verdicts recorded AFTER `economics report`
    runs do not reach that report, so the run appears to have recovered nothing and
    the operator concludes the feature does not work."""
    boundaries_at = metrics_body.index("run_classify boundaries")
    record_at = metrics_body.index("run_classify record")
    report_at = metrics_body.index("hm economics report")
    assert boundaries_at < record_at < report_at


def test_the_never_guess_continuation_rule_is_stated(metrics_body: str) -> None:
    """ADR-005's asymmetry is enforced in Python for the cache, but the JUDGMENT is
    the model's. A render-grep is the only mechanical hold on that half."""
    assert "Never guess `continuation`" in metrics_body
    assert "invisible" in metrics_body


def test_the_no_user_message_case_is_called_out_for_the_classifier(metrics_body: str) -> None:
    """The tempting inference — no user message therefore the stage continued — is
    exactly the one that would silently move real spend onto the wrong stage."""
    assert "has_user_message: false" in metrics_body
    assert "does NOT mean continuation" in metrics_body


def test_the_attribution_sources_are_distinguished_as_measured_versus_judged(
    metrics_body: str,
) -> None:
    """A table built from `inferred` rows is a reconstruction. Presenting it as a
    measurement is the substitution this whole workstream exists to avoid."""
    assert "`inferred`" in metrics_body
    assert "judged, not measured" in metrics_body


def test_transcript_content_is_declared_untrusted_for_the_classifier(
    metrics_body: str,
) -> None:
    """Step 5a has the model read arbitrary prior-session text, including tool output
    and file contents — the same exposure Step 2's adjudication already guards."""
    section = metrics_body[metrics_body.index("5a — Recover attribution") :]
    section = section[: section.index("5b — Compute the mix")]
    assert "Untrusted data" in section
    assert "inert DATA" in section
