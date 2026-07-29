---
type: spec
task_slug: wrapup-context-carry
status: approved
created: 2026-07-28
tags: [harness-maker, spec, python, observability, context-economy, delegation]
test_framework: pytest
tier: 2
research_doc: "[[RESEARCH-context-carry-economics-2026-07-28]]"
summary: "Count API calls not transcript records, and repair wrapup's silently-disabled delegation"
---

# SPEC — wrapup context carry

## 🎯 Intent

Two defects, discovered together while aiming `PLAN-context-carry-discipline`'s
follow-up lever at `hm:wrapup`:

1. **The meter over-counts by ~2.15×.** `economics_source.load_turns` emits one
   `TurnRecord` per assistant JSONL line. Claude Code writes one line **per content
   block** and stamps the *same* `usage` on each. One API call therefore bills two or
   three times.
2. **wrapup's delegation has been mechanically disabled since it shipped.**
   `delegation.stages: ["wrapup"]` is configured, `stage-delegate` exists, and the
   subagent was dispatched in **2 of 16** measured wrapup runs. The cause is not model
   judgment: the rendered command runs `wrapup_brief --root .` from a `!` line, which
   executes at the **base repo** where `HEAD` is `main`, and `derive_brief` treats its
   cwd as the task worktree — so the gate returns `degraded` on the normal Production
   path, every time.

The second is why `hm:wrapup` is the harness's worst context carrier; the first is why
nobody could see it. Fixing the meter first is not sequencing preference — it is the
only way this work's own before/after can mean anything.

## 🌅 Outcomes

| what | today | after |
|---|---|---|
| an API call split across N transcript records | counted N times | counted **once** |
| a report built from the two counting rules | silently comparable | **labelled**, so it cannot be silently compared |
| `wrapup_brief` invoked the way the rendered command invokes it | `degraded` on the normal path | `ok`, with the slug |
| a degraded brief | inline, silent, uncounted | printed, **one ledger row**, countable |
| whether the subagent was actually dispatched | observed nowhere | a second ledger row, written only on the dispatched path |
| delegation configured but never firing | invisible for 4 months | a failing `/hm:health` signal |

**No carry-reduction percentage is committed.** The mechanism is understood
(carry = ctx/turn × calls; delegation removes calls at wrapup's ~500k ctx/turn) and the
arithmetic suggests 51 → ~14 main-loop calls, but the delegated sample is n=2 and both
runs were atypical. What is committed is that the corrected meter makes the answer
measurable after the fact.

## 📏 The measurement this SPEC is built on

**Against a frozen corpus, because the live one moves.** `economics report` reads a rolling
`window_days: 30` and its window filter has a **lower bound only**, so every session spent
implementing this work enters the window and inflates the totals — the reference figures
could never reproduce. The corpus was therefore snapshotted before implementation began:

```
~/.cache/harness-maker/frozen-corpus-2026-07-28/-home-noel-harness-maker/   48 files, 162 MB
```

Every figure below comes from that snapshot, derived by
`tests/manual/oracle_dedupe_reference.py` — a script independent of the shipped
implementation, which does not yet exist. That independence is what makes these numbers an
oracle rather than a restatement.

**The split-record artifact, verbatim from one transcript:**

```
file=0217e9dd-….jsonl  message.id=msg_011CdF1bxf4qyKS3RE7i9RQR  records=3
  blocks=['thinking']   in=2 out=1663 cr=20352 cw=56171
  blocks=['text']       in=2 out=1663 cr=20352 cw=56171
  blocks=['tool_use']   in=2 out=1663 cr=20352 cw=56171
```

24,082 assistant records collapse to **10,945 calls** — 10,942 distinct `message.id`,
plus 3 because grouping is per-file: two ids genuinely recur across different subagent
transcripts, and merging those would fuse different agents' turns into one call.

| main loop, attributed spans | record-counted | call-counted |
|---|---:|---:|
| billed calls | 18,429 | **8,682** |
| total | $4,614 | **$2,150** |
| carry share | 74.9% | **79.2%** |
| `hm:wrapup` total / carry | $782 / $657 | **$339 / $294** |

**What survives the correction:** `mean_context_tokens` (a mean over identical values is
that value) and `context_composition`'s character shares (each content block appears in
exactly one record, so nothing is double-counted there). The RESEARCH document's
ordinal findings therefore stand; its absolute dollars do not.

