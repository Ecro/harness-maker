---
type: review
task_slug: pytest-only
created: 2026-11-10
spec: "[[SPEC-pytest-only]]"
plan: "[[PLAN-pytest-only]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 6 findings (1 major, 4 minor, 1 nit). Five accepted and fixed; the nit rejected."
---

# REVIEW — pytest-only

One code-reviewer round raised 6 findings. Five were accepted and fixed, and the nit was rejected
with an authority. Nothing is unresolved. The spec-validator was skipped (exempt SPEC, no
irreversible decision). No `Do not change` path was crossed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| 1 | major | src/harness_maker/check.py (`_python_project`, `no_runner_reason`) | Only the root was read, so a monorepo with `backend/pyproject.toml` was told it "has no Python test setup" and was advised to write a judgment AC. Fix: the markers are also looked for one directory down. The message now says the setup was "not found at the project root or one level down" | accepted | SPEC S1 |
| 2 | minor | src/harness_maker/check.py (`_PY_MARKERS`) | `Pipfile`, `poetry.lock` and `uv.lock` were missing. Fix: added to the code and to SPEC S1 | accepted | SPEC S1 |
| 3 | minor | tests/unit/test_pytest_only.py | The Python-root cases covered 4 of the markers. Fix: every marker is parametrized, at the root and one level down | accepted | SPEC AC-001 |
| 4 | minor | tests/unit/test_pytest_only.py | Nothing showed the reason reaching `hm check`'s output. Fix: `test_ac_001_hm_check_reports_it_degraded` runs `check.run --red` on a Node root and asserts exit 3 and the reason. The precedence of the tracked-lock and `.venv` branches is covered by the unchanged `test_pipeline_env_fixes.py` AC-003 and AC-004 rows | accepted | SPEC AC-001 |
| 5 | minor | README.md (Requirements) | "the rest of the pipeline still works" was broader than what was checked. Fix: "Stack detection and the review step do not depend on pytest." | accepted | SPEC Intent |
| 6 | nit | src/harness_maker/check.py (`no_runner_reason`) | The message does not say "exit 3, degraded" | rejected | The reason is printed inside `hm check`'s JSON, next to `"exit": 3` and `"degraded": true`. Repeating the code in the text adds length with no new information |
