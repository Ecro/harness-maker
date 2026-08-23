---
type: spec
task_slug: a5-duplicate-coverage-block
status: approved
created: 2026-08-23
tier: 2
tags: [harness-maker, spec, prompt-templates, execute-stage, test-reviewer, gating]
test_framework: pytest
research_doc: "[[RESEARCH-a5-duplicate-coverage-block]]"
summary: "Narrow Phase A.5's duplicate-coverage trigger from scenario-ID cardinality to observable-level duplication"
---

# SPEC — Phase A.5 duplicate-coverage trigger

## 🎯 Intent

`/hm:execute` Phase A.5 blocks whenever one SPEC scenario ID is covered by more than one
test, because `test-reviewer_body.md.j2`'s Hard Rule states the trigger as *"a scenario
covered twice"*. That contradicts the same agent's own rubric §1 — *"at least one dedicated
test function"* — and drops the qualifier the stage template carries at
`execute.md.j2:222`, where duplication is defined **per observable**, not per scenario ID.

Observed on `~/strange_chess` (`harness_maker_version: 0.54.0`, `archer-side-contrast`): five
tests asserting five different observables under one ID were judged duplicate coverage, and
the phase blocked for two rounds before escalating. The trigger is stated too coarsely; the
gate itself is correct and stays.

## 🌅 Outcomes

- A Phase A.5 reviewer that finds N tests under one scenario ID, each asserting a **different**
  observable, returns PASS for that scenario — no `per_scenario` FAIL, no round consumed.
- A reviewer that finds two tests asserting the **same** observable still FAILs that scenario,
  and the existing repair arm (*retarget or delete*) is a legal, executable repair for it.
- A maintainer reading `test-reviewer.md` finds no clause contradicting rubric §1.
- A future edit that reintroduces the coarse trigger at any one of the four sites fails a
  structural test rather than shipping.

## 📋 In-Scope Scenarios

### AC-001: reviewer Hard Rule states the trigger per observable

**Given** the **rendered** `test-reviewer` body for every target
**When** the Hard Rule that routes out-of-category findings into `per_scenario` is read
**Then** its duplication arm is qualified to duplication of the same **observable**
**And** its scenario-ID-mismatch arm carries no such qualifier
**And** no clause in the rendered body states the trigger as a count of tests sharing a scenario ID

### AC-002: all four A.5 duplication sites carry the same qualifier

**Given** the four sites that express the A.5 duplication trigger — the reviewer Hard Rule, and
the execute stage's coverage-lens table row, its `<brief>` routing sentence, and its dispatch
string — read from the **rendered** bodies for every target
**When** each site's duplication sentence is extracted
**Then** every extracted sentence carries the observable-level qualifier
**And** none of them states the trigger in scenario-ID-cardinality terms
**And** the literal "for the same observable" occurs exactly five times in total (four edited
trigger sites plus the pre-existing Phase A authoring rule)

### AC-003: rubric §1 keeps "at least one dedicated test function"

**Given** the rendered `test-reviewer` body after the change
**When** the SPEC-alignment rubric's first bullet is read
**Then** it still requires **at least one** dedicated test function per In-Scope Scenario
**And** it does not require exactly one

### AC-004: rendered reviewer prompt is internally non-contradictory

**Given** the `test-reviewer` body rendered from
`src/harness_maker/templates/agents/test-reviewer_body.md.j2` (harness-maker does not render its
own agents to disk — there is no `.claude/agents/` in this repo)
**When** it is judged against the `agent_prompt` rubric with the SPEC-alignment rubric and the
Hard Rule as the subject
**Then** no criterion reports a contradiction between the two clauses

## 🚫 Non-Goals

- **Approach B (round-1 plan-routing exit) is out of scope.** After AC-001 the coarse-scenario
  case is no longer a FAIL, so the exit would fire on cases the narrowed trigger already
  forgives, and it would hand `/hm:execute` an escape hatch for genuine duplication.
- **Approach C (demoting duplicate coverage to advisory) is out of scope** — it reopens the
  silent-drop hole `e446c8db` closed.
- **No upstream gate.** `/hm:spec` and `plan-validator` gain no "one scenario, one observable"
  check; a coarse scenario ID stays legal and unflagged.
- No change to the A.5 round budget, the merge algebra, the three repair arms, the reviewer
  JSON schema, or any Python module outside the new test file.
- No edit to `~/strange_chess`. That project picks this up by re-rendering.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard; the oracle is a structural test |
| Change surface | 2 template files (prose only) + 1 new test file | A안 단독 as locked in interview Round 1 |
| Schema / Python | no change to reviewer JSON schema or `harness_maker/*.py` | The defect is prompt wording, not code |
| Determinism | the structural test must not shell out to an LLM | Runs in the default suite; LLM judgment is AC-004's separate tier |
| Surface baseline | `tests/structural/surface_baseline.json` / `instruction_baseline.json` may need re-baselining | Prose edits move the aggregate character ratchet (`e446c8db` precedent) |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| AC-001 | unit | `tests/structural/test_duplicate_trigger_observable_parity.py::test_ac_001_reviewer_hard_rule_is_observable_qualified` |
| AC-002 | unit | `tests/structural/test_duplicate_trigger_observable_parity.py::test_ac_002_execute_body_carries_the_qualifier_at_every_trigger_site`, `::test_ac_002_no_cardinality_phrasing_survives_in_the_a5_region`, `::test_ac_002_brief_keeps_the_mismatch_arm_unqualified` |
| AC-003 | unit | `tests/structural/test_duplicate_trigger_observable_parity.py::test_ac_003_rubric_keeps_at_least_one_dedicated_test` |
| AC-004 | manual | Render the reviewer body, dispatch `judgment-reviewer` against it with `rubric_id: agent_prompt`, record the per-criterion verdict and hash `src/harness_maker/templates/agents/test-reviewer_body.md.j2` as the subject |

## ❓ Open Questions

None. All four RESEARCH open questions were resolved in interview Round 1:
- Scope → A안 단독 (Q1, revised after the user challenged Approach B's exit frequency).
- rubric §1 → "at least one" retained (Q2).
- Oracle → cross-template parity structural test (Q3).
- The fourth site (`execute.md.j2` coverage-lens question) → in scope, folded into AC-002;
  leaving it coarse would reintroduce the trigger through the lens question itself.

## 🔍 Refinement Decisions

- **Round 1** — Locked: scope = Approach A alone; rubric §1 keeps "at least one"; oracle =
  cross-template parity structural test. The user challenged the recommended A+B with *"too
  frequent an exit?"*; on re-examination A and B overlap — A removes the FAIL that B's exit
  was meant to escape, and A also makes the previously-illegal *retarget or delete* repair arm
  executable for every remaining FAIL. Recommendation was revised to A alone before the second
  question, and the user confirmed it.
- Step 0 skip did not apply: the change spans two templates, alters gate semantics for all
  consuming projects, and RESEARCH established that render-grep alone cannot detect this class.
- **Amended 2026-08-23 from `/hm:plan`** (plan-validator MAJOR_REVISION, interview #5/#6):
  AC-001/002/003 now assert over **rendered** bodies rather than `.j2` source (the `is_codex`
  failure class); AC-002 gains the ID-mismatch-arm and occurrence-count assertions; AC-004's
  judgment subject moved off `.claude/agents/test-reviewer.md`, which does not exist in this repo.
