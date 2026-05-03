---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 529ba1b89c6d16a528ce55e1e442976f1c339a9a2b550505efbdc39ec6883e4d
---
# /hm:exec-rev-wrap


## Stage: execute

# Stage: execute

> Atomic stage. Implement the plan with continuous verification.

> Invoked as part of the **exec-rev-wrap** workflow.


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

> Invoked as part of the **exec-rev-wrap** workflow.


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
   - Start from `harness.yaml`'s `reviewers.enabled`
   - `routing: always-all` → invoke every enabled reviewer
   - `routing: conditional` → use Conditional Router on the changed files
   - Add any extras passed via `--with-reviewers=<csv>` on the workflow command
     (must be present in `reviewers.installed`)
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

> Invoked as part of the **exec-rev-wrap** workflow.


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




---

## Inline overrides

Extra reviewers/skills can be activated for one invocation by passing flags:

    /hm:exec-rev-wrap <task description> --with-reviewers=security-reviewer,performance-reviewer
    /hm:exec-rev-wrap <task description> --with-skills=context-linter

Recognised flags parsed from `$ARGUMENTS`:

- `--with-reviewers=<csv>` — additionally activate these reviewers (must be in
  `harness.yaml`'s `reviewers.installed` list).
- `--with-skills=<csv>` — additionally activate these skills (must be in
  `harness.yaml`'s `skills.installed` list).

Flags are additive to the harness defaults (`reviewers.enabled` /
`skills.enabled`) and apply only to this run. Unknown identifiers are warned
and ignored. The flags themselves are stripped from `$ARGUMENTS` before the
fused stages read the user's task description.
