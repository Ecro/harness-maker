---
type: spec
task_slug: intent-owners-role-map
status: draft
created: 2026-09-21
tags: [harness-maker, spec, python, intent]
test_framework: pytest
tier: 2
interview_rounds: 0
summary: "Compatible owners role maps and honest advisory approval warnings"
---
# Owners role map

## 🎯 Intent
Make the declared owners field useful without pretending git names authenticate people.
Requirements come from the DRI-supplied handoff section 2 and section 9.

## 🌅 Outcomes
Existing files continue loading; teams receive advisory separation guidance at approval.

## 📋 In-Scope Scenarios

### S1: Role shapes
**Given** a role map, a legacy list, an absent block or an empty block.
**When** the project is loaded.
**Then** roles normalize to owner/dri/team strings; absent and empty produce {}; legacy names join with comma-space.

### S2: Role validation
**Given** an unknown role key, non-string map value or malformed legacy list.
**When** the project is validated.
**Then** the offending owners field is named and the file is rejected.

### S3: Advisory approval
**Given** two distinct nonblank role identities.
**When** approval is recorded through the CLI.
**Then** exit is zero, approval remains valid, and stderr warns that git identity is unverified and CODEOWNERS plus branch protection enforce real separation.

### S4: Silent solo approval
**Given** absent, empty, blank, partial or identical roles.
**When** approval is recorded.
**Then** no role advisory appears; approval remains valid.

### S5: Rendered guidance
**Given** an installed intent-layer skill.
**When** the approval guidance is read.
**Then** it describes owners as advisory, unverified git identity and hosting enforcement.

## 🚫 Non-Goals
No blocking approval gate, authenticated identity, new hosting configuration or schema major bump.

## ⚠️ Constraints
| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | Project convention |
| Compatibility | schema major 1; legacy list accepted | Existing installations |
| Security | advisory only | approved_by is an unverified git config string |
| Identity | strip blanks; case-sensitive | No directory or authentication provider |

## 🔒 Irreversible Decisions
| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | owners map has owner/dri/team strings; lists join into team | schema/file format/storage layout | Durable hand-edited format |

## ✅ Verification Criteria
- S1: pytest `tests/unit/test_intent_owners.py::test_s1` — Role shapes.
- S2: pytest `tests/unit/test_intent_owners.py::test_s2` — Role validation.
- S3: pytest `tests/unit/test_intent_owners.py::test_s3` — Advisory approval.
- S4: pytest `tests/unit/test_intent_owners.py::test_s4` — Silent solo approval.
- S5: pytest `tests/unit/test_intent_owners.py::test_s5` — Rendered guidance.

## Acceptance Criteria
### AC-001: Role shapes
Matches S1; golden expectations are the handoff requirements above.
### AC-002: Role validation
Matches S2; golden expectations are the handoff requirements above.
### AC-003: Advisory approval
Matches S3; golden expectations are the handoff requirements above.
### AC-004: Silent solo approval
Matches S4; golden expectations are the handoff requirements above.
### AC-005: Rendered guidance
Matches S5; golden expectations are the handoff requirements above.

## ❓ Open Questions
None for implementation. Approval stamp is deferred; the DRI authorized implementation.

## 🔍 Refinement Decisions
2026-09-21: handoff supplies requirements; execute chooses deterministic normalization in ADR-001.
