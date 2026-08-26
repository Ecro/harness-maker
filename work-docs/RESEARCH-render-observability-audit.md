---
type: research
task_slug: render-observability-audit
status: complete
created: 2026-08-26
tags: [harness-maker, research, observability, economics, telemetry, render-integrity]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
  - "[[PLAN-harness-economics-observability]]"
  - "[[wiki:architecture carry-is-a-main-loop-phenomenon]]"
  - "[[wiki:architecture ledger-exclusions-and-test-isolation]]"
summary: "Render clean at 0.54.1; 4 of 8 findings already remediated, 7 real issues remain"
---

# RESEARCH — 0.54.1 render integrity + observability waste audit

## 🎯 Recommended Direction

**The render is healthy. The expensive problem is that the observability layer is
lying about where the money goes — and two of its ledgers are contaminated badly
enough that acting on them would send work in the wrong direction.**

Re-rendering 0.54.1 over the live harness produces a byte-identical tree
(`git status --porcelain` → 0 lines, 99 files, 15 commands, 3 targets). Structural
health is 82/100 with only two known-benign failures. There is no render defect to fix.

By contrast, of $6,315 priced in the 30-day window, **$3,567 (56%) is attributed to
`(unattributed)`** because the stage-span ledger lost 36 of 36 July `end` events and
still drops 24% of August's. And **39% of the second-opinion ledger (147 of 375 rows)
is pytest fixture output written into the production file**, which makes the exact
health metric CLAUDE.md prescribes report codex at **61.3% loss when the truth is 2.1%** —
a 30× error in the signal that decides whether a paid second model is working.

Neither of these costs tokens directly. Both cost *decisions*, and the two prior
remediation plans in `work-docs/` were sized against numbers this corruption produced.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (render pipeline, ledger
schemas, hook wiring) + **Risk / compliance** (telemetry integrity). No `--deep`
interview — the topic was already concrete.

Scope: the user asked for *critical* token and time consumers only. Findings below
are ordered by whether they change a decision, not by curiosity value.

## 🛠️ Approaches Found

### Part 1 — Render integrity: PASS

| Field | Content |
|---|---|
| Approach | Idempotent re-render + audit diff as the verification oracle |
| Assumption | A correct render is a fixed point: re-running `make --audit` changes nothing |
| Evidence | `uv run python -m harness_maker.cli make . --audit` → rc=0, "harness applied to .claude (99 files)", then `git status --porcelain` → **0 lines**. Version sync verified across all 5 files (3 plugin manifests + pyproject + `__init__`) = `0.54.1`. Plugin cache holds 0.54.1 as newest. |
| Trade-off | `--audit` is not read-only — it re-renders. Safe only from a clean tree. |
| Compatibility | Targets `claude-code,cursor,codex` all rendered; keep=3, merge=20 user blocks preserved. |
| Risk | **low** |

Structural health = **82/100**, two failing signals, both understood:

- `context_quality:claude_md_within_limit` — CLAUDE.md is **624 lines vs the 500-line
  Production limit** (P1). This is the only render-adjacent finding with a direct
  token cost: CLAUDE.md is injected into every single turn of every session.
- `guardrails:judgment_verdict_freshness` — a stale judgment verdict for
  `SPEC-workflow-loop-efficiency:AC-010` (P2, procedural).

~~One cosmetic drift: `hm --help` omits `worktree`, `wrapup_*`.~~ **RETRACTED** — `hm --help`
emits 44 lines and all four ARE in `_DISPATCHABLE` (`hm.py:36-76`). The apparent omission was
a `head -40` truncation in the probe, not a defect in the tool.

### Part 2 — Where the money actually goes

30-day window, 27,061 priced turns, coverage 1.00, 630 transcript files, 0 read failures.

