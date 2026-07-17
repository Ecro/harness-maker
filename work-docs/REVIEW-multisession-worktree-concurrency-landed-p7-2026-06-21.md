---
type: review
task_slug: multisession-worktree-concurrency
status: APPROVED
created: 2026-06-21
scope: standalone independent re-review of LANDED Phase 7 (main c2b7a1f)
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: k-of-3
grade: A
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-worktree-concurrency
  computed_at: 2026-06-21
codex_status: invoked
---

# REVIEW — standalone independent re-review of landed Phase 7 (main `c2b7a1f`)

## 🎯 Summary

**Consensus grade: A — APPROVED.** Every finding is single-source (no two
reviewers surfaced the same issue), so zero consensus-passed P0/P1 → A. BUT this
independent pass earned its keep: the **Codex heterogeneous voter caught a real
doc-accuracy defect both Claude reviewers missed** (same pattern as Phase 6.1).
Reviewer standalone takes: code A (1×P3), security A (1×P2), Codex (1 medium + 1 low).

## 🔍 Drift gate
All 4 changed files within Phase 7 scope. `drift_verdict: clean`.

## 📝 Manual-only findings (single-source; real)

### MEDIUM (Codex) — docs over-claimed wrapup auto-land — **FIXED**
CLAUDE.md (L225) + MANUAL_CHECKLIST C10 stated `/hm:wrapup` calls `task-land` to
auto squash-land. **Verified false**: `rg "task-land" src/harness_maker/templates`
= 0 — no stage template invokes `task-land`; wrapup does normal `git commit` +
`post-commit-pop` + `drain`. The `task-land` CLI exists (Phase 4) but the wrapup
template **wiring is missing** — a real Phase-4 gap my Phase-7 docs accidentally
asserted as a working guarantee. **Fix applied**: CLAUDE.md L225 now states the
CLI is the entry point + flags the wiring gap as a follow-up; C10 reframed to test
the `task-land` CLI directly (not auto-wrapup). **Follow-up (real feature gap):
wire flag-on `task-land` into the wrapup stage template + a render/flow test.**

### LOW (Codex) — Production/Side flag-default wording — **FIXED**
CLAUDE.md L217 said "default True=Production / False=Side". Side does NOT render
`feature_branch_workflow: false` — it OMITS the key (`test_side_new_default_flag_absent`),
and key-absence is itself the migration signal. **Fix applied**: reworded to
"Production defaults True; Side omits the key (isolation off)".

### P2 (security) — primary base uses `.exists()` not `_is_git_repo` (pre-existing)
`_git_dirt_blocker` re-checks `(base/'.git').exists()`; the PRIMARY `target`
reaches it without the authoritative `_is_git_repo` gate that `_load_sibling_dirs`
applies to siblings. **Not exploitable** (a planted `.git` file → `git status`
raises → defers, fail-closed) and **pre-existing** (the old inline primary probe
used the same `.exists()`; my refactor preserved it byte-identical). Cosmetic
defense-in-depth inconsistency. **Disposition: not changed** (pre-existing,
fail-closed-safe). Optional polish: gate primary on `_is_git_repo` for symmetry.

### P3 (code) — no primary/sibling dedup → duplicate warning text (pre-existing)
`enablement_preflight` builds `bases = [(target,""), *siblings]` without dedup; a
sibling resolving back to the primary is scanned (and warned) twice. The
post-commit-pop path dedups via `dict.fromkeys`; `_load_sibling_dirs`'s docstring
claims dedup is "by callers" but this caller doesn't. Decision-correctness
unaffected (read-only, `if blockers:` truthiness, fail-closed). Cosmetic.
**Disposition: not changed**. Optional polish: `dict.fromkeys([target.resolve(),
*resolved_siblings])`.

## 🟢 Cleared (multi-reviewer agreement)
- Primary parity byte-identical (old inline vs `_git_dirt_blocker`, `label=""`).
- READ-ONLY invariant holds; never mutates git.
- Fail-closed per base: any `git status` RuntimeError → defer (never silent-clean).
- Strictly-stricter: blockers only ADDED, none removed; flip only on empty list.
- Both new tests genuinely RED on pre-change code; not tautological (assert `sib.name`).
- `sib.name` interpolation: display-only, from a `.resolve()`d + `_is_git_repo`-gated path — no injection/traversal.
- CLAUDE.md CLI/identifier claims verified (subcommands, registry, lock, `hm/`, landed-marker).

## ⚠️ Escalation (security-reviewer, on the deferred data-loss bug)
The deferred `create_time_prune` landed-marker bug (stage-only writes a marker →
prune deletes the recovery branch) lives on the **create-time prune path that runs
on EVERY `worktree create` for already-migrated Production users** — independent of
this PR's flip gate. Same failure class as the count:3 incidents. The follow-up
plan should carry **explicit P0/P1 + a RED-test-stays-red CI gate**, not a soft
"follow-up", to avoid becoming the 4th instance of the same absent-defense pattern.

## Verdict
**APPROVED (consensus grade A).** Code change is correct, read-only, fail-closed,
strictly-stricter. The two verified-real doc defects (Codex) are FIXED. Two
cosmetic pre-existing code findings (P2/P3) left as documented optional polish.
Two real follow-ups surfaced for dedicated plans: (1) wire `task-land` into wrapup;
(2) the stage-only landed-marker data-loss bug at P0/P1 with a CI gate.
