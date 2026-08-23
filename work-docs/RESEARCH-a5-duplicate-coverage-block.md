---
type: research
task_slug: a5-duplicate-coverage-block
status: complete
created: 2026-08-23
tags: [harness-maker, research, execute-stage, test-reviewer, phase-a5, gating]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[wiki:architecture] multi-lens-phase-a5-gate"]
summary: "Block is by design, but its trigger contradicts the rubric's own 'at least one dedicated test' clause"
---

# RESEARCH — Phase A.5 blocking on "duplicate dedicated coverage"

## 🎯 Recommended Direction

**The block is intended machinery firing on an unintended trigger.** The routing rule that
turns "a scenario covered twice" into a blocking `per_scenario` FAIL was added deliberately
(commit `e446c8db`) and works as written. But it contradicts the same agent's SPEC-alignment
rubric, which requires only **"at least one** dedicated test function" per scenario, and it
drops the qualifier the execute stage actually carries — duplication is defined **per
observable**, not per scenario ID. In `archer-side-contrast` the five S1 tests assert five
different observables, so the reviewer applied the coarse reading and blocked coverage that
the fine reading would have passed.

Recommended fix direction: narrow the reviewer's duplication trigger to observable-level
duplication, and give the genuine "scenario ID is too coarse" case an explicit,
round-1 exit that routes to `plan` instead of burning the 2-round budget. `stuck`'s Path B
recommendation was correct; the cost was that the harness took two full reviewer rounds to
reach a conclusion it could have reached in one.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (harness template semantics),
with a secondary **Risk** lens on gate incentives. `--deep` not set; topic was already
concrete (a specific gate firing on a specific input).

## 🛠️ Approaches Found

### Evidence base

| Locator | Text | Reading |
|---|---|---|
| `templates/agents/test-reviewer_body.md.j2:21` | "Every In-Scope Scenario (S1, S2, …) in SPEC has **at least one** dedicated test function." | N>1 tests per scenario is explicitly permitted |
| `templates/agents/test-reviewer_body.md.j2:105` (rendered `.claude/agents/test-reviewer.md:136`) | "a scenario **covered twice** … → a `per_scenario` entry … `quality: "FAIL"` … (this blocks — PASS requires every `per_scenario.quality` to be PASS)" | N>1 tests per scenario is a blocking defect |
| `templates/stages/execute.md.j2:222-224` | "do NOT write both an AC test and a scenario test **for the same observable**; the Phase A.5 test-reviewer adjudicates the union for duplication or coverage holes" | duplication is defined at the **observable** level |
| `templates/stages/execute.md.j2:317-322` | repair arm 3 for a `per_scenario` FAIL with no matching `blocking_issues`: "**retarget or delete** the offending test named in its `covered_by`" | the only sanctioned repairs are retarget or delete |

Lines 21 and 105 are mutually exclusive as stated. Line 222's "same observable" is the
qualifier that would reconcile them — and it lives in the stage template, which the reviewer
agent never reads. The consuming project `~/strange_chess` is on `harness_maker_version:
0.54.0` and carries this exact text, so this is live behavior, not stale render.

### Approach A — Narrow the trigger to observable-level duplication

| Field | Content |
|---|---|
| Assumption | The `e446c8db` routing rule meant "two tests asserting the same thing", not "two tests tagged with the same ID" |
| Evidence | `execute.md.j2:222` states the observable-level definition explicitly; rubric §1 permits N tests |
| Trade-off | "Same observable" is an LLM judgment call, so the gate loses some determinism; the genuine AC-test/scenario-test overlap stays catchable |
| Compatibility | Prose-only change in `test-reviewer_body.md.j2` + the mirrored brief text in `execute.md.j2:294`; no schema, no Python |
| Risk | low |

### Approach B — Add a fourth repair arm / fast exit for coarse scenario IDs

| Field | Content |
|---|---|
| Assumption | The real defect in this class is a SPEC/PLAN granularity error, which `/hm:execute` has no authority to fix |
| Evidence | Repair arm 3 offers only *retarget* or *delete*; retargeting five distinct observables requires new scenario IDs (S1a–S1e), i.e. a PLAN edit. Neither sanctioned repair is legal here, so round 2 re-dispatched against an unchanged file and failed identically — the exact waste the third arm was written to prevent |
| Trade-off | Adds a branch to a gate the harness has been trying to simplify; must not become an escape hatch for real duplication |
| Compatibility | Fits the existing blocked-phase → `stuck` → Path B path; changes only *when* that path fires (round 1 instead of round 2) |
| Risk | medium — a mis-stated branch lets a lazy executor declare any FAIL "a PLAN problem" |

### Approach C — Demote duplicate coverage to advisory (non-blocking)

| Field | Content |
|---|---|
| Assumption | Duplicate coverage costs test-suite time, never correctness, so it should not gate Phase B |
| Evidence | Contradicted by `e446c8db`: the routing rule exists *because* the previous `suggestions`-field hole caused a reviewer that found a defect to emit nothing and return PASS |
| Trade-off | Cheapest fix, but reopens the silent-drop hole the commit closed |
| Compatibility | Requires a schema-level "advisory" carrier that does not exist |
| Risk | high — regresses a fix that was landed against a measured failure |

## ⚠️ Pitfalls

- **Incentive inversion.** As written, the gate penalizes *thorough* coverage of one
  scenario, while nothing anywhere penalizes a PLAN that lets one scenario ID stand for five
  observables. The gate fires on the symptom-bearer, not the cause. `plan-validator` and
  `/hm:spec` have no check for "one In-Scope Scenario, one observable `Then`".
- **Absent-case footgun** (`[fail:design] absent-case`, count:8). "Duplicate" was never given
  a definition inside the reviewer body; the reviewer supplied the only definition available
  to it (ID cardinality). An undefined term in a blocking rule resolves to the coarsest
  reading.
- **Repair arms that cannot be executed.** A gate must only demand repairs the stage is
  authorized to make. Arm 3 demands a repair whose legal form is a PLAN edit — Phase A cannot
  perform it, so the budget is guaranteed to exhaust.
- **Render-grep cannot catch this class.** Both templates read as correct in isolation; the
  contradiction only exists across the seam between the agent body and the stage brief.
  Compare `[wiki:architecture] multi-lens-phase-a5-gate` — the same commit already fixed one
  seam defect (`suggestions` field) of exactly this shape.

## ❓ Open Questions

1. Should the fix land in the reviewer body only (Approach A), or A+B together? A alone
   leaves the genuine coarse-scenario case burning two rounds.
2. Should `/hm:spec` or `plan-validator` gain a "one scenario, one observable" check so this
   class is caught at authoring time instead of at A.5?
3. Is `at least one dedicated test function` (§1) the intended contract, or should the rubric
   be tightened the other way (exactly one)? The `e446c8db` rationale does not say.
4. Does the same coarse reading exist in the `coverage` lens question itself
   (`execute.md.j2:275`, "no missing scenario, no duplicate") — i.e. does the fix need to
   touch three locations, not two?

## 📚 Sources

- No external sources. All evidence is repository-internal (see locator table).

## 🔗 Related Internal Docs

- `[[wiki:architecture] multi-lens-phase-a5-gate` — the three-lens A.5 gate, merge algebra,
  and the three repair arms.
- `[[commit e446c8db]]` — `feat(execute): fan Phase A.5 out to three lenses in one round`;
  originates the routing rule under investigation.
- `src/harness_maker/templates/agents/test-reviewer_body.md.j2`
- `src/harness_maker/templates/stages/execute.md.j2`