| Stage | USD | turns | $/turn | ctx/turn | carry | dominant category |
|---|---:|---:|---:|---:|---:|---|
| **(unattributed)** | **3,567** | 13,386 | 0.266 | 405k | 0.75 | OTHER 67% |
| hm:execute | 799 | 3,604 | 0.222 | 353k | **0.79** | OTHER 67% |
| hm:review | 782 | 4,276 | 0.183 | 244k | 0.63 | VERIFY 83% |
| hm:wrapup | 493 | 2,565 | 0.192 | 302k | 0.75 | **OTHER 82%** |
| hm:plan | 408 | 1,973 | 0.207 | 257k | 0.61 | OTHER 50% |
| hm:spec | 102 | 467 | 0.219 | 276k | 0.62 | OTHER 57% |
| hm:research | 75 | 540 | 0.139 | 140k | 0.49 | OTHER 90% |
| hm:verify | 20 | 73 | 0.273 | **486k** | **0.89** | VERIFY 81% |

**Global carry ratio 0.72 — `cache_read_usd` is $4,556 of the $6,315 total (72%).**
Only $1,759 is work. This reproduces the 2026-07-27 wiki finding
(`carry-is-a-main-loop-phenomenon`) on a fresh window, and the monotonic
position-in-pipeline gradient survives: `research` 140k/0.49 → `plan` 257k/0.61 →
`execute` 353k/0.79 → `verify` 486k/0.89. **`hm:verify` pays ~$8 of rent per $1 of
work** while needing almost none of what it carries.

Subagent spend is $971 (15.4%), and reviewers are 87% of it:

| Agent | USD | share | turns | ctx |
|---|---:|---:|---:|---:|
| code-reviewer | 381.69 | 39.3% | 3,448 | 404M |
| test-reviewer | 185.05 | 19.0% | 1,234 | 131M |
| plan-validator | 121.62 | 12.5% | 759 | 86M |
| security-reviewer | 121.41 | 12.5% | 982 | 108M |
| stage-delegate | 118.45 | 12.2% | 1,362 | 183M |
| concurrency-reviewer | 31.57 | 3.2% | 265 | 26M |

### Part 3 — What the carried context is made of

`economics composition` over 58.4M chars:

| Category | chars | share |
|---|---:|---:|
| tool_call_input | 23.7M | **40.6%** |
| tool_result | 16.3M | 27.9% |
| **slash-command-body** | **9.5M** | **16.3%** |
| task-notification | 4.8M | 8.2% |
| assistant_text | 2.8M | 4.8% |
| system-reminder | 0.63M | 1.1% |
| compaction-summary | 0.56M | 1.0% |
| human-typed | 0.05M | 0.08% |

Per-tool decomposition (not reported by the shipped tool — measured here):

| Tool | input chars | calls | avg/call | result chars |
|---|---:|---:|---:|---:|
| Bash | 9.61M | 15,124 | 635 | 12.31M |
| Write | 6.10M | 738 | **8,266** | 0.13M |
| Edit | 5.47M | 3,675 | 1,489 | 0.78M |
| Agent | 2.04M | 590 | 3,464 | 0.64M |
| Read | 0.08M | 609 | 124 | 2.13M |

**Bash output is disciplined.** Mean result sizes: `grep/rg` 893 chars, `pytest` 477,
`file inspection` 1,357. Only **6 results in the entire corpus exceed 20k chars**
(0.14M total = 1.2% of Bash output). The context-discipline rules in CLAUDE.md are
working; the volume comes from *call count* (15,124 Bash calls), not from fat results.
There is no low-hanging truncation win here.

**The harness's own prompt surface is the largest single controllable block:**

| Injected command body | chars | share | n | avg | ~tokens |
|---|---:|---:|---:|---:|---:|
| hm:review | 2.60M | 27.3% | 44 | 59,025 | ~14.8k |
| hm:plan | 1.89M | 19.8% | 36 | 52,373 | ~13.1k |
| hm:wrapup | 1.69M | 17.8% | 36 | 46,990 | ~11.7k |
| hm:execute | 1.51M | 15.9% | 43 | 35,191 | ~8.8k |
| /harness-maker:make | 0.71M | 7.4% | 18 | 39,206 | ~9.8k |
| hm:research | 0.59M | 6.2% | 22 | 26,843 | ~6.7k |
| hm:spec | 0.34M | 3.5% | 11 | 30,583 | ~7.6k |

