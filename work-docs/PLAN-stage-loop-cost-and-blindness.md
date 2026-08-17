---
type: plan
task_slug: stage-loop-cost-and-blindness
status: draft
created: 2026-08-17
spec: null
research_doc: null
tags: [harness-maker, plan, observability, latency, review-loop]
summary: "Give the review record a producer that cannot skip it, and cut the mandated sequential CLI calls that dominate wall time"
---

# PLAN — stage loop: cost and blindness

Two defects that look unrelated and are the same shape: **a thing the harness
declares, and nothing produces.** One costs measurement (the review record), the
other costs an hour a session (the mandated call sequence). Both were surfaced by
measuring rather than by reading code, and neither is visible to any existing test.

## 📐 Measurements this plan is built on

Taken 2026-08-17 across `~/spoton`, `~/strange_chess`, `~/neuroTerm`,
`~/harness-maker`. Re-derive before acting on any number here — none of it is
pinned by a test yet, which is itself part of the problem.

| Fact | Value | Source |
|---|---|---|
| review telemetry rows carrying `churn_ratio` | **0 of 123** | `review-*.jsonl`, 4 repos |
| multi-round slugs whose later rounds found nothing | **16 of 22 (73%)** | `consensus_passed_n` by round |
| median session | **60 min / 158 tool calls** | `metrics-*.jsonl`, gap>30min sessionization, n=219 |
| sessions ≥ 2 h | **73 of 219 (33%)** | same |
| Bash share of measured wall time (all time) | **203.9 h of 304.3 h — 67%** | inter-call gaps <10 min |
| Bash share of tool calls (today only) | **5,481 of 7,828 — 70.0%** | 2026-08-17 |
| median gap after a Bash result | **3.4 s (today) / 7.8 s (all time)** | this is LLM turn latency, not execution |
| subagent share of wall time (today) | **1.13 h of 16.07 h — 7%** | Agent + spawn_agent + wait/close |
| harness CLI share of Bash calls | **8–9%** | `uv run --with` substring |
| `!` calls the four main stages MANDATE | **78** (review 21, execute 15, wrapup 28, plan 14) | rendered `.claude/commands/hm/*.md` |

**The two conclusions that decide the phases.** Cost is *number of sequential
main-loop tool calls × turn latency* — not subagents (7%), not the harness's own
CLI (8% of Bash). And the review loop cannot be tuned from evidence, because the
field the tuning would read has never been written.

## 🧭 ADRs

### ADR-001 — the telemetry producer moves from prose into the CLI

`review.md.j2:806` tells the model to "carry the four `churn_*` keys verbatim"
from Step 5b to the `emit` call at :1068 — **262 lines and roughly 15 tool calls
later**. It has never happened, in any repository, in any round.

`emit` gains `--churn-slug <slug> --churn-round <N>`. The churn ref names are
deterministic (`refs/hm-churn/v1/<slug>-r<N>-{pre,post}`), so Python re-derives
them, calls `measure_refs`, and writes the four keys itself.

**Model-supplied churn values are ignored, not merged.** A merge keeps the bug
alive in exactly the case that matters — the model supplies something plausible
and wrong, and the row validates.

### ADR-002 — the absent case must be loud

Today all four keys default to `None` and `_churn_record_is_readable` is
satisfied by all-None, so a row with no churn data is indistinguishable from a
round where nothing was measurable. That is the count:8 failure class verbatim:
a feature that activates on an optional field and silently no-ops when absent.

Add `churn_source: "measured" | "refs-absent" | "not-requested"`, required. The
black hole becomes a value you can group by.

### ADR-003 — a round that never reported is invisible, and that is a separate defect

In this repository's own 2026-08-17 review, **round 2 emitted no telemetry row at
all**. Every existing gate inspects rounds that appear in the ledger, so a round
that never reported cannot be caught by any of them. Gate: for a given slug and
run, emitted rounds must be contiguous `1..N`. A hole is a red test naming it.

### ADR-004 — `terminal` is a fact about the last row, not a field the model fills

Both rows of that same review carry `terminal: true`. Only round 3 was terminal.
`emit` should derive it, or the contiguity gate above should reject a second
terminal row for one slug+run.

### ADR-005 — batching follows the precedent already in the tree, not a new invention

