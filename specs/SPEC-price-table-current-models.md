---
type: spec
task_slug: price-table-current-models
status: approved
created: 2026-11-16
tags: [correctness, cost, economics, bench, intent-metric]
test_framework: pytest
interview_rounds: 0
intent: HM-LIGHT-LANE
summary: The price table gets rows for Sonnet 5.5, Fable 5.2 and Haiku 5.5, a point release that falls back to an older row leaves a trace, and the recorded tier-1 cost ratio and the published "subagent spend" explanation are corrected (7.563 was 6.984).
---

# SPEC — price-table-current-models

## Intent

`economics.PRICE_TABLE` matches a model id by substring, longest key wins. It has no row for
`sonnet-5-5`, so the bench model `claude-sonnet-5-5` resolves to `sonnet-5` and its cache reads are
priced at $0.20 per million tokens. The published rate for Sonnet 5.5 is $0.10. Nothing shows this:
the existing trace (`family_priced_turns`) fires only when an id lands on a bare family row such as
`opus`, and `sonnet-5` carries a hyphen. `fable-5-2` and `haiku-5-5` have the same gap
(`fable-5-2` resolves to `fable-5` at 10/50 with a $1.00 read against a published 8/40 and $0.20;
`haiku-5-5` resolves to the Haiku 3 row).

The bench judges `hm_cost_ratio_small` on the larger of two ratios, the CLI total and the
transcript price, and the published text explained the gap between them as "the CLI total leaves out
subagent spend". The recorded rows refute that. In all 179 recorded rows that carry both numbers
(`docs/evals/results.jsonl`, the three `history/` files, both tier-3 sets),
`transcript_cost_usd − cache_read × $0.10/Mtok` equals `cli_cost_usd` within 0.5% (178 within 0.2%),
and all 79 rows with subagent turns are inside that bound (their largest residuals are 0.50%, 0.13%
and 0.04%; rows without subagents stay under 0.001%). The CLI total includes subagent spend;
the whole gap was the cache-read rate. Because hm runs read far more cache than plain runs, the
wrong rate inflated the hm side: the recorded 7.563 is 6.984, and p4's 10.243 was 9.437 (weekly
research 2026-11-16, HR-021; recomputed for this SPEC from the committed rows).

Rates used here were read from the published pricing page on 2026-11-16 (USD per million tokens:
input, 5-minute cache write, 1-hour cache write, cache read, output):

| model | input | write 5m | write 1h | read | output |
|---|---|---|---|---|---|
| Sonnet 5.5 | 2 | 2.50 | 4 | 0.10 | 10 |
| Fable 5.2 | 8 | 10 | 16 | 0.20 | 40 |
| Haiku 5.5, prompt ≤ 100,000 tokens | 0.10 | 0.125 | 0.20 | 0.01 | 0.50 |
| Haiku 5.5, prompt > 100,000 tokens | 0.50 | 0.625 | 1 | 0.05 | 2.50 |

A request's prompt length counts all of its input tokens, cache reads and cache writes included.

## Outcomes

- Turns of the three current models are priced at their published rates.
- A point release that has no row of its own is priced as before and is listed in the report.
- The recorded metric, the published results and the text that explains them say what the rows show.

## In-Scope Scenarios

- S1 (normal): a transcript turn of `claude-sonnet-5-5`, `claude-fable-5-2` or `claude-haiku-5-5`
  (with or without a date or `[1m]` suffix) is priced from its own row, with no trace.
- S2 (edge): a Haiku 5.5 request whose prompt is over 100,000 tokens is priced on the long-prompt
  card; at exactly 100,000 it is priced on the base card.
- S3 (edge): `claude-sonnet-5-6`, released after this table, resolves to `sonnet-5`, is priced at
  that row, and appears in `family_priced_models`. A date suffix (`claude-sonnet-5-20260601`) does
  not. A bench run counts such turns in its row (`family_priced_turns`) and warns.
- S4 (unchanged): every id the table already had a row for is priced exactly as before.
- S5 (record): the 30 committed tier-1 rows carry the transcript price under table 4, the old value
  stays in the row, and `summarize` gives 6.984, met.
- S6 (text): the verdict text, the tier-3 cost note and the docs no longer say the CLI total leaves
  out subagent spend.

