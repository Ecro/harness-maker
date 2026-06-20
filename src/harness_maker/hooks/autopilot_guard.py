"""autopilot_guard PreToolUse hook — block never-auto ops WHILE autopilot is active.

ADR-003 (P4-impl refinement, user-confirmed): the never-auto list is code-fixed and
non-overridable, but it fires ONLY when the `.hm-autopilot` marker is active. With
autopilot OFF (the default) this hook is a no-op, so a solo user's manual `git push`
/ `rm` is never blocked — the footgun a static session-wide settings.json deny would
have created. The list exists *because auto-advance removes the human*, so it is gated
on exactly that condition. `autonomy.extra_deny` may ADD patterns, never subtract.
Claude-Code only (ADR-004): PermissionRequest (Codex) is allowed through.

Defense-in-depth, not the sole boundary (the worktree sandbox + host-IDE auto-mode are
the real ones). It is deliberately block-biased while autopilot is active — a
false-positive merely pauses the chain for the human; a false-negative ships an
irreversible op. git detection is word-tokenized (not adjacency-regex) so option
prefixes like `git -c k=v push` / `git -C dir push` cannot slip past (REVIEW P1).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from harness_maker import autopilot

# Non-git never-auto Bash patterns (category, regex), matched per command-segment.
# NOTE: `rm` escaping the worktree is NOT a regex here — a prefix-char regex missed
# mid-token traversal like `rm -rf build/../../etc` (REVIEW P1-2). It is now a
# shlex-tokenized operand check (`_segment_rm_escapes`), with cross-segment cd-tracking
# for `cd /abs && rm …` (REVIEW P2-1), both run ahead of this list in `_bash_hit`.
NEVER_AUTO_BASH: list[tuple[str, re.Pattern[str]]] = [
    ("find-delete", re.compile(r"\bfind\b[^\n]*-delete\b")),
    (
        "publish-or-deploy",
        re.compile(
            r"\b(?:npm\s+publish|uv\s+publish|poetry\s+publish|twine\s+upload"
            r"|gh\s+release\s+create|docker\s+push|helm\s+upgrade"
            r"|aws\s+s3\s+(?:cp|sync|rm)|gcloud\s+(?:deploy|run\s+deploy)"
            r"|terraform\s+(?:destroy|apply)|pulumi\s+(?:destroy|up)|kubectl\s+delete)\b"
        ),
    ),
    # A Bash write/redirect to ANY IDE's permission surface — the agent must not
    # `echo > .claude/settings.json` or rewrite a hooks.json to disable this guard. The
    # path set MUST match NEVER_AUTO_WRITE_PATH (Write-tool) — both cover .cursor/.codex
    # hooks, not just .claude (REVIEW P2-2: the two were asymmetric).
    (
        "permission-surface-write",
        re.compile(
            r"(?:\.claude/(?:settings(?:\.local)?\.json|hooks/hooks\.json)"
            r"|\.cursor/hooks\.json|\.codex/hooks\.json)\b"
        ),
    ),
]

# Write/Edit/MultiEdit targeting the permission surface — settings, this guard's own
# hooks.json, and the Cursor/Codex hook files. An active autopilot must not edit these.
NEVER_AUTO_WRITE_PATH = re.compile(
    r"(?:\.claude/(?:settings(?:\.local)?\.json|hooks/hooks\.json)"
    r"|\.cursor/hooks\.json|\.codex/hooks\.json)$"
)

# git options that consume the FOLLOWING token as their value (so the tokenizer must
# skip both when scanning for the subcommand): `git -c k=v push`, `git -C dir push`.
_GIT_VALUE_OPTS = frozenset({"-c", "-C", "--namespace", "--git-dir", "--work-tree", "--exec-path"})

_BASH = "Bash"
_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})
_SEGMENT_SPLIT = re.compile(r"[;&|\n]+")
_MARKER_REL = ".claude/.hm-autopilot"
_KNOWN_HOOK_EVENTS = frozenset(
    {"PreToolUse", "PostToolUse", "PreCompact", "Stop", "PermissionRequest"}
)


@dataclass(frozen=True)
class GateDecision:
    """Pure outcome — main() converts to exit code + stderr."""

    allow: bool
    matched: str  # category id, "" when allowed
    message: str


def _git_segment_hit(segment: str) -> str | None:
    """Word-tokenize one command segment; block destructive git subcommands.

    Tolerates global option prefixes (`-c k=v`, `-C dir`, `--no-pager`) between `git`
    and the subcommand so they cannot be used to bypass the adjacency check.
    """
    try:
        tokens = shlex.split(segment)
    except ValueError:
        # Malformed shell (unclosed quote). Fall back to a coarse whitespace split,
        # NOT `return None`: a `git push "unclosed` would then slip through as a
        # false-NEGATIVE bypass — the dangerous direction for a security guard. The
        # coarse split is block-biased (it may over-block a malformed-but-benign
        # command), which is the safe direction: a malformed command issued under
        # active autopilot is worth pausing for the human anyway (REVIEW round-2).
        tokens = segment.split()
    for i, tok in enumerate(tokens):
        if tok != "git" and not tok.endswith("/git"):
            continue
        rest = tokens[i + 1 :]
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            opt = rest[j]
            j += 1
            if opt in _GIT_VALUE_OPTS and j < len(rest) and not rest[j].startswith("-"):
                j += 1  # skip the option's value token
        if j >= len(rest):
            return None
        sub = rest[j]
        tail = rest[j:]
        if sub == "push":
            return "git-push"
        if sub == "reset" and "--hard" in tail:
            return "git-reset-hard"
        if sub == "stash" and len(tail) > 1 and tail[1] in ("drop", "clear"):
            return "git-stash-destroy"
        return None
    return None


def _extra_deny(project_dir: Path) -> list[str]:
    """Best-effort read of harness.yaml ``autonomy.extra_deny`` (additive substrings)."""
    path = project_dir / ".claude" / "harness.yaml"
    if not path.is_file():
        return []
    with contextlib.suppress(Exception):
        from harness_maker.io_utils import load_harness_yaml

        data = load_harness_yaml(path)
        if isinstance(data, dict):
            raw = data.get("autonomy", {})
            if isinstance(raw, dict):
                deny = raw.get("extra_deny", [])
                if isinstance(deny, list):
                    return [d for d in deny if isinstance(d, str) and d.strip()]
    return []


def _tokenize_segment(segment: str) -> tuple[list[str], bool]:
    """(tokens, malformed). On an unclosed quote, fall back to a coarse whitespace split
    and flag malformed — the caller block-biases a malformed rm rather than letting it
    slip through (same safe direction as `_git_segment_hit`)."""
    try:
        return shlex.split(segment), False
    except ValueError:
        return segment.split(), True


def _operand_escapes_worktree(operand: str) -> bool:
    """True when a path operand resolves OUTSIDE the worktree sandbox.

    Catches the canonical traversal forms the old prefix-char regex missed (REVIEW P1-2):
    an absolute path, a `~` home path, ANY `..` component (incl. mid-token
    `build/../../etc`), a `$`-expansion, or a `{a,b}` brace list — the last three cannot
    be statically bounded (bash expands `rm -rf {/etc,foo}` to multiple operands BEFORE
    the path is read — REVIEW P2). All are treated as escape (block-biased: a
    false-positive merely pauses the chain for the human).
    """
    if "$" in operand or operand.startswith("~"):
        return True
    if "{" in operand and "}" in operand and "," in operand:
        return True
    pure = PurePosixPath(operand)
    return pure.is_absolute() or any(part == ".." for part in pure.parts)


def _rm_operands(tokens: list[str]) -> list[str]:
    """Non-flag operands of every `rm` invocation in one tokenized segment."""
    operands: list[str] = []
    for i, tok in enumerate(tokens):
        if tok != "rm" and not tok.endswith("/rm"):
            continue
        operands.extend(op for op in tokens[i + 1 :] if op != "--" and not op.startswith("-"))
    return operands


def _segment_rm_escapes(segment: str) -> bool:
    """True when a segment's `rm` targets a path outside the worktree (or is malformed)."""
    tokens, malformed = _tokenize_segment(segment)
    has_rm = any(t == "rm" or t.endswith("/rm") for t in tokens)
    if malformed and has_rm:
        return True  # block-biased: an unparseable rm under autopilot is worth a pause
    return any(_operand_escapes_worktree(op) for op in _rm_operands(tokens))


