---
type: baseline-delta
task_slug: plan-interview-comprehension
created: 2026-08-13
owns: [surface_baseline.json]
summary: "Baseline movement from the interview.comprehension.depth disclosure partial"
---

# Baseline delta — plan-interview-comprehension

Baseline ownership follows **ADR-010**: one phase owns the ratchet, and a phase that
re-baselines the guard it tripped is `ratchet-rebaselined-by-its-own-subject` (count:2).
This document is this task's own attribution — it does not amend any previous task's.

The change: `interview.comprehension.depth: minimal | standard | deep`, a shared Jinja
partial included by `/hm:plan` and `/hm:spec` that discloses the design picture the plan
stage already builds and — per its own Step 1 heading — does not show.

## 1. Aggregate

| | Before | After | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 377 215 | 380 334 | **+3 119** |
| `aggregate_chars.codex` | 306 231 | 308 250 | **+2 019** |

**Direction: the shipped surface got LARGER.** The two variants differ by exactly 1 100, and
that asymmetry is real rather than a copy error: the `/hm:configure` dimension ADR-003 adds
is `+1 100`, and `configure` **has no codex variant at all** — the codex surface carries 10
keys to claude's 15, and none of them is a configure skill. Verified against
`surface_baseline.json`, not inferred. (A previous delta document in this repo invented a
dual-render story to explain an asymmetry that did not exist; the check is cheap and the
failure it prevents is a believed-but-wrong cause.)

The movement is not uniform across the changed commands, and one of them is not this task's
doing — see §2.

> **Re-measured twice.** The first version reported `+2 474` on both variants; it was written
> before the `configure.md.j2` edit landed — the exact ordering failure §5 warns about,
> committed by the author of §5. The second went stale the same way when `/hm:review` landed
> four fixes. Both corrections are the same lesson §5 already states and neither was a
> care problem: **any round that touches a template invalidates these figures.** The numbers
> here are post-review-round.
>
> The review round moved them in **both** directions: `configure` grew another `+384` (the
> security finding — the flag was missing from §4's dispatch list entirely, so an LLM
> following §4 literally would never have emitted it), while `plan` **shrank `−455`** because
> the round found ADR-008 had gated only Step A's heading, leaving `/hm:plan` shipping two
> contradicting round preambles at the default depth.

**What a third party pays: nothing.** This is the one number that makes the maintainer's
cost defensible. At `interview.comprehension.depth: minimal` the rendered `/hm:plan` and
`/hm:spec` are **byte-identical** to the pre-change render, asserted by SHA-256 against an
immutable golden captured before any template edit
(`tests/structural/comprehension_zero_cost_golden.json`, AC-003) — not by character count,
which cannot distinguish a swapped line from an equal-length one.

This repo does not opt out. Its `.claude/harness.yaml` carries no `comprehension` key, which
ADR-006 resolves to `standard` as an accepted retrofit, so the fleet pays the full **+3 119**
(claude) / **+2 019** (codex).

> **The `_ATOMIC_RATCHET` figures and this document's §2 figures are NOT the same
> measurement, and they do not reconcile.** A round-2 reviewer flagged the gap and is right
> to: `plan` moves +1 092 in the ratchet and +1 211 here; `spec` moves +1 577 there and
> +1 198 here. One template edit cannot move one render by two amounts, so at least one
> "before" is stale.
>
> They measure different renders — the ratchet uses synthetic preset fixtures at `flag_on`,
> this document renders **this repo's own `harness.yaml`** through `answers_from_harness_yaml`
> — but that difference is worth a handful of characters (`{{ config.locale }}` appears twice
> in the partial), not 119 and 379. The residual is almost certainly the same pre-existing
> drift §2 discloses for `execute`: the ratchet's "before" was frozen at an earlier commit,
> so this entry silently absorbs another task's movement.
>
> **I did not decompose it**, and the suite cannot: `test_atomic_commands_within_budget`
> tolerates +2%/−20%, so an entry wrong by 119 stays green. Disclosing it is the same
> obligation §2 discharges for `execute` — an attribution document that reports the right
> total with the wrong cause is worse than one that reports nothing, because it is believed.
> Decomposing the ratchet's stale baseline belongs with Phase 3b's regeneration at base.

