---
type: research
task_slug: harness-diet
status: complete
created: 2026-08-05
tags: [harness-maker, research, context-economics, prompt-scaffolding, memory-tiers, opus-5]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://arxiv.org/html/2603.05344v1
  - https://github.com/ai-boost/awesome-harness-engineering
related_docs:
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
  - "[[PLAN-token-economy-step-pruning]]"
  - "[[PLAN-workflow-step-audit]]"
  - "[[PLAN-context-carry-discipline]]"
summary: "Cut behavior scaffolding (fused workflows, verify stage, reviewer fan-out), keep state scaffolding (SPEC, memory, worktree)"
---

# RESEARCH — harness-maker diet

## 🎯 Recommended Direction

**Cut behavior scaffolding; keep state scaffolding.**

The single sharpest dividing line the evidence supports is *what the scaffolding is for*:

- **State scaffolding** — artifacts that survive a context window (SPEC/PLAN/RESEARCH files,
  `.claude/memory/`, worktree + branch lifecycle, receipts, harness.yaml). Anthropic's
  long-running-agents guidance is unambiguous that this is still load-bearing on frontier
  models, and this repo's own economics agree: stages that read a prior deliverable are the
  cheap ones (`hm:research` $44, `hm:spec` $15).
- **Behavior scaffolding** — prose that tells the model to do things it now does unprompted:
  separate verification stages, "double-check", multi-reviewer fan-out to cross-check its own
  output, pre-fused stage sequences that hard-code a call order. Anthropic's Opus 5 prompting
  guide says in as many words to delete these, and names harness scaffolding explicitly:
  *"The same applies to legacy harness scaffolding that adds separate verification steps."*

Applied to this repo, three cuts are supported by measurement, not just by the model guide:

1. **Delete the 5 fused workflow commands.** They are 512,808 of 876,301 rendered command
   bytes (**58.5%**) and have **zero** recorded invocations across the entire economics
   history, while autopilot has already performed **40** successful stage advances.
2. **Retire `/hm:verify` as a stage and `verify-before-completion` as a skill.** $11 / 0.4%
   of measured spend, 54 turns, and it is the exact pattern the Opus 5 guide names.
3. **Shrink the review apparatus.** `hm:review` is $658 (22.4% of $2,930 measured) at a
   **VERIFY:PRODUCE turn ratio of 4.4:1** — the highest in the harness. Two second-opinion
   models are mandatory per review *and* per plan, on top of multi-reviewer consensus and a
   separate false-positive-reduction pass.

Impact is **internal maintainer value**, not user-facing feature value: less prompt carried per
turn, fewer duplicate render targets, faster stages. It does not add capability.

**A caveat stated up front, because it is the binding trade-off:** the two Anthropic sources
disagree at the surface. The long-running-agents post argues frontier models need *more*
structure; the Opus 5 guide argues to *remove* instructions. They are reconcilable only along
the state/behavior line above, and that reconciliation is my **inference**, not a cited claim.
If it is wrong, the safe failure mode is cutting too much review rigor from a harness whose
whole selling point is rigor — so the plan should stage the cuts by measured usage (dead
surfaces first), not by the model guide alone.

## 🔍 Refinement Decisions

`--deep` was not set; no Phase 0 interview ran.

**Discovery lens:** (1) Technical architecture / implementation — rendered-surface inventory
and economics attribution over this repo; (2) User-workflow / product opportunity — how the
harness is actually invoked (telemetry) vs. how it is designed to be invoked; (3) Risk —
what breaks if a defense layer is removed. The Research/benchmark lens was used only for the
external model-guidance question and is not the sole basis of any recommendation.

**Local capability × user artifact mapping** (what this harness offers vs. what a solo
maintainer actually keeps):

