# Architecture Decision Records — harness-maker

## Convention

ADRs in this project live in two places:

1. **PLAN-scoped ADRs** — live inline in `work-docs/PLAN-*.md` files,
   numbered per-PLAN (e.g. `ADR-001`, `ADR-002` inside `PLAN-personalization-depth-2026-05`).
   The numbers reset between PLANs; cross-PLAN references take the form
   `(W2/ADR-002)` or `(PLAN-foo-ADR-006)`.
2. **Cross-PLAN ADRs** — promoted into this directory when a decision
   spans multiple PLANs or governs the whole project. Numbered globally
   `NNNN-kebab-title.md` starting at `0001`.

## Why this split exists

Most ADRs in harness-maker are tightly coupled to a single PLAN and
its phase task list. Promoting all of them globally would lose context
and inflate the index. Cross-PLAN ADRs (e.g. the locked rubric for
personalization, the structured-question hard rule for /hm:health) are
the ones that other PLANs and the CLI rely on, so they get a stable
home here.

## Index

| ADR | Title | Source / Promoted from |
|-----|-------|------------------------|
| [0001](0001-structured-question-gated-health.md) | Structured-question gating for /hm:health (no auto-apply) | `.claude/commands/hm/health.md` rule |
| [0002](0002-three-layer-ai-readiness-rubric.md) | Three-layer AI-readiness rubric (deterministic + LLM + cache) | `skills/ai-readiness-rubric/` |
| [0006](0006-three-layer-health-audit.md) | Three-layer health audit (amends ADR-0002) | Promoted from `PLAN-health-consolidation` |
| [0011](0011-personalization-rubric-locked-v0.md) | Personalization rubric v0 (L1 + L2 + L3 + composite + tier) | Promoted from `PLAN-personalization-depth-2026-05` |

## Adding a new cross-PLAN ADR

1. Pick the next free number (zero-padded to 4 digits).
2. Create `NNNN-kebab-title.md` with the template below.
3. Add a row to the index.
4. Update the source PLAN to point here (`→ docs/adr/NNNN`).

```markdown
# ADR-NNNN: <Title>

- **Status**: accepted | superseded by ADR-XXXX
- **Date**: YYYY-MM-DD
- **Source PLAN**: `work-docs/PLAN-...`

## Context

<one paragraph: what forced the decision>

## Decision

<the rule, stated as a rule>

## Consequences

- positive: ...
- negative: ...

## References

- ...
```
