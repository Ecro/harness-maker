# Baseline delta — ai-work-boundaries

Attribution for the `surface_allowance` block in `work-docs/PLAN-ai-work-boundaries.md`.

## Measured starting point

Read from `tests/structural/surface_baseline.json` (`render_sha` 573c9732), 2026-08-19.
Ceiling is the frozen ratchet × 1.02.

| command | size | ceiling | headroom |
|---|---:|---:|---:|
| plan (claude) | 59096 | 60278 | 1182 |
| execute (claude) | 46413 | 47341 | 928 |

Both commands this PLAN touches have headroom under the plain ratchet. The allowance is
declared anyway: the ratchet is an aggregate gate as well as a per-command one, and a change
that lands inside per-command headroom but is unattributed is exactly the unexplained growth
this mechanism exists to remove.

`review` is NOT touched — its consumption was removed from scope during validation (ADR-004),
and `review` is the binding constraint in the current baseline.

## What the characters buy

### `plan` — the required section (ADR-001, ADR-002, ADR-008)

The new required section `## 🚧 Contract Boundaries` in the required-sections list, its
`### Do not change` list, the explicit-`none` rule, the entry grammar, and one Step 6
verification bullet.

Declared: **1400** → measured **1758** (see Measured outcome)

### `execute` — citation and stage-exit comparison (ADR-003, ADR-009)

Step 1 gains a clause loading the PLAN's Do-not-change list on every implementation path
(not only the defect-repair path); Step 4's drift check gains it as a second comparison
target; the absent-section case is stated once.

Declared: **1000** → measured **2549** (see Measured outcome)

## Round trips

**Zero new round trips.** This PLAN adds no `!` line and no `Bash(` call site to either
command — the boundary list is read from the PLAN document already loaded, and the stage-exit
comparison is prose the model performs. `round_trips` is therefore omitted from the allowance
block, which is the correct encoding of "unchanged" (round trips are compared exactly).

## Two ratchets, not one — record both

`surface_allowance.commands` is consumed by `_ATOMIC_RATCHET` in
`tests/structural/test_command_size_budget.py`; `surface_allowance.chars` bounds
`tests/structural/surface_baseline.json`. **They count different things** — `len(flag_on[name])`
vs rendered command chars — so a close-out that folds one leaves the other passing on declared
headroom alone, and it goes red only when the allowance expires. That is exactly what
`BASELINE-DELTA-self-induced-regression-gate.md` records for `43234d0e`, discovered on
2026-08-19 while closing that PLAN out (commit `45e3622c`).

The Measured outcome section below therefore has a row for **each** ratchet per command. A
close-out cannot fold a number this document never named.

## Measured outcome

Measured 2026-08-19 after Phases 1-2 landed, by running the generators rather than by hand:
`uv run python tests/structural/_surface_baseline.py --print` for the first ratchet and the
`_render(feature_branch_workflow=True)` fixture the atomic gate itself uses for the second.

> **Run the generator from the WORKTREE's own package.** `uv run --with $HOME/harness-maker …`
> installs harness-maker from the **base** repo and therefore renders the base templates — it
> reported `+0` against a change that had already landed here. That is a silent wrong answer,
> not an error, and it is the same class as every other "measured the wrong thing" note in
> this repo.

| command | `surface_baseline.json` chars | `_ATOMIC_RATCHET[name]` |
|---|---|---|
| `plan` | 59096 → 60633 (**+1537**) | 53564 → 55322 (**+1758**) |
| `execute` | 46413 → 48962 (**+2549**) | 45169 → 47718 (**+2549**) |

> **Re-measured 2026-08-19 after the round-3 repair round.** The table above previously held the
> post-Phase-2 numbers (+1038 / +1223, aggregate +2261) while the PLAN frontmatter had already
> been raised twice past them. That gap is not cosmetic: ADR-010 makes THIS document the only
> input a close-out may fold from, and Phase 3's exit criterion is an equality assertion against
> it — so a wrapup would have re-frozen both ratchets at the stale figures and left ~1,700
> characters unfolded. That is `43234d0e`'s half-fold, reproduced by the PLAN that discovered it.
> Caught by the `consistency` lens at round 3.

