"""Phase 7 (PLAN-onboarding-backup-friction) cross-IDE preservation e2e.

End-to-end on-disk verification that the Phase 1+3 (hooks.json schema-aware
3-way merge) and Phase 2 (TOML/sh marker-aware MERGE_BLOCK) and Phase 4
(`.backup-*/` auto-gitignore) work survive a realistic brownfield re-render
across the three target file trees (claude-code, cursor, codex).

Per CLAUDE.md §테스트 정책 + checkpoint 8 of §"무언가를 고치거나 개선하기 전에":
- This module is the **automated half** of Phase 7. It exercises render →
  reconcile → manifest → sweep_orphans chains directly with realistic
  synthesize() blueprints.
- The **manual half** — verifying that Cursor IDE / Codex CLI actually FIRE
  the merged hooks at runtime — lives in `tests/cursor-compat/MANUAL_CHECKLIST.md`
  and is user-only (no IDE driver automation per CLAUDE.md ckpt 8).

Gated by ``INTEGRATION=1`` to avoid loading on every unit test run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import InterviewAnswers, ProjectProfile, Target
from harness_maker.reconcile import backup, reconcile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="Phase 7 e2e: set INTEGRATION=1 to run (preservation round-trip)",
)


def _build_targets(targets: list[Target]) -> tuple[ProjectProfile, InterviewAnswers]:
    """Build a (profile, answers) pair with the requested target list."""
    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True).model_copy(
        update={"targets": targets},
    )
    return profile, answers


def _render_initial(target_dir: Path, targets: list[Target]) -> None:
    """Fresh render — produces template content for every target."""
    profile, answers = _build_targets(targets)
    bp = synthesize(profile, answers)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)


def _render_brownfield(
    project_root: Path,
    target_dir: Path,
    targets: list[Target],
) -> None:
    """Brownfield render: backup() + reconcile() + render() — mirrors cli.make."""
    from harness_maker.models import ReconcileDecision

    profile, answers = _build_targets(targets)
    bp = synthesize(profile, answers)

    backup(target_dir)
    conflicts = reconcile(target_dir, bp)
    keep_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.KEEP}
    merge_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.MERGE_BLOCK}
    merge_json_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.MERGE_JSON}
    bp = bp.model_copy(update={"files": [f for f in bp.files if f.path not in keep_paths]})
    render(
        bp,
        target_dir,
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_paths=merge_paths,
        merge_json_paths=merge_json_paths,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1+3 hooks.json schema-aware in-place merge (3 schemas)
# ─────────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_e2e_claude_hooks_json_user_entry_survives(tmp_path: Path) -> None:
    """Claude PascalCase nested: user-added PostToolUse entry survives re-render.

    Scenario: (1) fresh /hm:make, (2) user appends a custom hook entry to
    hooks/hooks.json, (3) /hm:make --update, (4) assert user entry on disk
    AND shipped entries also present (template updates propagate).
    """
    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    _render_initial(target_dir, [Target.CLAUDE_CODE])

    hooks_path = target_dir / "hooks" / "hooks.json"
    assert hooks_path.is_file()

    # User edits the shipped hooks.json to add a custom PostToolUse entry.
    initial = json.loads(hooks_path.read_text(encoding="utf-8"))
    initial["hooks"].setdefault("PostToolUse", []).append(
        {
            "matcher": "Read",
            "hooks": [
                {"type": "command", "command": "my-custom-audit-logger", "timeout": 5},
            ],
        },
    )
    hooks_path.write_text(json.dumps(initial, indent=2) + "\n", encoding="utf-8")

    # Brownfield re-render
    _render_brownfield(project_root, target_dir, [Target.CLAUDE_CODE])

    after = json.loads(hooks_path.read_text(encoding="utf-8"))
    post_tool = after["hooks"]["PostToolUse"]
    commands = [e["hooks"][0]["command"] for e in post_tool]
    # User entry survived
    assert "my-custom-audit-logger" in commands
    # Shipped telemetry entry still there (template-wins on overlap)
    assert any("telemetry" in c for c in commands)


@INTEGRATION_GATE
def test_e2e_cursor_hooks_json_user_entry_survives(tmp_path: Path) -> None:
    """Cursor flat lowercase: user-added preToolUse entry survives.

    Cursor schema differs (flat {matcher, command} vs Claude nested) — ADR-006
    schema dispatch must route this to flat identity (matcher_or_empty, command).
    """
    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    _render_initial(target_dir, [Target.CLAUDE_CODE, Target.CURSOR])

    cursor_hooks = project_root / ".cursor" / "hooks.json"
    assert cursor_hooks.is_file()

    initial = json.loads(cursor_hooks.read_text(encoding="utf-8"))
    initial["hooks"].setdefault("preToolUse", []).append(
        {"matcher": "Read", "command": "my-cursor-custom-pretool"},
    )
    cursor_hooks.write_text(json.dumps(initial, indent=2) + "\n", encoding="utf-8")

    _render_brownfield(project_root, target_dir, [Target.CLAUDE_CODE, Target.CURSOR])

    after = json.loads(cursor_hooks.read_text(encoding="utf-8"))
    pretool_commands = [e["command"] for e in after["hooks"]["preToolUse"]]
    assert "my-cursor-custom-pretool" in pretool_commands
    # Shipped permission-gate entry still present
    assert any("permission_gate" in c for c in pretool_commands)


@INTEGRATION_GATE
def test_e2e_codex_hooks_json_permission_request_user_entry_survives(
    tmp_path: Path,
) -> None:
    """Codex PermissionRequest (matcher-less, nested) — user entry survives.

    Phase 1 closed the literal-match latent KEEP-fallback bug for
    `.codex/hooks.json`; Phase 3 made it MERGE_JSON. The PermissionRequest
    event has no `matcher` field — ADR-006's `matcher.get("", "")` fallback
    in the identity tuple must handle it.
    """
    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    _render_initial(target_dir, [Target.CLAUDE_CODE, Target.CODEX])

    codex_hooks = project_root / ".codex" / "hooks.json"
    assert codex_hooks.is_file()

    initial = json.loads(codex_hooks.read_text(encoding="utf-8"))
    initial["hooks"].setdefault("PermissionRequest", []).append(
        {
            "hooks": [
                {"type": "command", "command": "my-codex-extra-permission-check"},
            ],
        },
    )
    codex_hooks.write_text(json.dumps(initial, indent=2) + "\n", encoding="utf-8")

    _render_brownfield(project_root, target_dir, [Target.CLAUDE_CODE, Target.CODEX])

    after = json.loads(codex_hooks.read_text(encoding="utf-8"))
    pr_commands = [e["hooks"][0]["command"] for e in after["hooks"]["PermissionRequest"]]
    assert "my-codex-extra-permission-check" in pr_commands
    # Shipped permission_gate still present
    assert any("permission_gate" in c for c in pr_commands)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: TOML marker-aware MERGE_BLOCK on shipped `.codex/config.toml`
# ─────────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_e2e_codex_config_toml_user_block_survives(tmp_path: Path) -> None:
    """User-written `# @hm:user:NAME` ... `# @hm:/user:NAME` block in .codex/config.toml survives.

    Phase 2 (ADR-004/007): shipped template ships an empty user-extensions
    block; users add content between the markers; reconcile dispatches
    MERGE_BLOCK; render preserves the user-block content.
    """
    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    _render_initial(target_dir, [Target.CLAUDE_CODE, Target.CODEX])

    config_path = project_root / ".codex" / "config.toml"
    assert config_path.is_file()

    initial_text = config_path.read_text(encoding="utf-8")
    # Locate the shipped user-extensions block and seed it with user content.
    seeded_text = initial_text.replace(
        "# @hm:user:extensions\n"
        '# Add custom Codex configuration here ([mcp_servers."..."], '
        "[agents.NAME], etc.).\n"
        "# Content between these markers is preserved across `harness-maker make` "
        "re-renders\n"
        "# (PLAN-onboarding-backup-friction Phase 2, ADR-004/007).\n"
        "# @hm:/user:extensions",
        "# @hm:user:extensions\n"
        '[mcp_servers."my-custom-server"]\n'
        'command = "uv run my-server"\n'
        "# @hm:/user:extensions",
    )
    # Sanity: the replace landed (the shipped marker block text matched verbatim)
    assert seeded_text != initial_text, (
        "User-block seed failed — shipped marker block text changed; "
        "update the test fixture to match new template prose."
    )
    config_path.write_text(seeded_text, encoding="utf-8")

    _render_brownfield(project_root, target_dir, [Target.CLAUDE_CODE, Target.CODEX])

    after_text = config_path.read_text(encoding="utf-8")
    # User block content survived
    assert "my-custom-server" in after_text
    # Shipped block markers still present (round-trip intact)
    assert "# @hm:user:extensions" in after_text
    assert "# @hm:/user:extensions" in after_text


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: .backup-*/ auto-gitignore wiring (brownfield round-trip)
# ─────────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_e2e_backup_glob_added_to_user_gitignore(tmp_path: Path) -> None:
    """Brownfield render appends `.backup-*/` to user's .gitignore; idempotent.

    Mirrors cli.make()'s call site of `_ensure_gitignore_entry` after backup().
    """
    from harness_maker.worktree import _ensure_gitignore_entry

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    _render_initial(target_dir, [Target.CLAUDE_CODE])

    # Simulate the cli.make() brownfield branch:
    _ensure_gitignore_entry(project_root, ".backup-*/")
    _ensure_gitignore_entry(project_root, ".backup-*/")  # idempotency

    gitignore = project_root / ".gitignore"
    assert gitignore.is_file()
    text = gitignore.read_text(encoding="utf-8")
    assert ".backup-*/" in text
    # Substring count must be 1 — idempotent append
    assert text.count(".backup-*/") == 1
