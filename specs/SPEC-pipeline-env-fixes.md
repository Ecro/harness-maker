---
type: spec
task_slug: pipeline-env-fixes
status: approved
created: 2026-11-10
tags: [correctness, uv, worktree, runner, wrapup]
test_framework: pytest
interview_rounds: 2
summary: hm stops mutating the user's project through uv, picks a runner that can run, and preflight works from the task worktree.
---

# SPEC — pipeline-env-fixes

## Intent

Three bugs were reproduced on 0.65.3 (RESEARCH-hm-non-token-improvements F1–F3). Two stop a task
from landing, so they come before any other non-token work.

1. Every rendered `uv run --with <plugin> …` call runs inside the user's project. In a Python
   project that has a `pyproject.toml` and is not uv-managed, uv then creates `.venv/` and an
   untracked `uv.lock` there. `hm check` picks that pytest-less `.venv`, reports the test as
   `deselected`, and `hm worktree task-land` refuses forever on the `uv.lock` it recreates.
2. `hm worktree task-preflight <slug> "$(pwd)"` exits 1 when the shell is inside the task
   worktree, which is where a chained stage leaves it.
3. Rendered text and the CLI disagree: wrapup has no action for `hm check` exit 2, its
   `observe` example omits the required `--relation`, and `pytest_runner` cuts
   `uv run --with pytest pytest` at the wrong token.

## Outcomes

- hm's own calls (the stage `hm` prefix, hooks, skills, commands) create no `.venv/` and no
  `uv.lock` in a project that has no tracked `uv.lock`, and `task-land` lands there.
- `hm check` runs tests with an interpreter that has pytest, or stops with a reason that names
  what is missing and what to do. It never reports a runner that could not start as `deselected`.
- A uv-managed project (tracked `uv.lock`) keeps what in-project `uv run` gave it: a `.venv` in
  step with the lock, and its `.venv/bin` on the gate's PATH.
- A stage started with the shell in the task worktree gets its worktree path back, exit 0.
- Wrapup's rendered text covers every `hm check` exit code and its examples parse.
- A harness rendered by 0.65.3 upgrades in one `make` with no duplicate hook and no stale grant.

## In-Scope Scenarios

- **S1 (normal).** Given a git project with `pyproject.toml` and no `uv.lock`, When the rendered
  hm prefix runs `task-preflight`, a hook command and `hm check` in the task worktree, Then
  `git status --porcelain` shows no `uv.lock` and no `.venv` in the base or the worktree, and
  `task-land` lands the task.
- **S2 (edge).** Given that project and a root without `.venv`, When `hm check` needs an
  interpreter, Then it does not call uv, exits degraded, and its reason says that there is no
  `.venv/bin/python` in that root, that a worktree does not share the main checkout's `.venv`,
  and that hm creates one only for a tracked `uv.lock`.
- **S3 (normal).** Given that project and a root with its own `.venv` that has pytest, When the
  RED gate runs, Then it judges the AC test with that interpreter.
- **S4 (normal).** Given a project with a tracked `uv.lock`, When `hm check` needs an
  interpreter, Then it runs `uv sync --frozen --inexact` in that root and uses its
  `.venv/bin/python`; `uv.lock` is not rewritten.
- **S5 (failure).** Given a `.venv` whose Python has no pytest and no gate command that runs
  pytest, When the gate runs, Then it exits degraded and the reason names the pytest-less
  `.venv`.
- **S6 (failure).** Given a runner that ends without writing a JUnit file, When the gate runs,
  Then every requested test is `error` with the runner's last output line, never `deselected`.
- **S7 (normal).** Given the shell is in `.worktrees/<slug>/`, When `task-preflight <slug>
  "$(pwd)"` or `task-refresh <slug> "$(pwd)"` runs, Then it acts on the main checkout and prints
  the same worktree path.
- **S8 (upgrade).** Given a harness rendered by 0.65.3 with one user hook of its own and one
  user hook sharing a group with a harness hook, When `make --update` runs, Then every harness
  hook exists once with the new prefix, the old-prefix harness grants are gone, and both user
  hooks are untouched.
- **S9 (normal).** Given a CI file whose gate is a bare `pytest -q` or `ruff check .`, When the
  gate runs, Then `<root>/.venv/bin` comes first on its PATH.

## Non-Goals

- A second test runner for non-pytest stacks (card D, separate SPEC).
- The user's own toolchain commands (`uv run pytest -q`, `uv run ruff …`): they keep running in
  the project, unchanged.
- Using the main checkout's `.venv` from a linked worktree. An editable install there imports
  the main checkout's code, so the gate would judge the wrong tree.
- The second-opinion oracle's default toolchain (`uv run pytest/ruff/mypy`, used only when
  `second_opinion.models` is set). It still runs in the project; logged as a follow-up.
- Windows venv layouts (`Scripts/`); the gate already assumes `.venv/bin/python`.
- Deleting the unreferenced partials (card E). They get the new prefix by the same replacement.

