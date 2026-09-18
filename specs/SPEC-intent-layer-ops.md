---
type: spec
task_slug: intent-layer-ops
status: approved
created: 2026-09-18
tags: [harness-maker, spec, python, intent-layer, outcomes, withdrawal, evidence]
tier: 2
test_framework: pytest
summary: "Measured evidence names its definition by hash, not argv; `hm world gap` measures the layer's own withdrawal criterion"
---

# SPEC — Intent layer operations: short evidence, a withdrawal criterion someone counts

## 🎯 Intent

Two defects in how the intent layer runs day to day, found by reading the dogfood world on
2026-09-18. `outcomes.yaml` rows written by `hm world outcome measure` copy the full measure
command into `evidence` on every measurement — the dogfood commands are 300–700 characters of
inline Python, so the file grows by that much per row while the command is already bound by the
row's `definition_hash` and recoverable from `intent.yaml` at the recorded commit. And the
layer's own withdrawal criterion ("after 10 wrapups with no `observed:` and no `candidate`
revisit, remove the layer") exists only as a skeleton comment: nothing counts wrapups, so the
instrument that was meant to retire an unused layer can never fire.

## 🌅 Outcomes

- A measured row's `evidence` has constant length regardless of the command, and still
  identifies exactly which definition produced the number.
- `hm world gap --json` reports whether the withdrawal criterion is met, with the three counts
  it is made of and the date the clock started — or, when a count cannot be taken, `null` and
  the reason, never a `0` that reads as "unused".
- `/hm:wrapup` Step 5.7 prints one line when the criterion is met, so the operator sees it at
  the moment the layer is used.

## 📋 In-Scope Scenarios

### S1: measured evidence references the definition, not the command
**Given** an outcome whose `measure.cmd` is any command that exits 0 and prints a number
**When** the operator runs `hm world outcome measure <id>`
**Then** the appended row's `evidence` is `auto: measure#<first 12 hex of the row's definition_hash> @ <short sha> exit=0 cwd=<base|checkout>`
**And** no argv token longer than 3 characters appears in `evidence` (the command is not copied)
**And** `hm world outcome record` (manual) keeps the operator's evidence text verbatim, and rows
already in `outcomes.yaml` that the tool wrote are left byte-identical (hand-written formatting is
normalised by every append today — unchanged behaviour).

### S2: gap reports the withdrawal criterion
**Given** a checkout whose `.claude/intent.yaml` was committed as the skeleton, then committed
filled in at time T, and a base-root `.claude/observability/stage-spans.jsonl` holding
`hm:wrapup` `start` events both before and after T (and `end` events, which are not counted)
**When** the operator runs `hm world gap --json`
**Then** the payload carries `withdrawal` with exactly `filled_at` (T, UTC `Z`),
`wrapups_since_fill` (the `hm:wrapup` `start` events strictly after T; a timezone-less `ts` is
skipped), `objectives_observed`
(objectives whose `observed` is set), `revisit_candidates_now` (the count in `fired_revisits`),
`due` and `reason: "ok"`
**And** `hm world status --json` is unchanged — it carries no `withdrawal` key.

### S3: due is the criterion, exactly
**Given** a `withdrawal` block with counts `(wrapups, observed, candidates)`
**When** `due` is computed
**Then** `due` is true iff `wrapups >= 10` and `observed == 0` and `candidates == 0`, and false
whenever `wrapups` is `null`.

### S4: a count that cannot be taken is null with its reason
**Given** one of: `intent.yaml` still `not_filled_in`; no usable git (binary missing, the
checkout is not a repository, or a shallow clone); `intent.yaml` filled in the working tree but in
no commit; no regular `stage-spans.jsonl` at the base root (absent, a directory, unreadable); a
ledger with no `hm:wrapup` event at all (wrapup spans are not instrumented in this setup)
**When** the operator runs `hm world gap --json`
**Then** the command exits 0, the fields that could not be measured are `null`, `due` is false
and `reason` is `not_filled_in` | `no_git` | `fill_uncommitted` | `no_stage_spans` |
`no_wrapup_spans` (first applicable, in that order)
**And** a history commit that deleted `intent.yaml` is skipped, never reported as `no_git`.
**And** an invalid `intent.yaml` still returns the existing `state: invalid` payload with no
`withdrawal` key.

### S5: wrapup surfaces it once
**Given** a rendered harness with the intent layer in use
**When** `/hm:wrapup` reaches Step 5.7
**Then** it prints exactly one `[intent] withdrawal criterion met …` line when the `gap` output's
`withdrawal.due` is true, and nothing when it is false
**And** the `intent.yaml` skeleton comment names `hm world gap` / `withdrawal.due` as where the
criterion is reported.

### S6: surface accounting
**Given** the committed command-surface baseline
**When** the change lands
**Then** plan/review/help renders are byte-identical to the pre-change pin on every arm, wrapup
grows by no more than the declared allowance while in flight, and the allowance is retired
before land.

## 🚫 Non-Goals

- A verb that creates assumptions, or any change to `assumptions.yaml` handling.
- Enforcing or hashing the INTENT body — SPEC-playbook-alignment keeps it human-owned.
- Rewriting existing `outcomes.yaml` rows to the new evidence format.
- Logging revisit evaluations to reconstruct "ever candidate" — the criterion uses the current
  `fired_revisits`, because a revisit that is not logged cannot be counted after the fact.
- Acting on `due` automatically (removing the layer, disabling verbs). The operator decides.
- Editing the dogfood `.claude/intent.yaml` — it is human-written.
- Any change to the `hm world status` payload.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` (+ Hypothesis for S1) | repo standard; `tests/unit/world_fixture.py` exists |
| Status payload | byte-for-byte unchanged | SPEC-objective-gap-proposal pins it; plan Step 0.5 reads it |
| Git | `subprocess.run` with `shell=False`, timeout, `FileNotFoundError`/`TimeoutExpired`/`PermissionError` → `no_git` | CLAUDE.md external-command rule; `checkout_root` precedent |
| Roots | `intent.yaml` history read at the checkout root; `stage-spans.jsonl` at `resolve_base_root` | two-root rule — observability lives at the base |
| Threshold | 10 wrapups, a module constant | the SPEC-intent-world-model criterion, unchanged |
| Evidence | `measure#` + 12 hex of the row's own `definition_hash` | the hash already binds cmd/select/cwd/timeout; 12 hex is unambiguous at this row count |
| Compatibility | `outcomes.yaml` row schema unchanged; old rows load and compare as today | append-only history |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | property | `test_ac_001_measured_evidence_references_the_definition_not_the_command` |
| S2 | unit | `test_ac_002_gap_reports_the_withdrawal_block` |
| S3 | unit (parametric) | `test_ac_003_due_is_the_criterion_exactly` |
| S4 | unit (parametric) | `test_ac_004_unmeasurable_counts_are_null_with_reason` |
| S5 | unit (render) | `test_ac_005_wrapup_prints_withdrawal_line_when_due` |
| S6 | structural | `test_ac_006_surface_pinned_and_allowance_retired` |

