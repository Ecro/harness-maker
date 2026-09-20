---
type: review
task_slug: plan-stage-absorption
created: 2026-09-20
run_id: 1a1a58554622
review_base: a950a22c
rounds_run: 2
grade_round_1: C
threshold: A
summary: "10 findings, 9 fixed in round 2; 1 manual-only; one inherited red left to its owner"
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/autopilot.py
    - src/harness_maker/command_registry.py
    - src/harness_maker/hooks/autopilot_autoarm.py
    - src/harness_maker/readiness.py
  scenario_misses: []
  task_slug: plan-stage-absorption
  computed_at: 2026-09-20T00:00:00Z
---

# REVIEW — plan-stage-absorption

## Drift gate

**`scope_violation`.** Four Python files changed that no PLAN phase's Affected-components table
names. All four are *readers of the retired stage name*, found by the AST gate rather than by the
PLAN: `autopilot.py` and `hooks/autopilot_autoarm.py` construct `AtomicStage` from a raw pipeline,
`readiness.py` carries the `atomic_stages` set, `command_registry.py` lists the stage commands.
The PLAN under-listed its own blast radius; the code is correct. Recorded rather than waived.

Also flagged: four templates the PLAN declared (`wrapup.md.j2`, `review.md.j2`,
`loop-p5-batch.md.j2`, `trajectory-monitor.md`) needed no change. `wrapup` and `review` moved
anyway — through `step_manifest.md.j2`'s pipeline interpolation, not through an edit.

## Lens coverage

`{"exercised": [design, functionality, robustness, consistency, security, concurrency, tests],
"missing": [], "blocks_approval": false}` — Production, round 1, run `1a1a58554622`.

Four dispatches: `code-reviewer` (four core lenses), `security-reviewer`,
`concurrency-reviewer`, `test-reviewer`. Plus **codex** as a cross-model voter, invoked once and
frozen at round 1.

## Round 1 — grade C

`review_consensus finalize`: P0 0 / **P1 6** / P2 2 / P3 1, `errors: []`,
`human_review_needed: false`, dispositions `accepted: 10`.

Two findings arrived with two independent voices, and those are the two that matter.

### 1. P1 — `execute.md.j2`: Step 0.3 verified a field Step 0.1 had not yet judged

*Voices: `functionality` (core lens) + `codex`.*

The rendered order was `0 → 0.3 → 0.1 → 0.2`. Step 0.3's checklist asserts
`spec_need_verdict` is present with a valid value; Step 0.1 is what judges and writes it. So
Step 0's authored frontmatter had to carry a guess — and `frontmatter_upsert` preserves what is
already there, so the guess was terminal. Step 0.1's own self-check asks whether the key is
*absent*, which it is not, so **no point downstream could detect the stale value**.

`/hm:verify` Check 6 then enforces against a verdict nobody judged. That is the same
`absent-case = feature black hole` shape this task exists to close, rebuilt one layer in.

The PIDA verifier confirmed it against the source, not just the ordering:
`spec_need.py` drops any already-present key from `additions`, so the later write no-ops.

### 2. P1 — `interview.py`: the retirement filter was a literal, and the gate could not see it

*Voices: `consistency` (core lens) + `tests` lens.*

`_parse_autonomy` filtered with `!= "plan"` instead of `drop_retired_stages`. The structural
gate this task shipped — "discover readers by AST, never hand-list them" — walks for
`AtomicStage(...)` calls. `interview.py` has none: pydantic performs the coercion inside
`AutonomyConfig.model_validate`. So the one reader the SPEC claimed was *discovered* was in fact
*listed*, and invisible to its own gate.

The next retirement would have filtered correctly in the two hook/CLI readers and passed the new
name into `model_validate`, which rejects the whole `autonomy` block and resets the user's level,
caps and pipeline to defaults — warning about the *old* retirement while doing it. No shipped
test would have gone red.

### 3–6. P1 — the Step 0.1 recipe and its writer

- `--rationale "<why>"` double-quoted model-authored text, where `$()` and backticks expand. The
  Codex branch of the same recipe already single-quoted it, and this file's own
  `stage_agent_ledger` recipe carries the strip rule. (`security`)
- `--verdict` / `--target` / the `--plan` path were unquoted, so shell tokenization precedes
  `_validate_slug` entirely. (`security`)
- `frontmatter_upsert` took an arbitrary `plan_path` with no root confinement — the only
  path-bearing argument in `spec_need.py` without one. (`security`)
- `frontmatter_upsert` was a read-decide-write with no exclusion. `atomic_write` is atomic for
  one writer's own replace; it establishes nothing across the sequence, so a second session's
  whole-file write drops the first's key silently. (`concurrency`)

