"""Permissions gate — flag over-broad ``permissions.allow`` entries in settings.json."""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import Finding

# Catch-all entries — high severity (effectively unrestricted).
_CATCH_ALL = {
    "Bash(*)",
    "Bash(*:*)",
    "Write(*)",
    "Write(**)",
    "Read(*)",
    "Edit(*)",
    "*",
}

# Broad path patterns — medium severity (wildcards over filesystem roots).
# Only flag root-anchored or universal globs — relative subdir patterns
# like ``./src/**`` are considered scoped and clean.
_BROAD_PATH_TOKENS = ("(/**", "(/*", "(**/*")


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def scan(settings_json: Path) -> list[Finding]:
    """Return findings for over-broad ``permissions.allow`` entries."""
    findings: list[Finding] = []
    if not settings_json.exists():
        return findings
    try:
        body = _strip_frontmatter(settings_json.read_text(encoding="utf-8"))
        data = json.loads(body)
    except (OSError, json.JSONDecodeError):
        return findings
    if not isinstance(data, dict):
        return findings
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return findings
    allow = perms.get("allow")
    if not isinstance(allow, list):
        return findings

    rel = settings_json.name
    for entry in allow:
        if not isinstance(entry, str):
            continue
        if entry in _CATCH_ALL:
            findings.append(
                Finding(
                    severity="high",
                    category="permissions",
                    file=rel,
                    line=0,
                    evidence=f"catch-all permission: {entry!r}",
                    fix=f"Replace {entry!r} with narrow tool-specific patterns "
                    "(e.g., Bash(uv:*), Read(./src/**)).",
                ),
            )
            continue
        if any(token in entry for token in _BROAD_PATH_TOKENS):
            findings.append(
                Finding(
                    severity="medium",
                    category="permissions",
                    file=rel,
                    line=0,
                    evidence=f"broad path pattern: {entry!r}",
                    fix=f"Restrict {entry!r} to a specific directory under the project.",
                ),
            )
    return findings
