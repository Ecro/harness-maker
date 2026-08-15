"""mutmut wrapper + baseline-relative threshold gate (ADR-005).

threshold = max(measured_baseline + 5pp, tier_floor) where tier_floor ∈
{T1: 85, T2: 70, T3: informational (no gate)}.

Subprocess timeouts are mandatory per CLAUDE.md. ``shell=True`` is forbidden.
The fallback rule (60-min budget → sampled 200-mutant mode) is exposed via
``run_mutation(sampled=True)``.

mutation_runner_faults
----------------------
**Until 2026-08-15 this gate could not pass for any SPEC in this repository, and its failure
mode was a plausible number.** Three faults were live at once, each masking the next:

1. **Parse.** ``_COUNTERS_RE`` scanned for the words ``killed:``/``survived:``. mutmut 2.x
   writes an emoji-only progress line (``🎉 42  ⏰ 0  🤔 0  🙁 13  🔇 0``), so a healthy run
   parsed as all-zeros. See ``_EMOJI_COUNTERS``.
2. **Runner scope.** No ``--runner`` was passed, so mutmut ran the whole ``tests/`` tree per
   mutant — ~6 min here against a 600 s cap, i.e. the first mutant always timed out.
3. **Silent zero.** Both of the above produce an all-zero report, and ``score`` returns 0.0 for
   it because the denominator is empty. The gate printed ``score 0% < threshold 85%`` — the
   same string a genuine total wipeout produces. See ``MutationReport.ran``.

Fault 3 is why the other two survived: every SPEC author read a real-looking measurement and
wrote rationale around it (this repo has at least two such rationale blocks). The lesson worth
keeping is not "parse emoji" — it is that a wrapper which cannot distinguish *no observation*
from *a bad observation* will report the second when it means the first, indefinitely.

First real measurement after the fix: ``lens_coverage.py`` 55 mutants, 42 killed, 13 survived
— **76%**, below the T1 floor of 85%.
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

from harness_maker import command_registry
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
    #: True when the wall budget cut the run short. The counts are then a PREFIX of the run,
    #: not a result. Before the emoji parser landed this was invisible — partial output parsed
    #: to all-zeros and looked like the non-run case; now it parses to a real-looking number,
    #: which is strictly worse unless the truncation travels with it.
    truncated: bool = False
    #: Set ONLY by the `FileNotFoundError` branch. The absent-mutmut skip used to be a
    #: substring test for "command not found" against the whole captured output — and once
    #: `--runner` began injecting a user-supplied test command, that command's own
    #: `pytest: command not found` turned a broken-but-running gate into a silent non-gating
    #: skip. A guard named "the tool is absent" must be set where absence is observed.
    tool_missing: bool = False

    @property
    def total(self) -> int:
        return self.killed + self.survived + self.timeout + self.suspicious

    @property
    def score(self) -> float:
        """Killed fraction; survivors degrade the score."""
        denom = self.killed + self.survived + self.timeout
        return self.killed / denom if denom else 0.0

    @property
    def ran(self) -> bool:
        """True when mutmut actually checked at least one mutant.

        **The distinction this exists to draw:** an all-zero report is NOT a score of 0%. It
        means no mutant was ever evaluated — a crashed runner, a timeout, an unparseable
        output format — and `score` returns 0.0 for it only because the denominator is empty.

        That collision hid three separate faults in this wrapper for the lifetime of the tier-1
        gate (see `mutation_runner_faults` in the module docstring): every SPEC's gate reported
        `score 0% < threshold 85%` and every reader took it for "the tests are weak". Callers
        must branch on `ran` BEFORE reading `score`.
        """
        return (self.killed + self.survived + self.timeout + self.suspicious + self.skipped) > 0


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
    if not report.ran:
        # Fail LOUD, not at 0%. A non-run and a total wipeout are the same number and opposite
        # facts, and reporting the number let three runner faults ship behind a red gate that
        # read as a legitimate measurement.
        return False, (
            "mutmut checked ZERO mutants — this is a broken run, not a score of 0%. "
            "Inspect MutationReport.raw_output: the usual causes are a runner that cannot "
            "import the package, a wall-budget timeout because the runner is the whole test "
            "suite, or an output format this wrapper cannot parse"
        )
    if report.truncated:
        checked = report.killed + report.survived + report.timeout + report.suspicious
        return False, (
            f"partial run — the wall budget expired after {checked} mutant(s); the counts are a "
            "prefix of the run, not a score of the whole path set. Narrow `mutation_runner`, "
            "split `paths_to_mutate`, or re-run with --sampled"
        )
    score_pct = int(round(report.score * 100))
    if score_pct >= threshold:
        return True, f"score {score_pct}% >= threshold {threshold}%"
    return False, f"score {score_pct}% < threshold {threshold}%"


#: Substring an unsupported-mutmut report carries (see _detect_unsupported_mutmut).
#: Paired with _MUTMUT_ABSENT (defined near the CLI) — both route main() to a non-gating skip.
_MUTMUT_UNSUPPORTED = "mutmut: unsupported major version"

#: mutmut's own version in `mutmut --version` output — anchored to the tool name so
#: a stray dotted number in a preceding warning line cannot be read as the version.
_MUTMUT_VERSION_RE = re.compile(r"mutmut[^\d]*(\d+)\.(\d+)(?:\.(\d+))?", re.IGNORECASE)

#: The version pre-check is instant; a short timeout guards a hung binary.
_VERSION_PRECHECK_TIMEOUT_S = 10


def _detect_unsupported_mutmut(cwd: Path) -> str | None:
    """Return an _MUTMUT_UNSUPPORTED report string when the installed mutmut major
    version is >= 3, else None.

    mutmut 3.x rewrote the CLI and dropped ``--paths-to-mutate`` (which the run
    path hard-codes), so a 3.x binary makes ``mutmut run`` exit non-zero and the
    gate spuriously FAIL at 0%. Detecting it here lets the caller loud-skip.
    Any ambiguity (absent / timeout / unparsable / non-zero) returns None so the
    caller falls through to the normal run path — never false-skip a working 2.x,
    and let the existing run-FileNotFoundError handler own the absent contract.
    """
    try:
        proc = subprocess.run(
            ["mutmut", "--version"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_VERSION_PRECHECK_TIMEOUT_S,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        # A broken/ambiguous `mutmut --version` (non-zero exit) may spew unrelated
        # version-shaped text; treat as ambiguous → fall through so the real run
        # path surfaces the failure instead of a silent unsupported-skip.
        return None
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = _MUTMUT_VERSION_RE.search(blob)
    if m is None:
        return None
    if int(m.group(1)) >= 3:
        return (
            f"{_MUTMUT_UNSUPPORTED} {m.group(0)} "
            "(mutmut 3.x dropped --paths-to-mutate; pin mutmut<3)"
        )
    return None


def measure_baseline(
    paths_to_mutate: list[str],
    *,
    cwd: Path,
    wall_budget_min: int = DEFAULT_WALL_BUDGET_MIN,
    sample_budget: int = DEFAULT_SAMPLE_MUTANT_BUDGET,
    sampled: bool = False,
    timeout_seconds: int | None = None,
    runner: str | None = None,
) -> MutationReport:
    """Invoke mutmut and parse its output into a MutationReport.

    Designed to be cancellable: if real wall-clock exceeds the budget, caller
    can re-invoke with ``sampled=True`` per ADR-005 fallback rule.

    ``runner`` is the test command mutmut runs **per mutant**. Passing one is not an
    optimisation — on any repository whose full suite is slower than
    ``wall_budget / mutant_count`` it is the difference between a measurement and a
    guaranteed timeout. Measured here 2026-08-15: mutmut's default runner is the whole
    ``tests/`` tree (~6 min in this repo), so ONE mutant exhausted the 600 s cap and the gate
    returned all-zeros for every SPEC. Scoped to the tests that cover the mutated file, the
    same 55 mutants finish in under 550 s.
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
    unsupported = _detect_unsupported_mutmut(cwd)
    if unsupported is not None:
        return _parse_mutmut_output(unsupported, tuple(paths_to_mutate), sampled=sampled)
    args = ["mutmut", "run", "--paths-to-mutate", ",".join(paths_to_mutate)]
    if runner:
        args.extend(["--runner", runner])
    if sampled:
        args.extend(["--use-coverage"])  # narrow the universe
    # Compute timeout: wall budget in seconds, capped 600 per Bash policy
    deadline = timeout_seconds if timeout_seconds is not None else min(wall_budget_min * 60, 600)
    truncated = False
    tool_missing = False
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
        tool_missing = True
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
        truncated = True

    return _parse_mutmut_output(
        raw, tuple(paths_to_mutate), sampled=sampled, truncated=truncated, tool_missing=tool_missing
    )


