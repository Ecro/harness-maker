"""Tests for the Renderer (Task 3.2) — determinism contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from harness_maker.block_merge import MergeReport
from harness_maker.interview import interview
from harness_maker.models import Blueprint, FileEntry, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _profile() -> ProjectProfile:
    return ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")


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

    0.15.2+: `permissions.{allow,deny,ask}` lists are deep-merged (union)
    rather than replaced. Template entries come first; user additions
    survive. Other `permissions.*` keys still follow template-wins.
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
    # permissions.allow now unions: template + user.
    assert "Read" in data["permissions"]["allow"]  # template entry present
    assert "custom" in data["permissions"]["allow"]  # user entry preserved


def test_render_settings_json_unions_permissions_deny(tmp_path: Path) -> None:
    """User-added deny rules survive re-render — EXCEPT our own dead-shipped literals.

    The 0.15.2 contract preserved every user-added deny. 0.40.0 narrows it: a
    literal harness-maker itself shipped and that provably enforces nothing
    (`Write(/etc/**)`, `Bash(curl * | sh)`) is pruned on re-render, because it is
    our accreted history and it was the reported startup warning. The user loses
    nothing — the rule never fired. Rules that are the user's own — a custom path,
    or a live `Edit(/etc/**)` we never shipped — must still survive.
    """
    import json

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "deny": [
                        "Write(/etc/**)",  # our dead-shipped literal → pruned
                        "Edit(/etc/**)",  # never shipped by settings → the user's
                        "Bash(mycmd:*)",  # clearly the user's → survives
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    deny = data["permissions"]["deny"]
    assert "Write(/etc/**)" not in deny, "our dead-shipped literal must be pruned"
    assert "Edit(/etc/**)" in deny, "a live rule we never shipped is the user's"
    assert "Bash(mycmd:*)" in deny, "a user-custom rule must survive"


def test_render_settings_json_unions_dedup_no_duplicates(tmp_path: Path) -> None:
    """When user has a deny entry that the template also ships, no duplicate appears."""
    import json

    settings_path = tmp_path / "settings.json"
    # Bash(rm:*) is live and NOT pruned; Bash(mycmd:*) is the user's custom rule.
    settings_path.write_text(
        json.dumps({"permissions": {"deny": ["Bash(rm:*)", "Bash(mycmd:*)"]}}),
        encoding="utf-8",
    )
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    deny = data["permissions"]["deny"]
    # No duplicate of a shared entry (whether or not the template re-adds it).
    assert deny.count("Bash(rm:*)") == 1
    # User-only entry survived.
    assert "Bash(mycmd:*)" in deny


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

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    review_path = tmp_path / "commands" / "hm" / "wrapup.md"
    text = review_path.read_text(encoding="utf-8")
    edited = text.replace(
        "<!-- Your additions; kept on upgrade. -->",
        "## Project rule\n\nAlways check telemetry impact for hot-path changes.",
    )
    review_path.write_text(edited, encoding="utf-8")

    bp2 = synthesize(p, a)
    merge_paths = {Path("commands/hm/wrapup.md")}
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
    assert Path("commands/hm/wrapup.md") in merge_reports
    report = merge_reports[Path("commands/hm/wrapup.md")]
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

    review_path = tmp_path / "commands" / "hm" / "wrapup.md"
    review_path.write_text("# user wrote this\n", encoding="utf-8")

    bp2 = synthesize(p, a)
    render(bp2, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    final = review_path.read_text(encoding="utf-8")
    assert "# user wrote this" not in final
    assert "# /hm:wrapup" in final


# ──────────────────────────────────────────────────────────────────────────────
# Target trees — Phase 2.2/2.3
# ──────────────────────────────────────────────────────────────────────────────


def test_render_claude_only_target_omits_cursor_directory(tmp_path: Path) -> None:
    """targets=[claude-code] (default): .cursor/ 디렉토리 자체가 만들어지지 않음."""
    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)  # default [claude-code]
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    cursor_dir = project_root / ".cursor"
    assert not cursor_dir.exists()


@pytest.mark.parametrize("strictness_label", ["warn", "block"])
def test_render_hooks_json_valid_at_both_strictness_values(
    tmp_path: Path,
    strictness_label: str,
) -> None:
    """Round H GRADE-B 5: the Claude Code hooks must
    render valid JSON at both strictness values. The Jinja conditional for
    spec_gate uses inline `{% if %}` glued to commas (`}{% if ... %},`) —
    fragile under future maintainer reorderings. Lock both renderings via
    json.loads() validation."""
    import json as _json

    from harness_maker.models import Target

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    strictness = "block" if strictness_label == "block" else "warn"
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE], "strictness": strictness},
    )
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    # `.claude/hooks/hooks.json` is retired (ADR-005) — Claude Code never read it, so
    # it is no longer rendered. settings.json is the file Claude Code actually loads, and
    # it now carries the fragile `}{% if %},` spec_gate branch (Stage 3) this test locks:
    # a broken branch there costs the `permissions` block too. json.loads() raises on
    # invalid JSON at either strictness.
    settings = _json.loads((target_dir / "settings.json").read_text(encoding="utf-8"))
    assert "permissions" in settings, "a broken hooks branch must not take permissions with it"
    assert "PreToolUse" in settings["hooks"], (
        "Stage-3 PreToolUse gates (incl. the strictness-conditional spec_gate branch) "
        "must render at both strictness values"
    )
    assert "Stop" in settings["hooks"], "Stage-2 Stop hook must render at both strictness values"
    assert not (target_dir / "hooks" / "hooks.json").exists(), (
        "the retired .claude/hooks/hooks.json must no longer be rendered"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Multi-target snapshot determinism — Phase 2.7
# ──────────────────────────────────────────────────────────────────────────────


def _collect(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_render_both_targets_byte_identical_across_runs(tmp_path: Path) -> None:
    """Phase 2.7: targets=[claude-code, codex] 두 번 render → byte-identical."""
    from harness_maker.models import Target

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CODEX]},
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


def test_render_harness_yaml_preserves_user_added_top_level_key(tmp_path: Path) -> None:
    """Free-form top-level YAML keys (e.g. `memory:`) survive re-render.

    Regression guard for the 0.15.1 /hm:health audit follow-up: users add
    project-specific config blocks to harness.yaml that the template doesn't
    emit. Pre-0.15.2 the renderer wiped these on every `make` invocation.
    The fix appends user-only top-level keys after a marker comment.
    """
    project_root = tmp_path
    target = project_root / ".claude"
    target.mkdir()

    # Step 1: do a fresh render so harness.yaml exists.
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    # Step 2: user appends a free-form top-level block.
    # Use a key the template does NOT emit. (memory: is template-owned as of
    # 0.17.0 / ADR-002; using it here would test the overlap path instead.)
    yaml_path = target / "harness.yaml"
    existing = yaml_path.read_text(encoding="utf-8")
    user_block = (
        "\nproject_notes:\n"
        "  enabled: true\n"
        "  notebooks_dir: .claude/notebooks/\n"
        "  index: .claude/notebooks/index.md\n"
    )
    yaml_path.write_text(existing + user_block, encoding="utf-8")

    # Step 3: re-render. project_notes block must survive.
    bp2 = synthesize(p, a)
    render(bp2, target, freeze_time=DEFAULT_FREEZE_TIME)
    after_text = yaml_path.read_text(encoding="utf-8")

    # The canonical multi-doc loader returns the body data (skips frontmatter).
    from harness_maker.io_utils import load_harness_yaml

    body = load_harness_yaml(yaml_path)
    assert isinstance(body, dict)
    assert "project_notes" in body, (
        f"user-added `project_notes:` block wiped on re-render: {after_text}"
    )
    assert body["project_notes"]["enabled"] is True
    assert body["project_notes"]["index"] == ".claude/notebooks/index.md"


def test_render_harness_yaml_user_key_marker_present(tmp_path: Path) -> None:
    """The preservation appendix carries a `@hm:user:extensions` marker comment.

    Documents the convention so users discover that anything they add as
    a top-level YAML key persists. Marker is also a forward-compatibility
    anchor if we later need to address the block specifically.
    """
    project_root = tmp_path
    target = project_root / ".claude"
    target.mkdir()

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    yaml_path = target / "harness.yaml"
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8") + "\ncustom_block:\n  k: v\n",
        encoding="utf-8",
    )
    render(synthesize(p, a), target, freeze_time=DEFAULT_FREEZE_TIME)
    after = yaml_path.read_text(encoding="utf-8")
    assert "@hm:user:extensions" in after


def test_render_harness_yaml_template_key_wins_over_user(tmp_path: Path) -> None:
    """If a future template natively adds a key the user previously added,
    the template's value wins on the next render (no merge).

    Documents the contract: preservation only applies to keys the template
    does NOT emit. Once the template natively emits a key, it owns it.
    """
    project_root = tmp_path
    target = project_root / ".claude"
    target.mkdir()

    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    yaml_path = target / "harness.yaml"
    # The template always emits `preset:`. User tries to override it via append.
    yaml_path.write_text(
        yaml_path.read_text(encoding="utf-8") + "\npreset: USER_OVERRIDE\n",
        encoding="utf-8",
    )
    render(synthesize(p, a), target, freeze_time=DEFAULT_FREEZE_TIME)
    from harness_maker.io_utils import load_harness_yaml

    body = load_harness_yaml(yaml_path)
    # Template's value (Side, from _profile()) wins; user's USER_OVERRIDE is dropped.
    assert body["preset"] != "USER_OVERRIDE"


def test_render_multi_target_writes_targets_to_harness_yaml(tmp_path: Path) -> None:
    """Phase 2.7 bug fix: targets / recommended_model 키가 harness.yaml 에
    실제로 박힘 — 그렇지 않으면 re-render 시 옛 yaml 으로 잘못 인식되어
    silent fallback (`[claude-code]`) 으로 target 선택 손실.
    """
    from harness_maker.models import Target

    project_root = tmp_path
    target = project_root / ".claude"
    target.mkdir()

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CODEX]},
    )
    bp = synthesize(p, a)
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    yaml_text = (target / "harness.yaml").read_text(encoding="utf-8")
    assert "targets: [claude-code, codex]" in yaml_text
    assert "default_model: opus" in yaml_text  # ADR-002: version-agnostic alias floor


def test_render_agents_have_no_inert_permissions_frontmatter(tmp_path: Path) -> None:
    """0.40.0 (Phase 7, ADR-002): agent .md frontmatter must NOT carry a
    `permissions:` block.

    Inverts the 0.6.2 test, whose premise — that Cursor / Claude Code enforce
    per-agent frontmatter permissions — is false. Subagent frontmatter has no
    `permissions:` field; Claude Code silently ignores it, so the block enforced
    nothing while reading as a security boundary (it misled the incoming brief's
    author with the docs open). The real boundary is `tools:`. If a `permissions:`
    key reappears in rendered frontmatter, someone re-added inert theatre.
    """
    p = _profile()
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    # 0.64.0: a default render has three agents (lens reviewers need `reviewers.fanout`).
    names = ["code-reviewer", "judgment-reviewer", "spec-validator"]
    for name in names:
        agent_path = tmp_path / "agents" / f"{name}.md"
        assert agent_path.exists(), f"missing rendered agent: {name}"
        content = agent_path.read_text(encoding="utf-8")
        frontmatter = content.split("---", 2)[1] if content.startswith("---") else ""
        assert "permissions:" not in frontmatter, (
            f"{name}: inert `permissions:` frontmatter is back — Claude Code ignores "
            f"it; the real boundary is `tools:` (Phase 7, ADR-002)"
        )
        # The real boundary is still declared.
        assert "tools:" in frontmatter, f"{name}: missing tools: — the actual boundary"


def test_no_cursor_tree_rendered(tmp_path: Path) -> None:
    """0.63.0: no target renders `.cursor/` (the Cursor target was removed)."""
    from harness_maker.models import Target

    project_root = tmp_path
    target = project_root / ".claude"
    target.mkdir()
    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CODEX]},
    )
    bp = synthesize(p, a)
    render(bp, target, freeze_time=DEFAULT_FREEZE_TIME)

    assert not (project_root / ".cursor").exists()
    assert (target / "commands" / "hm").exists(), (
        "Claude commands must be rendered at .claude/commands/hm/"
    )


def _spec_gate_matchers(hooks: dict[str, object]) -> list[str]:
    """Matchers of the PreToolUse entries whose nested hooks run spec_gate."""
    entries = hooks.get("PreToolUse", [])
    assert isinstance(entries, list)
    return [
        str(e.get("matcher"))
        for e in entries
        if any("harness_maker.gates.spec_gate" in h.get("command", "") for h in e["hooks"])
    ]


@pytest.mark.parametrize("strictness", ["warn", "block"])
def test_render_settings_hooks_gate_spec_gate_on_strictness(
    tmp_path: Path, strictness: str
) -> None:
    """settings.json runs spec_gate exactly at block, on Write|Edit|MultiEdit.

    Replaces the 0.62 `.cursor/hooks.json` pair (SPEC-spec-gate AC-001): the strictness rule
    now lives in the two hook files that still render.
    """
    import json as _json

    from harness_maker.models import Target

    target = tmp_path / ".claude"
    target.mkdir()
    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE], "strictness": strictness},
    )
    render(synthesize(p, a), target, freeze_time=DEFAULT_FREEZE_TIME)
    hooks = _json.loads((target / "settings.json").read_text(encoding="utf-8"))["hooks"]
    expected = ["Write|Edit|MultiEdit"] if strictness == "block" else []
    assert _spec_gate_matchers(hooks) == expected


@pytest.mark.parametrize("strictness", ["warn", "block"])
def test_render_codex_hooks_gate_spec_gate_on_strictness(tmp_path: Path, strictness: str) -> None:
    """`.codex/hooks.json` runs spec_gate exactly at block, on Codex's `apply_patch`."""
    import json as _json

    from harness_maker.models import Target

    target = tmp_path / ".claude"
    target.mkdir()
    p = _profile()
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CODEX], "strictness": strictness},
    )
    render(synthesize(p, a), target, freeze_time=DEFAULT_FREEZE_TIME)
    hooks = _json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    expected = ["apply_patch"] if strictness == "block" else []
    assert _spec_gate_matchers(hooks) == expected


