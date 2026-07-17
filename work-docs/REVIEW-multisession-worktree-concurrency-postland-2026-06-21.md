---
type: review
task_slug: multisession-worktree-concurrency
status: CHANGES_REQUESTED
created: 2026-06-21
scope: standalone comprehensive re-review of the LANDED per-task feature-branch concurrency model, focused on the newest unreviewed commit 394f86e (wrapup task-land wiring + scoped-commit contamination fix)
reviewers_invoked: [land-correctness, concurrency, security, template-wiring, migration-dataloss, adversarial-verifier]
consensus_method: reviewer + independent adversarial verifier (empirical reproduction)
grade: B
human_review_needed: true
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-worktree-concurrency
  computed_at: 2026-06-21
---

# REVIEW — post-land comprehensive review (per-task feature-branch concurrency)

## 🎯 Summary

**Consensus grade: B — CHANGES_REQUESTED.** Two **P1** defects survived independent
adversarial verification with end-to-end git reproduction. Both are *new* — no prior
REVIEW (2026-06-20 / p6 / p7) or existing test covers them, and both re-open the exact
**cross-session contamination class** that commit `394f86e` set out to close, on paths
that commit did not cover.

- Reviewed surface: `worktree.py` task_land/squash/cleanup/registry/fence + `cli.py`
  migration + `wrapup.md.j2` Step 7.7 wiring + stage preflight partials.
- Method: 5-dimension parallel review (12 raw findings) → per-finding adversarial
  verifier (KEEP/DEMOTE/REFUTE) with empirical git reproduction → 9 survived, 3 refuted.
- The 394f86e fix itself (scoped `git commit -- <touched>` + `--no-renames`) is **correct
  for what it targeted** (concurrent *staged whole-index* churn) and well-tested. The
  P1s are in adjacent, uncovered paths the fix exposed.

| P0 | P1 | P2 | P3 | Grade |
|----|----|----|----|-------|
| 0  | 2  | 4  | 3  | **B** |

## 🔍 Drift gate

All changes within PLAN-multisession-worktree-concurrency scope. `drift_verdict: clean`.

## ✅ Findings (verified — reviewer + adversarial verifier, most reproduced end-to-end)

### P1-1 — `_squash_path_set` quotes non-ASCII filenames → land permanently fails AND leaves staged contamination in base
- **File:** `src/harness_maker/worktree.py:3619` (`_squash_path_set`), consumed at `:3816` / `:3625`
- **Mechanism (reproduced):** `git diff --name-only --no-renames <mb> <branch>` runs with git's
  default `core.quotepath=true`, so a path like `café.md` comes back as the C-quoted literal
  `"caf\303\251.md"`. `git merge --squash` (3806) stages the *real* file, but `git commit -m msg -- <quoted-literal>` (3816) → `error: pathspec ... did not match` → rc1. `git commit` with a
  pathspec is all-or-nothing, so the **whole commit aborts** (even ASCII siblings are not committed).
  Control falls into `_scoped_conflict_cleanup`, whose `git reset`/`git checkout -f` *also* run
  against the quoted literal → no-op, and the untracked-sweep intersects real names against quoted
  names → empty. **Net:** (1) any task whose diff touches a non-ASCII/tab/newline filename can
  **never land** via `/hm:wrapup` (permanent rc1); (2) the squash's staged add is left
  **orphaned + staged in the shared base index** — the count:3 contamination class, swept by the
  next whole-index commit. The stderr even claims "base reset clean" — **false**.
- **Why it matters here:** this is user-harness code running on *arbitrary* projects, and
  harness-maker is i18n-by-design (Korean locale default-switchable). CJK/emoji filenames in a
  user's `work-docs/`/memory/source tree are normal, not exotic. (This repo itself has zero
  non-ASCII tracked filenames — which is why it scored A in prior reviews.)
- **Fix:** NUL-delimit enumeration so git never quotes — `git diff -z --name-only --no-renames`
  split on `\x00`; apply the same `-z` to `_untracked_files` (`git ls-files -z --others
  --exclude-standard`) so its set matches `touched`; pass raw paths to commit/reset/checkout
  (argv is list-form, no shell). Add a non-ASCII-filename regression fixture.

