---
generated_by: harness-maker
harness_maker_version: 0.6.2
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 8a6eb5381c39daf6f079788436b643c810eb926bc63325744105014335216eae
---
# /hm:exec-rev


## Stage: execute

# Stage: execute

> Atomic stage. TDD machine driven by PLAN. Phase A → A.5 → B → C → D, with worktree isolation and **NO commits** (wrapup owns commits).

> Invoked as part of the **exec-rev** workflow.


## Communication Protocol

- Be direct. No flattery, no preamble.
- If a PLAN phase is under-specified, surface it before writing tests — don't guess.
- Don't hide test failures. Compiler/test errors go in the response verbatim.
- When Phase A.5 returns FAIL, treat the test-reviewer's reasoning as authoritative — rewrite, don't argue.

## Purpose

Apply the PLAN's phases to the codebase. Default mode is **TDD**: tests are written from SPEC's In-Scope Scenarios first, the implementation follows, and each PLAN phase exits only when its exit-criterion command is GREEN.

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

Engage isolation if `harness.yaml.worktree.scope` includes `execute`. The `worktree-isolator` skill is documentation-only — its trigger-based dispatch is probabilistic in Cursor IDE and can silently skip, leaving safety-critical edits on the main branch. **Invoke the worktree CLI directly** so isolation is deterministic across both IDEs.

**Idempotent under `/hm:loop`**: when this stage runs as part of a loop iteration, the loop has already engaged a per-loop worktree at step 5. The `worktree create` CLI detects we're already inside `.worktrees/<name>/` and returns that path — no nested worktrees, just reuse.

```bash
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260508T0357Z python -m harness_maker.worktree create execute "$(pwd)"
```

Read the **single line** the command prints — that is the contract for the rest of this stage. Two cases:

- **Absolute path** like `/path/to/project/.worktrees/execute-20260506T1830Z` → isolation engaged. **Treat that exact string as `<WT>` for the rest of this stage.** You (Claude) MUST substitute the literal absolute path everywhere `<WT>` appears below — **do NOT use a shell variable**: each `!` block is a fresh subshell, so `worktree_path=...` assignment is lost between blocks.
  - Every Read/Write/Edit call uses absolute paths starting with `<WT>/`.
  - Tests / lints / type checks: `!cd <WT> && <cmd>`.
- **Empty output** → `worktree.scope` does not include `execute`. No isolation; operate in `cwd`. Skip the finalize step at end.

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
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260508T0357Z python -m harness_maker.worktree finalize <WT> stage-only
```

```bash
# Stage halted on a blocker — preserve the worktree for inspection:
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260508T0357Z python -m harness_maker.worktree finalize <WT> fail
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

> Invoked as part of the **exec-rev** workflow.


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

### Step 3 — Parallel reviewer invocation

Run all selected reviewers in a **single message with multiple Task tool uses** for parallel execution. Each reviewer:
- Reads the diff with full context (use Read on changed files end-to-end, not just the patch).
- Walks the runtime path the diff touches — what runs first, what state mutates, what can fail.
- Returns findings per the Finding Schema partial: `{severity, file, line, summary, suggestion, reasoning?, …}`.

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
