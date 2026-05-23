"""Tests for PLAN-loop-mid-stop-and-review-skip Phase 3.

Phase 3 wires Gate 0 (receipt verification) into the rendered ``loop.md``
together with the ``.current-iter`` driver write, ``stage_retry_counts``
counter persistence, and ADR-005 auto-retry semantics.

All assertions are string-level on the rendered output so the contract is
visible to the autoloop driver LLM at runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


@pytest.fixture(scope="module")
def rendered_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered-loop")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


@pytest.fixture(scope="module")
def loop_md(rendered_root: Path) -> str:
    return (rendered_root / "commands" / "hm" / "loop.md").read_text(encoding="utf-8")


# ── runtime schema ──────────────────────────────────────────────────────────


def test_runtime_block_contains_stage_retry_counts(loop_md: str) -> None:
    """Step 4-F persistence schema must include the auto-retry counter map."""
    runtime_start = loop_md.find("runtime:")
    assert runtime_start > 0, "loop.md missing 'runtime:' YAML block"
    last_test_idx = loop_md.find("last_test_result", runtime_start)
    assert last_test_idx > 0, "loop.md runtime block missing last_test_result"
    schema_region = loop_md[runtime_start:last_test_idx]
    assert "stage_retry_counts" in schema_region, (
        "runtime: block must declare stage_retry_counts so /compact recovery "
        "can reload it (ADR-005, ADR-006)"
    )


def test_compact_recovery_reloads_stage_retry_counts(loop_md: str) -> None:
    """The /compact recovery instruction must mention stage_retry_counts.

    Without this reload, a /compact between Gate 0 retries would reset the
    retry budget every cycle — defeating the cap=2 semantics in ADR-005.
    """
    recovery_idx = loop_md.find("Post-`/compact` recovery")
    assert recovery_idx > 0, "loop.md missing post-/compact recovery section"
    # Look in the recovery paragraph (next ~600 chars after the heading).
    recovery_block = loop_md[recovery_idx : recovery_idx + 800]
    assert "stage_retry_counts" in recovery_block, (
        "post-/compact recovery list must reload stage_retry_counts"
    )


# ── .current-iter write ─────────────────────────────────────────────────────


def test_current_iter_marker_written_at_iter_start(loop_md: str) -> None:
    """Driver must write <WT>/.claude/.hm-iter-receipts/.current-iter at iter start.

    Stage templates read this file to derive ITER for their receipt-emit
    blocks (P2 contract). Without the driver writing it, the stage's shell
    guard sees no file and the receipt block is a no-op.
    """
    # Phase 3 originally wrote the marker via `printf > file`. Post-commit
    # P1 #1 fix replaced that non-atomic redirect with the atomic
    # `iter_receipts set-iter-marker` CLI subcommand (Python atomic_write).
    has_marker_write = (
        "iter_receipts set-iter-marker" in loop_md
        or ".hm-iter-receipts/.current-iter" in loop_md
    )
    assert has_marker_write, (
        "loop.md missing the .current-iter driver write — expected the "
        "`iter_receipts set-iter-marker` CLI invocation in Step 3.5"
    )


# ── Gate 0 receipt verification ─────────────────────────────────────────────


def test_gate0_invokes_iter_receipts_verify(loop_md: str) -> None:
    """Gate 0 mechanically checks per-stage receipts via the CLI."""
    assert "harness_maker.iter_receipts verify" in loop_md, (
        "loop.md missing Gate 0 verification CLI call (iter_receipts verify)"
    )


def test_gate0_documents_auto_retry_cap(loop_md: str) -> None:
    """ADR-005: cap=2 auto-retries per (iter, stage), then escalation."""
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    assert gate0_idx > 0, "loop.md missing 'Gate 0' section heading"
    gate0_section = loop_md[gate0_idx : gate0_idx + 7000]
    # The cap is explicit numeric, not vague.
    has_cap = (
        "cap=2" in gate0_section
        or "2 retries" in gate0_section
        or "cap of 2" in gate0_section
    )
    assert has_cap, "Gate 0 prose must state the auto-retry cap=2 from ADR-005"
    # Escalation route mentions the standard ask-tool.
    assert "AskUserQuestion" in gate0_section or "request_user_input" in gate0_section, (
        "Gate 0 escalation after cap exhausted must call AskUserQuestion / request_user_input"
    )


def test_gate0_appears_before_state_update(loop_md: str) -> None:
    """Gate 0 must fire AFTER workflow invocation but BEFORE 'Update state'."""
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    workflow_idx = loop_md.find("Invoke per-iter workflow")
    # Anchor on the step-5 header (markdown bold) not the Gate 4 prose mention.
    update_idx = loop_md.find("5. **Update state**")
    assert workflow_idx > 0, "loop.md missing 'Invoke per-iter workflow' step"
    assert update_idx > 0, "loop.md missing 'Update state' step"
    assert gate0_idx > 0, "loop.md missing 'Gate 0' step"
    assert workflow_idx < gate0_idx < update_idx, (
        f"Gate 0 must be between Invoke per-iter workflow (idx={workflow_idx}) "
        f"and Update state (idx={update_idx}); got Gate 0 idx={gate0_idx}"
    )


def test_gate0_failure_does_not_increment_failed_streak(loop_md: str) -> None:
    """ADR-005 rule: Gate 0 auto-retries do NOT increment failed_streak.

    Mixing them would let safety rail #3 (cap=5) fire before per-stage
    diagnosis surfaces. The prose must be explicit so the LLM driver
    cannot mis-route.
    """
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    gate0_section = loop_md[gate0_idx : gate0_idx + 7000]
    # Phrase may span a line break ("do NOT increment\n  `failed_streak`"),
    # so check the two halves and proximity rather than a single literal.
    idx_neg = gate0_section.find("do NOT increment")
    idx_streak = gate0_section.find("failed_streak", idx_neg if idx_neg >= 0 else 0)
    assert idx_neg >= 0, "Gate 0 prose missing 'do NOT increment' phrasing"
    assert idx_streak >= 0, "Gate 0 prose missing 'failed_streak' near exclusion"
    assert (idx_streak - idx_neg) < 50, (
        "'do NOT increment' and 'failed_streak' must be in the same sentence (ADR-005)"
    )


def test_gate0_option_b_breaks_out_of_reverify_loop(loop_md: str) -> None:
    """ADR-005 Option B (skipped marker) must explicitly bypass re-verify.

    Without an explicit "do NOT return to step 4.5" instruction, the LLM
    driver would re-run Gate 0 after writing the skipped marker; Gate 0
    would see verdict != pass and re-escalate forever. The prose must
    short-circuit the loop.
    """
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    gate0_section = loop_md[gate0_idx : gate0_idx + 7000]
    # Find Option B
    option_b_idx = gate0_section.find("Skip with explicit")
    assert option_b_idx > 0, "Gate 0 escalation missing 'Skip with explicit' option"
    option_b_block = gate0_section[option_b_idx : option_b_idx + 1500]
    # Must explicitly tell driver NOT to return to step 4.5
    has_bypass = (
        "do NOT return to step 4.5" in option_b_block
        or "jump directly to step 5" in option_b_block
        or "not return to step 4.5" in option_b_block
    )
    assert has_bypass, (
        "Option B must explicitly state it bypasses step 4.5 re-verify "
        "(otherwise infinite escalation deadlock — code-reviewer P1)"
    )


def test_loop_close_clears_stage_retry_counts(loop_md: str) -> None:
    """Step 7 must clear stage_retry_counts to prevent unbounded YAML growth.

    Without this, a 50-iter loop persists up to 200 entries that are reloaded
    on every /compact even though their cycles are closed.
    """
    close_idx = loop_md.find("Loop close — UNIFIED")
    assert close_idx > 0, "loop.md missing Step 7 'Loop close' heading"
    close_section = loop_md[close_idx : close_idx + 2000]
    has_cleanup = (
        "Clear `stage_retry_counts`" in close_section
        or "clear stage_retry_counts" in close_section
    )
    assert has_cleanup, (
        "Step 7 must clear stage_retry_counts at loop close (memory hygiene)"
    )


def test_gate0_treats_non_pass_verdict_as_failure(loop_md: str) -> None:
    """ADR-005 closes verdict-forging: skipped/fail trigger retry."""
    gate0_idx = loop_md.find("Gate 0 — Receipt verification")
    gate0_section = loop_md[gate0_idx : gate0_idx + 7000]
    # Must mention non-pass verdict triggering Gate 0 failure.
    has_verdict_rule = (
        "verdict != \"pass\"" in gate0_section
        or "verdict != 'pass'" in gate0_section
        or "non-pass verdict" in gate0_section
        or "verdict is not pass" in gate0_section
    )
    assert has_verdict_rule, (
        "Gate 0 must spell out: verdict != 'pass' counts as failure "
        "(closes 'forge skipped to bypass' loophole, ADR-005)"
    )
