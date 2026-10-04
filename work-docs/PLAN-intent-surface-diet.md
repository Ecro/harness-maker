---
type: plan
task_slug: intent-surface-diet
status: complete
created: 2026-10-04
tags: [harness-maker, plan, jinja2, intent-layer, rendered-surface]
spec: "[[SPEC-intent-surface-diet]]"
research_doc: "[[RESEARCH-intent-layer-diet]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "Cut intent-layer stage prose: drop Feedback collection, spec 4.9 and revisit check; compress 5.7, 3.3 and the reference"
spec_need_verdict: add
spec_need_target: intent-surface-diet
---

# PLAN — intent-surface-diet

## 🎯 Executive Summary

Shrink the intent layer's rendered stage prose without a toggle (SPEC rounds 1–4):

- Remove the `feedback-entry` / `feedback-close` partial blocks from all six stages, and
  execute's PLAN Feedback instruction.
- Remove spec Step 4.9 (intent draft), the draft-consent question, and the
  `rejected[]`/`revisits` check in 0.5.
- Compress wrapup 5.7. It must derive question candidates from task evidence, keep every
  guard phrase, and create the PLAN `## Feedback` table when absent.
- Compress review 3.3, keeping its contract.
- Rewrite the intent-layer SKILL lines and `references/workflow-feedback.md`.
- Re-freeze the structural ratchets in a terminal retire phase with BASELINE-DELTA
  attribution.

## 📚 Prior Work

- RESEARCH-intent-layer-diet §Approach C (byte measurements, usage census).
- `tests/unit/test_render_intent_feedback_batch.py` (SPEC-intent-layer-improvements) already
  pins 5.7's guard phrases with deletion controls. Its 5.7 tests are kept as the AC-003 guard
  oracle. Its feedback-block and 4.9 tests encode behaviour this SPEC removes, so they are
  retired.
- `[fail:test] assertion-invariant-over-named-dimension`: every new AC test pairs with a
  deletion or mutation control.
- `ratchet-rebaselined-by-its-own-subject` (ADR-010 convention): baselines are re-frozen only
  by the terminal retire phase, with row-per-key attribution.

## 📐 Architecture Decision Records

### ADR-001: Keep the 5.7 guard phrases verbatim and compress around them
**Decided by:** agent
The existing deletion-controlled tests pin the exact phrases of 5.7's safety rules. Keeping
those phrases means the pre-existing tests stay the differential guard oracle (AC-003). The
compression removes connective prose, not rules.

### ADR-002: Keep headings except the removed Step 4.9
**Decided by:** agent
The step-sensitivity registry keys on headings. Keeping every surviving heading (0.5, 3.3, 5.7)
limits registry churn to removing the 4.9 entries.

### ADR-003: Goldens per arm (preset × host), captured before the first template edit
**Decided by:** agent
`tests/fixtures/intent_surface_diet/goldens.json` holds, per arm:
- the 5.7 verb set and guard phrases;
- the 3.3 contract tokens and bytes;
- the Understanding/decided_by extracts and their count;
- the total stage+reference bytes and the intent-block bytes.

It is written by a capture helper in the AC test module from the unmodified templates and is
never regenerated.

### ADR-004: The reference shrinks with the stages
**Decided by:** agent
5.7 tells the agent to follow `references/workflow-feedback.md`, so AC-006 counts that file.
The reference is rewritten to describe the single wrapup moment, keeping the record map and the
disposition table.

## 🏗️ Technical Design

| Template | Change |
|---|---|
| `agents/_partials/step_manifest.md.j2` | delete the `@hm:feedback-entry` block |
| `agents/_partials/stage_end_summary.md.j2` | delete the `@hm:feedback-close` block (both arms) |
| `stages/execute.md.j2` | delete the 3-line Feedback-section instruction |
| `stages/spec.md.j2` | 0.5 keeps status read + link question + none + frontmatter; drop draft consent, rejected[]/revisits (and its second `!` status line); drop Step 4.9; frontmatter comment no longer mentions 4.9 |
| `stages/review.md.j2` | compress 3.3 to ≤60% bytes keeping contract tokens |
| `stages/wrapup.md.j2` | compress 5.7; add the evidence-derived source and absent-table creation |
| `skills/intent-layer/SKILL.md.j2` | lines 10 and 23: 5.7 is the single moment; no stage collection |
| `skills/intent-layer/references/workflow-feedback.md.j2` | rewrite to the single-moment model |
| `step_sensitivity.py` | remove the spec Step 4.9 entries |