def _segment_is_cd_escape(segment: str) -> bool:
    """True when a `cd` moves cwd OUTSIDE the worktree (absolute/home/`..`/bare/`-`).

    A later `rm` in the same command then operates on an escaped cwd even with a bare
    relative target, so `_bash_hit` poisons subsequent rm segments (REVIEW P2-1).
    """
    tokens, malformed = _tokenize_segment(segment)
    # Block-bias parity with `_segment_rm_escapes` (REVIEW P3): a malformed (unclosed-quote)
    # cd conservatively poisons subsequent rm segments rather than silently failing open.
    if malformed and any(t == "cd" for t in tokens):
        return True
    for i, tok in enumerate(tokens):
        if tok != "cd":
            continue
        operands = [o for o in tokens[i + 1 :] if not o.startswith("-")]
        if not operands or operands[0] == "-":
            return True  # bare `cd` → $HOME; `cd -` → previous (unbounded) dir
        return _operand_escapes_worktree(operands[0])
    return False


def _bash_hit(command: str, extra_deny: list[str]) -> str | None:
    """Return the matched category, or None when the command is allowed.

    Segments are scanned in order so a `cd` escaping the worktree poisons later `rm`
    segments (cross-segment cwd tracking — REVIEW P2-1)."""
    cwd_escaped = False
    for segment in _SEGMENT_SPLIT.split(command):
        git_hit = _git_segment_hit(segment)
        if git_hit is not None:
            return git_hit
        if _segment_rm_escapes(segment):
            return "rm-escapes-worktree"
        if cwd_escaped and _rm_operands(_tokenize_segment(segment)[0]):
            return "rm-after-cd-escape"
        for category, pattern in NEVER_AUTO_BASH:
            if pattern.search(segment):
                return category
        if _segment_is_cd_escape(segment):
            cwd_escaped = True
    low = command.lower()
    for extra in extra_deny:
        if extra.lower() in low:
            return f"extra_deny:{extra}"
    return None


