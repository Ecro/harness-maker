---
type: spec
task_slug: outcome-measure
status: approved
created: 2026-09-17
tags: [harness-maker, spec, python, jinja2, intent-layer, outcomes, measurement, subprocess]
tier: 1
test_framework: pytest
research_doc: "[[RESEARCH-outcome-measure]]"
summary: "Optional `measure: {cmd, select, cwd}` on an outcome + `hm world outcome measure` that runs, selects one number and records it with auto-evidence; manual stays the fallback"
---

# SPEC — Outcome measure: the harness records the number, the human never types it

## 🎯 Intent

Every outcome value is typed by hand today (`hm world outcome record --value …`), so the gap
table the previous task shipped stays empty until someone remembers, and the first intent
RESEARCH's Goodhart mitigation — "the harness runs a command and records its output, the model
never types the number" — was left as a non-goal. This SPEC lifts that non-goal for outcomes
whose measurement is a command: the outcome carries a machine-runnable `measure` definition
next to its human `how_measured`, one verb runs it under the repo's subprocess discipline and
records the number through the existing `record_value`, and the two prose surfaces that tell
the operator to "measure first" call that verb instead.

## 🌅 Outcomes

- An `intent.yaml` outcome may carry `measure: {cmd: "<argv string>", select: "<selector>",
  cwd: base|checkout}`; a malformed block is refused at validation with the field named, and an
  outcome without one is unchanged (manual).
- `hm world outcome measure <id>` runs `cmd` (argv, no shell, timeout, output budget,
  redaction), extracts exactly one number with `select`, and appends a value row whose
  `evidence` names the argv, the commit and the exit code — no human typed the number.
  `--all` does it for every outcome that has a `measure` block and prints one table;
  `--dry-run` prints without writing.
- A failed run (non-zero exit, no number, timeout, missing block) writes nothing and says why.
- Editing the `measure` block makes every earlier row `stale_definition`, so `gap` says
  "measure again", not "measured".
- The `intent-layer` skill's "measure first" opener and a third answer-gated wrapup 5.7
  question ("Measure outcomes now?") call the verb; both arms; approve/close stay human.

## 📋 In-Scope Scenarios

### S1: a measure block is validated with the outcome
**Given** `intent.yaml` declares outcome `carry` with `measure: {cmd: "python probe.py", select: "json:report.carry_ratio", cwd: base}`
**When** the intent is loaded
**Then** the outcome carries the block and `hm world status --json` still reports `state: ok`
**And** each of these is refused by `validate_intent` with the field named: empty `cmd`, an
option-shaped first token (`-c …`), `select` with an unknown prefix, `cwd` outside `base|checkout`,
a non-mapping `measure`.

### S2: the verb records the number it extracted
**Given** the outcome above and a `probe.py` that prints `{"report": {"carry_ratio": 0.672}}`
**When** the operator runs `hm world outcome measure carry --json`
**Then** a value row is appended with `value: 0.672`, `observed_at` = now (UTC `Z`),
`evidence` = `auto: python probe.py @ <short sha> exit=0 cwd=base`, and `definition_hash` of the current
definition
**And** the process runs with `shell=False`, a timeout, and its captured output is redacted and
truncated before any of it reaches stderr — stdout never lands in the row
**And** `select: "regex:carry=([0-9.]+)"` and `select: "last-number"` extract the same value
from a matching text output.

### S3: failures write nothing
**Given** the outcome above
**When** the probe exits non-zero, prints no number for the selector, exceeds the timeout, or
the outcome has no `measure` block
**Then** the verb exits non-zero naming the cause (`exit`, `select`, `timeout`, `measure`) and
`outcomes.yaml` is byte-identical to before.

### S4: dry-run and --all
**Given** three outcomes — two with `measure` blocks (one whose probe fails) and one manual
**When** the operator runs `hm world outcome measure --all --json`
**Then** the table lists all three: one `recorded` with its value, one `failed` with its cause,
one `manual` (skipped), the exit code is non-zero because one failed, and only the recorded one
has a new row
**And** `--all --dry-run` prints the same table with `would_record` and leaves every file under
the checkout byte-identical.

