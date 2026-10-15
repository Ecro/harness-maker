---
type: plan
task_slug: hm-light-lane-s3d
status: planning
created: 2026-10-15
spec: "[[SPEC-hm-light-lane-s3d]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
intent: HM-LIGHT-LANE
lane: full
tdd: true
adrs: 6
summary: "With no CI file, verification_cache run --spec-slug runs pytest (+ configured ruff/mypy) in the project .venv from a trusted light SPEC"
---

# PLAN: hm-light-lane-s3d (SPEC-derived gates when there is no CI file)

## 🎯 Goal

On a repo with no CI file, the light check's Check 2 should pass from the trusted SPEC's
`test_framework`, run in the project's `.venv`, instead of exiting 3. On a passing tree, light
runs then skip review and verify, which happened in 0 of 30 bench runs. Every other `run`
outcome, and every typed-stage render, stays byte-identical to `4bd3d3d8`
(SPEC-hm-light-lane-s3d). This is the spec-validator's minimal scope (2026-10-15).

## 🧭 ADRs

### ADR-001: Opt-in by slug; trust is `lane_of` plus the `.md` value
**Decided by:** agent (minimal scope). `run` gains `--spec-slug <slug>` (IRR-001). On the SPEC
path, a lazily imported `light_lane.lane_of(root, slug)` must return `light`. The
`SPEC-<slug>.md` frontmatter's `test_framework` must then be exactly `pytest`, read with the
frontmatter reader `lane_of` itself uses, from the directory `_named_spec_dir` resolves. Nothing
is stamped. The residual is recorded in the SPEC's Open Questions: an `.md` edit made after
approval, from another framework to `pytest`, is not detected. The import stays function-local,
because `light_lane` already imports `verification_cache` lazily.

### ADR-002: "CI absent" is a field of the plan reader
**Decided by:** agent. `VerificationPlan` gains `ci_absent: bool = False`, which is set on
`read_plan`'s two early returns. `to_json` lists its keys explicitly and does not gain this
one, so `hm verification_plan`'s output is unchanged. Every other degraded cause leaves the
flag inert (SPEC AC-001).

### ADR-003: The interpreter is `<root>/.venv/bin/python`, or nothing
**Decided by:** coordinator (validator scope). When `(root / ".venv" / "bin" / "python")`
exists, it is resolved to an absolute path and `shlex.quote`d into each command. Otherwise the
reason is "no .venv/bin/python", which gives exit 3. There is no PATH search, no import probe
and no `uv.lock` branch. Because the path sits inside the command strings, the unchanged
`_commands_hash` binds the marker to that interpreter. A `.venv` that lacks a tool fails that
gate (exit 1), and review stays in place.

### ADR-004: The plan is the closed map plus two pyproject keys, and trust comes before freshness
**Decided by:** agent. `_SPEC_FRAMEWORKS = {"pytest": "pytest"}`.
`spec_plan(root) -> list[str] | str` parses `pyproject.toml` with `tomllib`: a parse error is a
reason, and a missing file means no tools are configured. It returns, in order:
`<py> -m ruff check .` when `"ruff" in tool`; `<py> -m mypy` (with `.` unless
`tool.mypy.files` is set) when `"mypy" in tool`; then `<py> -m pytest`. The order in
`run_gates` is: `read_plan` (`ci_absent` and flag set) → trust (ADR-001) → interpreter
(ADR-003) → `spec_plan` → the unchanged `is_run_fresh(key, commands)` → `_run_all` → `_finish`.
Trust comes before freshness, so a SPEC that lost its trust never reports `cached: true`
(SPEC AC-003, last row). The summary gains `"gate_source": "spec"` on this path only (IRR-002).

### ADR-005: Only the light-check branch of the templates changes
**Decided by:** agent. Inside `{% if light_check %}` in `verify_check_2.md.j2`, the command block
gains `--spec-slug <slug>`. The command line is shared today, so the light check gets its own
block. Its exit-3 bullet reads "no CI file and no usable SPEC plan, or CI unreadable". In
`execute_light_check.md.j2`, the record's body line names the gate source: when the run JSON
has `gate_source: spec`, it writes `regression: pytest from SPEC (no CI file)`. The record
frontmatter, `light_lane.py` and verify's own Check 2 are unchanged.