_COUNTERS_RE = re.compile(r"(killed|survived|timeout|suspicious|skipped)[:\s]+(\d+)", re.IGNORECASE)

#: mutmut 2.x's progress line is EMOJI-ONLY — it never writes the English words above:
#:
#:     ⠋ 55/55  🎉 42  ⏰ 0  🤔 0  🙁 13  🔇 0
#:
#: `_COUNTERS_RE` therefore matched nothing on a perfectly healthy run, and the report parsed
#: as all-zeros. Measured 2026-08-15 against mutmut 2.5 on `lens_coverage.py`: 55 mutants,
#: 42 killed, 13 survived — reported by this wrapper as `score 0%`. The legend that names each
#: emoji is printed once at the top of the run, so the symbols are the stable contract, not a
#: cosmetic detail.
_EMOJI_COUNTERS: tuple[tuple[str, str], ...] = (
    ("\N{PARTY POPPER}", "killed"),
    ("\N{ALARM CLOCK}", "timeout"),
    ("\N{THINKING FACE}", "suspicious"),
    ("\N{SLIGHTLY FROWNING FACE}", "survived"),
    ("\N{SPEAKER WITH CANCELLATION STROKE}", "skipped"),
)


def _parse_mutmut_output(
    raw: str,
    paths: tuple[str, ...],
    *,
    sampled: bool,
    truncated: bool = False,
    tool_missing: bool = False,
) -> MutationReport:
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

    # mutmut 2.x: emoji progress line, rewritten in place with \r. Take the LAST occurrence of
    # each symbol — earlier ones are intermediate progress, and the final line is the result.
    # Runs after the word-form scan so a future JSON/worded output wins if both are present.
    if not any(counts.values()):
        # Only when the word-form scan found NOTHING. The comment above always claimed a
        # worded/JSON output wins if both are present; an unconditional assignment made the
        # emoji win instead, so a `\r`-rewritten progress snapshot could replace authoritative
        # totals.
        for symbol, key in _EMOJI_COUNTERS:
            matches = re.findall(rf"{re.escape(symbol)}\s*(\d+)", raw)
            if matches:
                counts[key] = int(matches[-1])
    return MutationReport(
        paths=paths,
        killed=counts["killed"],
        survived=counts["survived"],
        timeout=counts["timeout"],
        suspicious=counts["suspicious"],
        skipped=counts["skipped"],
        sampled=sampled,
        raw_output=raw,
        truncated=truncated,
        tool_missing=tool_missing,
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
    _guard = command_registry.guard_or_none("spec_mutation", argv)
    if _guard is not None:
        return _guard
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
    p_gate.add_argument(
        "--runner",
        default=None,
        help=(
            "test command mutmut runs per mutant, e.g. "
            "'python -m pytest -x -q tests/unit/test_foo.py'. Without it mutmut runs the WHOLE "
            "suite per mutant, which on this repo exceeds the wall budget on the first mutant "
            "and yields a zero report that reads as score 0%%."
        ),
    )

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

    # --runner beats the SPEC's own field, so a one-off diagnostic run needs no file edit.
    runner = args.runner or machine.mutation_runner
    report = measure_baseline(paths, cwd=args.cwd, sampled=args.sampled, runner=runner)
    if report.tool_missing:
        print(
            "mutation gate: mutmut not installed — skipping (non-gating). "
            "Run `uv sync --group dev` to enable.",
            file=sys.stderr,
        )
        return 0

    if _MUTMUT_UNSUPPORTED in report.raw_output:
        print(
            "mutation gate: mutmut 3.x unsupported (pin mutmut<3) — skipping (non-gating). "
            "The wrapper uses the 2.x `--paths-to-mutate` CLI; downgrade or pin to use the gate.",
            file=sys.stderr,
        )
        return 0

    if report.truncated or not report.ran:
        # mutmut edits the source in place and restores it when it finishes. A run that did NOT
        # finish can leave a mutant on disk — measured 2026-08-15, an interrupted run left
        # `if __name__ != "__main__"` in review_telemetry.py, which made importing the module
        # call sys.exit() and would have been committed unnoticed. Warn with the paths named;
        # do not auto-revert, because these files are the user's working tree.
        print(
            "mutation gate: this run did not complete — mutmut may have left a MUTATED source "
            "on disk. Verify before committing:\n  " + "\n  ".join(paths),
            file=sys.stderr,
        )

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
