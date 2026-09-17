---
type: plan
task_slug: outcome-measure
status: complete
created: 2026-09-17
tags: [harness-maker, plan, python, jinja2, intent-layer, outcomes, measurement, subprocess]
spec: "[[SPEC-outcome-measure]]"
research_doc: "[[RESEARCH-outcome-measure]]"
interview_rounds: 5
adrs: 7
validator_outcome: MAJOR_REVISION
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation: ["9eabe8fce323f4a9 accepted (dry-run semantics stated in ADR-006)", "1c4b0e6c20fb3f15 accepted (single-load append, ADR-004)", "75e4fddb29c6e3d1 accepted (float regex, ADR-003)", "82442947d33d868f accepted (exact last-number, ADR-001)", "6c3cf9f85121ab72 accepted (bool/non-finite refused, ADR-003)", "32de2d6b4d341bd9 rejected (ADR-010 is the attribution literal test_baseline_delta_attribution requires)"]
summary: "measure block on outcomes + hm world outcome measure (argv, selector, auto-evidence); skill + wrapup 5.7 call it; wrapup allowance retired at close-out"
spec_need_verdict: add
spec_need_target: outcome-measure
---

# PLAN — Outcome measure

## 🎯 Executive Summary

**TL;DR.** An outcome may carry `measure: {cmd, select, cwd?, timeout_s?}`. One verb,
`hm world outcome measure <id> [--all] [--dry-run] [--json]`, runs `cmd` as argv (no shell,
timeout, output redacted and truncated), extracts one number with `select`, and appends a row
through the existing `record_value` with evidence `auto: <argv> @ <sha> exit=0 cwd=<base|checkout>`.
`definition_hash` covers the block, so editing the measurement stales history. The skill's
"measure first" opener and a third answer-gated wrapup 5.7 question call the verb. The wrapup
growth is declared via allowance and retired before landing (the ADR-008 pattern from
objective-gap-proposal).

**What / Why.** Values are typed by hand today, so the gap table stays empty and the first
RESEARCH's Goodhart mitigation ("the model never types the number") is unmet. This lifts the
"no measurement automation" non-goal for command-measurable outcomes only; manual stays the
fallback (SPEC S1–S8).

**Key decisions.** ADR-001 `Measure` dataclass + validation · ADR-002 absent block hashes as
today, present block joins the hash · ADR-003 three selectors, one number, refusal on anything
else · ADR-004 subprocess discipline + evidence shape · ADR-005 `cwd: base` default via
`resolve_base_root` · ADR-006 three firing points, answer-gated at wrapup · ADR-007 wrapup
surface via allowance, retired in the last phase.

**Estimated impact.** ~60 lines in `intent.py`, ~160 in `world.py`, 2 template edits,
4 test files, one delta doc, two baseline re-freezes (pin + own fold).

## 📚 Prior Work

- [[RESEARCH-outcome-measure]] — Approaches A+B chosen; C (external service) and D (manual) rejected; pitfalls 1–8.
- [[RESEARCH-intent-world-model-objective-layer]] — "measure_cmd is mandatory" + "definition pinned and hashed" (Goodhart).
- [[PLAN-objective-gap-proposal]] — ADR-008 (allowance retirement phase), ADR-007 (delta-doc pin), the wrapup 5.7 answer-gated block shape; its REVIEW open items on LLM-text interpolation (this task adds no interpolated free text — the verb takes an id only).
- `src/harness_maker/second_opinion_oracle.py` — `redact`, `truncate`, `BUDGET_PER_COMMAND`, argv `subprocess.run(..., timeout=300, check=False)`.
- Memory: `surface-allowance-lacks-autofold` (count 1 — fold it yourself before landing), `round-trip-allowance-before-call-exists` (declare `round_trips` in the phase that adds the call), `rendered-harness-pins-released-plugin` (prose calling the new verb fails in dogfood until release; the verb works via `python -m harness_maker.world`).

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Schema | contract | Structured `measure` block or `cmd:` prefix in `how_measured`? | 2 | **block** | validated + hashed | ADR-001 |
| 2 | Firing points | scope | verb only / verb + skill / all three (+ wrapup 5.7)? | 3 | **all three** | wrapup answer-gated | ADR-006, ADR-007 |
| 3 | Hash scope | contract | `definition_hash` covers `measure`? | 2 | **yes** | absent block must not stale existing rows | ADR-002 |
| 4 | Dogfood | scope | Put a real outcome in this repo's `intent.yaml`? | 2 | **no** | mission is human-written; tests on tmp roots | — |
| 5 | Step 3.0 | phasing | Proceed to phase decomposition? | 3 | **proceed** | five defaults → ADR-002/003/004/005/007 | — |

