---
generated_by: harness-maker
harness_maker_version: 0.3.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: 77c4f694f67373003199b20a4219eda29d27a97c661467fd7182360b38196979
---
# Stage: spec

> Atomic stage. Acceptance-criteria specification.


## Purpose

Convert a task description into testable acceptance criteria so that
implementation has an objective definition of "done" and the test stage
has something concrete to write tests against.

## When to Run

- After `research` for non-trivial features
- Before `plan` whenever the change is observable to a user, an API consumer,
  or another module
- Skipped for: docs-only changes, single-file refactors, trivial bug fixes

## Inputs

- Research notes (if `research` was run)
- User requirements / acceptance constraints
- Existing SPEC if this is an evolution of prior behaviour

## Procedure

1. Write the user-facing summary in 2-3 sentences. If it doesn't fit, the
   spec is still too broad.
2. Enumerate behaviours as numbered acceptance criteria. Each MUST be:
   - Observable (you can write a test that fails before, passes after)
   - Independent (one criterion per concern)
   - Bounded (no "etc.", no "and other related cases")
3. List explicit non-goals. What this SPEC does NOT cover.
4. Capture edge cases and error modes. Each becomes a criterion.
5. Note open questions and resolve them via AskUserQuestion before
   marking the SPEC ready.

## Outputs

- `SPEC-{slug}.md` with frontmatter:
  - `type: spec`
  - `status: draft | approved`
  - `task_slug:`, `created:`, `tags:`
- Acceptance criteria numbered AC-1, AC-2, ...
- Non-goals section
- Open questions section (empty when status=approved)

## Quality Bar

- A test author can write tests directly from the criteria without guessing
- Criteria are not implementation details — they describe behaviour
- Non-goals prevent scope creep in `plan` and `execute`

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the spec stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
