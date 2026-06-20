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
    # Non-overridable: the baseline lives in code, not config. find/publish/
    # permission-surface are regex; git AND rm are tokenized (_git_segment_hit /
    # _segment_rm_escapes — rm moved off the prefix-char regex in REVIEW P1-2).
    cats = {c for c, _ in guard.NEVER_AUTO_BASH}
    assert {"find-delete", "publish-or-deploy", "permission-surface-write"} <= cats
    # rm escape enforcement is now a tokenized operand check, not a regex category.
    assert guard._segment_rm_escapes("rm -rf /etc")


# --- REVIEW P1-2 / P2-1 / P2-2: rm-escape bypasses closed ------------------------


def test_active_blocks_rm_midtoken_traversal(tmp_path: Path) -> None:
    # P1-2: a `..` preceded by `/` (the canonical traversal inside ONE path token) slipped
    # past the old prefix-char regex. The tokenized operand check must catch every form.
    _activate(tmp_path)
    for cmd in (
        "rm -rf build/../../etc",
        "rm -rf a/b/../../../sensitive",
        "rm -rf node_modules/../../outside",
        "rm -rf ./x/../../../y",
    ):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


def test_active_allows_relative_in_worktree_rm(tmp_path: Path) -> None:
    # Relative, non-escaping rm stays allowed — block-biased ONLY on a real escape.
    _activate(tmp_path)
    for cmd in ("rm -rf node_modules", "rm -rf dist/cache", "rm foo.txt", "rm -f a/b/c"):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


def test_active_blocks_cd_escape_then_rm(tmp_path: Path) -> None:
    # P2-1: a `cd` OUT of the worktree before a (bare-relative) rm escapes the sandbox —
    # segments are independent, so cross-segment cwd tracking must poison the later rm.
    _activate(tmp_path)
    for cmd in (
        "cd / && rm -rf foo",
        "cd ~ ; rm -rf bar",
        "cd /etc && rm -rf hosts",
        "cd && rm -rf x",
    ):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


def test_active_allows_cd_within_worktree_then_rm(tmp_path: Path) -> None:
    # A relative cd stays inside the sandbox → the subsequent rm is allowed.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("cd build && rm -rf cache"), tmp_path).allow is True


def test_active_blocks_malformed_rm(tmp_path: Path) -> None:
    # An unclosed quote around rm → block-biased (a malformed rm must not slip through as
    # a false-negative the way a shlex parse failure otherwise could).
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash('rm -rf "unclosed'), tmp_path).allow is False


def test_active_blocks_cursor_codex_hooks_redirect(tmp_path: Path) -> None:
    # P2-2: the Bash permission-surface regex now matches .cursor/.codex hooks too (it was
    # asymmetric vs the Write-tool path regex, which already covered them).
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("echo x > .cursor/hooks.json"), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("echo x > .codex/hooks.json"), tmp_path).allow is False


def test_active_blocks_rm_brace_expansion(tmp_path: Path) -> None:
    # Round-2 P2: a brace list expands BEFORE the path is read, so `rm -rf {/etc,/home}`
    # must be blocked even though the literal token isn't path-shaped.
    _activate(tmp_path)
    for cmd in ("rm -rf {/etc,/home}", "rm -rf {..,foo}", "rm -rf {../sibling,x}"):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


def test_active_blocks_rm_operand_after_double_dash(tmp_path: Path) -> None:
    # Round-2 P3: the `--` end-of-options separator and disguising flags must not let an
    # escaping operand slip past _rm_operands' flag-skip.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("rm -rf -- /etc"), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("rm -rf -- ../sibling"), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("rm --no-preserve-root -rf /"), tmp_path).allow is False
    # `--` with an in-worktree relative target stays allowed.
    assert guard.evaluate("Bash", _bash("rm -rf -- node_modules"), tmp_path).allow is True


