---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 48684dfab544d31bfeb94aec0ad2a592a8a45a362e18255af4ca5bc7b1469c0e
---
# /hm:careful


## Stage: research

# Stage: research

> Atomic stage. Information gathering and best-practice exploration.

> Invoked as part of the **careful** workflow.


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




## Stage: spec

# Stage: spec

> Atomic stage. Acceptance-criteria specification.

> Invoked as part of the **careful** workflow.


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




## Stage: plan

# Stage: plan

> Atomic stage. Implementation planning with phase decomposition.

> Invoked as part of the **careful** workflow.


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

- `PLAN-{slug}.md` with frontmatter:
  - `type: plan`, `task_slug:`, `created:`, `tags:`
  - `spec: "[[SPEC-{slug}]]"` (when SPEC exists)
- Numbered phase list with scope + exit criterion + risk for each
- Risk register with mitigations
- Rollback strategy

## Quality Bar

- An independent reader can predict the file diff per phase
- Each exit criterion is checkable (script, test, manual checklist)
- Risks are concrete, not platitudes ("might break things")




## Stage: execute

# Stage: execute

> Atomic stage. Implement the plan with continuous verification.

> Invoked as part of the **careful** workflow.


## Purpose

Apply the PLAN's phases to the codebase. Default mode is TDD: tests are
written from acceptance criteria first, the implementation follows, and
each phase exits only when its verification command is green.

## When to Run

- After `plan` (or after `research` for trivial changes that skip plan)
- Whenever there is concrete work to land

## Inputs

- PLAN-{slug}.md
- SPEC-{slug}.md (when present) — drives test authoring
- Codebase, tests, build/CI scripts

## Procedure

1. Confirm preconditions:
   - Working tree clean (or changes are intentional WIP)
   - PLAN's exit criteria for prior phases are met
2. For each PLAN phase, run the 5-phase TDD machine:
   - **Phase A** — Author tests from SPEC criteria (RED expected)
   - **Phase A.5** — Test-quality gate (criteria coverage, no false-positives)
   - **Phase B** — Run tests; confirm RED for the right reasons
   - **Phase C** — Implement to GREEN. No untested code paths.
   - **Phase D** — Post-GREEN verification: ruff, mypy, full pytest, manual smoke
3. Commit at phase boundaries with a message that maps to the PLAN phase.
4. If a phase blocks: stop, document the blocker, escalate to the user
   rather than thrash. Do not silently change scope.

## Outputs

- Code + tests committed to git
- Updated PLAN with phase status (in-progress / done / blocked)
- Optional SESSION-{slug}-{date}.md when `--session` is set

## Quality Bar

- All phase-D checks green
- No skipped/xfail tests added without justification
- Diff matches PLAN scope; surprises are documented




## Stage: review

# Stage: review

> Atomic stage. Multi-perspective code review.

> Invoked as part of the **careful** workflow.


## Purpose

Find defects, design weaknesses, and risk hotspots before they reach
production. Use the configured reviewer set (consensus or
conditionally-routed) and walk the code paths that the change touches.

## When to Run

- After `execute` whenever:
  - More than 3 files changed
  - Security-sensitive code (auth, secrets, perms) changed
  - Architectural surface (interfaces, contracts) changed
  - New public APIs are added
- Skipped for: docs-only, single-file fixes, config-only — unless overridden

## Inputs

- The diff under review (`git diff` since the prior reviewed commit)
- PLAN + SPEC if present (gives intent context)
- Failure log + wiki for relevant past lessons

## Procedure

1. Determine reviewer set:
   - `routing: always-all` → invoke every reviewer in `reviewers.list`
   - `routing: conditional` → use Conditional Router on the changed files
2. For each reviewer:
   - Read the diff with full context (use Read on changed files end-to-end,
     not just the patch)
   - Walk through the runtime path the diff touches — what runs first,
     what state mutates, what can fail
   - Emit findings as JSON: `{severity, file, line, summary, suggestion}`
3. Aggregate via consensus:
   - `single` — accept reviewer's findings as-is
   - `cross-check` — require 2/3 agreement on HIGH severity items
   - `k-of-n` — configurable threshold