def evaluate(tool_name: str, tool_input: dict[str, Any], project_dir: Path) -> GateDecision:
    """Allow everything unless autopilot is active AND the call is never-auto."""
    if autopilot.active_marker(project_dir) is None:
        return GateDecision(allow=True, matched="", message="")
    if tool_name == _BASH:
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return GateDecision(allow=True, matched="", message="")
        hit = _bash_hit(command, _extra_deny(project_dir))
        if hit is None:
            return GateDecision(allow=True, matched="", message="")
        return GateDecision(
            allow=False,
            matched=hit,
            message=(
                f"[autopilot] blocked never-auto op ({hit}) while autopilot is active. "
                "Turn autopilot off (`harness-maker autopilot off`) to run this manually."
            ),
        )
    if tool_name in _WRITE_TOOLS:
        path = tool_input.get("file_path")
        if isinstance(path, str) and NEVER_AUTO_WRITE_PATH.search(path):
            return GateDecision(
                allow=False,
                matched="permission-surface-edit",
                message="[autopilot] blocked permission-surface edit while autopilot active",
            )
    return GateDecision(allow=True, matched="", message="")


def _resolve_root(payload: dict[str, Any]) -> Path:
    """Resolve the project root the autopilot marker lives at — worktree-aware.

    The hook subprocess's cwd is often a `.worktrees/<wt>/` dir during an autonomous
    execute, while the marker lives at the base repo root. Mirror worktree_gate's
    payload-first resolution (workspace.current_dir / cwd / env) and THEN walk up for
    the marker (handling the `.worktrees/` parent) so the guard is not a silent no-op
    in exactly the mode it guards (REVIEW P0).
    """
    raw_ws = payload.get("workspace")
    ws: dict[str, Any] = raw_ws if isinstance(raw_ws, dict) else {}
    start = Path(
        ws.get("current_dir")
        or payload.get("cwd")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CURSOR_PROJECT_DIR")
        or os.getcwd()
    )
    for directory in [start, *start.parents]:
        if (directory / _MARKER_REL).exists():
            return directory
        parts = directory.parts
        if ".worktrees" in parts:
            idx = len(parts) - 1 - parts[::-1].index(".worktrees")
            if idx > 0:
                base = Path(*parts[:idx])
                if (base / _MARKER_REL).exists():
                    return base
    return start


def _stophook_reason(payload: dict[str, Any]) -> str | None:
    """Stop-hook backstop (P3): return a block reason while autopilot is active, else None.

    Prevents the session from terminating mid-pipeline when prompt-driven Skill chaining
    (P6) hasn't finished — the marker is cleared only when the pipeline completes. The
    `stop_hook_active` guard MUST be checked FIRST: omitting it makes the exit-2 re-fire
    the Stop event forever (same contract as loop_gate). Worktree-aware via `_resolve_root`.
    """
    if payload.get("stop_hook_active"):
        return None
    if autopilot.active_marker(_resolve_root(payload)) is None:
        return None
    # Descriptive, NOT imperative: the prompt-driven chainer (P6) is what actually
    # advances stages; until it lands, a "continue to the next stage" command would be
    # a false imperative the agent cannot fulfil. The backstop's only job is "don't
    # stop yet while a pipeline is in flight" (REVIEW P3 round-1).
    return (
        "[autopilot] pipeline in progress — not terminating. "
        "Run `harness-maker autopilot off` to end the autopilot session."
    )


def _pretooluse(payload: dict[str, Any]) -> int:
    """PreToolUse: exit 0 (allow) / 2 (block) + stderr. PermissionRequest (Codex):
    always exit 0 — autopilot is a Claude-Code feature (ADR-004)."""
    hook_event = str(payload.get("hook_event_name") or "")
    if hook_event == "PermissionRequest":
        return 0
    if hook_event and hook_event not in _KNOWN_HOOK_EVENTS:
        return 0
    tool_name = str(payload.get("tool_name") or "")
    raw_input = payload.get("tool_input")
    tool_input = raw_input if isinstance(raw_input, dict) else {}
    decision = evaluate(tool_name, tool_input, _resolve_root(payload))
    if decision.message:
        print(decision.message, file=sys.stderr)
    return 0 if decision.allow else 2


def main() -> int:
    """Dispatch on ``--mode`` (default pretooluse). stop-hook = the P3 backstop."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", default="pretooluse", choices=["pretooluse", "stop-hook"])
    args, _unknown = parser.parse_known_args()
    try:
        # isatty guard (mirror loop_gate): a bare TTY invocation must not block on
        # read() waiting for EOF — only Claude's non-TTY hook stdin carries a payload.
        text = "" if sys.stdin.isatty() else sys.stdin.read()
        payload: Any = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    if args.mode == "stop-hook":
        reason = _stophook_reason(payload)
        if reason is None:
            return 0
        print(json.dumps({"decision": "block", "reason": reason}))
        return 2
    return _pretooluse(payload)


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess in tests
    sys.exit(main())