| User artifact they already maintain | Harness capability that touches it | Observed use | Diet verdict |
|---|---|---|---|
| git history, branches | worktree task lifecycle, squash-land | heavy (all stages) | **keep** |
| `work-docs/PLAN\|SPEC\|RESEARCH` | stage deliverables, frontmatter chaining | heavy | **keep** |
| `.claude/memory/wiki+failures` | wrapup fold, `memory_retrieve` | writes heavy, reads noisy | **keep + evict** |
| Obsidian vault | `second_brain promote` (wrapup Step 5.6) | wrapup-only by design | keep, unchanged |
| Codex / Antigravity CLIs | mandatory second opinion on review + plan | 2 models × 2 stages | **make optional** |
| pre-fused command sequences | 5 fused `/hm:` commands | **zero invocations** | **cut** |

## 📊 Measured Baseline

All figures measured on this repo, 2026-08-05, from
`harness_maker.economics` and direct byte counts. Reproduce with
`uv run python -m harness_maker.economics stages --root .`.

### Per-stage spend

| Stage | USD | Share | Turns | Carry | VERIFY:PRODUCE turns |
|---|---:|---:|---:|---:|---|
| `hm:execute` | 705 | 24.1% | 3121 | 0.78 | 323 : 410 |
| `hm:review` | 658 | 22.4% | 2624 | 0.71 | **1373 : 310 (4.4×)** |
| *(unattributed)* | 612 | 20.9% | 2923 | 0.71 | 244 : 393 |
| `hm:wrapup` | 470 | 16.0% | 1847 | **0.84** | 141 : 217 |
| `hm:plan` | 346 | 11.8% | 1640 | 0.59 | 436 : 223 |
| `hm:research` | 44 | 1.5% | 301 | 0.44 | 17 : 23 |
| `hm:make` + `harness-maker:make` | 54 | 1.8% | 264 | — | — |
| `hm:spec` | 15 | 0.5% | 72 | 0.67 | 0 : 13 |
| `hm:verify` | **11** | **0.4%** | 54 | 0.82 | 42 : 0 |
| `hm:metrics` | 10 | 0.3% | 39 | 0.73 | — |
| **TOTAL** | **2930** | | | | |

**No fused workflow (`hm:exec-rev`, `hm:plan-exec-rev`, `hm:res-spec-plan`,
`hm:exec-rev-wrap`, `hm:exec-rev-wrap-ver`) appears in the attribution table at all.**
The attributed stage set is exactly the atomic stages plus utilities.

Autopilot ledger (`.claude/observability/auto-advance.jsonl`, 80 rows):
`advanced: 40`, `gate_blocked: 36`, `halted_cap: 1`. Autopilot is live and doing the
job the fused commands were built for.

### Context composition (whole measured history, 26.96M chars)

| Category | Share |
|---|---:|
| `tool_call_input` | 39.6% |
| `tool_result` | 29.7% |
| **`slash-command-body`** | **15.1%** (4.07M chars) |
| `task-notification` | 6.7% |
| `assistant_text` | 5.4% |
| `system-reminder` | 2.3% |

`write_after_read`: 407 write calls, **27.8%** duplicate chars (887,934) — the
CLAUDE.md "use Edit, not Write" rule is measurably not holding.

Within Bash: `grep/rg` 10.8%, `file inspection` 6.4%, `pytest` 4.2%,
`harness_maker CLI` 3.6%.

### Rendered surface inventory

| Group | Files | Bytes | Note |
|---|---:|---:|---|
| `.claude/commands/hm/` total | 20 | 876,301 | |
| — 5 fused workflows | 5 | **512,808 (58.5%)** | zero invocations |
| — 7 atomic stages | 7 | 258,745 | all invoked |
| — `loop` + `loop-p5-batch` | 2 | 58,251 | |
| — 6 utility commands | 6 | 46,497 | |
| `.claude/skills/` | 11 | 57,271 | `second-opinion-gate` alone 17,124 |
| `.claude/agents/` | 15 | 113,949 | 10 of 15 are reviewers/verifiers |
| `.agents/skills/` (Codex) | 26 dirs | 385,997 | 15 `hm-*` incl. 5 fused dupes |
| `src/.../templates/stages/*.j2` | 7 | 209,920 | source of truth |

