---
type: spec
task_slug: tpl-wiki-ko-md
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- template
- skeleton
test_framework: pytest
parent_spec: SPEC-templates
summary: Auto-generated skeleton SPEC for template feature tpl-wiki-ko-md.
---

## 🎯 Intent

`src/harness_maker/templates/memory/wiki.ko.md.j2` provides the **tpl-wiki-ko-md** template feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of tpl-wiki-ko-md can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: rendered output snapshot-stable (Layer 1)

**Given** the feature is loaded under default configuration
**When** the contract surface of tpl-wiki-ko-md is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

### AC-002: rendered output parses under consumer schema (Layer 2)

**Given** the feature is loaded under default configuration
**When** the contract surface of tpl-wiki-ko-md is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

### AC-003: rendered prompt fulfills SPEC intent (Layer 3, LLM-judged)

**Given** the feature is loaded under default configuration
**When** the contract surface of tpl-wiki-ko-md is exercised
**Then** AC (judgment) holds per its predicate / table / rubric

## 🚫 Non-Goals

- Cross-feature integration (covered by sibling SPECs)
- UX-only concerns (covered by user-facing documentation)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | project default |

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | unit (predicate) | (pending — backfill in P5 batch) |
| AC-002 | unit (predicate) | (pending — backfill in P5 batch) |
| AC-003 | LLM judge (rubric) | (pending — backfill in P5 batch) |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=templates, tier=3, kind=template).

## 🔗 Machine Spec

See [SPEC-tpl-wiki-ko-md.machine.yaml](./SPEC-tpl-wiki-ko-md.machine.yaml).
