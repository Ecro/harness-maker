---
type: spec
task_slug: nightly-py313-venv
status: approved
created: 2026-11-24
tags: [harness-maker, spec, ci, nightly, tests]
test_framework: pytest
interview_rounds: 0
summary: "Stop two e2e tests from rebuilding the project .venv on Python 3.12 in the middle of nightly's Python 3.13 run, by forwarding uv's interpreter variables through one shared scrubbed-env helper."
---

# SPEC — nightly-py313-venv

## Intent

Nightly's `py313` job has failed on both runs since it was added (45219033505 on 2026-11-23,
45438962001 on 2026-11-24), each time on a different test, with
`ModuleNotFoundError: No module named 'hypothesis...'` and finally `No module named 'hypothesis'`
in pytest's own terminal summary. The job selects 3.13 with `UV_PYTHON: "3.13"`, which overrides
`.python-version` (3.12). Two e2e tests (`test_verify_health_dashboard.py`,
`test_reconcile_orphan_sweep.py`) run `uv run python -m harness_maker.cli ...` with `cwd=REPO_ROOT`
and an env scrubbed down to `PATH HOME USER VIRTUAL_ENV UV_PROJECT_ENVIRONMENT`. Without
`UV_PYTHON`, uv reads `.python-version`, finds the shared `.venv` on 3.13, and recreates it on 3.12
while the other xdist workers are still importing from it. Reproduced locally with uv 0.11.32: a
3.13 `.venv` becomes 3.12 after one `env -i PATH=... uv run python -V`. The 3.12 jobs never see it
because `.python-version` already matches. PR #74's own note ("a venv I shared broke") was this bug.

## Outcomes

- O1. Nightly's `py313` job no longer loses its virtual environment mid-run.
- O2. A test that runs `uv run` in the repository with a scrubbed env builds that env in one place,
  so a new interpreter-selecting variable is forwarded once, not per test.

## In-Scope Scenarios

- S1 (normal). The suite runs with `UV_PYTHON=3.13` against a 3.13 `.venv`; the two e2e tests run
  `uv run` in the repo; the `.venv` stays on 3.13.
- S2 (edge). `UV_PYTHON` is unset (local runs, PR CI on 3.12); the helper forwards nothing extra
  and behaviour is unchanged.

## Non-Goals

- Changing nightly.yml, `.python-version` or how the py313 job selects its interpreter.
- Auditing tests that inherit the full `os.environ` (they already forward `UV_PYTHON`).
- The `SyncHttpxClientWrapper` unraisable warning in the same log (a warning, not a failure).

## Constraints

| constraint | value |
|---|---|
| change surface | tests only (`tests/_uv_env.py` + the two e2e callers); no `src/` change |
| forwarded keys | `PATH`, `HOME`, `USER`, `VIRTUAL_ENV` and every `UV_*` variable (uv reads them, nothing else does; covers `UV_PYTHON`, setup-uv's `UV_PYTHON_INSTALL_DIR`/`UV_CACHE_DIR`) |
| new dependency | none |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the helper forwards the interpreter pin and nothing unrelated
`tests._uv_env.uv_subprocess_env()` returns `PATH`, `HOME`, `USER`, `VIRTUAL_ENV` and every
`UV_*` variable that is set in `os.environ` (so `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR`,
`UV_PROJECT_ENVIRONMENT`, `UV_CACHE_DIR`), with their values; an unset one is absent and an
unrelated variable is not returned.

### AC-002: a `uv run` with the helper's env keeps the project venv's interpreter
In a scratch uv project pinned to 3.12 by `.python-version` whose `.venv` was built on 3.13 under
`UV_PYTHON=3.13`, `uv run python -V` with `uv_subprocess_env()` leaves `.venv` on 3.13, while the
same call with the old five-key env rebuilds it on 3.12 (the control that shows the check can fail).
Both arms also see `UV_PYTHON_INSTALL_DIR` so only the pin differs. Skipped when uv cannot find
both interpreters offline, except in nightly's py313 job (`GITHUB_ACTIONS` set and
`UV_PYTHON=3.13`), the one CI run that has both, where it fails instead.

### AC-003: the two e2e tests use the helper
`tests/e2e/test_verify_health_dashboard.py` and `tests/e2e/test_reconcile_orphan_sweep.py` build
their subprocess env with `uv_subprocess_env()` and no longer list the forwarded keys themselves.

## Verification

| scenario | mode | test |
|---|---|---|
| S1, S2 | unit | tests/unit/test_nightly_py313_venv.py::test_ac_001_helper_forwards_interpreter_pin |
| S1 | subprocess | tests/unit/test_nightly_py313_venv.py::test_ac_002_uv_run_keeps_venv_interpreter |
| S1 | unit (source) | tests/unit/test_nightly_py313_venv.py::test_ac_003_e2e_callers_use_helper |
| S1 | manual | a `workflow_dispatch` nightly on main after merge shows a green `py313` |

## Open Questions

none

## Refinement Decisions

- Fix the tests, not the workflow: pinning `.python-version` in the job would dirty the checkout
  that other tests read, and the scrubbed env would still be wrong for anyone running locally with
  `UV_PYTHON` set. Undo: revert one PR.
- One shared helper that forwards every `UV_*` variable (review F2) instead of adding `UV_PYTHON` to
  two tuples, so no future uv setting needs an edit. Cost: one small module under `tests/`.
- Small revertible test-only fix: approved by the project rule (auto-merge on green CI); no card.
- Intent: none. spec-validator skipped (3 ACs, default skip at <= 8).
