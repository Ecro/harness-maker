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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from harness_maker.io_utils import atomic_write

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
# Equivalent-mutant classifier (ADR-004, audited no-shrink denominator)
#
# Only a documented closed set of rules may exclude a survivor from the
# kill-rate denominator. Unknown survivors default to pending-review and STAY
# in the denominator — coverage cannot improve by relabeling. ``real-not-killed``
# is never produced by a rule; it is a human/caller override only.
# ---------------------------------------------------------------------------

Classification = Literal["equivalent", "real-not-killed", "pending-review"]


@dataclass(frozen=True)
class MutantDescriptor:
    """Minimal mutant view a rule matcher inspects (synthetic-friendly)."""

    mutant_id: str
    source_line: str
    context: str = ""


@dataclass(frozen=True)
class EquivalenceRule:
    """A documented reason a survivor is provably an equivalent mutant."""

    rule_id: str
    description: str
    matcher: Callable[[MutantDescriptor], bool]


@dataclass(frozen=True)
class ClassifiedMutant:
    """Per-mutant verdict, JSON-serializable for baseline persistence."""

    mutant_id: str
    classification: Classification
    rule_id: str | None


@dataclass(frozen=True)
class AdjustedScore:
    """Kill rate after excluding ONLY rule-equivalent survivors.

    ``excluded_equivalent`` is surfaced next to the score so a shrinking
    denominator is always visible, never hidden.
    """

    killed: int
    denominator: int
    excluded_equivalent: int
    score: float


@dataclass(frozen=True)
class GrowthVerdict:
    """Anti-loophole guard: did the rule-excluded set grow between runs?"""

    grew: bool
    added: tuple[str, ...]
    severity: Literal["ok", "warn", "fail"]


# ``cast("Literal", x)`` / ``typing.cast('T', x)`` — first arg is a string
# literal that is a type-checker-only no-op at runtime, so mutating it cannot
# change behavior. We require the FIRST argument to be a quoted string.
_CAST_STRING_RE = re.compile(
    r"""(?:^|[^.\w])(?:typing\.)?cast\(\s*['"]""",
)
# An integer default like ``data.get(k, 1)`` whose value is later subtracted
# from ``time.time()`` (~1.7e9) — an off-by-small-int is numerically
# indistinguishable in the elapsed computation.
_INT_DEFAULT_RE = re.compile(r"\.get\([^,]+,\s*\d+\s*\)")
_TIME_SUB_RE = re.compile(r"time\.time\(\)\s*-|-\s*time\.time\(\)")


def _matches_cast_string_noop(d: MutantDescriptor) -> bool:
    # The mutation is to the cast's string arg, so the cast MUST be on the
    # mutated source_line — an unrelated cast() in surrounding context must not
    # exclude a real survivor (REVIEW consensus P2 / Codex-high over-match).
    # Residual accepted limitation: a user helper literally named cast() taking a
    # string first arg also matches; bounded + growth-guarded + count-surfaced.
    return bool(_CAST_STRING_RE.search(d.source_line))


def _matches_int_default_near_time(d: MutantDescriptor) -> bool:
    # The mutated default (.get(k, N)) MUST be on the source_line; only the
    # time.time() subtraction *usage* may live in nearby context. Requiring the
    # default on the mutated line removes the "unrelated .get in context"
    # false-exclusion (REVIEW consensus P2).
    if not _INT_DEFAULT_RE.search(d.source_line):
        return False
    blob = d.source_line + "\n" + d.context
    return bool(_TIME_SUB_RE.search(blob))


EQUIVALENCE_RULES: tuple[EquivalenceRule, ...] = (
    EquivalenceRule(
        rule_id="typing-cast-string-noop",
        description=(
            "Mutation to the first (string) argument of typing.cast(...) — "
            "type-checker-only, runtime no-op."
        ),
        matcher=_matches_cast_string_noop,
    ),
    EquivalenceRule(
        rule_id="int-default-near-time",
        description=(
            "Integer default (data.get(k, N)) later subtracted from time.time() "
            "(~1.7e9) — numerically indistinguishable."
        ),
        matcher=_matches_int_default_near_time,
    ),
)