### S5: editing the measurement stales history
**Given** a recorded row for `carry` under the current `measure` block
**When** `measure.cmd` (or `select`, or `cwd`) is edited and `hm world gap --json` runs
**Then** `carry` reports `reason: stale_definition`; reverting the edit reports `measured` again
**And** editing `how_measured` prose alone keeps its existing effect (it is already hashed).

### S6: the command runs where the data is
**Given** the verb is invoked from inside a linked task worktree and the probe prints its cwd
**When** `cwd: base` (the default) is used
**Then** the printed path is the base checkout's root; with `cwd: checkout` it is the worktree
**And** the evidence string names which root ran.

### S7: the prose calls the verb
**Given** the rendered `intent-layer` skill and wrapup command, both arms
**When** they are read
**Then** the skill's "measure first" step (the one `**measure first**` block of "Proposing
objectives") runs `hm world outcome measure --all --dry-run`, names `hm world outcome measure --all`
as the record call and defers the ask to "The rule for every write"; wrapup 5.7 carries a third `<!-- @hm:answer-gated:outcome-measure -->` block —
**"Measure outcomes now?"** listing outcomes with a `measure` block and their last value/age —
whose yes-branch runs `hm world outcome measure --all` once and whose no-branch writes nothing;
the block sits after `objective-close`.

### S8: surface accounting
**Given** the rendered command set after this change
**When** the plan/review/help pins and the wrapup ratchet are compared
**Then** plan, review and help are byte-identical to the pre-change pin, wrapup grew by at most
the PLAN's `surface_allowance.commands.wrapup`, and at close-out the allowance is retired (both
baselines re-frozen with attribution, block deleted) so `pytest tests/structural` is green with
zero in-flight allowances.

## 🚫 Non-Goals

- No external service (Bencher-style); the time series is `outcomes.yaml`.
- No averaging / multi-run aggregation in the verb (the command does it, e.g. `hyperfine --runs`).
- No automatic measurement on every wrapup — the 5.7 question is answer-gated; no
  auto-measure inside `objective close`.