## Constraints

| Constraint | Value |
|---|---|
| Test framework | pytest (mandatory) |
| Interpreter owner | one function in `check.py` decides the project interpreter and its reason; `gate_commands`, `pytest_runner` and `verification_cache` all read it |
| Runner entry | `spec_machine.collect_runner` stays the single entry; the fix is in `check.pytest_runner` |
| Render | deterministic, no shell-out during render |
| External commands | no `shell=True`, a timeout on every subprocess (implementation-patterns.md) |
| Hook identity | stays keyed on `python -m harness_maker.<invocation>`; no new identity rule |
| Stage budgets | a stage over its budget is raised by its measured growth only (DRI card, round 2) |
| Docs | README, HOW-IT-WORKS and CHANGELOG state the new prefix and the `.venv` rule |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | Every rendered harness-maker invocation (stage `hm` prefix, hooks, skills, commands, plugin-root `commands/`, `skills/`, `hooks/`) is spelled `uv run --no-project --with <ref> …` | public API/CLI contract | The prefix is typed by the model and matched by user permission rules; changing it again costs every user a re-render. |
| IRR-002 | The rendered `permissions.allow` grants move to the new prefix and the old-prefix harness grants are pruned on re-render | security/permission boundary | A grant is a permission boundary; pruning must match only what harness-maker itself rendered. |
| IRR-003 | `task-preflight` and `task-refresh` accept a linked worktree as their base argument and act on its main checkout | public API/CLI contract | Stage text and any user script may come to rely on calling them from the worktree. |

## Acceptance Criteria

### AC-001: every harness-maker invocation hm emits carries `--no-project`
In every render arm (Production and Side, claude-code and codex) and in the plugin-root
`commands/`, `skills/` and `hooks/`, no line contains `uv run --with`; every `uv run` followed by
a harness-maker `--with` reference reads `uv run --no-project --with`. The remedy the worktree
gate prints at run time uses the same spelling. Project toolchain commands are not touched.

### AC-002: hm calls leave a project without a tracked `uv.lock` clean and landable
In a temp git project with a `pyproject.toml` and no `uv.lock`, driven through the prefix read
from a rendered stage: after `task-preflight`, one rendered hook command and `hm check` in the
worktree, `git status --porcelain` is empty in the worktree, lists only hm's own runtime files
under `.claude/` in the base, and neither holds a `.venv`; `hm check`'s reason names the
tracked-`uv.lock` rule. With a gitignored `.venv` that
has pytest in the worktree, the runner hm picks judges a failing AC test as `failed`. After a
commit there, `hm worktree task-land` exits 0 with the squash on the base.
Runs the real `uv`; skipped when `uv` is not on PATH.

### AC-003: `pytest_runner` picks a runner that can run pytest
Golden rows over (`.venv` state, gate commands) → runner argv. A `.venv` whose Python imports
pytest wins; a `.venv` without pytest is skipped; `uv run --with pytest pytest -q` yields
`uv run --with pytest pytest`; `python -m pytest -q` yields `python -m pytest`; nothing usable
yields no runner, and the degraded reason then names the pytest-less `.venv`.

### AC-004: one owner decides the interpreter, and uv runs only for a tracked `uv.lock`
Golden rows over (`uv.lock` tracked, uv on PATH, `.venv` present) → (uv argv, interpreter or
reason). With a tracked lock and uv on PATH, `uv sync --frozen --inexact` runs in the root
whether or not `.venv` exists; in every other row uv is not invoked. Without an interpreter the
reason is the row's text. `gate_commands` (no-CI path), `pytest_runner` and
`verification_cache`'s spec commands return that same interpreter or reason.

### AC-005: a runner that wrote no JUnit file reports `error` with the cause
When the runner process ends without writing a JUnit file, every requested test id gets outcome
`error` whose detail holds the last output line (for a pytest-less interpreter:
`No module named pytest`), whatever the exit code. A test that exists in its file but that a
completed run did not execute stays `deselected`.

