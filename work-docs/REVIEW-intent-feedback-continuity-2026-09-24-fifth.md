---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
created: 2026-09-24
run_id: 9991f50a9862
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-feedback-continuity
  computed_at: 2026-09-24T03:07:42Z
---

# Intent feedback continuity: fifth independent review

The reviewed worktree includes the approved SPEC, implementation, native evidence, and Phases 1–5 of the PLAN. The Phase 5 RED tests, independent A.5 test gate, focused regression set, full non-advisory pytest suite, Ruff, mypy, strict machine SPEC validation, approval status, and whitespace checks passed. The base real-task trial remains collecting/pending with two enrolled tasks and no user assessment. No commit or landing occurred.

Drift scan: changed paths are covered by the PLAN phases; AC-001–010 have their approved machine or judgment evidence. The public contract is fixed for this review.

Status: CHANGES_REQUESTED after the second confirmation pass.

## Round 1 summary

`review_consensus finalize` returned **C**: four counted P1 findings, four P2 reviewer findings, no errors, and all seven mandatory lenses exercised. Codex was invoked once. PIDA accepted all three Codex findings; its P1 is manual-only pending corroboration and remains a real SPEC concern.

## Consensus findings

| ID | Severity | Location | Finding |
|---|---|---|---|
| `d1c9d0bb529e52c3` | P1 | `src/harness_maker/intent_trial.py:279` | Malformed persisted assessment can crash trial status |
| `cf837a44fd20d822` | P1 | `src/harness_maker/intent_trial.py:585` | New acknowledged start blocks enrollment before first reconcile |
| `99bed858188146f1` | P1 | `src/harness_maker/intent_trial.py:557` | Equivalent timestamp formats invalidate start acknowledgment |
| `a9cf4b04b5954973` | P1 | `src/harness_maker/worktree.py:4917` | Incomplete secret copy can be landed as a tracked file |
| `1585b31c4a1bb80d` | P2 | `tests/integration/test_intent_trial_concurrency.py:113` | Writer-kill recovery test accepts unsuccessful follow-up writes |
| `800bfce3830edd55` | P2 | `tests/unit/test_intent_trial.py:406` | Persisted source-review validation lacks malformed-field regression oracle |
| `4359a07104cfdc1e` | P2 | `tests/unit/test_intent_trial.py:310` | Acknowledged extension tests require reviewed prefix to be committed first |
| `177b863ed3b23679` | P2 | `tests/unit/test_intent_trial.py:322` | Acknowledgment tests use only identical timestamp formatting |

## Manual-only findings

- `12b6ae2702587115` P1: Detect contradictions to frozen member starts even when task order is unchanged (`src/harness_maker/intent_trial.py:718`). **Resolved in round 2**; changed first-start evidence now yields `source_conflict` and a pending outcome.
- `7cd834f032407ed4` P2: Refresh derived Trial section when terminal evidence changes (`src/harness_maker/intent_trial.py:1259`).
- `f185f7358699dfe7` P2: Preserve blocked read reasons in record_decision (`src/harness_maker/intent_trial.py:1164`).

## Frozen cross-model findings (round 1)

```json
{
  "frozen_at_round": 1,
  "models": [
    {
      "model": "codex",
      "status": "invoked",
      "reason": null
    }
  ],
  "findings": [
    {
      "id": "12b6ae2702587115",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 718,
      "summary": "Detect contradictions to frozen member starts even when task order is unchanged",
      "evidence": "Committed starts a=01:00,b=02:00,c=03:00; new first start a=00:30. _status reports pending/passed without chronology conflict.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Reproduction: changing frozen a first start to earlier time kept outcome passed and reason pending; _status checks order only.",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "7cd834f032407ed4",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 1259,
      "summary": "Refresh derived Trial section when terminal evidence changes",
      "evidence": "Reconcile returns before rendering when membership, source_refs and recovery are unchanged, leaving Terminal=False and Collection=collecting in PLAN after completion.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Reproduction: terminal event made status terminal true but reconcile changed false and visible PLAN Terminal remained False.",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "f185f7358699dfe7",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 1164,
      "summary": "Preserve blocked read reasons in record_decision",
      "evidence": "_read returns trial=None for lifecycle_pending or deleted committed active PLAN; record_decision overwrites reason with no_trial.",
      "source": "codex",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Reproduction: deleted committed active PLAN gave status source_conflict but record_decision no_trial.",
      "status": "pending",
      "invalidation_reason": null
    }
  ]
}
```

## Review iteration summary

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 | C | — | four counted P1; accepted Codex P1 manual-only; P2 retained | — |
| 2 | A | 4 counted P1 fixes; 1 corroborated manual-only P1 fixed in the same source batch | four reviewer P2 and two Codex P2 retained | 0 |

### Iteration 2 (Grade: C → A)

The four counted P1 findings were fixed. Durable assessment payloads are validated before status reads; an accepted reviewed ledger may grow by appended records and enroll an acknowledged later start even before the first reconcile; timestamp acknowledgments compare instants; and copied secrets receive shared Git exclusion before copying, with landing blocked while a copy-pending marker remains. The same source-consistency batch fixed the accepted Codex P1: a committed member's first-start change now reports `source_conflict` and cannot preserve a passed outcome.

The focused trial and worktree suites, full pytest suite (9,370 passed, 100 skipped, 3 xfailed), strict mypy (787 files), Ruff, strict machine SPEC, and whitespace checks passed. A separate fault injection left a partial `.env` in a retained worktree after rollback contention: Git still ignored it, the pending marker remained, and landing was rejected. The only changes after the full suite were type annotations in two test helpers; both test files were rerun successfully.

