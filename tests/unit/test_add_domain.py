"""Tests for harness_maker.add_domain."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.add_domain import (
    AddDomainError,
    add_domain,
    update_harness_yaml,
    validate_domain_name,
)

# ──────────────────────────────────────────────────────────────────────────────
# validate_domain_name
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["python", "tauri", "react", "rust-stdlib", "go-1-22", "a", "ab", "p2p"],
)
def test_validate_accepts_lowercase_alphanum_dash(name: str) -> None:
    assert validate_domain_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "Python",  # uppercase
        "",  # empty
        "1python",  # starts with digit
        "a_b",  # underscore
        "a/b",  # slash (path traversal vector)
        "a b",  # space
        "abc!def",  # punctuation
        "a" * 32,  # too long
        "../etc/passwd",  # path traversal
    ],
)
def test_validate_rejects_invalid(name: str) -> None:
    with pytest.raises(AddDomainError):
        validate_domain_name(name)


# ──────────────────────────────────────────────────────────────────────────────
# update_harness_yaml
# ──────────────────────────────────────────────────────────────────────────────


def _seed_harness(target: Path, body: str = "preset: Side\nproject:\n  domains: []\n") -> Path:
    claude = target / ".claude"
    claude.mkdir(parents=True)
    yaml_path = claude / "harness.yaml"
    yaml_path.write_text(body)
    return yaml_path


def test_update_harness_yaml_appends_domain(tmp_path: Path) -> None:
    yaml_path = _seed_harness(tmp_path)
    changed = update_harness_yaml(yaml_path, "tauri")
    assert changed is True
    text = yaml_path.read_text()
    assert "tauri" in text


def test_update_harness_yaml_idempotent(tmp_path: Path) -> None:
    yaml_path = _seed_harness(
        tmp_path,
        "preset: Side\nproject:\n  domains:\n    - python\n",
    )
    changed = update_harness_yaml(yaml_path, "python")
    assert changed is False


def test_update_harness_yaml_preserves_frontmatter(tmp_path: Path) -> None:
    """Provenance frontmatter (--- blocks) survives the update."""
    yaml_path = _seed_harness(
        tmp_path,
        "---\ngenerated_by: harness-maker\ncontent_hash: deadbeef\n---\n"
        "preset: Side\nproject:\n  domains: []\n",
    )
    update_harness_yaml(yaml_path, "tauri")
    text = yaml_path.read_text()
    assert text.startswith("---\ngenerated_by: harness-maker")
    assert "tauri" in text


def test_update_harness_yaml_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(AddDomainError, match="harness.yaml not found"):
        update_harness_yaml(tmp_path / ".claude" / "harness.yaml", "tauri")


def test_update_harness_yaml_creates_project_when_missing(tmp_path: Path) -> None:
    yaml_path = _seed_harness(tmp_path, "preset: Side\n")
    update_harness_yaml(yaml_path, "tauri")
    text = yaml_path.read_text()
    assert "project:" in text
    assert "tauri" in text


# ──────────────────────────────────────────────────────────────────────────────
# add_domain (composite)
# ──────────────────────────────────────────────────────────────────────────────


def test_add_domain_creates_stub_and_registers(tmp_path: Path) -> None:
    _seed_harness(tmp_path)
    out = add_domain(tmp_path, "tauri", today="2026-05-03")
    assert out == tmp_path / ".claude" / "agents" / "_standards" / "tauri.md"
    assert out.exists()
    body = out.read_text()
    assert "tauri" in body
    assert "2026-05-03" in body
    yaml_text = (tmp_path / ".claude" / "harness.yaml").read_text()
    assert "tauri" in yaml_text


def test_add_domain_refuses_overwrite(tmp_path: Path) -> None:
    _seed_harness(tmp_path)
    add_domain(tmp_path, "tauri", today="2026-05-03")
    with pytest.raises(AddDomainError, match="already exists"):
        add_domain(tmp_path, "tauri", today="2026-05-03")


def test_add_domain_rejects_invalid_name(tmp_path: Path) -> None:
    _seed_harness(tmp_path)
    with pytest.raises(AddDomainError):
        add_domain(tmp_path, "../etc/passwd")