On disk: `review.md` **87,438 bytes**, `plan.md` 67,667, `loop.md` 53,711,
`execute.md` 51,100, `wrapup.md` 47,506 — 447KB across 15 commands. A single
`/hm:review` injection is ~15k tokens that then rides in the prefix for the rest of
the session and is re-read on every subsequent turn at the 0.63–0.79 carry ratio.

`write_after_read` duplication: **1.47M chars = 25.1% of all `Write` content** was a
re-send of a file already in context (89 of 738 Write calls). That is the exact
footgun CLAUDE.md's context-discipline section names, still live at 2.5% of total context.

### Part 4 — Time

`stage-spans` closed, id-bearing spans only (post-fix population, n=125, 30.9h):

| Stage | n | total | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| hm:execute | 27 | 11.8h | 7.7m | 36.2m | 288.3m |
| hm:plan | 22 | 7.4h | 19.8m | 28.1m | 45.8m |
| hm:spec | 8 | 4.2h | 24.6m | 46.7m | 90.0m |
| hm:wrapup | 24 | 2.8h | 1.8m | 11.8m | 61.9m |
| hm:review | 27 | 2.7h | 5.4m | 9.4m | 17.4m |

Wall clock by scope: main loop **515,257s (143h)**, subagents **94,788s (26h)** — the
subagent fleet is 15.5% of elapsed time and 15.4% of cost. Fan-out is *not* the time sink.

Blocking subagent gates, from `stage-agents.jsonl` (n=92):
- `plan-validator` 37 runs, 172.5m total, median 4.8m
- `test-reviewer` 43 runs, 130.7m total, median 3.1m
- Verdicts: **FAIL 40, MAJOR_REVISION 36, PASS 13** — 83% of gate runs demand rework.
- Attempts: 47 first-pass, **38 second, 6 third, 1 fourth** — 49% of gated work is re-run.

Review rounds (`review-*.jsonl`, 44 slugs): round 1 = 41, round 2 = 24, round 3 = 5.
**59% of reviews need a second round**; each round re-dispatches the reviewer fleet.
Verifier discrimination is near-null: 401 Pass-1 findings → 390 kept, only **5 dropped
across 66 rounds**, `verifier_false_drop_n` and `verifier_false_keep_n` both 0 everywhere.

## ⚠️ Pitfalls

### P0 — ALREADY REMEDIATED in code; the residual defect is in CLAUDE.md

`.claude/observability/second-opinion.jsonl` holds 375 rows, **147 of them pytest fixture
writes** (`FileNotFoundError: '/tmp/pytest-of-noel/...'`, `slug: "s"` ×144 /
`"hm-ledger-canary"` ×3, dated 2026-08-08 → 2026-08-17).

**Both halves are already fixed.** The producer was gated on 2026-08-17
(`tests/unit/test_ledger_isolation.py`; last polluted row is that same date), and the
reader side has a full exclusion mechanism — `.claude/observability/.ledger-exclusions.json`
already names `slug: "s"`, `hm-ledger-canary`, `hm-ledger-canary-invoke` and one bad
`run_id`, consumed by `ledger_exclusions.py` → `verifier_discrimination.py`, with a
call-site gate (`test_ledger_exclusions_call_sites.py`) whose docstring says in as many
words that "a correct helper wired to nothing is the defect".

Running the shipped reader confirms it works:

```
$ hm verifier_discrimination report --ledger .claude/observability/second-opinion.jsonl
  exclusions.rows_dropped: 150
  codex:       calls 93, invoked 91, skipped 2, failed 0, loss_rate 0.0215
  antigravity: calls 101, invoked 49, skipped 25, failed 27, loss_rate 0.5149
```

