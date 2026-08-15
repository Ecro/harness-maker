---
type: spec
task_slug: ai-review-exit-criteria
status: approved
created: 2026-08-14
tier: 2
tags: [harness-maker, spec, jinja2, review-stage, exit-criteria, lens-coverage]
test_framework: pytest
research_doc: "[[RESEARCH-ai-review-exit-criteria]]"
summary: "Systematically cover a declared failure space, on a frozen artifact, before exit."
---

# SPEC — declared failure space, covered on a frozen artifact

> **This document is the single source of the contract.** `PLAN-ai-review-exit-criteria.md`
> holds rationale, ADRs and phasing, and **references** the rules here by AC number; it does
> not restate them. That split is deliberate: across two adversarial validation rounds,
> 8 of 13 and then 8 of 13 findings were the two documents stating the same rule differently,
> because every repair had to be propagated by hand and no gate compared them. Any normative
> statement belongs here and nowhere else.

## 🎯 Intent

> The goal of AI review is not to find every problem. It is to systematically explore the
> failure space we have defined as mattering.

`/hm:review` today satisfies neither half of that sentence.

**No declared space.** Reviewer selection is *reductive* — `routing: conditional` drops
specialists by path substring, and nothing records which concerns were exercised. Two of the
five failure classes that matter have no reviewer in `/hm:review` at all:
failure/recovery/persistence has none, and tests/oracle/mutation has an agent
(`test-reviewer`) wired only into `/hm:execute` Phase A.5. A round can return Grade A having
never looked at recovery or at the tests' own oracles, and the report says nothing about that.

**No frozen artifact.** The auto-fix loop re-reviews only the scopes a round's fixes touched,
so the **last** round's fixes always exit unreviewed. Measured here, the defects those fixes
introduce run at 11/22, 7/7 and 3-of-4-rounds — every time behind a fully green four-gate run,
once behind a 7/7 mutation score (`[fail:test] fix-introduced-defect-passes-all-gates`,
count:7). The same compounding is measured in `/hm:plan`, where five of six rounds were
document revisions that each introduced the next round's P0, with no mechanical gate in
existence at all — and this SPEC's own planning reproduced it twice more.

Coverage without a frozen artifact declares a space and then explores the wrong object. A
frozen artifact without coverage explores the right object at random. Both ship, as one
mechanism.

## 🌅 Outcomes

- `/hm:review` declares a **failure space of five lenses** and records, per round, which were
  exercised. A reader of the REVIEW report or of `review-telemetry.jsonl` can name what was
  looked at; today neither artifact answers that.
- **Approval is unreachable while a mandatory lens is unexercised**, at every
  `grade_threshold` value. "No findings" can no longer be mistaken for "reviewed".
- A `/hm:review` reporting `APPROVED` has had its **final** diff — including the last round's
  fixes — covered by all five lenses over a frozen checkout, by a pass that applied none of
  those fixes.
- A `/hm:plan` whose last revision was validated reports its outcome with a token whose
  readers are named (AC-010) — including on the `NEEDS_REVISION` path, which today is never
  re-validated at all.
- The cost is bounded and stated (see Constraints).

## 📖 Definitions

