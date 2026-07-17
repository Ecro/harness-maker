---
type: research
task_slug: multisession-worktree-concurrency
status: complete
created: 2026-06-20
tags: [harness-maker, research, git-worktree, concurrency, stash, branching]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://code.claude.com/docs/en/worktrees
  - https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution
  - https://github.com/jj-vcs/jj
  - https://www.panozzaj.com/blog/2025/11/22/avoid-losing-work-with-jujutsu-jj-for-ai-coding-agents/
  - https://engincanveske.substack.com/p/running-parallel-agents-in-cursor
  - https://dora.dev/capabilities/trunk-based-development/
  - https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/
related_docs:
  - "[[PLAN-worktree-cross-session-data-loss-defense]]"
  - "[[PLAN-worktree-base-artifact-pollution]]"
  - "[[PLAN-worktree-deliverable-blocks-create]]"
  - "[[PLAN-worktree-finalize-stash-isolation]]"
  - "[[PLAN-p6-p7-worktree-finalize]]"
summary: "Lead with a first-class per-task feature branch (B), staged on top of leak-fix hardening (D); concurrency isolated by branch, not by racing onto shared main"
---

# RESEARCH — Multi-session worktree concurrency model

## 🎯 Recommended Direction

**Introduce a real, user-visible per-task feature branch (`hm/<slug>`) as the spine of a workflow — Approach (B) — but ship it on top of leak-fix hardening (Approach D) as a mandatory Phase 0.**

The user's pain is *user-facing workflow safety* ("doesn't feel safe", "is feature-branch discipline the answer?"), not internal plumbing. Today there is **no user-facing feature branch at all**: `create()` makes a disposable `execute-<uuid>-<ts>` branch and `merge()` squash-stages onto *whatever branch the base HEAD is on* (`worktree.py:268-323, 1303-1304`). That is the root of the felt inconsistency — concurrency is "race onto a shared `main`", and "sometimes a feature branch" is really "whatever branch I happened to be on by accident."

A per-task branch is the only direction that yields **one model that behaves identically whether two sessions are at the same or different stages**: each task owns a branch, concurrency is isolated *by branch* instead of by racing onto shared `main`, and the one genuinely **unsafe** scenario today — Session B's `/hm:wrapup` committing Session A's staged-but-uncommitted diff under B's message — becomes structurally impossible.

The main value is **user-facing safety**, not maintainability. But (B) must **not** ship before (D)'s leak fixes: the live repo already carries **76 leaked `execute-*` branches against 1 landed-marker** and the only janitor runs at `worktree create` time — make branches first-class and long-lived on top of that and the backlog compounds badly.

> ⚠️ This is *informational*. `/hm:plan` makes the binding architectural decision via interview + ADRs.

## 🔍 Refinement Decisions

- `--deep` not set → no Phase 0 interview. Topic was concrete enough (the user gave a precise pain description).
- **Discovery lens:** primarily **User-workflow / product opportunity** (reconstruct the actual entry-point isolation matrix) + **Technical architecture** (worktree/stash/branch lifecycle in `worktree.py`) + **Risk/compliance** (residual failure modes). External best-practice was a supporting lens (git-worktree / jj / trunk-based 2026 patterns), not the only one.
- **Mid-research scope relaxation from the user:** "worktree 생성하고, 다시 합치는 단계도 조정해도 돼. 필요하다면" — the **create and finalize/merge steps are explicitly in scope to change.** This promotes (B) and (C) from "theoretical alternatives" to fully buildable, and removes the "don't touch the hardened finalize core" guardrail as a hard constraint (it becomes a cost to weigh, not a veto).

## 🛠️ Approaches Found

### (A) "Every stage isolates" — universal worktree-per-session

| Field | Content |
|-------|---------|
| Assumption | Isolation should be per-session, not per-stage; every `/hm:` session takes a worktree at its first mutating step. |
| Evidence | Today only `execute`/`loop` actually create a worktree; `plan` scope is **dead code** (`plan.md.j2` has zero `worktree create`), `research/spec/review/wrapup/verify` + all manual edits run in-place. Widening `worktree.scope` to all stages wires `create` into every template. |
| Trade-off | Re-pays env/secret setup per stage; **breaks review** (review reads the *base* `git diff`, `review.md.j2:32` — an isolated review sees a worktree without the staged base diff); N stages × N sessions multiplies stash-queue pressure against the `≥2` queue-guard → `create` aborts far more often. |
| Compatibility | Builds on the decided scope mechanism but **contradicts** two decided invariants: "wrapup is the commit owner on base" and "keep-base-clean so the 5 layers go dormant" (more worktrees = more finalize churn, not less). |
| Risk | **high** — largest surface, fights two decided invariants, and does **not** fix the shared-base land target (every isolated stage still squash-merges onto one shared base). |