def classify_survivor(descriptor: MutantDescriptor) -> tuple[Classification, str | None]:
    """Return ``("equivalent", rule_id)`` only on a documented rule match.

    Never returns ``real-not-killed`` — that label is a human/caller override.
    Unknown survivors fall through to ``pending-review`` (kept in denominator).
    """
    for rule in EQUIVALENCE_RULES:
        if rule.matcher(descriptor):
            return "equivalent", rule.rule_id
    return "pending-review", None


def classify_survivors(descriptors: Sequence[MutantDescriptor]) -> list[ClassifiedMutant]:
    """Classify a batch, preserving per-mutant identity for persistence."""
    out: list[ClassifiedMutant] = []
    for d in descriptors:
        classification, rule_id = classify_survivor(d)
        out.append(
            ClassifiedMutant(mutant_id=d.mutant_id, classification=classification, rule_id=rule_id)
        )
    return out


def _excluded_ids(classified: Sequence[ClassifiedMutant]) -> set[str]:
    """Mutant ids excluded from the denominator — ONLY rule-equivalent ones."""
    return {c.mutant_id for c in classified if c.classification == "equivalent" and c.rule_id}


def adjusted_score(report: MutationReport, survivors: Sequence[MutantDescriptor]) -> AdjustedScore:
    """Kill rate excluding ONLY rule-equivalent survivors (count surfaced).

    ``pending-review`` / ``real-not-killed`` survivors stay in the denominator,
    so coverage cannot be inflated by relabeling.
    """
    classified = classify_survivors(survivors)
    excluded = len(_excluded_ids(classified))
    raw_denom = report.killed + report.survived + report.timeout
    denom = raw_denom - excluded
    score = report.killed / denom if denom > 0 else 0.0
    return AdjustedScore(
        killed=report.killed,
        denominator=denom,
        excluded_equivalent=excluded,
        score=score,
    )