### P1-2 — squash-conflict cleanup destroys a concurrent session's STAGED work on a guard-forgiven path
- **File:** `src/harness_maker/worktree.py:3625-3645` (`_scoped_conflict_cleanup`), called from `:3818`
- **Mechanism (reproduced end-to-end):** the base-dirty guard `_has_user_dirty_state` (3750)
  **excludes** `.claude/` + `work-docs/` deliverables (via `_is_create_guard_harness_artifact`),
  so a concurrent session's *staged* `work-docs/PLAN-x.md` does **not** abort the land. If the
  landing branch **touches that same path**, `git merge --squash` aborts ("local changes would be
  overwritten"). The RuntimeError → `_scoped_conflict_cleanup(base, touched, pre_untracked)`;
  `touched` includes the colliding path, and the loop runs `git reset -q HEAD -- <touched>` +
  `git checkout -f HEAD -- <p>` with **no guard for tracked/staged pre-merge dirt** (only
  `pre_untracked` is protected). Result: (a) path-in-HEAD → concurrent staged content force-reset
  to HEAD; (b) path-not-in-HEAD (new deliverable both sides) → file becomes untracked then
  `unlink()`ed. Recovery is silent (dangling blob via `git fsck` until gc; new-path case deletes
  the working file outright).
- **Coverage gap (confirmed):** the existing conflict test only covers an *untracked* deliverable
  on a path the branch does **not** touch — never exercises this.
- **Fix:** capture pre-merge staged/dirty tracked paths (`git diff --cached --name-only`, minus
  harness artifacts) before the merge; **exclude** them from the reset/checkout loop, symmetric to
  how `pre_untracked` already protects untracked paths. Add a regression test where the branch
  *also* touches the same `.claude/`/deliverable path.

### P2-1 — scoped land commit reads WORKING-TREE content (inverse of the 394f86e fix)
- **File:** `worktree.py:3806-3816` (`task_land`)
- **Mechanism (reproduced):** `git commit -- <pathspec>` is **partial-commit mode** — git builds a
  temp index from HEAD + the **working-tree** blobs of the named paths, *ignoring* the staged index.
  A write to a touched path's base working tree in the window between `git merge --squash` (3806)
  and `git commit -- <touched>` (3816) is committed instead of the squash result. The merge fence
  is harness-process-only ("does not lock external editors", docstring 3628), dirty-base guard runs
  *before* the merge → window unguarded.
- **Reachability:** narrow — needs a human/Cursor editing the *base* worktree on a touched file in a
  sub-second window (harness sessions work in their own worktrees). Demoted P1→P2.
- **Fix:** commit the index, not the working tree — unstage the unrelated staged paths
  (`git reset -q HEAD -- <not-touched-staged>`) then plain `git commit -m msg`; OR add a post-merge
  blob re-check (abort rc1 if any touched path's working-tree blob ≠ its `:<path>` staged blob).
  Note: the cleaner index-commit fix interacts with P1-1 (no pathspec → no quotepath bug) — solving
  both together is attractive.

### P2-2 — legitimate content-equivalent land mis-routed to the conflict path → never converges
- **File:** `worktree.py:3786-3824` (`task_land`)
- **Mechanism (reproduced):** when base HEAD already contains the branch's change (plus more),
  `_branch_content_in_head` still reports a per-blob mismatch (full-file blobs differ) → `already=False`;
  `_squash_path_set` returns non-empty → the `touched==[]` guard doesn't fire; `git merge --squash`
  succeeds but **stages nothing** (3-way resolves to HEAD); `git commit -- <touched>` → rc1 "nothing
  to commit" → routed to `_scoped_conflict_cleanup` + rc1 "conflict?". The land **never converges**
  (re-runs reproduce nothing-staged) — branch + worktree + registry row leak; user told to resolve a
  non-conflict. No data loss (base stays clean).
- **Fix:** after the merge, check `git diff --cached --quiet -- <touched>`; if nothing staged, treat
  as already-landed and converge to teardown rather than failing the commit. Or distinguish "nothing
  to commit" from a real conflict in the except handler.

### P2-3 — Step 7.7 lands with no `--message`: user's why-message + Co-Authored-By discarded on every flag-on wrapup
- **File:** `src/harness_maker/templates/stages/wrapup.md.j2:422-426`
- **Mechanism:** Step 7 has the LLM craft a why-focused commit (Co-Authored-By) onto `hm/<slug>`;
  Step 7.7 calls `task-land <SLUG> <BASE>` with **no** `--message`; `task_land` (3734)
  `msg = message or f"chore({slug}): squash-land {branch}"`. `git merge --squash` makes no commit and
  the explicit `git commit -m` overrides MERGE_MSG, so the branch's message is never carried. After
  teardown (`git branch -D`) the only surviving ref (base HEAD) reads `chore(<slug>): squash-land
  hm/<slug>` — **no rationale, no attribution**. Fires on **every** flag-on Production wrapup (default
  True). Defeats this file's own contract (L11 / Quality Bar L468).
- **Fix:** pass `--message` from Step 7's message to Step 7.7, OR have `task_land` reuse the branch's
  last commit message (the latter is LLM-behavior-independent — preferred).

### P2-4 — loop-close wrapup carries its own preflight → conflicting `<WT>` → possible double-land / orphan `hm/<slug>`
- **File:** `src/harness_maker/templates/commands/hm/loop.md.j2:958-960` vs `wrapup.md.j2:50-53`
- **Mechanism:** `/hm:loop` works in an `execute-<uuid>` worktree (finalize owns its land). But the
  flag-on standalone `wrapup.md` begins with the preflight partial that runs `task-preflight <slug>`
  and treats *its* stdout as `<WT>`. Loop-close tells the LLM to "execute the wrapup stage … operate
  inside `<WT>`" with no instruction to skip wrapup's own preflight → two contradictory `<WT>`
  definitions. The Step 7.7 `hm/*` branch guard only protects the path where the LLM stays in
  `execute-<uuid>`; if it obeys wrapup's preflight it *creates* a fresh `hm/<slug>` worktree and
  Step 7.7 lands that while loop finalize separately lands the execute work — double-land of disjoint
  content + orphan branch. No-double-land relies entirely on LLM disambiguation (no code guard).
  (Empty-squash sub-claim refuted: `task_land` aborts rc1 on empty path set, so no empty commit — the
  real risk is orphan branch/worktree + memory double-land + operator confusion.)
- **Fix:** loop-close explicitly instructs wrapup to **skip its preflight and reuse the loop's `<WT>`**;
  or render the wrapup preflight as a no-op when a loop is active. Make the invariant testable.

### P3-1 — ADR-004 uuid-primary-identity safe-drop is dead code in the shipped wiring
- **File:** `worktree.py:3700-3717` (`task_land._drop_own_row`)
- **Mechanism:** neither `_cli_task_land` (3909) nor wrapup Step 7.7 passes `session_uuid`, so
  `own=None` always; rows are registered with the *ephemeral* create/preflight subprocess pid (dead by
  land time), so the drop always takes the `not _pid_alive` branch. The uuid-match protection is never
  exercised. **No harm today** (different-branch rows preserved; same-branch row's shared worktree is
  already torn down before the drop; `test_task_land_no_uuid_preserves_foreign_live_pid_row` confirms a
  live foreign pid is preserved). Latent invariant erosion only — fragile if a future change ever
  registers a long-lived live pid on a contended branch.
- **Fix (hardening):** plumb `_current_session_uuid` into the land + register the live stage pid.

### P3-2 — `git check-ignore -q <rel>` missing `--` separator (parity gap, dormant path)
- **File:** `worktree.py:3401` (`_copy_and_exclude_secrets`)
- **Mechanism:** line 3401 omits `--`, unlike the parity call at `:2201` (`-- entry`). Path dormant
  (no live caller passes `include`). Defense-in-depth / consistency.
- **Fix:** `_run(["git", "check-ignore", "-q", "--", rel], cwd=base)`.

### P3-3 — flag-on wrapup Step 6/7 lack `cd <WT>` (instruction-clarity)
- **File:** `src/harness_maker/templates/stages/wrapup.md.j2:311-350`
- **Mechanism:** Step 6/7 git add+commit blocks don't reference `<WT>`, while the preflight contract
  says operate inside `<WT>` → the base `git commit` is frequently empty on flag-on. **Not** data loss
  / strand (refuted: execute Step 5 finalize routes flag-on task worktrees to `_finalize_commit_not_stash`
  → `wip(execute)` on `hm/<slug>`; `task_land` step 3 `_capture_pending_in_worktree` lands any pending
  worktree work; STOP is scoped to quality-gate failures, not empty commits). Polish only.
- **Fix:** prefix flag-on Step 6/7 with `cd <WT> &&` (mirror the preflight contract) + a render test.

## 🧪 Refuted (recorded, not actionable)

Three concurrency findings about "session_uuid is a throwaway per-subprocess uuid defeating ADR-004"
were **refuted** by the verifier:
- The registry is **advisory coordination**, not the safety boundary — the merge fence (flock+O_EXCL)
  and the git-dirt guards are uuid-independent. Worst case is a missed/incorrect informational warning.
- `task_preflight` runs `reclaim_stale` **before** snapshotting, so a single user's sequential stages
  don't trip false collision warnings (the prior subprocess's pid is dead → row reclaimed first).
- `register_session` dedups by branch (one row per branch), and every `_drop_own_row` path runs after
  the shared worktree is already removed, so no live foreign session loses an on-disk worktree.

Residue: the docstring wording "session_uuid PRIMARY identity" is aspirational at the CLI boundary
(P3-1 captures the actionable hardening).

## 🤝 Theme

Both P1s + P2-1 cluster on one root cause: **path-set scoping correctness in `task_land`**. The
394f86e fix correctly stopped a *whole-index* sweep but introduced/left three path-handling edges:
quotepath encoding (P1-1), the conflict-cleanup not honoring the same guard-forgiveness the commit
path now relies on (P1-2), and pathspec-commit reading the working tree (P2-1). A single consolidated
fix — enumerate with `-z`, commit the **index** (not pathspec/working-tree) after unstaging
non-touched paths, and exclude pre-merge-dirty paths from cleanup — closes P1-1, P1-2, and P2-1
together and is the highest-leverage change.

## Applied fixes (consolidated patch — P1-1 + P1-2 + P2-1)

Per user direction, the three root-cause-clustered `task_land` path-set findings were fixed together
in one patch to `src/harness_maker/worktree.py` (no template change):

- **`_split_z` + `_staged_files` helpers added**; `_squash_path_set` and `_untracked_files` switched to
  `git ... -z` NUL-delimited enumeration → non-ASCII/control-char filenames are never C-quoted (**P1-1**).
- **`task_land` now commits the INDEX, not the working tree**: after `git merge --squash`, the
  concurrent session's pre-staged churn (`_staged_files(base) − touched`) is unstaged, then a plain
  `git commit` (no pathspec) records exactly the squash's touched paths. This removes the working-tree
  read (**P2-1**) and the pathspec-quoting failure (**P1-1**) at once, while still never sweeping a
  concurrent session's staged churn into the squash (the count:3 contract holds — verified by
  `test_task_land_does_not_sweep_concurrent_staged_base_churn`). The churn is preserved as working-tree
  content for its owning session.
