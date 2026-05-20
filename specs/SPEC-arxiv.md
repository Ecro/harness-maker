---
type: spec
task_slug: arxiv
status: verified-skeleton
created: 2026-05-20
tier: 3
tags:
- harness-maker
- spec
- python
- skeleton
test_framework: pytest
parent_spec: SPEC-crawler
summary: Auto-generated skeleton SPEC for python feature arxiv.
---

## 🎯 Intent

`src/harness_maker/crawler/arxiv.py` provides the **arxiv** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of arxiv can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: arxiv crawler — uses ``feedparser`` against the public Atom query API

**Given** the feature is loaded under default configuration
**When** the contract surface of arxiv is exercised
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
| AC-001 | unit (predicate) | tests/unit/crawler/test_arxiv.py::test_crawl_returns_empty_on_parser_error, tests/unit/crawler/test_arxiv.py::test_crawl_returns_items_from_mocked_feed, tests/unit/crawler/test_arxiv.py::test_crawl_skips_entries_missing_required_fields |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=crawler, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-arxiv.machine.yaml](./SPEC-arxiv.machine.yaml).