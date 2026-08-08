---
type: experiment
task_slug: workflow-time-token-savings
phase: A4
status: pre-registered
created: 2026-08-08
registered_before_any_run: true
summary: "Does running /hm:wrapup in a fresh session reduce cost, or only relocate it?"
---

# Pre-registration — session length and the cost of `/hm:wrapup`

**This document is written before any run.** Nothing below may be amended after observing data
without an amendment note stating what was seen first — the precedent is
`stage_agent_ledger`'s own post-hoc widening, which is recorded in that module's docstring
together with the fact that an earlier version of the justification was flattering and false.

## 1. The hypothesis, and what would falsify it

**H1.** `/hm:wrapup` is expensive primarily because it inherits a long session's context, not
because of the work it does. Running it in a **fresh session** — one that must re-read the PLAN
and the diff it needs — costs materially less in total than running it at the end of the
originating session.

**H1 is falsified if** the fresh-session arm's total cost per completed wrapup is not lower by
at least the threshold in §5. The re-read is a real cost and may consume the entire saving;
that outcome is a valid result, not a failed experiment.

**Why it is worth measuring rather than assuming.** Measured 2026-08-08 across four projects,
`wrapup` is the highest-carry stage in every one of them (mean context 404k / 501k / 507k /
422k; carry ratio 0.84 / 0.75 / 0.89 / 0.84) and per-turn cost tracks mean context (research at
136k ≈ $0.14/turn; wrapup at 404k ≈ $0.24/turn). That is the motivation. It is **not** evidence
for H1, because it does not price the re-read.

## 2. Arms

| arm | definition |
|---|---|
| **A — inherited** (control) | `/hm:wrapup <slug>` invoked in the same Claude Code session that ran `/hm:execute` (and usually `/hm:review`) for that slug. This is today's default. |
| **B — fresh** | `/hm:wrapup <slug>` invoked as the **first** `/hm:` stage of a new session, with no prior stage in that session's transcript. The task worktree and its branch are unchanged; only the session boundary differs. |

Assignment is **by alternation over eligible wrapups in chronological order** (first eligible →
A, second → B, …), not by choice. Choosing per-case would let "this one feels big" select the
arm and confound the result.

**Eligibility.** A wrapup counts only if it (a) runs against an `hm/<slug>` task worktree,
(b) completes — reaches its own terminal banner or its `task-land`, and (c) is not a re-run of a
wrapup already counted for the same slug. An aborted or re-run wrapup is excluded from **both**
numerator and denominator, and the exclusion is logged with its reason.

## 3. Corpus

`harness-maker`, `spoton`, `strange_chess`, `edgelog` — the same four projects the
`economics` reader covers, all four now measurable after the Phase A1 encoder fix.

Projects are **not** pooled into a single mean. Their per-turn costs differ by 1.7×
($0.169/turn for edgelog vs $0.294/turn for spoton), so a pooled mean would mostly measure which
project happened to land in which arm. The decision rule in §5 is evaluated **per project** and
then combined by sign.

## 4. Metrics

**Primary — `total_usd` per completed wrapup**, attributed to `hm:wrapup` by
`economics stages`. For arm B this **includes** the re-read: every turn of the fresh session up
to and including the wrapup's terminal banner is charged to the wrapup, whether or not the
attributor tags it `hm:wrapup`. Charging only the tagged turns would hide exactly the cost that
decides the question.

**Secondary — `mean_context_tokens`** for the same population. It is the mechanism H1 proposes;
if the primary moves without it moving, the explanation is something other than carry.

**Explicitly NOT metrics:**

- **Wall clock is not summed across scopes.** `economics._wall_clock_by_scope`'s docstring states
  that `main` and `subagent` overlap in real time and must never be added. A "total wall clock"
  or a `subagent / (main + subagent)` share is an invalid quantity and may not appear in this
  experiment's analysis. An earlier draft of `RESEARCH-workflow-time-token-savings` reported such
  a ratio and it has been retracted; re-introducing it here would repeat a known error.
- **Turn count alone.** Cost is roughly `turns × mean_context`; either factor can move while the
  other compensates.

## 5. Decision rule and threshold

Per project, let `median_A` and `median_B` be the median `total_usd` per completed wrapup in each
arm. **Medians, not means** — a single compaction-heavy wrapup would otherwise decide the
result.

- **Adopt fresh-session wrapup for that project** iff `median_B <= 0.75 × median_A`
  (a ≥25% reduction) **and** `n >= 8` per arm for that project.
- **Reject** iff `median_B >= 0.95 × median_A`.
- **Inconclusive** otherwise, or whenever `n < 8` per arm — reported as inconclusive and **not**
  rounded toward adoption.

Combination across projects: adopt globally only if **no project rejects** and at least two
adopt. A mixed result adopts per project via `harness.yaml`, or not at all — it does not average.

The 25% threshold is set here, before any data, because a smaller effect would not justify a
workflow change that costs the user a session switch on every task.

## 6. Handling the terminal span cap

Between 20% and 54% of each project's spend sits in turns past the attribution span cap
(`capped_turns` / `capped_usd`), and the cap is **terminal** — those turns stay `(unattributed)`
and never join `by_stage["hm:wrapup"]`. Arm A's wrapups are far likelier to be capped than arm
B's, because arm A runs late in a long session.

**Therefore the primary metric is systematically biased in H1's favour** if taken naively: arm
A's most expensive wrapups are the ones most likely to have their cost land outside the stage
bucket entirely.

The correction, fixed in advance:

1. Every counted wrapup records `capped_turns` and `capped_usd` for its session at the time it
   ran (`economics report --root <p>`).
2. A wrapup whose session was capped **before** the wrapup began is **excluded from the primary
   analysis** and reported separately as `capped-excluded`, with its count.
3. If more than 30% of arm A is excluded this way, the primary comparison is declared
   **inconclusive regardless of the numbers** — an arm whose expensive third is unmeasurable
   cannot be compared against one whose is.

## 7. Analysis command

Run per project, after `n >= 8` per arm:

```bash
uv run python -m harness_maker.economics stages --root <project> --days <window>
uv run python -m harness_maker.economics report  --root <project> --days <window>
```

`stages` supplies `hm:wrapup`'s `total_usd`, `turns` and `mean_context_tokens`; `report` supplies
`capped_turns` / `capped_usd` for §6. Arm membership is not derivable from either — it is
recorded per wrapup in the log below at the time of the run, because a session boundary leaves
no marker either tool reads.

## 8. Run log

Filled in as runs happen. A row added after the analysis has begun invalidates the
pre-registration and must say so.

| # | date | project | slug | arm | `total_usd` | `mean_context_tokens` | capped before start? | excluded (reason) |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

## 9. What this experiment does not decide

- Whether other stages benefit from a fresh session. `wrapup` is measured because it is the
  highest-carry stage in all four projects; nothing here generalises to `execute` or `review`.
- Whether carry can be reduced *within* a session (compaction tuning, tool-output discipline).
  That is RESEARCH Approach D and a stated Non-Goal of this PLAN.
- Anything about the `(unattributed)` 51% of spend, which no stage owns and which this
  experiment's population excludes by construction.
