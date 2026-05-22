# ADR-0006: Three-layer health audit (amends ADR-0002)

- **Status**: superseded by [ADR-0007](0007-two-layer-health-audit.md) (2026-05-22)
- **Date**: 2026-05-17 (extracted into `docs/adr/` from PLAN-health-consolidation)
- **Source PLAN**: `work-docs/PLAN-health-consolidation` (commit 82eaddb)

## Reversal rationale (2026-05-22)

A 2026-05-22 production run of `/hm:health` surfaced 12 items via the
external_risks layer (4-source crawl × LLM relevance × adaptive threshold);
1 was already known (Claude Opus 4.7 — already pinned), 11 were rejected.
91% noise. The per-item AskUserQuestion contract (this ADR's hard rule)
made the noise interruptive. The user requested an honest evaluation;
`/hm:research` surfaced full demolition as the cleanest path.

ADR-0007 (2026-05-22) supersedes this decision: `/hm:health` collapses to
2 layers (structural + personalization). CVE coverage (the one
external_risks source with rare-but-critical value) survives via
`secscan/dependency_cves.py` consumed by `/hm:verify`. See
`work-docs/PLAN-hm-health-crawl-removal.md` for the execution plan and
ADR-0007 for the full new-decision body.

The original ADR-0006 decision body below remains as historical record.

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
