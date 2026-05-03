---
generated_by: harness-maker
harness_maker_version: 0.3.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/ai-readiness-rubric/SKILL.md.j2
provenance: official
name: ai-readiness-rubric
description: Compute the Health 6-dimension composite score (docs, tests, CI, observability,
  security, governance) for a project. Use when /hm:monitor renders the dashboard
  or /hm:verify needs a baseline comparison. Calls harness_maker.readiness.compute_health.
content_hash: bcbcec6cf3c24ac12ccf6363e4ca275c4063707dd156f3214048a4118c289df3
---

# ai-readiness-rubric

The Health 6-dim scoring rubric. Maps repo signals to a 0-100 composite
score with per-dimension drill-down. Side preset uses 5 dims (governance
= 0 weight); Production uses all 6 with rebalanced weights.

## When to Invoke

- `/hm:monitor` rendering the observability dashboard
- `/hm:verify` Check 3 (Health 점수 -5 이내) baseline comparison
- Anti-rot freshness gauge cross-checking against repo health

## The 6 Dimensions

| Dim | Side weight | Prod weight | Signal source |
|---|---|---|---|
| docs | 0.20 | 0.15 | CLAUDE.md, README.md, docs/adr/*.md |
| tests | 0.30 | 0.25 | tests/ dir, coverage report |
| ci | 0.20 | 0.15 | .github/workflows/*.yml jobs |
| observability | 0.15 | 0.15 | .claude/observability/dashboard.md, metrics.jsonl |
| security | 0.15 | 0.20 | findings.jsonl, settings.json permissions deny list |
| governance | 0.00 | 0.10 | CHANGELOG.md, CONTRIBUTING.md, ADR count |

## Implementation

```python
from pathlib import Path
from harness_maker.readiness import compute_health
from harness_maker.models import Preset

result = compute_health(Path("."), Preset.PRODUCTION)
# {
#   "composite": 78,
#   "dimensions": {
#     "docs": 90, "tests": 75, "ci": 80,
#     "observability": 60, "security": 85, "governance": 70
#   },
#   "preset": "Production"
# }
```

The function is pure (no IO beyond reading the project dir), deterministic,
and safe to call from the statusline tick.

## Scoring Conventions

- Each dim is 0-100 internally; weights sum to 1.0 → composite is 0-100
- Missing signal = dim score 0 (don't crash)
- New project (no CI yet) starts low; that's the point — Health is a
  pressure gauge, not a moral judgment

## Bronze-Tier Auto-Refresh

When the composite drops to Bronze (≤ 60), the agent-quality-rubric
sibling skill auto-registers an anti-rot patch candidate (see that skill).
This skill reports the drop; it does not patch.

## Output

A dict matching `compute_health(...)` return shape. Consumers
(dashboard, verify gate) format it for their context.

<!-- @hm:user:extensions -->
<!-- Project-specific dimension weights or extra signals. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