**`hm:wrapup`, 16 runs:** 1,136 API calls, median **51 calls/run**, 283k–750k ctx/turn,
carry 86.8% of the stage's cost. Three runs hold **52%** of the stage's carry. The
rendered command carries 30 `!` lines, ~17 of them inside Steps 1–5.6 — the delegated
region.

## 📋 In-Scope Scenarios

**S1 — one API call is one turn.** Given a transcript in which three assistant records
share a `message.id` and carry identical `usage`, when the report is computed, then that
call contributes one turn and its `cache_read` is priced once.

**S2 — the change of unit is visible.** Given any report, when it is read, then it states
how many duplicate records were collapsed, so a figure produced before this change cannot
be mistaken for one produced after it.

**S3 — deduplication cannot move what it must not move.** Given records that share an id
and identical usage, when they are collapsed, then `mean_context_tokens` is unchanged and
`cache_read_usd` is divided by the group size.

**S4 — the delegation gate answers correctly on the normal path.** Given the
feature-branch workflow with a live task worktree on `hm/<slug>`, when the brief is
derived **through the exact invocation the rendered command makes**, then it returns
`status: ok` carrying that slug.

**S5 — the standalone path still degrades gracefully.** Given a wrapup with no task
branch (standalone, recovered, or flag-off), when the same invocation runs, then it still
returns `degraded` with an actionable reason and exit 0. This path is supported, not an
error, and the fix must not convert it into one.

**S6 — every invocation is counted, degraded or not.** Given any brief derivation, when it
completes, then exactly one ledger row records it — `ok` as well as `degraded`. A writer
that logs only failures satisfies the visible half of this and silently destroys the
denominator that makes a dispatch rate computable, which is the whole reason the ledger
exists. On the degraded path the reason is also printed.

**S9 — the rendered self-skip path actually writes its row.** Given a harness whose IDE has
no subagent-dispatch tool, when the rendered wrapup stage takes its self-skip branch, then
an `unavailable` dispatch row lands in the base ledger. The branch is prose in a template,
so nothing but executing what the template renders can show that it does anything at all.

**S7 — a configured-but-dead delegation fails health.** The observable is **whether the
subagent was dispatched**, not whether the brief was derivable: a derivable brief that is
never dispatched is the state this SPEC exists to detect, so a signal built on
derivability alone would reinstall the blind spot one level up. Three cases, all decided:

**The signal reads a recency window, never the whole file.** The ledger is append-only, so
"has a dispatch ever happened" goes green on the first success and stays green through any
later regression — which is this defect's blind spot, rebuilt. The window is: the most
recent **10** `kind: brief` rows **of any status**, for **this stage**, ordered by parsed
timestamp, plus every same-stage `kind: dispatch` row at or after the oldest of those. No
row-to-row pairing, so concurrent sessions interleaving rows cannot confuse it. A brief
whose timestamp will not parse is **excluded before the slice**; an undatable dispatch
falls out by comparison.

| `delegation.stages` names wrapup | ledger, evaluated over that window | signal |
|---|---|---|
| yes | no ledger, or no brief row with a readable timestamp | **fail** + action "no invocation recorded yet" |
| yes | every brief in the window `degraded`, zero dispatch rows | **fail** + action "the brief is not derivable" |
| yes | ≥1 `ok` brief, **zero** dispatch rows in the window | **fail** + action "dispatch is not happening" |
| yes | dispatch rows in the window, **all** literally `unavailable` | **pass**, N-A — this IDE has no dispatch tool |
| yes | ≥1 non-`unavailable` dispatch row in the window | **pass** |
| yes | a recent dispatch with an **unrecognised** status | **fail** — unevaluable is not a pass |
| no | any | **pass**, N-A, no score effect |