| Term | Definition |
|---|---|
| **mandatory lens** | One of exactly five: `correctness` (spec / invariants), `failure` (recovery / persistence), `concurrency` (resource / lifetime), `security` (external input), `tests` (oracle / mutation). |
| **optional reviewer** | `ux-reviewer`, `performance-reviewer`. Outside the declared space; reachable through `routing: conditional`. |
| **exercised** | A lens is exercised for a round iff a result file for it exists and parses under AC-011. Never a self-report. |
| **`review_base`** | The commit the whole review is measured against. Resolved **once at round 1** by the first rule that yields a commit **other than `HEAD`**: (1) `git merge-base HEAD <base branch>`, where the base branch is `worktree.base_branch` from `harness.yaml` when set, else the repository's default branch as reported by `git symbolic-ref refs/remotes/origin/HEAD`, else `main`; (2) the fork point of the current branch (`git merge-base --fork-point`); (3) `HEAD~1` if it exists; (4) the empty tree. **Rule (1) is skipped when it returns `HEAD`** — which it does whenever the review runs directly on the base branch (worktree OFF / Side preset) or on a branch with no commits of its own. Without that skip the confirmation pass would diff only the uncommitted working state, i.e. only the last round's fixes — reinstating the very defect it exists to remove, on the two most ordinary configurations. |
| **`review_base` store** | `refs/hm-freeze/v1/<slug>-base`, written at round 1 and read by every confirmation pass. `review_base` must survive from round 1 across N rounds and a repair round; a value with no named store is a free variable that each pass would re-resolve, drifting as new commits land. |
| **pass id** | `confirm-1` for the first confirmation pass, `confirm-2` for the second. It is the `<n>` in the freeze ref and frozen root, and the `--round` value passed to the coverage CLI. A confirmation pass is **not** a round — the repair round does not increment `iteration_count` — so reusing a round number would let a lens that failed during the pass be counted as exercised from that round's stale result file, returning `blocks_approval: false`: a silent false approval produced by the coverage mechanism itself. |
| **new finding** | A finding whose `codex_adapter.finding_id` is absent from the union of every prior round's `consensus-passed` set in this `/hm:review`, read from the REVIEW report's per-round records. Mechanical, not a judgement: the confirmation pass runs lenses that never ran in earlier rounds, so it necessarily returns findings that are not regressions, and "new" decided by the model is the self-report class AC-011 exists to close. |
| **freeze commit** | A commit containing the current working state (tracked **and** untracked), parented on `review_base`, named by `refs/hm-freeze/v1/<slug>-<n>`. |
| **frozen root** | `.claude/.hm-freeze/<slug>-<n>/` — the detached worktree checked out at the freeze commit and given to lens briefs as their review root. |
| **confirmation pass** | One dispatch of all five mandatory lenses over `review_base..<freeze commit>`, from the frozen root, applying no fixes. |

## 📋 In-Scope Scenarios

### S1: The failure space is declared and exercised on the initial round

**Given** an `/hm:review` starting round 1
**When** reviewers are dispatched
**Then** all five mandatory lenses are dispatched as lens briefs, in parallel
**And** `review_base` is resolved and recorded
**And** the round's coverage is computed per AC-011
**And** `routing: conditional` may add or drop only optional reviewers

### S2: Incomplete coverage blocks approval independently of the grade

**Given** a round whose coverage set is a strict subset of the mandatory lenses
**When** the approval condition is evaluated, at any `grade_threshold` value
**Then** the review does not report `APPROVED`, regardless of the P0/P1 counts
**And** the report names the unexercised lens
**And** that lens is re-dispatched on every subsequent round until it returns a result or
the review terminates

### S2a: Coverage that cannot be completed within the round budget terminates visibly

**Given** a review whose round budget is exhausted — `max_review_rounds` is 1, or the
no-progress invariant fires because a re-dispatched lens keeps failing — with coverage
still incomplete
**When** the stage reaches its terminal state
**Then** it reports `CHANGES_REQUESTED` with a **coverage blocker** in the REVIEW report,
rendered distinctly from a finding: `lens <id> did not deliver a result in N attempts`
**And** a delivery failure and a clean lens never render the same way

### S3: Confirmation pass covers the whole declared space on a frozen checkout

**Given** an `/hm:review` whose grade would otherwise clear `grade_threshold`
**When** the grade gate would emit `APPROVED`
**Then** a freeze commit is built and checked out at the frozen root
**And** all five mandatory lenses are dispatched over `review_base..<freeze commit>`
**And** that pass applies no fixes
**And** the grade and the coverage set are recomputed from that pass
**And** a telemetry row records that the pass ran
**And** the frozen root is removed when the pass returns

### S4: Clean confirmation pass approves

**Given** a confirmation pass
**When** it yields zero new `consensus-passed` findings at P0 or P1, with all five lenses
exercised
**Then** the review terminates `APPROVED`
**And** the terminal telemetry row records zero new severe findings

### S4a: A confirmation pass with incomplete coverage never approves

**Given** a confirmation pass whose coverage set is a strict subset of the mandatory lenses
**When** the stage handles it — **including when it yielded zero new severe findings**
**Then** the review terminates `CHANGES_REQUESTED` with the AC-013 coverage blocker
**And** no repair round is consumed, because there is nothing to repair

