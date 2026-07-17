---
type: review
task_slug: multisession-worktree-concurrency
status: APPROVED
created: 2026-06-20
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: cross-check
codex_status: invoked
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-worktree-concurrency
  computed_at: 2026-06-20T00:00:00Z
---

# REVIEW — multisession-worktree-concurrency (Phase 0)

Scope of this review: the **Phase 0** staged diff only (ADR-009 drain-trigger relocation). Phases 1–7 are not yet implemented.

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0=0, P1=0). Threshold A met → **APPROVED**.
- Voters: `code-reviewer` (opus), `security-reviewer` (opus), `codex` (gpt-5.5, k-of-3, exit 0). Production-mandatory Codex invoked.
- Diff: `worktree.py` (+37: `_drain`/`_drain_summary`/`_cli_drain` + `drain` dispatch), `wrapup.md.j2` (Step 7.6), `health.md.j2` (drain section), `test_worktree_drain.py` (+147), 8 mechanical snapshot regens.
- Fixes applied: **0** (already grade A; the two findings are P3 advisory, below auto-fix priority while grade ≥ threshold).

## 🔍 Drift Findings

`drift_verdict: clean`. Every changed file traces to PLAN Phase 0 scope:
- `worktree.py` (drain trigger), `wrapup.md.j2`, `health.md.j2` — explicitly in Phase 0 `Scope (in)`.
- `tests/unit/test_worktree_drain.py` — TDD tests for the phase (implied by `tdd_active`).
- `tests/snapshot/*.expected.yaml` (×8) — mechanical regen forced by the wrapup/health template edits.

**Verified-clean risk (self-caught from memory `[fail:test] snapshot-regen-inside-worktree` count:7):** snapshots were initially regenerated inside the worktree, which can embed the worktree path into rendered output and diverge hashes. Re-running `regenerate.py` from the **main repo root** produced byte-identical files (`git diff` empty) → **no contamination**. The count:7 failure did NOT recur. Only the wrapup/health-embedding command hashes changed (`harness.yaml`/`help`/`exec-rev` unchanged), confirming scope.

No scope drift, no incomplete-phase (Phase 0 fully implemented).

## ✅ Consensus Findings

None at P0/P1/P2. The diff is clean against all stated invariants. All three voters independently confirmed:
- `_drain` is a thin delegation to `prune_stale` (the single content-gated, biased-to-preserve gate) — **cannot delete unmerged work**; no `--force`/escape path reachable.
- Create-time reaping **retained** (`prune_stale` still called in `_cli_create:1922`) — additive, not a move.
- Auto-trigger summary is **non-interactive** (single f-string, no `--force` nag).
- Template base paths correct (`"$(pwd)"` wrapup, `.` health); `{{ harness_maker_src_path }}` is harness-controlled (no injection); subprocess hygiene inherited (list argv, `timeout`, `check=True`, no `shell=True`).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

- **P3 (advisory, consensus on surface) — `_cli_drain` silently ignores extra positional args.** `rest[0]` is consumed; a stray second positional is dropped without a usage error. Both code-reviewer and security-reviewer noted it; both judged it **benign and consistent** with sibling CLIs (`_cli_prune_branches` takes only `rest[0]`). Not a regression; not auto-applied at grade A. Optional polish: reject `len(rest) > 1`.
- **P3 (manual-only, single source — code-reviewer) — `_drain_summary` omits `removed_worktrees` / `removed_markers` counts.** Reaped dangling worktree dirs + orphan loop-markers are invisible in the one-liner. Defensible: those reaps are uncontroversial and not user-actionable; the health "surface when preserved count non-zero" logic keys on the **preserved** count, which IS surfaced. Optional: add the two counts, or document the elision.
- **P3 (test-only — code-reviewer) — weak `"1" in summary` assertion** in `test_drain_summary_is_noninteractive`. Could tighten to `"removed 1 branch(es)" in summary`. Not a production defect.

## 🤝 Disagreements

Minor severity nuance on the extra-arg finding (code-reviewer P3 vs security-reviewer "P2-awareness, not a blocker"). Both agree it is **not a blocker** and benign; resolved conservatively as **P3** (cosmetic). Does not affect the grade.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0 (3× P3 advisory) | — |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
