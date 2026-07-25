"""Pure economics layer — classify, price and aggregate per-turn spend (no I/O)."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from harness_maker.economics_source import IngestionDiagnostics
    from harness_maker.models import EconomicsConfig

# ADR-010: pricing is per-turn from the turn's own model, against a VERSIONED table so
# historical reports stay reproducible. USD per million tokens.
PRICE_TABLE_VERSION = "1"
PRICE_TABLE_EFFECTIVE_DATE = "2026-07-25"

SpendCategory = Literal["REWORK", "VERIFY", "PRODUCE", "OTHER"]
Scope = Literal["main", "subagent"]

UNATTRIBUTED = "(unattributed)"


class ModelPrice(BaseModel):
    """USD per million tokens, per token type. 5m/1h cache-write tiers are distinct."""

    model_config = ConfigDict(strict=True, extra="forbid")

    input: float
    output: float
    cache_read: float
    cache_write_5m: float
    cache_write_1h: float


# The 1h tier is priced above the 5m tier. Keeping them separate matters because
# cache_diagnostics actively advises users to enable the extended TTL for long
# planning sessions — collapsing the tiers would understate exactly those users.
PRICE_TABLE: dict[str, ModelPrice] = {
    "opus": ModelPrice(
        input=15.0, output=75.0, cache_read=1.5, cache_write_5m=18.75, cache_write_1h=30.0
    ),
    "sonnet": ModelPrice(
        input=3.0, output=15.0, cache_read=0.3, cache_write_5m=3.75, cache_write_1h=6.0
    ),
    "haiku": ModelPrice(
        input=0.25, output=1.25, cache_read=0.025, cache_write_5m=0.3, cache_write_1h=0.5
    ),
}

_VERIFY_SKILLS = frozenset({"hm:review", "hm:verify"})
_REVIEWER_AGENT_SUFFIXES = ("-reviewer", "-validator", "-auditor", "-arbiter", "-verifier")
_REVIEWER_AGENT_NAMES = frozenset({"stuck", "judgment-reviewer"})

_DEFAULT_IDLE_GAP_CAP_MIN = 5.0


class TokenUsage(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0

    @property
    def context_tokens(self) -> int:
        """What the turn paid to *have* its context, regardless of how it was billed."""
        return (
            self.input_tokens
            + self.cache_read_tokens
            + self.cache_write_5m_tokens
            + self.cache_write_1h_tokens
        )


class TurnRecord(BaseModel):
    """One assistant turn, normalised out of a transcript line."""

    model_config = ConfigDict(strict=True, extra="forbid")

    session_id: str
    ts: datetime
    model: str | None
    usage: TokenUsage
    attribution_skill: str | None = None
    attribution_agent: str | None = None
    is_sidechain: bool = False
    task_slug: str | None = None
    written_paths: tuple[str, ...] = ()
    cwd: str | None = None
    git_branch: str | None = None

    @property
    def scope(self) -> Scope:
        return "subagent" if self.is_sidechain else "main"

    @property
    def stage(self) -> str:
        return self.attribution_skill or UNATTRIBUTED


class TurnCost(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    input_usd: float
    output_usd: float
    cache_read_usd: float
    cache_write_usd: float
    total_usd: float
    priced_with_fallback: bool


class AdjacencyBounds(BaseModel):
    """ADR-006 — every bound must reject, or a long manual stretch inherits a stale stage."""

    model_config = ConfigDict(strict=True, extra="forbid")

    enabled: bool = True
    max_gap_min: float = 10.0
    max_turns: int = 20


class CategoryTotals(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    turns: int = 0
    total_usd: float = 0.0


class StageTotals(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    turns: int = 0
    total_usd: float = 0.0
    output_tokens: int = 0
    context_tokens: int = 0
    cache_read_usd: float = 0.0
    work_usd: float = 0.0
    by_category: dict[str, CategoryTotals] = Field(default_factory=dict)

    @property
    def mean_context_tokens(self) -> float:
        return self.context_tokens / self.turns if self.turns else 0.0

    @property
    def carry_ratio(self) -> float:
        return self.cache_read_usd / self.total_usd if self.total_usd else 0.0


class EconomicsReport(BaseModel):
    """Aggregate spend by function. Deliberately carries NO cost-divided-by-count field.

    ADR-002: dividing cost by any deliverable count makes verification spend read as
    waste. The absence below is the enforced half of that decision; the prose layer in
    the command template is an instruction, not enforcement.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    total_usd: float = 0.0
    turns: int = 0
    price_table_version: str = PRICE_TABLE_VERSION
    price_table_effective_date: str = PRICE_TABLE_EFFECTIVE_DATE

    by_stage: dict[str, StageTotals] = Field(default_factory=dict)
    by_agent: dict[str, StageTotals] = Field(default_factory=dict)
    by_category: dict[str, CategoryTotals] = Field(default_factory=dict)

    cache_read_usd: float = 0.0
    work_usd: float = 0.0
    carry_ratio: float = 0.0

    estimated_attribution_usd: dict[str, float] = Field(default_factory=dict)
    estimator_coverage: float = 0.0
    rework_coverage: float = 0.0

    wall_clock_seconds_by_scope: dict[str, float] = Field(default_factory=dict)

    unknown_models: dict[str, int] = Field(default_factory=dict)
    fallback_priced_turns: int = 0


