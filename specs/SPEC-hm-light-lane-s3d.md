---
type: spec
task_slug: hm-light-lane-s3d
status: draft
created: 2026-10-15
tags: [harness-maker, spec, light-lane, verification-cache, regression, ci, cost]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 3d of HM-LIGHT-LANE: with no CI file, the light check runs gates from the trusted SPEC's test_framework"
---

# SPEC: hm-light-lane-s3d (stage 3d, SPEC-derived gates when there is no CI file)

## 🎯 Intent

Stage 3a's light check (execute Step 4.2) runs verify's Check 2 as
`hm observability.verification_cache run --mode relevant`. That command derives its gates from
`.github/workflows`, and on a repo without that directory it exits `3` ("degraded: no readable
CI"). The light check never guesses the gates, so on exit 3 it writes no record, and review and
verify run anyway. In the 2026-10-15 eval (`docs/evals/RESULTS.md`), 0 of 30 light runs skipped
review and verify, because the bench fixture `scripts/bench/timeparse` has no CI. The DRI decided
on the 2026-10-15 card: "SPEC framework: With no CI file, run the SPEC's declared test_framework
(e.g. pytest) plus ruff/mypy only if pyproject configures them."

## 🌅 Outcomes

- **An opt-in SPEC plan, used only when there is no CI file.** `verification_cache run` gains
  `--spec-slug <slug>`. The flag has an effect only when CI is **absent**: there is no
  `.github/workflows` directory, or the directory holds no `*.yml`/`*.yaml` file. In every other
  case the flag is inert and `run` behaves exactly as it does without it. That covers readable
  CI, unreadable YAML, CI with no recognised command, and CI whose every gate is
  `continue-on-error`. Without the flag, `run` is byte-identical to `4bd3d3d8` everywhere.
- **The plan comes from a closed map, never from SPEC text.** The SPEC's `test_framework`
  selects a key, and it must be exactly `pytest`. The map holds one entry today. Other value
  (`Pytest`, `pytest + hypothesis`, `unittest`, empty) leaves `run` on its unchanged exit 3, with
  the reason extended by why the SPEC plan was not used. The plan runs in this order, stopping at
  the first failure:
  1. `ruff check .`, only when `pyproject.toml` parses and its `tool` table has a `ruff` key;
  2. `mypy`, only when its `tool` table has a `mypy` key. It runs with no target when
     `[tool.mypy]` sets `files`, and with `.` otherwise;
  3. pytest, always.
  The runner depends on `uv.lock`. When `uv.lock` is **tracked at HEAD**, each command runs as
  `uv run <tool> …`. Otherwise it runs as `<python> -m <tool> …`, where `<python>` is the first
  `python3`, then `python`, on the caller's `PATH` that is outside hm's own environment and can
  import pytest. hm's own environment is `sys.prefix`'s bin directory and every `PATH` entry
  under the uv cache directory. When no such interpreter exists, the result is exit 3 with that
  reason. A `pyproject.toml` that does not parse is also exit 3. An untracked `uv.lock` does not
  count: `uv run --with … hm` writes one itself (see Refinement Decisions, probe).
- **The plan is used only from a trusted SPEC.** All of the following must hold:
  - `light_lane.lane_of(root, slug)` is `light`. That means an approved or exempt SPEC with no
    irreversible ids, whose stamp recorded `lane: light`.
  - The approval stamp's new `test_framework` (IRR-003) equals the `.md` frontmatter's
    `test_framework`.
  - The value is a key of the map.
  A stamp without the field (every stamp written before this change) never yields a SPEC plan.
  These checks run on every call, before any cached marker is reused.
- **The source is on the marker and in the output.** A SPEC-plan run prints its usual JSON plus
  `"gate_source": "spec"` and `"spec_slug"`. On a clean pass on an unchanged tree it writes the
  usual `run` marker (`writer: run`, `checks` = the commands, `commands_sha256`) plus
  `gate_source: spec`, `spec_slug` and `test_framework`. A CI-derived run and its marker carry no
  new key; a marker without `gate_source` means `ci`. The exit codes are still `0`, `1`, `3` and
  `4`, with today's meanings.
- **Sources never stand in for each other.** The CI path's freshness check accepts only a marker
  without `gate_source`. The SPEC path's freshness check accepts only a marker whose
  `gate_source` is `spec`, with the same `spec_slug`, `test_framework` and `commands_sha256`. A
  `mark-pass` marker satisfies neither, as today.
- **The light check opts in and records the source.** Under the partial's `light_check` flag,
  Check 2's command gains `--spec-slug <slug>`. Its exit-3 line says that neither CI nor a usable
  SPEC plan was found. The light-check record gains a top-level `gate_source` copied from the run
  JSON (`ci` when the key is absent). `light_lane.light_check_passed` additionally requires the
  record's `gate_source` to equal the marker's, where absent means `ci` on both sides. A record
  and marker written before this change therefore still agree.
- **Typed stages are untouched.** Verify's Check 2 (no `light_check`), wrapup, review, the loop
  and the Claude execute command render byte-identical to `4bd3d3d8`. Only the light-check
  reference file and the Codex execute skill change.

## 📋 In-Scope Scenarios

### S1: A trusted light task on a repo with no CI file passes Check 2 from its SPEC
**Given** a git repo with no `.github/workflows`, a `pyproject.toml` without `[tool.ruff]` or `[tool.mypy]`, a passing pytest suite, and an exempt `lane: light` SPEC whose stamp recorded `test_framework: pytest`
**When** the light check runs `hm observability.verification_cache run --root . --mode relevant --spec-slug <slug>`
**Then** the JSON line has `"exit": 0`, `"gate_source": "spec"` and one command, a pytest invocation
**And** the marker for the relevant key has `writer: run` and `gate_source: spec`, and the light check writes a record with `gate_source: spec`

### S2: Repos with CI behave exactly as today
**Given** a repo with readable CI, unreadable CI YAML, CI with no recognised command, or CI whose gates are all `continue-on-error`
**When** `run` is called with or without `--spec-slug`
**Then** stdout, exit code and marker are identical to the `4bd3d3d8` `run` on the same fixture

### S3: Without the flag, a repo with no CI file is unchanged
**Given** a repo with no `.github/workflows`
**When** `run` is called without `--spec-slug`
**Then** it exits `3` with `{"cached": false, "commands": [], "reason": …}` and writes no marker, byte-identical to `4bd3d3d8`

### S4: An untrusted or unknown SPEC never yields gates
**Given** a repo with no CI file and a SPEC that is full, unapproved, edited after approval, carrying irreversible ids, stamped before `approval.test_framework` existed, whose `.md` `test_framework` differs from the stamp's, or whose framework is not `pytest`
**When** `run --spec-slug <slug>` is called
**Then** it exits `3` with `commands: []`, writes no marker, and stderr names why the SPEC plan was not used
**And** a cached SPEC marker for the same tree is not reused once the SPEC has lost its trust

### S5: The plan follows the project's configuration
**Given** a repo with no CI file and a trusted pytest SPEC, with every combination of `[tool.ruff]`, `[tool.mypy]` (with and without `files`) and `uv.lock` (tracked, untracked, absent)
**When** the plan is derived
**Then** the command list equals the golden list for that combination, in the order ruff, mypy, pytest

### S6: A SPEC-plan pass is never read as a CI pass, nor the reverse
**Given** a marker from a SPEC plan, a CI plan, or `mark-pass` for a key
**When** `run` (CI path or SPEC path) checks freshness, or `light_lane.light_check_passed` compares the record with the marker
**Then** a marker is reused only by a run of its own source, and the boundary skips only when the record's `gate_source` equals the marker's

### S7: The SPEC plan fails closed
**Given** a SPEC plan whose gate exits non-zero (pytest exit 5, no tests collected, included), times out, cannot start, or whose tree changes during the run
**When** `run --spec-slug` finishes
**Then** it exits `1` or `4` as the CI path does and writes no marker

### S8: The bench fixture earns the skip
**Given** a copy of `scripts/bench/timeparse` committed as a git repo, a trusted light pytest SPEC, and hm invoked as `uv run --with <src> hm` from the fixture with the bench agent's `PATH`
**When** `run --spec-slug` runs and the light-check record is written from its output
**Then** the exit is `0` with `gate_source: spec`, and `light_lane.light_check_passed` is true

## 🚫 Non-Goals

- Changing verify's own Check 2, wrapup Step 2 or the verify-before-completion skill. Typed and
  wrapup runs keep the guessed-gates `mark-pass` fallback on a repo with no CI file (Open
  Questions).
- A SPEC plan when CI exists but is unreadable, declares no recognised command, or has no
  blocking gate. The DRI's option says "with no CI file".
- Frameworks other than `pytest`, and lint or type configuration outside `pyproject.toml`
  (`ruff.toml`, `.ruff.toml`, `mypy.ini`, `setup.cfg`).
- `ruff format --check`. The DRI's option names ruff and mypy; the guessed path's format check
  stays where it is.
- Installing tools (`uv run --with pytest`, `pip install`). A configured tool that the chosen
  interpreter cannot run fails the gate.
- Changing the verification key, `hm verification_plan`'s output, `check`, `mark-pass`, `key` or
  `explain`.
- Binding `approval.lane` or `approval.test_framework` into a hash. That is a follow-up from
  stage 3a, and this stage inherits it.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Trust | The framework is read only from a SPEC `light_lane.lane_of` reads as `light`, and only when the stamp's `test_framework` equals the `.md`'s; no command string contains SPEC text | The `.md` is outside the approval hash; a model-written value may only select a closed-map key |
| Fail closed | Every read error, unknown value, missing interpreter or unparseable `pyproject.toml` is exit 3 with `commands: []` and no marker | Exit 3 is already "not a pass" for the light check |
| Exit contract | `{0, 1, 3, 4}` unchanged in meaning; no new exit code | Rendered stages branch on `exit` |
| CI path | Without the flag, or with CI present, stdout, exit and marker byte-identical to `4bd3d3d8` | Boundary goldens; every harness rendered today |
| One reader | `light_lane.lane_of` decides trust; `verification_cache` imports it lazily | Two trust readers would disagree on a malformed SPEC |
| Interpreter | Never hm's own environment (`sys.prefix`, uv cache entries); probe bounded by the existing `_run_quiet` style timeout | Probe 2026-10-15: under `uv run --with <src> hm` the first `python` on `PATH` is hm's ephemeral env, which has no pytest |
| Subprocess | `shell=False`, timeouts on every probe and gate (implementation-patterns.md) | Project rule |
| Render | Verify, review, wrapup, loop and the Claude execute command byte-identical to `4bd3d3d8`; no new headings | AC-011; `test_step_sensitivity_registry.py` |
| Compatibility | Python 3.12; an old render never passes the flag (no change); an old CLI rejects the flag with argparse exit 2, which the light check reads as no JSON line = not a pass | Mixed versions fail closed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add `--spec-slug <slug>` to `hm observability.verification_cache run` | public API/CLI contract | The rendered light check calls it; removing or renaming it breaks every harness rendered with it |
| IRR-002 | `run`'s stdout JSON gains `gate_source: "spec"` and `spec_slug` on the SPEC path; absent means `ci` | public API/CLI contract | Rendered prose copies `gate_source` into the record; once harnesses read it, the key stays |
| IRR-003 | Add the optional field `test_framework` to the SPEC approval stamp (`approval.test_framework`), recorded by `approve` from the `.md` (human and `--exempt`), outside the content hash and excluded from `approve`'s stdout | schema/file format/storage layout | Every new stamp carries it, and the SPEC plan trusts only it; removing it later turns every SPEC plan off. Additive, releases no stamp |
| IRR-004 | Verification cache markers written by a SPEC plan carry `gate_source: spec`, `spec_slug`, `test_framework`; a marker without `gate_source` means `ci` | schema/file format/storage layout | Readers (`is_run_fresh`, `light_check_passed`, `check`'s printed marker) depend on the absent-means-ci rule; CI markers can never gain the key without changing that rule |
| IRR-005 | The light-check record gains top-level `gate_source: ci \| spec`; absent means `ci` | schema/file format/storage layout | Wrapup commits the record into history, and the boundary compares it with the marker |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (CLI) | `tests/unit/test_verification_cache_spec_plan.py::test_trusted_spec_plan_passes_and_marks_its_source` |
| S2 | unit (CLI, differential) | `tests/unit/test_verification_cache_spec_plan.py::test_ci_repos_match_4bd3d3d8_with_and_without_the_flag` |
| S3 | unit (CLI, golden) | `tests/unit/test_verification_cache_spec_plan.py::test_no_ci_without_flag_matches_4bd3d3d8` |
| S4 | unit (CLI) | `tests/unit/test_verification_cache_spec_plan.py::test_untrusted_spec_yields_no_gates`, `tests/unit/test_verification_cache_spec_plan.py::test_trust_is_rechecked_before_cached_reuse` |
| S5 | unit | `tests/unit/test_verification_cache_spec_plan.py::test_plan_follows_project_configuration` |
| S6 | unit (property) | `tests/unit/test_verification_cache_spec_plan.py::test_markers_are_reused_only_by_their_own_source`, `tests/unit/test_light_lane.py::test_record_and_marker_gate_source_must_agree` |
| S7 | unit (CLI) | `tests/unit/test_verification_cache_spec_plan.py::test_spec_plan_fails_closed` |
| S8 | integration (`INTEGRATION=1`) | `tests/integration/test_light_lane_s3d_timeparse.py::test_timeparse_light_check_passes_from_its_spec` |
| Outcome (stamp) | unit | `tests/unit/test_spec_approve_test_framework.py::test_stamp_records_test_framework_and_keeps_cli_output` |
| Outcome (interpreter) | unit | `tests/unit/test_verification_cache_spec_plan.py::test_interpreter_is_never_hms_own_environment` |
| Outcome (render) | unit (render, differential) | `tests/render/test_render_light_lane_s3d.py::test_light_check_passes_the_slug_and_records_the_source`, `tests/render/test_render_light_lane_s3d.py::test_typed_stages_match_4bd3d3d8` |

### AC-001: Without the flag, run is byte-identical to 4bd3d3d8
### AC-002: The flag is inert unless CI is absent
### AC-003: The SPEC plan is the golden function of the project's configuration
### AC-004: Only a trusted SPEC with a stamped, known test_framework yields a plan
### AC-005: A SPEC-plan run reports and marks its source and keeps the exit contract
### AC-006: Markers are reused only by a run of their own source
### AC-007: The approval stamp records test_framework without releasing a stamp or changing approve's output
### AC-008: The pytest interpreter is never hm's own environment
### AC-009: The light check passes the slug and copies the gate source into the record
### AC-010: The boundary skips only when the record's and the marker's gate source agree
### AC-011: Typed stages and the Claude execute command render byte-identical to 4bd3d3d8
### AC-012: The SPEC plan fails closed on any non-pass
### AC-013: Trust is re-checked before any cached marker is reused
### AC-014: The timeparse bench fixture passes the light check from its SPEC

## ❓ Open Questions

- **The interpreter rule is the main risk.** A probe on 2026-10-15 ran
  `uv run --with <src> python` in a copy of `scripts/bench/timeparse`. The first `python` on
  `PATH` was uv's ephemeral build environment, and `import pytest` failed there. uv also
  prepends its `--with` archive bin directory and the fixture's freshly created `.venv/bin`
  (no pytest), and it writes an untracked `uv.lock`. Under the bench, the first interpreter that
  passes the rule is harness-maker's dev venv, inherited from the bench's own `uv run`. That
  suffices for timeparse, which has no dependencies. In a real project with dependencies, a
  global pytest would fail with ImportError: a false fail, never a false pass. DRI: accept "first
  interpreter outside hm that imports pytest", or require the project's own `.venv`?
- Wrapup Step 2 calls `run` without the flag. On a repo with no CI file it still exits 3 and
  re-runs the guessed gates, and its `mark-pass` overwrites the SPEC marker. The saving is
  therefore the review and verify turns only, and the suite runs twice. Should wrapup pass
  `--spec-slug` on a light lane? That is a follow-up, out of scope here.
- The brief named "unreadable/absent" CI. The DRI's option says "with no CI file". This SPEC
  follows the DRI: absent only (Non-Goals).
- Every SPEC stamped before this change lacks `approval.test_framework`, so it gets no SPEC plan
  until it is re-stamped. Bench SPECs are written and stamped during the run, so they are
  unaffected.
- An edit to `approval.test_framework` itself is not detected (as for `approval.lane`; see
  PLAN-hm-light-lane-s3a's follow-ups).
- Whether light runs now skip review and verify on the bench (0 of 30 today) stays unmeasured
  until the eval is re-run on this change.

## 🔍 Refinement Decisions

- Interview not run: the scope is the DRI's 2026-10-15 card option, quoted verbatim in Intent.
  The details below are agent decisions for the DRI to accept or change at approval.
- Lane `full`: five irreversible decisions (two CLI contract changes, three storage-format
  changes) and about nine files.
- Opt-in by slug, not by path: `--spec-slug` resolves the SPEC through `light_lane.lane_of`,
  the boundary's own reader. A path flag would let the caller point at a file that the resolver
  never reads.
- "CI absent" means no workflows directory, or no workflow file in it. That follows the DRI's
  "with no CI file". The other degraded reasons mean that CI exists and its gates are unknown,
  and a SPEC plan there could be narrower than CI, which is the divergence `verification_plan`
  exists to close.
- The framework is trusted through the stamp, as `lane` is through IRR-005 of stage 3a. The
  approval hash covers only the machine yaml, so a `.md` value read alone would be trusted
  without approval.
- Closed map with one key, matched exactly (`pytest`). All 235 SPECs in this repo declare exactly
  `pytest`. A tolerant match would let free text select gates.
- Order ruff, mypy, pytest: the cheap gates first, stop at the first failure, as `_run_all` does.
- `uv run` only when `uv.lock` is tracked at HEAD. The probe showed that `uv run --with … hm`
  writes an untracked `uv.lock` into a project that had none, and `uv run pytest` there finds no
  pytest.
- Verify's Check 2 stays byte-identical. Its degraded path already guesses the gates with an
  explicit "the gates were guessed", and the brief found no strong reason to change the typed
  path. The light check is the only caller of the flag.
- The marker and the record use absent-means-ci rather than writing `gate_source: ci` on CI
  runs. That keeps every CI-path byte unchanged (AC-001, AC-002) and keeps old records and
  markers comparable.
- Work stays on the session's designated branch `claude/hm-light-lane-bench`, as in the earlier
  stages.
