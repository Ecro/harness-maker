"""Tests for the Verifier (Task 3.4)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.verify import verify


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


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


def test_verify_skip_hash_paths_exempts_kept_file(tmp_path: Path) -> None:
    """A reconcile-KEPT file's body is not ours to verify against its hash.

    Mirrors observability/dashboard.md: make renders provenance frontmatter with a
    content_hash, then /hm:health rewrites the body in place. reconcile KEEPs it,
    so make must NOT hard-fail on the now-stale hash. Passing the KEEP set via
    skip_hash_paths exempts it; an unrelated mismatching file still fails.
    """
    (tmp_path / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    stale = (
        "---\ngenerated_by: harness-maker\ncontent_hash: deadbeef\n---\n"
        "runtime-mutated body that no longer matches the declared hash\n"
    )
    kept = tmp_path / "observability" / "dashboard.md"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text(stale, encoding="utf-8")
    other = tmp_path / "other.md"
    other.write_text(stale, encoding="utf-8")

    # Without the exemption both files fail.
    baseline = verify(tmp_path)
    assert any("observability/dashboard.md" in e for e in baseline)
    assert any("other.md" in e for e in baseline)

    # KEEP set exempts only the kept file; the unrelated mismatch still fails.
    errors = verify(tmp_path, skip_hash_paths=frozenset({Path("observability/dashboard.md")}))
    assert not any("observability/dashboard.md" in e for e in errors), (
        f"KEPT file must be exempt from content_hash check; got: {errors}"
    )
    assert any("other.md" in e for e in errors), f"non-KEPT mismatch must still fail; got: {errors}"








