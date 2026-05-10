---
generated_by: harness-maker
harness_maker_version: 0.9.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: c68836d566e967dae3683b3bf6ae79a0b9c7d2c2aff8e3d4939024a099b1c218
---
# /hm:exec-rev-wrap-ver


## Stage: execute

# Stage: execute

> Atomic stage. TDD machine driven by PLAN. Phase A → A.5 → B → C → D, with worktree isolation and **NO commits** (wrapup owns commits).

> Invoked as part of the **exec-rev-wrap-ver** workflow.


## Communication Protocol

- Be direct. No flattery, no preamble.
- If a PLAN phase is under-specified, surface it before writing tests — don't guess.
- Don't hide test failures. Compiler/test errors go in the response verbatim.
- When Phase A.5 returns FAIL, treat the test-reviewer's reasoning as authoritative — rewrite, don't argue.

## Purpose

Apply the PLAN's phases to the codebase. When `tdd_active`, tests are written from SPEC's In-Scope Scenarios first, the implementation follows, and each PLAN phase exits only when its exit-criterion command is GREEN. Use `test_dep_map.build_test_hints()` to identify which tests are affected by each changed file — run only those tests during Phase D instead of the full suite on every edit.

## Usage

```
/hm:execute <slug> [--no-tdd]
```

- `<slug>` — task identifier matching `work-docs/PLAN-{slug}.md`. Required.
- `--no-tdd` — skip Phase A (test authoring), Phase A.5 (test-reviewer gate), and Phase B (RED gate). Phase C still loads SPEC reference. Use when:
  - Pure refactor (no behavior change — existing tests already cover).
  - Docs-only / config-only / typo fix.
  - Emergency fix where SPEC + tests are already present and correct.

  All other modes default to TDD. There is no second flag.

## Inputs

- `work-docs/PLAN-{slug}.md` (required — error if missing).
- From PLAN frontmatter:
  - `spec: "[[SPEC-{slug}]]"` → resolves to `specs/SPEC-{slug}.md`.
  - `research_doc: "[[RESEARCH-{slug}]]"` → resolves to `work-docs/RESEARCH-{slug}.md`.
- From SPEC frontmatter (when present):
  - `test_framework` (e.g., `pytest`, `gtest`, `vitest`) — Phase A writes tests against this.
  - `## 📋 In-Scope Scenarios` — drives Phase A test authoring.
  - `## ✅ Verification Criteria` — drives Phase B RED-gate command + Phase D regression check.
- Memory tiers (loaded below).

## Session Context Loading

Before any code edits, load memory in tier order (stops at first miss):

1. **Hot tier** — Read `.claude/memory/session/<today>.md` if it exists. A `checkpoint:compaction` entry means the prior session was interrupted mid-stage — check `.claude-progress.json` for partial state and resume from the last in-progress phase.
2. **Warm tier** — Skim `.claude/memory/failures.md` first 60 lines; targeted: `rg -F "[fail:" .claude/memory/failures.md` for patterns relevant to the task.
3. **Warm tier** — Skim `.claude/memory/wiki.md` first 40 lines for conventions in the implementation area.

## Procedure

### Step 0 — Worktree isolation (deterministic — do NOT rely on skill auto-discovery)

<!-- # SIBLING_WORKTREE_PATHS -->

Engage isolation if `harness.yaml.worktree.scope` includes `execute`. The `worktree-isolator` skill is documentation-only — its trigger-based dispatch is probabilistic in Cursor IDE and can silently skip, leaving safety-critical edits on the main branch. **Invoke the worktree CLI directly** so isolation is deterministic across both IDEs.

**Idempotent under `/hm:loop`**: when this stage runs as part of a loop iteration, the loop has already engaged a per-loop worktree at step 5. The `worktree create` CLI detects we're already inside `.worktrees/<name>/` and returns that path — no nested worktrees, just reuse.

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree create execute "$(pwd)"
```

Read **all non-empty output lines** — that is the contract for the rest of this stage. Three cases:

- **Empty output** → `worktree.scope` does not include `execute`. No isolation; operate in `cwd`. Skip the finalize step at end.
- **One absolute path** like `/path/to/project/.worktrees/execute-20260506T1830Z` → single-repo isolation. **Treat that exact string as `<WT>` for the rest of this stage.** You (Claude) MUST substitute the literal absolute path everywhere `<WT>` appears below — **do NOT use a shell variable**: each `!` block is a fresh subshell.
  - Every Read/Write/Edit call uses absolute paths starting with `<WT>/`.
  - Tests / lints / type checks: `!cd <WT> && <cmd>`.
- **Multiple lines** → multi-repo isolation. Line 1 = primary repo worktree (`<WT>`). Lines 2+ = sibling repo worktrees (`<WT-sibling-N>`). Use `<WT>` for primary-repo edits and `<WT-sibling-N>` for sibling-repo edits — the per-session gate marker covers all of them.

### Step 1 — Load PLAN + flag parsing

```bash
PLAN=work-docs/PLAN-${slug}.md
[ -f "$PLAN" ] || { echo "ERROR: PLAN not found at $PLAN — run /hm:plan ${slug} first"; exit 1; }
```

Read PLAN fully. Extract:
- Phase list with scope / exit-criterion / risk / rollback for each.
- ADRs (binding constraints — must not be violated by implementation).
- Frontmatter `spec:` and `research_doc:` references.

Parse flags from `$ARGUMENTS`:
- `--no-tdd` → set `tdd_active = false`.
- Otherwise `tdd_active = true`.

### Step 2 — Resolve SPEC + RESEARCH cache (when frontmatter references them)

Per PLAN frontmatter:

```bash
spec_field=$(yq '.spec' "$PLAN")            # e.g., "[[SPEC-mqtt-retry]]"
research_field=$(yq '.research_doc' "$PLAN") # e.g., "[[RESEARCH-mqtt-retry]]"
```

If `spec:` resolves to an existing file:
- Read SPEC fully.
- Extract `test_framework` from frontmatter — Phase A uses this verbatim.
- Extract `## 📋 In-Scope Scenarios` — Phase A authors one test per scenario.
- Extract `## ✅ Verification Criteria` — Phase B RED-gate uses the named test commands.

