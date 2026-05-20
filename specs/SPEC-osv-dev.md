---
type: spec
task_slug: osv-dev
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
summary: Auto-generated skeleton SPEC for python feature osv-dev.
---

## 🎯 Intent

`src/harness_maker/crawler/osv_dev.py` provides the **osv-dev** python feature. This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.

## 🌅 Outcomes

Consumers of osv-dev can rely on the AC below holding under the SPEC's verification regime.

## 📋 In-Scope Scenarios

### AC-001: OSV.dev CVE crawler — POSTs package specs to ``https://api.osv.dev/v1/query``

**Given** the feature is loaded under default configuration
**When** the contract surface of osv-dev is exercised
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
| AC-001 | unit (predicate) | tests/unit/crawler/test_osv_dev.py::test_crawl_handles_http_error, tests/unit/crawler/test_osv_dev.py::test_crawl_returns_vulnerabilities, tests/unit/crawler/test_osv_dev.py::test_crawl_with_no_packages_returns_empty |

## ❓ Open Questions

(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` to fill AC depth + open questions.)

## 🔍 Refinement Decisions

- 2026-05-20: skeleton SPEC seeded by `batch_generator` (parent=crawler, tier=3, kind=python).

## 🔗 Machine Spec

See [SPEC-osv-dev.machine.yaml](./SPEC-osv-dev.machine.yaml).