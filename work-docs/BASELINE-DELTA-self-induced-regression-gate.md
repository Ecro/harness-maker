# Baseline delta — self-induced-regression-gate

Attribution for the `surface_allowance` block in
`work-docs/PLAN-self-induced-regression-gate.md`.

## Measured starting point

Rendered sizes under the budget test's own harness (`_render(feature_branch_workflow=True)`),
measured 2026-08-17:

| command | size | ceiling (ratchet × 1.02) | headroom |
|---|---:|---:|---:|
| execute | 43193 | 44064 | 871 |
| review | 61531 | 61761 | **230** |
| plan | 53785 | 54635 | 850 |
| wrapup | 42808 | 43301 | 493 |
| spec | 32303 | 32756 | 453 |
| verify | 25124 | 25433 | 309 |
| research | 27241 | 27792 | 551 |

`review` is the binding constraint: 230 characters, and this PLAN adds mandated CLI calls to
exactly that command.

## What the characters buy

### `review` — run identity (ADR-003)

> **Item 3 below was withdrawn in review and ships nothing.** It is kept in this list because
> the characters were declared for it in advance, and a declaration edited to match the outcome
> stops being a prior declaration. See §Withdrawn during review.

Three additions were declared, each a mandated call plus the branch prose that tells the stage
what to do with a non-zero exit:

1. `hm review_run open` at the top of Round 1, whose refusal-to-open is the whole defence
   against a new run resetting `iteration_count`, `review_base` and the confirmation-pass
   budget. Without the prose that says *what a refusal means and that resuming is the correct
   response*, the call reads as noise and gets skipped — the failure mode this PLAN exists to
   close.
2. `hm review_run close` on every terminal branch of the Grade Gate and Confirmation Pass C3.
3. ~~`hm observability.verification_cache check` before the auto-fix loop's test command.~~
   **Withdrawn** — it could never hit.

Both variants are rendered (`!` lines for Claude, `Bash(...)` for Codex), so each call site
costs roughly twice its single-variant length.

### `execute` — root-cause hypothesis (ADR-002)

1. A three-line declaration before Phase C: the root-cause hypothesis, the repair's scope, and
   its non-goals. The shape moved twice — the source proposal's four items became one item plus
   three *references*, then the references were cut because two of them had no absent case, and
   round 6 restored scope and non-goals as *declarations*, which have none (ADR-002). Three
   declared lines rather than one is the largest single item in `execute`'s share.
2. ~~`hm observability.verification_cache check` in Phase D, both variants.~~ **Withdrawn.** The
   producer half was already removed (`is_fresh` does not compare check sets, so a targeted-run
   marker would let `verify` and `wrapup` skip the full suite); review then found the remaining
   consumer could never hit, and it went too.
3. A rewrite of the Phase D full-mode paragraph (`execute.md.j2:397-399`), which currently names
   `pyproject.toml` / `uv.lock` / CI workflows / `harness.yaml` as full-mode triggers. After
   Phase 1 none of them is. This is close to net-neutral in characters — it replaces a list
   rather than adding one.

## Why not offsetting deletions

The four previous size-budget episodes in this repo cut rationale sentences that pinned test
order or recorded a refuted claim, and two of those cuts were re-added by a later round. The
`review` stage in particular has 230 characters of slack precisely because it has already been
cut four times across two rounds. Cutting a fifth time to fund a mandated call trades a
load-bearing sentence for a call whose meaning that sentence would have carried.

## Reconciliation — done, and what it cost

`round_trips` was deliberately absent from the initial declaration: it is compared **exactly**,
so it could only be filled in once the call sites existed. **Phase 3 did the writing and the
measuring in one phase** — that is why it was atomic (ADR-009). A `.j2` change selects
`tests/render` + `tests/snapshot` + `tests/structural`, and `/hm:execute` Phase D runs that
selection with "All must pass", so a phase that edits the templates and leaves the parity map
for a later phase has an exit criterion it cannot satisfy.