### AC-006: preflight and refresh work from inside a task worktree
With the base argument pointing at `.worktrees/<slug>/` (or at another task's worktree),
`task-preflight <slug>` exits 0, prints the path git lists for branch `hm/<slug>`, registers the
session under the main checkout, and leaves `git status --porcelain` in the worktree empty;
`task-refresh <slug>` resolves the same base.

### AC-007: wrapup's text covers exit 2 and its `observe` example parses
The rendered wrapup gate step carries execute's exit-2 rule word for word, and every
`hm intent question observe` example in the rendered stages names each option the real argparse
parser marks required.

### AC-008: a 0.65.3 harness upgrades without duplicates or stale grants
Re-rendering over the captured 0.65.3 `settings.json` and `.codex/hooks.json`, with a user hook
in its own group, a user hook added to a harness hook's group, and a user-written
`uv run --with requests …` grant, yields each harness hook once with the new prefix (the one
kept in the mixed group included), no harness grant with the old prefix, and the three user
entries unchanged. An old-prefix grant built from the current install reference is pruned even
when that reference does not contain `harness-maker`.

### AC-009: the bench still gets an interpreter and its provenance guard accepts the new prefix
`scripts/bench_light_lane.py` reads the plugin reference out of a stage rendered with the new
prefix and still refuses a stale one. The bench fixture carries a `uv.lock`, so a built template
tracks it and AC-004's sync rule applies to every cell.

### AC-010: gate subprocesses find the project's own tools first
Every gate subprocess (gate commands, the AC test run) gets `<root>/.venv/bin` as the first PATH
entry when that directory exists, and an unchanged PATH when it does not.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1, S2, S3 | integration (real uv) | test_ac_002 |
| S4 | unit (uv recorded, real git) | test_ac_004 rows |
| S5 | unit | test_ac_003 rows |
| S6 | unit (real interpreter) | test_ac_005 |
| S7 | unit (real git) | test_ac_006 |
| S8 | unit | test_ac_008 |
| S9 | unit | test_ac_010 |
| prefix everywhere | render | test_ac_001 |
| wrapup text | render | test_ac_007 |
| bench guard and fixture | unit | test_ac_009 |
| bench still solves a task | manual | one tier-1 task, hm arm, 1 run, hidden tests pass (about $1) |

## Open Questions

## Refinement Decisions

- **Fix approach (DRI card, 2026-11-10):** `--no-project` on every invocation plus runner
  hardening, not symptom-only.
- **Preflight from a worktree (DRI card):** resolve the base automatically.
- **Wrapup exit 2 (DRI card):** fix the call and rerun, as execute does.
- **Intent (DRI card):** none.
- **Missing `.venv` (DRI card, round 2, 2026-11-10):** hm runs `uv sync` only for a tracked
  `uv.lock`; otherwise it uses the user's `.venv` or test command, else stops with the reason.
- **Stage budgets (DRI card, round 2, 2026-11-10):** raise a stage's budget by its measured
  growth only (about 13 chars per stage for the prefix, about 60 for wrapup's exit-2 rule).
- **Standing instruction (DRI, 2026-11-10 12:02Z, "모두 너의 추천대로 진행해"):** the defaults below
  were decided on the recommended option without a card, and this SPEC was approved on it.
- **Default — a worktree needs its own `.venv` (spec-validator, critical):** hm does not borrow
  the main checkout's `.venv`. In a project without a tracked `uv.lock` the gate in a fresh
  worktree stops with the reason until that worktree has an interpreter. A false green from the
  wrong tree is worse than a stop.
- **Default — sync on every lookup, `--frozen --inexact` (spec-validator):** with a tracked lock
  hm syncs each time (a no-op costs about 30 ms), so a task that changes the lock does not test
  against a stale `.venv`. `--frozen` never rewrites `uv.lock`; `--inexact` keeps packages the
  user installed by hand, as in-project `uv run` did.
- **Default — a tracked `uv.lock` that an older hm wrote (spec-validator):** 0.65.x could commit
  its stray `uv.lock`. hm cannot tell it from a real one, so it syncs; when the resulting
  `.venv` has no pytest the reason says so and names both remedies (add pytest to a dependency
  group; if the lock is not the user's, `git rm uv.lock`).
- **Default — "tracked" means `git ls-files` lists it:** an untracked `uv.lock`, or one outside
  a git repo, does not make a project uv-managed.
- **Default — pytest presence is probed by importing it** (`<python> -c "import pytest"`, with
  a timeout), not read from the filesystem, so a `.venv` with system site-packages is not
  skipped by mistake.
- **Default — the Maker skill's size cap rises 4,500 → 4,539** (three invocations × 13 chars), the
  same measured-growth rule as the stage budgets; no wording is trimmed.
- **Default — a preserved harness hook is rewritten, not only a mixed-group one:** any
  `harness_maker.*` hook command kept from disk gets the flag, including one the template no
  longer ships. Nothing else in the command changes.
- **Default — the bench fixture gets a committed `uv.lock`** for both arms. Until now its
  `.venv` came from in-project `uv run`, which this SPEC removes.
- **Default — grant pruning:** the existing must-name-harness-maker regex family is extended to
  the old-prefix shapes, and the exact old-prefix literals of the current render are pruned too.
- **Default — `bench_hash` moves `569e17ef29ab` → `92672094f80e`** because the committed lock is
  inside the hashed fixture. The task bytes are unchanged; rows measured before this SPEC keep
  the old hash and are not mixed with new ones (a run always uses a fresh `--out`).
- **Review (2026-11-10), accepted:** the mutation gate gets the project `.venv/bin` on PATH like
  every other gate; a failed `uv sync` is the reason shown on the AC and RED paths too, not a
  bare "no pytest runner"; `project_python` answers once per project state, so a failing sync
  is not retried by each reader; a chained hook command has only its harness-maker calls
  rewritten.
