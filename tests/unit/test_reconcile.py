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


def test_reconcile_hash_mismatch_no_markers_returns_keep(tmp_path: Path) -> None:
    """User edited a marker-less file → KEEP (legacy fallback)."""
    target = tmp_path / "a.md"
    body = "# user has edited this\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    # Use a real marker-less template so reconcile can read it; the hash
    # mismatch is what we exercise here, not template-unreadable.
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="stages/research.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


def test_reconcile_hash_mismatch_template_unreadable_returns_keep(tmp_path: Path) -> None:
    """Missing template → graceful KEEP with diagnostic reason."""
    target = tmp_path / "a.md"
    body = "# edited\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = _bp(["a.md"])  # template="x.j2" doesn't exist
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-template-unreadable"


def test_reconcile_hash_mismatch_both_have_markers_returns_merge_block(tmp_path: Path) -> None:
    """User edited a marker-bearing file whose template still has markers
    → MERGE_BLOCK so user blocks survive the upgrade.
    """
    target = tmp_path / "review.md"
    # OLD body has a user block — simulates a previously-rendered review.md.
    body = "# Stage: review\n<!-- @hm:user:notes -->\nmy custom step\n<!-- @hm:/user:notes -->\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = Blueprint(files=[FileEntry(path=Path("review.md"), template="stages/review.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason == "hash-mismatch-mergeable"


def test_reconcile_malformed_markers_falls_back_to_keep(tmp_path: Path) -> None:
    """User broke marker syntax (e.g., deleted the close tag) → KEEP not
    MERGE_BLOCK. Reason: silent loss of user edits is unacceptable; surface
    the diagnostic so the user can fix their markup.
    """
    target = tmp_path / "review.md"
    body = "# Stage: review\n<!-- @hm:user:notes -->\nuser content but close tag is missing\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = Blueprint(files=[FileEntry(path=Path("review.md"), template="stages/review.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-malformed-markers"


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
