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
| B3 | `aggregate_chars.claude` | 366088 | 367496 | **+1408** | judgment-gate branch in the shared `stage_end_summary` partial + the split review/plan gate strings |
| B3 | `aggregate_chars.codex` | 299251 | 299245 | **−6** | same edits; the codex skills inline a shorter form |
| B4 | — | — | — | 0 on THIS repo | the `ask-pending` picker branch and the skipped-smoke note render only when `autonomy.level == "ask"`; this repo commits `auto_safe` |

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

### Phase A5 — the `instrumentation` axis (ADR-011)

| Variant | `stage_agent_ledger: true` | `stage_agent_ledger: false` | Saved by OFF |
|---|---|---|---|
| `claude` commands | 347,327 | 340,089 | **−7,238** |
| `codex` skills | 340,718 | 333,471 | **−7,247** |

**Which of those two is the "default" depends on which question you are asking, and ADR-011
answers them differently on purpose.** A **freshly rendered** harness gets `false` — a
third-party install should not carry prose whose consumer is this repo. An **existing**
harness.yaml with no `instrumentation` key resolves to `true` — those predate the key and are
the fleet already producing rows, and a re-render must not silently stop them.

`aggregate_chars` in `surface_baseline.json` is measured from the default fixture, so it drops
by the figures above once that fixture is a fresh render. The saving is real for every new
install and zero for the four projects already contributing — which is exactly the split the
axis was created to make.

The figure is also larger than A3's −351 by a factor of twenty, for the reason A3 predicted:
A3 could only trim rationale from a block that had to stay, while A5 removes the block.

### Phases B3 + B4 — the judgment gate and the `ask` picker

Both ADD surface, and both are net-positive on purpose: B3 renders a judgment branch into the two
stages that own one, and B4 renders an `ask-pending` picker branch plus a skipped-smoke note. The
`surface_baseline.json` ratchet (`now <= was`) is what will report the exact figure when the
closing row is taken; the phases are recorded here so the closing number is attributable rather
than a mystery.

Set against them, A3 (−351) and A5 (−7,238 conditional) are the only reductions this PLAN makes
to the default render. **A default-render decrease is therefore not expected**, and B5's
assertion should be read with that in mind rather than as a target to be met by trimming
something else at the last minute.

*(B5 appends the measured net figure below.)*

### The re-freeze, and why it is not the failure class it resembles

`surface_baseline.json` was regenerated at base SHA `bdaa0ae0` (the task branch carries no
commits, so the durability check passes and the frozen SHA is one that survives the squash).
The mechanical fields moved with it: `payload_digest` and `render_sha` (both derived from the
render, not chosen), `frozen_at_sha`, and the per-command `chars` / `round_trips` entries.

**This is the shape of `[fail:test] ratchet-rebaselined-by-its-own-subject` (count:2), so the
difference has to be stated rather than assumed.** That failure is a ratchet re-frozen *to make
a change pass*, hiding the growth. Here the growth is measured (+1,408 claude), attributed to
the phase that caused it (B3), and — the part that makes it not the failure class — **the
PLAN-level assertion is NOT re-based**. `tests/structural/test_plan_net_surface.py` compares the
new frozen value against §0's pre-PLAN literal, which this document fixes and which no
regeneration touches. That test is `xfail` with the waiver below, so the net stays red and
visible in CI for as long as the PLAN is net-positive. Re-freezing restores day-to-day
ratcheting; it does not settle this PLAN's own account.

Per-command, so no row hides inside the aggregate:

| command | before | after | Δ | cause |
|---|---|---|---|---|
| `plan` (claude) | 50737 | 51189 | **+452** | B3's judgment branch + the rewritten gate string; A3's −351 is already inside this figure |
| `review` (claude) | 52283 | 53063 | **+780** | B3's judgment branch + ADR-010's split gate string (two predicates, stated separately) |
| `execute` (claude) | 34533 | 34398 | **−135** | A3's retired ledger rationale, with no judgment branch to offset it |
| `health` (claude) | 9816 | 9772 | **−44** | B4's `ask` branch is shorter than the smoke section it replaces — but this repo commits `auto_safe`, so what shrank is shared prose |
| `research` / `spec` / `verify` / `wrapup` (claude) | — | — | **+1 each** | whitespace from the `{% if judgment_stage %}` discriminator in the shared partial; these four own no judgment gate |
| `hm-plan` (codex) | 46261 | 46044 | **−217** | same edits, shorter codex phrasing |
| `hm-execute` (codex) | 31647 | 31511 | **−136** | A3 |
| `hm-review` (codex) | 47922 | 47918 | **−4** | A3 minus B3 |

ADR-010 of PLAN-workflow-step-audit owns this file's re-freeze rule; this section is the
attribution it requires.

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

### Review round 2 — the P0 fixes cost surface, and that is the right trade