### (B) "Feature-branch spine" — a real per-task branch a whole workflow lives on  ⭐ recommended

| Field | Content |
|-------|---------|
| Assumption | The unit of identity is the *task* (`hm/<slug>`), not the worktree. A whole workflow (research→wrapup) commits onto that branch; worktrees are ephemeral compute *under* it; landing to trunk is an explicit integrate step, never a stash-pop onto shared `main`. |
| Evidence | Matches the 2026 default of Cursor `/worktree` and Claude Code `claude -w`: both create a **named branch per task** (`tool_comparisons`). Aligns with DORA short-lived-branch / trunk-based guidance (merge small & frequent). Directly closes the unsafe `cross_session_scenarios[4]` (B's wrapup committing A's diff) and `[7]` (finalize onto wrong current branch). |
| Trade-off | Workflow-model change, not a bug fix — every stage template + loop driver + wrapup commit logic must learn "which branch is this task on?"; needs a branch registry/claim convention; needs a land policy (PR vs ff vs squash) and a divergence/rebase story; the 5-layer stash defense doesn't vanish (it still guards the *within-task* worktree finalize onto the feature branch) — you keep the machinery **and** add a branch layer. |
| Compatibility | Supersedes the confirmed-by-code AXIS-2 "no feature branch" status quo (a *state*, not a locked ADR). Composes with decided landed-marker / WIP-commit (those become within-task plumbing). Tension with decided "wrapup single commit on base." |
| Risk | **med-high** — highest user-facing payoff, largest conceptual change, reopens branch-lifecycle decisions `/hm:plan` must lock. |

### (C) "Commit-not-stash" — lean into the WIP commit, retire stash as the durability boundary

| Field | Content |
|-------|---------|
| Assumption | The durable artifact is *already a commit* (`wip(execute): capture uncommitted work` on the worktree branch, `worktree.py:350`). Make it the primary finalize mechanism; demote the deferred `.hm-finalize-stash-*` ref-file queue from a load-bearing finalize↔wrapup handoff to a transient detail (or eliminate it). |
| Evidence | Borrows jujutsu's "working copy IS a commit / `jj op log` + `jj undo`" durability — the most crash-resilient model for AI agents (`patterns[5]`, panozzaj.com, github.com/jj-vcs/jj). Closes the cross-session stash-pop SKIP that strands another session's WIP (`risks[2]`) and the stash-queue fragility. |
| Trade-off | Orthogonal to the user's *mental-model* complaint (doesn't touch worktree on/off inconsistency or the feature-branch question). Produces noisy WIP commits needing a squash/cleanup sweep. Removing the deferred-stash path risks regressing the decided transparent-stash-isolation contract (ADR-001/003) and its two-class pop-failure handling. |
| Compatibility | **Most compatible** — *extends* a decided mechanism (WIP commit + landed-marker) rather than replacing one; matches external rec "treat the stash as a transient detail, not the durability boundary." But primarily **internal maintainability**. Best folded into (B) as within-task plumbing. |
| Risk | **med** — internal-only, but touches the hardened stash core. |

### (D) "Status-quo hardening" + session-aware preflight  (Phase 0 of the recommendation)

