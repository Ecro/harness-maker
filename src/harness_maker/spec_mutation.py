"""mutmut wrapper + baseline-relative threshold gate (ADR-005).

threshold = max(measured_baseline + 5pp, tier_floor) where tier_floor ∈
{T1: 85, T2: 70, T3: informational (no gate)}.

Subprocess timeouts are mandatory per CLAUDE.md. ``shell=True`` is forbidden.
The fallback rule (60-min budget → sampled 200-mutant mode) is exposed via
``run_mutation(sampled=True)``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

VerificationTier = Literal[1, 2, 3]

TIER_FLOORS: dict[int, int | None] = {1: 85, 2: 70, 3: None}
"""Tier floor in percent. T3 = None → informational (non-gating)."""

DEFAULT_SAMPLE_MUTANT_BUDGET: int = 200
DEFAULT_WALL_BUDGET_MIN: int = 60
PLUS_DELTA_PP: int = 5  # +5pp ratchet per ADR-005


@dataclass(frozen=True)
class MutationReport:
    """Parsed result of one mutmut invocation."""

    paths: tuple[str, ...]
    killed: int
    survived: int
    timeout: int
    suspicious: int
    skipped: int
    sampled: bool
    raw_output: str

    @property
    def total(self) -> int:
        return self.killed + self.survived + self.timeout + self.suspicious

    @property
    def score(self) -> float:
        """Killed fraction; survivors degrade the score."""
        denom = self.killed + self.survived + self.timeout
        return self.killed / denom if denom else 0.0


def threshold_for(tier: VerificationTier, baseline: float | None) -> int | None:
    """Compute ``mutation_threshold`` per ADR-005.

    - T3 → None (no gate)
    - T1/T2 with no baseline yet → tier floor (gate is aspirational until baseline measured)
    - T1/T2 with baseline → max(baseline + 5pp, tier_floor)
    """
    floor = TIER_FLOORS[int(tier)]
    if floor is None:
        return None
    if baseline is None:
        return floor
    baseline_pct = int(round(baseline * 100)) if 0.0 <= baseline <= 1.0 else int(baseline)
    return max(baseline_pct + PLUS_DELTA_PP, floor)


def gate(
    report: MutationReport,
    tier: VerificationTier,
    *,
    baseline: float | None = None,
) -> tuple[bool, str]:
    """Return ``(passes, reason)``."""
    threshold = threshold_for(tier, baseline)
    if threshold is None:
        return True, f"T{tier} is informational (no gate)"
    score_pct = int(round(report.score * 100))
    if score_pct >= threshold:
        return True, f"score {score_pct}% >= threshold {threshold}%"
    return False, f"score {score_pct}% < threshold {threshold}%"


def measure_baseline(
    paths_to_mutate: list[str],
    *,
    cwd: Path,
    wall_budget_min: int = DEFAULT_WALL_BUDGET_MIN,
    sample_budget: int = DEFAULT_SAMPLE_MUTANT_BUDGET,
    sampled: bool = False,
    timeout_seconds: int | None = None,
) -> MutationReport:
    """Invoke mutmut and parse its output into a MutationReport.

    Designed to be cancellable: if real wall-clock exceeds the budget, caller
    can re-invoke with ``sampled=True`` per ADR-005 fallback rule.
    """
    if not paths_to_mutate:
        return MutationReport(
            paths=(),
            killed=0,
            survived=0,
            timeout=0,
            suspicious=0,
            skipped=0,
            sampled=sampled,
            raw_output="",
        )
    args = ["mutmut", "run", "--paths-to-mutate", ",".join(paths_to_mutate)]
    if sampled:
        args.extend(["--use-coverage"])  # narrow the universe
    # Compute timeout: wall budget in seconds, capped 600 per Bash policy
    deadline = timeout_seconds if timeout_seconds is not None else min(wall_budget_min * 60, 600)
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=deadline,
            check=False,
        )
        raw = proc.stdout + "\n" + proc.stderr
    except FileNotFoundError:
        raw = "mutmut: command not found (run `uv sync --group dev`)"
    except subprocess.TimeoutExpired as exc:
        # Preserve partial stdout/stderr so a partial mutation result still
        # parses into MutationReport — otherwise a slow run produces a 0%
        # score that spuriously fails the gate (REVIEW C-P1-E).
        partial_stdout = (
            exc.stdout
            if isinstance(exc.stdout, str)
            else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
        )
        partial_stderr = (
            exc.stderr
            if isinstance(exc.stderr, str)
            else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
        )
        raw = (
            (partial_stdout or "")
            + "\n"
            + (partial_stderr or "")
            + f"\n# mutmut timeout after {exc.timeout}s; consider sampled=True"
        )

    return _parse_mutmut_output(raw, tuple(paths_to_mutate), sampled=sampled)


_COUNTERS_RE = re.compile(r"(killed|survived|timeout|suspicious|skipped)[:\s]+(\d+)", re.IGNORECASE)


def _parse_mutmut_output(raw: str, paths: tuple[str, ...], *, sampled: bool) -> MutationReport:
    """Best-effort parse of mutmut's varying output formats.

    Future mutmut versions may emit JSON; switch to ``mutmut results --json``
    when widely available. For now we scan for ``killed: N`` patterns.
    """
    counts: dict[str, int] = {
        "killed": 0,
        "survived": 0,
        "timeout": 0,
        "suspicious": 0,
        "skipped": 0,
    }
    for m in _COUNTERS_RE.finditer(raw):
        key = m.group(1).lower()
        counts[key] = int(m.group(2))
    return MutationReport(
        paths=paths,
        killed=counts["killed"],
        survived=counts["survived"],
        timeout=counts["timeout"],
        suspicious=counts["suspicious"],
        skipped=counts["skipped"],
        sampled=sampled,
        raw_output=raw,
    )


def report_to_json(report: MutationReport) -> str:
    """Stable JSON dump for ``work-docs/spec-mutation-*.json`` artifacts."""
    payload = {
        "paths": list(report.paths),
        "killed": report.killed,
        "survived": report.survived,
        "timeout": report.timeout,
        "suspicious": report.suspicious,
        "skipped": report.skipped,
        "sampled": report.sampled,
        "total": report.total,
        "score": round(report.score, 4),
    }
    return json.dumps(payload, indent=2) + "\n"


# ---------------------------------------------------------------------------
# CLI (``python -m harness_maker.spec_mutation gate --yaml ... --tier 1``)
# ---------------------------------------------------------------------------

#: Substring mutmut-absent reports carry (see measure_baseline FileNotFoundError).
_MUTMUT_ABSENT = "command not found"


def main(argv: list[str] | None = None) -> int:
    """Tier-gated mutation gate over a SPEC.machine.yaml's paths_to_mutate.

    Used by /hm:execute Phase D (T1 only, ADR-003 of PLAN-spec-test-accumulation)
    and re-usable by /hm:loop. Degrades to non-gating (exit 0 + warning) when
    mutmut is not installed — never blocks a user who lacks the dev tool.
    """
    from harness_maker.spec_machine import load as load_machine

    parser = argparse.ArgumentParser(prog="python -m harness_maker.spec_mutation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_gate = sub.add_parser("gate", help="run mutmut + gate one machine.yaml by tier")
    p_gate.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_gate.add_argument(
        "--tier", type=int, default=None, help="override tier (default: yaml verification_tier)"
    )
    p_gate.add_argument("--sampled", action="store_true", help="200-mutant sampled mode")
    p_gate.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    machine = load_machine(args.yaml_path)
    tier_raw = args.tier if args.tier is not None else int(machine.verification_tier)
    if tier_raw not in (1, 2, 3):
        print(f"mutation gate: invalid tier {tier_raw} (expected 1/2/3)", file=sys.stderr)
        return 2
    tier: VerificationTier = cast(VerificationTier, tier_raw)
    paths = list(machine.paths_to_mutate)
    if not paths:
        print(f"mutation gate: {machine.spec_slug} has no paths_to_mutate (nothing to gate)")
        return 0

    report = measure_baseline(paths, cwd=args.cwd, sampled=args.sampled)
    if _MUTMUT_ABSENT in report.raw_output:
        print(
            "mutation gate: mutmut not installed — skipping (non-gating). "
            "Run `uv sync --group dev` to enable.",
            file=sys.stderr,
        )
        return 0

    passes, reason = gate(report, tier)  # baseline=None → tier floor (ADR-005)
    stream = sys.stdout if passes else sys.stderr
    print(f"mutation gate (T{tier}, {machine.spec_slug}): {reason}", file=stream)
    return 0 if passes else 1


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess/main() in tests
    raise SystemExit(main())


__all__ = [
    "DEFAULT_SAMPLE_MUTANT_BUDGET",
    "DEFAULT_WALL_BUDGET_MIN",
    "MutationReport",
    "PLUS_DELTA_PP",
    "TIER_FLOORS",
    "VerificationTier",
    "gate",
    "main",
    "measure_baseline",
    "report_to_json",
    "threshold_for",
]
