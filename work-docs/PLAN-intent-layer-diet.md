---
type: plan
task_slug: intent-layer-diet
status: complete
created: 2026-10-04
tags: [harness-maker, plan, python, intent-layer, worktree, dead-code]
spec: "[[SPEC-intent-layer-diet]]"
research_doc: "[[RESEARCH-intent-layer-diet]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "Delete intent_trial (module, CLI verbs, worktree.py hooks) and the objective_proposed write; goldens first"
spec_need_verdict: add
spec_need_target: intent-layer-diet
---

# PLAN — intent-layer-diet

## 🎯 Executive Summary

Delete the frozen trial machinery (`intent_trial.py` and its tests, the `hm intent
trial/reconcile/record-decision` verbs, and every trial branch in `worktree.py`) and the
write-only `objective_proposed` ledger append. Fix the autopilot objective gate's remediation
text so it names `hm intent`. Nothing else changes. The `hm world` CLI, the rubrics,
migrate, owners and every rendered template stay (SPEC rounds 3–4).

Behaviour-preservation argument: in this repository `intent_trial.active_trials()`,
`protected_trial_paths()` and `verified_trial_landing_paths()` all return empty today
(measured 2026-10-04), so every trial branch in `worktree.py` is currently inert. Deleting
the branches specializes the code to the path that already runs.

## 📚 Prior Work

- RESEARCH-intent-layer-diet: usage census (trial never produced a verdict) and caller map.
- SPEC-intent-layer-diet (approved, round 4): 7 ACs, IRR-001 (trial verbs removed, no stub).
- `[fail:test] assertion-invariant-over-named-dimension` (count 22): AC tests must assert
  the surviving invariant against real subjects, not vacuous checks.
- `[fail:design] fix-introduced-defect-passes-all-gates` (count 18): the `worktree.py` edits
  are proven by the pre-existing land/finalize/stash tests, run unmodified.
- `docs/reference/multi-session-worktree.md` does not mention the trial; no invariant there
  depends on it.

## 📐 Architecture Decision Records

### ADR-001: Specialize trial branches to their empty-trial path instead of stubbing intent_trial
**Decided by:** agent
Every `worktree.py` site becomes exactly what it computes when the trial sets are empty:
fence timeout `_FENCE_TIMEOUT`, no protected-path checks, no runtime staging, no
`chore(intent): persist trial collection` commit, `runtime_committed` removed. A stub module
would keep dead branches alive.

### ADR-002: Span emission is warn-only (SPEC round 1)
**Decided by:** user (source: SPEC Refinement Decisions, round 1)
`_trial_active` and the `required` flag go. `_emit_stage_span` always passes
`fence_timeout=5.0` (the non-required value it uses today) and only warns on failure.

### ADR-003: Goldens are captured from the unmodified engine before any source edit
**Decided by:** agent
The AC-007 status goldens are written by a capture helper in the AC test module, run once
before Phase 3 touches `src/`, with a pinned clock and fixture roots in `tests/fixtures/`.
The test compares the current engine to those files and never regenerates them. Fixture
content comes from this public repository's own intent files (current layout, with `owners`
populated for the fixture) and the empty legacy template shape (`mission:`/`outcomes:`). No
private consumer data is copied.

### ADR-004: Keep the `objective_proposed` event name and the `--from-proposal` contract
**Decided by:** agent
Only `_record_proposal` and its call go. `autopilot_ledger.LedgerEvent` keeps
`objective_proposed` so historical rows parse, and its comment is updated to say no writer
remains. `--from-proposal/--candidates/--declined` validation and the `rejected[]` prefill
are unchanged.

## 🏗️ Technical Design

