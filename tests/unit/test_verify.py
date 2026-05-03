"""Tests for the Verifier (Task 3.4)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.verify import verify


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")


def test_verify_clean_blueprint_passes(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    errors = verify(tmp_path)
    assert errors == [], f"expected clean, got: {errors}"


def test_verify_missing_harness_yaml_fails(tmp_path: Path) -> None:
    errors = verify(tmp_path)
    assert any("harness.yaml missing" in e for e in errors)


def test_verify_broken_yaml_fails(tmp_path: Path) -> None:
    (tmp_path / "harness.yaml").write_text(":not: valid: yaml: -- :\n - bad\n", encoding="utf-8")
    errors = verify(tmp_path)
    assert any("YAML error" in e for e in errors)


def test_verify_broken_settings_json_fails(tmp_path: Path) -> None:
    (tmp_path / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    (tmp_path / "settings.json").write_text("{not valid json", encoding="utf-8")
    errors = verify(tmp_path)
    assert any("settings.json JSON error" in e for e in errors)


def test_verify_md_no_frontmatter_is_skipped(tmp_path: Path) -> None:
    """User-owned .md files (no provenance frontmatter) must not produce errors."""
    (tmp_path / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    (tmp_path / "no_fm.md").write_text("plain markdown\n", encoding="utf-8")
    errors = verify(tmp_path)
    assert not any("no_fm.md" in e for e in errors), f"user-owned file was flagged: {errors}"


def test_verify_md_content_hash_mismatch_fails(tmp_path: Path) -> None:
    """Harness-generated .md (has content_hash) with wrong hash must error."""
    (tmp_path / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    bad = (
        "---\ngenerated_by: harness-maker\ncontent_hash: deadbeef\n---\n"
        "actual body that hashes differently\n"
    )
    (tmp_path / "bad_hash.md").write_text(bad, encoding="utf-8")
    errors = verify(tmp_path)
    assert any("content_hash mismatch" in e for e in errors), (
        f"expected mismatch error, got: {errors}"
    )
