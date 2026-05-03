---
generated_by: harness-maker
harness_maker_version: 0.3.2
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 87c77be6e78ff07d6080a016cd37fdb387805c9d235a34fd4a6bea33e8ae4b01
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

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the execute stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


## Stage: review

# Stage: review

> Atomic stage. Multi-perspective review + grade gate + auto-fix loop.

> Invoked as part of the **exec-rev-wrap** workflow.


## Purpose

Find defects, design weaknesses, and risk hotspots before they reach
production. Run the configured reviewer set, compute a grade from the
findings, and (when auto-fix is enabled) apply suggested fixes and re-review
until the grade passes the threshold or `max_review_rounds` is exhausted.

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

## Configuration

Defaults from `harness.yaml` `reviewers:`:

- `auto_fix` (bool, default `true`) — apply consensus-passed fixes between rounds
- `grade_threshold` (`A | B | C`, default `A`) — minimum grade needed to exit
- `max_review_rounds` (int, default `3`) — cap on review iterations

Per-invocation override: pass `--no-auto-fix` on the workflow command to
disable auto-fix for this run only (config default unchanged).

## Procedure — Round 1 (initial review)

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
   - Emit findings per the Finding Schema partial:
     `{severity, file, line, summary, suggestion, ...}`
3. Aggregate via consensus (per `reviewers.consensus`):
   - `single` — accept reviewer's findings as-is
   - `cross-check` — require 2/3 agreement on P0/P1 findings
   - `k-of-n` — configurable threshold
4. Tag each finding:
   - **consensus-passed** — survives the consensus rule (auto-fix candidate)
   - **manual-only** — single source / disagreement on severity (NEVER auto-fixed)
5. Write `REVIEW-{topic}-{date}.md` with:
   - All findings ordered by severity
   - Disagreements between reviewers (with reasoning)
   - Recommended actions

<!-- @hm:user:procedure-extras -->
<!-- Project-specific Round 1 steps (extra reviewers, custom heuristics, etc.). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:procedure-extras -->

## Grade Computation (after every round)

Count consensus-passed findings by severity:

- `P0_count` = consensus-passed findings with severity P0
- `P1_count` = consensus-passed findings with severity P1

P2/P3 and manual-only findings do NOT lower the grade.

| P0 | P1 | Grade |
|----|----|-------|
| 0  | 0  | **A** |
| 0  | 1–2 | B |
| 0  | ≥3 | C |
| 1–2 | * | D |
| ≥3 | * | F |

Order: A > B > C > D > F. Threshold met iff `grade ≥ grade_threshold`.

## Grade Gate

After Round 1's report is written:

```
IF grade ≥ grade_threshold:
  → STOP. Final report = Round 1 report. Proceed to wrapup.

IF auto_fix disabled (config OR --no-auto-fix):
  → STOP. Report grade + remaining findings.
  → Set human_review_needed=true if grade < threshold.

IF iteration_count ≥ max_review_rounds:
  → STOP. Report best grade + remaining findings.
  → Set human_review_needed=true.

ELSE:
  → Enter the auto-fix loop below.
```

## Auto-Fix Loop (rounds 2..max_review_rounds)

For each iteration:

1. **Select fixable findings.** Take only:
   - Severity P0, P1, or P2 (skip P3 unless current grade is D or F)
   - Tag = consensus-passed (skip manual-only)
   - Has a concrete `suggestion` with replacement code (skip vague advice)
2. **Apply fixes in priority order** (P0 → P1 → P2):
   - Read the file at `{file}:{line}`
   - Verify the current code still matches the finding's `evidence` /
     `current` snippet (prior fixes may have shifted lines)
   - Apply the suggested fix via `Edit`
   - Log: `[Fix #{N}] {severity} {summary} in {file}:{line}`
   - If the fix's target lines overlap a fix applied this round (same file,
     line ±5): **skip** and log `skipped — overlap with Fix #{prev}`
3. **Verify build.** Run the project's standard verification:
   - Python: `uv run pytest -x`, `uv run ruff check`, `uv run mypy --strict`
   - Rust: `cargo check`, `cargo test`
   - Node: `pnpm build`, `pnpm test`
   - Or invoke `/hm:verify` if the harness has it
   On failure:
   - Identify the last fix that touched the failing file
   - **Revert** that fix (restore original snippet) and log
     `Fix #{N} reverted — caused build failure`
   - Continue with remaining fixes (do not abort the round)
4. **Re-review** (selective). Re-spawn ONLY reviewers whose scope was touched
   by the applied fixes. Reviewers that approved untouched files are NOT
   re-run. Multi-instance code-reviewer consensus (when configured) still
   uses the configured number of instances on the modified files.
5. **Recompute grade** using the new findings.
6. **Append iteration record** to the REVIEW report:

   ```markdown
   ### Iteration {N} (Grade: {prev} → {new})
   Fixes applied: {count}
   | # | Severity | Summary | File | Status |
   |---|----------|---------|------|--------|
   | 1 | P0 | ... | ... | Applied |
   | 2 | P1 | ... | ... | Skipped — overlap |
   | 3 | P1 | ... | ... | Reverted — build failure |

   Remaining: {count} | New issues introduced: {count}
   ```

7. Return to the Grade Gate with the updated grade and incremented
   `iteration_count`.

## Final Summary (always)

Append to the REVIEW report:

```markdown
## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | {g1}  | —             | {n1}      | —   |
| 2         | {g2}  | {f2}          | {n2}      | {x2}|
| ...

Final grade: {final}
Iterations used: {N} / {max_review_rounds}
human_review_needed: {true|false}
```

- Final grade ≥ threshold → status `APPROVED`, ready for wrapup.
- Final grade < threshold after exhausting rounds → status
  `CHANGES_REQUESTED`, list remaining issues, set `human_review_needed=true`,
  proceed to wrapup (autoloop policy — do NOT halt the loop on D/F).

## Outputs

- REVIEW document with structured findings, per-iteration records, and final
  grade summary
- File modifications applied during the auto-fix loop (when enabled)
- `human_review_needed` flag when threshold was not reached

## Quality Bar

- P0/P1 findings have evidence (code reference + failure mode)
- Reviewer **agents** stay read-only (`permissions.deny: [Write, Edit]`); the
  **stage orchestrator** (Claude running this stage) applies fixes via
  `Edit`, preserving the reviewer permission boundary
- A finding category that should have been caught (per category-owner agent)
  triggers the rollback criterion
- Auto-fix never silently overwrites a build break; failed fixes are reverted
  and logged

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items (additional invariants, domain rules). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the review stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


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
- `--no-auto-fix` — disable the review stage's auto-fix loop for this run
  (config default in `harness.yaml`'s `reviewers.auto_fix` is unchanged).
  Findings are still reported; no edits are applied.

Flags are additive to the harness defaults (`reviewers.enabled` /
`skills.enabled`) and apply only to this run. Unknown identifiers are warned
and ignored. The flags themselves are stripped from `$ARGUMENTS` before the
fused stages read the user's task description.