| Component | Change |
|---|---|
| `src/harness_maker/intent_trial.py` | deleted |
| `src/harness_maker/intent.py` `_parser` | `trial` subparser removed |
| `src/harness_maker/intent_cli.py` | `args.cmd == "trial"` branch removed |
| `src/harness_maker/command_registry.py` | `trial`, `reconcile`, `record-decision` removed from the intent verbs |
| `src/harness_maker/worktree.py` | `_fenced_restore_base_dirty`, finalize fence block, post-commit pop, `_trial_active`/`_emit_stage_span`, `task_land` trial sets → empty-trial path |
| `src/harness_maker/world.py` | `_record_proposal` and its call removed; docstring updated |
| `src/harness_maker/autopilot_caps.py` | remediation names `hm intent approve`/`hm intent activate` |
| `src/harness_maker/autopilot_ledger.py` | comment only |
| tests | `test_intent_trial.py`, `test_intent_trial_freeze.py`, `integration/test_intent_trial_concurrency.py`, `trial_fixture.py` deleted; enumerated edits in `test_intent_doc_new.py` and `integration/test_intent_layer_lifecycle.py`; new `test_intent_layer_diet.py` + `tests/fixtures/intent_layer_diet/` |

`tests/integration/test_intent_trial_native_evidence.py` replays captured JSON and never
imports `intent_trial`, so it stays (historical evidence).

## 📝 Implementation Plan

### Phase 1 — Goldens (before any source edit)
- depends_on: none
- parallel_group: serial
- merge_hazards: none
- scope in: `tests/fixtures/intent_layer_diet/**`, the capture helper inside `tests/unit/test_intent_layer_diet.py`
- scope out: `src/**`
- exit criterion: `ls tests/fixtures/intent_layer_diet/{current,legacy}/status.golden.json` both exist, generated while `git diff --stat -- src` is empty
- risk: low
- rollback: delete the fixture directory

### Phase 2 — AC tests (RED)
- depends_on: Phase 1
- parallel_group: serial
- merge_hazards: none
- scope in: `tests/unit/test_intent_layer_diet.py`
- exit criterion: `uv run pytest tests/unit/test_intent_layer_diet.py` → AC-001, AC-002, AC-003, AC-004 and AC-006 fail for the missing change; AC-005 and AC-007 pass by design (preservation oracles, justified in the module docstring)
- risk: low
- rollback: delete the test file

### Phase 3 — Remove the trial (module, CLI, worktree)
- depends_on: Phase 2
- parallel_group: serial
- merge_hazards: `worktree.py` is the highest-risk module
- scope in: `intent_trial.py`, `intent.py`, `intent_cli.py`, `command_registry.py`, `worktree.py`, the four trial test files
- exit criterion: `uv run pytest tests/unit/test_intent_layer_diet.py -k "ac001 or ac002 or ac003"` green and `uv run pytest tests/unit/test_worktree_stash.py tests/unit/test_worktree_task_land.py tests/unit/test_worktree_finalize_commit_not_stash.py tests/unit/test_worktree_landed_marker.py` green with those files unmodified
- risk: medium
- rollback: `git checkout -- src/harness_maker/worktree.py` plus restore the deleted files

### Phase 4 — Remove the proposal write, fix the gate remediation
- depends_on: Phase 3
- parallel_group: serial
- merge_hazards: none
- scope in: `world.py`, `autopilot_caps.py`, `autopilot_ledger.py` (comment), `tests/unit/test_intent_doc_new.py`, `tests/integration/test_intent_layer_lifecycle.py` (enumerated edits only)
- exit criterion: `uv run pytest tests/unit/test_intent_layer_diet.py tests/unit/test_intent_doc_new.py tests/integration/test_intent_layer_lifecycle.py` green
- risk: low
- rollback: `git checkout --` the listed files

### Phase 5 — Full verification
- depends_on: Phase 4
- parallel_group: serial
- merge_hazards: none
- scope in: none (read-only gates)
- exit criterion: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src` and the full `uv run pytest` green
- risk: low
- rollback: n/a

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/` — no rendered change (AC-005; UNDERSTANDING-HANDOFF window)
- `src/harness_maker/intent_vocabulary.py` — Approach B, out of scope
- `src/harness_maker/intent_migrate.py` — legacy consumers (strange_chess) depend on it
- `src/harness_maker/world_model_digest.py` — Maker digest contract
- `src/harness_maker/hm.py` — `hm world` stays (SPEC round 4)
- `tests/unit/world_fixture.py` — the `hm world` test seam stays
- `tests/unit/test_worktree_stash.py` — AC-002 differential oracle, run unmodified
- `tests/unit/test_worktree_task_land.py` — AC-002 differential oracle, run unmodified
- `tests/unit/test_worktree_finalize_commit_not_stash.py` — AC-002 differential oracle
- `tests/unit/test_worktree_landed_marker.py` — AC-002 differential oracle
- `tests/snapshot/` — AC-005 pins are not regenerated
- `.claude/intent.yaml` — user state
- `intent/` — user state
- `work-docs/PLAN-world-intent-closed-loop-trial.md` — historical artifact
- Advisory: the `hm intent status --json` payload shape must not change (AC-007)

