---
type: review
task_slug: codex-finding-schema-strict-mode
status: APPROVED
created: 2026-06-03
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-finding-schema-strict-mode
  computed_at: 2026-06-03T00:00:00+00:00
---

# REVIEW: codex-finding-schema-strict-mode (2026-06-03)

## 🎯 Round 1 Summary

- **Final grade: A** (0 consensus-passed P0/P1 findings).
- **Status: APPROVED.**
- Reviewers: `code-reviewer`, `security-reviewer` (conditional routing — Python test + JSON schema contract feeding an external `codex exec` call).
- 5 findings total, all single-source (`manual-only`) → none lower the grade by the consensus rule. **Two probe-confirmed P1 guard defects were nonetheless manually fixed** (orchestrator, reviewers stayed read-only) because shipping a buggy regression guard defeats the fix's purpose.

## 🔍 Drift Findings

`drift_verdict: clean`. Diff maps cleanly to PLAN scope:
- Phase 1 test + Phase 2 schema + Phase 5 version files/CHANGELOG all present.
- `uv.lock` = documented version-sync companion (execution-log noted).
- Phase 3 (`.claude/schemas` re-render) intentionally NOT in the diff — re-scoped to a post-release chore (gitignored live copy; `make --update`-in-worktree is the `[fail:snapshot-regen-inside-worktree]` footgun). Not an incomplete-phase violation.
- No `common_ground_marks` in PLAN frontmatter → Step 2.5 silent-intent-miss hook skipped.

## ✅ Consensus Findings (consensus-passed)

None. The two reviewers' finding sets did not overlap (security-reviewer returned zero findings), so no cross-reviewer consensus formed. Grade-relevant count: **P0=0, P1=0 → A**.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (single-source)

From `code-reviewer` (schema fix itself confirmed correct by both reviewers):

| # | Sev | File:line | Finding | Disposition |
|---|-----|-----------|---------|-------------|
| 1 | P1 | test_schema_strict_mode.py:65 | Banned-keyword scan walks the `properties` map → a property literally named `format`/`pattern`/`minimum` false-positives. | **FIXED** — rewrote walker to recurse structurally (`_iter_subschemas`), never treating property names as schema keywords. New test `test_property_named_like_a_keyword_is_not_a_false_positive`. |
| 2 | P1 | test_schema_strict_mode.py:60 | Required-completeness only checked when `additionalProperties is False`; an object that *omits* it is silently passed — yet strict mode requires it on every object (the exact bug class the guard claims to catch). | **FIXED** — now emits `object with properties missing additionalProperties:false`. New test `test_object_missing_additional_properties_false_is_flagged`. |
| 3 | P2 | test_schema_strict_mode.py:86 | Parametrized test could pass vacuously if the glob returns zero files. | Accepted — already covered by sibling `test_schemas_dir_has_at_least_one_schema`; reviewer agreed risk is low. |
| 4 | P2 | test_schema_strict_mode.py:21 | Banned-keyword list broader than ADR-001's three; comment overclaimed provenance. | **FIXED** — comment now notes the extras are pre-emptive, not ADR-mandated. |
| 5 | P2 | .claude/schemas/codex-finding.schema.json | Rendered dogfood copy stale (pre-fix shape), divergent from the template. | Out of diff scope; already documented in PLAN execution log as a **post-release** re-render (gitignored copy). No action this stage. |

**security-reviewer: 0 findings.** Confirmed: dropping `minLength`/`minimum`/`maximum` weakens no security-relevant validation (consumers read the JSON as prose, never key-deserialize — verified no Python path consumes the codex output by key); nullable `file`/`evidence` opens no path/prompt-injection vector (those channels pre-existed as unconstrained free text); `severity` enum retained; `additionalProperties:false` is the tightest available boundary.

## 🤝 Disagreements

None — the reviewers were complementary (code-reviewer on test fidelity, security-reviewer on contract safety), not contradictory.

## Manual Fix Verification

After applying fixes 1, 2, 4:
- `test_schema_strict_mode.py`: **5 passed** (incl. 2 new regression tests + negative fixture still triggers both violation classes; the real current schema still GREEN).
- `ruff check` ✅ · `ruff format --check` ✅ · `mypy --strict` ✅.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 3 (manual, 2×P1 + 1×P2 comment) | 2 P2 (accepted/out-of-scope) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
