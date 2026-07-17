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
Permission-surface writes are matched by RESOLVING the write target's path identity
(cwd-tracked, normalized), not by a literal substring, so equivalent spellings of the
same file cannot slip past; a general backstop then blocks ANY non-read segment that still
names a surface directory, closing the path-spelling class as a whole rather than one
spelling at a time (REVIEW P0 — see `_resolved_surface_write` + `_surface_mention_backstop`).
The only residual is a write that never spells the surface path in the segment at all
(reached by a script/binary, a runtime-assembled path, or a symlink) — unclosable by a
textual guard; the worktree sandbox is the real boundary there.
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
# The permission-surface protection is ALSO not a regex in this list anymore — it is
# `_permission_surface_write` (a read-only ALLOWLIST, not a write-verb blacklist), run
# ahead of this list in `_bash_hit`. See its docstring for why (REVIEW Phase 3+4 P0 #2).
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
]

# The IDE permission-surface paths — settings, this guard's own hooks.json, and the
# Cursor/Codex hook files. `.claude/hooks/hooks.json` is dead in Claude Code but still
# rendered and still live in Cursor/Codex, so it stays covered.
_SURFACE_PATH = (
    r"(?:\.claude/(?:settings(?:\.local)?\.json|hooks/hooks\.json)"
    r"|\.cursor/hooks\.json|\.codex/hooks\.json)"
)
_SURFACE_RE = re.compile(_SURFACE_PATH + r"\b")
# A redirection whose TARGET is the surface (`> surface`, `2>> surface`, `>|` after the
# `>|`→`>` normalization in `_bash_hit`). A redirect INTO the surface is a write no
# matter the leading command, so it is judged a write even for a read-only command word.
_SURFACE_REDIR_TARGET = re.compile(r"\d*>>?\s*['\"]?" + _SURFACE_PATH + r"\b")

# The CLOSED read-only command allowlist. A Bash segment that NAMES the permission
# surface is blocked UNLESS its leading command is one of these (and the surface is not
# a redirect target). WHY an allowlist, not a write-verb blacklist (REVIEW P0 #2): a
# blacklist is unbounded — `python -c open(...,'w')`, `perl -i`, `install`, `ex -sc wq`,
# `git checkout/restore`, `tee`, `dd`, `truncate`, … all mutate. A read set is small,
# closed, and safe to enumerate. `less` was REMOVED (REVIEW P0 final): it is the only
# would-be member with a write option (`less -o`/`-O <file>` writes its output), and it is
# not needed in an autonomous chain — so plain `less .claude/settings.json` now blocks too
# (a deliberate conservative choice: reading via `less` in autopilot is not worth the risk).
_SURFACE_READ_ONLY = frozenset({"cat", "head", "tail", "grep", "jq"})
_SURFACE_READ_ONLY_GIT = frozenset({"diff", "log"})
_ENV_ASSIGN = re.compile(r"^\w+=")
# Write-capable output flags. If a segment mentioning a surface carries one of these (near
# an otherwise-read-only command), the clean-read exception is voided — belt-and-suspenders
# against a future allowlist addition (or `less`-style flag) that can write via a flag.
_WRITE_OUTPUT_FLAGS = frozenset({"-o", "-O", "-i", "--output", "--in-place"})

# Path-identity surface matching (REVIEW P0 — literal-substring bypasses). The literal
# `_SURFACE_RE` above fires only on a contiguous `.claude/settings.json` in the raw text,
# which many equivalent bash spellings evade (`.claude//settings.json`, `.claude/./…`, a
# quoted `.claude/'settings.json'`, a bare `settings.json` after `cd .claude`, or
# `git -C .claude checkout -- settings.json`). `_resolved_surface_write` normalizes the
# actual write target and matches these distinctive basenames when the resolved path
# carries an IDE surface directory anywhere in it. A `settings.json` OUTSIDE those dirs
# (e.g. `.vscode/settings.json`) is a different tool's file and stays allowed.
_SURFACE_BASENAMES = frozenset({"settings.json", "settings.local.json", "hooks.json"})
_SURFACE_DIRS = frozenset({".claude", ".cursor", ".codex"})
# The tracked shell cwd starts at the worktree root. A module-level singleton so it can be
# the (immutable) default for `_permission_surface_write` without a B008 call-in-default.
_WORKTREE_ROOT = PurePosixPath(".")
# A leading redirect operator on a shell token: `>`, `>>`, `2>`, `&>`, `1>>`, … (`>|` is
# already normalized to `>` in `_bash_hit` before the segment split).
_REDIR_OP_RE = re.compile(r"^(?:[0-9]+|&)?>>?")

