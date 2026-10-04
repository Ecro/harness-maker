---
type: spec
task_slug: spec-ac-superseded
status: approved
created: 2026-10-04
tags: [harness-maker, spec, python, spec-machine, approval, cli]
test_framework: pytest
tier: 2
interview_rounds: 2
summary: "Machine SPEC AC gains a hash-excluded superseded_by state, written only by `hm spec_machine retire`"
---

# SPEC — spec-ac-superseded

## 🎯 Intent

Some later SPECs deliberately remove behaviour that an earlier, landed SPEC specified. The machine SPEC schema has no way to say that an AC is no longer live. The only available state is `pending_test: true` with empty `test_ids`, which tells every reader that a test is still owed. intent-surface-diet recorded its retired ACs that way, and two reviews flagged it as a misstatement (REVIEW-intent-surface-diet confirm-1; REVIEW-wrapup-intent-hardening 0f00b443). Editing an authored field instead would void the landed SPEC's approval, so the honest state has to be a tooling field written by a verb and checked when it is read.

## 🌅 Outcomes

- One command marks a single AC of a landed SPEC as superseded by a named, approved SPEC in the same checkout, and the landed SPEC's approval stays valid.
- Every reader that treats an AC as owing a test skips a superseded AC. Every authored-content check (predicate, oracle, rubric) still applies to it.
- A hand-written or dangling `superseded_by` (bad slug, target file missing) is a validate error, so a retirement nobody checked cannot silently waive an obligation.
- A mistaken retirement can be undone. The undo returns the AC to the unbound state, which the next wrapup re-binds.
- The four stand-in ACs currently left as `pending_test: true` / `test_ids: []` are retired to the SPECs that removed their behaviour.

## 📋 In-Scope Scenarios

### S1: Retire an AC
**Given** a landed SPEC whose AC-002 is `pending_test: true` with empty `test_ids`, and an approved SPEC `intent-surface-diet` in the **same** `specs/` directory
**When** the operator runs `hm spec_machine retire --yaml <landed> --ac AC-002 --by intent-surface-diet`
**Then** AC-002 carries `superseded_by: intent-surface-diet` and `pending_test: false`, and its `test_ids` are unchanged
**And** the landed SPEC's approval content hash is unchanged and `approval-status` still reports `approved`

### S2: Refuse an unsafe or ambiguous retire
**Given** a landed SPEC
**When** `retire` is called with any of the following:
- a `--by` slug that does not match `[a-z0-9][a-z0-9-]*`
- a target with no `specs/SPEC-<slug>.machine.yaml` in the same directory as `--yaml`
- a target whose approval state is not `approved` or `exempt` (draft, malformed, invalid, legacy, missing)
- a target approved only in a different checkout (another worktree)
- the SPEC itself as the target
- an AC id that does not exist
- both `--by` and `--clear`, or neither
- a different target for an AC that is already superseded
**Then** it exits non-zero with a reason naming the failed check
**And** the `.machine.yaml` is byte-identical to before
**And** re-running `retire` with the same target on an already-superseded AC exits 0 and leaves the file byte-identical

### S3: Validate exempts only the binding obligation
**Given** a superseded AC
**When** validate runs
**Then** it raises no `needs >=1 test_ids OR pending_test=true` error for that AC
**And** it still raises every other error for it. For example, an invalid `oracle_source` on a superseded AC is still reported
**And** it raises an error when `superseded_by` fails the slug grammar or names a SPEC with no `.machine.yaml` in the same `specs/` directory
**And** it does not check the target's approval state

### S4: Superseded ACs owe nothing to any reader
**Given** a SPEC mixing live and superseded ACs, including a superseded judgment AC with a `fail` verdict and one with a stale `pass`
**When** these readers run:
- cross-validate
- evaluate_coverage
- find-unbound
- find-unjudged
- stale_judgment_verdicts
- spec_drift
- the spec_inventory batch refiner
**Then** cross-validate rule 3 does not resolve superseded `test_ids`
**And** coverage returns `{"coverage", "missing", "total"}`. `total` counts live ACs only, and the expected dict for each fixture is a literal constant. An all-superseded SPEC reports exactly what a SPEC with no AC reports
**And** find-unbound, find-unjudged and stale_judgment_verdicts never list a superseded AC
**And** spec_drift reports no mapping gap for it and does not count its `test_ids` as referenced
**And** the batch refiner leaves a superseded AC's fields untouched

### S5: mark-tested refuses superseded ACs atomically
**Given** a SPEC with one live and one superseded AC
**When** `mark-tested` is called naming the superseded AC, alone or together with the live one, with `validate_after` true or false
**Then** it returns an error naming the superseded AC before any pytest collection or write
**And** the file is byte-identical, so the live AC is not bound either

### S6: Undo a retirement
**Given** a superseded AC
**When** the operator runs `retire --yaml <landed> --ac AC-002 --clear`
**Then** `superseded_by` is removed and `pending_test` is `true`, whatever `test_ids` holds
**And** the approval content hash is unchanged
**And** `--clear` on an AC that is not superseded exits non-zero and leaves the file byte-identical

### S7: An absent field stays absent
**Given** any existing machine SPEC with no `superseded_by` anywhere
**When** a tooling write such as `mark-tested` rewrites it
**Then** no `superseded_by: null` line appears

