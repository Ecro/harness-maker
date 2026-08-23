---
type: plan
task_slug: a5-duplicate-coverage-block
status: complete
created: 2026-08-23
tags: [harness-maker, plan, prompt-templates, execute-stage, test-reviewer, gating]
spec: "[[SPEC-a5-duplicate-coverage-block]]"
research_doc: "[[RESEARCH-a5-duplicate-coverage-block]]"
interview_rounds: 4
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Narrow Phase A.5's duplicate trigger to observable level across four sites, guarded by a parity test"
spec_need_verdict: add
spec_need_target: a5-duplicate-coverage-block
---

# PLAN — Phase A.5 duplicate-coverage trigger

## 🎯 Executive Summary

**What:** Restate the Phase A.5 duplicate-coverage trigger as duplication of the same
*observable* rather than a count of tests sharing a scenario ID, at all four sites that express
it, and pin the four-site agreement with a structural test.

**Why:** `test-reviewer_body.md.j2:21` requires *at least one* dedicated test per scenario while
its own Hard Rule at `:105` blocks when a scenario is *covered twice*. Those cannot both hold.
The reconciling qualifier already exists at `execute.md.j2:222` ("for the same observable") but
lives in the stage template, which the reviewer agent never reads. Observed live on
`~/strange_chess` at `harness_maker_version: 0.54.0`: five tests asserting five different
observables blocked `/hm:execute` for two rounds before escalating.

**Key decisions:** ADR-001 (narrow the trigger, keep the gate) · ADR-002 (reject the round-1
plan-routing exit) · ADR-003 (hardcoded four-site parity oracle) · ADR-004 (reuse the existing
qualifier phrase verbatim).

**Estimated impact:** 2 template files (prose only), 1 new test file, 1 snapshot/baseline
reconciliation pass. No Python production code, no schema change.

## 📚 Prior Work

- `RESEARCH-a5-duplicate-coverage-block` — locator table establishing the contradiction, and the
  finding that this class is invisible to single-file render-grep because every file reads as
  correct in isolation.
- `[wiki:architecture] multi-lens-phase-a5-gate` — the gate's merge algebra and three repair
  arms, which this change leaves untouched.
- Commit `e446c8db` — originates the routing rule being narrowed. Its rationale records that the
  rule replaced a `suggestions` field the schema did not define, which is why Approach C
  (demoting the finding to advisory) is rejected rather than merely unchosen.
- CLAUDE.md §"렌더 컨텍스트 플래그는 출력 경로에서 파생시킬 것" — the precedent that a defect
  living in the seam between two correct-looking files needs a structural gate, not a grep.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Scope | Scope boundaries | How far to take the fix? | A alone / A+B exit / A+B+upstream gate | **A alone** | User challenged the recommended A+B with "too frequent an exit?". On re-examination A removes the FAIL that B's exit was meant to escape, and also makes the previously-illegal *retarget or delete* repair arm executable for every remaining FAIL. Recommendation revised before the next question. | ADR-001, ADR-002 |
| 2 | Contract shape | Contract shape | Keep rubric §1's "at least one"? | at least one / exactly one | **at least one** | Retaining it is what makes the archer case pass; the contradiction is resolved on the Hard Rule side. | ADR-001 |
| 3 | Testing depth | Testing depth | What is the oracle? | parity structural test / rubric judgment / fixture integration / render grep | **parity structural test** (+ rubric judgment retained as AC-004) | RESEARCH established render-grep cannot see this class. | ADR-003 |
| 4 | Site identification | Testing depth | How does the parity test find the sites? | hardcoded 4-tuple / pattern discovery / more questions first | **hardcoded 4-tuple** | Pattern discovery is circular with the defect (the wording differs per site) and would false-fail on unrelated `duplicate` vocabulary such as `code-verifier`'s ledger enum. | ADR-003 |
| 5 | ADR-001 repair-arm claim | Risk tolerance | plan-validator refuted "narrowing makes retarget-or-delete legal everywhere". Fix by adding the evidence contract, or lower the claim? | add evidence contract / lower claim + reopen ADR-002 / both | **lower the claim + reopen ADR-002** | The evidence-contract fix would unfreeze the reviewer output contract that Contract Boundaries pins. Residual accepted and assigned to a follow-up task rather than absorbed here. | ADR-001, ADR-002 |
| 6 | Oracle subject | Testing depth | Assert over `.j2` source or rendered output? | rendered output / keep source | **rendered output** | The `is_codex` precedent: templates read as correct, render-grep passed, and the context was wrong. A source-only oracle is blind to it. | ADR-005 |

