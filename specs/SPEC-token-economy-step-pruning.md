---
type: spec
task_slug: token-economy-step-pruning
status: draft
created: 2026-07-27
tags: [harness-maker, spec, python, token-economy, prompt-caching, observability, render]
tier: 2
test_framework: pytest
research_doc: "[[RESEARCH-token-economy-step-pruning]]"
summary: "Correct the billing model, compact fused commands under a ratchet, bound reviewer reads without touching verification"
---

# SPEC — Token economy correction and stage-prompt compaction

## 🎯 Intent

Measured over 30 days on this repo (`harness_maker.economics`, 20,480 turns,
ingestion coverage 1.0), **65.6% of spend is cache-*read* cost** — the price of
re-reading carried context, not of cache misses. The instrument that reports this
is itself miscalibrated in two verifiable ways, and the largest remaining
prompt-side lever — fused-command compaction — was explicitly deferred by
`PLAN-workflow-overhead-post024` and never picked up.

The trigger for this work was the hypothesis that `/hm:plan` has too many Steps.
Measurement refutes it: `/hm:plan` is 5th at 7.7% of spend with the **lowest**
mean context (165K) and **lowest** carry (0.38) of any working stage. A `Step`
heading costs O(1) cached tokens; a Step that spawns a subagent or forces a tool
round-trip costs O(context) per turn. This SPEC therefore prunes by
turn-and-context production, and fixes the meter first.

## 🌅 Outcomes

After this change:

- `/hm:health` Layer 3 and `/hm:metrics` report cache and cost numbers that match
  published Anthropic figures for the models actually in use — **applied per turn
  through the production path**, not merely available from a resolver. Re-running a
  historical window after this change yields different dollars; the report's
  `price_table_version` is the signal that says why (PLAN ADR-003, ADR-012).
- No rendered command file exceeds a size ceiling that a test enforces, measured in
  **characters**, with a floor as well as a ceiling so an empty render cannot pass.
  `exec-rev-wrap-ver` lands at **≤ 119,000 characters** (from 121,782). A future
  template addition that inflates a fused command fails CI instead of shipping
  silently (PLAN ADR-014). The reduction is **4.7%, not the 12.0% an earlier draft
  claimed** — the documentation-only trim that supplied the other 7.2% was withdrawn
  once it was shown to delete runtime instructions (PLAN ADR-017).
- A reviewer's default read is bounded, while it retains an explicit, always-available
  path to read more. The number of reviewer passes, the reviewer set, and the
  consensus threshold are **provably unchanged**.
- `(unattributed)` spend is decomposed into a **recoverable** and an
  **unrecoverable-in-window** part on an observable predicate, conserving both
  turns and USD, so the remaining 28.9% is a number with a cause attached rather
  than an opaque bucket (PLAN ADR-013).

## 📋 In-Scope Scenarios

### AC-001: cache minimums resolve per model, preserving non-monotonicity

**Given** `cache_diagnostics` is asked for the minimum cacheable prefix of
`claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`,
`claude-haiku-4-5`, and `claude-sonnet-5`
**When** the resolver runs
**Then** it returns 512, 1024, 2048, 4096, 4096, and 1024 respectively
**And** the values are **not** monotonic within the `opus` family, proving the
resolution is per-model rather than per-family-prefix

### AC-002: an unknown model never produces a guessed threshold verdict

**Given** a turn whose `message.model` matches no entry in the known-minimums table
**When** the cache failure-mode classifier runs on it
**Then** the turn is **not** classified `miss_min_threshold`
**And** it is surfaced as an explicitly unknown/unclassified model rather than
silently priced against a default guess

### AC-003: current-model pricing is correct and the report declares its table version

