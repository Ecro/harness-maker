"""Tests for secscan.secrets — pattern-based secret detection."""

from __future__ import annotations

from pathlib import Path

from harness_maker.secscan.secrets import scan


def test_clean_dir_returns_no_findings(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("x = 42\nprint('hi')\n", encoding="utf-8")
    (tmp_path / "doc.md").write_text("Just regular docs.\n", encoding="utf-8")
    assert scan(tmp_path) == []


def test_aws_access_key_detected(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text(
        'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n',
        encoding="utf-8",
    )
    findings = scan(tmp_path)
    assert any(f.category == "secrets" and "aws_access_key" in f.evidence for f in findings)
    assert all(f.severity == "high" for f in findings)


def test_github_pat_detected(tmp_path: Path) -> None:
    pat = "ghp_" + "A" * 36
    (tmp_path / "ci.md").write_text(f"export TOKEN={pat}\n", encoding="utf-8")
    findings = scan(tmp_path)
    assert any("github_pat" in f.evidence for f in findings)


def test_anthropic_api_key_detected(tmp_path: Path) -> None:
    key = "sk-ant-" + ("A" * 100)
    (tmp_path / "config.json").write_text(f'{{"key":"{key}"}}\n', encoding="utf-8")
    findings = scan(tmp_path)
    assert any("anthropic_api_key" in f.evidence for f in findings)


def test_env_secret_detected(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        'DATABASE_PASSWORD="hunter2hunter2"\nAPI_TOKEN=abcdefghij\n',
        encoding="utf-8",
    )
    findings = scan(tmp_path)
    assert any("env_secret" in f.evidence for f in findings)


def test_skips_dotgit_dir(tmp_path: Path) -> None:
    git = tmp_path / ".git"
    git.mkdir()
    (git / "config").write_text("AKIAABCDEFGHIJKLMNOP\n", encoding="utf-8")
    # .git is skipped + .git/config has no scanned extension anyway.
    assert scan(tmp_path) == []


def test_evidence_is_masked(tmp_path: Path) -> None:
    key = "sk-ant-" + ("A" * 100)
    (tmp_path / "leak.py").write_text(f'KEY = "{key}"\n', encoding="utf-8")
    findings = scan(tmp_path)
    assert findings
    # full key should NOT appear verbatim in evidence (mask applied)
    assert key not in findings[0].evidence
