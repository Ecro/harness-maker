---
generated_by: harness-maker
harness_maker_version: 0.3.5
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/monitor.md.j2
provenance: official
content_hash: acf6cec6265ef4739cb6b8e240da2f4917d01030f70d86988f490684c0451e04
---
# /hm:monitor

> Re-render the dashboard with current metrics (효율 + Health + Agent quality).

## Usage

```
/hm:monitor
```

## Arguments

(none)

## Behavior

Reads `.claude/observability/metrics.jsonl`, computes Health 6-dim via
`harness_maker.readiness.compute_health`, scores each agent via
`harness_maker.agent_quality.score_agent`, and re-renders
`.claude/observability/dashboard.md`.

```bash
!uv run python -c "from harness_maker.readiness import compute_health; from harness_maker.agent_quality import score_agent; print('updated')"
```

<!-- @hm:user:extensions -->
<!-- Project-specific monitor extensions (custom panels, additional metrics). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