**Given** the price table is asked for `claude-opus-5`
**When** a turn is priced
**Then** `input` is 5.0 and `output` is 25.0 USD per MTok, matching the published
rate
**And** `cache_read` is exactly `0.1 ×` input, `cache_write_5m` is `1.25 ×` input,
and `cache_write_1h` is `2.0 ×` input
**And** the emitted report's `price_table_version` differs from the pre-change
value, so a reader can tell which table produced the numbers
**And** a model matching no per-model key still resolves through the family
fallback rather than erroring

> **Scope correction (both second-opinion models, independently).** An earlier
> draft required that "a report generated against a prior `PRICE_TABLE_VERSION`
> still returns the numbers it returned before". That is not achievable and was
> not honest: `PRICE_TABLE_VERSION` is a **label emitted into the report**, not a
> dispatch key, and every report is recomputed from raw transcripts, so no stored
> historical artifact exists to preserve. Correcting any rate necessarily
> reprices old windows on re-run. Date-effective pricing would deliver real
> reproducibility but was declined as out of scope. The requirement is therefore
> reduced to what the system can actually guarantee — the report says which table
> produced it.

### AC-004: a 1-hour-TTL session is not misclassified as a TTL miss

**Given** two consecutive turns separated by 30 minutes in a session whose cache
entries carry the 1-hour TTL tier
**When** the cache failure-mode classifier runs
**Then** the second turn is **not** classified `miss_ttl`
**And** the same 30-minute gap under the default 5-minute tier **is** classified
`miss_ttl`

### AC-005: every rendered command is under a ratcheted size budget

**Given** the full render of this harness's commands
**When** the size-budget test runs
**Then** every rendered command file sits between its recorded floor and ceiling,
measured in characters (`len(read_text())`)
**And** the ceiling for `exec-rev-wrap-ver` is **≤ 119,000** — a ≥ 4.5% reduction
from its measured pre-change size of 121,782, not merely "less than 121,782"
**And** a deliberately inflated template makes the test fail, **and** an empty or
gutted render fails the floor (the ratchet is proven to bite in both directions)

### AC-006: shared prose renders once, per-stage command lines render per stage

**Given** the rendered fused workflow command for `exec-rev-wrap-ver`
**When** the worktree-preflight and Gate 0 receipt blocks are inspected
**Then** the **shared prose** of each renders exactly once, matched by content
fingerprint rather than by a bare occurrence count
**And** the **per-stage command line still renders once per stage** — all four
`--stage` values are present for Gate 0 (`execute`, `review`, `wrapup`,
`verify`) and for preflight (`hm:execute`, `hm:review`, `hm:wrapup`,
`hm:verify`)
**And** the Communication Protocol block is **out of scope** for this criterion

> **Corrected after measurement (PLAN ADR-016).** An earlier draft required all
> three blocks to appear "exactly once". Measured line-by-line against the
> committed render, they are not duplicates: preflight is 1,243 identical chars
> of 1,403; Gate 0 receipt is only 659 identical of 1,920 (heading, pass/fail
> criteria and `--stage` all vary); Communication Protocol is **40 identical of
> 349** and is per-stage by design. **One receipt per stage is the Gate 0
> missing-stage mechanism** — collapsing it would make the autoloop driver see
> three stages as missing every iteration. The original wording also contradicted
> AC-007, which requires the atomic `--stage wrapup` line to survive into the
> fused render.

### AC-007: compaction loses no instruction

**Given** the atomic command for each stage in a fused workflow, and the fused
command for that workflow
**When** the instruction sets are compared
**Then** every numbered Step / Phase / Check heading present in an atomic command
is reachable in the fused command
**And** every `!`-prefixed executable line present in an atomic command is present
in the fused command

### AC-008: reviewer reads are bounded, elision is visible, escalation is always available

**Given** the rendered review command
**When** the reviewer-dispatch instructions are inspected
**Then** they specify a bounded default read (the patch plus surrounding context)
rather than an unconditional end-to-end file read
**And** they state an explicit escalation clause permitting a full-file read when
the bounded read is insufficient for the reviewer's judgment
**And** they require any elision to be **visibly marked** in the delivered
content — a bounded read must never hand the reviewer a silently truncated file

