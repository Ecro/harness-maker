---
type: spec
task_slug: intent-surface-diet
status: approved
created: 2026-10-04
tags: [harness-maker, spec, jinja2, intent-layer, rendered-surface, context-budget]
test_framework: pytest
tier: 2
interview_rounds: 4
research_doc: "[[RESEARCH-intent-layer-diet]]"
summary: "Shrink the intent layer's rendered stage prose by at least half, without a toggle"
---

# SPEC — intent-surface-diet

## 🎯 Intent

Every rendered harness carries the intent layer's stage prose: about 14.6 KB per full
research→wrapup pipeline, doubled in the Codex stage skills. It is paid even by projects whose
`.claude/intent.yaml` is empty (3 of 6 local consumers). The usage census
(RESEARCH-intent-layer-diet, Approach C; question `q_intent_layer_unfired_paths`) showed
little return for it. About 59 per-stage Feedback rows were written, mostly about the
now-deleted trial; revisit checks never fired; review Step 3.3 found 2 real P2s in 12
reviews. This change shrinks that prose in every harness. It adds no configuration toggle, in
line with the project's first goal of simple over configurable.

## 🌅 Outcomes

- The rendered stage commands plus the intent-layer reference they point to shrink, per target
  (Claude and Codex separately), by at least half of the pre-change intent-block bytes.
- No stage collects Feedback rows before wrapup any more. Wrapup Step 5.7 derives question
  candidates itself from the task's evidence. 5.7 still writes its own disposition rows (the
  verdict and record marks) so re-runs stay idempotent.
- Intents are created only through Maker / the intent-layer skill; `/hm:spec` only links an
  existing intent.
- What still works unchanged: measurement, the manual-metric verdict (with its re-run safety),
  intent close, the review drift check and its output contract, and the wrapup Understanding
  block.

## 📋 In-Scope Scenarios

### S1: No stage carries a Feedback collection block
**Given** any preset/targets render
**When** all six stage renders are read (Claude commands and Codex `hm-*` skills, wrapup included)
**Then** none contains the `@hm:feedback-entry` or `@hm:feedback-close` block
**And** execute no longer instructs adding a `## Feedback` section to the PLAN

### S2: Spec only links an existing intent
**Given** a spec render
**When** Step 0.5 is read
**Then** it asks which intent to link only when `active`/`proposed` intents exist, keeps the "none" option and the `intent:` frontmatter write, and otherwise prints a one-line skip
**And** the render contains no Step 4.9 intent draft, no "Draft an intent for this task?" consent question, no `rejected[]` comparison and no `revisits` check

### S3: Wrapup 5.7 proposes from evidence, conditionally, with its safety rules
**Given** a wrapup render
**When** Step 5.7 is read
**Then** it tells the agent to derive question candidates from this task's PLAN, SPEC, REVIEW and diff, and still offers any `pending` Feedback rows already present (written before this change)
**And** the measure-all item appears only when a metric has `measure: true`; the verdict item appears only when the PLAN's intent is bound to a `measure: false` metric and is skipped when this task already has a recorded verdict row; an empty list asks nothing
**And** recorded/declined rows are skipped, a failed row is re-offered once, the withdrawal notice is kept, and the close question is asked only when the PLAN links an intent
**And** before writing a mark, 5.7 creates the PLAN's `## Feedback` table when it is absent
**And** consent is one batch: `AskUserQuestion` `multiSelect` on Claude/Cursor, and a numbered single reply on Codex

### S4: The Understanding block is untouched
**Given** the wrapup and execute renders before and after this change
**When** the Understanding-block instructions and the ADR `decided_by` instruction are extracted (non-empty, a fixed count per render)
**Then** they are byte-identical