Questions 1–3 ran under `/hm:spec`; question 4 under `/hm:plan` Step 3.0 (Case A applied — the
SPEC reached `status: approved` with no open questions, so the deep interview was skipped);
questions 5–6 were opened by `plan-validator`'s MAJOR_REVISION and answered before the PLAN was
finalized.

## 📐 Architecture Decision Records

### ADR-001: Narrow the A.5 duplication trigger to observable level; keep the gate
**Status:** Accepted (2026-08-23, via /hm:plan interview)
**Context:** `test-reviewer_body.md.j2` requires at least one dedicated test per scenario (§1)
and simultaneously blocks when a scenario is covered twice (Hard Rule). The qualifier that
reconciles them — duplication is per *observable* — exists only in `execute.md.j2:222`, which the
reviewer agent does not read.
**Decision:** Restate the Hard Rule and the three mirroring sites in `execute.md.j2` so the
trigger is duplication of the same observable. Rubric §1 keeps "at least one".
**Consequences:**
- ✅ N tests under one scenario ID, each asserting a different observable, pass — the archer case.
- ⚠️ "Same observable" is an LLM judgment call, so the gate is less deterministic than a count.
  Accepted: the count was deterministic and wrong.
- ⚠️ **The third repair arm is NOT made executable by this change.** An earlier draft claimed it
  was; that claim is withdrawn. `per_scenario[].reason` is capped at ≤80 chars
  (`test-reviewer_body.md.j2:69`) and the arm says "when `reason` does not disambiguate, treat
  every listed test as in scope" (`execute.md.j2:324-326`). After narrowing, N-tests-N-observables
  becomes the *normal* shape, so a FAIL naming two colliding observables among five tests can
  still send all five to *retarget or delete*. This residual is accepted, not solved — see the
  risk register and ADR-002.
**Rejected alternatives:**
- Tighten §1 to "exactly one dedicated test" — Rejected because it makes splitting the SPEC the
  only legal repair for a test-quality gate, pushing SPEC edits into `/hm:execute`, which has no
  authority to make them.
- Approach C, demote duplicate coverage to advisory — Rejected because `e446c8db` added this
  routing rule specifically to close a silent-drop hole (a reviewer that found a defect emitted
  nothing and returned PASS). There is no advisory carrier in the schema to demote into.
**Source:** Interview #1, #2

### ADR-002: No round-1 plan-routing exit; the repair-arm residual is accepted, not routed
**Status:** Accepted (2026-08-23, via /hm:plan interview; **re-derived** after plan-validator
refuted the premise of the first draft)
**Context:** RESEARCH recommended pairing ADR-001 with an exit routing the "scenario ID is too
coarse" case to `stuck`/Path B at round 1. The first draft rejected it on the ground that
ADR-001 made *retarget or delete* legal everywhere. `plan-validator` refuted that ground, so the
decision is re-derived here rather than inherited.
**Decision:** Still no exit — but for a different reason, and the residual it leaves is named.
**Reasoning on the sound premise:** the exit was designed for coarse scenario IDs, and after
ADR-001 that case is no longer a FAIL at all, so the exit has no trigger left to fire on. The
residual the validator found is a *different* defect — an under-specified `reason` field letting
a genuine same-observable FAIL scope every listed test — and a plan-routing exit does not address
it: the correct repair there is still local to Phase A, not a SPEC edit.
**Consequences:**
- ✅ No escape hatch for `/hm:execute` to reclassify genuine duplication as a PLAN problem.
- ✅ Change surface stays at prose in two files.
- ⚠️ A SPEC with one ID covering five observables is never flagged anywhere. Accepted: SPEC
  hygiene, no downstream cost.
- ⚠️ **Accepted risk:** the evidence-contract gap above ships unfixed. A same-observable FAIL can
  cost valid coverage. Recorded in the risk register; a follow-up task owns it.
**Rejected alternatives:**
- Add the exit — Rejected: no trigger survives ADR-001, and it is orthogonal to the residual.
- Extend Phase 1 to fix the evidence contract (require `reason` to name the duplicated observable
  and the offending test functions, widening the ≤80-char cap) — **Rejected for this task** on the
  user's scope call, not on merit. It would unfreeze the reviewer output contract, which
  Contract Boundaries pins. It is the correct next task.
- Add an upstream "one scenario, one observable" check — Rejected: makes every existing SPEC a
  latent violator for a defect class with no downstream cost.
**Source:** Interview #1, #5

