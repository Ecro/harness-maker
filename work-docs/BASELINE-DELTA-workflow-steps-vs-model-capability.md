---
type: baseline-delta
task_slug: workflow-steps-vs-model-capability
status: in-flight
created: 2026-09-12
summary: "Attribution for the -8 222 (claude) / -8 222 (codex) shipped-surface shrink from deleting the 5-term ceremony and verify Check 1b; re-freeze deferred to post-land"
---

# BASELINE-DELTA — workflow-steps-vs-model-capability

Attribution for the surface **shrink** this task ships (PLAN ADR-004: 5-term inequality ceremony
deleted from research / spec / plan / loop; ADR-003: verify Check 1b deleted). The aggregate moves
the right way — it is **smaller, not larger** — so this document declares **no `surface_allowance`**;
the ratchet is one-directional and a shrink needs attribution, not headroom.

## What shrank, measured against the base checkout

The frozen `tests/structural/surface_baseline.json` (`render_sha` `85b1216c30a9`,
aggregate `claude` = 435 437, `codex` = 370 292) is already behind the base
checkout (`main` @ `51b5bbfb`): before this task touched anything, base measured
`claude` = 435 839 / `codex` = 370 662 (plan +449, review +958,
wrapup +448/+451, health +35, verify −1 485, execute/research/spec −1). That drift belongs to the
PLANs that landed after the freeze (`BASELINE-DELTA-token-efficiency-autopilot-ux-speed` carries
the allowance for it) and is **not** this task's — so every row below is `base live → now`, not
`frozen → now`.

| Variant | Command | Base (51b5bbfb) | Now | Delta |
|---|---|---|---|---|
| `claude` | `loop` | 52 893 | 50 847 | **-2 046** |
| `claude` | `plan` | 66 159 | 63 813 | **-2 346** |
| `claude` | `research` | 26 174 | 23 608 | **-2 566** |
| `claude` | `review` | 86 177 | 86 171 | **-6** |
| `claude` | `spec` | 32 883 | 30 754 | **-2 129** |
| `claude` | `verify` | 23 059 | 23 930 | **+871** |
| `codex` | `hm-loop` | 51 801 | 49 755 | **-2 046** |
| `codex` | `hm-plan` | 61 313 | 58 967 | **-2 346** |
| `codex` | `hm-research` | 23 781 | 21 215 | **-2 566** |
| `codex` | `hm-review` | 82 439 | 82 433 | **-6** |
| `codex` | `hm-spec` | 30 155 | 28 026 | **-2 129** |
| `codex` | `hm-verify` | 20 421 | 21 292 | **+871** |
| — | **aggregate `claude`** | 435 839 | 427 617 | **-8 222** |
| — | **aggregate `codex`** | 370 662 | 362 440 | **-8 222** |

Measured with `tests/structural/_surface_baseline.measure_surface()` in the task worktree at
0.55.0 templates. `round_trips` is unchanged on every command: nothing deleted was a `!` line.

## Why, exactly

- **research / spec / plan / loop** — `agents/_partials/inequality_gate_block.md.j2` (the 5-term
  formula) plus each stage's "Term meanings" list, per-round ✅/❌ display, "Question generation"
  and "Exit" paragraphs are gone. One sentence survives per stage: the locale open-ended cap,
  still rendered from `harness.yaml.interview.deep_gate`. `comprehension_block.md.j2`'s
  "the 5-term gate still governs which get asked" became "the open-ended cap still governs how
  many get asked" (×8 include sites, plan/spec). Guard: `tests/unit/test_render_inequality_gate_removed.py`.
- **verify** — Check 1 keeps its mechanical drift-verdict read (1a) and loses the LLM PLAN/SPEC
  coverage judgement (1b) plus the two residue lines that pointed at it. Guard:
  `tests/unit/test_render_verify_check1_removed.py`. Numbering 2–6 untouched.
- **review** — one word: "recorded by the inequality gate" → "recorded by the interview".

The removed headings are allowlisted in `tests/structural/test_instruction_preservation.py`
under `workflow-steps-vs-model-capability-phase-3-five-term-ceremony` and
`…-phase-4-verify-check1b`; `instruction_baseline.json` is **not** regenerated here.

## The re-freeze, and why it is deferred (PLAN ADR-006)

