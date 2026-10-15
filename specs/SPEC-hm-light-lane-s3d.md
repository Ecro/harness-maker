---
type: spec
task_slug: hm-light-lane-s3d
status: approved
created: 2026-10-15
tags: [harness-maker, spec, light-lane, verification-cache, regression, ci, cost]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 3d of HM-LIGHT-LANE: with no CI file, the light check runs pytest from the trusted SPEC in the project .venv"
---

# SPEC: hm-light-lane-s3d (stage 3d, SPEC-derived gates when there is no CI file)

## 🎯 Intent

Stage 3a's light check (execute Step 4.2) runs verify's Check 2 as
`hm observability.verification_cache run --mode relevant`. That command takes its gates from
`.github/workflows`. On a repo without that directory it exits `3` ("degraded: no readable CI"),
and because the light check never guesses the gates, it writes no record and review and verify
run anyway. In the 2026-10-15 eval (`docs/evals/RESULTS.md`), 0 of 30 light runs skipped review
and verify, because the bench fixture `scripts/bench/timeparse` has no CI. The DRI's choice on the
2026-10-15 card was: "SPEC framework: With no CI file, run the SPEC's declared test_framework
(e.g. pytest) plus ruff/mypy only if pyproject configures them." The scope is the
spec-validator's minimal one (coordinator, 2026-10-15).

## 🌅 Outcomes

- **An opt-in SPEC plan, used only when there is no CI file.** `verification_cache run` gains
  `--spec-slug <slug>`. The flag has an effect only when CI is **absent**: there is no
  `.github/workflows` directory, or the directory holds no `*.yml`/`*.yaml` file. In every other
  case the flag is inert and `run` behaves as it does without the flag: readable CI, unreadable
  YAML, CI with no recognised command, and CI whose gates are all `continue-on-error`. Without the
  flag, `run` is byte-identical to `4bd3d3d8`.
- **Trust.** The plan is built only when `light_lane.lane_of(root, slug)` is `light` and the
  SPEC `.md` frontmatter's `test_framework` is exactly the string `pytest`. `lane_of == light`
  means an approved or exempt SPEC, no irreversible ids, and a stamp lane of `light`. The check
  runs on every call, before any cached marker is reused. Any other case is exit 3 with
  `commands: []`, no marker, and a reason naming why the SPEC plan was not used.
- **One interpreter: the project's `.venv`.** When `<root>/.venv/bin/python` exists, each
  command is that absolute path followed by `-m <tool> …`. When it does not exist, the result is
  exit 3. There is no PATH discovery, no import probe and no `uv.lock` branch.
- **The plan.** The commands run in this order and stop at the first failure:
  1. `<py> -m ruff check .`, only when `pyproject.toml` parses and its `tool` table has a `ruff`
     key;
  2. `<py> -m mypy`, only when the `tool` table has a `mypy` key. The command has no target
     when `[tool.mypy]` sets `files`, and ends in `.` otherwise;
  3. `<py> -m pytest`, always.

  A `pyproject.toml` that does not parse gives exit 3. The interpreter path is inside every
  command string, so the existing `commands_sha256` binds the marker to it. The marker and
  `is_run_fresh(key, commands)` are unchanged. The exit codes are still `0`, `1`, `3` and `4`,
  with today's meanings.
- **The output names the source.** On the SPEC path only, `run`'s JSON line gains
  `"gate_source": "spec"`. A CI-derived run prints no new key, and the slug is not echoed.
- **The light check opts in.** Under the partial's `light_check` flag, Check 2's command gains
  `--spec-slug <slug>`. Its exit-3 line says that neither CI nor a usable SPEC plan was found.
  When the run JSON says `gate_source: spec`, the light-check record's one-line body names the
  source, for example `regression: pytest from SPEC (no CI file)`. The record's frontmatter is
  unchanged, and so is `light_lane.light_check_passed`.
- **Typed stages are untouched.** Verify's own Check 2, review, wrapup, the loop and the Claude
  execute command render byte-identical to `4bd3d3d8`. Only the light-check reference file and
  the Codex execute skill change.