### Acceptance criteria

### AC-001: measured evidence references the definition, not the command
For any measure command that exits 0 and prints a number, the appended row's `evidence` equals `f"auto: measure#{row['definition_hash'][:12]} @ {sha} exit=0 cwd={cwd}"`, contains no argv token longer than 3 characters, and has the same length for every command; manual `record` evidence and pre-existing tool-written rows are unchanged.

### AC-002: gap reports the withdrawal block
On a committed skeleton→filled history with `hm:wrapup` `start` events either side of the fill commit, `gap_report(root)["withdrawal"]` has exactly the keys `filled_at, wrapups_since_fill, objectives_observed, revisit_candidates_now, due, reason` with the hand-computed values and `reason == "ok"`, and `"withdrawal" not in status_report(root)`.

### AC-003: due is the criterion exactly
`due` is true iff `wrapups_since_fill >= 10 and objectives_observed == 0 and revisit_candidates_now == 0`, and false whenever `wrapups_since_fill` is `None`.

### AC-004: unmeasurable counts are null with reason
`not_filled_in`, `no_git` (incl. shallow), `fill_uncommitted`, `no_stage_spans` (incl. a directory at the path) and `no_wrapup_spans` worlds each exit 0 with the unmeasurable fields `None`, `due` false and the matching `reason` (first applicable in that order); a deleting history commit is skipped; an invalid world returns the `state: invalid` payload without `withdrawal`.

### AC-005: wrapup prints withdrawal line when due
Both wrapup renders contain, inside Step 5.7, exactly one instruction keyed on `withdrawal.due` that prints `[intent] withdrawal criterion met`, and `intent.SKELETON` names `hm world gap` and `withdrawal.due`.

### AC-006: surface pinned and allowance retired
plan/review/help hashes equal the pre-change pin per arm; wrapup growth ≤ the declared allowance while in flight; at close-out the PLAN has no `surface_allowance`, the delta doc quotes the committed aggregate, and the structural suite is green.

### Test files (spec gate)

| Test file | ACs |
|---|---|
| `tests/unit/test_world_evidence_ref.py` | AC-001 |
| `tests/unit/test_world_withdrawal.py` | AC-002, AC-003, AC-004 |
| `tests/unit/test_render_intent_layer.py` | AC-005 |
| `tests/structural/test_intent_layer_ops_invariance.py` | AC-006 |

## ❓ Open Questions

None — every slot settled. Items for `/hm:plan` ADRs: how `filled_at` walks `git log` (oldest
commit whose blob is not `not_filled_in`), whether the evidence change also amends
SPEC-outcome-measure AC-002's test (it must — that test pins the old string), the wrapup
allowance amount.

## 🔍 Refinement Decisions

- `/hm:plan` validator follow-up (2026-09-18): count `hm:wrapup` **start** events and add
  `no_wrapup_spans` (the `end` event is Claude-Code-only and missed when stages chain — dogfood 42
  start vs 32 end); shallow clone → `no_git`; tool-written byte identity only.
- `/hm:plan` interview (2026-09-18), rounds 1–2: of four concerns raised, assumptions and INTENT
  body are **out of scope** (the body is SPEC-playbook-alignment's deliberate choice); withdrawal
  is **measured**, clock starts at the **first git commit that fills `intent.yaml`**, surfaced as
  **payload + one wrapup 5.7 line**; evidence becomes a **definition-hash reference**.
- `/hm:spec` round 1: unmeasurable counts are **`null` + `due: false` + `reason`** (never a
  disguised 0); SPEC layout is **this new SPEC + an AC-002 amendment** to SPEC-outcome-measure.
- Default taken without asking: the block lives in **`gap` only** — `status --json` is pinned
  unchanged by SPEC-objective-gap-proposal, and wrapup 5.7 already reads `gap`.
