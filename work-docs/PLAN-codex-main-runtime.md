---
type: plan
task_slug: codex-main-runtime
status: complete
spec_need_verdict: add
spec_need_target: codex-main-independent
spec: "[[SPEC-codex-main-independent]]"
---

# Codex main runtime: independent foundation delivery

This task worktree delivers only the independent foundation slice described in [[PLAN-codex-main-independent]], plus the operator-authorized inherited test collection repair. The broader Codex main-runtime goal remains open: plugin management, Claude subprocess transport, provider registration and post-absorption workflow integration require follow-up work.

## Delivered scope

- Pure package/engine identity and three-layer update-state helpers.
- Bounded strict Claude result-envelope parsing.
- Unit coverage and research/specification/review evidence.
- Existing land-hold tests aligned with their accepted SPEC; no change to that SPEC or production approval behavior.

## Boundaries

Do not edit the concurrent plan-stage-absorption worktree, shared workflow models/templates, or user installation/configuration. Do not claim live Claude second-opinion integration or plugin installation from these pure helpers.

## Validation

See [[VERIFY-codex-main-independent-2026-09-20]]: full CI gates pass, 9065 tests passed. Detailed review: [[REVIEW-codex-main-independent-2026-09-20]].

This parent task document maps the existing `hm/codex-main-runtime` worktree identity to its independently specified delivery slice; it introduces no new product scope or approval.

Wrapup body verified the fresh full-suite marker, matching clean drift verdict and
six forward-bound mechanical ACs (zero pending or judgment ACs). Complete denotes
this independent delivery slice; SPEC approval and landing remain caller-owned.
