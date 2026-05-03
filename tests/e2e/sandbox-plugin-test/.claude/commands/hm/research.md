---
generated_by: harness-maker
harness_maker_version: 0.2.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: 60596fc0a7dd270bb3f7a328ac0de373cef377f5bb2464c6527f356d91015169
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
- Existing wiki + failure-log entries (`.claude/memory/`)

## Procedure

1. Identify the scope. State explicitly what is in/out of scope.
2. Search prior art:
   - Repo memory: `rg -F "[tags:keyword]" .claude/memory/wiki.md`
   - Repo failures: `rg -F "[tags:keyword]" .claude/memory/failures.md`
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
