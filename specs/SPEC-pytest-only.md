---
type: spec
task_slug: pytest-only
status: approved
created: 2026-11-10
tags: [harness-maker, spec, check, docs]
test_framework: pytest
interview_rounds: 0
summary: "hm's RED and AC gates run pytest only. hm check says so when a project has no Python test setup, and the README states the limit."
---

# SPEC — pytest-only (state the pytest-only limit and fail with a clear reason)

## Intent

RESEARCH-hm-non-token-improvements F6: on a Node project `hm check --red` returns
`"reason": "no pytest runner"` (exit 3). A testable AC can never pass there, the message does not
say why, and the README promises 12+ stacks. The DRI chose the cheap option on 2026-11-10: write
"pytest only" in the docs and fail with a clear message. A second runner is not in scope.

## Scenario

- **S1.** Given a project with no Python test setup (no `pyproject.toml`, `setup.py`, `setup.cfg`,
  `requirements*.txt`, `tox.ini`, `pytest.ini`, `conftest.py`, `Pipfile`, `poetry.lock` or
  `uv.lock` at the root or one directory down), When `hm check` finds
  no pytest runner, Then the reason says that the RED and AC gates run pytest only and that such an
  AC needs a judgment AC instead.

## Non-Goals

- No second test runner (JUnit XML for jest, vitest, go or cargo). That is a separate decision.
- No change to stack detection, the profiler or the rendered templates.
- No change to exit codes: the missing runner still exits 3 (degraded).

## Acceptance Criteria

### AC-001: the no-runner reason names the pytest-only limit
`check.no_runner_reason(root)` on a root with none of the Python markers returns text containing
"the RED and AC gates run pytest only". On a root with a `pyproject.toml` and no runner it
does not contain that text.

## Verification

| scenario | mode | test |
|---|---|---|
| S1 | unit | `tests/unit/test_pytest_only.py` |

## Open Questions

None.

## Refinement Decisions

- Skip check: one code function plus docs, acceptance obvious from the title, no API, IPC, schema
  or file-format change, reversible within an hour. So the interview is skipped and the SPEC is
  stamped `--exempt`.
- A Python project with no runner keeps today's reasons, because there the fix is to install
  pytest, not to change the AC type.
- `tests/unit/test_pipeline_env_fixes.py::test_ac_003_runner_rows` now writes a
  `pyproject.toml` into its fixture root. Its golden rows (SPEC-pipeline-env-fixes AC-003) describe
  a Python project and stay unchanged; the bare root had been standing in for one.
- The README states the limit in its requirements table and in the stack-detection bullet.
  Detection itself is unchanged.