Row 3 covers both "never fired" and "fired once, then stopped" — they are the same
observation and the same remedy, so they are one arm rather than two. Row 2 is separate
because the remedy is a *different half of the seam*: a brief that cannot be derived means
the stage skips the dispatch before attempting it.

> **Amended 2026-07-29 — this section, not only AC-007.** The window used to read "the most
> recent 10 `kind: brief, status: ok` rows". That anchor stops being written by the very
> regression the signal detects, so the floor freezes in the last healthy era and the verdict
> reads `ok` indefinitely. AC-007 was corrected first and this section was not, which left the
> machine SPEC naming a **superseded table as AC-007's own oracle** — an implementer
> reconciling the two had no tiebreak, and following the oracle rebuilds the defect. Stage
> scoping and the undatable-brief exclusion are stated here for the same reason.

Three things this table settles that a shorter one hid:

- **A passing signal cannot carry a message.** `Signal.action` has exactly one consumer and
  it is gated on failure, so "pass with an action" renders nowhere. Both informational arms
  therefore **fail** — which is score-neutral at weight 0, because the dimension score sums
  the weights of *passed* signals only.
- **Row 2 is the state of every harness the day this ships.** Leaving it undecided is the
  recorded `absent-case = feature black hole` failure.
- **Row 3 exists because dispatch is impossible in some IDEs.** The rendered stage
  self-skips the subagent on Cursor and Codex, so those harnesses would otherwise sit
  permanently on row 1 with an action their user cannot satisfy. The self-skip branch
  records `unavailable` so the signal can tell "no dispatch tool here" from "the model
  never dispatched".

**The dispatch rate is a lower bound, not a measurement.** The reconciliation step that
writes the dispatch row is model-executed prose; a run that dispatches and then skips
reconciliation leaves no row. A rate below 1.0 is therefore evidence of *at most* that much
dispatch, never proof of non-dispatch.

**S8 — the drift signal survives the change of unit.** Given a transcript containing split
records, when ingestion completes, then `coverage` still reads ≈1.0 — it must keep meaning
"everything seen was priced" rather than collapsing to ~0.45 and going permanently red,
which would retire the one diagnostic that catches a real transcript-format change.

## 🚫 Non-Goals

- **A compaction or session boundary before late stages.** The original lever-1 framing.
  Deferred: reducing calls at high ctx buys the same carry as reducing ctx, needs no
  boundary, and does not touch the fused-workflow or autopilot contracts.
- **`hm:verify`.** 243 records against wrapup's 3,032, and zero attributed spans. It is
  named in the old lever for symmetry, not for cost.
- **Extending the delegate past Step 5.6.** ADR-004 keeps `git add` / commit /
  `task-land` in the main loop. Locked by the user: the ~9 further calls are 6% of the
  stage, and hiding the 5-layer worktree defense, the stash handshake, and land-abort
  recovery behind a subagent would make those failures undiagnosable.
- **Re-pricing.** `PRICE_TABLE` and its version are untouched; this is a counting fix,
  not a pricing one.
- **Retroactively rewriting committed reports.** Numbers already emitted by the old
  counting rule are labelled by S2, not restated. This does *not* cover
  `work-docs/RESEARCH-context-carry-economics-2026-07-28.md`, whose absolute dollars this
  work proves wrong — that document is corrected as part of this work unit, the same way
  it was corrected once before when the committed meter disagreed with its scratchpad.