## 📝 Implementation Plan

### Phase 1 — Goldens (before any template edit)
- depends_on: none · parallel_group: serial · merge_hazards: none
- scope in: `tests/fixtures/intent_surface_diet/goldens.json`, capture helper in `tests/unit/test_intent_surface_diet.py`
- exit criterion: goldens.json exists with non-empty values for all four arms while `git diff --stat -- src` is empty
- risk: low · rollback: delete the fixture

### Phase 2 — AC tests (RED)
- depends_on: Phase 1 · parallel_group: serial · merge_hazards: none
- scope in: `tests/unit/test_intent_surface_diet.py`
- exit criterion: `uv run pytest tests/unit/test_intent_surface_diet.py` → AC-001/002/005/006/008/009 red for the missing change; AC-003/004 green by design (preservation oracles, justified)
- risk: low · rollback: delete the file

> **Phase 2 A.5 history:** round 1 FAIL (3 issues, repaired) → round 2 FAIL (S3 conditions presence-only) → `stuck` → DRI chose Path B + a third round → positional gate checks added (goldens untouched) → round 3 FAIL (Codex consent exclusivity) → fixed (`consent_ok`) without a fourth round; that property is also pinned by the kept `test_record_batch_controls_codex`. Final A.4: 48 failed, 15 passed (4 AC-004 preservation + 1 gate-preservation + 10 controls).

### Phase 3 — Template edits
- depends_on: Phase 2 · parallel_group: serial · merge_hazards: snapshot/ratchet files (left to Phase 4)
- scope in: the templates in the table above; `tests/unit/test_render_intent_feedback_batch.py` (retire feedback-block and 4.9 tests only)
- exit criterion: `uv run pytest tests/unit/test_intent_surface_diet.py tests/unit/test_render_intent_feedback_batch.py tests/unit/test_render_intent_layer.py tests/unit/test_render_wrapup_delegation.py tests/unit/test_codex_stage_procedures.py` green
- risk: medium · rollback: `git checkout -- src/harness_maker/templates`

