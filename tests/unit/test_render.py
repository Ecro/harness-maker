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
    assert "permissions" in data


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


def test_render_settings_json_evicts_stale_harness_keys(tmp_path: Path) -> None:
    """Keys harness-maker used to write (e.g. statusLine) are evicted on re-render
    even if they're still present in the existing settings.json.
    """
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "statusLine": "some old status line value",
                "enabledPlugins": {"user-plugin": True},
            }
        ),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    # statusLine was owned by harness-maker in <=0.3.x — must be evicted.
    assert "statusLine" not in data
    # User-owned key survives.
    assert data["enabledPlugins"] == {"user-plugin": True}


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


# ──────────────────────────────────────────────────────────────────────────────
# Cursor target — Phase 2.2/2.3
# ──────────────────────────────────────────────────────────────────────────────


def test_render_cursor_target_emits_mdc_and_mcp_json(tmp_path: Path) -> None:
    """targets=[cursor] full pipeline mirrors real CLI: target_dir 는 ``.claude/``,
    ``.cursor/`` 자산은 그 sibling 으로 resolve.
    """
    from harness_maker.models import Target

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    mdc = project_root / ".cursor" / "rules" / "harness.mdc"
    mcp = project_root / ".cursor" / "mcp.json"
    assert mdc.exists()
    assert mcp.exists()

    # mdc: Cursor frontmatter 존재 + alwaysApply: true
    mdc_text = mdc.read_text(encoding="utf-8")
    assert mdc_text.startswith("---\n")
    assert "alwaysApply: true" in mdc_text
    assert "description:" in mdc_text

    # mcp.json: pure JSON, frontmatter 없음
    import json as _json

    mcp_text = mcp.read_text(encoding="utf-8")
    assert not mcp_text.startswith("---")
    parsed = _json.loads(mcp_text)
    assert isinstance(parsed, dict)
    assert "mcpServers" in parsed


def test_render_cursor_mdc_lacks_our_provenance_frontmatter(tmp_path: Path) -> None:
    """Cursor .mdc 는 _render_pure_text 로 처리되어 우리 ``generated_by``,
    ``content_hash``, ``source_template`` 메타가 박히지 않음 (Cursor strict-reject
    회피, Phase 1 A1.frontmatter 결과에 따라 sidecar 메타 분리는 Phase 2.4+).
    """
    from harness_maker.models import Target

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    mdc_text = (project_root / ".cursor" / "rules" / "harness.mdc").read_text(encoding="utf-8")
    assert "generated_by:" not in mdc_text
    assert "content_hash:" not in mdc_text
    assert "source_template:" not in mdc_text
    assert "harness_maker_version:" not in mdc_text


def test_render_claude_only_target_omits_cursor_directory(tmp_path: Path) -> None:
    """targets=[claude-code] (default): .cursor/ 디렉토리 자체가 만들어지지 않음."""
    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True)  # default [claude-code]
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    cursor_dir = project_root / ".cursor"
    assert not cursor_dir.exists()


def test_render_cursor_hooks_json_camelcase_with_path_wrap(tmp_path: Path) -> None:
    """Cursor IDE 가 .claude/hooks/hooks.json 을 안 읽으므로 cursor target 일 때
    .cursor/hooks.json 을 별도 렌더 (PLAN-cursor-rootcause.md R1.A).

    필수 보장:
    - `version: 1` (Cursor 스키마)
    - 이벤트 키 camelCase: preToolUse / postToolUse / preCompact (PascalCase X)
    - 각 command 가 PATH wrap 으로 시작 — Cursor spawn shell 의 PATH 미보장 방어
    - frontmatter 없음 (pure JSON)
    """
    from harness_maker.models import Target

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    cursor_hooks = project_root / ".cursor" / "hooks.json"
    assert cursor_hooks.exists()

    text = cursor_hooks.read_text(encoding="utf-8")
    # pure JSON — no provenance frontmatter
    assert not text.startswith("---")
    import json as _json

    parsed = _json.loads(text)
    assert parsed["version"] == 1

    hooks = parsed["hooks"]
    assert "preToolUse" in hooks
    # PLAN-cursor-rootcause follow-up: Cursor uses `stop` (per-turn) for
    # telemetry, NOT postToolUse (per-tool). Cursor never sends usage data
    # to hooks, so per-tool entries would all have tokens=0 and pollute
    # cache_diagnostics. stop fires once per agent turn with status /
    # loop_count / duration_ms — meaningful even without tokens.
    assert "stop" in hooks
    assert "postToolUse" not in hooks  # explicitly removed in 0.5.4
    assert "preCompact" in hooks
    # PascalCase must NOT appear — silent ignore in Cursor would produce no fire
    assert "PreToolUse" not in hooks
    assert "PostToolUse" not in hooks
    assert "PreCompact" not in hooks
    assert "Stop" not in hooks

    # Every hook command must defensively prepend the user-local PATH so
    # `uv` resolves even when Cursor spawns the subprocess from a shell
    # without ~/.local/bin in PATH.
    all_commands = [
        h["command"]
        for event_hooks in hooks.values()
        for h in event_hooks
    ]
    assert all_commands  # at least one
    for cmd in all_commands:
        assert cmd.startswith('PATH="$HOME/.local/bin:$PATH"'), cmd


