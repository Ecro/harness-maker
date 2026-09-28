---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-09-28
run_id: 01263f044f17
review_base: 9f60e97dc1514e58faf124f68023176d33879588
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
second_opinion_results:
  - model: codex
    status: invoked
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-feedback-continuity
  computed_at: 2026-09-28T08:20:00Z
---

# Intent feedback continuity: fresh review after Phase 6

Sixth review of the task and the first after the branch was rebased over 19 main commits (0.60.5)
and Phase 6 (approved tie order across an acknowledged later start) was finished. Span:
`9f60e97d..working tree` — the whole task, not only Phase 6.

## 🎯 Round 1 Summary

`review_consensus finalize`: **B** — one counted P1 (`74cd71ba38f9981d`; `546b5e82eeabd1e7` is
its duplicate from the concurrency lens), five P2, errors none. All seven lenses exercised
(`lens_coverage`: `blocks_approval: false`). Codex invoked once; PIDA accepted both of its
findings on a main-loop reproduction (the gatherer produced no oracle: `harness.yaml` declares no
`toolchains`). Both are P1 `manual-only`, so `human_review_needed: true` regardless of grade.

## 🔍 Drift Findings

None. Every changed path is inside a PLAN phase scope; snapshot files are rendered from the
changed `workflow-feedback.md.j2`; the trial PLAN is Phase 2's authorized recovery. Intent drift
(Step 3.3, `WORLD-INTENT-CLOSED-LOOP`): none — decisions stay `actor: user`, no automatic
approval or scope expansion.

## ✅ Consensus Findings

| id | Sev | Lens | Location | Finding |
|---|---|---|---|---|
| `74cd71ba38f9981d` | P1 | robustness | `src/harness_maker/worktree.py:5135` | A task-attributable stage-span append that cannot take the merge fence within 5 s now fails preflight, while land/finalize/refresh legitimately hold the same fence up to `_FENCE_TIMEOUT` (360 s); the raise path is untested. The fail-closed choice itself is the fifth review's intended repair — the defect is the budget. |
| `546b5e82eeabd1e7` | P1 | concurrency | `src/harness_maker/stage_spans.py:144` | Duplicate of `74cd71ba38f9981d` (same 5 s vs 360 s fence budget). |
| `e1f2e2267b6396a6` | P2 | consistency | `src/harness_maker/intent_cli.py:92` | Trial CLI exit-code set omits `source_conflict`, unlike the sibling rejected-write reasons. |
| `78a0c5c9b23d3e91` | P2 | consistency | `src/harness_maker/intent_trial.py:405` | `".worktrees"` literal duplicates `worktree.WORKTREE_DIR_NAME`. |
| `715c17f6a126ebb4` | P2 | tests | `tests/unit/test_intent_trial.py:1135` | Golden observables compare `reason` to strings the module never emits (always False). |
| `571b91b14419a2f3` | P2 | tests | `tests/unit/test_intent_trial.py:1134` | `questions` is a hardcoded `[]`, so the observable is always 0. |
| `555991870af104c3` | P2 | tests | `tests/unit/test_intent_trial.py:1158` | `invented_coverage` / `independent_work_may_continue` read keys never emitted. |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Location | Finding |
|---|---|---|---|---|
| `8138563b5c05b351` | P1 | codex (PIDA accepted) | `src/harness_maker/intent_trial.py:596` | `_reviewed_order` appends `later` tasks without checking ties inside that suffix; a reviewed order then suppresses `_status`'s tie check. Reproduced: approved `[b, a]`, then acknowledged `c` and `d` both at T3 → members `['b', 'a', 'c']` with no review of the c/d tie (AC-005). |
| `401b08cafb6b6222` | P1 | codex (PIDA accepted) | `src/harness_maker/intent_trial.py:594` | An append-only ledger change with no new task (`later == []`) returns `None`, so the approved tie order is dropped. Reproduced: approved `[b, a]`, then one resume start row for `b` → `order_conflict`. Every later stage entry of a tied member would block the trial. |

Security Pass 1 raised `actor == "user"` carrying no identity binding; Pass 2 dropped it against
context — the SPEC defines decisions as explicitly supplied files and the third review already
withdrew the same objection; harness-maker authenticates no local caller anywhere.

## 🤝 Disagreements

None across severity tiers. Tests-lens findings moved P0/P1 → P2 between passes: each golden row
still discriminates through a sibling field.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `8138563b5c05b351` | codex | P1 | src/harness_maker/intent_trial.py | 596 | Approved order also approves simultaneous starts of new tasks (unreviewed tie in the `later` suffix) | `resolved = ordered + later`; chronology check rejects only `>` | false | accepted | intent_trial.py:594-600 lets equal-time later tasks through (only > rejected). Repro: c/d tied at T3, members=['b','a','c'] with no review, against SPEC AC-005. | pending | — |
| `401b08cafb6b6222` | codex | P1 | src/harness_maker/intent_trial.py | 594 | Resume-only ledger append drops the approved tie order | `if not later or …: return None` | false | accepted | intent_trial.py:594: later=[] returns None, so the tie check at :783 fires. Repro: one resume row for b gives order_conflict. RESEARCH:134 requires same-slug resume to keep an equivalent status. | pending | — |

### Iteration 2 (Grade: B → A)
Fixes applied: 1

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Task-attributable stage-span append waits `_FENCE_TIMEOUT` instead of 5 s (`emit_event(fence_timeout=…)`); raise path now tested | `src/harness_maker/worktree.py:5135`, `src/harness_maker/stage_spans.py:144` | Applied · caused_by=none |

