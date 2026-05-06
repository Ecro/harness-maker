---
generated_by: harness-maker
harness_maker_version: 0.5.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/execute.md.j2
provenance: official
content_hash: c62a3b080fe5dcb91b8f39430a1dc4c5b1b194b2ac5c21ac19ec3558065d2ca0
---
# Stage: execute

> Atomic stage. Implement the plan with continuous verification.


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
