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

## Phase 7 — the post-land re-freeze, executed (2026-09-13)

Attempted on 2026-09-12 and **reverted**; executed here. The measured figures are identical both
times, because no template changed in between — only the precondition did.

**What blocked it, and what unblocked it.** ADR-006 named `assert_sha_is_durable` as the blocker.
That was right but incomplete: the SHA check passed on the first attempt too. The real
precondition is that **no peer PLAN is in flight holding a `surface_allowance`** — regenerating
the surface baseline is wholesale, so it folds every in-flight PLAN's unlanded growth into the
frozen figures while that PLAN's allowance stays live, funding the remainder twice.
`surface_allowance._sole_active` refuses the summed form of exactly that hazard; arriving through
the freeze instead does not make it a different hazard. On 2026-09-12 the peer was
`token-efficiency-autopilot-ux-speed` (`status: planning`, 15 unchecked boxes, 1 865 chars +
`round_trips: {wrapup: 1, hm-wrapup: 1}`). It landed on 2026-09-13, its allowance expired
(`load_active_allowances` → none), and the freeze became legitimate.

| Baseline | Field | Before (`85b1216c`) | After (`2ff7f035`) | Delta |
|---|---|---|---|---|
| `surface_baseline.json` | `aggregate_chars.claude` | 435 437 | 427 617 | **−7 820** |
| `surface_baseline.json` | `aggregate_chars.codex` | 370 292 | 362 440 | **−7 852** |
| `surface_baseline.json` | `payload_digest` | `14994829…` | `160b87ec…` | re-based |
| `surface_baseline.json` | `render_sha` | `85b1216c…` | `2ff7f035…` | re-based |
| `instruction_baseline.json` | `payload_digest` | `d1aebab0…` | `a3a55e97…` | re-based |

**Read the two aggregate figures against the right denominator.** The −8 222 quoted earlier in
this document is a *per-arm* delta from `autopilot_gate_golden.json` — one autonomy arm's rendered
command set. The −7 820 / −7 852 here are the *whole-surface* aggregates across all 15 claude
commands and 10 codex skills at the default config. They measure different things and are expected
to differ; neither corrects the other. **The direction is down on every arm** — this was a
surface-reduction unit and the aggregate moved the right way, not the wrong way and not larger.

### Per-key attribution (ADR-010)

Twenty-three keys moved. They split into two owners, and the split is the point — a wholesale
re-freeze is the one operation that can silently adopt another task's numbers, so each is named:

**This task (`workflow-steps-vs-model-capability`)** — the 5-term inequality ceremony removed from
`research` / `spec` / `plan` (and the `loop` body that embeds them), and verify's Check 1b LLM
judgement removed:
`surface.claude.research.chars`, `surface.claude.spec.chars`, `surface.claude.plan.chars`,
`surface.claude.loop.chars`, `surface.claude.verify.chars`, `surface.claude.review.chars` (one
word: "recorded by the inequality gate" → "recorded by the interview"), and their six
`surface.codex.hm-*` counterparts.

**`token-efficiency-autopilot-ux-speed`**, landed at `2ff7f035`'s parent and never re-frozen by
its own wrapup — three commands and their codex twins:

- `execute` (`surface.claude.execute.chars`) and `hm-execute` — the Phase 0.5 delegation block.
- `health` (`surface.claude.health.chars`) — the per-model second-opinion smoke.
- `wrapup` (`surface.claude.wrapup.chars` **and** `surface.claude.wrapup.round_trips`) and
  `hm-wrapup` — Phase 1's added `autopilot_ledger rollup` call, the one its
  `surface_allowance.round_trips` funded and the only `round_trips` movement in this freeze.

**Mechanical**: `aggregate_chars.claude`, `aggregate_chars.codex`, `payload_digest`, `render_sha` —
these move whenever anything else does.

This is deliberately not `[fail:test] ratchet-rebaselined-by-its-own-subject` (count:2): the
document records the movement, the freeze happens **after** both subjects have landed, by the
normal process, and no gate was red at the time. Ownership of the frozen figures stays with the
post-land step per ADR-010.

`_ALLOWED_REMOVALS` entries for
`workflow-steps-vs-model-capability-phase-3-five-term-ceremony` and `…-phase-4-verify-check1b`
are **kept**, not pruned. `test_the_allowlist_carries_no_stale_entries` computes
`_allowed_for(key) & present` — an entry is stale only while the string it names is still being
rendered. These strings are gone, so the entries are inert history, and the file's own policy
("each cutting phase adds its entries in its own commit") makes that record the point.
