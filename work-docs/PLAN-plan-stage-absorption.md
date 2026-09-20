---
type: plan
task_slug: plan-stage-absorption
status: implemented
created: 2026-09-20
tags: [harness-maker, plan, python, jinja2, stage-removal, migration]
spec: "[[SPEC-plan-stage-absorption]]"
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
interview_rounds: 0
adrs: 8
validator_outcome: NOT_RUN
phases_done: 5
summary: "Delete /hm:plan as a stage in five phases; execute Step 0 becomes the PLAN author and the document survives"
spec_need_verdict: add
spec_need_target: plan-stage-absorption
---

# PLAN — Plan stage absorption

> **Authored by `/hm:execute` Step 0, not by `/hm:plan`.** This is the target behaviour of the
> SPEC this PLAN implements, exercised one task early at the DRI's direction. There was no plan
> interview (`interview_rounds: 0`) and no `plan-validator` pass, which is why
> `validator_outcome` reads `NOT_RUN` rather than one of the four enum values the deleted stage
> documented. Nothing parses that field — verified: the only matches in `src/` and `tests/` are
> `plan.md.j2` itself and its render test — so the honest value costs no reader.

## 🎯 Executive Summary

**What.** Remove `/hm:plan` as a stage, interview and gate. Keep the PLAN *document*: move its
authorship to `/hm:execute` Step 0, and its DRI-owned content to the SPEC that already asks for
it. Relocate `plan-validator` to the SPEC stage as a conditional, never-blocking
`spec-validator`.

**Why.** Measured on 21 task slugs carrying both an interviewed SPEC and a PLAN: 9.70 interview
rounds per task today, 6.55 merged — a 32 % reduction whose estimate is stable across three
absorption models. 52 % of PLAN's 194 classified interview entries are questions the SPEC
interview already asks; 21 % are IC questions that should never have reached a human.

**Key decisions.** IRR-001 hard removal with no stub · IRR-002 enum removal plus a one-shot
pipeline migration · IRR-003 the SPEC-need producer moves to execute (ADR-001…005 below cover
the *how*).

**Estimated impact.** 5 Python modules, ~12 templates, 4 agent assets, 68 test files, 3 golden
fixtures. One BREAKING CHANGELOG entry.

## 📚 Prior Work

- **`PLAN-harness-diet`** — the direct precedent for removing a command surface. ADR-009 (no
  stubs; CHANGELOG BREAKING + `/hm:help`), ADR-012 (a retired key ships atomically with its
  schema removal) and ADR-014 (`/hm:loop` breaks first and needs its own ADR) are all reused
  here rather than re-derived.
- **`second_opinion` migration** — `answers_from_harness_yaml`'s one-shot silent conversion of
  `codex_second_opinion.enabled` is the shape Phase 3's pipeline drop copies.
- **`failures.md` classes that bear on this work** —
  `new-marker-content-field-must-update-every-reader` (count:3, every hand-made reader list was
  wrong: Phase 0 exists because of it), `fix-introduced-defect-passes-all-gates` (count:13,
  green gates measure the coverage that existed before the fix) and
  `assertion-invariant-over-named-dimension` (count:16, assertions not bound to the dimension
  they name).
- **`RESEARCH-ai-native-sdlc-vs-intent-world` Follow-up 2(a)** — the ownership table this SPEC
  implements, and its own verdict that the work is "a large migration … candidate for its own
  PLAN".

## 🎙️ Interview Transcript

No plan interview was held — this PLAN is agent-authored under the model the SPEC introduces.
The DRI decisions it implements were taken in the `/hm:spec` interview (3 rounds, 11 questions)
and are recorded in `specs/SPEC-plan-stage-absorption.md` § Refinement Decisions. Two further
decisions were taken at the start of this stage:

| # | Topic | Question | Choice |
|---|---|---|---|
| 1 | PLAN gap | `/hm:execute` Step 1 hard-errors with no PLAN. Author it here, run `/hm:plan`, or stop? | Author it here — exercise the post-absorption behaviour |
| 2 | SPEC approval | Stamp the DRI acceptance now, or leave `land: hold`? | Stamp now (`state: approved`, `land: ok`) |

