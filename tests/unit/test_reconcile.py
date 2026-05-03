"""Tests for the Reconciler (Task 3.3)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Blueprint, FileEntry, ReconcileDecision
from harness_maker.reconcile import backup, compute_body_hash, parse_frontmatter, reconcile


def _bp(rel_paths: list[str]) -> Blueprint:
    return Blueprint(
        files=[FileEntry(path=Path(rp), template="x.j2") for rp in rel_paths],
    )


def test_reconcile_new_only_returns_both(tmp_path: Path) -> None:
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.BOTH
    assert conflicts[0].reason == "new-only"


def test_reconcile_no_frontmatter_returns_keep(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("plain content with no frontmatter\n", encoding="utf-8")
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "no-frontmatter"


def test_reconcile_hash_match_returns_replace(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    body = "# hello\n"
    body_bytes = body.encode("utf-8")
    h = compute_body_hash(body_bytes)
    fm = "---\ncontent_hash: " + h + "\n---\n"
    target.write_text(fm + body, encoding="utf-8")
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "hash-match-ours"


def test_reconcile_hash_mismatch_returns_keep(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    body = "# user has edited this\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


def test_parse_frontmatter_no_marker(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("plain text\n")
    fm, body = parse_frontmatter(p)
    assert fm is None
    assert body == b"plain text\n"


def test_parse_frontmatter_valid(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("---\nfoo: bar\n---\nbody\n")
    fm, body = parse_frontmatter(p)
    assert fm == {"foo": "bar"}
    assert body == b"body\n"


def test_backup_creates_dir(tmp_path: Path) -> None:
    src = tmp_path / ".claude"
    src.mkdir()
    (src / "f.txt").write_text("hi\n")
    bdir = backup(src)
    assert bdir.exists()
    assert (bdir / "f.txt").read_text() == "hi\n"
    assert bdir.name.startswith(".backup-")


def test_backup_missing_dir_returns_path(tmp_path: Path) -> None:
    src = tmp_path / "nonexistent"
    bdir = backup(src)
    # backup_dir is computed but not created when src is missing
    assert bdir.name.startswith(".backup-")