### 7–9. P2/P3

- `frontmatter_upsert` preserved **per key**, so a present verdict beside an absent target got
  paired with the current call's target. Check 6 reads the two as one pair. (`design`)
- `spec.md.j2` still said "Prevents scope creep in `plan`". (`consistency`)
- `_render_plan` was dead and still read `commands/hm/plan.md`. (`tests`)

### 10. P2 — `manual-only`, not fixed

*Voice: `codex` alone.* Step 0.3 requires the frontmatter to carry "every key listed above"
while the Step 0 block marks `spec`, `research_doc` and `objective` omittable — so a valid PLAN
for a task where `/hm:research` never ran is rejected by its own verification step, retried once,
then stops.

PIDA disposition `accepted`; the contradiction is verbatim in the two blocks. But Step 4's tag
table makes a solo cross-model voice `manual-only`, which is not auto-fix eligible, so **it was
deliberately left in place**. It is a one-line wording change and is the first thing to pick up.

## Round 2 — the nine fixes

| Finding | Fix | Verified by |
|---|---|---|
| 1 | Step 0.3 moved after Step 0.2; the SPEC-need pair **removed** from Step 0's authored frontmatter, with a note saying why | `test_render_execute_spec_need`, golden re-capture |
| 2 | `drop_retired_stages` in `interview.py`; AST gate extended to discover `model_validate` sites on models carrying an `AtomicStage` field, the model set read from `models.py` | **mutant**: restoring the literal turns the gate red on `interview.py::<module>` and `::_parse_autonomy` |
| 3 | `'<why>'` in both branches + the strip rule | render test |
| 4 | every model-filled placeholder single-quoted | render test |
| 5 | `root` required keyword-only; `--root` required at the CLI, matching the module's other eight verbs | two new tests, incl. the CLI-omission arm |
| 6 | re-read immediately before the splice; **return values read back off disk**, so a caller that lost the race is told the peer's value rather than its own | property test arm |
| 7 | preservation is now **per pair**: verdict present → preserve, fill an absent target as `repaired`; verdict absent → write both fresh, replacing an orphan target | named example test + rewritten property |
| 8 | reworded | render |
| 9 | deleted | — |

Reordering Step 0.3 alone would not have fixed finding 1 — the guessed value would still be
written and preserved. Removing the pair from the authored frontmatter is the half that closes it.

**The fix surfaced a gate this task built, working.** Dropping the two keys from Step 0's block
made `test_plan_reader_baseline` report `verify.md.j2` as reading keys nobody writes. The writer
had not disappeared; it had changed shape from a declared block to a verb call. The detector now
credits `spec_need frontmatter-upsert` as authorship, with the key set imported from
`spec_need._SPEC_NEED_KEYS` rather than restated.

### What round 2 did NOT do

**No round-2 lens re-dispatch was run.** Each fix was verified against targeted tests and, for
finding 2, a mutant — but the grade was not re-established by a fresh reviewer pass. Round 1's
`C` is therefore the last *reviewed* grade, and the nine fixes are attested by their tests, not
by a second reviewer round. Stated here rather than implied, so nobody reads a green suite as a
re-review.

## Gates

`ruff check` ✅ · `ruff format` ✅ · `mypy --strict` ✅ (150 files) · full suite **8794 passed,
20 failed → all 20 addressed**: 8 snapshots regenerated, 8 delta-doc/attribution rows updated to
the re-frozen baseline, 1 instruction-preservation allowlist entry, 1 autopilot golden
re-captured with a dated docstring entry, 1 left red (below), 1 resolved by the delta-doc update.

> The background runner reported `exit code 0` for a run whose summary line read
> `20 failed`. The summary line is the only trustworthy signal.

### Inherited red, not fixed

`test_deliverable_single_source::test_gitignore_negations_match_the_source` —
`gitignore-only: ['MUTATION']`. `.gitignore:123` negates `work-docs/MUTATION-*.md` but
`worktree.DELIVERABLE_PREFIXES` lacks the prefix. It arrived with `865e3ef5`, is still live on
`main`, and neither file is in this change set. It belongs to the session currently working
`mutation-survivors-and-approval-p2s`; fixing it here would collide with their in-flight work.

## Surface

Re-frozen after the fixes rather than before: claude `400977 → 401697`, codex
`339385 → 340105` (+720 each). Final against the pre-task baseline: claude **−43000 (−9.7%)**,
codex **−37927 (−10.0%)**. Attribution in `BASELINE-DELTA-plan-stage-absorption.md`.