## 📐 Architecture Decision Records

### ADR-001: Phase 0 pins the reader set before anything is deleted
**Status:** Accepted (2026-09-20, agent-authored under the absorbed model)
**Context:** AC-003 requires that every PLAN reader still resolves against an execute-written
PLAN. A comparison needs a "before", and after Phase 4 the deleted stage cannot produce one.
**Decision:** The reader set is DISCOVERED by traversal (never listed) and the orphan invariant
that guards it lands in **Phase 1**, the first additive phase — not in a phase of its own.
**Amended 2026-09-20 during Phase A.4.** The original decision gave this its own Phase 0. That
phase could not exit its own RED gate: its only red test (`test_execute_is_a_plan_author`) turns
green only when Phase 1 makes `execute.md.j2` an author, and its two other tests are negative
invariants that are vacuously green until Phase 4. A phase whose entire test set is green has no
RED gate to pass, and A.4's case-2 justification requires the red positive sibling to be in the
same commit. Merging preserves the intent — Phase 1 still precedes Phase 4, so the baseline is
pinned before anything is deleted.
**Consequences:**
- ✅ The invariant exists before the deletion that would violate it, which is what ADR-001 is for.
- ✅ Every phase has a red test it makes green.
- ⚠️ The invariant is committed alongside the first template mutation rather than ahead of it;
  it is recomputed from the tree at test time, so it does not depend on being captured earlier.
**Rejected alternatives:**
- Discover at verification time — rejected: post-deletion discovery finds the readers that
  survive, which is the set that cannot fail the check.
- Keep Phase 0 and let it exit with an all-green suite — rejected: that is the shape A.4 exists
  to reject, and it would have shipped two invariants nothing had ever seen fail.
**Source:** SPEC Constraints (reader discovery) + `new-marker-content-field-must-update-every-reader`

### ADR-002: Additive phases land before subtractive ones
**Status:** Accepted (2026-09-20)
**Context:** `/hm:execute` must be able to write a PLAN before `/hm:plan` stops existing, or the
repo passes through a commit where no stage can produce one.
**Decision:** Phases 1 and 2 add capability (execute authors the PLAN; spec-validator exists).
Phases 3 and 4 remove. No phase both adds and removes.
**Consequences:**
- ✅ Every intermediate phase leaves a working pipeline, so a phase can be the rollback point.
- ⚠️ Both stages transiently render, so the surface grows before it shrinks.
**Rejected alternatives:**
- Delete first and backfill — rejected: the repo cannot plan anything between the two commits,
  including this task's own remaining phases.

### ADR-003: The SPEC-need write is presence-preserving, and only the producer side changes
**Status:** Accepted (2026-09-20, from SPEC Round 2 Q5)
**Context:** `verify.md.j2` Check 6 reads `spec_need_verdict` and treats an absent key as
`PASS (N-A)`. `plan.md.j2` is its only producer today.
**Decision:** `/hm:execute` Step 0 reads before it writes — a pre-existing verdict is preserved,
an absent one is judged and written — and asserts presence afterwards (retry once, then surface
and stop). `verify.md.j2`'s Check 6 logic is unchanged.
**Consequences:**
- ✅ The smallest diff that keeps the gate alive on the normal path.
- ⚠️ **Accepted limitation:** a path where `/hm:execute` never runs still auto-PASSes Check 6.
  If execute did not run, nothing was implemented, which is what makes the residual small.
**Rejected alternatives:**
- Also make Check 6 FAIL on an absent key — rejected by the DRI as scope: it widens the blast
  radius to Check 6 and the `spec_need` CLI contract, and legacy PLANs would start failing.