# Write/Edit/MultiEdit targeting the permission surface — an active autopilot must not
# edit these. Anchored `$` (whole file_path), unlike the Bash `\b` variant.
NEVER_AUTO_WRITE_PATH = re.compile(_SURFACE_PATH + r"$")

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


def _segment_is_read_only_surface_cmd(segment: str) -> bool:
    """True when a segment's LEADING command is in the closed read-only allowlist.

    Skips leading `VAR=val` env-assignments, resolves a `/usr/bin/cat`-style path to its
    basename, and for `git` walks past global option prefixes (`-c k=v`, `-C dir`) to the
    subcommand. A malformed (unclosed-quote) segment returns False — block-biased, the
    same safe direction as the rm/cd checks."""
    tokens, malformed = _tokenize_segment(segment)
    if malformed:
        return False
    idx = 0
    while idx < len(tokens) and _ENV_ASSIGN.match(tokens[idx]):
        idx += 1
    if idx >= len(tokens):
        return False
    base = tokens[idx].rsplit("/", 1)[-1]
    if base in _SURFACE_READ_ONLY:
        return True
    if base == "git":
        rest = tokens[idx + 1 :]
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            opt = rest[j]
            j += 1
            if opt in _GIT_VALUE_OPTS and j < len(rest) and not rest[j].startswith("-"):
                j += 1
        return j < len(rest) and rest[j] in _SURFACE_READ_ONLY_GIT
    return False


def _resolve_surface_candidate(token: str, cwd: PurePosixPath | None) -> PurePosixPath | None:
    """Normalize a write-target token to a path, resolved against the tracked cwd.

    `PurePosixPath` collapses `//` and `/./` for free; shlex already stripped quotes (the
    extra `.strip` is belt-and-braces). An absolute token stands alone; a relative token
    joins the tracked cwd, or — when the cwd is unknown (escaped by an untrackable `cd`) —
    is returned as-is so `_is_surface_path` still catches a token that itself spells a
    surface dir. Returns None only for an empty token."""
    token = token.strip("'\"")
    if not token:
        return None
    p = PurePosixPath(token)
    if p.is_absolute() or cwd is None:
        return p
    return cwd / p


def _is_surface_path(path: PurePosixPath) -> bool:
    """True when a normalized path names an IDE permission surface.

    Block-biased: a distinctive basename (`settings.json` / `settings.local.json` /
    `hooks.json`) whose path carries a `.claude` / `.cursor` / `.codex` component ANYWHERE
    (covers relative, cwd-joined, and absolute spellings, plus nested over-approximations
    like `.claude/settings.json` and `.claude/hooks/hooks.json`). A matching basename with
    NO surface directory (e.g. `.vscode/settings.json`, `config/settings.json`) is
    deliberately NOT a surface — it is another tool's file."""
    if path.name not in _SURFACE_BASENAMES:
        return False
    return any(part in _SURFACE_DIRS for part in path.parts)


def _redirect_targets(tokens: list[str]) -> list[str]:
    """File targets of every output redirect in a segment. `>&2` / `2>&1` fd-duplications
    (remainder starts with `&`) are excluded — they name a descriptor, not a file."""
    targets: list[str] = []
    i = 0
    while i < len(tokens):
        m = _REDIR_OP_RE.match(tokens[i])
        if m:
            rest = tokens[i][m.end() :]
            if rest.startswith("&"):
                i += 1
                continue
            if rest:
                targets.append(rest)
            elif i + 1 < len(tokens):
                targets.append(tokens[i + 1])
                i += 1
        i += 1
    return targets


def _command_operands(tokens: list[str]) -> list[str]:
    """Non-flag, non-redirect operand tokens of a segment. Over-inclusive by design
    (block-biased): keeps the command word and flag values too, which simply will not
    resolve to a surface path. A standalone redirect op and its following target token are
    dropped (targets are judged separately by `_redirect_targets`)."""
    ops: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        m = _REDIR_OP_RE.match(tok)
        if m:
            i += 2 if not tok[m.end() :] else 1  # skip op (+ its target token if standalone)
            continue
        if not tok.startswith("-"):
            ops.append(tok)
        i += 1
    return ops


