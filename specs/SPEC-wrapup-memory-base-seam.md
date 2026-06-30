---
type: spec
task_slug: wrapup-memory-base-seam
status: draft
created: 2026-06-30
tags: [harness-maker, spec, python, wrapup, worktree, memory]
tier: 2
test_framework: pytest
research_doc: "[[RESEARCH-wrapup-memory-base-seam]]"
summary: "Flag-on wrapup folds base-written memory tiers into the single squash commit after task-land"
---

# SPEC — wrapup memory-at-base seam fix

## 🎯 Intent

In the per-task feature-branch model (`worktree.feature_branch_workflow: true`), `/hm:wrapup`
runs inside `.worktrees/<slug>/` but `memory_md` writes the human memory tiers (`wiki.md`,
`failures.md`, `session/<today>.md`) to the BASE repo. Step 6's `cd <WT> && git add
.claude/memory/` therefore stages the worktree's (unchanged) tree and `task-land` preserves but
never commits the base memory — so **wrapup memory is silently never committed** on the flag-on
path. This fix makes the memory ride the single wrapup commit.

## 🌅 Outcomes

After a flag-on `/hm:wrapup`, the human memory tiers written during that wrapup are present in
**exactly one** new commit on the base branch — the same squash commit that carries the code —
with no extra commit and no leftover uncommitted memory dirt in the base working tree. Re-running
the fold is a safe no-op. The flag-off path is unchanged.

## 📋 In-Scope Scenarios

### S1: flag-on wrapup commits memory in the single squash commit
**Given** a flag-on harness whose `/hm:wrapup` has written `wiki.md` / `failures.md` /
`session/<today>.md` to the BASE `.claude/memory/`, and `task-land` has just created the squash
commit (code) on the base branch HEAD
**When** the memory-fold step runs from the base repo
**Then** the base branch HEAD commit additionally contains the modified memory tier blobs
**And** exactly one new commit exists on base relative to the pre-wrapup base tip
**And** the base working tree has no uncommitted `.claude/memory/` changes left over

### S2: fold is idempotent on re-run
**Given** the memory tiers are already committed into HEAD (a prior fold ran) and the base
working tree has no `.claude/memory/` changes
**When** the memory-fold step runs again
**Then** no new commit is created and HEAD is unchanged
**And** the step exits 0 (success, no-op)

### S3: force-add beats a blanket `.claude/` gitignore (dogfood)
**Given** a base repo whose `.gitignore` blanket-ignores `.claude/` but `wiki.md` / `failures.md`
are force-tracked, and those tracked files were modified during wrapup
**When** the memory-fold step stages the tiers
**Then** the modified tracked memory files are staged and committed (the fold uses `git add -f`),
not silently skipped

### S5: fold refuses an unexpected amend target
**Given** the base HEAD is NOT the expected fresh squash (a converge/no-op land) OR the base index
has staged content outside the memory tier pathspec
**When** the memory-fold helper runs with `--expect-head <fresh-squash-sha>`
**Then** it returns non-zero without amending — HEAD is unchanged and no foreign content is folded

### S4: flag-off path unchanged
**Given** a flag-off harness (`feature_branch_workflow: false`)
**When** `/hm:wrapup` renders
**Then** the memory-fold step is NOT emitted (it is gated on `feature_branch_workflow`)
**And** the existing flag-off behavior (wrapup runs in base; Step 6/7 commit memory there) is
untouched

## 🚫 Non-Goals

- Re-architecting `memory_md` to write into the worktree (rejected — memory is intentionally
  base-shared, ADR-001/002; the H1 flock is base-keyed).
- Making `task-land` sweep arbitrary base dirt into its squash (re-opens the count:3
  contamination — the fold targets ONLY the explicit human memory tier paths).
- Fixing the flag-OFF new-untracked-session-file `git add` skip (dogfood-specific; downstream
  harnesses do not blanket-ignore `.claude/`).
- Committing the machine memory tiers (`semantic/`/`episodic/`/`profile/`) — those stay churn.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | project standard |
| Language | Python 3.12, mypy --strict, ruff | CLAUDE.md tooling lock |
| Commit count | exactly one new commit per flag-on wrapup | existing wrapup quality bar |
| Fold mechanism | `git add -f` known tier paths + `git commit --amend --no-edit` from base | preserves task-land's reused message; beats dogfood gitignore |
| Idempotency | re-run with clean memory = no-op exit 0 | wrapup/land may re-run after a crash |
| Tier scope | `wiki.md`, `failures.md`, `session/<today>.md` only | bounded set; never arbitrary base dirt |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_fold_memory_into_squash_commit` |
| S2 | unit | `test_fold_memory_idempotent_noop` |
| S3 | unit | `test_fold_memory_force_adds_gitignored_tracked_tiers` |
| S4 | unit (render) | `test_wrapup_memory_fold_gated_on_feature_branch_flag` |
| S5 | unit | `test_fold_refuses_unexpected_head_or_foreign_staged` |

## 🔬 Acceptance Criteria

### AC-001: flag-on wrapup folds memory into the single squash commit
The fold helper, run from base after `task-land`, leaves the modified human memory tiers in the
base-branch HEAD commit AND keeps the new-commit count at exactly 1 relative to the pre-wrapup
base tip (maps S1).

### AC-002: memory fold is idempotent on re-run
Running the fold helper a second time with no `.claude/memory/` changes creates no commit, leaves
HEAD unchanged, and exits 0 (maps S2).

### AC-003: fold force-adds gitignored tracked memory tiers
In a repo whose `.gitignore` blanket-ignores `.claude/` but with force-tracked `wiki.md` /
`failures.md`, the fold stages and commits the modified tracked tiers via `git add -f` rather than
silently skipping them (maps S3).

### AC-004: memory fold step is gated on the feature-branch flag
The rendered wrapup emits the memory-fold step only when `worktree.feature_branch_workflow` is on;
the flag-off render does not contain it (maps S4).

### AC-005: fold refuses an unexpected HEAD or foreign staged content
The helper amends ONLY when `HEAD == --expect-head` (the fresh squash) AND nothing outside the tier
pathspec is already staged; otherwise it returns non-zero WITHOUT amending — HEAD unchanged, no
foreign content folded (maps S5).

## ❓ Open Questions

(For `/hm:plan` to lock as ADRs — these are HOW decisions, not WHAT:)
1. Exact home of the fold logic: a new `worktree` CLI subcommand (e.g. `commit-base-memory
   <base>`) vs folding into `task-land`'s tail. (Separate subcommand preferred — keeps
   task-land single-responsibility.)
2. Partial-failure semantics: if the `--amend` fails (pre-commit hook, signing) after the squash
   already landed, what state is surfaced and is it retry-safe?
3. How the wrapup template invokes the helper at Step 7.7 (after `task-land`, cwd=base) and
   passes the slug/date for the `session/<today>.md` path.

## 🔍 Refinement Decisions

- Task-driven, light interview (RESEARCH already produced the recommended direction).
- Locked: single-commit fold via amend (S1) over a separate base commit — honors the existing
  "exactly one commit per wrapup" quality bar (Interview Q1).
- Locked: flag-on only; flag-off new-session-file skip is a non-goal (Interview Q2).