### ADR-004: `spec-validator` is conditional, single-pass and never blocks
**Status:** Accepted (2026-09-20, from SPEC Round 2 Q7 / Round 3 Q10)
**Context:** `plan-validator` returned APPROVED 0 times in 54 runs. That is unproven
discrimination, not a disproven critic — it has produced genuine defects.
**Decision:** Relocate it to `/hm:spec` as `spec-validator`: one pass, no re-validation, fired
only when the SPEC declares or implies an irreversible decision or is not Step-0-light, and its
verdict never moves the SPEC's approval state. Every dispatch emits a ledger row so its
discrimination is measurable from run 1.
**Consequences:**
- ✅ The critique survives the absorption instead of vanishing with the stage.
- ✅ An unproven gate cannot hold a release while it is being measured.
- ⚠️ A real finding can now be ignored; the ledger is what makes that visible.
**Rejected alternatives:**
- Delete it — rejected: 0/54 is evidence of no discrimination, not of wrong findings.
- Block on missing irreversible decisions — deferred until the ledger shows discrimination.

### ADR-008: the batch-triage loop goes in the skill, not in this PLAN's notes
**Status:** Accepted (2026-09-20, DRI-approved mid-Phase 5 — scope addition)
**Context:** This migration broke 155 tests across ~70 files. The full suite was run **six
times** at ~10 minutes a pass before switching to "derive the failing set once, then iterate on
that set" — which took it 57 → 47 → 35 → 21 → 3 → 1 at 1–2 minutes a pass. The governing rule
(`rerun_failed` → targeted → full) was **already** in `targeted-test-selection` §"Two rules"
and already named by `/hm:execute` Phase D. It was followed for single edits and ignored here.
**Decision:** Add one arm to that skill for the case its existing wording does not cover — a
change that breaks a *population* of tests rather than a handful — with this task's measured
numbers as the evidence, plus the "never edit the tree while a suite is running" rule, which
this task also violated and had to discard a run for.
**Consequences:**
- ✅ The guidance now covers the shape that actually cost the time, in the skill both
  `/hm:execute` Phase D and `/hm:review`'s fix loop already point at.
- ⚠️ Out of this SPEC's ACs. Accepted as a scope addition because this task produced the
  evidence and the skill is where the rule lives; recorded here rather than absorbed silently.
- ⚠️ Prose, not enforcement. Nothing measures whether it is followed — the honest claim is
  that the case is now written down, not that it will be obeyed.
**Rejected alternatives:**
- Restate the existing rule more forcefully — rejected: it was already correct and correctly
  placed. A rule ignored once does not become a different rule by being louder.
- File it as a follow-up — the DRI chose to add it now, with the measurements still at hand.
**Source:** DRI question during Phase 5

### ADR-007: the enum IS the stage — Phases 3 and 4 are not separable the way ADR-002 assumed
**Status:** Accepted (2026-09-20, discovered during Phase 3)
**Context:** ADR-002 sequences additive phases before subtractive ones, and the phase plan
treated "remove `AtomicStage.PLAN`" (Phase 3) and "delete the rendered `/hm:plan` command"
(Phase 4) as two steps. Measured after the enum edit: `plan.md` **stops rendering immediately**.
`synthesize._ATOMIC_STAGES = [s.value for s in AtomicStage]` drives the stage-command render at
three sites; `_COMMAND_DESCRIPTIONS` is only a description lookup. An earlier reading of that
map concluded the two were independent. That reading was wrong.
**Decision:** Treat the enum member and the rendered stage as **one thing**. Phase 3 removes
both by construction. Phase 4 is reduced to cleaning up what is now dead: the orphaned
template file, the `plan-validator` assets, the registry and description entries, the
sensitivity registry, prose references, and the announcement.
**Consequences:**
- ✅ The single source of truth is real and the removal cannot half-land.
- ✅ The Phase 2 transitional restore of `plan-validator` is moot — nothing dispatches it once
  `plan.md` stops rendering — so Phase 4 deletes it and returns the Side inventory ceiling to 61.
- ⚠️ ADR-002's guarantee is weaker than written: Phase 3 is subtractive to the rendered surface
  whether or not Phase 4 has run. It is still ordered after the additive Phase 1, which is the
  part that mattered (execute must be able to author a PLAN before plan stops existing).
