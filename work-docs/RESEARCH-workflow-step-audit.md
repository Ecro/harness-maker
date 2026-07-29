---
type: research
task_slug: workflow-step-audit
status: complete
created: 2026-07-29
tags: [harness-maker, research, workflow, latency, subagents, stage-pruning]
mtime_warn_days: 7
libs_fetched: []
sources: [https://zylos.ai/research/2026-04-26-parallel-concurrency-agent-execution/, https://www.agentpatterns.ai/agent-design/agent-composition-patterns/, https://arxiv.org/pdf/2607.08010, https://ssojet.com/blog/parallel-sub-agent-coding-tools]
related_docs: ["[[RESEARCH-token-economy-step-pruning]]", "[[PLAN-token-economy-step-pruning]]", "[[PLAN-context-carry-discipline]]", "[[PLAN-workflow-overhead-post024]]"]
summary: "Collapse serial CLI round-trips into composite CLIs and fan out research/execute — do not cut interviews or gates"
---

# RESEARCH — Workflow step audit for development speed

## 🎯 Recommended Direction

**Cut *round-trips*, not *rigor*.** The seven stages spend their wall-clock on
two things the quality bar does not depend on: (a) long **serial chains of
deterministic CLI calls**, each one a full main-loop turn at 200–430K context,
and (b) **sequential gathering** in stages whose sources are independent and
could fan out. Every quality mechanism in the pipeline — the plan interview,
the ADRs, the test-reviewer gate, the consensus filter, the grade gate, verify's
fail-closed checks, the memory count++ machinery — can stay exactly as it is
while the pipeline gets substantially faster.

The canonical production workflow as rendered today (`exec-rev-wrap-ver`,
0.43.3) mandates **56 `!` shell round-trips**, including **4 redundant
`task-preflight` calls** and **4 `verification_cache` checks**. `res-spec-plan`
mandates **3 `memory_retrieve` calls, 5 `second_brain search` calls, 3
`task-preflight` calls and 3 copies of the 5-term inequality gate** — inside a
single fused command. None of that duplication buys quality; it buys latency.

There is one measured precedent for the fix already in this repo. `wrapup`
Steps 1–5.6 were delegated to the `stage-delegate` subagent on 2026-07-26
(`86556c6a`). Main-loop assistant turns per wrapup run before that change:
136, 111, 91, 245, 67, 329. After: **38, 46**. That is the mechanism this
research recommends generalizing — a subagent dispatch or a composite CLI turns
K main-loop turns into 1.

**What must not be cut** is listed explicitly in §Pitfalls. The prior
token-economy research already refuted the "delete stage prose" instinct
(prose is O(1) cached tokens; a turn is O(context)); this research reaches the
same conclusion from the latency side, which is why the two are compatible
rather than competing.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary — the
subject is this repo's own rendered stage prompts and their measured cost) plus
**Risk / compliance** (secondary — every proposed cut is scored against the
gate it might weaken). `--deep` was not set; no Phase 0 interview ran.

**Local capability × user artifact** (the discovery guard, applied to
harness-maker's *plugin users*, whose artifacts the stages produce and consume):

| Stage capability | User artifact it touches | Latency cost today |
|---|---|---|
| `research` multi-source gathering | `work-docs/RESEARCH-*.md`, `.claude/memory/`, Obsidian vault | 154 asst turns/run, all serial in the main loop |
| `spec` dual-file authoring + 3 validators | `specs/SPEC-*.md` + `.machine.yaml` | 3 separate validation round-trips |
| `plan` interview → ADRs → validator | `work-docs/PLAN-*.md` | 176 asst turns/run; PLAN re-read ~5× per task |
| `execute` TDD machine | source + tests | 285 asst turns/run — largest single stage |
| `review` 2-pass + consensus | `work-docs/REVIEW-*.md` | 91 turns/run — already the best-parallelized stage |
| `verify` 5/6 checks | `.claude/observability/verify-*.jsonl` | 13 `!` calls for ~1 judgment call |
| `wrapup` memory + single commit | `.claude/memory/`, git history, vault | 30 `!` calls; highest mean context (433K) |

## 📐 Measured baseline

**Turn attribution** (`harness_maker.economics stages`, 23,981 turns / $5,614):

| Stage | % turns | USD | carry | mean ctx |
|---|---|---|---|---|
| (unattributed) | 29.9% | 1,590 | 0.70 | 315K |
| `hm:execute` | 20.1% | 1,211 | 0.67 | 303K |
| `hm:review` | 18.1% | 1,052 | 0.66 | 326K |
| `hm:wrapup` | 12.6% | 787 | 0.82 | 433K |
| `hm:plan` | 10.2% | 518 | 0.45 | 193K |
| `hm:research` | 3.2% | 129 | 0.25 | 81K |
| `hm:verify` | 1.0% | 57 | 0.83 | 388K |
| `hm:spec` | 0.9% | 76 | 0.43 | 273K |

**Active wall-clock** (47 local transcripts, 4,030 active minutes, inter-entry
gaps > 300 s treated as idle and excluded):

| Segment | active min | % | runs | asst turns/run |
|---|---|---|---|---|
| `/compact` | 934 | 23.2% | 11 | 391 |
| `/hm:execute` | 852 | 21.1% | 14 | 285 |
| `/hm:wrapup` | 587 | 14.6% | 17 | 181 |
| `/hm:research` | 498 | 12.4% | 12 | 154 |
| `/hm:plan` | 391 | 9.7% | 9 | 176 |
| `/hm:review` | 211 | 5.2% | 9 | 91 |

Two caveats, stated because they change how the table should be read:
1. **Attribution is adjacency-based** — a segment runs from one `<command-name>`
   to the next, so trailing free-form work inflates the preceding stage. The
   *ranking* is robust; the absolute per-run figures are upper bounds.
2. **`/compact` at 23.2% is a boundary artifact**, not a stage. Post-compaction
   turns belong to whatever stage was interrupted, so the real stage shares are
   higher than shown. It is also an independent signal that stages routinely
   overrun the context window — which is itself a consequence of carry.

**Structurally mandated round-trips** (counted in the rendered
`.claude/commands/hm/*.md` at 0.43.3):

| Stage | `!` shell calls | subagent dispatches |
|---|---|---|
| wrapup | **30** | 1 (+ N judgment-reviewer) |
| execute | 14 | 1 per PLAN phase |
| verify | **13** | 0 |
| plan | 10 | 4 |
| research | 8 | 0 |
| review | 7 | 2N+1 (parallel) |
| spec | 6 | 0 |
| `exec-rev-wrap-ver` (fused) | **56** | — |
| `res-spec-plan` (fused) | 18 | — |

**Key asymmetry:** `review` does the most analytical work of any stage and has
the **fewest** main-loop turns per run (91) — because its work happens in
parallel subagents whose turns are not main-loop turns. `wrapup` does the least
analytical work and had 181 — because its work was a serial CLI chain. That
asymmetry *is* the finding.

## 🛠️ Approaches Found

### Approach A — Composite deterministic CLIs (collapse serial chains)

| Field | Content |
|---|---|
| Approach | Replace ordered runs of deterministic `!` calls with one CLI that runs them and returns one JSON receipt |
| Assumption | The intermediate outputs are not needed for LLM judgment — only the final verdict is |
| Evidence | `verify` is 13 `!` calls for 5 checks of which only Check 1b is a judgment call; `wrapup` Steps 6→7.7 are 7 fixed-order git operations; `spec` Step 4/4/4.5 are 3 validators over the same two files |
| Trade-off | Less step-by-step visibility on failure — mitigated by a per-step JSON receipt and verbatim stderr on the failing step (what the prose already does) |
| Compatibility | Native: the CLI-owns-mechanism / LLM-owns-judgment split is the project's stated architecture (CLAUDE.md §CLI 와 slash 명령의 책임 분리) |
| Risk | **low** |

Concrete targets, with the turn count they remove per pipeline run:

| Target | Today | After | Δ turns |
|---|---|---|---|
| `verify run --root .` (Checks 1a,2,3,4,5 + JSONL) | 13 | 1–2 | −11 |
| `wrapup land` (stage → commit → pop → drain → task-land → fold memory) | 7 | 1 | −6 |
| `spec_machine check --all` (validate + cross_validate + spec_quality) | 3 | 1 | −2 |
| execute Phase D `lint; type; test` in one call | 3/phase | 1/phase | −2N |
| `second_brain search` multi-type in one call (research 2, plan 3, review 2) | 7 | 3 | −4 |
| plan Step 1.5 loop-mode probe folded into `task-preflight` output | 1 | 0 | −1 |
| plan Step 6 read-back → `plan_lint` CLI | 1 full-PLAN read | 1 cheap | carry, not turns |

### Approach B — Fan-out where sources are independent

| Field | Content |
|---|---|
| Approach | Dispatch parallel subagents for independent gathering / independent PLAN phases, in one message |
| Assumption | The subtasks are genuinely independent (disjoint files, or read-only) |
| Evidence | External: fan-out/fan-in measured at **36–50% wall-clock reduction** in production agent pipelines ([Zylos](https://zylos.ai/research/2026-04-26-parallel-concurrency-agent-execution/)); independence is the stated precondition ([AgentPatterns](https://www.agentpatterns.ai/agent-design/agent-composition-patterns/)). Internal: `review` already does this and is the cheapest big stage per run |
| Trade-off | Subagent digests can drop the decisive detail; parallel writers can revert each other; concurrency hits rate limits (recommended cap **3–5**, [SSOJet](https://ssojet.com/blog/parallel-sub-agent-coding-tools)) |
| Compatibility | The mechanism exists: `Explore`, `general-purpose`, `executor`, `stage-delegate` agents are all installed; PLAN phases already carry `depends_on` / `parallel_group` / `merge_hazards` |
| Risk | **medium** |

Two concrete sites:

1. **`research` Phase 1** — 7 source classes (codebase grep, prior work-docs,
   memory, second brain, library docs, web, refdocs) executed serially in the
   main loop, every result carried for the rest of the session. Fan out 3–4
   read-only agents in one message; each returns a bounded digest **with
   citations and verbatim key snippets**; the main loop opens originals only for
   the one or two decisive claims. Research is 12.4% of active wall-clock and
   154 turns/run — the largest fan-out-shaped target in the pipeline.
2. **`execute` Step 1.5** — the "parallel split assessment" already exists but
   is **advisory prose with no mechanism**: it tells the model to decide, then
   never gives it a dispatch path. The PLAN metadata needed to gate it
   (`merge_hazards: none`, disjoint `scope`) is mandatory and already written by
   every plan. Turning that assessment into an actual per-phase `executor`
   fan-out (one worktree each) is the largest single wall-clock lever in the
   pipeline, since execute is 21.1% of active time.

### Approach C — De-duplicate cross-stage re-derivation

| Field | Content |
|---|---|
| Approach | Compute task context once, persist a small digest, have later stages read the digest instead of re-deriving |
| Assumption | The inputs are stable within one task (memory tiers, vault notes, PLAN body, diff classification) |
| Evidence | `res-spec-plan` renders 3× `memory_retrieve`, 5× `second_brain search`, 3× inequality gate, 3× `task-preflight`; `exec-rev-wrap-ver` renders 4× `task-preflight` + 4× `verification_cache`; the PLAN document is read in plan Step 6, execute Step 1, review, verify and wrapup — ~5 full reads per task |
| Trade-off | A cached digest can go stale — and a silent stale read is worse than a slow fresh one (this is the CLAUDE.md 2026-06-08 absent-case failure class) |
| Compatibility | Precedent exists and works: `verification_cache` already mediates the suite between verify and wrapup; RESEARCH→PLAN frontmatter caching is described in the research stage as "the single biggest token saver in the workflow" |
| Risk | **medium** — every cache needs an explicit staleness rule and an explicit absent-case |

Redundancy inventory (each line is a distinct duplicated computation):

| # | Duplication | Where | Verdict |
|---|---|---|---|
| 1 | `memory_retrieve` × 3 | research, spec Step 1, plan | collapse to 1 per task |
| 2 | `second_brain search` × 7 | research 2, plan 3, review 2 | 1 call per stage, multi-type |
| 3 | `task-preflight` × 4 | every stage of `exec-rev-wrap-ver` | keep 1 claim; the per-stage `--stage` value is registry telemetry, not a gate |
| 4 | Full suite × up to 7 | execute Phase D **per PLAN phase**, verify Check 2, wrapup Step 2 | targeted tests per phase; **one** full suite, owned by verify |
| 5 | Skip heuristic × 2 | spec Step 0, plan Step 0 (same 4 criteria) | one triviality verdict, recorded once |
| 6 | 5-term inequality gate × 3 | research 0.5, spec 2.5, plan Step E | keep the mechanism; in a fused run, evaluate once per interview surface |
| 7 | Drift verdict read × 2 | verify Check 1a, wrapup Step 3 | identical read; one owner |
| 8 | `high_diff classify` × 2 | plan Step 4(pre), review Step 3.5 | same diff → one classification |
| 9 | Full PLAN read × ~5 | plan Step 6, execute, review, verify, wrapup | in a fused workflow it is already in context; re-reads are pure duplication |
| 10 | Two false-positive filters in series | review Pass 1.5 verifier **and** Pass 2 | see Open Questions — needs measurement before merging |

## 📋 Per-step verdict table

Legend: **KEEP** (load-bearing) · **MERGE** (fold into an adjacent call) ·
**DELEGATE** (move off the main loop) · **REVISE** (change the rule, keep the
intent) · **GATE** (make conditional).

### research
| Step | Verdict | Note |
|---|---|---|
| Session context loading (memory) | KEEP | 1 call |
| Second Brain × 2 | MERGE | one multi-type call |
| Task worktree preflight | KEEP | 1 claim per task, not per stage |
| Phase 0 refinement interview | KEEP | already default-OFF |
| Phase 0.5 inequality gate | KEEP | `--deep` only |
| Phase 0.75 discovery lens | KEEP | free — pure judgment, 0 turns |
| **Phase 1 multi-source gathering** | **DELEGATE** | fan out 3–4 read-only agents; largest research lever |
| Phase 2 analysis | KEEP | 1 turn |
| Phase 3 write document | KEEP | use `Edit` on re-write, never full `Write` |
| Phase 4 validation STOP | KEEP | autopilot already bypasses it |

### spec
| Step | Verdict | Note |
|---|---|---|
| Step 0 skip heuristic | MERGE | shared with plan Step 0 |
| Step 1 knowledge retrieval | GATE | skip the memory + grep calls when a fresh RESEARCH doc exists — but define the stale case explicitly |
| Step 2 six categories | KEEP | quality core |
| Step 2.1.5 oracle elicitation | KEEP | this is the anti-circular-oracle mechanism |
| Step 2.5 inequality gate | REVISE | fold in as a filter on the 6-category loop rather than a separate phase that invites an extra round |
| Step 3 / 3.5 dual-file write | KEEP | contract |
| Step 4 validate + cross-validate + 4.5 quality | **MERGE** | one `check --all`, 3 turns → 1 |
| Step 5 status update | KEEP | 1 edit |

### plan
| Step | Verdict | Note |
|---|---|---|
| Second Brain × 3 | MERGE | 3 → 1 |
| Step 0 skip heuristic | MERGE | see spec |
| Step 1 internal draft | KEEP | already short-circuited in loop-mode |
| Step 1.5 loop-mode probe | MERGE | fold into `task-preflight` JSON |
| Step 1.7 spec-need (spec-driven) | MERGE | `marker-read`/`marker-fresh`/`op-check` → one `spec_need resume`; up to 5 round-trips today |
| Step 2 / 3.0 / 3 interview | **KEEP** | the reason execute is deterministic; lowest carry (0.45) of any working stage |
| Step 4 second opinion × 2 models | REVISE | issue both in one message (independent) |
| Step 4 plan-validator | KEEP | see Open Questions on parallelizing it with the models |
| Step 5 write PLAN | KEEP | |
| Step 6 verify-write read-back | REVISE | replace the full-body re-read with a `plan_lint` CLI asserting the same invariants |

### execute
| Step | Verdict | Note |
|---|---|---|
| Step 0/preflight | KEEP | |
| Step 1 load PLAN | KEEP | |
| **Step 1.5 parallel split** | **REVISE → mechanism** | today it is advisory prose with no dispatch path; gate a real fan-out on `merge_hazards: none` |
| Phase A author tests | KEEP | |
| Phase A.5 test-reviewer | MERGE | one dispatch over the union of phases rather than one per phase — the template already says it adjudicates the union |
| Phase B RED gate | KEEP | cheap, high value |
| **Phase C "check after each edit"** | **REVISE** | check after each *file / coherent unit*; the current rule doubles the turn count of every implementation phase |
| **Phase D full suite per phase** | **REVISE** | run targeted tests (`test_dep_map.build_test_hints()` — already named in the stage's own Purpose and contradicted by Phase D's text) + lint/type in **one** call; full suite once, owned by verify |
| Step 4 / 4.5 / 5 exit + finalize + crumb | GATE | on the flag-on task-worktree path several of these are structural no-ops that still cost a turn to discover |

### review
| Step | Verdict | Note |
|---|---|---|
| Step 1 reviewer selection | KEEP | conditional routing already prunes |
| Step 2 drift gate | KEEP | single owner — do not duplicate downstream |
| Step 2.5 silent-intent-miss | KEEP | cheap telemetry |
| Pass 1 (N parallel, redacted) | KEEP | the +47pp precision result is attached to the *redaction*, not to the pass count |
| Pass 1.5 verifier | KEEP | |
| **Pass 2 (N parallel, restored)** | **MEASURE** | second FP filter in series; the telemetry to A/B it already exists (`verifier_false_drop_n` / `verifier_false_keep_n`) |
| Step 3.5 second opinion × 2 | REVISE | one message, two calls |
| Step 4 consensus filter | KEEP | |
| Grade gate + auto-fix loop | KEEP | round 2+ re-review is already scope-selective — enforce it |
| Telemetry emit | KEEP | 1 call |

### verify
| Step | Verdict | Note |
|---|---|---|
| Check 1a drift verdict | MERGE | into the composite CLI |
| Check 1b SPEC coverage | KEEP | the one genuine judgment call in the stage |
| Check 2 regression smoke (4 commands) | MERGE | one composite; cache check already deterministic |
| Check 3 structural delta | MERGE | deterministic |
| Check 4 security findings | MERGE | deterministic |
| Check 5 worktree cleanliness | MERGE | deterministic |
| Check 6 spec-need (spec-driven) | MERGE | 2 CLI calls → 1 |
| Step 0.5 delegation | **ENABLE** | the template supports it; `harness.yaml delegation.stages` lists only `wrapup` |
| Advisory probe A1 | KEEP | free |

### wrapup
| Step | Verdict | Note |
|---|---|---|
| Step 0.5 delegate 1–5.6 | KEEP | measured: ~123 → ~42 main-loop turns |
| Step 1 pre-flight | KEEP | |
| Step 2 final verification | KEEP | cache-mediated |
| Step 3 drift read | MERGE | same read as verify Check 1a |
| Step 3.5 machine-SPEC write-back (+ find-unbound, judgment-reviewer, mark-judged, find-unjudged) | GATE | already skip-when-absent; keep the single existence test at the top |
| Step 4 PLAN status | KEEP | 1 edit |
| Step 5.1–5.3 memory + count++ | **KEEP** | load-bearing; the search-before-write step is what makes recurrence detection work |
| Step 5.6 promotion | KEEP | must-evaluate per ADR-001 |
| **Steps 6 → 7.7 git tail** | **MERGE** | 6–7 fixed-order CLI turns at 433K context → one `wrapup land`; the commit message is the only LLM input |
| Step 8 push | KEEP | never automatic |

## ⚠️ Pitfalls

1. **Do not prune by line count.** Already refuted with measurement in
   `[[RESEARCH-token-economy-step-pruning]]`: stage prose is O(1) cached tokens,
   a turn is O(context). Deleting instructions loses behavior and saves nothing.
   The withdrawn ADR-017 of `[[PLAN-token-economy-step-pruning]]` is the
   cautionary case — a documentation-only trim that deleted runtime
   instructions.
2. **Batching edits without checks compounds errors.** The Phase C
   "check after each edit" rule exists for a reason. The revision must bound the
   batch (one file / one coherent unit), not remove the check.
3. **A removed redundant read is an absent-case black hole.** CLAUDE.md's
   2026-06-08 learned correction, count:8, most-recurring: any gate that
   activates on an optional field must define the absent case. If `spec` skips
   its memory load when a RESEARCH doc exists, a *stale* RESEARCH silently
   degrades the SPEC. Every cache introduced here needs (a) a staleness rule,
   (b) an explicit absent-case, (c) a test for the absent case, not just the
   present one.
4. **Subagent digests lose the decisive detail.** The fix is to require
   citations plus verbatim snippets and to open originals for the claims that
   decide the recommendation — the same discipline `review`'s read-budget
   already imposes via `[elided: …]` markers.
5. **Parallel writers revert each other.** The `execute` fan-out must assign
   explicit file ownership and give each worker its own worktree; the PLAN's
   `merge_hazards` field is the gate, and `none` is the only safe value.
6. **Fan-out has a ceiling.** Recommended cap is 3–5 concurrent workers before
   rate limits dominate ([SSOJet](https://ssojet.com/blog/parallel-sub-agent-coding-tools));
   unbounded fan-out converts a latency win into a retry storm.
7. **Composite CLIs must report their own exit status to a file.** Background
   and wrapped runs have been observed reporting `exit 0` for failed work in
   this project; a composite that swallows a mid-chain failure is worse than the
   chain it replaces.
8. **Config drift found while auditing:** this repo sets
   `default_workflow: exec-rev-wrap-ver` (**commit, then verify**), while the
   shipped Production default is `exec-rev-ver-wrap` (`interview.py:136`), and
   `exec-rev-ver-wrap` is not even defined in this repo's `workflows:` map. With
   the current order a verify FAIL arrives *after* the commit has landed, which
   costs an extra amend/fix cycle. Verify-before-commit is both safer and
   faster.
9. **The local render is stale relative to `9f809f3f`** (`feat(fuse): hoist
   shared stage prose`). The 4× repeated preflight *prose* in the rendered
   `exec-rev-wrap-ver` predates the hoist; the 4× repeated preflight *command*
   is by design (ADR-006 keeps one `--stage` receipt per stage). Re-render
   before measuring the fused-command baseline again, or the improvement will be
   double-counted.

## ❓ Open Questions

1. **Does merging review's Pass 2 into Pass 1.5 preserve precision?** The
   telemetry schema already carries `verifier_false_drop_n` /
   `verifier_false_keep_n` / `fixture_label`, so this is measurable rather than
   arguable — but are there enough labelled fixture runs in
   `.claude/observability/review-*.jsonl` to decide? If not, the change needs a
   fixture campaign first and should not ship on judgment.
2. **What is the correct staleness rule for a per-task context digest?** The
   `verification_cache` precedent hashes source/tests/lockfiles/tool-config/CI.
   A memory+vault digest has no equivalent fingerprint — is mtime + task slug
   enough, or does this need an explicit invalidation on every `wrapup`?
3. **Should `plan-validator` run concurrently with the second-opinion models?**
   Today the models' findings are *injected* into the validator prompt
   (ADR-005/011 ownership contract). Parallelizing means reconciling in the main
   loop instead. That is an ADR-level change to a contract that exists to stop
   the validator shelling out — worth it only if the serial hop is measurably
   expensive.
4. **How many `execute` PLAN phases justify a worktree fan-out?** Each worktree
   costs setup time and disk. Below what phase count is serial faster?
5. **Which STOP boundaries survive under `autonomy.level: auto_safe`?** Several
   proposed merges (verify composite, wrapup land) change what the operator sees
   between steps. The gates that must remain human are worth naming before, not
   after.
6. **Does the `--stage` argument to `task-preflight` have a consumer beyond the
   registry row?** If it is telemetry only, three of the four calls in
   `exec-rev-wrap-ver` are removable; if a downstream check reads it, they are
   not.
7. **`spec` is effectively unused in this repo** (0 invocations in the 47-transcript
   window, 0.9% of turns) because `dev_mode: task-driven`. Is optimizing it worth
   any effort here, or is it purely a downstream-user concern?

## 📚 Sources

- [Parallel Concurrency in Production AI Agents: DAG Scheduling, Fan-Out/Fan-In, and Coordination at Scale — Zylos Research](https://zylos.ai/research/2026-04-26-parallel-concurrency-agent-execution/) — fan-out/fan-in measured at 36–50% wall-clock reduction.
- [Agent Composition: Chains, Fan-Out, Pipelines, Supervisors — AgentPatterns.ai](https://www.agentpatterns.ai/agent-design/agent-composition-patterns/) — independence as the precondition for fan-out.
- [Tool-Making and Self-Evolving LLM Agents in Low-Latency Systems — arXiv 2607.08010](https://arxiv.org/pdf/2607.08010) — replacing a subagent loop with direct tool calls cut p50 latency 42% and sub-agent turns 45%.
- [6 Coding Agents That Actually Run Sub-Agents in Parallel — SSOJet](https://ssojet.com/blog/parallel-sub-agent-coding-tools) — practical fan-out cap of 3–5 concurrent workers.
- Internal measurement: `uv run python -m harness_maker.economics stages --root .` (23,981 turns / $5,614).
- Internal measurement: per-stage active wall-clock over 47 transcripts in `~/.claude/projects/-home-noel-harness-maker/` (300 s idle-gap cap).
- Internal counts: `!` shell calls and duplicated CLI invocations in the rendered `.claude/commands/hm/*.md` at 0.43.3.

## 🔗 Related Internal Docs

- [[RESEARCH-token-economy-step-pruning]] — the cost-side companion; establishes that prose is O(1) and turns are O(context).
- [[PLAN-token-economy-step-pruning]] — Phases 1–2 landed; Phases 3–5 (reviewer read budget, fused compaction, unattributed breakdown) partly shipped since.
- [[PLAN-context-carry-discipline]] — the two carry rules now in CLAUDE.md, and the meter that judges them.
- [[PLAN-workflow-overhead-post024]] — the `verification_cache` precedent for cross-stage suite reuse.
- [[wiki:architecture harness-economics-observability]] — the instrument used for the turn-attribution table.
