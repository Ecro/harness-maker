---
type: review
task_slug: intent-surface-diet
status: APPROVED
created: 2026-10-04
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: eb42122723d1
review_base: c0285d7a204c082d3972700c253b68fdb7b52c7d
drift_verdict:
  result: scope_violation
  scope_violations: [CLAUDE.md, TECH_SPEC.md, docs/HOW-IT-WORKS.md, docs/HOW-IT-WORKS.ko.md, tests/unit/test_intent_layer_diet.py, specs/SPEC-intent-layer-diet.machine.yaml, specs/SPEC-intent-layer-improvements.machine.yaml]
  scenario_misses: []
  task_slug: intent-surface-diet
  computed_at: 2026-10-04T10:30:00Z
---

# REVIEW — intent-surface-diet

## Final verdict: APPROVED (grade A)

Round 2 reached grade A, and the confirmation pass (confirm-1) found zero new consensus-passed P0/P1, so the review is approved.
- Coverage: all 7 lenses exercised, `blocks_approval: false`.
- Carried (non-blocking): 4 P2 and 6 P3, listed under "Confirmation pass" below.

## 🎯 Round 1 Summary

- **Grade B** (1 consensus-passed P1, 7 P2, 2 P3; 3 codex findings PIDA-accepted, `manual-only`;
  1 codex finding `unresolved`).
- Coverage: all 7 lenses, `blocks_approval: false`.
- Pass 2 was dispatched for core and tests only. Security had zero findings and concurrency
  only a P3; their Pass 1 results stand.

## 🔍 Drift Findings

`scope_violation` (informational, P1 by rule). The files below fall outside the PLAN phase
scopes. Each is required by the change or by a rule:
- `CLAUDE.md` holds the registry's unsourced count (33 → 32).
- `TECH_SPEC.md` and `docs/HOW-IT-WORKS*.md` must match shipped behaviour (intent.yaml rule).
- `tests/unit/test_intent_layer_diet.py` lost a one-shot snapshot-pin guard that blocked
  legitimate regeneration.
