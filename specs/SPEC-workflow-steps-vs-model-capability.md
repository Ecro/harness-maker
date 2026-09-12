---
type: spec
task_slug: workflow-steps-vs-model-capability
status: approved
created: 2026-09-12
tags: [harness-maker, spec, python, jinja2, workflow-design, model-capability, structural-tests]
test_framework: pytest
tier: 2
research_doc: "[[RESEARCH-workflow-steps-vs-model-capability]]"
summary: "Step-sensitivity registry (COMP/HOST/INV/TUNE) enforced by structural tests, plus two COMP prose deletions"
---

# SPEC — Workflow step sensitivity registry

## 🎯 Intent

Frontier models (GPT-6 Astra, Fable 5.1) and the vendor harnesses around them keep absorbing
work this pipeline once had to prompt for. Today the only defense against "the new model
doesn't need X" is a prose argument, and the two times that argument was tested by measurement
it lost (plan-validator 22% verdict change; test-reviewer A.5 75% FAIL, Side-preset only, n=52).
This task turns the RESEARCH's per-step classification into a machine-checked registry so
every future removal is argued against a recorded class and evidence grade, and so the next
model release has a code-level answer to "what must be re-measured".

## 🌅 Outcomes

- A maintainer can look up any rendered `/hm:` step and read its sensitivity class, evidence
  grade, source, and (for TUNE) the re-measurement trigger, from one Python registry.
- Adding a new Step/Phase/Check heading to any stage template without classifying it fails
  the structural test suite.
- The Side preset's knob defaults are provably consistent with the registry: no knob that
  the registry marks COMP or TUNE is *more* aggressive on Side than on Production.
- Two COMP prose blocks are gone from the rendered surface (Phase 0.5 5-term ceremony in
  research/spec/plan; verify Check 1), with the surface baseline re-frozen and attributed.
- `MATRIX-native-redundancy.md` and CLAUDE.md state the four classes and the Side-only
  evidence caveat.

## 📋 In-Scope Scenarios

### S1: registry covers every rendered step heading
**Given** both presets rendered for both dev_modes (the `ARMS` matrix; targets do not change the command render)
**When** the structural test collects every `Step` / `Phase` / `Check` heading (levels 2–5) in the seven stage commands
**Then** each heading maps to exactly one registry entry with a class in {COMP, HOST, INV, TUNE}
**And** an entry with class TUNE carries a non-empty `remeasure_on` and `measure_cmd`
**And** an entry for a heading gated on a toggle axis outside `ARMS` carries `renders_when` (coverage of those headings is a named follow-up)

### S2: unclassified heading fails
**Given** a stage template gains a new `### Step 9 — Foo` heading
**When** the structural suite runs
**Then** the coverage test fails naming the stage and heading

### S3: Side defaults do not contradict the registry
**Given** the registry names the knob(s) each COMP/TUNE entry is governed by
**When** the Side and Production harness.yaml templates are rendered
**Then** for every such knob, Side's value is equal to or less aggressive than Production's under the registry's declared ordering

### S4: 5-term ceremony removed, open-ended cap retained
**Given** research/spec/plan rendered on both presets
**When** the rendered text is scanned
**Then** it contains no "5-Term Inequality Gate" section or per-candidate checklist line
**And** it still states the locale open-ended cap

### S5: verify Check 1 removed
**Given** verify rendered on both presets and both dev_modes
**When** the rendered text is scanned
**Then** no LLM "PLAN/SPEC satisfaction" check remains in the stop-on-first-FAIL chain
**And** the deterministic checks (regression, structural, security, worktree, SPEC requirement) all remain

### S6: surface baseline re-frozen and attributed
**Given** S4 and S5 landed
**When** the live render is measured against the frozen `tests/structural/surface_baseline.json`
**Then** the delta is negative and a `BASELINE-DELTA-workflow-steps-vs-model-capability.md` attributes it
**And** `test_baseline_delta_attribution` passes
**And** both baselines are re-frozen only after squash-land, from the base checkout at a `main` SHA (`assert_sha_is_durable` refuses task-branch commits)

