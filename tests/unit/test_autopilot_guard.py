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

import pytest

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


# --- REGRESSION: the `~/.claude/plugins/` cache path is NOT a permission surface ---------
#
# The real invocation of every harness helper is `uv run --with <plugin-path> python -m …`,
# where <plugin-path> is `~/.claude/plugins/cache/harness-maker/...`. That path contains the
# substring `.claude`, so the surface-mention backstop's OLD dir-only match classified it as
# `permission-surface-write` and blocked it. Under an active autopilot marker this bricked
# autopilot's OWN boundary/cap/receipt helpers (`autopilot_caps`, `worktree create`, …) and
# dead-locked with the Stop-hook backstop. The self-call test above missed it because it used
# a bare `uv run python …` with no `--with <plugin-path>` (CLAUDE.md checkpoint #8 blind spot).
_PLUGIN_PATH = "/home/noel/.claude/plugins/cache/harness-maker/harness-maker/0.41.0"
_HARNESS_PLUGIN_SELF_CALLS = [
    # the exact command danta ran when autopilot tried to auto-advance the plan stage
    f"cd /home/noel/danta; uv run --with {_PLUGIN_PATH} "
    "python -m harness_maker.autopilot_caps gate-blocked --root . --stage plan 2>&1; "
    'echo "exit=$?"',
    f"uv run --with {_PLUGIN_PATH} python -m harness_maker.worktree create execute .",
    "uv run --with ~/.claude/plugins/foo python -m harness_maker.x",
    "uv run pytest .claude/lib/test_foo.py",  # non-surface .claude/ subpath, no basename
    "uv run python -m harness_maker.render .claude/agents",  # dir + non-surface subdir
]


@pytest.mark.parametrize("cmd", _HARNESS_PLUGIN_SELF_CALLS)
def test_active_allows_plugin_cache_path_self_calls(tmp_path: Path, cmd: str) -> None:
    # A surface DIR substring with NO surface basename (settings.json/hooks.json) is not a
    # surface write — these must run under an active autopilot marker.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


_PLUGIN_PATH_STILL_BLOCKED = [
    # the plugin path must NOT become a bypass: a segment that ALSO writes a real surface
    # file (basename present) still blocks, whichever command carries the plugin `--with`.
    f"uv run --with {_PLUGIN_PATH} python -c x && printf y > .claude/settings.json",
    f"uv run --with {_PLUGIN_PATH} sed -i s/a/b/ .claude/settings.json",
    f"cd .claude && uv run --with {_PLUGIN_PATH} python -m x; printf y > hooks.json",
]


@pytest.mark.parametrize("cmd", _PLUGIN_PATH_STILL_BLOCKED)
def test_active_still_blocks_surface_write_alongside_plugin_path(tmp_path: Path, cmd: str) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


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
    # Non-overridable: the baseline lives in code, not config. find/publish are regex in
    # NEVER_AUTO_BASH; git, rm, AND the permission-surface are tokenized checks run ahead
    # of it in _bash_hit (_git_segment_hit / _segment_rm_escapes / _permission_surface_write).
    cats = {c for c, _ in guard.NEVER_AUTO_BASH}
    assert {"find-delete", "publish-or-deploy"} <= cats
    # rm escape enforcement is a tokenized operand check, not a regex category.
    assert guard._segment_rm_escapes("rm -rf /etc")
    # permission-surface enforcement is a read-only ALLOWLIST (REVIEW P0 #2), not a
    # write-verb regex category — it no longer lives in NEVER_AUTO_BASH.
    assert "permission-surface-write" not in cats
    assert guard._permission_surface_write("echo x > .claude/settings.json")


# --- REVIEW Phase 3+4 P0 #2: permission-surface is a read-only ALLOWLIST -----------
#
# The Phase-2 rule required a write TOKEN before the path. That fixed a false positive
# (blocking `cat settings.json`) but opened false NEGATIVES: any interpreter/verb NOT in
# the token blacklist mutated the file freely. Phase 3 makes this rule LIVE on PreToolUse
# for the first time, so the leak became a newly-reachable privilege escalation. The fix
# inverts the strategy — block ANY segment naming the surface unless it matches a closed
# read-only allowlist and the surface is not a redirect target.

