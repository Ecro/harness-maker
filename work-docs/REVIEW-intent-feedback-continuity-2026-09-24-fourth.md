---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
created: 2026-09-24
run_id: b6d189f3ecaf
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-feedback-continuity
  computed_at: 2026-09-24T02:25:00Z
---

# Intent feedback continuity: fourth independent review

## Round 1 summary

Grade **C** from `review_consensus finalize`: four counted P1 findings, no coverage blocker, all seven mandatory lenses exercised. The diff remains within PLAN Phases 1–4 and the approved SPEC. The task and live trial remain uncommitted; no user assessment or intent closure was inferred.

## Consensus findings

| ID | Severity | Location | Finding |
|---|---|---|---|
| `5b48b9319c14a566` | P1 | `intent_trial.py:868` | Deleting a committed active PLAN removes it from current-file discovery and landing protection. Core, security and Codex aligned. |
| `cba2e3e542bf9cbf` | P1 | `intent_trial.py:716` | Equivalent timestamps in different offsets bypass the ambiguous-start guard. Core independently reproduced the Codex finding. |
| `32e74d278060d785` | P1 | `intent_trial.py:1138` | Decision writer uses a worktree list captured before its fence, allowing a newly registered source to be omitted. |
| `a12ae27f45961801` | P1 | `worktree.py:498` | A sibling fence timeout bypasses multi-repo create rollback and removes its reservation. |
| `fd8a4dd44a938143` | P2 | `test_intent_trial_concurrency.py:113` | Crash-recovery oracle accepts follow-up errors other than lock_busy. |

## Manual-only findings

Codex P2 `123f6d6e94c7535b` reports that `reconcile --dry-run` returns current status without a proposed mutation preview. It is accepted by PIDA but has no reviewer-lens corroboration and does not lower the letter. Codex P1 `0147c2fa39cca22e` was rejected against SPEC AC-005: unrelated post-commit artifact drift does not automatically revoke an already committed completed cohort.

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
      "id": "7270f001545fe9d7",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 878,
      "summary": "Deleted committed active PLAN escapes protection",
      "evidence": "active_trials scans current files only",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "Current-file glob omits deleted active PLAN",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "0147c2fa39cca22e",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 733,
      "summary": "Completed cohort bypasses later source drift",
      "evidence": "_coverage and _status diverge after post-commit artifact edit",
      "needs_relaxation": false,
      "disposition": "rejected",
      "oracle_result": "SPEC AC-005 limits invalidation to affected provisional coverage",
      "status": "pending",
      "invalidation_reason": null
    },
    {
      "id": "4e7589263625426f",
      "source": "codex",
      "severity": "P1",
      "file": "src/harness_maker/intent_trial.py",
      "line": 716,
      "summary": "Equivalent timestamps escape tie detection",
      "evidence": "Same instant in different offsets bypasses raw-string tie guard",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "_iso sort and raw-string tie check disagree",
      "status": "resolved",
      "invalidation_reason": null
    },
    {
      "id": "123f6d6e94c7535b",
      "source": "codex",
      "severity": "P2",
      "file": "src/harness_maker/intent_trial.py",
      "line": 1191,
      "summary": "Dry-run omits proposed mutation preview",
      "evidence": "dry_run returns status only",
      "needs_relaxation": false,
      "disposition": "accepted",
      "oracle_result": "SPEC requests proposed mechanical diff",
      "status": "pending",
      "invalidation_reason": null
    }
  ]
}
```

## Review iteration summary

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 | C | — | four P1 | — |
| 2 | A provisional | four P1 repairs plus wrong-oracle correction | 0 counted P1; two P2 retained | 0 |

## Round 2 repair

The four counted P1s were repaired. Deleted committed trial PLANs are detected from the HEAD-to-working-tree deletion set and surface `source_conflict`; equivalent timestamp instants now trigger `order_conflict`; `record_decision` checks registered roots again under its writer fence; and multi-repo create rolls back on fence timeouts, retaining its reservation plus a diagnostic if rollback itself cannot finish. The existing no-trial unit/golden fixtures had represented an uncommitted deletion of an active trial. A test-lens P1 confirmed that oracle error; the fixtures now create a genuinely absent HEAD state, while a new test checks deletion conflict and immutable committed content. Targeted tests passed after this correction, along with manual deleted-trial, timezone-tie, worktree-race and timeout-rollback scenarios. Ruff, mypy, machine SPEC validation and whitespace checks passed.

The measured repair churn is 0.0381 over three files. The CLI returned `churn 0.04 < 0.30`, so selective re-review was skipped and all four applied fixes count as unreviewed until the mandatory whole-diff confirmation. Round 2 provisional grade A is the CLI result after pending→resolved transitions. P2 findings remain: the writer-kill test's weak recovery oracle and Codex's dry-run preview gap.

## Whole-diff confirmation 1

All seven mandatory lenses ran against the frozen full diff and coverage passed. This confirmation found two new P1s: malformed persisted `source_review` fields could raise from `status`, and an include-copy failure followed by a task-create rollback fence timeout could leave an unclaimed worktree. The tests lens retained the weak writer-recovery oracle and noted that two repaired races lack deterministic automated tests (P2). Confirmation 1 therefore failed; its ledger episode was recorded without closing the review run.

One confirmation repair extracted a shared source-review payload validator used for both new decisions and persisted records. Malformed inventory entries, task lists and `through` timestamps now return `source_incomplete`. Task creation now preserves its registry claim and prints the recovery path when fenced rollback cannot finish; it releases the claim only after the worktree is absent. Targeted tests, Ruff and mypy passed. Manual temporary-repository checks exercised three malformed payload shapes and a timed-out rollback followed by successful reattachment. The complete non-advisory suite passed before this repair; confirmation 2 follows the repair and targeted validation.

## Whole-diff confirmation 2 and terminal result

Coverage again exercised all seven mandatory lenses. Three new P1s prevent approval:

| Lens | Location | Finding |
|---|---|---|
| Robustness | `worktree.py:4882` | Retrying a task creation after an include-copy failure and timed-out rollback returns success while skipping the include copy. Reproduced in a temporary repository. |
| Concurrency | `worktree.py:3644` | Finalize reads protected trial paths before acquiring its merge fence; a task landing during the wait can make that set stale. |
| Tests | `test_intent_trial.py:388` | The malformed-record oracle omits a `source_review` decision with no `payload`; public `status()` raises `KeyError` on that input. Reproduced in a temporary repository. |

Security returned no new findings. Confirmation 2 exhausted this review run's confirmation budget, so the outcome is **CHANGES_REQUESTED** with human review needed. The provisional round-2 A did not become an approval. Both confirmation episodes were recorded; the review run was closed and its freeze refs reaped. No commit or task landing occurred. The P2 writer-recovery oracle and dry-run preview gap remain open.
