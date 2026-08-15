# BASELINE-DELTA — ai-review-exit-criteria (Phase 4)

Attribution for three baseline raises landed by `PLAN-ai-review-exit-criteria`. All three come
from one change to `/hm:review`: the stage stops exiting on *issue exhaustion* ("no more
findings") and starts exiting on *risk closure* (a declared failure space having been covered).

## What changed in the shipped surface

| Baseline | Before | After | Δ |
|---|---:|---:|---:|
| `review` command size | 35 828 | **47 652** | **+11 824** (Phase 4 +4 872, Phase 5 +5 825, review repairs +1 127) |
| `execute` command size | 39 343 | 41 222 | **+1 879** |
| `execute` round-trips | 17 | 18 | **+1** |
| `plan` command size | 48 595 | **51 130** | **+2 535** |
| `review` round-trips | 8 | **22** | **+14** (Phase 4 +8, Phase 5 +3, ledger row +1, repairs +2) |
| Shipped surface aggregate (claude) | 380 334 | **398138** | +17804 |
| Shipped surface aggregate (codex) | 308 250 | **326030** | +17780 |

**Direction: this makes the shipped surface larger.** Say it plainly, because a document that
lists the numbers without saying so is technically complete and practically misleading. Every
`/hm:review` invocation in every harness rendered from this version carries ~4 872 more
characters of instruction, on every round.

The aggregate rises by more than the two command rows sum to (+7 862 claude vs +6 751 from
`review` + `execute`). The remainder is the Codex-path re-render of the same two stages plus the
`reviewers:` routing comment in both `harness.yaml` templates — no third stage changed. The
figures above are **read from `surface_baseline.json`**, not derived by adding the rows: an
arithmetic estimate written here first said 387 085, and the measured value was 388 196. The justification is not that the cost is small — it
is that the stage previously had no exit criterion an operator could check, and the characters
are that criterion.

The Codex target moves by the same amount at `hm-review` — keys
`surface.codex.hm-review.chars` and `surface.codex.hm-review.round_trips`. `/hm:review` is
single-source across targets, so a change
to `review.md.j2` renders into `.agents/skills/hm-review/` as well. There is no Codex-specific
edit in this task — the two rows are the claude rows observed through the second renderer, and a
Codex delta that did *not* track the claude one would be the finding.

`execute` moves for a separate, later reason — follow-up **F1**, which adds `Phase A.4 — the
false-RED screen` ahead of the reviewer gate. It is in this document rather than its own because
it is the same task's follow-up and lands in the same commit; its own itemisation is in the F1
section below.

The same single-source rule applies to it: `hm-execute` moves in the Codex target too — keys
`surface.codex.hm-execute.chars` and `surface.codex.hm-execute.round_trips` — because
`execute.md.j2` renders into `.agents/skills/hm-execute/` as well. No Codex-specific edit exists
in this task for either stage.

`plan` moves for Phase 6 (AC-010), itemised at the end of this document — and so does `hm-plan`
in the Codex target (`surface.codex.hm-plan.chars`), by the same single-source rule that carries
`review` and `execute` across both renderers. No Codex-specific edit exists in this task. `spec`, `wrapup` and
every other stage are byte-identical.

## The size delta, itemised

1. **The five-lens dispatch fence** — one `Task(` line per mandatory lens (`correctness`,
   `failure`, `concurrency`, `security`, `tests`), in one message.
2. **The per-lens result contract** — five literal result paths under
   `.claude/observability/.hm-lens-results/<slug>/<round>/`, plus the rule that a dispatch which
   returns nothing produces no file.
3. **The coverage CLI call** and its three verdict keys (`exercised`, `missing`,
   `blocks_approval`).
4. **The approval condition's second conjunct** — `grade ≥ grade_threshold AND
   blocks_approval == false`.
5. **The AC-013 coverage blocker** — terminal, per-lens, rendered distinctly from a finding.
6. **The auto-fix re-dispatch rule** — re-dispatch whatever the CLI's `missing` list names.
7. **`review_base` resolution** at round 1, stored at `refs/hm-freeze/v1/<slug>-base`.

## Compaction ran first, and returned little — why

Raw was **+5 158**. A compaction pass cut it to **+4 872** (−286, −5.5%) by deleting a Step-1
paragraph that Step 3 restated and tightening three sentences.

That return is small compared with the entries above this one in the size table (which routinely
cut 25–45% from raw), and the reason is a genuine difference in kind rather than a lack of
effort. Most of those deltas were *prose* — explanation, rationale, contradiction repair — and
prose compresses. Most of this delta is **structure that render tests bind to**:

- Five literal `Task(` lines cannot become one parameterised call with a `<lens>` placeholder.
  That was considered and rejected on the same grounds the Phase A.5 fan-out rejected it (see
  the `execute` entry in the size table): the lenses run **concurrently in one message**, which
  is the property AC-002 asserts, and a loop over one template reads as serial.
- Five literal `<lens>.json` paths cannot collapse to a brace expansion, because
  `correctness.json` would then not appear in the rendered text — and that per-lens path is what
  the coverage CLI reads and what `test_each_mandatory_lens_is_dispatched_not_merely_named`
  asserts.

Compressing either would make the assertion unrenderable while leaving the instruction intact —
i.e. it would buy characters by deleting the enforceability, which is the move this repo's size
budget exists to make visible rather than to reward.

## The round-trip delta, itemised

`8 → 16`: five lens dispatches (+5), `hm freeze resolve-base` once at round 1 (+1), and
`hm lens_coverage check` twice (+2 — once after the round-1 dispatch, once in the auto-fix loop
after re-dispatching the missing lenses).

**The two CLI calls replace a judgement, not a cheaper call.** Before this change nothing
computed which lenses had run: the executing model reported its own attendance, and the gate
believed it. That is the self-report hole AC-011 exists to close. The round-trips are what buy
the gate an input it cannot fabricate.

**Honest limit on that claim** — recorded because the SPEC records it too, and it should not be
lost between documents. `hm lens_coverage check` verifies **liveness**, not validity: that a
result file exists, parses, and self-identifies with a matching lens id. It cannot observe
whether any reviewing occurred. A main loop that writes five well-formed files without
dispatching anything passes it. See AC-011's "judged proposition, exactly" note in
`specs/SPEC-ai-review-exit-criteria.md`.

## `payload_digest` and `render_sha`

Both are content hashes over the rendered surface, so both moved the moment the review stage's
bytes changed. Neither is a signal independent of the `review` row above — they are the same
edit observed at the digest level, and they would have moved for a one-character fix.

They are listed because the attribution gate requires every moved key to be named, and that rule
is right even for derived keys: a digest that moves *without* a content row above it is the
interesting case, and it cannot be spotted unless the uninteresting case is also written down.

## Ownership — why only Phase 7 may touch these baselines

These three numbers (`review` size, `review` round-trips, the surface aggregate) are a ratchet.
ADR-010 of `PLAN-workflow-time-token-savings` reserves changing them to the phase that measures
them, for one reason: the failure mode is
**ratchet-rebaselined-by-its-own-subject** — a phase that grows the surface and then edits the
number that would have flagged the growth, in the same commit, with the justification written by
the party that benefits from it.

The guard against that here is not restraint, it is separation. This document is the artifact a
reviewer reads *instead of* the diff, and the compaction result (+5 158 raw → +4 872) is stated
before the justification rather than after it, so a reader can see the size of what compaction
could not remove and judge the claim that the residue is structural.

## Related

- `specs/SPEC-ai-review-exit-criteria.md` — AC-002, AC-003, AC-011, AC-013.
- `work-docs/PLAN-ai-review-exit-criteria.md` — ADRs, and the Phase 4 A.5 gate-bypass record.
- `work-docs/RESEARCH-ai-review-exit-criteria.md` — the six merge criteria this implements.


## F1 — `execute` +1 879 chars, +1 round-trip

One numbered phase, `Phase A.4`, between Phase A and Phase A.5. The round-trip is the test
command; the characters are the two dispositions a passing test may take and the instruction to
read the counts rather than infer them.

**Why this delta is bought back rather than spent.** A three-lens `test-reviewer` dispatch costs
roughly 350 k tokens. Eleven findings across two tasks were "this test passes before the
implementation exists" — mechanically decidable by the one pytest run this phase adds. The
character cost is paid once per render; the reviewer rounds it removes are paid per task.

**What could not be compressed.** The clause admitting a legitimate passing test (a negative
invariant, vacuously true until the construct it forbids exists) and its requirement of a RED
positive sibling. Dropping it yields a shorter rule — "every test must fail" — that is *wrong*,
and whose failure mode is an author deleting the invariant to satisfy the gate.


## Phase 5 — `review` +5 825 chars, +3 round-trips

The confirmation pass: criterion ⑤, N clean passes on a **frozen** diff. It is the half that
makes Phase 4's coverage mean something — sweeping a declared failure space over an artifact that
moves underneath you is coverage of nothing in particular.

**Round-trips**: `hm freeze commit` (+1), `hm freeze read-base` (+1), one more
`hm lens_coverage check` over the pass's own results (+1). `read-base` is a round-trip whose
purpose is to *prevent* a computation — re-resolving the base at pass time silently uses one that
drifted with the commits landed during the review, and the drift is invisible in the diff the
pass then reviews. It fails loudly on the absent case rather than falling back to a re-resolve.

**Where the characters are, and why they do not compress.** The six-arm outcome block. The arms
are (incomplete coverage) × (clean) × (`auto_fix` off) × (first pass) × (second pass), and this
SPEC's S4a exists *because* an earlier draft collapsed two of them: zero-new-severe with
incomplete coverage then matched **no** branch at all — S4's conjunct fails, S5's dirty trigger
does not fire, and S9's not-run path does not apply because the pass did run. The pass dispatches
five lenses and a dispatch failure is medium-likelihood, so that state is reachable. Merging arms
to save characters is exactly how the hole was made; the arms stay.

**Cost, stated plainly.** A review that reaches the approval path now spends five more lens
dispatches, or ten plus a repair round on the dirty path — and the dirty path may still end
`CHANGES_REQUESTED`. Nothing extra is spent on a review that never approves: S9 skips the pass
entirely and records `confirm_pass_ran: false`, which is a different fact from a pass that ran
and found nothing.


## Phase 6 — `plan` +2 535 chars, **0 round-trips**

Step 4.5: terminal whole-document re-validation. It spends no new call — it re-uses the second
pass the existing two-pass cap already allows, and re-aims it from "the sections you revised" at
"the whole document".

**The characters are a measurement and a prohibition, and neither survives compaction.**

The measurement: 12 recorded `plan-validator` episodes, **none ever clean**, blocking findings
verified against source, and one PLAN recording that pass 2's criticals were *created by the
pass-1 fixes*. That is the argument for re-reading the whole document — a revision's damage is
cross-section, so reading only what changed misses it by construction.

The prohibition: the pass is **terminal** and the cap is **not raised**. Same data — every
recorded three-pass episode also ended `MAJOR_REVISION`, so a third pass buys findings, not
release.

Cutting the numbers leaves "re-validate the whole PLAN, terminally, and do not add a pass",
which reads as bureaucracy. This repository's own record is that a costly mandatory step
presented without its justification gets silently reinterpreted as optional
(`[wiki:gotcha] loop-body-skipping-review-stage`). The numbers are what make the instruction
survive contact with a model looking to save a dispatch.

`MAJOR_REVISION_TERMINAL` is a new **frontmatter** value, not a new ledger verdict — the ledger
keeps its three, because a new enum value needs every reader updated and the missed one is the
failure mode (`[fail:design] new-marker-content-field-must-update-every-reader`, count:3).