## ⚙️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | project standard (CLAUDE.md) |
| Network | none | economics is a local-transcript reader; the zero-network contract holds |
| Determinism | fixtures only | tests must never read the developer's `~/.claude` transcripts |
| Verification tier | 2 | real arithmetic in `economics_source`; mutation is sampled, not on execute's hot path |
| `subprocess` | `shell=False`, `timeout=` | CLAUDE.md external-command rule |
| Backward compat | additive | the report gains a field; no existing key changes meaning |

## ⚠️ Accepted Risks

**The delegated sample is n=2 and neither run looks like the median.** One took 21 calls,
the other 166. The 51 → ~14 estimate is arithmetic over the rendered command's structure,
not an observed delta. S2's labelling is what makes the real delta knowable once the fix
has run a few times; no number is promised in advance.

**A load-bearing lesson is encoded in S4's wording.** Step 0.5 of the rendered wrapup
already warns, for `wrapup_receipt`, that "`!` lines run at the BASE repo" — and the very
next tool call in the same step gets it wrong. A test that reads `wrapup_brief.py` and
agrees with itself would have passed for four months. S4 must execute the invocation the
command actually makes.

**`delegation_fires` detects a STOPPED dispatch, not an INTERMITTENT one — decided, not
overlooked (user, 2026-07-29).** The verdict returns `ok` when *any* dispatch row sits in
the window, so a harness dispatching once every ten wrapups reads green on every
evaluation. That includes the very regime that motivated this work: dispatch happened in
**2 of 16** measured runs. A reviewer proposed comparing counts instead of existence.

It was not adopted because ADR-005 already establishes that `dispatch ÷ brief-ok` is a
**lower bound, not a rate** — the dispatch row is written by a model-executed
reconciliation step, so a run that dispatches and skips reconciliation leaves no row. A
count threshold strict enough to catch 2-of-16 would therefore redden healthy harnesses,
and a permanently-red action nobody can clear is the documented anti-pattern this SPEC's
`unavailable-only` arm exists to avoid. No non-arbitrary threshold was available.

**What this costs:** the signal catches "delegation broke and stayed broken" and misses
"delegation works one time in ten". Anyone re-opening this needs a defensible threshold —
the missing input is how often a real dispatch skips reconciliation, which nothing measures
yet. A related, accepted consequence: the ledger is shared across IDEs, so a single
`unavailable` row from a Cursor or Codex run can satisfy the `unavailable-only` PASS arm
while a Claude Code session's dispatch is dead.

## ✅ Verification Criteria

| Scenario | Mode | AC |
|---|---|---|
| S1 | unit (fixture transcript) | AC-001 |
| S2 | unit | AC-002 |
| S3 | property (Hypothesis) | AC-003 |
| S4 | integration (real git worktree, real argv) | AC-004 |
| S5 | integration | AC-005 |
| S6 | unit | AC-006 |
| S7 | unit (seven fixture trees) | AC-007 |
| S8 | unit | AC-008 |
| S9 | integration (rendered self-skip line, executed) | AC-009 |

### AC-001: one API call contributes exactly one turn

**Given** a fixture transcript containing three assistant records that share one
`message.id` and carry identical `usage`, alongside one record with a distinct id
**When** the economics report is computed
**Then** the turn count is 2, not 4
**And** `cache_read_usd` equals the price of the two calls' `cache_read` tokens counted
once each — so the assertion fails if the collapse keeps the row but sums the usage

### AC-002: the report states how many records it collapsed

**Given** the same fixture
**When** the report is produced
**Then** it carries a diagnostic naming the number of duplicate records collapsed, and on
this fixture that number is 2
**And** on a fixture with no split records the same field is present and 0 — an absent
field would let a pre-fix report read as a post-fix one

### AC-003: collapsing preserves context per turn and divides carry

**Given** any generated group of 1..N assistant records sharing an id and identical usage
**When** the group is collapsed to one row
**Then** `mean_context_tokens` over the collapsed set equals the per-record context value
**And** the group's `cache_read_usd` is exactly 1/N of the uncollapsed sum
**And** this holds for every N, which is why it is a property and not an example