### ADR-003: Four-site parity, asserted from a hardcoded tuple
**Status:** Accepted (2026-08-23, via /hm:plan interview)
**Context:** The defect lives in the seam between two files that each read as correct alone, so a
single-file grep cannot detect it. The test must assert *agreement across sites*.
**Decision:** `tests/structural/test_duplicate_trigger_observable_parity.py` holds an explicit
tuple of the four (file, anchor) pairs and asserts each carries the qualifier, that none states
the trigger in scenario-ID-cardinality terms, and that the site count is exactly four.
**Consequences:**
- ✅ Same shape as `tests/structural/test_gate_base_root_parity.py`, an established precedent.
- ✅ Known-site parity is pinned: any one of the four sites losing the qualifier fails the test.
- ⚠️ **Drift protection is known-site only.** A tuple literal's length is a constant, so
  `len(SITES) == 4` cannot detect a *fifth* site added later — an earlier draft claimed it could;
  that claim is withdrawn. Partial compensation: the test also asserts the total occurrence count
  of the fixed literal across the two files, which does move when a new site appears in them.
- ⚠️ The tuple must be updated by hand when a site legitimately moves.

**Counting arithmetic, stated once so the test author does not guess:** there are **four edited
trigger sites** (1 in the reviewer body + 3 in `execute.md.j2`) and **five phrase occurrences**
in total after the change, because `execute.md.j2:222` already carried the phrase. Assertions are
phrased in those exact terms.
**Rejected alternatives:**
- Pattern discovery over every sentence containing `duplicate` — Rejected on two grounds: it is
  circular with the defect (the wording differs per site, which is what is being fixed), and it
  false-fails on unrelated vocabulary, notably `code-verifier_body.md.j2`'s
  `accepted/rejected/duplicate/unresolved` ledger enum.
**Source:** Interview #4

### ADR-004: The qualifier phrase is reused verbatim from `execute.md.j2:222`
**Status:** Accepted (2026-08-23, via /hm:plan interview)
**Context:** AC-001's oracle is `golden`, and its independence argument is that the expected
value comes from a site the change does not touch.
**Decision:** Use the existing phrase "for the same observable" (from `execute.md.j2:222`, the
Phase A authoring rule) as the qualifier at all four edited sites. Do not coin new wording.
**Placement is part of this decision, not left to the implementer.** Sites 1 and 3 are *compound*
clauses — "a scenario covered twice, **or** covered by a test aimed at a different scenario" —
carrying two unrelated defects. Split them into two predicates and attach the qualifier to the
**duplication arm only**. Scenario-ID mismatch is banned-pattern category 5
(`test-reviewer_body.md.j2:34`) and is a defect regardless of observable; a trailing qualifier
scoping the whole disjunction would licence mislabelled tests, a coverage regression introduced
by a task whose goal is to stop over-blocking.
**Consequences:**
- ✅ AC-001's golden stays independent — the expected string predates the change and was written
  for a different purpose.
- ✅ One phrase across five sites, so the parity assertion is a literal string comparison.
- ✅ The ID-mismatch arm is pinned *unqualified*, so the loose placement cannot pass the test.
- ⚠️ If the phrase is ever reworded at `:222`, the parity test fails and forces a deliberate
  co-update rather than silent drift. That is the intended behaviour.
**Rejected alternatives:**
- Coin a clearer phrase for the reviewer clause — Rejected because a phrase invented for the file
  under test makes the golden self-referential, which is the circular oracle the SPEC stage
  rejects by policy.
**Source:** Interview #3, ADR-003

