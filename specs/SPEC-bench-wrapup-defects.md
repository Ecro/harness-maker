---
type: spec
task_slug: bench-wrapup-defects
status: approved
created: 2026-11-25
tags: [correctness, wrapup, execute, gitignore, bench]
test_framework: pytest
interview_rounds: 0
summary: Two small /hm:wrapup defects the 2026-11-25 cost/value bench found - code missing from the first wrapup commit and a memory lock file committed. Two more reported defects are left out - mid-file imports (cause removed by SPEC-inline-golden-rows) and a missing Understanding block (a measurement artifact).
---

# SPEC — bench-wrapup-defects

## Intent

The 2026-11-25 bench (`/mnt/project-files/hm-blog-cost/`, 36 hm runs on tier 1 and 2, Sonnet 5.5,
worktree isolation off) reported four small defects in what hm leaves behind. Each costs the user a
manual fix or an extra model turn, and none is a design question.

Re-reading the 36 transcripts for this SPEC corrected two of the report's counts:

1. **Code missing from the wrapup commit: 35 of 36 runs, not 5.** With isolation off,
   `wrapup_land` stages only the deliverables (`--worktree` is `--base`, so the sweep is skipped by
   design). Nothing in the stage tells the model to stage its code first, so the commit held only
   PLAN/SPEC/REVIEW/memory. In 30 runs the model noticed afterwards and ran `git add <code>` +
   `git commit --amend`; in 5 it made a second commit (the 5 the report counted).
2. **`.claude/memory/.wiki.lock` committed: 30 of 36.** `memory_md` leaves the lock file next to
   `wiki.md`; the wrapup manifest stages `.claude/memory/` whole, and the harness gitignore block
   written into user projects does not list memory lock files (this repo's own `.gitignore`
   does: `.claude/memory/*.lock`).
3. **Mid-file imports: 3 of 36** (t3-hm-3, t9-hm-1, t9-hm-2; ruff E402). The model appended an AC
   test block, with its own `import json` / `from pathlib import Path`, to the end of an existing
   test file. Not fixed here: those imports exist only to read the golden JSON, which
   SPEC-inline-golden-rows replaces with rows pasted into the test; a stage sentence would also
   push SPEC-ask-less AC-007's growth cap over (Codex, Side: 768 > 750).
4. **Understanding block: missing from the final reply in 1 of 36, not 27-48%.** The report's
   check looked for the literal `Understanding:`; 16 replies printed the block reformatted
   (`**Understanding block:**`, bullets kept), and 1 (t10-hm-2) left it out. Not fixed here: one
   miss does not pay for more stage text, which every run reads.

## Outcomes

- With isolation off, the wrapup commit holds the task's code and tests on the first try.
- The receipt names working-tree changes the commit left out, so a miss is visible in the receipt.
- No memory lock file is committed in a project hm rendered.

## In-Scope Scenarios

- S1 (normal, isolation off): Given a task that created `src/new.py` and changed `tests/test_x.py`,
  when wrapup runs, then the model stages them before `wrapup_land` and the one commit holds them.
- S2 (failure, isolation off): Given the model forgot an untracked file, when `wrapup_land`
  commits, then `steps.left_out` lists it and stderr says how to amend it in.
- S3 (normal): Given `hm make` wrote the harness gitignore block, when `memory_md` leaves
  `.claude/memory/.wiki.lock`, then git ignores it and `wrapup_land --optional .claude/memory/`
  does not commit it; `wiki.md` still lands.

## Non-Goals

- Sweeping the shared working tree when isolation is off. `test_a_shared_working_tree_is_never_swept`
  keeps holding: unrelated work in the user's tree must not reach a wrapup commit.
- Untracking a lock file a project already committed (`git rm --cached` is the user's call).
- Adding ruff to `hm check`. Not every project uses ruff, and the defect has one cause.
- Golden JSON test layout (asked separately on a decision card) and the SPEC Verification table
  (separate SPEC).

## Constraints

| constraint | value |
|---|---|
| test framework | pytest |
| `wrapup_land` exit codes and receipt keys | unchanged; `steps.left_out` is added |
| stage size | no growth in the worktree-on render the surface ratchet measures; the isolation-off wrapup budget (`tests/unit/test_overhaul_p1_surface.py`) raised by the measured growth only |
| isolation-on path | unchanged (the sweep already stages everything) |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: isolation-off wrapup tells the model to stage its code first
The rendered `/hm:wrapup` with isolation off says, right after the `hm wrapup_land` call, to
`git add` this task's code and tests before it, in place of "`index_after` must hold the
code.". The isolation-on render keeps that sentence and does not carry the new one (its sweep
stages the worktree).
- oracle_source: golden. Fixed phrase "`git add` this task's code and tests before it.",
  chosen here before the template change; 35 of 36 bench commits lacked the code.

### AC-002: the receipt lists what the commit left out
After the commit, `wrapup_land` records `steps.left_out`: the porcelain paths still changed or
untracked (not ignored) in `--worktree`. A file staged before the call is not in it; an untracked
file the caller did not stage is. When the list is not empty, stderr carries one
`[wrapup_land] left out of the commit:` line. With isolation on the list is empty.
- oracle_source: golden. `git status --porcelain` on a fixture repo whose contents are fixed in
  the test.

### AC-003: memory lock files are ignored in rendered projects
`.claude/memory/*.lock` is in the harness gitignore patterns. In a git repo after
`_ensure_harness_gitignore`, `git check-ignore` ignores `.claude/memory/.wiki.lock` and does not
ignore `.claude/memory/wiki.md`, and `wrapup_land --optional .claude/memory/` commits `wiki.md`
without the lock file.
- oracle_source: golden. git's own ignore matching on a fixture repo.


## Verification

| scenario | mode | AC |
|---|---|---|
| S1 | render | AC-001 |
| S2 | unit (git fixture) | AC-002 |
| S3 | unit (git fixture) | AC-003 |
| regression | unit | `tests/unit/test_wrapup_land.py` (sweep gate, manifest, receipt JSON) |

## Open Questions

none

## Refinement Decisions

- Approval: the DRI asked for these fixes in the measurement thread (2026-11-25, "hm 에 보완해야할
  것") and picked "별도 스레드에서 진행" on its card; project rules let a small revertible fix merge
  on green CI. No further card.
- Default (agent): S1 is a prose fix, not a sweep. Isolation off means a shared tree; only the
  model knows which changed files are this task's. Undo: one sentence.
- Default (agent): S2 reports and does not abort. An abort would cost a turn in every run whose
  tree holds unrelated untracked files (the bench's `__pycache__/` dirs); the list plus the stderr
  line lets the model amend in the same turn. Undo: drop the field.
- Default (agent): the lock fix goes in `_HARNESS_CHURN_GLOBS` (the gitignore-only tuple), so the
  existing sync tests cover it. A project picks it up on its next `hm make`.
- Default (agent): no intent picked. HM-LIGHT-LANE is about cost; these are correctness defects.
- Default (agent): spec-validator skipped (5 live ACs; `validator: skip`).