**Rejected alternatives:**
- Keep the enum member and gate the render elsewhere — rejected: it invents a second source of
  truth for which stages exist, which is the defect class this repo keeps paying for.
**Source:** Phase 3 implementation, verified by rendering and listing `commands/hm/`.

### ADR-006: the SPEC-need write gets a CLI verb, not a prose recipe
**Status:** Accepted (2026-09-20, raised in `/hm:execute` Phase C, DRI-approved, SPEC re-stamped)
**Context:** AC-002's oracle is a property over *arbitrary* prior frontmatter states. A prose
instruction in `execute.md.j2` has no execution surface, so a test can only grep its text —
the exact shape CLAUDE.md records as having shipped four silent-skip bugs.
**Decision:** Add `hm spec_need frontmatter-upsert --root <r> --slug <s> --verdict <v>
--target <t>`, which performs the read-preserve-write atomically. `execute.md.j2` calls it in
one line. Recorded as **IRR-004** (public API/CLI contract, `source: execute`); appending it
invalidated the SPEC approval, which the DRI re-issued.
**Consequences:**
- ✅ AC-002 becomes a real Hypothesis property test over generated frontmatter states.
- ✅ The template carries a call, not a procedure the renderer cannot check.
- ⚠️ One more public CLI surface to keep stable, and `spec_need.py` joins `paths_to_mutate`.
**Rejected alternatives:**
- Internal helper, no subcommand — rejected: the template would still instruct in prose, so the
  test and the thing that actually runs would diverge (`assertion-invariant-over-named-dimension`).
- Keep prose and downgrade AC-002 to a `golden` oracle — rejected: it verifies the mechanism
  that keeps Check 6 alive most weakly of all the options.
**Source:** `/hm:execute` Phase C irreversible-decision check

### ADR-005: `codex_ledger`'s `stage` Literal keeps `"plan"`
**Status:** Accepted (2026-09-20)
**Context:** `codex_ledger.py:69` types `stage` as `Literal["review", "plan", "health"]`, and
`.claude/observability/second-opinion.jsonl` holds historical rows with `stage: "plan"`.
**Decision:** Leave the Literal alone. The stage stops *producing* those rows; the reader must
still parse the ones already written.
**Consequences:**
- ✅ `verifier_discrimination report` keeps working on the existing ledger.
- ⚠️ A dead enum member survives; a comment records why.
**Rejected alternatives:**
- Remove it for tidiness — rejected: it makes every historical row unparseable, and the
  `stage`-enum parity test compares names, so it would not have caught the loss.

## 🏗️ Technical Design

**Current state.** Seven atomic stages. `plan.md.j2` (855 lines) owns the second interview, ADR
promotion, `plan-validator`, SPEC-need detection (Step 1.7) and loop-mode per-iter planning
(Step 1.5). `AtomicStage` is an `Enum` whose members drive `autonomy.pipeline`.

**Affected components.**

| Layer | Files |
|---|---|
| Stage templates | `stages/plan.md.j2` (delete) · `execute.md.j2` · `spec.md.j2` · `wrapup.md.j2` · `review.md.j2` · `verify.md.j2` |
| Command templates | `commands/hm/loop.md.j2` · `loop-p5-batch.md.j2` · `help.en.md.j2` · `help.ko.md.j2` |
| Agents | `plan-validator.md.j2` + `plan-validator_body.md.j2` (→ `spec-validator`) · `stuck.md.j2` + `stuck_body.md.j2` · `trajectory-monitor.md` |
| Python | `spec_need.py` (new `frontmatter-upsert` verb) · `models.py` (AtomicStage, pipeline default) · `interview.py` (`answers_from_harness_yaml`) · `step_sensitivity.py` (STAGES + plan entries) · `autopilot_caps.py` (`_JUDGMENT_GATED_STAGES`) · `synthesize.py` (command map, agent descriptions) · `presets.py` (agent model maps) |
| Tests | 68 files — unit 37, structural 9, snapshot 8, fixtures 6, integration 3, render 1, codex-compat 1, manual 3 |
| Goldens | `tests/structural/autopilot_gate_golden.json` · `tests/fixtures/rendered_command_names.json` · `tests/fixtures/autopilot_caps_baseline.json` |

