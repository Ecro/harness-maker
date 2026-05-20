"""Tests for observability.spec_drift (P6, ADR-013)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from harness_maker.observability.spec_drift import (
    OQ_AGGREGATE_CAP,
    OQ_PER_SPEC_CAP,
    _count_open_questions,
    _is_stale,
    scan,
)


def test_dev_mode_task_driven_skips() -> None:
    report = scan(Path("/nonexistent"), dev_mode="task-driven")
    assert report.skipped_reason is not None
    assert "task-driven" in report.skipped_reason
    assert not report.has_findings


def test_dev_mode_spec_driven_runs_even_without_dir(tmp_path: Path) -> None:
    report = scan(tmp_path / "missing", dev_mode="spec-driven")
    assert report.skipped_reason is not None
    assert "no specs/" in report.skipped_reason


def _seed_spec(
    specs_dir: Path,
    slug: str,
    *,
    tier: int = 1,
    ac: list[dict] | None = None,
    last_mutation_run: str | None = None,
    oqs: int = 0,
) -> None:
    specs_dir.mkdir(parents=True, exist_ok=True)
    yp = specs_dir / f"SPEC-{slug}.machine.yaml"
    yaml_data = {
        "schema_version": 1,
        "spec_slug": slug,
        "verification_tier": tier,
        "mutation_threshold": 85 if tier == 1 else 70,
        "last_mutation_run": last_mutation_run,
        "paths_to_mutate": ["x.py"],
        "ac": ac
        or [
            {
                "id": "AC-001",
                "title": "t",
                "type": "mechanical",
                "test_ids": ["t::f"],
                "executable_predicate": "True",
            }
        ],
    }
    yp.write_text(yaml.safe_dump(yaml_data))
    md = specs_dir / f"SPEC-{slug}.md"
    body = ["---", f"task_slug: {slug}", "---", "# SPEC", "## ❓ Open Questions"]
    for i in range(oqs):
        body.append(f"### OQ-{i + 1}: example open question {i + 1}")
        body.append("")
    md.write_text("\n".join(body) + "\n")


def test_scan_finds_coverage_gap(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed_spec(
        specs,
        "x",
        ac=[
            {
                "id": "AC-001",
                "title": "t",
                "type": "mechanical",
                "executable_predicate": "True",
                "test_ids": [],
                "pending_test": False,
            }
        ],
    )
    report = scan(specs, dev_mode="spec-driven")
    assert "x::AC-001" in report.coverage_gaps


def test_scan_pending_test_does_not_flag_coverage_gap(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed_spec(
        specs,
        "x",
        ac=[
            {
                "id": "AC-001",
                "title": "t",
                "type": "mechanical",
                "executable_predicate": "True",
                "test_ids": [],
                "pending_test": True,
            }
        ],
    )
    report = scan(specs, dev_mode="spec-driven")
    assert report.coverage_gaps == []


def test_scan_stale_mutation_t1(tmp_path: Path) -> None:
    old = (date.today() - timedelta(days=14)).isoformat()
    specs = tmp_path / "specs"
    _seed_spec(specs, "x", tier=1, last_mutation_run=old)
    report = scan(specs, dev_mode="spec-driven")
    assert "x" in report.stale_mutations


def test_scan_fresh_mutation_t1(tmp_path: Path) -> None:
    today = date.today().isoformat()
    specs = tmp_path / "specs"
    _seed_spec(specs, "x", tier=1, last_mutation_run=today)
    report = scan(specs, dev_mode="spec-driven")
    assert report.stale_mutations == []


def test_scan_no_last_mutation_run_not_stale(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed_spec(specs, "x", tier=1, last_mutation_run=None)
    report = scan(specs, dev_mode="spec-driven")
    assert report.stale_mutations == []


def test_count_open_questions_counts_headings() -> None:
    text = (
        "# SPEC\n## ❓ Open Questions\n"
        "### OQ-1: a\n### OQ-2: b\n### OQ-3: c\n"
        "## Next Section\n### OQ-4: not counted\n"
    )
    assert _count_open_questions(text) == 3


def test_scan_oq_overflow(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed_spec(specs, "x", oqs=OQ_PER_SPEC_CAP + 1)
    report = scan(specs, dev_mode="spec-driven")
    assert any("x" in s for s in report.oq_overflow)


def test_scan_oq_aggregate(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed_spec(specs, "a", oqs=2)
    _seed_spec(specs, "b", oqs=3)
    report = scan(specs, dev_mode="spec-driven")
    assert report.aggregate_oq_count == 5


def test_constants_unchanged() -> None:
    assert OQ_PER_SPEC_CAP == 3
    assert OQ_AGGREGATE_CAP == 30


def test_is_stale_invalid_date_returns_false() -> None:
    assert _is_stale("not-a-date", 1) is False
