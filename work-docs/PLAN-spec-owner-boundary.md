---
type: plan
task_slug: spec-owner-boundary
status: planning
created: 2026-11-27
spec: "[[SPEC-spec-owner-boundary]]"
summary: Spec stage names the owner-only scope boundary and asks it once; Step 0 needs five conditions; hm check restores SIGINT for gate commands.
surface_allowance:
  chars: 471
  reason: "SPEC-spec-owner-boundary: the fifth Step 0 condition and the Step 2 Boundary rule (+471 in spec/hm-spec). The DRI chose this fix on a decision card (2026-11-27); budgets raised by the measured growth only, after trimming a +550 first draft."
  delta_doc: BASELINE-DELTA-spec-owner-boundary.md
  commands:
    spec: 471
    hm-spec: 471
---

# PLAN — spec-owner-boundary

SPEC: `specs/SPEC-spec-owner-boundary.md` (approved).

## Phase 1 — spec stage asks the owner-only boundary; hm check restores SIGINT

- [x] Reproduce: `bash -c 'uv run pytest … & wait'` fails
      `test_stop_signal_kills_live_agents_and_skips_queued_cells[sigint]` and
      `test_external_caller_cancellation_cleans_owned_processes` on main 124c4c8c; both pass in
      the foreground.
- [x] RED: `tests/render/test_spec_owner_boundary.py` (16 cases) and
      `tests/unit/test_check_sigint_inherit.py[ignore]` fail on main.
- [x] `stages/spec.md.j2`: Step 0 five conditions; Step 2 Boundary paragraph before the questions.
- [x] `check._run`: `preexec_fn` sets SIGINT to SIG_DFL in the gate child.
- [x] Budgets: spec stage 7140 → 7620, SPEC-ask-less AC-007 `_GRANTED = 480` (measured +475, after review fixes).
- [x] Snapshots regenerated; HOW-IT-WORKS (en/ko), CHANGELOG.
- [ ] Live: replay bench R3 + R4 hm arm × 2 on this branch.
