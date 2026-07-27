---
type: review
task_slug: token-economy-step-pruning
scope: PLAN Phase 2 — unattributed decomposition
status: APPROVED
created: 2026-07-27
reviewers_invoked: [code-reviewer, security-reviewer, code-verifier, codex, antigravity]
consensus_method: cross-check
voter_pool: 3            # code-reviewer + security-reviewer + codex (antigravity degraded out)
consensus_threshold_k: 2
rounds_used: 2
max_review_rounds: 3
final_grade: A
human_review_needed: false
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
  - model: antigravity
    status: skipped
    reason: "exit 1: Error: timeout waiting for response"
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: token-economy-step-pruning
  computed_at: 2026-07-27T00:00:00Z
---

# REVIEW — Phase 2 (unattributed decomposition)

Diff under review: `de9f3f58..e12b08ca` on `hm/token-economy-step-pruning`.
3 files, +271/−4: `src/harness_maker/economics.py` (+52),
`tests/unit/test_economics_unattributed_breakdown.py` (new, +193),
`work-docs/PLAN-token-economy-step-pruning.md` (status + ADR-010 receipt).

## ⚠️ Read the grade with this caveat

The letter is computed from **consensus-passed P0/P1 only**, and after Pass 1.5 and
Pass 2 there were none — so the grade was A from the moment the verifier demoted the
two P1s, and it could not have been anything else. It is **not** evidence the change
is good.

The load-bearing number is elsewhere: **round 2 found 7 findings, and every one of
them was a defect introduced by round 1's own fixes.** Phase 1's review found the
same shape (11 of 22). On this surface, "fix applied, gates green" carries no
information about correctness. Round 2 also had exactly **one** voter, so nothing in
it could reach consensus by construction — its findings are recorded `manual-only`
because of who ran, not because they are weak. Two of the three I verified
arithmetically myself before accepting them.

## 🎯 Round summary