The ceilings are now tightened from the opening estimate to the measured delta. **`round_trips`
stays absent, and that is the correct end state, not an omission** — `round_trip_headroom` sums
the declared value *into* the frozen baseline rather than replacing it, so a task that
re-baselines in its own commit (as this one does, attributed below) has already folded the
movement in. Declaring the measured `execute: 17` made the gate demand 34. The exact counts live
in the baseline and in the table below.

**The opening per-command estimate for `execute` was too small** — 2000 declared against
2008 actual, and 2000 against 2092 for `hm-execute`. It was never load-bearing, because the
aggregate ceiling then in force (6000) absorbed it, but a per-command figure that the change exceeds is a
figure that would have failed had it been the binding one. Recorded rather than quietly rounded.

## Surface baseline movement (regenerated 2026-08-18, after the review round)

`tests/structural/surface_baseline.json` was regenerated in this task's own commit, as
`test_surface_baseline.py`'s failure message instructs. Measured against the **pre-task**
committed baseline, not against the intermediate one:

| variant | aggregate before | after | delta |
|---|---:|---:|---:|
| claude | 418905 | 423214 | **+4309** |
| codex | 351729 | 356125 | **+4396** |

| command | chars | round_trips |
|---|---:|---:|
| `execute` | 44405 → 46413 (+2008) | 19 → **17** |
| `review` | 82389 → 84690 (+2301) | 36 → **37** |
| `hm-execute` | 43188 → 45280 (+2092) | 18 → **16** |
| `hm-review` | 77698 → 80002 (+2304) | 32 → **33** |

**The direction is larger.** This PLAN reduces *self-induced churn*, not shipped surface, and
it grew the surface in four places while doing so — a reader who scans the table without this
sentence would take a cost-reduction PLAN for a size-neutral one. The growth is funded by the
`surface_allowance` block in `PLAN-self-induced-regression-gate.md` and is now folded into the
baseline rather than sitting on top of it.

### Per-command rows

- `execute` — `chars` up: the Phase C.0 declaration and the `targeted-test-selection` pointer.
  `round_trips` **down** 19 → 17: ADR-010 collapses three `test-reviewer` dispatches into one.
  It was briefly 18 — ADR-008 had added a `verification_cache check` (+1) — and review withdrew
  that read, so the −2 stands alone.
- `review` — `chars` up: Step 0's run-open block, the id-source sentence and five `close`
  instructions. `round_trips` up 36 → 37, the single mandated `hm review_run open` call; `close`
  is inline prose on each branch rather than a mandated call line, so it is not charged.
- `hm-execute` / `hm-review` — the Codex arms of the same edits, in `spawn_agent` / `Bash(` form.

### Withdrawn during review

The **verification-cache reads** in both stages (ADR-008) are gone. `is_fresh` never compares
check sets, so the producer half had already been cut — and a consumer with no producer cannot
hit here, because both stages change files before reaching the read. `check` returned 1 on
essentially every call. `verify`, `wrapup` and the `verify-before-completion` skill keep the
cache; they hold both halves. This is the only item from the opening declaration that shipped
nothing, and it is why `execute`'s round-trip count landed at 17 rather than 18.

`payload_digest` and `render_sha` move mechanically with any surface change.

### Why this task may touch the ratchet at all

The ownership rule is **ADR-010** of PLAN-workflow-step-audit and the failure it names is
`ratchet-rebaselined-by-its-own-subject`: a phase that both grows the surface and re-freezes the
number that bounds it has removed its own gate. This task is allowed to re-baseline because the
movement is *declared in advance* — the `surface_allowance` block names the characters and the
commands before the edits, and `test_roundtrip_budget.py`'s own message directs a deliberate
change to re-baseline in the same commit and name the calls. The unattributed case is the one
the rule forbids, and this section is the attribution.
