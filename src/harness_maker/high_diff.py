"""High-diff detector — gates Codex mandatory on Side preset (PLAN-crossmodel-codex-gaps ADR-003).

Reuses the `/hm:review` When-to-Run criteria: >3 files, security-sensitive paths,
contract/architecture surface, new public APIs. The numeric/path criteria are
deterministic (this module); genuinely ambiguous changes set ``boundary=True`` so the
stage LLM adjudicates (``judge_boundary_llm`` is the optional LLM hook). Python owns
the deterministic floor; the LLM owns the boundary — per CLAUDE.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_maker.llm_judge import JudgeClient

# ">3 files changed" — strictly greater than 3 is high.
HIGH_DIFF_FILE_THRESHOLD = 3
# A change this large is high regardless of path (hard signal).
LARGE_LINE_THRESHOLD = 400
# Between this and LARGE, a non-sensitive change is a boundary case for the LLM.
BOUNDARY_LINE_THRESHOLD = 100

# Substrings (case-insensitive) marking security-sensitive paths — a single touch
# here is high even at 1 line (the validator's worried case).
_SECURITY_SUBSTRINGS: tuple[str, ...] = (
    "auth",
    "secret",
    "credential",
    "password",
    "passwd",
    "token",
    "permission",
    "/perms",
    ".ssh/",
    ".aws/",
    ".env",
    "settings.json",
    "hooks.json",
    "sudoers",
)

# Substrings marking contract / architecture surface.
_CONTRACT_SUBSTRINGS: tuple[str, ...] = (
    ".schema.json",
    "schema",
    "openapi",
    ".proto",
    "/api/",
    "migration",
    "models.py",
    "harness.yaml",
)


@dataclass
class HighDiffResult:
    """Deterministic high-diff verdict plus a boundary flag for LLM adjudication."""

    is_high: bool
    boundary: bool
    reasons: list[str] = field(default_factory=list)


def _matches(path: str, substrings: tuple[str, ...]) -> bool:
    low = path.lower()
    return any(s in low for s in substrings)


def classify_paths(
    changed_files: list[str],
    *,
    added_lines: int | None = None,
) -> HighDiffResult:
    """Classify a diff from its changed paths (+ optional added-line count).

    ``boundary`` is set ONLY when no hard criterion fires but a soft signal (a
    sizable non-sensitive change) means numbers alone cannot decide.
    """
    reasons: list[str] = []

    if len(changed_files) > HIGH_DIFF_FILE_THRESHOLD:
        reasons.append(f"file count {len(changed_files)} > {HIGH_DIFF_FILE_THRESHOLD}")

    security_hits = [p for p in changed_files if _matches(p, _SECURITY_SUBSTRINGS)]
    if security_hits:
        reasons.append(f"security-sensitive path(s): {security_hits}")

    contract_hits = [p for p in changed_files if _matches(p, _CONTRACT_SUBSTRINGS)]
    if contract_hits:
        reasons.append(f"contract/architecture path(s): {contract_hits}")

    if added_lines is not None and added_lines >= LARGE_LINE_THRESHOLD:
        reasons.append(f"added lines {added_lines} >= {LARGE_LINE_THRESHOLD}")

    is_high = bool(reasons)

    boundary = False
    if not is_high and added_lines is not None and added_lines >= BOUNDARY_LINE_THRESHOLD:
        boundary = True

    return HighDiffResult(is_high=is_high, boundary=boundary, reasons=reasons)


def judge_boundary_llm(
    diff_text: str,
    *,
    client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
) -> bool:
    """LLM adjudication for a boundary diff — returns True iff high-blast-radius.

    Reuses the ``llm_judge.JudgeClient`` protocol. Kept thin so the stage can call
    it or judge inline. INTEGRATION-gated in tests (real LLM call).
    """
    from harness_maker.llm_judge import AnthropicJudgeClient

    judge_client: JudgeClient = client if client is not None else AnthropicJudgeClient()
    system = (
        "You classify a code diff as high-blast-radius or not, reusing these criteria: "
        "security/auth/permissions touched, public API or contract changed, architectural "
        "surface altered. Reply with exactly 'HIGH' or 'LOW'."
    )
    raw = judge_client.judge(system, diff_text, model)
    return "HIGH" in raw.strip().upper()


# -- CLI -----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI: ``<paths-on-stdin> | python -m harness_maker.high_diff classify [--added-lines N]``."""
    args = list(sys.argv[1:]) if argv is None else list(argv)
    parser = argparse.ArgumentParser(prog="python -m harness_maker.high_diff")
    sub = parser.add_subparsers(dest="cmd", required=True)
    classify = sub.add_parser("classify", help="classify changed paths from stdin")
    classify.add_argument("--added-lines", type=int, default=None)
    ns = parser.parse_args(args)

    if ns.cmd == "classify":
        raw = sys.stdin.read()
        changed = [line.strip() for line in raw.splitlines() if line.strip()]
        result = classify_paths(changed, added_lines=ns.added_lines)
        sys.stdout.write(
            json.dumps(
                {"is_high": result.is_high, "boundary": result.boundary, "reasons": result.reasons},
                sort_keys=True,
            )
            + "\n"
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
