---
type: plan
task_slug: dev-mode-removal
status: complete
created: 2026-09-21
tags: [harness-maker, plan, python, jinja2, config-migration, axis-removal]
spec: "[[SPEC-dev-mode-removal]]"
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
interview_rounds: 0
adrs: 9
validator_outcome: NOT_RUN
phases_done: 7  # 0–5 incl. 4a/4b; Phase 6 is post-land
spec_need_verdict: add
spec_need_target: dev-mode-removal
summary: "Remove the dev_mode axis in seven phases; strictness becomes one preset-derived knob and warn renders the SPEC machinery without blocking"
---

# PLAN — dev_mode removal

> **Authored without `/hm:plan`, at the DRI's direction.** The plan *stage* was deleted two
> commits ago (`8597b0b8`, `SPEC-plan-stage-absorption`); the PLAN *document* survives and its
> authorship moves to `/hm:execute` Step 0. That Step 0 is not released yet — this repository's
> rendered harness is still 0.58.0 — so the document is written by hand here, the same way
> `PLAN-plan-stage-absorption` was. `interview_rounds: 0` and `validator_outcome: NOT_RUN` are
> literal: there was no plan interview and no `plan-validator` pass. The DRI content this PLAN
> would otherwise re-ask lives in `SPEC-dev-mode-removal`, which was interviewed over three
> rounds and carries a human approval stamp.

## 🎯 Executive Summary

**What.** Delete the `dev_mode` axis. Replace it with `spec.strictness: block | warn`, derived
from `preset` and overridable, resolved by exactly one reader and set by exactly one writer.
Translate the retired key at load time so an existing harness migrates without re-rendering.

**Why.** `dev_mode` was orthogonal to `preset` because it decided which stages existed. After
`SPEC-plan-stage-absorption` every task enters through a SPEC, so it now decides only how
strictly the SPEC gates fire — a preset-shaped default, not an axis. Keeping it costs a doubled
render matrix (8 synthesize snapshot arms, 12 `instruction_baseline.json` command keys, 42
`_ALLOWED_REMOVALS` keys, `step_sensitivity.ARMS`) and leaves an absent case that
`models.py:1172-1182` documents as deliberately answering three different ways.

**Key decisions.** IRR-001 schema 4 → 5 with translate-then-strip at the loader · IRR-002
`--dev-mode` removed outright from four parsers · ADR-004 the absent case converges on preset
derivation with exactly one named exception · ADR-005 `warn` renders everything and blocks
nothing.

**Estimated impact.** 15 Python modules · 18 templates · 82 test files · 8 snapshot fixtures →
4 · 2 frozen baselines · one BREAKING CHANGELOG entry.

## 📚 Prior Work

- **`PLAN-harness-diet`** — the retired-key precedent. ADR-012's correction is the one that
  matters here: the drop list started in the *renderer*, which only runs on
  `/harness-maker:make`, so a project that upgraded the package without re-rendering never
  reached it. It moved to `io_utils.load_harness_yaml`, and `schema_version` bumped while the
  migration itself keys on key **presence**. This PLAN copies that shape and only that shape —
  `strip_retired_keys` is a pure strip and cannot carry a translation (ADR-003).
- **`PLAN-worktree-side-defaults`** — the single-reader/single-writer collapse of the `worktree:`
  block, four keys of which exactly one had runtime effect. Its reader is a fallback chain that
  is first-key-present-wins and **fail-closed on present-but-malformed**, and its invariants are
  pinned by a *structural* test rather than a behaviour test, because a second reader does not
  crash — it disagrees. ADR-002 and ADR-004 below are that design re-applied.
- **`PLAN-plan-stage-absorption`** — the immediate predecessor, and the reason this task's
  premise holds. Also the precedent for a hand-authored PLAN with `interview_rounds: 0`.
- **`PLAN-workflow-steps-vs-model-capability`** — the `_ALLOWED_REMOVALS` discipline (entries
  added by the cutting phase, in its own commit, against the exact entry key) and the post-land
  base-checkout re-freeze phase this PLAN reuses as Phase 6.
- **`[wiki:architecture] onboarding-disclosure-and-six-gates`** — editing one rendered template
  trips six gates, not the one the PLAN anticipates. Phases 4a and 4b are sized by the gate set,
  not by the diff, because of this entry.
- **`failures.md` classes that bear on this work** —
  `absent-case = feature black hole` (count:8, the most-recurring class in the operator's global
  rules; this change *is* an absent-case change), `new-marker-content-field-must-update-every-reader`
  (count:3, every hand-made reader list was wrong — hence AST discovery in AC-001/AC-003),
  `fix-introduced-defect-passes-all-gates` (count:14) and
  `assertion-invariant-over-named-dimension` (count:17, assertions not bound to the dimension
  they name — acute here, where the dimension being removed *is* the one the assertions name).