> **Why the visibility clause is load-bearing (antigravity, P0).** An escalation
> clause is inert if the reviewer cannot tell it should fire. Truncation that
> leaves syntactically and semantically complete-looking content gives the
> reviewer no signal that context is missing, so the clause never triggers and
> the budget silently lowers recall — which would violate the verification
> non-goal despite the clause being present. Marking every elision restores the
> observation the escalation decision depends on.

### AC-009: the verification apparatus is provably unchanged

**Given** the rendered review command and reviewer configuration before and after
this change
**When** the verification structure is compared
**Then** the reviewer pass count is identical (Pass 1, Pass 1.5, Pass 2 all still
present when more than one reviewer is enabled)
**And** the enabled reviewer set is identical
**And** the consensus threshold is identical
**And** `plan-validator` and `second_opinion` invocation points are identical

### AC-010: unattributed spend is decomposed, not opaque

**Given** an economics report over a window containing unattributed turns
**When** the report is generated
**Then** the unattributed total is broken down into a **recoverable** part
(the turn has a neighbour stage resolvable within the configured adjacency
window, or carries `preceded_by_user: true` — the direct signature of the
documented cause) and an **unrecoverable-in-window** part
**And** the parts sum to the reported unattributed total **in both turns and USD**

> **Category framing corrected (PLAN ADR-013).** An earlier draft named the
> exempt part as "loop iterations, `feature_branch_workflow: false` harnesses,
> Cursor/Codex sessions". Checked against the data model, **none of the three is
> a per-turn property**, and two are not turn classifications at all: Cursor and
> Codex write no Claude Code transcripts, so those sessions never enter the
> report as turns, and `feature_branch_workflow` is a repository config. They are
> absences from the population, not members of it, and are reported as notes on
> the report rather than buckets in it. The buckets above are built on fields
> that exist on `TurnRecord`.

### AC-011: the metrics command renders the breakdown, not just computes it

**Given** a Production render of `commands/hm/metrics.md`
**When** Step 5d's prescriptive "Also surface, in one line each" list is read
**Then** it names `unattributed_breakdown` and both bucket keys, asks for `turns`
and `usd` per bucket, and instructs the reader to print
`unattributed_breakdown_notes` **verbatim**
**And** it does not restate the note prose inline, because those notes have exactly
one author (`economics._UNATTRIBUTED_BREAKDOWN_NOTES`) and a paraphrase would go
stale the first time that tuple is edited with nothing downstream to notice
**And** it does not instruct the reader to fold the breakdown into the per-stage
table — the split partitions `(unattributed)`, it does not attribute it (ADR-013)

> **Why this is a separate criterion from AC-010.** AC-010 proves the buckets are
> computed and conserve. It says nothing about whether anyone ever sees them.
> Step 5b already dumps the whole report JSON into the model's context, so the
> fields were never *dead* — but Step 5d's list is **prescriptive, not
> illustrative**: what it enumerates is what reaches the user's output.
> `metrics.md.j2` appeared **zero** times in the PLAN before Phase 5 was added,
> so as written no phase would ever have wired it — the global-CLAUDE.md
> 2026-06-08 absent-case pattern, a feature activating on a surface nobody owns.

## 🚫 Non-Goals

- **Weakening any verification apparatus.** Pass 1 / Pass 1.5 / Pass 2, the
  consensus filter and its threshold, `plan-validator`, and `second_opinion` are
  untouched — AC-009 exists specifically to enforce this. Re-opening the Pass 1.5
  decision is already a non-goal of `PLAN-workflow-overhead-post024`, and it is
  backed by a measured +47pp precision result.
- **Re-doing completed work.** Prompt `cache_control` on `llm_judge`, the HTTP
  cache, agent-quality / secscan fresh-skip, drift single-ownership, the
  verification cache, and Pass-1-skip-when-one-reviewer all shipped in
  `CLOSE-workflow-optimization-2026-05` and stay as they are.