## Non-Goals

- Re-running the bench. No new run is needed: the correction is exact from the recorded token counts.
- Repricing `docs/evals/history/*.jsonl` and the tier-3 rows. They are frozen records that older
  SPECs' bar tests read (`RECORDED_MISS` in p3, the p2 and p4 bars); the docs state they were priced
  with table 3 and give the corrected ratios.
- Editing `specs/SPEC-hm-eval-tier3.machine.yaml`. Its AC-010 golden row quotes the old cost note.
  Changing it would void the DRI's approval stamp on that SPEC; AC-007 here supersedes the sentence
  and the tier-3 SPEC's prose points to it.
- A general prompt-length tier mechanism for other models, and a table that loads rates from a file.
- Refusing to mix price tables in one bench `--out` (`MIXED_FIELDS`), and changing the verdict rule
  when a run has family-priced turns. The row records both facts; what to do with them in the
  pre-registered rule is the DRI's decision.
- The released 0.65.4 CHANGELOG notes.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| `ModelPrice` shape | unchanged (strict, five rates) |
| report fields | no new field: the trace reuses `family_priced_turns` / `family_priced_models` |
| rate of an id that falls back | unchanged; only its visibility changes |
| recorded rows | `cli_cost_usd`, `cost_usd`, tokens and every other field untouched |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: current models are priced at their published rates
A turn of 10,000 tokens of each type (input, output, cache read, 5-minute write, 1-hour write) costs
$0.186 on `claude-sonnet-5-5`, $0.742 on `claude-fable-5-2` and $0.00935 on `claude-haiku-5-5`, with
or without a date or `[1m]` suffix, and none of them is marked as fallback or family priced.
- oracle_source: golden. The expected dollars are computed by hand from the published rates above.

### AC-002: Haiku 5.5 switches to the long-prompt card above 100,000 prompt tokens
Prompt length is input + cache read + both cache writes. At 100,000 the base card applies; at
100,001 the long-prompt card applies to every token type of that request. Sonnet 5.5 has one card at
any length.
- oracle_source: golden. Hand-computed from the published two-tier rates and the published rule on
  what counts as prompt length.

### AC-003: ids that already had a row are priced as before
`claude-sonnet-5`, `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-4-5-20251001`,
`claude-opus-4-1-20250805`, `gpt-4` (fallback) and the other ids in the golden table cost the same
as before this change for the same 10,000-token turn. That includes a dated Fable 5 id
(`claude-fable-5-20260401`), which the new `fable-5-2` key must not capture.
- oracle_source: golden. The rows were computed from the table at origin/main 0ccfcf09.

### AC-004: a point release without its own row leaves a trace
A turn whose id continues with one more version number right after the matched key
(`claude-sonnet-5-6`, `claude-fable-5-3`, `anthropic/claude-opus-5.6`) or lands on a bare family row
(`claude-haiku-5-6`) is marked family priced and its id
appears in the aggregated report's `family_priced_models`. An id with its own row, a date suffix,
`@date` or `[1m]` is not marked. `claude-opus-9` is still marked and `gpt-4` is still the fallback
signal only.
- oracle_source: golden. The expected marks follow from the stated rule; the first three rows are
  the failure HR-021 reported (a versioned id priced by an older row with no signal).

### AC-005: the table is version 4
`PRICE_TABLE_VERSION` is `"4"`, the effective date is `2026-11-16`, and an aggregated report carries
both.
- oracle_source: property.

