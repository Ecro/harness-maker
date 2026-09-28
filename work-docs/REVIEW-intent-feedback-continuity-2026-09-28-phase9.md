---
type: review
task_slug: intent-feedback-continuity
status: APPROVED
human_review_needed: true
created: 2026-09-28
run_id: 62a89be1c890
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
  computed_at: 2026-09-29T00:30:00Z
---

# Intent feedback continuity: review after Phase 9

Fourth review of the day (runs `01263f044f17`, `4ddd6e47b02f`, `70de46f08f61` before it). Span
`9f60e97d..working tree`, the whole task.

## 🎯 Round 1 Summary

`review_consensus finalize`: **D** — consensus P0 `1819a48232d794ce`, P1 `6be634cd45dd2470`, two P2.
All seven lenses exercised. Codex invoked once; PIDA accepted three (P1 `03719f0a80a0ba00`, P2
`5a9dd18190ee4337`, P2 `ef978c86c9941057`) and left `ba266b55f2cdbb81` unresolved.

Pass 2 dropped: core exit-code P1 (duplicate of the standing P2; the SPEC contract defines no exit
code and the shipped workflow reads JSON); security `actor` P2 (accepted limitation); tests
native-evidence P2 (duplicate of the standing EDGE-fixture P2). Demoted: security secret-copy
P1 → P2 (exclusion written before the copy; landing blocked while copy_pending exists).

## 🔍 Drift Findings

None. Intent drift: none.

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Location | Finding | Status |
|---|---|---|---|---|---|
| `1819a48232d794ce` | P0 | concurrency | `src/harness_maker/worktree.py:3993` | `post-commit-pop` restored a deferred stash with no trial-protection check, unlike the other two restore sites; a trial activated between a legacy finalize and a later wrapup could have its PLAN overwritten. | resolved (round 2) |
| `6be634cd45dd2470` | P1 | concurrency | `src/harness_maker/worktree.py:924` | `_fenced_restore_base_dirty` re-checked trial protection only on fence timeout, not after a successful wait. | resolved (round 2) |
| `f6517f08d931b7e7` | P2 | security | `src/harness_maker/worktree.py:4936` | A copied secret that git would not ignore stayed on disk on the reused-worktree path. | resolved (round 2) |
| `dd31bc466412dbdf` | P2 | tests | `tests/unit/test_intent_trial.py:991` | The status lock-failure test used the SUT's `_ACTION` as its own oracle. | resolved (round 2) |

## 📝 Manual-Only Findings

| id | Sev | Source | Location | Finding | Status |
|---|---|---|---|---|---|
| `03719f0a80a0ba00` | P1 | codex, PIDA accepted | `src/harness_maker/intent_trial.py:1129` | `_publish` never compared the destination with the bytes `_read` returned, so an unfenced edit between read and publish was silently overwritten. | resolved (round 3, user-approved repair of a manual-only finding) |
| `5a9dd18190ee4337` | P2 | codex, PIDA accepted | `src/harness_maker/intent_trial.py:1171` | reconcile/record_decision lock-failure paths still read sources unfenced via `_blocked`. | open |
| `ef978c86c9941057` | P2 | codex, PIDA accepted | `tests/unit/test_intent_trial.py:1391` | Golden observables compare against never-emitted values (standing P2). | open |
| (not stamped) | P1 | consistency (confirm-1) | `src/harness_maker/command_registry.py:59` | See confirmation pass 1 — oracle-blocked. | unresolved |

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `03719f0a80a0ba00` | codex | P1 | src/harness_maker/intent_trial.py | 1129 | Publication can overwrite a concurrent edit | `current = path.read_bytes()` compared only with HEAD | false | accepted | _publish never compared current bytes with _read's content. | resolved | — |
| `5a9dd18190ee4337` | codex | P2 | src/harness_maker/intent_trial.py | 1171 | Write-path lock failures read unfenced | `_blocked` → `_read` | false | accepted | lock_busy paths call _blocked, which runs _read unfenced. | pending | — |
| `ba266b55f2cdbb81` | codex | P2 | src/harness_maker/intent_trial.py | 932 | Status roots computed before the lock | `_roots` before `_writer` | false | unresolved | Worktree creation does not take the lock; harm unclear. | pending | — |
| `ef978c86c9941057` | codex | P2 | tests/unit/test_intent_trial.py | 1391 | Vacuous golden projections | never-emitted reason strings | false | accepted | 0 grep hits for the compared strings. | pending | — |

