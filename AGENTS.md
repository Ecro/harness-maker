<!-- harness-maker: content_hash=d99d8c758f8314bf07d65fc7ee7ccc2a1c508640289793bc7e1bf6cb94cf464a version=0.9.0 generated_at=2026-05-10T11:10:08.647564+00:00 -->
# AGENTS.md — Production preset

> harness-maker task-driven mode. Edit the user blocks below to add project-specific rules.

## Workflow

Default: `@hm-exec-rev-wrap-ver` skill — invokes the fused workflow that chains atomic stages.

Run individual stages: `@hm-research`, `@hm-spec`, `@hm-plan`, `@hm-execute`, `@hm-review`, `@hm-verify`, `@hm-wrapup`.

## Reviewers

verbosity: `standard` — code, security, performance, concurrency, and UX reviewers available.

## Caching

`agent-aware` — per-agent prompt cache + session cache.

## Autoloop / Worktree

autoloop / worktree toggles live in `.claude/harness.yaml`.

<!-- @hm:user:project-rules -->
<!-- Project-specific rules (coding style, domain terms, agent invocation conventions). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:project-rules -->

<!-- @hm:user:extensions -->
<!-- Free-form AGENTS.md additions. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
