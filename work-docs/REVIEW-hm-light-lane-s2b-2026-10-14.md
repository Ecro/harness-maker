---
type: review
task_slug: hm-light-lane-s2b
status: APPROVED
created: 2026-10-14
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
run_id: c4f3eabc42e7
review_base: d2c0ab0fa461b995b2944f8afdeebe1c929dab24
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-light-lane-s2b
  computed_at: 2026-10-14T19:00:00Z
---

# REVIEW — hm-light-lane-s2b (stage 2b of HM-LIGHT-LANE)

Run on the PR branch (no per-task worktree). Lane `full`, preset Production. Diff
`review_base..HEAD` with regenerated outputs (snapshots, goldens, surface baseline, fixture JSON)
excluded from the reviewer diff.

**Procedure deviations, stated so nobody infers a step that did not run:**
- Round 1 was two dispatches (core lenses; security + concurrency + tests), both read-only with no
  shell, so they reviewed the tree by reading it. `lens_coverage`: 7 lenses exercised,
  `blocks_approval: false`.
- Pass 2 was the main loop deciding each finding, not a second dispatch.
- The confirmation pass was one dispatch with a shell over the whole `review_base..HEAD` diff. It
  rendered ten configs and read the commands and `.claude/hm/` files, not the four-dispatch C2.
- The cross-model second opinion was skipped (`codex` CLI not installed; warn and proceed).
- The new test file was written after the implementation and checked RED against an unmodified
  HEAD worktree; round-1 fix tests were written first and run RED.

## Round 1

Grade **B** before fixes (P0 0, P1 3). 19 findings: core 9, security 3, concurrency 3, tests 4.

| Sev | Id | Summary | Disposition |
|---|---|---|---|
| P1 | S1 | A missing steps file let an empty delegate receipt reconcile and commit | fixed: `!test -r <base_root>/.claude/hm/<file>` before the dispatch; MISSING stops (verify reports FAIL) |
| P1 | K1 | The confirm-1 repair round had no pointer to `review-autofix.md` | fixed: autofix pointer and both prefaces cover it |
| P1 | K2 | The receipt-mismatch repair had no pointer to the steps file (locked memory CLI rule) | fixed: the bullet reads `wrapup-steps.md` with the shared fail-closed clause |
| P2 | S2 | `/hm:loop`'s wrapup step substituted `<WT>` for `.claude/hm/` reads | fixed: same exemption as Step 4 |
| P2 | S3 | "Project root" is prose; the main-loop Read path is not made absolute | **accepted residual**: the same rule SPEC-hm-light-lane-s2 accepted for `autopilot-advance.md`; the delegate path and the existence check use `base_root` |
| P2 | T1/K8 | Line-growth bound raised 60→70 | fixed: the expanded delta is pinned as an equality (77) with dated attribution |
| P2 | C1 | Commands rendered before the files they point at | fixed: `_reference_files` first in `_base_files` |
| P2 | C2 | A review STOP left the run open and the freeze unreaped | fixed: reap + `review_run close --outcome CHANGES_REQUESTED` before STOP |
| P2 | T2 | Instruction baseline masked an inline-body deletion | fixed: a reference file counts only where the command points at it |
| P2 | K3 | Delegate told to follow a file that, loop on, says to emit Gate 0 | fixed: preface and delegate prompt say Gate 0 is the caller's |
| P2 | K4 | `<WT>` undefined for the delegate | fixed: prefaces define it as the brief's `worktree_root` |
| P3 | T3, T4, C3, K5, K6, K7, K9 | Allowlist exactness, instruction capture for all 7 configs, A.5 `tdd_active`, relative references, spacing, unmatched pointers, a template artifact | fixed (K6 not reproducible; a test pins the spacing) |

## Confirmation pass

**PASS**: every round-1 finding fixed except S3 (residual), no new P0/P1, six P3s. Five fixed after
the pass (the mismatch bullet's missing-file clause, the existence check on `base_root`, the Codex
gate on the delegate's step-list paragraph, a vacuous assert, reference-file calls counted in the
round-trip budget). Accepted: a missing `execute-a5.md` gives a bare STOP mid-phase; it fails
closed, and the file renders in every harness.

## Grade

**A** after round 1 + confirmation. Status APPROVED.
