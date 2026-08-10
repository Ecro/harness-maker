---
type: review
task_slug: multi-lens-review-round
status: CHANGES_REQUESTED
created: 2026-08-10
reviewers_invoked: [code-reviewer(correctness), code-reviewer(test-quality), codex]
consensus_method: cross-check
run_id: 20260810T2350Z
grade: B
human_review_needed: true
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multi-lens-review-round
  computed_at: 2026-08-10T23:50:00Z
---

# REVIEW — multi-lens-review-round (round 1)

## 🎯 Round 1 Summary

**Grade B** (0 consensus-passed P0, 1 consensus-passed P1). Threshold is **A**, so
**CHANGES_REQUESTED**. `human_review_needed: true` — eight `manual-only` findings sit at P0/P1.

Three voices: two Claude `code-reviewer` lenses (correctness, test-quality) and **codex**.
**antigravity `skipped`** (exit 1, empty response) — its fourth consecutive unusable attempt
across this task's plan and review stages. This review is a 3-voice review, not 4.

**The headline is not the grade.** Twenty-three findings landed and they cluster on one theme:
*the change's central claims are asserted nowhere, and its own retry rules contradict each other.*

## 🔍 Drift Findings

`result: clean`. All 16 changed files are inside the PLAN's declared scope
(`execute.md.j2`, the three baseline artifacts, the new render test, the amended ledger-wiring
test, the 8 regenerated snapshots, and the two work-docs). No PLAN-scoped file is unchanged.

## ✅ Consensus Findings (`consensus-passed`)

### P1 — A dead dispatch fails the round but has no repair path
*codex + claude-r1, same file, lines 249/253 (within ±5), same tier, aligned CONCLUDE.*

`overall_assessment` makes a dead dispatch or unparseable JSON a round FAIL. The retry then says
**"Re-dispatch only the lenses that returned FAIL"** — and a lens that died never *returned*
anything. So the round is FAIL, there is nothing in `blocking_issues[]` to rewrite, and no lens
qualifies for re-dispatch. The executor's defined actions are exhausted while the verdict is FAIL.

Both voices independently reached the same two likely behaviours: burn the budget on an empty
round and escalate, or proceed on the two surviving PASSes — **a silent pass with one lens never
run.** The second is the exact failure mode the fail-closed rule was written to prevent.

**Fix:** re-dispatch every lens that returned FAIL **or failed to return at all**.

## ⚠️ Weak Consensus

None. Every other cross-voice agreement failed the surface-match filter on **severity tier**,
not on substance — see below.

## 📝 Manual-Only Findings

> **Read this section before reading the grade.** Six defects were found by **two independent
> voices each** and are nonetheless tagged `manual-only`, because Step 4a forbids bridging
> severity tiers and the two voices scored them differently. The grade is B because of a
> tagging rule, not because these are doubtful. This is precisely the case
> `human_review_needed` exists for.

### P0 — Round 2 has no definable verdict (codex P0 · claude-r1 P1)

The single most important finding in this review, and it is **verified in the shipped text**, not
inferred. Three sentences in `execute.md.j2` are mutually unsatisfiable:

| | Sentence |
|---|---|
| Merge table | `overall_assessment` — **PASS iff all three PASS** |
| Retry | **Re-dispatch only the lenses that returned FAIL** |
| Retry | **No verdict carries between rounds** |

Round 2 therefore holds **fewer than three verdicts**. Read strictly, three PASSes cannot exist
and the gate can *never* clear round 2 — every A.5 whose first round fails escalates to the user.
Read charitably, the executor carries the round-1 PASSes, which the third sentence explicitly
forbids, and clears the round on lenses that never saw the rewritten file.

**This is a producer/consumer gap inside this task's own artifacts.** PLAN ADR-006 states the
correct rule — "each round's merge is computed over the lenses dispatched *in that round*" — and
that qualifier **did not reach the template**. The ADR is right; the shipped prompt is wrong, and
the shipped prompt is what executes.

**Fix:** scope the PASS rule to the lenses dispatched in the round.

### P1/P2 — The reviewer's own Hard Rules discard out-of-lens defects (claude-r1)

`test-reviewer_body.md.j2:105` says an observation that matches none of the 8 banned categories
is **downgraded to a `suggestion`**, and `:97` says suggestions **do not change
`overall_assessment`**. The schema has no `suggestions` field. The `coverage` lens's core question
— duplicate scenario coverage — maps to no category at all.