- **`_scoped_conflict_cleanup` gained a `preserve` set** (= pre-merge staged paths); when a conflict
  collides on a guard-forgiven path the branch also touches, that path is excluded from the
  reset/checkout/unlink → the concurrent session's staged work is no longer clobbered (**P1-2**).

Regression tests added: `test_task_land_lands_non_ascii_filename_and_leaves_base_clean` (P1-1),
`test_task_land_conflict_preserves_concurrent_staged_same_path` (P1-2). Verification: full unit suite +
`ruff check` + `mypy --strict` all green; not committed (user owns the commit).

## Applied fix (P2-3 — squash-land message reuse)

Follow-on patch (same `worktree.py`, no template change), per user direction:

- **`_branch_tip_message(base, branch)` helper added**; `task_land` now defaults its squash message to
  `message or _branch_tip_message(...) or "chore(<slug>): squash-land <branch>"`. The default is the
  branch tip's curated commit message (wrapup Step 7's why-subject/body + `Co-Authored-By`), computed
  BEFORE the fence/`_capture_pending_in_worktree` so the tip is the wrapup commit, not a later
  `wip(execute): capture`. Explicit `--message` still overrides; generic placeholder is the last-resort
  fallback only. **LLM-behavior-independent** — no template/flag dependency.
- Regression test: `test_task_land_reuses_branch_tip_message_when_none_given` (subject + why-body +
  Co-Authored-By all carried; no `squash-land` placeholder).
