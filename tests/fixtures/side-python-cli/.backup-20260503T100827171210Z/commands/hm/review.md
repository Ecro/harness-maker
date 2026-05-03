---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: 284cb78ea4f4c943f798818bb49879ef66c6821331ba4cdd337416ab23b76c24
---
# Stage: review

> Atomic stage. Multi-perspective code review.


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