If `research_doc:` resolves to an existing file with mtime < `mtime_warn_days` (frontmatter, default 7):
- Read it; reuse `libs_fetched`, `sources` to skip duplicate context-fetching.
- Cache HIT → no re-retrieval.

If RESEARCH file is older than `mtime_warn_days`: warn the user, proceed with implementation, but log the staleness in the PLAN's session log.

### Step 3 — Per-PLAN-phase TDD machine

For each phase in PLAN's `## 📝 Implementation Plan`, run Phases A → A.5 → B → C → D in order:

#### Phase A — Author tests (skipped when `tdd_active == false`)

For each SPEC In-Scope Scenario in scope of this PLAN phase:
1. Write test file(s) at the project's test directory using `test_framework` from SPEC.
2. Test function name encodes the scenario ID: `test_s1_<short-name>`, `test_s2_<short-name>`, etc.
3. Assertions match the scenario's `**Then**` clause exactly. No tautologies, no over-mocking, no stub-only bodies (test-reviewer enforces — Phase A.5).
4. Tests MUST be RED initially — they import / depend on functions that do not yet exist or are stubs. The implementation is written in Phase C.

#### Phase A.5 — test-reviewer gate (skipped when `tdd_active == false`)

Invoke the `test-reviewer` agent on the just-authored test files:

```
Task(
  subagent_type="test-reviewer",
  description="Phase A.5 test-quality gate: {slug}",
  prompt="<SPEC body + Phase A test file paths + test_framework name>\n\nReturn ONLY the JSON output as specified in your instructions."
)
```

Resolution:
- `overall_assessment: PASS` → proceed to Phase B.
- `overall_assessment: FAIL` → for each entry in `blocking_issues[]`, rewrite the offending test (the `passing_tests[]` list is FROZEN — do not re-author them). For each `scenarios_missing[]`, author a new test. **Re-invoke test-reviewer** until PASS. Retry budget: **2 attempts**. After 2 FAILs in a row, surface the latest verdict and stop — escalate to user.

#### Phase B — RED gate (skipped when `tdd_active == false`)

Run the test command from SPEC's `## ✅ Verification Criteria` table (or the PLAN phase's exit criterion if SPEC absent):

```bash
!cd <WT> && <test_command>
```

Expected result: tests FAIL for the right reasons (missing implementation, not syntax errors / import errors / framework misconfiguration). Verify by reading the failure output. If the test passes by accident → return to Phase A and rewrite (false-RED is a Phase A.5 escape).

#### Phase C — Implementation to GREEN

Write the implementation. No untested code paths — every public function added must be covered by a test from Phase A (or by an existing test, when `tdd_active == false`).

Constraints from PLAN's ADRs are binding: do NOT introduce a pattern that contradicts an ADR; surface as a Phase D blocker if the ADR turns out wrong.

Compile / type-check after each edit; do not batch multiple edits before checking. Include compiler / lint output in your response when surfacing progress.

#### Phase D — Post-GREEN verification

Run the project's full check suite:

```bash
!cd <WT> && <lint command>     # e.g., ruff check
!cd <WT> && <type command>     # e.g., mypy --strict
!cd <WT> && <test command>     # e.g., pytest tests/ -q
```

Plus the PLAN phase's exit-criterion command. All must pass. If any fails:
- Compile / type / lint failure → fix in Phase C (re-edit, re-check); do NOT advance.
- Test failure that wasn't there before → regression. Find the offending change, fix or revert.
- Phase exit-criterion failure → the PLAN phase is not done. Either fix or escalate.

### Step 4 — Stage exit (NO commit — wrapup owns commits)

When all PLAN phases complete GREEN:
1. Verify the worktree's working tree is clean of unintended drift (no stray edits outside scope).
2. **Leave changes staged or unstaged on the worktree branch — DO NOT run `git commit`.** Wrapup stage owns the single user-facing commit.
3. Update PLAN with phase status (in-progress / done / blocked) — but do NOT commit the PLAN file edit either.

