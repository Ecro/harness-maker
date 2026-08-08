---
type: research
task_slug: workflow-time-token-savings
status: complete
created: 2026-08-08
tags: [harness-maker, research, economics, observability, cross-project, workflow-cost]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[RESEARCH-workflow-loop-efficiency]]"
  - "[[PLAN-workflow-loop-efficiency]]"
  - "[[BASELINE-DELTA-P7]]"
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
  - "[[PLAN-economics-attribution-and-carry]]"
summary: "Stage 1's instrument refutes both of stage 2's planned deletions; carry and session length are the levers"
---

# RESEARCH — workflow time and token savings, measured across four projects

## 🎯 Recommended Direction

**Stage 2 must not be the deletion stage it was scoped as.** The stage-1 instrument
(`09e261da`, `stage_agent_ledger`) has now produced 47 rows across three projects, and both
pre-registered deletion criteria are **refuted by their own denominators**: a later
`plan-validator` pass changes the verdict **2 of 9 times (22%)**, and Phase A.5
`test-reviewer` returns FAIL **9 of 24 times (37.5%)**. Neither step is low-yield. The
instrument did its job — it just returned "keep" on both questions.

What the same measurement says the lever actually is: across the four projects,
**72% of all spend is cache-read (context carry), 51% of spend sits in turns no stage
owns, 28% sits in turns past the attribution span cap, and ~85% of wall clock is the main
loop, not subagents.** Step count is not the cost. Session length and per-turn context are.

And before any of that: **the meter is blind to any project whose path contains an
underscore.** `strange_chess` reported `$0 / 0 turns`; measured through a corrected
transcript root it is **$1,637 over 6,305 turns**. Every cross-project decision made from
the meter as it ships today is missing whole repositories.

Recommended ordering — cheapest first, each with a measured size:

1. Fix `encode_project_dir` (`_` → `-`). One line; recovers $1,637 of invisible spend and
   unblocks the denominator for everything below.
2. Attack session length, not step count. 28% of spend ($3.1k of $11.0k) is past the
   terminal span cap; `strange_chess` is 54%.
3. Apply the composition fix that matches each project — the profile differs by 7× between
   repos, so one rule cannot serve all four.
4. Delete the stage-1 instrumentation prose *that has now answered its question*, since the
   deletions it was buying will not happen. This is the only safe cut available.

This is informational. `/hm:plan` makes the binding decision.

## 🔍 Refinement Decisions

`--deep` was not set; Phases 0 and 0.5 were skipped.

**Discovery lens:** *Technical architecture / implementation* (primary) + *Risk /
measurement validity* (secondary). The user-workflow lens does not bind here: the subject is
this toolchain's own internal cost, an internal-maintainer-value topic with first-party
telemetry, not a product-opportunity question. No arXiv/benchmark lens was used.

**Warm memory tier:** the `memory_retrieve` helper was not invoked; the session already
carried `MEMORY.md` plus this repo's `CLAUDE.md`, and the entries relevant to this topic are
cited inline below (`feedback_pytest_background`, `feedback_subagent_model_override`,
`project_background_exit_code_unreliable`). Recorded rather than silently skipped.

## 📊 Measured baseline (all first-party)

Sources: `harness_maker.economics {report,stages,composition}`,
`.claude/observability/stage-agents.jsonl`, `.claude/observability/stage-spans.jsonl`,
`.claude/observability/delegation.jsonl`. Measured 2026-08-08.

### Per project

| Project | Preset | Total | Carry % | Carry $ | Unattributed | Past span cap | Main wall-clock | Subagent share |
|---|---|---|---|---|---|---|---|---|
| spoton | Production / spec | $4,751 | 69.1% | $3,285 | 61% | 20% ($958) | 92 h | 21.1% |
| harness-maker | (self) | $4,094 | 73.7% | $3,018 | 36% | 25% ($1,035) | 103 h | 15.3% |
| strange_chess | Side / task | $1,637 | 78.0% | $1,277 | 48% | 54% ($883) | 29 h | 0.0% ⚠ |
| edgelog | Side / task | $540 | 64.1% | $346 | 60% | 39% ($213) | 20 h | 8.8% |
| **total** | | **$11,022** | **~72%** | **~$7,926** | **~51%** | **~28% ($3,089)** | **244 h** | **~15%** |