### ADR-005: The mechanical ACs assert over rendered output, not template source
**Status:** Accepted (2026-08-23, via /hm:plan interview #5)
**Context:** The first draft's AC-001/AC-002/AC-003 predicates read the `.j2` sources. But the
SPEC frames the bug as what the *reviewer agent* carries, and CLAUDE.md records a shipped instance
(`is_codex`) where every template read as correct, every render-grep passed, and the render
**context** was wrong — so the output diverged from the source and no source-level test could see
it.
**Decision:** The parity test renders and asserts over the rendered bodies for all targets,
parametrized across the Claude and Codex arms, using the `_render_root()` pattern already in
`tests/structural/test_multi_lens_a5.py`. The four-site tuple stays the anchor set (ADR-003).
**Consequences:**
- ✅ A render branch (`is_codex`, `tdd_active`) that ships the coarse trigger to one arm is caught.
- ✅ Reuses an existing render harness — no new machinery.
- ⚠️ Slower than a file read, and a render failure now also fails this test. Accepted: the render
  harness is already exercised by its neighbours in the same directory.
**Rejected alternatives:**
- Keep asserting on `.j2` source — Rejected: structurally blind to the one failure class this
  repo has already shipped once.
**Source:** Interview #5, plan-validator critique 5

## 🏗️ Technical Design

**Current state.** Four sites express the A.5 duplication trigger, none carrying the observable
qualifier:

| # | File | Anchor |
|---|---|---|
| 1 | `src/harness_maker/templates/agents/test-reviewer_body.md.j2` | Hard Rule: "a scenario covered twice, or covered by a test aimed at a different scenario" |
| 2 | `src/harness_maker/templates/stages/execute.md.j2` | coverage-lens table row: "no missing scenario, no duplicate" |
| 3 | `src/harness_maker/templates/stages/execute.md.j2` | `<brief>` routing sentence: "a scenario covered twice, or covered by a test aimed at another scenario" |
| 4 | `src/harness_maker/templates/stages/execute.md.j2` | dispatch string: "with no missing scenario and no duplicate" |

A fifth, unedited site — `execute.md.j2:222` — already carries the phrase and is the qualifier's
provenance (ADR-004).

**Affected components.** Two Jinja templates; one new structural test; the snapshot fixtures
under `tests/snapshot/*.expected.yaml`; possibly `tests/structural/surface_baseline.json` and
`instruction_baseline.json`.

**Dependencies.** None added.

**Design decisions.** All four ADRs above. No new module, no schema change, no Python production
code — the change is prompt wording plus its guard.

**Data flow.** Unchanged: `/hm:execute` Phase A.5 dispatches one `test-reviewer` call carrying
three lens questions; the merge algebra recomputes `overall_assessment` from the merged carriers.
Only the predicate a reviewer applies when deciding `per_scenario[].quality` changes.

**API changes.** None. The reviewer's JSON output schema is untouched.

## 📝 Implementation Plan

### Phase 1 — Narrow the trigger at all four sites, guarded by the parity test
- `depends_on`: `[]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `src/harness_maker/templates/stages/execute.md.j2` is edited at three separate
  anchors in one file — all three must land together or the parity test fails on a partial edit.
  This is the intended failure mode, not a hazard to route around.
- **Scope (in):** `src/harness_maker/templates/agents/test-reviewer_body.md.j2`,
  `src/harness_maker/templates/stages/execute.md.j2`,
  `tests/structural/test_duplicate_trigger_observable_parity.py` (new).
- **Compound-clause split (ADR-004):** at sites 1 and 3 the single sentence becomes two
  predicates — a duplication arm carrying "for the same observable", and an ID-mismatch arm
  carrying no qualifier. Both arms are pinned independently by the parity test.
- **Scope (out):** every other template, all Python modules, the reviewer JSON schema,
  `code-verifier_body.md.j2`.
- **Exit criterion:** `uv run pytest tests/structural/test_duplicate_trigger_observable_parity.py -q`
  passes. The test asserts, over **rendered** bodies for every target (ADR-005): each of the four
  anchor sites carries the qualifier on its duplication arm; the ID-mismatch arm at sites 1 and 3
  carries none; no scenario-ID-cardinality phrasing survives; and the total occurrence count of
  the literal "for the same observable" is **five** (1 reviewer + 4 execute, the fourth being the
  pre-existing `:222`).
- **Risk:** low
- **Rollback point:** the task branch tip before Phase 1 (`hm/a5-duplicate-coverage-block` at
  `task-create` base).

**Status: BLOCKED at Phase A.5 (2026-08-23).** Phase C was never entered — no template edit
exists on disk. Both failing rounds were about the *oracle*, not the fix.

- **Round 1 FAIL** — 1 blocking issue (category 6): the qualifier at the `<brief>` routing sentence
  was inferred from the aggregate `body.count(QUALIFIER) == 4`, so padding it into another line
  satisfies the sum while the brief stays coarse. Repaired: two `in` checks upgraded to
  `count(...) == 1`, a third locus assertion added for the brief, and a
  `_DUPLICATION_MARKER = "two tests covering one scenario"` constant introduced to locate the
  duplication arm without circling back to the qualifier under test.
- **Round 2 FAIL** — 2 blocking issues (category 6, both on that constant): the literal appears
  nowhere in the SPEC or PLAN, so a correct Phase C implementation phrasing the arm differently
  goes RED. The repair traded a false-GREEN for a false-RED at the same two assertions. Folded
  into AC-002's FAIL: `_EXPECTED_REVIEWER_OCCURRENCES = 1` is defined and documented but
  referenced by no assertion, so only 4 of AC-002's required 5 occurrences are pinned.
- **Binding constraint (`stuck`)**: ADR-004 locks the qualifier and its placement but locks no text
  by which the duplication *arm* can be identified, and its own Rejected Alternatives bar the
  executor from coining one. `_MISMATCH_MARKER` is legal only because it quotes ADR-004's prose;
  the duplication arm has no equivalent sentence in the plan record. That asymmetry — not wording
  taste — is what makes one constant legal and the other a trap.
- **`stuck` recommendation: Path C** — elimination-based arm derivation plus a separator-agnostic
  splitter, all expected literals predating the change; Path A is the same minus the separator fix;
  Path B promotes the locator to an ADR-006 but reverses ADR-004's rejected alternative. Under
  every path the missing `reviewer_body.count(QUALIFIER) == 1` assertion is mandatory.
- **Not acted on.** `stuck` is advisory; the unblock path is the user's call.
- `[boundaries] comparison not performed — blocked exit`

**Second blocked exit — budget 2 exhausted (2026-08-23).** Path C (approved by the user after the
first escalation) was applied in full and the phase blocked again.

- **Budget 2, round 1 FAIL** — 2 blocking issues, both verified by grep before repairing.
  (a) `_MISMATCH_MARKER = "regardless of observable"` is the same invented-literal defect one arm
  over: ADR-004's rationale is not prescribed rendered content, and SPEC AC-001's Then clause
  prescribes no wording for that arm. (b) `_brief_paragraph()`'s `scenarios_missing` anchor is not
  unique — it also occurs at `execute.md.j2:312` (merge-rules table) and 319/324/331/337 (the
  Resolution paragraph), and that paragraph carries its own unedited "test aimed at another
  scenario" at :321, a **fifth site the four-site table never schedules for editing**. The oracle
  was unsatisfiable by the scope-compliant fix. Repaired: constant deleted; `_brief_block` bounded
  structurally from the brief's opening line to the first dispatch match.
- **Budget 2, round 2 FAIL** — 3 blocking issues, one root cause, category tautology: `_arms()`
  splits on bare `.`, so the exact wrong implementation ADR-004 names as rejected passes vacuously
  whenever an incidental period (an `i.e.` aside, an abbreviation) lands between the locator and
  the qualifier — each half then satisfies one assertion. Reproduced before escalating.

**Root cause (`stuck`, second escalation):** *"AC-002's arm-separation half asks a mechanical
oracle to decide a prepositional-attachment question over prose whose syntactic shape nothing
prescribes."* ADR-004 locks the qualifier's placement **semantically** but locks no separator, arm
order or clause shape, so the author has only two moves and both are defective — infer a boundary
from generic punctuation (under-determined: rounds 1 and 4) or invent a boundary/marker
(circular oracle, false-RED: rounds 2 and 3). **Every round kept the splitter and moved along the
loose↔tight axis. That axis has no fixed point under the current constraint set.** `stuck` also
refuted round 4's own recommended fix: a coarse `;`-only split false-REDs the scope-compliant
single-clause phrasing `"a scenario covered twice for the same observable, or covered by a test
aimed at a different scenario"`.

**`stuck` recommendation: Path A** — delete `_arms()` and `_assert_arms_separate()` outright and
assert **window exclusion** instead of clause membership: the qualifier must not occur between
`_MISMATCH_LOCATOR` and the next `per_scenario` after it. Both anchors predate the change; nothing
is tokenized, so punctuation is irrelevant. Named residual: a qualifier trailing *after* the
`per_scenario` mention escapes the window — narrower than every hole shipped so far, and to be
written into the docstring rather than claimed away. Path B (ADR-006 prescribes a `;` separator,
plan round, no residual) and Path C (demote arm separation to AC-004's rubric, SPEC amendment,
weakens ADR-004's stated consequence) are the alternatives.

- **Not acted on.** `stuck` is advisory; the unblock path is the user's call.
- `[boundaries] comparison not performed — blocked exit`

**Phase 1 GREEN (2026-08-23), third A.5 budget, round 2 PASS.** Six rounds across three budgets;
the two blocked exits and their four defects are recorded above. Final oracle shape: window
exclusion, no clause tokenizing, every expected literal pre-existing in the templates it reads.
`uv run pytest tests/structural/test_duplicate_trigger_observable_parity.py -q` → 13 passed.
Source counts: reviewer body 1, execute body 4.

**Phase D.5 — newly-reachable window (this phase repairs a defect, so it applies).**

1. **What input window does the repair newly make reachable?** Phase A.5 verdicts on a SPEC
   scenario covered by **N > 1 tests**. Before the change every such scenario reached
   `per_scenario[].quality = FAIL` regardless of what the tests asserted; the reviewer never had
   to evaluate whether the observables differed, so that judgment was unreachable. After the
   change the reviewer must decide *same observable or not* for every N > 1 scenario — a decision
   that did not exist on this path before. The window also includes the **N = 1** boundary
   (trivially clean, never reached the trigger either way) and, at the other edge, a scenario
   whose N tests genuinely duplicate one observable — which must still FAIL, now with the
   duplicated observable and the offending tests named.
2. **Which test enters that window, and is it in this same commit?** No test enters the *runtime*
   window, and that is a property of the subject, not an omission: the changed artifact is a
   prompt, so the decision is made by an LLM reviewer at `/hm:execute` time and has no in-process
   call site to exercise. What is in this commit is the *instruction* half —
   `tests/structural/test_duplicate_trigger_observable_parity.py::test_ac_001_reviewer_hard_rule_is_observable_qualified`
   and the three `test_ac_002_*` cases pin, over rendered bodies for every target, that the
   N-tests-N-observables case is stated as PASS and that the qualifier does not scope the
   scenario-ID-mismatch predicate. The behavioural half is AC-004's `judgment-reviewer` verdict in
   Phase 3.
3. **Named gap, not silence.** No fixture exercises a live `test-reviewer` against a
   one-scenario-many-observables input; that was rejected in the SPEC interview as
   non-deterministic and expensive, and re-raised by codex as `f00fdde0` during plan validation.
   The residual is therefore: *the rendered instruction is pinned; the reviewer's obedience to it
   is not.* AC-004 covers the reviewer body only — the `<brief>` copy at `execute.md.j2` has no
   behavioural check at all.
4. **Absent-case.** The feature activates on a field that is always present (`per_scenario[]` is
   emitted for every scenario), so there is no optional-field absent case. The nearest analogue is
   a scenario with **zero** tests, which routes to `scenarios_missing[]` and is untouched by this
   change — confirmed: no edit in this phase went near that arm.

### Phase 2 — Re-render and reconcile snapshots and baselines
- `depends_on`: `[1]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `tests/snapshot/*.expected.yaml`, `tests/structural/surface_baseline.json`,
  `tests/structural/instruction_baseline.json` — all regenerated artifacts; a concurrent phase
  touching any template would produce an unattributable delta.
- **Scope (in):** regenerated snapshot fixtures; the two baseline JSONs **only if** the ratchet
  trips; `work-docs/BASELINE-DELTA-a5-duplicate-coverage-block.md` if a re-baseline is needed.
- **Scope (out):** any hand edit to a `.expected.yaml` (regeneration only).
- **Exit criterion:** the **full** suite `uv run pytest -q` passes (≈6 min — run it in the
  background, per project policy) with no hand-edited fixture, and any baseline movement is
  attributed in a BASELINE-DELTA note. The subset `tests/snapshot tests/structural` is NOT
  sufficient: `tests/unit/test_render_dispatch_macro.py` and `tests/unit/test_agent_body_partials.py`
  render these same templates. (`test_render_dispatch_macro.py:237`'s frozen A.5 literal is a
  *pre-migration* string inside the `_COLLAPSED_MULTILINE` exemption set, so it is not a known
  break — the wider run is insurance, not a repair.)
- **Status: DONE.** Snapshots regenerated in the worktree (8 files, 24 lines, all `body_sha256`
  for the two edited templates' consumers — no unrelated churn). Full suite `uv run pytest -q`
  green, `rc=0` read from the output file rather than the background notification, which reported
  exit 0 on the failing run. Nine failures were reconciled first — **seven of them caused by the
  `antigravity` config removal, not by this SPEC**: `instruction_preservation` x4 (allowlisted
  under `config-second-opinion-antigravity-off`, and a stale premise in the neighbouring
  comprehension note corrected), `roundtrip_budget` x2 + `surface_baseline` (health 7 -> 6, one
  fewer per-model smoke call; re-baselined and attributed in
  `work-docs/BASELINE-DELTA-a5-duplicate-coverage-block.md`). The two caused by this SPEC:
  the frozen `test-reviewer` sha256 (re-pinned with rationale) and
  `test_new_gates_file_a_mutation_receipt` (two receipts recorded after actually deleting
  `execute.md.j2:275` and `test-reviewer_body.md.j2:21` and observing the gate go red).
- **Risk:** low
- **Rollback point:** Phase 1 exit.
- **Note:** run `tests/snapshot/regenerate.py` **inside the task worktree** — it is pinned to be
  worktree-invariant, and running it from base regenerates templates this task did not change.

### Phase 3 — Record the AC-004 judgment verdict
- `depends_on`: `[2]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `specs/SPEC-a5-duplicate-coverage-block.machine.yaml` — the same file Phase 3
  writes is read by the wrapup `find-unjudged` gate.
- **Judgment subject (corrected):** `src/harness_maker/templates/agents/test-reviewer_body.md.j2`.
  The first draft named `.claude/agents/test-reviewer.md`, **which does not exist** — harness-maker
  does not render its own reviewer agents to disk (no `.claude/agents/` directory in this repo), so
  `judgment_subject_hash` could never have been re-derived and the staleness trigger would have
  been dead on arrival. The reviewer dispatch judges the body rendered from this template; the
  hash pins the template, which is the artifact whose edit must invalidate the verdict.
- **Scope (in):** `specs/SPEC-a5-duplicate-coverage-block.machine.yaml` fields
  `judgment_verdict`, `judged_at`, `judgment_evidence`, `judgment_subject_hash`,
  `judgment_subject_paths` on AC-004.
- **Scope (out):** every other AC; the SPEC prose.
- **Exit criterion:** `uv run hm spec_machine check --all --yaml specs/SPEC-a5-duplicate-coverage-block.machine.yaml --md specs/SPEC-a5-duplicate-coverage-block.md --dev-mode spec-driven`
  exits 0, and AC-004 carries a non-null `judgment_verdict` with a `judgment_subject_hash`
  matching the current `src/harness_maker/templates/agents/test-reviewer_body.md.j2`.
- **Status: DONE.** `judgment-reviewer` returned `pass` on all 6 `agent_prompt` criteria.
  **Re-judged in review round 2** after the must-PASS fix changed the subject, which made the
  first verdict's hash stale — that is what the hash exists to detect, so the verdict was cleared
  and re-taken rather than carried. Recorded in the machine SPEC with `judgment_subject_hash:
  a0545d1fda948e79da852cdb66e7ccc86efd275165f2266e2b2fdda9a4ceca09` over
  `src/harness_maker/templates/agents/test-reviewer_body.md.j2` — the corrected subject.
  Key finding: narrowing opens no loophole for banned pattern 5, because the mismatch predicate
  is stated as holding "regardless of observable".
- **Risk:** low
- **Rollback point:** Phase 2 exit.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/templates/agents/code-verifier_body.md.j2` — its
  `accepted`/`rejected`/`duplicate`/`unresolved` ledger vocabulary is a different sense of
  "duplicate" and must not be swept into this change.
- `src/harness_maker/templates/schemas/second-opinion-ledger.schema.json` — unrelated `duplicate`
  enum member.
- Advisory: the `test-reviewer` JSON output schema — the field names `per_scenario`,
  `blocking_issues`, `scenarios_missing`, `passing_tests` and their semantics — must not change;
  `execute.md.j2`'s merge algebra keys on those exact names.
- Advisory: the A.5 round budget (2 rounds), the merge algebra, and the three repair arms stay
  exactly as written. This task changes only the predicate a reviewer applies. This freeze is
  what forces ADR-002's accepted residual — a follow-up task must lift it deliberately, not this
  one incidentally.
- Advisory: rubric §1's "at least one dedicated test function" is load-bearing for AC-003 and
  must survive verbatim.

## 🧪 Testing Strategy

- **Unit / structural:** `tests/structural/test_duplicate_trigger_observable_parity.py` — three
  tests, one per mechanical AC (AC-001, AC-002, AC-003). Authored RED in `/hm:execute` Phase A.
- **Regression:** `tests/snapshot` + `tests/structural` full run in Phase 2.
- **Manual / judgment:** AC-004 — render the reviewer body and dispatch `judgment-reviewer`
  against it with `rubric_id: agent_prompt`, recording the per-criterion verdict in the machine
  SPEC and hashing `src/harness_maker/templates/agents/test-reviewer_body.md.j2` as the subject.
- **Not run:** no integration test against a live `test-reviewer` dispatch. Rejected in the SPEC
  interview as non-deterministic and expensive; the parity test plus the rubric judgment cover
  the mechanical and semantic halves respectively.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Reviewers read "same observable" more loosely than intended and stop catching real duplication | medium | medium | AC-004's rubric judgment reads the clause as shipped; the `blocking_issues` route for tautologies/magic-values is untouched and still catches the tests that would pass a wrong implementation |
| The parity tuple goes stale when a site legitimately moves | medium | low | The explicit count assertion fails loudly rather than silently narrowing coverage (ADR-003) |
| Surface/instruction ratchet trips and is re-baselined without attribution | medium | medium | Phase 2 requires a BASELINE-DELTA note for any baseline movement — the `e446c8db` precedent, where the aggregate was raised without recording the implementation |
| Snapshot regeneration run from base instead of the worktree regenerates unrelated templates | low | medium | Phase 2 note pins the worktree; the regenerator is worktree-invariant by design |
| A consuming project keeps the old behaviour until it re-renders | high | low | Expected and accepted — this is how every template change propagates; no migration is written |
| **A same-observable FAIL scopes every test in `covered_by` and valid coverage is deleted** | medium | **high** | **Unmitigated in this task (ADR-002 accepted residual).** `reason` is ≤80 chars and the arm treats an ambiguous reason as blanket scope. Owner: a follow-up task that widens the reason contract to name the duplicated observable and the offending test functions. Surfaced here so it is a decision, not a discovery |
| A fifth trigger site is added later and the parity tuple never sees it | low | medium | Partially covered: the occurrence-count assertion (five) moves when a new site appears in either file. A site added to a *third* file is still invisible — stated in ADR-003 rather than claimed away |
| The qualifier is attached to the whole compound clause and licenses scenario-ID mismatch | medium | high | ADR-004 fixes the placement, and the parity test pins the ID-mismatch arm as *unqualified* — the loose placement fails |

## ✅ Success Criteria

- [x] AC-001 — the reviewer Hard Rule carries the observable qualifier and no scenario-ID-count
      clause remains in that file.
- [x] AC-002 — all four sites carry the qualifier on their duplication arm, the ID-mismatch arm at
      sites 1 and 3 carries none, and the literal occurs five times in total. Asserted over
      **rendered** bodies for every target (ADR-005).
- [x] AC-003 — rubric §1 still says "at least one dedicated test function".
- [x] AC-004 — `judgment-reviewer` reports no contradiction between §1 and the Hard Rule; the
      verdict and a `judgment_subject_hash` of
      `src/harness_maker/templates/agents/test-reviewer_body.md.j2` are recorded in the machine SPEC.
- [x] The full `uv run pytest -q` suite passes.
- [x] Any baseline movement is attributed in a BASELINE-DELTA note.

## 🔍 Plan Validation

**Outcome: `MAJOR_REVISION_RESOLVED`** — one validator pass, 2 critical + 3 warning + 2
suggestion. Every critique was resolved in this document before it was finalized. **No second
validator pass was run**, per the project's standing single-pass policy; the resolutions below are
therefore unreviewed by the validator and are recorded so a later reader can check them.

| # | Severity | Critique | Resolution |
|---|---|---|---|
| 1 | critical | AC-004's judgment subject `.claude/agents/test-reviewer.md` does not exist — no `.claude/agents/` directory in this repo, so `judgment_subject_hash` could never be re-derived and the staleness trigger was dead on arrival | Subject changed to `src/harness_maker/templates/agents/test-reviewer_body.md.j2` in Phase 3, the Testing Strategy, and the machine SPEC's `judgment_subject_paths` |
| 2 | critical | ADR-001's claim that narrowing makes *retarget or delete* legal for every remaining FAIL is false while `reason` is ≤80 chars and the arm treats an ambiguous reason as blanket scope — ADR-002's rejection of Approach B rested on the same premise | Claim withdrawn (ADR-001 consequences); ADR-002 re-derived on a sound premise; the residual is named as an accepted, unmitigated risk with a follow-up owner (Interview #5) |
| 3 | warning | ADR-003 claims a hardcoded tuple detects a fifth site; `len(SITES) == 4` is a constant | Claim narrowed to known-site parity; an occurrence-count assertion (five) added as partial compensation; the uncovered case stated rather than claimed away |
| 4 | warning | Sites 1 and 3 are compound clauses carrying two defects; ADR-004 fixes the phrase but not its placement, and both ACs pass either way — a trailing qualifier would licence scenario-ID mismatch (banned pattern 5) | ADR-004 now specifies the split and the duplication-arm-only attachment; the parity test pins the ID-mismatch arm as *unqualified* |
| 5 | warning | The oracle reads `.j2` source, but the defect is defined by what the rendered agent carries — the `is_codex` class | ADR-005 added: assert over rendered bodies for all targets via the `_render_root()` pattern; SPEC AC-001/AC-002 amended (Interview #6) |
| 6 | suggestion | The counting contract is stated three ways (four sites / five occurrences / grep 1 and 4) | Arithmetic stated once in ADR-003 and the assertions phrased in those terms |
| 7 | suggestion | Phase 2's exit runs a subset of the suite | Widened to the full `uv run pytest -q` |

**Cross-model second opinion.** `codex` — `invoked`, 7 findings. `antigravity` — **`skipped`**
(`exit 1; CLI said <<<<empty>>>>`); that model cast no vote and this PLAN is Claude+codex only.

Validator dispositions on the codex findings: 6 `accepted`, 1 `rejected`. The rejected one
(`e13a5e04`, "editing the dispatch string breaks `test_render_dispatch_macro.py:237` and
`claude_arm_baseline.json`") had been reported to the user as confirmed by the main loop; that was
wrong. The literals are present but are *pre-migration* per-lens strings sitting inside the
`_COLLAPSED_MULTILINE` exemption set, which the baseline gate accepts unconditionally
(`test_render_dispatch_macro.py:226-238, 290-314`). Editing site 4 cannot break them. The generic
concern behind the finding — Phase 2 asserting less than a green suite — survived as critique 7.
