---
generated_by: harness-maker
harness_maker_version: 0.14.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/health.md.j2
provenance: official
content_hash: 5571e73913d60d3424dc3e425a9a3438c7d99bae5a3337e36f74ba54064f9a78
---
# /hm:health

> Three-layer health audit (ADR-002 amended by ADR-006).
> Layer 1 Structural · Layer 2 External risks · Layer 3 Personalization.
> 100% structured-question gated — no auto-apply (ADR-001).

## Layers

| Layer | What it measures |
|-------|------------------|
| `structural`     | ai_readiness 3-layer score (CLAUDE.md, ADRs, frontmatter, etc.) |
| `external_risks` | crawler (anthropic_blog/github/arxiv/osv) + stale assets filtered by LLM relevance |
| `personalization`| ADR-011 rubric: L1 conversion (0.4) + L2 stability (0.3) + L3 cadence (0.3) |

## Run

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.cli health . --json-output .claude/observability/.health.tmp.json
```

Then read `.claude/observability/dashboard.md` to inspect the three sections.

## Per-item structured question (ADR-001 hard rule)

For each unresolved item across the three layers, present:
- **structural**: file-level remediation suggestion (e.g. "add docs/adr/").
- **external_risks**: each pending item with relevance ≥ 0.7 (CVE, breaking-change, stale standard).
- **personalization**: each ADR-011 ActionItem with priority P0/P1.

Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code) per item with three options:
- `accept` → apply the suggested change
- `reject` → record decision, leave alone
- `defer` → keep in queue

Append every answer to `.claude/observability/health/decisions.jsonl`.

Never auto-apply. Never batch into yes/no over multiple items.

## Autoloop behavior

Stop after writing the dashboard. The structured-question step requires
interactive mode; autoloop must not synthesize a default answer.

<!-- @hm:user:extensions -->
<!-- Project-specific /hm:health hooks. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
