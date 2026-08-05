---
type: research
task_slug: workflow-loop-efficiency
status: complete
created: 2026-08-05
tags: [harness-maker, research, token-economics, workflow-design, review-pipeline, autonomy]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
related_docs:
  - "[[fail:test fix-introduced-defect-passes-all-gates]]"
  - "[[wiki:architecture harness-diet-fused-axis-removal]]"
  - "[[wiki:gotcha loop-body-skipping-review-stage]]"
  - "[[PLAN-harness-diet]]"
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
summary: "Loops are 23% of spend and already bounded; 73% is context carry. Cut per-round cost + fix-introduced defects, not rounds."
---

# RESEARCH — workflow loop efficiency

## 🎯 Recommended Direction

**Do not attack the loops. Attack the cost of one pass through them, and attack the
defect class that makes a second pass necessary.**

The two loops named in the request — `plan→validator→re-plan→re-validator` and
`execute→review→fix→review` — are both already bounded (validator: hard cap of 2
passes, stated in the template; review: 92% of 41 reviews converged within 2 rounds,
max observed 3). Together their measured cost is **≈23% of total spend**. The other
77% is not loop iteration at all: **73% of every dollar this project has spent is
`cache_read` — re-reading context that already exists — not `work`.** Cost is
`turns × context_size`, and the loops move `turns` by less than the request assumes.

The direction with the best evidence-to-risk ratio is a four-part cut, in this order:
(1) restore subagent model tiering, which is currently bypassed on 179 of 188
dispatches; (2) delete the two review sub-steps whose measured yield is ~2–3% and
which Anthropic's Opus 5 guidance names explicitly as scaffolding to remove;
(3) instrument `plan→validator` and `execute` Phase A.5, which today have **zero**
telemetry and therefore cannot be cut responsibly; (4) add the one missing *step* that
targets fix-introduced defects — the count:4 failure class that is the actual engine of
multi-round convergence.

The impact is mostly **maintainer-internal** (cost and wall-clock), not user-facing.

## 🔍 Refinement Decisions

