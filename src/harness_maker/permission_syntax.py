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