### Iteration 2 (Grade: D → A)
Fixes applied: 4

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P0 | post-commit-pop refuses a stash that holds a protected trial path (stash and ref kept, rc 1) | `src/harness_maker/worktree.py` | Applied · caused_by=none |
| 2 | P1 | fenced restore re-checks protection inside the fence | `src/harness_maker/worktree.py` | Applied · caused_by=none |
| 3 | P2 | unignored secret copy unlinked before the error | `src/harness_maker/worktree.py` | Applied · caused_by=none |
| 4 | P2 | lock-failure test hardcodes action strings | `tests/unit/test_intent_trial.py` | Applied · caused_by=none |

Tests: `tests/integration/test_intent_trial_concurrency.py::test_s2_post_commit_pop_never_restores_over_a_trial_activated_since_the_stash`, `::test_s2_fenced_restore_rechecks_trial_protection_after_a_successful_wait`, `::test_s2_unignored_secret_copy_is_removed_before_the_error` — all three RED with their fixes removed. Verification: ruff, format, mypy --strict; 282 targeted tests passed.
Remaining: 3 manual-only | New issues introduced: 0
Churn: 0.119 (max: tests/integration/test_intent_trial_concurrency.py, measured 3, excluded 0)
rereview: skipped — churn 0.12 < 0.30

### Iteration 3 (Grade: A → A)
Fixes applied: 1 (manual-only finding, repaired on the user's explicit decision)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `_publish(…, read)` refuses when the destination changed after `_read`; callers pass `content` | `src/harness_maker/intent_trial.py` | Applied · caused_by=none |

Test: `tests/unit/test_intent_trial.py::test_s2_edit_between_read_and_publish_is_not_overwritten[record_decision|reconcile]` — RED with the check removed (edit overwritten, `changed: true`). Verification: ruff, format, mypy --strict; 177 targeted tests passed.
Churn: 0.018 (max: tests/unit/test_intent_trial.py) · rereview: skipped — churn 0.02 < 0.30
After this round `human_review_needed` was false.

## Confirmation pass 1 (freeze `02b165ad`, span `9f60e97d..02b165ad`) — terminal

All seven lenses exercised. Security, concurrency and tests: nothing new; each judged this
review's fixes sound (post-commit-pop guard, in-fence re-check, secret unlink, publish revalidation,
no nested lock acquisition). One new finding:

| Sev | Lens | Location | Finding | Disposition |
|---|---|---|---|---|
| P1 | consistency | `src/harness_maker/command_registry.py:59` | The `intent` registry lists `reconcile`/`record-decision` as top-level subcommands although they are nested under `trial`; `misroute_guard` therefore steps aside for `intent reconcile` instead of redirecting to `stage_agent_ledger reconcile`. | **unresolved / oracle-blocked.** `tests/unit/test_command_surface_gate.py::test_tc2_subparser_registry_matches_source_bidirectionally` pins the registry to equal every `add_parser` literal in the module, flattened — the existing `intent` entry already lists nested `add`/`observe`/`resolve`/`record`/`measure`/`approve`… the same way. Removing the two entries would fail that gate. Whether the registry should model nesting at all is a pre-existing design question for a separate task. Retagged manual-only; it sets `human_review_needed`. |

No new consensus P0/P1 → **APPROVED**; `human_review_needed: true` for the oracle-blocked P1.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | P0 1, P1 1, P2 2 + manual-only P1 1, P2 2 | — |
| 2         | A     | 4             | manual-only P1 1, P2 2 | 0 |
| 3         | A     | 1             | manual-only P2 2 | 0 |
| Confirm 1 | clean | —             | — | 1 P1 oracle-blocked |

Final grade: A
Iterations used: 3 / 3
Exit reason: converged
Status: APPROVED
human_review_needed: true
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

### For human review before wrapup

1. The oracle-blocked registry P1 above (design question about flattened nested verbs).
2. Open P2s carried to a follow-up: write-path `_blocked` unfenced reads; exit code vs `changed`; `_writer` fence reuse; stash-scan caching; second in-lock snapshot; span fence for non-trial projects; dead golden observables; EDGE fixture hash; status roots before the lock (unresolved).

## 📏 Size & Complexity

Round 2: `src/harness_maker/worktree.py`, `tests/integration/test_intent_trial_concurrency.py` (+≈100 test lines). Round 3: `src/harness_maker/intent_trial.py` (+4), `tests/unit/test_intent_trial.py` (+≈30).
