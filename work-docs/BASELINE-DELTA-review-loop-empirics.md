# BASELINE-DELTA — review-loop-empirics (Phase 1)

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
