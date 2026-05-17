# ADR-0002: Three-layer AI-readiness rubric

- **Status**: accepted (amended by [ADR-0006](0006-three-layer-health-audit.md))
- **Date**: 2026-05-17 (extracted into `docs/adr/` from existing implementation)
- **Source**: `skills/ai-readiness-rubric/`, `src/harness_maker/ai_readiness/`

## Context

A single-number "AI readiness" score is too coarse to be actionable
and too easy to game. Different parts of a project rot at different
rates: structural shape changes when you add files, content quality
changes when you edit prompts, and cache-friendliness changes when
you reshuffle context. Mixing them into one signal hides the diagnosis.

## Decision

AI-readiness is scored as three independent layers, each producing a
0–100 score, with a composite that is the simple mean:

1. **`readiness` (Layer 1, deterministic)** — structural signals
   computed without an LLM: presence of CLAUDE.md, ADRs under
   `docs/adr/`, hooks declared, tests detected, CI workflow present,
   deny patterns cover the dangerous set, observability metrics has
   samples, harness.yaml has memory configured, etc.
2. **`llm_judge` (Layer 2, content quality)** — LLM-judged scoring of
   each prompt artifact (CLAUDE.md, agent .md files, skill SKILL.md,
   command .md files) against per-dimension rubric YAMLs:
   context_quality, workflow_clarity, governance, guardrails, etc.
3. **`cache` (Layer 3, prompt-cache failure-mode classification)** —
   measured prompt-cache hit rate and classification of failure modes
   (cache breakage from drifting front-loaded content, ineffective
   chunking, etc.).

The composite is published alongside the three layer scores; never as
a standalone number.

## Consequences

- positive: action lists per layer let users target the right edit
  (Layer 1 = file shape, Layer 2 = prompt content, Layer 3 = ordering
  and caching).
- positive: regressions in one layer don't mask gains in another.
- negative: composite hides nothing — but also requires users to read
  three numbers. Mitigated by always showing the layer breakdown in
  the dashboard.

## References

- `skills/ai-readiness-rubric/`
- `src/harness_maker/ai_readiness/`
- ADR-0006 (amendment: rubric extended to a three-layer health audit
  that nests this rubric as its Layer 1 source)