_SURFACE_WRITE_BYPASSES = [
    "python -c \"open('.claude/settings.json','w').write('{}')\"",
    "perl -i -pe 's/deny/allow/' .claude/settings.json",
    "git checkout HEAD -- .claude/settings.json",
    "git restore .claude/settings.json",
    "install /dev/null .claude/settings.json",
    "printf '{}' | ex -sc 'wq' .claude/settings.json",
]


@pytest.mark.parametrize("cmd", _SURFACE_WRITE_BYPASSES)
def test_active_blocks_permission_surface_write_bypasses(tmp_path: Path, cmd: str) -> None:
    # Each of the six commands the Phase-2 write-token rule ALLOWED must now be blocked.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


# --- REVIEW P0 (path identity): literal-substring bypasses of the surface rule ---------
#
# The read-only allowlist got the VERB axis right, but the rule only fired when a fixed
# regex found the CONTIGUOUS substring `.claude/settings.json` in the raw command text.
# Bash has many equivalent spellings of that path the literal missed; for each, the guard
# returned "not a surface command" and ALLOWED the write to the file holding both
# `permissions` and the `hooks` gating them. The fix RESOLVES the write target (cwd-tracked,
# normalized) instead of matching text. All five must now be BLOCKED.

_SURFACE_PATH_IDENTITY_BYPASSES = [
    "cd .claude && printf '{}' > settings.json",  # bare basename after an unresolved cd
    "printf '{}' > .claude//settings.json",  # // breaks the literal
    "printf '{}' > .claude/./settings.json",  # /./ breaks the literal
    "printf '{}' > .claude/'settings.json'",  # a quote mid-path breaks the literal
    "git -C .claude checkout HEAD -- settings.json",  # -C sets dir; path is a split token
]


@pytest.mark.parametrize("cmd", _SURFACE_PATH_IDENTITY_BYPASSES)
def test_active_blocks_surface_path_identity_bypasses(tmp_path: Path, cmd: str) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


def test_active_blocks_surface_cwd_and_basename_variants(tmp_path: Path) -> None:
    # The cwd-tracking + basename resolution must cover every surface, not just settings.json.
    _activate(tmp_path)
    for cmd in (
        "cd .claude && printf '{}' > settings.local.json",
        "cd .claude/hooks && printf '{}' > hooks.json",
        "cd .cursor && printf '{}' > hooks.json",
        "cd .codex && printf '{}' > hooks.json",
    ):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


_NON_SURFACE_SETTINGS_WRITES = [
    "printf '{}' > .vscode/settings.json",  # a different tool's config, not our surface
    "printf '{}' > config/settings.json",
    "printf '{}' > ./settings.json",  # a bare settings.json at the worktree root
    "cd build && printf '{}' > settings.json",  # resolves to build/settings.json
]


@pytest.mark.parametrize("cmd", _NON_SURFACE_SETTINGS_WRITES)
def test_active_allows_non_surface_settings_writes(tmp_path: Path, cmd: str) -> None:
    # False-positive guard: a settings.json NOT under .claude/.cursor/.codex is a different
    # tool's file. Resolving path identity (vs substring-matching the basename) lets these
    # through — the surface-directory ancestor is what distinguishes ours from theirs.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


def test_active_blocks_dotdot_laden_cd_then_surface_write(tmp_path: Path) -> None:
    # REVIEW P0 re-probe: `cd .claude/../.claude` folds lexically back to `.claude`, so the
    # later bare `settings.json` writes the surface. `PurePosixPath` does not collapse `..`
    # on its own — the cd-target normalizer must, or the tracker discards it as an escape
    # and the write slips through.
    _activate(tmp_path)
    assert (
        guard.evaluate(
            "Bash", _bash("cd .claude/../.claude && printf x > settings.json"), tmp_path
        ).allow
        is False
    )


def test_active_blocks_uncertain_cd_then_bare_config_write(tmp_path: Path) -> None:
    # Block-biased fallback: when the cd target is unresolvable ($-expansion, ~, absolute,
    # command substitution), a later write to a bare config basename MIGHT land on .claude/,
    # so it is blocked rather than allowed. Closes the class, not just one spelling.
    _activate(tmp_path)
    for cmd in (
        "cd $SOMEDIR && printf x > settings.json",
        'cd "$HOME/proj" && printf x > settings.local.json',
        "cd $(pwd) && printf x > hooks.json",
        "cd ~ && printf x > settings.json",
    ):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


