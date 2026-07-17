---
type: review
task_slug: loop-mid-stop-and-review-skip
phase: 4
status: APPROVED_PARTIAL
created: 2026-05-23
reviewers_invoked: [code-reviewer]
consensus_method: single-source-acknowledged-anti-coverage
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-mid-stop-and-review-skip
  computed_at: "2026-05-23T11:55:00Z"
phase_scope_shipped: [1, 2, 3, 4]
phase_scope_blocked_partial:
  phase: 4
  blocker: "Phase 1-3 work in finalize stash queue; needs /hm:wrapup before Phase 4 completes"
phase_scope_remaining: [5, 6]
---

# 🎯 Round 1 Summary

**Diff:** 3 source changes + 1 new test + 8 snapshot regens.
- `src/harness_maker/interview.py` — `plan-exec-rev: [PLAN, EXECUTE, REVIEW]` (3-stage) added to both `_SIDE_STARTER` and `_PRODUCTION_STARTER`; registry asymmetry doc-comment added.
- `src/harness_maker/templates/stages/plan.md.j2` — Step 1 short-circuit guard + new Step 1.5 "Loop-mode detection" + ADR-pivot escape-hatch callout.
- `tests/unit/test_interview.py` — stale comment fixed + `plan-exec-rev` / `plan-exec-rev-wrap` registry assertions added.
- `tests/unit/test_plan_loop_mode_and_fused.py` (new) — 10 tests, 8 pass + 2 xfail (blocked on Phase 1-3 stash).

**Phase 4 status:** **APPROVED_PARTIAL**. Registry change + plan.md loop-mode branch are complete and tested. The third planned edit (re-add `plan-exec-rev` to Gate 0 EXPECTED_STAGES table in loop.md.j2) is **blocked on base repo state** — Phase 1-3 work sits in stash queue (4 `hm-finalize-*` stashes) waiting for `/hm:wrapup`'s `post-commit-pop`. PLAN status block documents the recovery path.

**Grade trajectory:** B (initial) → **A** after auto-fix.

**Anti-coverage caveat:** Single reviewer again. Same rubric gap as Phases 1-3.

# 🔍 Drift Findings

None.

# 📝 Manual-Only Findings

### P1 #1 — 2 blocked tests had no xfail marker → suite reports red *(FIXED)*

**File:** `tests/unit/test_plan_loop_mode_and_fused.py`.

**Reasoning:** Committed failing tests with no `xfail` block CI even when the failures are documented as expected (Phase 1-3 stash queue dependency). Misrepresents suite health.

**Fix applied:** Added `@pytest.mark.xfail(strict=True, reason="...")` to both blocked tests (`test_plan_exec_rev_command_file_rendered`, `test_loop_md_expected_stages_includes_plan_exec_rev`). `strict=True` ensures they FAIL (not silently pass) once Phase 1-3 land, surfacing the unblock automatically.

---

### P1 #2 — plan-exec-rev.md snapshot drift *(N/A — REJECTED as P2 in reviewer notes)*

Reviewer flagged conditional concern that was already mitigated by snapshot regen. No action needed.

---

### P1 #3 — Stale comment in `test_interview.py` *(FIXED)*

**File:** `tests/unit/test_interview.py:41`.

**Reasoning:** Comment listed pre-Phase-4 SIDE starter set. After adding `plan-exec-rev` to the registry, the comment would mislead future maintainers + the test lacked an assertion for the new entry.

**Fix applied:** Updated comment to include `plan-exec-rev` (3-stage) and `plan-exec-rev-wrap` (4-stage). Added 2 new assertions for these registry entries.

---

### P2 #1 — Step 1 internal-draft work wasted in loop-mode *(FIXED)*

**File:** `plan.md.j2:88`.

**Fix applied:** Added "Loop-mode short-circuit" note at top of Step 1: if `.hm-loop-active` exists, skip Step 1 entirely and jump to Step 1.5. Saves LLM tokens and avoids confusing intermediate draft state.