`_surface_baseline.assert_sha_is_durable` refuses to freeze at any commit that is not an
ancestor of `main`, and a task branch tip never is once it carries a commit — the squash-land
deletes it. So neither `surface_baseline.json` nor `instruction_baseline.json` is touched inside
this task. **Phase 7 (post-land, base checkout)** re-freezes both at the landed `main` SHA and
appends the closing measured row below. Until then the ratchet compares against the stale frozen
figures plus the earlier document's allowance, which is why every shrink above still reads green.

This is deliberately not `[fail:test] ratchet-rebaselined-by-its-own-subject` (count:2): the
document records the movement and the freeze happens **after** the subject has landed, by the
normal process, not to make a red gate green. Ownership of the frozen figures stays with the
post-land step per ADR-010 (only the closing freeze may touch `aggregate_chars` /
`payload_digest` / `render_sha` / `frozen_at_sha`, and only from base).

`tests/structural/autopilot_gate_golden.json` (the byte-identity golden for the non-gated autonomy
arms) was re-based with a `rebases` row pointing here — per-arm deltas `auto_safe@spec-driven`
-8 222, `auto_safe@task-driven` -8 360, `ask@flag_on` -8 234, `ask@flag_off` -8 234 — because every
moved command is one of the six this task edits and none of the moves touches the advance or
picker blocks.

## Phase 7 attempted post-land, then reverted — the freeze is still blocked (2026-09-12)

Phase 7 ran from the base checkout on `main` at the landed squash `5d2b763e`. Both freezers
succeeded — `assert_sha_is_durable` accepted the SHA, which was the only blocker ADR-006
anticipated — and the result was reverted anyway. The measured figures are recorded here because
they are the evidence for the revert, not because they were kept:

| Baseline | Field | Frozen at `85b1216c` | Would become at `5d2b763e` | Delta |
|---|---|---|---|---|
| `surface_baseline.json` | `aggregate_chars.claude` | 435 437 | 427 617 | −7 820 |
| `surface_baseline.json` | `aggregate_chars.codex` | 370 292 | 362 440 | −7 852 |

**Why it was reverted.** `tests/structural/test_baseline_delta_attribution.py` reported seven
moved keys, and only some of them are this task's: `surface.claude.execute.chars`,
`surface.claude.health.chars`, `surface.claude.wrapup.chars`,
`surface.claude.wrapup.round_trips` and the three `codex` counterparts belong to
**`PLAN-token-efficiency-autopilot-ux-speed`**, which is `status: planning` with 15 unchecked
boxes — genuinely in flight, not stale bookkeeping. It holds a live
`surface_allowance` of 1 865 chars plus `round_trips: {wrapup: 1, hm-wrapup: 1}`, and
`test_round_trip_counts_match_the_live_render` went red on exactly that: frozen 26 plus a
headroom of 1 against a render of 26.

A wholesale re-freeze would have folded that PLAN's **unlanded** growth into the frozen figures
while its allowance stayed live, so the remaining work would have been funded twice — once by the
baseline that now contains it, once by the allowance that still admits it.
`surface_allowance._sole_active` states the rule this violates in its own docstring: fold a
**completed** PLAN's growth into the baseline; borrowing across in-flight PLANs is the failure it
refuses. Re-freezing a subset of keys is not an option either — the freezers regenerate the whole
payload, and a hand-edited subset would carry a `payload_digest` and `render_sha` that describe
nothing.

This is the same family as `ratchet-rebaselined-by-its-own-subject` (count:2), one step removed:
the subject here is not this task but the task next to it. ADR-006 predicted the wrong blocker —
it named `assert_sha_is_durable`, which passed. The real precondition is that **no other PLAN is
in flight holding a surface allowance**, and ADR-006 did not state it.

**Unblock condition.** Phase 7 becomes runnable once
`PLAN-token-efficiency-autopilot-ux-speed` reaches `status: complete` (its wrapup lands and its
allowance expires). At that point re-run both freezers from `/home/noel/harness-maker` on `main`,
append the closing row, and expect the attribution test to demand rows naming `execute`, `health`,
`wrapup`, `hm-execute` and `hm-wrapup` — that PLAN's movement, attributed to that PLAN.

`_ALLOWED_REMOVALS` entries for
`workflow-steps-vs-model-capability-phase-3-five-term-ceremony` and `…-phase-4-verify-check1b`
are kept and remain the mechanism that holds this task's cuts green in the meantime:
`test_the_allowlist_carries_no_stale_entries` computes `_allowed_for(key) & present`, so an entry
is stale only while the string it names is still rendered. These strings are gone.