**Amplification factor ≈ 6×**: 210KB of stage source renders to ~1.26MB of shipped
prompt across Claude + Codex targets. Fusion and dual-target render are the two
multipliers; only fusion is discretionary.

### Memory tiers

| Tier | Bytes | Entries | Avg entry | Pre-July share | Never recurred |
|---|---:|---:|---:|---:|---:|
| `failures.md` | 266,104 | 156 | 1,672 B | **67%** (104/156) | **87%** (135, `count:1`) |
| `wiki.md` | 297,483 | 212 | 1,358 B | **81%** (170/210 dated) | n/a (no count field) |

Recurrence distribution in `failures.md`: `count:1`→135, `2`→13, `3`→5, `4`→1,
`6`→1, `13`→1. **Eight entries (5%) carry all the recurrence signal.**

There is **no eviction, TTL, archival, or decay mechanism** anywhere in
`memory_md.py` / `memory_retrieve.py`. The only bound is a retrieval-side
`byte_cap=10240`. Growth is monotonic by construction; wrapup appends, nothing
ever removes. The one relevant lever shipped 2026-07-05 —
`memory_md consolidate` — is **opt-in and exact-slug-only** (merges duplicate
slugs; it does not evict stale entries).

**Retrieval quality is the live symptom, not file size.** The `memory_retrieve`
call at the top of *this* session, on the topic "harness diet / fused workflow
removal / memory pollution", returned: PyPI trusted publishing, OSS launch
readiness, README install prompts, and worktree finalize conflicts. One of six
hits (`cursor-reads-the-claude-command-render`) was relevant. That is a lexical
prefilter over 368 entries doing what lexical prefilters do at that scale.

### Instruction-density in shipped prompts

Counted across `.claude/commands/hm/`: `NEVER` ×386, `MUST` ×177,
`consensus` ×204, `verify` ×172, `subagent` ×22. Across stage templates:
`STOP` ×66, `NEVER` ×84, `Do NOT` ×64, `consensus` ×90.

Separately: **no rendered `/hm:` command carries a frontmatter `description:`.**
Every one of the 20 falls back to its first body line, so the tool listing shows
14 commands whose descriptions are the *identical* string
`"> **Before you begin — outline your plan.** First check whether an autoloop is"`.
This is visible in this session's own skill listing. The byte cost is trivial
(~2KB); the cost is that the model cannot tell the commands apart from the
listing alone.

### What shipped since 2026-07-01 (105 commits: 42 chore, 26 fix, 23 feat, 6 docs, 4 test, 4 refactor)

The July+ trajectory is already a diet, but an *observability-first* one — the
harness built the instruments before it cut anything. Grouped:

| Theme | Commits | Diet relevance |
|---|---|---|
| **Economics / attribution** | `feat(economics)` ×4 (07-25→07-29), `feat(metrics)` ×3, `feat(context)` 07-28 | **Enables this diet.** The per-stage table above exists because of these. Keep all. |
| **Workflow collapse** | `feat(workflow): collapse four stages' fixed call sequences into single calls` (07-29), `feat(fuse): hoist shared stage prose into a per-workflow preamble` (07-27) | Already the first diet increment. The fuse-preamble hoist *reduced* fused-command bytes — but the fused commands are still unused, so it optimized dead surface. |
| **Review apparatus growth** | `feat(review)` ×4 (07-01→08-01), `feat(second-opinion): generalize codex→multi-model` (07-09) | **Net additions** to the most expensive stage. This is the subsystem that grew while everything else shrank. |
| **Hooks correction** | `feat(hooks)` Stage-2/Stage-3 (07-17, 07-18), retire dead `hooks.json` | Correcting the 2026-07-17 finding that Claude Code never read `.claude/hooks/hooks.json`. Real dead weight removed. |
| **Autopilot simplification** | `refactor(autopilot): remove guard_when axis` + `refactor(hooks): retire autopilot_guard` (07-21), after adding `guard_when` on 07-18 | Added and removed within 3 days — evidence the harness *can* shed an axis cleanly. Precedent for Approach A. |
| **Memory** | `feat(memory)`: stemmer recall (07-05), opt-in `consolidate` (07-05), `refactor(memory): session tier checkpoint-only` (07-10) | Recall and dedup improved; **eviction still absent.** Approach C is the unfinished half. |
| **Delegation** | `feat(delegation): make the wrapup gate resolvable` (07-29) | Targets `hm:wrapup`'s 0.84 carry — the right target, keep. |

