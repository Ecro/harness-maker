"""Tests for provenance verification (Phase 10 Task 8.6)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.provenance import compute_hash, parse_frontmatter, verify_file
from harness_maker.reconcile import compute_body_hash


def _write_with_provenance(
    path: Path,
    body: str,
    source_template: str = "x.j2",
) -> str:
    body_bytes = body.encode("utf-8")
    h = compute_body_hash(body_bytes)
    fm = f"---\ncontent_hash: {h}\nsource_template: {source_template}\n---\n"
    path.write_text(fm + body, encoding="utf-8")
    return h


def test_parse_frontmatter_returns_dict_for_provenance(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    _write_with_provenance(f, "# hi\n")
    fm = parse_frontmatter(f)
    assert "content_hash" in fm
    assert fm["source_template"] == "x.j2"


def test_parse_frontmatter_returns_empty_for_no_fm(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("plain content\n", encoding="utf-8")
    assert parse_frontmatter(f) == {}


def test_compute_hash_matches_recorded(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    expected = _write_with_provenance(f, "# hello world\n")
    assert compute_hash(f) == expected


def test_verify_file_passes_for_unmodified(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    _write_with_provenance(f, "# hello\nbody\n", source_template="claude-md.j2")
    matches, source = verify_file(f)
    assert matches is True
    assert source == "claude-md.j2"


def test_verify_file_fails_for_user_edited(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    _write_with_provenance(f, "# original\n")
    # Read full text, mutate body, rewrite (preserving frontmatter)
    text = f.read_text(encoding="utf-8")
    head, _sep, body = text.partition("\n---\n")
    # text is "---\nfm\n---\nbody"; partition on first "\n---\n" → head="---\nfm", body="body"
    f.write_text(head + "\n---\n" + body + "USER EDIT\n", encoding="utf-8")
    matches, source = verify_file(f)
    assert matches is False
    assert source != ""  # source_template still present


def test_verify_file_returns_false_no_frontmatter(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("plain user file with no provenance\n", encoding="utf-8")
    matches, source = verify_file(f)
    assert matches is False
    assert source == ""


def test_verify_file_returns_false_no_hash_field(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text(
        "---\nsource_template: x.j2\n---\nbody only, no hash\n",
        encoding="utf-8",
    )
    matches, source = verify_file(f)
    assert matches is False
    assert source == "x.j2"


def test_verify_file_handles_missing_source_template(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    body = "# body\n"
    h = compute_body_hash(body.encode("utf-8"))
    f.write_text(f"---\ncontent_hash: {h}\n---\n" + body, encoding="utf-8")
    matches, source = verify_file(f)
    assert matches is True
    assert source == ""
