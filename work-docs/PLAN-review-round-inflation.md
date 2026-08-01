---
type: plan
task_slug: review-round-inflation
status: complete
created: 2026-08-01
tags: [harness-maker, plan, python, jinja2, review-stage, auto-fix-loop, convergence]
research_doc: "[[RESEARCH-review-round-inflation]]"
interview_rounds: 7
adrs: 12
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Re-derive the model before batching fixes, and count what the loop leaves unreviewed."
---

# PLAN — review-round-inflation

## 🎯 Executive Summary

**TL;DR.** `/hm:review`'s Auto-Fix Loop patches one finding at a time and never re-derives the
state model behind them, so fixes reproduce defects at a ~1:1 rate and the loop runs to 6
rounds. This PLAN makes the loop re-derive the model before editing whenever the round's
findings indicate a shared model or a prior fix's regression, and it makes the loop's residual
blind spot countable.

**What.** Two changes ship: **A** a batch-and-re-derive step in the Auto-Fix Loop, gated on a
two-arm trigger; **C** three counters that record what the loop left unreviewed and how much of
a round's work was self-inflicted. **Why.** Measured on the reference case, roughly half of 30
findings were defects inside the previous round's own fix; two chains each recreated the
original reported bug out of the fix for it (`.worktrees/autopilot-advance-noop/work-docs/REVIEW-autopilot-advance-noop-2026-07-31.md:240-298`).

**Key decisions.** The trigger is two-armed, not one (ADR-001) — a reproduction showed the
one-armed version provably misses both chain-initiating findings. Judgment lives in prompts,
counters live in Python (ADR-002). The counters gate nothing this round (ADR-003). The loop
contract moves to the SKILL, which both fixes a duplicate-contract drift risk and pays the
surface-ratchet budget for everything this PLAN adds (ADR-005, ADR-008).

**Estimated impact.** One Python module + one PRIVACY row group + two SPEC files; two template
files; three test files. No config surface, no new user-facing flag. Ships ON for every harness.

## 📚 Prior Work

- `work-docs/RESEARCH-review-round-inflation.md` — the causal analysis and the rejected
  alternatives (raising `max_review_rounds`; routing cross-layer findings out of auto-fix).
- `.worktrees/autopilot-advance-noop/work-docs/REVIEW-autopilot-advance-noop-2026-07-31.md` —
  the 6-round reference case, its per-round tables, and its own retrospective.
- `[wiki:review] reproduction-outranks-consensus-count` — the rule this PLAN's own review
  process followed: two models converged on the trigger defect, and the claim was adopted only
  after re-counting the round tables by subsystem.
- `PLAN-second-opinion-acceptance-gate` — origin of the round-state contract, finding `id`
  stamping, and the frozen cross-model set that rounds 2..N re-read.
- `[fail:design] stash-list-substring-match`, `[fail:design] gitignore-write-text-non-atomic` —
  the counter-examples: local defects the loop caught and fixed correctly in one round. The
  trigger must not slow these down.
- CLAUDE.md learned correction 2026-06-08 (absent-case = feature black hole) — the direct
  source of ADR-006 and ADR-009.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | → ADR |
|---|-------|-------|----------|----------|--------|-------|
| 1 | 1 | Scope | Scope boundaries | Which of the four measures ship? | A only (batch-and-re-derive) | ADR-001 |
| 2 | 1 | Enforcement surface | Architecture | Prompt, Python, or split? | Split — judgment in prompt, counters in Python | ADR-002 |
| 3 | 1 | Shipping default | Risk tolerance | ON for all / preset-gated / opt-in? | ON for all, no flag | ADR-003 |
| 4 | 2 | Cost of B | Testing depth | Apply failing-test-first, and how widely? | B excluded — cost judged too high this round | ADR-007 |
| 5 | 2 | Additional scope | Scope boundaries | Add C (counters) and/or D (escape branch)? | C only; D deferred until C produces data | ADR-003 |
| 6 | 2 | A's trigger | Architecture | Always / ≥2 same subsystem / severity-based? | ≥2 same subsystem | superseded by #8 |
| 7 | 3 | Counter visibility | Observability | Report only / + turn warning / + `human_review_needed`? | Report + telemetry only | ADR-003 |
| 8 | 4 | A's trigger (revised) | Architecture | Reproduction showed ≥2-only misses #7 and #20 — keep, revise, or replace? | Revise: (≥2 same subsystem) OR (attributed to a prior round's fix) | ADR-001 |
| 9 | 5 | Ratchet + contract ownership | Architecture | Budget-neutral relocation / keep contract in stage / authorize a ceiling raise? | Budget-neutral — relocate to SKILL, pay for the additions | ADR-005, ADR-008 |
| 10 | 5 | Telemetry emission point | Contract shape | Discriminator field / drop from JSONL / extra terminal row? | Add a `terminal` discriminator | ADR-009 |
| 11 | 6 | Ratchet raise width | Risk tolerance | Minimize the additions first, or raise for the drafted text? | Minimize, then raise — minimisation alone sufficed, no raise taken | ADR-008 |
| 12 | 6 | The RED window | Risk tolerance | Follow the land→re-freeze precedent, or add an allowance field? | Follow the precedent — moot once the budget turned positive and no raise was needed | ADR-008 |
| 13 | 7 | §5 placement | Architecture | Split into a generic skill / keep in `second-opinion-gate` / return to the stage? | Keep in `second-opinion-gate` (user override of the recommendation) | ADR-011 |

Rounds 4 and 5 were opened by the cross-model second opinion and the plan-validator
respectively; both overturned a decision made in an earlier round. Interview entry #6 is
recorded rather than deleted because ADR-001's rejected-alternatives list cites it.

## 📐 Architecture Decision Records

### ADR-001: Two-armed trigger for batch-and-re-derive
**Status:** Accepted (2026-08-01, via /hm:plan interview #6 → #8)
**Context:** Fixes reproduce defects at ~1:1 because each round patches the reported cell of a
multi-dimensional state model without re-deriving the model. A trigger is needed that fires on
the expensive cases without taxing the cheap ones.
**Decision:** The Auto-Fix Loop re-derives the model before editing when **either** (a) ≥2 of
the round's findings belong to the same subsystem/state model, **or** (b) any finding is
attributed to a previous round's fix (ADR-004's `caused_by`). Otherwise the existing
immediate-patch path is unchanged.
**Consequences:**
- ✅ Both chain-initiating findings in the reference case are caught by arm (b).
- ✅ Round 1 has no prior fixes, so lone first-round findings keep the fast path — no cost added
  to the single-round cases the loop already handles correctly.
- ✅ Arm (b) gives measure C an in-loop reader, so the counters are not inert (ADR-003).
- ⚠️ Whether the model was genuinely re-derived — as opposed to a conforming block being
  emitted — is not verifiable by any test in this repo. Recorded in ADR-007.
