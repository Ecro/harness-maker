# AUDIT — lens axis pilot (PLAN-review-loop-empirics Phase 0)

Satisfies **AC-018**. Measures what the nine-lens discovery axis actually yields on this
repository's own diffs, and records today's dispatch baseline so the cost delta in
[[PLAN-review-loop-empirics]] is a number rather than an argument (T-08).

**This audit informs; it does not gate.** The axis itself is a user decision (interview #20).
What it decides is which lenses are *prune candidates* and what R11's surface budget has to buy.

## §0 — Method, and how it departs from the shipped configuration

Three real commits from this repository, chosen for a size and nature spread:

| diff | nature | non-test Python | files |
|---|---|---|---|
| `b83551df` | bug fix — three fail-opens in the autonomy judgment gate | 154 lines | 4 |
| `01922911` | contract fix — unknown top-level key in `.codex/hooks.json` | 46 lines | 1 |
| `8137bd8e` | feature — declare project toolchains, stop fabricating oracle evidence | 639 lines | 6 |

Eleven lenses per diff, 33 dispatches total: the six-category core (`design`, `functionality`,
`complexity`, `robustness`, `naming`, `consistency`), the three domain lenses (`security`,
`concurrency`, `tests`), and the two legacy-only lenses (`correctness`, `failure`). The 9-lens arm
is the union of the first nine; the 5-lens arm is `correctness`, `failure`, `concurrency`,
`security`, `tests` — the set shipped today. The three shared lenses are dispatched once and counted
in both arms.

**Departures from the shipped configuration, stated because the yield does not transfer cleanly
without them:**

1. **The nine-lens configuration does not exist yet** — Phase 2 builds it. The pilot hand-dispatches
   nine briefs. A rendered brief carries more surrounding contract than a hand-written one, so these
   numbers are a floor, not a forecast.
2. **The diff shown to each lens is the commit's non-test Python only.** Template, snapshot and test
   hunks were excluded to keep briefs bounded; lenses could Grep the repo for the rest, and the
   `tests` lens was told to.
3. **The `tests` lens ran on `code-reviewer`, not `test-reviewer`.** `test-reviewer`'s output
   contract is Phase A.5-specific and would not have produced comparable rows.
4. **Output was capped at six findings per lens.** `complexity` on `8137bd8e` returned exactly six
   and may have been truncated; no other lens hit the cap.
5. **Single run per lens per diff.** The source experiment measured a median Jaccard of 0.36 between
   two runs of the same reviewer, so per-lens counts carry that sampling variance. **Directions are
   readable; individual counts are not.** `correctness` returning NONE on two diffs and three majors
   on the third is the visible face of that variance.
6. **The clustering is single-pass and LLM-judged (mine).** The source experiment validated its
   clusterer three ways — reordered runs at ARI 1.000, a cross-vendor model reproducing the same
   partition, and a chance-level calculation. **None of that was done here.** Duplicate/exclusive
   attribution below is therefore the softest number in this document, and the arm comparison in §2,
   which needs no clustering, is the firmest.

## §1 — Per-lens exclusive yield

"Exclusive" = finding-groups no *other lens in the same run* produced. `vs legacy` = groups none of
the five lenses shipped today produced — the number that answers "what does the axis change buy".

| lens | raw findings | exclusive (of 11) | exclusive vs the shipped 5 | majors among them |
|---|---|---|---|---|
| `complexity` | 14 | 12 | **12** | 5 |
| `design` | 11 | 8 | **11** | 3 |
| `consistency` | 11 | 8 | **11** | 3 |
| `tests` | 8 | 8 | — (already shipped) | 3 |
| `security` | 7 | 7 | — (already shipped) | 3 |
| `naming` | 7 | 6 | **6** | 2 |
| `failure` | 7 | 5 | — (already shipped) | 4 |
| `robustness` | 8 | 4 | **5** | 3 |
| `functionality` | 6 | 3 | **5** | 3 |
| `concurrency` | 2 | 1 | — (already shipped) | 1 |
| `correctness` | 3 | 0 | — (already shipped) | 0 |

**Total exclusive-vs-shipped: ~52 finding-groups, ~16 of them major, across three real diffs.**

The six new lenses each earned their slot; none returned nothing across all three diffs. The largest
contributors are `complexity`, `design` and `consistency` — precisely the "a general reviewer
truncates these under a top-15-by-severity instruction" categories the source experiment predicted,
reproduced here on a different codebase and a different lens vocabulary.

## §2 — Arm comparison

No clustering needed, so this is the firm number.

| diff | 9-lens raw | 5-lens raw | 9-lens dispatches | 5-lens dispatches |
|---|---|---|---|---|
| `b83551df` | 31 | 11 | 9 | 5 |
| `01922911` | 12 | 2 | 9 | 5 |
| `8137bd8e` | 31 | 14 | 9 | 5 |
| **total** | **74** | **27** | **27** | **15** |

**+174 % raw findings for +80 % dispatches** — 2.74 findings per dispatch versus 1.80.

The `01922911` row is the sharpest: on a 46-line contract fix the shipped five produced **two**
findings (both from `tests`; `correctness`, `failure`, `security` and `concurrency` all returned
NONE) while the six-category core produced **ten**. A small, low-risk-looking diff is exactly where
today's axis goes quiet — and `design`, `complexity` and `consistency` each found something real in
it, including a docstring that promises pruning "from BOTH sides" against code that prunes one.

**This contradicts one thing the source experiment reported.** There, category fan-out produced
*21 % fewer* raw remarks than repeated identical calls. Here raw remarks went *up* 174 %. The
comparisons are not the same: theirs was 6 category calls vs 6 identical calls at equal budget; ours
is 9 category calls vs 5 different calls at unequal budget. The "fewer raw remarks" claim was never
tested here and this audit does not support it.

## §3 — Today's dispatch baseline

| stage | dispatches today | under the nine-lens axis |
|---|---|---|
| round 1 | 5 | 9 |
| each repair round | 1–2 (scope-selected, `review.md.j2:661`) | 1 above the churn threshold, **0** below |
| confirmation pass | 5 | 9 |
| **floor for an approved review** (round 1 + one repair + confirm-1) | **11–12** | **19** |

The floor rises by **7–8 dispatches per approved review**, about +65 %. T-08's retraction stands and
is now quantified: the repair-round saving is at most 1–2 dispatches and cannot offset +8 at round 1
plus +8 at the confirmation pass. **The change is a cost increase defended on coverage.**

## §4 — Prune candidates

- **`correctness` — retire it, and note the correction.** Zero exclusive groups across all three
  diffs. Its one real contribution (the `toolchains: []`-means-off contract violation on
  `8137bd8e`) was also found by `functionality`, which additionally found three groups
  `correctness` missed. So the data says: `functionality` subsumes it, and the axis change is right
  to drop it.

  > **Correction (2026-08-16).** This bullet originally read "*this turns the axis change from
  > 5 → 9 lenses into 5 → 8, recovering one of the eight added dispatches*". **That is wrong and
  > the claim was reported to the operator before it was caught.** `correctness` is not in the
  > nine — the target set is design · functionality · complexity · robustness · naming ·
  > consistency · security · concurrency · tests. It is one of the *current* five, which the axis
  > change retires along with `failure` (subsumed by `robustness`). Pruning it therefore recovers
  > **nothing**: nine stays nine, and §3's dispatch figures are unaffected. What the finding
  > actually licenses is narrower and still worth having — it is positive evidence that the
  > substitution is sound, and it makes explicit a decision an implementer could otherwise have
  > taken the other way by carrying all eleven lenses forward.

  The only candidate that would actually reduce the nine is `concurrency` (one exclusive group),
  and the bullet below argues against it.
- **`concurrency` — keep, with the caveat recorded.** One exclusive group in three diffs and NONE on
  two. That is weak on its face, but the one group it found is a genuine multi-session defect (a
  gated-level early return skipping `touch()`, so a peer's takeover picker reads a live session as
  idle) that four other lenses looked at the same line and missed. CLAUDE.md documents a
  three-times-recurring cross-session contamination class; a lens is not redundant because the
  sample happened to be light on threads. Re-measure on a diff that touches the worktree/session
  layer before pruning.
- **No other prune candidate.** Every remaining lens produced ≥4 exclusive groups.

## §5 — What this does and does not license

**Supports:** adopting the six-category core. Each of the six earned exclusive yield on real diffs
from this repository, and the two categories our axis had no equivalent for at all — `complexity`
and `consistency` — are the two largest contributors.

**Supports:** keeping `security` and `tests` as mandatory domain lenses. `security` found a
plausible RCE class on `8137bd8e` (`_ALLOWED_RUNNERS` gates only `argv[0]`, so a `toolchains`
template can pass `python -c`), and `tests` was the *only* lens to find anything at all on
`01922911` from the shipped set. Neither exists in the six-category axis.

**Supports, unexpectedly, ADR-007.** On `b83551df`, four lenses reported `autopilot_caps.py:266` and
each named a **different** defect: an unvalidated `--current` reaching the ledger (design), a
permanently unconfirmed `advance_authorized` (functionality), a stale `last_seen` misleading a
peer's takeover picker (concurrency), and unbounded `gate_blocked` rows (robustness). Under today's
Step 4 — surface match plus reasoning alignment — same file, same line, divergent reasoning is
demoted to `manual-only`, which neither grades nor gets fixed. **The pilot produced a live instance
of T-01 rather than a hypothetical one**, and it argues the per-lens-sovereignty decision is load
bearing rather than merely convenient.

**Does NOT support:** any claim about finding *quality*. Truth was not adjudicated. "Exclusive
group" counts distinct claims, not correct ones, and `major` is self-assigned by the reporting lens.
Several findings are plainly stylistic (an f-string idiom, a duplicated comment) and would be P2/P3.

**Does NOT support:** the source experiment's "fewer raw remarks" result — see §2.

**Does NOT support:** a forecast. Single run per cell, unvalidated clustering, three diffs from one
repository, one model family. The direction is consistent across all three diffs; the magnitudes
are not load-bearing.