If a PLAN phase blocks (Phase A.5 retry exhausted, Phase D unfixable, or ADR conflict):
- Document the blocker inline in the PLAN under the affected phase.
- Surface to the user with the blocker's exact failure output.
- Do NOT silently change scope.

### Step 5 — Worktree finalize

Pick **exactly one** finalize command. Substitute `<WT>` with the literal absolute path from Step 0.

```bash
# All phases GREEN — stage-merge the branch back (NO commit) + cleanup the worktree.
# /hm:wrapup will create the single user-facing commit (with proper message + Co-Authored-By).
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree finalize <WT> stage-only
```

```bash
# Stage halted on a blocker — preserve the worktree for inspection:
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree finalize <WT> fail
```

If Step 0 printed empty (no isolation engaged), skip both — there is nothing to finalize.

**Workflows without wrapup** (e.g., `/hm:exec-rev`): if you exit a fused workflow at this stage without wrapup running afterward, the staged changes remain uncommitted on the base branch. Either run `/hm:wrapup` to commit them, or commit manually:

```bash
git commit -m "<your message>"
```

## Outputs

- Code + tests **staged but not committed** (commit happens in `/hm:wrapup`).
- Updated PLAN with phase status (in-progress / done / blocked) — also uncommitted.
- Optional: a SESSION-{slug}.md log if the user passes `--session` (default OFF — PLAN is the primary artifact).

## Quality Bar

- All Phase D checks GREEN at stage exit, OR the blocker is documented in PLAN.
- Every SPEC In-Scope Scenario maps to a test (when `tdd_active`).
- Phase A.5 test-reviewer returned PASS (or `--no-tdd` was set).
- No diff outside the PLAN's stated scope — surprise edits are flagged.
- No `git commit` invoked from this stage. (Verify: `git log` shows no new commit relative to stage start.)
- Worktree finalized exactly once: success or fail.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the execute stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


## Stage: review

# Stage: review

> Atomic stage. Multi-perspective review with **surface-match + reasoning-alignment** consensus, grade gate, and auto-fix loop.

> Invoked as part of the **exec-rev-wrap-ver** workflow.


## Communication Protocol

- Be direct. No flattery, no preamble.
- Surface disagreements between reviewers — never average findings into mush.
- When applying auto-fix, log every step verbatim so the next round can audit.
- A reviewer's finding is authoritative *only* when it survives the consensus filter; single-source findings are recorded as `manual-only`, never auto-applied.

## Purpose

Find defects, design weaknesses, and risk hotspots **before** they reach `wrapup`. Run the configured reviewer set, dedupe findings via surface + reasoning alignment, compute a grade, and (when auto-fix is enabled) apply consensus-passed fixes and re-review until the grade meets threshold or `max_review_rounds` is exhausted.

## When to Run

- After `execute` whenever:
  - More than 3 files changed.
  - Security-sensitive code (auth, secrets, perms) changed.
  - Architectural surface (interfaces, contracts) changed.
  - New public APIs are added.
- Skipped for: docs-only, single-file fixes, config-only — unless overridden.

> When invoked as part of a fused workflow, the skip conditions above do **NOT** apply — always run.

## Inputs

- The diff under review (`git diff` since the prior reviewed commit, or full worktree diff when running post-`execute`).
- PLAN at `work-docs/PLAN-{slug}.md` and SPEC at `specs/SPEC-{slug}.md` (intent / scenarios / ADRs).
- Memory tiers (loaded below).

## Session Context Loading

1. **Hot tier** — Read `.claude/memory/session/<today>.md` if it exists. Prior session decisions may explain intentional design choices in the diff.
2. **Warm tier** — Skim `.claude/memory/failures.md` for patterns matching the changed code area: `rg -F "[fail:" .claude/memory/failures.md`.
3. **Warm tier** — Skim `.claude/memory/wiki.md` for relevant conventions. Known-good patterns should NOT trigger findings.

## Configuration

Defaults from `harness.yaml.reviewers:`:
- `auto_fix` (bool, default `true`) — apply consensus-passed fixes between rounds.
- `grade_threshold` (`A | B | C`, default `A`) — minimum grade to exit.
- `max_review_rounds` (int, default `3`) — cap on review iterations.
- `consensus` — `single` | `cross-check (2/3)` | `k-of-n` (default: cross-check).
- `routing` — `conditional` | `always-all` (default: conditional).

Per-invocation overrides (workflow command flags):
- `--no-auto-fix` — disable auto-fix this run only.
- `--with-reviewers=<csv>` — add ad-hoc reviewers (must exist in `reviewers.installed`).


## Procedure — Round 1 (initial review)

### Step 1 — Reviewer set selection

- Start from `harness.yaml.reviewers.enabled`.
- `routing: always-all` → invoke every enabled reviewer in parallel.
- `routing: conditional` → use Conditional Router (M6) on the changed-file paths to pick the subset.
- Add any extras from `--with-reviewers=<csv>`.

