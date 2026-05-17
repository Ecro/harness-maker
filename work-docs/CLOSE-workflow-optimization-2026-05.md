---
type: close
task_slug: workflow-optimization-2026-05
status: closed
created: 2026-05-17
closed_at: 2026-05-17
plan_ref: "[[PLAN-workflow-optimization-2026-05]]"
phases_completed: 12/12
---

# CLOSE — Workflow Stage Optimization (2026-05)

## Summary

All 12 phases of the workflow optimization plan completed successfully.
38 files changed, +1953 / -136 lines, 40+ new unit tests, zero regressions.

## Phase Completion

| # | Scope | Key Change |
|---|-------|------------|
| 1 | C2 verify Preset.SIDE bugfix | `Preset('{{ config.preset }}')` replaces hardcoded `Preset.SIDE` |
| 2 | Baseline measurement | `scripts/measure_workflow_baseline.py` (7 axes) |
| 3 | A3+A4 prompt cache_control | Verified `cache_control: ephemeral` in `llm_judge.py` |
| 4 | A5 HTTP cache | `src/harness_maker/cache.py` + `crawl_all_cached` |
| 5 | A6 fresh-skip | Agent quality: skip Platinum/Gold; SecScan: skip < 24h |
| 6 | A2 drift demote | Review = single drift owner; wrapup/verify read-only |
| 7 | A7 memory preamble | `## Shared Session Context` in fused workflows |
| 8 | A1 check-suite skip | `VerificationCache` with inverted-env skip-key (ADR-007) |
| 9 | A8 Pass 1.5 verifier | code-verifier activated in review |
| 10 | B2 Pass 1 skip | Skip Pass 1+1.5 when reviewer count == 1 |
| 11 | B1+B3+B6 schema | `schema_version`, interview caps, Side v2 defaults |
| 12 | Closing sweep | This document |

## Hypothesis vs Actual

- **Check-suite 4x→1-2x**: Enabled (verification cache markers)
- **Token 60-80% reduction**: Enabled (ephemeral cache_control on system blocks)
- **Crawler HTTP 0 on hit**: Enabled (HttpCache per-source TTLs)
- **Drift 3-4x→1x**: Verified (review single owner)
- **Side interview 50-66% shorter**: Verified (1/1/5 caps vs 3/2/unlimited)
