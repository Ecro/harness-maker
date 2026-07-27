---
type: review
task_slug: token-economy-step-pruning
phase: 4
reviewed_at: 2026-07-27
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: token-economy-step-pruning
  computed_at: 2026-07-27
---

# REVIEW — Phase 4: fused-command compaction

## What landed

The shared prose of three blocks is hoisted into a per-workflow preamble rendered once
by `workflow_fuse.fuse()`. What stays at each stage is what is *addressed to that stage*:
the heading, the pass/fail criteria, the guard's own variant tails, and — critically —
the `--stage <stage>` invocations, which are the Gate-0 missing-stage mechanism, not
redundancy (ADR-016, risk R10).

| command | pre | post | Δ |
|---|---:|---:|---:|
| `exec-rev-wrap-ver` | 123,397 | 118,960 | −4,437 |
| `exec-rev-wrap` | 109,218 | 106,540 | −2,678 |
| `plan-exec-rev` | 108,923 | 106,246 | −2,677 |
| `res-spec-plan` | 89,067 | 86,391 | −2,676 |
| `exec-rev` | 68,410 | 67,492 | −918 |

All 7 atomic commands re-render **byte-identically** — verified by diff against a
pre-change render, not asserted. They are AC-007's differential control, so the entire
change had to land inside two partials plus a new preamble; no stage template was edited.

## Findings

### F1 — the ceiling was already stale when this phase started (recorded, not fixed)

ADR-014 derived `≤ 119,000` from a render taken before any phase of this plan landed.
Phase 3 then added ~1,615 chars to the same command. The natural, fully-classified hoist
lands at **118,960 — a 40-character margin**, which is not a budget. Re-applying ADR-014's
own rule to the current artifact gives ≈120,045.

**Not fixed here on purpose.** A phase that discovers its own gate is mis-set should not
also be the phase that resets it. [ADR-019](PLAN-token-economy-step-pruning.md#adr-019)
records the recommended value; the test's docstring says the same thing at the point of
failure, which is where the next person will read it.

**What the margin did NOT come from:** no shipped instruction was shortened. Every trim
taken to reach it was inside the preamble this phase authored — a duplicated example
command that all four stages already show, and a wordier back-reference.

### F2 — ADR-016's discipline had not been applied to every block

The ADR's own consequence note says classifying "the blocks I am currently measuring" is
not the rule. Enumerating **all 11** repeated paragraphs (6,600 redundant chars) surfaced
two it never named — recorded as [ADR-020](PLAN-token-economy-step-pruning.md#adr-020):

- the stage-summary skip rule (4 × 286, fully uniform) → **hoisted**;
- the Phase-3 reviewer read budget (2 × 1,181) → **must not be hoisted**. It is the
  single largest repeat in the document and the most obvious compaction target, and
  hoisting it is precisely how risk R2 says this phase silently regresses Phase 3.
  AC-008 asserts it *at every dispatch site*. Large-and-identical is not the test;
  addressed-to-one-site is.

### F3 — ADR-016's own numbers were off, and one was measured in the wrong unit

Preflight identical prose 1,241 (not 1,243); Gate 0 657 line-aligned (not 659);
Communication Protocol 28 shared (not 40). More substantively, the line-aligned figure is
the **wrong unit** for Gate 0: several of its "identical" lines sit *inside the runnable
fenced command*, and you cannot hoist three of a fence's four lines. Classifying by
semantic unit is what ADR-016 actually asks for; doing it by line-diff overstates what is
available and would have produced a broken fence.

### F4 — `tests/structural/` had no install-ref pin (instance 14 of a 13-instance ledger entry)

AC-005 freezes character counts as constants. Unpinned, `harness_maker_src_path` bakes the
running checkout's absolute path into the render dozens of times, so every number in the
ratchet would have been a measurement of *this machine*. `tests/structural/` inherited the
pin from none of its three existing owners — the same shape as Phase 3's P0, one directory
over. Caught **before** capture this time, by checking rather than by generalising.

Two things were added rather than one: the autouse fixture, and `pin_install_ref()` as a
plain function — because the render fixtures here are **module-scoped**, and a module-scoped
fixture is set up *before* any function-scoped autouse fixture, so the autouse pin is not in
effect while it renders. A pin the render path cannot reach is how the last one got in.
`test_no_rendered_command_bakes_a_machine_specific_absolute_path` gates the property.

### F5 — three real gate gaps, all found by the mutation receipt, none by review

The first receipt run: 10 mutants, **3 survivors + 1 stale anchor**. Every survivor was a
genuine hole in tests that were passing:

- **M8** — the banner skip rule could be deleted from the preamble entirely while the
  stages no longer carried it. AC-006 fingerprinted only preflight and Gate 0, so the
  third hoisted block had no gate at all. Fixed by a third fingerprint, chosen as the
  clause the preamble and the atomic block share *verbatim* (they word the rule
  differently, so a wording fingerprint would have matched neither).
- **M10** — an atomic render could lose its whole preflight tail (the `<WT>` rule, the
  drift remedy, the `task-refresh` command) with everything green: AC-005 measures only
  fused commands, and the atomic check fingerprinted the intro sentence alone. Fixed with
  explicit tail markers over all seven atomic commands.
- **M6** — *not* a gate gap but a defective mutant: the anchor matched the **Codex** branch,
  which no Claude-Code render emits, so it mutated a line that never reaches the output. A
  mutant that does not reach the render measures the mutation script, not the gate. Re-aimed
  at the bash branch, it is killed.

Second run: **10 / 10 killed, 0 survivors, 0 anchor errors.**

### F6 — two self-inflicted defects during implementation, both caught by measurement

- A Jinja comment added beside a conditional contributed its own trailing newline to the
  output. That moved **every atomic render and every snapshot hash** — 19–20 entries per
  fixture instead of the expected 5–6. Trimming it with `-#}` then ate the blank line after
  the heading instead. The comment now lives in the file header where its newline is inert.
  Caught by auditing *which* snapshot entries changed rather than accepting that some did.
- That same comment contained a literal `#}` inside its prose, which terminated the comment
  early and broke the render.

Neither was caught by reading the diff.

## Grade

**A.** The exit criterion is met on every arm: AC-005/006/007 green including the flag-off
arm and both negative controls; all four `--stage` values survive in both flag states;
Phase 3's AC-008/AC-009 guards green; 10/10 mutants killed; full suite `rc=0`; ruff, ruff
format, and `mypy --strict` clean.

**Caveat on that grade, stated because it is load-bearing:** this review is single-voter.
Every finding above is mine about my own work, so the consensus filter marks all of it
`manual-only` by construction. The three findings that mattered most (F5) came from
*measurement*, not from reading — which is the same pattern as Phases 2 and 3, and the
reason the mutation receipt is a required step rather than a nice-to-have.

## Follow-ups (not in this phase)

1. Re-derive ADR-014's ceiling to ≈120,045 against a current measurement (F1).
2. Phase 5 — wire `unattributed_breakdown` into `/hm:metrics` Step 5d. It re-renders
   `commands/hm/metrics.md`, which this phase does not touch, so it is now unblocked.
3. The fixed-cost preamble means a 2-stage workflow gains almost nothing (−918 on
   `exec-rev` vs −4,437 on the 4-stage). Worth stating in user-facing docs: **fusing more
   stages is what makes this pay.**
