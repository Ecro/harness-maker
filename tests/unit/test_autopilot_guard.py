"""Phase 4 — autopilot_guard PreToolUse hook (PLAN-human-bottleneck-auto-advance).

ADR-003 (P4-impl refinement): a code-fixed never-auto list is enforced ONLY while
the `.hm-autopilot` marker is active. autopilot OFF → the guard is a no-op, so a
solo user's manual `git push` / `rm` is untouched (the footgun a static settings.json
deny would have created). autopilot ON → never-auto ops are blocked. The list is
non-overridable; `autonomy.extra_deny` can only ADD.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

from harness_maker import autopilot
from harness_maker.hooks import autopilot_guard as guard
from harness_maker.models import AtomicStage

_PIPE = [AtomicStage.RESEARCH, AtomicStage.WRAPUP]


def _activate(root: Path) -> None:
    autopilot.write(root, level="auto_safe", pipeline=_PIPE)


def _bash(cmd: str) -> dict[str, str]:
    return {"command": cmd}


# --- the keystone: OFF → no-op (manual workflows untouched) ----------------------


def test_marker_off_allows_everything(tmp_path: Path) -> None:
    # No autopilot marker → guard must NOT block even a never-auto command.
    d = guard.evaluate("Bash", _bash("git push origin main"), tmp_path)
    assert d.allow is True


def test_marker_off_allows_rm(tmp_path: Path) -> None:
    d = guard.evaluate("Bash", _bash("rm -rf /tmp/whatever"), tmp_path)
    assert d.allow is True


# --- ON → never-auto blocked -----------------------------------------------------


def test_active_blocks_git_push(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("git push origin main"), tmp_path).allow is False


def test_active_blocks_force_push(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("git push --force-with-lease"), tmp_path).allow is False


def test_active_blocks_reset_hard(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("git reset --hard HEAD~1"), tmp_path).allow is False


def test_active_blocks_stash_drop(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("git stash drop stash@{0}"), tmp_path).allow is False


def test_active_blocks_rm_escaping_worktree(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("rm -rf /etc/hosts"), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("rm -rf ../sibling"), tmp_path).allow is False


def test_active_blocks_publish_and_deploy(tmp_path: Path) -> None:
    _activate(tmp_path)
    for cmd in ("uv publish", "npm publish", "twine upload dist/*", "terraform destroy"):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


def test_active_blocks_settings_edit(tmp_path: Path) -> None:
    _activate(tmp_path)
    d = guard.evaluate("Write", {"file_path": ".claude/settings.json"}, tmp_path)
    assert d.allow is False


# --- ON → surgical: safe commands still allowed (no blanket interpreter ban) ------


def test_active_allows_safe_commands(tmp_path: Path) -> None:
    _activate(tmp_path)
    for cmd in ("uv run pytest", "git status", "git diff HEAD", "ls -la", "python -m pytest"):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


def test_active_does_not_block_harness_self_call(tmp_path: Path) -> None:
    # CRITICAL: never-auto must NOT be a blanket interpreter ban — the harness
    # invokes `python -m harness_maker...` for its own hooks/CLI.
    _activate(tmp_path)
    cmd = "uv run python -m harness_maker.worktree create execute ."
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True


def test_active_allows_in_project_write(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Write", {"file_path": "src/foo.py"}, tmp_path).allow is True


# --- extra_deny is ADDITIVE; baseline is non-overridable -------------------------


def test_extra_deny_adds_a_pattern(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "autonomy:\n  level: auto_safe\n  extra_deny: ['make deploy-prod']\n"
    )
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("make deploy-prod"), tmp_path).allow is False
    # baseline still fires regardless of what extra_deny contains
    assert guard.evaluate("Bash", _bash("git push"), tmp_path).allow is False


def test_baseline_constant_is_nonempty_code_fixed() -> None:
    # Non-overridable: the baseline lives in code, not config. rm/find/publish/
    # permission-surface are regex; git is word-tokenized (_git_segment_hit).
    cats = {c for c, _ in guard.NEVER_AUTO_BASH}
    assert {
        "rm-escapes-worktree",
        "find-delete",
        "publish-or-deploy",
        "permission-surface-write",
    } <= cats


# --- REVIEW round 1 hardening: git tokenizer, bypass surface, marker root ---------


def test_active_blocks_git_push_with_config_prefix(tmp_path: Path) -> None:
    # `git -c k=v push` / `git -C dir push` must NOT bypass via the option prefix.
    _activate(tmp_path)
    assert (
        guard.evaluate("Bash", _bash("git -c user.email=x push origin main"), tmp_path).allow
        is False
    )
    assert guard.evaluate("Bash", _bash("git -C . push"), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("git --no-pager push"), tmp_path).allow is False


def test_active_blocks_stash_clear(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("git stash clear"), tmp_path).allow is False


def test_active_allows_benign_git_and_stash(tmp_path: Path) -> None:
    # Tokenizer must not false-positive on non-destructive git, even with "push" text.
    _activate(tmp_path)
    for cmd in (
        "git stash list",
        "git stash show",
        "git stash pop",
        'git commit -m "fix push bug"',
        "git log --grep=push",
    ):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


def test_active_blocks_rm_var_expansion_and_find_delete(tmp_path: Path) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash('rm -rf "$HOME"/.ssh'), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("find . -name '*.py' -delete"), tmp_path).allow is False


def test_active_blocks_bash_redirect_to_permission_surface(tmp_path: Path) -> None:
    # The settings/hooks write block must also cover Bash redirects, not just the Write tool.
    _activate(tmp_path)
    assert (
        guard.evaluate("Bash", _bash("echo '{}' > .claude/settings.json"), tmp_path).allow is False
    )
    assert (
        guard.evaluate("Bash", _bash("sed -i s/x/y/ .claude/hooks/hooks.json"), tmp_path).allow
        is False
    )


def test_active_blocks_hooks_json_write(tmp_path: Path) -> None:
    # Self-disable gap: the agent must not edit the file that registers this guard.
    _activate(tmp_path)
    for tool in ("Write", "Edit", "MultiEdit"):
        d = guard.evaluate(tool, {"file_path": ".claude/hooks/hooks.json"}, tmp_path)
        assert d.allow is False, tool


def test_active_blocks_settings_edit_all_write_tools(tmp_path: Path) -> None:
    _activate(tmp_path)
    for tool in ("Write", "Edit", "MultiEdit"):
        assert (
            guard.evaluate(tool, {"file_path": ".claude/settings.json"}, tmp_path).allow is False
        ), tool


def test_marker_off_allows_write_tools(tmp_path: Path) -> None:
    # Keystone OFF→no-op must hold for the Write side too, not just Bash.
    for tool in ("Write", "Edit", "MultiEdit"):
        assert (
            guard.evaluate(tool, {"file_path": ".claude/settings.json"}, tmp_path).allow is True
        ), tool


def test_stale_marker_ignored(tmp_path: Path) -> None:
    # A marker older than the TTL (crash leftover) must not arm the guard.
    autopilot.write(tmp_path, level="auto_safe", pipeline=_PIPE, now="2026-06-19T00:00:00+00:00")
    far_future = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    assert autopilot.active_marker(tmp_path, now=far_future) is None
    # …and the guard therefore treats the session as autopilot-OFF.
    assert guard.evaluate("Bash", _bash("git push"), tmp_path).allow is True


def test_future_dated_marker_rejected(tmp_path: Path) -> None:
    # A crafted/clock-skewed future created_at must NOT keep autopilot armed (negative
    # age would slip past a one-sided `> TTL` check) — REVIEW round-2 P2.
    autopilot.write(tmp_path, level="auto_safe", pipeline=_PIPE, now="2099-01-01T00:00:00+00:00")
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    assert autopilot.active_marker(tmp_path, now=now) is None


def test_resolve_root_finds_marker_from_worktree_subdir(tmp_path: Path) -> None:
    # P0: the hook's cwd is the worktree, the marker is at the base root. The guard
    # must walk up (and across .worktrees/) to find it, else it silently no-ops.
    autopilot.write(tmp_path, level="auto_safe", pipeline=_PIPE)
    wt = tmp_path / ".worktrees" / "execute-deadbeef-20260620T0000Z"
    wt.mkdir(parents=True, exist_ok=True)
    root = guard._resolve_root({"workspace": {"current_dir": str(wt)}})
    assert root == tmp_path
    # end-to-end: a never-auto op issued from the worktree cwd is still blocked.
    assert guard.evaluate("Bash", _bash("git push"), root).allow is False


# --- main() integration (PreToolUse exit-code contract) --------------------------


def _push_payload() -> str:
    return json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push"},
        }
    )


def test_main_blocks_with_exit_2(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _activate(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(_push_payload()))
    assert guard.main() == 2


def test_main_allows_when_marker_off(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(_push_payload()))
    assert guard.main() == 0


def test_main_blocks_write_to_settings_exit_2(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # main() must thread the Write tool path through to a block (exit 2), not just Bash.
    _activate(tmp_path)
    monkeypatch.chdir(tmp_path)
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": ".claude/settings.json"},
        }
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert guard.main() == 2