`strange_chess` required a corrected transcript root (see Pitfall 1). **Correction 2026-08-08:**
an earlier version of this row read its `subagent` wall clock as `0.0 h` and called that a
disagreement with its 39 ledger dispatches. That was an artifact of the ad-hoc fixture used to
work around the encoder bug, not a property of the project — the real corpus has 1,704 subagent
turns. See Open Question 2, retracted.

### Per stage (harness-maker, $ from `economics stages`; minutes from `stage-spans.jsonl`)

| Stage | $ | Turns | Carry | Mean ctx | Wall-clock total | n runs | Median |
|---|---|---|---|---|---|---|---|
| (unattributed) | 1,487 | 6,035 | 0.75 | 376k | — | — | — |
| hm:execute | 765 | 3,374 | 0.78 | 358k | 138.0 min | 8 | 20.2 |
| hm:review | 751 | 3,130 | 0.70 | 342k | 62.7 min | 8 | 7.3 |
| hm:wrapup | 549 | 2,289 | **0.84** | **404k** | 104.1 min | 9 | 3.6 |
| hm:plan | 382 | 1,812 | 0.59 | 256k | 123.2 min | 6 | 23.4 |
| hm:research | 54 | 387 | **0.47** | **136k** | 18.9 min | 2 | 11.1 |
| hm:verify | 14 | 63 | 0.84 | 371k | 1.7 min | 1 | 1.7 |

Per-turn cost tracks mean context, not stage complexity: research at 136k costs
**$0.14/turn**; wrapup at 404k costs **$0.24/turn**. Across projects the spread is wider —
`edgelog` averages $0.169/turn, `spoton` $0.294/turn.

`wrapup` is the worst stage in **every** project (ctx 404k / 501k / 507k / 422k; carry
0.84 / 0.75 / 0.89 / 0.84). It runs last, so it inherits the whole session.

### Context composition — the profile diverges by project

| Category | harness-maker | strange_chess | spoton | edgelog |
|---|---|---|---|---|
| `tool_result` | 29.9% | 40.5% | **78.6%** | **77.8%** |
| `tool_call_input` | **39.7%** | **36.8%** | 11.3% | 10.6% |
| `slash-command-body` | **15.7%** | 14.7% | 5.7% | 6.9% |
| `task-notification` | 6.5% | 4.4% | 2.3% | 2.4% |
| `assistant_text` | 5.4% | 3.0% | 1.6% | 2.1% |
| `human-typed` | 0.12% | — | — | 0.1% |
| bash `grep/rg` | 11.4% | 11.4% | 3.5% | 3.9% |
| bash `file inspection` | 7.1% | 10.0% | 2.6% | 2.7% |
| bash `pytest` | 5.4% | — | 0.9% | — |
| `write_after_read` dup | **23.8%** of write chars | 11.8% | 18.3% | 20.1% |
| total chars carried | 35.9 M | 21.1 M | **97.5 M** | 21.3 M |

Two distinct cost shapes:
- **spoton / edgelog are `tool_result`-dominated (~78%)**, and bash accounts for only ~10 of
  those points — so the mass is `Read`/`Grep`/`Task` output, i.e. whole documents pulled into
  the main context. spoton carries **97.5 M chars**, 4.6× harness-maker, for comparable spend.
- **harness-maker / strange_chess are `tool_call_input`-dominated (37–40%)** — what *we send*:
  Write/Edit bodies, heredocs, long commands. `CLAUDE.md`'s two carry-discipline rules target
  exactly this, and they are being violated on **12–24% of written chars** (80 duplicate
  Write-after-Read calls in harness-maker alone, 970 kB).

### The stage-1 ledger's two pre-registered questions, answered

47 rows: `plan-validator` 20, `test-reviewer` 25, `code-reviewer` 2. Sentinels
(`dispatch-failed`, `dispatch-skipped`) excluded from numerators and denominators per the
module's own rule — 2 of 47 rows, a ~4% silent-dispatch-loss signal in its own right.