| Round | Grade | Findings in | Applied | Deferred | Dropped |
|---|---|---|---|---|---|
| 1 (initial) | A | 8 raised (5 code-reviewer, 0 security-reviewer, 3 codex) | 2 | 1 | 5 |
| 2 (review of round 1's fixes) | A | 7 | 7 | 0 | 0 |

## 🔍 Drift findings

**`result: clean`.** `economics.py` and `tests/unit/test_economics_unattributed_breakdown.py`
are Phase 2's declared scope verbatim. The `work-docs/PLAN-*.md` edits are
stage-mandated artifacts, not drift: `/hm:execute` Step 4 requires the phase-status
update, and **ADR-010** requires the mutation check be recorded. No file outside scope
was modified — in particular `templates/commands/hm/metrics.md.j2` was deliberately
**not** touched (see F1 below).

No SPEC scenario miss: AC-010 is Phase 2's governing criterion and is covered.
AC-005..AC-009 belong to Phases 3-5, which are not started.

## ✅ Consensus findings

### P2 — AC-010's absolute `1e-9` USD tolerance is unsafe at the live window's magnitude
`consensus-passed [2/3]` — **code-reviewer** (Pass 2, `specs/…machine.yaml:442`) +
**codex** (`economics.py:630`).

Surface match was admitted on the *same-defect / same-symbol* clause rather than
file+line: the two voters named the same invariant at its two ends — codex at the
accumulation site, code-reviewer at the assertion site — at the same severity tier.
Reasoning aligned: OBSERVE (the breakdown sum and the `by_stage` total are
differently-ordered float accumulations over the same values) and CONCLUDE (an
absolute bound cannot hold across scales) match.

codex's repro used `10**21` output tokens, which is absurd. I measured the realistic
case myself — 6,242 turns totalling $8,960, split into two buckets — and got a
divergence of **7.3e-12**, comfortably inside 1e-9. So the *empirical* risk is low.
The argument still survives on its bound: worst-case `n·eps·sum ≈ 1.2e-8` exceeds
1e-9, and nothing in production evaluates the predicate — it is realised only by the
4-turn unit fixture.

**Applied.** `< 1e-9` → `<= 1e-9 * abs(total)` in AC-010's `executable_predicate` and
both test assertions. This is **not** a uniform strengthening (round 2 caught me
claiming it was): strictly tighter at fixture scale (1.75e-11) and at a zero total
(only exact 0 passes, where the absolute form allowed 1e-9 of slop), and deliberately
**8,960× looser** at the live window — which is the point, because the absolute bound
there sat below the divergence float64 can actually produce.

## 📝 Manual-only findings

### P2 — note 1 over-claimed relative to the predicate ADR-013 locked
`manual-only` — code-reviewer. Raised P1, demoted P2 by the verifier.

The mechanism was **verified**: `estimate_attribution` anchors only on
`turn.attribution_skill` and never re-anchors on inferred/ledger stages, so an
un-adjudicated `run_classify` run's tail past `AdjacencyBounds.max_turns=20` genuinely
gets `est=None` and lands in `unrecoverable_in_window` — even though one boundary
verdict would attribute the whole run. But the code implements ADR-013 **verbatim**;
the defect was my note claiming `recoverable` means "attributable IN PRINCIPLE", which
asserts by implicature that its complement is not.

**Applied** (note text only — the predicate is untouched; amending ADR-013 to admit
"a verdict would resolve this" would reopen the exact hole the ADR closed, since that
is a property of the classification cache, not of a turn).

The reviewer's numeric half was **wrong** and is recorded as such: it claimed the note
contradicts `classification_cache_misses`, but that field counts **boundaries**, not
turns, so there is no contradiction between the two figures.

### P2 — the new fields are not named in `/hm:metrics` Step 5d
`manual-only` — code-reviewer. Raised P1, demoted P2 by the verifier.

**Not** a dead field: Step 5b dumps the full report JSON into the model's context, so
the fields and their notes do reach the reader. But Step 5d's "Also surface, in one
line each" list is *prescriptive*, not illustrative, and `metrics.md.j2` appeared zero
times in this PLAN — so no phase would ever have wired it.

**Deferred, not applied.** Fixing it inside Phase 2 would force a re-render of
`.claude/commands/hm/metrics.md`, which Phase 4 regenerates — the stale-artifact
hazard Phase 3's own `merge_hazards` reasons about. Written into the PLAN as
**Phase 5** so the absent-case has an owner.

### P2 ×7 — defects introduced by round 1's fixes
All `manual-only` (round 2 had one voter). All applied.

| # | Where | Defect |
|---|---|---|
| 1 | `SPEC:468` | My new note claimed the relative tolerance "strengthens the contract rather than relaxing it" — false; it is 8,960× looser at live scale. The same over-claim shape the note I was fixing had. |
| 2 | `SPEC:484` | `expected_relation` still read `sum(parts) == unattributed_total` — the exact float equality validator-3 M4 rejected. Intra-AC drift my own fix left behind. |
| 3 | `SPEC:464` | "roughly 1e7 ulps of slack" — `ulp(0.0175) = 3.47e-18`, so 1e-9 is **2.9e8** ulps. Off by ~29×; a fabricated-precision number I invented. |
| 4 | `PLAN:1035` | AC-010 checkbox said "not yet reviewed" while the same section said Phase 2 was not started. |
| 5 | `PLAN:301` | ADR-009 is titled "**Four** independent commits" and enumerates 1-4 exhaustively; adding Phase 5 left an executor with no commit slot for it. Frontmatter said "Phases 3-4 NOT started". |
| 6 | `PLAN:961` | Phase 5's own rationale said "`metrics.md.j2` appears **zero** times in this PLAN" — eight lines below a section that names it. Stale tense carried verbatim into the text that falsifies it. |
| 7 | `economics.py:240` | Note 1 now points the reader at sibling field `classification_cache_misses` with nothing tying the string to the field. Gated with `assert "classification_cache_misses" in EconomicsReport.model_fields`. |

Round 2 also **refuted** a concern I had raised myself: with a zero unattributed
total the relative form degenerates to `0 <= 0`, which I thought was a weakening. It
is not — the absolute form allowed up to 1e-9 against a zero total, so the new form
is strictly stricter there.

## 🚫 Dropped findings

| Finding | Dropped by | Why |
|---|---|---|
| `all(v["turns"] > 0)` is fixture-coupled (`test:70`) | Pass 1.5 verifier | Verbatim transcription of AC-010's `executable_predicate`, bound via `test_ids`. Dropping it from the test alone breaks the SPEC↔test binding rather than fixing anything. |
| Rename `UnattributedBucket.usd` → `total_usd` for sibling parity | Pass 1.5 + Pass 2 | The name is pinned by an external contract: AC-010's predicate literally reads `v["usd"]`. Observation valid, suggestion refuted. |
| Post-loop rebuild silently discards a future third key (`economics.py:666`, filed by **both** code-reviewer P2 and codex P3) | Pass 2 | Premise refuted: a third key carrying turns would be dropped and then **fail AC-010's conservation conjunct loudly**, in two existing tests. Unreachable today (binary ternary) and already gated. Note the two filings were at **different severity tiers**, so Step 4a's no-bridging rule made them independent, not consensus. |
| Breakdown admits turns outside the `adjacency`/`none` population (`economics.py:617`, codex P2) | Pass 2 | See disagreement below. |

## 🤝 Disagreements

**`attribution_skill == "(unattributed)"` sentinel collision.** `security-reviewer`
observed this independently and **declined to file it** (pre-existing in `by_stage`,
unchanged by the diff, inherited consistently, conservation holds). `codex` filed it
as P2.

Pass 2 adjudicated **for the reviewer who declined**, and added a fourth reason
neither had: codex's implied remedy — gating on `source in {adjacency, none}` instead
of `resolved_stage == UNATTRIBUTED` — would **actively break AC-010**. In the exact
collision case codex describes, such a turn enters `by_stage[UNATTRIBUTED]` but would
not enter the breakdown, so conservation fails. The finding trades a theoretical
collision (requiring a skill literally named `(unattributed)`) for a real conservation
violation. At most a one-line ADR-013 prose nit: the ADR describes the population as
"source adjacency or none", which is a prose approximation of the `resolved_stage`
gate the code actually implements.

## 🧬 Mutation receipt (ADR-010)

Re-run after **both** rounds of fixes: **7 mutants, 7 killed, 0 survivors.** Four are
held by exactly one test each (`M4` terminal-cap guard, `M5` notes, `M6` empty
population, `M7` off-by-one membership) — deleting that test silently reopens the
defect. Full table in the PLAN under "🧬 ADR-010 mutation receipt — Phase 2 / AC-010".

## Review Iteration Summary

| Iteration | Grade | Fixes applied | Remaining | New |
|---|---|---|---|---|
| 1 (init) | A | — | 3 kept (1 consensus-passed, 2 manual-only) | — |
| 2 | A | 9 (2 from round 1 + 7 round-1-introduced) | 1 deferred to PLAN Phase 5 | 7 |

Final grade: **A**
Iterations used: **2 / 3**
Status: **APPROVED**
human_review_needed: **false** (no `manual-only`/`weak-consensus` finding at P0 or P1)

> The flag is `false` by the rule, but see the caveat at the top: round 2's single
> voter means its 7 findings are `manual-only` by construction, and the grade never
> had a path to being anything other than A.
