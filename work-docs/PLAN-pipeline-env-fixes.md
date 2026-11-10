---
type: plan
task_slug: pipeline-env-fixes
status: planning
created: 2026-11-10
spec: "[[SPEC-pipeline-env-fixes]]"
summary: Add --no-project to every harness-maker invocation, give check.py one interpreter owner, and let preflight resolve the main checkout.
surface_allowance:
  chars: 294
  reason: "SPEC-pipeline-env-fixes: `--no-project ` (13 chars) at every rendered harness-maker invocation, plus wrapup's exit-2 rule and the full `observe` example (+60). DRI-confirmed on 2026-11-10 (card: raise by the measured growth only)."
  delta_doc: BASELINE-DELTA-pipeline-env-fixes.md
  commands:
    execute: 13
    hm-execute: 13
    spec: 13
    hm-spec: 13
    research: 13
    hm-research: 13
    metrics: 13
    health: 65
    make: 65
    uninstall: 39
    wrapup: 73
    hm-wrapup: 73
---

# PLAN — pipeline-env-fixes

## Phases

- **P1 prefix.** scope: `templates/**` (stage macro, settings, hooks, codex hooks, skills, commands, partials), plugin-root `commands/make.md` `hooks/hooks.json` `skills/`, `gates/worktree_gate.py` remedy text, `render.py` (old-prefix grant pruning, ref refresh in mixed groups), `scripts/bench_light_lane.py` `_CLI_PREFIX`, pinned baselines and budgets. exit: `uv run pytest -q tests/unit/test_pipeline_env_fixes.py -k "ac_001 or ac_008 or ac_009"`. risk: a pinned snapshot or budget test goes red for a reason other than the prefix. rollback: `git checkout -- src/harness_maker/templates src/harness_maker/render.py commands hooks skills`.
- **P2 interpreter and runner.** scope: `check.py` (`project_python`, `pytest_runner`, `run_tests`, `gate_env`), `observability/verification_cache.py` spec commands, `scripts/bench/timeparse/uv.lock`. exit: `uv run pytest -q tests/unit/test_pipeline_env_fixes.py -k "ac_003 or ac_004 or ac_005 or ac_010" tests/integration/test_pipeline_env_fixes_uv.py`. risk: an existing gate test relied on `.venv` being chosen without a probe. rollback: `git checkout -- src/harness_maker/check.py src/harness_maker/observability/verification_cache.py`.
- **P3 preflight base.** scope: `worktree.py` `_cli_task_preflight`, `_cli_task_refresh` and one helper that maps a linked worktree to its main checkout. exit: `uv run pytest -q tests/unit/test_pipeline_env_fixes.py -k ac_006`. risk: the helper misreads a bare repo or a submodule. rollback: `git checkout -- src/harness_maker/worktree.py`.
- **P4 text and docs.** scope: `templates/stages/wrapup.md.j2` (exit 2, `observe --relation`), stage budgets, README, `docs/HOW-IT-WORKS*.md` one paragraph, CHANGELOG, re-rendered harness. exit: `uv run pytest -q tests/unit/test_pipeline_env_fixes.py -k ac_007 tests/unit/test_overhaul_p1_surface.py tests/structural/test_command_size_budget.py`. risk: a stage goes over budget by more than its measured growth. rollback: `git checkout -- src/harness_maker/templates/stages docs README.md CHANGELOG.md`.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/second_opinion_oracle.py`
- `src/harness_maker/hm.py`
- `.claude/intent.yaml`
- `docs/evals/RESULTS.md`
- `scripts/bench/tasks/`
- `tests/fixtures/hm_cost_p4/`

## ADRs

- ADR-001: The prefix is `uv run --no-project --with <ref>` at every emitted site; the change is a text replacement in templates and plugin-root files, with no new render variable. **Decided by:** user (card "--no-project + 러너 보강", IRR-001)
- ADR-002: `check.project_python(root)` is the only place that decides the project interpreter. It returns the interpreter or a reason; with a git-tracked `uv.lock` and uv on PATH it first runs `uv sync --frozen --inexact` in the root. `gate_commands`, `pytest_runner` and `verification_cache._spec_commands` read it. **Decided by:** user (card "uv.lock 있을 때만 uv sync"); flags by agent (SPEC Refinement Decisions)
- ADR-003: `pytest_runner` keeps its signature for `collect_runner`. It uses the `.venv` interpreter only when `<python> -c "import pytest"` exits 0, otherwise the first gate command that runs pytest, cut after the pytest token found by skipping uv's value-taking options and `python -m`. The reason for "no runner" comes from a companion function, not from a changed return type. **Decided by:** agent
- ADR-004: `run_tests` reports `error` when the JUnit file does not exist after the run, whatever the exit code. **Decided by:** agent
- ADR-005: A gate subprocess gets `<root>/.venv/bin` first on PATH when it exists; nothing else in its environment changes. **Decided by:** agent
- ADR-006: Linked-worktree resolution lives in the two CLI entry points (`task-preflight`, `task-refresh`), so every base-scoped read and write below them sees the main checkout. **Decided by:** user (card "base를 자동으로 찾기", IRR-003)
- ADR-007: Old-prefix grants are pruned two ways: the existing must-name-harness-maker regex family gains the shapes 0.65.3 rendered, and the exact old-prefix twin of each grant in the current render is pruned. Hook identity is unchanged; every harness-managed command in a preserved entry (a mixed group, or one the template no longer ships) is rewritten to the `--no-project` spelling. **Decided by:** agent (IRR-002)
- ADR-008: The bench fixture commits a `uv.lock`; `bench_hash` therefore moves `569e17ef29ab` → `92672094f80e` and its two pins move with it. **Decided by:** agent
- ADR-009: Stage budgets rise by the measured growth only. **Decided by:** user (card "올리기")