**Q1 — delete the second `plan-validator` pass?**
`P(verdict changes | a later pass ran)` = **2/9 = 22.2%**.
- `strange_chess/pv-cb41ebb-aiop`: MAJOR_REVISION → MAJOR_REVISION → **APPROVED** (pass 3).
- `strange_chess/wsd-plan-20260808`: MAJOR_REVISION → **NEEDS_REVISION**.
- The other 7 later passes agreed with pass 1.
**Verdict: keep.** Cost of the later passes is 36.2 min of serial wall clock across all
observed runs — real, but it is buying a verdict flip roughly one time in five.

**Q2 — delete the Phase A.5 `test-reviewer` gate?**
`P(FAIL)` = **9/24 = 37.5%** (15 PASS, 9 FAIL, 1 `dispatch-skipped`).
**Verdict: keep, emphatically.** A gate that rejects over a third of RED-stage test suites is
not a formality.

Total agent wall clock in the ledger: `test-reviewer` 59.6 min, `plan-validator` 86.3 min,
`code-reviewer` 9.1 min.

## 🛠️ Approaches Found

### Approach A — Delete the two instrumented steps (stage 2 as scoped) ❌ refuted

| Field | Content |
|---|---|
| Approach | Execute stage 2's pre-registered deletions: second validator pass, Phase A.5 gate |
| Assumption | Both steps rarely change the outcome, so the barrier is pure latency |
| Evidence | **Contradicted** by the instrument built to test it: 22.2% and 37.5%. `PLAN-workflow-loop-efficiency:77` had already flagged counter-evidence ("the validator's 2nd pass had just caught 2 criticals here") |
| Trade-off | Would buy back ~36 min of serial wall clock and ~3,000 chars of prompt, at the price of one verdict flip in five plans and one rejected test suite in three |
| Compatibility | Mechanically easy — the templates already gate on config |
| Risk | **high** — this is the `ratchet-rebaselined-by-its-own-subject` shape inverted: deleting a step *after* its instrument said keep |

**This is the finding that most changes what stage 2 should be.** Note the near-miss:
harness-maker's own 6 rows alone give **0/3** for the validator — "delete". Adding the two
consumer projects gives 2/9 — "keep". A single-repo evaluation of a correctly
pre-registered rule would have deleted a load-bearing step.

### Approach B — Fix the meter's blind spot, then re-decide ✅ recommended first

| Field | Content |
|---|---|
| Approach | `economics_source.encode_project_dir` maps `/` and `.` to `-` but not `_`; Claude Code maps `_` too (`/home/noel/strange_chess` → `-home-noel-strange-chess`) |
| Assumption | none — verified by direct call: `encode_project_dir` returns `-home-noel-strange_chess`, `discover_transcript_dirs` returns `[]`, both roots |
| Evidence | `economics stages --root /home/noel/strange_chess` → `$0 / 0 turns`. Same command with a corrected transcript root → **$1,637 / 6,305 turns**. `encode_project_dir` is shared by `economics_source`, `context_composition` and `run_classify`, so the cost meter, the composition meter and the boundary classifier are all blind together |
| Trade-off | Almost none. The precedent for the failure is in-repo: `run_classify.py:431` records the identical class (`Path(".")` → `"-"` → matched nothing, `boundaries` reported 0 while `economics report` saw 392, and every unit test passed because they all used absolute `tmp_path`) |
| Compatibility | One regex; the fix must also cover the sibling-worktree prefix |
| Risk | **low** — the only hazard is that historical numbers move, which is the point |

Affected beyond `strange_chess`: `edge_testfarm_os`, `edge_bsp_foundation`, `AC_sources`,
`log_agent`, `log_seeker` — any repo with `_` in its path.

### Approach C — Attack session length and per-turn context ✅ recommended

| Field | Content |
|---|---|
| Approach | Treat stage boundaries as session boundaries; force compaction (or a fresh session) before `wrapup`; keep mean context nearer research's 136k than wrapup's 404–507k |
| Assumption | Cost is roughly `turns × mean_context`, and the carried context at wrapup is mostly not needed to write a commit |
| Evidence | carry 64–78% of spend ($7.9k of $11.0k); **28% of spend ($3,089) is in turns past the terminal span cap** (`strange_chess` 54%, `edgelog` 39%); per-turn cost rises from $0.14 at 136k to $0.24 at 404k; `wrapup` is the worst stage in all four projects |
| Trade-off | A fresh session re-reads PLAN/SPEC/REVIEW — some carry is recreated, not eliminated. Unquantified; see Open Question 4 |
| Compatibility | `wrapup` already delegates via `stage-delegate` (`delegation.jsonl`: brief→dispatch, though 1 of 6 rows is a `mismatch` on promotion arithmetic). Delegation is the right shape; nobody has measured whether it actually cuts carry |
| Risk | **medium** — the saving is inferred from the cost model, not yet demonstrated by an A/B |