### S7: documentation carries the classes
**Given** the registry exists
**When** `work-docs/MATRIX-native-redundancy.md` and `CLAUDE.md` are read
**Then** the matrix has a sensitivity-class column and CLAUDE.md has a section naming the four classes and the "Side-preset only, n=" caveat

## 🚫 Non-Goals

- Changing `second_opinion.models` defaults (user decision R1: keep `[]` on both presets).
- Running harness-bench on Fable 5.1 / GPT-6 Astra (separate task; registry only records the trigger + command).
- Pruning COMP steps from the Side render (render output is unchanged; snapshots untouched).
- Deleting execute C.0 / D.5 prose (coupled to mutation receipts).
- Any Production knob default change.
- A third preset.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard; structural suite already lives in `tests/structural/` |
| Render output | unchanged except S4/S5 deletions | Cursor/Codex parity; no snapshot regen beyond the two deletions |
| Evidence provenance | every TUNE grade cites ledger + `Side-preset only, n=` | Production stage-agent rows are 0 (user decision R1) |
| Surface ratchet | negative delta only, attributed; no in-task re-freeze | `test_baseline_delta_attribution`; `assert_sha_is_durable` hard-refuses non-`main` SHAs |
| Config schema | no new `harness.yaml` key | registry is Python-side; Side derivation is a test, not a renderer branch |
| Type/lint | `mypy --strict`, `ruff` clean | CI quality-gate |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `tests/structural/test_step_sensitivity_registry.py::test_every_rendered_heading_is_classified` |
| S2 | unit | `tests/structural/test_step_sensitivity_registry.py::test_unclassified_heading_fails` |
| S3 | unit | `tests/structural/test_step_sensitivity_registry.py::test_side_defaults_consistent_with_registry` |
| S4 | unit | `tests/unit/test_render_inequality_gate_removed.py::test_five_term_ceremony_absent_cap_retained` |
| S5 | unit | `tests/unit/test_render_verify_check1_removed.py::test_verify_has_no_llm_satisfaction_check` |
| S6 | unit | `tests/structural/test_baseline_delta_attribution.py::test_the_delta_document_exists` (existing) |
| S7 | unit | `tests/structural/test_step_sensitivity_registry.py::test_docs_carry_classes` |

### AC-001: every rendered step heading is classified
Rendered Step/Phase/Check headings across presets × targets are a subset of registry keys; TUNE entries carry `remeasure_on` and `measure_cmd`.

### AC-002: an unclassified heading fails the structural suite
Injecting a heading absent from the registry makes the coverage test fail with stage + heading in the message.

### AC-003: Side defaults are consistent with the registry
For each registry entry naming a knob, Side's rendered value ≤ Production's under the entry's declared ordering.

### AC-004: five-term ceremony absent, open-ended cap retained
Rendered research/spec/plan contain no 5-term gate section; the locale cap sentence remains.

### AC-005: verify has no LLM satisfaction check
Rendered verify contains no Check 1 LLM satisfaction step; deterministic checks remain.

### AC-006: surface baseline re-frozen with attributed negative delta
Measured delta < 0 and a BASELINE-DELTA doc attributes it in-task; the re-freeze itself happens post-land on base.

### AC-007: docs carry the classes
Matrix has the class column; CLAUDE.md names the four classes and the Side-only caveat.

## ❓ Open Questions

(none — all resolved in interview; `/hm:plan` decides the registry's data shape, the heading-extraction mechanism, and how the Side-vs-Production ordering is declared per knob)

## 🔍 Refinement Decisions

- R1: scope = docs + schema (registry + structural test), not docs-only and not bench measurement; COMP deletions included (1–2); `second_opinion.models` stays `[]`; TUNE evidence Side-only with explicit tag.
- R2: deletions = Phase 0.5 5-term ceremony (cap retained) + verify Check 1; enforcement = registry + structural test, no Side render pruning; TUNE entries carry `remeasure_on` + `measure_cmd` fields only (no automation).
