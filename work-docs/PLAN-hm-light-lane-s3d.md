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
adrs: 9
summary: "With no CI file, verification_cache run --spec-slug runs gates from the trusted SPEC's test_framework; the light check opts in"
---

# PLAN: hm-light-lane-s3d (SPEC-derived gates when there is no CI file)

## 🎯 Goal

When a repo has no CI file, the light check's Check 2 should pass from the trusted SPEC's
`test_framework`, plus `ruff`/`mypy` when `pyproject.toml` configures them, instead of exiting
3. On a passing tree, light runs then skip review and verify. Today that happens 0 of 30 times on
the bench. Every CI-path byte stays as it is at `4bd3d3d8` (SPEC-hm-light-lane-s3d).

## 🧭 ADRs

### ADR-001: Opt-in by slug, trust through `light_lane.lane_of`
**Decided by:** agent. `run` gains `--spec-slug <slug>` (IRR-001). Inside `run_gates`, a lazily
imported `light_lane.lane_of(root, slug)` must return `light`. The stamp's `test_framework` must
then equal the `.md`'s, and the value must be a key of the closed map. A path flag was rejected
because it lets the caller name a file the boundary never reads. The import stays lazy:
`light_lane` already imports `verification_cache` lazily, so a top-level import either way would
create a cycle.

### ADR-002: "CI absent" is a field of the plan reader, not a second rule
**Decided by:** agent. `VerificationPlan` gains `ci_absent: bool = False`, set on `read_plan`'s
two early returns: no workflows directory, and no workflow file in it. `to_json` lists its keys
explicitly and does not gain this one, so `hm verification_plan`'s output is unchanged. The
other degraded causes (unreadable YAML, no recognised command) and `run`'s "no blocking gate"
case leave `ci_absent` false, and the flag stays inert for them (SPEC AC-002).

### ADR-003: The plan is a closed map plus two pyproject probes
**Decided by:** agent. `_SPEC_FRAMEWORKS = {"pytest": "pytest"}` is the only map, matched
exactly. `spec_plan(root, framework) -> list[str] | str` returns either the command list or the
reason it cannot be built. It parses `pyproject.toml` with `tomllib`; a parse error is a reason,
and a missing file means no tools are configured. It adds `ruff check .` when `"ruff" in tool`,
and `mypy` (with `.` unless `tool.mypy.files` is set) when `"mypy" in tool`, then pytest. The
order is ruff, mypy, pytest. The runner is `uv run` when `git ls-files --error-unmatch uv.lock`
succeeds, and `<python> -m` otherwise. No SPEC text reaches a command string.

### ADR-004: The interpreter is the caller's, never hm's
**Decided by:** agent. Probe of 2026-10-15: under `uv run --with <src> hm`, `PATH` starts with
uv's builds-v0 environment (= `sys.prefix`, with no pytest), then the `--with` archive bin, then
the project's new `.venv/bin`. `<python>` is the first `python3` and then `python` on `PATH`,
skipping `Path(sys.prefix)/"bin"` and every entry under the uv cache directory (`UV_CACHE_DIR`,
else `uv cache dir`, run with a timeout, else `~/.cache/uv`). It must answer
`<py> -c "import pytest"` with rc 0 within 10 s. The command records the absolute interpreter
path, so the marker says which interpreter ran. When there is no candidate, the result is a
reason and exit 3 (SPEC AC-008).

### ADR-005: Absent means `ci`, on the marker and in the output
**Decided by:** agent (IRR-002, IRR-004). `mark_passed` gains a keyword `extra: dict | None`,
which only the SPEC path passes: `{gate_source: "spec", spec_slug, test_framework}`.
`is_run_fresh(key, commands, *, source=None)` becomes stricter. With `source=None` (the CI path)
it rejects any marker that carries `gate_source`. With a source, it requires an exact
`gate_source`, `spec_slug` and `test_framework`. The summary JSON gains `gate_source` and
`spec_slug` only on the SPEC path. `_commands_hash` is unchanged, so CI markers keep their
bytes.

