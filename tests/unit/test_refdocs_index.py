"""Tests for the refdocs_index minimal yaml index builder."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness_maker.models import RefFolder
from harness_maker.refdocs_index import build


def _ref(path: str, glob: str = "**/*.{md,txt,pdf}") -> RefFolder:
    return RefFolder(path=path, glob=glob)


def test_build_empty_ref_folders_writes_skeleton(tmp_path: Path) -> None:
    """No ref_folders → empty yaml block + zero entries (still atomic-writes)."""
    result = build(tmp_path, [], now_iso="2026-05-06T00:00:00Z")
    assert result.entry_count == 0
    assert result.warnings == []
    data = yaml.safe_load(result.index_path.read_text())
    assert data["ref_folders"] == []
    assert data["generated_at"] == "2026-05-06T00:00:00Z"


def test_build_resolves_tilde_relative_ref_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``~/foo`` paths must resolve via $HOME — NOT under harness_root.

    Regression guard for the 0.11.3 expanduser-after-join silent-no-op fix:
    `Path("/harness_root") / "~/foo"` produces `/harness_root/~/foo`, and a
    subsequent `.expanduser()` is a no-op because `~` is no longer at position 0.
    The bug surfaced as "ref_folder not found" with a confusing resolved path
    that visibly contained `~`. Expansion must happen BEFORE the join.
    """
    # $HOME points to a real directory containing a .md file; harness_root is
    # somewhere else entirely. Pre-fix: the indexer joins harness_root + "~/docs"
    # → bogus path under harness_root, returns 0 entries + a warning.
    fake_home = tmp_path / "fake_home"
    docs = fake_home / "docs"
    docs.mkdir(parents=True)
    (docs / "spec.md").write_text("# Spec\n\nbody\n")
    monkeypatch.setenv("HOME", str(fake_home))
    harness_root = tmp_path / "harness_project"
    harness_root.mkdir()

    result = build(harness_root, [_ref("~/docs")], now_iso="2026-05-13T00:00:00Z")

    data = yaml.safe_load(result.index_path.read_text())
    entries = data["ref_folders"][0]["entries"]
    assert len(entries) == 1
    assert entries[0]["relpath"] == "spec.md"
    assert result.warnings == []


def test_build_md_extracts_frontmatter_title_and_h2(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text(
        "---\ntitle: Authentication Flow\n---\n\n## OAuth2 setup\n\n## Session storage\n",
    )
    result = build(tmp_path, [_ref("./docs")], now_iso="2026-01-01T00:00:00Z")
    data = yaml.safe_load(result.index_path.read_text())
    entries = data["ref_folders"][0]["entries"]
    assert len(entries) == 1
    assert entries[0]["relpath"] == "auth.md"
    assert entries[0]["title"] == "Authentication Flow"
    assert entries[0]["headings"] == ["OAuth2 setup", "Session storage"]


def test_build_md_uses_first_h1_when_no_frontmatter(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "spec.md").write_text("# MQTT Spec\n\n## Topic format\n\nbody\n")
    result = build(tmp_path, [_ref("./docs")])
    data = yaml.safe_load(result.index_path.read_text())
    entry = data["ref_folders"][0]["entries"][0]
    assert entry["title"] == "MQTT Spec"
    # First H1 was promoted to title; it is dropped from the headings list to
    # avoid duplication with the title.
    assert entry["headings"] == ["Topic format"]


def test_build_pdf_filename_only(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "diagram.pdf").write_bytes(b"%PDF-1.4 fake")
    result = build(tmp_path, [_ref("./docs")])
    entry = yaml.safe_load(result.index_path.read_text())["ref_folders"][0]["entries"][0]
    assert entry["kind"] == "pdf"
    assert entry["filename_only"] is True
    assert "title" not in entry


def test_build_docx_emits_warning_and_skips_entry(tmp_path: Path) -> None:
    """Default glob doesn't match .docx, but a second pass still warns about it
    so users know to convert — the whole point of the unsupported-format alert.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "old.docx").write_bytes(b"PK\x03\x04 fake")
    (docs / "ok.md").write_text("# OK\n")
    # Default glob — does NOT include docx; second pass should still warn.
    result = build(tmp_path, [_ref("./docs")])
    data = yaml.safe_load(result.index_path.read_text())
    rels = [e["relpath"] for e in data["ref_folders"][0]["entries"]]
    assert rels == ["ok.md"]
    assert any(".docx" in w and "old.docx" in w for w in data["warnings"])


def test_build_docx_inside_user_glob_warns_only_once(tmp_path: Path) -> None:
    """If the user's glob does include docx, first-pass already warned —
    second pass must not double-warn (seen set prevents re-emit).
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "old.docx").write_bytes(b"PK\x03\x04 fake")
    result = build(tmp_path, [_ref("./docs", glob="**/*.{md,docx}")])
    data = yaml.safe_load(result.index_path.read_text())
    docx_warns = [w for w in data["warnings"] if "old.docx" in w]
    assert len(docx_warns) == 1


def test_build_missing_folder_warns_but_does_not_crash(tmp_path: Path) -> None:
    result = build(tmp_path, [_ref("./does-not-exist")])
    assert result.entry_count == 0
    assert any("not found" in w for w in result.warnings)


def test_build_brace_glob_expansion(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "sub").mkdir(parents=True)
    (docs / "a.md").write_text("# A\n")
    (docs / "sub" / "b.txt").write_text("plain text body\n")
    (docs / "c.pdf").write_bytes(b"%PDF")
    (docs / "ignored.json").write_text("{}")
    result = build(tmp_path, [_ref("./docs")])
    data = yaml.safe_load(result.index_path.read_text())
    rels = sorted(e["relpath"] for e in data["ref_folders"][0]["entries"])
    assert rels == ["a.md", "c.pdf", "sub/b.txt"]


def test_build_writes_to_observability_dir(tmp_path: Path) -> None:
    """Always writes to .claude/observability/docs_index.yaml under harness_root."""
    result = build(tmp_path, [])
    assert result.index_path == tmp_path / ".claude" / "observability" / "docs_index.yaml"
    assert result.index_path.exists()


def test_build_skips_hidden_dirs(tmp_path: Path) -> None:
    """If a ref_folder happens to point at a repo root, .git / .venv / etc
    must not pollute the index — and unsupported files inside hidden dirs
    must not warn either.
    """
    docs = tmp_path / "docs"
    git = docs / ".git"
    venv = docs / ".venv"
    git.mkdir(parents=True)
    venv.mkdir()
    (docs / "real.md").write_text("# real\n")
    (git / "config.md").write_text("# git config\n")
    (venv / "old.docx").write_bytes(b"PK fake")
    result = build(tmp_path, [_ref("./docs")])
    data = yaml.safe_load(result.index_path.read_text())
    rels = [e["relpath"] for e in data["ref_folders"][0]["entries"]]
    assert rels == ["real.md"]
    assert data["warnings"] == []