- **Dependency note:** the why-message survives only if wrapup's Step-7 commit actually lands on
  `hm/<slug>` as the branch tip. The **P3-3** `cd <WT>` gap (Step 6/7 may commit in BASE) can leave the
  branch tip as a `wip(execute)` commit instead — fixing P3-3 closes that interaction. Tracked below.

## Applied fix (P2-2 — content-equivalent land never converges)

Follow-on patch (same `worktree.py`, no template change):

- After `git merge --squash`, `task_land` now checks whether the squash staged any of the branch's
  OWN paths (`_staged_files(base) & set(touched)`). When it staged **nothing** — the 3-way merge
  resolved every touched path to base HEAD content (the branch's delta is already present in HEAD via a
  prior land / cherry-pick / subset edit) — it **converges to teardown** (writes the landed-marker,
  tears down branch/worktree/registry row, rc0) instead of letting `git commit` fail "nothing to
  commit" and routing to the conflict path. The old behavior NEVER converged (every re-run re-resolved
  to nothing-staged) → branch + worktree + registry row leaked indefinitely. The detection uses git's
  ACTUAL 3-way merge result, which is strictly more accurate than the `_branch_content_in_head` per-blob
  heuristic that missed this case. Any concurrent churn is left staged exactly as found (index untouched).