def ratio_field_kinds() -> dict[str, tuple[str, str]]:
    """Declare every ratio field's numerator/denominator KIND (ADR-002 invariant).

    A `("cost", "count")` entry would be the forbidden cost-per-deliverable shape.
    """
    return {
        "carry_ratio": ("cost", "cost"),
        "estimator_coverage": ("cost", "cost"),
        "rework_coverage": ("count", "count"),
    }


# ------------------------------------------------------------------ classification


def _is_reviewer_agent(name: str | None) -> bool:
    if not name:
        return False
    return name in _REVIEWER_AGENT_NAMES or name.endswith(_REVIEWER_AGENT_SUFFIXES)


def _verifies(turn: TurnRecord) -> bool:
    """Rule 2 WITHOUT the writes-nothing clause — used both by the ladder and by rule 1."""
    return turn.attribution_skill in _VERIFY_SKILLS or _is_reviewer_agent(turn.attribution_agent)


def classify_turns(turns: Sequence[TurnRecord]) -> list[SpendCategory]:
    """Ordered ladder REWORK > VERIFY > PRODUCE > OTHER — exactly one label per turn.

    Rule 1's VERIFY-clause and rule 2's writes-nothing clause together keep the
    review->fix loop out of REWORK and out of VERIFY: a fix is production work.
    """
    # Write history is TASK-scoped: one task worktree is worked across many sessions, so
    # a rewrite in a later session is still rework on that task.
    # The verify window is SESSION-scoped: `load_turns` globally sorts turns from every
    # session, and concurrent sessions on one task are a supported workflow — a peer
    # session's review must not silently absolve THIS session's rewrite. Where the causal
    # link is unproven the bias is toward the visible label (REWORK), not toward absolution.
    last_write_at: dict[tuple[str, str], int] = {}
    last_verify_at: dict[tuple[str, str], int] = {}
    labels: list[SpendCategory] = []

    for idx, turn in enumerate(turns):
        verifies = _verifies(turn)
        writes = bool(turn.written_paths)

        verify_key = (turn.session_id, turn.task_slug or "")
        is_rework = False
        if writes and not verifies and turn.task_slug is not None:
            is_rework = all(
                (prior := last_write_at.get((turn.task_slug, path))) is not None
                and last_verify_at.get(verify_key, -1) < prior
                for path in turn.written_paths
            )

        if is_rework:
            labels.append("REWORK")
        elif verifies and not writes:
            labels.append("VERIFY")
        elif writes:
            labels.append("PRODUCE")
        else:
            labels.append("OTHER")

        # Record the verify window ONLY for a turn whose final label is VERIFY. A turn
        # that both verifies and writes is PRODUCE (a review-driven fix); letting it
        # stamp last_verify_at makes `last_verify < prior` compare idx < idx == False,
        # so the NEXT unprompted rewrite of that path escapes REWORK.
        if labels[-1] == "VERIFY" and turn.task_slug is not None:
            last_verify_at[verify_key] = idx
        if writes and turn.task_slug is not None:
            for path in turn.written_paths:
                last_write_at[(turn.task_slug, path)] = idx

    return labels


# ------------------------------------------------------------------ pricing


