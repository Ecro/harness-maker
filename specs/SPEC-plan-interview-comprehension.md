---
type: spec
task_slug: plan-interview-comprehension
status: approved
created: 2026-08-13
tier: 2
tags: [harness-maker, spec, jinja2, python, interview, plan-stage, harness-yaml]
test_framework: pytest
research_doc: "[[RESEARCH-plan-interview-comprehension]]"
summary: "interview.comprehension.depth ordinal that discloses the plan/spec interview's design picture"
---

# SPEC — Plan/spec interview comprehension depth

## 🎯 Intent

`/hm:plan` already synthesizes a complete design picture — Step 1 is titled
*"Pre-interview internal draft (NOT shown to user)"* and produces tentative architecture,
candidate phase decomposition, and a blast-radius-ranked ambiguity list — and then withholds it.
Step A's round-by-round "current plan state" block is explicitly optional and skippable. The user
therefore answers architectural questions through a keyhole: they see one ambiguity and a
one-sentence "why it matters", never the whole design or what each option rewrites downstream.

This SPEC adds a single `harness.yaml` ordinal that turns disclosure on. It spends its budget on
**context per question**, never on more questions — the 5-term inequality gate and its
`open_ended_cap_by_locale` stay untouched.

## 🌅 Outcomes

After this ships, a harness user running `/hm:plan` on a non-trivial task can:

- Read a **design brief** in chat *before* Round 1 — goal, component/data-flow sketch, phase
  skeleton, and the ranked ambiguity list stating which items will be asked and which are being
  defaulted (with the default and its reason).
- See **what changed** in the design between rounds, as a delta, without asking.
- At `deep`, see for each question: what it decides · what it rewrites downstream · the
  recommended default and why · the reversibility cost — and a closing readback of the locked
  design.
- Choose the level with **one** key (`interview.comprehension.depth`), and a harness that opts
  out (`minimal`) pays **zero** additional rendered surface.

What they cannot do today: any of the above. The information exists and is discarded.

## 📋 In-Scope Scenarios

### S1: Default new install discloses the design brief
**Given** a new harness rendered with no explicit `interview.comprehension` block
**When** the harness is rendered
**Then** `interview.comprehension.depth: standard` is written to `.claude/harness.yaml`
**And** the rendered `/hm:plan` command contains the design-brief instruction block and the
required-when-changed round-state block
**And** it does NOT contain the `decision_depth` or `teach_back` blocks

### S2: `deep` adds per-decision depth and closing readback
**Given** `interview.comprehension.depth: deep` in `harness.yaml`
**When** the harness is rendered
**Then** the rendered `/hm:plan` command contains all four blocks: brief, round_state,
decision_depth, teach_back
**And** the teach_back block instructs an output-only readback that requires no user response
and introduces no gate

### S3: `minimal` is a true opt-out — zero surface cost
**Given** `interview.comprehension.depth: minimal` in `harness.yaml`
**When** the harness is rendered
**Then** none of the four blocks appear in the rendered `/hm:plan` or `/hm:spec` commands
**And** the rendered character count of those two commands equals the pre-change count exactly

### S4: A harness.yaml written before this feature still works
**Given** a `harness.yaml` with an `interview` block containing only `deep_gate` and `main_loop`
(no `comprehension` key at all)
**When** the config is loaded and the harness is rendered
**Then** no exception is raised
**And** the effective depth is `standard`, i.e. the rendered output is identical to S1's
**And** this is an accepted retrofit, not a preservation bug: an existing install's `/hm:plan`
and `/hm:spec` grow on its next re-render, and that outcome is the decision — the user opts back
out with `depth: minimal`

### S5: An explicit depth survives a re-render
**Given** a `harness.yaml` carrying an explicit `interview.comprehension.depth`
**When** that file is read back through `interview.answers_from_harness_yaml` and re-rendered
**Then** the emitted `harness.yaml` carries the same depth value
**And** this holds for every value in `{minimal, standard, deep}`

