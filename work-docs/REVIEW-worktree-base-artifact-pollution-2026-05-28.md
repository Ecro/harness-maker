---
type: review
task_slug: worktree-base-artifact-pollution
status: APPROVED
created: 2026-05-28
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: worktree-base-artifact-pollution
  computed_at: 2026-05-28T00:00:00+00:00
final_grade: A
human_review_needed: false
---

# REVIEW — worktree-base-artifact-pollution

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0/P1). Threshold A met → **APPROVED**.
- 3 reviewers (code, security, concurrency), single round, model=opus.
- **No data-loss, no P0/P1** — all reviewers independently confirmed: the `prune_stale` drain is triple-gated (wt-dir absent AND session-marker absent AND stash-object gone), `git cat-file -e <sha>^{commit}` is a sound "unrecoverable" proxy (dropped-but-reflog-recoverable stashes still resolve → preserved), subprocess inputs are `_SHA_RE`-validated with list-argv (no injection), and the narrow finalize-filter strict-subset invariant holds (genuine user `.claude/` edits stay dirt).
- **1 consensus-passed finding auto-fixed** this round (file-churn exact-match). Remaining items are manual-only P2/P3, each assessed below as pre-existing or accepted trade-off.

## 🔍 Drift Findings

None. All 15 changed files map to PLAN phases: `worktree.py`/`cli.py`/`render.py` → Phases 1/2/4; `wrapup.md.j2` → Phase 3; `CLAUDE.md`/`CHANGELOG.md` → Phase 5; 8 `tests/snapshot/*.expected.yaml` → Phase 3 regen artifact; `test_worktree_churn_pollution.py` → tests. `drift_verdict: clean`.

## ✅ Consensus Findings (auto-fixed)

### [consensus-passed][P3] File-shaped churn matched by `startswith` → sibling misclassification
- **Reviewers:** code-reviewer (worktree.py:69) + security-reviewer (worktree.py:444) — independent surface+reasoning match.
- **Issue:** `_HARNESS_CHURN_PREFIXES` mixed dir prefixes and file paths, all matched via `startswith`. A sibling like `work-docs/p5-batch-state.yaml.bak` or `.claude/.hm-session-uuid-notes` would be wrongly forgiven (excluded from finalize stash + dirty-base guard). Latent (no real path collides today).
- **Fix applied:** split into `_HARNESS_CHURN_DIRS` (prefix match, trailing-slash) and `_HARNESS_CHURN_FILES` (exact `==` match). `_is_harness_artifact` now uses `startswith(_HARNESS_CHURN_DIRS) or path in _HARNESS_CHURN_FILES`. Removed the now-dead `_WORKDOCS_CHURN_PREFIXES` (was tests-only — create-guard covers work-docs churn via delegation). Sync test updated; added prefix-collision + rename/quoted/empty-line coverage. ruff + mypy + worktree suite GREEN.

## ⚠️ Weak Consensus