### ADR-006: The bench fixture declares pytest, and the outcome test runs without the dev venv
**Decided by:** coordinator. `scripts/bench/timeparse/pyproject.toml` gains
`[dependency-groups] dev = ["pytest"]`. The 2026-10-15 probe showed the effect:
`uv run --with <src> hm …` then syncs a `.venv` with pytest, from the cache when it is warm and
over the network when it is cold. Both eval arms start from the changed file, so the before and
after numbers are not strictly comparable, and the eval notes say so. AC-007 runs the real
`uv run --with <src> hm` on a copy, with harness-maker's `.venv/bin` removed from `PATH`, so
that any pass comes from the fixture's own `.venv`.

## 📝 Implementation Plan

0. **Phase 0: goldens, before any edit.** depends_on: none · parallel_group: 0 ·
   merge_hazards: none · scope: `git archive` unpacks of `4bd3d3d8` and `df070f6c` under the
   scratchpad, and `tests/fixtures/light_lane_s3d/` (new). The fixtures hold `run`'s stdout,
   exit code and marker bytes over AC-001's domain, and the render SHAs for AC-006, with the
   capture script beside them, as in `light_lane_s3a/` · exit: fixtures committed · risk: low ·
   rollback: delete the fixtures.

   **Reference SHAs (2026-10-15, execution).** AC-001 and AC-003 compare against `4bd3d3d8`
   as written: `verification_cache.py` and `verification_plan.py` are byte-identical between
   `4bd3d3d8` and `df070f6c`. AC-006's render reference is **`df070f6c`**, the main tip this
   stage builds on, not `4bd3d3d8`: stage 3c (merged after the SPEC was written) changed those
   renders, so a `4bd3d3d8` reference would fail on 3c's bytes, not on 3d's. The AC's intent —
   3d adds no render bytes outside the light check — is what the `df070f6c` reference tests.
   The SPEC files are not edited (that would void the stamp); the test name
   `test_typed_stages_match_4bd3d3d8` is kept as the SPEC lists it, and its docstring says so.
1. **Phase 1: Python.** depends_on: 0 · parallel_group: 1 · merge_hazards: none · scope:
   `src/harness_maker/verification_plan.py` (`ci_absent`) and
   `src/harness_maker/observability/verification_cache.py` (`--spec-slug`, the trust check, the
   `.venv` interpreter, `spec_plan`, `gate_source` in the summary). New test files:
   `tests/unit/test_verification_cache_spec_plan.py` · exit: AC-001…004 green;
   `tests/unit/test_verification_cache_run.py` green and unchanged; ruff, ruff format and
   mypy --strict clean · risk: medium (`run` is load-bearing for every stage; AC-001 guards it)
   · rollback: revert the phase.
2. **Phase 2: templates.** depends_on: 1 · parallel_group: 2 · merge_hazards: snapshots and the
   size baseline · scope: `templates/stages/_partials/verify_check_2.md.j2` (the light_check
   branch only), `templates/stages/_partials/execute_light_check.md.j2` (the record body line),
   `tests/render/test_render_light_lane_s3d.py` (new), the re-captured light-check reference and
   Codex execute snapshots with a dated note, `tests/structural/surface_baseline.json` plus
   `work-docs/BASELINE-DELTA-hm-light-lane-s3d.md` only if the aggregate ratchet requires them,
   and `CHANGELOG.md` · exit: AC-005 and AC-006 green; `test_step_sensitivity_registry.py`
   green and unchanged; `uv run pytest tests -n auto` green except the known environment
   failures · risk: low · rollback: revert the phase.
3. **Phase 3: the bench fixture and the outcome test.** depends_on: 2 · scope:
   `scripts/bench/timeparse/pyproject.toml` (the dev group);
   `tests/unit/test_bench_light_lane.py`, if anything pins the fixture's bytes;
   `tests/integration/test_light_lane_s3d_timeparse.py` (new); a note in
   `docs/evals/RESULTS.md`'s next run that the fixture changed · exit: AC-007 green under
   `INTEGRATION=1` with harness-maker's dev venv off `PATH` · risk: medium (needs a warm uv
   cache or network) · rollback: revert the phase.

### Execution notes (2026-10-15)

- **ADR-005 as built.** The light check's command gains `--spec-slug <slug>` through an inline
  `{% if light_check %}` at the end of the shared command line rather than a separate block: the
  verify render is the same bytes either way (AC-006), and the template stays one source. The
  record body line is one parenthesis, and the `0` bullet is unchanged, to keep the reference
  file's growth to the two named additions.
- **Exit 3 on the SPEC path** carries `reason` = the CI reason plus `; no usable SPEC plan: <why>`,
  and no `gate_source` key: no SPEC gate ran. `gate_source: spec` is on exits 0, 1 and 4.