| Field | Content |
|-------|---------|
| Assumption | Keep today's model (isolation ⟺ execute-or-loop, land onto current base); fix the concrete leaks and make the inconsistency *legible* rather than silent. |
| Evidence | Three targeted fixes: (1) drain the **76-branch leak** by moving `prune-branches` reaping off the create-only trigger (e.g. wrapup / `/hm:health`); (2) a **continuous** (not just create-time) dirty-base / foreign-session check so a concurrent `/hm:review`/`/hm:wrapup` can't silently commit over an open execute worktree; (3) a **session-aware preflight** that lists active `.hm-loop-*` markers + open worktrees + pending stash refs and warns "Session A holds execute worktree X; running /hm:wrapup now will commit its staged diff — proceed?" |
| Trade-off | Does **not** give a single uniform model — isolation stays conditional, so the conceptual inconsistency persists; it is made *visible*, not *removed*. The preflight is advisory (LLM-honored), not a hard kernel. |
| Compatibility | **Fully compatible** — pure additive hardening, re-proposes nothing; the branch-drain is literally the decided `prune-branches --force` moved to a second trigger. |
| Risk | **low.** |

**Recommended composition:** (D) as Phase 0 (leak fixes + legibility, low-risk, immediately useful) → (B) as the spine (user-facing model) → (C) folded into (B) as the within-task durability mechanism. (A) is **not** recommended.

## ⚠️ Pitfalls

- **The 76-branch leak is real and live-verified** (76 branches / 1 `refs/hm-landed/v1/*` / 1 stale `.hm-finalize-stash-execute-85d4064c848f-*`). `_branch_content_in_head` (`worktree.py:1564-1566`) cannot recognize a squash-merge as landed (new blob identities), so markerless legacy branches PRESERVE+warn **forever**, and `prune_stale` runs **only** at create-time (`worktree.py:1922`). Any model that makes branches first-class inherits this unbounded growth — plus a cry-wolf warning wall that trains the operator to ignore the very warnings meant to flag genuine unmerged work.
- **Cross-session commit capture is the one *unsafe* scenario today.** After A's execute finalize stages onto base (no commit), B's `/hm:wrapup` can't distinguish A's staged diff from its own and commits it under B's message. Bare `git commit` in wrapup (`wrapup.md.j2:337`, no `-a`) commits whatever is in the index.
- **The scope-guard only fences the finalize *merge* boundary** — work landing on base while NO finalize is running (a concurrent `/hm:review` auto-fix or `/hm:wrapup` commit) is invisible to it (`_verify_scope_subset`, `worktree.py:952-995`). This is the recurrence path for the contamination incident (count:3).
- **`worktree_gate` weakens under concurrency:** it unions ALL active `.hm-loop-*` markers, so with two sessions a Write into *either* worktree is allowed; Bash-redirect writes (`>`, `sed -i`, `python -c open()`) are NOT gated at all (`worktree_gate.py:30-33,64-92,149`). Enforcement is weakest exactly when concurrency makes it matter most.
- **Stash-pop SKIP strands WIP and the ownership check is admitted-unreliable in-code** — `_owned_session_uuids` reads markers that are "shared filesystem state across all sessions" (`worktree.py:2639-2649`); empty `HM_OWNED_SESSION_UUIDS` falls back to the vulnerable marker-exists check (`worktree.py:2668`); a stranded preserved-but-never-popped WIP can be silently dropped if a later in-HEAD judgment is a false positive.
- **review→wrapup index drift:** review auto-fix Edits land *unstaged* in the working tree; wrapup `git add`s only a deliverable allowlist (`wrapup.md.j2:311`) — a review fix to a not-already-staged source file is silently dropped from the commit; no `staged-index == reviewed-tree` reconciliation exists.
- **Runtime-isolation gap:** worktrees isolate files, NOT ports/DBs/`.env` (penligent.ai). Any multi-session model running dev servers / tests-against-DB needs per-session ports + DBs — warn users.
- **`.worktreeinclude` for secrets:** a fresh worktree lacks gitignored `.env`/secrets — sessions silently break without a copy mechanism (now an official Claude Code feature, code.claude.com/docs/en/worktrees).
- **Never `git stash drop` without a `git stash show -p` preview** (already decided ADR-008) — any new land/cleanup path must keep this contract and the grep-assert marker.
- **Enforcement ceiling:** under `--dangerously-skip-permissions`/bypassPermissions + default deny-empty `settings.json`, every CLI guard and the ADR-008 contract are behavioral conventions, not hard kernels. A model that *feels* safe can still be stepped around.

## ❓ Open Questions