def _normalize_relparts(parts: tuple[str, ...]) -> list[str] | None:
    """Lexically collapse `.` and `..` in a relative path's parts. `PurePosixPath` does NOT
    fold `..` on its own (it can't, without touching the filesystem), so a purely lexical
    fold is done here: a `..` pops the last kept segment; a `..` at the tracked root escapes
    above it and returns None (a real cwd-escape). `cd .claude/../.claude` therefore folds
    back to `.claude` rather than being discarded as an escape (REVIEW P0 re-probe)."""
    out: list[str] = []
    for part in parts:
        if part in (".", ""):
            continue
        if part == "..":
            if not out:
                return None  # escapes above the tracked worktree root
            out.pop()
        else:
            out.append(part)
    return out


def _join_cwd(cwd: PurePosixPath | None, directory: str) -> PurePosixPath | None:
    """Join a `-C`/`cd` directory onto the tracked cwd, folding `.`/`..` lexically.

    Returns None (an UNCERTAIN cwd) when the target cannot be resolved to a concrete
    relative dir — an absolute path, a `~` home path, a `$`/backtick expansion, or a `..`
    that escapes above the tracked root. An uncertain cwd is block-biased downstream: a
    later write to a bare config basename with no directory is treated as a surface write
    (`_resolved_surface_write`), since the write MIGHT land on `.claude/`."""
    directory = directory.strip("'\"")
    if not directory:
        return cwd
    if "~" in directory or "$" in directory or "`" in directory:
        return None
    p = PurePosixPath(directory)
    if p.is_absolute() or cwd is None:
        return None
    norm = _normalize_relparts(cwd.parts + p.parts)
    if norm is None:
        return None
    return PurePosixPath(*norm) if norm else PurePosixPath(".")


def _is_bare_config_basename(token: str) -> bool:
    """True when a token is JUST a permission-surface basename with no directory component
    (`settings.json`, `settings.local.json`, `hooks.json`, optionally `./`-prefixed). Under
    an UNCERTAIN cwd this is treated as a surface write (block-biased) — the file it lands
    on cannot be resolved, so it might be `.claude/settings.json`."""
    token = token.strip("'\"")
    p = PurePosixPath(token)
    return not p.is_absolute() and len(p.parts) == 1 and p.name in _SURFACE_BASENAMES


def _segment_git_dir(tokens: list[str], base_cwd: PurePosixPath | None) -> PurePosixPath | None:
    """Effective operand-resolution cwd for a segment carrying `git -C <dir>` (or a bare
    `-C <dir>` / `--directory <dir>` / `-C<dir>` / `--directory=<dir>`). Unchanged when no
    directory override is present."""
    for i, tok in enumerate(tokens):
        directory: str | None = None
        if tok in ("-C", "--directory") and i + 1 < len(tokens):
            directory = tokens[i + 1]
        elif tok.startswith("--directory="):
            directory = tok.split("=", 1)[1]
        elif tok.startswith("-C") and len(tok) > 2:
            directory = tok[2:]
        if directory is not None:
            return _join_cwd(base_cwd, directory)
    return base_cwd


def _updated_surface_cwd(segment: str, cwd: PurePosixPath | None) -> PurePosixPath | None:
    """Tracked cwd AFTER a `cd` in this segment (else unchanged). None when the `cd`
    escapes trackable relative space (bare `cd`→$HOME, `cd -`, absolute, `~`, `..`)."""
    tokens, _malformed = _tokenize_segment(segment)
    # Untrackable cwd mutations → UNCERTAIN (None): `pushd`/`popd` maintain a dir stack this
    # tracker does not model, and a `CDPATH=` assignment makes a "relative" `cd` resolve
    # against a search path we cannot see. Either poisons a later bare-config-basename write
    # into the block-biased uncertain path (REVIEW P0 re-probe: pushd/CDPATH bypasses).
    if any(t in ("pushd", "popd") or t.startswith("CDPATH=") for t in tokens):
        return None
    for i, tok in enumerate(tokens):
        if tok != "cd":
            continue
        operands = [o for o in tokens[i + 1 :] if not o.startswith("-")]
        if not operands:
            return None  # bare `cd` → $HOME (untrackable)
        return _join_cwd(cwd, operands[0])
    return cwd


def _literal_surface_write(segment: str) -> bool:
    """The read-only-allowlist rule over the LITERAL path substring (REVIEW Phase 3+4 P0
    #2). Kept because it catches a surface path spelled INSIDE a command-string argument
    where no shell token IS the path — `python -c "open('.claude/settings.json','w')"`,
    `perl -i … .claude/settings.json`, `ex -sc wq …` — which path resolution cannot reach.
    A segment naming the surface is a write UNLESS its leading command is read-only AND the
    surface is not a redirect target."""
    if not _SURFACE_RE.search(segment):
        return False
    if _SURFACE_REDIR_TARGET.search(segment):
        return True
    return not _segment_is_read_only_surface_cmd(segment)