The round changed four files. `review_churn` measured maximum ratio 0.0649 in `intent_trial.py`, below the 0.30 re-review threshold; `review_consensus plan` returned `dispatches: []` and reason `churn 0.06 < 0.30`. All seven lenses remain exercised cumulatively. No repair was reverted. Six P2 findings remain in the record, including two accepted cross-model findings; none is severe. `review_consensus finalize` returned grade **A**, `human_review_needed: false`, with no errors. The next step is the frozen full-scope confirmation pass.

## Frozen confirmation pass 1

The full review span `cdc6a7181c5ffa2e6b350c22077f92055778b87b..fd837a05ec726cf7f4742c1708ec44f6c03ae9ad` was frozen before dispatch. All seven mandatory lenses returned and the coverage CLI reported no missing lens. The pass found three new P1 clusters, so it **failed** and entered its one permitted repair round; the review run remains open.

| Severity | Lens | Finding | Evidence |
|---|---|---|---|
| P1 | functionality | `trial_feedback` event with `id: null` is accepted | Temporary-repository status returned `awaiting_reconciliation` and exposed a null event ID instead of `source_incomplete`. |
| P1 | robustness + concurrency | Parallel secret-copy operations lose shared Git exclusions | Synchronized task creation copied two secrets, but common `info/exclude` retained one and Git exposed the other as untracked. |
| P1 | concurrency | Merge-fence timeout can discard a task's first start | Stage-span append waits five seconds and the preflight caller treats its timeout as nonfatal, while trial discovery requires the first start. |

The tests lens also repeated four nonsevere gaps: partial-secret fault injection, distinct post-crash decision recovery, pre-first-reconcile acknowledged extension, and equivalent timestamp formats. The first and third P1 clusters were directly reproduced; the start-loss path follows the existing timeout and caller behavior and will be exercised during the repair. No cross-model voter was re-invoked.

### Confirmation repair

The one permitted repair round resolved the three P1 clusters without changing the approved trial's decisions. Evidence event IDs must be nonempty strings; malformed IDs now make source status `source_incomplete`. Shared Git exclusion entries are read and published under the merge fence before secrets are copied; each copied path is checked as ignored before the pending marker is removed. For an attributable task start, a failed stage-span append now fails preflight with an explicit retry instruction, so a stage cannot silently proceed without its first-start evidence. Non-task telemetry retains its warning-only behavior.

Focused trial, worktree, preflight, and stage-span tests passed. Manual reproductions confirmed the null-ID rejection, blocked preflight followed by a successful recorded retry, and preservation of both exclusion entries under synchronized parallel task creation. The post-repair non-advisory full suite passed: 9,369 passed, 100 skipped, 3 xfailed. Strict mypy, Ruff, machine SPEC, and whitespace checks passed. This repair now proceeds to the second and final frozen confirmation pass.

## Frozen confirmation pass 2 and terminal result

The full repaired span `cdc6a7181c5ffa2e6b350c22077f92055778b87b..987b74a7dfaeb576c8800d2fba5ea83721e06148` exercised all seven mandatory lenses with no coverage blocker. One new P1 prevents approval: after a user-approved source review resolves equal-time tasks as `[b, a]` and reconciliation commits that cohort, adding an acknowledged later task `c` changes inventory; `_reviewed_order` drops the approved tie order, and status compares `[a, b, c]` against `[b, a]`, returning `order_conflict`. The core reviewer reproduced this in a temporary repository. The repair needed is to preserve the approved prefix when reviewed sources are unchanged or append-only and the new start is acknowledged.

The pass also found a P2 malformed `legacy_snapshot.members` crash and three P2 test-oracle gaps (partial secret copy, failed start-log append/retry, null event ID). Security and concurrency returned no new findings. This second confirmation is stage-terminal under the two-pass bound: **CHANGES_REQUESTED**, `human_review_needed: true`. The provisional round-2 A never became approval. No commit or task landing occurred. The next action is a fresh repair and review run for the tie-order defect; the P2 gaps remain visible.

## Review iteration summary

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 | C | — | four counted P1 and accepted manual-only P1 | — |
| 2 | A provisional | four counted P1 plus the corroborated manual-only P1 | six P2 | 0 |
| Confirmation 1 | failed | one permitted repair of three P1 clusters | — | three P1 clusters |
| Confirmation 2 | terminal failure | — | one new P1 and P2 gaps | one P1 |

Final grade: A provisional; final status: CHANGES_REQUESTED. Iterations used: 2 / 3. Exit reason: confirmation-2-new-severe. Unreviewed fixes: five before confirmation; regression-attributed: 0; attribution unknown: 0.

## Size and complexity (round 2 repair)

| File | LOC | Cyclomatic | Max nesting | Status |
|---|---|---|---|---|
| `src/harness_maker/intent_trial.py` | 1,317 → 1,372 | 384 → 407 | 10 → 11 | measured |
| `src/harness_maker/worktree.py` | 6,268 → 6,282 | 796 → 798 | 7 → 7 | measured |
| `tests/integration/test_intent_trial_concurrency.py` | 523 → 526 | 97 → 97 | 3 → 3 | measured |
| `tests/unit/test_worktree_task_lifecycle.py` | 240 → 243 | 39 → 39 | 1 → 1 | measured |
