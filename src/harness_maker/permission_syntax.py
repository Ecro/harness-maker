"""Detect permission rules Claude Code accepts but can never match."""

from __future__ import annotations

import re

# Tools whose rules take a path arg but are NOT consulted by the file-permission
# check. Claude Code accepts these and warns at startup; they enforce nothing.
# Only `Edit` and `Read` are actually matched (`Write` is covered by `Edit`).
UNMATCHED_PATH_TOOLS: frozenset[str] = frozenset({"Write", "NotebookEdit", "Glob"})

# Bash command separators. A Bash rule is matched against each subcommand AFTER
# the command is split on these, so a rule spanning one can never match — and
# unlike the path-tool case it fails SILENTLY, which is how `Bash(curl * | sh)`
# survived 39 releases.
BASH_SEPARATORS: tuple[str, ...] = ("&&", "||", "|&", ";", "|", "&", "\n")

_RULE_RE = re.compile(r"^(?P<tool>[A-Za-z_][A-Za-z0-9_]*)(?:\((?P<arg>.*)\))?$", re.DOTALL)


def unmatchable_reason(rule: str) -> str | None:
    """Why `rule` can never match, or None when it is enforceable.

    Returns prose, not a code — the callers are a health signal and a test
    assertion message, both of which are read by a human deciding what to type
    instead.
    """
    if not isinstance(rule, str) or not rule.strip():
        return "empty rule"

    m = _RULE_RE.match(rule.strip())
    if m is None:
        # Not `Tool` or `Tool(arg)`. Unknown shape — do not claim it is dead.
        return None

    tool = m.group("tool")
    arg = m.group("arg")

    # A bare `Tool` with no arg matches every use of that tool.
    if arg is None:
        return None

    if tool in UNMATCHED_PATH_TOOLS:
        return (
            f"`{tool}(...)` is accepted but never consulted by the file-permission "
            f"check — only Edit/Read are. Use `Edit({arg})` instead."
        )

    if tool == "Bash":
        for sep in BASH_SEPARATORS:
            if sep in arg:
                shown = "newline" if sep == "\n" else f"`{sep}`"
                return (
                    f"Bash rules are matched per-subcommand after splitting on "
                    f"{shown}, so a rule spanning it never matches (silently). "
                    f"Deny each command separately, or use a PreToolUse hook."
                )

    return None


def is_matchable_rule(rule: str) -> bool:
    """Whether `rule` can ever fire. See `unmatchable_reason` for the why."""
    return unmatchable_reason(rule) is None


def _wildcard_body(pattern: str) -> str:
    """`*` matches any run of characters (spaces included); everything else is literal."""
    return ".*".join(re.escape(part) for part in pattern.split("*"))


def _arg_regex(arg: str) -> re.Pattern[str]:
    """Compile a Bash rule argument to the matcher Claude Code documents.

    The load-bearing subtlety is the WORD BOUNDARY: a trailing `` *`` (and `:*`, which
    the docs define as an equivalent spelling) requires the prefix to be followed by a
    space or end-of-string, while a trailing `*` with no space does not. So
    `Bash(x -m pkg:*)` does NOT match `x -m pkg.sub …` — the next character is `.`, not
    a space — but `Bash(x -m pkg*)` does. Getting this backwards yields a rule that is
    accepted, warns about nothing, and silently matches no command.
    """
    if arg.endswith(":*"):
        arg = arg[:-2] + " *"
    if arg.endswith(" *"):
        return re.compile(f"^{_wildcard_body(arg[:-2])}(?: .*)?$", re.DOTALL)
    return re.compile(f"^{_wildcard_body(arg)}$", re.DOTALL)


def rule_matches_command(rule: str, command: str) -> bool:
    """Whether a single `Bash(...)` rule matches one already-split subcommand."""
    m = _RULE_RE.match(rule.strip())
    if m is None or m.group("tool") != "Bash":
        return False
    arg = m.group("arg")
    if arg is None:  # bare `Bash` allows everything
        return True
    return _arg_regex(arg).search(command.strip()) is not None


def split_subcommands(command: str) -> list[str]:
    """Split on the separators Claude Code splits on before matching."""
    parts = [command]
    for sep in BASH_SEPARATORS:
        parts = [piece for part in parts for piece in part.split(sep)]
    return [p.strip() for p in parts if p.strip()]


def command_allowed_by(command: str, rules: list[str]) -> bool:
    """Whether EVERY subcommand of `command` is matched by at least one rule.

    Mirrors the documented compound-command behaviour: a rule that matches the whole
    string is not enough — each subcommand is matched independently.
    """
    subs = split_subcommands(command)
    if not subs:
        return False
    return all(any(rule_matches_command(r, sub) for r in rules) for sub in subs)