So a lens that sees a defect outside its category downgrades it, has nowhere to put it, emits
nothing, and returns PASS. **That defeats the measured justification for this entire change**: the
evidence in the PLAN is that a lens returning PASS on its own rubric surfaced two defects in
another lens's category. Under the shipped rules those two defects vanish.

### P1 — "In one message" is asserted nowhere (claude-r2)

Concurrency is the property the change buys and the reason the round-trip baseline was raised by
2. `test_three_lens_dispatches_precede_the_resolution` asserts only *count* and *order*. Split the
three dispatches into three fenced blocks with "dispatch, await the verdict, then the next"
between them and the test stays green — while the behaviour reverts to the serial,
one-category-per-round gate this task exists to replace.

### P1 — No per-target positive control (claude-r2)

`_bodies()` asserts only that *something* was found. Its own docstring says content discovery
exists because "path-based discovery would silently miss the codex family" — but nothing asserts
the codex artifact is present. If `.agents/skills/hm-execute/SKILL.md` stopped carrying the A.5
gate, every test in the file would pass over the two remaining claude artifacts.

### P1 — The no-git rule does not cover the codex render (claude-r2 P1 · codex P2)

The invocation filter matches `!…git…` or a line starting with `git`. The codex arm renders
commands as `Bash("cd <WT> && git diff")` — neither shape. A future `git diff` reinstated in the
retry passes on exactly the artifacts where it would be written that way.

### P1 — The `scenarios_missing` handoff assertion is inert (codex P1 · claude-r2 P3)

`assert "scenarios_missing" in retry` searches a ~40-line region that **already contains the
token** in the ordinary fix instruction ("author one test per `scenarios_missing[]`"). Delete the
after-only handoff arm entirely and the test still passes.

### P1 — The ledger guard was weakened, not re-pointed (codex P1 · claude-r2 P2)

`expected` is now the constant `1` for `execute`, plus a substring search for
`One row per **round**` over the whole document. A second, genuinely separate test-reviewer round
added later with no emit line passes; so does deleting the A.5 emit while any other
`stage_agent_ledger emit` exists in the file. The phrase check has no locus and goes inert the
moment the words appear anywhere.

**This one is mine to own.** The PLAN claims the guard was "re-pointed, not weakened". Two voices
say otherwise and they are right: re-pointing would derive the expected count from the number of
fan-out blocks, not hard-code it.

### P1 — Raising `aggregate_chars` does not implement ADR-008 (codex)

ADR-008 says instrumentation-gated text should not be *charged* to the ratchet. What shipped
instead raises the frozen aggregate by 2130 for both variants — a permanent allowance that will
absorb the next 2130 characters of **real** shipped growth silently. The decision was the user's
and stands; the **implementation** does not match the stated rationale.

### P1/P2 — Dedupe key collapses distinct defects (codex P1 · claude-r1 P2)

`test_file:test_function:category` merges two genuinely different bad assertions in the same
function under the same category, and leaves undefined which duplicate's `line`/`title`/`reasoning`
survives. The authoritative rewrite list becomes incomplete.

### P2 — Remaining test-quality gaps (claude-r2, codex)

- Lens ownership is pinned to the dispatch **line**, so three distinct labels with three identical
  prompt bodies pass — the degenerate fan-out the test names in its own docstring.
- The rewrite-conditioning check is a two-word vocabulary filter; *"Do not modify anything in
  `passing_tests[]`"* evades it and restores the frozen-list reading.
- The before/after handoff is checked by selector *mention*; no content transfer is required.

### P2/P3 — Consistency

- `test-reviewer_body.md.j2:96` still calls `passing_tests[]` FROZEN while the merge table says it
  decides nothing.
- `execute.md.j2:10` still says "the test-reviewer's reasoning" (singular) for a three-lens gate.
- The ledger prose says `--pass` is the round number; the command literal still reads
  `<attempt-number>`.

## 🤝 Disagreements

Six same-issue pairs were scored in different tiers (codex higher in five of six). Per Step 4a they
are **not** consensus candidates and are never bridged. They are recorded as independent findings
above and are the whole reason `human_review_needed` is set.

