"""Tests for the Renderer (Task 3.2) — determinism contract."""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import Blueprint, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")


def test_render_empty_blueprint(tmp_path: Path) -> None:
    bp = Blueprint()
    written = render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    assert written == []


def test_render_writes_files(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    written = render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    assert len(written) == len(bp.files)
    for path in written:
        assert path.exists()


def test_render_dry_run_skips_writes(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    written = render(bp, tmp_path, dry_run=True, freeze_time=DEFAULT_FREEZE_TIME)
    assert len(written) == len(bp.files)
    # Nothing should have been written under tmp_path itself
    files_in_tmp = [f for f in tmp_path.rglob("*") if f.is_file()]
    assert files_in_tmp == []


def test_render_byte_identical_with_freeze_time(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp1 = synthesize(p, a)
    bp2 = synthesize(p, a)
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    render(bp1, out1, freeze_time=DEFAULT_FREEZE_TIME)
    render(bp2, out2, freeze_time=DEFAULT_FREEZE_TIME)

    files1 = sorted(out1.rglob("*"))
    files2 = sorted(out2.rglob("*"))
    rels1 = [f.relative_to(out1) for f in files1 if f.is_file()]
    rels2 = [f.relative_to(out2) for f in files2 if f.is_file()]
    assert rels1 == rels2
    for rel in rels1:
        a_bytes = (out1 / rel).read_bytes()
        b_bytes = (out2 / rel).read_bytes()
        assert a_bytes == b_bytes, f"byte-mismatch for {rel}"


def test_render_md_files_have_frontmatter(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    md_files = list(tmp_path.rglob("*.md"))
    assert md_files
    for md in md_files:
        head = md.read_text(encoding="utf-8").splitlines()[:1]
        assert head, f"{md} is empty"
        assert head[0] == "---", f"{md} missing frontmatter"


def test_render_settings_json_has_provenance(tmp_path: Path) -> None:
    import json

    from harness_maker.reconcile import parse_frontmatter
    from harness_maker.verify import _read_json_body

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    settings_path = tmp_path / "settings.json"
    assert settings_path.exists()
    # Provenance now lives ONLY in the YAML frontmatter (not duplicated in JSON body)
    # so reconciler hash verification matches across renders.
    fm, _body = parse_frontmatter(settings_path)
    assert fm is not None
    assert fm["generated_by"] == "harness-maker"
    assert "content_hash" in fm
    # JSON body itself contains only the user-facing config, no _provenance leak.
    data = json.loads(_read_json_body(settings_path))
    assert "_provenance" not in data


def test_render_populates_body_sha256(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    for f in bp.files:
        assert f.body_sha256
        assert len(f.body_sha256) == 64  # sha256 hex