def test_active_blocks_rm_command_substitution(tmp_path: Path) -> None:
    # `$(...)` / backtick targets are statically unboundable → block-biased ($ caught).
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("rm -rf $(echo /etc)"), tmp_path).allow is False
    assert guard.evaluate("Bash", _bash("rm -rf `echo /etc`"), tmp_path).allow is False


def test_active_blocks_malformed_cd_then_rm(tmp_path: Path) -> None:
    # Round-2 P3: a malformed (unclosed-quote) cd block-biases like a malformed rm, so it
    # still poisons a later bare-relative rm rather than failing open.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash('cd "/etc && rm -rf passwd'), tmp_path).allow is False


def test_active_blocks_rm_inworktree_dotdot_overblock(tmp_path: Path) -> None:
    # Round-2 P3 (accepted over-block): ANY `..` component is treated as escape even when it
    # resolves back inside the worktree (`build/../dist`). This is the intended fail-safe
    # direction — static containment is undecidable, so block-biased.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash("rm -rf build/../dist"), tmp_path).allow is False


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


# --- P3: Stop-hook backstop (block premature termination while autopilot active) --


def test_stophook_blocks_while_active(tmp_path: Path) -> None:
    _activate(tmp_path)
    reason = guard._stophook_reason({"workspace": {"current_dir": str(tmp_path)}})
    assert reason is not None
    assert "autopilot" in reason.lower()


def test_stophook_allows_when_marker_off(tmp_path: Path) -> None:
    assert guard._stophook_reason({"workspace": {"current_dir": str(tmp_path)}}) is None


def test_stophook_respects_stop_hook_active_guard(tmp_path: Path) -> None:
    # The infinite-loop guard MUST win even when the marker is active, else exit-2
    # re-fires the Stop event forever.
    _activate(tmp_path)
    payload = {"stop_hook_active": True, "workspace": {"current_dir": str(tmp_path)}}
    assert guard._stophook_reason(payload) is None


def test_stophook_worktree_aware(tmp_path: Path) -> None:
    # Marker at base root, Stop fires with cwd = worktree subdir → must still block.
    _activate(tmp_path)
    wt = tmp_path / ".worktrees" / "execute-cafef00d-20260620T0000Z"
    wt.mkdir(parents=True, exist_ok=True)
    assert guard._stophook_reason({"workspace": {"current_dir": str(wt)}}) is not None


def test_main_stophook_mode_exit_codes(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # `--mode stop-hook`: exit 2 (block) while active, exit 0 when off.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["autopilot_guard", "--mode", "stop-hook"])
    # Explicit workspace so root resolution matches the dedicated stop-hook tests.
    payload = json.dumps({"hook_event_name": "Stop", "workspace": {"current_dir": str(tmp_path)}})
    _activate(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert guard.main() == 2
    autopilot.clear(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert guard.main() == 0


def test_main_stophook_active_guard_through_main(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # The infinite-loop guard end-to-end through main(): stop_hook_active wins over
    # an active marker → exit 0 (NOT 2), or exit-2 would re-fire Stop forever.
    _activate(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["autopilot_guard", "--mode", "stop-hook"])
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "workspace": {"current_dir": str(tmp_path)},
        }
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert guard.main() == 0


def test_main_stophook_corrupt_stdin_exits_0(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # Corrupt / non-dict stdin must fail open (exit 0), never crash-as-block.
    _activate(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["autopilot_guard", "--mode", "stop-hook"])
    monkeypatch.setattr("sys.stdin", io.StringIO("{bad json"))
    assert guard.main() == 0
    monkeypatch.setattr("sys.stdin", io.StringIO('"just a string"'))
    assert guard.main() == 0


def test_main_default_mode_is_pretooluse(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # The PreToolUse hooks.json entry passes NO --mode → default must be pretooluse
    # (a Stop-event payload has no tool_name → allow, exit 0). Documents the
    # intentional default (required=True would break the no-flag PreToolUse entry).
    _activate(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["autopilot_guard"])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"hook_event_name": "Stop"})))
    assert guard.main() == 0
