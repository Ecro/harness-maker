# ADR-0006: Three-layer health audit (amends ADR-0002)

- **Status**: accepted (amends [ADR-0002](0002-three-layer-ai-readiness-rubric.md))
- **Date**: 2026-05-17 (extracted into `docs/adr/` from PLAN-health-consolidation)
- **Source PLAN**: `work-docs/PLAN-health-consolidation` (commit 82eaddb)

## Context

Before 0.13.0 there were three separate audit slash commands:
`/hm:ai-readiness`, `/hm:refresh`, and `/hm:personalization-audit`.
Each had its own dashboard, its own cadence guidance, and its own
decisions log. Users had to remember which to run when, and the
overlap (e.g. anti-rot crawl results affecting AI-readiness scoring)
was implicit.

## Decision

Consolidate the three audits into a single `/hm:health` slash command
that surfaces a unified dashboard with three sections:

| Layer | What it measures | Source |
|-------|------------------|--------|
| `structural`     | AI-readiness 3-layer score (per ADR-0002) | `harness-maker health --json-output` (Layer 1) |
| `external_risks` | crawler (anthropic_blog / github / arxiv / osv) + stale assets filtered by LLM relevance | `research-crawler` skill + `relevance-filter` skill |
| `personalization`| ADR-0011 rubric: L1 conversion (0.4) + L2 stability (0.3) + L3 cadence (0.3) | `harness_maker.personalization_audit` |

`/hm:health` is the single entry point. The legacy
`/hm:refresh` and `/hm:ai-readiness` skill triggers remain registered
for backward compatibility but route to the consolidated flow.

Per-item structured-question gating from
[ADR-0001](0001-structured-question-gated-health.md) applies across
all three layers — no auto-apply at any layer.

## Consequences

- positive: one command, one dashboard, one decisions log
  (`.claude/observability/health/decisions.jsonl`).
- positive: cross-layer signals (e.g. a CVE finding in `external_risks`
  that also lowers `structural` guardrails coverage) can be reasoned
  about together.
- negative: existing user habits and bookmarks for the three legacy
  commands need a transition window. Mitigated by leaving the legacy
  command files orphan-swept-but-preserved until the next major bump.

## References

- `.claude/commands/hm/health.md`
- `src/harness_maker/cli.py` (`health` and `health-finalize` subcommands)
- Commit 82eaddb (`feat(0.13.0): consolidate audit commands into /hm:health`)