### [weak][P2/P3] `.gitignore` forgiveness narrows the dirty-base guard for a lone user `.gitignore` edit
- **Reviewers:** code-reviewer (P2, worktree.py:436) + security-reviewer (P3, worktree.py:436) — aligned reasoning, severity differs (→ resolved P2 per Step 4c middle-of-scale isn't applicable; recorded as the higher P2 for visibility).
- **Assessment:** intentional + safe. `_is_harness_artifact` forgiving `.gitignore` is required so the harness's own churn-pattern append doesn't trip the guard / get stashed. Both reviewers confirmed **no data-loss and no secret exposure**: the finalize squash carries only the worktree-branch diff and never modifies the base `.gitignore`, so a user's own `.gitignore` edit is left intact on disk (never swept). The only effect is a `.gitignore`-only dirty state no longer blocks `create`. **Accepted, documented** in CLAUDE.md `## Multi-session worktree`. Not auto-fixed (precise "only-harness-lines" detection adds complexity for negligible gain).

## 📝 Manual-Only Findings (assessed — not auto-applied)

### [manual][P2] `.gitignore` read-modify-write race across parallel `create`s — concurrency-reviewer (worktree.py:1813)
- **Pre-existing**, amplified. `_ensure_gitignore_entry` (read full file → atomic_write) is not lock-protected; two parallel creates can lose-update a churn line (last-writer-wins; no torn file, no dup). **Impact bounded to stash hygiene** — the load-bearing dirty-base/queue guards match the in-code churn tuples, NOT `.gitignore` contents, so a lost line does not regress the guards (a dropped pattern is re-added on the next create). The existing `.hm-loop-*`/`.hm-session-uuid` appends already have this race. **Follow-up** (separate PLAN): make `_ensure_gitignore_entry` use `O_APPEND` atomic-append, or wrap `_ensure_harness_gitignore` in the merge fence.

### [manual][P2] `prune_stale` orphan-marker sweep can delete a stage-only session's kept-alive marker — concurrency-reviewer (worktree.py:1456)
- **Pre-existing** (the orphan-marker sweep predates this change; verified the new ref-drain branch PRESERVES stage-only refs — object exists + content-not-in-HEAD → preserve+warn, never drains live WIP). Cross-session only: if session B's `create` runs `prune_stale` between session A's stage-only finalize and A's `post-commit-pop`, A's kept-alive marker can be orphan-swept, after which A's `post-commit-pop` skips its own ref (stash object survives → no hard loss, but deferred restore is skipped). **Not a regression from this change.** **Follow-up** (separate PLAN): exclude markers still referenced by a non-drained finalize-stash ref from the orphan sweep.

### [manual][P2] Harness-appended base `.gitignore` is never committed → permanent `M .gitignore` — code-reviewer (worktree.py:1609)
- **Accepted trade-off.** `.gitignore` is forgiven by the filter, so the `M` neither blocks `create` nor gets stashed — cosmetic only. Documented in CLAUDE.md with an opt-in manual commit. Not auto-fixed (adding `.gitignore` to wrapup's git-add could sweep unrelated user `.gitignore` edits).

### [manual][P3] `.gitignore` stash-sweep/pop-conflict under concurrent finalize-with-dirt — concurrency-reviewer (worktree.py:436)
- Narrow, gated behind concurrent finalize + `--allow-dirty-base`. Noted; low priority.

## 🤝 Disagreements

Severity split on the `.gitignore`-forgiveness finding (code P2 vs security P3) — recorded above as weak-consensus at P2 for visibility. No reasoning conflict (both: guard-narrowing, not data-loss).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 1 (consensus-passed file-churn exact-match) | 4 manual (2 pre-existing P2, 1 trade-off P2, 1 P3) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false**

Follow-ups (non-blocking, separate PLANs): (1) atomic-append for `_ensure_gitignore_entry` RMW race; (2) orphan-marker sweep vs stage-only kept-alive marker.

---

## Round 2 — Standalone independent re-review (2026-05-29)

A fresh `code-reviewer` (NO prior context) was run on the staged diff (including Round-1's auto-fix). It surfaced **3 findings Round 1 missed** — the independent pass paid off.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| R2-1 | P2 | `_HARNESS_CHURN_*` hard-code `work-docs/`, but `work_docs.dir` is user-configurable → a non-default dir is NOT churn-isolated (regression for those users). | **Documented as known limitation** (code comment at the churn constants + CHANGELOG). The dominant churn (`.claude/observability/`, written every tool call) is NOT configurable, so the core fix holds. Config-threading into pure porcelain-line filters is disproportionate → deferred follow-up. |
| R2-2 | P2 | `prune_stale` drain crashes with uncaught `FileNotFoundError` when a ref's recorded `base` dir is gone (e.g. removed sibling repo): `_run` only catches `CalledProcessError`/`TimeoutExpired`; `_stash_object_exists` only catches `RuntimeError`; `_cli_create` calls `prune_stale` unguarded → next `worktree create` aborts with a traceback. | **FIXED** — `prune_stale` now drains a ref whose `ref_base` is not a dir (gone base = unreachable stash = cruft) BEFORE calling git, preventing the crash. Regression test `test_prune_drains_ref_whose_base_dir_is_gone_without_crashing` added. ruff+mypy+full suite GREEN. |
| R2-3 | P3 | CHANGELOG referenced the now-split constant `_HARNESS_CHURN_PREFIXES`. | **FIXED** — updated to `_HARNESS_CHURN_DIRS` + `_HARNESS_CHURN_FILES`. |

All Round-1 binding invariants independently re-confirmed by the fresh reviewer (strict-subset filter; `.gitignore` co-management safe; drain preserves un-landed work; gitignore↔filter sync). No P0/P1. R2-2 was a real robustness bug on the new code path — fixed proactively (single-source but a genuine crash, not a style nit).

### Round 2 iteration record (Grade: A → A)
Fixes applied: 2 (R2-2 crash guard + test; R2-3 changelog). Documented: 1 (R2-1). New issues introduced: 0.

**Final grade (Round 2): A** — Status: **APPROVED**, human_review_needed: **false**.

Follow-ups now (non-blocking, separate PLANs): (1) `_ensure_gitignore_entry` RMW race → atomic-append; (2) orphan-marker sweep vs stage-only kept-alive marker; (3) churn-isolation for non-default `work_docs.dir`.
