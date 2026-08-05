---
type: spec
task_slug: workflow-loop-efficiency
status: draft
created: 2026-08-05
tier: 2
tags: [harness-maker, spec, python, token-economics, review-pipeline, telemetry]
test_framework: pytest
research_doc: "[[RESEARCH-workflow-loop-efficiency]]"
summary: "Stage 1 of a 2-stage landing: cut the two proven-low-yield steps, instrument the three unmeasured ones."
---

# SPEC — workflow loop efficiency (stage 1)

## 🎯 Intent

`RESEARCH-workflow-loop-efficiency` measured that the two loops the user identified —
`plan→validator` and `execute→review→fix` — are already bounded (validator caps at 2
passes; 92% of 41 reviews converge within 2 rounds) and together account for only
≈15–23% of the $3,174 measured spend, while **73% of every dollar is `cache_read`** and
**all subagents combined are 13.5%**. Cutting rounds therefore trades detection for a
small saving.

This SPEC covers **stage 1 of a 2-stage landing**: land only the cuts whose yield is
already measured, add the instrumentation that makes the remaining three decisions
possible, and produce the redundancy survey the user asked for. Stage 2 — deleting
`code-verifier`'s successors (`test-reviewer` Phase A.5, the validator's second pass,
review Pass 2) and acting on the survey — is deliberately **out of scope** and will be
decided from the data this work produces.

## 🌅 Outcomes

After this work a maintainer can:

- Run `/hm:review` without the Pass 1.5 verifier step, and see one fewer sequential
  barrier between Pass 1 and Pass 2.
- Read a ledger row for **every** `plan-validator` dispatch and **every** `test-reviewer`
  Phase A.5 dispatch, including the verdict and which pass it was — today no row exists
  for either, which is why neither can be adjudicated.
- Read a recorded Pass-2 ablation result on archived diffs, so the "+47pp precision"
  claim is either reproduced or refuted on the record rather than inherited.
- Read a redundancy matrix covering every rendered command, skill, and agent against its
  native Claude Code equivalent, with a keep/retire recommendation per row.
- Run `/hm:wrapup` with a delegate whose mismatch cause has a named root cause and a
  regression test, rather than a 40% observed failure rate.

## 📋 In-Scope Scenarios

### S1: the review pipeline no longer runs a verifier subagent
**Given** a harness rendered at the post-change version, for any of `claude-code`, `cursor`, `codex`
**When** the reviewer inspects the rendered `/hm:review` surface
**Then** no rendered command instructs a Pass 1.5 `code-verifier` (mode A) dispatch
**And** the Pass 1 → Pass 2 sequence contains no intervening agent step
**And** the `code-verifier` agent itself still renders, because cross-model PIDA mode B still uses it

### S2: a repair names the input window it newly makes reachable
**Given** `/hm:execute` is running Phase D after a Phase C repair
**When** the rendered stage body is read
**Then** it contains a step requiring the author to name the input window the repair newly makes reachable and to assert a fixture enters it in the same commit
**And** the step renders on all three targets

### S3: every plan-validator dispatch leaves a row
**Given** `/hm:plan` dispatches `plan-validator`
**When** the dispatch returns a verdict
**Then** a row is appended recording the task slug, the pass number (1 or 2), and the verdict (`APPROVED` / `NEEDS_REVISION` / `MAJOR_REVISION`)
**And** a second pass on the same slug produces a second row, so "did pass 2 change the verdict" is answerable from the ledger alone

### S4: every Phase A.5 dispatch leaves a row
**Given** `/hm:execute` dispatches `test-reviewer` at Phase A.5
**When** the reviewer returns `overall_assessment`
**Then** a row is appended recording the task slug, the attempt number, and `PASS` / `FAIL`

### S5: the Pass 2 ablation is executed and recorded, and nothing is deleted
**Given** 3 or more archived diffs with known REVIEW findings
**When** the review pipeline is run against each twice — Pass-1-only and Pass-1+Pass-2
**Then** a recorded artifact holds, per diff, the finding set from each arm and their difference
**And** the artifact states whether the "+47pp precision on anchoring-prone diffs" claim reproduced
**And** Pass 2 remains in the pipeline regardless of the result — the deletion decision is stage 2

### S6: the wrapup delegate mismatch has a named cause and a regression test
**Given** the two recorded `mismatch` rows in `.claude/observability/delegation.jsonl`
**When** the mismatch condition is reproduced
**Then** a test exists that fails against the pre-change reconciliation path and passes after it
**And** the root cause is recorded in `.claude/memory/`

