---
type: review
task_slug: bench-wrapup-defects
created: 2026-11-25
spec: "[[SPEC-bench-wrapup-defects]]"
plan: "[[PLAN-bench-wrapup-defects]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 5 findings (1 P2, 4 P3), no P0/P1. Four accepted and fixed, one rejected on the size cap."
---

# REVIEW — bench-wrapup-defects

One code-reviewer round on the uncommitted diff. The reviewer ran the PLAN exit set plus
`test_deliverable_single_source`, `test_understanding_block`, `test_overhaul_p1_kept`,
`test_step_sensitivity_registry` and `test_git_disposition` (all green), confirmed the lock glob
keeps the gitignore sync test equal, and that nothing else pins the isolation-off
"`index_after` must hold the code." sentence. No `Do not change` path was crossed.

After the round, `hm check`'s full suite stopped on SPEC-ask-less AC-007 (the Codex Side render
grew 768 > 750). The execute sentence "Imports go on top." was dropped with its AC (SPEC defect 3
now records why: SPEC-inline-golden-rows removes the JSON-loading imports that caused it), and the
wrapup sentence was shortened; the growth is now 749 / 735 (Codex) and 728 (Claude Side).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | CHANGELOG.md | No `[Unreleased]` entry although the PLAN scope lists it. Fix: `### Fixed` entry added | accepted | PLAN Phase 1 scope |
| F2 | P3 | src/harness_maker/wrapup_land.py:297 | `left_out_paths` parsed porcelain by hand; git quotes paths with spaces or non-ASCII, so the receipt named a path `git add` cannot use. Fix: `--porcelain -z`, rename source entries skipped; test adds an `a b.py` path | accepted | SPEC AC-002 |
| F3 | P3 | src/harness_maker/worktree.py:142 | The `_HARNESS_CHURN_GLOBS` comment says each glob has an `_HARNESS_ARTIFACT_PREFIXES` twin; the lock glob has none. Fix: comment says it is gitignore-only on purpose | accepted | code accuracy |
| F4 | P3 | work-docs/PLAN-bench-wrapup-defects.md:7 | PLAN summary claimed an Understanding-block fix the SPEC leaves out. Fix: clause removed | accepted | SPEC Intent item 4 |
| F5 | P3 | src/harness_maker/templates/stages/wrapup.md.j2:56 | The stage prose never names `steps.left_out`; the model relies on the stderr line | rejected | SPEC-ask-less AC-007 growth cap (749 of 750 used); the stderr line names the amend command |