### S8: Retire the four landed stand-ins
**Given** these ACs, each with `pending_test: true` and `test_ids: []`:
- SPEC-intent-layer-improvements AC-002 and AC-011
- SPEC-intent-layer-diet AC-005
- SPEC-intent-layer-improvements AC-006 (trial freeze)
**When** AC-002, AC-011 and AC-005 are retired to `intent-surface-diet`, and AC-006 is retired to `intent-layer-diet`
**Then** the committed files carry those `superseded_by` values
**And** both SPECs report `approved`
**And** `find-unbound` exits 0 on both

## 🚫 Non-Goals

- No superseded state for a whole SPEC; only individual ACs are retired.
- No automatic detection of which ACs a new SPEC supersedes. The operator names them.
- No change to `approve`, to the approval hash algorithm, or to any authored field.
- No re-check of the target's approval at read time; validate checks the target's grammar and that it exists.
- No stage-template change. Wiring `retire` into `/hm:spec` or `/hm:wrapup` prose is a later decision.
- No reason or note on retirement; the superseding SPEC carries the why.
- No new tests for lock or atomic-write mechanics, because `retire` reuses the `mark-tested` write path.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Repo standard |
| Approval invariance | `superseded_by` joins `HASH_DENYLIST_AC` | Otherwise every retirement voids the landed SPEC's approval, which is the problem being solved |
| Write safety | `retire` writes through the same lock and atomic write as `mark-tested` | Concurrent wrapups write machine SPECs |
| Checkout scope | The target resolves in the same `specs/` directory as `--yaml`, never through base/worktree precedence | An unlanded worktree copy must not authorize a retirement on main |
| Compatibility | An absent `superseded_by` means live and is never serialised as null | Absent-case rule: existing SPECs behave and diff exactly as before |
| Slug grammar | `--by` and `superseded_by` match `[a-z0-9][a-z0-9-]*` | The value becomes a path component |
| Integration test | S8 reads the committed files and does not run `retire` on the repo | The test must not mutate the repo |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add an optional AC field `superseded_by` (a spec slug) to `.machine.yaml`, excluded from the approval hash and checked at validate time for grammar and target existence | schema/file format/storage layout | Landed SPECs will carry it. It also moves waiver authority: a tooling field now removes an approved obligation without re-approval. Validate catches bad or dangling values. "Only `retire` writes it" stays a convention, since a hand edit that names an existing SPEC passes |
| IRR-002 | Add the CLI verb `hm spec_machine retire --yaml --ac (--by <slug> \| --clear)` | public API/CLI contract | Operators and later templates call it by name, with these refusal and no-op semantics |

## ✅ Verification Criteria

Tests live in `tests/unit/test_spec_ac_superseded.py`.

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac001_retire_records_superseded_by` |
| S2 | unit | `test_ac002_retire_refuses_unsafe` |
| S1, S6 | unit | `test_ac003_retire_keeps_approval_hash` |
| S3 | unit | `test_ac004_validate_exempts_only_binding` |
| S4 | unit | `test_ac005_readers_skip_superseded` |
| S5 | unit | `test_ac006_mark_tested_refuses_atomically` |
| S6 | unit | `test_ac007_clear_repends` |
| S7 | unit | `test_ac008_absent_field_not_serialised` |
| S8 | integration | `test_ac009_landed_stand_ins_retired` |
| all | structural | full suite green (AC-010) |

### AC-001: Retire records superseded_by and clears pending_test
### AC-002: Retire refuses unsafe or ambiguous calls and leaves the file unchanged
### AC-003: Retire and clear never change the approval content hash
### AC-004: Validate exempts only the binding obligation and checks superseded_by
### AC-005: Every owes-a-test reader skips superseded ACs
### AC-006: Mark-tested refuses superseded ACs atomically
### AC-007: Clear removes the field and re-pends the AC
### AC-008: An absent superseded_by is never serialised
### AC-009: The four landed stand-ins are retired and their SPECs stay approved
### AC-010: The full suite stays green

## ❓ Open Questions

(none)

## 🔍 Refinement Decisions

- Pre-interview (user, earlier this session): the field is hash-excluded and written only by a CLI verb that checks the superseding SPEC is approved.
- Round 1:
  - Coverage leaves superseded ACs out of the denominator.
  - `retire --clear` is provided.
  - Retire flips `pending_test` to false and keeps `test_ids` as history.
  - Intent: none.
- Review (codex P1×5/P2×5, spec-validator MAJOR_REVISION). Agent-decided; none is an irreversible call:
  - The target resolves in the same checkout.
  - The validate exemption is narrowed to the binding error.
  - mark-tested refuses atomically.
  - Retarget is refused, and re-retire to the same target is a no-op.
  - `stale_judgment_verdicts`, the spec_drift orphan set and the batch refiner are added as readers.
  - An all-superseded SPEC's coverage equals a zero-AC SPEC's.
  - No null serialisation.
- Round 2 (user):
  - Intent-layer-improvements AC-006 is the fourth stand-in and is retired to `intent-layer-diet`.
  - Validate checks `superseded_by` grammar and target existence; IRR-001 is updated.
  - `--clear` always re-pends; this replaces round 1's "true only when test_ids is empty".
  - Approve after applying.
