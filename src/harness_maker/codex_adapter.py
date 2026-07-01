"""Codex-finding -> reviewer-finding adapter (PLAN-crossmodel-codex-gaps ADR-001 / Phase 4a).

Normalizes a Codex finding (``codex-finding.schema.json`` shape) into the reviewer-finding
shape the ``/hm:review`` Step 4 consensus filter consumes, so Codex can be a real k-of-3
voter. Two normalizations are load-bearing (both flagged by plan-validator):
- **severity vocabulary** — Codex ``info/low/medium/high/critical`` -> reviewer ``P0..P3``,
  else Step 4a's "same severity tier" predicate rejects every Codex finding.
- **null location** — when ``file``/``line`` is null, set ``needs_relaxation`` so the Step 4
  filter applies the symbol/message-similarity surface-match fallback (prose half, P4b).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from harness_maker import command_registry

# critical->P0, high->P1, medium->P2, low/info->P3 (ADR-001, validator pass-2 critical).
_SEVERITY_TO_PTIER: dict[str, str] = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
    "info": "P3",
}


def map_codex_severity(codex_severity: str) -> str:
    """Map a Codex severity enum value to a reviewer P-tier."""
    key = codex_severity.strip().lower()
    try:
        return _SEVERITY_TO_PTIER[key]
    except KeyError:
        raise ValueError(f"unknown codex severity: {codex_severity!r}") from None


def adapt_codex_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Adapt one Codex finding into a reviewer-shaped finding for the Step 4 filter.

    ``needs_relaxation`` is True when ``file`` or ``line`` is null — the signal for the
    consensus filter to fall back to symbol/message-similarity for surface-match
    candidacy (Codex findings often omit a precise location).
    """
    file = finding.get("file")
    line = finding.get("line")
    message = finding.get("message", "")
    return {
        "severity": map_codex_severity(finding["severity"]),
        "file": file,
        "line": line,
        "summary": message,
        "evidence": finding.get("evidence"),
        "source": "codex",
        "needs_relaxation": file is None or line is None,
    }


def adapt_finding_list(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Adapt a Codex output payload (``{findings:[...]}`` or a bare list) into reviewer findings."""
    findings = payload.get("findings", []) if isinstance(payload, dict) else payload
    return [adapt_codex_finding(f) for f in findings]


# -- CLI -----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m harness_maker.codex_adapter adapt`` — reads the Codex output JSON on
    stdin (the ``--output-last-message`` file) and writes the adapted reviewer-finding list.

    Reading from stdin/file (not an inlined shell arg) keeps untrusted Codex content out of
    the shell, and makes the severity map + null-location flag actually deterministic rather
    than LLM-applied prose (REVIEW round 3, finding C)."""
    _guard = command_registry.guard_or_none("codex_adapter", argv)
    if _guard is not None:
        return _guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args or args[0] != "adapt":
        sys.stderr.write("usage: python -m harness_maker.codex_adapter adapt < codex-output.json\n")
        return 2
    raw = sys.stdin.read()
    if not raw.strip():
        sys.stderr.write("adapt: stdin is empty\n")
        return 1
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"adapt: stdin is not valid JSON: {exc}\n")
        return 1
    try:
        adapted = adapt_finding_list(payload)
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        sys.stderr.write(f"adapt: malformed codex finding: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(adapted, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
