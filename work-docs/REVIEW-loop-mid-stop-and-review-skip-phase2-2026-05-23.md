---
type: review
task_slug: loop-mid-stop-and-review-skip
phase: 2
status: APPROVED
created: 2026-05-23
reviewers_invoked: [code-reviewer]
consensus_method: single-source-acknowledged-anti-coverage
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-mid-stop-and-review-skip
  computed_at: "2026-05-23T06:30:00Z"
phase_scope_shipped: [1, 2]
phase_scope_remaining: [3, 4, 5, 6]
---

# 🎯 Round 1 Summary

**Diff:** 6 stage templates + 1 new test + 8 snapshot YAML regen.
- `src/harness_maker/templates/stages/{execute,review,wrapup,plan,spec,research}.md.j2` — receipt-emit section added.
- `tests/unit/test_render_stage_receipts.py` (new) — 19 tests after auto-fix.
- `tests/snapshot/*-{task,spec}.expected.yaml` × 8 — regen'd to reflect new rendered template SHAs.

**Scope verdict:** clean. PLAN Phase 2 status flipped DONE; Phases 3-6 still NOT STARTED.

**Grade trajectory:** B (initial) → **A** after auto-fix.

**Anti-coverage caveat:** Single reviewer (code-reviewer) again. Cross-check rubric tags every finding `manual-only` → strict rubric reports Grade A trivially (same gap as Phase 1 round). Findings acted on regardless. Recorded for re-calibration.

# 🔍 Drift Findings

None. All changes in PLAN Phase 2 scope.

# ✅ Consensus Findings

None — single reviewer.

# ⚠️ Weak Consensus

None.

# 📝 Manual-Only Findings

### P0 #1 — `ITER=0` fallback clashes with `Field(ge=1)` schema *(FIXED)*

**Files:** all 6 stage templates.

**Reasoning:**
- OBSERVE: Phase 1's `iter_receipts.py` declares `iter: int = Field(ge=1)`. Phase 2's templates emitted `|| echo 0` fallback when `.current-iter` was absent.
- INFER: Standalone-with-isolation runs (worktree exists, no autoloop) hit the fallback → CLI passes `--iter 0` → Pydantic raises ValidationError → exit 1. The prose claim "writes to iter-0/, which Gate 0 ignores" was incorrect — nothing was written.
- CONCLUDE: P0. Documented behavior diverges from actual behavior; standalone runs silently emit a non-zero exit from a docs-said-benign code path.

**Fix applied:** Replaced the 2-line `cat||echo 0` + CLI invocation with a single shell-guarded block: `if [ -f .../.current-iter ]; then ITER=$(cat); uv run ...; fi`. Receipt only writes when `.current-iter` exists (i.e., autoloop is actually running). Prose updated in all 6 templates to reflect "no write when no `.current-iter`" semantics. Both Claude Code (`!if ... fi`) and Codex (`Bash("if ... fi")`) variants updated.

---

### P0 #2 — Snapshot YAMLs claimed stale *(REJECTED as false positive)*

**Reasoning:**
- The reviewer claimed all 8 snapshot YAMLs still carried the pre-Phase-2 hash `cb1e27...` for `commands/hm/execute.md`, citing the sandbox e2e fixture.
- Reality: `regenerate.py` pins `HM_MAIN_CHECKOUT_PATH=/home/noel/harness-maker`. The regen-produced hash differs from a worktree-path-unpinned standalone render. Pinning is part of `tests/unit/conftest.py` autouse fixture; `test_synthesize_snapshot.py` passes 12/12 with the post-regen YAMLs. Verified by re-running the snapshot suite after regen.
- CONCLUDE: Not a defect. Reviewer conflated sandbox-plugin-test fixtures (separate dir, rendered at v0.23.2) with `tests/snapshot/*.expected.yaml`. Recording for future-reviewer-prompt calibration.

---

### P1 #1 — `<WT>` undefined in non-execute templates *(FIXED prose; no shell change)*