- **Older suites that froze the light check** (s3a `test_light_check_runs_the_kept_gates`, s3c
  `test_full_lane_changes_only_by_named_deltas` and `test_surface_meets_bounds`, phase3
  `test_the_stage_does_not_touch_the_verification_cache`) now undo exactly 3d's bytes with
  `tests/unit/light_lane_s3d_fixture.py::without_s3d` (each addition must occur exactly once)
  and compare with their frozen text, so any other addition still fails there.
- **The RESULTS note.** `docs/evals/RESULTS.md` is written by `bench_light_lane.py publish`
  ("do not edit"), so the fixture-change note went to `docs/evals/README.md`; the next
  `publish` run is where the RESULTS page changes.
- **Review round 1 (2026-10-15).** Applied: the SPEC plan also needs `.venv/pyvenv.cfg`, and
  exits 3 when HEAD tracks a `*.yml`/`*.yaml` under `.github/workflows` that the tree lacks, when
  HEAD's pyproject has `tool.ruff`/`tool.mypy` the working copy lacks, or when
  `ruff.toml`/`.ruff.toml`/`mypy.ini`/`.mypy.ini` exists; mypy takes no `.` when `[tool.mypy]`
  sets `files`, `modules` or `packages`; Check 2's light intro names the SPEC plan, the record
  example reads `regression: gates from SPEC (no CI file)`, and the fixture pins
  `pytest>=8`. The HEAD-workflow check counts only workflow files (what `read_plan` reads), so a
  tracked `.github/workflows/README.md` with no workflow still takes the SPEC plan.
- **Snapshots** were regenerated with `tests/snapshot/regenerate.py`: only
  `hm/execute-light-check.md`'s body hash moved, in all four profiles.

## 🚧 Contract Boundaries

### Do not change
- `run` without `--spec-slug`, and `run` with it whenever CI is present: stdout, exit code and
  marker bytes (AC-001).
- `is_run_fresh`, `mark_passed`, `_commands_hash`, `compute_relevant_skip_key`,
  `compute_skip_key`, `check`, `mark-pass`, `key`, `explain`, and `hm verification_plan`'s JSON.
- `src/harness_maker/light_lane.py` and `src/harness_maker/spec_machine.py`.
- `verify_checks.md.j2`, `wrapup_steps.md.j2`, `review.md.j2`, `loop.md.j2` and the Claude
  execute command: byte-identical renders (AC-006).
- The light-check record's frontmatter keys.

## 🧪 Testing Strategy

Phase 0 captures every golden from `4bd3d3d8` before an edit. The Phase 1 and 2 tests are
written against those goldens and the SPEC's tables (RED), then implemented (GREEN). Unit tests
run gates with a fake runner, or with a stub `.venv/bin/python` script in `tmp_path`. Only
AC-007 runs real `uv` and real pytest, and only under `INTEGRATION=1`. Every test sets
`HARNESS_MAKER_CACHE_DIR` to a `tmp_path` (checklist 7). AC-007's starting tree has run its
suite once with `.venv/bin/python -m pytest`, as execute's GREEN step does, so the `.pyc`
files are current. The cold case is a SPEC open question.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| A CI-path regression in `run` | AC-001 differential against `4bd3d3d8` over the whole product |
| The `.venv` is not the project's real environment (deps missing, or no pytest) | The gate fails with exit 1 and review stays. The stage's saving is lost, but no review is skipped on a failing gate. Stated honestly in the SPEC |
| A post-approval `.md` edit from another framework to `pytest` | Not detected; recorded as a SPEC open question. Only the one map key can be selected |
| First pytest run after an edit writes untracked `__pycache__` and moves the key | `run` exits 4 (not a pass) and review stays; AC-007's precondition mirrors the bench; a fixture `.gitignore` is an open question |
| A cold uv cache with no network leaves the `.venv` without pytest | Exit 1, and review stays; AC-007 needs a warm cache or network |
| The eval's before and after are not comparable | Stated in the SPEC and in the next RESULTS note |
| An old CLI with a new render | argparse exits 2 with no JSON line, which the light check reads as not a pass, so review runs |

## ✅ Success Criteria

- [ ] AC-001 … AC-007 of SPEC-hm-light-lane-s3d pass.
- [ ] The eval is re-run on light tasks and the skip count is recorded, noting the fixture
      change (follow-up; today 0 of 30).

## 🔜 Follow-ups

- On a light lane, wrapup Step 2 could pass `--spec-slug`, so a repo with no CI file does not
  run the suite twice.
- Bind the `.md` `test_framework` (and `approval.lane`) into the approval stamp, if the
  post-approval edit residual matters in practice.
- More map keys (`vitest`, `cargo`), and other interpreter locations, once a fixture needs them.
