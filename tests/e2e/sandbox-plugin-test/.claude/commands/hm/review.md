---
generated_by: harness-maker
harness_maker_version: 0.5.7
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: 85ff7c48aaa9d73c28439b6af7f26df0460127987e1f3fd81d5a0adbfe90b5d5
---
# Stage: review

> Atomic stage. Multi-perspective review + grade gate + auto-fix loop.


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

> **When invoked as part of a fused workflow** (see preamble), the skip
> conditions above do NOT apply — always run.

## Inputs

- The diff under review (`git diff` since the prior reviewed commit)
- PLAN + SPEC if present (gives intent context)
- Memory tiers — see loading order below

## Session Context Loading

Before starting, load memory in tier order:

1. **Hot tier** — Read `.claude/memory/session/<today's date>.md` in full if it
   exists. Prior session decisions may explain intentional design choices in the diff.
2. **Warm tier** — Skim `.claude/memory/failures.md` for patterns that match
   the changed code area. Targeted: `rg -F "[fail:" .claude/memory/failures.md`
3. **Warm tier** — Skim `.claude/memory/wiki.md` for relevant conventions.
   Known-good patterns should NOT trigger findings.

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
5. Write `work-docs/REVIEW-{topic}-{date}.md` with:
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
