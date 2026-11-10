---
type: spec
task_slug: readme-slogan
status: approved
created: 2026-11-10
tags: [harness-maker, spec, docs, readme]
test_framework: pytest
interview_rounds: 0
intent: UNDERSTANDING-HANDOFF
summary: "Add the slogan pre-registered for UNDERSTANDING-HANDOFF met to both READMEs, and replace their stale 'not shipped yet' line about the wrapup understanding summary."
---

# SPEC — readme-slogan

## Intent

UNDERSTANDING-HANDOFF closed as met (8/10, PR #61). Its pre-registered rule makes adding the README
slogan "Automate the work. Elevate the engineer." a separate task; the DRI said to proceed. Both
READMEs also still say the understanding summary is "not shipped yet".

## Outcomes

- O1. Both READMEs carry "Automate the work. Elevate the engineer." directly under the tagline.
- O2. Neither README says the understanding summary is unshipped.

## In-Scope Scenarios

- **S1 (normal).** Given README.md and README.ko.md, When read, Then the slogan sits under the
  tagline and the Human-owned row describes the shipped `Understanding:` block.

## Non-Goals

- No other README rewrite; no change to the brand image.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Doc contract | README marker sections unchanged | `documentation_contract.py` |

## Irreversible Decisions

None. Documentation only.

## Acceptance Criteria

### AC-001: both READMEs carry the slogan and no stale not-shipped line
README.md and README.ko.md each contain "Automate the work. Elevate the engineer." before the
`> **Version**:` line, and neither contains "Not shipped yet" or "아직 출하 전".

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | `tests/unit/test_readme_slogan.py` (AC-001) |

## Open Questions

None.

## Refinement Decisions

- Skip check: two docs, acceptance obvious, no API or format change, reversible in minutes;
  one mechanical AC. The slogan stays English in the Korean README (it is a fixed slogan).
