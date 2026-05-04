---
generated_by: harness-maker
harness_maker_version: 0.4.5
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: 6074e6325c03448d8ee515a2e74d6296a44edd41bd17dcf0ee138c5398ef79ac
---
# Stage: wrapup

> Atomic stage. Final quality gate, memory append, commit.


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
6. **Commit** — single commit summarising the work unit, body explains
   the "why".
7. (Optional) push.

## Outputs

- Updated wiki + failures
- pending-drift.md / pending-proposals.md entries when applicable
- Git commit + (optional) push
- TODO sync

## Quality Bar

- Wiki entries are searchable (good tags) — `rg -F "[tags:keyword]"` works
- Failure entries deduplicate (count++ rather than new section for repeats)
- Commit message captures intent, not just diff summary

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific wrapup checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the wrapup stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