**What is NOT fixed is the instruction.** CLAUDE.md tells the reader to compute the metric
by hand — "`(skipped + failed) / total` 을 모델별로 계산하고 `stage: "health"` 행은 제외할
것" — and never mentions `.ledger-exclusions.json` or
`hm verifier_discrimination report`. Following CLAUDE.md literally over the live file yields
**codex 61.3%** where the shipped tool yields **2.15%**. That is not hypothetical: this audit
reproduced the 30× error before finding the tool, which is the third recorded instance of the
same shape (the exclusions file's own `reason` fields record the first two).

Secondary, unchanged: `antigravity` really is at 51.5% loss (13 empty-`response` SUCCESS
envelopes, 9 `timeout waiting for response`, 8 `CANCELED`, 2 quota) — but it is not enabled
(`second_opinion.models: ["codex"]`), so this is experiment residue, not live cost.

### P1 — 56% of spend is unattributable because the span ledger dropped its `end` events

`stage-spans.jsonl`: 180 `start`, 109 `end`. Split by month:

| month | start | end | unclosed | session-less starts |
|---|---:|---:|---:|---:|
| 2026-07 | 36 | **0** | 36 | 36 / 36 |
| 2026-08 | 144 | 109 | 35 | 18 / 144 |

July emitted **zero** `end` events — `_cli_span_end` read the session id only from
`HM_SESSION_ID`, which is an unexported shell variable a hook subprocess never sees, so
the hook matched none of its own events and wrote nothing. That was fixed (round-3 review;
`_span_end_session_id` now reads stdin first, `worktree.py:5704`) and August closes 76%.

The consequence is still live in the numbers: **16,078 of 27,061 turns (59%) were closed
by the span cap rather than a real `end`, carrying $4,017 (64%)**, and the report itself
states `"A turn past the span cap is never recoverable"` — `unattributed_breakdown.recoverable`
is exactly **0 turns / $0.00**. The $3,567 `(unattributed)` bucket at 405k ctx/turn is
mostly main-loop work that a working ledger would have named.

**The code fix is confirmed landed and working.** August closure by week: 27/46 (59%) →
39/43 (91%) → 31/41 (76%) → 13/15 (87%). The residual ~15-20% is consistent with sessions
killed without a Stop hook and with Cursor/Codex sessions, which `_cli_span_end`'s own
docstring says write no hook at all. **The $3,567 unattributed figure is therefore a
30-day-window artifact dominated by the broken July population, not a live regression** —
it will age out. No code change is indicated for P1; only the interpretation of the number.

### P2 — `end` rows drop `task_slug` and `git_branch`

`_emit_stage_span` passes both on `start`; `_cli_span_end` passes neither
(`worktree.py:5783` — `emit_event("end", stage=..., cwd=base, session_id=mine)`).
Every `end` row therefore carries `task_slug: null, git_branch: null`. The reader chains
by session sequence so it still works, but **no per-task or per-branch join is possible
from the ledger**, and the obvious naive join (by slug) silently yields zero spans.

### P3 — Two internally inconsistent wall-clock views

Median `hm:wrapup` span is **1.8m** while economics attributes **2,565 turns** to
`hm:wrapup`. Those cannot both be right. Spans are being closed early by the next stage's
`start` (`_build_spans` closes on next start within a session), so span duration and span
turn-attribution disagree about the same window. **Do not size any change on span wall
clock** until this is reconciled.

### P4 — `orphans-*.jsonl`: 16,438 rows for 308 distinct paths

50 daily files, 2.2MB, **53× duplication** — every `make --audit` / re-render re-logs the
same 265 `theirs` orphans. Cheap on disk, never enters context, but it makes the file
useless for spotting a *new* orphan. Low severity; listed so it is not mistaken for signal.

### P5 — `delegation.jsonl`: 54% of wrapup dispatches mismatch

28 dispatch rows: 12 `dispatched`, **15 `mismatch`**, 1 `unparseable`. Mismatch reasons are
receipts claiming memory entries that do not exist (`wiki-missing`, `failure-missing`,
`promotion-missing`), plus `promotion-arithmetic` (4 candidates → 3 promoted + 0 skipped),
`receipt-unparseable` (pydantic `extra_forbidden` on `steps_skipped` / `drift_verdict`), and
7 `document-escapes-root` from absolute worktree paths. Each mismatch is rework in the
most expensive stage-adjacent path.

### P6 — RETRACTED (misread schema), with one real residual

~~123 of 200 auto-advance rows carry `stage: null`.~~ **False.** The advance-family events
use a different key by design: `gate_blocked`/`gate_auto_answered` carry `stage`, while
`advanced`/`advance_authorized`/`advance_entered` carry **`to`**. Every row is fully
attributed; the probe keyed on the wrong field.

The one real residual: `advance_authorized` 44 vs `advance_entered` 32. That gap is exactly
what `autopilot_ledger.py:33` says the split vocabulary exists to expose ("announces the next
stage but never enters"), and `_pending_authorization` implements greedy in-order pairing for
it. **The instrument is working**; whether a 12-authorization gap is acceptable is a policy
question, not a defect.

### P7 — CLAUDE.md is 624 lines against a 500-line Production ceiling

The one finding where render and token cost meet. CLAUDE.md is in the prefix of every turn
of every session, at a 0.72 global carry ratio.

## ✅ Triage — already remediated vs real

Verified against current source and the shipped tooling, not against memory.

| # | Finding | Status | Evidence |
|---|---|---|---|
| P0 | second-opinion ledger 39% test pollution | **ALREADY FIXED** (code) / **REAL** (docs) | producer gated 2026-08-17; `.ledger-exclusions.json` + `verifier_discrimination report` drops 150 rows, reports codex 2.15%. CLAUDE.md still prescribes the hand formula that yields 61.3%. |
| P1 | span `end` events lost → 56% unattributed | **ALREADY FIXED** | `_span_end_session_id` reads stdin first (`worktree.py:5704`); Aug closure 59→91→76→87% by week. Residual is window artifact + hookless runtimes. |
| P2 | `end` rows drop `task_slug`/`git_branch` | **REAL** | `worktree.py:5783` — `emit_event("end", stage=…, cwd=…, session_id=…)`, both fields omitted. |
| P3 | span duration vs turn-attribution contradict | **REAL** | wrapup median 1.8m vs 2,565 turns attributed. |
| P4 | orphans 53× duplication | **REAL** (low) | 308 paths → 16,438 rows / 2.2MB across 50 files; `reconcile._log_orphan_kept` appends unconditionally. |
| P5 | delegation dispatch 54% mismatch | **REAL** (live) | 15 of 28, spanning 2026-08-01 → 2026-08-23. |
| P6 | auto-advance rows unattributed | **RETRACTED** | advance-family uses `to:`, not `stage:`. Probe error. |
| P7 | CLAUDE.md 624 vs 500 lines | **REAL** | `/hm:health` P1. |
| — | `hm --help` omits `worktree`/`wrapup_*` | **RETRACTED** | `head -40` truncation; all present in `_DISPATCHABLE`. |
| C1 | `/hm:review` 87KB = 27.3% of injected command text | **REAL** | measured; ~15k tok/injection × 44. |
| C2 | `Write` re-sends 25.1% of already-read content | **REAL** | 89 of 738 calls, 1.47M chars. No guard exists (`post_write_reminder` is an unrelated domain reminder). |
| C3 | Pass 1.5 verifier discrimination ≈ 0 | **REAL** | 401 findings → 5 drops over 66 rounds; false-drop/false-keep both 0 in all 11 samples. |
| C4 | gate FAIL rate 83%, 49% of work re-run | **REAL** | FAIL 40 + MAJOR_REVISION 36 vs PASS 13; attempts 47/38/6/1. |
| C5 | `hm:verify`/`hm:wrapup` carry 0.89/0.75 @ 486k/302k | **REAL** | per-stage economics table above. |

**Net: 2 retracted, 2 already fixed in code (1 leaving a docs defect), 10 real.**

Recommended order — cheapest-first, decision-impact-weighted:

1. **P0-docs** — CLAUDE.md must point at `hm verifier_discrimination report` / `.ledger-exclusions.json` instead of a hand formula. One paragraph; prevents the 30× misread that has now happened three times.
2. **P7** — trim CLAUDE.md to ≤500 lines. Every-turn prefix cost, and it is the file P0-docs edits.
3. **P2** — pass `task_slug`/`git_branch` on the `end` event. Two arguments.
4. **P5** — the wrapup delegate receipt mismatch (54%, live rework).
5. **C1** — `/hm:review` surface reduction.
6. **C3/C4** — decide whether Pass 1.5 and the 83%-FAIL gates earn their dispatch.
7. **P3** — reconcile the two wall-clock views (blocks sizing any future change).
8. **P4** — orphan-log dedup (cosmetic, do last).

## ❓ Open Questions

1. **Purge or partition the polluted ledger rows?** Deleting 147 rows from an append-only
   file conflicts with its append-only contract; the alternative is a
   `.ledger-exclusions.json` entry (one already exists at 957 bytes) or a reader-side
   filter. Which is the intended mechanism?
2. **Is the residual 24% of unclosed August spans a second defect, or expected**
   (sessions killed without a Stop hook, Cursor/Codex sessions that write no hook at all)?
   The docstring says Cursor/Codex should show higher `capped_turns` by construction.
3. **Should `hm:verify` and `hm:wrapup` be delegated or context-reset?** They carry
   486k/302k ctx/turn at 0.89/0.75 carry with 81%/82% non-productive categories.
   `delegation.stages: ["wrapup"]` is already configured and firing (33 `brief ok`), yet
   wrapup still shows 0.75 carry — is delegation reducing carry at all here?
4. **Is the `/hm:review` 87KB command body reducible?** It is 27.3% of all injected
   command text and ~15k tokens per invocation. Prior work (`PLAN-harness-diet`,
   `PLAN-token-economy-step-pruning`) already cut this axis — is there headroom left,
   or is this the floor?
5. **Do `plan-validator` / `test-reviewer` earn their 83% FAIL rate?** 38 of 92 runs are
   attempt ≥2. The user has already locked "plan-validator runs once" as policy
   (`feedback_plan_validator_single_pass`) — does the same reasoning apply to `test-reviewer`?
6. **Is the verifier (Pass 1.5) worth its dispatch?** 5 drops out of 401 findings across
   66 rounds, with zero measured false-drops or false-keeps in 11 discrimination samples.

## 📚 Sources

All evidence is local instrumentation on this checkout; no external sources were fetched.

- `uv run python -m harness_maker.economics {doctor,report,stages,composition} --root .`
- `uv run python -m harness_maker.cli make . --audit` + `git status --porcelain`
- `uv run python -m harness_maker.cli health . --session-id "$HM_SESSION_ID"`
- `harness_maker.stage_spans.{read_events,_build_spans}` over `.claude/observability/stage-spans.jsonl`
- Direct reads of `.claude/observability/`: `second-opinion.jsonl`, `stage-agents.jsonl`,
  `review-*.jsonl`, `delegation.jsonl`, `auto-advance.jsonl`, `orphans-*.jsonl`,
  `run-verdicts.jsonl`
- Custom per-tool / per-command composition pass over
  `~/.claude/projects/-home-noel-harness-maker/*.jsonl` (59 files), reusing
  `economics_source.discover_transcript_dirs` + `context_composition._classify_user_text`
- Source reads: `worktree.py:4897-4922` (`_emit_stage_span`), `worktree.py:5704-5786`
  (`_span_end_session_id`, `_cli_span_end`), `stage_spans.py:174-229` (`_build_spans`),
  `tests/unit/test_ledger_isolation.py`

## 🔗 Related Internal Docs

- [[RESEARCH-context-carry-economics-2026-07-28]] — the 87.9%/70.0% main-loop carry baseline
- [[PLAN-economics-attribution-and-carry]] — the attribution model this audit exercises
- [[PLAN-harness-economics-observability]] — where the span ledger came from
- [[PLAN-harness-diet]] / [[PLAN-token-economy-step-pruning]] — prior surface-size cuts
- [[PLAN-wrapup-context-carry]] / [[PLAN-context-carry-discipline]] — prior carry work
- [[BASELINE-DELTA-workflow-time-token-savings]] — prior time/token baseline
- `[[wiki:architecture carry-is-a-main-loop-phenomenon]]` (2026-07-27)
- `[[wiki:architecture ledger-exclusions-and-test-isolation]]` (2026-08-17)
- `[[wiki:observability stage-agent-ledger-reconciled-against-transcripts]]` (2026-08-08)
- `[[fail:design observability-field-with-no-consumer]]` (count:2)
