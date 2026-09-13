---
type: review
task_slug: reviewer-lens-fanout-merge
status: CHANGES_REQUESTED
created: 2026-09-13
run_id: 78e4ea74f2d6
reviewers_invoked: [code-reviewer (design), code-reviewer (functionality), code-reviewer (robustness), code-reviewer (consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
grade: A
lenses_exercised: [design, functionality, robustness, consistency, security, concurrency, tests]
blocks_approval: false
confirm_pass_ran: true
confirm_pass_new_severe_n: 3
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/unit/test_render_dispatch_macro.py
    - tests/structural/test_no_claude_tool_calls_in_codex_output.py
    - tests/structural/test_instruction_preservation.py
    - tests/structural/autopilot_gate_golden.json
    - tests/structural/test_autopilot_gate_render.py
  scenario_misses:
    - "PLAN Phase 3 scope names tests/structural/test_review_dispatch_has_no_literals.py; that file was never created"
  task_slug: reviewer-lens-fanout-merge
  computed_at: 2026-09-13T03:20:00Z
---

# REVIEW — reviewer-lens-fanout-merge

## 🎯 Round 1 Summary

**Grade B** — `review_consensus finalize`'s answer, not a hand count:
`{"grade": "B", "counts": {"P0": 0, "P1": 1, "P2": 8}, "disposition_counts": {"accepted": 11,
"rejected": 3}, "human_review_needed": false, "errors": []}`. Seven lenses exercised,
`blocks_approval: false`, plus one cross-model voter (`codex`, `status: invoked`, 70.6 s).
Fourteen findings.

> **A correction, recorded because the mistake is instructive.** This section first said grade A,
> reasoning that the one counting P1 had been *fixed*. That is not the rule: `accepted` counts
> toward the grade whether or not it was repaired, and **only an AC-cited `rejected` clears it**.
> A round's grade records what that round found, not how much of it the author then tidied. The
> letter was hand-derived before the CLI ran, which this stage's own text forbids — "use its
> answer; do not re-derive one". Below B, threshold A, `auto_fix` on → the auto-fix loop runs.

- **1 P1 fixed** — `c1`, the `exercised_lenses` docstring.
- **1 P1 rejected on `AC-004`** — `k1`/`s1`, the merged-group coverage credit. See the
  disposition note; it does not count toward the grade and the reasons are recorded rather than
  waved through.
- **6 P2 fixed** outside the selection rule, which is a stated deviation (below).
- **6 P2 carried** for a human sweep.

A note on this review's own instrument: the rendered `/hm:review` that ran is the **installed
0.55.0 render**, which still fans out to seven dispatches. This change was therefore reviewed by
the thing it replaces.

## 🔍 Drift Findings

**`result: scope_violation`** — P1 severity per the drift gate, not counted in the code grade.

**Five files changed that no PLAN phase's `Scope in` named.** All five were found during execute
by running the full structural suite, and all five are documented in the PLAN's Phase 4 status
block: `test_render_dispatch_macro.py`, `test_no_claude_tool_calls_in_codex_output.py`,
`test_instruction_preservation.py`, `autopilot_gate_golden.json`, `test_autopilot_gate_render.py`.
The PLAN's R10 called the migration inventory "mitigated" after a mechanical `rg`; it was not.

**One incomplete phase.** PLAN Phase 3's scope names
`tests/structural/test_review_dispatch_has_no_literals.py`. **That file does not exist.** AC-008's
no-literals assertion was folded into
`test_render_review_lens_groups.py::test_no_lens_text_is_a_literal_in_the_template` and the fold
was never written back — the SPEC's Verification Criteria row for AC-008 and the PLAN's Testing
Strategy both still point at a path with nothing behind it. The assertion exists and passes; the
map to it is wrong.

> **The drift gate measured itself here, and that is worth recording.** The first computation
> scored 6 drifted paths, the second 25, the third (by hand) 5+1. The first was circular — the
> PLAN was updated *during* execute with the very files that drifted, so they read as in-scope;
> the second had a broken regex. A gate whose reference document the subject may edit is a gate
> with a hole, independent of this change.

## ✅ Consensus Findings

### P1 — `c1` · `lens_coverage.py:23` · FIXED

`exercised_lenses`'s docstring said an accepted file "carries a `lens` field matching both its
filename stem and a **known lens name**". `core.json` carries `lens: "core"`, and `core` is
deliberately absent from `ALL_LENSES`/`KNOWN_LENSES`. Worse, the paragraph this change *added*
two below it ("Every check below is unchanged and applies to a group file exactly as it did to a
per-lens one") reinforces the false reading.

Voice: `consistency` (solo lens votes alone, ADR-007). Disposition `accepted`.

**Why it is P1 and not a wording nit:** the docstring names a specific wrong edit —
`payload["lens"] in KNOWN_LENSES` — that reads like hardening and silently deletes the entire
merged path, because no group file would count as exercised again. A docstring that makes a
reader believe something false about behaviour is a defect; one that recommends a specific
breaking change is a trap.

**Fix:** the paragraph now says "a name `lenses_for_result_file` recognises", states that the
recognised name is a lens **or a group**, and names the wrong edit explicitly so the next reader
does not make it.

### P1 — `k1` + `s1` · `lens_coverage.py:72` · REJECTED, `authority: AC-004`

Two voices — `concurrency` and `security` — at the same file, same line, same tier, with aligned
CONCLUDE: `exercised_lenses` credits a merged group's full membership from the router table, so a
merged dispatch that substantively addressed two of its four lenses still yields `missing: []`
and `blocks_approval: false`.

**The finding is correct.** It is rejected only because **SPEC AC-004 specifies exactly this
behaviour** — "a round directory holding a single `core.json` … `missing` contains none of
design, functionality, robustness, consistency" — and SPEC Open Question #2 states the
consequence in the SPEC's own words: the gate "answers 'was this lens asked' rather than 'did
this lens deliver'". `robustness` reached the same finding and rated it **P2 for that reason**,
which is the severity disagreement recorded below.

**What the rejection does NOT dispose of, and why a follow-up is filed rather than closed.** The
three lenses supplied a fact ADR-003 did not weigh: the per-finding `lens` stamp **already
exists** (ADR-007 added it) and coverage simply does not read it. ADR-003 rejected "the agent
returns its own lenses-covered list" because an omission would block a clean review — a sound
objection to a *list*, but never applied to the *stamp*. Neither reviewer suggestion is safe as
written (`concurrency`'s would make a lens with no findings `missing`; `security`'s empty-vs-
subset rule blocks the common case where all four were reviewed and only one had findings), so
nothing was changed here beyond the precondition below.

### P2 — `codex-2` · `review.md.j2:764` · FIXED

The Auto-Fix Loop's re-dispatch instruction hardcoded "a missing `design` re-runs the merged core
call and produces `core.json`". Restore singleton groups — the one-constant reversal ADR-005
promises — and following that sentence writes a `core.json` that `lenses_for_result_file` no
longer recognises, leaving `design` missing on every retry. **The prose broke the reversal the
code preserves.** Now it says to read the group and its filename off the dispatch list, never
from a worked example.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None. Every cross-model finding was `accepted` at Step 3.6 against a source oracle.

## 🤝 Disagreements

**`lens_coverage.py:72` — P1 (concurrency, security) vs P2 (robustness).** Step 4a does not bridge
tiers, so these stayed independent rather than merging. The disagreement is substantive, not a
rounding difference: `robustness` rated it P2 **because it is disclosed** in SPEC Open Question #2
and ADR-003, and `concurrency`/`security` rated it P1 on the blast radius (one file now vouching
for four lenses, a 4× fail-open). Both readings are defensible and the disclosure is what settles
the disposition, not the severity.

## 🧊 Cross-model findings (frozen @ round 1)

Model `codex`, `status: invoked`, 70.6 s, 2 findings. Rounds 2..N re-read this section instead of
re-invoking.

| id | severity | file:line | summary | disposition | oracle |
|---|---|---|---|---|---|
| `da5d…` (`codex-1`) | P2 | `review.md.j2:216` | the merged reviewer is never told to return each finding's member lens; the main loop is left guessing among four | `accepted` | grep: the stamp instruction addresses the main loop; the dispatch brief never asked the agent |
| `e421…` (`codex-2`) | P2 | `review.md.j2:764` | the hardcoded recovery example breaks the promised one-constant reversal | `accepted` | by construction: with singleton groups `lenses_for_result_file("core")` returns `()` |

Both fixed. `codex-1`'s fix — the merged brief now ends "tag each finding with the lens it came
from" instead of "a defect under any of them is yours to report" — is the **precondition** for
ever addressing `k1`/`s1`: coverage cannot read a stamp the agent was never asked to write.

## 📋 P2 findings carried (not fixed)

| id | file:line | summary | why carried |
|---|---|---|---|
| `d1` | `review.md.j2:284,348` | the dispatch ternary is duplicated verbatim in both blocks | Real. The fix (move `description`/`brief_text` into `LensGroup`) is the right shape and is a design change, not a repair; AC-008's parity guard plus `test_the_confirmation_pass_groups_match_round_one` cover membership drift today, not prose drift. |
| `f1` | `conditional_router.py:174` | `lenses_for_result_file` returns static `LENS_GROUPS[stem]`, not the `present` list `lens_dispatch_groups` computed | Latent by the reviewer's own analysis — `mandatory_lenses` never makes `CORE_LENSES` partial on either preset, so `present == CORE_LENSES` always. A cross-check test is the suggested guard. |
| `s2` | `conditional_router.py:141` | the mixed-agent `ValueError` fires at render time only | The reviewer downgraded it themselves: it degrades to under-report, never over-report. |
| `k2` | `lens_coverage.py:32` | "every check is unchanged" understates that their semantic weight changed | Partially addressed by `c1`'s fix, which now says what is and is not checked. Kept listed because the reviewer's framing is sharper than the replacement text. |
| `r1` | `lens_coverage.py:72` | the P2 reading of `k1`/`s1` | Same finding, rejected under the same authority. |
| `c2` | `review.md.j2:134` | Step 1's count clause quoted the dispatched set beside a sentence enumerating the mandatory set — wrong antecedent on Side | **Fixed** (the clause now defers the count to Step 3). Listed here because the fix changed the sentence rather than the number. |

## 🔎 Confirmation passes

### confirm-1 — frozen `9018a08877cb`, span `2ff7f035..9018a088`

Seven lenses, `blocks_approval: false`, **three new findings**. Five lenses returned nothing and
independently re-derived the carried dispositions rather than restating them — `functionality`
re-traced `f1`'s "latent" label through `routable_lenses`' opt-out design; `design` checked the
one defect it expected from a merge (a single LLM turn inflating into four corroborating voices,
or a solo-lens finding losing its status by sharing an agent identity) and found Step 4d's
per-lens `source` handles both; `concurrency` looked for a different angle on `k1` before
accepting the instruction not to re-raise, and concluded it collapses to the same root cause.

| id | sev | file:line | finding | resolution |
|---|---|---|---|---|
| `cf-t1` | P1 | `test_lens_coverage_merged.py:60` | **The most-argued behaviour in this task was pinned by no test.** Every fixture tagged findings for all four members, so an implementation crediting `{f["lens"] for f in findings} & CORE_LENSES` — the alternative AC-004 rejects — passed every assertion identically. `k1`/`s1` was settled by citation and nothing else. | Fixed: `test_a_partially_covered_group_file_still_credits_every_member`, parametrized one-of-four / two-of-four. Five confirm-2 lenses independently traced that it fails under the rejected alternative. |
| `cf-c1` | P1 | `REVIEW-…-2026-09-13.md:188` | The terminal iteration table said `A` / `APPROVED` while the corrected Round 1 Summary said `B`. The table is what a reader and `/hm:wrapup` land on. | Fixed — rounds itemised. **Incompletely**: see `cf2-c1`. |
| `cf-c2` | P2 | `conditional_router.py:172` | `LENS_GROUPS`'s comment claimed one backward-compat mechanism; core-lens stems use the separate `ALL_LENSES` fallback. A maintainer "simplifying" it away breaks AC-004's third clause. | Fixed — both mechanisms named, with the consequence of deleting the fallback. |

### confirm-2 — frozen `6d6d27de3067`, span `2ff7f035..6d6d27de`

Seven lenses, `blocks_approval: false`, **one new finding**.

| id | sev | file:line | finding | resolution |
|---|---|---|---|---|
| `cf2-c1` | P1 | `REVIEW-…-2026-09-13.md:9` | `cf-c1`'s repair fixed the body table and left the **frontmatter** `grade: B` contradicting the body's `Final grade: A`. A reader skimming frontmatter, or a script grepping `grade:`, sees the stale value — the same confusion one field over. | Frontmatter corrected. The status stays `CHANGES_REQUESTED` regardless (see the note under the iteration summary). |

**What the confirmation passes bought.** Round 2 ended clean — zero new findings over the seven
round-1 fixes. Sweeping the whole failure space over a frozen artifact then produced three more,
and two of them sat where a scope-selective re-review structurally cannot look: the discriminating
power of the test suite as a whole, and this report itself. That is the case for the pass, made by
this review rather than asserted.

**The `consistency` lens raised every counting P1 in this review** — `c1`, `cf-c1`, `cf-c2`,
`cf2-c1` — and all four are the same shape: a document asserting something the code or the rest of
the document contradicts. Three of the four were written by this task's own author in the act of
repairing the previous one.

## 🔁 Oscillation

No repair rounds ran, so no oscillation scan was possible.

## 📏 Size & Complexity

Not measured — no repair round ran, so `review_churn` has no pre/post endpoints to compare.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | 7             | 6 (P2)    | —   |
| 2 (re-review of the 7 fixes) | A | 0 | 0 | 0 |
| confirm-1 (whole failure space, frozen `9018a088`) | — | 3 | — | 3 |

Final grade: **A** (round 2; confirm-1's repairs are budgeted separately and do not increment
`iteration_count`)
Iterations used: 2 / 3
Exit reason: converged
Status: **CHANGES_REQUESTED**
human_review_needed: **true**
Exit reason (confirmation pass): confirm-2 returned a new severe finding, which is terminal —
no third pass is ever dispatched in one `/hm:review`.

> **The code is clean; the status is not, and the difference is the point.** `confirm-2`'s only
> new finding (`cf2-c1`, below) is about THIS document's frontmatter, not about the change. The
> frontmatter was repaired. The status stays `CHANGES_REQUESTED` anyway, because the rule that
> makes a dirty confirm-2 terminal exists precisely to stop a review from patching its way to a
> clean declaration without a reader — which is exactly what declaring APPROVED here would be.
> A human decides whether a self-contradiction in the report, found and fixed, warrants
> re-running the pass.

> **This table said `A` / `APPROVED` while the Round 1 Summary two screens above said `B`.** The
> confirm-1 `consistency` lens raised it as a P1 and was right to: the terminal tabular summary is
> what a reader and `/hm:wrapup` land on, so an uncorrected table silently reinstates the exact
> belief the correction paragraph exists to prevent. Corrected here, and the "Stated deviations"
> wording below is corrected with it.

### Stated deviations

1. **The 2-pass redaction protocol ran with a self-built Pass 1 brief.** `hm two_pass_review
   redact` operates on `pr_title` / `pr_description` / `author` / `commit_message`; this change
   has no PR and no commit (wrapup owns it), so the CLI is a **verified no-op** here — its output
   was byte-identical to its input on a probe. Running the two passes as written would have made
   Pass 2 an identical re-dispatch of Pass 1, spending seven dispatches for nothing. The anchoring
   content in this setup is the author's own advocacy prose, so Pass 1 was given a brief with the
   rationale withheld. **Pass 2 was then not dispatched** — the findings were consistent and no
   metadata existed to restore, so the contextual-verdict half had no new input. The
   anchoring-neutralisation property was obtained; the two-pass *mechanism* was not run as
   written.
2. **Six P2s were fixed at grade B**, outside the selection rule (P2 is auto-fix eligible only at
   D/F). Reason: three of them — `codex-2`, `r2`, `t1` — are defects that make a *guard* silently
   stop guarding, which is the one class where leaving it in the report for a human sweep means
   the next reader sees green. The rest were one-line prose corrections in the same files.
3. **The confirmation pass DID run** (`confirm-1`, frozen at `9018a088`), after an earlier draft
   of this document recorded that it had not. Round 1 graded B, so the gate never reached its
   APPROVE exit at that point; round 2's re-review of the seven fixes reached A, and that is the
   arm the confirmation pass gates.