def baseline_to_json(classified: Sequence[ClassifiedMutant]) -> str:
    """Stable JSON for the per-mutant classification baseline."""
    payload = {
        "classifications": [
            {
                "mutant_id": c.mutant_id,
                "classification": c.classification,
                "rule_id": c.rule_id,
            }
            for c in classified
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def load_baseline(path: Path) -> list[ClassifiedMutant]:
    """Load a prior classification baseline; missing file → empty (absent-case)."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[ClassifiedMutant] = []
    for entry in data.get("classifications", []):
        out.append(
            ClassifiedMutant(
                mutant_id=str(entry["mutant_id"]),
                classification=cast(Classification, entry["classification"]),
                rule_id=entry.get("rule_id"),
            )
        )
    return out


def detect_exclusion_growth(
    prev_baseline: Sequence[ClassifiedMutant],
    new_classifications: Sequence[ClassifiedMutant],
    *,
    fail_on_growth: bool = False,
) -> GrowthVerdict:
    """Flag when the rule-excluded set GROWS between runs (anti-loophole guard).

    A previously-pending survivor relabeled as excluded is the loophole this
    catches. Default severity is ``warn``; ``fail_on_growth`` escalates to
    ``fail`` for a hard gate.
    """
    prev_excluded = _excluded_ids(prev_baseline)
    new_excluded = _excluded_ids(new_classifications)
    added = tuple(sorted(new_excluded - prev_excluded))
    if not added:
        return GrowthVerdict(grew=False, added=(), severity="ok")
    return GrowthVerdict(
        grew=True,
        added=added,
        severity="fail" if fail_on_growth else "warn",
    )


def _descriptors_from_payload(survivors: Sequence[object]) -> list[MutantDescriptor]:
    """Parse survivor descriptors from a decoded JSON list (CLI input)."""
    out: list[MutantDescriptor] = []
    for raw in survivors:
        if not isinstance(raw, dict):
            continue
        out.append(
            MutantDescriptor(
                mutant_id=str(raw.get("mutant_id", "")),
                source_line=str(raw.get("source_line", "")),
                context=str(raw.get("context", "")),
            )
        )
    return out


# ---------------------------------------------------------------------------
# CLI (``python -m harness_maker.spec_mutation gate --yaml ... --tier 1``)
# ---------------------------------------------------------------------------

#: Substring mutmut-absent reports carry (see measure_baseline FileNotFoundError).
_MUTMUT_ABSENT = "command not found"


def _run_classify(args: argparse.Namespace) -> int:
    """Classify survivors, print adjusted score + excluded count + growth verdict."""
    raw = (
        args.input_path.read_text(encoding="utf-8")
        if args.input_path is not None
        else sys.stdin.read()
    )
    doc = json.loads(raw)
    killed = int(doc.get("killed", 0))
    descriptors = _descriptors_from_payload(doc.get("survivors", []))

    classified = classify_survivors(descriptors)
    report = MutationReport(
        paths=(),
        killed=killed,
        survived=len(descriptors),
        timeout=0,
        suspicious=0,
        skipped=0,
        sampled=False,
        raw_output="",
    )
    adj = adjusted_score(report, descriptors)

    # Growth is only meaningful against a provided prior baseline. A first run
    # (no --prev-baseline) has nothing to grow from → never warn.
    if args.prev_baseline is not None:
        prev = load_baseline(args.prev_baseline)
        verdict = detect_exclusion_growth(prev, classified, fail_on_growth=args.fail_on_growth)
    else:
        verdict = GrowthVerdict(grew=False, added=(), severity="ok")

    for c in classified:
        suffix = f" [{c.rule_id}]" if c.rule_id else ""
        print(f"  {c.mutant_id}: {c.classification}{suffix}")
    print(
        f"adjusted score: {adj.score:.4f} "
        f"(killed {adj.killed} / denom {adj.denominator}; "
        f"excluded-equivalent {adj.excluded_equivalent})"
    )
    print(
        f"exclusion-growth: grew={verdict.grew} severity={verdict.severity} "
        f"added={list(verdict.added)}"
    )

    if args.baseline_out is not None:
        atomic_write(args.baseline_out, baseline_to_json(classified))

    if verdict.severity == "fail":
        return 1
    if verdict.severity == "warn":
        return 3
    return 0


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

    p_cls = sub.add_parser(
        "classify",
        help="classify survivor descriptors + adjusted score + exclusion-growth guard",
    )
    p_cls.add_argument(
        "--input",
        dest="input_path",
        type=Path,
        default=None,
        help="JSON {killed, survivors:[{mutant_id,source_line,context}]} (default: stdin)",
    )
    p_cls.add_argument(
        "--prev-baseline",
        dest="prev_baseline",
        type=Path,
        default=None,
        help="prior baseline JSON to detect exclusion-set growth against",
    )
    p_cls.add_argument(
        "--baseline-out",
        dest="baseline_out",
        type=Path,
        default=None,
        help="write the new per-mutant classification baseline here (atomic)",
    )
    p_cls.add_argument(
        "--fail-on-growth",
        action="store_true",
        help="exit non-zero when the rule-excluded set grows (hard gate)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "classify":
        return _run_classify(args)

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
    "EQUIVALENCE_RULES",
    "PLUS_DELTA_PP",
    "TIER_FLOORS",
    "AdjustedScore",
    "Classification",
    "ClassifiedMutant",
    "EquivalenceRule",
    "GrowthVerdict",
    "MutantDescriptor",
    "MutationReport",
    "VerificationTier",
    "adjusted_score",
    "baseline_to_json",
    "classify_survivor",
    "classify_survivors",
    "detect_exclusion_growth",
    "gate",
    "load_baseline",
    "main",
    "measure_baseline",
    "report_to_json",
    "threshold_for",
]