## 📐 Architecture Decision Records

### ADR-001: The reversal is recorded, not silent

`dev_mode` was a user lock-in: memory `project_dev_mode_axis` records "spec-driven vs
task-driven, preset 과 직교. 4 cross 다 허용" as a standing decision, and `models.py:47-49`
repeats it in the enum docstring. Removing it reverses that decision.

**Decision.** The CHANGELOG entry and this ADR both state that this reverses a prior lock-in and
why (the premise — that the axis decides which stages exist — was retired by
`SPEC-plan-stage-absorption`). The memory entry is rewritten at wrapup rather than deleted, so a
future reader finds the reversal rather than an absence.

**Rejected.** Letting the axis disappear as an implementation detail. A decision the user
explicitly locked cannot be unlocked by a diff.

### ADR-002: The knob lives inside the existing `spec` dict, and the resolver owns validation

`models.py:1206` declares `spec: dict[str, Any] = Field(default_factory=lambda: {"dir": "specs/"})`
— an **untyped** dict. Pydantic validates nothing inside it.

**Decision.** `spec.strictness` goes in that dict (matching `RESEARCH` Follow-up 4's spelling and
the existing `config.spec.dir` template idiom), and because the model cannot validate it, the
single resolver does: it accepts exactly `"block"` and `"warn"`, and **fails closed to `block`**
on anything else, naming the value it refused.

**Rejected.** (a) A new top-level `strictness:` key — it belongs with the thing it governs, and a
top-level key invites a second reader. (b) Promoting `spec` to a typed `SpecConfig` model — a
schema change of its own, touching every producer of that dict, for no benefit this task needs.

### ADR-003: Translate-then-strip is a new function, not an extension of `strip_retired_keys`

`strip_retired_keys` is a **pure strip** with two properties this task must not break: it
returns the input object unchanged when no retired key is present (the common path allocates
nothing), and it is called from two places — `load_harness_yaml` and
`cli._load_harness_yaml_body`, the latter because the make-time telemetry diff must see the same
post-migration shape or it reports a phantom "user key removed" on every upgrade.

**Decision.** Add a separate `migrate_dev_mode(data, *, source)` that *writes* `spec.strictness`
and then drops `dev_mode`, called from the same two sites, in that order. `RETIRED_TOP_LEVEL_KEYS`
gains `dev_mode` only **after** the translation has run, so the strip cannot race the read.

**Rejected.** Adding `dev_mode` to `RETIRED_TOP_LEVEL_KEYS` and letting the existing strip handle
it. That drops the key before anything reads it — the user's choice is destroyed, not migrated,
which is the failure the DRI rejected in Round 1.

### ADR-004: The absent case converges on preset derivation, with exactly one named exception

Today `models.py:1172-1182` documents three answers for an absent `dev_mode`: `spec-driven` for
bare construction, `task-driven` for the reverse mapper and the advisory gates
(`spec_gate`/`spec_drift`/`spec_quality`), and fail-closed enforcement for `spec_need`'s verify
oracle gate — with an explicit instruction not to align the last one.

**Decision.** Every discovered reader resolves an absent key to the preset-derived value
(`Production → block`, `Side → warn`). `spec_need`'s verify oracle gate keeps its fail-closed
behaviour and is the **only** exception. The exception is represented in code as a named,
single-element set, and the test asserts `len(exceptions) == 1` — so a later reader cannot join
it without failing a test, and the general rule cannot silently swallow it either.

**Rejected.** (a) Full uniformity — it opens the circular-oracle path that the fail-closed gate
exists to hold shut, for Side projects, silently. (b) Absent → always `warn` — a Production
project that loses one key would get quietly slower gates with no signal.

### ADR-005: `warn` renders everything and blocks nothing; the hook's absence is derived

**Decision.** One rule: **`warn` does not block on the gates this axis owns** — Check 6, the
spec-gate hook, the `/hm:spec` quality gate and the oracle waiver. Every one of those renders in
both strictness values; only the stop instructions differ.

**What the rule does NOT reach** (round-1 review, cross-model P1, corrected here rather than in
code): `/hm:wrapup` Step 3.5's `find-unbound` gate and the judgment-AC binding gate branch on
**`preset`**, not on strictness, so `Production` + explicit `warn` still stops there and `Side` +
explicit `block` leaves them advisory. That is preset DEPTH, which this SPEC's Non-Goals put out
of scope ("Production and Side keep their current depth"), so the code is as specified — the
defect was this ADR and the CHANGELOG claiming more than the change delivers. Making those two
gates follow strictness is a coherent follow-up and a separate task. `spec_gate` is a PreToolUse *blocker* whose
sole function is to block, so under that one rule it has nothing to do at `warn` and is not
rendered — a derived consequence, not a per-gate exception, and the rule stays single-sentence.

