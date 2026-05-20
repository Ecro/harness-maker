---
type: spec
task_slug: crawler
status: verified-skeleton
created: 2026-05-20
tier: 2
tags:
- harness-maker
- spec
- l1-cluster
- skeleton
test_framework: pytest
summary: L1 cluster invariants for Anti-rot crawler (anthropic_blog/arxiv/github/osv).
---

## 🎯 Intent

L1 cluster `crawler` groups member L2 SPECs sharing invariants.

## 🌅 Outcomes

All L2 children pass their per-feature gates AND respect this cluster's invariants.

## 📋 In-Scope Scenarios

### AC-001: cluster invariants hold across members

**Given** every L2 member of cluster `crawler`
**When** their AC are evaluated
**Then** the cluster-level invariant predicate holds

## 🚫 Non-Goals

- Member-specific AC (lives in L2 SPECs)

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | pytest | default |

## ✅ Verification Criteria

| Scenario | Verification mode | Test reference |
|---|---|---|
| AC-001 | aggregated unit | (pending — P5 cluster batch) |

## ❓ Open Questions

(L1 stub — refine in cluster's first P5 batch.)

## 🔍 Refinement Decisions

- 2026-05-20: L1 stub seeded by `batch_generator`.

## 🔗 Machine Spec

See [SPEC-crawler.machine.yaml](./SPEC-crawler.machine.yaml).