- The two landed machine SPECs had dead `test_ids` pruned (round 2 Fix #1).

These are recorded in the PLAN phase-status table. No scenario is uncovered.

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Finding | Disposition |
|---|---|---|---|---|
| e6e55fbe5e140849 | P1 | consistency | Landed machine SPECs listed retired test ids in `test_ids[]` | accepted, fixed r2 (Fix #1): `test_ids: []` + `pending_test: true` (tooling fields only; both approvals re-checked valid) |
| e9f17bbb90feadeb | P2 | functionality | Deferred 5.7 items "stay pending" with no row; SPEC/RESEARCH source rows marked only in the PLAN | accepted, fixed r2 (Fix #2) |
| 8979e1e152a731b0 | P2 | functionality | Empty-list path skips the readback the close question requires (compression dropped the clause) | accepted, fixed r2 (Fix #3) |
| 747e6d68b1078a22 | P2 | tests | No test pinned spec 0.5's `hm intent status --json` read | accepted, fixed r2 (Fix #4) |
| 2ffe796dc68e26ba | P2 | tests | AC-001 checked marker comments only | accepted, fixed r2 (Fix #5: `no_collection_prose`) |
| b59f7c28a4827b7a | P2 | tests | S33_CONTRACT omitted the drift criteria; synthetic control | accepted, fixed r2 (Fix #6: criteria tokens + real-render deletion loop) |
| 53cf9637b0354b60 | P2 | tests | S33_CONTRACT lacked `file` = the PLAN, never edit the record, intent trigger, skip lines | accepted, fixed r2 (Fix #6) |
| 25884309654a6994 | P2 | tests | 5.7 skip/failed-once rules unpinned | accepted, fixed r2 (Fix #7: `S57_RULES` + controls) |
| 44d10bae33c038a7 | P3 | tests | AC-008 phrase has no position/control | accepted, carried |
| b9a1b8da4b93e74a | P3 | concurrency | `@cache _root()` mkdtemp render never removed | accepted, carried (same pattern as existing render tests) |

**Deviation from the auto-fix policy (recorded):** the loop selects only P0/P1 at grade B. The
seven P2s were applied in the same round anyway. Two were behaviour regressions this task
introduced (the empty-list readback, and source rows never updated). The other five
strengthened oracles cheaply. The P3s were not applied.

Dropped in Pass 2: the core P3 "scan for pending rows no stage writes" (deliberate under S3),
and the core P3 "withdrawal 'no fired revisit'". The CLI computes candidates from fired
revisits (`world.py:1028,1151-1209`), so that text is true.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Finding | Status |
|---|---|---|---|---|
| aeca8f3216f89248 | P2 | codex | SPEC/RESEARCH source rows stay `pending` after processing | resolved by Fix #2 |
| 92256a2c9eaaee85 | P3 | codex | Empty-batch path conflicts with the close readback | resolved by Fix #3 |
| c6252f79c08f586c | P2 | codex | 3.3 test misses the judgment rules | resolved by Fix #6 |

## 🤝 Disagreements

The empty-list readback: codex P3 vs core P2. Kept independent.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| aeca8f3216f89248 | codex | P2 | src/harness_maker/templates/stages/wrapup.md.j2 | 593 | Existing SPEC/RESEARCH rows' dispositions not updated | — | false | accepted | :579 collects SPEC/RESEARCH rows; :593 marked only the PLAN | resolved | — |
| f2bc8206d1166c3d | codex | P2 | src/harness_maker/templates/stages/wrapup.md.j2 | 592 | Deferred items beyond 16 not persisted on Claude | — | false | unresolved | rowless derived items re-derivable; loss unproven | resolved | — |
| 92256a2c9eaaee85 | codex | P3 | src/harness_maker/templates/stages/wrapup.md.j2 | 590 | Empty-batch path conflicts with close readback | — | false | accepted | dropped 'Step 1 read is the readback' clause | resolved | — |
| c6252f79c08f586c | codex | P2 | tests/unit/test_intent_surface_diet.py | 285 | 3.3 preservation test misses judgment rules | — | false | accepted | S33_CONTRACT lacked scope/out_of_scope/statement etc. | resolved | — |

### Iteration 2 (Grade: B → A)
Fixes applied: 7 (+ re-freeze)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | prune retired test ids in landed machine SPECs | specs/SPEC-intent-layer-diet.machine.yaml, specs/SPEC-intent-layer-improvements.machine.yaml | Applied · caused_by=none |
| 2 | P2 | deferred wording + source-row marking | src/harness_maker/templates/stages/wrapup.md.j2 | Applied · caused_by=none |
| 3 | P2 | restore empty-list readback clause | src/harness_maker/templates/stages/wrapup.md.j2 | Applied · caused_by=none |
| 4 | P2 | pin spec 0.5 status read per target | tests/unit/test_intent_surface_diet.py | Applied · caused_by=none |
| 5 | P2 | collection-prose check on non-wrapup stages | tests/unit/test_intent_surface_diet.py | Applied · caused_by=none |
| 6 | P2 | S33 contract tokens + real-render deletion loop | tests/unit/test_intent_surface_diet.py | Applied · caused_by=none |
| 7 | P2 | S57 rule regexes + controls | tests/unit/test_intent_surface_diet.py | Applied · caused_by=none |

Re-freeze after Fix #2/#3: surface baseline (wrapup +181 / hm-wrapup +125), snapshots,
autopilot gate golden (wrapup only), BASELINE-DELTA rows updated.
Targeted verification: 969 passed, 19 skipped.
Remaining: 2 (P3) | New issues introduced: 0 (re-review: one `code-reviewer` functionality dispatch, no findings)
Churn: 0.341 (max: work-docs/BASELINE-DELTA-intent-surface-diet.md, measured 12, excluded 0)

## ✔️ Confirmation pass (confirm-1)

The pass was frozen at `8f5dc541`, with span `c0285d7a..8f5dc541`. All 4 dispatches returned and every lens was exercised. It found **0 new P0/P1**.

| Sev | Lens | Finding | Disposition |
|---|---|---|---|
| P2 | functionality | 5.7 step 5 "in that table too" is ambiguous: a reader may not know to mark the SPEC/RESEARCH source row in its own table | carried. Follow-up: reword to "in its own table" and re-pin S57_RULES (one-word fix; it moves the wrapup surface by about 3 chars, so it is left out of this frozen diff) |
| P2 | consistency (+ tests P3) | Retired ACs in landed SPECs are recorded as `pending_test: true` / `test_ids: []`, which says a test is still owed | carried. `find_unbound_closed_type_acs` is per-yaml and safe-skips ACs with no collectable test (`spec_machine.py:957`), so this produces no false gate failure. The schema has no `superseded` state, and adding one is a schema change outside this task |
| P3 | security | 5.7/close ids reach the shell line with no `[A-Z0-9-]+` check | pre-existing; carried as a hardening follow-up |
| P3 | consistency | intent-layer skill does not say it is now the only creation path | carried |
| P3 | concurrency | SPEC/RESEARCH source-row marks have no re-read-before-edit rule | carried (per-task worktree squash surfaces conflicts at land) |
| P3 | concurrency | `@cache _root()` mkdtemp never removed | carried (same as round 1) |
| P3 | tests | AC-008 phrase / absent-table clause lack a deletion control and a placement check | carried (same as round 1) |

## 📊 Summary

- Rounds: 2, plus 1 confirmation pass. Grade B → A.
- Fixes applied: 7 (1 P1 + 6 P2). The P2 fixes are a recorded policy deviation.
- Review run `eb42122723d1` closed with outcome APPROVED. Freeze refs were reaped.