### S6: `/hm:spec` receives the same disclosure blocks from the same source
**Given** any `depth` other than `minimal`
**When** the harness is rendered
**Then** the rendered `/hm:spec` command carries the **same enabled block set** as `/hm:plan`,
emitted by the **same** shared partial invoked with `stage='spec'`
**And** the brief's subject differs by stage — `/hm:plan` discloses its Step 1 internal design
draft, `/hm:spec` discloses the inherited SPEC scope, the AC skeleton, and which of the six
categories remain open — because `/hm:spec` has no architecture/phase draft to disclose
**And** at `standard` the `/hm:spec` round-state instruction appears exactly once: the partial
subsumes the existing §2.3 round preamble rather than adding a second one

## 🚫 Non-Goals

- **Not** changing `interview.deep_gate` — `eig_epsilon`, `confidence_tau`,
  `open_ended_cap_by_locale`, `common_ground` are out of scope in both value and semantics. The
  explicit rejected alternative is "ask more/harder questions"; it inverts 0.16.0's design.
- **Not** adding a mandatory gate. `teach_back` is output-only; no `gate-blocked` branch, no
  autopilot `auto_full` auto-answer, no loop-mode interaction beyond inheriting Step 1's existing
  loop-mode short-circuit.
- **Not** writing a new file. The brief is inline chat only — no
  `work-docs/PLAN-<slug>.draft.md`, no second writer against the single-source deliverable.
- **Not** applying to `/hm:research --deep`, `/hm:execute`, `/hm:review`, or any other stage.
  Scope is `/hm:plan` and `/hm:spec` only.
- **Not** per-level `minimal|standard|deep` override keys. One ordinal; no override layer.
- **Not** a `schema_version` bump — the key is purely additive and migrations in this repo key on
  key presence, not on the recorded version.
- **Not** preserving pre-feature behavior for existing installs. This was originally listed as a
  Non-Goal and it was **false**: `answers_from_harness_yaml` rebuilds the whole `interview` block
  from `_preset_extras`, so an existing `harness.yaml` with no `comprehension` key acquires
  `standard` on the next `/harness-maker:make --update` and its `/hm:plan` grows. That retrofit is
  now an accepted, explicit outcome (see S4). Only an *explicit* depth value is preserved (S5).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard (`toolchains.python.commands.test`) |
| Config surface | one key: `interview.comprehension.depth` | User decision Round 1 — ordinal beats 4 booleans on `/hm:configure` and surface cost |
| Schema typing | no pydantic model change | `HarnessConfig.interview` is `dict[str, Any]` (`models.py:1215`); defaults live beside `interview_deep_gate_defaults()` |
| Template structure | one shared Jinja partial included by `plan.md.j2` and `spec.md.j2` | Precedent: `agents/_partials/inequality_gate_block.md.j2` is included by plan/spec/research — single-source or the two stages drift |
| Template access pattern | `.get(...)` / `\| default(...)` on every read | An old `harness.yaml` has no `comprehension` key; a bare attribute access is the count:8 absent-case black hole |
| Surface ratchet | accepted via waiver + BASELINE-DELTA attribution row | User decision Round 2; follows the existing `test_plan_net_surface.py` xfail-waiver precedent. **Never** re-freeze `surface_baseline.json` to make the gate pass |
| Opt-out cost | exactly 0 characters at `depth: minimal` | The only mechanical evidence a third-party install pays nothing |
| Locale | brief/round_state/decision_depth/teach_back prose is emitted in `config.locale` at interview time; the rendered template stays English | Matches the existing live-interview vs document-on-disk split |
| Compatibility | `harness.yaml` files with `schema_version` 1–4 and no `comprehension` key | Absent-case must be a tested branch, not an inferred one |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (structural render) | `tests/structural/test_comprehension_render_gate.py::test_standard_renders_brief_and_round_state_only` |
| S2 | unit (structural render) | `tests/structural/test_comprehension_render_gate.py::test_deep_renders_all_four_blocks` |
| S3 | unit (structural render) | `tests/structural/test_comprehension_render_gate.py::test_minimal_renders_nothing_and_costs_zero_chars` |
| S4 | unit | `tests/unit/test_comprehension_absent_case.py::test_legacy_harness_yaml_without_comprehension_defaults_to_standard` |
| S5 | unit (property) | `tests/unit/test_comprehension_roundtrip.py::test_explicit_depth_survives_yaml_answers_yaml_roundtrip` |
| S6 | unit (structural render) | `tests/structural/test_comprehension_render_gate.py::test_spec_stage_carries_the_same_partial` |

