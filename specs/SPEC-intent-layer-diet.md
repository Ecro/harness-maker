---
type: spec
task_slug: intent-layer-diet
status: approved
created: 2026-10-04
tags: [harness-maker, spec, python, intent-layer, simplification, dead-code]
test_framework: pytest
tier: 2
interview_rounds: 4
research_doc: "[[RESEARCH-intent-layer-diet]]"
summary: "Remove the intent layer's trial machinery and proposal ledger write with zero behaviour change elsewhere"
---

# SPEC — intent-layer-diet

## 🎯 Intent

The intent layer has about 5,450 Python LOC. Its largest single component, `intent_trial.py`
(1,472 LOC, plus 2,598 test LOC), never produced a verdict: the trial was frozen at 0/3 on
2026-09-23, and the intent it served closed `met` on 2026-10-04 through manual metric rows.
The `objective_proposed` ledger event has no reader. The project's first goal is to remove
devices that do not pay their way and to prefer the simpler design. This change deletes that
machinery and leaves every surviving behaviour unchanged (RESEARCH-intent-layer-diet,
Approach A, narrowed in round 3 to keep the rubrics and in round 4 to defer the `hm world`
CLI, which turned out to be the subprocess seam of ~32 engine tests).

## 🌅 Outcomes

- A maintainer reading `worktree.py` no longer meets trial branches in stash-restore,
  finalize, post-commit pop, land or span emission.
- `hm intent` no longer offers the trial verbs, and the autopilot objective gate's
  remediation names `hm intent` instead of the deprecated `hm world`.
- Every consumer's existing `.claude/intent.yaml`, `intent/*.md` and
  `.claude/intent/metrics.yaml` (current and legacy layout) reads exactly as before, and
  every rendered harness is byte-identical.

## 📋 In-Scope Scenarios

### S1: Trial verbs and module are gone
**Given** a checkout after this change
**When** a user runs `hm intent --help` or imports `harness_maker.intent_trial`
**Then** `trial`, `reconcile` and `record-decision` are not offered as verbs, and the import fails
**And** `command_registry` lists none of the three verbs

### S2: Worktree non-trial paths are unchanged
**Given** the worktree stash, finalize, post-commit pop and land tests that existed before this change
**When** they run unmodified against the trimmed `worktree.py`
**Then** every one passes
**And** no code path in `worktree.py` imports or calls `intent_trial`

### S3: Stage-span emission never blocks a stage
**Given** a task stage start with a `task_slug` and a span emitter that raises
**When** `task-preflight` emits the stage-span start event
**Then** preflight succeeds and returns the worktree path
**And** a warning naming the failed span write is printed to stderr

### S4: Intent tests keep passing and the gate remediation names `hm intent`
**Given** a checkout after this change
**When** the pre-existing intent and world test suites run, and the autopilot objective gate halts on an unapproved intent
**Then** the tests pass, with changes confined to the enumerated `objective_proposed` assertions (AC-004)
**And** the gate's remediation text names `hm intent approve` / `hm intent activate` and no longer names `hm world objective`

### S5: Proposal flag is accepted but writes no ledger event
**Given** a hermetic base checkout with a linked worktree, a filled `intent.yaml` with a metric `m`, and historical `objective_proposed` rows seeded in the base ledger
**When** `hm intent new X ... --metric m --from-proposal --candidates 1` runs in the worktree
**Then** `intent/X.md` is created in the worktree in state `proposed`
**And** the base and worktree autopilot ledgers are byte-identical to before the run
**And** the seeded historical rows still parse through `autopilot_ledger`

### S6: User state and renders are preserved
**Given** committed fixture roots (a current-layout project with questions and populated owners, and a legacy `mission:`/`outcomes:` project) and their `hm intent status --json` output, captured before any code change with a pinned clock and an isolated ledger
**When** the same commands run after the change
**Then** the status JSON is identical (key for key, value for value) and every fixture input file is byte-unchanged
**And** a fresh render of all four snapshot arms matches the `body_sha256` pins generated before the change (`tests/unit/test_synthesize_snapshot.py`)

## 🚫 Non-Goals

- Approach B: any change to questions, assumptions, `revisit_when`, `needs_revalidation`,
  `conflicts`, evidence locators, `intent_vocabulary`, the content-hash approval or the
  `hm intent status` payload.