- No change to `record_value`'s row schema, `status --json`, the gate, review 3.3.
- No new selector language beyond `json:<dotted.path>`, `regex:<one-group>`, `last-number`.
- No filling of this repo's own `intent.yaml` (mission is human-written; tests use tmp roots).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard; `world_fixture` + render tests exist |
| Subprocess | argv via `shlex.split`, `shell=False`, `timeout` (default 300 s, `measure.timeout_s` optional), cwd fixed | CLAUDE.md `shell=True` 금지 · timeout 필수; same discipline as `second_opinion_oracle` |
| Output handling | `redact` + `truncate(BUDGET_PER_COMMAND)` from `second_opinion_oracle`; stdout never stored | secrets in command output; evidence stays short |
| Hash | `definition_hash` covers `target`, `how_measured`, `higher_is_better`, `measure` (canonical JSON; the `measure` key is added only when a block is present) | Goodhart brake (RESEARCH pitfall 1); absent `measure` must hash identically to today so existing rows do not go stale |
| Surface | plan/review/help pinned; wrapup via allowance then retired (ADR-008 pattern) | surface ratchet |
| Compatibility | `intent.yaml` without `measure` loads unchanged; `outcomes.yaml` row schema unchanged | three consumers of the row |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac_001_measure_block_validates_with_the_outcome` |
| S2 | unit | `test_ac_002_measure_records_the_extracted_number_with_auto_evidence` |
| S3 | unit | `test_ac_003_failures_write_nothing_and_name_the_cause` |
| S4 | property | `test_ac_004_dry_run_writes_nothing` |
| S4 | unit | `test_ac_004_all_reports_every_outcome_and_records_only_successes` |
| S5 | unit | `test_ac_005_editing_measure_stales_history` |
| S6 | unit | `test_ac_006_default_cwd_is_the_base_root` |
| S7 | unit (render) | `test_ac_007_skill_and_wrapup_call_the_verb` |
| S8 | structural | `test_ac_008_surface_pinned_and_allowance_retired` |

### Acceptance criteria

### AC-001: measure block validates with the outcome
`load_intent` accepts `measure: {cmd, select, cwd}` (cwd optional, default `base`; `timeout_s` optional positive int) and exposes it on `Outcome.measure`; `validate_intent` refuses an empty or option-shaped `cmd`, an unknown `select` prefix, a `cwd` outside `base|checkout`, a non-positive `timeout_s`, and a non-mapping `measure`, naming `outcomes[i].measure.<field>`.

### AC-002: measure records the extracted number with auto evidence
`hm world outcome measure <id>` runs `shlex.split(cmd)` with `shell=False`, `cwd` resolved per the block and `timeout`, extracts one number via `json:`/`regex:`/`last-number`, and appends a row equal to `record_value(root, outcome_id, value, now_utc, "auto: <argv> @ <sha> exit=0")`; captured output is redacted/truncated and never stored.

### AC-003: failures write nothing and name the cause
Non-zero exit, no selector match, timeout, and a missing `measure` block each exit non-zero with `field ∈ {exit, select, timeout, measure}` and leave `outcomes.yaml` byte-identical.

### AC-004: dry-run writes nothing
For every loadable world with any mix of measurable, failing and manual outcomes, `outcome measure --all --dry-run` leaves the sha256 of every file under the checkout unchanged; `--all` without `--dry-run` records only the successes, reports all three statuses and exits non-zero when any failed.

### AC-005: editing measure stales history
`definition_hash(…, *, measure)` (required keyword) includes the canonical `measure` block (`measure=None` → unchanged hash vs today), so a row recorded under one block reports `stale_definition` in `gap_report` after the block changes and `measured` after it is restored.

### AC-006: default cwd is the base root
Invoked from a linked worktree, `cwd: base` runs the command at `resolve_base_root(root)` and `cwd: checkout` at the worktree, and the evidence string names the root used.

### AC-007: skill and wrapup call the verb
Both renders of the skill contain, inside the one `**measure first**` step, `hm world outcome measure --all --dry-run`, the record call `hm world outcome measure --all` and the deferral phrase "The rule for every write"; both renders of wrapup contain a third `@hm:answer-gated:outcome-measure` block after `objective-close` with "Measure outcomes now?", one `hm world outcome measure --all` call inside it, and the "write nothing" line.

### AC-008: surface pinned and allowance retired
plan/review/help hashes equal the pre-change pin per arm; wrapup growth ≤ the declared allowance while in flight; at close-out the PLAN has no `surface_allowance`, the delta doc quotes the committed aggregate, and the structural suite is green.

### Test files (spec gate)

| Test file | ACs |
|---|---|
| `tests/unit/test_intent_measure.py` | AC-001, AC-005 |
| `tests/unit/test_world_outcome_measure.py` | AC-002, AC-003, AC-004, AC-006 |
| `tests/unit/test_render_intent_layer.py` | AC-007 |
| `tests/structural/test_outcome_measure_invariance.py` | AC-008 |

## ❓ Open Questions

None — every slot settled. Items for `/hm:plan` ADRs: exact `measure` field set (`timeout_s`
default), selector parsing rules (dotted path with list indexes; regex must have one group;
`last-number` = last float in stdout), the `--all` table shape, allowance amount for wrapup.

## 🔍 Refinement Decisions

- Round 1 — **structured `measure` block** (not a `cmd:` prefix); **fires in all three places**
  (verb, skill "measure first", wrapup 5.7 third question); **`definition_hash` covers the block**
  (absent block hashes as today); **dogfood `intent.yaml` untouched** — tests on tmp roots.
- Defaults: selectors `json:`/`regex:`/`last-number`; `cwd: base` default; no auto-measure at
  `objective close`; `pytest`.
- Discovery lens and direction from [[RESEARCH-outcome-measure]] ("최대한 효율적으로 자동화가능하게").