### Step 2 — Drift gate (PLAN/SPEC vs actual diff)

Before reviewers run, scan the diff against PLAN scope:
- Files changed that are NOT in any PLAN phase's "scope" → flag as **scope drift**.
- Files in PLAN phase's scope that have NOT changed → flag as **incomplete phase**.

Drift findings get severity `P1` and surface in the REVIEW report; reviewers still run on the actual diff.

### Step 3 — Parallel reviewer invocation (2-pass redaction)

Run reviewers in **two sequential passes** to neutralize metadata anchoring
(Phase 0 ablation showed +47 percentage-point precision gain on
anchoring-prone diffs):

#### Pass 1 — rubric-only (metadata redacted)

1. Build `pass1_context` from the diff context with PR title / description /
   author / commit message redacted. Pipe the JSON context through the
   harness CLI rather than redacting in prose:
   ```bash
   echo '<full_context_json>' | python -m harness_maker.two_pass_review redact
   ```
   The CLI returns a JSON object with the same fields but anchoring values
   replaced by `[REDACTED]`.
2. Run all selected reviewers in a **single message with multiple Task tool
   uses** for parallel execution, passing `pass1_context`. Each reviewer:
   - Reads the diff with full context (use Read on changed files
     end-to-end, not just the patch).
   - Walks the runtime path the diff touches — what runs first, what state
     mutates, what can fail.
   - Returns findings per the Finding Schema partial:
     `{severity, file, line, summary, suggestion, reasoning?, …}`.

#### Pass 2 — contextual verdict (full metadata restored)

3. Re-run the same reviewer set with the **full** context (metadata
   restored) and the Pass 1 findings list. Each reviewer validates each
   finding against the metadata, drops any that the context proves to be
   spurious, and adjusts severity if the context changes risk.
4. Merge the two passes via the harness CLI:
   ```bash
   echo '{"pass1": [...], "pass2": [...]}' | python -m harness_maker.two_pass_review merge
   ```
   Pass 2 is authoritative — Pass 1 findings absent from Pass 2 are
   invalidated by context and **dropped** (CP10 contract).
5. The merged finding list is the input to the consensus filter (Step 4).

### Step 4 — Consensus filter (surface + reasoning alignment)

For each pair of findings from different reviewers, decide if they describe the **same issue** via this 2-step filter:

#### Step 4a — Surface match (candidacy)

Two findings are consensus *candidates* iff they satisfy BOTH:
1. Same `file` AND `line ± 5` (or both target the same named symbol when line numbers shift).
2. Same `severity` tier (P0 vs P0; P1 vs P1; do not bridge tiers).

Pairs failing surface match are recorded as **independent** findings — preserve both.

#### Step 4b — Reasoning alignment (verification)

For surface-match candidates, compare the `reasoning` chains (OBSERVE → INFER → CONCLUDE):
- **CONCLUDE clauses identify the same execution risk?** → **strong consensus** (`[2/N]` or `[N/N]`).
- **OBSERVE matches but CONCLUDE diverges** (e.g., one says "race condition", other says "null deref") → **weak consensus** (`[2/N weak]`) — keep both, flag for manual judgment.
- **OBSERVE matches but reasoning is missing on one side** → demote to `manual-only`.

#### Step 4c — Severity resolution (when consensus has differing severities)

| Votes | Applied severity |
|-------|------------------|
| All agree | Agreed severity |
| 2 agree, 1 differs | Majority severity |
| All differ (one each) | Middle of the scale (P1 over P0/P2) |

#### Step 4d — Tag every finding

| Tag | Condition | Auto-fix eligible? |
|-----|-----------|--------------------|
| `consensus-passed` | Survived surface + reasoning alignment with strong consensus | ✅ Yes |
| `weak-consensus` | Surface match, reasoning diverges | ❌ No (manual) |
| `manual-only` | Single source, or consensus failed | ❌ No (manual) |

### Step 5 — Write REVIEW report

Write `work-docs/REVIEW-{slug}-{date}.md` with frontmatter + sections:

```yaml
---
type: review
task_slug: {slug}
status: in-progress  # → APPROVED | CHANGES_REQUESTED on final summary
created: {YYYY-MM-DD}
reviewers_invoked: [{names}]
consensus_method: cross-check
---
```

Sections:
1. **🎯 Round 1 Summary** — grade, fixes pending, manual items.
2. **🔍 Drift Findings** — from Step 2.
3. **✅ Consensus Findings** — `consensus-passed`, by severity.
4. **⚠️ Weak Consensus** — `weak-consensus`, by severity.
5. **📝 Manual-Only Findings** — `manual-only`, by severity.
6. **🤝 Disagreements** — when reasoning aligned but severity differed; show all reviewer takes.

<!-- @hm:user:procedure-extras -->
<!-- Project-specific Round 1 steps (extra reviewers, custom heuristics). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:procedure-extras -->

## Grade Computation (after every round)

Count **`consensus-passed`** findings only by severity:

- `P0_count` = consensus-passed findings with severity P0.
- `P1_count` = consensus-passed findings with severity P1.

