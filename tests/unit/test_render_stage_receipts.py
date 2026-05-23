"""Tests for PLAN-loop-mid-stop-and-review-skip Phase 2.

Each fused-workflow stage (execute / review / wrapup / plan / spec / research)
must emit a Gate 0 receipt at stage close. This test renders the full harness
and asserts the receipt-emit Bash block is present in every rendered atomic
stage command file.

The block must:
1. Reference `harness_maker.iter_receipts write` — the CLI under ADR-004.
2. Pass `--stage <name>` with the correct stage identifier per file.
3. Read `$ITER` from `.claude/.hm-iter-receipts/.current-iter` (driver-written
   per ADR-001) with a graceful fallback when the file is absent.
4. Appear AFTER the stage's main procedure (Step 0..Step 4) and BEFORE the
   "## Outputs" section so it fires after work completes but before the file
   reader hits anything resembling closing summary text.
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
    """Render the full harness once per module (slow setup, fast asserts)."""
    out = tmp_path_factory.mktemp("rendered")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


STAGE_NAMES = ("execute", "review", "wrapup", "plan", "spec", "research")


@pytest.mark.parametrize("stage", STAGE_NAMES)
def test_stage_command_contains_receipt_emit(rendered_root: Path, stage: str) -> None:
    """Every atomic stage command file emits a receipt at stage close."""
    cmd_file = rendered_root / "commands" / "hm" / f"{stage}.md"
    assert cmd_file.is_file(), f"missing rendered command file: {cmd_file}"
    body = cmd_file.read_text(encoding="utf-8")
    # Receipt CLI invocation must be present.
    assert "harness_maker.iter_receipts write" in body, (
        f"{stage}.md is missing the iter_receipts CLI invocation"
    )
    # Stage name must be passed to --stage so the receipt path is correct.
    assert f"--stage {stage}" in body, (
        f"{stage}.md does not pass --stage {stage} to iter_receipts CLI"
    )
    # ITER must come from the driver-written marker file with fallback.
    assert ".hm-iter-receipts/.current-iter" in body, (
        f"{stage}.md does not read ITER from .current-iter"
    )


@pytest.mark.parametrize("stage", STAGE_NAMES)
def test_receipt_emit_positioned_before_outputs(rendered_root: Path, stage: str) -> None:
    """Receipt-emit must appear AFTER the procedure and BEFORE '## Outputs'.

    Positioning matters: a Bash block above the procedure would write the
    receipt before any work; below '## Outputs' would put it inside summary
    prose that an LLM may not reach. The contract is: emit *after* the last
    procedural step but *before* the outputs section.
    """
    cmd_file = rendered_root / "commands" / "hm" / f"{stage}.md"
    body = cmd_file.read_text(encoding="utf-8")
    receipt_idx = body.find("harness_maker.iter_receipts write")
    assert receipt_idx > 0, f"{stage}.md missing receipt-emit"
    outputs_idx = body.find("## Outputs")
    assert outputs_idx > 0, f"{stage}.md missing '## Outputs' anchor"
    assert receipt_idx < outputs_idx, (
        f"{stage}.md receipt-emit at {receipt_idx} is after '## Outputs' at "
        f"{outputs_idx} — must appear before Outputs"
    )


@pytest.mark.parametrize("stage", STAGE_NAMES)
def test_receipt_block_warns_against_skipped_verdict(rendered_root: Path, stage: str) -> None:
    """ADR-005: every stage's receipt-emit section must carry the warning.

    Each stage template holds its own verbatim copy of the receipt block (no
    shared Jinja macro), so the warning must be asserted per-stage. A future
    edit that drops the warning from one template must fail this test.
    """
    cmd_file = rendered_root / "commands" / "hm" / f"{stage}.md"
    body = cmd_file.read_text(encoding="utf-8")
    section_idx = body.find("Emit Gate 0 receipt")
    receipt_idx = body.find("harness_maker.iter_receipts write")
    assert section_idx > 0, f"{stage}.md missing 'Emit Gate 0 receipt' section"
    assert receipt_idx > section_idx, (
        f"{stage}.md receipt CLI invocation must appear after the section heading"
    )
    section = body[section_idx : receipt_idx + 200]
    assert "skipped" in section, (
        f"{stage}.md receipt-emit section must warn against emitting verdict=skipped"
    )


def test_fused_workflow_inherits_receipts(rendered_root: Path) -> None:
    """exec-rev fuses execute+review — both receipt blocks must appear.

    Without this, an iter that runs exec-rev would only emit one receipt and
    Gate 0 would never see both stages — the original 2026-05-22 silent-skip
    failure mode is preserved.
    """
    cmd_file = rendered_root / "commands" / "hm" / "exec-rev.md"
    assert cmd_file.is_file(), (
        "exec-rev fused workflow must exist in the default harness — the loop's "
        "default per-iter workflow needs it (loop.md.j2 step 6)"
    )
    body = cmd_file.read_text(encoding="utf-8")
    assert "--stage execute" in body
    assert "--stage review" in body