- **Changing delegation scope.** `delegation.stages` currently holds `["wrapup"]`.
  Enabling `verify`, or extending delegation to any other stage, is a separate
  decision governed by the soak exit condition in
  `PLAN-economics-attribution-and-carry` ADR-011.
- **Switching `default_workflow`.** This harness runs the legacy
  `exec-rev-wrap-ver`; the canonical `exec-rev-ver-wrap` is not even defined in
  its `workflows:` map. Recorded as an Open Question, not changed here.
- **Running an `effort` sweep.** Appendix A of the RESEARCH document supplies the
  methodology, but harness-maker cannot set `effort` (its only request surface is
  `llm_judge.py`). Out of scope; see Open Questions.
- **Proving a measured token reduction in production.** Acceptance is mechanism
  plus a render-time budget. A real reduction can only be shown by a soak window,
  and wrapup delegation was enabled 2026-07-26, so the confounder is fresh.
- **Any change to `resolve_model_family`, the `estimate_attribution` adjacency
  path, or making `by_agent` a partition** — all explicit non-goals of
  `PLAN-economics-attribution-and-carry`, retained here.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md locks the toolchain; no per-task choice |
| Language / typing | Python 3.12+, `mypy --strict`, `ruff` | CLAUDE.md, non-negotiable |
| Template engine | `Jinja2` | Fused-command compaction is a template restructure |
| Pricing history | `PRICE_TABLE_VERSION` must be bumped; rows **may** be corrected in place | Amended per PLAN ADR-003. The version is a report label, not a dispatch key, and reports are recomputed from transcripts — the old "never edited in place" rationale asserted an invariant the architecture does not implement, and it would have blocked the Haiku 4.5 correction |
| Render determinism | `freeze_time` + `generated_at` masking | CLAUDE.md snapshot policy; AC-005/006/007 are render-output assertions |
| Size budget origin | Ratchet against measured **characters** (`len(read_text())`), not bytes and not a chosen constant | The budget number is not a value the user or author can meaningfully guess; deriving it from measurement makes it unfalsifiable-by-taste |
| Reviewer escalation | Bounded read must be a **default**, never a cap | Reconciles "bound reviewer reads" with "verification apparatus untouchable" — without escalation, a read budget silently lowers recall |

## ✅ Verification Criteria

| AC | Verification mode | Test name / manual step |
|---|---|---|
| AC-001 | unit | `tests/unit/test_cache_minimums_per_model.py::test_min_cacheable_is_per_model_and_non_monotonic` |
| AC-002 | unit | `tests/unit/test_cache_minimums_per_model.py::test_unknown_model_never_min_threshold` |
| AC-003 | unit | `tests/unit/test_economics_pricing.py::test_opus5_rate_and_versioned_history` |
| AC-004 | unit | `tests/unit/test_cache_minimums_per_model.py::test_one_hour_ttl_not_miss_ttl` |
| AC-005 | unit (render) | `tests/structural/test_command_size_budget.py::test_rendered_commands_within_budget` |
| AC-006 | unit (render) | `tests/structural/test_command_size_budget.py::test_shared_blocks_appear_once` |
| AC-007 | unit (render) | `tests/structural/test_command_size_budget.py::test_fused_loses_no_instruction` |
| AC-008 | unit (render) | `tests/render/test_render_review_read_budget.py::test_bounded_read_with_escalation` |
| AC-009 | unit (render) | `tests/render/test_render_review_read_budget.py::test_verification_structure_unchanged` |
| AC-010 | unit | `tests/unit/test_economics_unattributed_breakdown.py::test_unattributed_decomposes_and_sums` |

## ❓ Open Questions

1. **Is the remaining 28.9% unattributed recoverable, or is it the documented
   floor?** AC-010 makes the question answerable but does not answer it. Whether
   any recovery work follows is a `plan`-stage decision.
