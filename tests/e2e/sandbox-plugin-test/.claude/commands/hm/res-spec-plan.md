---
generated_by: harness-maker
harness_maker_version: 0.5.6
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 8ac13bed6b3ea7e8ac5b9b052d8fe10b1a9a7d9f6847a903713ba228db210440
---
# /hm:res-spec-plan


## Stage: research

# Stage: research

> Atomic stage. Information gathering and best-practice exploration.

> Invoked as part of the **res-spec-plan** workflow.


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


## Stage: spec

# Stage: spec

> Atomic stage. Acceptance-criteria specification.

> Invoked as part of the **res-spec-plan** workflow.


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

- `specs/SPEC-{slug}.md` with frontmatter:
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


## Stage: plan

# Stage: plan

> Atomic stage. Implementation planning with phase decomposition.

> Invoked as part of the **res-spec-plan** workflow.


## Purpose

Convert acceptance criteria into a concrete sequence of implementation
phases. Each phase has a verifiable exit criterion so that progress can
be measured and stalled work can be diagnosed.

## When to Run

- After `spec` (or after `research` when `spec` is skipped)
- Before `execute` for any change touching more than 2-3 files or
  introducing new architectural elements

## Inputs

- SPEC (if available) or research notes + user requirements
- Existing TECH_SPEC.md, ADRs, prior PLANs in `work-docs/`
- Codebase structure (modules, conventions, test layout)

## Procedure

1. Restate the goal in one sentence. If it changed during research, note that.
2. Identify architectural touchpoints: which modules change, which contracts
   shift, what new files appear.
3. Decompose into phases. Each phase MUST have:
   - A clear scope (what's in)
   - An exit criterion (a command or check that proves the phase is done)
   - An estimate of risk (low / medium / high)
4. Order phases by dependency. Earlier phases unblock later ones.
5. Identify rollback points — checkpoints from which work can resume on
   failure without redoing prior phases.
6. Call out risks and unknowns. For each, list the mitigation.

## Outputs

- `work-docs/PLAN-{slug}.md` with frontmatter:
  - `type: plan`, `task_slug:`, `created:`, `tags:`
  - `spec: "[[SPEC-{slug}]]"` (when SPEC exists)
- Numbered phase list with scope + exit criterion + risk for each
- Risk register with mitigations
- Rollback strategy

## Quality Bar

- An independent reader can predict the file diff per phase
- Each exit criterion is checkable (script, test, manual checklist)
- Risks are concrete, not platitudes ("might break things")

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


---

## Harness Configuration [MUST FOLLOW — overrides built-in defaults]

These values come from `.claude/harness.yaml` and **must not be replaced by
model defaults**. If a value conflicts with your training-data intuition, the
harness value wins.

| Key | Value |
|-----|-------|
| `reviewers.grade_threshold` | `A` |
| `reviewers.auto_fix` | `true` |
| `reviewers.max_review_rounds` | `3` |
| `reviewers.consensus` | `cross-check` |
| `dev_mode` | `spec-driven` |
| `caching` | `agent-aware` |

Re-read `.claude/harness.yaml` whenever you are unsure of the current value.

---

## Inline overrides

Extra reviewers/skills can be activated for one invocation by passing flags:

    /hm:res-spec-plan <task description> --with-reviewers=security-reviewer,performance-reviewer
    /hm:res-spec-plan <task description> --with-skills=context-linter

Recognised flags parsed from `$ARGUMENTS`:

- `--with-reviewers=<csv>` — additionally activate these reviewers (must be in
  `harness.yaml`'s `reviewers.installed` list).
- `--with-skills=<csv>` — additionally activate these skills (must be in
  `harness.yaml`'s `skills.installed` list).
- `--no-auto-fix` — disable the review stage's auto-fix loop for this run
  (config default in `harness.yaml`'s `reviewers.auto_fix` is unchanged).
  Findings are still reported; no edits are applied.

Flags are additive to the harness defaults (`reviewers.enabled` /
`skills.enabled`) and apply only to this run. Unknown identifiers are warned
and ignored. The flags themselves are stripped from `$ARGUMENTS` before the
fused stages read the user's task description.