### Approach D — Per-project composition fix ✅ recommended, but not one rule

| Field | Content |
|---|---|
| Approach | Route the fix by profile: `tool_result`-heavy repos get bounded reads / `head_limit` / delegated reading; `tool_call_input`-heavy repos get Edit-over-Write enforcement |
| Assumption | The two profiles have different dominant terms, so a single global rule under-serves both |
| Evidence | `tool_result` 78.6% / 77.8% (spoton, edgelog) vs `tool_call_input` 39.7% / 36.8% (harness-maker, strange_chess); spoton carries 97.5 M chars; `write_after_read` duplication 11.8–23.8% of write chars in all four |
| Trade-off | `CLAUDE.md` already carries both rules as prose with no hook enforcement — the document says so explicitly, and the 23.8% duplication rate in this very repo is the measurement of that gap |
| Compatibility | The meter can already judge it (`composition`), which is what makes it a ratchet candidate rather than advice |
| Risk | **low** on the read side; **medium** on enforcement — a PreToolUse gate on Write-after-Read is a new failure surface |

### Approach E — Cut the shipped prompt surface stage 1 added ✅ recommended, small

| Field | Content |
|---|---|
| Approach | Retire the instrumentation prose whose question is now answered, keeping the emits |
| Assumption | The ledger's value was the answer, not perpetual collection |
| Evidence | `BASELINE-DELTA-P7.md §1`: stage 1 grew `aggregate_chars.claude` by **+7,113** and mandated round-trips by +3, of which ~3,000 chars and all 3 round-trips are the ledger, explicitly conditional — *"only pays for itself if stage 2 actually reads those ledgers and deletes something."* Stage 2 now has the reading, and the answer is *delete nothing.* |
| Trade-off | `slash-command-body` is 5.7–15.7% of carried chars, so prompt size is a real term — but 3,000 chars is small against $7.9k of carry |
| Compatibility | Both aggregations are one-shot answers; keeping the emits costs almost nothing and preserves the denominator |
| Risk | **low**, with one caveat: deleting the ledger entirely would make the "keep" verdicts unfalsifiable later |

## ⚠️ Pitfalls

1. **A silently-empty meter reads as a cheap project.** `strange_chess` reported `$0` for
   $1,637 of real spend, with exit status 0 and no diagnostic. Same class as
   `run_classify.py:431`, already recorded in-repo, and the same reason unit tests missed it
   (absolute `tmp_path` everywhere). Related: `project_background_exit_code_unreliable` —
   a clean exit is not evidence the thing ran.
2. **Evaluating a pre-registered rule on one repo.** harness-maker alone: 0/3 → delete.
   All three: 2/9 → keep. The flip is not noise; one of the two changed verdicts went
   MAJOR_REVISION → APPROVED on a third pass. Whatever stage 2 decides, it must pool projects.
3. **Instrumentation that grows the prompt is a loan, and this one came due.** +7,113 chars
   shipped on the promise of a later deletion that the data now forbids. If it stays as-is,
   the cost-reduction plan's net effect on surface is a permanent increase.
4. **`dispatch-failed` / `dispatch-skipped` are outcomes-shaped but are not outcomes.**
   2 of 47 rows. The module's aggregation rule excludes them; an aggregation that forgets
   deflates both rates. They are also a ~4% silent-loss signal — see
   `feedback_subagent_model_override` (reviewer subagents fail to launch in 1M-Opus sessions
   unless `model` is passed explicitly), which is a plausible cause worth checking rather
   than assuming.
5. **`wrapup`'s cheap median hides its cost.** harness-maker median 3.6 min, mean 11.6 min,
   $61 per run — the mean is the truth here, and it is the highest-carry stage in all four
   projects.
6. **Don't poll a long meter run.** `economics` over these corpora takes minutes;
   `feedback_pytest_background` applies — background it and read the notification.