Two observations that bear on the diet: (a) the economics work is what makes any
cut defensible, so it is the one area that should not be trimmed; (b) `hm:review`
is the only stage that has been *added to* every month since July while also being
the most expensive — the growth and the cost are the same fact.

## 🛠️ Approaches Found

### Approach A — Dead-surface deletion (usage-driven)

| Field | Content |
|---|---|
| **Approach** | Delete only what telemetry proves unused: 5 fused workflows, `/hm:verify` + `verify-before-completion`, the 5 Codex `hm-*` fused dupes. Add frontmatter `description:` to every rendered command. |
| **Assumption** | This repo's own usage is representative of downstream harnesses. |
| **Evidence** | Zero fused invocations across the full economics history; 40 autopilot advances; `hm:verify` at 0.4% / 54 turns. Opus 5 guide names separate verification steps explicitly. |
| **Trade-off** | Removes an escape hatch for IDEs where autopilot does not exist. Autopilot's auto-advance block is **Claude-Code-only** by construction (`Skill` tool + marker); Cursor and Codex sessions fall through to the STOP banner. Deleting fused commands makes multi-stage runs manual on those targets. |
| **Compatibility** | High. `workflows:` is a `harness.yaml` key and fused rendering is already conditional; `RESERVED_WORKFLOW_NAMES` and `interview.py` preset tables would shrink. `default_workflow: exec-rev-wrap` in `models.py:1160` is a schema default that needs a migration path. |
| **Risk** | **low** — for Claude Code. **medium** for the Cursor/Codex story. |

### Approach B — Behavior-scaffolding pass (Opus-5-guide-driven)

| Field | Content |
|---|---|
| **Approach** | Sweep every stage template for instructions Opus 5 already performs: self-verification steps, "report everything then filter" already-correct patterns, subagent-to-double-check dispatch, mandatory second opinion on both review *and* plan. Reduce reviewer fan-out; make `second_opinion.models` opt-in rather than mandatory-per-stage. |
| **Assumption** | Opus 5's stated review precision/recall makes redundant verifier passes net-negative. |
| **Evidence** | Guide: *"do not use subagents to verify or double-check your own work"*; *"Claude Opus 5 verifies its own work without being told to… removing them reduces wasted tokens with no loss in quality"*. Locally: `hm:review` VERIFY:PRODUCE = 4.4:1, $658. |
| **Trade-off** | The same guide contains a **counter-instruction** that argues for keeping part of the apparatus: *"If your review prompt says 'only report high-severity issues' or 'be conservative,' the model may follow that instruction literally… ask it to report everything and filter in a separate pass instead."* That is precisely `code-verifier` mode A. So the reduce-pass survives; what does not survive is *N independent reviewers cross-checking each other*. |
| **Compatibility** | Medium. The k-of-2 consensus threshold, the PIDA acceptance gate, and the auto-fix loop's monotonic lattice are interlocked (CLAUDE.md documents a P0 that fired when one piece was changed alone). |
| **Risk** | **high** — this is the harness's differentiator and its most tangled subsystem. Cross-model second opinion has a documented case (fleet C3) where Codex caught a P0 two Claude reviewers missed. |

### Approach C — Memory eviction + retrieval upgrade

