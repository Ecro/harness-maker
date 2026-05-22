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


def test_work_docs_footgun_probe(tmp_path: Path) -> None:
    """Phase 2 of PLAN-fix-work-docs-naming-footgun.

    Three assertions:
      (a) Rendered verify stage contains the Advisory probes section.
      (b) verify-before-completion SKILL still has exactly 6 numbered
          checks (regression guard against scope creep into the SKILL).
      (c) The A1 probe bash snippet, when executed against a tempdir
          containing work_docs/, exits 0 and emits the expected WARN
          strings on stderr.
    """
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    verify_stage = (tmp_path / "stages" / "verify.md").read_text(encoding="utf-8")

    # (a) verify stage has the new advisory section
    assert "## Advisory probes (non-blocking)" in verify_stage, (
        "verify stage must include the Advisory probes section "
        "(Layer 2 of the work_docs/ footgun guardrail)"
    )

    # (b) verify-before-completion SKILL has exactly 6 numbered checks
    skill_text = (tmp_path / "skills" / "verify-before-completion" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    check_headings = re.findall(r"^### (\d+)\. ", skill_text, flags=re.MULTILINE)
    assert check_headings == ["1", "2", "3", "4", "5", "6"], (
        f"verify-before-completion SKILL must keep exactly 6 numbered checks; "
        f"got headings={check_headings}. Do NOT add a 7th — advisory probes "
        "live in verify.md stage body (see ADR-003 in PLAN)."
    )

    # (c) A1 probe bash executes correctly against tempdir with work_docs/
    probe_match = re.search(
        r"### A1\. `work_docs/`.*?```bash\n(.*?)\n```",
        verify_stage,
        flags=re.DOTALL,
    )
    assert probe_match, (
        "could not extract A1 probe bash block from rendered verify stage; "
        "expected '### A1. `work_docs/`' heading followed by a ```bash fenced block"
    )
    probe_script = probe_match.group(1)

    sandbox = tmp_path / "probe_sandbox"
    sandbox.mkdir()
    (sandbox / "work_docs").mkdir()
    proc = subprocess.run(
        ["bash", "-c", probe_script],
        cwd=sandbox,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, (
        f"probe must exit 0 (WARN-only); got rc={proc.returncode}, stderr={proc.stderr!r}"
    )
    assert "WARN" in proc.stderr, f"probe stderr must contain 'WARN'; got: {proc.stderr!r}"
    assert "work-docs/ (hyphen)" in proc.stderr, (
        f"probe stderr must mention hyphen directory; got: {proc.stderr!r}"
    )
    assert "git mv work_docs/* work-docs/" in proc.stderr, (
        f"probe stderr must include copy-pasteable migration command; got: {proc.stderr!r}"
    )


def _prod_profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="medium", lifecycle="active")


def test_preset_dynamic(tmp_path: Path) -> None:
    """Phase 1 (C2): verify SKILL uses the project's actual preset, not hardcoded SIDE.

    Regression guard: Production harness must render Preset('Production')
    in the health-score check, not Preset.SIDE.
    """
    prod_out = tmp_path / "prod"
    prod_out.mkdir()
    p = _prod_profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a, preset=Preset.PRODUCTION)
    render(bp, prod_out, freeze_time=DEFAULT_FREEZE_TIME)

    skill_text = (prod_out / "skills" / "verify-before-completion" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Preset('Production')" in skill_text, (
        "Production harness must use Preset('Production'), not Preset.SIDE"
    )
    assert "Preset.SIDE" not in skill_text, (
        "Production harness must NOT contain hardcoded Preset.SIDE"
    )

    side_out = tmp_path / "side"
    side_out.mkdir()
    p_side = _profile()
    a_side = interview(p_side, autoloop_mode=True)
    bp_side = synthesize(p_side, a_side, preset=Preset.SIDE)
    render(bp_side, side_out, freeze_time=DEFAULT_FREEZE_TIME)

    side_skill = (side_out / "skills" / "verify-before-completion" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Preset('Side')" in side_skill, "Side harness must use Preset('Side')"
