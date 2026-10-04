---
type: review
task_slug: spec-ac-superseded
status: APPROVED
created: 2026-10-04
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 7f208579564c
review_base: 575e3b5af83e26af94731ae377a2e141a736157e
drift_verdict:
  result: scope_violation
  scope_violations: [tests/unit/test_spec_approval.py, src/harness_maker/command_registry.py]
  scenario_misses: []
  task_slug: spec-ac-superseded
  computed_at: 2026-10-04T13:50:00Z
---

# REVIEW — spec-ac-superseded

## Final verdict: APPROVED (grade A)

Round 1 graded B (one P1). Round 2 fixed it and graded A. The confirmation pass (confirm-1) found 0 new P0/P1, and all 7 lenses were exercised, so `blocks_approval: false` and `human_review_needed: false`.

## 🎯 Round 1 Summary

- **Grade B.** One consensus-passed P1 (concurrency: `_run_retire` had no error handling for a lock timeout or an unreadable SPEC). Codex was invoked and returned one P2, which PIDA accepted. It stands as a lone cross-model voice, so it is `manual-only`.
- Coverage: all 7 lenses were exercised and `blocks_approval` is false.
- **Base correction (recorded):** `hm freeze resolve-base` returned HEAD~1 (`17693054`) because the task branch has no commits. The ref was moved to the true base `575e3b5a` with `git update-ref`, guarded by the old value. This is the same tooling bug as in wrapup-intent-hardening; it is now `[fail] resolve-base-head-parent-empty-branch` count 3 with a proposal filed.
- **Pass 2 not dispatched (recorded deviation).** The single P1 is a mechanical CLI-wrapper gap, and the confirmation pass re-sweeps the whole span.

## 🔍 Drift Findings

`scope_violation` (informational). Two files sit outside the PLAN phase scopes, and both are required:
- `tests/unit/test_spec_approval.py` enforces a mutation entry and a `_DENY` oracle for every model field. IRR-001 deliberately moves `superseded_by` into the hash denylist.
- `src/harness_maker/command_registry.py`: `test_command_surface_gate` enforces registry↔source parity for the new `retire` subparser.

Both are recorded in the PLAN notes. No scenario is uncovered.

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Finding | Disposition |
|---|---|---|---|---|
| eeadaf762457a328 | P1 | concurrency | `_run_retire` lets the lock-timeout `ApprovalError` (and load/YAML errors) escape as a traceback | accepted, fixed r2 (Fix #1, with test `test_ac002_retire_cli_unreadable_spec_exits_cleanly`) |
| a1985711ce10c5f4 | P2 | security | Same defect as eeadaf (CLI wrapper error handling) | accepted, resolved by Fix #1 |
| 9218e7c9a5388293 | P2 | functionality | `mark-judged` still writes a verdict onto a superseded judgment AC | accepted, carried (no reader consults it; the field is hash-excluded) |
| 860e08b8577304b5 | P2 | security | Same-target re-run no-op returns before the target existence/approval checks, so a hand-written value gets exit 0 | accepted, carried (the file is unchanged; validate still catches a missing target) |
| cc549dbebe954938 | P2 | concurrency | Target approval is read without the target's lock (TOCTOU before the write) | accepted, carried (low probability; IRR-001 already accepts that the target approval is not re-checked) |
| f5b8ec8042a0f737 | P2 | tests | The dangling-target validate error is tested only through `validate(spec_dir=)`; the CLI `validate`/`check --all` wiring is unpinned | accepted, carried |
| 2749080a52c21a96 | P3 | consistency | batch_refiner tests truthiness where other readers use `is not None` | accepted, carried |
| cc2885fc2365b292 | P3 | design | `retire` sits out of order in `__all__` | accepted, carried |
| 50cda03c58bed4c7 | P3 | tests | The spec_drift test pins only coverage_gaps | accepted, carried |
| 94130c77af657b29 | P3 | tests | The other-checkout refusal has not been mutation-checked against `approval_state` precedence | accepted, carried |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Finding | Status |
|---|---|---|---|---|
| 7d13ce3a20c7c196 | P2 | codex | The superseded skip in spec_drift also drops the `missing_oracle_source` advisory. SPEC Outcomes keeps oracle checks for superseded ACs | PIDA accepted; carried (a real SPEC deviation at P2, so it does not lower the grade) |

## 🤝 Disagreements

None.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7d13ce3a20c7c196 | codex | P2 | src/harness_maker/observability/spec_drift.py | 125 | superseded skip drops missing_oracle_source advisory | — | false | accepted | spec_drift.py:125 continue precedes :132 append; SPEC Outcomes keeps oracle checks | pending | — |

### Iteration 2 (Grade: B → A)
Fixes applied: 1
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `_run_retire` catches (ApprovalError, OSError, YAMLError, ValidationError) like `_run_approve`; test added | src/harness_maker/spec_machine.py, tests/unit/test_spec_ac_superseded.py | Applied · caused_by=none |

Remaining: 9 (4 P2, 4 P3 + 1 manual-only P2) | New issues introduced: 0
Churn: 0.015 (max: tests/unit/test_spec_ac_superseded.py, measured 2, excluded 0) — rereview: skipped — churn 0.02 < 0.30

## ✔️ Confirmation pass (confirm-1)

Frozen at `ed8d128a`; span `575e3b5a..ed8d128a`. All four dispatches returned: security 0, concurrency 0, core 1 × P3 and tests 2 × P3. There are **0 new P0/P1**. The three new P3s are carried:

| Sev | Lens | Finding |
|---|---|---|
| P3 | functionality | `retire --clear` re-pends judgment ACs too, which never owed a test. This is cosmetic: the field is hash-excluded and no judgment gate reads it. The round-2 DRI answer was "always re-pend". |
| P3 | tests | The batch_refiner `all_clean` superseded clause has no discriminating test. |
| P3 | tests | The CLI error test exercises only the YAMLError branch, not ApprovalError/OSError. |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 11        | —   |
| 2         | A     | 1             | 9         | 0   |

- Final grade: A
- Iterations used: 2 / 3
- Exit reason: converged
- Status: APPROVED
- human_review_needed: false
- Counters: unreviewed 1 (round 2 re-review skipped by the churn gate; confirm-1 covered it) · prior-fix 0 · unattributed 0

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/spec_machine.py | — | 352 → 353 | 4 → 4 | measured (round 2) |
| tests/unit/test_spec_ac_superseded.py | — | 93 → 95 | 13 → 13 | measured (round 2) |

### Carried follow-ups

- **7d13ce3a (P2, codex, PIDA accepted):** the spec_drift superseded skip also drops `missing_oracle_source`. Move the oracle advisory above the `continue`.
- **9218e7c9 (P2):** `mark-judged` should refuse superseded judgment ACs.
- **860e08b8 (P2):** run the target checks before the same-target no-op.
- **cc549dbe (P2):** the target approval TOCTOU; document it or re-check it after the write.
- **f5b8ec80 (P2):** pin the CLI `validate`/`check --all` dangling-target wiring.
- The P3s listed above and in round 1.