> **Round 4 re-measure: +3860 → +4097.** Six template repairs out of that round's eighteen
> findings. Five are replacement wordings and one — naming globs in the form-(a) exclusion list,
> which ADR-008 required and the shipped grammar had dropped — is net shorter. The growth sits in
> three: C.0 no longer claims to compare a derived diff (nothing derives one, and Phase 2's
> scope-out forbids adding the command, so the honest statement is that the operand is the
> implementer's own enumeration), Step 4 gained the partial-list case Step 1 could always
> produce, and a crossing became an exact match or a `/`-terminated descendant instead of any
> lexical prefix. **103 characters of headroom remain** under the 4,200 ceiling — a further
> repair round cannot be funded by a raise, which is the mechanism working rather than a
> problem.

> **Round 5: +4097 → +4086, and the ceiling did its job.** Reviewing the round-4 repairs found
> eight P1s, all of them in those repairs. The structural fix — Step 4 becomes the only site that
> defines a crossing, with Step 1, ADR-008 and R2 deferring to it — plus seven smaller repairs
> measured **4212**, twelve over the ceiling. Per this PLAN's own Phase 3 rule that is a trim, not
> a raise: ~126 characters came out (the single-owner claim said in half the words, and a sentence
> narrating the document to itself), landing at **4086** with 114 to spare. Both cuts were ones
> the `design` lens had already asked for, which is the argument for measuring before raising.

> **Re-measured again after ADR-011 cut `### Deliberately unspecified`** (operator decision at
> round 3). The recovery is **107 characters**, not the "roughly half the plan-side growth" the
> option was pitched as — the plan-side cost was always the ADR-008 grammar and its Step 6
> enforcement, not the free-slot bullet. The cut is still right, and its return is one fewer
> mandatory authoring obligation and no gate-enforced artifact that nothing reads; it is not a
> size win. Recorded because an estimate stated to the operator and then quietly left uncorrected
> is the same defect class as the stale table above.

Aggregate: claude 423214 → 427300 and codex 356125 → 360211, **+4086** on both, against a
declared 4086 and a 4,200 ceiling. `round_trips` unchanged on all four rendered commands (`plan` 15/14,
`execute` 17/16) — the boundary list is read from the PLAN the stage already loads and the
Step 4 comparison reuses the path set the drift check already has, so no `!` line or `Bash(`
site was added. That was a declared constraint, not a lucky outcome: round trips are compared
exactly and this PLAN declared zero headroom for them.

**The `execute` per-command declaration was short by 223.** Declared 1000, measured 1223. The
gate passed anyway — the ceiling is `int(45169 × 1.02) + headroom`, so 903 characters of
standing 2% slack absorbed it — but it passed on slack rather than on the declaration, and the
declaration is the part that was supposed to be checkable in advance. That is the same
MEASURED-replaces-estimate move `BASELINE-DELTA-self-induced-regression-gate.md` records.

> **The correction it describes is HISTORY, not the current frontmatter.** That round set
> `chars: 2261 / plan: 1259 / execute: 1223`; two repair raises and ADR-011's cut have moved it
> since. **The current values are the ones in the Measured-outcome table above** — and those are
> what a close-out folds. Nothing outside that table states a live figure: ADR-010 makes this
> document the only input a fold may read, so a second live figure here is the half-fold hazard
> in miniature. Caught by the `consistency` lens at round 4.

Aggregate growth is at the declaration and under the 4,200 ceiling (raised from 3,600 by
operator decision on 2026-08-19 — see Phase 3). **Neither ratchet is folded here** — folding is wrapup's act at close-out, and
per ADR-010's finding a close-out can only fold what this document named, which is why both
columns exist above.

## The direction is larger

This PLAN is about **writing boundaries down**, and it grew the shipped surface by 4086
characters to do it. A reader who scans the two tables above without this sentence takes a
discipline PLAN for a size-neutral one. The growth is real, it is funded by the
`surface_allowance` block in `PLAN-ai-work-boundaries.md`, and it buys exactly two things: a
required PLAN section with its grammar, and the three places `/hm:execute` reads it. Both of
those have a consumer; the half that did not was cut (ADR-011).

## Why this task may touch the ratchets at all

The ownership rule is **ADR-010** of PLAN-workflow-step-audit and the failure it names is
`ratchet-rebaselined-by-its-own-subject`: a phase that both grows the surface and re-freezes the
number bounding it has removed its own gate. This task is allowed to declare headroom because
the movement was **declared in advance** — the `surface_allowance` block named the characters
and the commands before the edits, and this document is the attribution. What it must NOT do is
fold: neither `surface_baseline.json` nor `_ATOMIC_RATCHET` is re-frozen here. That is wrapup's
act at close-out, and ADR-010 of *this* PLAN records what happens when a close-out folds only
one of the two.

## Trimming, not raising

An intermediate draft measured **+2441**, 41 over. The response was to cut 180 characters of
prose from the `execute` paragraphs, not to raise the allowance: raising a budget by 41 to avoid
trimming a sentence is the direction CLAUDE.md's first goal tells us not to take.

## Fold at close-out (2026-08-19) — BOTH ratchets, one commit

ADR-010 exists because `43234d0e` folded one of the two and the miss stayed invisible until the
allowance retired. So this close-out names every key it moved, in both artifacts.

**Ratchet 1 — `tests/structural/_ATOMIC_RATCHET`** (`len(flag_on[name])`), hand-edited with an
attribution comment per entry:

| key | before → after | Δ | declared |
|---|---|---:|---:|
| `plan` | 53564 → 55322 | +1758 | 1758 |
| `execute` | 45169 → 47718 | +2549 | 2549 |

**Ratchet 2 — `tests/structural/surface_baseline.json`**, re-frozen by its **own generator**
(`uv run python tests/structural/_surface_baseline.py`), never by hand:

| key | before → after | Δ |
|---|---|---:|
| `aggregate_chars.claude` | 423214 → 427300 | +4086 |
| `aggregate_chars.codex` | 356125 → 360211 | +4086 |
| `surface.claude.plan.chars` | 59096 → 60633 | +1537 |
| `surface.claude.execute.chars` | 46413 → 48962 | +2549 |
| `surface.codex.hm-plan.chars` | 53351 → 54888 | +1537 |
| `surface.codex.hm-execute.chars` | 45280 → 47829 | +2549 |
| `payload_digest` | `f613c8be…` → `c3d0b95e…` | derived |
| `render_sha` | `573c9732` → `45e3622c` | derived |

The Codex rows are the same two commands under their Codex names — `hm-plan` carries the
required-section edit and `hm-execute` the load/cite/compare edits, byte-for-byte the same
deltas as `plan` and `execute` above, because both variants render from the same stage
templates. Naming them here is not redundancy: the attribution gate requires a row to name its
SUBJECT, and a table keyed only by dotted path attributes a metric to nothing.

`payload_digest` and `render_sha` are **generator-owned**, not editorial: they are what makes a
hand-edited baseline detectable. This fold learned that the hard way — the first attempt edited
the JSON by hand, got every number right, and reddened three tests on the digest alone. **The
two ratchets are folded differently**: one is a Python dict whose comments carry the
attribution, the other is a generated artifact that must be re-emitted. ADR-010 says they count
different things; it should also have said they are *written* differently.

Aggregate movement is **+4086 on both variants**, equal to the declared `surface_allowance.chars`
and to the sum of the two per-command declarations. `round_trips` unchanged everywhere.