- Regression test: `test_task_land_converges_when_branch_change_already_in_head` (branch change already
  in HEAD + an unrelated HEAD change so full blobs differ → rc0, no new commit, no branch/worktree/row leak).

## Applied fix (P2-4 — loop-close `<WT>` ambiguity → double-land / orphan)

Template fix (`templates/commands/hm/loop.md.j2`, loop-close step 3 — option (a), advisory per ADR-005):

- The loop-close "Run wrapup ONCE" step now explicitly instructs the LLM to **SKIP wrapup's own
  worktree preflight** (`task-preflight` → a fresh `hm/<slug>` worktree) and **SKIP wrapup's Step 7.7**
  (`task-land`), reusing the loop's own `<WT>` (the `execute-<uuid>` worktree). The loop's `finalize`
  remains the sole land owner. This removes the two-contradictory-`<WT>` race (no code guard was viable:
  loop-close removes `.hm-loop-active` BEFORE wrapup runs, so a marker-keyed guard could not fire).
- Render test added: `test_loop_close_wrapup_reuses_loop_worktree_not_a_task_worktree` (asserts the
  SKIP-preflight + SKIP-Step-7.7 instructions are present in rendered `loop.md`).
- Snapshots regenerated (loop.md body_sha across all 8 fixtures); verified the diff is loop.md-only.
- **Further hardening (not done, optional):** a `.hm-loop-active`-independent code guard in
  `worktree_preflight.md.j2` was rejected because the marker is already removed at loop-close; the
  advisory instruction is the consistent ADR-005 mechanism.

> **⚠️ Concurrent-session note (real, encountered during this work):** while fixing these, an
> **independent Claude session was actively editing the shared working tree** (autopilot work +
> `templates/agents/_partials/stage_end_summary.md.j2`). That session's in-flight `stage_end_summary`
> change breaks the prod (and later all 8) `test_synthesize_snapshot` cases — **proven unrelated to this
> patch**: stashing only their file makes all 12 snapshot cases pass. This patch's snapshot regen was
> done with their file stashed, so the regenerated snapshots contain only the loop.md change. See the
> commit-coordination note below.