### AC-004: the rendered command's brief invocation succeeds on the normal path

**Given** a temporary git repository with a task worktree on `hm/<slug>`, and the
`wrapup_brief` argv extracted from the **rendered** `.claude/commands/hm/wrapup.md`
**When** that argv is executed with cwd set to the base repo, as a `!` line runs it
**Then** the parsed stdout has `status: "ok"` and `brief.slug == "<slug>"`
**And** the argv comes from the rendered artifact, not from the test, so a template that
drifts back to the base-cwd form fails this AC
**And** the artifact is a **hermetic render into a tmp tree**, not the repo's committed
`.claude/commands/hm/wrapup.md`, so the AC tests the template rather than whatever the
dogfood copy last happened to be
**And** the test substitutes **only the `<slug>` token** with the branch it created,
asserting first that the extracted line still carries a base-relative `--root` — a test
that re-typed the whole argv would agree with itself and prove nothing

### AC-005: no task branch still yields a graceful degrade

**Given** the same repository with `HEAD` on `main` and no task worktree
**When** the same rendered argv is executed
**Then** the exit code is 0, `status` is `"degraded"`, and `verdict.reason` is non-empty
**And** `verdict.missing` names `slug` — the supported standalone path must not become a
failure, and a fix that made every cwd resolve would break it
**And** this holds for both standalone shapes: the argv with its `<slug>` substituted to a
name that has no task worktree, and the argv with the slug argument absent entirely

### AC-008: the ingestion drift signal survives the change of unit

**Given** a fixture whose records include a split group, and a second fixture whose split
group is **partly outside the reporting window**
**When** ingestion completes
**Then** `coverage` is 1.0 on the first and remains 1.0 on the second
**And** the second fixture is the one that bites: it is where a denominator that mixes
record-counted and group-counted terms produces a value outside [0, 1] or a silent
off-by-a-group

### AC-006: every derivation writes exactly one ledger row

**Given** a derivation that degrades
**When** it completes
**Then** the delegation ledger gains exactly one row carrying `stage`, `status`, and the
same `reason` string the verdict printed
**And** a second degrade appends a second row rather than replacing the first
**And given** a derivation that **succeeds**, it also appends exactly one row, with
`status: ok` — without this arm a writer that logs only failures passes the whole AC while
destroying the denominator, and the dispatch rate becomes uncomputable in the one direction
nobody would notice

### AC-007: health fails a configured-but-never-firing delegation

