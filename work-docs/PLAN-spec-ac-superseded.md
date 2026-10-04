---
type: plan
task_slug: spec-ac-superseded
status: complete
created: 2026-10-04
tags: [harness-maker, plan, python, spec-machine, approval, cli]
spec: "[[SPEC-spec-ac-superseded]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "superseded_by AC field + `spec_machine retire`; every owes-a-test reader skips it; retire 4 stand-ins"
spec_need_verdict: add
spec_need_target: spec-ac-superseded
---

# PLAN — spec-ac-superseded

## 🎯 Executive Summary

Add a hash-excluded `superseded_by` field to `AcceptanceCriterion`. A new `retire` verb writes it after checking that the target exists in the same `specs/` dir and is `approved` or `exempt`. Every reader that treats an AC as owing a test skips superseded ACs:
- validate (binding error only)
- cross-validate rule 3
- coverage
- find-unbound and find-unjudged
- stale_judgment_verdicts
- spec_drift
- batch_refiner
- mark-tested, which refuses them atomically

Validate also checks the field's grammar and that the target exists. Finally, four landed stand-in ACs are retired. All decisions were locked in SPEC rounds 1–2.

## 📚 Prior Work

- `[wiki] render-golden-path-and-spec-hash`: editing authored fields voids approval. This is why the field must sit in `HASH_DENYLIST_AC`.
- The absent-case rule (failures, count 8): an absent `superseded_by` means live and is never serialised. AC-008 tests this.
- `approval_state` resolves through base/worktree precedence. retire uses `_state_at(slug, yaml.parent)` instead (SPEC Constraints: same checkout).
- `_mark_tested_locked` refuses unknown ids before writing. The superseded refusal sits right beside that check.

## 📐 Architecture Decision Records

### ADR-001: Retire reuses `_spec_write_lock` + `_dump_machine_yaml`
This gives the same locking and atomic write as mark-tested, with no new write path.
**Decided by:** agent

### ADR-002: The target check uses `_state_at(by_slug, yaml_path.parent)`
`approval_state(base, slug)` would prefer an unlanded worktree copy. `_state_at` is pinned to the directory that holds `--yaml`.
**Decided by:** agent

### ADR-003: `evaluate_coverage` gains a `total` key (live count). An all-superseded SPEC reuses the zero-AC branch.
The function has no production caller, so the added key changes no contract (spec-validator reconciliation).
**Decided by:** agent

### ADR-004: Validate's target-existence check resolves relative to the SPEC file's own directory
`validate(model)` has no path, so the check runs in `check`/`cross_validate` and in the CLI validate path, which do have one. The exemption itself stays in `validate`.
**Decided by:** agent

## 🏗️ Technical Design

- Model: `superseded_by: str | None = None`, added to `HASH_DENYLIST_AC`. `_dump_machine_yaml` pops AC-level `superseded_by: None`.
- `validate`: skip the binding error when `superseded_by` is set, and add a grammar error for a non-slug value.
- `superseded_target_errors(model, spec_dir)`: reports a missing `SPEC-<slug>.machine.yaml` in `spec_dir`. Called from `cross_validate` and from `check`.
- `cross_validate` rule 3: skip superseded ACs.
- `evaluate_coverage`: count live ACs only, and return `{coverage, missing, total}`.
- `select_pytest_bindable` / `select_judgment`: exclude superseded ACs. This covers find-unbound, find-unjudged and stale_judgment_verdicts.
- `_mark_tested_locked`: refuse any named superseded id before the empty or pre-check, and before the write.
- `retire(yaml_path, ac_id, *, by=None, clear=False) -> list[str]`, plus CLI `retire --yaml --ac (--by|--clear)`.
- `spec_drift.scan`: superseded ACs produce no coverage gap or pending candidate, and their `test_ids` are not referenced.
- `batch_refiner`: skip superseded ACs, and count them as clean.

## 📝 Implementation Plan

### Phase 1: RED tests
- depends_on: none · parallel_group: A · merge_hazards: none
- Scope in: `tests/unit/test_spec_ac_superseded.py`. Scope out: src.
- Exit: `uv run pytest tests/unit/test_spec_ac_superseded.py` has AC-001…AC-009 failing for a missing feature.
- risk: low · rollback: delete the file

### Phase 2: Implementation
- depends_on: Phase 1 · parallel_group: B · merge_hazards: `spec_machine.py` is shared by many tests
- Scope in: `src/harness_maker/spec_machine.py`, `src/harness_maker/observability/spec_drift.py`, `src/harness_maker/spec_inventory/batch_refiner.py`
- Exit (Path A addition): with the slug-grammar check temporarily removed, exactly `test_ac002_retire_refuses_unsafe[bad-slug]` and `[traversal]` fail (mutation check), then restore. Then: the Phase 1 tests (except AC-009) plus `tests/unit/test_spec_machine*.py tests/unit/test_spec_approval.py tests/unit/test_spec_drift*.py` are green, and so is `mypy --strict`
- risk: medium · rollback: `git checkout` the three files