def resolve_model_family(model: str | None) -> str | None:
    """Map a transcript model string onto a PRICE_TABLE row, or None when unrecognised.

    Longest-match wins so the answer never depends on PRICE_TABLE's insertion order —
    a string containing two family names must resolve deterministically.
    """
    if not model:
        return None
    lowered = model.lower()
    matches = [family for family in PRICE_TABLE if family in lowered]
    if not matches:
        return None
    return max(sorted(matches), key=len)


def price_turn(turn: TurnRecord, *, fallback_model: str = "opus") -> TurnCost:
    family = resolve_model_family(turn.model)
    used_fallback = family is None
    # Resolve the fallback through the SAME matcher: `price_model` is free text, so an
    # exact-key lookup would silently drop `claude-sonnet-4-5` onto the opus rate — a
    # 5x mispricing in a tool whose entire output is dollar figures.
    fallback_family = resolve_model_family(fallback_model) or fallback_model
    price = PRICE_TABLE.get(family or fallback_family) or PRICE_TABLE["opus"]

    u = turn.usage
    input_usd = u.input_tokens * price.input / 1e6
    output_usd = u.output_tokens * price.output / 1e6
    cache_read_usd = u.cache_read_tokens * price.cache_read / 1e6
    cache_write_usd = (
        u.cache_write_5m_tokens * price.cache_write_5m
        + u.cache_write_1h_tokens * price.cache_write_1h
    ) / 1e6
    return TurnCost(
        input_usd=input_usd,
        output_usd=output_usd,
        cache_read_usd=cache_read_usd,
        cache_write_usd=cache_write_usd,
        total_usd=input_usd + output_usd + cache_read_usd + cache_write_usd,
        priced_with_fallback=used_fallback,
    )


# ------------------------------------------------------------------ adjacency estimate


def estimate_attribution(
    turns: Sequence[TurnRecord], bounds: AdjacencyBounds | None = None
) -> list[str | None]:
    """Guess a stage for unattributed turns from the nearest PRECEDING attributed turn.

    Every bound must be able to reject: an unbounded lookback silently hands hours of
    unrelated manual work to whichever stage last set attributionSkill.
    """
    b = bounds or AdjacencyBounds()
    out: list[str | None] = [None] * len(turns)
    if not b.enabled:
        return out

    anchor: TurnRecord | None = None
    anchor_idx = -1
    for idx, turn in enumerate(turns):
        if turn.attribution_skill:
            anchor, anchor_idx = turn, idx
            continue
        if anchor is None:
            continue
        if turn.session_id != anchor.session_id:
            anchor = None
            continue
        if turn.cwd != anchor.cwd or turn.git_branch != anchor.git_branch:
            anchor = None
            continue
        if turn.task_slug != anchor.task_slug:
            anchor = None
            continue
        if idx - anchor_idx > b.max_turns:
            continue
        if (turn.ts - anchor.ts).total_seconds() > b.max_gap_min * 60.0:
            continue
        out[idx] = anchor.attribution_skill
    return out


# ------------------------------------------------------------------ aggregate


def _accumulate(bucket: StageTotals, turn: TurnRecord, cost: TurnCost, label: str) -> None:
    bucket.turns += 1
    bucket.total_usd += cost.total_usd
    bucket.output_tokens += turn.usage.output_tokens
    bucket.context_tokens += turn.usage.context_tokens
    bucket.cache_read_usd += cost.cache_read_usd
    bucket.work_usd += cost.cache_write_usd + cost.output_usd
    cat = bucket.by_category.setdefault(label, CategoryTotals())
    cat.turns += 1
    cat.total_usd += cost.total_usd


def _wall_clock_by_scope(turns: Sequence[TurnRecord], idle_gap_cap_min: float) -> dict[str, float]:
    """Sum gaps inside contiguous same-attribution runs, each gap capped at the idle cap.

    Reported per scope and never summed across scopes — main and subagent turns overlap
    in real time, so a combined total would double-count.
    """
    cap = idle_gap_cap_min * 60.0
    totals: dict[str, float] = {}
    per_scope: dict[str, list[TurnRecord]] = defaultdict(list)
    for turn in turns:
        per_scope[turn.scope].append(turn)
    for scope, scope_turns in per_scope.items():
        ordered = sorted(scope_turns, key=lambda t: t.ts)
        seconds = 0.0
        for prev, cur in zip(ordered, ordered[1:], strict=False):
            if prev.stage != cur.stage:
                continue
            seconds += min((cur.ts - prev.ts).total_seconds(), cap)
        totals[scope] = seconds
    return totals