### S7: the redundancy matrix covers the whole surface
**Given** the rendered harness at the post-change version
**When** the survey artifact is read
**Then** it contains one row for every rendered `/hm:` command, every skill, and every agent
**And** each row names the native Claude Code equivalent (or `none`), its availability on `cursor` and `codex`, and a `keep` / `retire` / `merge` recommendation
**And** the recommendation column applies the **Claude Code criterion**: a native equivalent in Claude Code justifies retirement even though Cursor and Codex lose the capability

### S8: the cross-model voters no longer wait for Pass 2
**Given** a harness rendered at the post-change version, on any target
**When** the rendered `/hm:review` stage is read
**Then** it instructs the enabled second-opinion models to launch concurrently with Pass 1
**And** the high-diff classifier (Side preset) runs before that launch, not after Pass 2
**And** Step 3.6/3.7 (PIDA) still runs after the cross-model results, because it consumes them
**And** the Step 4 consensus fold point and the K=2 threshold are unchanged

## 🚫 Non-Goals

- **Deleting `test-reviewer` Phase A.5, the validator's second pass, or review Pass 2.**
  All three are stage-2 decisions gated on the telemetry this work adds.
- **Acting on the redundancy matrix.** This work produces the matrix; retiring anything
  from it is a separate PLAN.
- **Restoring subagent model tiering (Approach B1).** 179 of 188 dispatches force
  `model: "opus"` because of a launch-failure workaround whose root cause is unknown;
  changing it without that root cause trades cost for launch failures. Out of scope.
- **Shrinking `CLAUDE.md` or the ≥48 KB stage bodies (Approach D).** Measured ceiling is
  ~4% of total; not worth coupling to this work.
- **Reducing `max_review_rounds` or the validator's 2-pass cap.** The research
  specifically recommends against it.
- Any change to the consensus filter, cross-model voting, or the PIDA gate.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md); `/hm:execute` Phase A writes against it |
| Language | Python 3.12+, no Bash | CLAUDE.md — hooks and tooling are `python -m harness_maker.<module>` |
| Targets | all of `claude-code`, `cursor`, `codex` must still render | Removing a step must not break a target's render; the *retirement criterion* in S7 is a recommendation, not an action |
| File writes | atomic (`tempfile` + `os.replace`) | CLAUDE.md implementation pattern; ledger appends included |
| Telemetry location | `.claude/observability/*.jsonl`, gitignored churn | Matches existing ledgers; must not trip the worktree dirt guards |
| Ledger row discipline | one row per dispatch, with a discriminator field | `second-opinion.jsonl` already shipped a bug where two row kinds shared a status and silently polluted a rate — do not repeat the shape |
| Surface budget | `surface_baseline.json` / `_ATOMIC_RATCHET` updated deliberately, never absorbed silently | Existing ratchet contract |
| Compatibility | no `harness.yaml` schema bump | Nothing here is user-configurable |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render-grep) | `test_ac_001_no_pass15_verifier_in_rendered_review` |
| S2 | unit (render-grep) | `test_ac_002_phase_d_names_newly_reachable_window` |
| S3 | unit | `test_ac_003_validator_ledger_row_per_pass` |
| S4 | unit | `test_ac_004_phase_a5_ledger_row_per_attempt` |
| S5 | manual + unit | ablation run recorded in `work-docs/`; `test_ac_005_ablation_artifact_shape` |
| S6 | unit | `test_ac_006_wrapup_receipt_mismatch_regression` |
| S7 | unit (coverage count) | `test_ac_007_redundancy_matrix_covers_surface` |
| S8 | unit (render-grep, ordering) | `test_ac_009_crossmodel_launches_with_pass1` |
| all | integration | full `pytest` + `ruff check` + `ruff format --check` + `mypy --strict src/` green |

### AC-001: rendered review surface contains no Pass 1.5 verifier dispatch
### AC-002: execute Phase D requires naming the newly-reachable input window
### AC-003: plan-validator writes one ledger row per dispatch pass
### AC-004: test-reviewer Phase A.5 writes one ledger row per attempt
### AC-005: Pass 2 ablation artifact records both arms and a reproduction verdict
### AC-006: wrapup delegate mismatch is covered by a failing-then-passing regression test
### AC-007: redundancy matrix covers every command, skill, and agent
### AC-008: the four mechanical gates stay green and the surface ratchet moves deliberately
### AC-009: the rendered review stage launches the cross-model voters concurrently with Pass 1

