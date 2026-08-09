---
type: review
task_slug: workflow-time-token-savings
status: APPROVED
created: 2026-08-09
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - commands/make.md
    - tests/e2e/test_autopilot_chain_e2e.py
    - tests/snapshot/*.expected.yaml
  scenario_misses: []
  task_slug: workflow-time-token-savings
  computed_at: 2026-08-09T00:00:00Z
---

# REVIEW — PLAN-workflow-time-token-savings, phases A5 + B1–B5

Reviewing commit `bdf533a0` (59 files, +1965/−254) against `bdaa0ae0`. This is the second
review of this slug; the first covered Track A (`f2eb0743`).

## 🎯 Round 1 Summary

**Two P0s, both in the autonomy gating, both reproduced by direct execution before any fix.**
Neither was found by the change's own 22-case test matrix. One came from a cross-model voter
and one from the security reviewer; the author's self-review before landing found neither.

Voter pool N = 4 (code-reviewer, security-reviewer, codex, antigravity). Grade after round 1:
**B** — two `consensus-passed` P1s, zero `consensus-passed` P0. `unverified_severe` = TRUE.

## 🔍 Drift Findings

**`result: scope_violation`** — three file groups changed outside every PLAN phase's declared
scope:

| File | Phase that should have owned it | Assessment |
|---|---|---|
| `commands/make.md` | A5 (disclosure row for the new axis) | Real omission in the PLAN's scope list, not scope creep. A structural gate (`test_make_fastpath_contract`) *forced* the edit — a new `HarnessConfig` axis must be classified and disclosed. |
| `tests/e2e/test_autopilot_chain_e2e.py` | B3 | B3's scope named `tests/unit/test_autopilot_caps.py` and `tests/render/`; no phase named `tests/e2e/`. The file had to change because B3's fail-closed default halts the clean chain. |
| `tests/snapshot/*.expected.yaml` (×8) | A5 / B4 (both change rendered `harness.yaml`) | Mechanical regeneration; no phase named `tests/snapshot/`. |

None of these is the change wandering outside its intent — each is a consequence the PLAN's
scope lists failed to anticipate. The honest reading is that **the scope lists were written
from the source files the author expected to edit, not from the gates those edits would trip.**

**Incomplete phase (one):** B3's scope named `tests/unit/test_autopilot_caps.py` as the home of
the judgment-gate matrix. That file is unchanged; the matrix went to a new
`tests/unit/test_autopilot_judgment_gate.py`. Equivalent coverage, different file — recorded
rather than corrected, because moving it now would churn a green suite for no behavioural gain.

## ✅ Consensus Findings

### P1 — `autopilot_caps.py:363` · auto_full's auto-answer wrote no ledger row `[2/4]`
*security-reviewer + code-reviewer, independent, same line, same tier.*

The `auto_full` branch set two JSON fields and fell through to the ordinary
`advance_authorized` append. On the ledger an `auto_full` pass over a human decision was
byte-identical to an `auto_safe` advance, so no audit could count how many judgments the
widest level skipped. The only durable record was the model choosing to obey a prose
directive — the failure mode the directive's own last sentence names.

**Fixed.** `gate_auto_answered` added to `LedgerEvent` and appended in that branch.

### P1 — `configure.md.j2:77` · the config surface shipped a stale level vocabulary `[2/4]`
*code-reviewer + codex, independent.*

`/hm:configure` offered `gated / auto_safe / full`: the retired spelling was selectable, the
new `auto_full` was unreachable except by hand-editing yaml, and the new default `ask` could
not be returned to once left — `cli._build_autonomy_override` rejected it. Line 79 also
asserted "the plan interview … always stop[s] regardless", which `auto_full` specifically
overrides. **The AST guard could not see this**: it walks `src/**/*.py` only.

**Fixed.** Four-value vocabulary, corrected safety claim, and `ask` accepted by the config
surface while every runtime surface still refuses it.

## ⚠️ Weak Consensus

None. See the next section for why that line is misleading.

## 📝 Manual-Only Findings

### P0 — `autopilot_caps.py:339` · `auto_full` advanced past a CHANGES_REQUESTED review
*security-reviewer, single source. Reproduced by execution.*

```
$ boundary --current review --judgment-gate pending   # marker level: auto_full
{"proceed": true, "next_stage": "verify", "judgment_auto_answered": true, ...}
```

ADR-010 states the grade half is "mandatory at every level, including `auto_full`", and
ADR-009's Interview #5 **explicitly rejected** prose-only enforcement — "a grep-asserted
control can pass while the behaviour is absent". The implementation shipped exactly that: a
two-valued flag cannot carry a three-way distinction, so a CHANGES_REQUESTED review and an
APPROVED-with-`human_review_needed` review both arrived as `pending`, and `auto_full` cleared
both. The separation lived in one template sentence, placed *after* the dominant instruction
telling the model to carry the verdict to Step 2.

**Fixed** by giving the flag a third value, `blocked`, which halts at every level.

### P0 — `step_manifest.md.j2:50` · a `gated` marker auto-advanced
*codex, single source. Reproduced by execution.*

`boundary` never read `marker.level` to decide *whether* to advance — every branch read it only
to decide *how*. A `gated` marker returned `proceed: true`. The hole predates this work; what
this work added is the **reachability**: B4's picker offers "or **gated**" and instructs "arm
with the PICKED level", making it a normal path on the new default (`ask`) harness.

**Fixed** in code — a prompt-level fix would not be enforcement.

### P1/P2 — three findings the consensus rule dropped despite two voices each

| Finding | Voices | Why it landed here |
|---|---|---|
| `stage_end_summary.md.j2:40` — judgment stages lost their only `gate-blocked` call | code P1 + security P2 | severity tiers differ |
| `stage_end_summary.md.j2:61` — bracketed placeholder inside a rendered shell command | security P1 + code P2 | severity tiers differ |
| un-re-rendered harnesses deadlock at plan/review | security P1 (:344) + code P2 (:353) | tiers differ **and** lines 9 apart |

All three were fixed anyway. See **Disagreements** — the rule, not the findings, is what needs
attention here.

### P2 — `interview.py:1347` · absent `instrumentation` key resolves ON — REFUTED

The security reviewer proposed scoping the absent→True default to harnesses that already have
`stage-agent*.jsonl` rows. **Rejected**: that makes a render's output depend on gitignored
runtime state, so two renders of the same repo could disagree — a determinism break traded for
a marginal privacy gain. The absent-key population is empirically this maintainer's own four
projects; a fresh install gets `False` from the class default.

### P2 — two antigravity findings, refuted by execution

- `autopilot_ledger --level full` rejected → **false**: `hm autopilot_ledger smoke --level full`
  returns a normal JSON payload.
- `_committed_level` does not normalize → **irrelevant**: it compares only against `ASK_LEVEL`,
  which no alias maps to.

## 🤝 Disagreements

**The consensus rule failed three times in one review, in the same way.** Two reviewers
identified the same defect at the same location and the "do not bridge severity tiers" rule
recorded both as `manual-only` — the P1 voice and the P2 voice cancelling into no consensus at
all. This is `[fail:design] severity-tier-split-drops-unanimity`, recorded 2026-08-08 with
count:1; this review takes it to **count:2 with three fresh instances**.

The rule's purpose is sound — a P0 and a P3 on one line are probably different observations —
but adjacent tiers on an *identical* file:line are far more likely to be one finding with two
risk estimates. Nothing here changes the rule; the recurrence is recorded so the next PLAN that
touches consensus has the evidence.

**A second, quieter failure:** both P0s were `manual-only` by construction (single source), and
`manual-only` findings are **not auto-fix eligible**. Had the orchestrator followed the letter
of the auto-fix rule, two reproduced P0 fail-opens in the autonomy gate would have been left
for a human to notice. They were fixed on reproduction evidence and labelled as such rather
than relabelled `consensus-passed`.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | location | disposition | oracle |
|---|---|---|---|---|---|
| — | codex | P0 | `step_manifest.md.j2:50` | **accepted** | direct `boundary` run: `proceed: true` on a gated marker |
| — | codex | P1 | `configure.md.j2:77` | **accepted** | grep: line 77 reads `gated / auto_safe / full` |
| — | codex | P2 | `step_manifest.md.j2:49` | **accepted** (mechanism restated) | render: the `ask` picker's "Arm with the PICKED level:" is followed by a different bullet, not by a command. Codex attributed it to whitespace trimming; the defect is real, the mechanism named was not. |
| — | antigravity | P2 | `autopilot_ledger.py:354` | **rejected** | `hm autopilot_ledger smoke --level full` succeeds |
| — | antigravity | P2 | `autopilot.py:837` | **rejected** | `_committed_level` compares only to `ASK_LEVEL` |
| — | antigravity | P2 | `cli.py:1493` | **accepted** | `_build_autonomy_override("ask", …)` raised `Exit(1)` |
| — | antigravity | P2 | `Production.yaml.j2:128` | **rejected** | the `else true` arm mirrors `_parse_instrumentation`'s absent-key rule by design |
| — | antigravity | P3 ×2 | style | **rejected** | no behavioural claim |

**A capture defect in this review's own instrumentation, recorded rather than hidden:** the
antigravity invoker's stdout was piped through `tail -c 4000`, which truncated the **head** of
its JSON payload. An unknown number of its findings — everything before the `cli.py:1493` entry
— was lost before it could be read. The six above are what survived. Antigravity's vote in this
review is therefore **partial**, and any later analysis reading this section as that model's
full contribution would be wrong.

## Round 2 — fixes applied

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P0 | `blocked` gate value; halts at every level | `autopilot_caps.py` | Applied · manual-only, reproduction evidence |
| 2 | P0 | `gated` marker fails closed | `autopilot_caps.py` | Applied · manual-only, reproduction evidence |
| 3 | P1 | `gate_auto_answered` ledger event | `autopilot_caps.py`, `autopilot_ledger.py` | Applied · consensus-passed |
| 4 | P1 | four-value vocabulary + `ask` in the config surface | `configure.md.j2`, `cli.py` | Applied · consensus-passed |
| 5 | P1 | placeholder out of the rendered command | `stage_end_summary.md.j2` | Applied · manual-only (tier split) |
| 6 | P1 | stale-render diagnostic in the halt reason | `autopilot_caps.py` | Applied · manual-only (tier split) |
| 7 | P2 | `AutonomyConfig` docstring corrected | `models.py` | Applied |

**A test was found to encode the bug.** `test_clear_proceeds_at_every_level` parametrized
`gated` as a level that advances on a clear gate. Fixing the P0 turned it red — the test was
wrong, not the fix. Narrowed to `_ADVANCING_LEVELS`, with a dedicated
`test_a_gated_marker_never_advances`.

Cost: **+1,270 chars** of shipped surface, attributed in the BASELINE-DELTA. Moving ADR-010's
grade half out of prose and into an enforceable flag is longer than the sentence that failed,
and that is the correct direction.

## Round 3 — the fix's own P0

**Both round-2 reviewers independently found a P0 in round 2's fix**, and it was the same
mistake in a new place: `--judgment-gate` kept `default="pending"`, and `pending` is the one
value `auto_full` clears. So an OMITTED verdict at `auto_full` was auto-answered — the round-1
hole, reopened at the only level where it matters. Worse, the stale-render diagnostic added in
the same round lived in the `else` branch that `auto_full` can never reach, so the level most
likely to be running against a stale render was the level that printed nothing.

The error underneath it: I implemented "fail-closed on absent" by mapping absence onto a value
that is, by design, clearable. Fail-closed is not a default value — it is a distinction.

| # | Severity | Summary | Status |
|---|---|---|---|
| 8 | P0 | `default=None`; absence is un-clearable at every level, with its own diagnostic | Applied · **[2/2] round-2 consensus** |
| 9 | P1 | `plan.md.j2` never emitted `blocked`; a twice-`MAJOR_REVISION` plan was auto-answered at `auto_full` | Applied · security-reviewer |
| 10 | P1 | "unsure → `pending`" pointed the tiebreak at the clearable value; now → `blocked` | Applied · security-reviewer |
| 11 | P2 | `blocked` was a silent no-op outside plan/review; hoisted above the membership test | Applied · security-reviewer |
| 12 | P2 | `gate_auto_answered` fired on runs that then stopped at the land gate | Applied · code-reviewer |
| 13 | P2 | two of the round-2 tests passed for the wrong reason | Applied · code-reviewer |

**Finding 13 deserves its own line.** The render test asserted `"--judgment-gate blocked" in
text`, which the shared partial satisfies for *every* stage including `plan` — so it would have
passed with review's grade sentence deleted. The unit test for the `blocked` path never
asserted the ledger row it exists to produce. Both were written by the author in the same round
that fixed a P0, and both would have reported that fix as verified.

Verified matrix after round 3 (direct execution, not inference):

| call | result |
|---|---|
| absent verdict + `auto_full` | HALT `judgment_gate`, reason names STALE RENDER |
| `blocked` + `auto_full` | HALT |
| `blocked` + a non-judgment stage | HALT |
| explicit `pending` + `auto_full` | proceed + `gate_auto_answered` |
| `clear` + `auto_safe` | proceed |
| any gate + `gated` marker | HALT `kill_switch`, marker preserved |

## Round 3's own re-review — four more, and a disagreement between reviewers

| # | Severity | Summary | Status |
|---|---|---|---|
| 14 | P1 | the block that BUILDS the command still said "omitting it reads as `pending`" — the opposite of the code, read last | Applied |
| 15 | P2 | `gate_auto_answered` placement — **the two reviewers proposed opposite directions** | Applied, round 3's way |
| 16 | P2 | the tiebreak covered pending-vs-blocked and lost clear-vs-pending | Applied — a `clear < pending < blocked` ladder |
| 17 | P2 | plan's new `blocked` sentence had no render test | Applied |

**The disagreement, and how it was settled.** Round 2's code-reviewer said the
`gate_auto_answered` row fires on runs that then stop at the land gate, inflating the count.
Round 3's security-reviewer said suppressing it there makes such a run byte-identical on the
ledger to a `clear`-gate `auto_safe` run — the exact indistinguishability the row exists to
remove. **Round 3 wins**: the row answers "was a human judgment cleared?", and the answer is
yes regardless of what the chain did next. The outcome became a field (`advanced`), so both
questions stay answerable. The round-2 move was in the wrong direction and is reverted.

**And once more in this file's own tests:** the section heading read
`# ── 2 + 3: pending stops by default, and absent IS pending ──`. That was true for exactly one
round, and that round was the P0. Corrected, with the reason left in place.

