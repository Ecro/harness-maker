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

from .run_classify import ClassificationAttribution
from .stage_spans import SpanAttribution

if TYPE_CHECKING:
    from harness_maker.economics_source import IngestionDiagnostics
    from harness_maker.models import EconomicsConfig

# ADR-010: pricing is per-turn from the turn's own model. USD per million tokens.
#
# The version is a LABEL emitted into the report, not a dispatch key: reports are
# always recomputed from raw transcripts, so correcting a rate necessarily reprices
# historical windows on re-run and no stored artifact exists to preserve. (An earlier
# comment here claimed the table made "historical reports reproducible" — it never
# did, and that claim is what made a wrong rate look safe to leave in place.) Both
# labels move together: the version says WHICH table, the date says FROM WHEN.
PRICE_TABLE_VERSION = "2"
PRICE_TABLE_EFFECTIVE_DATE = "2026-07-27"

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
#
# Keys are matched as SUBSTRINGS of the lowered model id by `resolve_model_family`,
# longest-match wins. Point-release keys therefore shadow their family key, which is
# the whole point: `"opus"` alone captured `claude-opus-5` and priced 30 days of this
# repo's spend at 15/75 against a published 5/25 — a 3x overstatement on 65.6% of the
# bill. The family rows are RETAINED so a genuinely pre-4.5 id still resolves (and a
# post-table release still prices rather than erroring).
#
# R8 — the recurrence path, and how it is now visible. A model released after this
# table is written matches its FAMILY key, so `resolve_model_family` returns non-None,
# `price_turn`'s `used_fallback = family is None` stays False, and the turn appears in
# neither `report.unknown_models` nor `fallback_priced_turns`: `claude-opus-9` would be
# priced at the pre-4.5 15/75 with no trace, bit for bit the recurrence of the bug this
# table exists to fix. Those two fields only ever caught ids matching no key at all
# (`gpt-*`). `report.family_priced_turns` / `family_priced_models` close that blind
# spot (ADR-018). They change no rate — the family row still serves as the fallback,
# which remains ADR-002's locked policy; what changes is that the fallback is now
# observable. An earlier revision of this comment asserted the first two fields already
# covered this, and asserting an untested safety net is how the original defect
# survived — so the claim above is pinned by
# `test_a_family_priced_turn_is_visible_in_the_report`, which asserts through the
# aggregated report rather than the flag.
_OPUS_4_5_PLUS = ModelPrice(
    input=5.0, output=25.0, cache_read=0.5, cache_write_5m=6.25, cache_write_1h=10.0
)
_SONNET = ModelPrice(
    input=3.0, output=15.0, cache_read=0.3, cache_write_5m=3.75, cache_write_1h=6.0
)