**Data flow after the change.** `/hm:spec` (interview + irreversible decisions + spec-validator)
→ `/hm:execute` Step 0 (writes `work-docs/PLAN-{slug}.md` incl. the SPEC-need fields) → Phases
A…D → `/hm:review` → `/hm:verify` (Check 6 reads the PLAN, unchanged) → `/hm:wrapup`.

**API changes.** `/hm:plan` removed. `AtomicStage.PLAN` removed. One new CLI verb,
`hm spec_need frontmatter-upsert` (ADR-006, IRR-004). `interview_rounds` stays frontmatter the
spec stage writes.

## 📝 Implementation Plan

**Phase status (2026-09-20).** All five DONE. Gate at exit: `ruff` clean, `ruff format --check`
clean, `mypy --strict` clean, `pytest` **8804 passed / 1 failed**.

The one failure is **not this task's**: `test_deliverable_single_source` reports
`gitignore-only: ['MUTATION']`. `.gitignore` carries `!work-docs/MUTATION-*.md` from commit
`865e3ef5` and `worktree.DELIVERABLE_PREFIXES` was never given the matching entry — one half of
a pair, landed by the concurrent session. Neither file is in this task's change set, and
`worktree.py` is adjacent to that session's in-flight work, so it is reported rather than
fixed here.


### Phase 1 — `/hm:execute` Step 0 authors the PLAN, guarded by the reader invariant  ·  **DONE**
- `depends_on`: []
- `parallel_group`: `templates-additive`
- `merge_hazards`: none (owns `execute.md.j2`; Phase 2 owns `spec.md.j2`)
- **Scope (in):** `tests/structural/test_plan_reader_baseline.py` — the discovered-reader
  orphan invariant (AC-003, ADR-001); `spec_need.py` gains the `frontmatter-upsert` verb (ADR-006/IRR-004) that owns
  the presence-preserving write; `stages/execute.md.j2` — Step 0 writes the PLAN with its
  required per-phase fields (AC-010), calls `frontmatter-upsert` and asserts presence
  afterwards (AC-002), and carries the loop-mode per-iter branch with its ADR-halt rule
  (AC-005). **(out):** `plan.md.j2` (still rendering), every other Python module.
- **Exit criterion:** `uv run pytest tests/unit tests/render -k "spec_need or plan_reader"`
  passes, including the Hypothesis property over arbitrary prior frontmatter states.
- **Risk:** medium — this is the phase that must not lose the deleted Step 1.5/1.7 semantics.
- **Rollback point:** n/a (first phase)

### Phase 2 — `spec-validator` and the round-count field  ·  **DONE**
- `depends_on`: []
- `parallel_group`: `templates-additive`
- `merge_hazards`: none (owns `spec.md.j2` + the agent assets)
- **Scope (in):** ADD the `spec-validator` agent pair (re-scoped body: ACs, circular oracles,
  implied-but-unlisted irreversible decisions, scope boundary); add the conditional dispatch,
  the single-pass rule and the ledger emit to `spec.md.j2` Step 4.6 (AC-007, AC-008); add
  `interview_rounds` to the SPEC frontmatter contract (AC-009); register both validators in
  `presets.py` and `synthesize.py`.
  **(out):** `execute.md.j2`, the enum, every deletion.
- **Amended 2026-09-20 mid-phase.** The first pass DELETED the `plan-validator` assets here.
  That breaks ADR-002's own rule — `plan.md.j2` still dispatches that agent until Phase 4, so
  the intermediate commit shipped a stage pointing at a subagent that does not exist. Both
  validators are therefore installed transitionally, which raises the Side inventory ceiling
  61 → 62 (`tests/unit/test_synthesize.py`, attributed in place). **Phase 4 owns the deletion
  and must lower that ceiling back to 61.**
- **Exit criterion:** `uv run pytest tests/unit -k "spec_validator or synthesize"` passes and
  `ls src/harness_maker/templates/agents/spec-validator*.j2` lists both files.