`74cd71ba38f9981d` and its duplicate `546b5e82eeabd1e7` → `resolved` (verification passed: ruff, format, mypy --strict, 192 targeted tests). New tests:
`tests/integration/test_intent_trial_concurrency.py::test_s2_task_start_waits_out_a_fence_held_past_the_telemetry_budget`
(a peer holds the fence 6.5 s) and `::test_s2_stage_span_failure_is_fatal_only_for_a_task_start`; both go
RED with the budget reverted to 5 s. P2s not selected (grade B, not D/F).

Remaining: 5 P2 + 2 manual-only P1 | New issues introduced: 0
Churn: 0.077 (max: tests/integration/test_intent_trial_concurrency.py, measured 3, excluded 0)
rereview: skipped — churn 0.08 < 0.30

## Confirmation pass 1 (freeze `efe0f5d3`, span `9f60e97d..efe0f5d3`)

All seven lenses exercised. New findings:

| id | Sev | Lens | Location | Disposition |
|---|---|---|---|---|
| `83dd3e02f1188efa` | P1 | functionality | `tests/unit/test_intent_trial.py:792` | accepted — the new `hm intent trial` CLI had no test for `reconcile` or any exit-1 path |
| `a4b4f5247f16fcad` | P1 | concurrency | `src/harness_maker/stage_spans.py:149` | **rejected (AC-004)** — proposes a dedicated lock name for the span ledger; ADR-003 deliberately puts trial sources and supported writers on the repository merge fence, which is what AC-004's committed-state guarantee rests on |
| `925994bef2cc5b82` | P1 | concurrency | `src/harness_maker/worktree.py:5136` | **rejected (AC-004)** — a task preflight waiting behind a peer's land is the designed cost of required evidence under the shared fence; it fails only past the same `_FENCE_TIMEOUT` ceiling every holder uses |
| `9f689a7f623a7c9c` | P2 | security | `src/harness_maker/intent_trial.py:1065` | accepted — `_writer()` hand-rolls the fence instead of `_acquire_merge_fence` |
| four P2 | — | tests / consistency | as round 1 | duplicate of round-1 ids |

> **Self-adjudication note.** Both rejected P1s target the round-2 fix made by the same orchestrator
> that rejected them. The authority is AC-004 plus PLAN ADR-003, and the confirm-2 concurrency lens
> independently traced the lock topology and found no deadlock on an existing path — but a human
> should read these two rejections, not trust them.

Dirty → one repair round (not counted as an iteration): added
`tests/unit/test_intent_trial.py::test_s1_cli_reconcile_dry_run_writes_nothing_and_apply_commits` and
`::test_s2_cli_rejected_decision_exits_nonzero_without_writing`. Each goes RED on its mutant (dropping the
`--dry-run` wiring; removing `revision_conflict` from the exit-1 set). Verification: ruff, format,
mypy --strict, 133 intent tests passed.

## Confirmation pass 2 (freeze `dc512b41`, span `9f60e97d..dc512b41`) — terminal

All seven lenses exercised; security, concurrency and tests returned nothing new. One new severe finding:

| id | Sev | Lens | Location | Finding |
|---|---|---|---|---|
| `7744145e38828620` | P1 | consistency | `src/harness_maker/intent_trial.py:1249` | `record_decision`'s five early returns (`replay`/`decision_conflict`, `revision_conflict`, `authority_required`, `source_conflict`) override `reason` but keep the `action` `_status()` computed before the check, while `reconcile` (:1362/:1375) and `_blocked` keep them in sync. The rendered skill tells the agent to follow `action`, so after a conflict it is told an unrelated next step. Verified by reading the code. |

Stage-terminal under the two-pass bound: **CHANGES_REQUESTED**, `human_review_needed: true`. No third pass.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 P1, 5 P2, 2 manual-only P1 | — |
| 2         | A     | 1             | 5 P2, 2 manual-only P1 | 0 |
| Confirm 1 | dirty | 1 repair (CLI tests) | — | 1 P1 accepted, 2 P1 rejected, 1 P2 |
| Confirm 2 | dirty | —             | — | 1 P1 |

Final grade: A provisional (never approved)
Iterations used: 2 / 3
Exit reason: confirmation-2-new-severe
Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

### Open before this task can land

1. `7744145e38828620` (P1) — `record_decision` `action` out of sync with `reason`.
2. `8138563b5c05b351` (P1, codex, PIDA-accepted, reproduced) — unreviewed tie inside the `later` suffix.
3. `401b08cafb6b6222` (P1, codex, PIDA-accepted, reproduced) — a resume-only ledger append drops the approved tie order; in a live trial every later stage entry of a tied member blocks collection.
4. The two AC-004 rejections above need a human read.
5. P2s: exit-code set, `.worktrees` literal, three dead golden observables, hand-rolled `_writer` fence.

Items 2 and 3 sit in the same function Phase 6 changed, and the repair is a real design question —
how a reviewed order extends when later tasks tie among themselves, and whether a same-slug resume
counts as an inventory change at all — so they belong in a new PLAN phase with a test-first gate,
not an auto-fix.

## 📏 Size & Complexity (round 2)

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/stage_spans.py` | 297 → 302 | 29 → 29 | 4 → 4 | measured |
| `src/harness_maker/worktree.py` | 6296 → 6299 | 801 → 802 | 7 → 7 | measured |
| `tests/integration/test_intent_trial_concurrency.py` | 526 → 570 | 97 → 101 | 3 → 3 | measured |
