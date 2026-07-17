---
type: research
task_slug: review-stage-main-mutation-multisession
status: complete
created: 2026-06-22
tags: [harness-maker, research, worktree, review-stage, autopilot, multisession]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: [[PLAN-multisession-worktree-concurrency]], [[PLAN-worktree-cross-session-data-loss-defense]]
summary: "By design main is never mutated by review/execute; symptom of changes on main = worktree isolation not engaged (prompt-enforced, not runtime-enforced)"
---

# RESEARCH — Does `/hm:review` leave changes on `main`? Is multi-session safe?

## 🎯 Recommended Direction

**By design, neither `execute` nor `review` ever mutates `main` — `wrapup` is the
sole committer, via a fenced squash-land.** If changes actually appeared on the
`main` working tree during an autopilot `execute → review` chain, the per-task
worktree isolation was **not engaged for those edits** (edits were applied at the
repo root instead of inside `.worktrees/<slug>/`). Isolation is **prompt-enforced,
not runtime-enforced**, so this is a known soft spot — the code path is correct,
but the LLM must faithfully substitute the `<WT>` path on every Read/Write/Edit.
The decisive next step is a 3-command diagnostic (below) to confirm whether the
changes are *committed* on `main` (serious) or *uncommitted working-tree dirt*
(recoverable) and whether the `hm/<slug>` branch/worktree even exists.

## 🔍 Refinement Decisions

- Discovery lens: **Technical architecture / implementation** + **Risk / concurrency**.
- This project's harness.yaml: `preset: Production`, `worktree.feature_branch_workflow: true`,
  `worktree.scope: [execute, plan]`, `reviewers.auto_fix: true`, `grade_threshold: A`.

## 🛠️ Approaches Found — what the code actually does

### Fact 1 — `review` never commits, and operates inside the task worktree

`templates/stages/review.md.j2`:
- Line 102-105: when `feature_branch_workflow` is on, review includes the
  `worktree_preflight` partial → it runs `task-preflight <slug>` and operates
  inside the **persistent** `.worktrees/<slug>/` on branch `hm/<slug>` — the same
  worktree every `/hm:` stage for the task shares. NOT `main`.
- Line 484-486 (Outputs): auto-fix file modifications are **"Not committed —
  wrapup owns the commit."**
- Line 494 (Quality Bar): **"No `git commit` invoked from this stage. (Verify:
  `git log` shows no new commit relative to stage start.)"**

So review, run correctly, edits only `hm/<slug>` in the worktree and commits
nothing. `main`'s history and working tree are untouched.

| Field | Content |
|-------|---------|
| Approach | review = read + auto-fix inside `hm/<slug>` worktree, no commit |
| Assumption | The stage faithfully substitutes `<WT>` from `task-preflight` stdout |
| Evidence | review.md.j2:102-105, 484-486, 494; worktree_preflight.md.j2:10 |
| Trade-off | Isolation is prompt-level (LLM discipline), not runtime-enforced |
| Compatibility | Matches feature-branch model (this project's flag = on) |
| Risk | low — *if* `<WT>` is honored; medium if the LLM edits at repo root |

### Fact 2 — `execute` finalize does NOT merge to `main` under the flag

`worktree.py`:
- `_cli_finalize` (line 2861) routes by mode. Line 2912-2913: **when
  `feature_branch_workflow` is on AND `<WT>` is a genuine `hm/<slug>` task
  worktree → `_finalize_commit_not_stash`**.
- `_finalize_commit_not_stash` (line 2791) docstring: **"The base working tree is
  never touched (no `git stash`, no merge-to-base, no `.hm-finalize-stash-*`
  ref) and the persistent worktree is left in place — including on `fail`."** It
  captures pending work as WIP commits **on `hm/<slug>`**.
- The legacy `stage-only` merge-back-into-base path (which *does* leave staged
  uncommitted changes in the base checkout) is the **flag-OFF** path only. Under
  the flag with a task worktree, that branch is never taken.

So in the correct flag-on path, `main` is mutated **only** by `wrapup`.

### Fact 3 — `wrapup` is the sole `main` mutator, via a fenced squash-land

`templates/stages/wrapup.md.j2` Step 7.7 (line 439-475) + `worktree.py task_land`
(line 4339):
- Wrapup is the **land owner**: `task-land <slug> <BASE>` squash-merges
  `hm/<slug>` onto the base branch (base HEAD — `main`/`master`/current, not a
  hardcoded `main`) as **exactly one squash commit**, then tears down
  branch + worktree + registry row + marker. Idempotent; self-aborts on a dirty base.

## ⚠️ Pitfalls

1. **Isolation is prompt-enforced, not runtime-enforced.** `execute.md.j2:72`
   itself warns the isolator skill's "trigger-based dispatch is probabilistic …
   and can silently skip, **leaving safety-critical edits on the main branch**."
   The preflight prints `<WT>` and instructs "Treat that exact string as `<WT>`
   … Do NOT use a shell variable" — but if the model applies edits using
   repo-root-relative paths, they land on `main`'s working tree. **This is the
   most likely cause of the observed symptom.**

2. **Autopilot auto-advance carries the `next_stage` name, NOT the slug.**
   `autopilot_caps._cmd_boundary` (line 131) emits `{proceed, next_stage,
   pipeline_complete, …}` — no `slug`. `review.md.j2` auto-advance does
   `Skill(hm:<next_stage>)` with no slug. The next stage must **re-derive the
   slug + worktree from session context**. Within one chained session this
   usually works (context carries the slug), but it is not a hard binding — a
   wrong/empty `<WT>` inference sends review's edits to the base checkout.

3. **Stranded edits on `main` break multi-session lands.** If work ends up as
   uncommitted dirt on `main` (isolation skipped), then:
   - `hm/<slug>` is empty/partial → `wrapup`'s `task-land` squashes an empty
     branch (work never lands) **or** aborts on the base-dirty guard.
   - Any *other* session's `task-land` also aborts: `_has_user_dirty_state`
     (line 4450) refuses to land onto a dirty base → cross-session lands blocked.

4. **`auto_fix` mutates files mid-review.** Even on the correct path, review
   edits files (uncommitted) on `hm/<slug>`. Seeing modified files in the
   *worktree* is expected; seeing them in the *main checkout* is not.

## ✅ Multi-session safety (intended path) — well defended

- Per-task branch+worktree (`hm/<slug>`) → distinct tasks never share a branch.
- `task-land` runs its **entire** critical section under `_acquire_merge_fence`
  (flock primary + O_EXCL secondary, WSL2-reliable; `worktree.py:1346`,
  `4349-4352`). The fence covers even distinct slugs because all lands serialize
  on the shared base HEAD/index.
- Base-cleanliness abort (won't clobber a peer's work), session registry with a
  dedicated lock (never deletes live mismatched-UUID rows), and
  `task-preflight` drift warnings + `task-refresh` rebase complete the picture.

**Conclusion:** multi-session is safe *for the intended path*. The risk is
entirely the isolation-not-engaged failure mode in Pitfalls 1-3.

## ❓ Open Questions (decisive diagnostic — run in the repo root)

```bash
git log --oneline -8                 # are there NEW commits on main, or is history clean?
git status --porcelain               # uncommitted dirt on the main checkout?
git worktree list                    # does .worktrees/<slug>/ on hm/<slug> exist?
git branch --list 'hm/*'             # does the task branch exist + have commits?
git log --oneline main..hm/<slug>    # (if branch exists) is the work actually ON the branch?
```

Interpretation:
- **New commits on `main`** → something committed to `main` directly (would be a
  real defect — only wrapup should commit, and only via squash-land). Needs a
  separate root-cause.
- **Only `git status` dirt, `hm/<slug>` empty** → isolation was skipped; work is
  stranded on `main`'s working tree (Pitfall 1/3). Recoverable: move the dirt
  onto the branch or re-run inside `<WT>`.
- **Dirt on `main` AND `hm/<slug>` has the commits** → partial isolation; reconcile.

## 🔬 Live diagnosis — `~/edge_testfarm_os` (2026-06-22)

**The earlier design analysis assumed harness-maker's OWN config (Production +
`feature_branch_workflow: true`). `edge_testfarm_os` runs a DIFFERENT model.**