> Without this scenario the zero-new-severe-but-incomplete-coverage state matches no branch:
> S4's conjunct fails, S5's dirty trigger does not fire, and S9's not-run path does not apply
> because the pass did run. A dispatch failure is medium-likelihood and the pass dispatches
> five lenses, so the state is reachable — an absent case inside the mechanism built to close
> absent cases.

### S5: Dirty confirmation pass re-enters the fix loop exactly once

**Given** a confirmation pass yielding ≥1 new `consensus-passed` P0 or P1, **with `auto_fix`
enabled**
**When** the stage handles it
**Then** the fix loop is re-entered for exactly one **repair round**, budgeted separately
from `max_review_rounds` and not incrementing `iteration_count`
**And** a new freeze commit is built and a second confirmation pass is dispatched
**And** no third confirmation pass is ever dispatched in the same `/hm:review`

### S5a: With `auto_fix` disabled, a dirty pass opens no repair round

**Given** a dirty confirmation pass with `auto_fix` disabled by config or `--no-auto-fix`
**When** the stage handles it
**Then** the review terminates `CHANGES_REQUESTED` with `human_review_needed = true`
**And** no repair round is opened and no second confirmation pass is dispatched

> This holds **whatever the grade** and whatever order the gate evaluates its branches in.
> An earlier draft justified this case by asserting that the shipped gate tests
> `grade ≥ grade_threshold` before the auto-fix-disabled branch. That ordering may be true
> today, but Phase 4 edits that gate, and no test pinned it — so the rule is stated
> order-independently instead: **with `auto_fix` off, the confirmation pass is read-only and
> never opens a repair round.**

### S6: Second dirty pass terminates without approval

**Given** a second confirmation pass that still yields ≥1 new `consensus-passed` P0 or P1
**When** the stage handles it
**Then** the review terminates `CHANGES_REQUESTED` with `human_review_needed = true`
**And** the surviving findings are named in the REVIEW report

### S7: Inside `/hm:loop`, a dirty second pass halts the iteration

**Given** a `/hm:review` running under an active loop for this session
**When** the second confirmation pass is dirty
**Then** the stage emits a Gate 0 receipt with `verdict: fail`
**And** the loop driver owns retry and escalation

### S8: Cross-model voters are re-read, never re-invoked

**Given** a harness with `second_opinion.models` non-empty
**When** a confirmation pass runs
**Then** it re-reads the `## 🧊 Cross-model findings (frozen @ round 1)` section
**And** the confirmation-pass block issues no `second_opinion_invoke` call

### S9: A non-approval exit skips the confirmation pass entirely

**Given** an `/hm:review` that stops for `max_review_rounds` or the no-progress invariant
**When** the stage reaches its terminal state
**Then** no confirmation pass is dispatched
**And** the telemetry row records the pass as not-run rather than as clean

> `auto_fix` disabled is deliberately **not** on this list — S5a governs it. An earlier draft
> listed it here while the PLAN said the opposite; that contradiction was itself introduced
> by a repair.

### S10: plan-validator re-validates the whole PLAN once after the last revision

**Given** a `/hm:plan` whose PLAN has been revised in response to validator findings, on
**either** the `NEEDS_REVISION` or the `MAJOR_REVISION` path
**When** the last revision is written
**Then** the whole PLAN document is re-validated in one pass — not only the revised sections
**And** pass 2 is **terminal**: its findings are recorded in `## 🔍 Plan Validation`, never
revised
**And** if blocking findings survive, the PLAN frontmatter records
`validator_outcome: MAJOR_REVISION_TERMINAL`
**And** its two readers are: `/hm:execute` proceeds, treating the recorded findings as known
risks; loop-mode Gate 0 emits `verdict: fail`
**And** the existing two-pass cap and its `stage_agent_ledger` rows are otherwise unchanged

## 🚫 Non-Goals

- **Accepted-risk register** — an `accepted` disposition with owner and rationale. The
  coverage record shipping here is the baseline it would record against.
- **Human semantic-ownership attestation** — no representation is added.
- **Per-project lens configuration.** The five lenses are fixed this round; a `harness.yaml`
  axis is a later decision and needs this default to migrate from.
