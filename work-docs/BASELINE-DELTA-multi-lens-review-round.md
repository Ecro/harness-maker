# BASELINE-DELTA — multi-lens-review-round (2026-08-10)

Attribution for every surface-baseline number this task moved. Nothing here was transcribed by
hand: the JSON was rewritten from `measure_surface()` + `payload_digest()`, and the two test
tables were set from that same measurement.

## Direction: this change made the shipped surface **LARGER**

Both aggregates moved **up** — `claude` 371066 → **377215**, `codex` 300082 → **306231**, +6149
each. Say it plainly rather than leaving it to be inferred from a table: a delta document that
lists numbers without naming the direction is technically complete and practically misleading.
The task's *justification* is finding more defects per round, not spending fewer characters.

## Who may move these, and why (ADR-010)

The surface baseline is owned by the phase that froze it. The failure mode the ownership rule
exists to prevent is **`ratchet-rebaselined-by-its-own-subject`** — the change being measured
quietly re-freezing the yardstick it is being measured against, so the ratchet records whatever
just happened instead of constraining it. This document is that rule's escape hatch, not a
bypass of it: the re-baseline is deliberate, argued below, attributed key by key, and lands in
the same commit as the change that caused it.

`payload_digest` moved because the surface mapping it hashes moved; it is derived, not decided,
and was recomputed by the generator rather than edited. `render_sha` did **not** move — see the
final section for why that is deliberate.

## What changed in the render

`templates/stages/execute.md.j2`, Phase A.5 only:

- One `test-reviewer` `Task(` dispatch → **three**, one per lens (`red-correctness`,
  `discrimination`, `coverage`), in a **single message**.
- A merge algebra for the three outputs, **recomputed** rather than read off any lens's header:
  PASS iff every lens dispatched this round returned PASS **and** the merged carriers are clean;
  `blocking_issues` unioned and deduped on `test_file:test_function:category` carrying a line
  **list**; `scenarios_missing` unioned; worst-quality `per_scenario`; `passing_tests`
  **demoted to advisory**.
- Three repair arms, one per carrier: rewrite the named functions, author a test per
  `scenarios_missing[]`, and retarget-or-delete for a `per_scenario` FAIL that names no blocking
  issue (an empty `covered_by` routes to the authoring arm instead).
- Retry rescoped to **rounds** (2). **Any repair re-dispatches all three lenses** — a single rule
  rather than a trigger list, because a rewrite changes a file the other lenses already judged
  and no per-lens condition can express that without contradicting "no verdict carries". The
  handoff carries the before/after of rewritten functions and the after-only text of authored
  ones, with no `git` invocation.
- Also touched, because the seam ran through them: `test-reviewer_body.md.j2` (its Hard Rule used
  to discard out-of-category findings into a non-existent `suggestions` field) and
  `stuck_body.md.j2` (still named the budget in "attempts").
- Ledger: one row per **round** (ADR-007), not per dispatch.

## Numbers

| Artifact | Field | Before | After | Δ |
|---|---|---|---|---|
| `tests/structural/test_roundtrip_budget.py` | `_CLAUDE_ROUND_TRIPS["execute"]` | 15 | **17** | +2 |
| `tests/structural/test_command_size_budget.py` | `_ATOMIC_RATCHET["execute"]` | 34533 | **39343** | +4810 |
| `tests/structural/surface_baseline.json` | `claude` → `execute`.`round_trips` | 15 | **17** | +2 |
| `tests/structural/surface_baseline.json` | `codex` → `hm-execute`.`round_trips` | 14 | **16** | +2 |
| `tests/structural/surface_baseline.json` | `claude` → `execute`.`chars` | — | — | +2130 |
| `tests/structural/surface_baseline.json` | `codex` → `hm-execute`.`chars` | — | — | +2130 |
| `tests/structural/surface_baseline.json` | `aggregate_chars.claude` | 371066 | **377215** | +6149 |
| `tests/structural/surface_baseline.json` | `aggregate_chars.codex` | 300082 | **306231** | +6149 |

| `tests/structural/surface_baseline.json` | `payload_digest` | — | recomputed | derived |

**Four increments, not one.** +2130 landed with the feature; **+1724 / +1149 / +1146** landed in
review rounds 2, 3 and 4 and are **entirely defect repair**, not new surface — every one of them
added **zero** round-trips. Rounds 3 and 4 were repairing rounds 2's and 3's *own fixes*: the
review found a fix-induced defect in every single round. What the repairs bought, in order —
round 2: a retry-round PASS rule that could not be satisfied, a dead dispatch with no repair
path, and a brief routing out-of-lens findings into a `suggestions` field the schema does not
have (so they were discarded and the lens returned PASS); round 3: a merge that trusted a
lens's self-reported PASS, a blocking `per_scenario` state with no repair action, and tests
authored for `scenarios_missing[]` that no discrimination lens ever saw; round 4: a re-dispatch
clause that was **unreachable** by construction while the hole it was written for stayed open.

