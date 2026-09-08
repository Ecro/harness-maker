---
type: baseline-delta
task_slug: token-efficiency-autopilot-ux-speed
status: in-flight
created: 2026-09-08
summary: "Attribution for the net +1,865-char shipped-surface delta across Phases 1, 4, 5 and the review fixes"
---

# BASELINE-DELTA — token-efficiency-autopilot-ux-speed

Attribution for the `surface_allowance` block in `PLAN-token-efficiency-autopilot-ux-speed.md`.
An allowance without this document is the thing the mechanism exists to replace — an unexplained
number that makes the budget bigger.

## What grew, measured

| Phase | Variant | Was | Now | Delta |
|---|---|---|---|---|
| 1 | `claude` | 435,437 | 435,484 | **+47** |
| 4 | `claude` | 435,484 | 436,940 | **+1,456** |
| 5 | `claude` | 436,940 | 436,886 | **−54** |
| review fixes | `claude` | 436,886 | 437,302 | **+416** |
| — | **total against the frozen baseline** | 435,437 | 437,302 | **+1,865** |

An earlier revision of Phase 4's prose measured 1,684. 182 of those characters were a note about a
*test convention* (why an agent name is left unbackticked) — information for template authors that
the model reading the rendered command cannot act on. It moved into a Jinja comment, which renders
to nothing, and the figure came back to 1,503. Recorded because "explain it in the prose" is the
default instinct and it is billed per harness, per invocation.

`surface_allowance.chars` is the **total** (1,449), not the per-phase increment — the gate compares
the live figure against the frozen baseline plus the allowance, so an allowance carrying only the
latest phase's delta would fail on the earlier one. It is tightened to the measured figure at each
phase rather than left as a loose ceiling: an allowance carrying slack is exactly as unattributed as
no allowance, for the size of the slack.

Measured by `tests/structural/test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow`
and corroborated by `tests/structural/test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`,
both of which are **zero-tolerance** — not a 2% band. This is the whole growth of Phase 1; no
other rendered surface moved.

## Why, exactly

One string, added to **both** invocation branches of `wrapup_land`'s typed manifest in
`src/harness_maker/templates/stages/wrapup.md.j2` (`{% if is_codex %}` at :598 and `{% else %}`
at :602):

```
 --optional work-docs/BASELINE-ledger-rollup.md
```

47 characters × 1 branch reaches the `claude` variant's aggregate; the codex branch feeds the
`codex` variant.

## Why it could not be avoided

The roll-up is the artifact ADR-002 introduces to make measurements survive a clone. `work-docs/`
is **not** blanket-staged: the `worktree-sweep` row that would otherwise catch an unnamed file
records `skipped-not-isolated` when the worktree IS the base, so on a `worktree.enabled: false`
harness the roll-up would be written and never committed — the exact silent loss this unit exists
to end (SPEC risk R3). Naming it in the typed manifest is the only mechanism that stages it there,
and the manifest is rendered prose, so naming it costs rendered characters.

Two cheaper alternatives were considered and rejected:

- **Rely on the `worktree-sweep`.** Rejected: it is the branch that does not run in the case that
  matters.
- **Use `{{ config.work_docs.dir }}`** as the neighbouring manifest entries do. Rejected: the
  writer hardcodes `autopilot_ledger.ROLLUP_RELPATH`, so a configured directory would stage a path
  the writer never writes. The non-default `work_docs.dir` case is an accepted SPEC limitation,
  inherited from both worktree dirt-filters.

## Phase 4 (+1,455) — why, exactly

Two stage-guarded blocks added to `agents/_partials/second_opinion_dispatch.md.j2`, which this
repo renders because `second_opinion.models` is `["codex"]`:

- a review-stage block telling the model to run the invoker with `run_in_background: true` and
  dispatch the Pass 1 fan-out without waiting;
- a plan-stage block telling it **not** to, because `/hm:plan` injects the adapted findings into
  `plan-validator`'s prompt in its very next step, so a backgrounded call there would leave nothing
  to inject and silently make plan validation Claude-only.

**Why it could not be cheaper.** The partial is shared between the two stages, so a single
unguarded instruction would have broken the plan stage while the review-stage test went green — the
guard is the load-bearing half, and it costs a second block. The prose is what the model reads at
dispatch time; there is no non-rendered surface that could carry it.

**What it buys, and what it does not.** ADR-011 of the review work hoisted the cross-model call to
run "concurrently with Pass 1" and `run_in_background` appeared **nowhere** in the harness, so the
foreground Bash blocked for up to `CODEX_TIMEOUT_S=300` before the first reviewer was dispatched.
This wiring is what that decision always assumed. It does **not** buy a verified saving: AC-006's
oracle is one real cross-model dispatch, no second-opinion CLI is installed here, and the SPEC
records the AC as MECHANISM LANDED, ORACLE UNVERIFIED rather than green.

## Phase 5 (−54) — why, exactly

Phase 5 is the only phase in this unit that **removes** rendered surface, and both removals are
consequences of an AC rather than an optimization:

