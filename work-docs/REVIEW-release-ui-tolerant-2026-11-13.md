---
type: review
task_slug: release-ui-tolerant
created: 2026-11-13
spec: "[[SPEC-release-ui-tolerant]]"
plan: "[[PLAN-release-ui-tolerant]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: no blockers or majors, 3 minor findings, all rejected with a reason."
---

# REVIEW — release-ui-tolerant

One code-reviewer round with no blockers or majors and 3 minor findings, all rejected with a
reason; nothing is unresolved. The cross-model second opinion is not configured for this harness.
No `Do not change` path was crossed: `src/` is untouched.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | minor | .github/workflows/release.yml (github-release) | `gh release view` treats any error (5xx, rate limit) as "no Release", so a transient error on the UI path falls into `gh release create`, which fails loudly with "already exists" | rejected | Fails loud with the pre-change behaviour and is re-runnable; a retry adds code for a rare transient. SPEC Non-Goals |
| F2 | minor | .github/workflows/release.yml (github-release) | `gh release edit` overwrites the title and notes typed in the UI | rejected | Intended: SPEC Refinement Decisions keep CHANGELOG as the single source of release notes |
| F3 | minor | tests/unit/test_release_ui_tolerant.py | The test is a string-shape check on the step, not an execution of the shell, and it is brittle to reformatting | rejected | Same pattern as `test_release_identity.py::test_s3_release_workflow_enforces_both_identity_boundaries`; it fails on the old step and catches inverted branches. PyYAML is already used by that test under mypy |