def aggregate(
    turns: Sequence[TurnRecord],
    *,
    bounds: AdjacencyBounds | None = None,
    idle_gap_cap_min: float = _DEFAULT_IDLE_GAP_CAP_MIN,
    fallback_model: str = "opus",
) -> EconomicsReport:
    report = EconomicsReport()
    if not turns:
        return report

    labels = classify_turns(turns)
    costs = [price_turn(t, fallback_model=fallback_model) for t in turns]
    estimates = estimate_attribution(turns, bounds)

    unknown: Counter[str] = Counter()
    unattributed_usd = 0.0
    estimated_usd = 0.0
    writing_turns = 0
    resolvable_writing_turns = 0

    for turn, cost, label, est in zip(turns, costs, labels, estimates, strict=True):
        report.turns += 1
        report.total_usd += cost.total_usd
        report.cache_read_usd += cost.cache_read_usd
        report.work_usd += cost.cache_write_usd + cost.output_usd

        _accumulate(report.by_stage.setdefault(turn.stage, StageTotals()), turn, cost, label)
        if turn.attribution_agent:
            _accumulate(
                report.by_agent.setdefault(turn.attribution_agent, StageTotals()), turn, cost, label
            )
        cat = report.by_category.setdefault(label, CategoryTotals())
        cat.turns += 1
        cat.total_usd += cost.total_usd

        if cost.priced_with_fallback:
            report.fallback_priced_turns += 1
            unknown[turn.model or "(none)"] += 1

        if turn.attribution_skill is None:
            unattributed_usd += cost.total_usd
            if est is not None:
                estimated_usd += cost.total_usd
                report.estimated_attribution_usd[est] = (
                    report.estimated_attribution_usd.get(est, 0.0) + cost.total_usd
                )

        if turn.written_paths:
            writing_turns += 1
            if turn.task_slug is not None:
                resolvable_writing_turns += 1

    report.unknown_models = dict(unknown)
    report.carry_ratio = report.cache_read_usd / report.total_usd if report.total_usd else 0.0
    report.estimator_coverage = estimated_usd / unattributed_usd if unattributed_usd else 0.0
    report.rework_coverage = resolvable_writing_turns / writing_turns if writing_turns else 0.0
    report.wall_clock_seconds_by_scope = _wall_clock_by_scope(turns, idle_gap_cap_min)
    return report


# ------------------------------------------------------------------ CLI
# Co-located with the pure functions, matching delivery_metrics.py — purity here comes
# from the economics/economics_source module split, not from module-per-concern.


def _load_cli_config(root: Path) -> EconomicsConfig:
    """Tolerant read: an absent or malformed block yields defaults, never an abort."""
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.models import EconomicsConfig as _Cfg

    path = root / ".claude" / "harness.yaml"
    if not path.is_file():
        return _Cfg()
    try:
        data = load_harness_yaml(path)
    except Exception:  # noqa: BLE001 - a broken harness.yaml must not break reporting
        return _Cfg()
    raw = data.get("economics") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return _Cfg()
    clean = {k: v for k, v in raw.items() if k in _Cfg.model_fields}
    try:
        return _Cfg.model_validate(clean)
    except Exception:  # noqa: BLE001
        return _Cfg()


def _collect(
    root: Path,
    transcript_root: Path | None,
    days: int | None,
    now: datetime | None = None,
) -> tuple[EconomicsReport, IngestionDiagnostics, EconomicsConfig]:
    from harness_maker.economics_source import load_turns

    cfg = _load_cli_config(root)
    result = load_turns(
        root,
        transcript_root=transcript_root,
        days=days if days is not None else cfg.window_days,
        now=now,
    )
    bounds = AdjacencyBounds(
        enabled=cfg.adjacency_estimate,
        max_gap_min=cfg.adjacency_max_gap_min,
        max_turns=cfg.adjacency_max_turns,
    )
    report = aggregate(
        result.turns,
        bounds=bounds,
        idle_gap_cap_min=cfg.idle_gap_cap_min,
        fallback_model=cfg.price_model,
    )
    return report, result.diagnostics, cfg


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _cmd_report(
    root: Path, transcript_root: Path | None, days: int | None, now: datetime | None
) -> int:
    report, diag, _cfg = _collect(root, transcript_root, days, now)
    _print_json(
        {
            "status": "ok",
            "report": report.model_dump(mode="json"),
            "ingestion": {**diag.model_dump(mode="json"), "coverage": diag.coverage},
            "external_models_unmeasured": True,
        }
    )
    return 0