**Given** `delegation.stages` naming wrapup and a ledger holding ≥1 brief-ok row and **zero
dispatch rows**
**When** `/hm:health`'s readiness computation runs
**Then** the delegation signal is `passed: false` with a non-empty `action`
**And given** no ledger exists yet, the signal is also `passed: false`, with an action
**distinct** from the previous one — both arms must fail, because a passing signal's action
is never rendered, and they must be distinguishable, because the remedies differ
**And given** the window's dispatch rows are all `unavailable`, the signal is `passed: true`
— an IDE with no dispatch tool must not sit permanently red on an action nobody can satisfy
**And given** a recent dispatch row carries a status that is neither a known dispatch
outcome nor `unavailable`, the signal is `passed: false` — a corrupt or unrecognised status
is unevaluable, and unevaluable must never be spent as evidence of a pass
**And given** a ledger whose **oldest** rows contain a successful dispatch but whose most
recent 10 brief rows carry none, the signal is `passed: false` — delegation that worked
and then stopped is the regression this signal exists to catch, and a lifetime-existence
rule goes green on it forever
**And given** the most recent 10 brief rows are **all `degraded`**, the signal is
`passed: false` with an action **distinct from both other failing arms** — a brief that
cannot be derived makes the stage skip the dispatch before attempting it, so the two are
different halves of the seam with different remedies
**And** the window is anchored on **every** brief row, not only the `ok` ones: anchoring on
`ok` alone means the anchor stops being written by the very regression being detected, so
the floor freezes in the last healthy era and the verdict reads `ok` indefinitely
**And** rows are ordered by **parsed timestamp**, not by position in the file — file order
and timestamp order diverge under late writes and interleaved concurrent sessions, and `Z`
and `+00:00` are the same instant that a string comparison ranks hours apart
**And** a **brief** whose timestamp cannot be parsed is **excluded from the window before
the slice**, not merely sorted oldest: sorted oldest it survives the slice whenever the
ledger holds few enough briefs, lands at index 0, becomes the floor, and admits every
dispatch in the file — restoring the lifetime-existence semantics this signal removes. An
undatable **dispatch** needs no special handling; it falls out by comparison. When no brief
in the window is datable the signal is `passed: false`
**And** the window is **stage-scoped**: both writers stamp `stage`, `verify` is delegatable
and its rendered line carries no `--slug` so its briefs degrade structurally, and unfiltered
those rows would flip a correctly-dispatching wrapup to the degrading arm — while a verify
dispatch row would vouch for a wrapup that never dispatched
**And given** `delegation.stages` is empty, the signal is `passed: true` — the absent case
is decided, not left to fall through
**And** every failing arm is unreachable from brief rows alone **except** the
all-degraded arm, which is by definition a statement about brief rows — a signal wired to
mere derivability still fails this AC, because the healthy verdict remains unreachable
without a dispatch row

> **Amended 2026-07-29.** The first version of this AC said "most recent 10 **brief-ok**
> rows", which described — and therefore approved — an implementation whose anchor
> disappears exactly when delegation regresses. Two review rounds passed it before a
> re-review traced the consequence. The two clauses about anchoring and ordering are stated
> here rather than left to the ADR because both are properties an implementation can quietly
> lose while every other clause still holds.

### AC-009: the rendered self-skip branch writes its unavailable row

**Given** a hermetic render of the wrapup stage with `delegation.stages` naming wrapup
**When** the self-skip branch's ledger command is extracted from the rendered artifact and
executed from a base repo
**Then** the base ledger gains one `kind: dispatch, status: unavailable` row
**And** the command is extracted from the render, not written by the test — a prose branch
that says it records something records nothing, and no fixture-built ledger can reveal that

## ❓ Open Questions

None. The four decisions this stage surfaced were all resolved in interview:
scope (meter + delegation, no boundary), stage (wrapup only), delegate extent (ADR-004
holds), and silent-degradation defense (print + ledger + health signal).

`/hm:plan` owns the remaining *how*: whether the seam is closed by changing the rendered
argv, by making `derive_brief` resolve the task worktree itself, or by both; and where
the health signal is dimensioned.

## 🔍 Refinement Decisions

- **Round 0 (measurement, before any question).** Verified the split-record artifact
  against raw transcript lines, recomputed the headline under both counting rules, and
  confirmed `context_composition` is unaffected. This overturned the RESEARCH document's
  absolute figures and reframed lever 1 — the interview started from corrected numbers.
- **Round 1 — scope.** Meter correction + delegation repair; compaction/session boundary
  explicitly out. Rationale: carry = ctx/turn × calls, and the calls half is cheaper,
  already designed, and contract-free.
- **Round 1 — stage.** wrapup only; `hm:verify` dropped from the lever's name and scope
  on measured size.
- **Round 2 — delegate extent.** ADR-004 upheld. git stays in the main loop.
- **Round 2 — recurrence defense.** Loud reason + ledger row + `/hm:health` signal,
  over warn-only and over repair-only.
- **§2.5 inequality gate.** Two candidates generated, both skipped: test framework
  (common-ground — CLAUDE.md pins `pytest`), and the shape of the cwd fix (EIG below ε
  here; it is a *how* question owned by `/hm:plan`).
