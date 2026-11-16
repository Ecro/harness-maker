---
type: plan
task_slug: price-table-current-models
status: complete
created: 2026-11-16
spec: "[[SPEC-price-table-current-models]]"
summary: Three price rows, a long-prompt card for Haiku 5.5 and a wider fallback trace in economics.py; then the 30 recorded tier-1 rows are repriced by formula, the results are republished and the subagent-spend text is corrected.
---

# PLAN — price-table-current-models

- [x] Phase 1 — price table. scope: `src/harness_maker/economics.py`, `src/harness_maker/cache_diagnostics.py` (the shared key matcher), `tests/unit/test_price_table_current_models.py`, `tests/unit/test_economics_pricing.py` (the pinned version label). exit: `uv run pytest tests/unit/test_price_table_current_models.py tests/unit/test_economics_pricing.py tests/unit/test_economics_pure.py tests/unit/test_economics_dedupe.py tests/unit/test_economics_review_fixes.py -q`. risk: a new key shadows an existing id (longest match). rollback: revert the file.
- [x] Phase 2 — record and text. scope: `scripts/bench_light_lane.py` (two sentences, two row fields, one warning), `docs/evals/results.jsonl`, `docs/evals/RESULTS.md`, `README.md` (generated block), `docs/evals/README.md`, `docs/evals/tier3/notes.md`, `specs/SPEC-hm-cost-p5.md`, `specs/SPEC-hm-cost-p4.md`, `specs/SPEC-hm-cost-p3.md`, `specs/SPEC-hm-eval-tier3.md`, `specs/SPEC-hm-light-lane-bench.md`, `src/harness_maker/step_sensitivity.py` (one note), `tests/unit/test_bench_tier3.py`, `tests/unit/test_bench_scripted_dri.py` (the pinned row key set), `.claude/intent/metrics.yaml` (a new record at wrapup), `CHANGELOG.md`. exit: `uv run pytest tests/unit/test_bench_tier3.py tests/unit/test_bench_light_lane.py tests/integration/test_hm_cost_p5_bar.py tests/integration/test_hm_cost_p4_bar.py tests/integration/test_hm_cost_p3_bar.py -q`. risk: a bar test of an older SPEC pins a number that moves. rollback: `git checkout` the data and docs.

## 🚧 Contract Boundaries

### Do not change

- docs/evals/history/hm-cost-p2.jsonl
- docs/evals/history/hm-cost-p3.jsonl
- docs/evals/history/hm-cost-p4.jsonl
- docs/evals/tier3/pilot/results.jsonl
- docs/evals/tier3/diagnostic/results.jsonl
- specs/SPEC-hm-eval-tier3.machine.yaml

## Decisions

ADR-001: The trace for a point release priced by an older row reuses `priced_with_family_row` and the report's `family_priced_*` fields; no new field. **Decided by:** agent
ADR-002: "A further version number" is a hyphen and one or two digits right after the matched key, not followed by a digit. **Decided by:** agent
ADR-003: Haiku 5.5's long-prompt card lives in a second table keyed by row name; `ModelPrice` keeps its shape. **Decided by:** agent
ADR-004: Only `docs/evals/results.jsonl` is repriced, by `old − cache_read × 0.10/1e6`, with the old value kept as `transcript_cost_usd_table_v3`; history and tier-3 rows stay as recorded. **Decided by:** agent
ADR-005: `specs/SPEC-hm-eval-tier3.machine.yaml` is not edited; this SPEC's AC-007 supersedes the cost-note sentence of its AC-010 and the test keeps its node id. **Decided by:** agent
ADR-006: A price-table key that ends in a digit does not match right before another digit (`economics.model_key_end`, shared with `cache_diagnostics`), so `fable-5-2` cannot capture a dated Fable 5 id; found in review. **Decided by:** agent
ADR-007: A bench row records `price_table_version` and `family_priced_turns`, and the run warns on a family-priced turn; the verdict rule and `MIXED_FIELDS` are unchanged. **Decided by:** agent