def test_resolve_output_path_codex_routes_to_parent() -> None:
    """.codex/ assets route to target_dir.parent (sibling of .claude/)."""
    from harness_maker.render import resolve_output_path

    target_dir = Path("/project/.claude")
    assert resolve_output_path(target_dir, Path(".codex/config.toml")) == Path(
        "/project/.codex/config.toml"
    )
    assert resolve_output_path(target_dir, Path(".codex/hooks.json")) == Path(
        "/project/.codex/hooks.json"
    )
    assert resolve_output_path(target_dir, Path(".codex/agents/code-reviewer.toml")) == Path(
        "/project/.codex/agents/code-reviewer.toml"
    )


def test_resolve_output_path_agents_routes_to_parent() -> None:
    """.agents/ assets (skills) route to target_dir.parent."""
    from harness_maker.render import resolve_output_path

    target_dir = Path("/project/.claude")
    assert resolve_output_path(target_dir, Path(".agents/skills/foo/SKILL.md")) == Path(
        "/project/.agents/skills/foo/SKILL.md"
    )
    assert resolve_output_path(target_dir, Path(".agents/skills/hm-research/SKILL.md")) == Path(
        "/project/.agents/skills/hm-research/SKILL.md"
    )


def test_resolve_output_path_agents_md_routes_to_parent() -> None:
    """AGENTS.md at project root routes to target_dir.parent (not .claude/AGENTS.md)."""
    from harness_maker.render import resolve_output_path

    target_dir = Path("/project/.claude")
    assert resolve_output_path(target_dir, Path("AGENTS.md")) == Path("/project/AGENTS.md")


