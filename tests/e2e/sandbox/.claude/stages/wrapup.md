---
generated_by: harness-maker
harness_maker_version: 0.5.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/wrapup.md.j2
provenance: official
content_hash: 71ae5a91b8b078f50e25f08038d65dd4ff583dbbfd0cdc54111961296fac6514
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

> **When invoked as part of a fused workflow** (see preamble), always run —
> do not skip based on the conditions above.

## Inputs

- All artefacts from prior stages: SPEC, PLAN, REVIEW, code, tests
- `.claude/memory/wiki.md`, `.claude/memory/failures.md`
- `.claude/memory/session/<today>.md` — hot-tier session log (if exists)
- TODO.md / task tracking source

## Procedure

1. **Drift gate (advisory)** — diff intent (SPEC/PLAN) against actual diff.
   Log unexpected scope changes to `.claude/memory/pending-drift.md`.
2. **Final reviewer pass** — REVIEWER agent runs over the full work unit
   (not just the latest diff) for ≥3-file or security-sensitive changes.
3. **Memory append**:
   - Wiki — append entry using structured format:
     `## [wiki:<category>] <slug> | <YYYY-MM-DD>`
     (category: pattern / convention / gotcha / architecture / tooling / api / other)
   - Failures — if a new failure pattern emerged, append or increment count:
     `## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>`
     (category: import / test / render / hook / lint / type / runtime / design / other)
   - For repeated failures: update `count:N` in the existing heading (no duplicate section)
4. **Failure-driven proposal** — when a failure entry's count ≥ 3, log a
   skill/agent proposal to `.claude/memory/pending-proposals.md`.
5. **Session log append** — write a summary entry to
   `.claude/memory/session/<YYYY-MM-DD>.md` (today's date):
   ```
   ## [decision:<slug>] <what was decided> | <HH:MM> UTC | stage:wrapup
   <one paragraph: non-obvious constraint, key trade-off, or surprise from this work unit>
   ```
   Create the file (with README header) if it doesn't exist. Omit if the work
   unit was trivial (typo fix, doc-only) — session log is for non-obvious decisions.
6. **TODO sync** — mark task complete, move to weekly archive.
7. **Commit** — single commit summarising the work unit, body explains
   the "why".
8. (Optional) push.

## Outputs

- Updated wiki + failures (structured headings)
- Session log entry in `.claude/memory/session/<today>.md`
- pending-drift.md / pending-proposals.md entries when applicable
- Git commit + (optional) push
- TODO sync

## Quality Bar

- Wiki entries are searchable — `rg -F "[wiki:" .claude/memory/wiki.md` works
- Failure entries deduplicate (count++ in heading, not duplicate sections)
- Session log captures the non-obvious — a future reader can reconstruct why
- Commit message captures intent, not just diff summary

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific wrapup checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the wrapup stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
