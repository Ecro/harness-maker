---
type: review
task_slug: layer3-per-session-ownership
status: CHANGES_REQUESTED
created: 2026-06-21
reviewers_invoked: [code-reviewer, concurrency-reviewer, codex]
consensus_method: k-of-3 (cross-check)
codex_status: invoked
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: layer3-per-session-ownership
  computed_at: 2026-06-21
final_grade: B
iterations_used: 2
human_review_needed: true
---

# REVIEW — layer3-per-session-ownership

## 🎯 Round 1 Summary

- **Reviewers:** code-reviewer + concurrency-reviewer + Codex (k-of-3, Production-mandatory).
- **Round-1 grade: B** — one consensus-passed P1 (same-slug crumb peer-pop) + three real
  lower findings (legacy owner-strand, SKILL env-less pop, empty-slug crumb).
- **Round-2 (auto-fix):** B/C/D **fixed**; A **mitigated** (cross-task broadening closed +
  docstring corrected) with a documented **accepted-risk** residual. **Final grade: B**,
  `human_review_needed: true` — the same-slug-same-task contamination is narrowed +
  guarded (SharedSlug flag-on) but not eliminated; a SharedSlug-on-crumb follow-up is needed.

## 🔍 Drift Findings

`drift_verdict: clean`. All changed files map to PLAN phases (worktree.py→P1, the two
templates→P2, snapshots→P2 mechanical, the three test files→P1/2/3, CLAUDE.md→P4). The
SKILL.md.j2 + render-gate extension were added in auto-fix (Finding C).

## ✅ Consensus Findings

### [P1, consensus = Codex + concurrency; mitigated → accepted-risk] Same-slug crumb is a peer-pop, not a strand

**OBSERVE:** `_owned_crumb_add` UNIONs uuids into `.hm-owned-uuids-<slug>` (read-modify-write
set union, confirmed by `test_worktree_layer3_pop_isolation.py:91`). **INFER:** two DIFFERENT
sessions on the SAME `<slug>` accumulate both uuids into one crumb; session A's wrapup reads
`owned={A,B}`, and post-commit-pop's guard (`B in {A,B}` → not skipped) + a live B marker →
**A pops B's deferred stash** (cross-session contamination). **CONCLUDE:** the docstring's
"same-slug collision is last-writer-wins → never a peer" was **factually wrong** (it's union,
not last-writer-wins).

**Severity:** Codex P0, concurrency-reviewer P1 (explicitly scoped: distinct-slug is the
normal fleet case; this needs two concurrent same-slug stage-only sessions with dirty bases).
code-reviewer **mis-cleared** it ("acceptable, fail-safe") — resting on the same wrong
"last-writer-wins" premise. Resolved to **P1** (concurrency's scoped reasoning).

**Auto-fix (Iteration 2) — MITIGATED, residual ACCEPTED-RISK:**
- Docstring corrected to state the same-slug peer-pop honestly (no false "fail-safe" claim).
- `_cli_owned_crumb_add/read/clear` now **reject an empty slug** — closes the broader
  cross-UNRELATED-task collision (a missed `<slug>` substitution sharing one `.hm-owned-uuids-`
  crumb), the more dangerous variant.
- **Accepted-risk (the same-slug-same-task residual):** the crumb is slug-keyed, not
  session-keyed; eliminating the same-slug peer-pop needs a SharedSlug-style foreign-live
  guard on the flag-OFF crumb path (a follow-up). It is **bounded + guarded**: flag-ON blocks
  same-slug via `claim_task_branch`'s `SharedSlugError`; flag-OFF same-slug-concurrent is a
  pre-existing footgun (the two sessions already share the `.worktrees/<…>` namespace); and it
  is **no worse than the pre-fix all-markers behavior** (which popped peers regardless of slug).
  The **distinct-slug fleet** — the fix's stated goal and the user's single-session-per-task
  config — is fully isolated. `human_review_needed: true` surfaces this for the operator.

### [P1, code-reviewer; FIXED] Legacy bare-timestamp worktree stranded the owner's OWN stash

**OBSERVE:** `_write_stash_ref_file` set `effective_uuid = … or _current_session_uuid(base)` →
a legacy bare-timestamp `wt_name` (no embedded uuid) got a NON-empty uuid that `wt-uuid`
(empty on a bare-timestamp name) could never reproduce into the crumb. **INFER:** wrapup's
crumb is empty → the new strict guard SKIPs the owner's OWN legacy ref (pre-fix: the
`owned_uuids and` short-circuit fell through to the marker pop). **CONCLUDE:** a regression I
introduced — a legacy in-flight worktree's owner could no longer restore its own stash.

**Auto-fix (Iteration 2) — FIXED:** dropped the `_current_session_uuid` fallback →
`effective_uuid = session_uuid or dirname_uuid`. A bare-timestamp name → empty session_uuid →
marker fallback (its old owner-pops-own behavior); standard `execute-<uuid>-<ts>` names still
derive a non-empty uuid (writer-uuid-proof test unchanged). Test
`test_writer_legacy_bare_timestamp_empty_session_uuid` pins it.

## 📝 Manual-Only Findings

### [P2, Codex; FIXED] `worktree-isolator/SKILL.md` ran `post-commit-pop` env-less

A producer path the render-gate didn't cover: the skill's recovery example ran
`post-commit-pop "$(pwd)"` with no `HM_OWNED_SESSION_UUIDS`. After the guard change that
skips uuid'd refs on an empty set, it strands the owner's own stash. **FIXED:** the SKILL now
sources `HM_OWNED_SESSION_UUIDS` from `owned-crumb-read "$(pwd)" <slug>`; the render-gate
`test_no_envless_post_commit_pop_in_any_producer` extended to scan the SKILL + commands so a
future env-less producer is caught.

### [P2, concurrency-reviewer; FIXED] Empty-slug crumb cross-task collision

Folded into Finding A's mitigation — the crumb CLIs reject an empty/whitespace slug.

### [P3, code-reviewer; WON'T-FIX] `owned-crumb-add` writes before ensuring gitignore

Cosmetic (a crash between `atomic_write` and `_ensure_gitignore_entry` leaves an un-ignored
crumb) — matches the existing `_write_stash_ref_file` ordering; gitignore is documented
best-effort. No action.

## 🤝 Disagreements

On Finding A, **code-reviewer disagreed with Codex + concurrency** — it cleared the same-slug
case as "fail-safe (last-writer-wins)". That clear rests on a **factual error**: the crumb
UNIONs (read-modify-write set), it does not last-writer-win. Verified against the code +
`test_worktree_layer3_pop_isolation.py:91` (two same-slug adds → `{aaaa,cccc}`). When one
reviewer's clear depends on a wrong premise, the consensus is not averaged — Codex +
concurrency are correct; the finding stands.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | — | A (P1) + B,C,D | — |
| 2 (auto-fix) | B | B,C,D fixed; A mitigated→accepted-risk | A residual (accepted) | 0 |

**Final grade: B** (one consensus P1 mitigated-but-not-eliminated; the distinct-slug fleet is
fully fixed, the same-slug-same-task residual is a documented, guarded accepted-risk).
**Status: CHANGES_REQUESTED**, **human_review_needed: true** — the operator should note the
same-slug-concurrent residual + the SharedSlug-on-crumb follow-up. The shipped code is safe
for the user's single-session-per-task / distinct-slug fleet.

**Post-fix verification:** layer3 ownership/isolation + render-gate + stash + snapshot suites
GREEN; ruff/format/mypy clean. No commit (wrapup owns it).
