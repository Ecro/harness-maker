---
type: spec
task_slug: docs-rewrite
status: approved
created: 2026-11-10
tags: [harness-maker, spec, docs, overhaul-phase-2]
test_framework: pytest
interview_rounds: 0
summary: "Item 5: rewrite HOW-IT-WORKS (en/ko) for the four-stage 0.64+ workflow, and remove the stale lines about deleted modules from ARCHITECTURE, CONTRIBUTING, README and two reference docs."
---

# SPEC — docs-rewrite (item 5 of RESEARCH-hm-non-token-improvements)

## Intent

`docs/HOW-IT-WORKS{,.ko}.md` (3,055 and 2,590 lines) still describe the seven-stage workflow: whole
sections for `hm:loop`, `hm:review`, `hm:verify`, autopilot and the `stuck` agent, with a banner
saying those parts are "a record". A reader cannot tell what runs today. Phase 2 slices 1–2 also
deleted modules that ARCHITECTURE, CONTRIBUTING and two reference docs still list. This rewrite
makes the living docs describe only what ships, and points to CHANGELOG and ARCHITECTURE for the
history.

## Outcomes

- O1. Each HOW-IT-WORKS locale has one section per live stage (`/hm:research`, `/hm:spec`,
  `/hm:execute`, `/hm:wrapup`), plus `hm check`, Maker, worktrees, agents, skills, hooks, memory,
  second opinion, other commands, key settings, and one short "Retired in 0.64.0" list.
- O2. No HOW-IT-WORKS heading gives a retired command, autopilot or a retired agent a live section.
- O3. CONTRIBUTING's layout, ARCHITECTURE's M17 and version-drift lines, README's digest list and
  example `harness.yaml`, `autoloop-pattern.md` and `block-merge-spec.md` no longer present a
  deleted module as present.
- O4. The doc contract (`documentation_contract.validate_repository`) and every existing doc pin
  still pass.

## In-Scope Scenarios

- **S1 (normal).** Given either HOW-IT-WORKS locale, When its headings are read, Then each live
  stage has one.
- **S2 (edge).** Given either locale, When searched for a heading naming `hm:loop`, `hm:review`,
  `hm:verify`, the old "6 Atomic" stages, Autopilot or the `stuck` escalation, Then none is found.
- **S3 (failure guard).** Given CONTRIBUTING, `autoloop-pattern.md` and both HOW-IT-WORKS files,
  When searched for a deleted module name, Then none is found.

## Non-Goals

- The dated snapshot files (`HISTORICAL_DOC_FILES`, e.g. `multi-session-worktree.md`,
  `reviewer-fanout.md`) stay verbatim: they are the recorded why, and
  `test_claude_md_relocation` pins them.
- `TECH_SPEC.md` (the original build spec) is not rewritten.
- No code change.

## Constraints

| Constraint | Value | Source |
|---|---|---|
| Test framework | pytest (mandatory) | CLAUDE.md |
| Doc contract | marker sections, version line and pinned phrases kept | `documentation_contract.py`, `test_documentation_contract.py` |
| Anchors | `#render-pipeline` / `#렌더-파이프라인` stay | `test_docs_render_pipeline.py` |

## Irreversible Decisions

None. Documentation only.

## Acceptance Criteria

### AC-001: living docs describe the four live stages and no deleted module
Both HOW-IT-WORKS locales have a heading naming each of the four stage commands and no heading
for a retired piece; CONTRIBUTING, `autoloop-pattern.md` and both HOW-IT-WORKS files name none of
`foreign_config.py`, `provenance.py`, `relevance.py`, `templates/foreign-configs`.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1, S2, S3 | unit | `tests/unit/test_docs_rewrite.py` (AC-001) |
| O4 | unit | existing `tests/structural/test_documentation_contract.py` and doc pins |

## Open Questions

None.

## Refinement Decisions

- No interview: documentation only, no contract change, reversible in minutes; the DRI told this
  thread to proceed on recommendations without asking.
- A rewrite, not an edit: the old guide is 85% retired material, so editing would keep the
  structure that makes it misleading. History stays in CHANGELOG and ARCHITECTURE.
