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


def test_render_settings_json_is_pure_json(tmp_path: Path) -> None:
    """settings.json is co-owned with Claude Code (which expects pure JSON), so
    we cannot prepend YAML frontmatter the way other rendered files do.
    """
    import json

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    settings_path = tmp_path / "settings.json"
    assert settings_path.exists()
    raw = settings_path.read_text(encoding="utf-8")
    assert not raw.startswith("---\n"), "settings.json must be pure JSON, no frontmatter"
    data = json.loads(raw)
    assert "permissions" in data
    assert "statusLine" in data
    assert data["statusLine"]["type"] == "command"


def test_render_settings_json_shallow_merges_existing(tmp_path: Path) -> None:
    """When Claude Code already wrote settings.json with `enabledPlugins`, the
    re-render must preserve that key while adding our own.
    """
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"enabledPlugins": {"foo@bar": True}, "permissions": {"allow": ["custom"]}}),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    # User's enabledPlugins survived (template doesn't define this key).
    assert data["enabledPlugins"] == {"foo@bar": True}
    # Template's permissions won (template owns this key).
    assert data["permissions"]["allow"] != ["custom"]
    assert "Read" in data["permissions"]["allow"]
    # Template's statusLine landed.
    assert data["statusLine"]["type"] == "command"


def test_render_settings_json_falls_back_when_existing_corrupt(tmp_path: Path) -> None:
    """Malformed JSON on disk → render writes pure template content (no crash).

    The user's corrupt file is overwritten because we can't merge against
    invalid JSON. Less catastrophic than crashing the whole render.
    """
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{ this is not valid JSON ::: ", encoding="utf-8")
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "statusLine" in data
    assert "permissions" in data


def test_render_settings_json_preserves_user_status_line(tmp_path: Path) -> None:
    """User's custom statusLine survives a re-render — we add what's missing,
    we do not overwrite a user-curated command.
    """
    import json

    settings_path = tmp_path / "settings.json"
    user_status = {"type": "command", "command": "echo my-custom-statusline"}
    settings_path.write_text(
        json.dumps({"statusLine": user_status, "enabledPlugins": {"x@y": True}}),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["statusLine"] == user_status
    # Other template keys still land.
    assert "permissions" in data
    assert data["enabledPlugins"] == {"x@y": True}


def test_render_settings_json_overwrite_policy_replaces_user(tmp_path: Path) -> None:
    """statusline_policy='overwrite' → user's custom statusLine replaced by template's."""
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {"statusLine": {"type": "command", "command": "echo custom"}},
        ),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME, statusline_policy="overwrite")
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "bash .claude/lib/run-statusline.sh"


def test_render_settings_json_combine_policy_points_to_combined_wrapper(tmp_path: Path) -> None:
    """statusline_policy='combine' → settings.json points to combined wrapper."""
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {"statusLine": {"type": "command", "command": "echo custom"}},
        ),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME, statusline_policy="combine")
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "bash .claude/lib/run-statusline-combined.sh"


def test_render_settings_json_upgrades_outdated_status_line(tmp_path: Path) -> None:
    """v0.3.0–0.3.3 shipped a broken statusLine command; users stuck on it
    get auto-upgraded to the current wrapper-based command on next make.
    """
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "statusLine": {
                    "type": "command",
                    "command": "uv run python -m harness_maker.statusline",
                },
            },
        ),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "bash .claude/lib/run-statusline.sh"


def test_render_settings_json_strips_legacy_frontmatter(tmp_path: Path) -> None:
    """Pre-0.4.0 settings.json output had a YAML frontmatter prefix. The new
    render must read past it when shallow-merging (back-compat).
    """
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        "---\ngenerated_by: harness-maker\ncontent_hash: deadbeef\n---\n"
        + json.dumps({"enabledPlugins": {"x@y": True}}),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    raw = settings_path.read_text(encoding="utf-8")
    assert not raw.startswith("---\n")
    data = json.loads(raw)
    assert data["enabledPlugins"] == {"x@y": True}
    assert "statusLine" in data


def test_render_populates_body_sha256(tmp_path: Path) -> None:
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    for f in bp.files:
        assert f.body_sha256
        assert len(f.body_sha256) == 64  # sha256 hex


def test_render_with_merge_paths_preserves_user_blocks(tmp_path: Path) -> None:
    """Round-trip: render → user edits a user:<id> block → re-render with
    merge_paths → user content survives, hash reflects merged body.
    """
    from harness_maker.block_merge import MergeReport

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    review_path = tmp_path / "stages" / "review.md"
    text = review_path.read_text(encoding="utf-8")
    edited = text.replace(
        "<!-- Free-form project-specific additions to the review stage. "
        "Preserved across harness-maker upgrades. -->",
        "## Project rule\n\nAlways check telemetry impact for hot-path changes.",
    )
    review_path.write_text(edited, encoding="utf-8")

    bp2 = synthesize(p, a)
    merge_paths = {Path("stages/review.md")}
    merge_reports: dict[Path, MergeReport] = {}
    render(
        bp2,
        tmp_path,
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_paths=merge_paths,
        merge_reports=merge_reports,
    )

    final = review_path.read_text(encoding="utf-8")
    assert "Always check telemetry impact" in final
    assert Path("stages/review.md") in merge_reports
    report = merge_reports[Path("stages/review.md")]
    assert "extensions" in report.user_blocks_preserved


def test_render_without_merge_paths_overwrites(tmp_path: Path) -> None:
    """Sanity: when merge_paths is empty, render performs plain REPLACE.
    User edits in user blocks would be lost — by design (caller didn't ask
    for merge).
    """
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    review_path = tmp_path / "stages" / "review.md"
    review_path.write_text("# user wrote this\n", encoding="utf-8")

    bp2 = synthesize(p, a)
    render(bp2, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    final = review_path.read_text(encoding="utf-8")
    assert "# user wrote this" not in final
    assert "Stage: review" in final