Discovery lens: **technical architecture** (exhaustive step inventory of all 7 stage
templates) + **measured telemetry** (this project's own economics/observability ledgers)
+ **risk** (what leaks a P0 if cut). Academic/benchmark lens deliberately not used as a
primary source — this project has 41 reviews and 13,951 priced turns of first-party
data, which beats any external benchmark for this question.

`--deep` was not set; no Phase 0 interview ran.

## 📊 Measured baseline (all first-party, `harness_maker.economics` + `.claude/observability/`)

| Quantity | Value |
|---|---|
| Total priced spend | **$3,174** over 13,951 turns |
| `work_usd` / `cache_read_usd` | **$855 (27%) / $2,317 (73%)** |
| Global carry ratio | 0.73 |
| **All subagents combined** | **$428 = 13.5%** of total |
| Main loop | 86.5% |
| Wall-clock main / subagent | 81.5 h / 16.0 h |

Per stage (main-loop turns; `carry` = fraction of that stage's cost that is re-read):

| Stage | USD | % | turns | carry | mean ctx | dominant category |
|---|---|---|---|---|---|---|
| `hm:execute` | 756 | 23.8% | 3373 | 0.78 | 357k | OTHER 64% |
| *(unattributed)* | 738 | 23.3% | 3378 | 0.73 | 323k | OTHER 73% |
| `hm:review` | 687 | 21.6% | 2791 | 0.71 | 354k | **VERIFY 55%** |
| `hm:wrapup` | 494 | 15.6% | 1957 | **0.84** | **425k** | OTHER 77% |
| `hm:plan` | 354 | 11.1% | 1676 | 0.59 | — | VERIFY 26% |
| `hm:research` | 46 | 1.4% | 314 | 0.45 | — | — |
| `hm:spec` | 15 | 0.5% | 72 | — | — | — |
| `hm:verify` | 11 | 0.3% | 54 | — | — | — |

Per subagent:

| Agent | USD | % of agent spend | turns |
|---|---|---|---|
| code-reviewer | 138.7 | 32.4% | 1081 |
| **plan-validator** | 70.0 | 16.4% | 460 |
| security-reviewer | 69.8 | 16.3% | 524 |
| test-reviewer | 61.2 | 14.3% | 361 |
| general-purpose | 46.3 | 10.8% | 460 |
| stage-delegate | 34.5 | 8.1% | 359 |
| **code-verifier** | **1.2** | **0.3%** | **8** |

Context composition (29.08M chars):
`tool_call_input` 39.4% · `tool_result` 30.0% · **`slash-command-body` 15.3%** ·
`task-notification` 6.5% · `assistant_text` 5.3%.
Within `tool_call_input`: Edit 30.5%, Write 29.6%, Bash 29.1%, **Agent (Task prompts)
only 6.2%** (avg 3.7 KB — reviewers fetch the diff themselves rather than having it
pasted in; that part is already efficient). `write_after_read` duplicate share 26.5%.

Review funnel, 41 invocations / 66 rounds, non-fixture:

| Gate | In | Out | Dropped |
|---|---|---|---|
| Pass 1 (reviewers, redacted) | — | 355 | — |
| **Pass 1.5 `code-verifier`** | 261 | 256 | **5 (1.9%)** |
| **Pass 2 (full metadata)** | 355 | 344 | **11 (3.1%)** |
| Consensus filter | 344 | 45 | 299 (87%) |

Round distribution: **19 slugs at 1 round, 19 at 2, 3 at 3.** 25 of 66 rounds (38%)
are re-reviews. `auto_fix_reverted_n` 2, `build_break_count` 11,
`verifier_false_drop_n` 0, `verifier_false_keep_n` 0.

`plan→validator`: **no telemetry exists.** Not one row anywhere. The template
(`plan.md.j2:554`) caps it at two passes and then escalates A/B to the user.

Delegation ledger: **12 rows, all `wrapup`** — 7 briefs, 3 `dispatched`, **2
`mismatch`**. `hm:verify` delegation has never fired.

## ⏱️ Correction — the dollar lens hid the latency problem

*Added 2026-08-05 after user pushback, before any implementation.*

The request said "**시간및** 토큰이 엄청 소모됨" — time **and** tokens. Everything above is
denominated in dollars, and the headline conclusion ("all subagents are 13.5% of spend")
is *true* and *actively misleading* about wall-clock. Two different problems with two
different answers:

| Axis | Dominated by | Fix |
|---|---|---|
| **Cost** | context carry — 73% of spend is `cache_read` | fewer main-loop turns, smaller carried context |
| **Wall-clock** | **serialization barriers** + full-suite runs | fewer serial segments, narrower full-suite triggers |

A review round is **five serial segments**, each a barrier that waits for every dispatch in
it: `Pass 1 → Pass 1.5 → Pass 2 → cross-model → PIDA`. So **Pass 1.5 costs $1.2 in its
entire lifetime and adds one full serialized agent round-trip to every round.** The dollar
figure argues for leaving it; the latency figure argues for removing it, and the latency
figure is the one matching the complaint. The same inversion applies to the
`plan-validator` second pass (measured at **4.2 min** in this session, on top of a 6.1 min
first pass) and to the Phase D full suite (~6 min, once per phase).

Measured wall-clock: **subagents are 16.1 h of 98.4 h (16.4%)** cumulative — but cumulative
agent-seconds is the wrong statistic, because agents inside one barrier run concurrently
while the barriers themselves do not.

**A telemetry gap this exposed:** per-invocation agent latency is **not recoverable from the
transcripts at all**. Dispatch is asynchronous, so the tool result returns immediately and
the real duration arrives out of band. The harness has *zero* data on the axis the user
experiences first. That is why `duration_ms` and `barrier_index` were added to ADR-004's
row schema.

**New open question (not adjudicated here):** the Phase D full-suite trigger. Eight phases ×
~6 min is ~48 minutes of pytest, and `test_dep_map`'s `mode: full` fires for
`pyproject.toml` / `uv.lock` / CI / `harness.yaml` changes. Narrowing it trades regression
attribution for time — on a task with frequent fix-introduced defects that is the worst
place to economise, so it needs its own evidence.

## 🛠️ Approaches Found

### Approach A — Cut the loop iterations (the request's own hypothesis)

| Field | Content |
|---|---|
| Approach | Cap review at 1 round; drop the validator's second pass |
| Assumption | Repeat rounds are where the tokens go |
| Evidence | **Contradicted.** review VERIFY ≈ 55% × $687 ≈ $378; plan VERIFY ≈ 26% × $354 ≈ $92; all-stage REWORK $262. Loops ≈ **$470–730 = 15–23%** of $3,174. Both loops are *already* capped. |
| Trade-off | Round 2 exists because round 1's fixes broke something: `[fail:test] fix-introduced-defect-passes-all-gates` count:4, most recently **14 findings of which 11 were defects this task's own fixes introduced**, every one on a green four-gate run. Capping at 1 round ships those. |
| Compatibility | Trivial (config already has `max_review_rounds`) |
| Risk | **high** |

### Approach B — Cut per-round cost: tiering + the two low-yield review sub-steps ✅ recommended

| Field | Content |
|---|---|
| Approach | (B1) stop forcing `model: "opus"` on every subagent dispatch; (B2) delete Pass 1.5 `code-verifier`; (B3) re-run the Pass 2 ablation and delete Pass 2 if it does not reproduce |
| Assumption | Detection is a property of the reviewer set, not of how many times each reviewer runs |
| Evidence | **B1:** 179 of 188 measured dispatches passed `model: "opus"` explicitly, overriding every reviewer's `model: sonnet` frontmatter — the harness's only cost-tiering lever is bypassed 100% of the time, per the workaround in `[[feedback_subagent_model_override]]`. **B2:** `code-verifier` dropped 5 findings ever (1.9%), cost $1.2 total, and is by construction "a subagent to verify" — Anthropic's Opus 5 guide: *"do not use subagents to verify or double-check your own work"*, and its review section reports Opus 5's *"additional findings are mostly real issues rather than false positives"*, which is exactly a 1.9% drop rate. **B3:** Pass 2 drops 3.1% but **doubles every reviewer invocation**; its justification is a Phase-0 ablation claiming "+47pp precision on anchoring-prone diffs" that has never been re-run against a current model. |
| Trade-off | B2 removes a serialization barrier as well as a step (Pass 1 → 1.5 → 2 is strictly sequential). B3 halves reviewer count per round — the single largest structural cut available. B1's ceiling is bounded: subagents are only 13.5% of spend. |
| Compatibility | B1 needs the launch-failure root cause fixed first, or it regresses to "validator fails to launch". B2/B3 are template edits + a ratchet update. |
| Risk | B1 **low**, B2 **low**, B3 **medium until the ablation is re-run** |

### Approach C — Attack fix-introduced defects, the actual engine of round 2 ✅ recommended alongside B

| Field | Content |
|---|---|
| Approach | Make the memory's own remedy a numbered step in `execute` Phase C/D rather than a lesson in `failures.md` |
| Assumption | Round 2 is caused by round 1's repairs, not by round 1's incompleteness |
| Evidence | count:4 with the ratios recorded: 11/22, then **7/7**, then 5, then 11/14. In the 7/7 instance all four gates *and* a 7-mutant/7-killed mutation check were green between the rounds. The memory already states the fix: *(a) after a repair, name the input window the repair newly makes reachable and assert a fixture enters it, in the same commit; (b) when a third consecutive round finds defects in the same mechanism, treat the mechanism's EXISTENCE as the finding.* **Neither is a step in any stage template today.** |
| Trade-off | Adds a step to `execute` in order to remove rounds from `review` — the trade is favorable only if it actually lands: 25 re-review rounds ≈ 38% of review spend ≈ $260 historical. |
| Compatibility | Fits Phase D, which already runs post-GREEN verification |
| Risk | **low** — it is additive and cannot leak a P0 |

### Approach D — Cut context, not steps

| Field | Content |
|---|---|
| Approach | Shrink `CLAUDE.md` (62 KB, loaded every turn, already over the 500-line Production lint limit) and the four ≥48 KB stage bodies (`loop` 53 KB, `review` 52 KB, `plan` 49 KB, `wrapup` 48 KB) |
| Assumption | Prompt surface is a meaningful share of carry |
| Evidence | `slash-command-body` is **15.3% of all context chars** (4.46 MB). But per turn the fixed harness overhead is ~30k of a ~375k mean context ≈ **8%**, so halving it saves ~4% of total. The 0.47.0 diet cut 45.3% of *shipped* surface and saved approximately nothing at runtime, because the deleted fused commands had **zero** invocations. |
| Trade-off | Real but modest; the honest ceiling is single-digit percent |
| Compatibility | High |
| Risk | **low**, **low reward** |

### Approach E — Fix or delete `wrapup` delegation

| Field | Content |
|---|---|
| Approach | `wrapup` is 15.6% of spend at the **worst carry (0.84) and largest mean context (425k)** — bookkeeping running at maximum context, ~49 turns per invocation. Step 0.5 exists precisely to cut this. |
| Assumption | The delegate reduces main-loop carry |
| Evidence | It has dispatched **3 times** with **2 `mismatch` verdicts** — a 40% rate at which the delegate claimed work not on disk and the main loop had to redo it, paying twice. `hm:verify` delegation has never fired at all. |
| Trade-off | Either raise the dispatch rate and fix the mismatch cause, or delete the mechanism per remedy (b) of the count:4 note |
| Compatibility | Self-contained |
| Risk | **medium** — a mechanism with a 40% failure rate and 5 lifetime uses is a candidate for deletion, not repair |

## 📋 Full step inventory — verdict per step

65 named steps across 7 stages (`wrapup` 753 lines, `plan` 665, `review` 659, `execute`
473, `verify` 433, `spec` 410, `research` 334). Verdicts: **KEEP** (state scaffolding
or a deterministic gate) · **CUT** (behavior scaffolding the model already performs) ·
**MEASURE** (no telemetry — cannot be adjudicated) · **RELAX** (keep the intent, delete
the prescription).

### research — $46 / 1.4%. Not worth optimizing.
| Step | Verdict | Why |
|---|---|---|
| Phase 0 refinement interview (`--deep`) | KEEP | dormant by default |
| **Phase 0.5 five-term inequality gate** | **RELAX** | 42 prompt lines rendering a per-candidate ✅/❌ checklist for a gate that only runs under `--deep`. Opus 5 applies the judgment natively; the display is behavior scaffolding. Collapse to the criteria, drop the mandated render. |
| Phase 0.75 discovery lens | KEEP | changes search direction; cheap |
| Phase 1–4 | KEEP | — |

### spec — $15 / 0.5%, 3 invocations. Not worth optimizing.
`Step 4 + 4.5` are already merged into ONE call — this is the pattern the other stages
should copy.

### plan — $354 / 11.1%
| Step | Verdict | Why |
|---|---|---|
| Step 0 skip heuristic | KEEP | state |
| **Step 1 pre-interview internal draft (not shown to user)** | **CUT** | "think before you answer" scaffolding. The template *already* calls it "pure waste" and short-circuits it in loop-mode; if it is waste there it is suspect everywhere. Opus 5 thinks by default. |
| Step 1.5 loop-mode detection | KEEP | state |
| Step 1.7 SPEC-need detection | KEEP (157 lines — trim) | state |
| Step 2 / 3.0 SPEC inheritance + lock-in | KEEP | prevents re-asking answered questions |
| Step 3 A–E interview | KEEP | user-mandated high-value gate ([[feedback_ask_thoroughly_when_planning]]) |
| Step A "render current plan state (OPTIONAL)" | RELAX | already optional; the 27-line format-priority list is prescription |
| Step D ADR promotion / Step E exit check | RELAX | judgment the model makes anyway |
| **Step 4 plan-validator (+2nd pass)** | **MEASURE** | $70 / 460 turns / 34 dispatches and **zero telemetry**. Unknown: how often the 2nd pass changes the verdict. Instrument before cutting. |
| Step 5 write PLAN | KEEP | — |
| **Step 6 "verify write"** | **CUT** | verbatim the pattern the Opus 5 guide says to remove; `Write` already errors on failure |

### execute — $756 / 23.8% (largest)
| Step | Verdict | Why |
|---|---|---|
| Step 0 worktree isolation | KEEP | state |
| Step 1 load PLAN | KEEP | — |
| Step 1.5 parallel split assessment | RELAX | rarely fires; 23 lines to usually conclude "serial" |
| Step 2 SPEC/RESEARCH cache | KEEP | this is the biggest token *saver* in the pipeline |
| Phase A author tests | KEEP | — |
| **Phase A.5 test-reviewer gate** | **MEASURE** | $61 / 361 turns / 42 dispatches. Structurally "a subagent to double-check work this same session just wrote" — the doc's exact target. But it is a RED-gate quality gate with **no PASS/FAIL telemetry**. Instrument, then decide. |
| Phase B RED gate | KEEP | deterministic state (proves the test can fail) |
| Phase C implementation | KEEP | — |
| Phase D post-GREEN verification | KEEP | deterministic |
| **+ new: newly-reachable-window assertion** | **ADD** | Approach C |
| Step 4/5 stage exit + finalize | KEEP | — |

### review — $687 / 21.6%
| Step | Verdict | Why |
|---|---|---|
| Phase 0 mechanical pre-checks | KEEP | gated off in this repo; deterministic where on |
| Step 1 reviewer selection / Step 2 drift gate | KEEP | single-owner state |
| Step 2.5 silent-intent-miss hook | KEEP | pure telemetry, cheap |
| Pass 1 (redacted) | KEEP | — |
| **Pass 1.5 `code-verifier`** | **CUT** | 1.9% drop, $1.2 lifetime, doc-named, and a serialization barrier |
| **Pass 2 (full metadata)** | **CUT pending ablation** | 3.1% drop for a 2× reviewer multiplier; the "+47pp" claim is unreproduced |
| Step 3.4 stamp ids | KEEP | deterministic |
| Step 3.5–3.7 cross-model + PIDA | KEEP | earned it: Codex caught the C3 P0 that two Claude reviewers missed |
| Step 4a–4d consensus filter | KEEP | the Opus 5 guide independently endorses the shape — *"ask it to report everything and filter in a separate pass instead"* |
| Step 5 write REVIEW | KEEP | — |

### verify — $11 / 0.3%
All 6 checks **KEEP**. Five deterministic machine gates reading `dashboard.md`,
`findings-*.jsonl` and git state — not a request to re-check reasoning. The 0.47.0 diet
nominated this stage for deletion on cost and reversed itself on exactly this ground.

### wrapup — $494 / 15.6%, carry 0.84 (worst)
| Step | Verdict | Why |
|---|---|---|
| **Step 0.5 stage-delegate** | **FIX or DELETE** | 3 dispatches, 2 mismatches — Approach E |
| Step 1 pre-flight | KEEP | — |
| Step 2 final verification pass | KEEP | already cached via `verification_cache` |
| Step 3 drift verdict read | KEEP | read-only, explicitly no re-analysis |
| Step 3.5/3.6 machine-SPEC write-back + waiver | KEEP | only fires when a machine SPEC exists |
| Step 4 PLAN status | KEEP | — |
| **Step 5 memory append (5.1–5.6)** | **KEEP, RELAX shape** | six sub-steps; the `OTHER` 1511 turns live here. The *content* is why this project's failure classes are known — do not cut it. The *choreography* can compress. |
| Steps 6→7.6 stage/commit/pop/drain | KEEP | already ONE call |
| Step 7.7 squash-land / Step 8 push | KEEP | state |

## ⚠️ Pitfalls

1. **Cutting a review pass to save review tokens saves less than it appears, and the
   thing it removes is the thing that catches P0s.** In the most recent task, round 3
   returned three verified P1s (the cap is 3 — it was deliberately exceeded to round 4),
   and the two P0s of the task lived in the 87% `manual-only` bucket that the consensus
   filter does not auto-apply. A cut sized against the 87% drop rate would have removed
   both. Source: `[[work-docs/REVIEW-harness-diet-phases2-6-2026-08-05]]`.
2. **Green gates after a repair are evidence about the gates' coverage, not the repair.**
   count:4, once at 7/7 with a passing mutation check. Any "we cut a round and the suite
   is green" argument is this fallacy.
3. **Context pressure makes the model silently skip stages rather than report it.**
   `[[wiki:gotcha loop-body-skipping-review-stage]]`: 30+ reviewer invocations across a
   6-phase loop caused a self-preservation heuristic to reinterpret review as optional,
   discovered only when the user asked directly. A cut that *raises* per-round context
   can therefore reduce compliance, not just cost.
4. **The 0.47.0 precedent: cutting unused surface saves nothing.** −45.3% of shipped
   prompt characters produced no measurable runtime saving, because the deleted commands
   had zero invocations. Only cuts on the *executed* path move the number.
5. **`model: sonnet` in agent frontmatter is currently decorative.** Any plan that
   reasons about cost from the frontmatter is reasoning about a value the dispatch
   overrides 179 times out of 188.
6. **Deleting a step that the Opus 5 doc names is still a behavior change, not a
   no-op.** The doc's claim is "no loss in quality" for *verification instructions in
   prose*. Pass 1.5 and Phase A.5 are agents with rubrics and tools; the analogy is
   strong but it is an analogy. Measure yield before deleting the ones with no telemetry.
7. **`--deep` gates and per-iter branches are dormant code paths.** They cost prompt
   characters on every render but almost never execute. Trimming them is Approach D:
   safe, small.

## ❓ Open Questions

These block `/hm:plan` from locking a design:

1. **Pass 2 ablation** — does the "+47pp precision on anchoring-prone diffs" claim
   reproduce on a current model? Without it, cutting Pass 2 is preference, not evidence.
   *How to settle:* re-run the Phase-0 ablation on 3–5 archived diffs with known
   findings, Pass-1-only vs Pass-1+2.
2. **`plan-validator` yield** — of 34 dispatches, how many returned `MAJOR_REVISION`,
   and how many *second* passes changed the verdict? No row exists. *Blocking:* nothing
   about the plan loop can be decided until this is instrumented.
3. **Phase A.5 yield** — FAIL rate of `test-reviewer` across 42 dispatches. Same
   problem. If it FAILs rarely, it is the largest doc-supported cut remaining ($61).
4. **B1 root cause** — *why* do reviewer subagents fail to launch in 1M-Opus sessions
   without an explicit `model: "opus"`? Until this is understood, restoring tiering
   trades cost for launch failures. Is it stale frontmatter, or a real platform
   constraint?
5. **Approach E disposition** — repair `wrapup` delegation or delete it? Deletion is
   defensible under remedy (b) of the count:4 note (5 lifetime uses, 40% mismatch).
   Repair is defensible because `wrapup` is 15.6% of spend at the worst carry in the
   pipeline. This is an architecture call for the plan interview.
6. **Is there an appetite for `low`/`medium` effort on reviewer agents?** The Opus 5
   guide recommends effort as *"your primary control for token cost"* and says review
   accuracy holds at lower settings. The harness has `reasoning_effort` in
   `models.py:674` but wires it **only** to Codex, never to Claude subagents. Unexplored,
   and potentially larger than B1.
7. **Scope of this work** — Approaches B+C+E are three separable landings. Should they
   be one PLAN with phases, or sequenced so each is measured before the next?

## 📚 Sources

- [Prompting Claude Opus 5 — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) — verification-instruction removal, "do not use subagents to verify or double-check your own work", "report everything and filter in a separate pass instead", effort as primary cost control, review precision per pass.
- First-party: `uv run python -m harness_maker.economics {report,stages,composition} --root .`
- First-party: `.claude/observability/{review-*.jsonl, delegation.jsonl, stage-spans.jsonl}`
- First-party: 40 most recent session transcripts under `~/.claude/projects/-home-noel-harness-maker/` (Agent dispatch `model` parameter census)
- First-party: `src/harness_maker/templates/stages/*.j2` (step inventory), `.claude/commands/hm/*.md` (rendered sizes)

## 🔗 Related Internal Docs

- `[[fail:test fix-introduced-defect-passes-all-gates]]` (count:4) — the root cause behind multi-round convergence, with a remedy that is not yet a step
- `[[wiki:architecture harness-diet-fused-axis-removal]]` — "keep state scaffolding, cut behavior scaffolding"; the precedent that cutting unused surface saves nothing
- `[[wiki:gotcha loop-body-skipping-review-stage]]` — context pressure causes silent stage skipping
- `[[PLAN-harness-diet]]` — 0.47.0, the preceding diet
- `[[REVIEW-harness-diet-phases2-6-2026-08-05]]` — the 4-round review this research draws its counter-evidence from
- `[[RESEARCH-context-carry-economics-2026-07-28]]` — the carry measurements CLAUDE.md's context-discipline section is built on