- **Risk:** medium
- **Rollback point:** n/a (independent of Phase 1)

### Phase 3 — Schema removal and the one-shot migration (atomic)  ·  **DONE**
- `depends_on`: [1, 2]
- `parallel_group`: `serial-schema`
- `merge_hazards`: `models.py` `AtomicStage` is read by `interview.py`, `autopilot_caps.py` and
  `step_sensitivity.py` — all four change in one commit or existing harnesses fail to load.
- **Scope (in):** `models.py`, `interview.py`, `step_sensitivity.py`, `autopilot_caps.py`.
  **(out):** `codex_ledger.py` (ADR-005), templates.
- **Exit criterion:** `uv run pytest tests/unit -k "atomic_stage or pipeline or answers_from"`
  passes, and a fixture harness.yaml carrying `plan` in `autonomy.pipeline` loads twice with
  exactly one advisory.
- **Risk:** high — this is IRR-002, the irreversible one.
- **Rollback point:** Phase 2

### Phase 4 — Delete the stage and announce it  ·  **DONE**
- `depends_on`: [3]
- `parallel_group`: `serial-removal`
- `merge_hazards`: render output feeds every golden in Phase 5.
- **Scope (in):** delete `stages/plan.md.j2` **and both `plan-validator` assets** (deferred
  here from Phase 2), lower `tests/unit/test_synthesize.py`'s Side ceiling 62 → 61, drop
  `commands/hm/plan.md` and the `plan-validator` entries from `synthesize.py`'s maps and
  `presets.py`; update `loop.md.j2` (stage-name list, `--per-iter-stages` example),
  `loop-p5-batch.md.j2`, both help templates, and the `/hm:plan` prose in `wrapup.md.j2`,
  `review.md.j2`, `verify.md.j2`, `stuck*.j2`, `trajectory-monitor.md`; add the BREAKING
  CHANGELOG entry (AC-001, AC-006).
  **(out):** `verify.md.j2`'s Check 6 *logic* (ADR-003) — prose references only.
- **Exit criterion:** `uv run pytest tests/render tests/structural -k "command_names or help"`
  passes and `grep -r "stages/plan.md.j2" src/` returns nothing.
- **Risk:** high — IRR-001.
- **Rollback point:** Phase 3

### Phase 5 — Test and golden migration  ·  **DONE**
- `depends_on`: [4]
- `parallel_group`: `serial-fixtures`
- `merge_hazards`: the three goldens are regenerated from Phase 4's render; regenerating before
  Phase 4 freezes the pre-deletion bytes.
- **Scope (in):** the 68 test files, and the three goldens — each re-captured **with an
  appended entry in `tests/structural/test_autopilot_gate_render.py`'s docstring naming the
  date, this task, and what moved and why**.
  **(out):** any production module.
- **Exit criterion:** the full suite is green: `uv run pytest` (background) plus
  `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src/`.
