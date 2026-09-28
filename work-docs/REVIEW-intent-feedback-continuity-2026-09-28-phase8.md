---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-09-28
run_id: 70de46f08f61
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
  computed_at: 2026-09-28T16:00:00Z
---

# Intent feedback continuity: review after Phase 8

Third review today (after runs `01263f044f17` and `4ddd6e47b02f`). Span `9f60e97d..working tree`.

## 🎯 Round 1 Summary

`review_consensus finalize`: **A** — no consensus P0/P1, five P2. All seven lenses exercised.
Codex invoked once; PIDA accepted two P1s (one reproduced) and left one P2 unresolved. They are
single-voice `manual-only`, so `human_review_needed: true`. The user chose to close this review
and fix the two accepted P1s in Phase 9 before a confirmation pass (none ran here:
`confirm_pass_ran: false`).

Pass 2 dropped: security P2 on the self-asserted `actor` (third time; accepted limitation);
concurrency P1 "status() should take a shared lock" (contradicts ADR-003/006 decided today, and
the O_EXCL fallback has no shared mode). Demoted: core P0 exit code → P2 (not in the SPEC
contract; the shipped workflow reads JSON `reason`/`action`); tests P1 ×2 → P2 (same standing
disposition as the first run today).

## 🔍 Drift Findings

None. Intent drift: none.

## ✅ Consensus Findings

| id | Sev | Lens | Location | Finding |
|---|---|---|---|---|
| `4e26d7b7ced0c1f1` | P2 | consistency | `src/harness_maker/intent_cli.py:92` | Trial CLI exit code comes from a reason denylist, not `changed`/`failed`; exit 0 on unwritten outcomes. |
| `ba5e22bf02e8fb79` | P2 | design | `src/harness_maker/intent_trial.py:598` | Four helpers re-derive the latest accepted source_review. |
| `4fd1a4aeb062a73e` | P2 | tests | `tests/unit/test_intent_trial.py:1320` | Golden observables compare `reason` to strings never emitted. |
| `d5ea5b24a23c6168` | P2 | tests | `tests/unit/test_intent_trial.py:1343` | Golden observables read keys never emitted. |
| `52ef297a9ea3b1dd` | P2 | concurrency | `src/harness_maker/stage_spans.py:144` | Every span append takes the merge fence, including non-trial projects. |

## 📝 Manual-Only Findings

| id | Sev | Source | Location | Finding |
|---|---|---|---|---|
| `3a82fb47025eba3b` | P1 | codex, PIDA accepted | `src/harness_maker/intent_trial.py:924` | On `lock_busy`/`unsupported_lock`, `status()` returns `_blocked`, which re-reads trial and sources without the lock — the fenced read ADR-006 promises is bypassed on exactly the contention path. |
| `37294c7dfda5af64` | P1 | codex, PIDA accepted, reproduced | `src/harness_maker/intent_trial.py:893` | A working-copy PLAN whose committed active-trial marker was removed (no legacy body) reports `no_trial`/`none` from status and record_decision, while `active_trials` and `protected_trial_paths` list it as active. |

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `3a82fb47025eba3b` | codex | P1 | src/harness_maker/intent_trial.py | 924 | Lock-failure status response re-reads unfenced | `return _blocked(base, roots, trial_id, str(exc))` | false | accepted | PLAN:114-115 promises no unfenced read; _blocked runs _read without the lock. | pending | — |
| `f2b7e93a1462b429` | codex | P2 | src/harness_maker/intent_trial.py | 920 | status() does not re-discover roots after acquiring the lock | `_roots` before `_writer` | false | unresolved | Race not reproduced; reconcile rechecks. | pending | — |
| `37294c7dfda5af64` | codex | P1 | src/harness_maker/intent_trial.py | 893 | Marker-removed committed trial reads as absent | `if trial is None:` returns `_status` with no HEAD check | false | accepted | Repro: no_trial/none while active_trials lists it. | pending | — |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 5 P2 + manual-only 2 P1, 1 P2 | — |

Final grade: A provisional (not approved)
Iterations used: 1 / 3
Exit reason: closed by user decision to fix the accepted manual-only P1s first
Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0
