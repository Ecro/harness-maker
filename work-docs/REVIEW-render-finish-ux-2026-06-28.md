---
type: review
task_slug: render-finish-ux
status: APPROVED
created: 2026-06-28
reviewers_invoked: [code-reviewer, security-reviewer, ux-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: render-finish-ux
  computed_at: 2026-06-28T00:00:00Z
---

# REVIEW — render-finish-ux (2026-06-28)

## 🎯 Round 1 Summary

- **Reviewers:** code-reviewer, security-reviewer, ux-reviewer (Claude, conditional routing — perf/concurrency N/A: no hot paths/threads) + **Codex** heterogeneous 3rd voter (Production mandatory, `codex_status: invoked`).
- **Single-pass note:** the diff is a local worktree diff with no PR title/author/commit metadata to anchor on, so the 2-pass redaction was moot; reviewers ran single-pass with full context. Per project memory (`fail:` 1-pass hallucination guard), tool-output-format claims were cross-checked against the actual (green) test runs — none surfaced.
- **Round-1 grade: B** (0 consensus-passed P0, 1 consensus-passed P1).
- **Auto-fix → Round 2 grade: A.** Status **APPROVED**.

## 🔍 Drift Findings

`drift_verdict: clean`. All 20 changed files map to a PLAN phase:
- `git_disposition.py` + 4 test files → P1/P2/P3/P4; `cli.py` → P1+P2; `commands/make.md` + `make.md.j2` → P3; README×2 + HOW-IT-WORKS×2 → P4; 8 snapshot fixtures → P3 regeneration consequence. No scope violations, no incomplete phases.

## ✅ Consensus Findings

### P1 — `consensus-passed` (code-reviewer P1 ∧ ux-reviewer P2; severity resolved to P1)
**Unscoped `git commit` sweeps unrelated pre-staged work into the harness commit.**
- **Surface match:** both target `make.md.j2:90` + `commands/make.md:608` (and the `offer_stage` commit). **Reasoning aligned:** both CONCLUDE that `git commit` with no pathspec commits the entire index, so a user with unrelated staged work who picks "Commit them" gets it committed under `chore: add harness-maker harness` — contradicting the "commit is clean" framing. Same class as the harness's own Layer-5 scope-guard.
- **Severity resolution:** code=P1, ux=P2 → P1 (code-reviewer's "wrong commit under realistic input" reasoning is decisive; matches the scope-guard precedent).
- **FIXED (Round 2):** scoped both `git add` and `git commit` to existing roots — `roots=""; for r in …; do [ -e "$r" ] && roots="$roots $r"; done; git add $roots && git commit -m "…" -- $roots`. Same `-- <paths>` scoping applied to the `offer_stage` commit (both surfaces).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (single-source — fixed as orchestrator where cheap/correct)

### P1 — Codex (corroborated by plan-validator round-2): `!`-autorun of effectful actions in `commands/make.md` §6.5
`!`-prefixed `git commit` / `git-ignore-roots` snippets are autorun by the slash-command expander at load time, not gated by the surrounding choice prose — so invoking `/harness-maker:make` could apply commit/ignore **before** the user chooses. (make.md.j2 was already correctly de-`!`'d; the meta command regressed.)
- **FIXED (Round 2):** removed `!` from all effectful §6.5 snippets + the Update-section apply, with an explicit "run with the Bash tool when you reach it — NOT `!`-autorun; the action fires only after the user's choice" instruction. Mirrors make.md.j2's gated style.

### P2 — security-reviewer: manifest `..`-traversal reaches a read-only git probe (defense-in-depth)
Not exploitable (manifest is harness-self-authored via `path.resolve().relative_to(project_root)`; all sinks are read-only; the `git add` loop uses fixed roots) — but a `..`-bearing unit should never reach a git call.
- **FIXED (Round 2):** added `_is_traversal()` guard excluding `..`-segment units in `compute_git_status`, with `test_traversal_path_excluded_from_units`.

### P3 — ux: commit listed first reads as a mild ordering signal vs the "no preference ordering" intent.
- **FIXED:** added "(the order below is not a recommendation)" to both surfaces.

### P3 — ux: four-state branch lacked an explicit no-rendered-roots catch.
- **FIXED:** folded "no rendered roots present → nothing to dispose" into the already-decided branch (both surfaces).

### P3 — ux: en/ko drift — README.ko RENDER domain-packs line claimed `node`/`rust` ship pre-filled (only `python` does).
- **FIXED:** aligned README.ko.md:151 + :366 to README.md (only `python` ships pre-filled; others scaffold blank stubs). (Pre-existing, but in the RENDER subsection under review.)

### P3 — code-reviewer: commit-all loop hard-codes 5 roots; a stale non-target root (e.g. leftover `.cursor/` from a reverted multi-target config) could be committed.
- **ACCEPTED (won't fix):** low harm; the scoped commit still only commits roots that exist on disk. Deriving the root set from `git-status.target_roots` would tighten but adds bash complexity; documented as an accepted limitation.

## 🤝 Disagreements

bare-commit severity (code P1 vs ux P2) — resolved to P1 (see Consensus Findings). No reasoning conflict, only severity.

## Validated as clean (no finding)

- **Truth table** (`compute_git_status`): code-reviewer + Codex confirm `prior_decision`/`decision_needed`/`offer_stage` correct + complete across mixed/transition states — no re-nag, no wrong suppression. Residual full-prompt case (manual exact-file ignore + new file) is a genuinely-undecided file, not a false positive.
- **check-ignore rc=1** handled via `check=False` + returncode branching (not `worktree._run`).
- **Subprocess safety:** args list, `timeout=10`, no `shell=True` (prior `subprocess-missing-timeout` P1 does not recur).
- **ignore_roots loud contract:** re-verifies each root post-append, raises `GitDispositionError` → CLI exit 1; catches the swallowed-OSError of `_ensure_gitignore_entry`.
- **gitignore atomicity:** reuses `_ensure_gitignore_entry` (atomic_write).
- **dry-run read-only:** reconcile only builds a conflict list; no write/backup/render in that branch.
- **CLI never commits:** `git-status` JSON-only; `git-ignore-roots` mutates `.gitignore` only.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 P1 (consensus) + 1 P1 + 1 P2 + 4 P3 (manual) | — |
| 2 (auto-fix) | A  | 6 (P1 consensus scope-commit, P1 `!`-autorun, P2 traversal, 3× P3) | 1 P3 accepted | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false

**Round-2 re-verification:** `ruff check` clean; `mypy --strict` clean; affected unit tests (git_disposition 16/16 incl. traversal, render-make 4/4, docs 3/3) green; snapshots regenerated (diff confined to `make.md` hash); full suite green. The consensus P1 fix is the reviewers' own verbatim suggestion (`-- <roots>` pathspec), mechanically verified + test-adjacent — no new reviewer round needed to re-adjudicate. **No `git commit` invoked from this stage.**