4. Write `REVIEW-{topic}-{date}.md` with:
   - All findings ordered by severity
   - Disagreements between reviewers (with reasoning)
   - Recommended actions

## Outputs

- REVIEW document with structured findings
- Optional auto-fix patches (when `--no-fix` not set)

## Quality Bar

- HIGH-severity findings have evidence (code reference + failure mode)
- Reviewers do NOT mutate code (read-only) — fixes are proposed, not applied
- A finding category that should have been caught (per category-owner agent)
  triggers the rollback criterion




## Stage: wrapup

# Stage: wrapup

> Atomic stage. Final quality gate, memory append, commit.

> Invoked as part of the **careful** workflow.


## Purpose

Close the loop on a unit of work. Capture lessons in repo memory so the
next session benefits, run the final review pass, sync TODOs and commit.

## When to Run

- After `review` (when review ran)
- Before pushing to a shared branch
- Whenever a logical work unit completes (feature flag flipped, ticket
  closed, demo-ready)

## Inputs

- All artefacts from prior stages: SPEC, PLAN, REVIEW, code, tests
- `.claude/memory/wiki.md`, `.claude/memory/failures.md`
- TODO.md / task tracking source

## Procedure

1. **Drift gate (advisory)** — diff intent (SPEC/PLAN) against actual diff.
   Log unexpected scope changes to `.claude/memory/pending-drift.md`.
2. **Final reviewer pass** — REVIEWER agent runs over the full work unit
   (not just the latest diff) for ≥3-file or security-sensitive changes.
3. **Memory append**:
   - Wiki — append entry: `## [tags:..] [date:..] [slug:..]`
   - Failures — if a new failure pattern emerged, append or increment count
4. **Failure-driven proposal** — when a failure entry crosses the threshold
   (count ≥ 3), log a skill/agent proposal to `.claude/memory/pending-proposals.md`.
5. **TODO sync** — mark task complete, move to weekly archive.
6. **RAG reindex** — run the project's janitor to update the vector index.
7. **Commit** — single commit summarising the work unit, body explains
   the "why".
8. (Optional) push.

## Outputs

- Updated wiki + failures
- pending-drift.md / pending-proposals.md entries when applicable
- Git commit + (optional) push
- TODO sync

## Quality Bar

- Wiki entries are searchable (good tags) — `rg -F "[tags:keyword]"` works
- Failure entries deduplicate (count++ rather than new section for repeats)
- Commit message captures intent, not just diff summary




## Stage: verify

# Stage: verify

> Atomic stage. Pre-completion verification gate.

> Invoked as part of the **careful** workflow.


## Purpose

Block silent regressions and partial completions. Run a rigid checklist
that any work-unit MUST pass before being declared done. This is the
machine-checkable stop sign before `wrapup`.

## When to Run

- Just before `wrapup`
- At the end of every autoloop iteration
- On demand via `/hm:verify` whenever doubt arises

## Inputs

- Current working tree state
- PLAN / SPEC for the in-progress work unit
- Health snapshot, anti-rot pending queue, security findings

## Checklist (all must pass)

1. **PLAN/SPEC satisfaction** — every acceptance criterion has a passing
   test or an explicit waiver
2. **Regression smoke** — full pytest, ruff, mypy strict, project's own
   verify script (e.g. `.claude-verify.sh phase_N`)
3. **Health delta** — Health score did not drop more than 5 points vs.
   the prior snapshot
4. **Anti-rot pending** — no critical refresh items left unresolved
   (high relevance + security category)
5. **Security high findings** — zero unresolved HIGH-severity findings
   from the most recent security scan
6. **Worktree merge** — when worktree isolation is enabled, the worktree
   merges cleanly into the parent branch (no conflicts)

## Procedure

1. Run each check in order. Stop on the first FAIL.
2. On FAIL: emit a diagnostic with the exact failed check, the evidence,
   and a suggested next action.
3. On PASS: emit a single GREEN line and let `wrapup` proceed.

## Outputs

- `PASS` (zero failures) — proceed
- `FAIL` — list of failed checks + evidence (do NOT proceed to `wrapup`)

## Quality Bar

- The gate is non-negotiable; bypassing requires explicit user override
- A failed check produces actionable evidence, not just a red line