1. **Branch granularity: per-task or per-stage?** A task spans research→wrapup; is `hm/<slug>` claimed at task start (warm, drift-prone) or per workflow-invocation? How does a fused `plan-exec-rev` map onto it?
2. **Land mechanism: PR, fast-forward, or squash-to-trunk?** Solo public repo, push is backup-only (CLAUDE.md Git policy). DORA favors small frequent squash-to-trunk; PR adds GitHub round-trips.
3. **How do concurrent sessions coordinate — lockfile, registry, or naming convention?** Today markers are shared filesystem state and `worktree_gate` *unions* them. Branch-name claim + a registry file is the candidate; must define claim / release / stale-reclaim.
4. **Does wrapup still own "the single commit," and onto which branch?** Reconcile with decided wrapup-commits-on-base. Feature-branch wrapup commits onto `hm/<slug>`, then a separate integrate step — define that step's owner.
5. **Fate of the deferred base-dirty stash queue under feature branches.** If sessions no longer share base dirt, does `.hm-finalize-stash-*` + `post-commit-pop` become dead code (folding in (C))? Or kept as a net? Touches decided ADR-001.
6. **Manual edits + `git checkout -b` interplay.** If a user manually branches (the only way to get feature behavior today), does the spine adopt that branch or conflict with it? Define detection.
7. **Backfill the 76 legacy branches** — auto-`prune-branches --force` (markerless+diverged-blind, data-loss-adjacent) vs. one-time human-reviewed drain. Lock the trigger (wrapup? health? both?) so create-time-only never recurs.
8. **Hard kernel or advisory?** Under bypass mode + default deny-empty settings, all CLI guards are advisory. Decide whether the feature-branch land step gets a real hook backstop or stays prose-discipline.

## 📚 Sources

**Internal (live-verified against this repo):**
- `src/harness_maker/worktree.py` — 268-323 (`create`), 350 (WIP-commit), 952-995 (scope-guard), 1303-1329 (`merge --squash`), 1564-1566 (content-gate), 1609 (landed-marker), 1648-1735 (`prune_stale`), 1922 (create-time-only prune), 2531-2715 (`post-commit-pop`), 2842-2859 (`prune-branches`)
- `templates/stages/{execute,review,wrapup,plan,research,spec,verify}.md.j2`, `src/harness_maker/worktree_gate.py`, `.claude/harness.yaml:135-136` (`scope: [execute, plan]`)
- Live git state: 76 `execute-*`/`plan-*` branches, 1 `refs/hm-landed/v1/*`, 1 stale `.hm-finalize-stash-*`

**External:**
- https://code.claude.com/docs/en/worktrees — `claude -w`, `.worktreeinclude`, `git worktree lock`, conditional cleanup, `worktree.baseRef`
- https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution — worktree + sparse-checkout for large repos
- https://github.com/jj-vcs/jj , https://www.panozzaj.com/blog/2025/11/22/avoid-losing-work-with-jujutsu-jj-for-ai-coding-agents/ — jj auto-snapshot, `jj op log`/`jj undo`, snapshot-on-hook
- https://engincanveske.substack.com/p/running-parallel-agents-in-cursor , medium/dev.to Cursor `/worktree` writeups — named-branch-per-agent, `/apply-worktree`, `/best-of-n`
- https://dora.dev/capabilities/trunk-based-development/ , atlassian / mergify / launchdarkly — short-lived branch-per-task, merge-fast guidance
- https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/ — runtime (ports/DB/env) isolation gap
- coreui.io / baeldung — dropped-stash recovery via reflog/fsck (~90-day gc window)

## 🔗 Related Internal Docs

- [[PLAN-worktree-cross-session-data-loss-defense]] — the 5-layer defense (ADR-001..008); the contamination incident (count:3) origin
- [[PLAN-worktree-base-artifact-pollution]] — keep-base-clean / churn-isolation; ref-drain policy
- [[PLAN-worktree-deliverable-blocks-create]] — landed-marker (ADR-003), `prune-branches` CLI (ADR-004), deliverable create-guard exemption
- [[PLAN-worktree-finalize-stash-isolation]] — transparent stash isolation, deferred-stash ref handoff, two-class pop-failure
- [[PLAN-p6-p7-worktree-finalize]] — de-risk decision, orphan-branch sweep in `prune_stale`, merge-fence boundary
- [[PLAN-loop-mid-stop-and-review-skip]] — Gate 0 receipts, loop-mode plan, per-iter PLAN handling