### S5: Review 3.3 is shorter and keeps its contract
**Given** a review render
**When** Step 3.3 is read
**Then** it still runs only when the PLAN carries `intent:` (or legacy `objective:`, rejecting conflicts), still validates the id against `[A-Z0-9-]+` and skips the command on mismatch, still calls `hm intent show`, and still adds findings at P2, `source: "main-loop"`, category `scope_drift`, with the id as message prefix, before Step 3.4 stamps ids, with no halt
**And** its bytes are at most 60% of the pre-change Step 3.3

### S6: The intent-layer skill stops prescribing per-stage collection
**Given** the intent-layer `SKILL.md` and `references/workflow-feedback.md` renders (Claude and `.agents` copies)
**When** they are read
**Then** neither instructs stages to collect pending rows ("stages only collect", "in every stage", "where it was observed")
**And** they describe wrapup 5.7 as the one place observations are proposed, while existing ids, history and approvals are preserved

### S7: Budgets move only with attribution
**Given** the structural ratchets (surface baseline, roundtrip budget, instruction baseline, command size budget, snapshot pins, step-sensitivity registry)
**When** the change lands
**Then** each moved value is re-pinned with a BASELINE-DELTA attribution row, the registry drops entries for deleted headings, and the full suite passes

## 🚫 Non-Goals

- A `harness.yaml` toggle or any render condition that reads user state (rejected in round 1:
  it adds a config axis, and reading `intent.yaml` at render time breaks render determinism
  and leaves a fresh intent invisible until the next re-render).
- Any Python behaviour change in `hm intent`, `world.py`, the Maker digest or the autopilot gate.
- The always-loaded pointers (`## World model`, `## Project knowledge`, Maker description).
- The wrapup Understanding block and ADR `decided_by` (UNDERSTANDING-HANDOFF measurement window).
- Removing review Step 3.3 (kept, compressed — round 2).
- Approach B (questions/assumptions/revisit machinery in Python).
- Releasing a version.
- **Accepted trade-off (round 4):** an observation made mid-task that never reaches the
  PLAN/SPEC/REVIEW/diff, for example lost to context compaction or an interrupted task, is no
  longer captured before wrapup. This is not listed as irreversible because no stored data is
  migrated or destroyed and re-rendering restores the old prose. Pending rows already written
  before this change are still offered (S3).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard |
| Render determinism | No shell-out or user-state read during render | intent.yaml rule; snapshot determinism |
| Targets | Claude commands, Codex `hm-*` skills and `.agents` skill copies change together; Cursor reads the Claude render; every check runs per target | Single-source rendering rule |
| Locale | Prose changes apply to every locale variant the templates carry | Rendered for en/ko |
| Oracle discipline | Pre-change extracts (verb set, 5.7 guard phrases, 3.3 contract tokens, Understanding text, byte counts) are captured before the first template edit, asserted non-empty, and never regenerated | Avoids circular oracles |
| Size | Maker SKILL ≤ 4,500 chars and pointer caps unchanged | Maker invariants |

## 🔒 Irreversible Decisions

none

## ✅ Acceptance Criteria

### AC-001: No stage renders a Feedback collection block
Covers S1.

### AC-002: Spec renders only the intent link step
Covers S2.

### AC-003: Wrapup 5.7 keeps its verbs, guards and target-specific consent
Covers S3 (conditions, safety rules, consent mode, absent-table creation, pending compatibility).

### AC-004: Understanding and decided_by instructions are byte-identical
Covers S4.

### AC-005: Review 3.3 keeps its contract at no more than 60 percent of its bytes
Covers S5.

### AC-006: Whole-render shrink per target covers at least half of the intent-block bytes
Covers the Outcomes size claim. Measured as, per target, the pre-change total bytes of the six
stage renders plus the intent-layer reference minus the post-change total. The result must be
at least 0.5 × the pre-change sum of the named intent blocks for that target, so text moved
out of a block into another rendered file does not count.

### AC-007: Moved budgets carry attribution and the suite is green
Covers S7.

### AC-008: Wrapup 5.7 derives question candidates from task evidence
Covers S3's replacement source. The pre-change 5.7 fails it.

