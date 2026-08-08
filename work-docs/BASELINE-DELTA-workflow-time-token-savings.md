---
type: baseline-delta
task_slug: workflow-time-token-savings
phase: A1
created: 2026-08-08
owns: [surface_baseline.json]
summary: "Every size baseline this PLAN moves, attributed to the phase that moved it"
---

# Baseline delta — PLAN-workflow-time-token-savings

## 0. The pre-PLAN literal (recorded by Phase A1, read by A3 and B5)

`aggregate_chars` in `tests/structural/surface_baseline.json`, as committed **before any phase
of this PLAN landed**:

| key | pre-A1 value |
|---|---|
| `aggregate_chars.claude` | **366439** |
| `aggregate_chars.codex` | **299602** |

**Why this is written down rather than derived.** ADR-008.3. The net-surface assertion belongs
to Phase B5, which runs after four phases have each legitimately moved the baseline. Asking B5
to reconstruct the starting value means `git show <A1^>:tests/structural/surface_baseline.json`
in a repo where phases land as squashes — the executor would first have to identify which commit
was A1. Recording the integer here makes the comparison a literal lookup, and makes a wrong
comparison visible in review rather than silent.

**B5 asserts `aggregate_chars.claude <= 366439`** and must be able to fail. If the PLAN ends
net-positive, the only permitted escape is an explicit `xfail` with a waiver referencing the
closing row in §3 — never a re-freeze (`ratchet-rebaselined-by-its-own-subject`, count:2).

## 1. Per-phase rows

`tests/structural/test_baseline_delta_attribution.py` fails if a changed key in
`surface_baseline.json` has no row here, so a silent rebaseline fails **mechanically** rather
than by anyone noticing.

| phase | key | before | after | Δ | why |
|---|---|---|---|---|---|
| A1 | — | — | — | 0 | A1 touches no template; it records the literal above only. |
| A3 | `aggregate_chars.claude` | 366439 | 366088 | **−351** | ledger rationale prose retired |
| A3 | `aggregate_chars.codex` | 299602 | 299251 | **−351** | same block, both variants |

**A3, in detail.** Phase A2's verdict token is **`ledger-trustworthy: yes`**, so A3 took the
"question answered" branch. What was deleted is the *rationale* — the two paragraphs telling the
model why the ledger exists ("~34 lifetime dispatches and **zero** ledger rows, so 'does the
second pass ever change the verdict?' … has no data behind it"; "~42 lifetime dispatches … the
question 'is A.5 worth its barrier?' currently has no data at all"). Both questions now have
answers, so the prose is arguing for a decision already made. Every operational instruction
stayed: the emit command, the `--terminal` rule, the sentinel verdicts, the quote-stripping
warning, the `--duration-ms` "omit rather than zero" rule.

**The emit invocations survive, and that is the load-bearing part of this phase.** Deleting them
alongside the prose would have satisfied a "surface decreased" criterion *more* easily while
making both keep-verdicts permanently unfalsifiable. Verified: `grep -c 'stage_agent_ledger emit'`
is 2 in each of `templates/stages/{plan,execute}.md.j2` (the Codex and Claude branches) and 1 in
each rendered command.

**The frozen baseline is deliberately NOT re-frozen here.** `test_surface_baseline` asserts
`now <= was`, so a shrink passes against the old value and nothing is owed. Re-freezing at A3
would also destroy the anchor B5 needs: §0's literal is the pre-PLAN number, and B5's job is to
assert the **net** across every phase, including the growth B3/B4 will add. A3 measured its own
delta and recorded it; B5 owns the freeze decision.

**The keep-verdict this phase records.** Both pre-registered aggregations, evaluated on the
ledger A2 certified:

| step | rule | result | verdict |
|---|---|---|---|
| second `plan-validator` pass | `P(verdict changes \| a later pass ran)` | **2/9 = 22.2%** | **KEEP** |
| Phase A.5 `test-reviewer` gate | `P(FAIL)` | **9/24 = 37.5%** | **KEEP** |

Neither is the low ratio that ADR-004 of PLAN-workflow-loop-efficiency pre-registered as the
evidence for deletion. Both populations are **Side-preset only** (A2's caveat) — Production is
absent because spoton has not run a gated stage since the emit was rendered there, not because
of a defect. This must not be described as a cross-preset result.

*(B3, B4 and B5 append their rows as they land. Phase A5 — the ADR-011 instrumentation axis —
is not started; when it lands it will remove considerably more than A3 did, because it deletes
the emit blocks entirely on the off path rather than trimming their rationale.)*

## 2. Stage-1's outstanding debt

`BASELINE-DELTA-P7.md` §1 records that PLAN-workflow-loop-efficiency grew
`aggregate_chars.claude` by **+7,113** on an explicit condition — *"only pays for itself if
stage 2 actually reads those ledgers and deletes something."* This PLAN is stage 2. Phase A3
settles that debt on **both** branches of Phase A2's `ledger-trustworthy` token:

- `yes` → the prose whose question is now answered is retired, and the keep-verdict for the
  second validator pass and the Phase A.5 gate is recorded with its denominator.
- `no` → the prose is still retired (instrumentation that produced untrustworthy data is not
  worth its surface), and A3's row records the withdrawal of both rates plus the follow-up that
  owns re-instrumenting.

Neither branch may close with the debt unrecorded.

## 3. Closing row (Phase B5)

*(B5 appends the net figure here, with its cause attributed to the phases that moved it.)*
