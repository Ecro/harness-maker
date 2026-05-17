# ADR-0001: Structured-question gating for /hm:health (no auto-apply)

- **Status**: accepted
- **Date**: 2026-05-17 (extracted into `docs/adr/` from existing rule)
- **Source**: `.claude/commands/hm/health.md` ("100% structured-question gated — no auto-apply (ADR-001)")

## Context

The health audit surfaces actionable items across three layers
(structural · external risks · personalization). Auto-applying every
suggested remediation would let the LLM make load-bearing edits
(permission changes, file deletions, harness reconfigurations) with no
user intent recorded. Past experience with auto-apply loops in adjacent
tools showed the same pattern: an LLM accepts a noisy rubric finding,
edits the file, the user inherits the edit silently, and the next
audit run cannot tell what was deliberate vs. drift.

## Decision

Every unresolved health item — whether structural, external-risk, or
personalization — MUST be presented to the user via a per-item
structured question (`AskQuestion` in Cursor, `AskUserQuestion` in
Claude Code) offering three options:

- `accept` — apply the suggested change now
- `reject` — record decision, leave file untouched
- `defer` — keep in queue for re-surface on next run

Hard rules:

- One question per item. Never batch multiple items into a single
  yes/no question.
- Never auto-apply, even if the suggestion is obviously safe.
- Every answer (including `reject` and `defer`) is appended to
  `.claude/observability/health/decisions.jsonl` with timestamp,
  layer, signal, and decision.
- In autoloop / non-interactive mode, the orchestrator writes the
  dashboard and stops; it must not synthesize default answers.

## Consequences

- positive: every audit-driven file change has an explicit user-intent
  record; rejected items stay rejected; deferred items resurface.
- positive: the decisions log is a forensic trail for "why did this
  signal stop firing" questions.
- negative: a long action list means many AskQuestion turns. Mitigated
  by tools that allow batching up to 4 questions per turn (still 1
  question per item).

## References

- `.claude/commands/hm/health.md`
- `.claude/observability/health/decisions.jsonl`
