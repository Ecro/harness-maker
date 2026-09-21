---
type: spec
task_slug: intent-vocabulary-rename
status: draft
created: 2026-09-21
tags: [harness-maker, spec, python, intent, migration]
test_framework: pytest
tier: 2
interview_rounds: 0
summary: "Readable intent vocabulary with lossless legacy reads and an explicit migration"
---
# Intent vocabulary migration

## 🎯 Intent
Apply the DRI handoff's vocabulary without invalidating approvals or restarting history clocks.
The user authorized adapting unreleased SPEC/execute planning in this session.

## 🌅 Outcomes
Use hm intent and readable durable fields. An intent groups 1:N tasks (broader than Playbook's
1:1 meaning); no new grouping concept or cardinality change is introduced.

## 📋 In-Scope Scenarios

### S1: Compatible project schema
**Given** legacy mission/vision/outcomes/non_negotiables/non_scope/unknowns or canonical fields.
**When** the same loader validates and loads either format.
**Then** purpose retains statement and vision; metrics, rules, out_of_scope and question claims retain every value; unsupported schema versions and conflicting mixed keys are rejected.

### S2: Stable approvals and measurements
**Given** an approved legacy record and recorded metric value.
**When** migration writes intent/ID.md with statement/metric_id/out_of_scope.
**Then** approval remains valid, definition hash and approval hash are byte-identical, record body and timestamps survive.

### S3: Historical withdrawal clock
**Given** a git repo with old-key filled project commits and later canonical commits.
**When** canonical status reads the withdrawal window.
**Then** filled_at remains the old filled commit timestamp; quiet-wrapup count is unchanged; shallow history stays unevaluable.

### S4: Safe repeatable migration
**Given** legacy project/questions/measurements and INTENT records.
**When** hm intent migrate runs twice.
**Then** all values are preserved in canonical locations, retired sources are removed only after successful writes, and the second invocation changes no bytes; conflicting destinations cause a nonzero result without writes.

### S5: One question store
**Given** legacy assumptions and project unknowns.
**When** the project migrates and a question is resolved.
**Then** all claims and evidence/history survive in one authoritative open_questions store; known -> confirmed, assumed/unknown -> open, conflict -> wrong; resolving does not resurrect old unknowns.

### S6: Canonical CLI and compatibility alias
**Given** a canonical project.
**When** hm intent status, metric record/measure, question add/observe/resolve and direct new/approve/activate/drop/reopen/close/show are used.
**Then** verbs work with canonical field names; status includes gaps, revisit results and withdrawal; hm world remains usable with a stderr deprecation notice and clean JSON stdout.

### S7: Installed and land consumers
**Given** generated skills and a checkout with canonical records.
**When** instructions render and deliverables are collected.
**Then** new CLI and intent/ID.md paths are used, body-preserving migration is documented, and records are collected for staging.

## 🚫 Non-Goals
No authentication, no state-based directories, no external dependencies, no metric formula or
approval-payload changes, no migration of unrelated project words or historical SPEC IDs.
Compatibility code and frozen regression fixtures necessarily retain legacy spellings.

## ⚠️ Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Framework | pytest | Existing suite |
| Schema | major 1, both dialects accepted | Avoid foreign-major early rejection |
| Purpose | mapping with statement and vision strings | Preserve both original prose fields |
| Records | intent/<ID>.md, statement/metric_id/out_of_scope | Folder denotes type, frontmatter state |
| Questions | open/confirmed/wrong, preserve evidence/history | One authoritative persisted store |
| Reads | never rewrite files | Status and historical blobs must be side-effect free |
| Migration | preflight every collision before writes, atomic file replacement | Prevent silent loss |
| Hash | frozen old payload key strings | Preserve existing approvals |
| CLI | hm world alias for one release | Existing user scripts continue working |

## 🔒 Irreversible Decisions
| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | purpose={statement,vision}, metrics, rules, out_of_scope | schema/file format/storage layout | Durable vocabulary |
| IRR-002 | intent/<ID>.md; statement/metric_id/out_of_scope; intent remains 1:N | data migration | Existing links and approvals |
| IRR-003 | hm intent with direct record verbs, metric and question groups; hm world deprecated | public API/CLI contract | Scripts and instructions |
| IRR-004 | open questions merge claims, preserving evidence/history and mapping statuses | data migration | Avoid two conflicting stores |

## ✅ Verification Criteria
- S1: pytest `tests/unit/test_intent_vocabulary.py::test_s1` — Compatible project schema.
- S2: pytest `tests/unit/test_intent_vocabulary.py::test_s2` — Stable approvals and measurements.
- S3: pytest `tests/unit/test_intent_vocabulary.py::test_s3` — Historical withdrawal clock.
- S4: pytest `tests/unit/test_intent_vocabulary.py::test_s4` — Safe repeatable migration.
- S5: pytest `tests/unit/test_intent_vocabulary.py::test_s5` — One question store.
- S6: pytest `tests/unit/test_intent_vocabulary.py::test_s6` — Canonical CLI and compatibility alias.
- S7: pytest `tests/unit/test_intent_vocabulary.py::test_s7` — Installed and land consumers.

## Acceptance Criteria
### AC-001: Compatible project schema
Matches S1; independent legacy fixtures are the oracle.
### AC-002: Stable approvals and measurements
Matches S2; independent legacy fixtures are the oracle.
### AC-003: Historical withdrawal clock
Matches S3; independent legacy fixtures are the oracle.
### AC-004: Safe repeatable migration
Matches S4; independent legacy fixtures are the oracle.
### AC-005: One question store
Matches S5; independent legacy fixtures are the oracle.
### AC-006: Canonical CLI and compatibility alias
Matches S6; independent legacy fixtures are the oracle.
### AC-007: Installed and land consumers
Matches S7; independent legacy fixtures are the oracle.

## ❓ Open Questions
None for implementation. SPEC approval stamp is deferred to DRI acceptance before landing.

## 🔍 Refinement Decisions
Handoff settles migration-first, frozen hashes, 1:N chosen explicitly, and folder=type.
Canonical user surfaces use new vocabulary; adapters, historical fixture bytes and SPEC IDs
remain legacy where renaming would defeat compatibility verification.