## 2. Per-command attribution

Every changed key gets a row. Two of the three command rows are this task; the third is not.

| Key | Before | After | Δ | Attributed to |
|---|---|---|---|---|
| `surface.claude.plan` | 52 705 | 53 916 | +1 211 | **this task** — brief + round-state at `standard`, net of the −455 duplicate-preamble fix |
| `surface.claude.spec` | 30 465 | 31 663 | +1 198 | **this task** — the same partial at `stage='spec'` |
| `surface.claude.configure` | 10 982 | 12 082 | +1 100 | **this task** — the ADR-003 dimension **and** its §4 dispatch line; claude-only, no codex variant exists |
| `surface.claude.execute` | 40 548 | 40 158 | −390 | **not this task** — pre-existing drift |
| `surface.codex.hm-plan` | 46 044 | 47 255 | +1 211 | **this task** — same partial, codex variant |
| `surface.codex.hm-spec` | 27 734 | 28 932 | +1 198 | **this task** |
| `surface.codex.hm-execute` | 37 660 | 37 270 | −390 | **not this task** — pre-existing drift |
| `render_sha` | `bdf533a0` | `01922911` | — | mechanical — moves on every regeneration |
| `payload_digest` | (old) | (new) | — | mechanical — moves on every regeneration |

**The `execute` rows are not mine and saying so is the point.** The baseline was frozen at
`bdf533a0`; HEAD is `01922911`. `execute.md.j2` changed in between (the Phase A.5 three-lens
fan-out and its follow-ups) and the baseline was never re-frozen, so −390 was already owed
before this task started. It surfaces here only because regenerating the file settles every
outstanding row at once. Attributing it to this PLAN would be the same class of error as
copying a previous task's figures: an attribution document that reports the right total with
the wrong cause is worse than one that reports nothing, because it is believed.

`render_sha` and `payload_digest` are `_MECHANICAL_KEYS`. Both move on **every** regeneration
by construction — `head_sha()` and `payload_digest()` are recomputed — so a document written
to a spec that omits them fails `test_every_changed_key_has_an_attribution_row`. This PLAN's
first draft named five mandated strings; there are seven.

## 3. Round-trips: unchanged, deliberately

| Variant | plan | spec | execute |
|---|---|---|---|
| `claude` | 14 → 14 | 6 → 6 | 17 → 17 |
| `codex` | 13 → 13 | 5 → 5 | 16 → 16 |

`test_round_trip_counts_match_the_live_render` and `tests/structural/test_roundtrip_budget.py`
are **exact**, not ratchets: one `^!` line or one `Task(` token added by the partial trips
both. The partial contains neither, and
`test_comprehension_render_gate.py::test_the_partial_adds_no_round_trip` asserts it directly
so the failure names its cause instead of surfacing as an opaque budget mismatch.

## 4. Compaction before residue

The bar the neighbouring `_ATOMIC_RATCHET` entries set is compaction first, then the residue.

| | Raw | After one pass | Cut |
|---|---|---|---|
| `plan` (atomic ratchet) | +1 923 | +1 547 | −20% |
| `spec` (atomic ratchet) | +1 778 | +1 577 | −11% |

The residue is the feature. The brief is what the user asked for; the round-state delta
contract is what stops it becoming a re-dump every round. ADR-008's replacement of
`#### Step A — Render current plan state (visualization OPTIONAL)` and ADR-007's subsumption
of `## SPEC Interview Round {N}` are **swaps**, not additions, so they cost nothing here —
both are recorded in `test_instruction_preservation._ALLOWED_REMOVALS` under this task's key,
against all four entry arms, because a cut that hit only one arm would be the bug that
keying exists to expose.

## 5. Ordering

The figures above were written **after** the final template edit and measured with
`python tests/structural/_surface_baseline.py --print`, which renders without writing. The
freeze itself cannot happen on this branch: `assert_sha_is_durable` refuses a SHA that
`task-land` will squash away, so `surface_baseline.json` is regenerated at base after the
land (PLAN Phase 3b). Any further template edit invalidates §1 and §2 and they must be
re-measured — that is the failure mode the previous delta document was corrected for four
times, and it is an ordering problem, not a care problem.