| Field | Content |
|---|---|
| **Approach** | Add a decay/eviction policy to `memory_md`: archive `count:1` entries older than N days into `.claude/memory/archive/`, keep everything `count>=2` permanently. Raise `memory_retrieve` recall by reranking over a smaller, higher-signal corpus. |
| **Assumption** | An entry that has not recurred in 60+ days is unlikely to recur, and its retrieval-slot cost exceeds its option value. |
| **Evidence** | 87% of failures never recurred; 67% predate Opus 5's 2026-07-24 ship date; measured retrieval returned 1/6 relevant hits on this session's own topic. No eviction mechanism exists in code. |
| **Trade-off** | Failures are the harness's institutional memory and archiving is lossy in practice even when reversible in principle — nobody reads `archive/`. The 8 high-`count` entries prove the mechanism *does* catch repeats, and an entry at `count:1` today can become `count:2` tomorrow. Also: "written for a weaker model, now obsolete" is an **assumption**, not a measured property — most entries in `failures.md` are *system* invariants (schema drift, marker discipline, worktree races), not model-capability workarounds. Deleting them because the model got smarter would be a category error. |
| **Compatibility** | High — `memory_md` already owns write/dedup and shipped an opt-in `consolidate` in 0.36-era. |
| **Risk** | **medium**. Reversible if archive-not-delete. |

### Synthesis — ordering

Do **A** first (dead surface, low risk, largest byte win), **C** second (bounded and
reversible), **B** last and incrementally (highest spend, highest risk, most
interlocked). Do not do B in the same change as A — a review-apparatus regression
would be indistinguishable from a fused-workflow removal regression.

## ⚠️ Pitfalls

1. **"Fewer instructions" is not the lesson; "fewer *redundant* instructions" is.**
   Anthropic's long-running-agents post argues the opposite of minimalism for
   long-horizon work and explicitly says compaction alone is insufficient even for
   frontier models. A diet that removes progress files, SPECs, or the worktree
   lifecycle is cutting the wrong layer. ([Anthropic, effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents))

2. **Removing the fused commands breaks non-Claude targets silently.** Autopilot's
   auto-advance section is a documented no-op without the `Skill` tool. CLAUDE.md
   already records the sibling failure: `.cursor/commands/` is dead code, so Cursor
   reads `.claude/commands/hm/*.md` — a target-conditional gate written as
   `"claude-code" in targets` ships to Cursor anyway. Any fused-removal gate must be
   written as `"cursor" not in targets` and tested with cursor **in** targets.
   ([[wiki:architecture] cursor-reads-the-claude-command-render])

3. **Reviewer cuts have a live counter-example.** CLAUDE.md's fleet-parallel-safety
   entry records a P0 that only the *cross-model* voter caught, where two Claude
   reviewers trusted a misleading docstring. Cutting the second opinion to save $
   removes exactly the diversity that caught it. Reduce the *count* of same-model
   reviewers before touching cross-model.

4. **Deleting the false-positive filter is the wrong read of the Opus 5 guide.**
   The guide's own review advice is to *report everything and filter in a separate
   pass*. `code-verifier` mode A is that pass. Cut the redundant *finders*, keep the
   *filter*.

5. **Memory age ≠ obsolescence.** 67% of failures predate Opus 5, but sampling the
   headers shows they encode system invariants (`yaml-safe-load-on-multi-doc-harness-yaml`,
   `snapshot-regen-inside-worktree` at `count:13`, `worktree-finalize-pulls-orphan-wip-into-main`
   at `count:3`), not model deficiencies. An age-only eviction rule would delete the
   `count:13` entry's cohort-mates that simply have not fired yet.

6. **The `/hm:make --update` blast radius.** Every surface change re-renders into a
   user's `.claude/`, and the reconcile path uses `content_hash` fingerprinting to
   decide KEEP vs REPLACE. Deleting a shipped command is a *removal*, which the
   fingerprint path does not obviously cover — a stale `plan-exec-rev.md` left on
   disk after the template is gone would keep working and keep drifting.
   Verify `reconcile.py` handles deletions before assuming the diet propagates.

