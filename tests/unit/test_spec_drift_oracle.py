"""Phase 6 — spec_drift surfaces missing_oracle_source as an advisory (ADR-006)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from harness_maker.observability.spec_drift import scan


def _seed(specs_dir: Path, slug: str, ac: dict[str, Any]) -> None:
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / f"SPEC-{slug}.machine.yaml").write_text(
        yaml.safe_dump({"spec_slug": slug, "verification_tier": 1, "ac": [ac]}),
        encoding="utf-8",
    )


def test_legacy_ac_flagged_as_missing_oracle_source(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed(
        specs,
        "legacy",
        {"id": "AC-001", "title": "t", "type": "mechanical", "pending_test": True},
    )
    report = scan(specs, dev_mode="spec-driven")
    assert "legacy::AC-001" in report.missing_oracle_source
    assert report.has_findings is True
    assert "missing_oracle_source" in report.to_dict()


def test_v2_ac_with_oracle_source_not_flagged(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _seed(
        specs,
        "modern",
        {
            "id": "AC-001",
            "title": "t",
            "type": "mechanical",
            "pending_test": True,
            "oracle_source": "differential",
            "oracle_evidence": "reference impl golden",
        },
    )
    report = scan(specs, dev_mode="spec-driven")
    assert report.missing_oracle_source == []
