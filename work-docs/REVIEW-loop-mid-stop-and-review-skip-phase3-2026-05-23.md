---
type: review
task_slug: loop-mid-stop-and-review-skip
phase: 3
status: APPROVED
created: 2026-05-23
reviewers_invoked: [code-reviewer]
consensus_method: single-source-acknowledged-anti-coverage
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-mid-stop-and-review-skip
  computed_at: "2026-05-23T08:25:00Z"
phase_scope_shipped: [1, 2, 3]
phase_scope_remaining: [4, 5, 6]
---

# 🎯 Round 1 Summary

**Diff:** 1 template modified + 1 new test + 8 snapshot YAML regen.
- `src/harness_maker/templates/commands/hm/loop.md.j2` — Gate 0 wiring (Step 3.5 `.current-iter` write + Step 4.5 Gate 0 verification + Step 7.0 cleanup + runtime schema + /compact recovery).
- `tests/unit/test_loop_template_render.py` (new) — 10 tests covering Gate 0 contract surface.
- 8 snapshot YAMLs regen'd.

**Scope verdict:** clean. PLAN Phase 3 status flipped DONE.

**Grade trajectory:** C (initial) → **A** after auto-fix.

**Anti-coverage caveat:** Single reviewer again. Same rubric gap. Findings acted on regardless.

# 🔍 Drift Findings

None.

# 📝 Manual-Only Findings

### P0 — EXPECTED_STAGES table referenced wrong workflow name + missed production default *(FIXED)*

**File:** `loop.md.j2` step 4.5 (Gate 0 section).

**Reasoning:**
- OBSERVE: My initial table mapped `plan-exec-rev → plan,execute,review`. The actual registry (`interview.py:_SIDE_STARTER` + `_PRODUCTION_STARTER`) has `plan-exec-rev-wrap` (4 stages including wrapup), `exec-rev-wrap-ver` (production default, 4 stages including verify), and `res-spec-plan` (3 stages: research/spec/plan).
- INFER: Production harness users (default workflow `exec-rev-wrap-ver`) would hit the fallback prose path — "read the workflow command file header" — which is exactly the LLM-prose-as-gate that Phase 3 is supposed to eliminate.
- CONCLUDE: P0. Gate 0 silently under-checks for the majority of production users; wrapup + verify receipts never mechanically verified.

**Fix applied:** Table now lists all 5 registry entries (`exec-rev`, `exec-rev-wrap`, `exec-rev-wrap-ver` *(prod default)*, `plan-exec-rev-wrap`, `res-spec-plan`). Fallback prose retained for custom user-defined workflows.

---

### P1 — Option B deadlock: writing `verdict:skipped` then re-verifying Gate 0 loops forever *(FIXED)*

**File:** `loop.md.j2` step 4.5 escalation block.

**Reasoning:**
- OBSERVE: After cap=2 exhaustion, Option B writes `verdict:skipped`. The surrounding control flow says "proceed to step 5" but doesn't explicitly break the Gate 0 re-verify cycle. Gate 0 treats `skipped != pass` as failure.
- INFER: A context-pressured LLM would re-invoke Gate 0 after the skipped write → exit 1 → escalate again → user picks Option B again → infinite loop.
- CONCLUDE: P1. Without an explicit "do NOT return to step 4.5" bypass, Option B is broken.

**Fix applied:** Option B prose now states "jump directly to step 5 — do NOT return to step 4.5" with rationale. Sets `gate0_skipped_explicitly[K] = true` in working memory so step 5 distinguishes user-acknowledged hole from workflow success. New test `test_gate0_option_b_breaks_out_of_reverify_loop` pins the bypass prose.

---

### P1 — `stage_retry_counts` unbounded growth *(FIXED)*

**File:** `loop.md.j2` Step 7 loop close.

**Reasoning:**
- OBSERVE: My initial design reset entries to 0 on Gate 0 PASS but never deleted keys. Over 50 iters × 4 stages, the runtime block accumulates up to 200 keys, all reloaded on every `/compact`.
- INFER: Memory growth in long loops + slower `/compact` recovery. Not an immediate correctness bug (per-iter keys don't interfere), but YAML bloat.
- CONCLUDE: P1. Address with explicit cleanup at loop close.

**Fix applied:** New Step 7.0 — "Clear `stage_retry_counts`" — writes an empty map at loop close. Documented why (only current iter's keys ever matter at runtime). New test `test_loop_close_clears_stage_retry_counts` pins this.

---

### P2 — Codex variant `echo <N>` newline risk *(FIXED)*

**File:** `loop.md.j2` Step 3.5 Codex variant.

**Fix applied:** Changed `echo <N>` to `printf '%s' <N>` for both Claude Code and Codex variants. Explicit single-byte write avoids any context where trailing newline could leak into `--iter "$ITER"`. Inline prose explains the rationale.

---

### P2 — Fallback prose for custom workflows is LLM-driven *(DEFERRED)*

**Defer rationale:** Reviewer suggested adding machine-readable `<!-- hm:stages: ... -->` comments to each rendered fused workflow command file and having Gate 0 grep them. Real improvement but out of Phase 3 scope (touches the fused workflow renderer + every fused workflow file). Logged for follow-up PLAN candidate.

---

### P2 — Test coverage gap: Option B deadlock not covered *(FIXED)*

**File:** `tests/unit/test_loop_template_render.py`.

**Fix applied:** New test `test_gate0_option_b_breaks_out_of_reverify_loop` asserts the bypass prose. Test count went from 8 → 10.

# 🤝 Disagreements

None.

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 6         | —   |
| 2 (auto-fix) | A | 5 (P0×1 + P1×2 + P2×2; 1 P2 deferred) | 1 (custom-workflow machine-readable stage list) | 0 |

**Final grade:** A
**Iterations used:** 2 / 3
**Status:** APPROVED
**human_review_needed:** false
**phase_scope_shipped:** 3 / 6

---

## Catch-of-the-day

The P0 finding is especially valuable — my PLAN ADR-002 talked about adding `plan-exec-rev` as a new fused workflow, but the registry already has `plan-exec-rev-wrap`. Phase 4 was scoped to add a workflow that effectively exists under a different name. **This dogfooding pass caught a PLAN drift.** PLAN Phase 4 will need amendment: instead of adding `plan-exec-rev`, simply make loop-mode `/hm:plan` aware that `plan-exec-rev-wrap` is the existing fused workflow that triggers per-iter plan refinement.

This is precisely the kind of catch the loop-skip-review mechanism prevents going forward — when stages get silently dropped, no one notices that an ADR contradicts the codebase.

## Notes

- No `git commit` invoked from this stage.
- Telemetry: not emitted (same reason as Phase 1/2 — single-reviewer schema mismatch).
- Snapshot regen produced byte-identical YAMLs except for the rendered `loop.md` SHA changes.
