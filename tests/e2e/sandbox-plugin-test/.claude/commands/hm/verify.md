---
generated_by: harness-maker
harness_maker_version: 0.5.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: a84a42a8869d10de5d1ea6ad9a201e5b8ad2c73d099058e9ccbe7feb7fb0f194
---
# Stage: verify

> Atomic stage. Pre-completion verification gate.


## Purpose

Block silent regressions and partial completions. Run a rigid checklist
that any work-unit MUST pass before being declared done. This is the
machine-checkable stop sign before `wrapup`.

## When to Run

- Just before `wrapup`
- At the end of every autoloop iteration
- On demand via `/hm:verify` whenever doubt arises

## Inputs

- Current working tree state
- PLAN / SPEC for the in-progress work unit
- Health snapshot, anti-rot pending queue, security findings

## Checklist (all must pass)

1. **PLAN/SPEC satisfaction** — every acceptance criterion has a passing
   test or an explicit waiver
2. **Regression smoke** — full pytest, ruff, mypy strict, project's own
   verify script (e.g. `.claude-verify.sh phase_N`)
3. **Health delta** — Health score did not drop more than 5 points vs.
   the prior snapshot
4. **Anti-rot pending** — no critical refresh items left unresolved
   (high relevance + security category)
5. **Security high findings** — zero unresolved HIGH-severity findings
   from the most recent security scan
6. **Worktree merge** — when worktree isolation is enabled, the worktree
   merges cleanly into the parent branch (no conflicts)

## Procedure

1. Run each check in order. Stop on the first FAIL.
2. On FAIL: emit a diagnostic with the exact failed check, the evidence,
   and a suggested next action.
3. On PASS: emit a single GREEN line and let `wrapup` proceed.

## Outputs

- `PASS` (zero failures) — proceed
- `FAIL` — list of failed checks + evidence (do NOT proceed to `wrapup`)

## Quality Bar

- The gate is non-negotiable; bypassing requires explicit user override
- A failed check produces actionable evidence, not just a red line

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific verify checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the verify stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