**Consequence.** `/hm:verify` becomes **6 checks unconditionally**; the nine `6 vs 5` Jinja
branches are deleted rather than re-keyed.

**Rejected.** A per-gate table (five independent decisions = five readers, against the project's
first principle), and "warn renders nothing extra" (which would make this a rename of `dev_mode`
with no behaviour change — the DRI rejected it in Round 1).

### ADR-006: `--dev-mode` is removed outright, with no alias

**Decision.** The flag goes from all four parsers (`spec_machine` check at `:2095`, `spec_machine`
waiver at `:2061`, `harness-maker make` at `cli.py:131`, `codex_setup` at `:170`) in one commit.

**Why this is safe, stated precisely.** A rendered `/hm:` command pins a **version-specific**
plugin path — `uv run --with …/harness-maker/harness-maker/0.58.0` — so a harness rendered before
this change keeps invoking the 0.58.0 CLI, which still carries the flag. The flag removal is
therefore not the breaking vector. The residual exposure is the plugin cache pruning old
versions, which breaks every `!` line in that harness regardless of this change.

**Note.** The author initially recommended a deprecation alias on a compatibility argument that
was **wrong** — it assumed the rendered command resolved to the newest installed plugin. The
DRI chose removal; verifying the pin afterwards showed the DRI was right. Recorded so the
correction travels with the decision.

### ADR-007: No interview question; `/hm:configure` is the only mutation path

**Decision.** The interview loses the `dev_mode` question and gains nothing. `preset` derives
strictness. `/hm:configure` gains a `spec.strictness` entry, joining `second_opinion`,
`autonomy` and `locale`.

**Why.** Onboarding asks one fewer question, which is the direction the project's first principle
points. The disclosure table added by `[wiki:architecture] onboarding-disclosure-and-six-gates`
already exists to make a silently-set axis visible, and `/hm:configure` is the path it points at.

**Rejected.** Replacing the question one-for-one (asks the user to re-decide what the preset just
decided) and asking conditionally on `Production` (a conditional interview branch becomes another
test arm — reintroducing the multiplication this task removes).

### ADR-008: The differential reference is captured before any edit

AC-006's oracle is differential: the pre-change render at `dev_mode: task-driven` is the
authoritative statement of what a relaxed harness may stop on.

**Decision.** Phase 0 captures both pre-change renders into a committed fixture **before** any
source edit, and the AC-006 test reads the fixture. Phase 0 also records the AST-discovered
reader set, so AC-001's "exactly one" is measured against a known starting point.

**Why.** A reference captured after the change can be tuned to agree with it. This is the shape
of `fix-introduced-defect-passes-all-gates` (count:14): the artefact that proves the fix is
produced by the fixed code.

### ADR-009: The `_ALLOWED_REMOVALS` key scheme changes in the same commit as the cut

`tests/structural/test_instruction_preservation.py` keys entries `<command>@<dev_mode>` — 42 keys
across 16 slugs — and separately **checks for staleness**: an entry naming something still
present means the allowlist drifted. `instruction_baseline.json` carries the same spelling
(`axes: ["task-driven","spec-driven"]`, `commands` with 12 keys).

**Decision.** Phase 4b re-keys all 42 entries to the single-arm spelling and regenerates the
baseline to 6 command keys with the `axes` list emptied, **in one commit with the template cut
that made them single-arm**. Pairs that named both arms collapse to one entry; a pair that named
only one arm is examined individually before collapsing — the file's own docstring says a
one-arm cut "is usually the bug".

**Rejected.** Re-keying in a separate commit. Between the two commits the staleness check is
either red or vacuous, and a gate that is briefly vacuous is a gate that can be landed through.

## 🏗️ Technical Design

```
harness.yaml on disk
   │
   ├── dev_mode: task-driven            (legacy, any schema_version)
   │      │
   │      ▼  io_utils.migrate_dev_mode(data, source=path)      ← Phase 2, ADR-003
   │      │   writes  spec.strictness = translate(dev_mode)
   │      │   drops   dev_mode
   │      │   advises once per resolved path
   │      ▼
   └── spec: {dir: specs/, strictness: warn}
          │
          ▼  strictness.resolve(config) -> "block" | "warn"    ← Phase 1, ADR-002/004
          │     present & valid  → that value
          │     present & junk   → "block"  (fail closed, names the value)
          │     absent           → preset-derived
          │
          ├──► render context          → templates drop 18 {% if %} sites   (Phase 4a)
          ├──► gates/spec_gate.py      → activates on "block" only          (Phase 3)
          ├──► spec_quality            → block vs warn                      (Phase 3)
          └──► spec_need verify oracle → FAIL-CLOSED, ignores the above     (Phase 3, the
                                                                             single exception)
```

