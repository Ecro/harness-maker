---
type: baseline-delta
task_slug: execute-step5-model-mismatch
created: 2026-08-08
owns: [surface_baseline.json]
summary: "Baseline movement from gating execute's Step 5 finalize to ephemeral loop worktrees"
---

# Baseline delta — execute-step5-model-mismatch

Baseline ownership follows **ADR-010**: one task owns the ratchet, and a task that
re-baselines the guard it tripped is `ratchet-rebaselined-by-its-own-subject` (count:2).
This document is this task's own attribution — it does not amend any previous task's.

Figures written **after** the final regeneration, per the correction recorded in
`BASELINE-DELTA-validator-pass-cap.md`: any later edit to a template invalidates them, and
that document had to be corrected four times for exactly that reason.

## 1. Aggregate

| | Before | After | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 364 738 | 366 439 | **+1 701** |
| `aggregate_chars.codex` | 297 901 | 299 602 | **+1 701** |

**Direction: larger, deliberately, under an explicit instruction that a ceiling gives way to
correctness.** Two components:

**+424 — the Step 5 gate.** The first draft added +954; compressing the new gate and the
now-loop-only legacy prose around it got that to +424, and further golfing was producing
worse sentences rather than fewer characters. What remains buys a runtime branch check that
prevents a destructive merge.

**+595 — the loop's per-iter preflight override.** See §3: this was going to ship as a
documented open problem, and shipping the *knowledge* of a work-stranding path while leaving
the path open is the worse half of the trade. The loop already gives wrapup this exact
override; the per-iter stages were simply missed.

**+682 — the wrapup receipt paragraph, restored.** It was written during the previous task,
**reverted in `a3cd8c16`** to avoid moving this number, and brought back here. That revert
was the wrong call: the paragraph tells the operator that `steps.stage[]` carries a
`worktree-sweep` row and that `index_after` must contain their CODE — and `wrapup_land`
omitted the implementation from its own commit twice while reporting `ok: true`. A field
that is the only distinguisher between "committed the work" and "committed the paperwork" is
not narration. Recorded rather than silently re-added, because reversing a documented
decision without saying so is how a ratchet stops meaning anything.

`payload_digest` moved with them. It is a hash over the whole measured surface, so it changes
whenever any command's character count does — it carries no independent information here, and
a delta that did NOT move it while the aggregate moved would be the anomaly worth explaining.

`render_sha` moved to `203b540c` (the 0.50.0 release commit, this task's base). It records the
commit the baseline was rendered from, so it moves on every legitimate regeneration; the
adjacent gate only accepts a **durable** sha, which is why an amend that orphans one has
previously had to be re-frozen rather than left pointing at a commit nobody can fetch.

The per-command ratchet `execute` was raised 33 774 → 34 533 in
`tests/structural/test_command_size_budget.py`, under the ADR-011 bar quoted in that file:
compaction first (+954 → +424, −55%), residue is unguarded correctness. The reasoning is
recorded at the table entry, not only here.

## 1b. Per-key movement

| Key | Carries |
|---|---|
| `execute` (claude) / `hm-execute` (codex) | the Step 5 rewrite — the runtime branch check plus the compression that paid for most of it |
| `loop` (claude) / `hm-loop` (codex) | the one-paragraph correction to the loop driver's description of what `/hm:execute` does at Step 0 |
| `wrapup` (claude) / `hm-wrapup` (codex) | the restored receipt paragraph — the `worktree-sweep` row and the `index_after` check |

The equality pins in `tests/unit/test_render_wrapup_delegation.py` moved with it, 658 → 668
and 691 → 701 (uniform +10, the same paragraph in both presets), attributed at that
parametrize.

Both IDE variants move because the change is in the shared stage/command templates and each
variant renders its own copy. A move in only ONE variant would mean the edit reached one render
path and not the other — the asymmetry this per-key arm exists to expose.

## 2. Attribution — what moved and why

**`commands/hm/execute.md` and `stages/execute.md` (+~500, offset by ~-80 of compression).**

Step 5 told the operator to run `worktree finalize <WT> stage-only`, and the stage's Step 0
is the per-task `task-preflight`. Both blocks render under the same `wt_on` condition, so on
every isolated `/hm:execute` the document instructed a **legacy-model** merge into base on a
worktree that `task-land` owns. Its prose still referenced "Step 0 `worktree create`" and
"your `execute-<uuid>-<ts>` worktree from Step 0" — a step the rendered document no longer
contains, because `/hm:execute` stopped creating ephemeral worktrees.

The finalize is correct for the OTHER model: under `/hm:loop`, `<WT>` is an `execute-<uuid>`
worktree and each iteration stages back to base. So the fix cannot be a render-time gate —
both models reach the same rendered text. Step 5 now opens with a runtime read of
`git -C <WT> rev-parse --abbrev-ref HEAD` and skips itself on `hm/*`, which is the same
discriminator `/hm:wrapup` Step 7.7 already uses, and mirrors the loop's existing
"**SKIP wrapup's Step 7.7**" override for the symmetric case.

**`commands/hm/loop.md` (≈0).** Replaced a stale paragraph asserting that standalone
`/hm:execute` "calls `worktree create` again" — it does not, and has not since the per-task
model landed — with the actual contract between the two.

## 3. The second `<WT>` — found while writing this document, then closed

Under loop dispatch the driver reads each stage file inline and runs *every* step, Step 0
included. `task-preflight` **creates** `.worktrees/<slug>/` when it is absent and prints that
path as `<WT>` — so one iteration carried two `<WT>` definitions, the loop's `execute-<uuid>`
and the stage's task worktree. The resolutions are not equally bad:

- follow the loop's → the task worktree is an orphan (directory, `hm/<slug>` branch, registry
  row, marker). Mostly self-cleaning via `prune_stale`. Friction.
- follow the stage's → the iteration's work lands on `hm/<slug>` while loop-close finalizes
  the **empty** ephemeral worktree. The work is stranded and invisible to convergence, with
  every exit code 0.

The loop already carried this exact override for **wrapup** ("SKIP wrapup's own worktree
preflight / Step 0"), which is evidence someone hit the shape once and fixed it where they
were standing. The per-iter stages never got it. They do now, gated on `wt_on`, asserted by
`test_loop_tells_per_iter_stages_to_skip_their_own_preflight` with a control that the general
"without skipping any" rule survives.

**Honest limit: no observed incident.** `hm/*` branches and `.worktrees/` were checked and
hold only this task's own entries. The defect is derived from reading two documents that
contradict each other in one context, not from a measured loss — so the *possibility* is
established and the *frequency* is unknown. It ships closed rather than documented, because a
work-stranding path left open with a written description of how it strands work is the worse
half of that trade.

## 4. What this still does NOT claim

The two worktree models are not unified — they still coexist, and a reader of `execute.md`
still has to run a branch check to know which one they are in. This task removes the
destructive instruction and the ambiguous second claim; it does not collapse the models.
