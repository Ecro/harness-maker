---
generated_by: harness-maker
harness_maker_version: 0.20.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/health.md.j2
provenance: official
content_hash: 8043f244b91b8091d3c61b67e2ffc0fc052912bd8f40002224d9c3f7ed35c2a5
---
# /hm:health

> Three-layer health audit (ADR-002 amended by ADR-006).
> Layer 1 Structural · Layer 2 External risks · Layer 3 Personalization.
> 100% structured-question gated — no auto-apply (ADR-001).

## Layers

| Layer | What it measures |
|-------|------------------|
| `structural`     | ai_readiness 3-layer score (CLAUDE.md, ADRs, frontmatter, etc.) + `silent_intent_miss_rate` sub-check |
| `external_risks` | crawler (anthropic_blog/github/arxiv/osv) + stale assets filtered by LLM relevance |
| `personalization`| ADR-011 rubric: L1 conversion (0.4) + L2 stability (0.3) + L3 cadence (0.3) |

### Layer 1 sub-check — `silent_intent_miss_rate` (ADR-008)

Reads `.claude/observability/silent-intent-miss-*.jsonl` audit logs (one per
task slug; appended by `harness_maker.observability.intent_miss.record_intent_miss`
when REVIEW flags mis-specification on a slot previously marked common-ground
at LLM-inference ≥ 0.95, or when a user reopens such a slot in-session).

Compute `silent_intent_miss_rate = miss_events / common_ground_marks_total` and
surface as a Layer 1 ActionItem when rate exceeds the calibrated threshold.
Initial default = `0.10` (10% miss); this is narrative-only for the first
release pending telemetry-driven calibration — promote to
`harness.yaml.observability.silent_intent_miss_threshold` when post-ship data
justifies a different value. When triggered, the suggested remediation is
either raising `interview.deep_gate.common_ground.llm_inference_threshold` or
flipping the ADR-012 kill-switch (`llm_inference_enabled: false`).

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
