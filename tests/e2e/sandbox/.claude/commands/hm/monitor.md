---
generated_by: harness-maker
harness_maker_version: 0.2.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/monitor.md.j2
provenance: official
content_hash: c12b4fbff532ceed89daa1cc759668411af7b5b3d7abedef624682ad69aded5a
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