- **Risk:** medium — volume, not difficulty.
- **Rollback point:** Phase 4

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/spec_machine.py` — a concurrent session owns it and lands it to main; a
  collision costs this side.
- `src/harness_maker/io_utils.py` — same concurrent session.
- `src/harness_maker/world.py` — same concurrent session.
- `src/harness_maker/codex_ledger.py` — ADR-005: the `stage` Literal keeps `"plan"` so
  historical ledger rows stay parseable.
- Advisory: `verify.md.j2`'s Check 6 **logic** stays exactly as it is, including the absent-key
  `PASS (N-A)` path (ADR-003). Its prose references to the deleted stage may change.
- Advisory: a golden is re-captured **in the phase whose render moved it**, never later, and
  never without the docstring entry naming the task, the moved commands and the verification
  that nothing else moved. **Amended 2026-09-20 during Phase 1**: the original wording deferred
  all three goldens to Phase 5, which would have left the suite red across Phases 2-4 and
  destroyed the signal those phases depend on — and `test_autopilot_gate_render`'s own rule says
  a third-party task that legitimately moves bytes should re-capture and record, which is
  exactly this case. What stays forbidden is re-capturing a golden to make its OWN subject green.

## 🧪 Testing Strategy

- **Unit.** The migration's idempotence (Phase 3), the SPEC-need preserve-and-assert behaviour
  (Phase 1), the spec-validator's single-pass and approval-invariance (Phase 2).
- **Property (Hypothesis).** AC-001 over the render matrix, AC-002 over arbitrary prior
  frontmatter states, AC-004 over pipelines containing `plan` in any position, AC-007 over the
  verdict range.
- **Structural.** AC-003's discovered-reader traversal (Phase 0 pins it, Phase 5 re-runs it).
- **Integration.** `tests/integration/test_loop_parallel_session.py` and
  `test_stage_spans_e2e.py` exercise the loop path that loses its `plan` member.
- **Mutation.** Tier 1 → `hm spec_mutation gate --tier 1` over the four `paths_to_mutate`.
- **Manual.** None required; the three `tests/manual/` hits are probe documents, not gates.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A PLAN reader is missed and silently stops resolving | medium | high | ADR-001 — Phase 0 pins a *discovered* set before deletion; the three prior hand-lists in this repo were each wrong |
| Phase 3 lands without its migration and existing harnesses fail to load | low | high | `merge_hazards` forces the four modules into one commit; the exit criterion loads a legacy fixture twice |
| Phase 1 drops a semantic from the deleted Step 1.5/1.7 | medium | high | Phase 1's exit criterion is keyed on the SPEC-need and loop-mode tests, not on "execute renders" |
| A green suite hides a defect the repair itself introduced | high | medium | `fix-introduced-defect-passes-all-gates` is at count:13 — Phase D.5's newly-reachable-window question is answered in writing for every repair phase |
| Goldens re-captured to make red tests green | medium | medium | Contract Boundaries pins the order (Phase 5 only, after Phase 4) and requires the docstring entry |
| Concurrent session lands `spec_machine.py` under us | medium | medium | Contract Boundaries names the three files; `task-refresh` rebases before each phase that follows a drift warning |
| `/hm:execute`'s own preflight fails on re-entry from inside the worktree | observed | low | Filed for REVIEW — `task-preflight <slug> "$(pwd)"` assumes a base-repo cwd and tries to nest a worktree when called from `<WT>` |

## ✅ Success Criteria

- [ ] AC-001 — `/hm:plan` renders on no target in any arm
- [ ] AC-002 — execute writes the SPEC-need fields and preserves a pre-existing verdict
- [ ] AC-003 — every discovered PLAN reader resolves against an execute-written PLAN
- [ ] AC-004 — a legacy pipeline naming `plan` loads, migrates once, and says so once
- [ ] AC-005 — the per-iter PLAN keeps its frontmatter contract under a new producer
- [ ] AC-006 — the removal is announced and leaves no stub
- [ ] AC-007 — spec-validator is single-pass, conditional, and cannot move approval
- [ ] AC-008 — every spec-validator dispatch is recorded
- [ ] AC-009 — the merged interview records its round count on the SPEC
- [ ] AC-010 — the PLAN document keeps its required per-phase fields
- [ ] Full suite green; `ruff`, `ruff format --check`, `mypy --strict` clean
- [ ] Tier-1 mutation gate passes over the four `paths_to_mutate`

## 🔍 Plan Validation

**Not run.** `plan-validator` was not dispatched: this PLAN is agent-authored under the model
the SPEC introduces, in which the validator has moved to `/hm:spec` (ADR-004) and is not yet
built — Phase 2 builds it. `validator_outcome: NOT_RUN` records that honestly rather than
borrowing one of the four enum values, which would make an unvalidated PLAN indistinguishable
from a validated one.

**What stands in for it.** The SPEC passed `hm spec_machine check --all` at 89/100 with no weak
dimension and carries a DRI approval stamp (`state: approved`, `land: ok`); its 10 ACs are the
acceptance this PLAN's phases are keyed to. The risk register above is the critique this PLAN
received in place of a validator pass, and it is the weakest part of this document — a reader
should treat it as such.