def _cmd_stages(
    root: Path, transcript_root: Path | None, days: int | None, now: datetime | None
) -> int:
    report, _diag, _cfg = _collect(root, transcript_root, days, now)
    rows = sorted(report.by_stage.items(), key=lambda kv: -kv[1].total_usd)
    _print_json(
        {
            "status": "ok",
            "price_table_version": report.price_table_version,
            "stages": [
                {
                    "stage": name,
                    "turns": s.turns,
                    "total_usd": round(s.total_usd, 6),
                    "mean_context_tokens": round(s.mean_context_tokens, 1),
                    "carry_ratio": round(s.carry_ratio, 4),
                    "by_category": {k: v.turns for k, v in sorted(s.by_category.items())},
                }
                for name, s in rows
            ],
        }
    )
    return 0


def _cmd_doctor(root: Path, transcript_root: Path | None) -> int:
    """Positive liveness smoke (ADR-009). Measures the READER, never the spend."""
    from harness_maker.economics_source import discover_transcript_dirs, load_turns

    resolved = transcript_root
    dirs = discover_transcript_dirs(root, transcript_root=resolved) if resolved else None
    if resolved is None:
        from harness_maker.economics_source import default_transcript_root

        resolved = default_transcript_root()
        dirs = discover_transcript_dirs(root, transcript_root=resolved)
    result = load_turns(root, transcript_root=resolved)
    diag = result.diagnostics
    if not dirs or diag.files_discovered == 0:
        _print_json(
            {
                "status": "n/a",
                "reason": "no transcript store for this project (fresh clone, CI, Cursor or Codex)",
                "dirs_scanned": diag.dirs_scanned,
            }
        )
        return 0
    if diag.turns_with_usage == 0:
        _print_json(
            {
                "status": "fail",
                "reason": "transcript files exist but zero turns priced — the reader is "
                "silently degraded (format drift?)",
                "ingestion": {**diag.model_dump(mode="json"), "coverage": diag.coverage},
            }
        )
        return 1
    _print_json(
        {
            "status": "ok",
            "turns_priced": diag.turns_with_usage,
            "coverage": round(diag.coverage, 4),
            "dirs_scanned": diag.dirs_scanned,
        }
    )
    return 0


def _parse_now(raw: object) -> datetime | None:
    """Always tz-aware. A naive `--now` vs aware transcript stamps raises TypeError."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness_maker.economics")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=".", help="project root (resolved from any cwd)")
        p.add_argument(
            "--transcript-root",
            default=None,
            help="override ~/.claude/projects (testing + non-default installs)",
        )

    p_report = sub.add_parser("report", help="full economics report as JSON")
    add_common(p_report)
    p_report.add_argument("--days", type=int, default=None)
    p_report.add_argument("--now", default=None, help="ISO instant for window math (testing)")

    p_stages = sub.add_parser("stages", help="per-stage cost breakdown as JSON")
    add_common(p_stages)
    p_stages.add_argument("--days", type=int, default=None)
    p_stages.add_argument("--now", default=None, help="ISO instant for window math (testing)")

    p_doctor = sub.add_parser("doctor", help="liveness smoke: is the reader still pricing?")
    add_common(p_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    from harness_maker import command_registry

    guard = command_registry.guard_or_none("economics", argv)
    if guard is not None:
        return guard
    args = _build_argparser().parse_args(argv)
    root = Path(args.root).resolve()
    transcript_root = Path(args.transcript_root).resolve() if args.transcript_root else None
    now = _parse_now(getattr(args, "now", None))
    if args.command == "report":
        return _cmd_report(root, transcript_root, args.days, now)
    if args.command == "stages":
        return _cmd_stages(root, transcript_root, args.days, now)
    return _cmd_doctor(root, transcript_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