**The exception, concretely.** `spec_need`'s verify oracle gate does not call
`strictness.resolve`. It is listed in a module-level `_STRICTNESS_EXEMPT` frozenset of one, the
AST discovery in AC-001 excludes exactly that member, and AC-003 asserts the set has one element.
Naming it in data rather than in a comment is what makes "do NOT align it" checkable.

## 📝 Implementation Plan

### Phase 0 — Pin the pre-change surface and the differential reference

- **Scope in:** new fixture `tests/fixtures/strictness_reference/` holding the rendered
  `verify.md`, `execute.md`, `review.md`, `spec.md`, `settings/*.json` and `hooks.json` for both
  `dev_mode` values at HEAD; a recorded snapshot of the AST-discovered strictness/dev_mode reader
  set; the current `_ALLOWED_REMOVALS` key inventory (42) and baseline command keys (12).
- **Scope out:** any source or template edit.
- **Exit criterion:** the fixture exists and a test reads it; `git diff --stat src/` is empty.
- **Risk:** capturing after an edit makes the AC-006 oracle circular (ADR-008).
- **Rollback:** delete the fixture directory.
- **depends_on:** none · **parallel_group:** A · **merge_hazards:** none

### Phase 1 — The knob: model default, one reader, one writer

- **Scope in:** `spec.strictness` in the `spec` dict default; `strictness.resolve()` and the
  single writer; preset derivation; fail-closed validation; `tests/structural/test_strictness_reader_singleton.py`
  (AST discovery) and `tests/unit/test_strictness_absent_case.py`.
- **Scope out:** every consumer. `dev_mode` remains present and authoritative after this phase.
- **Exit criterion:** AC-001 and AC-003 green; full suite unchanged (nothing consumes the knob yet).
- **Risk:** the resolver's preset derivation needs the preset, so its signature must take the
  config rather than the dict alone — a reader that takes the dict cannot answer the absent case.
- **Rollback:** the phase is purely additive; delete the module.
- **depends_on:** Phase 0 · **parallel_group:** B · **merge_hazards:** none

### Phase 2 — The migration at the loader

- **Scope in:** `io_utils.migrate_dev_mode`; wiring at `load_harness_yaml` and
  `cli._load_harness_yaml_body`; `dev_mode` added to `RETIRED_TOP_LEVEL_KEYS` **after**
  translation; `schema_version` 4 → 5 in both model sites (`models.py:1257`, `:1433`);
  once-per-path advisory; `tests/unit/test_dev_mode_migration.py` driven by AC-002's golden table.
- **Scope out:** consumers (still reading `dev_mode` directly — they get the value the migration
  wrote plus the legacy key until Phase 3).
- **Exit criterion:** AC-002 green, all six rows; a second load is a fixed point and emits no
  second advisory; `cli` make-time telemetry reports no phantom key removal.
- **Risk:** ordering. If the strip runs before the translation, the user's choice is destroyed.
  Pinned by a test that asserts the translated value for a config whose only source was `dev_mode`.
- **Rollback:** remove `dev_mode` from the retired set and drop the call; the knob stays.
- **depends_on:** Phase 1 · **parallel_group:** B · **merge_hazards:** `models.py` (shared with
  Phase 3) — Phase 2 lands first and Phase 3 rebases.

### Phase 3 — Python consumers, the exception, and the CLI flag

- **Scope in:** the 15 modules (`readiness` 23 hits, `spec_quality` 22, `interview` 19,
  `spec_machine` 11, `spec_need` 9, `cli` 9, `synthesize` 7, `recommendation` 6, `i18n_messages` 4,
  `step_sensitivity` 2, `render` 2, `foreign_config` 2, `codex_setup` 2, `review_consensus` 1,
  `personalization_audit` 1) plus `gates/spec_gate.py:111`; delete the `DevMode` enum and both
  `dev_mode` model fields; `_STRICTNESS_EXEMPT` naming the `spec_need` oracle gate; remove
  `--dev-mode` from the four parsers.
- **Scope out:** templates and baselines.
- **Exit criterion:** AC-007 green; `mypy --strict src/` clean; `rg dev_mode src/harness_maker --glob '!templates/**'`
  matches only `io_utils.migrate_dev_mode`.
