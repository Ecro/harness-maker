---
type: review
task_slug: intent-feedback-continuity
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-09-28
run_id: 4ddd6e47b02f
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
  computed_at: 2026-09-28T13:10:00Z
---

# Intent feedback continuity: review after Phase 7

Second review today, after Phase 7 fixed the three P1s left by run `01263f044f17`
(REVIEW-intent-feedback-continuity-2026-09-28.md). Span `9f60e97d..working tree` — the whole task.

## 🎯 Round 1 Summary

`review_consensus finalize`: **A** — no consensus P0/P1; four P2 and one P3. All seven lenses
exercised. Codex invoked once; PIDA (on main-loop reproductions — the gatherer has no
`toolchains`) accepted three findings and left one unresolved. The two accepted Codex P1s are
single-voice `manual-only`, so `human_review_needed: true` from round 1.

Pass 2 dropped: design P1 "gate task-start span writes on `active_trials`" (dropped then as a
duplicate of an AC-004 rejection — see confirm-2, where it came back); security P2 on the
`actor == "user"` docstring (the docstring describes a single entry point, not authentication).
Demoted: concurrency P1 → P2 (in-lock revalidation is required by SPEC; only its cost is at
issue); tests P1 → P2 (EDGE fixture behaviours are covered live in unit tests).

## 🔍 Drift Findings

None. Intent drift (`WORLD-INTENT-CLOSED-LOOP`): none.

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Location | Finding |
|---|---|---|---|---|
| `59abac84647df067` | P2 | robustness | `src/harness_maker/intent_trial.py:1018` | `_pending_trial_stash` runs one `git stash show` per stash ref on every `_read`. |
| `d36cef214d0efbf3` | P2 | design | `src/harness_maker/intent_trial.py:1068` | `_writer` hand-rolls the merge fence (also recorded in run `01263f044f17`). |
| `b9437fbb3d512d7a` | P2 | concurrency | `src/harness_maker/intent_trial.py:1370` | Reconcile's required revalidation is a second full `_source_snapshot` under the 5 s lock. |
| `3f8571793484f956` | P2 | tests | `tests/integration/test_intent_trial_native_evidence.py:74` | EDGE native-evidence fixture has no protocol hash binding, unlike CAPTURE. |
| `6206d13060ab4ad4` | P3 | tests | `tests/unit/test_intent_trial.py:733` | Negative reason assertion accepts any other wrong reason. |

## 📝 Manual-Only Findings

| id | Sev | Source | Location | Finding |
|---|---|---|---|---|
| `3e276d7862e4d34c` | P1 | codex, PIDA accepted | `src/harness_maker/intent_trial.py:919` | `status()` reads sources without the merge fence; ADR-003 says trial reads coordinate with it. Race not reproduced; code read confirms. |
| `29bed4fd1b7eb29f` | P1 | codex, PIDA accepted | `src/harness_maker/intent_trial.py:805` | Full-cohort `_status` skips coverage, so rewriting a reviewed observation keeps `passed`. Reproduced. |
| `a896c5186f992501` | P2 | codex, PIDA accepted | `src/harness_maker/intent_trial.py:662` | A same-slug resume after source-review approval but before the first reconcile gives `source_conflict`, cohort `[]` (`_coverage` still requires `later`). Reproduced. |
| `058209f6d232966e` | P2 | codex, PIDA unresolved | `src/harness_maker/intent_trial.py:893` | PLAN with the trial marker removed. Repro with the legacy body kept gives `policy_revision_required`, not the claimed `no_trial`; the no-body case is untested. |

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `3e276d7862e4d34c` | codex | P1 | src/harness_maker/intent_trial.py | 919 | status() reads without the merge fence | `return _read(base, roots, trial_id)[0]` outside `_writer` | false | accepted | ADR-003 trial reads use the fence; status() calls _read without _writer. Race not reproduced. | pending | — |
| `29bed4fd1b7eb29f` | codex | P1 | src/harness_maker/intent_trial.py | 805 | Full cohort skips coverage; changed reviewed evidence keeps passed | coverage only on the not-full-cohort branch | false | accepted | Repro: PLAN-b evidence rewrite keeps pending/passed; :805 skips _coverage. | pending | — |
| `a896c5186f992501` | codex | P2 | src/harness_maker/intent_trial.py | 662 | Resume before first reconcile blocks enrollment | `_coverage` requires `later` | false | accepted | Repro: source_conflict, cohort []. ADR-005 says approved order survives. | pending | — |
| `058209f6d232966e` | codex | P2 | src/harness_maker/intent_trial.py | 893 | Marker-removed PLAN treated as absent | `if trial is None:` returns `_status` without HEAD check | false | unresolved | Legacy-body repro gives policy_revision_required; no-body case untested. | pending | — |