### AC-001: standard renders brief and round_state only

The default level discloses the whole picture without paying for per-decision depth. Rendering a
config with `depth: standard` must put the brief block and the round-state block into the
`/hm:plan` command text and leave the other two out.

### AC-002: deep renders all four blocks, teach_back output-only

`depth: deep` renders brief + round_state + decision_depth + teach_back, and the teach_back prose
states it requires no user response and creates no gate.

### AC-003: minimal renders nothing and costs zero bytes

`depth: minimal` renders none of the four blocks, and the rendered `/hm:plan` and `/hm:spec`
bytes are **identical** to the pre-change render — compared by SHA-256, not by character count.

The oracle is an **immutable committed golden** (`tests/structural/comprehension_zero_cost_golden.json`)
captured **before** any template edit and never regenerated by this task. It must NOT be
`surface_baseline.json`: that file is regenerated at the new `standard` default later in this
work, after which it records standard-level numbers and the comparison would silently become
minimal-vs-standard. The golden records the two digests plus the source commit SHA, and the test
asserts that SHA is an ancestor of HEAD.

### AC-004: absent comprehension key defaults to standard without error

A `harness.yaml` whose `interview` block predates this feature loads and renders without raising,
and produces output identical to an explicit `depth: standard`.

### AC-005: explicit depth survives the yaml to answers to yaml round-trip

For every value in `{minimal, standard, deep}`, reading a rendered `harness.yaml` back through
`answers_from_harness_yaml` and re-emitting it preserves the value — a re-render never silently
resets a user's chosen depth.

### AC-006: the spec stage carries the same enabled block set from the same source

At any depth other than `minimal`, `/hm:spec` and `/hm:plan` render the **same set of enabled
blocks** from the **same** partial, invoked with different `stage` arguments. Identity is asserted
on the block set and on the partial's own source path — not on the rendered text, whose brief
subject and round-state anchor legitimately differ by stage.

## ❓ Open Questions

None. All seven of RESEARCH's open questions were resolved in the interview:

| RESEARCH open question | Resolution |
|---|---|
| Key placement / name | `interview.comprehension.depth`; no `schema_version` bump (migrations key on presence) |
| Default value | `standard` for new installs; existing files round-trip their explicit value |
| Granularity | single ordinal `minimal \| standard \| deep`, no per-level overrides |
| Scope of stages | `/hm:plan` + `/hm:spec` only |
| Surface budget | growth accepted via waiver + BASELINE-DELTA attribution row; `minimal` must cost 0 |
| Brief delivery | inline chat only, before Round 1 |
| `teach_back` gate | output-only, no user response, no gate — autopilot untouched |

## 🔍 Refinement Decisions

- **Round 1** — locked the config shape: single ordinal `depth`, applied to `/hm:plan` and
  `/hm:spec`, defaulting ON for new installs, brief delivered inline in chat only.
- **Round 2** — locked default `standard`; `teach_back` is output-only with no gate; primary
  oracle is render-output grep; the repo's own surface growth is accepted via waiver with a
  recorded rationale rather than by offsetting cuts elsewhere.
- **§2.5 inequality gate** — 1 of 4 candidates passed (key name, `schema_version`, and loop-mode
  short-circuit were all resolved by common ground). The passing candidate raised that
  render-grep alone proves "the block rendered", not "the feature reaches existing users"; the
  user added the absent-case and round-trip guards, which became AC-004 and AC-005.
