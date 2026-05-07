---
generated_by: harness-maker
harness_maker_version: 0.5.7
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: d4fbce30234185c6b3f3f50c4c86d4915ce8ddcc91b26ccd7699c796d80171bc
---
# Stage: research

> Atomic stage. Information gathering and best-practice exploration.


## Purpose

Gather sufficient context before committing to a plan. Surface unknowns, prior
art, library docs, and architectural constraints so that downstream stages
(`spec`, `plan`, `execute`) can proceed without rework.

## When to Run

- Starting a new feature or change in an unfamiliar area of the codebase
- Selecting between competing approaches (libraries, patterns, algorithms)
- Investigating a bug whose root cause is unclear
- Before writing a SPEC for a non-trivial change

## Inputs

- User question, task description, or feature request (`$ARGUMENTS`)
- Codebase context (relevant files, prior PLANs, prior REVIEWs)
- Memory tiers: session log (hot), failures + wiki (warm) — see loading order below

## Session Context Loading

Before starting, load memory in tier order (stops at first miss per tier):

1. **Hot tier** — Read `.claude/memory/session/<today's date>.md` in full if it
   exists. Compaction checkpoint entries reveal where the prior session ended.
2. **Warm tier** — Skim `.claude/memory/failures.md` (first 60 lines).
   Search for relevant entries: `rg -F "[fail:" .claude/memory/failures.md`
3. **Warm tier** — Skim `.claude/memory/wiki.md` (first 60 lines).
   Search for relevant entries: `rg -F "[wiki:" .claude/memory/wiki.md`

## Procedure

1. Identify the scope. State explicitly what is in/out of scope.
2. Search prior art (using loaded memory above as starting point):
   - Targeted grep: `rg -F "[wiki:<keyword>]" .claude/memory/wiki.md`
   - Targeted grep: `rg -F "[fail:<keyword>]" .claude/memory/failures.md`
   - Codebase patterns via Grep/Glob
3. Fetch external documentation when a library/framework/API is involved.
   Prefer official docs over training data — versions drift.
4. Enumerate alternatives. For each, capture: assumption, evidence, trade-off.
5. Surface open questions for the user before SPEC. Use AskUserQuestion when
   the answer would change the chosen approach.

## Outputs

- Research notes summarising:
  - Scope
  - Alternatives considered
  - Recommended direction with rationale
  - Open questions (if any)
- Updated reading list / external references for the plan stage

## Quality Bar

- No "I don't know" surprises in later stages on points covered here
- Recommendation is grounded in evidence, not authority
- Open questions are explicit, not hidden as assumptions

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the research stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