def test_render_cursor_hooks_json_omits_spec_gate_when_task_driven(
    tmp_path: Path,
) -> None:
    """dev_mode=task-driven 이면 .cursor/hooks.json 의 preToolUse 에는 spec_gate
    가 포함되지 않음 (.claude/hooks/hooks.json 과 동일 규칙)."""
    from harness_maker.models import DevMode, Target

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CURSOR], "dev_mode": DevMode.TASK_DRIVEN},
    )
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    text = (project_root / ".cursor" / "hooks.json").read_text(encoding="utf-8")
    assert "spec_gate" not in text
    assert "permission_gate" in text  # always-on


def test_render_cursor_hooks_json_includes_spec_gate_when_spec_driven(
    tmp_path: Path,
) -> None:
    """Symmetric to the task-driven test: dev_mode=spec-driven includes the
    Write|Edit spec_gate matcher in the cursor preToolUse list. Both gates
    receive the PATH wrap from the template."""
    import json as _json

    from harness_maker.models import DevMode, Target

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CURSOR], "dev_mode": DevMode.SPEC_DRIVEN},
    )
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    parsed = _json.loads(
        (project_root / ".cursor" / "hooks.json").read_text(encoding="utf-8"),
    )
    pre_tool_use = parsed["hooks"]["preToolUse"]
    assert len(pre_tool_use) == 2  # Bash + Write|Edit
    matchers = {h["matcher"] for h in pre_tool_use}
    assert matchers == {"Bash", "Write|Edit"}
    spec_gate_hook = next(h for h in pre_tool_use if h["matcher"] == "Write|Edit")
    assert "spec_gate" in spec_gate_hook["command"]
    assert spec_gate_hook["command"].startswith('PATH="$HOME/.local/bin:$PATH"')


# ──────────────────────────────────────────────────────────────────────────────
# Cursor target snapshot determinism — Phase 2.7
# ──────────────────────────────────────────────────────────────────────────────


def _collect(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_render_cursor_target_byte_identical_across_runs(tmp_path: Path) -> None:
    """Phase 2.7: targets=[cursor] 두 번 render → byte-identical (frozen time)."""
    from harness_maker.models import Target

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})

    def _run(root: Path) -> dict[Path, bytes]:
        target = root / ".claude"
        target.mkdir()
        bp = synthesize(p, a)
        render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)
        return _collect(root)

    r1 = tmp_path / "r1"
    r1.mkdir()
    r2 = tmp_path / "r2"
    r2.mkdir()
    assert _run(r1) == _run(r2)


def test_render_both_targets_byte_identical_across_runs(tmp_path: Path) -> None:
    """Phase 2.7: targets=[claude-code, cursor] 두 번 render → byte-identical."""
    from harness_maker.models import Target

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CURSOR]},
    )

    def _run(root: Path) -> dict[Path, bytes]:
        target = root / ".claude"
        target.mkdir()
        bp = synthesize(p, a)
        render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)
        return _collect(root)

    r1 = tmp_path / "r1"
    r1.mkdir()
    r2 = tmp_path / "r2"
    r2.mkdir()
    assert _run(r1) == _run(r2)


def test_render_cursor_target_writes_targets_to_harness_yaml(tmp_path: Path) -> None:
    """Phase 2.7 bug fix: targets / recommended_model 키가 harness.yaml 에
    실제로 박힘 — 그렇지 않으면 re-render 시 옛 yaml 으로 잘못 인식되어
    silent fallback (`[claude-code]`) 으로 cursor 선택 손실. Phase 2.0/2.1 의
    누락이 Phase 2.7 진행 중 발견되어 fix.
    """
    from harness_maker.models import Target

    project_root = tmp_path
    target = project_root / ".claude"
    target.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CURSOR]},
    )
    bp = synthesize(p, a)
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    yaml_text = (target / "harness.yaml").read_text(encoding="utf-8")
    assert "targets: [claude-code, cursor]" in yaml_text
    assert "recommended_model: claude-opus-4-7" in yaml_text