Cost: **+1,133 chars**. Cumulative net for the PLAN: `claude` **+3,460**, `codex` **−357**.

## Round 4 — requested by the user, because round 3 was never re-reviewed

The config cap (`max_review_rounds: 3`) was spent. Round 3's fix was therefore the only one no
one had checked, **in a layer that had broken on every previous fix**. The user asked for one
more round instead of landing on that. Seven findings, three of them consequential:

| # | Severity | Summary | Voices |
|---|---|---|---|
| 18 | P1 | `review.md.j2`'s `CHANGES_REQUESTED` bullet still said "proceed to wrapup" | security |
| 19 | P1 | `plan.md.j2`'s `blocked` keyed on an immutable past fact, so a user who accepts the risk can never clear it | codex + security |
| 20 | P1 | `ruff format --check` would fail CI on a round-3 line | code + security |
| 21 | P1 | `review.md.j2:608` ordered autopilot to STOP on the one gate `auto_full` exists to answer | code + security |
| 22 | P1 | the absent-verdict diagnostic blamed a stale render on a FRESH render, prescribing a no-op remedy | code + codex |
| 23 | P1 | the `advanced` field was pinned only in its False case — a constant `False` passed the suite | code |
| 24 | P2 ×3 | a gated stop wrote no ledger row; the `blocked` hoist comment overstated; the directive claimed "proceeding past" on runs that halt | code + security |