The only commands whose entries moved are `execute` (claude) and `hm-execute` (codex) — the two
renders of the one edited template. Every other command's `chars` and `round_trips` are
byte-identical, which is what makes the aggregate delta attributable to this change alone.

`round_trips` moved on **exactly two** entries — `claude/execute` and `codex/hm-execute` — and on
no other command. The A.5 block has no `{% if is_codex %}` guard, so it renders into both.

**The round-trip figure is an over-count and that is known.** `count_round_trips` adds every
`Task(` occurrence, but the three lens dispatches leave in ONE message and cost one main-loop
turn. This is the same over-count `research`'s three-`Explore` fan-out already carries; see
`test_the_fan_out_is_counted_as_three_though_it_costs_one_turn`. The rule was not relaxed —
relaxing it to recognise "adjacent `Task(` in one fence" would silently un-count real serial
dispatches elsewhere.

## Why the character ratchet was re-baselined rather than offset

The aggregate arms (`test_aggregate_shipped_surface_does_not_grow`) sat at **exactly zero slack**
in both variants — 371066/371066 and 300082/300082 — so this change could not ship as a net
addition without cutting ~2.1k characters of instruction from elsewhere in `execute.md.j2`.

That offset was attempted and abandoned on a deliberate decision (2026-08-10). **The reason first
recorded here was wrong for this change, and the correction is the point of this section.**

The original wording said: *prompt text gated behind the `instrumentation` axis is measuring
apparatus, not shipped instruction, and should not compete with the thing it measures* — the axis
defaults OFF for a fresh install, yet the baseline is measured against this repo's own
`harness.yaml` where it is ON, so the ledger recipes are fully charged to the ratchet.

**That principle is sound and it does not apply here.** Measured after the fact by rendering
`execute` with the axis ON and OFF, before and after this change (Production, claude-only fixture):

| | before | after | Δ |
|---|---:|---:|---:|
| `execute` total (instrumentation ON) | 36034 | 40609 | **+4575** |
| ├ shipped instruction (axis OFF) | 34171 | 38953 | **+4782** |
| └ instrumentation block | 1863 | 1656 | **−207** |

The instrumentation block **shrank** — the per-dispatch ledger bullets collapsed to per-round ones.
**Every character this change added is shipped instruction**: prose a user's `/hm:execute` reads on
every invocation. Nothing here was measuring apparatus, so the "instrument vs. product" argument
had zero purchase on this case. A true general principle was applied to a case it did not cover,
and the result read as *"the growth was only instrumentation"*, which is false.

**The actual reason the ratchet was re-baselined:** the user decided (2026-08-10) that the ratchet
is a measuring instrument rather than a design constraint, and directed that the block not be
contorted to fit it. Under that decision the shipped-surface growth was **accepted**, not
explained away. The zero slack was a real constraint and this change really did grow the shipped
surface — by ~4.8k in `execute` alone, +6149 across the repo's own render.

The standing debt in the last section is unchanged and, if anything, now better founded: excluding
instrumentation from the measurement remains the right fix to the *measurement*, but it would not
have absorbed this change.

Compaction was still applied where it cost nothing — the shared reviewer brief is stated once
instead of three times, and the per-dispatch ledger bullets collapsed to per-round ones.

**One compaction was tried and reverted.** A single parameterised `Task(` template with a
`<lens>` placeholder cost ~500 fewer characters *and* zero round-trips. It was reverted: the
repo's only fan-out precedent uses three literal lines, a literal example is what an executing
model imitates, and picking the cheaper form *because* it was cheaper is precisely the move that
produced two of the four P0s in `opus5-selfreview-vs-harness-gates`.

## `render_sha` is deliberately unchanged

`surface_baseline.json` still carries `bdf533a0…`. `assert_sha_is_durable` refuses to freeze
against a task-branch commit — a squash-land deletes it, so the SHA would be green locally and
red in CI. The committed SHA is a durable base commit and the tests only require it to *be* a
commit, so leaving it is legal; the numbers say "current tree" and the SHA says "the durable
point they should be re-frozen from".

**Follow-up required after this lands:** run
`python -m tests.structural._surface_baseline` from the **base** checkout to re-freeze
`render_sha` against the landed commit. Skipping it leaves the two fields describing different
trees — harmless to the gates, misleading to the next reader.

## Test whose meaning changed

`test_stage_agent_ledger_wiring.py::test_every_dispatch_site_is_accompanied_by_an_emit_line` used
to derive its expected emit count from the number of dispatch sites. Under ADR-007 the unit for
`execute` is the **round**, so three dispatch sites correctly accompany one emit line. The guard
was re-pointed rather than weakened: for `execute` it now also asserts the template states the
row is per-round, so the check cannot decay into the bare presence test this file's own history
records as insufficient.