PRICE_TABLE: dict[str, ModelPrice] = {
    # Pre-4.5 Opus. Deliberately left at the legacy rate — editing this row instead of
    # adding point releases would leave genuine pre-4.5 turns priced 3x under.
    "opus": ModelPrice(
        input=15.0, output=75.0, cache_read=1.5, cache_write_5m=18.75, cache_write_1h=30.0
    ),
    "opus-4-5": _OPUS_4_5_PLUS,
    "opus-4-6": _OPUS_4_5_PLUS,
    "opus-4-7": _OPUS_4_5_PLUS,
    "opus-4-8": _OPUS_4_5_PLUS,
    "opus-5": _OPUS_4_5_PLUS,
    "sonnet": _SONNET,
    "sonnet-4-5": _SONNET,
    "sonnet-5": _SONNET,
    # Pre-4.5 Haiku. The 0.25/1.25 this row carries is the Haiku 3 published rate — it
    # is NOT a stale value to overwrite. An earlier draft of this change edited it in
    # place to Haiku 4.5's 1/5, which repriced every older Haiku turn 4x: the same
    # class of error this table exists to remove, introduced in the opposite direction
    # and in violation of the rule stated 15 lines above. Point releases get keys; the
    # family row keeps the legacy rate.
    "haiku": ModelPrice(
        input=0.25, output=1.25, cache_read=0.025, cache_write_5m=0.3, cache_write_1h=0.5
    ),
    "haiku-4-5": ModelPrice(
        input=1.0, output=5.0, cache_read=0.1, cache_write_5m=1.25, cache_write_1h=2.0
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
    # Retroactive-classification inputs (Phase 3). `uuid` is the verdict cache key;
    # anything else (index, timestamp) shifts when the reporting window moves.
    # `preceded_by_user` is the only trace of ADR-005's "boundary with no user
    # message" case that survives the loader dropping every non-assistant line.
    uuid: str | None = None
    preceded_by_user: bool = False

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
    # Two DISTINCT signals, never collapse them. `priced_with_fallback` means the id
    # matched no key at all (`gpt-4`) and took `fallback_model`. `priced_with_family_row`
    # means it matched a BARE FAMILY row — the R8 recurrence path, where a model released
    # after this table silently takes the family rate. Defaulted so existing constructors
    # keep working.
    priced_with_family_row: bool = False


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


class UnattributedBucket(BaseModel):
    """One part of the `(unattributed)` partition. Counts and cost only, no quotient."""

    model_config = ConfigDict(strict=True, extra="forbid")

    turns: int = 0
    usd: float = 0.0


# ADR-013 requires the re-framing to be observable in the artifact rather than living
# only in the PLAN. Emitted alongside the buckets, never instead of them.
_UNATTRIBUTED_BREAKDOWN_NOTES: tuple[str, ...] = (
    "`recoverable` means adjacency-resolvable within the configured window, or "
    "carrying `preceded_by_user`. It is not a claim that these turns will be "
    "recovered, and its complement is not a claim that the rest are unattributable "
    "— a turn outside the window may still be attributed by a later classification "
    "verdict (see `classification_cache_misses`).",
    "A turn past the span cap is never `recoverable`: the cap is terminal, so "
    "user-adjacency does not re-open it.",
    "Cursor and Codex sessions write no Claude Code transcripts, so they are absent "
    "from this population rather than a third bucket inside it.",
    "`feature_branch_workflow: false` harnesses are a repository config, not a turn "
    "attribute — the same kind of absence, not a bucket.",
)


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
    # R8 visibility. A turn priced through a BARE FAMILY row is not "unknown" — it
    # resolved — so it appears in neither field above. That silence is how `"opus"`
    # captured `claude-opus-5` at 15/75 for 30 days. These two fields make the next
    # occurrence loud; they change no rate.
    family_priced_turns: int = 0
    family_priced_models: dict[str, int] = Field(default_factory=dict)

    # ── attribution provenance (ADR-001/009 of PLAN-economics-attribution-and-carry)
    # Source is a per-TURN property, so these are the conserved axis: every priced
    # turn lands in exactly one bucket and the USD buckets sum to `total_usd`.
    # `by_agent` deliberately stays a CROSS-CUT (a turn appears there *and* in
    # `by_stage`), so no cross-population conservation is claimed — see ADR-009.
    # All sums and counts; no cost-per-count quotient (ADR-002 of the prior work).
    usd_by_attribution_source: dict[str, float] = Field(default_factory=dict)
    turns_by_attribution_source: dict[str, int] = Field(default_factory=dict)
    # ADR-013. A decomposition OF `by_stage["(unattributed)"]`, so it conserves against
    # that entry on both turns and USD — and it is absent entirely when that entry is,
    # rather than reporting a partition of nothing.
    unattributed_breakdown: dict[str, UnattributedBucket] = Field(default_factory=dict)
    unattributed_breakdown_notes: list[str] = Field(default_factory=list)
    capped_turns: int = 0
    capped_usd: float = 0.0
    ambiguous_session_join: int = 0
    unknown_stage_emissions: int = 0
    ledger_ground_truth_disagreements: int = 0
    # Retroactive classification health (ADR-005). Counts, never a quotient: a miss
    # is judgment not yet made, an unknown is judgment that could not decide, and
    # both leave the run in `(unattributed)` rather than on a guessed stage.
    classification_boundaries: int = 0
    classification_cache_misses: int = 0
    classification_unknown: int = 0


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
    # Every point-release key carries a hyphen; the family rows do not. No version
    # heuristic is needed — a newly released model always brings a version suffix, so
    # "resolved to a bare family row" is exactly the R8 population.
    family_priced = family is not None and "-" not in family

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
        priced_with_family_row=family_priced,
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
    spans: SpanAttribution | None = None,
    inferred: ClassificationAttribution | None = None,
) -> EconomicsReport:
    report = EconomicsReport()
    if not turns:
        return report

    labels = classify_turns(turns)
    costs = [price_turn(t, fallback_model=fallback_model) for t in turns]
    estimates = estimate_attribution(turns, bounds)
    # Length mismatch is a caller bug, and an unchecked one surfaced as an IndexError
    # from deep inside the loop rather than as a description of what was wrong
    # (review M-14).
    for name, seq in (("spans", spans), ("inferred", inferred)):
        if seq is not None and len(seq.stages) != len(turns):
            msg = f"{name}.stages has {len(seq.stages)} entries for {len(turns)} turns"
            raise ValueError(msg)
    ledger_stages: Sequence[str | None] = (
        spans.stages if spans is not None else (None,) * len(turns)
    )
    capped_set = set(spans.capped_indices) if spans is not None else set()
    if spans is not None:
        report.ambiguous_session_join = spans.ambiguous_session_join
        report.unknown_stage_emissions = spans.unknown_stage_emissions
    inferred_stages: Sequence[str | None] = (
        inferred.stages if inferred is not None else (None,) * len(turns)
    )
    if inferred is not None:
        report.classification_boundaries = inferred.boundaries
        report.classification_cache_misses = inferred.cache_misses
        report.classification_unknown = inferred.unknown

    unknown: Counter[str] = Counter()
    family_priced: Counter[str] = Counter()
    unattributed_usd = 0.0
    estimated_usd = 0.0
    writing_turns = 0
    resolvable_writing_turns = 0

    for idx, (turn, cost, label, est) in enumerate(
        zip(turns, costs, labels, estimates, strict=True)
    ):
        report.turns += 1
        report.total_usd += cost.total_usd
        report.cache_read_usd += cost.cache_read_usd
        report.work_usd += cost.cache_write_usd + cost.output_usd

        # ADR-001 precedence ladder: direct > ledger > inferred > adjacency > none.
        # Exactly one wins, so the source axis partitions the turns.
        ledger_stage = ledger_stages[idx]
        inferred_stage = inferred_stages[idx]
        if idx in capped_set:
            # ADR-003 makes the cap TERMINAL: turns past it stay unattributed. The cap
            # leaves `ledger_stages[idx] = None`, which is indistinguishable from "no
            # span claimed this turn", so `inferred` and `adjacency` would happily pick
            # the turn up — and it would then be reported as BOTH capped and
            # attributed (review F-03). Ground truth still wins: a turn carrying its
            # own `attributionSkill` is not a guess, so the cap does not suppress it.
            inferred_stage = None
            est = None
        if turn.attribution_skill is not None:
            source = "direct"
            resolved_stage = turn.attribution_skill
            if ledger_stage is not None and ledger_stage != turn.attribution_skill:
                # The ledger's health signal: 44.1% of turns carry ground truth, so a
                # silently-broken emitter shows up here rather than nowhere.
                report.ledger_ground_truth_disagreements += 1
        elif ledger_stage is not None:
            # ADR-009: a sidechain turn nests into the enclosing stage span. It still
            # appears on `by_agent` below — that cross-cut is intentionally unchanged.
            source = "ledger"
            resolved_stage = ledger_stage
        elif inferred_stage is not None:
            # Retroactive, and labelled as such: the breakdown keeps the inferred
            # population non-comparable with the measured one by construction.
            source = "inferred"
            resolved_stage = inferred_stage
        elif est is not None:
            source = "adjacency"
            resolved_stage = UNATTRIBUTED
        else:
            source = "none"
            resolved_stage = UNATTRIBUTED

        report.turns_by_attribution_source[source] = (
            report.turns_by_attribution_source.get(source, 0) + 1
        )
        report.usd_by_attribution_source[source] = (
            report.usd_by_attribution_source.get(source, 0.0) + cost.total_usd
        )
        if idx in capped_set:
            report.capped_turns += 1
            report.capped_usd += cost.total_usd

        if resolved_stage == UNATTRIBUTED:
            # ADR-013: decompose on fields that EXIST on a turn. Gating on
            # `resolved_stage` rather than on `source` is what makes conservation with
            # `by_stage[UNATTRIBUTED]` structural instead of incidental — the same
            # condition selects both populations.
            #
            # The cap already forced `est = None` above, so `idx not in capped_set`
            # guards only the `preceded_by_user` arm. That arm needs the explicit
            # guard: the cap is terminal, and user-adjacency must not re-open it.
            recoverable = idx not in capped_set and (est is not None or turn.preceded_by_user)
            key = "recoverable" if recoverable else "unrecoverable_in_window"
            bucket = report.unattributed_breakdown.setdefault(key, UnattributedBucket())
            bucket.turns += 1
            bucket.usd += cost.total_usd

        _accumulate(report.by_stage.setdefault(resolved_stage, StageTotals()), turn, cost, label)
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
        if cost.priced_with_family_row:
            report.family_priced_turns += 1
            family_priced[turn.model or "(none)"] += 1

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
    report.family_priced_models = dict(family_priced)
    if UNATTRIBUTED in report.by_stage:
        # A partition names all of its parts, including an empty one, and in a fixed
        # order — but only once there is something to partition.
        report.unattributed_breakdown = {
            key: report.unattributed_breakdown.get(key, UnattributedBucket())
            for key in ("recoverable", "unrecoverable_in_window")
        }
        report.unattributed_breakdown_notes = list(_UNATTRIBUTED_BREAKDOWN_NOTES)
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
    from harness_maker.run_classify import (
        attribute_runs,
        boundary_inputs,
        find_boundaries,
        read_verdicts,
        verdict_cache_path,
    )
    from harness_maker.stage_spans import attribute_turns, ledger_path, read_events

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
    # Both attribution sources are read here rather than in `aggregate`, which stays
    # pure. An absent ledger or an absent verdict cache is the normal case on a fresh
    # clone: both readers return empty and the report falls back to adjacency exactly
    # as it did before either existed.
    events, _ledger_diag = read_events(ledger_path(root))
    spans = attribute_turns(
        result.turns, events, max_turns=cfg.span_max_turns, max_min=cfg.span_max_min
    )
    verdicts, _verdict_diag = read_verdicts(verdict_cache_path(root))
    # Both entry points derive these through ONE helper (review R2-02): building them
    # separately is how `boundaries` and `report` came to disagree about capped turns
    # and therefore about boundary UUIDs, silently discarding recorded verdicts.
    stages, capped = boundary_inputs(result.turns, spans)
    inferred = attribute_runs(
        result.turns,
        find_boundaries(result.turns, already_attributed=stages, capped=capped),
        verdicts,
        max_turns=cfg.span_max_turns,
        max_min=cfg.span_max_min,
    )
    report = aggregate(
        result.turns,
        bounds=bounds,
        idle_gap_cap_min=cfg.idle_gap_cap_min,
        fallback_model=cfg.price_model,
        spans=spans,
        inferred=inferred,
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


def _cmd_composition(root: Path, transcript_root: Path | None) -> int:
    """What the context is carrying, as opposed to what it cost (PLAN ADR-001/005).

    Shares the reader's discovery + project-boundary rules rather than re-deriving them;
    four scratchpad scripts each re-implemented transcript iteration and that is the
    reproducibility hole this subcommand exists to close.
    """
    from harness_maker.context_composition import compose
    from harness_maker.economics_source import (
        default_transcript_root,
        discover_transcript_dirs,
        resolve_project_root,
    )

    resolved = transcript_root or default_transcript_root()
    project = resolve_project_root(root)
    _print_json(compose(discover_transcript_dirs(project, transcript_root=resolved), project))
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

    p_comp = sub.add_parser("composition", help="what the carried context is made of, as JSON")
    add_common(p_comp)

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
    if args.command == "composition":
        return _cmd_composition(root, transcript_root)
    return _cmd_doctor(root, transcript_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