### AC-010: the Phase D.5 repair guard carries operative force

Added during wrapup, after `/hm:review` established that ADR-003's requirement could not be
met mechanically. The guard's `type` is `judgment` because the question is semantic: a step
that says "consider pausing" and one that says "STOP — do not advance the phase" are
indistinguishable to every literal-grep predicate in the structural test, and those two
wordings are the entire difference between a guard and a suggestion.

Two mechanical mutation controls were attempted first and both were circular — deleting the
grepped literal, then replacing it with a weaker paraphrase, each turn the predicate red for
the same construction-level reason rather than because the mutant is weaker. The verdict
therefore comes from an **independent** `judgment-reviewer` against the `repair_guard_force`
rubric, whose criteria were written from the four recorded recurrences of
`[fail:code] fix-introduced-defect-passes-all-gates` rather than from the step being judged.
`mark-judged` stores a hash of the subject, so editing the step invalidates the pass.

## ❓ Open Questions

These are handoffs to `/hm:plan`, to be locked as ADRs:

1. **The chosen oracle is deliberately weak, and this SPEC records that as an accepted
   risk.** The user selected `golden` — cost metrics as the acceptance number, with
   detection preserved *by proxy* via the regression suite. This session's own evidence
   contradicts the proxy: `[fail:test] fix-introduced-defect-passes-all-gates` is at
   count:4, most recently 11 of 14 findings being defects introduced by this repo's own
   fixes, **every one on a green four-gate run**, once including a 7/7 mutation check.
   A green suite is therefore evidence about the suite's coverage, not about the change.
   AC-008 carries an `oracle_independence_waiver` for exactly this reason.
   *For plan:* is there a cheap non-circular detection check worth adding — e.g. replaying
   one archived diff through the changed pipeline and asserting the previously-found
   P0/P1 ids still surface — or is the risk accepted as recorded?
2. **AC-005 has a gap no gate can close.** "The ablation was run honestly" is not
   mechanically checkable; the AC only checks the artifact's shape. Accept, or add a
   judgment rubric + `judgment-reviewer` binding?
3. **Where do the two new ledgers live?** One shared `stage-agents.jsonl` with a `stage`
   discriminator, or two files matching the existing per-domain convention? The
   `second-opinion.jsonl` precedent argues for an explicit discriminator either way.
4. **S6 root cause is unknown at SPEC time.** The 2 mismatch rows say the delegate
   claimed work not on disk; whether that is a worktree-path issue (the known
   `--worktree` footgun), a receipt-schema issue, or the delegate over-claiming, is not
   yet established. If the cause turns out to be unreproducible, does the AC become
   "delete the mechanism" per remedy (b) of the count:4 note?
5. **Does removing Pass 1.5 change the Pass 2 input contract?** Pass 2 currently
   consumes the verifier's `kept` list. It must fall back to the raw Pass 1 list —
   confirm no downstream step reads `stats.dropped_n`.

## 🔍 Refinement Decisions

- **Round 1** — Scope: B2 (delete Pass 1.5) + C (fix-introduced-defect step) + MEASURE
  (instrument validator and Phase A.5) + B3 (run the Pass 2 ablation), plus a new
  user-raised item: survey whether commands/skills are still needed given the model's own
  native harness. Oracle: `golden` — cost metrics only, detection proxied by the
  regression suite (concern recorded, user reaffirmed). `wrapup` delegate: **repair**,
  not delete. Landing: **2-stage** — instrument first, decide second.
- **Round 2** — Retirement criterion for the redundancy survey: **Claude Code basis** —
  a native equivalent in Claude Code justifies retirement, accepting the capability loss
  on Cursor and Codex. Pass 2 deletion: **deferred to stage 2** regardless of the
  ablation outcome, consistent with the 2-stage landing.
- **§2.5 gate** — candidates generated and rejected: `test_framework?` ❌ common-ground
  (CLAUDE.md fixes `pytest`); `performance budget?` ❌ EIG (no perf-sensitive path);
  `include agents in the matrix?` ❌ common-ground (zero marginal cost, already implied);
  `migration notice for Cursor/Codex retirement?` ❌ confidence ≥ τ (CHANGELOG + 5-file
  version policy already governs breaking changes). No candidate passed all 5 terms;
  interview closed.