def _resolved_surface_write(segment: str, cwd: PurePosixPath | None) -> bool:
    """The path-identity rule (REVIEW P0): resolve the segment's actual write target(s)
    and block when one lands on a permission surface, so equivalent spellings the literal
    substring misses cannot slip past — `.claude//settings.json`, `.claude/./settings.json`,
    a quoted `.claude/'settings.json'`, a bare `settings.json` after `cd .claude`, or
    `git -C .claude checkout -- settings.json`.

    A write indicator is (1) a redirect whose target resolves to the surface — a write for
    ANY leading command, `echo x > surface` truncates it — or (2) a path-like operand of a
    NON-read-only command that resolves to the surface (`sed -i … surface`,
    `git checkout -- surface`). A read-only leading command (cat/grep/jq/git diff …) with
    the surface only as a read operand or a redirect SOURCE stays allowed.

    An UNCERTAIN cwd (`cwd is None` — an earlier `cd`/`git -C`/`pushd`/`CDPATH=` that could
    not be folded to a concrete relative dir: `$`-expansion, command substitution, `~`,
    absolute, or a `..` escaping the tracked root) is block-biased: a write to a bare config
    basename with no directory is treated as a surface write, since it MIGHT land on
    `.claude/`. A residual spelling this resolver misses is caught by the general
    `_surface_mention_backstop` (any token naming a surface DIR in a non-read segment)."""
    tokens, malformed = _tokenize_segment(segment)
    if not tokens:
        return False
    if malformed:
        # Boundaries are unreliable — block-bias only if the raw text carries both a
        # surface basename and a surface dir (the literal rule handles the contiguous case).
        return any(b in segment for b in _SURFACE_BASENAMES) and any(
            d in segment for d in _SURFACE_DIRS
        )
    # (1) redirect targets — resolved against the shell cwd, independent of the command.
    for target in _redirect_targets(tokens):
        if cwd is None and _is_bare_config_basename(target):
            return True  # uncertain cwd + bare config write → block-biased
        resolved = _resolve_surface_candidate(target, cwd)
        if resolved is not None and _is_surface_path(resolved):
            return True
    # A read-only leading command with the surface only as a read operand → allowed.
    if _segment_is_read_only_surface_cmd(segment):
        return False
    # (2) operands of a non-read-only command — resolved against a `git -C`-adjusted cwd.
    seg_cwd = _segment_git_dir(tokens, cwd)
    for operand in _command_operands(tokens):
        if seg_cwd is None and _is_bare_config_basename(operand):
            return True  # uncertain cwd + bare config operand → block-biased
        resolved = _resolve_surface_candidate(operand, seg_cwd)
        if resolved is not None and _is_surface_path(resolved):
            return True
    return False


def _surface_mention_backstop(segment: str) -> bool:
    """General block-biased backstop that ends the path-SPELLING whack-a-mole (REVIEW P0).

    The precise rules above (literal substring, resolved path, uncertain-cwd) each close a
    finite set of spellings, but a textual guard over bash can always be out-spelled by one
    more form — `pushd`/`popd`, a `CDPATH=` search path, `git --work-tree=`/`--git-dir=`, a
    second `-C`, a dynamic-FD `exec {fd}>…` or `<>` read-write redirect, a `{ …; } > …`
    brace-group redirect. They ALL share one property: the surface DIRECTORY is still
    spelled somewhere in the segment. So block any segment that names a surface dir
    (`.claude`/`.cursor`/`.codex` as a substring of ANY token) UNLESS it is a clean read —
    a read-only-allowlisted command (cat/grep/jq/git diff/log) whose surface reference is
    NOT a redirect target. This is the conceptual boundary, not another enumerated spelling.

    A command substitution `$(…)` / `` `…` `` that mentions the surface voids the clean-read
    exception: a read-only LEADING command can hide an arbitrary write inside the
    substitution (`cat $(truncate -s 0 .claude/settings.json)`), and we cannot cheaply prove
    the substituted command is itself read-only, so a surface mention anywhere in a segment
    carrying `$(`/backtick is block-biased — even a contrived `cat $(ls .claude/settings.json)`
    that is technically a read (blocking that is acceptable, and safer).

    A write-capable output flag (`-o`/`-O`/`--output`/`-i`/`--in-place`) near a surface also
    voids the exception (belt-and-suspenders should a future allowlist member write via a
    flag, as `less -o` does). Accepted over-block: `grep -i foo .claude/settings.json`
    (case-insensitive read) is blocked because `-i` collides with in-place — safe direction.

    TRUE RESIDUAL (out of scope, and unclosable by any textual guard): a write where the
    surface path is NOT spelled in the segment at all — reached only by indirection. A
    helper script or binary that writes the file, a variable / base64-decoded path assembled
    at runtime, or symlink redirection. Nothing in the argv names the surface, so no static
    inspection can see it. The worktree sandbox is the real boundary there."""
    tokens, _malformed = _tokenize_segment(segment)
    if not any(any(d in tok for d in _SURFACE_DIRS) for tok in tokens):
        return False
    # A surface named inside a command substitution can mask a write behind a read-only
    # leading command — the clean-read exception is void when `$(`/backtick is present.
    if "$(" in segment or "`" in segment:
        return True
    # A write-capable output flag near a surface also voids the clean-read exception.
    if any(tok.split("=", 1)[0] in _WRITE_OUTPUT_FLAGS for tok in tokens):
        return True
    # Otherwise a clean read (read-only-allowlisted command, surface not a redirect target)
    # is not a write; any other segment that still names a surface dir is blocked.
    is_clean_read = _segment_is_read_only_surface_cmd(segment) and not _SURFACE_REDIR_TARGET.search(
        segment
    )
    return not is_clean_read