def test_resolve_output_path_claude_unchanged() -> None:
    """Regular .claude/ assets still route to target_dir."""
    from harness_maker.render import resolve_output_path

    target_dir = Path("/project/.claude")
    assert resolve_output_path(target_dir, Path("harness.yaml")) == Path(
        "/project/.claude/harness.yaml"
    )
    assert resolve_output_path(target_dir, Path("agents/code-reviewer.md")) == Path(
        "/project/.claude/agents/code-reviewer.md"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Codex render infrastructure — predicates + _render_pure_toml (Phase 2)
# ──────────────────────────────────────────────────────────────────────────────


def _fe(path: str) -> FileEntry:
    """Minimal FileEntry helper for predicate testing."""
    return FileEntry(path=Path(path), template="hooks/hooks.json.j2", context={})


def test_is_codex_hooks_json_true() -> None:
    from harness_maker.render import _is_codex_hooks_json

    assert _is_codex_hooks_json(_fe(".codex/hooks.json"))


def test_is_codex_hooks_json_false_for_claude_hooks() -> None:
    from harness_maker.render import _is_codex_hooks_json

    assert not _is_codex_hooks_json(_fe("hooks/hooks.json"))


def test_is_codex_config_toml_true() -> None:
    from harness_maker.render import _is_codex_config_toml

    assert _is_codex_config_toml(_fe(".codex/config.toml"))


def test_is_codex_config_toml_false_for_other() -> None:
    from harness_maker.render import _is_codex_config_toml

    assert not _is_codex_config_toml(_fe("harness.yaml"))


def test_is_codex_agent_toml_true() -> None:
    from harness_maker.render import _is_codex_agent_toml

    assert _is_codex_agent_toml(_fe(".codex/agents/code-reviewer.toml"))
    assert _is_codex_agent_toml(_fe(".codex/agents/executor.toml"))


def test_is_codex_agent_toml_false_for_md_agent() -> None:
    from harness_maker.render import _is_codex_agent_toml

    assert not _is_codex_agent_toml(_fe("agents/code-reviewer.md"))


def test_is_agents_md_true() -> None:
    from harness_maker.render import _is_agents_md

    assert _is_agents_md(_fe("AGENTS.md"))


def test_is_agents_md_false_for_claude_md() -> None:
    from harness_maker.render import _is_agents_md

    assert not _is_agents_md(_fe("../CLAUDE.md"))
    assert not _is_agents_md(_fe("CLAUDE.md"))


def test_render_pure_toml_invalid_raises_value_error(tmp_path: Path) -> None:
    """_render_pure_toml() raises ValueError containing template name on parse failure."""

    from harness_maker.render import _render_pure_toml

    # Write a valid Jinja2 template that renders invalid TOML
    (tmp_path / "bad.toml.j2").write_text("this is not valid toml content\n")
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import FileEntry

    env = Environment(
        loader=FileSystemLoader(str(tmp_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    fe = FileEntry(path=Path(".codex/config.toml"), template="bad.toml.j2", context={})
    with pytest.raises(ValueError, match="bad.toml"):
        _render_pure_toml(fe, env, tmp_path / ".claude", dry_run=True, freeze_time=None)


def test_render_pure_toml_valid_toml_dry_run(tmp_path: Path) -> None:
    """_render_pure_toml() does not write when dry_run=True."""
    from harness_maker.render import _render_pure_toml

    (tmp_path / "ok.toml.j2").write_text("[features]\ncodex_hooks = true\n")
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import FileEntry

    env = Environment(
        loader=FileSystemLoader(str(tmp_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    fe = FileEntry(path=Path(".codex/config.toml"), template="ok.toml.j2", context={})
    out = _render_pure_toml(fe, env, target_dir, dry_run=True, freeze_time=None)
    assert str(out).endswith(".codex/config.toml")
    assert not (tmp_path / ".codex" / "config.toml").exists()


def test_render_agents_md_dry_run(tmp_path: Path) -> None:
    """_render_agents_md() renders AGENTS.md as pure text with HTML-comment metadata."""
    from harness_maker.render import _render_agents_md

    (tmp_path / "agents.md.j2").write_text("# Project Instructions\n\nHello.\n")
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import FileEntry

    env = Environment(
        loader=FileSystemLoader(str(tmp_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    fe = FileEntry(path=Path("AGENTS.md"), template="agents.md.j2", context={})
    out = _render_agents_md(fe, env, target_dir, dry_run=True, freeze_time=None)
    assert out == tmp_path / "AGENTS.md"


def test_render_agents_md_writes_html_comment_metadata(tmp_path: Path) -> None:
    """AGENTS.md written to disk has harness-maker HTML metadata comment."""
    from harness_maker.render import _render_agents_md

    (tmp_path / "agents.md.j2").write_text("# Project Instructions\n")
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import FileEntry

    env = Environment(
        loader=FileSystemLoader(str(tmp_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    fe = FileEntry(path=Path("AGENTS.md"), template="agents.md.j2", context={})
    out = _render_agents_md(fe, env, target_dir, dry_run=False, freeze_time=None)
    content = out.read_text(encoding="utf-8")
    assert "<!-- harness-maker:" in content
    assert "content_hash=" in content


def test_render_agents_md_block_merge_preserves_user_blocks(tmp_path: Path) -> None:
    """Re-rendering AGENTS.md with merge_reports preserves @hm:user:* block content."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import FileEntry
    from harness_maker.render import DEFAULT_FREEZE_TIME, _render_agents_md

    template_text = (
        "# AGENTS.md\n\n"
        "<!-- @hm:user:rules -->\n"
        "<!-- Default placeholder. -->\n"
        "<!-- @hm:/user:rules -->\n"
    )
    (tmp_path / "agents.md.j2").write_text(template_text)
    env = Environment(
        loader=FileSystemLoader(str(tmp_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    # Simulate existing AGENTS.md with user's custom rules
    existing = (
        "<!-- harness-maker: content_hash=old version=0.8.1 generated_at=2026-01-01 -->\n"
        "# AGENTS.md\n\n"
        "<!-- @hm:user:rules -->\n"
        "Use snake_case always.\n"
        "<!-- @hm:/user:rules -->\n"
    )
    (tmp_path / "AGENTS.md").write_text(existing)

    merge_reports: dict[Path, MergeReport] = {}
    fe = FileEntry(path=Path("AGENTS.md"), template="agents.md.j2", context={})
    out = _render_agents_md(
        fe,
        env,
        target_dir,
        dry_run=False,
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_reports=merge_reports,
    )
    result = out.read_text(encoding="utf-8")
    # User block preserved
    assert "Use snake_case always." in result
    # Default placeholder replaced
    assert "Default placeholder." not in result
    # Metadata header still present with new hash
    assert result.startswith("<!-- harness-maker:")
    assert "content_hash=" in result
    # merge reported
    assert Path("AGENTS.md") in merge_reports


def test_render_agents_md_block_merge_fallback_on_missing_file(tmp_path: Path) -> None:
    """When no existing AGENTS.md, merge_reports provided but no file → fresh render."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import FileEntry
    from harness_maker.render import DEFAULT_FREEZE_TIME, _render_agents_md

    (tmp_path / "agents.md.j2").write_text("# Fresh\n")
    env = Environment(
        loader=FileSystemLoader(str(tmp_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    merge_reports: dict[Path, MergeReport] = {}
    fe = FileEntry(path=Path("AGENTS.md"), template="agents.md.j2", context={})
    out = _render_agents_md(
        fe,
        env,
        target_dir,
        dry_run=False,
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_reports=merge_reports,
    )
    assert out.read_text(encoding="utf-8").startswith("<!-- harness-maker:")
    assert Path("AGENTS.md") not in merge_reports  # no merge; no existing file


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1+3 (PLAN-onboarding-backup-friction, ADR-003/006):
# _merge_hooks_json in-place 3-way merge tests.
# ─────────────────────────────────────────────────────────────────────────────


def test_merge_hooks_json_claude_nested_preserves_user_entries() -> None:
    """Claude PascalCase nested schema: user entries with distinct (matcher,
    command, type) identity survive template re-render; shipped entries get
    template-replaced; matcher-less events (Stop, SessionStart) work."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "shipped-telemetry"}],
                },
                {
                    "matcher": "Write|Edit",
                    "hooks": [{"type": "command", "command": "user-custom-write-hook"}],
                },
            ],
            "Stop": [
                {"hooks": [{"type": "command", "command": "shipped-stop"}]},
                {"hooks": [{"type": "command", "command": "user-custom-stop"}]},
            ],
        },
        "preset": "Side",  # user wrote this; template has Production
    }
    new_data = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "shipped-telemetry"}],
                },
            ],
            "Stop": [
                {"hooks": [{"type": "command", "command": "shipped-stop"}]},
            ],
        },
        "preset": "Production",
    }
    merged = _merge_hooks_json(existing, new_data)
    # PostToolUse: shipped (telemetry) + user (Write|Edit custom)
    post_tool = merged["hooks"]["PostToolUse"]
    assert len(post_tool) == 2
    assert post_tool[0]["hooks"][0]["command"] == "shipped-telemetry"
    assert post_tool[1]["hooks"][0]["command"] == "user-custom-write-hook"
    # Stop: shipped + user (matcher-less event preserved correctly)
    stop = merged["hooks"]["Stop"]
    assert len(stop) == 2
    assert stop[0]["hooks"][0]["command"] == "shipped-stop"
    assert stop[1]["hooks"][0]["command"] == "user-custom-stop"
    # Top-level: template wins on conflict
    assert merged["preset"] == "Production"


def test_merge_hooks_json_codex_permission_request_event() -> None:
    """Codex's PermissionRequest event (matcher-less, nested) preserves user
    custom entries with different commands."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PermissionRequest": [
                {"hooks": [{"type": "command", "command": "shipped-permission-gate"}]},
                {"hooks": [{"type": "command", "command": "user-extra-permission-check"}]},
            ],
        },
    }
    new_data = {
        "hooks": {
            "PermissionRequest": [
                {"hooks": [{"type": "command", "command": "shipped-permission-gate"}]},
            ],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    pr = merged["hooks"]["PermissionRequest"]
    assert len(pr) == 2
    assert pr[0]["hooks"][0]["command"] == "shipped-permission-gate"
    assert pr[1]["hooks"][0]["command"] == "user-extra-permission-check"


def test_merge_hooks_json_user_event_unknown_to_template_preserved() -> None:
    """User added a hook for an event our template doesn't ship — preserve verbatim."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "shipped"}]},
            ],
            "UserSpecialEvent": [
                {"matcher": "X", "hooks": [{"type": "command", "command": "user-only"}]},
            ],
        },
    }
    new_data = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "shipped"}]},
            ],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    assert "UserSpecialEvent" in merged["hooks"]
    assert merged["hooks"]["UserSpecialEvent"][0]["hooks"][0]["command"] == "user-only"


def test_merge_hooks_json_malformed_existing_falls_back_to_template() -> None:
    """Existing has non-dict 'hooks' field → fall back to template overwrite."""
    from harness_maker.render import _merge_hooks_json

    existing = {"hooks": "this is not a dict"}
    new_data = {"hooks": {"PostToolUse": [{"matcher": "*", "hooks": []}]}}
    merged = _merge_hooks_json(existing, new_data)
    # Fell back to template (new_data) unchanged
    assert merged == new_data


def test_merge_hooks_json_collapses_duplicate_user_and_shipped() -> None:
    """User entry with identical (matcher, command, type) to shipped → dedup
    to template-only (no double entries). Documented semantic dedup."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "X"}]},
                {"matcher": "*", "hooks": [{"type": "command", "command": "X"}]},
            ],
        },
    }
    new_data = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "X"}]},
            ],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    # Both existing entries match template identity → no user-only addition;
    # result has exactly one entry from template.
    assert len(merged["hooks"]["PostToolUse"]) == 1


def test_merge_hooks_json_malformed_entries_dropped() -> None:
    """Entry with non-string command, missing matcher, or non-list hooks →
    dropped from identity computation; doesn't crash merge."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "good"}]},
                {"matcher": 123, "hooks": [{"command": "bad-matcher-type"}]},  # noqa: E501 - matcher must be str
                "not even a dict",  # malformed entry
                {"hooks": "not a list"},  # malformed
            ],
        },
    }
    new_data = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": "good"}]},
            ],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    # Only the well-formed shipped entry; malformed entries dropped silently
    # (backup is the recovery path per ADR-001).
    assert len(merged["hooks"]["PostToolUse"]) == 1
    assert merged["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == "good"


def test_merge_hooks_json_dedupes_across_hm_cache_version_bumps() -> None:
    """Regression for spoton 2026-05-23: each `/plugin update` re-renders hook
    commands with a fresh `uv run --with .../harness-maker/X.Y.Z/...` path.
    Without command-path normalization, the merge treated the on-disk
    previous-version entry as a "user addition" (its full command string
    differed by 5 chars from the shipped command), preserved it alongside
    the new entry, and produced duplicate hooks that fired twice per event
    AND dangled at a cache version `/plugin update` later cleaned up.

    This test pins the FIX: the harness-maker-managed cache-version-pinned
    portion of the command is elided before identity comparison, so the same
    semantic hook entry across versions dedupes correctly.
    """
    from harness_maker.render import _merge_hooks_json

    # Existing on-disk: a previous-version (0.23.2) harness-maker-managed
    # entry — the situation in spoton after /plugin update bumped to 0.23.4.
    old_cmd = (
        "uv run --with /home/noel/.claude/plugins/cache/"
        "harness-maker-local/harness-maker/0.23.2 python -m "
        "harness_maker.gates.permission_gate"
    )
    new_cmd = (
        "uv run --with /home/noel/.claude/plugins/cache/"
        "harness-maker-local/harness-maker/0.23.7 python -m "
        "harness_maker.gates.permission_gate"
    )
    existing = {
        "hooks": {
            "PermissionRequest": [
                {"hooks": [{"type": "command", "command": old_cmd}]},
            ],
        },
    }
    new_data = {
        "hooks": {
            "PermissionRequest": [
                {"hooks": [{"type": "command", "command": new_cmd}]},
            ],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    # Exactly ONE entry — the new-version command. The old-version entry
    # MUST NOT survive as a "user addition" because it's the SAME semantic
    # hook, just pinned at the prior cache version.
    assert len(merged["hooks"]["PermissionRequest"]) == 1, (
        f"merge produced {len(merged['hooks']['PermissionRequest'])} entries; "
        f"version-bump dedup is broken — spoton-class regression"
    )
    assert merged["hooks"]["PermissionRequest"][0]["hooks"][0]["command"] == new_cmd, (
        "merged entry should be the new shipped command, not the stale on-disk one"
    )


def test_merge_hooks_json_preserves_genuine_user_added_command_alongside_hm() -> None:
    """The counter-test: a user-authored hook command (NOT matching the
    harness-maker cache shape) is correctly preserved as a user addition
    even when a harness-maker-managed entry also exists. Confirms the
    normalize-only-hm-managed surface is tight."""
    from harness_maker.render import _merge_hooks_json

    hm_old = (
        "uv run --with /home/noel/.claude/plugins/cache/"
        "harness-maker-local/harness-maker/0.23.2 python -m "
        "harness_maker.gates.permission_gate"
    )
    hm_new = (
        "uv run --with /home/noel/.claude/plugins/cache/"
        "harness-maker-local/harness-maker/0.23.7 python -m "
        "harness_maker.gates.permission_gate"
    )
    user_cmd = "/usr/local/bin/my-custom-permission-check.sh"
    existing = {
        "hooks": {
            "PermissionRequest": [
                {"hooks": [{"type": "command", "command": hm_old}]},
                {"hooks": [{"type": "command", "command": user_cmd}]},
            ],
        },
    }
    new_data = {
        "hooks": {
            "PermissionRequest": [
                {"hooks": [{"type": "command", "command": hm_new}]},
            ],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    cmds = [e["hooks"][0]["command"] for e in merged["hooks"]["PermissionRequest"]]
    # New hm-managed command replaces the old one; user-authored command
    # survives as a user addition.
    assert hm_new in cmds, "new hm-managed command must be present"
    assert user_cmd in cmds, "genuine user-added command must be preserved"
    assert hm_old not in cmds, "old hm-managed command must be deduped out"
    assert len(cmds) == 2, f"expected 2 entries (hm-new + user), got {len(cmds)}: {cmds}"


# ──────────────────────────────────────────────────────────────────────────
# PLAN-hooks-merge-stale-path-dedup: the 05-22 normalizer matched ONLY the
# `harness-maker-local` cache path, so the GitHub marketplace cache and the
# dev-repo `--with` path evaded dedup → triplication on marketplace switch
# (spoton 2026-05-28). Identity must key on the `python -m harness_maker.*`
# module namespace, path-agnostic. (ADR-001)
# ──────────────────────────────────────────────────────────────────────────

_GH = "/home/noel/.claude/plugins/cache/harness-maker/harness-maker/0.26.6"
_GH_OLD = "/home/noel/.claude/plugins/cache/harness-maker/harness-maker/0.26.5"
_LOCAL = "/home/noel/.claude/plugins/cache/harness-maker-local/harness-maker/0.26.4"
_DEVREPO = "/home/noel/harness-maker"


def _hm_cmd(path: str, invocation: str = "harness_maker.gates.permission_gate") -> str:
    return f"uv run --with {path} python -m {invocation}"


def _nested_entry(command: str, matcher: str | None = None) -> dict[str, Any]:
    e: dict[str, Any] = {"hooks": [{"type": "command", "command": command}]}
    if matcher is not None:
        e["matcher"] = matcher
    return e


def test_merge_hooks_json_dedupes_across_github_cache_version_bump() -> None:
    """github marketplace cache path (no `-local`) must dedup across version bumps,
    just like the local cache already did."""
    from harness_maker.render import _merge_hooks_json

    existing = {"hooks": {"PreToolUse": [_nested_entry(_hm_cmd(_GH_OLD), "Bash")]}}
    new_data = {"hooks": {"PreToolUse": [_nested_entry(_hm_cmd(_GH), "Bash")]}}
    merged = _merge_hooks_json(existing, new_data)
    entries = merged["hooks"]["PreToolUse"]
    assert len(entries) == 1, f"github-cache version bump must dedup, got {len(entries)}"
    assert entries[0]["hooks"][0]["command"] == _hm_cmd(_GH)


def test_merge_hooks_json_collapses_marketplace_switch_local_and_devrepo() -> None:
    """spoton scenario: existing on-disk has local-cache + dev-repo forms; the
    template ships the github form. All three are the SAME hook → collapse to one
    (the github/template entry)."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PreToolUse": [
                _nested_entry(_hm_cmd(_LOCAL), "Bash"),
                _nested_entry(_hm_cmd(_DEVREPO), "Bash"),
            ],
        },
    }
    new_data = {"hooks": {"PreToolUse": [_nested_entry(_hm_cmd(_GH), "Bash")]}}
    merged = _merge_hooks_json(existing, new_data)
    entries = merged["hooks"]["PreToolUse"]
    assert len(entries) == 1, f"local+devrepo+github are one hook; got {len(entries)}"
    assert entries[0]["hooks"][0]["command"] == _hm_cmd(_GH)


def test_merge_hooks_json_self_heals_full_triplication() -> None:
    """An already-triplicated on-disk file (github-old + local + dev-repo) re-rendered
    against the current github template self-heals to one entry per (event,matcher,module)."""
    from harness_maker.render import _merge_hooks_json

    existing = {
        "hooks": {
            "PreToolUse": [
                _nested_entry(_hm_cmd(_GH_OLD), "Bash"),
                _nested_entry(_hm_cmd(_LOCAL), "Bash"),
                _nested_entry(_hm_cmd(_DEVREPO), "Bash"),
            ],
        },
    }
    new_data = {"hooks": {"PreToolUse": [_nested_entry(_hm_cmd(_GH), "Bash")]}}
    merged = _merge_hooks_json(existing, new_data)
    entries = merged["hooks"]["PreToolUse"]
    assert len(entries) == 1, f"triplication must self-heal to 1, got {len(entries)}"
    assert entries[0]["hooks"][0]["command"] == _hm_cmd(_GH)


def test_merge_hooks_json_normalizes_with_intermediate_uv_flag() -> None:
    """W1: identity must be prefix-agnostic. Use the LOCAL cache path (which the
    old regex DID match) plus an intermediate `--python 3.12` flag (which the old
    anchored `<path> python` regex could NOT tolerate), isolating the flag
    dimension from the path-family dimension."""
    from harness_maker.render import _merge_hooks_json

    local_new = _LOCAL.replace("/0.26.4", "/0.26.5")
    old = f"uv run --with {_LOCAL} --python 3.12 python -m harness_maker.telemetry"
    new = f"uv run --with {local_new} --python 3.12 python -m harness_maker.telemetry"
    existing = {"hooks": {"PostToolUse": [_nested_entry(old, "*")]}}
    new_data = {"hooks": {"PostToolUse": [_nested_entry(new, "*")]}}
    merged = _merge_hooks_json(existing, new_data)
    entries = merged["hooks"]["PostToolUse"]
    assert len(entries) == 1, f"intermediate-flag command must still dedup, got {len(entries)}"


def test_merge_hooks_json_matcherless_args_discriminate() -> None:
    """W4: matcher-less Stop hooks — trailing args are the sole discriminator.
    Same module + DIFFERENT args stay distinct; same module + same args across
    different paths collapse to one."""
    from harness_maker.render import _merge_hooks_json

    stop_a = "harness_maker.hooks.loop_gate --mode stop-hook"
    stop_b = "harness_maker.hooks.loop_gate --mode subagent-stop"
    # Different args → must stay distinct (2 entries).
    existing = {"hooks": {"Stop": [_nested_entry(_hm_cmd(_GH, stop_b))]}}
    new_data = {
        "hooks": {
            "Stop": [_nested_entry(_hm_cmd(_GH, stop_a)), _nested_entry(_hm_cmd(_GH, stop_b))],
        },
    }
    merged = _merge_hooks_json(existing, new_data)
    assert len(merged["hooks"]["Stop"]) == 2, "different --mode args must NOT collapse"
    # Same args, different paths → must collapse to one.
    existing2 = {"hooks": {"Stop": [_nested_entry(_hm_cmd(_LOCAL, stop_a))]}}
    new_data2 = {"hooks": {"Stop": [_nested_entry(_hm_cmd(_GH, stop_a))]}}
    merged2 = _merge_hooks_json(existing2, new_data2)
    assert len(merged2["hooks"]["Stop"]) == 1, "same module+args across paths must collapse"


def test_rendered_hooks_template_has_unique_identity_per_event(tmp_path: Path) -> None:
    """W2 / ADR-003: self-heal collapses ON-DISK dups against the template set but
    never dedups template-internal entries. Guard the template-side invariant:
    the freshly-rendered nested hooks.json has exactly one identity per
    (event, matcher, module) — so a future Jinja change that emits a duplicate
    fails loudly here instead of shipping a dup the merge can't fix."""
    import json

    from harness_maker.models import Blueprint, FileEntry
    from harness_maker.render import _entry_identity, render

    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("hooks/hooks.json"),
                template="hooks/hooks.json.j2",
                context={
                    "harness_maker_src_path": "/dummy",
                    "preset": "Production",
                    "config": SimpleNamespace(preset="Production", spec={"strictness": "block"}),
                },
                frontmatter={},
            ),
        ],
    )
    render(bp, target_dir, merge_json_paths={Path("hooks/hooks.json")})
    data = json.loads((target_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for event, entries in data["hooks"].items():
        idents = [_entry_identity(e) for e in entries]
        assert len(idents) == len(set(idents)), (
            f"template emits duplicate hook identities in event {event!r}: {idents}"
        )


def test_render_hooks_json_merged_manifest_records_merged_hash(tmp_path: Path) -> None:
    """REVIEW fix (code-reviewer P1): Phase 1+3 exit criterion explicitly required
    a manifest test. After in-place merge, `.hm-render-manifest.jsonl` MUST
    record the SHA-256 of the MERGED bytes (not template-only). Otherwise
    sweep_orphans._classify_orphan falls into the "theirs" branch on every
    brownfield re-render and emits permanent KEEP+warn for hooks.json.

    This test exercises the full render → manifest → sweep_orphans path,
    not just `_merge_hooks_json` in isolation.
    """
    import hashlib
    import json

    from harness_maker.models import Blueprint, FileEntry
    from harness_maker.reconcile import sweep_orphans
    from harness_maker.render import RENDER_MANIFEST_NAME, render

    # Existing brownfield hooks.json with a user-added entry the template doesn't ship
    target_dir = tmp_path / ".claude"
    target_dir.mkdir()
    existing_path = target_dir / "hooks" / "hooks.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "user-custom"}],
                        },
                    ],
                },
            },
        )
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("hooks/hooks.json"),
                template="hooks/hooks.json.j2",
                context={
                    "harness_maker_src_path": "/dummy",
                    "preset": "Side",
                    "config": SimpleNamespace(preset="Side", spec={"strictness": "warn"}),
                },
                frontmatter={},
            ),
        ],
    )

    # MERGE_JSON path: render() must (a) merge in place + (b) record MERGED hash
    render(
        bp,
        target_dir,
        merge_json_paths={Path("hooks/hooks.json")},
        freeze_time=DEFAULT_FREEZE_TIME,
    )

    # User-added entry survived
    merged_text = existing_path.read_text(encoding="utf-8")
    assert "user-custom" in merged_text, "User entry must survive the merge"

    # Manifest hash matches the merged bytes (not template-only)
    manifest_path = target_dir / RENDER_MANIFEST_NAME
    assert manifest_path.is_file()
    manifest_lines = [
        json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line
    ]
    # Manifest key for .claude/-bound files is prefixed with ".claude/" per
    # _manifest_key_for (render.py:933-951). Cross-tree files (.codex/, .agents/)
    # keep their prefix; this is the .claude/-bound case.
    hooks_entries = [e for e in manifest_lines if e["path"] == ".claude/hooks/hooks.json"]
    assert hooks_entries, "Manifest must record an entry for hooks/hooks.json"
    recorded_hash = hooks_entries[-1]["content_hash"]
    merged_bytes = existing_path.read_bytes()
    expected_hash = hashlib.sha256(merged_bytes).hexdigest()
    assert recorded_hash == expected_hash, (
        f"Manifest recorded {recorded_hash} but on-disk merged hash is {expected_hash}. "
        f"sweep_orphans._classify_orphan would mis-route this file to 'theirs'."
    )

    # sweep_orphans does NOT classify the merged hooks.json as orphan/theirs
    # (the manifest match path in reconcile.py:411-428 sees ours-clean)
    sweep_report = sweep_orphans(tmp_path, bp)
    # hooks/hooks.json is in the blueprint, so orphan-sweep skips it as expected.
    # The key invariant: it must NOT appear in kept with classification "theirs".
    theirs_paths = [str(p) for p, classifier in sweep_report.kept if classifier == "theirs"]
    assert "hooks/hooks.json" not in theirs_paths, (
        f"Merged hooks.json mis-classified as 'theirs' by sweep_orphans: {theirs_paths}"
    )