P2/P3, weak-consensus, and manual-only findings do NOT lower the grade.

| P0 | P1 | Grade |
|----|----|-------|
| 0 | 0 | **A** |
| 0 | 1–2 | B |
| 0 | ≥3 | C |
| 1–2 | * | D |
| ≥3 | * | F |

Order: A > B > C > D > F. Threshold met iff `grade ≥ grade_threshold`.

## Grade Gate

After each round's report:

```
IF grade ≥ grade_threshold:
  → STOP. Final report = current. Status = APPROVED. Proceed to wrapup.

IF auto_fix disabled (config OR --no-auto-fix):
  → STOP. Report grade + remaining findings. Status = CHANGES_REQUESTED.
  → Set human_review_needed=true if grade < threshold.

IF iteration_count ≥ max_review_rounds:
  → STOP. Best grade + remaining. Status = CHANGES_REQUESTED.
  → Set human_review_needed=true.

ELSE:
  → Enter the auto-fix loop below.
```

## Auto-Fix Loop (rounds 2..max_review_rounds)

Per iteration:

1. **Select fixable findings** — only:
   - Severity P0, P1, or P2 (skip P3 unless current grade is D or F).
   - Tag = `consensus-passed`.
   - Has a concrete `suggestion` with replacement code (skip vague advice).

2. **Apply fixes in priority order** (P0 → P1 → P2):
   - Read the file at `{file}:{line}`.
   - Verify current code still matches the finding's `evidence` snippet (prior fixes may have shifted lines).
   - Apply the suggested fix via `Edit`.
   - Log: `[Fix #{N}] {severity} {summary} in {file}:{line}`.
   - Skip when target lines overlap a fix applied this round (same file, line ±5): log `skipped — overlap with Fix #{prev}`.

3. **Verify build** — run the project's standard verification:
   - Python: `uv run pytest -x`, `uv run ruff check`, `uv run mypy --strict`.
   - Rust: `cargo check`, `cargo test`.
   - Node: `pnpm build`, `pnpm test`.
   - Or invoke `/hm:verify` if the harness has it.

   On failure: identify the last fix that touched the failing file → **revert** it (restore original snippet) and log `Fix #{N} reverted — caused build failure`. Continue with remaining fixes (do not abort the round).

4. **Re-review (selective)** — re-spawn ONLY reviewers whose scope was touched by applied fixes. Reviewers that approved untouched files are NOT re-run. Multi-instance code-reviewer consensus (when configured) still uses the configured number of instances on modified files.

5. **Recompute grade** using the new findings (Step 4 consensus filter again).

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

7. Return to the Grade Gate with the updated grade and incremented `iteration_count`.

## Final Summary (always)

Append to the REVIEW report:

```markdown
## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | {g1}  | —             | {n1}      | —   |
| 2         | {g2}  | {f2}          | {n2}      | {x2}|

Final grade: {final}
Iterations used: {N} / {max_review_rounds}
Status: APPROVED | CHANGES_REQUESTED
human_review_needed: {true|false}
```

- `APPROVED` → ready for wrapup.
- `CHANGES_REQUESTED` (autoloop policy) → list remaining issues, set `human_review_needed=true`, **proceed to wrapup** (do NOT halt the loop on D/F — wrapup will surface the flag).

## Outputs

- `work-docs/REVIEW-{slug}-{date}.md` with all findings, per-iteration records, and final grade summary.
- File modifications applied during auto-fix (when enabled). **Not committed** — wrapup owns the commit.
- `human_review_needed` flag when threshold not reached.

## Quality Bar

- P0/P1 findings have evidence (code reference + failure mode + OBSERVE/INFER/CONCLUDE).
- Reviewer **agents** stay read-only (`permissions.deny: [Write, Edit]`); the **stage orchestrator** (Claude running this stage) applies fixes via `Edit`, preserving the reviewer permission boundary.
- A finding category that should have been caught (per category-owner agent) triggers the rollback criterion.
- Auto-fix never silently overwrites a build break; failed fixes are reverted and logged.
- No `git commit` invoked from this stage. (Verify: `git log` shows no new commit relative to stage start.)
- `weak-consensus` items are surfaced separately — never silently merged with strong-consensus findings.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items (additional invariants, domain rules). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the review stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


## Stage: wrapup

# Stage: wrapup

> Atomic stage. **Single commit owner**: integrates execute's staged changes + memory + PLAN status updates into ONE user-facing commit with Co-Authored-By: Claude.

> Invoked as part of the **exec-rev-wrap-ver** workflow.


## Communication Protocol

- Be direct. No flattery, no preamble.
- The commit message describes the **why**, not the diff. Future readers (including future-you at 2 a.m.) need intent, not file lists.
- If a quality gate fails, surface the failure verbatim and STOP — do not paper over with "mostly works" language.
- Memory entries are written in the user's voice — concise, specific, traceable.

## Purpose

Close the loop on a unit of work:
1. Run the final verification pass (build / tests / lint).
2. Capture lessons in repo memory so the next session benefits.
3. Update PLAN status to mark phases done.
4. Create the **single commit** for this work unit (execute already staged its changes; this stage adds memory + PLAN updates and commits everything).