| key | before | after | Δ | why |
|---|---|---|---|---|
| `aggregate_chars.claude` | 367496 | 368766 | **+1270** | the third gate value `blocked` (ADR-010's hard half moved from prose into an enforceable flag), the append-instruction that replaced a bracketed placeholder inside a shell command, and the stale-render diagnostic in the halt reason |
| `aggregate_chars.codex` | 299245 | 299245 | 0 | the codex skills inline the same partial and net out |
| `configure` (claude) | — | — | grew | `/hm:configure` offered `gated / auto_safe / full` and asserted that the plan interview "always stops regardless" — the level list was stale and the safety claim is false at `auto_full`. Both reviewers and the codex voter flagged it independently. |

Two P0s came out of `/hm:review`, both reproduced by direct execution before any fix:
`auto_full` advanced past a CHANGES_REQUESTED review (the separation between a quality
threshold and a judgment existed only in a template sentence), and a `gated` marker
auto-advanced (`boundary` never read the level; B4's picker made that reachable). **Both are
now enforced in Python.** The prose that replaced them is longer than the prose that failed,
and that is the correct direction: Interview #5 of ADR-009 rejected prose-only enforcement
precisely because a grep-asserted control passes while the behaviour is absent.

### Review round 3 — the fix's own fix

| key | before | after | Δ | why |
|---|---|---|---|---|
| `aggregate_chars.claude` | 368766 | 369899 | **+1133** | absence made distinct from `pending` (a sentinel default plus its own diagnostic), `blocked` honoured on every stage, plan's gate string given the threshold half it lacked, and the "unsure →" tiebreak moved from the clearable value to the safe one |

Round 2's own fix had a P0 in it, and **both round-2 reviewers found it independently**: the
flag still defaulted to `pending`, so an OMITTED verdict at `auto_full` was auto-answered —
reopening the round-1 hole at the one level where it matters, with the stale-render diagnostic
sitting in a branch `auto_full` could never reach. `pending` is now a claim the caller makes;
absence is the caller saying nothing, and it halts everywhere.

The round's own re-review then found four more, one of them the contradicting sentence in the
block that builds the command ("omitting it reads as `pending`" — the opposite of what the code
now does, placed where the model reads it last). Those are included in the figure above.

### Review round 4 — the round the user asked for, and it was not empty

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 369899 | 371066 | **+1167** |
| `aggregate_chars.codex` | 299245 | 300082 | **+837** |

The config cap (`max_review_rounds: 3`) was spent after round 3, and round 3's fix was
therefore the only one never re-reviewed — in a layer that had broken on **every** previous
fix. The user asked for one more round rather than landing on that. It found seven more,
including two the code could not have caught:

- `review.md.j2`'s `CHANGES_REQUESTED` bullet still said "proceed to wrapup". Nothing in code
  can tell a failed grade from a passing one — the boundary acts only on the value the model
  types — so that sentence was a live route back to the round-1 P0.
- `plan.md.j2`'s new `blocked` predicate keyed on the immutable fact "the second pass returned
  MAJOR_REVISION", which stays true after the user explicitly accepts the risk. The halt would
  have been permanent and its own prescribed remedy impossible.
- `ruff format --check` would have failed CI on a line added in round 3. `ruff check` passes on
  it; only the formatter gate catches it, and it had not been run.

**Net: `claude` +4627 (366439 → 371066); `codex` +480 (299602 → 300082).** The `codex` variant
crosses from negative to positive here — the PLAN is now net-positive on **both** surfaces, and
the closing figure should not be read as if one of them still paid for the other.

`tests/structural/test_plan_net_surface.py` carries the ADR-008.4 waiver as an `xfail`, so the
overrun stays red in every CI run rather than being absorbed into a re-frozen number. It is
`strict=False` because the `codex` variant genuinely passes and an XPASS there must not be
reported as a failure.

Attribution, largest first: **B3 +1,408** (the judgment-gate branch in the shared
`stage_end_summary` partial, plus ADR-010's split review gate — the two predicates have to be
stated separately or Step 1 cannot treat them differently), **A3 −351**, **B4 0 on this repo**
(its branches render only under `level: ask`; this repo commits `auto_safe`), **A5 0 on this
repo** (the axis is ON here — this repo *is* the cross-project denominator).

**The honest summary is that the two audiences net out differently, and the PLAN should be
judged on both.** A third-party install renders with the instrumentation axis OFF and nets
roughly **−6,200**: it stops carrying prose whose only consumer is this repository. The
maintainer's own harness pays **+1,057** to keep collecting the data that made this PLAN's
keep-verdict correct in the first place. Reporting only the first number would be marketing;
reporting only the second would suggest a cost-reduction PLAN that raised costs for everyone.

Stage 1's +7,113 debt (§2) is therefore **paid for third-party installs and not paid here**.
A follow-up that wants to close it on this repo has to find the reduction in the shared
partials, not in the instrumentation the ledger verdict depends on.