The pattern is worth naming: codex consistently graded *contract and enforcement* defects higher
than the Claude reviewers did. On the round-2 verdict contradiction — a rule that cannot be
satisfied on the shipped surface — codex said P0 and the Claude reviewer said P1.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | file:line | disposition | summary |
|---|---|---|---|---|---|
| b28182a484bd5d8e | codex | P0 | execute.md.j2:249 | accepted | retry-round PASS undefined |
| 20652ead09dd7733 | codex | P1 | execute.md.j2:249 | accepted | dead lens excluded from retry |
| 76728f8b24504bae | codex | P1 | execute.md.j2:249 | accepted | PASSing lens never re-verifies its own driven rewrite |
| 76f941e801997feb | codex | P1 | execute.md.j2:242 | accepted | dedupe collapses distinct defects |
| 2e2074c3e585f011 | codex | P1 | test_multi_lens_a5.py:160 | accepted | scenarios_missing assertion inert |
| 807fd6f70e4f3673 | codex | P2 | test_multi_lens_a5.py:153 | accepted | handoff checked by mention only |
| ae50a800e6d873f0 | codex | P2 | test_multi_lens_a5.py:170 | accepted | no-git misses codex call form |
| 728b3c9db55bbbcb | codex | P1 | test_stage_agent_ledger_wiring.py:113 | accepted | ledger guard weakened |
| d9ce5c6bab2d09e9 | codex | P1 | surface_baseline.json:3 | accepted | aggregate raise ≠ ADR-008 |

**antigravity:** `skipped` — `exit 1; CLI said <<<<empty>>>>`. Fourth consecutive failure across
this task. Not a finding about this change; a standing degradation of the voter pool.

### Iteration 2 — fixes applied

21 fixes, covering every P0/P1/P2 in round 1 except the ADR-008 re-implementation (see below).
Applied in the review's own suggested order; the two load-bearing ones first.

| # | Sev | Finding | Fix | Status |
|---|---|---|---|---|
| 1 | P0 | Round-2 verdict unsatisfiable | `overall_assessment` row now reads **"PASS iff every lens dispatched in THIS round returned PASS"**, and says outright that a round-1 PASS is never reused | Applied |
| 2 | P1 | Dead dispatch has no repair path | Retry re-dispatches every lens that returned FAIL, **failed to return at all**, or supplied a `blocking_issues` entry that was acted on | Applied |
| 3 | P1 | Out-of-lens defects discarded via a non-existent `suggestions` field | Brief now **routes** them to real carriers; the agent body's Hard Rule no longer says "downgrade to a suggestion" but names the same three carriers | Applied |
| 4 | P1 | PASSing lens never re-verifies the rewrite its own finding drove | Covered by arm (c) of fix #2 | Applied |
| 5 | P1/P2 | Dedupe collapses distinct defects | Key is now `test_file:test_function:category:line`; survivor is the earliest lens in table order | Applied |
| 6 | P1 | Concurrency asserted nowhere | New **contiguity** assertion: the three dispatch lines must be consecutive and inside one fence | Applied |
| 7 | P1 | No per-target positive control | `test_all_three_targets_carry_the_a5_gate` asserts all three concrete paths | Applied |
| 8 | P1 | no-git blind to the codex call form | Third shape added: `Bash("… git …")` | Applied |
| 9 | P1 | `scenarios_missing` assertion inert | Sentence-scoped and must carry the after-only qualifier | Applied |
| 10 | P1 | Ledger guard weakened | `expected` now derived from the number of fan-out **blocks**; the per-round phrase must sit between the last dispatch and the emit line | Applied |
| 11 | P2 | Lens ownership pinned to the label | Lens must appear in **both** the `description=` and prompt segments of its own line | Applied |
| 12 | P2 | Rewrite-conditioning a two-word filter | Broadened to an action class incl. `frozen`/`freeze`/`do not modify\|touch\|change` | Applied |
| 13 | P2 | Agent body still calls `passing_tests` FROZEN | Restated as advisory, pointing at `blocking_issues` + `scenarios_missing` | Applied |
| 14 | P3 | `:10` singular reviewer | "the merged verdict of its lenses" | Applied |
| 15 | P3 | `--pass <attempt-number>` | `<round-number>`, both arms | Applied |
| — | P1 | ADR-008 implementation ≠ its rationale | **Not fixed** — deliberate, see below | Deferred |