### ADR-006: Trust before freshness
**Decided by:** agent (SPEC AC-013). On the SPEC path, the order is: `read_plan` (`ci_absent`) →
trust (ADR-001) → `spec_plan` → `is_run_fresh(..., source=spec)` → gates. A SPEC that lost its
trust after a pass gets exit 3, never `cached: true`, even when its files sit outside the
relevant key (`spec.dir` under `work-docs/`).

### ADR-007: The stamp records `test_framework` the way it records `lane`
**Decided by:** agent (IRR-003; the precedent is stage 3a IRR-005). `SpecApproval.test_framework:
str | None = None`. `approve` fills it from a `_md_test_framework(yaml_path)` that mirrors
`_md_lane`. `_dump_machine_yaml` drops a `None` value, as it does for `lane`. `_run_approve`'s
`exclude` gains `"test_framework"`, so `approve`'s stdout keeps its four keys. `approval` is in
`HASH_DENYLIST_TOP`, so no stamp is released.

### ADR-008: Only the light-check branch of the templates changes
**Decided by:** agent. In `verify_check_2.md.j2`, inside `{% if light_check %}`, the command
gains `--spec-slug <slug>` and the exit-3 bullet reads "no CI file and no usable SPEC plan, or
CI unreadable". This needs a light-check-only command block, because the command line is shared
today. `execute_light_check.md.j2`'s record block gains `gate_source: <the run JSON's
gate_source, ci when absent>`. `light_lane.light_check_passed` compares it with the marker's
(SPEC AC-010). Verify's own Check 2 is unchanged: no strong reason was found, and its degraded
path already says the gates were guessed.

### ADR-009: The bench fixture is the outcome test
**Decided by:** agent. The SPEC's purpose is the bench number, so AC-014 runs the real
`uv run --with <src> hm` on a copy of `scripts/bench/timeparse` under `INTEGRATION=1`, with the
agent `PATH` the bench gives its agent. The unit tables (AC-003, AC-008) use fake bin
directories and do not prove that real interpreter resolution works.

## 📝 Implementation Plan

0. **Phase 0: goldens and the interpreter check, before any edit.** depends_on: none ·
   parallel_group: 0 · merge_hazards: none · scope: a detached `4bd3d3d8` worktree under the
   scratchpad; `tests/fixtures/light_lane_s3d/` (new): `run` stdout, exit and marker bytes for
   AC-001's fixture domain, `approve` stdout keys, and render SHAs for AC-011, with the capture
   script beside them, as in `light_lane_s3a/`. Also re-run the uv probe with the bench agent's
   `PATH` (from `scripts/bench_light_lane.py` `_AGENT_ENV`) and confirm that ADR-004 finds an
   interpreter that imports pytest · exit: fixtures committed. If the probe finds no
   interpreter, **stop and return to the DRI** (the SPEC's first open question) before Phase 1
   · risk: low · rollback: delete the fixtures.
1. **Phase 1: Python.** depends_on: 0 · parallel_group: 1 · merge_hazards: none · scope:
   `src/harness_maker/verification_plan.py` (`ci_absent`),
   `src/harness_maker/observability/verification_cache.py` (`--spec-slug`, `spec_plan`,
   interpreter resolution, `mark_passed(extra=)`, `is_run_fresh(source=)`, summary keys),
   `src/harness_maker/spec_machine.py` (`SpecApproval.test_framework`, `_md_test_framework`, the
   approve exclude, the dump pop), `src/harness_maker/light_lane.py` (the gate_source agreement),
   `tests/unit/test_verification_cache_spec_plan.py` (new),
   `tests/unit/test_spec_approve_test_framework.py` (new), `tests/unit/test_light_lane.py` ·
   exit: AC-001…008, 010, 012 and 013 green; `tests/unit/test_verification_cache_run.py` green
   unchanged; ruff, ruff format and mypy --strict clean · risk: medium (`run` is load-bearing for
   every stage; AC-001 and AC-002 guard it) · rollback: revert the phase.
2. **Phase 2: templates.** depends_on: 1 · parallel_group: 2 · merge_hazards: snapshots, size
   baseline · scope: `templates/stages/_partials/verify_check_2.md.j2` (light_check branch only),
   `templates/stages/_partials/execute_light_check.md.j2` (record `gate_source`),
   `tests/render/test_render_light_lane_s3d.py` (new), the re-captured light-check reference and
   Codex execute snapshots with a dated note, and `tests/structural/surface_baseline.json` plus
   `work-docs/BASELINE-DELTA-hm-light-lane-s3d.md` only if the aggregate ratchet requires them.
   `CHANGELOG.md` · exit: AC-009 and AC-011 green; no new headings, so
   `test_step_sensitivity_registry.py` green unchanged; `uv run pytest tests -n auto` green
   except the known environment failures · risk: low · rollback: revert the phase.
3. **Phase 3: the bench outcome.** depends_on: 2 · scope:
   `tests/integration/test_light_lane_s3d_timeparse.py` (new) · exit: AC-014 green under
   `INTEGRATION=1`. Re-running the eval on light tasks and recording the skip count is a
   follow-up and does not gate this PLAN · risk: medium (environment-dependent; ADR-004) ·
   rollback: revert the test.

## 🚧 Contract Boundaries

### Do not change
- `run` without `--spec-slug`, and `run` with it whenever CI is present: stdout, exit code and
  marker bytes (AC-001, AC-002).
- `hm verification_plan`'s JSON output, `compute_relevant_skip_key`, `compute_skip_key`,
  `_commands_hash`, `check`, `mark-pass`, `key` and `explain`.
- `templates/stages/_partials/verify_checks.md.j2`, `wrapup_steps.md.j2`, `review.md.j2`,
  `loop.md.j2` and the Claude execute command: byte-identical renders (AC-011).
- `spec_machine.approval_state`, `approval_content_hash`, `HASH_DENYLIST_TOP`, and `approve`'s
  stdout keys.
- `light_lane.lane_of`. In `light_check_passed`, every existing condition stays. The one
  addition is the gate_source agreement check.

## 🧪 Testing Strategy

Phase 0 captures every golden from `4bd3d3d8` before an edit. The Phase 1 and 2 tests are
written against those goldens and against the SPEC's tables (RED), then implemented (GREEN).
Gate execution in the unit tests uses a fake runner, or stub interpreters in temp bin
directories that answer the import probe. Only AC-014 runs real `uv` and real pytest, and only
under `INTEGRATION=1`. `HARNESS_MAKER_CACHE_DIR` is a `tmp_path` in every test (checklist 7).

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| No interpreter outside hm imports pytest in the bench agent's environment, so the number does not move | Phase 0 measures it first and stops for the DRI; AC-014 is the outcome test |
| A global pytest without the project's dependencies runs the suite | It fails with ImportError: exit 1, a false fail, never a false pass; named in the SPEC's open questions |
| A CI-path regression in `run` | AC-001 differential and AC-002 metamorphic, both against `4bd3d3d8` |
| A SPEC-plan pass read as a CI pass | Absent-means-ci on both sides; AC-006 property; AC-010 record/marker agreement |
| `.md` `test_framework` edited after approval | Trusted only when it equals the stamp's (ADR-007); AC-004 row |
| Wrapup's `mark-pass` on a repo with no CI file overwrites the SPEC marker | Only after the boundary already skipped; the effect is conservative (no later skip). Wrapup using the SPEC plan is a follow-up |
| Old CLI with a new render | argparse exits 2 with no JSON line, which the light check reads as not a pass, so review runs |
| Import cycle between `light_lane` and `verification_cache` | Both imports stay function-local (ADR-001) |
| Interpreter probe cost | One `import pytest` probe per candidate, 10 s cap, on the SPEC path only |

## ✅ Success Criteria

- [ ] AC-001 … AC-014 of SPEC-hm-light-lane-s3d pass.
- [ ] Every CI-path `run` output and every typed-stage render is byte-identical to `4bd3d3d8`.
- [ ] The eval is re-run on light tasks and the skip count is recorded (follow-up; today 0 of 30).

## 🔜 Follow-ups

- On a light lane, wrapup Step 2 could pass `--spec-slug`, so a repo with no CI file does not
  run the suite twice.
- Bind `approval.lane` and `approval.test_framework` into a hash (inherited from stage 3a).
- More map keys (`vitest`, `cargo`) once a bench fixture needs them.
