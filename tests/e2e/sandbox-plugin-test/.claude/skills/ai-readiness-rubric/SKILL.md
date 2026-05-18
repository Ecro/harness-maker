---
generated_by: harness-maker
harness_maker_version: 0.17.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/ai-readiness-rubric/SKILL.md.j2
provenance: official
name: ai-readiness-rubric
description: 3-layer rubric scoring AI-readiness — Layer 1 deterministic structural
  signals, Layer 2 LLM-judged content quality vs rubric YAMLs, Layer 3 prompt-cache
  failure-mode classification. Invoked by /hm:health Step 1 (structural layer).
content_hash: 752821a90419f28cf346ca5be6c3964a16807db4f82184875092ad75c8e1069e
---

# ai-readiness-rubric

Composite ai-readiness rubric. Three layers, distinct evidence types,
folded into a single 0-100 score plus a ranked list of actionable items.


## Communication Protocol

- Be direct. No flattery, no preamble, no "Great question!"
- Lead with concerns before agreement; when you agree, explain WHY with specific reasoning.
- Do not fold on pushback unless new evidence is presented.
- Fabrication is the cardinal sin: every claim cites file:line or is labeled as inference.
- Surface disagreements verbatim — never average findings into mush.

<!-- @hm:communication_variant: full -->


## When to invoke vs skip

**Invoke when:**
- `/hm:health` Step 1 (structural layer) computes the 3-layer composite score.
- A regression check after a major harness change to confirm Health did not drop.

**Skip when:**
- A score from less than 1h ago is still valid (no harness changes since).
- The user only wants Layer 1 (deterministic) — the rubric loader supports a layer-only mode.
## When to Invoke

- `/hm:health` Step 1 — full scan (terminal summary + dashboard.md `structural` section update)
- `/hm:verify` — Layer 1 composite as the baseline-comparison gate

## Layers

| Layer | Module | What it checks |
|---|---|---|
| 1 readiness | `harness_maker.readiness` | 7 deterministic dimensions: context_quality, guardrails, verification, workflow_clarity, memory_continuity, observability_setup, governance. Each dim decomposes into yes/no signals with weighted contribution. |
| 2 llm_judge | `harness_maker.llm_judge` | Rubric YAMLs at `.claude/rubrics/*.yaml`. LLM evaluates each rubric pass/fail with evidence + tailored suggestion. P0/P1/P2 severity weights (3/2/1) drive per-file score. System prompt cached. |
| 3 cache | `harness_maker.cache_diagnostics` | `metrics.jsonl` analysis. Classifies miss reasons: `min_threshold` (prefix < cache-write min), `invalidation` (prefix mutated), `ttl` (>5min gap), `first` (expected). |

## Composite

```
final = 0.70 * readiness  +  0.25 * llm_judge_avg  +  0.05 * cache
```

## Entry point

```python
from harness_maker.ai_readiness import run_ai_readiness
plan = run_ai_readiness(Path("."), preset=Preset.SIDE)
```

Returns `ImprovementPlan` with `composite_score`, `layer_scores`, and a
priority-sorted `actions` list. Each `ActionItem` has priority, dimension,
target file/area, summary, detail (evidence), and suggestion (how to fix).

## Extension

Drop additional rubric YAMLs into `.claude/rubrics/`; they're picked up
automatically. Shipped rubrics are preserved across upgrades.

<!-- @hm:user:extensions -->
<!-- Project-specific dimension weights or extra signals. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