**The strengthened test caught a fix-induced gap immediately.** After #9 landed, the handoff
assertion went red: the sentence naming `test_function` did not also name `scenarios_missing`, so
the two arms were bound only by adjacency. The template was corrected to state both arms in one
sentence. That is the first repair round in this task where the *test* caught the *fix* — which is
the entire point of #6–#12.

**Scope expansion, recorded:** `templates/agents/test-reviewer_body.md.j2` was listed under
"Not affected" in the PLAN. Fixes #3 and #13 change it, because the defect lives at the seam
between the stage brief and the agent's own Hard Rules and cannot be closed from one side.

**#16 (ADR-008) deliberately not fixed.** Excluding instrumentation-gated text from the surface
measurement is a change to the measuring code, which the PLAN puts out of scope, and it is
recorded as debt in the BASELINE-DELTA document rather than silently absorbed. The finding stands.

**Second re-baseline.** Round 2 added **+1724 characters** and **zero round-trips**. Every one of
those characters is defect repair, not feature surface. `_ATOMIC_RATCHET["execute"]` 35322 →
37048, `aggregate_chars` +1724 per variant, snapshots regenerated (the agent body moved too).

### Iteration 3 — re-review of the fixes, and its own repairs

Codex + one Claude reviewer re-read the round-2 diff with one instruction: *assume the fixes broke
something.* They found 13. **Three of codex's five, and the Claude reviewer's headline P1, were
created by round 2.**

| Finding | Created by | Fix |
|---|---|---|
| Merge trusted a lens's self-reported `overall_assessment` while the new brief openly lets a lens report a defect — an inconsistent-but-parseable reply passed the gate | round 2 | PASS is now **recomputed** from the merged carriers |
| `per_scenario.quality=FAIL` became a blocking state with **no repair action**, so the same lens re-ran against an unchanged file until the budget died | round 2 | third repair arm: retarget or delete the offending test |
| A test authored for `scenarios_missing[]` was reviewed only by the coverage lens that asked for it — never for false-RED or discrimination | round 2 | authoring re-dispatches all three |
| Contiguity assertion demanded three *consecutive physical lines*, so a correct multi-line `Task(` rewrite would fail | round 2 | same fence + no prose between; formatting no longer frozen |
| Rewrite-verb class flagged the **correct** sentence "`passing_tests` is not frozen and must not control rewrites" | round 2 | explicit advisory-disclaimer exemption |

### Iteration 4 — the last, and the sharpest finding of the review

The Claude reviewer read the round-3 text and found that **the fix's own load-bearing clause could
never fire**:

> Clause (c) re-dispatched a lens that "supplied a `blocking_issues` entry you acted on — even if
> it returned PASS". But `test-reviewer_body.md.j2:93` defines PASS as *zero* `blocking_issues`.
> A compliant lens supplying an entry has therefore already returned FAIL and is caught by clause
> (a). **(c) is reachable only for a schema-violating lens** — while the hole it was written for,
> a **rewrite** leaving the other two lenses blind to the changed file, stayed wide open, because
> the authoring clause fired only on authored tests.

Four clauses collapsed into one: **repair anything → re-dispatch all three.** That closes the
rewrite hole, deletes the unreachable clause, and removes the standing contradiction with "no
verdict carries" — a round now always has all three verdicts about the current file.

Six more landed with it, three of them out-of-diff consequences the change had made false:

| Finding | Fix |
|---|---|
| Dedupe keyed on `line` almost never merged cross-lens duplicates (two lenses anchor one defect on different lines) — the opposite of round 1's complaint | key is `file:function:category` carrying a line **list**; both concerns satisfied |
| `per_scenario` FAIL with **empty** `covered_by` named a test that does not exist | routes to the authoring arm |
| A truncated sentence shipped in the prompt: *"Ask what those newly made reachable."* | completed |
| Ledger round-count derived from line adjacency — a blank line between dispatches would demand 3 emit rows, driving the template into the colliding-rows state ADR-007 forbids | derived from the **fence** |
| `stage_agent_ledger.py`'s invariant note asserted A.5 is "a single dispatch, not batched" | corrected; the note now explains why the arithmetic still holds and what would break it |
| `stuck_body.md.j2` still told the escalation agent the budget was "2 attempts", and its "last 3 outputs" heuristic now collects one round | both corrected |

