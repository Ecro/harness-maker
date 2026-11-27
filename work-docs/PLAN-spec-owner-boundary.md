---
type: plan
task_slug: spec-owner-boundary
status: complete
created: 2026-11-27
spec: "[[SPEC-spec-owner-boundary]]"
summary: Spec stage names the owner-only scope boundary and asks it once; Step 0 needs five conditions; hm check restores SIGINT for gate commands.
surface_allowance:
  chars: 622
  reason: "SPEC-spec-owner-boundary: the fifth Step 0 condition and the Step 2 Boundary rule (+622 in spec/hm-spec, incl. revision 2 +151). The DRI chose this fix on a decision card (2026-11-27); budgets raised by the measured growth only, after trimming a +550 first draft."
  delta_doc: BASELINE-DELTA-spec-owner-boundary.md
  commands:
    spec: 622
    hm-spec: 622
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
- [x] Live (revision 1): replay R3 + R4 hm run 1, spec stage: owner facts before code 3/5 (old 0–1),
      boundary asked as a question 0/3 (written as hm's own assumption instead).
- [x] Revision 2: the Boundary is open unless the ask states it or nothing old is kept, and an open
      one is asked (not only written down); Step 0 "no **Boundary** left open". Budgets +151:
      spec stage 7620 → 7771, `_GRANTED = 640`, allowance 622.
- [x] Live (revision 2): replay R3 + R4 hm × 2, spec-stage turns: owner facts before code 2, 3 of 5;
      boundary asked as a question 0/6. The DRI chose "지금 상태로 머지" (2026-11-27 19:09Z); merged #83.
- [x] Fold: surface baseline re-frozen at the merge commit.