**#18 is the one that mattered most.** Nothing in code can distinguish a failed grade from a
passing one — `boundary` acts solely on the value the model types. That bullet was therefore a
live route back to the round-1 P0, sitting in the same file as the fix for it.

**#19 is the mirror of the mistake this whole review has been about**, pointed the other way. I
moved a threshold into an un-clearable verdict without checking what the verdict made
impossible: `blocked` keyed on "the second pass returned MAJOR_REVISION", which stays true
after a human explicitly accepts the risk, so the halt became permanent and its own prescribed
remedy could never lift it. Safe direction, wrong behaviour — and it overrode a human decision,
which is the opposite of what this PLAN is for.

**#20 would have gone red in CI.** `ruff check` passes on that line; only `ruff format --check`
catches it, and it had not been run since the round-3 edit. `[fail:lint]
ruff-format-not-in-local-verify-pass`, count:2, recurring.

**#23 is the fourth test in this review found to pass for the wrong reason**, and the fourth
written by the author in the same round that fixed a P0.

One cross-model P0 was **refuted**: codex argued that an absent verdict fails open on the six
non-judgment stages. Those stages are never instructed to classify — `--judgment-gate` does not
appear in their rendered text at all — so absence there is the absence of a question, not an
unanswered one. Requiring `clear` from them would halt 6 of 7 stages on every existing harness,
a cost codex's own suggestion acknowledges. The residual it points at is real but guarded:
`test_exactly_the_judgment_stages_carry_the_flag` compares the rendered set against the code
set, so a stage that gains a judgment without joining `_JUDGMENT_GATED_STAGES` fails the suite.