- **Retiring `ux-reviewer` / `performance-reviewer`.** They stay as optional reviewers.
  Removing them is the only choice here that *reduces* what the harness can find.
- **New reviewer agents.** Lenses are dispatch-time briefs, not agent files.
- **Raising `max_review_rounds`.** Rejected by `RESEARCH-review-round-inflation`.
- **Gating on the measure-C counters** (`unreviewed_fix_count`, `regression_attributed_n`,
  `attribution_unknown_n`). They stay advisory.
- **Re-typing the P0..P3 severity rubric.** It is a wire format across append-only rows.
- **An `open_items` field on the `stage_agent_ledger` row.** Considered and dropped: the
  terminal outcome is recorded in the PLAN frontmatter and `## 🔍 Plan Validation`, which
  needs no schema change and no phase that owns one.
- **`/hm:execute` Phase A.5 and `/hm:verify`.** Out of surface scope.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md §Runtime/Tooling) |
| Mandatory lenses | exactly 5, fixed, one constant | A declared space must be enumerable to be gateable |
| New agent files | 0 | Lens briefs are prompt-only — the form validated at `/hm:execute` Phase A.5, where 3 parallel lenses raised findings from 2–3 to 9–12 with zero overlap between the blocking lenses |
| Confirmation passes per `/hm:review` | ≤ 2 | The cost/completeness trade-off |
| Repair round budget | 1, **separate from `max_review_rounds`** | Counting it against the cap makes the mechanism inert on exactly the reviews that used every round |
| Cost of an approval | +1 full pass = **5 parallel lens dispatches**; dirty path **+10 dispatches plus one repair round**, which may still end `CHANGES_REQUESTED`; plus **1 dispatch per missing mandatory lens per subsequent round** while coverage is incomplete | Wall-clock is one pass per confirmation (subagents run concurrently, never entering main-loop context); token cost is per dispatch. A review that never reaches the approval path pays nothing extra |
| Diff base | `review_base`, resolved once at round 1 | Parenting the freeze commit on `HEAD` and diffing from it would show **only** the last round's fixes — turning the confirmation pass into the scope-selective re-review it replaces |
| Frozen root | `.claude/.hm-freeze/<slug>-<n>/`, gitignored and covered by the harness churn prefixes | It must be outside `.worktrees/` (whose guards and prefix sweep do not cover it) *and* invisible to the create-guard, the finalize dirt-filter and wrapup's `git add` — otherwise the freeze becomes user dirt, and a second freeze's `git add -A` ingests the first |
| Second-opinion invocations | exactly 1 per enabled model per `/hm:review` | Vote-freeze contract of `PLAN-second-opinion-acceptance-gate` |
| Evidence of execution | telemetry fields + a called CLI, never prose | A prompt-level criterion is not enforcement; this stage has a precedent of a model reinterpreting a costly mandatory step as optional (`[wiki:gotcha] loop-body-skipping-review-stage`) |
| Verifier strength | every Python verifier under the tier-1 mutation gate (AC-015) | A passing test is evidence about the gates' coverage, not the code's correctness; defect injection is the only procedure in this task that produced strong evidence |
| What AC-011 judges | **liveness**, not validity | The verdict answers "did five result files appear and parse", which is a checked surface distinct from the requested behaviour — see AC-011's note and the residuals below |
| Loop mode | dirty second pass ⇒ `verdict: fail` receipt | An absent-case with no reader is the count:8 feature-black-hole class |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `test_round1_dispatches_all_mandatory_lenses` |
| S2 (coverage verdict) | unit (CLI, end-to-end) | `test_coverage_cli_blocks_when_any_mandatory_lens_is_absent` |
| S2 (threshold independence) | unit (render, ×3 threshold renders) | `test_gate_requires_coverage_at_every_threshold` — the CLI cannot verify this; it is threshold-blind |
| S2a | unit (render) | `test_coverage_blocker_renders_distinctly_from_a_finding` |
| S3 | unit (git) + render | `test_freeze_commit_equals_working_tree_and_diffs_from_review_base` |
| S3 (`review_base` fallback) | unit (git) | `test_review_base_never_resolves_to_head` — on the base branch, and on a branch with no own commits |
| S3 (pass id) | unit (CLI + git) | `test_confirmation_pass_never_reuses_a_results_directory` |
| S4 | unit (schema) | `test_terminal_row_records_clean_confirmation` |
| S4a | unit (render) | `test_incomplete_coverage_on_confirmation_pass_never_approves` |
| AC-015 | mutation gate | `hm spec_mutation gate --yaml specs/SPEC-ai-review-exit-criteria.machine.yaml --tier 1` over `paths_to_mutate` |
| S5 | unit (render) | `test_confirmation_reentry_bounded_at_one` |
| S5a | unit (render) | `test_auto_fix_off_opens_no_repair_round` |
| S6 | unit (render) | `test_second_dirty_pass_requests_changes` |
| S7 | unit (render) | `test_loop_mode_dirty_second_pass_emits_fail_receipt` |
| S8 | unit (render) | `test_confirmation_pass_does_not_reinvoke_second_opinion` |
| S9 | unit (schema) | `test_non_approval_exit_records_pass_not_run` |
| S10 | unit (render) | `test_plan_validator_revalidates_whole_document_once` |