## ❓ Open Questions

1. **What is the unattributed 51% ($5.5k) made of?** For harness-maker,
   `unattributed_breakdown` is `recoverable: 273 turns / $58` vs
   `unrecoverable_in_window: 5,730 turns / $1,423`, and
   `classification_cache_misses: 166` against `classification_boundaries: 199` — so the
   retroactive classifier has barely run. It is the largest single bucket in every project
   (36–61%) and no stage-level change can reach it. Running the classifier is the cheapest
   next measurement.
2. ~~**`strange_chess`: `subagent = 0.0 h` vs 39 ledger dispatches.**~~ **RETRACTED
   2026-08-08 — this was my own measurement error, not an instrument disagreement.** The `0`
   came from an ad-hoc hardlinked transcript fixture built to work around the Open-Question-4
   encoder bug, not from the real corpus. Measured against the real transcript root after that
   bug was fixed, `strange_chess` has **1,704 subagent turns across 45 turn-groups** against 39
   ledger dispatches — the ledger is *corroborated* there, and comfortably smaller because it
   records only `plan-validator` / `test-reviewer` / `code-reviewer`, not every subagent. The
   "~85% of wall clock is the main loop" figure loses this caveat but keeps the one about
   scopes being non-summable.
3. **Why does spoton have no `stage-agents.jsonl` at all? — now the ONLY live anomaly, and a
   bigger one than the retracted item above.** Measured 2026-08-08: spoton has **6,153 subagent
   turns across 57 turn-groups and zero ledger rows**. It re-rendered to 0.50.1 (`261843e`), so
   the emit is rendered and simply never fires. spoton is the **only Production / spec-driven**
   project of the four, which means the pre-registered 22.2% / 37.5% rates are computed on a
   denominator that **structurally excludes an entire preset class**. This is the
   `absent-case = feature black hole` class (count:8), and Pitfall 2 applies to it directly —
   one preset's absence can flip a verdict the same way one repo's did.
4. **Does splitting a session actually reduce total cost, or relocate it?** Approach C's
   saving is inferred from `turns × mean_context`; the re-read cost of a fresh session is
   unmeasured. This needs a pre-registered A/B, not an argument.
5. **Is `write_after_read` duplication worth a hook?** 12–24% of write chars across four
   projects, with the prose rule already shipped and demonstrably not holding. Enforcement
   is a new PreToolUse surface with its own risk.
6. **Which of the four projects should set the default?** spoton's profile (78%
   `tool_result`, 97.5 M chars) and harness-maker's (40% `tool_call_input`) want opposite
   defaults; `targets`/`preset` do not currently carry a composition axis.

## 📚 Sources

No external sources. Every figure is first-party, produced 2026-08-08 by:

- `uv run python -m harness_maker.economics {report,stages,composition} --root <project>`
  (4 projects; `strange_chess` via `--transcript-root` over a corrected directory name)
- `.claude/observability/stage-agents.jsonl` — 47 rows (harness-maker 6, strange_chess 39,
  edgelog 2)
- `.claude/observability/stage-spans.jsonl` — 124 rows, harness-maker, 2026-07-27 → 2026-08-08
- `.claude/observability/delegation.jsonl` — 6 rows
- `git show 09e261da` — the stage-1 instrumentation commit and its own conditional claim
- `src/harness_maker/economics_source.py:104` (`encode_project_dir`),
  `src/harness_maker/run_classify.py:431` (the in-repo precedent)

## 🔗 Related Internal Docs

- [[RESEARCH-workflow-loop-efficiency]] — the harness-maker-only predecessor; this document
  extends it cross-project and evaluates the ledger it asked for
- [[PLAN-workflow-loop-efficiency]] — stage 1's plan; lines 29, 67, 77, 176, 379, 487 define
  the deletions now refuted
- [[BASELINE-DELTA-P7]] §1 — the +7,113 char surface growth and its explicit condition
- [[RESEARCH-context-carry-economics-2026-07-28]] — where the carry-discipline rules in
  `CLAUDE.md` came from
- [[PLAN-economics-attribution-and-carry]] — the attribution model behind `(unattributed)`
  and the span cap
- Memory: `feedback_pytest_background`, `feedback_subagent_model_override`,
  `project_background_exit_code_unreliable`