## Confirmation pass 1 (freeze `a900516a`)

All seven lenses exercised; security and tests returned nothing new.

| id | Sev | Lens | Location | Disposition |
|---|---|---|---|---|
| `8c78ec963190ae04` | P1 | functionality | `src/harness_maker/intent_trial.py:1060` | **unresolved / oracle-blocked.** Claims a never-committed trial PLAN (`base_blob == "unverified_preexisting"`, `"untracked"` never written) blocks every `task_land`. The refusal is intended — `_publish` records that it "cannot certify unrelated preexisting dirt" and `test_s2_first_publication_does_not_certify_preexisting_manual_dirt` pins the refusal and its message. A manual commit or discard of the trial file resolves it, so the "deadlock" is refuted. An edit to the message was started before reading that test and reverted; `intent_trial.py` is byte-identical to the pre-repair ref. The dead `"untracked"` sentinel and the message wording remain a P2-grade clarity issue. `finalize` derives tags from voices and still counted it; the retag is recorded here. |
| `b194850341a80fe3` | P1 | concurrency | `src/harness_maker/worktree.py:924` | accepted, **fixed** — `_fenced_restore_base_dirty` reused its pre-fence `trial_stash` after a fence timeout and could restore unfenced over a trial activated during the wait (up to `_FENCE_TIMEOUT`). Now re-checks before the fallback. Test: `tests/integration/test_intent_trial_concurrency.py::test_s2_trial_activated_during_the_fence_wait_blocks_the_unfenced_restore` (RED `(True, '')` without the re-check). |

Repair verification: ruff, format, mypy --strict clean; 184 targeted tests passed. Churn 0.04.

## Confirmation pass 2 (freeze `a7dcfe8b`) — terminal

Security and tests: nothing new. Concurrency confirmed the TOCTOU fix and deadlock-freedom, and
added one P2 (`3cf63f32efb36a21`, `_writer`'s lock-dir resolution omits `_acquire_merge_fence`'s
`is_dir()` fallback — the same family as `d36cef214d0efbf3`). New severe finding:

| id | Sev | Lens | Location | Finding |
|---|---|---|---|---|
| `ea0fee937f2eb240` | P1 | design | `src/harness_maker/worktree.py:5136` | Task-start span writes are fatal and wait up to `_FENCE_TIMEOUT` for **every** task preflight, including projects that never activated a trial; a disk or permission error in `.claude/observability/` now fails every stage start where it used to warn. Suggests gating on `intent_trial.active_trials(base)`. |

This re-raises a finding Pass 2 dropped as an AC-004 duplicate, with a new angle (non-lock
failures in trial-less projects). The Pass 2 drop rested on PLAN text, not an AC. Whether a
trial-less project should pay this cost is a design decision — see "Open before landing".

Stage-terminal under the two-pass bound: **CHANGES_REQUESTED**, `human_review_needed: true`.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 4 P2, 1 P3 + manual-only 2 P1, 2 P2 | — |
| Confirm 1 | dirty | 1 repair (TOCTOU) | — | 1 P1 fixed, 1 P1 oracle-blocked |
| Confirm 2 | dirty | —             | — | 1 P1, 1 P2 |

Final grade: A provisional (never approved)
Iterations used: 1 / 3
Exit reason: confirmation-2-new-severe
Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

### Open before landing

1. `ea0fee937f2eb240` (P1) — decide whether trial-less projects keep fatal, long-waiting task-start span writes, or gate them on an active trial.
2. `29bed4fd1b7eb29f` (P1, reproduced) — a full cohort stops revalidating reviewed evidence.
3. `3e276d7862e4d34c` (P1) — `status()` reads outside the fence (ADR-003 wording says reads coordinate with it).
4. `a896c5186f992501` (P2, reproduced) — resume between approval and first reconcile.
5. `8c78ec963190ae04` — oracle-blocked; clarity only (message, dead sentinel).
6. P2/P3 list above.

## 📏 Size & Complexity

Confirm-1 repair: `src/harness_maker/worktree.py` +2 lines; `tests/integration/test_intent_trial_concurrency.py` +24 lines.
