"""Tests for the spec_need_forcing advisory signal in /hm:health.

PLAN-spec-requirement-gate ADR-008:
- weight=0 AND hard_gate=False — display-only visibility into over/under-forcing,
  never docks the structural score (mirrors judgment_verdict_freshness ADR-001).
- N-A (no signal) when there is no spec-need-*.jsonl ledger at all.
- Degrade silently on malformed lines (no crash).

FIX 4 (R1-P1a): verdict scan excludes spec-need-waiver-*.jsonl files so their
  "verdict" field does not inflate the forcing count.
FIX 5 (R1-P1b): waiver-rate counts spec-need-waiver-*.jsonl files directly
  (no producer ever writes verdict=="waived" into a verdict ledger).
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import Preset
from harness_maker.readiness import _dim_guardrails, compute_readiness

_SIG = "spec_need_forcing"


def _signal_of(project_dir: Path, sig_id: str = _SIG):  # type: ignore[no-untyped-def]
    dim = _dim_guardrails(project_dir)
    return next((s for s in dim.signals if s.id == sig_id), None)


def _obs_dir(project_dir: Path) -> Path:
    d = project_dir / ".claude" / "observability"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_event(
    project_dir: Path,
    verdict: str,
    target: str = "my-feature",
    rationale: str = "test rationale",
) -> None:
    """Append a single spec-need event to the target's ledger."""
    obs = _obs_dir(project_dir)
    ledger = obs / f"spec-need-{target}.jsonl"
    event = {
        "verdict": verdict,
        "target": target,
        "rationale": rationale,
        "detected_at": "2026-06-23T00:00:00+00:00",
        "changed_files_hash": "",
    }
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


# (a) signal FIRES when a spec-need ledger exists with >=1 event
def test_signal_fires_with_one_event(tmp_path: Path) -> None:
    _write_event(tmp_path, "add")
    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.id == _SIG


# (b) evidence reflects verdict counts
def test_evidence_reflects_verdict_counts(tmp_path: Path) -> None:
    _write_event(tmp_path, "add")
    _write_event(tmp_path, "change")
    _write_event(tmp_path, "none")
    sig = _signal_of(tmp_path)
    assert sig is not None
    assert "add=1" in sig.evidence
    assert "change=1" in sig.evidence
    assert "none=1" in sig.evidence


# (c) evidence reflects forcing count (add+change+delete+not-evaluated)
def test_evidence_reflects_forcing_count(tmp_path: Path) -> None:
    _write_event(tmp_path, "add")
    _write_event(tmp_path, "change")
    _write_event(tmp_path, "delete")
    _write_event(tmp_path, "not-evaluated")
    _write_event(tmp_path, "none")
    sig = _signal_of(tmp_path)
    assert sig is not None
    # 4 forcing verdicts, 1 none
    assert "forcing=4" in sig.evidence
    assert "none=1" in sig.evidence


def _write_waiver_receipt(project_dir: Path, slug: str = "my-feature") -> None:
    """Write a waiver receipt file the way write_waiver() actually does.

    Uses a hand-crafted receipt with a fake hash so the test does not need
    real files on disk (compute_subject_hash is not invoked here).
    """
    obs = _obs_dir(project_dir)
    receipt_path = obs / f"spec-need-waiver-{slug}.jsonl"
    receipt = {
        "slug": slug,
        "verdict": "add",
        "target": slug,
        "rationale": "test waiver reason",
        "waiver_hash": "deadbeef1234",
        "waived_at": "2026-06-23T00:00:00+00:00",
    }
    with receipt_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt) + "\n")


# (d) waiver-rate surfaced in evidence (FIX 5: waiver count from receipt files, not
#     verdict=="waived" — no producer ever writes that verdict into a verdict ledger)
def test_evidence_reflects_waiver_rate(tmp_path: Path) -> None:
    _write_event(tmp_path, "add")
    _write_waiver_receipt(tmp_path)  # real waiver receipt, not a synthetic "waived" verdict
    sig = _signal_of(tmp_path)
    assert sig is not None
    assert "waived" in sig.evidence


# (e) N-A: no ledger at all → _dim_guardrails emits NO spec_need_forcing signal
def test_no_ledger_emits_no_signal(tmp_path: Path) -> None:
    # No .claude/observability/ directory at all
    assert _signal_of(tmp_path) is None


def test_obs_dir_present_but_no_spec_need_files_emits_no_signal(tmp_path: Path) -> None:
    # Create the directory and an unrelated file but no spec-need-*.jsonl
    obs = _obs_dir(tmp_path)
    (obs / "other.jsonl").write_text('{"x": 1}\n', encoding="utf-8")
    assert _signal_of(tmp_path) is None