7. **`write_after_read` at 27.8% shows prose-only rules do not hold.** CLAUDE.md's
   context-discipline section is unenforced by design ("this instruction is not
   enforced by a hook"). Any diet measure that is only a prose instruction should be
   expected to decay the same way. Prefer deleting the surface over instructing the
   model not to load it.

8. **Rendered commands with no `description:` are invisible to routing.** Before
   deleting commands to save the model's attention, note that 14 of the surviving
   ones are currently indistinguishable in the tool listing. Fixing descriptions may
   recover more routing quality per byte than deleting commands does.

## ❓ Open Questions

1. **Cursor/Codex multi-stage story.** If fused workflows are deleted, what replaces
   them on targets where autopilot cannot run? Options: (a) accept manual stage
   chaining, (b) render fused commands **only** when `targets` excludes `claude-code`,
   (c) port a minimal autopilot to Cursor. This is the binding decision for Approach A.

2. **Which fused workflows, if any, does a *downstream* harness use?** This repo's
   telemetry is n=1. Is there any signal from other installs, or is the `zero
   invocations` result specific to a maintainer who always runs atomic stages?

3. **Reviewer count target.** Current: `consensus: cross-check`, `max_review_rounds: 3`,
   10 reviewer/verifier agents, 2 mandatory second-opinion models on both review and
   plan. What is the intended floor — one reviewer + one filter + one cross-model, or
   something else? Needs a decision before Approach B can be scoped.

4. **`/hm:verify` removal vs. re-scoping.** Is verify genuinely redundant, or is it
   under-used because it is buried in fused workflows that are never invoked? 54 turns
   is too small a sample to distinguish "unwanted" from "undiscovered".

5. **Memory eviction policy shape.** Archive-vs-delete, age threshold, and whether
   `wiki.md` (no `count` field) needs a recurrence signal added before it can be
   evicted at all.

6. **Does `reconcile.py` handle template *deletion*?** Blocks Approach A's propagation
   story. Needs a code read, not a guess.

7. **Target for the diet.** How much of the 1.26MB shipped prompt is the goal — 50%?
   And is the success metric bytes, `slash-command-body` share (15.1%), or
   `total_usd` per completed task?

## 📚 Sources

- [Prompting Claude Opus 5 — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) — the "remove verification instructions" / "legacy harness scaffolding" / "do not use subagents to verify" guidance, and the counter-instruction about not telling a reviewer to be conservative.
- [Effective harnesses for long-running agents — Anthropic Engineering](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — the pro-structure position: progress files, explicit initialization, compaction insufficiency.
- [Building Effective AI Coding Agents for the Terminal: Scaffolding, Harness, Context Engineering (arXiv 2603.05344)](https://arxiv.org/html/2603.05344v1) — scaffolding-vs-harness split; context degradation from stale tool results and abandoned plans.
- [awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) — landscape reference for harness patterns, memory, permissions.
- Local instrumentation (primary evidence, not external): `uv run python -m harness_maker.economics stages|composition --root .`; `.claude/observability/auto-advance.jsonl`; direct byte counts over `.claude/`, `.agents/`, `src/harness_maker/templates/`.

## 🔗 Related Internal Docs

- [[RESEARCH-context-carry-economics-2026-07-28]] — the 87.9%/70.0% carry measurement CLAUDE.md's context-discipline section is derived from; this document re-measures it (`write_after_read` 27.8%).
- [[PLAN-token-economy-step-pruning]] — prior step-pruning attempt; check what it already removed before proposing the same cuts.
- [[PLAN-workflow-step-audit]] / [[BASELINE-workflow-step-audit]] / [[RECEIPT-workflow-step-audit]] — the audit that produced the fused-workflow preamble hoist (2026-07-27) and ADR-010's research fan-out.
- [[PLAN-workflow-overhead-post024]] and [[PLAN-workflow-optimization-2026-05]] / [[CLOSE-workflow-optimization-2026-05]] — earlier overhead work; likely overlaps Approach A.
- [[PLAN-context-carry-discipline]] — where the unenforced prose rules came from.
- [[PLAN-economics-attribution-and-carry]] / [[PLAN-harness-economics-observability]] — the attribution machinery this research relies on; read before trusting the per-stage table.
- [[wiki:architecture] cursor-reads-the-claude-command-render] — why a `claude-code in targets` gate is the wrong gate.
