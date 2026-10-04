---
type: review
task_slug: wrapup-intent-hardening
status: APPROVED
created: 2026-10-04
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 19f73a45698c
review_base: f57cef3b5585ad07464bb687acfe507bd7bf461d
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: wrapup-intent-hardening
  computed_at: 2026-10-04T11:05:00Z
---

# REVIEW — wrapup-intent-hardening

## Final verdict: APPROVED (grade A)

Rounds 1 and 2 both graded A. The confirmation pass (confirm-1) found 0 new P0/P1, and all 7 lenses were exercised, so `blocks_approval: false`. `human_review_needed: false`.

## 🎯 Round 1 Summary

- **Grade A.** 0 P0, 0 P1, 8 P2, 4 P3. All findings are `consensus-passed` single-lens voices. Codex was invoked and returned 0 findings, so no PIDA input.
- Coverage: all 7 lenses exercised, `blocks_approval: false`.
- **Base correction (recorded):** `hm freeze resolve-base` resolved `b371c564` (HEAD~1) because the task branch has no commits yet. Left as is, the span would have pulled the previous task's commit `f57cef3b` into this review. The ref was moved to the true base `f57cef3b` with `git update-ref`, guarded by the old value.
- **Pass 2 not dispatched (recorded deviation):** every Pass 1 finding was P2/P3, and Pass 2 can only drop findings or re-grade them. The confirmation pass re-sweeps all 7 lenses over the final artifact.
- **Policy deviation (user decision):** the grade cleared at A, where auto-fix selects nothing. The user chose to fix the core P2s now rather than carry them, because three of them sit on the very seam this task closes.

## 🔍 Drift Findings

`clean`. Every changed file is inside a PLAN phase scope, and the task artifacts (SPEC, PLAN, BASELINE-DELTA) are task-owned. `tests/unit/test_intent_surface_diet.py` is in Phase 2 scope; its `S57_RULES` entry was retargeted.

## ✅ Consensus Findings (round 1)

