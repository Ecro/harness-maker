---
generated_by: harness-maker
harness_maker_version: 0.4.8
generated_at: '2026-01-01T00:00:00+00:00'
source_template: observability/dashboard.md.j2
provenance: official
content_hash: b4570b96aa7bacf396b079f45d1fe03a91bb0e8e85245b061469bca4d4645efd
---
# AI Readiness Dashboard

**Project:** unknown
**Preset:** Production

> This file is re-rendered every time `/hm:ai-readiness` runs.
> The composite, layer breakdown, and ranked action list below reflect the
> most recent scan.

## Composite

Run `/hm:ai-readiness` to populate this section.

## Layer scores

| Layer | What it measures |
|-------|------------------|
| readiness | Deterministic structural signals (CLAUDE.md, hooks, tests, CI, …) |
| llm_judge | LLM-judged content quality vs `.claude/rubrics/*.yaml` |
| cache | Prompt-cache hit rate + failure-mode diagnosis from `metrics.jsonl` |

## Actions

Run `/hm:ai-readiness` to populate the actions table.

<!-- @hm:user:extensions -->
<!-- Project-specific dashboard panels (KPIs, external dashboard links, etc.). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