- Approach C: any change to rendered templates (stage prose, Feedback rows, wrapup 5.7,
  spec 0.5/4.9, review 3.3, intent-layer skill, Maker) or a harness.yaml toggle.
- Removing the deprecated `hm world` CLI (`world._parser`/`main`, `hm.py` allowlist,
  `command_registry`) and its read helpers. It is the subprocess seam
  (`tests/unit/world_fixture.run_cli`) of ~32 engine tests across 11 files whose verbs and
  JSON keys differ from `hm intent`; removing it would mean rewriting those assertions
  (round 4 decision, deferred).
- Deleting the ten unrendered rubric templates (`rubrics/world_intent_*`,
  `intent_feedback_continuity`, `objective_scope_drift`). Four kept historical machine SPECs
  reference them, and `spec_machine` rule-4 would fail on those SPECs (round 3 decision).
- Removing `intent_migrate.py` or the legacy-layout read paths (`strange_chess` still holds a
  legacy file and can only become writable through migrate).
- Removing the `owners` schema key or its approval advisory (set in spoton, neuroTerm, edgelog).
- Any change to the UNDERSTANDING-HANDOFF measurement (wrapup Understanding block, ADR `decided_by`).
- Deleting historical artifacts: `PLAN-world-intent-closed-loop-trial.md`, trial SPECs, old
  ledger rows. The `objective_proposed` name stays registered in `autopilot_ledger` so old rows
  still parse.
- Releasing a version (a wrapup/release decision).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Type / lint | `mypy --strict`, `ruff check`, `ruff format` | Project standard |
| Render | Byte-identical fresh renders for all four snapshot arms | Approach A promises no rendered change; protects the UNDERSTANDING-HANDOFF window |
| Compatibility | Existing consumer intent files (current and legacy layout) parse unchanged | pre-change-checklist item 1 (user state preservation) |
| Worktree | Follow `docs/reference/multi-session-worktree.md`; no change to land/finalize/stash semantics for non-trial runs | Highest-risk module; silent data loss history |
| Oracle discipline | Goldens (status captures) are written **before** the first source edit and never regenerated after it. Behaviour preservation is proven by tests that predate the change. The only permitted edits to pre-existing tests are the enumerated `objective_proposed` assertions (AC-004). Tests that exercised only removed behaviour (trial) are deleted, not rewritten to pass | Avoids circular oracles on a deletion |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Remove `hm intent trial/reconcile/record-decision` from the CLI, with no stub | public API/CLI contract | Anyone who types these by hand gets an argparse "invalid choice" error. Rendered harnesses do not call them, and old harnesses run their own pinned plugin cache. Restoring them means re-adding ~1.5k LOC |

## ✅ Acceptance Criteria

### AC-001: Trial verbs and module are removed
Covers S1.

### AC-002: Worktree non-trial paths pass pre-existing tests unmodified
Covers S2.

### AC-003: Stage-span emission failure warns and never blocks preflight
Covers S3.

### AC-004: Intent tests pass with enumerated edits only and the gate names hm intent
Covers S4. Permitted edits are limited to the `objective_proposed` row and warning
assertions at `tests/unit/test_intent_doc_new.py` (around lines 194, 251, 269, 291) and
`tests/integration/test_intent_layer_lifecycle.py` (around line 191). The fault-injection test
that expects "objective_proposed NOT recorded" is deleted. Every other assertion in those
tests, including record placement in the worktree, refusal before any write, and the
`rejected` prefill, stays byte-identical.

### AC-005: Fresh renders match the pre-change snapshot pins
Covers S6 (render half).

### AC-006: From-proposal creates the record and leaves both ledgers untouched
Covers S5.