### AC-006: the recorded tier-1 rows agree with the CLI and give 6.984
Every row of `docs/evals/results.jsonl` has `price_table_version` `"4"`, keeps its former transcript
price under `transcript_cost_usd_table_v3`, has `transcript_cost_usd` equal to that value minus
`cache_read × 0.10 / 1e6` (to the row's 6 decimals), and is within 0.5% of `cli_cost_usd`.
`summarize` over the rows gives verdict `met` and ratio 6.984.
- oracle_source: golden. `cli_cost_usd` is what the host billed, recorded on 2026-11-10 and not
  produced by the price table; 6.984 was computed from those rows before the change.

### AC-007: the published text says the CLI total includes subagent spend
The tier-3 cost note in the rendered RESULTS.md section and README block says the CLI cost includes
subagent spend and no longer says it excludes it or that an hm $ understates the run. When
`summarize` returns `suspect` for a CLI/transcript gap, its reason names the price table, not
subagent spend. The committed `docs/evals/RESULTS.md` and README block equal what `publish` renders
from the committed rows.
- oracle_source: golden. The claim is settled by the 79 recorded subagent rows (Intent), not by the
  code that prints the note.

## Verification

| scenario | mode | test |
|---|---|---|
| S1 | unit | AC-001 |
| S2 | unit | AC-002 |
| S3 | unit | AC-004 |
| S4 | unit | AC-003, existing `tests/unit/test_economics_pricing.py` |
| S5 | integration (committed data) | AC-006, `tests/integration/test_hm_cost_p5_bar.py` (the SPEC result line equals `summarize`) |
| S6 | unit (render) | AC-007 |
| version | unit | AC-005 |

AC-003 is green before any code: it pins behaviour that must not move.

## Open Questions

none

## Refinement Decisions

- Approval (DRI, 2026-11-16): the DRI picked "둘 다 고치기" on the weekly research card for HR-021 and
  HR-022, under the standing instruction of 2026-11-10 13:26Z. The SPEC is approved on that; no
  further card.
- Default (agent): the trace reuses `family_priced_turns` / `family_priced_models`. The existing
  fields mean "priced by a row that is not this model's own"; a second pair of fields for the same
  meaning would give every reader two places to look. Cost to undo: one expression in `price_turn`.
- Default (agent): the rule for "a further version number" is the text right after the matched key:
  a hyphen, one or two digits, then no digit. Dates (8 digits, or `-2026-…`), `@date` and `[1m]` do
  not match. A model that brings a three-digit version would be missed; none exists.
- Default (agent): Haiku 5.5's long-prompt card is a second table keyed by row name with its
  threshold, applied in `price_turn`. `ModelPrice` keeps its shape. Only Haiku 5.5 publishes such a
  tier today.
- Default (agent): only `docs/evals/results.jsonl` is repriced, by the exact formula, with the old
  value kept in the row (the tier-3 plain-continue correction of PR #35 did the same). History files
  stay as recorded. New runs stamp `price_table_version` in each row so a later table change is
  visible in the data.
- Default (agent): the metric gets a new record (6.984) with evidence that names the correction; the
  7.563 record stays in `metrics.yaml` as history.
- Default (agent): corrected ratios stated in the docs, all CLI-equal after the fix: p2 11.04
  (was 12.21), p3 10.27 (was 11.36), p4 9.44 (was 10.24), p5 6.98 (was 7.56). The spec-validator
  A/B: tier 1 9.44 against 7.00 without the step, tier 2 9.36 against 7.61.
- Default (agent): no irreversible decision. Rates and a label change; every recorded value that is
  replaced stays readable.
- Default (agent): spec-validator skipped (7 live ACs; `validator: skip`).
- Correction (agent, after review): the new `fable-5-2` key is a substring of
  `claude-fable-5-20260401`, so a dated Fable 5 turn moved to the 5.2 card with no trace. A key that
  ends in a digit now does not match right before another digit (`economics.model_key_end`; bare
  family keys keep plain substring matching), and `cache_diagnostics` uses the same function so the
  two tables keep one matching rule. The only ids whose result changes are ones where such a key is
  directly followed by a digit; no dated, `[1m]`, `@date` or Bedrock id is among them. An older PLAN's ADR-002 kept substring
  matching so that dated ids resolve; they still do. AC-003 gained the dated rows. Re-approved on the
  standing instruction above.
- Correction (agent, after review): the bench row gains two keys, `price_table_version` and
  `family_priced_turns`. The exact key set of a tier-1/2 row is pinned by tests bound to
  SPEC-hm-eval-tier3 AC-007 and SPEC-hm-eval-scripted-dri AC-007; both pins are widened by these
  two keys and still pin the exact set.
- Source note: the tier-2 figures (9.36 and 7.61) come from the 63 spec-validator A/B rows kept in
  the project files (`hm-cost-research/spec-validator-ab-tier2-2026-11-10.jsonl`), not in this
  repository, so the repository cannot reproduce them. The figures they replace (10.24 and 8.42) had
  the same source.
- The version rule also accepts a dot (`claude-opus-5.6`).
