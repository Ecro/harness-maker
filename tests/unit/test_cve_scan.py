"""Tests for secscan.dependency_cves — OSV.dev integration with mock query_fn."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_maker.models import CrawlItem
from harness_maker.secscan.dependency_cves import scan


def _write_uv_lock(path: Path) -> Path:
    p = path / "uv.lock"
    p.write_text(
        """
version = 1

[[package]]
name = "requests"
version = "2.32.0"

[[package]]
name = "urllib3"
version = "1.26.0"
""",
        encoding="utf-8",
    )
    return p


def test_no_lock_no_pyproject_returns_empty(tmp_path: Path) -> None:
    findings = scan(tmp_path, query_fn=lambda specs: [])
    assert findings == []


def test_clean_query_returns_empty(tmp_path: Path) -> None:
    _write_uv_lock(tmp_path)
    findings = scan(tmp_path, query_fn=lambda specs: [])
    assert findings == []


def test_high_severity_classification(tmp_path: Path) -> None:
    _write_uv_lock(tmp_path)

    def mock_query(specs: list[dict[str, Any]]) -> list[CrawlItem]:
        return [
            CrawlItem(
                source="osv_dev",
                item_id="CVE-2099-9999",
                title="Severe RCE in requests",
                metadata={
                    "package": "requests",
                    "ecosystem": "PyPI",
                    "version": "2.32.0",
                    "severity": [{"type": "CVSS_V3", "score": "9.8"}],
                },
            ),
        ]

    findings = scan(tmp_path, query_fn=mock_query)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].category == "cve"
    assert "CVE-2099-9999" in findings[0].evidence


def test_medium_severity_classification(tmp_path: Path) -> None:
    _write_uv_lock(tmp_path)

    def mock_query(specs: list[dict[str, Any]]) -> list[CrawlItem]:
        return [
            CrawlItem(
                source="osv_dev",
                item_id="CVE-2099-MED",
                title="Medium",
                metadata={
                    "package": "urllib3",
                    "ecosystem": "PyPI",
                    "version": "1.26.0",
                    "severity": [{"type": "CVSS_V3", "score": "5.5"}],
                },
            ),
        ]

    findings = scan(tmp_path, query_fn=mock_query)
    assert findings[0].severity == "medium"


def test_low_severity_classification(tmp_path: Path) -> None:
    _write_uv_lock(tmp_path)

    def mock_query(specs: list[dict[str, Any]]) -> list[CrawlItem]:
        return [
            CrawlItem(
                source="osv_dev",
                item_id="CVE-2099-LOW",
                title="Low",
                metadata={
                    "package": "urllib3",
                    "ecosystem": "PyPI",
                    "version": "1.26.0",
                    "severity": [{"type": "CVSS_V3", "score": "2.0"}],
                },
            ),
        ]

    findings = scan(tmp_path, query_fn=mock_query)
    assert findings[0].severity == "low"


def test_pyproject_fallback(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["requests>=2.0", "urllib3"]\n',
        encoding="utf-8",
    )

    captured: list[list[dict[str, Any]]] = []

    def mock_query(specs: list[dict[str, Any]]) -> list[CrawlItem]:
        captured.append(specs)
        return []

    scan(tmp_path, query_fn=mock_query)
    assert captured, "query_fn was not called"
    names = [s["package"]["name"] for s in captured[0]]
    assert "requests" in names
    assert "urllib3" in names
