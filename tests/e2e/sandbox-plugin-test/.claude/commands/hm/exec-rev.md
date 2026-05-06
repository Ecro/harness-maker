---
generated_by: harness-maker
harness_maker_version: 0.5.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 429589016f24ef5eae2d2f64235615b69c0b4855e10cac05e749470ea7b1edea
---
# /hm:exec-rev


## Stage: execute

# Stage: execute

> Atomic stage. Implement the plan with continuous verification.

> Invoked as part of the **exec-rev** workflow.


## Purpose

Apply the PLAN's phases to the codebase. Default mode is TDD: tests are
written from acceptance criteria first, the implementation follows, and
each phase exits only when its verification command is green.

## When to Run

- After `plan` (or after `research` for trivial changes that skip plan)
- Whenever there is concrete work to land

## Inputs

- `work-docs/PLAN-{slug}.md`
- `specs/SPEC-{slug}.md` (when present) — drives test authoring
- Codebase, tests, build/CI scripts
- Memory tiers — see loading order below

## Session Context Loading

Before starting, load memory in tier order:

1. **Hot tier** — Read `.claude/memory/session/<today's date>.md` in full if it
   exists. If a `checkpoint:compaction` entry is present, this session was
   interrupted mid-stage — check `.claude-progress.json` for partial state.
2. **Warm tier** — Skim `.claude/memory/failures.md` (first 60 lines) for
   patterns relevant to the task. Targeted: `rg -F "[fail:" .claude/memory/failures.md`
3. **Warm tier** — Skim `.claude/memory/wiki.md` (first 40 lines) for
   conventions that apply to the implementation area.

## Procedure

### 0. Worktree isolation (deterministic — do NOT rely on skill auto-discovery)

Before any code edits, engage isolation if `harness.yaml.worktree.scope`
includes `execute`. The `worktree-isolator` skill is documentation only —
its trigger-based dispatch is probabilistic in Cursor IDE and can silently
skip, leaving safety-critical edits on the main branch. **Invoke the
worktree CLI directly** so isolation is deterministic across both IDEs.

Run the create command:

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree create execute "$(pwd)"
```

Read the **single line** the command prints — that is the contract for
the rest of this stage. Two cases:

- **Absolute path** like `/path/to/project/.worktrees/execute-20260506T1830Z`
  → isolation engaged. **Treat that exact string as `<WT>` for the rest
  of this stage.** You (Claude) MUST substitute the literal absolute
  path everywhere `<WT>` appears below — **do NOT use a shell variable**:
  each `!` block is a fresh subshell, so any `worktree_path=...`
  assignment is lost between blocks.
  - Every Read/Write/Edit call uses absolute paths starting with `<WT>/`.
  - Tests / lints / type checks: `!cd <WT> && <cmd>`.
- **Empty output** → `worktree.scope` does not include `execute`. No
  isolation; operate in `cwd`. Skip the finalize step at the end.

### Stage exit (after the TDD machine below completes)

Pick **exactly one** finalize command based on the outcome. Substitute
`<WT>` with the literal absolute path you read in step 0.

```bash
# All phases GREEN + verification clean — squash-merge the branch back + cleanup:
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree finalize <WT> success
```

```bash
# Stage halted on a blocker — preserve the worktree for inspection:
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree finalize <WT> fail
```

If step 0 printed empty (no isolation engaged), skip both — there is
nothing to finalize.

### TDD machine (the actual stage work)

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

> Invoked as part of the **exec-rev** workflow.


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

    /hm:exec-rev <task description> --with-reviewers=security-reviewer,performance-reviewer
    /hm:exec-rev <task description> --with-skills=context-linter

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
