---
type: spec
task_slug: context-lint
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-configuration-manifests
summary: Auto-generated skeleton SPEC for python feature context-lint.
---

## 🎯 Intent

`src/harness_maker/context_lint.py` provides the **context-lint** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of context-lint can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: Context Lint — flag verbose files and context window overuse

**Given** the feature is loaded under default configuration
**When** the contract surface of context-lint is exercised
**Then** AC (mechanical) holds per its predicate / table / rubric

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
| AC-001 | unit (predicate) | tests/unit/test_context_lint.py::test_agents_md_html_comment_excluded_from_count, tests/unit/test_context_lint.py::test_at_threshold_returns_no_warnings, tests/unit/test_context_lint.py::test_frontmatter_excluded_from_count |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=configuration-manifests, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-context-lint.machine.yaml](./SPEC-context-lint.machine.yaml).