**Rejected alternatives:**
- **Arm (a) only** (the interview's first answer) — refuted by reproduction against the round
  tables: ownership finding #7 was the only ownership finding in round 2, and slug finding #20
  was the only slug finding in round 5. Those two are precisely the fixes that recreated the
  original bug, and a one-armed trigger sends both down the fast path.
- **Arm (b) only** — misses round 1, where the reference case had three ownership findings and
  no prior fix to attribute them to; the chain would form before the trigger could fire.
- **Always re-derive** — pays the re-derivation cost on quiet rounds, which the reference case
  shows are the majority.
**Source:** Interview #6, #8; cross-model second opinion (codex P1, antigravity P0).

### ADR-002: Enforcement split — prompt owns judgment, Python owns counters
**Status:** Accepted (2026-08-01, via /hm:plan interview #2)
**Context:** CLAUDE.md's LLM-utilization principle puts classification and convergence judgment
in prompts and type contracts, storage and safety rails in Python.
**Decision:** Grouping, re-derivation and attribution judgments live in `review.md.j2` and the
`second-opinion-gate` SKILL. The counter schema, its wire semantics and its persistence live in
`src/harness_maker/review_telemetry.py`.
**Consequences:**
- ✅ The numeric contract is unit-testable even though the judgment producing it is not.
- ⚠️ The values are LLM-emitted, so the schema constrains shape but not accuracy.
**Rejected alternatives:**
- **Python-first classification** (a rule that assigns findings to subsystems) — rejected because
  the reference case's one chain spans ownership, heartbeat, GC and TOCTOU; a path-prefix rule
  would split it. Contradicts CLAUDE.md's LLM-utilization principle.
- **Prompt-only** — leaves the counters as prose, which is the exact shape that got compacted
  into an inverted meaning in the reference case.
**Source:** Interview #2.

### ADR-003: The counters are reporting-only this round
**Status:** Accepted (2026-08-01, via /hm:plan interview #5, #7)
**Context:** Measure D (a revert/re-plan escape branch) needs a defect-per-fix rate that does
not exist yet. Measuring before gating avoids inventing a threshold with no data behind it.
**Decision:** `unreviewed_fix_count`, `regression_attributed_n` and `attribution_unknown_n`
appear in the REVIEW report's Final Summary and in the telemetry JSONL. They do not change the
grade, do not set `human_review_needed`, and do not print a turn-level warning.
**Consequences:**
- ✅ No signal erosion — a normal 2-round review does not acquire a new scary flag.
- ✅ The **only** in-loop reader is ADR-001 arm (b), which reads the iteration record's
  `caused_by`, not the JSONL. That keeps the counters from being inert without gating on them.
- ⚠️ Nothing acts on a bad number this round. D is the named follow-up.
**Rejected alternatives:**
- **Set `human_review_needed` on a nonzero unreviewed delta** — would flag almost every review,
  eroding the meaning `unverified_severe` currently carries.
- **A read-side aggregation helper in Python** — dropped from scope: it would have had no
  consumer, and an unused helper is a maintenance liability that reads like coverage.
**Source:** Interview #5, #7; codex P2 (dead helper).

### ADR-004: Attribution is a relation, not a scalar
**Status:** Accepted (2026-08-01, via cross-model second opinion)
**Context:** "How many of this round's findings came from last round's fix" cannot be audited or
recomputed from a single number, and the chains this PLAN exists to explain are relations.
**Decision:** Each per-iteration record row carries `caused_by: <finding-id | null>`. The counter
`regression_attributed_n` is **derived by counting DISTINCT finding `id`s** with a non-null
`caused_by` — not rows; `attribution_unknown_n` likewise counts distinct ids. No free-hand
estimate.

**`unreviewed_fix_count` re-defined (2026-08-01, forced by ADR-012's amendment).** It was "fixes
applied in the terminal round, which the loop never re-reviewed". Under the adopted apply-first
order the round re-reviews its own fixes, so that reading is **0 by construction** — a counter
reporting a constant (`code-reviewer`, review round 1). It now counts **fixes whose file was not
covered by any re-spawned reviewer's scope**, summed over the run. That is a real, non-zero
quantity: step "selective re-review" deliberately re-spawns only reviewers whose scope the fixes
touched, so a fix in a file no reviewer covers is genuinely unreviewed — which is exactly the
blind spot measure C exists to make visible.

> **Why distinct ids, not rows.** The iteration record lists fixes *attempted* this round, and a
> `Reverted — build failure` or `Skipped — overlap` fix leaves its finding `pending`
> (`review.md.j2:528,536`; `SKILL.md.j2:169-171`), so the same finding is re-selected next round
> and emits a **second** row carrying the same stamped `caused_by` (ADR-012 rule 2 stamps once
> and never recomputes). Row-counting therefore double-counts exactly the build-breaking chains
> this PLAN exists to study, and the value is written to append-only telemetry where a wrong
> number is permanent (R4). ADR-003 names this dataset as the sole input to the deferred measure
> D, so the defect would be inherited by the follow-up.
**Consequences:**
- ✅ The chain `#2 → #7 → #15 → #21 → #25` is reconstructable from the artifact.
- ✅ ADR-001 arm (b) has a concrete field to read.
- ⚠️ Attribution is an LLM judgment; `attribution_unknown_n` is the honest escape rather than a
  forced binary.
**Rejected alternatives:**
- **A scalar count only** — unauditable, and it cannot feed arm (b) at row granularity.
**Source:** codex P1 (regression attribution needs a `caused_by` relation).

### ADR-005: The SKILL is the normative owner of the round-state contract
**Status:** Accepted (2026-08-01, via /hm:plan interview #9)
**Context:** The same four rules exist in `review.md.j2:509-514` and in
`templates/skills/second-opinion-gate/SKILL.md.j2:165-202`. Duplicated contracts drift, and in
the reference case a size-driven compaction pass inverted a negation in exactly this kind of
prose.
**Decision:** The SKILL's §5 is normative. `review.md.j2` stops restating the rules and instead
carries an **unconditional** imperative to load §5 — placed outside the
`{% if config.second_opinion … %}` guard that currently wraps the only existing load
instruction at `:338-342`.
**Consequences:**
- ✅ One owner, so compaction cannot silently fork the contract.
- ✅ Removing **both** restatements from the rendered commands is what pays ADR-008's budget —
  `:509-514` and `:539-545`. Counting only the first is what made the budget look negative.
- ⚠️ A user who removes `second-opinion-gate` from their enabled skills would delete the
  convergence contract. Mitigated by a render-time assertion (Phase 3) rather than left to the
  preset force-enable in `interview.py:161-178`.
**Rejected alternatives:**
- **Keep the contract in the stage** (interview option 2) — resolves the load-instruction risk
  for free, but forfeits the ratchet budget and keeps the drift risk that caused the reference
  case's inverted negation.
**Source:** Interview #9; codex P2 (duplicate contract), plan-validator critical #3.

### ADR-006: New telemetry counters are `int | None`, never `int = 0`
**Status:** Accepted (2026-08-01, via plan authoring under CLAUDE.md 2026-06-08)
**Context:** `ReviewTelemetryRecord` defaults numeric fields to 0 so aggregations need no
null-coalescing. Applying that convention here would make "this harness version never measured
it" indistinguishable from "measured zero" — the absent-case failure mode CLAUDE.md records as
the most-recurring class in this project.
**Decision:** The three counters are `int | None = None`. Absent/null = not measured. 0 =
measured zero.
**Consequences:**
- ✅ Rows written before this change stay interpretable.
- ⚠️ `emit` serializes `model_dump()` unconditionally (`review_telemetry.py:144`), so optional
  fields appear on the wire as explicit `null`. A key-presence test would therefore pass over a
  harness that never measures. Phase 3's structural test asserts semantics, not key presence.
**Rejected alternatives:**
- **`int = 0`** — collapses the absent case, per the above.
- **A `schema_version` discriminator** — heavier, and ADR-009's `terminal` field already
  supplies the discrimination the emission point actually needs.
**Source:** CLAUDE.md learned correction 2026-06-08; codex P2 (wire semantics).

### ADR-007: Two limitations are accepted, not fixed
**Status:** Accepted (2026-08-01, via /hm:plan interview #4)
**Context:** Measure B (failing-test-first per fix) is out of scope by user decision, and the
loop's exit structure is unchanged.
**Decision:** Record both residual defects explicitly rather than implying this PLAN closes them.
1. **`resolved` remains uninformative.** Verification is still the pre-existing suite
   (`review.md.j2:530-536`), which is green by construction for a newly-discovered defect class.
   A re-derived model is therefore still unverified when the round marks its findings resolved.
2. **The terminal round's fixes still exit unreviewed.** `:565` returns to the grade gate
   immediately after the iteration record.
Measure C makes both **visible**; neither is closed.
**Consequences:**
- ✅ An `A` grade is no longer implicitly read as "settled" — the Final Summary states the
  unreviewed count.
- ⚠️ A re-derivation that is wrong will still pass the round. This is the single largest
  remaining exposure and the reason B is the first follow-up, ahead of D.
**Rejected alternatives:**
- **Ship B narrowly** (state-model/cross-layer P0-P1 only) — user judged the cost unacceptable
  this round; the option and its cost analysis are preserved in RESEARCH for the follow-up.
**Source:** Interview #4; codex P1 ×2, antigravity P1.

### ADR-008: The surface ratchet is paid, not raised
**Status:** Accepted (2026-08-01, via /hm:plan interview #9)
**Context:** `tests/structural/test_surface_baseline.py:277` asserts `now <= was` per variant —
a shrink-only ratchet. Its docstring states that re-freezing after growth is what ADR-011 of the
originating PLAN forbids. Everything this PLAN adds to `review.md.j2` is net-additive **before
minimisation**; the measurement below is what decides whether that survives.
**The ratchet's axis is two TARGET variants, not command names** (`_surface_baseline.py:51-52`,
`:109-117`): `claude` measures `.claude/commands/hm/*.md` and `codex` measures
`.agents/skills/hm-*/SKILL.md`. `review`, `exec-rev`, `exec-rev-wrap` and `plan-exec-rev*` are
commands *inside* those variants, and `test_surface_baseline.py:275-277` compares per-variant
aggregates. Both variants are fed by `review.md.j2`.
**Decision:** The additions are paid for by ADR-005's relocation, and the payment is **two**
removals, not one — the restatement at `:509-514` (422 rendered chars) **and** the second
restatement of §5's "do not re-invoke the models" rule at `:539-545` (317 rendered chars, present
in both variants; §5 already carries it verbatim at `SKILL.md.j2:193-196`, so removal loses no
content and is mandated by this ADR's own single-owner logic). The exemption is precise:
`second-opinion-gate` renders **outside** the `hm-*` glob, so its text is measured by neither
variant — relocating prose into an `hm-*` skill would buy nothing. Phase 0 measures the delta on
**real drafted text**; Phase 3's ratchet run is the **binding** gate. ADR-011 is not overridden
and no ceiling raise is taken.

**Sign convention, stated once and used everywhere below:** `budget = removed − added`, and it
must be **≥ 0**. A positive budget passes; a negative budget halts.

**Measured outcome (Phase 0, after three rounds of minimisation):**

| | template chars |
|---|---|
| Removed — `:509-514` + `:539-545` | **739** |
| Added — the minimal form (see Phase 2) | **551** |
| **Budget (removed − added)** | **+188** → claude **+940**, codex **+188** — PASSES |

**The budget is config-dependent on the removal side and unconditional on the addition side.**
`:539-545` renders only under `{%- if config.second_opinion and config.second_opinion.models %}`.
This repo's own config has both models enabled (`.claude/harness.yaml:152`), so the gate sees the
full 739. A downstream harness with `models: []` frees only 422 while still paying 551 — a
**+129 template-char growth** (claude +645) in every review-bearing command. Nothing measures
that: `_surface_baseline.py:95-108` renders one config. Recorded in R10 rather than gated.

The first draft measured +1035 net and the second +464; only the third — after folding the load
imperative and the trigger condition into one, serialising `caused_by` into the existing Status
cell instead of adding a column, one-lining the counters, and keeping the emit roster
authoritative in one place — went negative, and only once the second restatement was counted on
the removal side. **A ceiling raise was authorised by the user and turned out to be unnecessary;
it is not taken.**
**Consequences:**
- ✅ The ratchet keeps its meaning; no ceiling is raised.
- ✅ The measurement is a phase, not an assumption — if the relocation does not cover the
  additions, the shortfall is known before the prose exists rather than after.
- ⚠️ If Phase 0 shows the budget is insufficient, Phase 2's prose must be cut further or this
  ADR must be reopened. That branch is named in the risk register rather than pre-decided.
**Rejected alternatives:**
- **Authorize a one-time ceiling raise** (interview option 3) — the simplest path, rejected
  because a ratchet loosened once for a good reason is loosened again for the next good reason.
**Source:** Interview #9; plan-validator critical #2.

### ADR-009: A `terminal` discriminator on the telemetry row
**Status:** Accepted (2026-08-01, via /hm:plan interview #10)
**Context:** Telemetry emits one line per round (`review.md.j2:595`), but the three counters are
end-of-review quantities computed in the Final Summary. On rounds 1..N-1 they have no defined
value, and `null` there would collide with ADR-006's "not measured by this version".
**Decision:** Add `terminal: bool | None = None`. Counters carry values only on the terminal
row; non-terminal rows carry `terminal: false` with the counters null. Pre-change rows have
`terminal: null`, which is distinguishable from both.
**Consequences:**
- ✅ Aggregation is unambiguous: filter `terminal == true`.
- ✅ One field, no second row type.
- ⚠️ A run that crashes before the Final Summary emits no terminal row. That is correct — the
  measurement did not happen — and matches the null semantics.
- ⚠️ **Nothing forbids `terminal: true` with all three counters null** — to an aggregation
  filtering `terminal is True` that reads as "measured nothing" rather than "did not measure".
  No cross-field validator is mandated here, deliberately: the counters are LLM-emitted and a
  schema-level requirement would turn a prompt slip into a hard validation error on the review's
  own telemetry write. Recorded as an aggregation-side caveat (surfaced by Phase A.5's
  test-reviewer) rather than left unstated.
**Rejected alternatives:**
- **Drop the counters from JSONL** — contradicts ADR-002 and leaves aggregation manual.
- **A separate terminal-only row type** — two row kinds in one file is precisely how the
  second-opinion ledger's skip-rate got silently polluted (CLAUDE.md).
**Source:** Interview #10; antigravity P2, plan-validator critical #4.

### ADR-010: `group_key` has a default derivation rule
**Status:** Accepted (2026-08-01, via plan authoring)
**Context:** ADR-001 arm (a) needs "same subsystem", but findings carry `file`, `line`,
`severity` and `id` — no subsystem label. Without a rule, two rounds label the same subsystem
differently and the groups are not comparable across rounds.
**Decision:** `group_key` defaults to the dominant file-path stem shared by the group's
findings. A free-text key is allowed when the model judges the subsystem spans paths, but the
derived prefix is recorded alongside it in the iteration record.
**Consequences:**
- ✅ Cross-round comparison has a stable fallback.
- ⚠️ Still LLM-assigned. Arm (b) carries the expensive cases regardless of grouping quality,
  which is why this is a suggestion-level mitigation rather than a gate.
**Rejected alternatives:**
- **Free-text only** — non-comparable across rounds, so the recorded groups cannot be audited.
**Source:** plan-validator suggestion; codex P1 (grouping is not an executable contract).

### ADR-011: §5 stays inside `second-opinion-gate`
**Status:** Accepted (2026-08-01, via /hm:plan interview #12 — user override)
**Context:** The unconditional load imperative ADR-005 requires makes **every** review read the
`second-opinion-gate` skill. That file is 231 lines and §5 starts at 165, so a harness with
`second_opinion.models: []` loads ~160 lines of second-opinion-specific text (§1–§4, §6) to
obtain generic round-state rules. Splitting §5 into a small `review-round-state` skill was
recommended and explicitly rejected by the user.
**Decision:** §5 remains in `second-opinion-gate`. No new skill asset.
**Consequences:**
- ✅ Scope stays small — no renderer registration, no preset skill-list change, no extra phase.
- ⚠️ **Accepted risk:** a `models: []` harness pays ~160 lines of irrelevant context per review,
  and that cost is invisible to the surface ratchet, which measures rendered commands only. The
  150-line Production context-lint threshold is already exceeded (231) and the lint is warn-only,
  so nothing forces a future cut — "it is already warning" is a description, not a justification.
**Rejected alternatives:**
- **Split §5 into a generic `review-round-state` skill** — genuinely reduces the per-review
  context cost and would clear the lint warning; rejected by the user as scope growth. Named here
  as the deferred follow-up so the next PLAN touching this skill finds it.
**Source:** Interview #13; codex P2.

### ADR-012: Attribution is stamped once, and the round order is pinned end to end
**Status:** Accepted (2026-08-01, via cross-model second opinion + plan-validator)
**Context:** ADR-001 arm (b) fires when a finding is attributed to a prior round's fix, and reads
ADR-004's `caused_by`. The earlier draft wrote `caused_by` when **appending** the iteration
record — after fix selection — so the trigger could never see it and a lone regression finding
would take the fast path. That is the same shape as the defect this PLAN exists to remove: a fix
that does not fire on the case it targets. Pinning the order alone is not sufficient: §5 keeps
voter state merged by `id` and **retains** findings a reviewer stops reporting, so a per-round
re-attribution would flip a round-1 finding null→non-null once its target overlapped a later
round's hunks, and an attributed finding stays `pending` until resolved — arm (b) would become
unconditionally true from round 3.
**Decision:** Three rules.
1. **Order, end to end** (amended 2026-08-01 — see the amendment note below): merge the previous
   round's re-review output by `id` → stamp ids on new findings → determine `caused_by` → group
   and evaluate the two-arm trigger → batch re-derive (on a fire) → select fixes → apply →
   **verify build, reverting on failure** → **selective re-review** → recompute grade → progress
   invariant → append the iteration record. Attribution precedes the trigger, which is the whole
   point and what makes arm (b) reachable. **Verify and re-review stay INSIDE the round**, after
   apply.
2. **`caused_by` is stamped exactly once**, at a finding's first appearance, keyed by its stable
   `id`, and is never recomputed. "First appearance" is well-defined across a `stale`-then-
   re-report **because of `codex_adapter.finding_id:51-61`**, which hashes
   `[source, file, line, message]` at adaptation and freezes it: a re-report at a shifted
   location yields a **different** id (genuinely new → new stamp → arm (b) may fire), and a
   re-report at an unchanged location yields the **same** id (not new → no re-fire, correct,
   because nothing regressed). Rule 2 depends on those hash inputs — changing them breaks it.
3. **Arm (b)'s domain is findings NEW to this round**, not the merged voter state.
**Consequences:**
- ✅ Arm (b) can fire, and fires only on fresh regressions — ADR-001's "lone first-round findings
  keep the fast path" survives.
- ✅ Re-attribution across rounds is impossible, so a finding's origin cannot drift. Counting
  each regression **once** additionally requires ADR-004's distinct-id derivation — stamp-once
  alone does not deliver it, because one finding can occupy rows in several rounds.
- ⚠️ The round boundary does **not** move — only attribution and the trigger move earlier. Phase 3
  asserts the sequence survives rendering.

**Amendment note (2026-08-01, `/hm:review` round 1).** The original rule 1 put verify and
re-review at the **top** of the round, so a round's own fixes were verified in the next one.
`code-reviewer` and `codex` independently found it contradicted the stage's numbered loop, and
working the fix surfaced that the two orders are not interchangeable:

| | apply-last (original) | apply-first (adopted) |
|---|---|---|
| Build safety | a break survives a full round | reverted in-round |
| `unreviewed_fix_count` | the terminal round's fixes | 0 under the old definition — see ADR-004 |
| arm (b) reachable | yes | yes (attribution moved earlier) |

Adopted apply-first: catching a build break immediately is worth more than what apply-last bought,
and the counter is recoverable by definition (ADR-004) whereas build safety is not. **Neither
order was auto-fixable** — the review escalated rather than picking, because silently choosing
would have contradicted a binding ADR.
**Rejected alternatives:**
- **Pin the order only** — leaves the idempotence and domain holes, which make arm (b) always-on
  from round 3.
- **Recompute `caused_by` every round** — cheap to write, but flips attributions with no causal
  relation behind them.
**Source:** codex P1 (ordering); plan-validator critical (idempotence + domain).

## 🏗️ Technical Design

**Current state.** `review.md.j2:507-565` defines the Auto-Fix Loop: select fixable findings →
apply per finding in priority order → verify with the project suite → selectively re-review →
recompute grade → evaluate the progress invariant → append an iteration record → return to the
grade gate. The round-state contract is stated twice: normatively in
`templates/skills/second-opinion-gate/SKILL.md.j2:165-202`, and restated inline at
`review.md.j2:509-514`. Telemetry is one JSONL line per round
(`review.md.j2:595-618` → `review_telemetry.emit`).

**Affected components.**

| Component | Change |
|---|---|
| `src/harness_maker/review_telemetry.py` | +4 optional fields on `ReviewTelemetryRecord` |
| `PRIVACY.md` | +4 rows in the review-telemetry field table |
| `specs/SPEC-review-telemetry.{md,machine.yaml}` | schema description follows the record |
| `src/harness_maker/templates/stages/review.md.j2` | Auto-Fix Loop step 2 rewrite; iteration record `caused_by`; Final Summary counters; emit contract at three sites; unguarded SKILL load line; restatement removed |
| `src/harness_maker/templates/skills/second-opinion-gate/SKILL.md.j2` | §5 becomes normative owner; absorbs the trigger rule |
| `tests/` | telemetry unit tests; two-config render test; executed-surface structural test |

**Dependencies.** None added. No new library, no config key, no `harness.yaml` schema change.

**Data flow.** Reviewers → findings with `id` (Step 3.4, unchanged) → Auto-Fix Loop groups by
`group_key` (ADR-010) and evaluates ADR-001's two-arm trigger → re-derivation block or
immediate patch → iteration record rows carry `caused_by` (ADR-004) → Final Summary aggregates
the three counters → one terminal telemetry row with `terminal: true` (ADR-009).

**Emit contract sites (all three must move together).** `review.md.j2` states the schema in
prose near `:599`, gives the `bash` emit block at `:604-612`, and lists the field roster at
`:615`. The roster is what the runtime model copies when constructing the record. Editing fewer
than three leaves the fields accepted by Python but never sent — the absent-case failure this
project has shipped before. The stale literal "14-field schema" is corrected in the same edit.

## 📝 Implementation Plan

### Phase 0 — Measure the ratchet budget
- `depends_on`: `[]`
- `parallel_group`: `serial-0`
- `merge_hazards`: none (measurement only, no file writes outside the PLAN)
- **Scope (in):** read `tests/structural/surface_baseline.json`; **draft** Phase 2's additive
  prose and the replacement load imperative into this PLAN's `## 📏 Ratchet budget` section, so
  the added-character term is measured on real text rather than estimated; count the characters
  the ADR-005 relocation removes from `review.md.j2`. **(out):** any template edit — the draft
  lives in the PLAN, not in `.j2`.
- **Exit criterion:** `uv run pytest tests/structural/test_surface_baseline.py -q` is green at
  branch start (baseline sanity), and `## 📏 Ratchet budget` records removed − added for **both
  target variants** (`claude`, `codex`). A negative budget in either variant halts and reopens
  ADR-008 before Phase 2 touches a template. This is a cheap early warning, not the gate —
  Phase 3's ratchet run against a real render is binding.
- **Risk:** low
- **Rollback point:** n/a — no mutation.

#### ✅ COMPLETE — 2026-08-01, `/hm:execute` Phase 0 (blocked once, then resolved)

**Result: net −188 template chars (claude −940, codex −188). The ratchet passes with no raise.**
Phase 0's first run halted on its own negative-budget condition and refuted ADR-008 as then
written; three rounds of minimisation plus one uncounted removal turned it positive. The halt log
below is kept because ADR-008's numbers are only defensible next to the measurements that
produced them.

<details><summary>Phase 0 halt log (superseded — kept for provenance)</summary>

Branch-start sanity passed (`tests/structural/test_surface_baseline.py` green, 13 passed) after
rebasing onto `30e316cf` — the task branch had been 2 commits behind and one of those commits
re-froze `surface_baseline.json`, so measuring before the rebase would have used a stale ceiling.

**Measured headroom is zero.** A live render (`_surface_baseline.render_surface`) reproduces the
frozen aggregate exactly — `claude 851807`, `codex 319187` in both the live measurement and
`surface_baseline.json`, so any net addition fails `now <= was`.

**Embedding multiplier, measured not assumed.** The review stage body renders into 5 claude
commands (`review`, `exec-rev`, `exec-rev-wrap`, `exec-rev-wrap-ver`, `plan-exec-rev`) and 1
codex skill (`hm-review`). One template character costs 5 claude chars and 1 codex char.

**Budget, measured on real drafted text:**

| Item | chars |
|---|---|
| Removable — the `:509-514` restatement, as rendered | **422** |
| Add — unconditional `Load §5` imperative (ADR-005, validator C3) | 348 |
| Add — step 2 two-arm trigger pointer | 267 |
| Add — `caused_by` column in the iteration record | 202 |
| Add — three counters in the Final Summary | 349 |
| Add — four fields at the emit roster + bash example | 160 |
| Add — wire-semantics sentence | 131 |
| **Added total** | **1457** |
| **Net per template char** | **−1035** |
| **claude variant (×5)** | **−5175** |
| **codex variant (×1)** | **−1035** |

**ADR-008's premise is refuted.** The relocation does not pay for the additions, and it cannot:
the imperative that ADR-005 requires in its place already consumes 83% of what the removal frees.
Pushing further prose into §5 does not close it either — the surface the stage must structurally
keep (load imperative + `caused_by` column + emit field names + bare counter lines) is ~830 chars
against 422 freed. This is a structural result, not an estimation error.

**Sub-result worth carrying into the decision:** measure **A alone** — the load imperative plus
the trigger pointer, with no counters and no `caused_by` — is ~615 added against 422 removed
(−193 template, −965 claude). Still negative, but within reach of a modest offsetting cut,
whereas A+C is not.

No template was modified. Phases 1–4 are not started.

</details>

**How it was resolved (three minimisations + one uncounted removal):**

Budget = removed − added, must be ≥ 0 (ADR-008's convention):

| Draft | Removed | Added | Budget (template) | claude | Verdict |
|---|---|---|---|---|---|
| 1 — first pass | 422 | 1457 | −1035 | −5175 | halt |
| 2 — tightened wording (antigravity P3) | 422 | 886 | −464 | −2320 | halt |
| 3 — codex's four reductions | 422 | 551 | −129 | −645 | halt |
| 4 — **+ the second restatement counted** (plan-validator) | **739** | 551 | **+188** | **+940** | **passes** |

The four reductions in draft 3: merge the §5 load imperative and the trigger's firing condition
into one imperative; serialise `caused_by` into the existing `Status` cell rather than adding a
column; one-line the counters with their meaning in §5; keep the emit field roster authoritative
in exactly one place. The step-4 removal is `review.md.j2:539-545` — 317 rendered chars, in both
variants, restating §5's "do not re-invoke the models" rule that `SKILL.md.j2:193-196` already
owns. ADR-005's single-owner logic mandates its removal independently of the budget.

**Verified, not assumed:** the multiplier (5 claude commands + 1 codex skill) and every char
count come from `_surface_baseline.render_surface()` on a live render, not from the committed
`.claude/` tree — which is stale relative to `c962e57e` and would have given wrong numbers.
Branch-start sanity (`test_surface_baseline.py`, 13 passed) ran **after** rebasing onto
`30e316cf`; the branch had been 2 commits behind, one of which re-froze the baseline.

### Phase 1 — Python rail — ✅ DONE (2026-08-01)
Verification: `ruff check` + `ruff format --check` + `mypy --strict` + full `pytest` chained on
`&&`, exit 0. `test_dep_map` returned `mode: full`, reason verbatim: *"full suite: no test maps to
PRIVACY.md, specs/SPEC-review-telemetry.machine.yaml"*.
Two gates fired and both were right: the **RED gate** caught a test of mine that was green in
both directions (it passed via `extra=forbid` before the fields existed and would pass after —
fixed with an accept-0 arm plus a `greater_than_equal` cause pin), and the **test-reviewer**
caught wire assertions that checked key presence only, which a null→0 serialization coercion
would have passed while destroying ADR-006 in append-only rows.
- `depends_on`: `[0]`
- `parallel_group`: `serial-1`
- `merge_hazards`: `PRIVACY.md` is also touched by unrelated schema work; the two SPEC files
  are unenforced docs and must not be assumed test-covered.
- **Scope (in):** `src/harness_maker/review_telemetry.py` (+`unreviewed_fix_count`,
  `regression_attributed_n`, `attribution_unknown_n`, `terminal`, all optional per ADR-006/009)
  **including its module docstring `:6` ("sufficient for the 14-field record") and the class
  docstring `:30-34` ("Numeric fields default to 0 (not None)")** — both state the opposite of
  ADR-006 and must move with it; `PRIVACY.md` (+4 rows, written inside a scoped
  `<!-- @hm:privacy:review-telemetry -->` marker block); `specs/SPEC-review-telemetry.md` and
  `specs/SPEC-review-telemetry.machine.yaml`; `tests/unit/test_review_telemetry.py`.
  **(out):** any template, any consumer/aggregation helper (ADR-003 rejected it).
- **Why the marker block:** `test_privacy_doc_schema.py:94-100` harvests backticked identifiers
  **document-wide**, so a backticked generic token like `terminal` appearing anywhere in
  `PRIVACY.md` would make the gate vacuous for that field. The file's own comment at `:29-38`
  records that this is exactly why the feedback-module block exists; scope the assertion the
  same way.
- **Exit criterion:**
  `uv run pytest tests/unit/test_review_telemetry.py tests/unit/test_privacy_doc_schema.py -q`
  green, including a test that a pre-change row still validates with the four new fields as
  `None`, a test pinning the three wire states (absent → null, `terminal:false` + null counters,
  `terminal:true` + integer counters).
- **ADR-004's distinct-id derivation is NOT pinned here** (corrected during `/hm:execute`): the
  derivation has no Python subject to test. ADR-003 rejected the read-side aggregation helper, so
  the counters are produced by the LLM and Python owns only the schema. A unit test would have to
  invent a function that nothing calls. The pin moves to **Phase 2** (the instruction states
  "count distinct finding ids, not rows", with the reverted/overlap case named) and **Phase 3**
  (the render assertion checks that instruction is present in the executed surface).
- **Risk:** low
- **Rollback point:** revert this phase's commit. Rows already written carry the fields as null
  and stay valid under the old schema.
- **Pre-existing condition, not introduced here:** `hm spec_machine validate
  specs/SPEC-review-telemetry.machine.yaml` exits 1 on **AC-001**, whose auto-generated
  `executable_predicate` is the prose placeholder `# placeholder — refine in /hm:spec …`.
  Verified identical at `HEAD` before any edit in this phase; the AC-002 added here validates.
  Fixing AC-001 means authoring a real predicate for an unrelated AC on one of many skeleton
  SPECs — out of this PLAN's scope, recorded rather than silently left.

### Phase 2 — Prompt: trigger, attribution, counters — ✅ DONE (2026-08-01)
Exit green (57 tests). **The ratchet caught an ADR-005 violation I introduced**: the first cut
came in at claude **+1055 / codex +211 — RED**, because two of my additions (a distinct-id
instruction in the Final Summary and a measure-C paragraph in the telemetry section) were fresh
restatements of §5 rules. Deleting them was a correction, not a compromise, and the budget then
held: claude **−615**, codex **−123**.
- `depends_on`: `[1]`
- `parallel_group`: `serial-2`
- `merge_hazards`: `review.md.j2` and the SKILL template are both re-rendered by Phase 3;
  `tests/render/test_render_review_read_budget.py` parses the rendered command by section, so
  heading or numbering changes in the loop can shift its extractors.
- **Scope (in):**
  - `templates/skills/second-opinion-gate/SKILL.md.j2` §5 — **the only place the rule text is
    written.** §5 absorbs ADR-001's two-arm trigger and the required per-group block spec
    (`group_key` + derived prefix per ADR-010, `covered_finding_ids`, enumerated model
    dimensions, one consolidated edit).
  - `review.md.j2` — **both** restatements are deleted: `:509-514` (the round-state rules) and
    `:539-545` (the "do not re-invoke the models" rule §5 already owns). In their place, ONE
    unconditional imperative that carries the §5 load **and** the trigger's firing condition, so
    a reader at the point of use knows whether to fire without opening the skill.
  - `review.md.j2` mechanical surface only, in the minimal form Phase 0 measured (551 chars):
    - `caused_by` **serialised into the existing `Status` cell** — no new column. Grammar is
      literal and pinned: `Applied · caused_by=#7` / `Applied · caused_by=none` /
      `Applied · caused_by=unknown`, and the same `· caused_by=` suffix on `Skipped — overlap`
      and `Reverted — build failure`. Phase 3 asserts the rendered example row uses it. An
      unspecified grammar here is unreadable by both consumers (arm (b) next round, the Final
      Summary's counter derivation) and no test could detect the drift.
    - the three counters as ONE line in the Final Summary, with their meaning in §5.
    - the four new fields at the emit roster, kept authoritative in exactly **one** place; the
      stale "14-field schema" literal is corrected in the same edit.
  - `templates/skills/second-opinion-gate/SKILL.md.j2` §5 additionally absorbs ADR-012's full
    round order and the counter/wire semantics prose.
  - `tests/render/test_review_pida_and_freeze.py` — **retarget, do not delete.** Both deleted
    blocks are pinned by currently-green assertions in this file, and Phase 3's exit runs it:
    - `:240-244 test_no_reinvoke_clause_is_guarded_and_present` — assert the rule against
      `gate_skill()` (`SKILL.md.j2:193-196` owns it now) and **drop the
      `not in review_off()` arm**: §5 is loaded unconditionally in both configs, so the rule
      reaches a `models: []` harness by design.
    - `:279-288 test_round_state_contract_is_reachable_from_every_harness` — keep the
      both-configs reachability intent its docstring names (assert the load imperative reaches
      `review_off()`), and move `"never replaced wholesale"` to `gate_skill()`.
  - **(out):** any restatement of the trigger or round-state rules in `review.md.j2`; any
    Python; any grade-table or `human_review_needed` change; any new skill asset (ADR-011).
- **Why the test edits are in THIS phase:** deleting the blocks without retargeting leaves two
  assertions demanding the presence of exactly what Phase 3's new negative assertion demands the
  absence of — two tests in one pytest invocation encoding opposite contracts.
- **Why the split is exact:** writing the rule in both files recreates the duplicate-contract
  shape ADR-005 exists to remove, and `review.md.j2` feeds every review-bearing command in both
  measured variants — so a stage-side restatement is also the dominant consumer of ADR-008's
  budget. One rule, one file.
- **Exit criterion:**
  `uv run pytest tests/unit/test_render_review_surfacing.py tests/render/test_render_review_read_budget.py -q`
  green.
- **Risk:** medium — this is the phase whose own failure mode is the one the PLAN describes.
- **Rollback point:** revert to Phase 1's tip; the Python schema is inert without this phase
  (fields accepted, never sent) and harmless.

### Phase 3 — Render + executed-surface gates — ✅ DONE (2026-08-01)

Resolved by re-freezing `_ATOMIC_RATCHET["review"]` 29235 → 29848 (user's call), with the
justification that file demands: compaction shown first, then the residue named as unguarded
correctness, then why the aggregate ratchet passes while this ceiling moves. Snapshots
regenerated (`tests/snapshot/regenerate.py`, rc 0) and leak-checked by **property** — no
worktree name and no `/home|/Users|/root` path survives in any fixture, per the recorded
13-instance failure whose lesson is to check the property, not the symptom.
Final: `ruff check` + `ruff format --check` + full `pytest` → **exit 0, zero failures**.

<details><summary>Blocker log (resolved — kept for provenance)</summary>

**A second ratchet the PLAN never modelled.** `tests/structural/test_command_size_budget.py::
test_atomic_commands_within_budget[review]` caps each atomic command at `measured × 1.02`.
Verified green at `HEAD` with my template changes stashed, so this is mine, not pre-existing.

**Why it fires while the aggregate ratchet passes.** This is the config-dependence ADR-008 and
R10 already record, enforced by a gate neither anticipated. The `:539-545` removal (317 chars)
sits inside `{% if config.second_opinion.models %}`; the size-budget fixture renders a harness
where that block never existed, so it frees nothing there, while every addition is
unconditional. Aggregate ratchet (models enabled): claude **−615** / codex **−123**, green.
Atomic budget (models off): **over**.

**Trimmed three times, all principled:** tightened the load imperative and the step-2 pointer
(−88); moved the `caused_by` grammar into §5, where a rule belongs under ADR-005, leaving
exemplar rows in the stage (−73). 30009 → 29921 → 29848 against a 29819 ceiling.

**Stopped at −29.** Closing the last 29 chars means cutting meaning, and shaving wording to pass
a gate after the logic is settled is precisely the unreviewed-compaction failure this PLAN
names as a defect source (the reference case inverted a negation that way). Escalated instead.

Everything else in Phase 3 is done and green: the negative restatement assertion (both deleted
blocks), the ADR-012 round-order test with the lone arm-(b) case, the `caused_by` grammar
assertion, the emitted-roster test, the two-config load-line test, and the renderer enablement
guard with its three tests. `test_surface_baseline.py` green without a re-freeze.

**Not done, and not blocked by the above:** the self-harness re-render. `/harness-maker:make
--update` owns it — not invocable from this stage's Bash, and conventionally its own
`chore(harness):` commit. No gate depends on it; the ratchet and render tests all render fresh.

</details>

**Carry into the next PLAN that touches command size:** this PLAN modelled one ratchet and there
are two. `test_command_size_budget` caps each atomic command at `measured × 1.02` and renders a
**models-off** harness, so any `{% if config.second_opinion.models %}`-guarded removal frees
nothing there while unconditional additions still cost. A budget computed only against
`surface_baseline.json` will keep missing this.
- `depends_on`: `[2]`
- `parallel_group`: `serial-3`
- `merge_hazards`: rendered `.claude/` output and render snapshots; the surface ratchet.
- **Scope (in):** re-render the self-harness; add a structural test asserting the **executed**
  surface — the four keys present in the rendered roster line *and* in the emitted example, and
  a semantics assertion that distinguishes `terminal:false` from an unmeasured row (key presence
  alone must not pass); add a two-config render test asserting the unconditional SKILL load line
  is present under both `second_opinion.models: []` and `models: ["codex"]`; add a **negative**
  render assertion that the rendered review command contains no restatement of the trigger or
  round-state rules — covering **both** deleted blocks (`:509-514` and `:539-545`), since the
  positive load-line test cannot detect a restatement sitting next to it; add a structural test
  asserting ADR-012's **full** round order (verify → re-review → merge → stamp → attribute →
  group/trigger → re-derive → select → apply → record) survives rendering, exercised against a
  lone arm-(b) reference case so a fast-path regression fails it; add a `Status`-cell grammar
  assertion against the rendered example row; add a render-time enablement guard for
  `second-opinion-gate`. **(out):** `tests/structural/surface_baseline.json` (Phase 4 owns it).
- **Enablement guard behavior (named, not left to the executor):** when `second-opinion-gate` is
  absent from the enabled skills while the review stage renders, the renderer **auto-adds it and
  emits a one-shot advisory** — it does **not** abort. This matches the `interview.py:161-178`
  force-enable precedent and satisfies CLAUDE.md checkpoint #1: a hard raise would turn
  `/harness-maker:make --update` into a total render failure for any user who had trimmed that
  skill, with no migration path.
- **Exit criterion:**
  `uv run pytest tests/structural tests/render tests/unit/test_render_*.py -q` green — including
  `test_surface_baseline.py`, which must pass **without** a re-freeze. **Only a
  `test_surface_baseline.py` failure means the budget was wrong** — halt and reopen ADR-008 in
  that case alone. Any other red in this command is an ordinary defect in Phase 2/3's own edits;
  attributing it to the budget would reopen a correctly-measured ADR.
- **Risk:** medium
- **Rollback point:** revert to Phase 2's tip; the un-re-rendered harness keeps the old loop.

### Phase 4 — Post-land baseline tightening (optional)
- `depends_on`: `[3]`
- `parallel_group`: `serial-4`
- `merge_hazards`: must not run inside the task worktree.
- **Owner:** the human operator, **after** `/hm:wrapup` squash-lands the branch.
- **Scope (in):** re-freeze `tests/structural/surface_baseline.json` so the ratchet tightens to
  the new, smaller surface. **(out):** everything else.
- **Why separate:** `tests/structural/_surface_baseline.py:155-176` `assert_sha_is_durable`
  refuses a SHA that is not an ancestor of `main`, so this cannot run from
  `hm/review-round-inflation`. This phase is **optional** — Phase 3 already proves the ratchet
  passes unchanged; this only lowers the ceiling to lock in the gain.
- **Exit criterion:** from the base checkout on `main` after land:
  `PYTHONPATH=. uv run python -m tests.structural._surface_baseline` succeeds (the `-m` form is
  what `test_surface_baseline.py:213` asserts is portable; it self-refuses a non-durable SHA),
  then `uv run pytest tests/structural/test_surface_baseline.py -q` green, and
  `git diff -U0 -- tests/structural/surface_baseline.json | grep -E 'aggregate_chars|^[+-] *"?(claude|codex)'`
  shows each variant's `aggregate_chars` **decreased or unchanged** (equality is allowed —
  Phase 3's gate is `<=`, and requiring a strict decrease would contradict it). If any value
  increased, do not commit: that contradicts Phase 3 and means the ratchet was never green.
- **Risk:** low
- **Rollback point:** `git checkout tests/structural/surface_baseline.json`.

## 🧪 Testing Strategy

**Unit** (Phase 1) — `tests/unit/test_review_telemetry.py`: the four fields default to `None`; a
pre-change row validates; the three wire states are distinguishable; `extra="forbid"` still
rejects unknown keys. `tests/unit/test_privacy_doc_schema.py` (existing) covers the doc gate.

**Render** (Phases 2-3) — the two-config load-line test is the one that would have caught the
ADR-005 relocation defect the validator found: it renders with `second_opinion.models: []` and
asserts the imperative is present. `tests/render/test_render_review_read_budget.py` guards the
extractors against heading drift.

**Structural** (Phase 3) — the executed-surface test asserts the roster line *and* the example
record, not a whole-file substring. This is the repo's documented lesson: a gate scoped to
prose stays green for a working instruction and an inert one alike
(`REVIEW-autopilot-advance-noop-2026-07-31.md` finding #26), and the existing
`tests/structural/test_no_positional_params_in_commands.py` is the shape to copy.

**Manual** — one `/hm:review` run on a real change after Phase 3, checking that a lone finding
attributed to a prior fix takes the re-derivation path and that the terminal telemetry row
carries `terminal: true` with integer counters.

**Not tested, by construction (ADR-007):** whether a re-derivation is *correct*. No oracle
exists in this repo for that judgment.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Phase 0's budget is insufficient — the relocation does not pay for the additions | medium | Phase 2/3 blocked | Phase 0 measures before any prose exists; the halt condition and the ADR-008 reopen are named, not improvised |
| R2 | A re-derivation is wrong and passes the round | medium | a new regression ships | Not mitigated — ADR-007 accepted limitation. Measure B is the named follow-up |
| R3 | The counters are LLM-emitted and drift from reality | medium | measurement is noisy | ADR-004 derives them from per-row `caused_by`; `attribution_unknown_n` absorbs uncertainty instead of forcing a wrong binary |
| R4 | The telemetry schema semantics turn out wrong after rows exist | low | append-only rows cannot be re-interpreted | ADR-006/009 make absent, false and measured-zero distinguishable up front; a wrong *value* is still permanent |
| R5 | Relocating the contract loses it for `models: []` harnesses | low | convergence contract unreachable | Unconditional load line + two-config render test + render-time enablement guard (Phase 3) |
| R6 | Phase 2's own prose edit compacts a rule into an inverted meaning | medium | the exact reference-case defect | The contract has one owner (ADR-005); Phase 3's exit includes a post-render read of §5 before the phase closes |
| R7 | Phase 4 is skipped silently | medium | ratchet not tightened | Phase 4 is explicitly optional with a stated owner; skipping it leaves the ratchet correct, only looser. This holds **because no raise is taken** — under a raise it would have left main red, which is why the raise was avoided |
| R8 | Arm (b) never fires, or fires always | medium | measure A misses its target cases, or taxes every late round | ADR-012 pins the order, stamps `caused_by` once at first appearance, and scopes arm (b) to findings new this round; Phase 3's structural test uses a lone arm-(b) reference case so a fast-path regression fails |
| R9 | The `Status`-cell grammar drifts between rounds | medium | attribution unreadable; the two counters disagree with their own rows | Grammar is literal in Phase 2's scope and asserted against the rendered example in Phase 3 |
| R10 | A `models: []` harness pays ~160 lines of irrelevant §5 context per review **and** a +129 template-char (claude +645) surface growth, because its half of the budget's removal side never renders | high (certain) | context cost invisible to the ratchet, which measures one config | Accepted (ADR-011 + ADR-008, user decision). The split into a generic skill is the named follow-up and would remove both halves at once |

## ✅ Success Criteria

- [x] The Auto-Fix Loop re-derives the model when a finding is attributed to a prior round's
      fix, even when it is the only finding in its subsystem that round.
- [x] A lone, unattributed finding still takes the immediate-patch path (no cost added to the
      cases the loop already handles in one round).
- [x] The iteration record carries `caused_by` per row and a `group_key` with its derived prefix.
- [x] The Final Summary states `unreviewed_fix_count`, `regression_attributed_n` and
      `attribution_unknown_n` on every exit path.
- [x] Exactly one telemetry row per review carries `terminal: true` with integer counters; all
      others carry `terminal: false` with null counters.
- [x] `PRIVACY.md` documents all four new fields and `test_privacy_doc_schema.py` is green.
- [x] `test_surface_baseline.py` is green **without** a re-freeze, and no ceiling raise is taken.
- [x] Both restatements (`:509-514`, `:539-545`) are gone from every rendered review-bearing
      command, and the negative render assertion covers both.
- [x] The rendered round order matches ADR-012 end to end, and a lone arm-(b) reference case
      takes the re-derivation path rather than the fast path.
- [x] `caused_by` appears only in the pinned `Status`-cell grammar, and is stamped once.
- [x] The SKILL load imperative renders under `second_opinion.models: []`.
- [x] No grade-table change, no `human_review_needed` change, no new config key.

## 🔍 Plan Validation

**Cross-model second opinion (Step 4 pre).** Both enabled models ran: `codex` — `invoked`,
10 findings; `antigravity` — `invoked`, 4 findings. Both independently reported that the
originally-locked `≥2 same subsystem` trigger would let the chain-initiating findings through.
Per `[wiki:review] reproduction-outranks-consensus-count`, the claim was not adopted on the
count: the reference REVIEW's round tables were re-counted by subsystem, which confirmed #7 was
the only ownership finding in round 2 and #20 the only slug finding in round 5. Interview round
4 then revised the trigger (ADR-001). One codex finding is `unresolved` — whether measure A has
a testable execution surface — because no oracle in this repo can settle it; it is recorded in
ADR-007 rather than adjudicated.

**plan-validator: MAJOR_REVISION → resolved.** Four critical critiques, each reproduced against
the code before adoption:

| Critique | Verified at | Resolution |
|---|---|---|
| P1's exit could not detect the PRIVACY schema-drift gate it breaks | `tests/unit/test_privacy_doc_schema.py:20`, `PRIVACY.md:96-97` | Phase 1 scope += `PRIVACY.md`; exit += that test |
| The surface baseline is shrink-only, so P3's exit was unreachable and P4's re-freeze was the forbidden ceiling-raise | `tests/structural/test_surface_baseline.py:255-277` | Interview #9 → ADR-008 (pay, don't raise) + Phase 0 measurement + Phase 4 made optional |
| ADR-005 would leave the load imperative inside the second-opinion guard | `review.md.j2:338-342` vs `:509-514` | Unconditional load line + two-config render test + enablement guard (Phase 3) |
| Terminal-only counters on per-round rows collide with ADR-006's null semantics | `review.md.j2:595` | Interview #10 → ADR-009 `terminal` discriminator |

**plan-validator second pass.** All four pass-1 criticals were verified **against the code**, not
against the prose, and returned RESOLVED. The pass raised **one new critical, created by the
revision itself**: Phase 2's scope line instructed the executor to write ADR-001's trigger into
*both* `review.md.j2` and the SKILL — recreating the duplicate contract ADR-005 exists to remove,
and consuming the ratchet budget ADR-008 rests on. Fixed here rather than re-validated a third
time (the stage caps validator re-runs at one to prevent a loop): Phase 2's scope now puts the
rule text in SKILL §5 only and leaves the stage a pointer plus its mechanical surface, and
Phase 3 gains a **negative** render assertion — the positive load-line test cannot detect a
restatement sitting next to it. Second-pass warnings and suggestions also applied: the ratchet's
axis corrected to the two target variants with the precise `hm-*` glob exemption (ADR-008);
Phase 0 now drafts the additive prose so its delta is measured rather than estimated, with
Phase 3 named as the binding gate; the enablement guard's behavior fixed to auto-add + advisory
rather than an unspecified abort; Phase 4's `--stat` replaced with a command that prints the
values, `-m` invocation for parity with `test_surface_baseline.py:213`, and equality allowed to
match Phase 3's `<=`; `PRIVACY.md` rows scoped inside a marker block against the document-wide
backtick scan; `review_telemetry.py`'s two docstrings added to Phase 1 scope.

**Second `/hm:plan` invocation (2026-08-01, after `/hm:execute` Phase 0 halted).** The halt
refuted ADR-008 as written, so the PLAN was re-opened. Both models ran again (`codex` invoked, 5
findings; `antigravity` invoked, 5 findings), then the validator returned **MAJOR_REVISION** with
4 criticals. Every claim was reproduced against the code before adoption:

| Finding | Source | Verified at | Resolution |
|---|---|---|---|
| The ~830-char "irreducible minimum" is not a credible floor | codex P1 | re-measured on drafted text | Four reductions → 551 added; net +129, then negative |
| **`review.md.j2:539-545` is a second, uncounted removal** | plan-validator critical | live render: 317 chars, both variants; `SKILL.md.j2:193-196` already owns the rule | Counted → net **−188**; **the raise is not needed and is not taken** |
| **Arm (b) cannot fire — `caused_by` was written after fix selection** | codex P1 | `review.md.j2:518-565` vs ADR-001/004 | ADR-012 pins the full round order |
| Arm (b) would then be always-on from round 3 (re-attribution + merged domain) | plan-validator critical | `SKILL.md.j2:185-191` retains findings by `id` | ADR-012: stamp once at first appearance; domain = findings new this round |
| The RED window could launder unrelated growth; re-freeze unreachable through `wrapup:189` | codex P1, antigravity P1, plan-validator critical | `wrapup.md.j2:180-189` hard-stops on a failing suite | **Dissolved** — with a negative budget nothing goes red |
| `caused_by` in the `Status` cell has no grammar | plan-validator warning | `review.md.j2:558-560` holds a different enum | Literal grammar pinned in Phase 2, asserted in Phase 3 |
| The pinned order omitted verify + re-review | plan-validator warning | `review.md.j2:530-538` | ADR-012 states the sequence end to end |
| Unconditional §5 load costs a `models: []` harness ~160 irrelevant lines | codex P2 | skill is 231 lines, §5 starts at 165 | **Accepted risk** by user override → ADR-011, with the split named as the follow-up |
| Antigravity's alternative: patch `assert_sha_is_durable` to accept a task-branch SHA | antigravity P1 | — | **Rejected** — disabling the durability check to ship a change is worse than the window it removes |

**Second-pass re-validation (budget exhausted).** All four criticals above were re-verified
against the code and returned RESOLVED. The pass raised **two new criticals, both created by the
revision**, plus two warnings and a suggestion — all applied here:

| New finding | Verified at | Applied |
|---|---|---|
| Phase 2 deletes two strings that `tests/render/test_review_pida_and_freeze.py:240-244,279-288` assert the presence of; Phase 3's exit runs that file, and its halt text would blame ADR-008 | read both tests; `gate_skill()` helper exists at `:67` | Both tests added to Phase 2 scope as **retarget, not delete**; Phase 3's halt text scoped to a `test_surface_baseline.py` failure only |
| ADR-004 counts non-null **rows**, but a reverted/overlap-skipped finding emits a second row next round with the same stamp → double-count | `review.md.j2:528,536`; `SKILL.md.j2:169-171` | Derivation changed to **distinct finding `id`s**; Phase 1 pins it with a reverted-then-applied case |
| Two opposite sign conventions for "the budget" | Phase 0 exit vs ADR-008 table vs interview #12 | One convention stated in ADR-008 (`removed − added ≥ 0`) and every table/sentence restated in it |
| The budget is config-dependent: a `models: []` harness gets +129 growth, not a saving | `:539-545` is `{% if %}`-guarded; the additions are unconditional | Qualified in ADR-008; folded into R10 |
| ADR-012 rule 2 relies on an uncited property of `codex_adapter.finding_id` | `codex_adapter.finding_id:51-61` | Cited inline, with the dependency named |

**The validator re-run budget is now spent (one per MAJOR_REVISION cycle), so these five fixes
are themselves unvalidated.** That is the same exposure ADR-007 records for the Auto-Fix Loop,
and it is stated here rather than left implicit.

Note on the biggest one: the uncounted removal was found by the validator, not by the
measurement phase that existed to find exactly this. Phase 0 counted the removal it had been
told about rather than every removal ADR-005 mandates — the same shape as the defect this PLAN
addresses, one level up.

Pass-1 warnings resolved: `tests/render/` added to Phase 2/3 exits; the three emit sites enumerated in
Phase 2's scope; Phase 4 given a literal command, exit assertion and owner; a risk register and
per-phase rollback points added. Suggestions resolved: rejected alternatives added to ADR-002
and ADR-006; the two SPEC files added to Phase 1 scope; `group_key` given a derivation rule
(ADR-010).