def _permission_surface_write(segment: str, cwd: PurePosixPath | None = _WORKTREE_ROOT) -> bool:
    """True when a segment WRITES an IDE permission surface (the file holding both
    `permissions` and the `hooks` gating them). Three block-biased OR branches: the literal
    substring rule (`_literal_surface_write`, catches a path embedded in a code-string arg),
    the path-identity rule (`_resolved_surface_write`, catches equivalent path spellings),
    and the general `_surface_mention_backstop` (blocks any non-read segment that still names
    a surface DIRECTORY, closing every path-spelling class at once).

    `cwd` is the tracked relative shell cwd for cross-segment `cd` resolution (see
    `_bash_hit`). It defaults to the worktree root when unpassed; a passed `None` is a
    distinct signal — an UNCERTAIN cwd (untrackable earlier `cd`) — which
    `_resolved_surface_write` block-biases. The default is immutable (`PurePosixPath`)."""
    return (
        _literal_surface_write(segment)
        or _resolved_surface_write(segment, cwd)
        or _surface_mention_backstop(segment)
    )


def _bash_hit(command: str, extra_deny: list[str]) -> str | None:
    """Return the matched category, or None when the command is allowed.

    Segments are scanned in order so a `cd` escaping the worktree poisons later `rm`
    segments (cross-segment cwd tracking — REVIEW P2-1)."""
    # `>|` (bash noclobber override) → `>` BEFORE the segment split, else the split on
    # `|` separates the redirect token from its target path and the surface check on
    # each half misses both (REVIEW P1). Every other redirect form already stays in one
    # segment. `2>|`, `>|` both collapse to a plain redirect the surface check sees.
    command = command.replace(">|", ">")
    cwd_escaped = False
    # Tracked relative shell cwd (worktree-root = ".") so a `cd .claude` in one segment
    # lets a later bare `settings.json` resolve to the surface (REVIEW P0 path identity).
    # Distinct from `cwd_escaped`, which is the worktree-escape signal for the rm checks.
    surface_cwd: PurePosixPath | None = _WORKTREE_ROOT
    for segment in _SEGMENT_SPLIT.split(command):
        git_hit = _git_segment_hit(segment)
        if git_hit is not None:
            return git_hit
        if _segment_rm_escapes(segment):
            return "rm-escapes-worktree"
        if cwd_escaped and _rm_operands(_tokenize_segment(segment)[0]):
            return "rm-after-cd-escape"
        if _permission_surface_write(segment, surface_cwd):
            return "permission-surface-write"
        for category, pattern in NEVER_AUTO_BASH:
            if pattern.search(segment):
                return category
        if _segment_is_cd_escape(segment):
            cwd_escaped = True
        surface_cwd = _updated_surface_cwd(segment, surface_cwd)
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
                "Remove the `.claude/.hm-autopilot` marker to run this manually."
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
    execute, while the marker lives at the base repo root. This is the payload→Path
    adapter; the worktree-stripping + sentinel resolution itself lives in the shared
    `autopilot.resolve_marker_root` so the hook, the CLI, and the marker read/write/
    clear ops all resolve identically (ADR-003, validator W1).
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
    return autopilot.resolve_marker_root(start)


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
        "Remove the `.claude/.hm-autopilot` marker to end the autopilot session."
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
