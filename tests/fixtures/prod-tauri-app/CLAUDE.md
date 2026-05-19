---
generated_by: harness-maker
harness_maker_version: 0.17.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: claude-md/Production.en.md.j2
provenance: official
content_hash: 7432d856351787fc797ac14173bc8d3b453b96c1af44c1e70d917e23546d90e0
---
# CLAUDE.md — Production preset

> Phase 3 stub. Phase 6 fills in the locale × preset content.

## Workflow

Default: `/hm:exec-rev-wrap-ver` — a fused workflow that chains atomic stages.

## Reviewers

consensus: `cross-check` — Phase 9 adds the security gate.

## Caching

`agent-aware` — per-agent prompt cache + session cache.

## Autoloop / Worktree

autoloop / worktree toggles live in `harness.yaml`.

<!-- @hm:user:project-rules -->
<!-- Project-specific rules (coding style, domain terms, agent invocation conventions). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:project-rules -->

<!-- @hm:user:extensions -->
<!-- Free-form CLAUDE.md additions. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
