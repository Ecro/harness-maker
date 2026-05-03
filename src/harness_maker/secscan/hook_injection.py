"""Hook injection gate — flag dangerous shell patterns in hooks.json commands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harness_maker.models import Finding

_DANGER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rm_rf", re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b")),
    ("curl_pipe_sh", re.compile(r"\bcurl\b[^\n|]*\|\s*(?:sh|bash|zsh|sudo\s+sh|sudo\s+bash)\b")),
    ("wget_pipe_sh", re.compile(r"\bwget\b[^\n|]*\|\s*(?:sh|bash|zsh|sudo\s+sh|sudo\s+bash)\b")),
    ("eval_call", re.compile(r"\beval\s+")),
    ("dd_destruct", re.compile(r"\bdd\s+if=.*\s+of=/dev/(?:sd[a-z]|nvme|disk)")),
    ("nc_reverse", re.compile(r"\bnc(?:at)?\b[^\n]*-e\s+(?:/bin/)?(?:sh|bash)")),
]


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def _walk_commands(node: Any) -> list[str]:
    """Collect all string fields named 'command' (or top-level command strings)."""
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "command" and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_walk_commands(v))
    elif isinstance(node, list):
        for item in node:
            out.extend(_walk_commands(item))
    return out


def scan(hooks_json: Path) -> list[Finding]:
    """Return findings for dangerous shell patterns in hook commands."""
    findings: list[Finding] = []
    if not hooks_json.exists():
        return findings
    try:
        body = _strip_frontmatter(hooks_json.read_text(encoding="utf-8"))
        data = json.loads(body)
    except (OSError, json.JSONDecodeError):
        return findings

    commands = _walk_commands(data)
    rel = hooks_json.name
    for cmd in commands:
        for category, pattern in _DANGER_PATTERNS:
            if pattern.search(cmd):
                findings.append(
                    Finding(
                        severity="high",
                        category="hook_injection",
                        file=rel,
                        line=0,
                        evidence=f"{category}: {cmd[:200]}",
                        fix=f"Replace dangerous {category!r} pattern with a safer "
                        "scoped alternative; pin URLs and avoid pipe-to-shell.",
                    ),
                )
    return findings