## Applied fixes (P3 batch — P3-1 + P3-2 + P3-3)

- **P3-2** (`worktree.py:_copy_and_exclude_secrets`): added the missing `--` to `git check-ignore -q -- rel`,
  matching the parity call. One-char, zero behavior change in the dormant path; hardens it pre-wiring.
- **P3-1** (`worktree.py:SessionRow` docstring): the "proper" fix (a stable per-session UUID threaded
  through `task-create`/`-preflight`/`-land`) is the **already-deferred dirname-embedded-UUID refactor** —
  `_current_session_uuid` is explicitly project-scoped (REVIEW round 1 P0-MANUAL2) so threading it would
  REGRESS cross-session isolation. The shipped pid+worktree heuristic is already safe (drops only a
  same-branch row whose worktree is gone; preserves live foreign-pid rows). Action taken: corrected the
  misleading "`session_uuid` is the PRIMARY identity" docstring to describe the CLI-boundary reality and
  point at the deferred refactor. **No behavior change** (none is safe to make here without the refactor).
- **P3-3** (`wrapup.md.j2` Step 6/7): flag-on now prefixes the `git add` loop and `git commit` with
  `cd <WT> &&` (via a `wt_prefix` Jinja var) so the staging + commit land on the `hm/<slug>` task branch
  instead of the base repo's empty index. This **completes P2-3** — the curated commit now reliably
  becomes the branch tip whose message `task_land` reuses. Flag-off keeps the bare base-repo commit
  byte-for-byte. Render tests added: `test_wrapup_commit_runs_inside_worktree_when_flag_on` /
  `..._in_base_when_flag_off`. Snapshots regenerated (wrapup.md + stages/wrapup.md + the 4 fused
  `*-wrap*` commands that embed the wrapup stage); verified the diff is wrapup-only + loop.md (P2-4),
  no concurrent-session contamination.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 2×P1, 4×P2, 3×P3 | — |
| 2 (patch) | A*    | P1-1, P1-2, P2-1 (3) | 3×P2 (P2-2/P2-3/P2-4), 3×P3 | 0 |
| 3 (patch) | A*    | P2-3 (1)      | 2×P2 (P2-2/P2-4), 3×P3 | 0 |
| 4 (patch) | A*    | P2-2 (1)      | 1×P2 (P2-4), 3×P3 | 0 |
| 5 (patch) | A*    | P2-4 (1)      | 3×P3 (P3-1/P3-2/P3-3) | 0 |
| 6 (patch) | A*    | P3-1, P3-2, P3-3 (3) | 0 | 0 |

\* Grade A counts only **consensus-passed P0/P1**; both P1s are fixed, leaving 0 P0 / 0 P1.

Final grade (post-patch): **A** (P0=0, P1=0). **All findings resolved or dispositioned** (P3-1 = accurate
docs + deferred-refactor pointer; P3-2/P3-3 = fixed). Status: **APPROVED**. The only deferred item is the
substantive dirname-embedded-UUID refactor underlying P3-1, which predates this review.

## Commit-coordination note

My change set (all verified green in isolation): `src/harness_maker/worktree.py`,
`src/harness_maker/templates/commands/hm/loop.md.j2`, `tests/snapshot/*.expected.yaml` (×8, loop.md
hash only), `tests/unit/test_worktree_task_land.py`, `tests/unit/test_loop_template_render.py`.

A **concurrent session** holds uncommitted WIP (`autopilot*.py`, `cli.py`, `workflow_fuse.py`,
`stage_end_summary.md.j2`, autopilot tests). Per `concurrent-sessions-land-coordination`: committing my
files alone right now leaves `test_synthesize_snapshot` red (their `stage_end_summary` change is not in
my regen). Recommended: land in a clean window — either after their WIP commits (then re-run
`tests/snapshot/regenerate.py` once so the 8 snapshots carry BOTH changes), or commit my source now and
defer the shared snapshot regen until their change lands. human_review_needed: **false** for the patch
correctness; the only open item is commit sequencing with the other session.