**A test caught a fix, twice.** The strengthened `scenarios_missing` assertion went red the moment
its own fix landed (the two handoff arms were bound only by adjacency), and the round-4 lens-
ownership rewrite was made *because* review showed the round-3 version would fail a correct future
template. That two-way traffic — tests catching fixes, and reviews catching over-strict tests — is
new in this task and is what rounds 6–12 were built for.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New | Of which fix-induced |
|-----------|-------|---------------|-----------|-----|---|
| 1 (init)  | B     | —             | 23        | —   | — |
| 2         | —     | 21            | 2         | —   | — |
| 3 (re-review) | B | 5             | 2         | 13  | **4** |
| 4         | A     | 8             | 0         | —   | — |

Final grade: **A** — zero consensus-passed P0/P1 remain after round 4.
Iterations used: 3 / 3 (rounds 2 and 4 were fix rounds; round 3 was a full re-review)
Exit reason: **converged**
Status: **APPROVED**
human_review_needed: **true**

**The flag stays true, and not as a formality.** Two things are unresolved by design:

1. **ADR-008's implementation still does not match its rationale** (codex, P1, round 1). The
   decision — instrumentation-gated text should not be charged to the ratchet — was the user's and
   stands. What shipped raises the frozen aggregate by **6149** instead of excluding those blocks
   from the measurement, so the next 6149 characters of *real* growth land silently. Recorded as
   debt in `BASELINE-DELTA-multi-lens-review-round.md`; the fix is a change to the measuring code,
   which this PLAN puts out of scope.
2. **Fail-closed is still unverified by any test.** A round that treats a dead lens as PASS is
   indistinguishable from a round that passed. No render test can see it — the behaviour is the
   executor's, not the document's. Named in the PLAN's Phase D.5 as a known gap; it needs a live
   A.5 with a deliberately killed dispatch, which belongs in `/hm:verify` or a manual fixture.

Counters: unreviewed 0 · prior-fix 4 · unattributed 0

## What this review measured about itself

The task's thesis is that parallel breadth finds independent defects in one round, but cannot find
defects the *previous round's fix* created. This review is a clean four-round instance of both
halves:

- **Breadth worked.** Round 1's 23 findings came from three voices with little overlap; six
  defects were found by two voices independently, and the single most important one — a retry
  round whose verdict was unsatisfiable — was caught by codex at P0 and a Claude reviewer at P1.
- **Breadth did not stop fix-induced defects.** Round 3 found 13 more, **4 of them created by
  round 2's fixes**, including one where the repair described the hole and attached it to a
  condition that could never fire.
- **The severity-tier rule cost visibility.** Six two-voice defects were tagged `manual-only`
  purely because the voices scored them in different tiers, so the grade read B while a confirmed
  P0 sat in the report. Consensus counted 1 of the 23. That is the rule working as written, and
  it is why `human_review_needed` exists — but a reader who skims to the letter learns the wrong
  thing.

## Why the auto-fix loop was not entered in this session

The loop is enabled and two rounds remain, so this is a deviation and it is recorded rather than
taken silently.

**This session has now produced a fix-induced defect in six consecutive repair rounds** — five
during planning (each revision introduced the next round's P0) and at least one during execute
(a compaction broke a shipped test by re-wrapping a line). The P0 in this review is itself the
direct product of the fix for the *previous* round's P0: ADR-006's no-carry rule was added to kill
a stale-verdict defect, and it created an unsatisfiable one.

Twenty-three findings, several of which require judgment about the `test-reviewer` agent contract,
is not the shape of work to start at the end of a 390-minute session on that record. The findings
are specific and each names its fix; a fresh session can apply them with the round-1 evidence
intact in this document.

**Suggested order** — the first two are load-bearing, the rest are mechanical:

1. Scope the PASS rule to the lenses dispatched in the round (kills the P0).
2. Decide the out-of-lens carrier: either drop the agent body's downgrade rule, or give each lens
   a legal category. Without this the multi-lens design does not deliver its measured benefit.
3. Re-dispatch non-returning lenses; include `line` in the dedupe key.
4. Test gaps: single-fence assertion for concurrency, per-target positive control, codex-shaped
   git matcher, sentence-scoped `scenarios_missing`, fan-out-derived ledger count, prompt-segment
   lens ownership, broadened rewrite-verb class.
5. Consistency: agent body `passing_tests` line, `:10` singular, `--pass <round-number>`.
6. Revisit ADR-008's implementation — exclude instrumentation text from the measurement rather
   than raising the frozen aggregate.
