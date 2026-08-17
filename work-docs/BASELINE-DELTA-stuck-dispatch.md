---
type: baseline-delta
task_slug: stuck-dispatch
created: 2026-08-17
owns: [surface_baseline.json, _ATOMIC_RATCHET.execute, _CLAUDE_ROUND_TRIPS.execute]
summary: "Baseline movement from wiring /hm:execute's blocker path to the stuck agent"
---

# Baseline delta — stuck-dispatch

Baseline ownership follows **ADR-010**: one phase owns the ratchet, and a phase that
re-baselines the guard it tripped is `ratchet-rebaselined-by-its-own-subject` (count:2). This
document is this task's own attribution — it does not amend any previous task's. The subject
here is the *blocker path*; the guard it moved is the *size* of `execute.md`. The gate that
guards the change itself (`test_stuck_dispatched_on_blocker.py`) is not re-baselined by it.

Figures below were written **after** the final template edit and the regeneration that followed
it. Every earlier delta document in this directory that got corrected got corrected for exactly
that ordering — and this one was corrected once for the other reason, below.

## 1. Aggregate

| | Before | After | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 417 164 | 418 905 | **+1 741** |
| `aggregate_chars.codex` | 349 105 | 351 729 | **+2 624** |

**Direction: the shipped surface got LARGER on both variants.** No offsetting deletion was
available — this change adds an escalation that did not exist rather than replacing one.

**The two variants move by different amounts, and that asymmetry is real** — the opposite of the
copy error the `validator-pass-cap` document had to retract. The dispatch renders through
`agents/_partials/dispatch.md.j2`, whose `dispatch_intro()` is a single line on Claude
(`Dispatch each item below with the Task tool.`) and a two-paragraph spawn-and-join contract on
Codex, because `spawn_agent` returns when an agent starts rather than when it answers. The Codex
arm therefore pays ~880 chars more for the same instruction, in the one rendered Codex surface
(`.agents/skills/hm-execute/SKILL.md` — `synthesize._codex_stage_skills` emits exactly one file
per stage). Nothing about the blocker path itself differs between them.

## 2. Per-command

Every row below is the same command under a different measure: the claude command `execute` and
its Codex counterpart `hm-execute`.

| Key | Subject | Before | After | Δ |
|---|---|---|---|---|
| `_ATOMIC_RATCHET` | `execute` | 41 459 | 43 200 | **+1 741** |
| `_CLAUDE_ROUND_TRIPS` | `execute` | 18 | 19 | **+1** |
| `surface.claude.…​.chars` | `execute` | 42 664 | 44 405 | **+1 741** |
| `surface.claude.…​.round_trips` | `execute` | 18 | 19 | **+1** |
| `surface.codex.…​.chars` | `hm-execute` | 40 564 | 43 188 | **+2 624** |
| `surface.codex.…​.round_trips` | `hm-execute` | 17 | 18 | **+1** |

The aggregate deltas in §1 are these per-command `chars` deltas — `execute` is the only command
this change touches, on either variant.

`payload_digest` and `render_sha` move with every regeneration by construction — the first is a
hash over the payload just tabulated, the second the commit it was generated at (`ea8087ff`).
Neither is an independent movement to attribute.

> **The ratchet's previous entry read `41222`, and it was STALE by 237 chars.** That is measured,
> not inferred: stashing only this task's template edit and re-running the `flag_on` fixture
> renders **41 459**. A first draft of this document attributed `41222 → 42595` as `+1373`, and a
> review round refuted it by noticing that the machine-generated `surface_baseline.json` pair
> reported `+1136` for the same unconditional insertion — two claude measurements of one edit
> cannot disagree. The drift predates this change and is not attributed to it. It survived
> because the assertion band is `measured * 1.02`, which a 237-char stale base clears silently;
> the only way to catch it is to measure BOTH endpoints, which is now written into the ratchet
> comment for the next person.

## 3. What moved and why

The `stuck` agent has shipped in **every** preset since 0.1.0. Its own body names its triggers:
"`/hm:execute` Phase A.5: test-reviewer FAIL retry budget … exhausted", Phase D unfixable, ADR
conflict. And `grep -r stuck src/harness_maker/templates/stages/` returned **zero** — no stage
template ever dispatched it. So `execute.md.j2`'s blocker path did what it said and no more:
document the blocker in the PLAN, surface the failure output, stop. The agent written to name the
binding constraint behind that output never ran on any of its three triggers.