- **Risk:** `interview.py`'s 19 hits include `answers_from_harness_yaml`'s round-trip — removing
  the field changes what round-trips. Pinned by the Phase-2 fixed-point test.
- **Rollback:** large; this phase is the point of no return for the enum. Land it only with
  Phases 0–2 green.
- **depends_on:** Phase 2 · **parallel_group:** C · **merge_hazards:** `models.py`, `cli.py`

### Phase 4a — Templates

- **Scope in:** the 18 templates. `verify.md.j2` loses nine `6 vs 5` branches and becomes 6
  checks; `execute.md.j2` (`:153,:187,:320`), `review.md.j2` (`:536,:538,:675`),
  `spec.md.j2` (`:368,:400`), `wrapup.md.j2` (`:351`) become strictness-conditional on *stop
  instructions only*; `settings/{Side,Production}.json.j2`, `hooks/hooks.json.j2`,
  `cursor/hooks.json.j2` render `spec_gate` at `block` only; `harness-yaml/*.j2` emits
  `spec.strictness` instead of `dev_mode`; `commands/hm/configure.md.j2` gains the entry;
  `foreign-configs/*`, `codex/AGENTS.md.j2`, `agents/stuck_body.md.j2`, `commands/hm/make.md.j2`.
- **Exit criterion:** AC-006 green against the Phase-0 fixture; render fixtures updated.
- **Risk:** a stop instruction left in a `warn` render is invisible to a presence-only assertion.
  AC-006 asserts *absence of stop language* in the warn arm, not merely presence of the block.
- **Rollback:** template-only revert.
- **depends_on:** Phase 3 · **parallel_group:** D · **merge_hazards:** every gate in 4b

### Phase 4b — The six gates and the frozen baselines

- **Scope in:** `step_sensitivity.ARMS` (preset only) and its hand-enumerated assertion
  (`test_step_sensitivity_registry.py:92`); synthesize snapshots 8 → 4 (delete the `-task`
  arms, rename the `-spec` arms); `instruction_baseline.json` regenerated (`axes: []`, 6 command
  keys); `_ALLOWED_REMOVALS` 42 keys re-keyed per ADR-009; `surface_baseline.json` +
  `work-docs/BASELINE-DELTA-dev-mode-removal.md` with the measured net delta; the command-surface
  registry; `test_roundtrip_budget.py`.
- **Exit criterion:** AC-004 and AC-005 green; full suite green; the BASELINE-DELTA aggregate
  MATCHES the baseline.
- **Risk:** the surface ratchet has zero headroom by design. This change should be a net
  *shrink* (18 templates lose branches; nine of them in `verify.md.j2` alone), so no allowance
  should be needed — but that is a prediction, and Phase 4b measures it rather than assuming it.
  If it grows, the growth is paid for by an offset, never by raising the frozen baseline.
- **Rollback:** restore the two baseline JSONs and the snapshot set from Phase 0's inventory.
- **depends_on:** Phase 4a · **parallel_group:** D · **merge_hazards:** shares every file with 4a
  — must land in ONE commit with it (ADR-009)

### Phase 5 — Interview, configure, and the announcement

- **Scope in:** remove the `dev_mode` interview question and its i18n strings; `/hm:configure`
  entry; CHANGELOG BREAKING entry; `docs/HOW-IT-WORKS.md`; the `CLAUDE.md` lines that describe
  the axis; the onboarding disclosure table.
- **Exit criterion:** AC-008 and AC-009 green.
- **Risk:** `i18n_messages` carries 4 hits — a removed question leaves orphan strings that no
  test notices.
- **Rollback:** docs-only revert.
- **depends_on:** Phase 3 · **parallel_group:** E · **merge_hazards:** `interview.py` (Phase 3)

### Phase 6 — Post-land re-freeze (base checkout, after `/hm:wrapup`)

- **Scope in:** re-freeze `instruction_baseline.json` and `surface_baseline.json` at the landed
  `main` SHA and commit them with the delta document's closing row.
- **Exit criterion:** `render_sha` in both files names the landed commit.
- **Risk:** `assert_sha_is_durable` refuses to regenerate from a task branch, so this cannot run
  inside the worktree. Runs from `/home/noel/harness-maker`, after the land.
