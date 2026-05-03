"""Tests for secscan.permissions — over-broad allow-list detection."""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.secscan.permissions import scan


def _write_settings(path: Path, allow: list[str]) -> Path:
    p = path / "settings.json"
    p.write_text(json.dumps({"permissions": {"allow": allow}}), encoding="utf-8")
    return p


def test_missing_settings_returns_empty(tmp_path: Path) -> None:
    assert scan(tmp_path / "missing.json") == []


def test_narrow_permissions_clean(tmp_path: Path) -> None:
    p = _write_settings(tmp_path, ["Bash(uv:*)", "Bash(git:status)", "Read(./src/**)"])
    findings = scan(p)
    assert findings == []


def test_catch_all_bash_high_severity(tmp_path: Path) -> None:
    p = _write_settings(tmp_path, ["Bash(*)"])
    findings = scan(p)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].category == "permissions"


def test_catch_all_write_high_severity(tmp_path: Path) -> None:
    p = _write_settings(tmp_path, ["Write(*)"])
    findings = scan(p)
    assert any(f.severity == "high" for f in findings)


def test_broad_path_pattern_medium(tmp_path: Path) -> None:
    p = _write_settings(tmp_path, ["Read(/**)"])
    findings = scan(p)
    # "/**" triggers broad-path check; not a tool-prefixed wildcard with ":".
    assert any(f.severity == "medium" for f in findings)


def test_handles_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(
        "---\nfoo: bar\n---\n" + json.dumps({"permissions": {"allow": ["Bash(*)"]}}),
        encoding="utf-8",
    )
    findings = scan(p)
    assert any(f.severity == "high" for f in findings)