## When to Run

- After `review` (when review ran).
- Before pushing to a shared branch.
- Whenever a logical work unit completes (feature flag flipped, ticket closed, demo-ready).

> When invoked as part of a fused workflow, always run — do not skip based on the conditions above.

## Inputs

- All artefacts from prior stages: SPEC, PLAN, REVIEW, code, tests.
- `.claude/memory/wiki.md`, `.claude/memory/failures.md`, `.claude/memory/session/<today>.md`.
- The currently-staged changes from `/hm:execute` Step 5 (`stage-only` mode).
- TODO source if the project tracks tasks in a structured place (optional).

## Procedure

### Step 1 — Pre-flight checks

Before touching anything, verify state:

1. **Working tree state**: there should be staged changes (from execute) OR clean (if execute was skipped). If there are *unstaged* changes that don't trace to execute's worktree merge, surface them — they may be drift.
2. **Worktree finalize state**: any `.worktrees/execute-*` directories should be cleaned up by execute Step 5 (`stage-only`) already. If one persists, log a warning — it means execute exited with `fail` or stage-only failed. **Multi-repo**: when sibling repos are configured, `finalize stage-only` merges all repos' worktrees into their respective main branches; if any sibling's merge failed, the marker file is kept and the directory remains — resolve manually before committing.
3. **PLAN existence**: `work-docs/PLAN-{slug}.md` exists (skip wrapup with a clear error otherwise).

### Step 2 — Final verification pass

Run the project's full check suite once before committing. Catch regressions wrapup-stage edits could introduce:

```bash
# Pick the toolchain that matches the project. Examples:
!uv run pytest -x                      # Python
!uv run ruff check src/ tests/          # lint
!uv run mypy --strict src/              # type
# Rust: cargo test && cargo check
# Node: pnpm test && pnpm build
```

If any fail: STOP, surface the failure, do NOT proceed. Reverting an executed-merge is more painful than diagnosing here.

### Step 3 — Drift gate (advisory)

Diff intent (SPEC scenarios + PLAN phase scopes) against the actual staged changes:

- **Files staged but NOT in any PLAN phase scope** → log to `.claude/memory/pending-drift.md`.
- **Files in PLAN scope but NOT staged** → log incomplete-phase warning to `pending-drift.md`.
- **SPEC scenarios with no test coverage in the diff** → log missing-coverage warning.

This is advisory; do not block the commit. The next session reads `pending-drift.md` to catch up.

### Step 4 — PLAN status update

Update `work-docs/PLAN-{slug}.md`:

1. **Frontmatter**: `status: planning` → `status: complete`.
2. **Checkboxes**: replace every `- [ ]` with `- [x]` in the body. At wrapup time the plan's phases are either done or explicitly deferred — the checkbox state should reflect that.

Use a single Edit / Write call (atomic). Verify by reading back: assert `status: complete` is present and zero `- [ ]` remain.

### Step 5 — Memory append

#### 5.1 Wiki

Append (or update) one entry under `.claude/memory/wiki.md`:

```markdown
## [wiki:<category>] <slug> | <YYYY-MM-DD>
<one-paragraph summary of the pattern / convention / gotcha learned>
```

- **category**: `pattern` | `convention` | `gotcha` | `architecture` | `tooling` | `api` | `other`.
- **slug**: kebab-case, ≤40 chars, derived from the work unit.
- If a `[wiki:<same-slug>]` entry already exists: replace its body with the updated learning (do NOT duplicate).

#### 5.2 Failures

For each new failure pattern that emerged this work unit, append (or increment count) under `.claude/memory/failures.md`:

```markdown
## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>
<symptom + cause + fix in one paragraph>
```

- **category**: `import` | `test` | `render` | `hook` | `lint` | `type` | `runtime` | `design` | `other`.
- **count**: increment when the same `<category>:<slug>` already exists; do NOT duplicate sections.
- **Qualifies as failure**: incorrect API usage, wrong syntax, convention misunderstanding, build failures, tool mistakes, workflow violations.
- **Does NOT qualify**: user preference changes, expected errors, normal debugging cycles, design evolution.

#### 5.3 Failure-driven proposal

When a failure entry's `count >= 3`, write a skill / agent / rule proposal to `.claude/memory/pending-proposals.md`:

```markdown
## Proposal: {short-title} ({YYYY-MM-DD})
**Triggered by:** [fail:<category>] <slug> (count: 3)
**Proposed mechanism:** {new skill | rule update | agent | hook}
**Rationale:** {why an automated guard would have prevented this 3 times}
```

The user reviews proposals later and decides whether to ingest into the harness.

#### 5.4 Managed documents


No additional managed documents configured. To add documents that wrapup
should update (e.g. CHANGELOG.md, TODO.md), run `/hm:configure` and select
**Wrapup documents**.


#### 5.5 Session log

