# BASELINE-DELTA — review-loop-empirics (Phase 1)

> **SUPERSEDED IN PART, 2026-08-16 — the re-freeze this document attributed has been UNDONE.**
> `surface_baseline.json` is back at its pre-Phase-1 values (`claude` 398 138, `codex` 326 030).
> The same +732 chars are now covered by a **`surface_allowance` block in the PLAN's frontmatter**
> (ADR-010), which the two aggregate guards and the per-command ceiling read and which **expires
> when the PLAN reaches `status: complete`**. This document remains the `delta_doc` the allowance
> points at — the mechanism refuses an allowance whose attribution is missing — so §1–§3 below
> still describe what grew and why. Only §0's "after" column and §3's framing are historical:
> the baseline did not move, and the count:3 occurrence of
> `[fail:design] ratchet-rebaselined-by-its-own-subject` was reverted rather than accepted.
>
> Read §3 anyway. It is the argument that produced the allowance.


Attribution for the `tests/structural/surface_baseline.json` re-freeze made by
[[PLAN-review-loop-empirics]] Phase 1. Written in the same commit that moved the baseline
(ADR-010).

## §0 — What moved

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | **398138** | **398 870** | +732 |
| `aggregate_chars.codex` | **326030** | **326 762** | +732 |
| `surface.claude.review.chars` | 67 876 | 68 608 | +732 |
| `surface.codex.hm-review.chars` | 61 758 | 62 490 | +732 |
| `payload_digest` | `d0c52f53…` | `18d7f4b8…` | recomputed |
| `render_sha` | `64c7dbea` | `edb87a59` | recomputed |

The two commands that moved are the Claude `review` command and its Codex counterpart
`hm-review` — one subject, rendered twice.

Both variants moved by the same +732 because the change is a single edit to
`templates/stages/review.md.j2`, which both the Claude command render and the Codex skill
render read. No other command's `chars` moved; the two mechanical keys (`payload_digest`,
`render_sha`) are regenerator output, not authored values.

## §1 — Direction: the aggregate got **larger**, and this is the wrong way

The surface ratchet exists because a prior line of work
(PLAN-workflow-loop-efficiency → PLAN-workflow-time-token-savings) grew the shipped surface
and had to justify it. This delta grows it again. Nothing here reduces surface; the
justification is entirely about what the added prose prevents.

## §2 — Owning phase and why only it may touch these

**Owner: PLAN-review-loop-empirics, Phase 1.** Its scope is exactly the two clauses below,
and no other phase of that PLAN has landed. A later phase that moves the baseline again must
write its own row here rather than reusing this one — the attribution is per-change, not
per-PLAN, which is what makes `test_every_changed_key_has_an_attribution_row` able to fail.

The +732 chars are two instructions in `review.md.j2`:

1. **The shared-brief scoping line** — "the public contract is fixed and out of scope". Without
   it a reviewer proposes API changes, which is not a reviewer defect: it is the question the
   brief asked. Measured behaviour in the source experiment
   ([[RESEARCH-review-loop-empirics]]).
2. **The test-edit ban with its carve-out** (ADR-006) — the fixer may run tests and may not edit
   one to make a finding go away, *except* when the finding's own target is the test. The
   carve-out is the load-bearing half: `tests` is a mandatory lens, so an unqualified ban leaves
   its findings permanently `pending` → one non-progressing round → a terminal `no-progress`.
   That is an unapprovable review on a finding class the stage itself mandates, and it is why
   this could not be shipped as a shorter, unqualified sentence.

Both were compressed before landing: the first draft cost 1 123 chars and was cut to 732 while
keeping every clause. The remainder is not compressible without dropping the carve-out.

## §3 — The failure class this re-freeze knowingly re-enters

`[fail:test] ratchet-rebaselined-by-its-own-subject` — **count:2** in this repo's failures log,
and `tests/structural/test_plan_net_surface.py` names it in its own docstring while forbidding
exactly this move for the PLAN it measures.

