# SPEC Coverage Matrix

Generated 2026-05-20 by `harness_maker.spec_inventory.batch_generator` +
refined by `harness_maker.spec_inventory.batch_refiner` per PLAN-total-spec-coverage P5.

## Aggregate

| metric | value |
|---|---|
| **Total SPECs** | **174** |
| L1 cluster SPECs | 15 |
| L2 feature SPECs | 159 |
| Schema validate | 174 / 174 green |
| 6-rule cross_validate | 174 / 174 green |
| Tier-1 | 3 (render, synthesize, agent-code-reviewer) |
| Tier-2 | 29 |
| Tier-3 | 142 |
| AC titles refined from module docstring | 83 / 174 (47.7%) |
| **test_ids resolved via pytest --collect-only** | **203 / 208 (97.6%)** |
| SPECs with ≥ 1 verified test_id | **69** |
| spec_quality scores persisted (T1+T2) | 32 |

## spec_quality scores (heuristic mode)

T1 (3 features):
- `render` — **87** ✓ (≥85 gate)
- `synthesize` — **84**
- `agent-code-reviewer` — **68**

T2 average: **74.2** (1/29 ≥ 85 currently)

Heuristic mode under-scores `testability` dim (40 baseline) because skeleton
SPECs use generic phrasing. LLM-judge wiring (INTEGRATION=1 follow-up) will
re-score with semantic understanding.

## Mutation baseline (P0.5)

| module | baseline | tier | computed_threshold | status |
|---|---|---|---|---|
| `cache.py` | **3.8%** (1 killed / 26 of 52 completed in 5-min sample) | T2 (floor 70%) | **70%** | measured — large gap to floor, test backfill needed |
| `render.py` | — | T1 (floor 85%) | **85%** | pending (~hours of wall-clock; deferred to nightly CI) |

Tool: mutmut 2.5.1 pinned (3.x removed `--paths-to-mutate`). Per ADR-005 formula `max(measured_baseline_pct + 5pp, tier_floor)`.

## Layer status

| Layer | Status |
|---|---|
| Schema validation | **green for all 174** |
| Cross-validation (6-rule) | **green for all 174** |
| test_id resolution (`pytest --collect-only`) | **97.6%** (203/208) |
| `spec_quality` heuristic | recorded on T1+T2 (32 SPECs) |
| `spec_quality` LLM-judge ≥ 0.85 | pending INTEGRATION=1 wiring |
| Mutation gate | 1/2 pilot measured; framework validated |
| 3-layer non-Python (snapshot + schema + LLM) | pending per-feature P5 batch enrichment |

## P5 batch state

- BatchSpecState: **174 / 174 complete**
- Total batches processed: 18
- `work-docs/p5-batch-state.yaml` archives status per feature

## Loop artifacts

- `work-docs/PLAN-total-spec-coverage.md` — source PLAN (798 lines, 13 ADRs)
- `work-docs/loop-context/total-spec-coverage.yaml` — initial /hm:loop context
- `work-docs/loop-context/p5-batch-all.yaml` — P5 refinement loop context
- `work-docs/REVIEW-total-spec-coverage-2026-05-20.md` — 4-reviewer findings + 10 fixes applied
- `work-docs/spec-framework-v1.1-deltas.md` — P4 framework adjustment log
- `work-docs/spec-catalog-2026-05.yaml` — 172 enumerated features + 15 L1 seeds
- `work-docs/spec-catalog-disagreements-2026-05.md` — LLM-vs-heuristic tier disagreements (pending LLM)
- `work-docs/test-inventory-2026-05.json` — 1972 reverse-mapped test entries
- `work-docs/spec-mutation-baseline-2026-05.json` — mutmut baseline + threshold formula

## Worktree

Branch `execute-20260519T1544Z` — 4 commits since main:
1. `f25f368` framework + 6 pilot SPECs
2. `cf9e936` batch_generator + 174 skeleton SPECs
3. `ca6769c` batch_refiner first pass (later corrected for pytest collect bug)
4. (pending merge) batch_refiner re-run + spec_quality scoring + mutmut baseline