### AC-009: The intent-layer skill no longer prescribes per-stage collection
Covers S6.

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac001_no_feedback_blocks` |
| S2 | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac002_spec_link_only` |
| S3 | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac003_wrapup_57_guards_and_consent`, `::test_ac008_57_derives_from_evidence` |
| S4 | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac004_understanding_byte_identical` |
| S5 | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac005_review_33_contract_and_size` |
| S6 | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac009_skill_no_stage_collection` |
| Outcomes | unit (render) | `tests/unit/test_intent_surface_diet.py::test_ac006_whole_render_shrink_per_target` |
| S7 | structural + full suite | `tests/structural/*` green with BASELINE-DELTA rows; full `pytest` |

Goldens live under `tests/fixtures/intent_surface_diet/` and are captured from the pre-change
render.

## ❓ Open Questions

None. The exact compression wording of 5.7/3.3 belongs to `/hm:execute` Step 0, within the
ACs. AC-008's pinned phrase is "from this task's PLAN, SPEC, REVIEW and diff".

## 🔎 Spec Validation

spec-validator (pass 1, run `spec-intent-surface-diet-20261004`): **MAJOR_REVISION** →
amended in round 4. codex: invoked, 11 findings.

| Finding | Source | Disposition |
|---|---|---|
| The evidence-derived proposal had no AC; removing collection alone passed every AC | validator critical (+ codex P1) | Accepted → AC-008 |
| AC-003 checked verbs, not conditions or idempotency; S3 was unconditional | validator critical + codex P1×2 | Accepted → S3 conditional, AC-003 guard golden |
| AC-006 extractor could be gamed by moving text; aggregate hid a Codex miss | validator + codex P1 | Accepted → whole-render per-target measure |
| intent-layer SKILL/reference still prescribe per-stage collection | validator + codex P1 | Accepted → S6, AC-009 |
| AC-001 excluded wrapup, though wrapup renders feedback-entry; Outcome 2 contradicted 5.7's own row writes | validator + codex P1 | Accepted → AC-001 covers wrapup; Outcome 2 reworded |
| 5.7's verdict mark lost its table when the execute/entry instructions go | validator | Accepted → 5.7 creates the table when absent |
| AC-003's multiSelect clause is false on Codex | validator + codex P1 | Accepted → target-specific consent mode |
| AC-005 kept three strings but not the drift output contract | validator + codex P1 | Accepted → 3.3 contract golden |
| AC-002 missed the `rejected[]` comparison | validator + codex P2 | Accepted |
| AC-004 could pass vacuously on empty extracts | validator + codex P2 | Accepted → non-empty, fixed count |
| Hidden data-loss decision should be in `irreversible_decisions` | codex P1 | Rejected (outside the five categories); recorded as an accepted trade-off in Non-Goals |
| AC-007 is circular | codex P1 | Rejected: `test_baseline_delta_attribution` already enforces per-key attribution |

## 🔍 Refinement Decisions

- Round 1: intent link = none; approach = shrink prose only, no toggle.
- Round 2: remove per-stage Feedback collection; remove spec 4.9 intent draft and its consent
  question; remove the 0.5 revisit check; compress wrapup 5.7; keep review 3.3 compressed; no
  intent draft for this task.
- Round 3: AC/oracle table accepted with a 50% size target; a compatibility line for
  pre-existing `pending` rows added (absent-case); `irreversible_decisions: []`. The DRI
  approved the SPEC.
- Round 4 (after spec-validator MAJOR_REVISION + codex): all eight amendments applied
  (AC-008 evidence source, AC-003 guards and consent per target, Outcome 2 split plus
  absent-table creation, AC-001 wrapup coverage, AC-009 skill/reference, AC-006 whole-render
  per-target measure, AC-005 contract, AC-002/AC-004 tightening). The DRI re-approved.

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