## 📊 Phase Status

| Phase | Status | Evidence |
|---|---|---|
| 1 Goldens | done | `tests/fixtures/intent_layer_diet/` written while `git diff --stat -- src` was empty |
| 2 AC tests | done | A.4: 6 failed, 5 passed (5 justified preservation oracles); A.5 test-reviewer PASS round 1 |
| 3 Trial removal | done | AC-001/002/003 green; the four AC-002 worktree suites unmodified, 56 passed; all worktree + span suites 542 passed, 8 skipped |
| 4 Proposal write + gate text | done | intent/gate/lifecycle suites 762 passed |
| 5 Full verification | done | ruff, ruff format, mypy --strict clean; full pytest 9847 passed, 100 skipped, 2 xfailed, 1 xpassed, 0 failed (rc=0, read from the output file) |

Enumerated AC-004 edits, as made: in `tests/unit/test_intent_doc_new.py` the three
`objective_proposed` row assertions now assert no row, the fault-injection test
`test_ac_003_a_failed_ledger_append_keeps_the_record_and_warns` is deleted, the section comment
is updated, and three test names that claimed an emitted event are renamed to match
(`…_emits_no_event`, `…_share_the_declined_list`, `…_writes_the_record_in_the_worktree_and_no_row`).
In `tests/integration/test_intent_layer_lifecycle.py` the row count assertion became 0, with an
absent-ledger guard. Every record, layout and refusal assertion is byte-identical.

Boundary comparison (Step 4): 20 changed paths (8 src modified/deleted, 6 tests
modified/deleted, 6 new). None equals or sits under a `Do not change` entry, so there are no
crossings.

## 🧪 Testing Strategy

- Unit: `tests/unit/test_intent_layer_diet.py` (AC-001…AC-007).
- Differential: the four worktree test files and the intent/world suites run unmodified,
  except the enumerated AC-004 edits.
- Integration: `tests/integration/test_intent_layer_lifecycle.py`, snapshot suite.
- Full suite once at Phase 5 (≈6 min, run in background).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A `worktree.py` edit changes a non-trial path | low | high | Specialize mechanically (ADR-001); the four worktree suites run unmodified |
| Span emission semantics shift | low | medium | AC-003 injects a failure; the timeout matches today's non-required value |
| A structural test pins the intent verb list or module set | medium | low | Full suite at Phase 5; update only if the pin encodes the removed verbs |
| Golden drift from clock or ledgers | medium | medium | Pinned clock, fixture roots in tmp copies, isolated ledger (ADR-003) |
| Unused import left after deletion | medium | low | ruff + mypy at Phase 5 |

## ✅ Success Criteria

- [x] AC-001 trial verbs and module removed
- [x] AC-002 worktree non-trial paths pass pre-existing tests unmodified
- [x] AC-003 span failure warns, never blocks
- [x] AC-004 intent tests pass with enumerated edits only; gate names `hm intent`
- [x] AC-005 fresh renders match the pre-change pins
- [x] AC-006 from-proposal leaves both ledgers untouched
- [x] AC-007 status JSON and fixture bytes identical
- [x] ruff, mypy --strict and the full pytest suite green

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| Usage census 2026-10-04 (carried from SPEC): trial never produced a verdict; revisits, revalidation, conflicts and the objective halt never fired | purpose ("remove devices that do not pay their way") | recorded | question add q_intent_layer_unfired_paths (confirmed) | operator | wrapup Step 5.7 | none |
| wrapup 5.7 measure all (2026-10-04): lead_time 2.9, CFR 0, churn 8.3, unsourced 45.2, dead_bytes 7.5 | metrics | recorded | metric measure --all | operator | wrapup Step 5.7 | none |