---

### P2 #2 — ADR escape-hatch buried in numbered list *(FIXED)*

**File:** `plan.md.j2` Step 1.5 body.

**Fix applied:** Extracted to a prominent `> ⚠️ **LOOP-MODE ADR CONSTRAINT (CRITICAL)** —` callout block with explicit halt mechanism (write blocker, exit non-zero, safety rail #4 fires).

---

### P2 #3 — Phase `<M>` derivation from prose Status lines fragile *(DEFERRED)*

**Defer rationale:** Real concern but requires structuring the master PLAN's status convention (canonical "Status:" line format). Cross-cutting change across all existing PLAN documents. Out of Phase 4 scope; logged as follow-up PLAN candidate.

---

### P2 #4 — plan-validator may false-positive on narrow per-iter PLAN *(DEFERRED)*

**Defer rationale:** Requires updating the plan-validator agent prompt to conditionally suppress scope-drift warnings when `loop_mode: true` is in the per-iter PLAN frontmatter. Touches a separate file (the agent prompt) that's already mid-evolution per the existing PLAN-antisycophancy-2026-05 communication-variant work. Logged as follow-up.

---

### P2 #6 — Registry asymmetry undocumented *(FIXED)*

**File:** `interview.py` (above `_PRODUCTION_STARTER`).

**Fix applied:** Added doc-comment explaining why `plan-exec-rev-wrap` (4-stage) is deliberately absent from Production preset — Production loop expects `plan-exec-rev` (3-stage) and loop-close owns wrapup.

# 🤝 Disagreements

None.

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 6 actionable + 1 N/A + 2 deferred | — |
| 2 (auto-fix) | A | 5 (P1×2 + P2×3) | 2 (P2 deferred — follow-up PLAN candidates) | 0 |

**Final grade:** A
**Iterations used:** 2 / 3
**Status:** APPROVED_PARTIAL (Phase 4 — minus the loop.md Gate 0 amend that depends on Phase 3 being in base)
**human_review_needed:** false (for what was shipped)
**phase_scope_shipped:** ~3.7 / 6 (Phase 4 minus 1 of 3 edits)

---

## Critical PLAN-level finding (catch-of-the-day)

This Phase 4 turn surfaced a **systemic flow problem**: the harness's stage-only finalize design defers stash-pop to `/hm:wrapup`'s `post-commit-pop`, but **the user has been invoking sequential `/hm:exec-rev` turns without running `/hm:wrapup` between them**. Each finalize pushes a stash that's never popped, so the second-and-later worktree iterations work against a stale HEAD (`d92c6b3`) that lacks all prior phases' code.

The dogfooding pass caught this because Phase 4 explicitly depends on Phase 1-3 artifacts (Gate 0 table re-amend depends on Phase 3's Gate 0 section; receipt-emit assertions depend on Phase 2's stage templates). Without that explicit dependency, the silent staleness would have continued indefinitely.

**Recommendation for user:**
1. Run `/hm:wrapup` now to commit Phase 1-3 + pop the stash queue.
2. Resolve the stalled `UU` merge conflicts on `tests/e2e/sandbox-plugin-test/*` (likely just accept regen output).
3. Re-run `/hm:exec-rev loop-mid-stop-and-review-skip -phase4` to land the remaining Gate 0 table amendment.

This is also a **PLAN-level recommendation**: future PLANs that span multiple `/hm:exec-rev` turns should explicitly note "run `/hm:wrapup` between turns to clear the stash queue" in their wrapup procedure.

## Notes

- No `git commit` invoked from this stage.
- Telemetry: not emitted (same single-reviewer-schema-mismatch as Phases 1-3).
- The `xfail(strict=True)` markers will auto-surface the unblock — when Phase 1-3 land in base, those tests will fail-as-xfail (an XPASS), which pytest reports as a different failure mode, signaling the markers should be removed.
