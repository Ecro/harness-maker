# PLAN — maker-resume-no-ask

SPEC: `specs/SPEC-maker-resume-no-ask.md` (approved).

## Phase 1 — resume without asking, from the worktree

- [x] Reproduce: hm S4r turns in `/mnt/project-files/hm-omc-bench/data/saga-results.jsonl`
      (5/5 found `tz-setting`, 5/5 asked first, reps 2 and 4 "not on disk", rep 3 two tasks).
- [x] RED: `test_ac001_interrupted_from_open_span[cut]` and `[second-cut]` fail on main 115504d0.
- [x] `world_model_digest.interrupted()`: newest span row is a `start` → `interrupted: true`
      (emitted only when true).
- [x] `world-model/SKILL.md.j2`: Resume consent line, "the stage opens the worktree, check no
      files", Claude-only `interrupted` pick for two or more tasks; Briefing names
      `.worktrees/<slug>/`. Render 4,677 chars (cap 4,689).
- [x] Docs: reference/world-model.md, CHANGELOG.
- [ ] Live: saga S4,S4r on the hm arm; boundary live suite (Host check).