Observed 2026-08-17 on a Codex `/hm:execute` that exhausted the two-round A.5 budget, reported
two test blockers, and stopped — leaving a defect list that a lens-level rewrite had already
failed twice to fix, which is precisely the situation "name the ONE binding constraint" exists
for.

**Compaction first**, per the bar every entry above this one in `_ATOMIC_RATCHET` sets. The first
draft was +1 630 of prose; moving the rationale into this document cut it to +1 136.

**The remaining +605 is what two review rounds put back, and none of it is prose.** Six defects,
each raised by an independent lens and none fixable without text in the rendered file:

- **`stuck` has no Write tool.** Its `tools:` line is `Read, Grep, Glob`, which per CLAUDE.md is
  the one subagent boundary Claude Code actually enforces. The original brief ended "Write the
  escalation note and return its path" and the surface step printed that path — so every Claude
  Code blocker run would have reported a path to a file that was never created. Four lenses
  raised it independently. The note is now returned inline, and `stuck_body.md.j2` Step 5 was
  corrected too: its instruction to write `.claude/memory/escalations/…` had been dead the whole
  time the agent had no dispatcher, and nothing in this repo has ever read that directory.
- **The dispatch rendered unconditionally.** `dispatch_intro()` and the fenced call sat *after*
  the blocker bullets with nothing restating the condition, so a run that exited Step 4 GREEN
  read an unqualified "Dispatch each item below" imperative. The blocked path is now four
  numbered steps under an explicit "blocked path ONLY" sentence.
- **The failure output could be withheld.** The only degrade clause was "Skip only if it dies",
  which defines neither what dying is nor what to surface instead — and on Codex the join
  contract says an agent that has not answered is *not* an agent that failed. A blocked run could
  wait indefinitely on the escalation while holding back the output the user needs. There is now
  an explicit `[stuck] unavailable` branch that surfaces the failure output alone. Round 2 added
  its fourth arm — *has not answered after the first collect step* — because the other three
  ("errors, refuses, returns no note") are exactly the conditions the join contract says a hang
  does not satisfy, so without it the branch could not fire on the case it was written for.
- **The scope qualifier named the wrong referent.** "Everything under this heading" pointed at
  `### Step 4`, which also spans the GREEN exit items; it now says "the four steps below".
- **The human docs still described the removed file write.** `docs/HOW-IT-WORKS{,.ko}.md` had
  `stuck` saving to `.claude/memory/escalations/` in three places each, including a directory
  node in the memory-layout tree.
- **The brief interpolates repo-controlled text.** Test stderr, ADR bodies and reviewer verdicts
  go into a sub-agent prompt whose reply is surfaced to the user as the recommended move, with
  none of the untrusted-data framing every sibling dispatch in this repo uses. It now carries the
  same clause `wrapup.md.j2` uses for `judgment-reviewer`.

**The residue is the dispatch itself plus the four facts `stuck` Step 1 lists as required and
cannot reconstruct from the PLAN alone**: WHICH of the three triggers fired (it routes Step 2's
search for the binding constraint), the merged verdict of BOTH A.5 rounds, the verbatim
lint/type/test stderr, and the ADR text with the move it forbids.

## 4. Cost shape

The round-trip is **off the happy path** — and after the fix above, that is now true of the
rendered text and not only of the intent. It fires only when a phase has already stopped, so a
run that completes GREEN pays nothing. That is the opposite shape from the `+1` in `plan`'s table
(a call on every run), and it is why one added call is acceptable here without a compensating
removal.

## 5. Gate

`tests/structural/test_stuck_dispatched_on_blocker.py` pins the dispatch **site** inside the
blocker region and ahead of the surface instruction, across the three rendered documents that
carry the blocker path (two target variants — `.cursor/commands/` is dead code, so Cursor reads
the claude file).

The order assertion measures `_DISPATCH_STUCK`'s own offset. Its first draft compared the
*bullet* that promises a dispatch against the surface bullet, and was green on a template whose
actual fenced call sat six lines BELOW the surface instruction — the exact configuration the
gate's docstring says it rejects. A proxy for the subject is not the subject.

An earlier version of this section claimed the gate avoids token checks because "a token check
would have been green through the whole period this defect shipped". **That was false and is
withdrawn**: the rendered `execute.md` at `ea8087ff` contains the string `stuck` zero times, so a
plain `assert "stuck" in body` would have been red. The real reason for locus-and-order
assertions is narrower and still holds — a bare token cannot show that the dispatch is *inside*
the blocker region and *ahead of* the surface step, which is the property that distinguishes this
fix from a mention of the agent's name.
