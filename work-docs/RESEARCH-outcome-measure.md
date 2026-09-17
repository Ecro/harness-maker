---
type: research
task_slug: outcome-measure
status: complete
created: 2026-09-17
tags: [harness-maker, research, python, intent-layer, outcomes, measurement, subprocess]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://bencher.dev/docs/explanation/adapters/
  - https://bencher.dev/hyperfine/
  - https://bencher.dev/learn/track-in-ci/python/pytest-benchmark/
related_docs:
  - "[[RESEARCH-intent-world-model-objective-layer]]"
  - "[[SPEC-intent-world-model-objective-layer]]"
  - "[[SPEC-objective-gap-proposal]]"
  - "[[PLAN-objective-gap-proposal]]"
  - "[[REVIEW-objective-gap-proposal-2026-09-16]]"
summary: "Structured `measure` block on an outcome + `hm world outcome measure <id>` (shell=False, selector, auto-evidence); manual stays the fallback"
---

# RESEARCH — outcome-measure

## 🎯 Recommended Direction

**Give an outcome an optional, machine-runnable measurement (`measure: {cmd, select}`) next to
its human `how_measured`, and add one verb — `hm world outcome measure <id> [--all]` — that runs
the command with the repo's existing subprocess discipline (argv, `shell=False`, timeout, output
budget, redaction), extracts one number with a small selector, and records it through the
existing `record_value` with auto-generated evidence (argv, exit code, commit, timestamp).** An
outcome without a `measure` block stays manual, exactly as today. The skill's "measure first"
opener and wrapup 5.7 call the verb instead of telling the operator to run something by hand.

Rationale. The first intent RESEARCH already reached this conclusion — "**`measure_cmd` is
mandatory** — the harness runs a command and records its output, the model never types the
number" (its Goodhart mitigation, with `step_sensitivity.py`'s `measure_cmd` as the in-tree
precedent) — and the first SPEC then listed measurement automation as a non-goal to keep the
slice state-only. Two tasks later the user hit the cost: every value is typed by hand, so the
gap table this pipeline just shipped is empty until someone remembers. The pieces exist:
`record_value` already validates and hashes; `second_opinion_oracle` already runs
user-configured commands safely with a budget and redaction; `definition_hash` already turns a
changed definition into `stale_definition`. Main impact is **user-facing workflow value** (the
outcome table fills itself where it can); maintainer cost is one schema field, one verb and two
prose edits.

## 🔍 Refinement Decisions

Discovery lens: **User-workflow / product opportunity** (where a solo maintainer's numbers
actually come from — CLI output, CI, dashboards) and **Technical architecture** (subprocess
discipline, selector, hashing) and **Risk** (executing a string from a versioned YAML; Goodhart).
`--deep` not set; the user set the direction in conversation: "최대한 효율적으로 자동화가능하게",
manual stays the fallback, wrapup should ask rather than measure blindly.

## 🛠️ Approaches Found

### Approach A — `measure` block + `outcome measure` verb (recommended)

| Field | Content |
|---|---|
| Approach | `intent.yaml` outcome gains optional `measure: {cmd: "<argv string>", select: "<selector>", cwd?: base\|checkout}`; `hm world outcome measure <id>` (and `--all`) runs it, selects one number, calls `record_value` with `evidence: "auto: <argv> @ <sha> exit=0"` and the normalised now-timestamp; `--dry-run` prints the number without recording. |
| Assumption | Most outcomes a maintainer cares about are already printed by some command (`hm economics report` → `report.carry_ratio` = 0.672 on this repo today; pytest counts; `hyperfine --export-json`). |
| Evidence | `record_value` (world.py:891) already owns validation + `definition_hash`; `second_opinion_oracle._run` (subprocess argv, `timeout=300`, `truncate`, `redact`) is the shipped pattern for running user-configured commands; `step_sensitivity.measure_cmd` is the precedent for pinning a measurement command next to the thing it measures; first RESEARCH's "measure_cmd is mandatory" paragraph. Bencher's adapter model (parse a harness's JSON export, one selector per metric) is the external shape. |
| Trade-off | A second definition surface: `how_measured` (prose) and `measure` (machine) can drift. Mitigation: `definition_hash` covers the `measure` block too, so editing the command stales every prior value — the Goodhart brake the first RESEARCH asked for. |
| Compatibility | Excellent: `Outcome` dataclass + `validate`, one verb in `world.py`, `command_registry` name, skill/wrapup prose. No gate change. |
| Risk | **low-medium** — executes a string from a versioned, human-authored file (same trust class as `harness.yaml toolchains`); no `shell`, argv via `shlex.split`, timeout, cwd fixed. |

### Approach B — wrapup 5.7 third question + skill "measure first" runs the verb (bundle with A)

| Field | Content |
|---|---|
| Approach | wrapup 5.7 adds an answer-gated **"Measure outcomes now?"** (lists outcomes with a `measure` block and their last value/age); yes → `outcome measure --all`, printed table, no auto-close. The skill's "measure first" opener runs `outcome measure --all --dry-run` and offers to record. |
| Assumption | Effects lag code, so measuring at every wrapup is noise; a question keeps the human in the loop at zero typing cost. |
| Evidence | wrapup 5.7 already has two answer-gated blocks (`<!-- @hm:answer-gated:… -->`); the render test pattern for them exists (`test_ac_015_wrapup_writes_sit_inside_answer_gated_blocks…`). |
| Trade-off | wrapup surface grows (a third block, one call) → `surface_allowance` + retirement phase again. |
| Compatibility | Good; same block shape. |
| Risk | **low** |

### Approach C — external continuous-benchmarking service (Bencher-style) — rejected

Bencher ingests harness JSON exports and tracks them over time, but it is a hosted service:
CLAUDE.md's "100% 로컬 telemetry — 외부 전송 금지" rules it out, and the outcome table already is
the time series (`outcomes.yaml` rows + `definition_hash`).

### Approach D — keep manual — rejected by the user

The gap table stays empty until someone types; the first RESEARCH's Goodhart mitigation (the
model never types the number) is not met either, because today the model *does* type it via
`outcome record` when asked.

