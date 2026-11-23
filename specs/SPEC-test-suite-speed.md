---
type: spec
task_slug: test-suite-speed
status: approved
created: 2026-11-23
tags: [tests, speed, local-gate]
test_framework: pytest
interview_rounds: 0
summary: Cut local full-suite time without dropping coverage — format AST hit locations lazily, and share one live make run across the three identical live e2e tests.
---

# SPEC — test-suite-speed

## Intent

Plan item S2 (thread "Harness Maker 개발 퀄리티·속도·병목 개선안", 2026-11-22). PR #74 already
sharded PR CI (13 → ~5 min), so the remaining cost is the local full suite that `hm check`
runs about twice per task (~10 min on 4 cores, CPU-bound). Two tests waste time without
buying coverage:

- `tests/unit/test_memory_tier_removed.py::test_no_imports_remain` (24.5 s) builds a
  location string for every one of ~1.05 M AST nodes, though it reports only hits. Parse +
  walk alone is 1.8 s.
- `tests/e2e/test_plugin_live.py` launches a real `claude -p` make session 4 times; three
  use identical arguments (Side/en/task) and only read the result.

## Outcomes

- `ast_uses` returns exactly the same hits as before, but formats a location only on a hit.
- The live e2e module launches `claude` once per distinct argument set (2), not 4 times,
  and every existing assertion still runs.

## In-Scope Scenarios

- **S1 (normal):** Given a source tree with removed-tier imports, names, attributes, prose and
  string literals, when `ast_uses` scans it, then it returns the same hit list as the
  unchanged code.
- **S2 (edge):** Given the same tree, when `ast_uses` scans it, then the number of location
  formattings equals the number of hits.
- **S3 (normal):** Given `claude` on PATH, when `test_plugin_live.py` runs, then `claude` is
  launched twice (default args once, Production once) and all live tests pass.
- **S4 (failure):** Given `claude` absent, the live tests skip as before; given the weekly
  limit, the shared run skips every test that depends on it.

## Non-Goals

- Moving tests to nightly, deleting or weakening any test, test-impact selection.
- The other slow tests (`test_overhaul_p1_*`): their cost is real coverage work.
- CI workflow changes (done in PR #74).

## Constraints

| Constraint | Source |
|---|---|
| pytest; ruff, ruff format, mypy --strict clean | CLAUDE.md |
| No new dependency; Python only (fake `claude` is a Python script) | CLAUDE.md |
| Live tests keep their `skipif(not _claude_available())` guard | existing contract |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: ast_uses returns the unchanged hit list

On a seeded tree (`src/pkg/a.py` with every hit kind plus prose and a string literal,
`tests/b.py` with one name, `tests/excluded.py` excluded), `sorted(ast_uses(...))` equals the
golden list computed by running the unchanged code at spec time.

### AC-002: ast_uses formats a location only on a hit

On the same tree, calls to `Path.relative_to` on scanned files during `ast_uses` equal
`len(hits)` (9), not the node count.

### AC-003: the live e2e module launches claude once per argument set

With a fake `claude` (Python script) first on PATH that records each launch and writes a
harness, running `pytest tests/e2e/test_plugin_live.py` passes every test and records exactly
2 launches.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | `tests/unit/test_test_suite_speed.py::test_ac_001_ast_uses_golden` |
| S2 | unit | `tests/unit/test_test_suite_speed.py::test_ac_002_location_formatted_only_on_hit` |
| S3 | integration | `tests/unit/test_test_suite_speed.py::test_ac_003_live_make_runs_once_per_args` |
| S4 | review | skip paths read by the reviewer; module-scoped `pytest.skip` skips dependents |

## Open Questions

none

## Refinement Decisions

- **Intent:** none picked; HM-LIGHT-LANE targets token cost, not test time.
- **Scope:** only the two tests that waste time with no coverage gain (measured 2026-11-22
  `--durations`); the 71 s `test_ac008` matrix and the brownfield module are real coverage.
  Undo: revert one PR.
- **AC-003 oracle is a fake `claude`:** CI has no `claude`, so the module would otherwise
  only ever skip there; the fake makes the launch count observable deterministically.
- **Hit order is not a contract:** `rglob` order is filesystem-dependent and the only caller
  asserts emptiness, so AC-001 compares sorted lists.
- **Approval:** the DRI said "끝까지 진행해. 추천대로" (2026-11-23) in this thread; no
  irreversible decision is involved.