This is the third occurrence, and it is **deliberate rather than accidental**: the user was
shown the conflict (the prior PLAN's ADR-011 forbids re-freezing once a phase has cut) and chose
to supersede it. Recording it as a knowing supersede rather than an oversight is the only thing
that distinguishes this from the two prior instances — and it is worth stating plainly that the
distinction is procedural, not technical. A future reader comparing surface numbers across
PLANs cannot use `surface_baseline.json` as a stable origin; this row is where the discontinuity
is.

**What it costs.** PLAN-review-loop-empirics risk **R11** records the consequence: Phases 2–7
add nine lens briefs, consensus scoping, disposition rules, the churn gate and oscillation
prose — far more than 732 chars. If each pays for itself by re-freezing, the ratchet stops being
a ratchet. The alternative named in R11 — moving stage prose into a loaded skill — lowers the
measured number without lowering what the model reads, so it is metric-gaming and is **not** the
escape. The decision R11 asks for before Phase 2 is therefore real and still open: either accept
a documented surface increase for the whole PLAN with a single justified ceiling, or cut
existing prose to fund it.

`test_the_plan_did_not_grow_the_shipped_surface` is unaffected: it is already `xfail`
(`strict=False`) under its own waiver for the PLAN it measures.

---

## §5 — Phases 2–4 (2026-08-16): +9 074 chars, +17 / +13 round trips

The allowance this document attributes now covers Phases 2, 3 and 4 as well. The baseline is
still frozen; the numbers below are what the PLAN's `surface_allowance` block admits while its
`status` is `planning`, and what the fold-in will freeze when it is not.

| key | frozen | rendered | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 398 138 | 407 212 | **+9 074** |
| `aggregate_chars.codex` | 326 030 | 335 104 | **+9 074** |
| `surface.claude.review.round_trips` | 22 | 39 | **+17** |
| `surface.codex.hm-review.round_trips` | 16 | 29 | **+13** |

Same shape as §0: one edit to `templates/stages/review.md.j2` (plus a note in the
`second-opinion-gate` skill and the two `harness-yaml` routing comments), rendered twice. No
other command moved.

### What the characters bought

1. **Nine lens dispatches instead of five, at both sites.** The axis change is the PLAN's
   subject; the dispatch list is where it becomes real. Six of the nine share `code-reviewer`
   and are distinguished **only** by the lens line in their brief, so the lines are not
   decoration — remove them and six dispatches become six identical ones.
2. **Step C2 renders its own dispatch list.** It previously said "dispatch the mandatory set in
   ONE message, exactly as round 1 does". That back-reference was adequate under an axis where
   every lens had a self-describing agent; it is not adequate now, because the briefs that tell
   the six apart appear nowhere in the confirmation pass. This is the single largest line item
   and the one most likely to be proposed for a cut. Cutting it makes the confirmation pass
   unexecutable as written, which is worse than not having it.
3. **Step 4 calls a CLI instead of describing arithmetic** (ADR-008), and **Step 4e is new**
   (ADR-002). Both are net additions rather than replacements: the prose that described the
   consensus rule was ~40 lines and stays, because a reader has to be able to see a mismatch
   between what the CLI returns and what the stage claims it applies.

### Why `round_trips` needed its own declaration

`round_trips` is compared **exactly** — a mandated call is added or removed on purpose, never
"improved" — so it has no ratchet and no allowance was needed for it before. The only way to go
green was `python tests/structural/_surface_baseline.py`, which rewrites the frozen `chars` in
the same file. A **description** update would therefore have destroyed the **ratchet** sitting
next to it, silently, as a side effect. `surface_allowance.round_trips` closes that: the added
calls are declared, per variant, in the same block that funds the characters.

The counts differ by variant (+17 vs +13) because the counting rule does: `^!` lines for claude,
`Bash(` call sites for codex, and the template branches on `is_codex`. They are separate keys for
that reason — folding them onto one would let a real drift in one variant hide behind the other's
number.
