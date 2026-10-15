---
type: spec
task_slug: bench-cli-provenance
status: approved
created: 2026-10-15
tags: [harness-maker, spec, python, uv, bench, eval]
test_framework: pytest
interview_rounds: 0
lane: light
summary: "uv --with installs rebuild on source edits, and the bench refuses a stale hm CLI"
---

# SPEC: the hm arm runs the CLI it claims to run

## 🎯 Intent
Rendered commands call `uv run --with <checkout> hm …`. uv rebuilds that install only when a
cache key changes, and the default key is `pyproject.toml` alone. At an unchanged version
(0.62.0) every source edit kept running a build cached on 2026-10-14 15:25 UTC, before stage 2a.
The full eval of 2026-10-15 therefore graded 3a templates against a pre-2a CLI: the light
approval never recorded a lane, so all 30 light runs still ran review and verify, and PR #21's
autopilot fix never ran. The published 26x ratio and 9 stalls measure that mismatch, not hm.

## 🌅 Outcomes
- A source or template edit at an unchanged version reaches the next `uv run --with` call.
- `bench_light_lane.py run` refuses, before any model spend, when the hm arm's CLI is not the
  checkout's code.

## 📋 In-Scope Scenarios

### S1: an edit reaches the next call (AC-001)
**Given** a checkout whose `harness_maker` was already installed through `uv run --with <path>`
**When** a `src/**/*.py` or `src/harness_maker/templates/**` file is edited and the same command runs again
**Then** the edited bytes are what the call imports or reads.

### S2: a stale CLI stops the bench (AC-002)
**Given** an hm template whose `uv run --with <path>` install differs from `<path>/src/harness_maker`
**When** `bench_light_lane.py run` reaches the point after the templates are built
**Then** it exits 2, prints both digests and the fix, and starts no run and writes no row.

### S3: a fresh CLI passes (AC-003)
**Given** the install and the source hold the same package bytes (all files but `__pycache__`)
**When** the check runs
**Then** it returns without output and the grid runs as before.

## ✔️ Acceptance Criteria

### AC-001
A source edit at an unchanged version reaches `uv run --with <checkout>` (S1).

### AC-002
bench run refuses before any model spend when the hm arm's CLI differs from the checkout (S2).

### AC-003
bench run proceeds when the installed CLI matches the checkout (S3).

## 🚫 Non-Goals
- Changing how rendered commands invoke `hm` (the `uv run --with` prefix stays).
- Re-running the eval: that follows this change and is not part of it.
- Detecting dependency drift: the digest covers the package bytes only; a dependency change in
  pyproject.toml already triggers a rebuild through the cache keys.

## ⚙️ Constraints
- `pytest`. The live uv probe for S1 builds a throwaway copy in `tmp_path`; it is skipped when
  `uv` is not on PATH.
- The check reads the `uv run --with <path>` prefix from the rendered `/hm:spec` command and
  runs it with `--no-project`, so it resolves the same cached build the agent does and writes
  nothing (no `.venv`) into the template every cell is copied from. It runs under the agent's
  allowlisted environment (same `HOME`, same uv cache) and expands `$HOME` the way the agent's
  shell does, because the renderer writes `$HOME/...` for a checkout under home.
- Cache keys: `pyproject.toml`, `src/**/*.py`, `src/harness_maker/templates/**/*` and
  `src/harness_maker/**/*.yaml` (the rubric data the CLI reads at runtime).
- Tests: `tests/unit/test_bench_cli_provenance.py`.

## ✅ Verification
| Scenario | Mode | Oracle |
|---|---|---|
| S1 | integration (live uv, tmp copy) | golden: the edited marker is visible after the edit |
| S2 | unit (fake installed tree) | golden: exit 2, no `runs/` entry, no row |
| S3 | unit (identical trees) | golden: equality |

## ❓ Open Questions
None.

## Refinement Decisions
- Lane `light`: three files (pyproject.toml, the bench script, one test file), one session,
  no irreversible decision. Interview skipped: the failure and its fix were found and confirmed
  in the eval forensics of 2026-10-15; the DRI was told the plan in the thread.
- `irreversible_decisions: []`: a uv cache-key list is build configuration, reverted by deleting it.