## ⚠️ Pitfalls

1. **The agent editing the measurement to make the number move** (first RESEARCH; Goodhart in
   agentic loops). `definition_hash` must include the `measure` block (`cmd` + `select` + `cwd`),
   so any edit stales history and shows up as `stale_definition` in `gap`; the diff to
   `intent.yaml` is a reviewed change (it is a versioned file).
2. **Shell injection through a versioned string.** `cmd` is `shlex.split` into argv, never
   `shell=True`; no `$`/backtick expansion; refuse an empty argv or an option-shaped first token.
   The repo's subprocess rule (`shell=True` 금지 · timeout 필수) applies verbatim.
3. **Wrong cwd.** Observability data lives at the **base** root (`.claude/observability/` is
   gitignored, absent in a worktree) — `hm economics report --root <worktree>` sees nothing.
   The verb must run with `cwd = resolve_base_root(root)` by default and offer `cwd: checkout`
   for repo-content metrics; the recorded evidence names which.
4. **Non-numeric or multi-number output.** A selector is required (`json:<dotted.path>`,
   `regex:<pattern with one group>`, `last-number`); parse failure is a refusal (`WorldError`),
   never a recorded 0. Bencher's adapters solve the same problem per harness.
5. **Noisy measures.** One run = one row; the verb does not average. Averaging belongs in the
   command (`hyperfine --runs 5 --export-json` then `json:results.0.mean`). Record this as a
   documented limit rather than building an aggregator.
6. **Secrets in output.** Reuse `second_opinion_oracle.redact` on captured output before it
   reaches evidence; evidence keeps argv + exit code + sha, never raw stdout.
7. **Rendered harness runs the released plugin cache** (memory: `rendered-harness-pins-released-plugin`)
   — the wrapup/skill prose calling `outcome measure` fails in dogfood until the next release;
   the verb itself works via `uv run python -m harness_maker.world`.
8. **Surface accounting** — wrapup grows (Approach B) → allowance + retirement phase (ADR-008
   of objective-gap-proposal), and `test_playbook_alignment_invariance` pins wrapup hashes? No —
   it pins plan/review/help; the wrapup ratchet (`_CLAUDE_ROUND_TRIPS`, `_ATOMIC_RATCHET`) moves
   by one call and must be re-baselined with attribution.

## ❓ Open Questions

1. **Schema shape.** A structured `measure: {cmd, select, cwd}` block (recommended: explicit,
   validated, hashed) vs a `cmd:` prefix inside `how_measured` (one field, but parsing prose).
2. **Selector language.** `json:<dotted path>` + `regex:<one-group>` + `last-number`
   (recommended — three forms, no library) vs a JSONPath dependency.
3. **Default cwd.** Base root (observability metrics) vs checkout (repo-content metrics);
   recommended: `cwd: base` default with `checkout` opt-in, evidence names it.
4. **Where it fires.** On demand (`outcome measure`), skill "measure first", wrapup 5.7 third
   question — all three (recommended), or on demand only.
5. **Auto-close?** Should `objective close` offer to measure the objective's outcome first?
   Recommended: no — close stays a human verdict; the wrapup question comes before it.
6. **Definition hash.** Include the `measure` block (recommended) — changing the command stales
   history; or keep hashing only `target/how_measured/higher_is_better` and add a separate
   `measure_hash` on the row.
7. **Dogfood outcome.** Fill this repo's `intent.yaml` with one real measurable outcome
   (`carry_ratio` from `hm economics report`, currently 0.672, lower is better) as the acceptance
   fixture, or keep the skeleton and test on tmp roots only.

## 📚 Sources

- Bencher adapters (per-harness JSON parsing, one selector per metric) — https://bencher.dev/docs/explanation/adapters/
- Bencher + hyperfine (`--export-json`, `--file`) — https://bencher.dev/hyperfine/
- Bencher + pytest-benchmark (`--benchmark-json`) — https://bencher.dev/learn/track-in-ci/python/pytest-benchmark/

## 🔗 Related Internal Docs

- [[RESEARCH-intent-world-model-objective-layer]] — "measure_cmd is mandatory" (Goodhart mitigation), the metric-definition-pinned-and-hashed argument.
- [[SPEC-intent-world-model-objective-layer]] — `outcomes.yaml` row schema, `definition_hash`, the "no measurement automation" non-goal this task lifts.
- [[SPEC-objective-gap-proposal]] / [[PLAN-objective-gap-proposal]] — `gap` reasons (`never_measured` / `stale_definition`), the skill's "measure first" opener, ADR-008 allowance retirement (to repeat for the wrapup growth).
- [[REVIEW-objective-gap-proposal-2026-09-16]] — open items the wrapup edit may touch (`--claim` / `--declined` escaping class).
- `src/harness_maker/second_opinion_oracle.py` — subprocess argv + timeout + `truncate` + `redact`; `src/harness_maker/step_sensitivity.py` — `measure_cmd` precedent; memory `rendered-harness-pins-released-plugin`.
