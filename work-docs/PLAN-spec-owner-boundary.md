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