`antigravity` returned `status: failed` with an empty response — the known intermittent
large-prompt residual. **This time the capture was correct** (written straight to a file, not
piped through `tail`), so "empty" is a measurement rather than an artifact of the harness
operator's own truncation, which is what round 1 could not distinguish.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 13        | —   |
| 2         | B     | 7             | 4         | 1 (P0, in the fix) |
| 3         | A     | 10            | 4         | 0   |
| 4         | A     | 10            | 0         | 0   |

Final grade: **A**
Iterations used: 4 / 3 — **the cap was exceeded by user instruction**, and the extra round was
not empty: seven findings, one of them a live route back to the round-1 P0 and one a CI-red
formatter failure.
Exit reason: converged
Status: **APPROVED**
human_review_needed: **true**
Counters: unreviewed 0 · prior-fix 1 · unattributed 0

⚠️ **Grade A but `human_review_needed = true`.** Both round-1 P0s and the round-2 P0 were
`manual-only` by the consensus rule — single-source, or split across severity tiers — so none
of them ever counted toward the letter. **The grade was A at every round while three P0 fail-opens
in the autonomy gate were live.** The letter is not the finding here; the findings are.

Two further reasons a human should look before this is trusted:

1. **Every fix round to this layer introduced a defect, and round 4 is now the unreviewed one.**
   Round 1's code had two P0s; round 2's fix had its own P0; round 3's fix left three
   contradictions and a CI-red line. Round 4 fixed those. By induction the honest expectation
   is that round 4's changes contain something too — they are prose corrections and one test,
   which is the lowest-risk shape so far, but "lowest risk so far" is not "verified".
2. **The cross-model half of round 1 is partially lost.** The antigravity invoker's stdout was
   piped through `tail -c 4000` by this stage's operator, truncating the head of its payload.
   An unknown number of its findings were never read.