| id | Sev | Lens | Finding | Disposition |
|---|---|---|---|---|
| b14672d1f0b03f4e | P2 | consistency | Close paragraph lost its predicate, so the skip line's gating is ambiguous (absent-case) | accepted, fixed r2 |
| 13dfd3c43a78647d | P2 | consistency | Re-offer rule stated twice; `<item>` undefined and can leak a value | accepted, fixed r2 |
| 89eebe5edccfd8fc | P2 | security | Intent id `[A-Z0-9-]+` admits a leading dash, so it can be read as an option | accepted, fixed r2 (`[A-Z0-9][A-Z0-9-]*`) |
| f2bb8a6829a5ccd7 | P3 | robustness | Option-shaped tokens pass (`--`, locator starting with `-`) | accepted, fixed r2 (same change, plus the locator's first char) |
| 4c519a0bc72d1d85 | P2 | tests | AC-001 outcome check satisfied by the sentence's old tail | accepted, fixed r2 (60-char window after the phrase plus a clause-deletion control) |
| 7c2a70dcd96012f6 | P2 | tests | AC-003 order vacuous; "after any edit" never asserted | accepted, fixed r2 (`EDIT_CLAUSE` per arm, ordered before the whole-value check, with deletion and swap controls) |
| 63cf894101f1d5de | P3 | tests | AC-004 never asserts "ask nothing" | accepted, fixed r2 ("ask nothing" plus "otherwise" between skip line and question, with controls) |
| ea249543351b400e | P2 | design | The seam is closed by prose the agent self-applies; the lasting fix is to stop composing values onto a shell line | accepted, carried (follow-up: argv-free record or temp-file arguments, a CLI contract change) |
| 0f00b443a314b98e | P2 | consistency | Machine SPEC ACs show `pending_test: true`, and the AC-003 predicate words differ from the loosened test | accepted, carried. Wrapup Step 3.5 binds `test_ids` by design. The AC-003 `executable_predicate` text predates the user's step-5-wide loosening; editing it would invalidate the approval hash |
| 99031332b60fabf2 | P2 | concurrency | `@cache` mkdtemp render roots never removed | accepted, carried (same convention as `test_intent_surface_diet.py`) |
| f5b046b2f255a0e5 | P3 | design | Prose-shape regex pins are brittle | accepted, carried |
| a018ab28415fbe34 | P3 | tests | Enum binding is a proximity heuristic | accepted, carried |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

Leading-dash id: security rated it P2, robustness P3. Different tiers, so they were kept independent. Both were fixed by the same change.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

codex: `status: invoked`, 0 findings. No rows.

### Iteration 2 (Grade: A → A)
Fixes applied: 7 (P2/P3; user-chosen deviation from the P0/P1-only policy)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P2 | Close sentence: restored predicate; skip line under the "Only when" gate | src/harness_maker/templates/stages/wrapup.md.j2 | Applied · caused_by=none |
| 2 | P2 | `<item>` = item kind; malformed clause points at the single re-offer rule | src/harness_maker/templates/stages/wrapup.md.j2 | Applied · caused_by=none |
| 3 | P2 | Intent id `[A-Z0-9][A-Z0-9-]*`; locator path leading char | src/harness_maker/templates/stages/wrapup.md.j2, specs/SPEC-wrapup-intent-hardening.md | Applied · caused_by=none |
| 4 | P3 | (same change as #3) option-shaped tokens | — | Applied · caused_by=none |
| 5 | P2 | AC-001 outcomes bound to the clause after the phrase | tests/unit/test_wrapup_intent_hardening.py | Applied · caused_by=none |
| 6 | P2 | AC-003 `EDIT_CLAUSE` asserted and ordered; deletion/swap controls | tests/unit/test_wrapup_intent_hardening.py | Applied · caused_by=none |
| 7 | P3 | AC-004 "ask nothing" + "otherwise" asserted with controls | tests/unit/test_wrapup_intent_hardening.py | Applied · caused_by=none |

Re-freeze: surface baseline (wrapup +75 / hm-wrapup +75 over round 1), snapshots, gate golden (wrapup only), BASELINE-DELTA updated. Targeted: 119 passed; structural: 919 passed.
Re-review: one `code-reviewer` functionality dispatch (churn 0.50 ≥ 0.30). It confirmed every fix on both arms and found 1 new P2:
- 615c9eaa3e5b4135 (P2, functionality): the machine SPEC `oracle_evidence` still cites `world.py:75 [A-Z0-9-]+`. **Accepted, carried.** It is an authored, hash-bound field, so an edit would void the DRI's approval. The stricter pattern and why it supersedes the citation are recorded in the SPEC.md Refinement Decisions.
Remaining: 6 (4 P2 carried, 2 P3 carried) | New issues introduced: 1 (P2, doc provenance)
Churn: 0.5 (max: work-docs/BASELINE-DELTA-wrapup-intent-hardening.md, measured 10, excluded 0)

## ✔️ Confirmation pass (confirm-1)

The frozen commit is `4e5ea802` and the span is `f57cef3b..4e5ea802`. All 4 dispatches returned. The pass found **0 new P0/P1**. It reported 4 new P3s, all carried:

| Sev | Lens | Finding |
|---|---|---|
| P3 | design | `measure` is listed as an `<item>` kind but cannot be malformed, and the metric/verdict overlap is unspecified |
| P3 | consistency | The test module docstring is multi-paragraph |
| P3 | tests | AC-001 uses a 60-char window rather than the same sentence, and `sentence_with` is now unused |
| P3 | tests | The format patterns are checked anywhere in 5.7 rather than positioned in step 5 |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 12        | —   |
| 2         | A     | 7             | 6         | 1   |

- Final grade: A
- Iterations used: 2 / 3
- Exit reason: converged
- Status: APPROVED
- human_review_needed: false

## 📏 Size & Complexity

No Python source changed; every changed file is `not-python` (template, SPEC, snapshots, goldens) or a test. `wrapup.md.j2` stayed at 889 lines through round 2 (the edits were inside existing lines).

### Carried follow-ups

- **ea249543 (P2):** remove the shell seam by construction, through an argv-free record or temp-file arguments. This is a CLI contract change.
- **615c9eaa (P2):** the machine SPEC `oracle_evidence` cites `world.py:75`, but the pattern is now stricter. The field is hash-bound, so fix it the next time this SPEC is re-approved.
- **0f00b443 (P2):** the AC-003 `executable_predicate` words predate the step-5-wide loosening. `test_ids` are bound at wrapup Step 3.5.
- **99031332 (P2):** the `mkdtemp` render roots are never cleaned up. This repo-wide test convention also appears in `test_intent_surface_diet.py`.
- The confirm-1 P3s above, plus f5b046b2 and a018ab28.