### AC-001: The five mandatory lenses are enumerable in code

One module-level constant enumerates the mandatory lenses; every consumer reads that
constant. Covers S1.

### AC-002: Round 1 dispatches every mandatory lens

The rendered `/hm:review` instructs round 1 to dispatch all mandatory lenses in parallel and
to resolve `review_base` and write it to its store. `route_reviewers` may not drop a mandatory
lens; its docstring and the `harness.yaml` reviewer-routing comment both state that routing
governs optional reviewers only. Covers S1.

### AC-003: Incomplete coverage blocks approval at every threshold

`APPROVED` requires both `grade ≥ grade_threshold` and a complete mandatory-lens coverage
set, for `grade_threshold` values `A`, `B` and `C` alike, irrespective of P0/P1 counts. The
rendered gate consumes the AC-011 verdict and the report names the unexercised lens. Covers S2.

### AC-004: The freeze is faithful, and the pass diffs from `review_base`

`review_base` resolves per its Definitions row, never to `HEAD`, and is written to its store
at round 1 and read from there by every confirmation pass. The freeze commit's tree is
byte-equal to the working tree for tracked **and** untracked paths; it is parented on
`review_base`; the confirmation pass diffs `review_base..<freeze commit>`; the frozen root is
created at `.claude/.hm-freeze/<slug>-<pass id>/`, does **not** appear in `git status`, and is
removed afterwards; the pass applies no fixes. Covers S3.

### AC-005: Telemetry carries a confirmation and coverage record

`ReviewTelemetryRecord` accepts `lenses_exercised`, `confirm_pass_ran` and
`confirm_pass_new_severe_n` under the three rules of AC-012. "Both-or-neither" does **not**
describe this pair. Covers S4, S9.

### AC-006: Confirmation re-entry is bounded at one

No `/hm:review` dispatches more than two confirmation passes, for any input; the repair round
does not increment `iteration_count`. Covers S5.

### AC-007: A dirty pass without auto-fix, and a dirty second pass, both terminate

With `auto_fix` disabled, a dirty confirmation pass opens no repair round and terminates
`CHANGES_REQUESTED` with `human_review_needed = true`, whatever the grade and whatever the
gate's branch order. The same terminal applies to a dirty second pass. Covers S5a, S6.

### AC-008: Loop mode fails the receipt rather than persisting silently

Under an active loop for this session, a dirty second confirmation pass emits a Gate 0
receipt with `verdict: fail`. Covers S7.

### AC-009: The confirmation pass does not re-invoke the second-opinion CLIs

The confirmation-pass block contains no `second_opinion_invoke` call and does contain the
instruction to re-read the frozen cross-model section. This render assertion is the **only**
verification mode; a ledger-row comparison is optional and `INTEGRATION`-guarded. Covers S8.

### AC-010: plan-validator re-validates once, terminally, with a named outcome and readers

