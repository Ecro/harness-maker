---
type: review
task_slug: cursor-mdc-orphan-sweep
status: APPROVED
created: 2026-05-28
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: cursor-mdc-orphan-sweep
  computed_at: 2026-05-28T00:00:00+00:00
---

# REVIEW — cursor-mdc-orphan-sweep (2026-05-28)

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0=0, P1=0). Threshold A met → **APPROVED**.
- Reviewers: `code-reviewer`, `security-reviewer` (both `model: opus`), single round.
- Auto-fix loop: not entered (grade ≥ threshold; manual-only findings are not auto-fix-eligible).
- Consensus-passed findings: **0**. All 4 findings are single-source `manual-only` (P2/P3 hardening) — recorded below, none blocking.

Both reviewers independently confirmed the R4 safety contract holds: the new branch
deletes only a file whose full-file sha256 matches a render-manifest entry **under its own
path key** (`manifest.get(rel_key)`), so user-authored `.mdc` (no entry), edited renders
(hash miss), and content-colliding files under a different path are all KEPT.

## 🔍 Drift Findings

`drift_verdict: clean`. Diff-vs-PLAN mapping:

| File(s) | PLAN phase | Verdict |
|---|---|---|
| `src/harness_maker/reconcile.py`, `tests/unit/test_reconcile_orphan_sweep.py` | Phase 1 (in-scope) | ✅ in scope |
| 5 version files + `CHANGELOG.md` | Phase 3 (in-scope) | ✅ in scope |
| `uv.lock` | — | mechanical: `uv` re-pins the local package version on every bump |
| 8 `tests/snapshot/*.expected.yaml` | — | mechanical: rendered version strings changed → regen mandated by CLAUDE.md release procedure; recorded in PLAN execution-status |

`uv.lock` + the 8 snapshots are **deterministic byproducts of the planned Phase 3 version
bump**, not unplanned scope creep — every version bump in this repo touches them (the prior
0.26.4 release commit did the same). Hence `scope_violations: []`. No PLAN-scoped code file
was left unchanged (no incomplete-phase). PLAN has no `common_ground_marks` frontmatter →
Step 2.5 silent-intent-miss hook skipped.

## ✅ Consensus Findings

None. No pair of findings shared file + line(±5) + severity tier with aligned reasoning.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| # | Sev | Reviewer | File:Line | Summary | Disposition |
|---|-----|----------|-----------|---------|-------------|
| 1 | P2 | code-reviewer | reconcile.py:472 | Byte-equality invariant (disk bytes == recorded body hash) load-bearing but documented only implicitly | **Already mitigated** — call-site comment ties to `render._render_pure_text`; `test_cursor_mdc_trailing_newline_perturbation_kept` pins the byte-exact invariant. No change. |
| 2 | P2 | code-reviewer | test:271 | No explicit test that a `.mdc` carrying `generated_by: harness-maker` routes to the first (body-hash) branch, not the new one | **Deferred** — branch boundary is implicitly covered (`test_ours_clean_deleted` exercises the harness-provenance branch; 5 RC1 tests exercise the new branch). Marginal; future hardening. |
| 3 | P3 | security-reviewer | reconcile.py:472 (via `_iter_disk_files`) | `is_file()` resolves symlinks → a content-matched symlink under a sweep root becomes newly deletable (only the link, never the target) | **Deferred — out of RC1 scope (ADR-002).** Pre-existing behavior in shared `_iter_disk_files`; affects all sweep branches. Track as standalone hardening (`if f.is_symlink(): continue`). |
| 4 | P3 | security-reviewer | reconcile.py:463 | `parse_frontmatter` failure silently routes a file to the no-frontmatter byte-match path; no audit log | **Deferred — out of RC1 scope.** Both paths are per-path byte-gated (no false-positive deletion); optional audit log is a future improvement. |

## 🤝 Disagreements

None. Findings 1 and 3 both reference line 472 but address different issues (invariant
documentation vs symlink resolution) at different severity tiers (P2 vs P3) — recorded as
independent, not a severity disagreement.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 4 manual-only (2×P2, 2×P3) | — |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