`wrapup_land` already collapsed Steps 6, 7, 7.5 and 7.6 into **one** call
returning a structured JSON receipt with per-step dispositions. That is the
pattern: a composite call is acceptable **only** when it returns a receipt that
says what each step did, because otherwise a failure inside a batch is a single
opaque non-zero exit. Generalize that, do not improvise a different shape.

### ADR-006 — do not batch across an LLM decision point

A run of consecutive `!` calls is collapsible only when no step between them
requires the model to read a result and choose. Step 7.7 (`task-land`) is
deliberately outside `wrapup_land` for exactly this reason — it is the only step
that can lose work, so it keeps its own invocation and its own operator decision.
Batching must preserve every such seam; the inventory in Phase 3 classifies them
before anything is merged.

### ADR-007 — measure the win, or do not claim it

The baseline above is reproducible from `metrics-*.jsonl`. Phase 4 re-runs the
same computation after batching and reports the delta in mandated calls and in
median session tool count. A refactor that reduces the mandated count but not the
observed count has not paid for its risk.

## 📝 Implementation plan

### Phase 1 — churn producer (ADR-001, ADR-002)
- **Scope**: `src/harness_maker/review_telemetry.py`, `review_churn.py`,
  `templates/stages/review.md.j2` (Step 5b/emit prose), tests.
- **Exit**: `emit --churn-slug X --churn-round N` writes the four keys from the
  refs with `churn_source: measured`; absent refs yield `refs-absent`, never
  silent None; a test proves a model-supplied churn value in the input JSON is
  overwritten, not merged.
- **Risk**: low. Additive flags; the stdin path is unchanged.
- **Rollback**: revert; rows go back to all-None.

### Phase 2 — round contiguity + terminal (ADR-003, ADR-004)
- **Scope**: a structural test beside `test_review_payload_persisted.py`;
  `emit` derives or validates `terminal`.
- **Exit**: a slug with rounds {1,3} is red and names the hole; two terminal rows
  for one slug+run is red.
- **Risk**: medium — this repository's existing ledger already violates it. The
  waiver list pattern already in `test_review_payload_persisted.py` is the
  precedent for grandfathering, with a written reason per entry.
- **Rollback**: delete the test.

### Phase 3 — inventory and classify the 78 mandated calls (ADR-006)
- **Scope**: read-only. Produce a table: stage, call, what it needs from the
  previous result, collapsible-with-next yes/no, and why.
- **Exit**: every one of the 78 is classified; the collapsible runs are named
  with their lengths. **No template edited in this phase.**
- **Risk**: none — nothing changes.

### Phase 4 — collapse the independent runs (ADR-005, ADR-007)
- **Scope**: the runs Phase 3 marked collapsible; one composite CLI per run,
  each returning a `wrapup_land`-shaped receipt.
- **Exit**: mandated `!` count drops; every composite returns per-step
  dispositions; the stage still halts at every seam Phase 3 marked non-collapsible;
  the metrics re-measurement from ADR-007 is recorded.
- **Risk**: **high** — this touches every stage template, and a batch that hides
  a failed sub-step is worse than the latency it saves. Land one stage at a time.
- **Rollback**: per-stage; each composite is additive until the prose switches.

### Phase 5 — recalibrate the threshold from real rows (depends on Phase 1)
- **Scope**: none until rows accumulate. `DEFAULT_CHURN_RATIO` was moved 0.20 →
  0.30 on 2026-08-17 as a *second estimate*, explicitly not a recalibration.
- **Exit**: enough rows with `churn_source: measured` to correlate ratio against
  next-round yield, then set the number from that correlation.

## ⚠️ Risks carried

- **R1** — Phase 4 is the only phase whose failure mode is silent. A composite
  that reports `ok: true` while a sub-step did nothing is the exact shape that
  let `wrapup_land` commit the PLAN alone twice while reporting success. Every
  composite needs an `index_after`-equivalent: a field showing what actually happened.
- **R2** — The 73%-yield figure comes from `consensus_passed_n`, which is
  LLM-assembled like everything else in that row. It is the best evidence
  available and it is not independent of the defect Phase 1 fixes.
- **R3** — Turn latency (3.4–7.8 s) is not under this project's control. If the
  mandated-call reduction is small, the session length will barely move; that is
  a reason to do Phase 3 before committing to Phase 4, not a reason to skip it.
