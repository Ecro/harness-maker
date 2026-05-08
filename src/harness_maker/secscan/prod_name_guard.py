"""Production-name guard — environment regex + sequence pattern detection (Phase 8, ADR-008).

Detects:
1. Direct references to production environment names/paths in tool calls
2. Dangerous tool-call sequences (e.g., Read(prod.db) → Write(prod.db))
"""

from __future__ import annotations

import re
from typing import Any

from harness_maker.models import Finding

PROD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bprod(uction)?\b", re.IGNORECASE),
    re.compile(r"\bprod[-_.]?(db|database|server|api|env)\b", re.IGNORECASE),
    re.compile(r"\b(master|main)[-_.]?db\b", re.IGNORECASE),
    re.compile(r"/prod/", re.IGNORECASE),
    re.compile(r"production\.env", re.IGNORECASE),
]

DANGEROUS_SEQUENCES: list[tuple[str, str, str]] = [
    ("Read", "Write", "Read→Write on same target — potential production data modification"),
    ("Read", "Edit", "Read→Edit on same target — potential production file modification"),
    ("Read", "Delete", "Read→Delete on same target — potential production data deletion"),
]

_DEFAULT_WINDOW = 5


def scan_tool_call(
    tool_name: str,
    args: dict[str, Any],
) -> list[Finding]:
    """Check a single tool call for production name patterns."""
    findings: list[Finding] = []
    args_str = str(args)

    for pattern in PROD_PATTERNS:
        match = pattern.search(args_str)
        if match:
            findings.append(
                Finding(
                    severity="P0",
                    category="prod_name_guard",
                    file=str(args.get("path", args.get("file", ""))),
                    line=0,
                    evidence=(
                        f"Tool '{tool_name}' references production pattern "
                        f"'{match.group()}' in args: {args_str[:200]}"
                    ),
                    fix=(
                        "Verify this is not targeting a production resource. "
                        "Use a test/staging environment."
                    ),
                )
            )
    return findings


def scan_sequence(
    tool_calls: list[dict[str, Any]],
    window: int = _DEFAULT_WINDOW,
) -> list[Finding]:
    """Detect dangerous tool-call sequences within a sliding window."""
    findings: list[Finding] = []
    if len(tool_calls) < 2:
        return findings

    for i in range(len(tool_calls)):
        current = tool_calls[i]
        current_name = str(current.get("tool_name", ""))
        current_target = _extract_target(current)
        if not current_target:
            continue

        start = max(0, i - window)
        for j in range(start, i):
            prev = tool_calls[j]
            prev_name = str(prev.get("tool_name", ""))
            prev_target = _extract_target(prev)
            if not prev_target:
                continue

            if prev_target != current_target:
                continue

            for seq_first, seq_second, description in DANGEROUS_SEQUENCES:
                if prev_name == seq_first and current_name == seq_second:
                    has_prod = any(p.search(current_target) for p in PROD_PATTERNS)
                    severity = "P0" if has_prod else "P1"
                    findings.append(
                        Finding(
                            severity=severity,
                            category="prod_name_guard_sequence",
                            file=current_target,
                            line=0,
                            evidence=(
                                f"Dangerous sequence: {prev_name}({prev_target}) → "
                                f"{current_name}({current_target}). {description}"
                            ),
                            fix=(
                                "Verify this sequence is intentional and does not "
                                "target production data."
                            ),
                        )
                    )
    return findings


def _extract_target(call: dict[str, Any]) -> str:
    """Extract the primary target path/resource from a tool call."""
    args = call.get("args", {})
    if isinstance(args, dict):
        for key in ("path", "file", "target", "database", "url"):
            val = args.get(key)
            if isinstance(val, str) and val:
                return val
    return ""