Observed:
- `preset: Side`; `worktree.scope: [execute]`; **`feature_branch_workflow` key
  ABSENT → flag OFF → OLD model.** So the `hm/<slug>` per-task worktree +
  squash-land design does NOT apply here.
- `git worktree list` → only the main checkout. **No `.worktrees/`, no `hm/*`
  branch.** Expected for flag-off.
- `git status` → 17 entries, **2019 insertions / 14 files** staged+unstaged on
  `main` (core/serial_guard.py, tests/unit/test_board_registry.py,
  tests/meta/test_meta_queue_recovery.py, …). All real work, intact, **not lost.**
- `git log` HEAD = `chore(harness): autonomy.level gated → auto_safe` — **clean;
  nothing wrongly committed to main.**
- `.claude/.hm-autopilot` present: `level: auto_safe`,
  pipeline `[research, spec, plan, execute, review, verify, wrapup]`,
  created `2026-06-22T01:53`.
- Two ORPHAN loop markers (`.hm-loop-execute-91c3…-20260618`,
  `.hm-loop-execute-fba0…-20260622`) pointing at `.worktrees/execute-*` dirs that
  no longer exist; the 06-22 one has an **empty `claude_session_id:` header**
  (degraded session-scoping). No legacy `.hm-loop-active`.

**Verdict — NOT a bug; this is by-design flag-OFF behavior:**
1. In the OLD model, `execute` isolates in an ephemeral `.worktrees/execute-<uuid>/`
   then `finalize stage-only` **merges the branch back into the base (main)
   working tree as staged-but-uncommitted changes** — intentional. `review`/
   `verify` then run in the base checkout. So "changes on main" is the *designed
   handoff* to wrapup, which is the sole committer (plain `git commit`, no
   squash-land in this model).
2. Autopilot auto-advanced execute → review → verify, then **STOPPED at the
   wrapup merge-gate** (`autopilot_caps` `merge_gate` halt — land/commit is
   human-gated). That is exactly why the work sits uncommitted on `main`:
   **wrapup has not run yet.** Run `/hm:wrapup` to commit it.

**Real follow-ups (not data loss):**
- Run `/hm:wrapup` BEFORE starting any new execute/loop — otherwise the
  **dirty-base guard (Layer 2)** will block the next `worktree create` on these
  2019 lines of dirt (forcing a risky `--allow-dirty-base`).
- The 2 orphan markers get reaped by `prune_stale` at the next `worktree create`;
  harmless now (no live loop). The empty-session-id marker means multi-session
  scoping was degraded for that run.
- **Multi-session here is the OLD 5-layer stash model, not `hm/<slug>` isolation.**
  If you want the stronger per-task-branch isolation + fenced squash-land, set
  `worktree.feature_branch_workflow: true` in harness.yaml and re-render via
  `/harness-maker:make` (note: Side preset's default is `false`).

## 📚 Sources

- (internal code only — no external sources)

## 🔗 Related Internal Docs

- [[PLAN-multisession-worktree-concurrency]]
- [[PLAN-worktree-cross-session-data-loss-defense]]
- [[RESEARCH-multisession-worktree-concurrency]]
- CLAUDE.md §Multi-session worktree (per-task feature-branch model, ADR-001~010)
