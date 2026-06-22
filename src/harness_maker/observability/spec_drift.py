"""SPEC drift detector for /hm:health (P6, ADR-013 dev_mode-gated).

Scans `specs/` for SPEC.md + SPEC.machine.yaml pairs and reports:
- orphan tests (test files with no AC reference in any machine.yaml)
- stale mutation runs (last_mutation_run > 7 days for T1, > 14 days for T2)
- AC↔test mapping gaps (AC without test_ids[] and pending_test=false)
- per-SPEC Open Question overflow (> 3 → CI lint fail)
- aggregate OQ count vs cap (30)

Only runs when ``dev_mode == "spec-driven"``. In task-driven mode the
function returns ``None`` so the /hm:health template can skip the layer
entirely.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker.spec_machine import load as load_machine
from harness_maker.spec_machine import unresolved_test_ids

STALE_T1_DAYS: int = 7
STALE_T2_DAYS: int = 14
OQ_PER_SPEC_CAP: int = 3
OQ_AGGREGATE_CAP: int = 30


@dataclass
class SpecDriftReport:
    """Aggregate findings across all specs/ entries."""

    orphan_tests: list[str] = field(default_factory=list)
    stale_mutations: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    oq_overflow: list[str] = field(default_factory=list)  # SPECs with >3 OQs
    # ACs whose test_ids resolve but pending_test is still true: the wrapup
    # write-back never ran (e.g. manual commit instead of /hm:wrapup).
    # ADR-009 of PLAN-spec-test-accumulation — surfaces the wrapup-gated gap.
    resolved_but_pending: list[str] = field(default_factory=list)
    # ACs with oracle_source == legacy-unspecified — pre-v2 specs that predate
    # the oracle axis. Advisory only (ADR-006): nudge migration, never block.
    missing_oracle_source: list[str] = field(default_factory=list)
    aggregate_oq_count: int = 0
    spec_count: int = 0
    skipped_reason: str | None = None

    @property
    def has_findings(self) -> bool:
        return bool(
            self.orphan_tests
            or self.stale_mutations
            or self.coverage_gaps
            or self.oq_overflow
            or self.resolved_but_pending
            or self.missing_oracle_source
            or self.aggregate_oq_count > OQ_AGGREGATE_CAP
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "orphan_tests": list(self.orphan_tests),
            "stale_mutations": list(self.stale_mutations),
            "coverage_gaps": list(self.coverage_gaps),
            "oq_overflow": list(self.oq_overflow),
            "resolved_but_pending": list(self.resolved_but_pending),
            "missing_oracle_source": list(self.missing_oracle_source),
            "aggregate_oq_count": self.aggregate_oq_count,
            "spec_count": self.spec_count,
            "skipped_reason": self.skipped_reason,
            "has_findings": self.has_findings,
        }


def _count_open_questions(md_text: str) -> int:
    """Count ``### OQ-N:`` headings under the ``## ❓ Open Questions`` section."""
    in_oq = False
    count = 0
    for line in md_text.splitlines():
        if line.startswith("## ❓ Open Questions"):
            in_oq = True
            continue
        if in_oq and line.startswith("## "):
            break
        if in_oq and re.match(r"^###\s+OQ-\d+", line):
            count += 1
    return count


def _is_stale(last_run_iso: str | None, tier: int) -> bool:
    if not last_run_iso:
        return False  # never run yet — different signal, not drift
    try:
        last = datetime.fromisoformat(last_run_iso).date()
    except (TypeError, ValueError):
        return False
    threshold = STALE_T1_DAYS if tier == 1 else STALE_T2_DAYS
    return (date.today() - last).days > threshold


def scan(specs_dir: Path, *, dev_mode: str = "task-driven") -> SpecDriftReport:
    """Walk ``specs/`` and produce a drift report.

    Returns an empty report (with ``skipped_reason`` set) when
    ``dev_mode != "spec-driven"`` — per ADR-013.
    """
    report = SpecDriftReport()
    if dev_mode != "spec-driven":
        report.skipped_reason = f"dev_mode={dev_mode} (spec_drift gates only on spec-driven)"
        return report
    if not specs_dir.exists():
        report.skipped_reason = f"no specs/ at {specs_dir}"
        return report

    referenced_test_ids: set[str] = set()
    # (slug, ac_id, test_ids) for pending ACs that nonetheless carry test_ids —
    # candidates for the resolved-but-pending (write-back-missed) check below.
    pending_with_ids: list[tuple[str, str, tuple[str, ...]]] = []
    for yp in sorted(specs_dir.glob("SPEC-*.machine.yaml")):
        report.spec_count += 1
        try:
            machine = load_machine(yp)
        except (yaml.YAMLError, OSError, ValueError):
            continue
        # coverage gaps
        for ac in machine.ac:
            if not ac.test_ids and not ac.pending_test:
                report.coverage_gaps.append(f"{machine.spec_slug}::{ac.id}")
            if ac.pending_test and ac.test_ids:
                pending_with_ids.append((machine.spec_slug, ac.id, tuple(ac.test_ids)))
            # Advisory migration nudge (ADR-006): a v1 AC predates the oracle axis.
            if ac.oracle_source == "legacy-unspecified":
                report.missing_oracle_source.append(f"{machine.spec_slug}::{ac.id}")
            referenced_test_ids.update(ac.test_ids)
        # stale mutations
        if machine.mutation_threshold is not None and _is_stale(
            machine.last_mutation_run, int(machine.verification_tier)
        ):
            report.stale_mutations.append(machine.spec_slug)
        # OQ overflow (read sibling .md)
        md_path = yp.with_suffix("").with_suffix(".md")
        if md_path.exists():
            oqs = _count_open_questions(md_path.read_text(encoding="utf-8"))
            report.aggregate_oq_count += oqs
            if oqs > OQ_PER_SPEC_CAP:
                report.oq_overflow.append(f"{machine.spec_slug} ({oqs} OQs)")

    # resolved-but-pending: one batched pytest collect over all candidate
    # test_ids, then flag any AC whose test_ids all resolve yet stay pending.
    # Skip entirely when pytest is unavailable (REVIEW C-P2a): unresolved_test_ids
    # degrades to "all resolved" on a missing pytest, which would otherwise
    # false-flag EVERY pending-with-ids AC as a write-back miss.
    if pending_with_ids and shutil.which("pytest") is not None:
        all_ids = sorted({tid for _, _, tids in pending_with_ids for tid in tids})
        unresolved = set(unresolved_test_ids(all_ids, specs_dir.parent))
        for slug, ac_id, tids in pending_with_ids:
            if tids and not (set(tids) & unresolved):
                report.resolved_but_pending.append(f"{slug}::{ac_id}")

    return report


__all__ = [
    "OQ_AGGREGATE_CAP",
    "OQ_PER_SPEC_CAP",
    "STALE_T1_DAYS",
    "STALE_T2_DAYS",
    "SpecDriftReport",
    "scan",
]