The rendered `/hm:plan` instructs a whole-document re-validation after the last revision on
both revision paths, within the existing two-pass cap; states that pass 2 is terminal
(findings recorded, never revised); records `validator_outcome: MAJOR_REVISION_TERMINAL` in
the PLAN frontmatter when blocking findings survive; and names both readers — `/hm:execute`
proceeds with the recorded findings as known risks, loop-mode Gate 0 emits `verdict: fail`.
No `stage_agent_ledger` schema change. Covers S10.

### AC-011: Coverage liveness is computed by a called CLI from main-loop-written results

> **The judged proposition, exactly:** for each mandatory lens, a result file exists at the
> path below, parses as JSON, and self-identifies with a matching lens id. Nothing else.
>
> **What it therefore does NOT judge:** whether any reviewing occurred. The proposition is
> satisfied by writing five well-formed files. The earlier wording "fail-closed by
> construction" is withdrawn — it described the file-set check as if it were a validity check.
>
> Two measurements set the size of that gap. *Building to the Test* (arXiv 2606.28430): with a
> hidden 222-test oracle in the loop, agents scored near-perfect from a demo holding the tested
> behaviour while the requested library was left dead. *RuBench* (arXiv 2607.06411): systematic
> oracle-hunting in one model family, in one case mining a prior round's artifacts from the run
> machine's disk — the exact move the `<round>` keying below forbids in prose and nothing
> enforces.


**The main loop** writes one result file per *returned* lens dispatch to
`.claude/observability/.hm-lens-results/<slug>/<round>/<lens-id>.json`; a dispatch that
returns nothing produces no file. The lens subagents do not write these files — they are
read-only by tool set, and a subagent writing its own attendance record would restore the
self-report hole this AC exists to close. The rendered template then calls
`hm lens_coverage check --results-dir <dir> --slug <slug> --round <n>`, whose JSON
(`{exercised, missing, blocks_approval}`) is the **sole** producer of the coverage verdict.
A missing, unparseable, or unknown-lens file yields `blocks_approval: true`. `<n>` is a round
number for a round and a **pass id** for a confirmation pass; a results directory is written
once and **never reused**, so no pass can inherit a prior round's files. The rendered auto-fix
loop re-dispatches any missing mandatory lens each subsequent round, and renders the AC-013
coverage blocker when the budget runs out. Covers S1, S2, S2a, S4a.

> The CLI is **threshold-blind by construction** — `grade_threshold` is not an input and
> `APPROVED` is not an output. It answers only "is the coverage set complete". AC-003's
> threshold-independence is therefore *not* verifiable through this entrypoint; see its own
> verification row.

### AC-014: A confirmation pass with incomplete coverage never approves

A confirmation pass whose coverage set is incomplete terminates `CHANGES_REQUESTED` with the
AC-013 blocker, for **every** new-severe finding count including zero, and consumes no repair
round. Covers S4a.

### AC-013: Coverage that cannot be completed within the round budget terminates visibly

When the round budget is exhausted with coverage incomplete, the rendered stage terminates
`CHANGES_REQUESTED` and emits a coverage blocker reading `lens <id> did not deliver a result
in N attempts`, rendered distinctly from a finding. Covers S2a.

### AC-015: The Python verifiers are themselves verified by defect injection