# (f) malformed ledger line → no crash (degrade)
def test_malformed_ledger_line_no_crash(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    ledger = obs / "spec-need-bad.jsonl"
    ledger.write_text("{ this is not valid json [\n", encoding="utf-8")
    sig = _signal_of(tmp_path)  # must not raise
    # The file exists but has no parseable events → 0 total → N-A (no signal)
    assert sig is None


def test_malformed_line_mixed_with_valid_line_degrades_gracefully(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    ledger = obs / "spec-need-mixed.jsonl"
    valid_event = {
        "verdict": "add",
        "target": "mixed",
        "rationale": "ok",
        "detected_at": "2026-06-23T00:00:00+00:00",
        "changed_files_hash": "",
    }
    ledger.write_text(
        "{ broken json [\n" + json.dumps(valid_event) + "\n",
        encoding="utf-8",
    )
    sig = _signal_of(tmp_path)  # must not raise
    # valid line parses → signal fires with the valid event counted
    assert sig is not None
    assert "add=1" in sig.evidence


# (g) score-invariance: weight==0 AND hard_gate is False AND guardrails score AND
#     composite are identical whether the ledger is present-with-forcing-verdicts or absent.
#     Uses a same-filesystem-state comparison: both arms have the .claude/observability/
#     directory (so other dimension signals are identical); only the ledger content differs.
#     Mirror of the judgment stale test's strengthened invariant.
def test_signal_weight_zero_hard_gate_false_score_and_composite_invariant(
    tmp_path: Path,
) -> None:
    # Pre-create the observability dir in both arms so _dim_observability_setup
    # sees the same state and the ceremony_penalty is identical — only the
    # spec-need-*.jsonl ledger differs between the two arms.
    _obs_dir(tmp_path)  # ensures .claude/observability/ exists in both arms

    # arm 1 — observability dir present but NO spec-need ledger (no signal)
    absent_sig = _signal_of(tmp_path)
    assert absent_sig is None
    absent_dim = _dim_guardrails(tmp_path).score
    absent_composite = compute_readiness(tmp_path, Preset.PRODUCTION).composite

    # arm 2 — add several forcing events (signal present, same dir already exists)
    _write_event(tmp_path, "add")
    _write_event(tmp_path, "not-evaluated")
    _write_event(tmp_path, "delete")
    present_sig = _signal_of(tmp_path)
    assert present_sig is not None
    assert present_sig.passed is True  # advisory is always passing
    present_dim = _dim_guardrails(tmp_path).score
    present_composite = compute_readiness(tmp_path, Preset.PRODUCTION).composite

    # verify the advisory constraints
    assert present_sig.weight == 0
    assert present_sig.hard_gate is False

    # the advisory is genuinely display-only — guardrails score and composite unchanged
    assert absent_dim == present_dim
    assert absent_composite == present_composite

    # stronger: the spec-need ledger contributes EXACTLY 0 — the signal is absent
    # when no spec-need files exist (even with the observability dir present).
    no_signal_dir = tmp_path / "bare"
    no_signal_dir.mkdir()
    (no_signal_dir / ".claude" / "observability").mkdir(parents=True)
    assert _signal_of(no_signal_dir) is None
    assert absent_dim == _dim_guardrails(no_signal_dir).score


# (h) signal is always passing (advisory, never fails)
def test_signal_always_passing(tmp_path: Path) -> None:
    _write_event(tmp_path, "not-evaluated")
    _write_event(tmp_path, "add")
    sig = _signal_of(tmp_path)
    assert sig is not None
    assert sig.passed is True


# (i) multi-target ledgers: events across multiple targets are aggregated
def test_multi_target_ledgers_aggregated(tmp_path: Path) -> None:
    _write_event(tmp_path, "add", target="feature-a")
    _write_event(tmp_path, "none", target="feature-b")
    _write_event(tmp_path, "delete", target="feature-c")
    sig = _signal_of(tmp_path)
    assert sig is not None
    # 3 events total
    assert "add=1" in sig.evidence
    assert "none=1" in sig.evidence
    assert "delete=1" in sig.evidence
    assert "forcing=2" in sig.evidence  # add + delete


# FIX 4 (R1-P1a) — waiver receipt files must NOT be scanned for verdicts.
# A spec-need-waiver-{slug}.jsonl file has a "verdict" key that mirrors the
# original verdict; if included in the verdict scan, the forcing count inflates.
def test_waiver_receipt_file_not_counted_in_verdict_scan(tmp_path: Path) -> None:
    # One forcing event in the verdict ledger
    _write_event(tmp_path, "add", target="feat")
    # One waiver receipt (a SEPARATE file, not a verdict ledger)
    _write_waiver_receipt(tmp_path, slug="feat")
    sig = _signal_of(tmp_path)
    assert sig is not None
    # forcing must be 1 (the one verdict-ledger event), not 2
    assert "forcing=1" in sig.evidence
    # The waiver receipt file's "verdict" field must NOT appear as a verdict count
    # (a real spec-need-waiver-*.jsonl has verdict="add" in it; if scanned, add=2)
    assert "add=1" in sig.evidence
    assert "add=2" not in sig.evidence


# FIX 5 (R1-P1b) — waiver count comes from waiver receipt files, not from
# a "verdict=='waived'" value (no producer ever writes that verdict).
def test_waiver_count_from_receipt_files_not_verdict_field(tmp_path: Path) -> None:
    # One forcing event
    _write_event(tmp_path, "add", target="feat")
    # Two waiver receipts for two different slugs
    _write_waiver_receipt(tmp_path, slug="feat")
    _write_waiver_receipt(tmp_path, slug="feat2")
    sig = _signal_of(tmp_path)
    assert sig is not None
    # waived=2 must appear (two receipt files)
    assert "waived=2" in sig.evidence
    # The rate line should reflect 2 waivers against 1 forcing event
    assert "2/1 waived" in sig.evidence


def test_only_waiver_receipt_files_no_verdict_ledger_emits_no_signal(tmp_path: Path) -> None:
    # Only waiver receipt files with no verdict ledger — the signal must NOT fire
    # (N-A rule: signal only fires when there are verdict-ledger events).
    _write_waiver_receipt(tmp_path, slug="feat")
    assert _signal_of(tmp_path) is None