### AC-007: Intent status JSON and fixture files are identical before and after
Covers S6 (state half).

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `tests/unit/test_intent_layer_diet.py::test_ac001_trial_verbs_removed` |
| S2 | unit + integration | Pre-existing `tests/unit/test_worktree_stash.py`, `test_worktree_task_land.py`, `test_worktree_finalize_commit_not_stash.py`, `test_worktree_landed_marker.py` run unmodified; plus `test_ac002_worktree_has_no_trial_reference` |
| S3 | unit | `tests/unit/test_intent_layer_diet.py::test_ac003_span_failure_warns_not_blocks` |
| S4 | unit | `tests/unit/test_intent_layer_diet.py::test_ac004_gate_remediation_names_hm_intent`; pre-existing intent and world tests green with only the enumerated edits (checked against `git diff` of those files) |
| S5 | unit | `tests/unit/test_intent_layer_diet.py::test_ac006_from_proposal_ledgers_untouched` |
| S6 | integration | `tests/unit/test_intent_layer_diet.py::test_ac007_status_json_identical` against goldens in `tests/fixtures/intent_layer_diet/` (committed before the change); `tests/unit/test_synthesize_snapshot.py` unchanged and green (`test_ac005_fresh_render_matches_pins`) |

## ❓ Open Questions

None. Implementation choices (the order in which the `worktree.py` trial sites are removed,
which trial-only tests are deleted) belong to `/hm:execute` Step 0, within the limits above.

## 🔎 Spec Validation

spec-validator (pass 1, run `spec-intent-layer-diet-20261004`): **MAJOR_REVISION** →
amended in round 3. codex second opinion: invoked; output truncated after 8 findings.

| Finding | Source | Disposition |
|---|---|---|
| AC-004 contradicts AC-006 (intent suite asserts `objective_proposed` rows); AC-006 predicate names no ledger | validator critical + codex P1/P2 | Accepted → AC-004 enumerated edits; AC-006 hermetic base+worktree, byte-identical ledgers |
| Deleting the 10 rubrics breaks rule-4 on 4 kept historical SPECs | validator warning | Accepted → rubrics kept, moved to Non-Goals |
| `hm world` removal can be half-done; `autopilot_caps.py:353` remediation names `hm world objective` | validator warning + codex P2 | Accepted → S4/AC-004 extended |
| `test_world_*` mixes engine and CLI coverage | validator warning + codex P1 | Accepted → AC-008 node-ID inventory |
| AC-007 not hermetic; fixture unnamed; legacy layout and owners uncovered | validator warning + codex P1 | Accepted → committed fixtures, pinned clock, isolated ledger, byte-unchanged inputs |
| AC-005 could compare pins with themselves | validator suggestion + codex P1 | Accepted → fresh renders via `test_synthesize_snapshot.py` |
| AC-003 should also verify path, success-path emission, fields, timeout | codex P2 | Rejected (validator): the `worktree.py:2904` caller passes no slug, so its behaviour is unchanged; the key regression (ImportError → `_trial_active` True) is caught by AC-003 |
| IRR should list the lost proposal history and the lost trial stash/land protection | codex P2 | Rejected (validator): outside the five categories; re-adding the write is a reversible code change and the trial is frozen |

## 🔍 Refinement Decisions

- Round 1: intent link = none; scope = Approach A only (keep `intent_migrate` because
  strange_chess is legacy, and keep owners because 3 consumers set it); span emission =
  warn-only (pre-trial behaviour).
- Round 2: oracle table accepted (golden for the removal lists and injected failure;
  differential against pre-change tests, captures and snapshot hashes); IRR-001 with no stub;
  no intent draft. The DRI approved the SPEC.
- Round 3 (after spec-validator MAJOR_REVISION + codex): all five amendments applied (AC-004
  enumerated edits, clean `hm world` removal including the autopilot remediation string,
  AC-008 engine-test inventory, hermetic AC-007 fixtures, AC-005 fresh renders); the 10
  rubrics are kept. The DRI re-approved the amended SPEC.
- Round 4 (during `/hm:execute` Step 0, new evidence): the `hm world` CLI is the subprocess
  seam (`world_fixture.run_cli`) of ~32 engine tests in 11 files, so removing it would rewrite
  their assertions. The DRI deferred its removal: AC-004 now covers only the enumerated intent
  test edits and the gate remediation string, AC-008 was dropped, and IRR-001 narrowed to the
  trial verbs. The DRI approved the narrowed scope.

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| Usage census 2026-10-04 (carried from RESEARCH): trial never produced a verdict; revisits, revalidation, conflicts and the objective halt never fired | purpose ("remove devices that do not pay their way") | recorded | question add q_intent_layer_unfired_paths (confirmed) | operator | wrapup Step 5.7 | none |