def test_active_allows_uncertain_cd_then_nonconfig_write(tmp_path: Path) -> None:
    # The uncertain-cwd block-bias is scoped to config basenames — an unresolvable cd
    # followed by a plain-file write is NOT a surface write and stays allowed.
    _activate(tmp_path)
    for cmd in ("cd $SOMEDIR && printf x > out.txt", "cd ~ && printf x > notes.md"):
        assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


def test_active_allows_dotdot_cd_staying_in_worktree_nonsurface(tmp_path: Path) -> None:
    # A `..` that folds to a concrete NON-surface dir stays allowed — `build/../dist` == `dist`.
    _activate(tmp_path)
    assert (
        guard.evaluate(
            "Bash", _bash("cd build/../dist && printf x > settings.json"), tmp_path
        ).allow
        is True
    )


def test_permission_surface_write_resolves_cwd(tmp_path: Path) -> None:
    # Direct unit check of the resolver: a bare basename with a .claude cwd is a surface
    # write; the same basename at the root (cwd ".") is not.
    from pathlib import PurePosixPath

    assert guard._permission_surface_write("printf '{}' > settings.json", PurePosixPath(".claude"))
    assert not guard._permission_surface_write("printf '{}' > settings.json", PurePosixPath("."))


# --- REVIEW P0 (whack-a-mole close): general surface-mention backstop -------------------
#
# A textual guard over bash can always be out-spelled by one more path form. Rather than
# enumerate each, a general backstop blocks any NON-read segment that still names a surface
# DIRECTORY (`.claude`/`.cursor`/`.codex` as a substring of any token). These four classes
# each evaded the precise resolver but all spell the surface dir in the segment.

_SURFACE_MENTION_BYPASSES = [
    "pushd .claude && printf x > settings.json",  # pushd/popd dir stack untracked
    "CDPATH=.claude cd hooks && printf x > hooks.json",  # CDPATH search-path resolution
    "env CDPATH=.claude cd hooks && printf x > hooks.json",  # env-prefixed CDPATH
    "git --work-tree=.claude checkout HEAD -- settings.json",  # --work-tree, not -C
    "git -C . -C .claude checkout HEAD -- settings.json",  # second -C ignored by resolver
    "git --git-dir=.claude/x checkout HEAD -- settings.json",  # --git-dir
    "exec {fd}>.claude//settings.json",  # dynamic-FD redirect
    "exec 3<>.claude//settings.json && printf x >&3",  # <> read-write redirect
    "{ printf x; } > .claude//settings.json",  # brace-group redirect
]


@pytest.mark.parametrize("cmd", _SURFACE_MENTION_BYPASSES)
def test_active_blocks_surface_mention_backstop(tmp_path: Path, cmd: str) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


_SURFACE_BACKSTOP_ALLOWS = [
    "cat .claude/settings.json",  # clean read
    "jq . .claude/settings.json",
    "grep foo .claude/settings.json",
    "git diff",  # no surface reference at all
    "git log -p .claude/settings.json",  # read-only git subcommand
    "cat .claude/settings.json > /tmp/backup",  # surface is the redirect SOURCE
    "printf x > .vscode/settings.json",  # a different tool's file (no .claude dir)
    "cd build/../dist && printf x > settings.json",  # resolves to dist/, concrete non-surface
    "cd $VAR && printf x > out.txt",  # uncertain cwd but non-config write
]


@pytest.mark.parametrize("cmd", _SURFACE_BACKSTOP_ALLOWS)
def test_active_backstop_keeps_clean_reads_and_non_surface_allowed(
    tmp_path: Path, cmd: str
) -> None:
    # The backstop must NOT reintroduce the false positives the precise logic correctly
    # allows — clean reads of the surface, and non-surface writes.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


# --- REVIEW P0 (final): command-substitution masking of the clean-read exception ---------
#
# A read-only LEADING command (`cat`) classifies the whole segment as a clean read, masking
# a write hidden INSIDE a `$(...)` / backtick substitution. Since we cannot prove the
# substituted command is read-only, a surface mention inside a segment carrying `$(`/backtick
# voids the clean-read exception → block-biased.