### Phase 4 — Retire: re-freeze ratchets with attribution
- depends_on: Phase 3 · parallel_group: serial · merge_hazards: shared baselines
- scope in: `src/harness_maker/step_sensitivity.py`, `tests/structural/surface_baseline.json`, `tests/structural/instruction_baseline.json` / `_ALLOWED_REMOVALS`, `tests/structural/test_roundtrip_budget.py` counts, `tests/structural/test_command_size_budget.py` ceilings, `tests/structural/autopilot_gate_golden.json`, `tests/structural/comprehension_zero_cost_golden.json`, `tests/snapshot/*.expected.yaml` (regenerate.py), `work-docs/BASELINE-DELTA-intent-surface-diet.md`; other render tests that pin removed prose
- exit criterion: `uv run pytest tests/structural tests/unit/test_synthesize_snapshot.py` green, then full suite green; ruff + `mypy --strict src tests`
- risk: medium · rollback: `git checkout --` the baseline files

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/world.py` — no Python behaviour change (SPEC Non-Goal)
- `src/harness_maker/intent_cli.py` — no Python behaviour change
- `src/harness_maker/world_model_digest.py` — Maker digest contract
- `src/harness_maker/templates/skills/world-model/` — Maker skill and its size cap
- `src/harness_maker/templates/agents/_partials/world_model_pointer.md.j2` — always-loaded pointer
- `src/harness_maker/templates/agents/_partials/project_knowledge_pointer.md.j2` — always-loaded pointer
- `tests/fixtures/intent_surface_diet/goldens.json` — pre-change oracle, never regenerated after Phase 1
- Advisory: the wrapup Understanding block and execute `Decided by` instructions stay byte-identical (AC-004)

## 📊 Phase Status

| Phase | Status | Evidence |
|---|---|---|
| 1 Goldens | done, re-captured once | First capture held raw install-ref paths (env-dependent bytes). Re-captured with path normalisation from the **HEAD** templates in a temporary detached worktree, still pre-change. Reported as a crossing below. |
| 2 AC tests | done | A.5: round 1 FAIL → round 2 FAIL → `stuck` → DRI Path B + round 3 FAIL → `consent_ok` fix, no round 4 (history above) |
| 3 Template edits | done | AC tests + kept batch/render tests 224 passed; retired tests that encoded removed behaviour (feedback blocks, Step 4.9 id derivation/draft, rejected[]/revisit, execute Feedback-section) |
| 4 Retire | done | registry 4.9 entry removed (unsourced 33→32, CLAUDE.md updated); roundtrip spec 12→10; surface baseline + snapshots + autopilot gate golden re-frozen; BASELINE-DELTA-intent-surface-diet.md; wrapup line pin 829/831→817/819; `test_intent_file_inputs` dropped the spec surface; intent-layer-diet's one-shot snapshot-pin guard retired; docs (HOW-IT-WORKS en/ko, TECH_SPEC) updated |
| Final | green | ruff, `mypy --strict src tests` clean; full pytest 9863 passed, 0 failed (rc=0 read from the output file) |

AC-006 measured savings per arm: 9126 / 9132 bytes = 0.66–0.67 × the pre-change intent-block
bytes (target ≥ 0.5).

Boundary comparison (Step 4): 34 changed paths (27 tracked modified/deleted, 6 untracked new
plus the fixture dir). **Crossing:** `tests/fixtures/intent_surface_diet/goldens.json` (entry
"pre-change oracle, never regenerated after Phase 1"). It was re-captured once, after Phase 2
review, to normalise the environment-dependent install path. The re-capture ran against the
unmodified HEAD templates, so the oracle is still pre-change, but the letter of the entry was
crossed. No other `Do not change` entry is touched. Beyond the phase scopes, these also changed:
`CLAUDE.md` (registry count), `TECH_SPEC.md`, `docs/HOW-IT-WORKS*.md`,
`tests/unit/test_intent_layer_diet.py`, `tests/unit/test_intent_file_inputs.py`.

## 🧪 Testing Strategy

- `tests/unit/test_intent_surface_diet.py`: AC-001…AC-009 over four arms (Production/Side × Claude/Codex), each with a deletion or mutation control.
- `tests/unit/test_render_intent_feedback_batch.py`: kept 5.7 guard/verdict/close tests (differential oracle for AC-003).
- Structural ratchets and snapshots re-frozen in Phase 4 only.
- Full suite once at the end (background, ~12 min); `mypy --strict src tests`.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Compression drops a 5.7 safety rule | medium | high | Existing deletion-controlled clause tests + AC-003 guard golden |
| Codex arm diverges from Claude | medium | medium | Every AC runs on all four arms |
| A render test elsewhere pins removed prose | high | low | Phase 4 sweep; update only tests that encode removed behaviour |
| Ratchet re-frozen without attribution | low | medium | `test_baseline_delta_attribution` + BASELINE-DELTA doc |
| mypy on tests skipped locally | medium | low | Run `mypy --strict src tests` (CI parity; failures.md count 5) |

## ✅ Success Criteria

- [x] AC-001 no Feedback collection blocks in any stage render
- [x] AC-002 spec link step only
- [x] AC-003 5.7 verbs, guards, consent per target, absent-table creation, pending compatibility
- [x] AC-004 Understanding/decided_by byte-identical
- [x] AC-005 3.3 contract kept at ≤60% bytes
- [x] AC-006 whole-render shrink ≥ 50% of intent-block bytes per arm
- [x] AC-007 ratchets attributed; full suite green
- [x] AC-008 5.7 derives from task evidence
- [x] AC-009 skill/reference no per-stage collection

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
