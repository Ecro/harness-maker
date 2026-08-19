# BASELINE-DELTA — three review-loop fixes from the 230-run experiment re-audit

**Date:** 2026-08-19 · **Owner:** the review-loop-ledger re-audit (ADR-010's attribution document).

## What moved

Measured with `tests/structural/_surface_baseline.py` after the trim described below, not before.

| Key | Was | Now | Δ |
|---|---|---|---|
| `review` (claude) `chars` | 84 690 | **86 599** | +1 909 |
| `hm-review` (codex) `chars` | 80 002 | **81 911** | +1 909 |
| `aggregate_chars.claude` | 427 300 | **429 209** | +1 909 |
| `aggregate_chars.codex` | 360 211 | **362 120** | +1 909 |
| `review` / `hm-review` `round_trips` | 37 / 33 | **37 / 33** | **0** |

`round_trips` is flat on purpose: all three changes are rules applied inside steps that already
run. Nothing here adds a mandated call, so the axis that has no ratchet direction does not move.

The per-command atomic ceiling (`test_command_size_budget`, flag-on render) needs **631**; the
aggregate needs **1 909**. Both are declared in `PLAN-review-loop-ledger-fixes.md`.

## The four rows

**1. `disposition_counts` on the telemetry row (+~500).** ADR-002's disposition gate shipped
with no measurement surface. `review_consensus.finalize` writes nothing — it returns the
dispositions on stdout — and the ledger's per-finding disposition rows are a closed enum of
second-opinion vendors, so a reviewer-lens disposition had no value that would name it. Its only
record was REVIEW prose. The consequence is not cosmetic: the **rejection rate is the number
ADR-002 exists to move** (the source experiment measured 0% when rejection was optional against
20–26% when it was forced) and it could not be read off disk at all.

The characters are the field name in the record list plus four lines: copy it rather than tally
it, all four keys always present, never null. The Python half is free of this budget —
`finalize` now returns `disposition_counts` beside `counts`, and a nullable `dict[str, int]` on
the record validates against `codex_ledger.DISPOSITION_VALUES`, the frozenset `review_consensus`
already imports, so the vocabulary has one source. Counts only. The per-finding record stays Step 8's iteration table,
which is what AC-006's completeness invariant reads.

> **This is deliberately NOT a new persisted artifact.** `review-payloads/` already exists and
> already looked like the place; it is not. It snapshots at Step 3.4, **before** Step 4d/4e assign
> tag and disposition, and `persist_payload`'s docstring pins it as a verbatim un-parsed replay
> corpus. Reading those files as the gate's output is what produced a "2.1% rejection rate" during
> this audit — a number measured against a store the gate never writes to.

**2. Reachability before the revert diagnosis (+~690).** The auto-fix loop's build-failure branch
reverted the last fix and logged `caused build failure`, unconditionally. The added rule asks one
question first — can production reach the state the failing assertion pins — and **reverts either
way**; the answer changes the record, not the action. When the state is unreachable the fix broke
no behaviour, so the old log line was a false diagnosis of a test that over-specifies; it now logs
`test pins unreachable state` and carries one `manual-only` P1 `spec_gap`, on the same never-
grade-lowering footing as an oscillation.

Reverting regardless is what keeps this cheap and safe: an unreachable-state guard is a no-op, so
reverting it costs nothing real, and the loop never leaves the tree red. It also cannot become a
licence to edit tests — the existing ban is untouched and the new branch grants no authority.

The source experiment reached "AI fixes cause regressions, 4/4 reproduced" one step from
publication on exactly this: four independent runs broke the same four tests, the code was never
broken, and the finding behind the guard was later adjudicated a false positive.

**3. P2 out of the auto-fix queue (+~720).** Selection was `P0, P1, or P2 (skip P3 unless D or F)`;
it is now `P0 or P1`, with P2/P3 restored at D or F. P2/P3 cannot move the grade — the grade rule
three sections above counts `consensus-passed` P0/P1 only — so every P2 the fixer applied was
churn against a gate structurally unable to read it. The adjudicated split of a comparable finding
set was 31% real against 69% naming, comments and structure: accurate, and mostly not worth a
round trip.

The exposure is new rather than longstanding. The four-lens merge folded `naming` into
`consistency` and that is what made this volume reachable; `RESEARCH-review-loop-empirics.md`
predicted it in as many words ("Adding those lenses without a routing decision buys report volume
and zero gate signal"), the lenses landed, and the routing decision did not.

**No deadlock.** A P2-only finding set cannot reach the auto-fix loop: zero `consensus-passed`
P0/P1 is grade A, so the gate approves before the loop is entered. The progress invariant is
therefore never evaluated against a round whose only candidates were just made ineligible.

**4. The measured fields stop passing through the model (net +1).** Row 1 shipped the same defect
it was written to fix, and the ledger already had the receipt. `ReviewTelemetryRecord`'s measured
fields are nullable and the row is assembled by the model from prose; on this repository's own 69
rows, `churn_ratio` 0/69, `churn_measured_n` 0/69, `lenses_exercised` 0/69, `confirm_pass_ran`
0/69 — while all **nine required** fields were present in every row. A schema optional is a prompt
optional, and "always, per round" does not survive it. `review_churn.DEFAULT_CHURN_RATIO` is what
that costs: a live gate threshold set from a second estimate because the recalibration data never
arrived across four repositories and 123 rows.

So `round_record.py` gives each round a scratch file that the producers write and
`review_telemetry emit` reads. `finalize` and `review_churn measure` gain `--slug`/`--round`
(optional, so every existing caller is unaffected), and `emit` **strips** the measured keys from
the model's row and takes them only from the record — a supplied value is discarded and reported
as drift. Both anomalies go to stderr and neither is fatal: a review must not fail over telemetry.

Stripping rather than defaulting is the load-bearing choice. "Use the model's value when the
record is empty" restores the field to optional, which is the entire defect. `emit` needs no new
argument — it derives the record path from the row's own required `slug`/`round`, so a path that
does not match the row it lands on cannot be passed.

The surface cost is **+1 net**: the producer flags cost ~104 characters and the transcription
instructions they delete nearly pay for them. `finalize()` and the churn measurement stay pure —
both writes live in the CLI layer, which already did IO.

## Direction

**Larger**, and it is a trade, not a correction. The first draft measured **+2 516** per variant;
compressing all three blocks to the facts that change a reader's decision brought it to +1 861;
moving the counts onto `finalize`'s payload then added the `copy it, never tally it yourself`
rule and took it to +1 975, and a further rationale cut landed it at **+1 908**. Both cuts
happened before this number was taken — per this repo's own rule that prose is cut
back before a ceiling is raised.

Whether the trade pays is measurable for row 1 in a way it is not for rows 2 and 3 — but only
because of row 4. Before it, `disposition_counts` would have joined the 0/69 club; the honest
prediction now is that the next review's row carries it, and that is checkable on the first run. Rows 2 and 3 change what a round
*reports* and what it *skips*; the evidence for both is a re-audit, not a counter.

## Why only this document may move these numbers (ADR-010)

The ratchet's subject is the prompt surface and the failure mode is
`ratchet-rebaselined-by-its-own-subject`: the change that grows the surface also holds the pen, so
regenerating the baseline is always the cheapest way to green and erases the evidence in the same
stroke. This row is the price of the regeneration.
