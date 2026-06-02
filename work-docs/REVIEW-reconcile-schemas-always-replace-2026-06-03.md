---
type: review
task_slug: reconcile-schemas-always-replace
status: APPROVED
created: 2026-06-03
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: reconcile-schemas-always-replace
  computed_at: 2026-06-03T00:00:00+00:00
---

# REVIEW: reconcile-schemas-always-replace (2026-06-03)

## 🎯 Round 1 Summary

- **Final grade: A** (0 consensus-passed P0/P1).
- **Status: APPROVED.**
- Reviewers: `code-reviewer` (reconcile decision logic) + `security-reviewer` (REPLACE-on-path-class overwrite/data-loss vector).
- **0 findings total** from either reviewer. No auto-fix loop entered.

## 🔍 Drift Findings

`drift_verdict: clean`. Diff maps cleanly to PLAN scope: `reconcile.py` (Phase 2), `tests/unit/test_reconcile_schemas.py` (Phase 1/3), 5 version files + CHANGELOG (Phase 4); `uv.lock` = documented version-bump companion. No missing-phase, no out-of-scope file. No `common_ground_marks` in PLAN frontmatter → Step 2.5 silent-intent-miss hook skipped.

## ✅ Consensus Findings (consensus-passed)

None. Both reviewers returned empty finding lists. Grade-relevant: **P0=0, P1=0 → A**.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None. (code-reviewer's out-of-scope aside — "no unit test asserts REPLACE" — is already satisfied by `test_reconcile_schemas.py::test_reconcile_stale_schema_returns_replace`; the reviewer was not given the test file. Not a defect.)

## 🤝 Disagreements

None — both reviewers concurred the change is correct and low-risk.

## Reviewer verifications (for the record)

**code-reviewer (5 dimensions, all correct):**
1. **Placement** — `schemas/*.json` matches no earlier branch (harness.yaml/settings.json/AGENTS.md/hooks/.toml/.sh); placed immediately before the `fm is None → KEEP` is the **only** correct slot (one line later = the freeze being fixed).
2. **Fresh install** — line 147 `not exists() → BOTH` runs first; the REPLACE branch is only reachable when the file exists. No first-install regression.
3. **Shared predicate** — reconcile already imports from render (no cycle); reusing `_is_schemas_json` keeps reconcile's gate and render's dispatch on identical logic (anti-drift).
4. **Path form** — `synthesize` emits `schemas/codex-finding.schema.json`; `startswith("schemas/") and suffix==".json"` holds on both sides.
5. **`reason` string** — cosmetic; `cli.py` routes solely on `.decision`. A REPLACE path is excluded from `keep_paths` → survives into the render blueprint → `_render_pure_json` overwrites. `verify.py` only inspects `*.md` + 3 named JSON, never `schemas/*.json`.

**security-reviewer (0 findings):**
- Data-loss: `backup()` runs before render (same guard as reconcile/render), so a REPLACE'd schema is snapshotted to `.backup-<ts>/` first — recoverable, same mitigation the existing always-REPLACE files (harness.yaml/settings.json) rely on.
- Scope: predicate only runs against `blueprint.files`; the schema is emitted only when `codex_second_opinion.enabled`. No over-match of user-owned files.
- Path-traversal/injection: fixed package-controlled relative path, no user input, no `..`. Symlink-follow is pre-existing for all always-REPLACE files, not a regression.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 0         | —   |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
