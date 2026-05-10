# ADR-005 Verification: Codex Sandbox + git worktree Compatibility

> Status: PENDING — requires manual verification in a live Codex session.

## Background

ADR-005 (from `work-docs/PLAN-codex-target-support.md`) accepted the decision to **omit** a
`worktree_gate` from Codex hooks and instead verify empirically whether
`git worktree add` succeeds inside Codex's sandbox (Seatbelt on macOS, Landlock on Linux).

The `@hm-loop` skill now includes an explicit worktree fallback path (ADR-005 non-blocking):
if `Bash("uv run ... worktree create ...")` fails, the loop logs "Proceeding in-place" and
continues with `<WT> = $(pwd)`.

## How to Verify

1. Open a Codex session in a git repository (any project with harness-maker installed).
2. Invoke `@hm-loop "test goal"`.
3. Observe Step 5 of the loop procedure:
   - The skill will call `Bash("uv run --with <path> python -m harness_maker.worktree create execute $(pwd)")`
   - Read the output.

## Expected outcomes

| Outcome | What to record |
|---------|---------------|
| ✅ Worktree created successfully | Record: `git worktree add` works in Codex sandbox (PASS) |
| ❌ Error or empty output (sandbox blocked) | Record: sandbox blocks `git worktree add` (FALLBACK path engaged) |

If fallback engages, verify the message "Worktree creation failed — proceeding in-place" appears
in the Codex response before any file edits begin.

## Results

| Date | Codex version | Platform | Result | Notes |
|------|--------------|----------|--------|-------|
| — | — | — | PENDING | Not yet tested |

## Acceptance

- If worktree creation **succeeds**: ADR-005 is empirically confirmed. Update row above.
- If worktree creation **fails**: ADR-005 fallback is working as designed. Update row above.
  No code change needed — the fallback path is intentional.

## References

- ADR-005: `work-docs/PLAN-codex-target-support.md` § ADR-005
- Loop template Step 5: `src/harness_maker/templates/commands/hm/loop.md.j2` (worktree section)
- Research: `work-docs/RESEARCH-codex-loop-execute-gaps.md` § Gap 7