**Files:** review.md.j2, wrapup.md.j2, plan.md.j2, spec.md.j2, research.md.j2.

**Reasoning:**
- Only execute.md.j2's Step 0 defines `<WT>` substitution. The other 5 stages have no Step 0 worktree block.
- INFER: An LLM running standalone `/hm:review` would encounter `<WT>` in the receipt block with no prior substitution instruction.
- However, the auto-fix's `if [ -f <WT>/.claude/.hm-iter-receipts/.current-iter ]` guard naturally handles this: when `<WT>` is a literal string (unsubstituted), `[ -f ./<WT>/.claude/.hm-iter-receipts/.current-iter ]` is false → receipt block is a no-op.
- CONCLUDE: P1, addressed via the same shell-guard fix as P0 #1. Prose updated in 4 affected stages to call out "literal `<WT>` test is also false, so no write fires."

---

### P1 #2 — `skipped`-warning test only checked one stage *(FIXED)*

**Files:** `tests/unit/test_render_stage_receipts.py`.

**Fix applied:** Parametrized `test_receipt_block_warns_against_skipped_verdict` over all 6 STAGE_NAMES. The "by construction" claim is now mechanically verified per-stage. Test count went from 1 → 6 for this assertion family.

---

### P2 #1 — Heading level inconsistency (`### Step 4.5` in execute vs `## Emit` elsewhere) *(DEFERRED)*

**Defer rationale:** Cosmetic. `test_receipt_emit_positioned_before_outputs` uses `body.find("## Outputs")` which finds the literal string regardless of receipt section heading level (`###` and `##` both come before `##  Outputs`). No correctness impact. Fixing would touch every template; leave for a future cleanup pass.

---

### P2 #2 — `test_fused_workflow_inherits_receipts` skip-silently *(FIXED)*

**Files:** `tests/unit/test_render_stage_receipts.py`.

**Fix applied:** Removed `pytest.skip()` branch. The test now asserts `cmd_file.is_file()` unconditionally — `exec-rev` is the default loop per-iter workflow and must always be present in the default harness.

---

### P2 #3 — Wrapup pass criterion claimed worktree finalize *(FIXED)*

**Files:** `wrapup.md.j2`.

**Fix applied:** Pass criterion now reads "the wrapup commit landed and memory was appended" — finalization belongs to the execute stage. Wrapup cannot know its state.

# 🤝 Disagreements

None — single reviewer.

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 7         | —   |
| 2 (auto-fix) | A | 5 (P0×1 + P1×2 + P2×2; 1 P0 rejected + 1 P2 deferred) | 1 (cosmetic deferred) | 0 |

**Final grade:** A
**Iterations used:** 2 / 3
**Status:** APPROVED
**human_review_needed:** false
**phase_scope_shipped:** 2 / 6

---

## Next Phase

P3 — Gate 0 wiring in `loop.md.j2`. With P1+P2 in place, the loop driver template can now:
1. Write `<WT>/.claude/.hm-iter-receipts/.current-iter` at iter start.
2. After each fused-workflow returns, invoke `python -m harness_maker.iter_receipts verify --iter N --expected execute,review --root <WT>` as Gate 0.
3. On verify exit-code 1, auto-retry the missing stage (per ADR-005, cap=2).
4. Track `stage_retry_counts` in loop-context `runtime:` block.

P3 should fit one `/hm:exec-rev` turn — single-file template edit + snapshot regen.

## Notes

- No `git commit` invoked from this stage (verified: `git status` shows untracked + modified, no new commits).
- Telemetry: not emitted; same reason as Phase 1 round — 14-field schema is review-pass-pair specific, single-reviewer single-round doesn't fit cleanly.
- Cross-check anti-coverage: this is the second `/hm:exec-rev` round documenting the same rubric gap. A small follow-up PLAN to extend `reviewers.consensus` with a `single-explicit` mode (acknowledges 1 reviewer is enough for trivial diffs without penalizing grade) would close the recurring caveat. Not in this PLAN's scope.