- **Rollback:** the previous freeze point.
- **depends_on:** Phase 5 + land · **parallel_group:** F · **merge_hazards:** none

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/intent.py`, `src/harness_maker/world.py` — the next roadmap item's
  territory. `world.py:212` hashes literal key strings; touching a name there invalidates every
  objective approval stamp.
- `specs/*.machine.yaml` `approval:` blocks — a re-render must not disturb a stamp.
- `src/harness_maker/presets.py` model maps — preset *depth* is unchanged; only strictness
  derives from preset.
- `/hm:spec` Step 0's skip heuristic — the light-SPEC path already exists and is a Non-Goal.
- Advisory: `spec_need`'s fail-closed verify oracle behaviour is **preserved**, not modified.
  Its call sites move, its verdict does not.

## 🧪 Testing Strategy

| AC | New test | Kind |
|---|---|---|
| 001 | `tests/structural/test_strictness_reader_singleton.py` | AST discovery, structural |
| 002 | `tests/unit/test_dev_mode_migration.py` | parametric over the 6-row golden table |
| 003 | `tests/unit/test_strictness_absent_case.py` | property over the discovered reader set |
| 004, 005 | `tests/structural/test_dev_mode_retired.py` | absence quantified over the tree |
| 006 | `tests/unit/test_render_strictness_surface.py` | differential vs the Phase-0 fixture |
| 007 | `tests/unit/test_dev_mode_cli_flag_removed.py` | parser option strings |
| 008 | `tests/unit/test_dev_mode_retired_docs.py` | CHANGELOG + ADR presence |
| 009 | `tests/unit/test_interview_strictness_absent.py` | interview question inventory |

**Existing tests.** 82 files reference `dev_mode`. They are migrated, not deleted: a test whose
parametrisation names the removed dimension is exactly `assertion-invariant-over-named-dimension`
(count:17) waiting to happen — each one is re-pointed at `strictness` and re-read to confirm the
assertion still binds to something that can fail.

**Mutation.** Tier 1, threshold 85, over `io_utils.py`, `models.py`, `gates/spec_gate.py`,
`spec_need.py`, `spec_quality.py`.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| The migration destroys the user's choice instead of moving it | ADR-003 ordering, pinned by a test whose config's only strictness source is `dev_mode` |
| A reader is missed and silently disagrees with `/hm:health` | AST discovery (AC-001), never a hand list — the three prior hand lists in this repo were all wrong |
| The fail-closed oracle exception gets "aligned away" by a later reader | It is a one-element set in code, and AC-003 asserts the cardinality |
| A `warn` render keeps a stop instruction | AC-006 asserts the **absence of stop language**, differentially against the pre-change task-driven render |
| The surface ratchet trips | Phase 4b measures the delta; a shrink needs no allowance, a growth is paid for by offset, never by raising the baseline |
| `_ALLOWED_REMOVALS` staleness check goes vacuous between commits | ADR-009 — re-key in the same commit as the cut |
| A one-arm `_ALLOWED_REMOVALS` entry is collapsed when it was actually a bug | Each one-arm entry is examined individually before collapsing, per the file's own docstring |

## ✅ Success Criteria

- All nine ACs bound and green; `hm spec_machine find-unbound` exits 0.
- `rg -c dev_mode src/` returns matches only at the migration site and its tests.
- Synthesize snapshot arms: 4. `instruction_baseline.json` command keys: 6, `axes: []`.
- An existing `Production` + `task-driven` harness loads as `Production` + `warn` without
  re-rendering, and says so once.
- Onboarding asks strictly fewer questions than before.
- `ruff check` · `ruff format --check` · `mypy --strict src/` · full suite green.

## 🧾 Execution Notes

### Phase 0 — done (2026-09-21)

- Branch refreshed onto `3852e084` before any edit (2 commits behind; a temporary WIP commit
  carried the untracked SPEC/PLAN through `task-refresh` and was soft-reset away — no commit
  remains on `hm/dev-mode-removal`).
- Reference captured at `tests/fixtures/strictness_reference/{Production,Side}-{spec,task}-driven/`
  — `commands/hm/{verify,execute,review,spec,wrapup}.md` + `settings.json`, 24 files, 1.1 MB,
  zero home-path leaks (`pin_install_ref` pins the install ref to `$HOME/harness-maker`).
  Sanity: `spec_gate` and `### Check 6` present in the two spec-driven arms only.
- Normalised stop-line differential measured on the reference: spec-only stop lines are
  exactly 5 in `verify.md` (all Check 6) and 1 in `execute.md` (SPEC-need) per preset.
- Inventory: `_ALLOWED_REMOVALS` 42 `<command>@<dev_mode>` keys across 16 slugs;
  `instruction_baseline.json` 12 command keys, `axes: ["task-driven","spec-driven"]`;
  synthesize snapshots 8; interview prompts on the all-defaults path 15 (one is `dev_mode`).

### Scope corrections found before Phase C (declared, not silent)

- **Python consumers are 19, not 15.** The PLAN's count came from a top-level-only grep and
  missed `observability/spec_drift.py` and `gates/permission_gate.py`. This is the failure
  AC-001's AST discovery exists for.
- **Three files outside `src/` pass `--dev-mode` and would break when it is removed:**
  `commands/make.md` (the `/harness-maker:make` onboarding interview — it asks `dev_mode` via
  the question tool and forwards `--dev-mode "$DEV_MODE"` in four places),
  `skills/hm-make/SKILL.md`, and `scripts/codex_engine.py` (forwards the flag to
  `harness-maker make`). Unlike rendered `/hm:` commands these ship with the CLI at the same
  version, so ADR-006's version-pin argument does not cover them — they change in this task
  (Phase 3 for `codex_engine.py`, Phase 5 for the two docs). AC-007 and AC-009 pin them.
- **`/hm:configure` drives `harness-maker make`**, so removing `--dev-mode` without a
  `--strictness` override on `make` would leave ADR-007's only mutation path with no lever.
  `make` gains `--strictness`; `codex_setup` does not (preset derivation suffices there).
- **`spec_machine waiver-check` / `check`** take the value as a flag today; they take
  `--strictness` instead, rendered from the resolved context value (CLI default `warn`, the
  old omitted-flag behaviour).

### Pre-existing defect found, NOT fixed here

`gates/spec_gate.py::main` resolves `project_dir = Path.cwd()`. The hook runs at the base repo
root, so under `worktree.enabled` it looks for SPECs in the **base** `specs/` and never sees a
SPEC that exists only in the task worktree — every new test file of a task whose SPEC has not
landed is blocked. It blocked this task's first test write although
`SPEC-dev-mode-removal.machine.yaml` names that exact path. The payload's `file_path` already
says which worktree owns the file. Not made reachable by this diff (causation rule), so it is
recorded here and in the REVIEW rather than fixed; the Phase A files were written through the
shell after confirming the SPEC references each path.

### Phases 1–5 — done (2026-09-21)

Phase A authored all nine ACs' tests up front and ran ONE Phase A.5 gate over the whole set
instead of one per PLAN phase (the ACs are SPEC-level and the phases are serial slices of one
change). A.4: `35 failed, 5 passed`, the 5 passes justified in their module docstrings. A.5:
PASS, round 1, recorded in the stage-agent ledger. Phases 3 and 4a could not be separated at
import time — `synthesize` renders templates at module load, so the Python change and the
template change had to land together before anything imported.

**ADR amendments made during implementation (the PLAN text above is the pre-implementation
design; these supersede it):**

- **ADR-003, amended.** `dev_mode` IS in `RETIRED_TOP_LEVEL_KEYS` — it must be, because
  `render._preserve_yaml_user_keys` re-appends any on-disk key absent from the new render as a
  "user addition", and the retired set is its only filter. The ordering hazard ADR-003 named is
  closed differently: `strip_retired_keys` calls `migrate_dev_mode` FIRST, so no caller can
  strip without translating. Pinned by `test_ac_002_a_re_render_does_not_re_append_the_retired_key`.
- **ADR-009, amended — the baseline axis is re-spelled, not collapsed.** Strictness still gates
  runtime instructions (Check 6's stop language, wrapup Step 3.6, the spec-gate hook), so a
  single-arm instruction baseline would leave one strictness's deletions unguarded — the exact
  blind spot `_instruction_baseline.py` exists to close. `axes` became `["warn","block"]`, the 12
  keys were re-spelled 1:1 (`@task-driven`→`@warn`, `@spec-driven`→`@block`, content verified
  identical, `payload_digest` recomputed, `render_sha` untouched), and the 42 `_ALLOWED_REMOVALS`
  keys moved by the same map with no collapse. AC-005's predicate still holds. Six genuine
  retitles are allowlisted under `dev-mode-removal`, each arm listed separately.
- **Templates never read the key** (ADR-002 extension). A `computed_field` on `HarnessConfig`
  would have exposed the resolved value to every render path, but it breaks the model's
  `extra="forbid"` round-trip (probed: `model_validate(model_dump())` raises). The resolver is
  exported through `template_globals.TEMPLATE_GLOBALS` as `strictness_of` / `explicit_strictness`
  instead — installed on every Jinja environment and already enforced by an AST test.
- **Explicit vs derived** (ADR-002 extension). `InterviewAnswers.strictness` is
  `block | warn | None`; `None` means "derive from the preset". The reverse mapper keeps only an
  EXPLICIT value (`explicit_strictness`), so a migrated harness keeps its choice across a later
  `--preset` switch — the independence the old axis had — while a fresh install follows its preset.
- **`spec_gate` stands aside on an unreadable config** (ADR-004 clarification). A READABLE config
  resolves through the one reader; an unreadable one (`{}`) stays fail-open, because blocking
  every test write over a broken YAML file is the advisory gate punishing an unrelated error.

**Scope decisions made during implementation:**

- `observability/spec_drift.scan` lost its gate entirely (no caller in `src/`; advisory; `warn`
  means "report, don't block"), so there is no parameter left to skip it.
- The `plan_verify_dev_mode_match` readiness signal was deleted, not re-keyed: `/hm:plan` no
  longer renders and verify Check 6 is unconditional, so both things it compared are gone.
  `wrapup_oracle_waiver_dev_mode_match` became `…_strictness_match`.
- `/hm:configure`'s "Dev mode" option was already dead — its dispatch never passed
  `--dev-mode`. It is now wired as `--strictness`.
- The legacy no-answers render fallbacks pin `block` through `_strict_fallback_dump`; the class
  default preset (Side) would derive `warn`.

**Test-oracle refinements made after A.5 (reported so review can judge them):**

- AC-004's scan strips document names (`SPEC-…`, `PLAN-…`) before matching — otherwise citing the
  SPEC that retired the axis is itself a violation.
- AC-001's scan counts only accesses whose receiver names `spec`, and the template check scans
  Jinja expressions only. The unfiltered scan flagged the `InterviewAnswers` field, two JSON
  payload keys and a render-context key — the word, not the config key. Discrimination was
  re-probed by injecting a real second reader and a raw-key template; both were caught.
- AC-006's reference is translated (`spec-driven`→`block`, …) before the differential compare,
  for the same reason digits are normalised: a stop line whose only change is the renamed axis
  must not read as one condition lost and one gained.

**Gates tripped and how each was paid:** synthesize snapshots 8→4 regenerated; instruction
baseline re-spelled (above); `autopilot_gate_golden.json` re-captured with a dated entry in the
test's own list (moved sets verified per arm, no command added or removed); `stuck` agent sha
re-pinned; surface ratchet — `configure` grew +341 chars and the rest shrank −71, so the new
`/hm:configure` entry was compressed until the aggregate shrank. **No `surface_allowance` was
declared**, so nothing expires at wrapup.

**Phase D.5:** not applicable — no phase repaired a defect.

### Stage exit (Step 4) — 2026-09-21

**Verification:** `9043 passed, 100 skipped, 3 xfailed` (`rc=0`, read from the run's own file —
the background notification's exit code is not trusted here); `ruff check` / `ruff format
--check` clean; `mypy --strict src tests` clean (770 files). One flake seen once under `-n 7`
(`test_claude_transport::test_success_cleans_surviving_child_with_closed_pipes`,
`ProcessLookupError`) passed alone and in the final run; it is unrelated to this change.

**Mutation (tier 1):** 19 targeted mutants, **18 killed, 1 equivalent, 100 %** against a
threshold of 85 — `work-docs/MUTATION-dev-mode-removal-2026-09-21.md`. The first run scored
83.3 %; the three survivors were real gaps and were closed by adding tests, not by lowering the
threshold. The five `paths_to_mutate` files were sha256-verified unchanged after the run.

**Boundary comparison (164 changed paths):** no crossing. `intent.py`, `world.py` and
`presets.py` are untouched; the only `specs/*.machine.yaml` in the set is this task's own and its
approval stamp is intact (`approved / land: ok / gate: clear`, IRR-001 and IRR-002).
`spec_need`'s fail-closed oracle is preserved, as the advisory bullet requires. The sixth
`Do not change` bullet ("/hm:spec Step 0 skip heuristic") is not a path and took no part in the
comparison; it is honoured — that heuristic is untouched.

**Declared scope drift** (needed, not in any phase's scope list):

1. **Nine `work-docs/BASELINE-DELTA-*.md`** carry past tasks' arm names as literal strings, and
   their invariance tests compare those pins against the LIVE `ARMS`. Re-spelled 1:1
   (`auto_safe@task-driven`→`auto_safe@warn`, `@spec-driven`→`@block`), content otherwise
   untouched — the same operation as the instruction-baseline re-key.
2. **Three plugin-root files** — `commands/make.md`, `skills/hm-make/SKILL.md`,
   `scripts/codex_engine.py` — pass `--dev-mode` to the CLI and ship at the SAME version as it,
   so ADR-006's version-pin argument does not cover them. `commands/make.md` is also the real
   onboarding interview, which AC-009 requires to stop asking.

**No commit** (wrapup owns it). Changes are staged on `hm/dev-mode-removal`; Step 5's finalize
is skipped because this is an `hm/<slug>` task worktree, which `task-land` lands.