### Phase 3: Retire the four stand-ins
- depends_on: Phase 2 · parallel_group: C · merge_hazards: landed SPEC files
- Scope in: `specs/SPEC-intent-layer-improvements.machine.yaml`, `specs/SPEC-intent-layer-diet.machine.yaml` (written via `retire` only)
- Exit: AC-009 test green, `approval-status` approved for both, `find-unbound` exit 0 for both
- risk: low · rollback: `retire --clear`

### Phase 4: Full suite
- depends_on: Phase 3 · parallel_group: D · merge_hazards: none
- Exit: `ruff check .`, `ruff format --check .`, `mypy --strict src tests` and the full pytest run are all green. `tests/structural` runs after `git add -N` of new files.
- risk: low · rollback: none

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/` — no stage-template change (SPEC Non-goal)
- Advisory: approval hash algorithm and `approve` unchanged; only `HASH_DENYLIST_AC` gains a field
- Advisory: authored fields of the landed SPECs stay byte-identical; only `superseded_by` and `pending_test` change

## 🧪 Testing Strategy

- Unit tests build temporary `specs/` dirs with hand-written fixture SPECs: an approved target, a draft target, an approved-in-other-dir target, mixed live/superseded ACs, and judgment ACs with fail/stale verdicts.
- Every reader gets a control: a live AC that must still fire.
- The AC-003 property test uses Hypothesis over AC sets.
- The AC-009 test reads the committed repo SPECs.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| A new model field leaks `null` into every rewritten SPEC | `_dump_machine_yaml` pop plus the AC-008 test |
| An existing test pins the `evaluate_coverage` dict shape | Run the spec_machine tests in Phase 2; add the key, do not rename |
| find-unbound on the landed SPECs runs a repo-wide pytest collect (slow) | AC-009 calls it once per SPEC |
| A structural scanner misses the untracked new test | `git add -N` before the structural run (memory) |

## ✅ Success Criteria

- [x] AC-001 retire records superseded_by
- [x] AC-002 refusals leave the file byte-identical, and a same-target re-run is a no-op
- [x] AC-003 approval hash invariant
- [x] AC-004 validate exempts only the binding error and checks the field
- [x] AC-005 every reader skips superseded ACs
- [x] AC-006 mark-tested refuses atomically
- [x] AC-007 clear re-pends
- [x] AC-008 no null serialisation
- [x] AC-009 four stand-ins retired, SPECs approved
- [x] AC-010 suite green

## Phase status

| Phase | Status |
|---|---|
| 1 | done — A.5 exhausted at round 2; round-2 fix (traversal `x/../up`, 'must match') applied after the budget, NOT reviewed (user chose Path A) |
| 2 | done — mutation check passed (only [bad-slug]/[traversal] fail with the grammar check removed); spec-related unit tests green |
| 3 | done — four stand-ins retired via `retire`; both SPECs still approved; AC-009 green |
| 4 | done — ruff, format, mypy --strict src tests (801 files) and full pytest (9934 passed, 0 failed) all green |

## Notes

- **A.5 (Phase 1):** round 1 FAIL (4 issues), round 2 FAIL (1 issue: traversal/bad-slug did not isolate the grammar check). The round-2 fix was applied after the budget ran out and was not reviewed. Per the user's Path A, it is verified at the Phase 2 exit by a mutation check.
- **Unobservable clause:** SPEC S4 says spec_drift does not count superseded `test_ids` as referenced. `referenced_test_ids` in `spec_drift.scan` is computed and never consumed, because `orphan_tests` is never populated. The code still excludes them, but no test can observe it.
- **Phase 2 scope addition:** `tests/unit/test_spec_approval.py` gained `ac.superseded_by` in its `_DENY` oracle, its `_REPLACEMENTS` table and its independent-hash key list. That test enforces a mutation entry for every model field, and IRR-001 deliberately moves this field into the hash denylist.
- **Environment incident:** an empty `/tmp/.git` (created 20:49 KST, origin unknown) made every git-lock test under `/tmp` fail, on pristine main as well. It was removed with the user's consent before Phase 2 verification.
- **Phase 4 scope addition:** `src/harness_maker/command_registry.py` registers the new `retire` subparser. `test_command_surface_gate` enforces registry↔source parity, and the first full run caught the omission.
- **D.5:** skipped. This is new-feature work, not a defect repair.

## Boundary comparison (Step 4)

There are 11 changed paths:
- 2 landed SPEC yamls, with only `pending_test`/`superseded_by` lines changed
- `spec_machine.py`, `spec_drift.py`, `batch_refiner.py`, `command_registry.py`
- `test_spec_approval.py`
- 4 new files: the SPEC ×2, the test and the PLAN

None sits under `src/harness_maker/templates/`, so there are **0 crossings**. Both advisories are honoured: the approval algorithm is unchanged (only the denylist grew), and the authored fields of the landed SPECs are byte-identical.