- **The bench fixture declares pytest.** `scripts/bench/timeparse/pyproject.toml` gains
  `[dependency-groups] dev = ["pytest"]`, so that `uv run --with <src> hm …` syncs a `.venv`
  that has pytest in it. **This changes what both eval arms start from.** The plain arm and the
  /hm: arm both get the new `pyproject.toml`, so the eval baseline before and after this change
  is not strictly comparable.
- **Probe of 2026-10-15** (a copy of the fixture with that change, committed as a git repo):
  - `uv run --with <src> hm observability.verification_cache key --root .` created `.venv` and
    installed 5 packages (pytest and its dependencies). Then `.venv/bin/python -m pytest -q`
    passed 20 tests.
  - It needed no network here: the same command with `UV_OFFLINE=1` succeeded, because the uv
    cache already held pytest.
  - With an empty `UV_CACHE_DIR` and `UV_OFFLINE=1`, `uv sync` failed ("Packages were
    unavailable because the network was disabled"). A cold cache therefore needs the network,
    through the proxy.
  - uv also wrote an untracked `uv.lock`, before hm starts, so the key is stable across the run.
    `.venv` is ignored through uv's own `.venv/.gitignore`.
  - The fixture has no `.gitignore`, and the first pytest run after a source edit writes
    untracked `__pycache__/*.pyc` files. That moves the relevant key: the same tree went from
    `539da2e2…` to `c58126d8…`. A repeat run with current `.pyc` files kept it stable
    (`bc96d46f…` twice). See Open Questions.

## 📋 In-Scope Scenarios

### S1: A trusted light task on a repo with no CI file passes Check 2 from its SPEC
**Given** a git repo with no `.github/workflows`, a `.venv/bin/python` that has pytest, a passing suite, no `[tool.ruff]`/`[tool.mypy]`, and an exempt `lane: light` SPEC with `test_framework: pytest`
**When** the light check runs `hm observability.verification_cache run --root . --mode relevant --spec-slug <slug>`
**Then** the JSON line has `"exit": 0`, `"gate_source": "spec"` and the single command `<root>/.venv/bin/python -m pytest`
**And** the usual `run` marker is written for the relevant key, and the record's body line names pytest from the SPEC

### S2: Everything outside the opt-in case behaves exactly as today
**Given** any fixture repo whose CI is present (readable, unreadable, no recognised command, all advisory) or absent
**When** `run` is called without `--spec-slug`, or with it when CI is present
**Then** stdout, exit code and marker bytes equal the `4bd3d3d8` `run` on the same fixture

### S3: The plan follows the project's configuration
**Given** a repo with no CI file, a trusted pytest SPEC and `.venv/bin/python`, with each combination of `[tool.ruff]` and `[tool.mypy]` (with and without `files`)
**When** the plan is derived
**Then** the command list equals the golden list for that combination, in the order ruff, mypy, pytest

### S4: An untrusted SPEC, a missing interpreter or a broken pyproject yields no gates
**Given** a repo with no CI file, and a SPEC that is full, unapproved, edited after approval, carries irreversible ids, or declares a framework other than exactly `pytest`, or no `.venv/bin/python`, or an unparseable `pyproject.toml`
**When** `run --spec-slug <slug>` is called
**Then** it exits `3` with `commands: []`, writes no marker, and stderr names why the SPEC plan was not used
**And** after a passing SPEC run, a SPEC made untrusted without touching any relevant path also gets exit `3`, not `cached: true`

### S5: The SPEC plan fails closed
**Given** a SPEC plan whose gate exits non-zero (pytest exit 5, no tests collected, included), times out, cannot start, or whose tree changes during the run
**When** `run --spec-slug` finishes
**Then** it exits `1` or `4` as the CI path does and writes no marker

### S6: Only the light check opts in
**Given** a render of the same answers for Claude Code and Codex
**When** the light-check reference file, the Codex execute skill and verify's render are read
**Then** the light check's Check 2 passes `--spec-slug <slug>` and its record body names the gate source, and verify's Check 2 has no `--spec-slug`

### S7: Typed stages render as today
**Given** a render of the same answers before and after the change
**When** verify, review, wrapup, the loop and the Claude execute command are compared
**Then** each is byte-identical to its `4bd3d3d8` render

### S8: The bench fixture earns its pass without harness-maker's environment
**Given** a copy of `scripts/bench/timeparse` (with its new dev group) committed as a git repo, a trusted light pytest SPEC, its suite already run once by `.venv/bin/python -m pytest`, and a `PATH` from which harness-maker's dev venv is removed
**When** `uv run --with <src> hm observability.verification_cache run --root . --mode relevant --spec-slug <slug>` runs in it
**Then** the exit is `0` and the JSON carries `gate_source: spec`

## 🚫 Non-Goals

- A SPEC plan when CI exists but is unreadable, has no recognised command or has no blocking
  gate. The DRI's option says "with no CI file".
- Finding an interpreter anywhere other than `<root>/.venv/bin/python`. That rules out PATH
  search, `uv run`, `.venv/Scripts/python.exe`, conda and pyenv.
- Installing anything. A `.venv` without pytest, or without a configured ruff or mypy, fails
  the gate.
- Frameworks other than `pytest`, and lint or type configuration outside `pyproject.toml`.
- `ruff format --check`. The DRI's option names ruff and mypy.
- Recording the gate source on the marker or in the record frontmatter, and any change to
  `light_lane.py`, `spec_machine.py`, the verification key, `is_run_fresh`, `check`,
  `mark-pass`, `key`, `explain`, or `hm verification_plan`'s output.
- Changing verify's own Check 2, wrapup Step 2 or the verify-before-completion skill.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Trust | `light_lane.lane_of == "light"` and the `.md` `test_framework` exactly `pytest`; SPEC text only selects the one map key and never reaches a command string | Minimal scope; residual in Open Questions |
| Interpreter | Only `<root>/.venv/bin/python`, as an absolute, shell-quoted path inside each command | `commands_sha256` binds the marker to it without a marker change |
| Fail closed | Unknown framework, untrusted SPEC, no `.venv/bin/python` or unparseable `pyproject.toml` gives exit 3, `commands: []`, no marker | Exit 3 is already not a pass for the light check |
| Exit contract | `{0, 1, 3, 4}`, meanings unchanged | Rendered stages branch on `exit` |
| CI path | Byte-identical to `4bd3d3d8` without the flag, and with it when CI is present | Every harness rendered today |
| Subprocess | `shell=False`, timeouts on every gate (implementation-patterns.md) | Project rule |
| Render | Only the light-check branch changes; no new headings | AC-006; `test_step_sensitivity_registry.py` |
| Compatibility | Python 3.12. An old CLI rejects the flag with argparse exit 2 and prints no JSON line, which the light check reads as not a pass | Mixed versions fail closed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add `--spec-slug <slug>` to `hm observability.verification_cache run` | public API/CLI contract | The rendered light check calls it; removing or renaming it breaks every harness rendered with it |
| IRR-002 | `run`'s stdout JSON gains `"gate_source": "spec"` on the SPEC path only; a CI-derived run prints no new key, and the slug is not echoed | public API/CLI contract | The light check reads it to name the source in the record; once harnesses read the key it cannot be renamed or dropped |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (CLI) | `tests/unit/test_verification_cache_spec_plan.py::test_trust_and_exit_table` (the passing row) |
| S2 | unit (CLI, differential) | `tests/unit/test_verification_cache_spec_plan.py::test_outside_the_opt_in_case_matches_4bd3d3d8` |
| S3 | unit | `tests/unit/test_verification_cache_spec_plan.py::test_plan_follows_project_configuration` |
| S4 | unit (CLI) | `tests/unit/test_verification_cache_spec_plan.py::test_trust_and_exit_table` |
| S5 | unit (CLI) | `tests/unit/test_verification_cache_spec_plan.py::test_spec_plan_fails_closed` |
| S6 | unit (render) | `tests/render/test_render_light_lane_s3d.py::test_only_the_light_check_passes_the_slug` |
| S7 | unit (render, differential) | `tests/render/test_render_light_lane_s3d.py::test_typed_stages_match_4bd3d3d8` |
| S8 | integration (`INTEGRATION=1`) | `tests/integration/test_light_lane_s3d_timeparse.py::test_timeparse_passes_from_its_spec_without_the_dev_venv` |

### AC-001: Outside the opt-in case, run is byte-identical to 4bd3d3d8
### AC-002: The SPEC plan's command list is the golden function of the project's configuration
### AC-003: Only a trusted pytest SPEC with a project .venv yields a plan
### AC-004: The SPEC plan fails closed on any non-pass
### AC-005: Only the light check passes --spec-slug and names the gate source
### AC-006: Verify, review, wrapup, the loop and the Claude execute command render byte-identical to 4bd3d3d8
### AC-007: The timeparse bench fixture passes from its SPEC with harness-maker's dev venv off PATH

## ❓ Open Questions

- **A post-approval edit is not detected.** The approval hash covers only the machine yaml.
  If a SPEC declared another framework (for example `vitest`) and its `.md` is edited to
  `pytest` after approval, it gets pytest gates without re-approval. The edit can only select
  the one map key, and it runs the project's own pytest, but it does skip a human. Binding the
  value into the stamp was dropped from this scope.
- **A `.venv` that is not the project's real environment fails the gate.** A `.venv` that lacks
  the project's dependencies, pytest, or a configured ruff or mypy fails with exit 1, so review
  and verify stay in place. Only the cost of this stage is lost. On a project without a
  `dependency-groups`/dev entry for pytest, the `.venv` that uv creates has no pytest, and this
  stage never fires there.
- **`__pycache__` can move the key.** On a repo with no `.gitignore`, the first pytest run
  after a source edit writes untracked `.pyc` files, and `run` then exits 4 (tree changed).
  The light check reads that as not a pass. In the bench, execute's GREEN step normally ran
  pytest after the last edit, so the files are current; the cold case is unmeasured. Should
  the fixture gain a `.gitignore`? That would change what both arms start from again.
- Wrapup Step 2 calls `run` without the flag. On a repo with no CI file it still re-runs the
  guessed gates, so the suite runs twice. That is a follow-up.
- Whether light runs now skip review and verify (0 of 30 today) stays unmeasured until the eval
  is re-run. Before and after are not strictly comparable (Outcomes).

## 🔍 Refinement Decisions

- Interview not run: the scope is the DRI's 2026-10-15 option, quoted verbatim in Intent.
- Rewritten 2026-10-15 to the spec-validator's minimal scope, on the coordinator's instruction
  (verdict MAJOR_REVISION):
  - PATH discovery, the import probe and the `uv.lock` branch were replaced by the project
    `.venv` alone;
  - the stamped `test_framework`, the marker fields and the record frontmatter field were
    dropped, and with them the edits to `spec_machine.py` and `light_lane.py`;
  - the IRRs fell from five to two, and the ACs became the validator's seven.
- Lane `full`: two irreversible decisions (CLI contract).
- Opt-in by slug, not by path. `--spec-slug` resolves the SPEC through `light_lane.lane_of`, the
  boundary's own reader.
- "CI absent" means no workflows directory, or no workflow file in it, per "with no CI file".
- Exact match on `pytest`. All 235 SPECs in this repo declare exactly `pytest`.
- Order: ruff, mypy, pytest. The cheap gates run first and the run stops at the first failure,
  as `_run_all` does.
- Verify's Check 2 stays byte-identical. No strong reason was found to change it, and its
  degraded path already says the gates were guessed.
- The fixture's dev group is in scope because without it the uv-created `.venv` has no pytest
  (probe), and the stage would never fire on the bench.
- Work stays on `claude/hm-light-lane-bench`, as in the earlier stages.