_SURFACE_CMDSUBST_BYPASSES = [
    "cat $(truncate -s 0 .claude/settings.json) </dev/null",  # write masked by leading cat
    "echo $(printf x > .claude/settings.json)",  # redirect-into-surface inside $()
    "grep foo $(tee .claude/settings.json)",  # tee write inside $()
    "cat `sed -i s/a/b/ .claude/settings.json`",  # backtick form
    "cat $(ls .claude/settings.json)",  # technically a read, but block-biased (contrived)
]


@pytest.mark.parametrize("cmd", _SURFACE_CMDSUBST_BYPASSES)
def test_active_blocks_surface_in_command_substitution(tmp_path: Path, cmd: str) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


_SURFACE_CMDSUBST_ALLOWS = [
    "cat .claude/settings.json",  # no substitution → clean read
    "jq . .claude/settings.json",
    "grep foo .claude/settings.json",
    "git diff",
    "cat .claude/settings.json > /tmp/backup",  # surface is the redirect SOURCE
    "echo $(date) > /tmp/x",  # substitution WITHOUT a surface mention → allowed
]


@pytest.mark.parametrize("cmd", _SURFACE_CMDSUBST_ALLOWS)
def test_active_cmdsubst_keeps_clean_reads_allowed(tmp_path: Path, cmd: str) -> None:
    # A substitution with no surface mention, and reads without substitution, stay allowed.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


def test_active_blocks_noclobber_override_redirect(tmp_path: Path) -> None:
    # REVIEW P1: `>|` (bash noclobber override) split at the pipe, separating the redirect
    # token from the surface path so neither segment matched. Normalizing `>|`→`>` before
    # the segment split keeps the redirect target visible to the surface check.
    _activate(tmp_path)
    assert (
        guard.evaluate("Bash", _bash("echo '{}' >| .claude/settings.json"), tmp_path).allow is False
    )


_SURFACE_READS = [
    "cat .claude/settings.json",
    "head -n 5 .claude/settings.json",
    "tail -f .claude/settings.json",
    "grep deny .claude/settings.json",
    "jq . .claude/settings.json",
    "git diff .claude/settings.json",
    "git log -p .claude/settings.json",
    "cat .claude/settings.json > /tmp/backup",  # surface is the redirect SOURCE, not target
]


@pytest.mark.parametrize("cmd", _SURFACE_READS)
def test_active_allows_permission_surface_reads(tmp_path: Path, cmd: str) -> None:
    # The read-only allowlist must stay green — the Phase-2 false positive (blocking a
    # `cat`) is exactly what the inverted rule must NOT reintroduce.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


# --- REVIEW P0 (final): `less` write-flag + write-output-flag backstop -------------------
#
# `less -o`/`-O <file>` writes its output, so `less` is removed from the read-only allowlist
# entirely (it is the only member with a write flag, and nobody needs it in an autonomous
# chain). A write-capable output flag near any allowlisted command also voids the clean-read
# exception, belt-and-suspenders against a future allowlist member with such a flag.

_SURFACE_WRITE_FLAG_BLOCKS = [
    "less -O .claude/settings.json /etc/hosts",  # -O writes the surface
    "less -o .claude/settings.json x",  # -o writes the surface
    "grep --output=.claude/settings.json foo",  # defensive: --output near a surface
    "less .claude/settings.json",  # plain less now blocks too (deliberate conservative)
]


@pytest.mark.parametrize("cmd", _SURFACE_WRITE_FLAG_BLOCKS)
def test_active_blocks_write_flag_near_surface(tmp_path: Path, cmd: str) -> None:
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is False, cmd


_SURFACE_NONWRITE_FLAG_ALLOWS = [
    "head -20 .claude/settings.json",  # numeric flag, not a write flag
    "tail -5 .claude/settings.json",
    "grep -n deny .claude/settings.json",  # -n line-number, not in-place
]


@pytest.mark.parametrize("cmd", _SURFACE_NONWRITE_FLAG_ALLOWS)
def test_active_allows_nonwrite_flag_reads(tmp_path: Path, cmd: str) -> None:
    # Read-only flags (`-20`/`-5`/`-n`) must NOT trip the write-output-flag void.
    _activate(tmp_path)
    assert guard.evaluate("Bash", _bash(cmd), tmp_path).allow is True, cmd


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