Every Python surface this SPEC ships a verifier on — `lens_coverage`'s verdict construction
(AC-011), `freeze`'s `review_base` resolution and commit construction (AC-004), and
`review_telemetry`'s three rules (AC-005, AC-012) — is covered by the repository's existing
tier-1 mutation gate over its `paths_to_mutate`, at the **85%** the gate enforces. A surviving
mutant is a test gap, closed by strengthening the assertion; the threshold is never lowered.
> **Correction (2026-08-15).** An earlier draft read the gate's `score 0% < threshold 85%` as
> "the correct state — no run recorded yet." **That was wrong, and the way it was wrong is the
> subject of this whole SPEC.** The 0% was not a measurement: three faults in the shared
> `spec_mutation` wrapper made the tier-1 gate unpassable for *every* SPEC in this repository —
> an emoji-only mutmut output the parser could not read, an unscoped runner that timed out on
> the first mutant, and a `score` that returns 0.0 for an empty denominator so a **non-run and a
> total wipeout print the same string**. That third one is why the other two survived: a
> plausible number invited rationale instead of investigation, and this SPEC supplied it.
>
> All three are fixed (`mutation_runner_faults` in `spec_mutation`'s module docstring). First
> real measurement: `lens_coverage.py`, 55 mutants, 42 killed, 13 survived — **76%**, below the
> floor. AC-015 remains unmet, but now for a reason that is a fact about the tests.

**Why this is an acceptance criterion and not a nicety.** A green suite is evidence about the
gates' coverage, not about the code's correctness — this repository records that confusion at
count:7. The one procedure in this task that produced *strong* evidence was re-inserting each
defect and confirming the test failed: `review_base` accepting `HEAD`, the freeze commit
parented on `HEAD`, and an unparseable result file counted as exercised were all caught that
way, and none of them by a passing run. *Building to the Test* uses the same method — a no-op
ablation to check each verdict — as its central instrument. It was done here by hand, once,
and required by nothing. Covers S2, S3, S4.

> **Not applicable to the rendered templates.** Mutation testing cannot reach Jinja prose. The
> equivalent guarantee for render ACs is the RED gate: a render assertion that passes against
> the *unmodified* template is a false-RED and is not evidence. See the follow-up recorded in
> the PLAN — this task does not change the stage that runs that gate.

### AC-012: The telemetry validator makes new rows self-identifying

`lenses_exercised` is never null on a row this version emits — an all-lenses-failed round
writes `[]`, and null-tolerance exists only in the reader for legacy rows. A row carrying
`lenses_exercised` must also carry `confirm_pass_ran`. `confirm_pass_new_severe_n` is
required when `confirm_pass_ran` is true and must be null when it is false. A row with all
three fields absent still validates as a legacy row. Covers S4, S9.

## ❓ Open Questions

None. Every question raised across six rounds is resolved in the rules above.

## 🔍 Refinement Decisions

- **Round 1 (spec)** — One fix-loop re-entry on a dirty pass; `/hm:review` + plan-validator
  in one SPEC. The user first asked whether the pass lengthens the review and whether
  plan-validator was eligible; both were answered before the decision.
- **Round 2 (spec)** — Confirmation pass replaces the approval step; accepted-risk register
  excluded. Lens coverage was excluded here and **reopened** in round 5.
- **Round 3 (spec)** — Execution evidence is a machine receipt, not prose. plan-validator's
  form is a whole-PLAN re-validation after the last revision.
- **Round 4 (plan)** — Corrected a cost claim from round 2: the selective re-review cannot be
  pre-emptively replaced, because the grade identifying the final round is computed *from* it.
  Freeze mechanism recorded as "a git ref" — **superseded in round 6**.
- **Round 5 (plan)** — The user restated the thesis as "systematically explore the failure
  space we defined as mattering", which is the definition of lens coverage, not of the frozen
  pass. Scope reopened: coverage became the body, the frozen pass sits on top. Five-lens
  taxonomy fixed; incomplete coverage blocks; prompt-only briefs, zero new agents;
  `ux`/`performance` stay optional.
- **Round 6 (plan, adversarial)** — Two cross-model second opinions found 8 real defects; the
  plan-validator then found 11 more, 8 of them created by the repairs of those 8; a second
  validator pass found 13 more, again mostly created by the repairs. **The mechanism, not the
  findings, was the problem**: 8 of the last 13 were the SPEC and the PLAN stating one rule two
  ways, propagated by hand with no gate comparing them. Resolved by making this document the
  sole contract holder (see the note under the title). The substantive fixes landed in the
  same revision: coverage became an approval condition rather than a grade cap (inert at
  `grade_threshold` B/C); the freeze became a **detached worktree at a commit built from the
  current working state**, at a **named gitignored path**, diffed from **`review_base`** rather
  than `HEAD` (which would have shown only the last round's fixes — inverting the mechanism);
  `auto_fix`-off was restated **order-independently**; coverage gained a **CLI seam** with the
  **main loop** as the named writer; the telemetry pair's "both-or-neither" was replaced by
  three stronger rules; AC-009's three incompatible verification modes collapsed to one; and
  the `open_items` ledger field was dropped rather than left without an owning phase.
- **Skipped by the common-ground term** — test framework (`pytest`, fixed by CLAUDE.md); phase
  decomposition and file placement (established by reading the templates directly).
