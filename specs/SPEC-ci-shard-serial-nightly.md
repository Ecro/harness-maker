---
type: spec
task_slug: ci-shard-serial-nightly
status: approved
created: 2026-11-23
tags: [harness-maker, spec, ci, release, nightly]
test_framework: pytest
interview_rounds: 0
summary: "Split CI's full pytest run into three parallel shards on PRs, pushes and releases; move the one serial full-suite run from release.yml to nightly, which also gains a Python 3.13 run and skips a main SHA it already passed."
---

# SPEC — ci-shard-serial-nightly

## Intent

The repository is public, so GitHub-hosted runner minutes cost nothing; what CI costs is waiting.
Every PR push waits about 13 minutes for `quality-gate` (pytest -n auto is 12m17s of it on one
4-vCPU runner, run 45091302995), and every merge that changes the version waits about 32 minutes for
release.yml, whose serial pytest takes about 28 minutes on a SHA that ci.yml has just tested in
parallel. A local 4-core run spends 29 minutes of CPU in 9m27s of wall time, so the suite is
CPU-bound and more runners shorten it.

CI is still the only check not run by the agent that wrote the change (run 549 caught two tests that
failed only under `/home/runner`; #45 fixed a test red only on main), so the suite must keep running
in full before merge. The DRI chose this restructure on a decision card on 2026-11-23 ("샤드 병렬 +
직렬은 nightly").

## Outcomes

- O1. A PR's full test suite runs as three parallel shards that together select every test exactly
  once; `quality-gate` finishes in about 5 minutes instead of 13.
- O2. release.yml runs the same three shards instead of a serial run; a release takes about
  8–10 minutes instead of 32.
- O3. The serial full-suite run (the order- and isolation-dependence oracle) lives in nightly, which
  also runs the suite on Python 3.13 and skips a scheduled run when main has not moved since the
  last green nightly.
- O4. Locally nothing changes: `hm check` still derives and runs the full, unsharded suite.

## In-Scope Scenarios

- S1 (normal). A PR is opened; CI starts `quality-gate (1/3)`, `(2/3)`, `(3/3)` in parallel; each
  runs ruff, format, mypy and its share of pytest; a job named `quality-gate` reports green only
  when all three passed.
- S2 (edge). `HM_TEST_SHARD` is unset (a developer's machine, `hm check`); pytest runs every test.
  It is set to `1/1`; pytest also runs every test.
- S3 (failure). One shard fails; the `quality-gate` summary job fails too, so a required check or
  an agent reading the PR sees red. `HM_TEST_SHARD` holds an unusable value (`4/3`, `x`); pytest
  stops with a usage error instead of silently running nothing or everything.
- S4 (edge). The scheduled nightly fires and main's SHA equals the last successful nightly's SHA;
  the serial and 3.13 jobs are skipped. A manual dispatch always runs them.

## Non-Goals

- Running the live host tests (`claude` signed in) in CI; they still run locally (needs a secret
  and paid calls; tracked separately).
- macOS runners, a Python matrix on PRs, or changing which tests exist.
- Branch-protection or ruleset settings (DRI's repository setting).
- Changing `boundary`, `dependency-review`, `boundary-advisory`, publishing or autotag.

## Constraints

| constraint | value |
|---|---|
| test framework | pytest (+ pytest-xdist, already a dependency) |
| new dependency | none (no pytest-split; the shard filter lives in `tests/conftest.py`) |
| local gate | the pytest `run:` line stays `uv run pytest -x --tb=short -n auto --dist loadfile`, so `verification_plan` derives the same command; sharding comes only from job `env` |
| check names | the matrix jobs are `quality-gate (N/3)`; a summary job keeps the bare name `quality-gate` |
| action pins | reuse the SHAs already in the workflows |
| shard unit | the test file (keeps `--dist loadfile`'s within-file ordering) |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the shard filter partitions the suite by file
With `HM_TEST_SHARD=i/n`, the test session keeps exactly the tests whose file maps to shard `i`
(a stable hash of the file's path relative to the rootdir, modulo `n`); over `i = 1..n` every
collected test is kept exactly once. With the variable unset or `1/1`, nothing is deselected. A
value that is not `i/n` with `1 <= i <= n` stops the session with a usage error.

### AC-002: ci.yml shards quality-gate and keeps a summary check
In `.github/workflows/ci.yml`, job `quality-gate` has `strategy.matrix.shard: [1, 2, 3]`, job-level
env `HM_TEST_SHARD: "${{ matrix.shard }}/3"`, the steps `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy --strict src tests` and
`uv run pytest -x --tb=short -n auto --dist loadfile`, and no `continue-on-error`. A second job
whose `name` is `quality-gate` needs `quality-gate`, runs `if: always()` and fails unless the
result is `success`. `install-cmd-regression` has no `needs`.

### AC-003: release.yml tests with the same shards, not serially
In `.github/workflows/release.yml`, job `quality-gate` has the same shard matrix and env, every
pytest command in it carries `-n`, and `build` still needs `quality-gate`. No release job runs a
serial full-suite pytest.

### AC-004: nightly owns the serial run, adds 3.13 and skips an unchanged SHA
`.github/workflows/nightly.yml` has a job that runs `uv run pytest -x --tb=short` (no `-n`), a job
that runs the suite with `UV_PYTHON: "3.13"`, and a first job that, on a `schedule` event, compares
`github.sha` with the head SHA of the last successful nightly run and outputs whether to run; both
test jobs need it and run only on its yes. A `workflow_dispatch` always runs.

### AC-005: the local gate still runs the full, unsharded suite
`verification_plan.read_plan(repo).primary_commands()` is unchanged by this task: it equals the
golden list computed from the unchanged code, so `hm check` runs the full suite with no shard
argument.

### AC-006: the shard variable does not leak into tests
Inside a test body `HM_TEST_SHARD` is not in `os.environ`, even when the session was started with
it set, so a test that runs an inner pytest is not sharded by the outer one.

## Verification

| scenario | mode | test |
|---|---|---|
| S2, S3 | unit + subprocess | tests/unit/test_ci_shard_serial_nightly.py::test_ac_001_shard_filter_partitions_by_file |
| S1, S3 | unit (workflow parse) | test_ac_002_ci_quality_gate_sharded |
| S1 | unit (workflow parse) | test_ac_003_release_quality_gate_sharded |
| S4 | unit (workflow parse) | test_ac_004_nightly_serial_py313_skip |
| S2 | unit (golden) | test_ac_005_local_gate_unsharded |
| S2 | subprocess | test_ac_006_shard_env_does_not_leak |
| S1 | manual | this PR's CI shows three green shards and a green `quality-gate`, and its wall time |

## Open Questions

none

## Refinement Decisions

- Approval: the DRI picked option A ("샤드 병렬 + 직렬은 nightly") on the 2026-11-23 01:21Z card,
  which is exactly this SPEC's design; stamped approved without another card (ask-less rule).
  Undo: revert one PR.
- Shard by file hash in `tests/conftest.py`, not pytest-split: no new dependency and no durations
  file to keep fresh. Cost: shards are balanced by chance, not by measured time. Undo: swap the hook.
- Ruff, format and mypy run in every shard (about 20 s each, free on a public repo) so the steps
  need no `if:` and every shard is a complete gate on its own. Undo: add `if: matrix.shard == 1`.
- Summary job named `quality-gate`: keeps the old check name meaning "the full suite passed", in
  case a required check or an agent waits on that name. Undo: delete the job.
- `install-cmd-regression` loses `needs: quality-gate`: the dependency only saved minutes, which
  cost nothing here, and made the job finish 13 minutes late.
- Nightly drops its parallel full-gate: every push to main already runs the sharded suite on the
  merge commit; nightly keeps what nothing else runs (serial order, 3.13, fresh-install readiness).
- The skip check uses `gh run list` in the workflow (read-only `actions: read`), like the shell
  steps already in release.yml; no new Python module for a one-line comparison.
- Intent: none (`[intent] none`; HM-LIGHT-LANE is about session cost, not CI).
- spec-validator skipped (6 ACs, default skip at <= 8).