Append to `.claude/memory/session/<YYYY-MM-DD>.md` (today's date):

```markdown
## [decision:<slug>] <what was decided> | <HH:MM> UTC | stage:wrapup
<one paragraph: non-obvious constraint, key trade-off, or surprise from this work unit>
```

Create the file (with README header) if it doesn't exist. **Omit** when the work unit was trivial (typo fix, doc-only) — session log is for non-obvious decisions.

### Step 6 — Stage memory + PLAN updates

```bash
!git add .claude/memory/ work-docs/PLAN-{slug}.md work-docs/REVIEW-{slug}-*.md 2>/dev/null
```

(REVIEW-*.md is optional — only present when `/hm:review` ran.)

### Step 7 — Single commit

Write the commit message: `<type>(<scope>): <subject ≤72 chars>` followed by a body explaining **why**, not **what**. The diff already says what.

```bash
!git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body — explains why this change exists, what trade-off was accepted, and
which constraint forced the chosen approach. Cite ADR-NNN or Interview-#N
when the rationale lives in the PLAN.>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Type** (per CLAUDE.md `<type>(<scope>): <subject>` convention): `feat | fix | chore | ci | test | docs | refactor`.

The commit captures: the staged execute changes + the memory updates + the PLAN status update — **all in one commit**.

### Step 8 — Push (manual; never automatic)

Wrapup does **NOT** auto-push. The user explicitly requests push when ready:

```bash
# (User runs separately when they want to push)
!git push
```

If the user asks to push during wrapup, that is fine — but never push without an explicit request.

## Outputs

- **One** git commit including: implementation diff (from execute), wiki + failures + session log + PLAN status updates.
- `.claude/memory/pending-drift.md` entries when drift was detected.
- `.claude/memory/pending-proposals.md` entries when failure count crossed threshold.
- Updated `.claude/memory/session/<today>.md` for non-trivial work units.

## Quality Bar

- **Exactly one** commit per wrapup invocation. (Verify: `git log` shows one new commit relative to wrapup start.)
- Commit message subject ≤72 chars; body explains **why**, not what.
- `Co-Authored-By: Claude` line present.
- Wiki entries are searchable: `rg -F "[wiki:" .claude/memory/wiki.md` returns the new entry.
- Failure entries deduplicate by slug (count++ in heading, not duplicate sections).
- Session log captures non-obvious decisions; trivial work units do NOT add noise.
- PLAN frontmatter `status: complete` and zero `- [ ]` remain in the body.
- Final verification pass GREEN before commit.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific wrapup checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the wrapup stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


## Stage: verify

# Stage: verify

> Atomic stage. Pre-completion verification gate — 6-check stop sign before `wrapup`. Failures block by default; `--force` overrides explicitly.

> Invoked as part of the **exec-rev-wrap-ver** workflow.


## Communication Protocol

- Be direct. PASS / FAIL — no soft language.
- A failed check produces actionable evidence: which check, what failed, what to run to reproduce. Never just "regression detected".
- `--force` is logged with reason; never silent.
- Stop at the first FAIL — do not run remaining checks. The user fixes that one and re-runs.

## Purpose

Block silent regressions and partial completions. Run a rigid 6-check rubric that any work unit MUST pass before being declared done. This is the machine-checkable stop sign before `/hm:wrapup`.

## When to Run

- Just before `wrapup` (paired stages — verify then wrapup).
- At the end of every autoloop iteration (M8 invariant).
- On demand via `/hm:verify` whenever doubt arises.

## Usage

```
/hm:verify [--force] [--reason=<text>]
```

- `--force` — proceed even when one or more checks FAIL. **Logged with the override reason.** Use only when the user has consciously chosen to bypass (emergency hotfix, intentional debt). Without `--reason=<text>`, `--force` requires confirmation via AskUserQuestion in `en`.
- `--reason=<text>` — free-form override rationale. Required for `--force` in non-interactive contexts (autoloop).

## Inputs

- Current working tree state (staged + unstaged).
- `work-docs/PLAN-{slug}.md` and `specs/SPEC-{slug}.md` (when present) — drive Check 1.
- Most recent Health snapshot at `.claude/observability/dashboard.md`.
- Most recent security findings at `.claude/observability/security/findings-*.jsonl`.
- Anti-rot pending queue at `.claude/observability/refresh/pending.jsonl`.

## The 6 Checks (run in order; STOP on first FAIL unless `--force`)

### Check 1 — PLAN/SPEC satisfaction

Every SPEC In-Scope Scenario in `specs/SPEC-{slug}.md` (when SPEC exists) is covered by a passing test in the work unit's diff, OR has an explicit waiver recorded in the PLAN's `## ❓ Open Questions` resolution.

```bash
# When SPEC exists:
- For each S1, S2, ... in SPEC: confirm a test function `test_s<N>_*` exists and passes.
- For each PLAN phase exit-criterion: confirm the criterion command runs GREEN.
```

FAIL when: any scenario lacks coverage AND lacks waiver.

### Check 2 — Regression smoke

Run the project's full check suite. Pick the toolchain that matches the project:

```bash
# Python:
!uv run pytest -q
!uv run ruff check src/ tests/
!uv run mypy --strict src/
# Rust: cargo test && cargo check
# Node: pnpm test && pnpm build
```

If the harness has its own `.claude-verify.sh phase_<N>` script, prefer it over the generic toolchain commands.

FAIL when: any subprocess returns non-zero.

### Check 3 — Health delta

Read the prior Health score from `.claude/observability/dashboard.md` (the snapshot recorded at the start of this work unit, or the last `/hm:ai-readiness` run).

Recompute current Health (or invoke `/hm:ai-readiness` if a fresh score is needed).

FAIL when: `current - prior < -5` (Health dropped more than 5 points). Mid-work-unit dips are normal; a 5+ point drop signals quality regression.

### Check 4 — Anti-rot pending queue

Read `.claude/observability/refresh/pending.jsonl` (when present).

FAIL when: any pending item has `relevance_score >= 0.8` AND `category in {security, breaking-change}`. These are blocking items — `wrapup`-ing while ignoring them silently absorbs the rot.

PASS when: queue is empty, or remaining items are below the blocking threshold.

### Check 5 — Security high findings

Read the most recent `.claude/observability/security/findings-*.jsonl`.

FAIL when: any finding has `severity == "high"` AND `resolution != "accepted-risk-with-rationale"`. Resolutions must be deliberate (recorded in PLAN ADR or wrapup commit body).

PASS when: zero unresolved high findings.

### Check 6 — Worktree merge cleanliness

When worktree isolation was engaged (`.worktrees/execute-*` exists or did exist), confirm the merge happened cleanly:

```bash
!git status
!git diff --check  # detects whitespace conflicts
```

FAIL when: there are unmerged paths, conflict markers, or unresolved merge state.

PASS when: working tree is clean OR has only the staged changes from `/hm:execute` Step 5 `stage-only`.

## Output

Write **both** formats:

### Text (stdout, for humans)

```
=== /hm:verify ===

[1/6] PLAN/SPEC satisfaction       ✅ PASS
[2/6] Regression smoke             ✅ PASS
[3/6] Health delta                 ✅ PASS  (87 → 89, +2)
[4/6] Anti-rot pending queue       ❌ FAIL
        2 items at relevance≥0.8 + category=security:
        - CVE-2026-12345 in dependency `httpx` (pending since 2026-05-01)
        - Anthropic blog "tool-use schema v3" (pending since 2026-05-03)
        Run /hm:refresh to triage these before wrapup.

[5/6] (skipped — stopped at first FAIL)
[6/6] (skipped — stopped at first FAIL)

RESULT: FAIL — 1 of 6 checks failed.
Override: --force --reason="<text>"  (logs to verify-<date>.jsonl with the reason)
```

### JSON (`.claude/observability/verify-<YYYY-MM-DD>.jsonl`, append one record)

```json
{
  "timestamp": "2026-05-08T14:23:01Z",
  "stage": "verify",
  "result": "FAIL",
  "checks": [
    {"id": 1, "name": "plan_spec_satisfaction", "result": "PASS"},
    {"id": 2, "name": "regression_smoke", "result": "PASS"},
    {"id": 3, "name": "health_delta", "result": "PASS", "delta": 2, "prior": 87, "current": 89},
    {"id": 4, "name": "antirot_pending", "result": "FAIL", "blocking_items": 2, "items": [...]},
    {"id": 5, "name": "security_high", "result": "SKIPPED"},
    {"id": 6, "name": "worktree_merge", "result": "SKIPPED"}
  ],
  "force_override": false,
  "override_reason": null
}
```

When `--force` is set, append the same record with `"force_override": true, "override_reason": "<text>"`.

## Procedure

1. Read inputs (PLAN, SPEC, dashboard, security findings, pending queue).
2. Run Check 1. If PASS, continue. If FAIL: emit text + JSON record + STOP (unless `--force`).
3. Repeat for Checks 2-6.
4. Emit final RESULT line + JSON record.
5. When `--force` is set with FAILing checks: emit text + JSON record with override flag + reason, then return PASS exit code (let the workflow proceed). Wrapup will surface the override in the commit body footer.

## Outputs

- Text summary on stdout (human-facing).
- One JSON record appended to `.claude/observability/verify-<YYYY-MM-DD>.jsonl`.
- Exit code: `0` for PASS or `--force` override; non-zero for FAIL without override.

## Quality Bar

- The gate is **non-negotiable**; bypassing requires `--force --reason=<text>`.
- A failed check produces actionable evidence (which scenario / which test / which finding) — not just a red line.
- The JSON record is parseable by the autoloop driver to make stop/continue decisions without re-parsing stdout.
- `--force` is recorded in the JSONL with the reason — auditable later.
- No check produces false PASS by missing inputs (e.g., a missing `findings-*.jsonl` is a soft skip, not a silent PASS).

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific verify checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the verify stage. Preserved across harness-maker upgrades. -->
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

    /hm:exec-rev-wrap-ver <task description> --with-reviewers=security-reviewer,performance-reviewer
    /hm:exec-rev-wrap-ver <task description> --with-skills=context-linter

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
