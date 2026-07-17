---
type: review
task_slug: latency-worktree-step-preview
status: APPROVED
created: 2026-05-31
reviewers_invoked: [code-reviewer, code-reviewer]
consensus_method: cross-check
scope: Phase 2 only (step-manifest partial — base-checkout template pass)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: latency-worktree-step-preview
  computed_at: 2026-05-31T00:00:00Z
---

# REVIEW — latency-worktree-step-preview (Phase 2: step-manifest)

## 🎯 Round 1 Summary

Diff: new `_partials/step_manifest.md.j2` + `{% include %}` into 4 wrappers (8 src insertions) + new structural test + 8 regenerated snapshots (hash-only diff, file_count unchanged).

Two `code-reviewer` instances on disjoint aspects (so findings are single-source by construction → `manual-only` by the consensus letter). **Round-1 grade by consensus-passed count: A.** But Reviewer B surfaced two **orchestrator-verified P1s** that hit the PLAN's own #1-flagged risk (loop suppression). Rather than grade-game them as manual-only and ship, I verified both against the code and entered a Round-2 fix pass.

- **Reviewer A (render/wiring): clean.** Traced the uncovered Codex path (`render._render_text_file` → `_split_template_frontmatter`): the manifest lands strictly below the frontmatter `---`, so Codex `name`/`description` parsing is intact. Confirmed StrictUndefined-safe (partial has zero variables), one-manifest-per-fused-workflow, sound ordering, no whitespace defect.
- **Reviewer B (behavioral): 2×P1 + 2×P2** (below).

## 🔍 Drift Findings

None. Phase 2 scope = the manifest partial + 4 wrappers + test + snapshot regen; the diff matches exactly. (`loop.md.j2` was deliberately NOT edited — see P1 #2 routing. PLAN-doc edits are gitignored, not in the diff.) `drift_verdict: clean`.

## ✅ Consensus Findings

None. The two reviewers examined disjoint aspects (render vs behavior), so no two findings surface-matched. This is expected from the deliberate aspect split, not a reasoning disagreement.

## 📝 Manual-Only Findings (single-source; orchestrator-verified + acted on)

### P1 #1 — Suppression marker resolution under-specified for worktree cwd → **FIXED (Round 2)**
- **File:** `agents/_partials/step_manifest.md.j2`
- **OBSERVE:** manifest said "skip if `.hm-loop-active` exists at the project root." The loop driver runs with cwd inside `<WT>` (`.worktrees/<name>/`), and the marker is at the project root; `plan.md.j2:101-104` has a precise resolution precedent (`git rev-parse --show-toplevel` + walk out of `.worktrees/`) that the manifest omitted. `hooks/loop_gate.py:_worktree_parent_marker` exists precisely because this resolution is non-trivial.
- **CONCLUDE:** from inside a worktree a naive check misses the marker → manifest prints every iteration → the ×iterations transcript-flood the suppression was meant to prevent. **This is the PLAN's #1-flagged risk, not fully closed by the initial impl.**
- **Resolution:** rewrote the manifest's suppression clause to mirror `plan.md.j2` — explicit worktree→project-root resolution. Locked by a new test assertion (`.worktrees` must appear in the partial).

### P1 #2 — Loop ingests the workflow file inline; no mechanical boundary strips the preamble → **ROUTED to Phase 3**
- **File:** `commands/hm/loop.md.j2:761` (Phase 3's file)
- **OBSERVE:** the loop reads the workflow/stage `.md` inline into the driver's own context (loop.md.j2:761-763, 834-835), so suppression rests entirely on the driver-LLM honoring the marker check.
- **CONCLUDE:** belt-and-suspenders: the driver should ALSO be told to ignore the preamble. The reviewer itself labeled this "belt-and-suspenders with the marker check."
- **Resolution:** P1 #1's precise marker-resolution fix is the primary mitigation (landed in Phase 2). Editing `loop.md.j2` now would be Phase-2 scope drift; Phase 3 owns `loop.md.j2`, so the driver-side "never print the manifest" instruction was added to **Phase 3 scope** in the PLAN.

### P2 #3 — Framing didn't name terminal STOP boundaries → **FIXED (Round 2)**
Added to the manifest: "...and any stage's own `STOP — do not proceed` boundary override this plan; never treat the printed manifest as a commitment to run past a STOP."

### P2 #4 — Fused-workflow manifest granularity loose → **FIXED (Round 2)**
Manifest now instructs: for a fused workflow, list **one line per stage** (`## Stage:` entries), not every sub-step.

### (Reviewer A note) Extend exclusion test to `stages/*.md.j2` → **APPLIED (Round 2)**
Added `test_stages_do_not_include_step_manifest` to lock the one-manifest-per-workflow invariant.

## 🤝 Disagreements

None. Reviewer A (clean) and Reviewer B (findings) examined different aspects — complementary, not contradictory.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 2 P1 + 2 P2 (manual-only) | — |
| 2 (fix)   | A     | P1#1, P2#3, P2#4, +2 test assertions; P1#2 routed to Phase 3 | 0 (P1#2 tracked in Phase 3 scope) | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false (P1 #1 — the primary loop-suppression gap — is fixed; P1 #2 is secondary hardening tracked in Phase 3 scope)