- `templates/stages/review.md.j2` drops `- Start from \`harness.yaml.reviewers.enabled\`.` (**−47**).
  AC-015: `lens_dispatch(preset)` never reads that list, so narrowing it to two reviewers still
  dispatches four. The sentence named a lever that does not exist. It is **retracted, not reworded** —
  A.5 round 1 demonstrated that a form-based test for "misleading imperative" had both a false
  negative (three rephrasings that still mislead) and a false positive (it flagged the intended
  correct wording), whereas the key's absence from the rendered command is mechanical.
- `templates/agents/_partials/step_manifest.md.j2` corrects the disclosed default for
  `autopilot_persistent` from `false` to `true` (**−1 × 7 commands = −7**). AC-007: the class
  default is `True`, and this line renders into every stage command, so the wrong value shipped
  seven times per harness.

Neither edit touches the autopilot advance block, so Phase 3's byte-neutrality claim for that block
is unaffected. `tests/structural/autopilot_gate_golden.json` carries a `rebases` row saying so.

## Review fixes (+416) — why, exactly

`/hm:review` returned two P1s that could only be fixed by adding rendered instructions, because in
both cases the defect *was* the absence of one:

- **`wrapup.md.j2` gains the roll-up producer (+~380).** The manifest already staged
  `work-docs/BASELINE-ledger-rollup.md` as `--optional` and **nothing wrote it** — grep for
  `autopilot_ledger` across every template returned one hit, the `smoke` verb in `health.md.j2`. So
  on any harness where an operator did not type the CLI by hand, `wrapup_land` recorded
  `absent-optional` and ADR-002's "survives a clone" guarantee was unreachable. A manifest entry for
  a file no template generates is AC-014's own defect class wearing AC-001's clothes, and it was
  found by a reviewer, not by me — I had generated the file by hand during review and mistaken that
  for the workflow working.
- **`health.md.j2` gains `--targets {{ config.targets | join(',') }}` (+~36).** Phase 2 added
  `smoke_check`'s `targets` parameter to remove a permanent false alarm on a cursor-only harness, and
  the rendered command never passed it, so `targets=None` kept `applicable` True and the false alarm
  shipped unchanged while a unit test saw the fix. Same class again, in the phase whose subject is
  that class.

Neither is prose for a human: both are commands the model executes. The `wrapup` per-command ceiling
now sits 26 chars from its band, which is recorded here rather than absorbed by widening the band —
the next edit to that command has to compact something, which is the ratchet working as intended.

## Scope of the allowance

`chars: 1865` **and `round_trips: {wrapup: 1, hm-wrapup: 1}`**. No phase declares a `commands`
entry — no per-command ceiling was raised (the two ratchet constants that moved are a
measurement-SUBJECT change under ADR-011's carve-out, recorded above and in ADR-011, not a raised
band).

The `round_trips` entry is the roll-up producer: one new `!` line in the `claude` variant's `wrapup`
and one new `Bash(` call site in the `codex` variant's `hm-wrapup`, 25 → 26 and 23 → 24. **This
section previously asserted "no `!` line or `Task(` site was added or removed"** — true until the
review fixes landed, false afterwards, and caught by `test_round_trip_counts_match_the_live_render`
rather than by me. That arm exists precisely because a `chars`-only baseline let a `configure` 3 → 4
drift age silently, and its docstring names the escape used here: declare the calls, because
regenerating `surface_baseline.json` rewrites the frozen `chars` in the same file and would destroy
the ratchet it sits next to.

**`_ATOMIC_RATCHET` DID move, in Phase 6, and this document said otherwise.** It read
"`_ATOMIC_RATCHET` is untouched — ADR-011 assigns the only re-derivation to Phase 6" — true when
written, false once Phase 6 landed, and A.5 round 1 caught it as the same
`attribution-doc-reports-the-wrong-movement` class this repo has paid for twice. The actual
re-derivation, measured through the pinned `_render` fixture:

| Command | Was | Now | Δ |
|---|---|---|---|
| `plan` | 55,322 | 62,703 | **+7,381** |
| `review` | 70,153 | 80,586 | **+10,433** |

The other five atomic commands are **byte-identical** across models-off and models-on, which is what
makes ADR-011's carve-out ("only `review` and `plan`") a measurement rather than an assumption; the
differential arm `test_ac_013_the_models_delta_is_produced_by_configuration` asserts exactly that, so
the day the partial is included in a third stage, the claim fails instead of rotting.

This is a **ratchet** re-derivation, not a `surface_allowance` entry: the aggregate figure is
unaffected (the flag was already on in this repo's own harness), so it does not belong in
`chars` — but it does belong in this document, which is the one place a reader looks for what moved.

**This allowance expires with the PLAN.** It is read only while the PLAN's `status` is
`planning`/`blocked`; once the PLAN closes, the baseline is re-frozen at the new figure by the
normal process and the allowance stops applying. Re-freezing `surface_baseline.json` *instead* of
declaring this allowance is the destructive act the mechanism exists to remove.