2. **Should `default_workflow` move to the canonical `exec-rev-ver-wrap`?** It is
   not defined in this harness's `workflows:` map at all, so adopting it is a
   config *and* render change with its own risk. Deliberately excluded here.
3. ~~**Does `resolve_model_family` map `claude-opus-5` onto the `opus` key?**~~
   **ANSWERED (PLAN ADR-002).** Yes — it matches PRICE_TABLE keys as substrings
   with longest-match-wins (`economics.py:300-312`), so `"opus"` captures
   `claude-opus-5` and every Opus 5 turn is priced at $15/$75 against a published
   $5/$25. The matcher needs no change; per-model keys work through it as-is.
4. ~~**What target reduction should the AC-005 ratchet encode?**~~
   **ANSWERED (PLAN ADR-014), then REVISED DOWN (PLAN ADR-017).** ≤ 119,000
   characters for `exec-rev-wrap-ver`, derived from a removable set of **5,706
   chars of hoistable shared prose** (preflight 3,729 + Gate 0 shared prose 1,977;
   Communication Protocol excluded per ADR-016) giving a 116,076 projection.
   The first answer was ≤ 110,000, which additionally counted an 8,738-char
   "documentation-only" trim of the fused render. That trim was **withdrawn**: the
   `## When to Run` sections it removed carry the fused-only overrides
   ("When invoked as part of a fused workflow … always run") that are the sole
   defence against the documented `loop-body-skipping-review-stage` failure, and
   `## Quality Bar` carries binding exit invariants plus a user-owned
   `@hm:user:extra-quality-checks` preservation block. Unit is characters; the set
   is every file under `.claude/commands/hm/`; a floor of 0.80× rejects a gutted
   render.
5. **Does bounding reviewer reads measurably change finding recall?** AC-008/009
   guarantee structure and escalation, not outcome. If recall matters enough to
   verify empirically, that needs a labelled diff set — out of scope here.
6. **Effort sweep** — methodology is captured in RESEARCH Appendix A; running it
   is a separate task, and the external evidence is mutually contradictory
   (`low` measured both cheaper and more expensive depending on whether cost is
   counted per request or per task).

## 🔍 Refinement Decisions

- **Round 1 — Scope.** User selected **A+B+C+D**: L1 model correction, fused-prompt
  compaction, reviewer read budget, and residual-unattributed decomposition.
- **Round 1 — Definition of done.** Mechanism plus a **render-time token budget**;
  a measured production reduction is explicitly not required (wrapup delegation
  landed 2026-07-26 and confounds any near-term soak).
- **Round 1 — Quality floor.** Verification apparatus is untouchable and recorded
  as a non-goal. **Reconciliation surfaced by the author:** a read budget that is
  a hard cap *would* weaken verification, contradicting this answer; the only form
  satisfying both answers is escalation-preserving, so that is encoded as a
  Constraint and as AC-008.
- **Round 2 — gate exit.** Three candidates evaluated. `Q-nongoals` and
  `Q-oracle-mode` failed common-ground (settled by Round 1 and by prior-work
  non-goals). `Q-budget-N` failed CLARITI — the user cannot meaningfully answer
  "what should the ceiling be" any better than the author can, so the budget is
  defined as a ratchet against measured bytes instead. Gate reached natural
  termination; no Round 2 was presented.
- **Mid-stage user input (effort sweep material).** Checked before asking: no
  `double-check` / `re-verify` / self-check prose exists in any stage or agent
  template, so the "A.0 precondition" conflict with the quality-floor answer does
  not arise. Recorded in RESEARCH Appendix A; no question was asked.
- **Step 1 prior-art correction.** Three completed plans were discovered that the
  research phase missed; the RESEARCH document was corrected in place (one false
  claim about harness-maker having no API surface, one already-answered open
  question, one missing prior-work section) rather than duplicated.