Rounds 1–4 were `/hm:spec`'s interview; round 5 this stage's Case-A lock-in.

## 📐 Architecture Decision Records

### ADR-001: `measure` is a validated, frozen sub-record of `Outcome`
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** `Outcome` has five fields; `_validate_outcome` rejects unknown keys, so a new key must be declared and validated with the same field-naming discipline (`outcomes[i].measure.<field>`).
**Decision:** `OUTCOME_FIELDS` gains optional `measure`; `Measure(cmd: str, select: str, cwd: Literal["base","checkout"] = "base", timeout_s: int = 300)` frozen dataclass; `Outcome.measure: Measure | None`. Validation: mapping; `cmd` non-empty string whose `shlex.split` succeeds, is non-empty and whose first token does not start with `-`; `select` is `json:<non-empty path>`, `regex:<pattern>` (must compile, exactly one group) or exactly `last-number` (no suffix — refused at load, not at run); `cwd` in the two values; `timeout_s` positive int; unknown keys refused. `write_skeleton_if_absent` documents the block in its comment.
**Consequences:**
- ✅ A bad block is refused at load, before any subprocess exists.
- ⚠️ `intent.yaml` grows a second measurement surface next to `how_measured` (prose) — the hash (ADR-002) keeps them honest.
**Rejected alternatives:**
- `cmd:` prefix inside `how_measured` — rejected by the user (Interview #1).
**Source:** Interview #1

### ADR-002: the hash covers `measure` only when present
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** `definition_hash(target, how_measured, higher_is_better)` is canonical JSON of three keys; every existing `outcomes.yaml` row carries that hash. Adding a `measure: null` key would change the JSON and stale every existing row on upgrade.
**Decision:** `definition_hash(target, how_measured, higher_is_better, *, measure)` — the keyword is **required, no default**, so `mypy --strict` names every call site (a missed one would silently write a block-less hash and stale every row forever). When `measure is None` the payload is exactly today's three keys; when present it adds `"measure": {cmd, select, cwd, timeout_s}`. `last_value`/`gap`/`record_value`/`world_fixture` pass the outcome's block. A pinned literal of today's hash for a block-less outcome is asserted in AC-005.
**Consequences:**
- ✅ No upgrade stale-out; editing `cmd`/`select`/`cwd`/`timeout_s` stales history (Goodhart brake).
- ⚠️ `timeout_s` edits also stale — accepted: a timeout change can change which runs succeed.
- ⚠️ The machine SPEC's AC-005 predicate is amended to pass `measure=None` explicitly (Phase 0).
**Rejected alternatives:**
- Separate `measure_hash` on the row — rejected by the user (Interview #3).
**Source:** Interview #3, #5 (default 1)

### ADR-003: three selectors, one number, refusal on anything else
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** Command output is arbitrary; Bencher solves this with per-harness adapters; this repo wants no new dependency.
**Decision:** `select_number(text, select) -> float`: `json:<path>` parses the whole stdout as JSON and walks a dotted path (`a.b.0.c`, integer segments index lists); `regex:<pattern>` uses the first match's group 1; `last-number` takes the last token matching `[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?` in stdout (so `1e-3` → 0.001 and `.672` → 0.672). The selected leaf/match must be an `int`/`float` that is **not a bool and is finite** (`json.loads` accepts `NaN`/`Infinity`; a NaN row would make every `gap` comparison permanently False); the value is normalised through the existing `_json_number` so the measure path stores `17` where `outcome record` would (one row schema, two writers). Anything else — no JSON, path missing, non-numeric/bool/non-finite leaf, no match, no number — raises `WorldError("select", …)`. Only stdout is selected from; stderr is diagnostics.
**Consequences:**
- ✅ Deterministic, dependency-free, three forms to document.
- ⚠️ No JSONPath filters; a command must print something addressable.
**Rejected alternatives:**
- JSONPath library — rejected: dependency for a feature that needs a dotted path.
**Source:** Interview #5 (default 2)

### ADR-004: subprocess discipline and the evidence shape
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** CLAUDE.md forbids `shell=True` and requires timeouts; `second_opinion_oracle` already runs user-configured argv with `redact` + `truncate`.
**Decision:** `run_measure(outcome, root) -> MeasureResult`: `argv = shlex.split(measure.cmd)`; `subprocess.run(argv, cwd=<per ADR-005>, capture_output=True, text=True, timeout=measure.timeout_s, check=False)`; `OSError`/`TimeoutExpired` → `WorldError("timeout"|"exit", …)`; non-zero exit → `WorldError("exit", "exit=<rc>: <redacted, truncated tail>")`; success → `select_number(stdout)`. **One disk snapshot per row:** the `Outcome` loaded before the run is the one hashed and appended — `record_value` is split into `record_value(root, id, …)` (loads, then delegates) and `_append_value(root, outcome, value, now, evidence)`; the measure path calls `_append_value` with the already-loaded outcome and never reloads `intent.yaml` (same invariant `gap_report`'s docstring states). Evidence = `f"auto: {' '.join(argv)} @ {sha} exit=0 cwd={cwd_kind}"` — SPEC S2 / machine AC-002 are amended in Phase 0 to this exact shape (AC-006 already requires the root to be named) with `sha` = `git rev-parse --short HEAD` at the cwd (`nogit` fallback). Raw stdout/stderr never reach the row; diagnostics on stderr go through `redact` + `truncate(BUDGET_PER_COMMAND)`.
**Consequences:**
- ✅ Same containment as the oracle; evidence is short and reproducible.
- ⚠️ Argv strings with quotes must be shell-quoted in YAML (`shlex` rules); documented in the skeleton comment.
**Rejected alternatives:**
- `shell=True` for pipelines — rejected: CLAUDE.md rule; pipelines belong in a script the command names.
**Source:** Interview #5 (default 3)

### ADR-005: `cwd: base` by default, `checkout` opt-in, named in the evidence
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** Observability data (`hm economics`) lives at the base root; a task worktree's `.claude/observability/` is absent. Repo-content metrics belong in the checkout.
**Decision:** `cwd: base` → `resolve_base_root(root)`; `cwd: checkout` → `root` (the checkout the verb was given). The evidence names `cwd=base|checkout`. AC-006 runs the verb from a linked worktree with a probe that prints a marker only present in the directory it runs in.
**Consequences:**
- ✅ The dogfood metric works from inside a task worktree.
- ⚠️ `resolve_base_root`'s git-failure cwd fallback (open item 22d6fb0d from the previous review) applies here too — recorded, not fixed.
**Rejected alternatives:**
- Always checkout — rejected: the first real outcome (economics) would read an empty directory.
**Source:** Interview #5 (default), RESEARCH pitfall 3

### ADR-006: three firing points; wrapup and skill are answer-gated; `--all` reports, never aborts
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** Effects lag code; an automatic measurement at every wrapup is noise; the skill already opens with "measure first".
**Decision:** (1) `outcome measure <id>` / `--all` / `--dry-run` on demand. (2) The skill's "measure first" step runs `hm world outcome measure --all --dry-run`, shows the table and asks once whether to record (`--all` without `--dry-run` on yes). (3) wrapup 5.7 gains `<!-- @hm:answer-gated:outcome-measure -->` after `objective-close`: "Measure outcomes now?" listing measurable outcomes with last value and age **read from `hm world gap --json`** — `gap_report` outcome rows gain `measure: bool` and `last_observed_at: str|null` (gap is not frozen; `status --json` is); yes → `outcome measure --all` once; no → write nothing. The 5.7 heading "two questions" becomes "three questions". **`--dry-run` runs `cmd` and selects the number, and the harness writes nothing** — the command's own side effects are the command's (AC-004's immutability property holds over the test-authored, non-mutating probes; the contract is "no harness write"). `--all` runs every measurable outcome, reports `recorded|failed|manual|would_record` per outcome, records the successes, exits 1 if any failed. `objective close` is untouched.
**Consequences:**
- ✅ Zero typing on the common path; a human still says when.
- ⚠️ wrapup grows by one block (ADR-007); the prose calls a verb the pinned plugin cache lacks until release (dogfood limit).
**Rejected alternatives:**
- Auto-measure at every wrapup — rejected: noise; the question is the gate.
**Source:** Interview #2

### ADR-007: wrapup surface via allowance, retired in the last phase; plan/review/help pinned
**Status:** Accepted (2026-09-17, via /hm:plan interview)
**Context:** `test_playbook_alignment_invariance` and `test_objective_gap_proposal_invariance` pin plan/review/help at this version; the wrapup ratchets (`_ATOMIC_RATCHET`, `_CLAUDE_ROUND_TRIPS['wrapup']: 28`) move by one block/one call; the allowance expires at `complete` with no automatic fold (memory `surface-allowance-lacks-autofold`).
**Decision:** Phase 0 pins plan/review/help sha + wrapup length per arm into `BASELINE-DELTA-outcome-measure.md`; Phase 3 measures the wrapup delta and declares `surface_allowance.commands.wrapup/hm-wrapup` **and** `round_trips.wrapup/hm-wrapup: N` (N = the measured count of new calls in the block) in the same phase as the calls; `_CLAUDE_ROUND_TRIPS['wrapup']` 28 → 28+N with attribution; Phase 5 re-freezes both baselines from the worktree, moves `_ATOMIC_RATCHET['wrapup']` only if outside the band, writes §3.1, deletes the allowance block, and exits on `pytest tests/structural` green with zero allowances (AC-008). Main is checked green before Phase 0 (it is: objective-gap-proposal retired its own).
**Consequences:**
- ✅ Main stays green after the land.
- ⚠️ Two more pins on plan/review/help at this version (skip loudly on the next bump).
**Rejected alternatives:**
- Skill-only prose (no wrapup edit) — rejected by the user (Interview #2).
**Source:** Interview #2, #5 (default 5)

## 🏗️ Technical Design

**Current state.** `intent.py`: `Outcome` (5 fields), `_validate_outcome` (unknown key refused), `load_intent`, `write_skeleton_if_absent`. `world.py`: `definition_hash` (3 keys), `record_value` (validates + hashes + appends), `last_value`/`gap`/`gap_report`, `outcome record` subparser. `second_opinion_oracle.py`: `redact`, `truncate`, `BUDGET_PER_COMMAND`. wrapup.md.j2 5.7 has two answer-gated blocks; the skill has "Proposing objectives" with a "measure first" step (prose only).

**Affected components.** `intent.py` (Measure, validation, load, skeleton comment), `world.py` (`definition_hash` signature, `select_number`, `run_measure`, `measure_outcome(s)`, `outcome measure` subparser + dispatch), `command_registry.py` (`measure`), `templates/skills/intent-layer/SKILL.md.j2`, `templates/stages/wrapup.md.j2`, tests, baselines/ratchets, CHANGELOG, HOW-IT-WORKS §7.13, `tests/unit/world_fixture.py` (`outcome(measure=…)`).

**Data flow.** intent.yaml → `load_intent` (Measure) → `measure_outcome(root, id, dry_run)` → `run_measure` (argv at cwd) → `select_number` → `record_value(root, id, value, now, evidence)` → outcomes.yaml row (+ `definition_hash` incl. measure) → `gap_report` reasons.

**API changes.** New: `Measure`, `Outcome.measure`, `world.select_number`, `world.run_measure`, `world.measure_outcome`, `world.measure_all`, CLI `world outcome measure <id> | --all [--dry-run] [--json]`; `definition_hash(..., measure=None)` (keyword, default preserves today's output). Unchanged: `outcome record`, row schema, `status`, gate.

## 📝 Implementation Plan

### Phase 0 — Pin the pre-change surface, confirm main is green
- `depends_on`: [] · `parallel_group`: serial-0 · `merge_hazards`: `work-docs/BASELINE-DELTA-*.md` (attribution-doc selection)
- **Scope (in):** run `pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py -q` from the worktree to confirm the inherited state is green (no fold expected this time); write `work-docs/BASELINE-DELTA-outcome-measure.md` §1 with the fenced JSON pin `{arms{arm: {plan, review, help, wrapup}}, wrapup_len{arm}, harness_maker_version}` (recipe: `_instruction_baseline.AXES` + `_render_atomic`, `test_command_size_budget._render`), §2 "no inherited fold", §3 placeholder. No `surface_allowance` yet. Amend SPEC S2 + machine AC-002 evidence to `auto: python probe.py @ <sha> exit=0 cwd=base` and AC-005's predicate to `definition_hash(10, 'stopwatch', False, measure=None)`; re-run `spec_machine check`. **Out:** src, templates.
- **Exit:** `uv run pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py tests/structural/test_baseline_delta_attribution.py -q` green; the pin reproduces from a clean render.
- **Risk:** low · **Rollback:** delete the doc.

### Phase 1 — `Measure` schema, validation, hash
- `depends_on`: [0] · `parallel_group`: serial-1 · `merge_hazards`: `src/harness_maker/intent.py`, `src/harness_maker/world.py` (`definition_hash` signature), `tests/unit/world_fixture.py`
- **Scope (in):** ADR-001 dataclass + `_validate_measure`; `load_intent` builds it; skeleton comment documents the block; `definition_hash(..., *, measure)` per ADR-002 (required keyword) and its callers (`record_value`, `last_value`, `world_fixture.definition_hash`, any other mypy names); `record_value` → `_append_value` split (ADR-004); `tests/unit/test_intent_measure.py` — AC-001 (good block loads; each bad fixture refused with the named field), AC-005 (hash literal for a block-less outcome equals today's; block edit → `stale_definition` in `gap_report`, revert → `measured`). **Out:** the verb.
- **Exit:** `uv run pytest tests/unit/test_intent_measure.py tests/unit/test_world_outcomes.py tests/unit/test_world_gap.py tests/unit/test_intent_validate.py -q` green; `mypy --strict src/harness_maker/intent.py src/harness_maker/world.py`.
- **Risk:** low · **Rollback:** Phase 0.

### Phase 2 — `hm world outcome measure`
- `depends_on`: [1] · `parallel_group`: serial-1 · `merge_hazards`: `src/harness_maker/world.py`, `src/harness_maker/command_registry.py`
- **Scope (in):** `select_number` (ADR-003), `run_measure` (ADR-004/005, imports `redact`/`truncate` from `second_opinion_oracle`), `measure_outcome(root, id, *, dry_run)` and `measure_all(root, *, dry_run)` returning `{results: [...]}`, subparser `outcome measure [id] [--all] [--dry-run] [--json]` (id xor `--all`), dispatch, registry name `measure`; `gap_report` rows gain `measure` + `last_observed_at` (ADR-006) with a `test_world_gap.py` assertion; selector edge tests: `1e-3`, `.672`, bool leaf, `NaN`, `last-numberXYZ` refused at load, integral float stored as int; `tests/unit/test_world_outcome_measure.py` — AC-002 (probe scripts as fixtures printing JSON / `carry=0.672` / prose ending in a number; evidence + hash computed from fixture facts), AC-003 (exit 3 / no number / `sleep` past a 1 s timeout / manual outcome → non-zero, cause word, `outcomes.yaml` bytes unchanged), AC-004 property (Hypothesis over worlds mixing ok/failing/manual, `--all --dry-run` tree hash unchanged) + `--all` table/exit test, AC-006 (throwaway base + `git worktree add`, probe prints a marker read from a file present only at its cwd; `cwd: base` vs `checkout`; evidence names the root). **Out:** templates.
- **Exit:** `uv run pytest tests/unit/test_world_outcome_measure.py tests/unit/test_intent_doc_new.py -q` green; `hm world outcome measure --all --dry-run --json` on the dogfood root prints an empty results list with `state: not_filled_in` handling (no crash); no file written.
- **Risk:** medium (subprocess + selector edge cases) · **Rollback:** Phase 1.

### Phase 3 — Skill + wrapup 5.7 prose, allowance
- `depends_on`: [2] · `parallel_group`: templates · `merge_hazards`: `tests/structural/test_roundtrip_budget.py`, `tests/structural/test_command_size_budget.py`, `tests/structural/autopilot_gate_golden.json` (`wrapup` in all arms), `tests/snapshot/*.expected.yaml`, both prior delta-doc pins (they pin plan/review/help — untouched by this phase; verify)
- **Scope (in):** skill "measure first" step → `hm world outcome measure --all --dry-run` + record-on-yes sentence; wrapup 5.7 third block per ADR-006 (both arms, listing from `hm world gap --json`, exactly one `outcome measure --all` call, "write nothing" line, heading "two questions" → "three questions"); measure the wrapup delta; declare `surface_allowance{chars, commands.wrapup/hm-wrapup, round_trips.wrapup/hm-wrapup: <exact measured count of new calls — likely 2: gap listing + measure>, delta_doc}` in this PLAN's frontmatter in the same commit as the calls (memory: never before; the arm is exact two-way); `_CLAUDE_ROUND_TRIPS['wrapup']` 28 → 28+N with attribution; gate golden re-capture for `wrapup` (verify it is the only moved command) + `rebases` entry + docstring bullet; snapshot regen in the worktree; `tests/unit/test_render_intent_layer.py` AC-007 (both arms; block ordering after `objective-close`; exactly one call in the block). **Out:** plan/review/help templates.
- **Exit:** `uv run pytest tests/unit/test_render_intent_layer.py tests/structural tests/snapshot -q -k "not ac_008"` green with the allowance active; delta doc §3 records the measured wrapup growth.
- **Risk:** medium (ratchet choreography) · **Rollback:** Phase 2.

### Phase 4 — Lifecycle, docs, CHANGELOG
- `depends_on`: [3] · `parallel_group`: serial-4 · `merge_hazards`: `CHANGELOG.md` `[Unreleased]` top
- **Scope (in):** `tests/integration/test_intent_layer_lifecycle.py` — an outcome with a `measure` block: gap `never_measured` → `outcome measure` → gap `measured` with the right verdict → edit block → `stale_definition`; CHANGELOG Added; HOW-IT-WORKS §7.13 paragraph (the `measure` block, the three selectors, the `cwd` rule, the wrapup question); `tests/structural/test_outcome_measure_invariance.py` AC-008 (plan/review/help pinned; retirement half red until Phase 5); Tier-1 mutation obligation: run `uv run python -m harness_maker.spec_mutation gate --yaml specs/SPEC-outcome-measure.machine.yaml` and record a `mutation_receipt` — the known zero-mutant outcome (memory, count 3) is recorded as a receipt with `--gate`, not hidden.
- **Exit:** full `hm verification_plan commands` suite green except AC-008's retirement half; mutation receipt row present.
- **Risk:** low · **Rollback:** Phase 3.

### Phase 5 — Retire the allowance (ADR-007)
- `depends_on`: [4] · `parallel_group`: serial-5 · `merge_hazards`: `tests/structural/surface_baseline.json`, `tests/structural/instruction_baseline.json`, `tests/structural/test_command_size_budget.py`, this PLAN's frontmatter
- **Scope (in):** re-freeze both baselines from the worktree; move `_ATOMIC_RATCHET['wrapup']` only if outside the 2 % band; delta doc §3.1 attribution rows ("Phase 5", "larger", "ADR-010", "ratchet-rebaselined-by-its-own-subject"); delete the `surface_allowance` block; re-pin `wrapup` in §1.
- **Exit:** `uv run pytest tests/structural -q` green with zero in-flight allowances (AC-008); full suite green.
- **Risk:** medium · **Rollback:** Phase 4.

### Phase status

| Phase | Status |
|---|---|
| 0 | done (pin written, inherited gates green) |
| 1 | done (AC-001/005 green, A.5 PASS round 2) |
| 2 | done (AC-002/003/004/006 green, A.5 PASS round 1) |
| 3 | done — A.5 budget exhausted once (test-shape findings); user chose `stuck` Path A (2026-09-17): SPEC S7 / AC-007 amended to name the record call and the deferral phrase; fresh A.5 run PASS (round 2). wrapup +601/+611, round_trips +1, golden re-captured, snapshots regenerated, 5.7 heading rename allowlisted |
| 4 | done — lifecycle test, CHANGELOG, HOW-IT-WORKS §7.13, AC-008 test; mutation receipt recorded from a real probe (world.py:973 → 4 failed); `spec_mutation gate` still collects zero mutants (known, count now 4) |
| 5 | done — both baselines re-frozen from the worktree, allowance deleted, wrapup re-pinned, §3.1 attribution |

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/autopilot_caps.py` — the gate is untouched
- `src/harness_maker/templates/stages/plan.md.j2` — pinned by AC-008 and the two prior invariance tests
- `src/harness_maker/templates/stages/review.md.j2` — pinned
- `src/harness_maker/templates/commands/hm/help.en.md.j2`
- `src/harness_maker/templates/commands/hm/help.ko.md.j2`
- `tests/fixtures/autopilot_caps_baseline.json`
- `.claude/intent.yaml` — the dogfood skeleton stays as it is (Interview #4)
- Advisory: `record_value`'s row schema and `status --json` payload are frozen; the baselines are frozen between Phase 0 and Phase 5

## 🧪 Testing Strategy

- **Unit:** `test_intent_measure.py` (AC-001, AC-005), `test_world_outcome_measure.py` (AC-002, AC-003, AC-004 property + `--all`, AC-006 linked worktree), `test_render_intent_layer.py` (AC-007 both arms).
- **Structural:** `test_outcome_measure_invariance.py` (AC-008), existing ratchets with allowance (Phase 3–4) and without (Phase 5), snapshot regen.
- **Integration:** lifecycle extension.
- **Manual (dogfood):** `uv run python -m harness_maker.world outcome measure --all --dry-run --json` on this repo → no measurable outcomes, no crash; on a tmp copy with `measure: {cmd: "uv run python -m harness_maker.economics report --root /home/noel/harness-maker", select: "json:report.carry_ratio"}` → records 0.672-ish.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Existing rows go `stale_definition` on upgrade | low | high | ADR-002: absent block hashes exactly as today; AC-005 pins the literal |
| R2 | Command output leaks secrets into stderr diagnostics | low | medium | `redact` + `truncate`; stdout never stored |
| R3 | Hung command | medium | low | `timeout_s` (default 300) → `WorldError("timeout")`, nothing written |
| R4 | Ratchet choreography (wrapup allowance, round trips, golden, snapshots, retirement) | medium | medium | Phase 0 pin; declare `round_trips` with the call; Phase 5 fold with attribution; main checked green first |
| R5 | Mutation gate zero mutants (count 3, proposal filed) | high | low | world/intent suites re-run by hand; receipt via a genuine probe |
| R6 | Prose calls a verb the cached plugin lacks | high (dogfood) | low | known limit; verb usable via `python -m` |
| R7 | `resolve_base_root` git-failure fallback runs the command in the wrong dir | low | low | evidence names the root; carried open item |

## ✅ Success Criteria

- [x] AC-001 measure block validates with the outcome
- [x] AC-002 measure records the extracted number with auto evidence
- [x] AC-003 failures write nothing and name the cause
- [x] AC-004 dry-run writes nothing (property) + `--all` reports every outcome
- [x] AC-005 editing measure stales history; absent block hashes as today
- [x] AC-006 default cwd is the base root
- [x] AC-007 skill and wrapup call the verb (both arms)
- [x] AC-008 plan/review/help pinned; allowance retired; structural green with zero allowances
- [x] full suite + ruff + mypy green; snapshots regenerated in the worktree

## 🔍 Plan Validation

Single pass (2026-09-17). Codex: 6 findings (5 accepted, 1 rejected — `ADR-010` is the literal `test_baseline_delta_attribution` requires). plan-validator: MAJOR_REVISION, 11 findings, all folded in place without a second pass (project rule):

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | P1 | evidence string contradicts SPEC AC-002 equality | SPEC S2 + machine AC-002 amended in Phase 0 to the `cwd=` shape (ADR-004) |
| 2 | P1 | `measure=None` default re-creates the every-reader class | required keyword-only (ADR-002); machine AC-005 predicate passes `measure=None` |
| 3 | P1 | wrapup listing source undefined / collides with AC-007 | `gap_report` gains `measure` + `last_observed_at`; block lists from `hm world gap --json` (ADR-006) |
| 4 | P1 | `--dry-run` semantics unstated | runs + selects, harness writes nothing; AC-004 = "no harness write" (ADR-006) |
| 5 | P1 | `last-number` regex mis-parses `1e-3`/`.672` | full float regex (ADR-003) |
| 6 | P1 | two disk snapshots per row (TOCTOU) | `_append_value` takes the loaded `Outcome`; no reload (ADR-004) |
| 7 | P2 | no phase owns the Tier-1 mutation obligation | Phase 4 runs the gate and records a receipt |
| 8 | P2 | bool / non-finite leaves | refused as `select` (ADR-003) |
| 9 | P2 | integral float vs `_json_number` | routed through `_json_number` (ADR-003) |
| 10 | P3 | `last-numberXYZ` passes `startswith` | exact match (ADR-001) |
| 11 | P3 | 5.7 heading "two questions"; `interview_rounds` | heading edit in Phase 3; frontmatter 5 |
