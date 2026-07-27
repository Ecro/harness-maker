---
type: research
task_slug: token-economy-step-pruning
status: complete
created: 2026-07-27
tags: [harness-maker, research, python, token-economy, prompt-caching, context-rot, stage-pruning]
mtime_warn_days: 7
libs_fetched: [claude-api skill (shared/prompt-caching.md, shared/model-migration.md, shared/models.md, shared/tool-use-concepts.md, shared/agent-design.md)]
sources: [https://www.morphllm.com/context-rot, https://redis.io/blog/context-rot/, https://www.tmls.nyc/research/context-rot-mechanistic, https://zylos.ai/research/2026-01-19-llm-context-management/, https://decodeclaude.com/compaction-deep-dive/, https://claudefa.st/blog/guide/mechanics/context-buffer-management, https://claude-wiki.com/claude-code-auto-compact-window.html, https://platform.claude.com/docs/en/build-with-claude/compaction]
related_docs: ["[[wiki:architecture harness-economics-observability]]", "[[fail:render wrapup-eof-append-outside-marker]]", "[[wiki:architecture session-tier-checkpoint-only]]", "[[wiki:gotcha codex-exec-allow-rule-needs-bare-command]]"]
summary: "Cut carried context per turn, not stage prose — 65.6% of measured spend is cache-read carry; /hm:plan is not the cost problem"
---

# RESEARCH — Token economy and stage-step pruning

## 🎯 Recommended Direction

**Attack carried context per turn, not the number of Steps in a stage prompt.**
Measured over the last 30 days on this repo, **65.6% of all spend ($8,960 of
$13,656 across 20,480 turns) is cache-*read* cost** — the price of re-reading an
already-cached, already-huge context on every turn. Cache *misses* are not the
problem; context *volume* is. `/hm:plan`, the stage the brief singles out, is
measurably **not** the cost problem: it ranks 5th at $1,056 (7.7%), with the
**lowest** mean context (165K) and **lowest** carry ratio (0.38) of any working
stage.

The reason the intuition misfires is a unit mismatch. A `Step` heading in a stage
template costs **O(1) tokens, written once and cache-read thereafter**; a Step
that spawns a subagent or forces a tool round-trip costs **O(context) per turn**.
Deleting 200 lines of `/hm:plan` prose saves roughly 50 tokens per turn amortized.
Dropping one reviewer pass avoids ~100K context tokens × N reviewers × rounds.
Prune by *turn-and-subagent production*, not by line count.

A prerequisite: harness-maker's own L1 model is currently wrong in two places
(stale price table, wrong per-model cache minimums), so the instrument that would
validate any pruning is itself miscalibrated. Fix that in the same change.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary — the
subject is our own templates and Python layer) + **User-workflow / maintainer
value** (the consumer is the harness maintainer running the pipeline) +
**Risk** (every candidate cut trades a verification step for tokens).
`--deep` was not set; the topic arrived fully specified, so Phase 0 / Phase 0.5
were skipped.

## 📐 Measured baseline (this repo, 30 days)

`uv run python -m harness_maker.economics stages --root . --days 30`
and `… report --root . --days 30`. 196 transcript files, 20,480 turns with usage,
ingestion coverage 1.0.

| Stage | Turns | Mean ctx/turn | Carry | USD | Share |
|---|---:|---:|---:|---:|---:|
| **(unattributed)** | 6,242 | 291,668 | 0.672 | $3,947 | 28.9% |
| `hm:review` | 3,906 | 324,976 | 0.654 | $2,816 | 20.6% |
| `hm:execute` | 4,077 | 316,297 | 0.673 | $2,714 | 19.9% |
| `hm:wrapup` | 2,456 | **470,901** | **0.833** | $2,073 | 15.2% |
| `hm:plan` | 1,815 | **165,048** | **0.381** | $1,056 | 7.7% |
| `hm:research` | 746 | 79,894 | 0.267 | $278 | 2.0% |
| `hm:make` | 429 | 225,711 | 0.591 | $239 | 1.8% |
| `harness-maker:make` | 342 | 190,519 | 0.437 | $211 | 1.5% |
| `hm:verify` | 204 | 391,383 | 0.826 | $144 | 1.1% |
| `hm:metrics` | 193 | 228,951 | 0.672 | $97 | 0.7% |
| `hm:spec` | 65 | 226,309 | 0.359 | $58 | 0.4% |

Global: `total_usd` $13,656 · `cache_read_usd` $8,960 · `work_usd` $4,615 ·
`carry_ratio` **0.656**. `carry_ratio` is defined in `economics.py:163` as
`cache_read_usd / total_usd`.

Subagent spend, $1,526 (11.2% of total). **`by_agent` is a cross-cut, not a
partition** — `economics.py:418-422` accumulates each turn into *both* `by_stage`
and `by_agent`, so these rows overlap the stage table above rather than adding to
it (`PLAN-economics-attribution-and-carry` non-goal 6 makes this deliberate).

| Agent | Turns | USD | Context tokens |
|---|---:|---:|---:|
| `code-reviewer` | 1,195 | $415 | 119.4M |
| `plan-validator` | 618 | $262 | 53.3M |
| `general-purpose` | 1,006 | $259 | 126.0M |
| `test-reviewer` | 707 | $246 | 59.1M |
| `security-reviewer` | 657 | $234 | 59.8M |
| others (Explore, executor, concurrency, fork, ux, guide) | 419 | $110 | 20.8M |

Reviewer-family agents alone (`*-reviewer` + `plan-validator`) = **$1,187, 78% of
subagent spend**, and each carries ~100K context tokens per turn.

**Caveat on absolute dollars.** `economics.PRICE_TABLE` prices `opus` at
`$15/$75` per MTok. Current Opus 5 is `$5/$25` (`shared/models.md`). Absolute USD
for opus turns is therefore **~3× overstated**. Ratios and rankings are
unaffected — `cache_read` is exactly `0.1 ×` `input` in the table (1.5/15.0), the
same multiplier the real pricing uses, and every stage is priced by the same
table. Treat the dollar column as a relative index until the table is fixed
(see Approach C).

## 📚 Prior Work — what is already done, and what was deliberately left open

Discovered during `/hm:spec` Step 1 retrieval; **Phase 1 of this research missed
it** because the `work-docs/` grep used token/cache vocabulary and these plans are
filed under "workflow". Read this before proposing anything below.

| Doc | Status | What it settled |
|---|---|---|
| `CLOSE-workflow-optimization-2026-05` | closed, 12/12 phases | Prompt `cache_control: ephemeral` on `llm_judge` system blocks; HTTP cache (`cache.py`); agent-quality/secscan fresh-skip; **drift = review single owner** (wrapup/verify read-only); `## Shared Session Context` preamble in fused workflows; verification cache skip-key; **Pass 1.5 `code-verifier` activated**; **Pass 1 skipped when reviewer count == 1**. |
| `PLAN-workflow-overhead-post024` | complete | Verify owns full regression before wrapup; verification cache CLI-backed; canonical `exec-rev-ver-wrap` added (legacy `exec-rev-wrap-ver` kept); plan-time parallelism metadata; execute/review parallelism gates. **Explicitly deferred: "full Claude/Cursor fused command compaction … to a follow-up."** Non-goal: "do not re-open already-completed prompt-cache, HTTP-cache, Side preset cap, or **Pass 1.5** decisions except where current wiring is incomplete." |
| `PLAN-economics-attribution-and-carry` | complete, 2026-07-26 | Attribution recovery (59% → 28.9% unattributed, verified today) **and** whole-stage subagent delegation for wrapup + verify behind `delegation.stages`. Non-goals include **"any change to pricing"** and **"delegating any stage other than wrapup and verify."** |

**Live config state in this repo** (`.claude/harness.yaml`): `delegation.stages:
["wrapup"]` — wrapup delegation is **ON**, verify is **OFF** (soak). It landed
2026-07-26, so the 30-day wrapup row above (471K / 0.833) is **overwhelmingly
pre-fix data** and must not be used as the post-delegation baseline.
`default_workflow: exec-rev-wrap-ver` — the **legacy** order, not the canonical
`exec-rev-ver-wrap` that `PLAN-workflow-overhead-post024` introduced; that
workflow is not even defined in this harness's `workflows:` map.

**What this leaves genuinely open** (and therefore in scope):

1. **L1 model correctness** — untouched by all three plans, and pricing is an
   explicit non-goal of the most recent one. See Approach C.
2. **Fused-prompt compaction** — the named deferred follow-up, now with a
   measured number (30.4K tokens; 12% doc-only prose; near-duplicate blocks).
3. **20-block cache-lookback guidance** — appears in no prior doc.
4. **Reviewer read budget** — `code-reviewer` at 119.4M context tokens is not
   addressed by any prior plan.
5. **Residual 28.9% unattributed** — recoverable or documented floor?

## 🛠️ Approaches Found

### Approach A — Carry attack: cut context *volume* per turn

| Field | Content |
|---|---|
| **Approach** | Reduce mean context tokens per turn, chiefly by moving high-context work behind subagent boundaries and bounding tool-result size. |
| **Assumption** | The pipeline's cost is dominated by re-reading carried context, and a meaningful share of that context is not load-bearing for the current turn. |
| **Evidence** | Global `carry_ratio` 0.656; `hm:wrapup` at 470,901 mean ctx / carry 0.833 runs **last** and carries the most. `stage-delegate` already exists and already fronts wrapup Steps 1–5.6 and verify's checks (`wrapup.md.j2` Step 0.5, `verify.md.j2` Step 0.5) — the mechanism is built, the coverage is partial. `review.md.j2` Step 3 Pass 1 instructs reviewers to "Read the diff with full context (use Read on changed files **end-to-end**, not just the patch)". |
| **Trade-off** | Subagent boundaries cost a brief round-trip and lose main-loop context; a badly-scoped brief makes the subagent re-derive what the main loop already knew. `[wiki:architecture] harness-economics-observability` already warns that a naive cost÷deliverable metric punishes exactly this kind of verification spend — so the success metric must be `mean_context_tokens` and `carry_ratio`, never cost-per-deliverable. |
| **Compatibility** | High. Uses existing `stage-delegate`, existing `economics.py` measurement, no new config axis. |
| **Risk** | **medium** — a delegated stage that loses context can regress silently (the degraded-brief path in `stage-delegate` already falls back to an inline body, so failure is visible but expensive). |

Concrete candidates under A:
1. **Bound reviewer reads.** Replace "Read changed files end-to-end" with a
   budgeted read (patch + N lines of surrounding context, escalate on demand).
   Directly targets the 119M context tokens on `code-reviewer`.
2. **Tool-result envelope** (`{status, summary, structured, artifact_refs, preview}`
   from the brief). Whether harness-maker can *enforce* this is an open question
   — see ❓ below.
3. **Reorder or re-scope the tail.** `hm:wrapup` and `hm:verify` are the two
   highest-context, highest-carry stages and they run last by construction.
   Widening `stage-delegate` coverage is the cheapest way to make them run in a
   fresh window instead of the accumulated one.

### Approach B — Step pruning (the literal ask), redirected to turn-producing steps

| Field | Content |
|---|---|
| **Approach** | Audit each stage for Steps that produce **turns or subagent invocations**, and cut redundancy there. Treat prose trimming as a separate, minor second-order pass. |
| **Assumption** | Some verification steps are redundant with each other given the full pipeline (plan → execute → review → verify → wrapup all validate overlapping things). |
| **Evidence** | `review.md.j2` Step 3 runs each reviewer through **three** passes over the same diff — Pass 1 (rubric-only, redacted), Pass 1.5 (`code-verifier` reduce), Pass 2 (contextual, full metadata) — then Step 3.5 adds one voter **per** enabled `second_opinion.models` entry, then Step 4 runs consensus, then the Grade Gate can loop rounds 2..max. `plan.md.j2` adds Step 4-pre (cross-model second opinion) **and** Step 4 (`plan-validator`, $262 / 53.3M ctx). `/hm:verify` Check 1 re-runs a PLAN/SPEC drift verdict that `wrapup.md.j2` Step 3 also reads. Doc-only prose (`Purpose` / `When to Run` / `Usage` / `Inputs` / `Outputs` / `Quality Bar` / `Communication Protocol` / `Stage summary`) is **12% of stage templates — 24,835 chars ≈ 6.2K tokens of ~50.2K**. |
| **Trade-off** | Every cut here trades a *measured* quality mechanism for tokens. The 2-pass redaction protocol cites a **+47 percentage-point precision gain** on anchoring-prone diffs (`review.md.j2` Step 3). Removing it is a deliberate quality decision, not an optimization. |
| **Compatibility** | High — pure template edits, plus `harness.yaml` knobs that already exist (`reviewers.enabled`, `second_opinion.models`, `max_review_rounds`). |
| **Risk** | **medium-high** — this is the path most likely to quietly lower the quality floor the pipeline exists to hold. |

Concrete candidates under B, ranked by tokens-saved ÷ quality-risk:
1. **Doc-only prose trim** (~6.2K tokens, near-zero risk). `When to Run` and
   `Usage` are dead weight at execution time — the decision to run has already
   been made by the time the model reads them.
2. **Near-duplicate block collapse in fused workflows.** The default workflow
   `exec-rev-wrap-ver` is 121,782 chars ≈ **30.4K tokens** injected per
   invocation, containing 4× `Task worktree preflight`, 4× `Communication
   Protocol`, 4× `Emit Gate 0 receipt`, 4× `Quality Bar` / `Purpose` / `Outputs`
   / `Inputs`, 3× `When to Run`. Stage-name-normalized exact duplication is only
   **2.3% (2,834 chars)** because bodies diverge — so mechanical dedup is *not*
   worth much; hoisting the shared blocks to a single workflow preamble is.
3. **Collapse the plan-stage double check.** Step 4-pre (second opinion) and
   Step 4 (`plan-validator`) both critique the draft PLAN. One of them, chosen by
   config, is likely enough.
4. **Drop Pass 1.5 or Pass 2 in the reviewer protocol** — highest token saving,
   highest quality risk, explicitly ablation-backed. **Do not cut without the
   user's decision.**

### Approach C — Fix harness-maker's L1 model, and advise on the knobs we don't own

| Field | Content |
|---|---|
| **Approach** | Correct the two Python surfaces where harness-maker *models* the billing layer, and turn `/hm:metrics` + `/hm:health` into advisors for the knobs the user owns but harness-maker cannot set. |
| **Assumption** | harness-maker is **almost entirely** a plugin rather than an API client. It has exactly **one** request-construction surface — `llm_judge.py:73-79` builds `Anthropic().messages.create(...)` and **already** sets `cache_control: {"type": "ephemeral"}` on its system block (landed by `CLOSE-workflow-optimization-2026-05` Phase 3). Everywhere else it emits prompts that the CLI turns into requests, so it can never set `effort`, `role:"system"`, `defer_loading`, or a beta header. Its L1 surface is therefore (a) that one judge call, (b) modeling billing correctly for measurement, (c) telling the user what to configure. |
| **Evidence** | Two verified defects. **(1)** `economics.PRICE_TABLE` prices opus at `$15/$75`; current Opus 5 is `$5/$25`. **(2)** `cache_diagnostics._THRESHOLDS = {haiku: 4096, opus: 1024, sonnet: 1024}` with `_DEFAULT_THRESHOLD = 1024`, matched by **family-name prefix** (`cache_diagnostics.py:53`). The official per-model minimums are **non-monotonic within a family** and therefore not expressible as a family map — see the table below. `_TTL_SECONDS = 5*60` is likewise hard-coded, ignoring the `ttl: "1h"` tier the same file's own comment says users are advised to enable. This feeds `/hm:health` Layer 3 via `ai_readiness.py` and `improvement.py`. |
| **Trade-off** | Saves zero tokens by itself. But every A/B decision is validated against this instrument, so shipping A or B on a miscalibrated meter risks optimizing the wrong stage. |
| **Compatibility** | Trivial — self-contained Python, existing tests. |
| **Risk** | **low** |

Official minimum cacheable prefix (`shared/prompt-caching.md`), vs what
harness-maker currently assumes:

| Model | Official | harness-maker | Effect |
|---|---:|---:|---|
| Opus 5 / Fable 5 / Mythos 5 | **512** | 1024 | false `miss_min_threshold` on 512–1023-token prefixes |
| Opus 4.8 / Sonnet 5 / Sonnet 4.6 / 4.5 / Opus 4.1 / 4 | 1024 | 1024 | ✅ |
| Opus 4.7 / Mythos Preview / Haiku 3.5 | 2048 | 1024 / 4096 | misses under-reported (opus) / over-reported (haiku) |
| Opus 4.6 / Opus 4.5 / Haiku 4.5 | 4096 | 1024 / 4096 | opus misses badly under-reported |

The brief's "비단조" trap is not hypothetical — it is already sitting in our own
diagnostic layer, and a family-prefix matcher structurally cannot express it.

## ⚠️ Pitfalls

1. **Treating `input_tokens` as the prompt size.** It is the *uncached remainder
   only*; the total is `input_tokens + cache_creation_input_tokens +
   cache_read_input_tokens` (`shared/prompt-caching.md`). Any dashboard reading
   the single field under-reports a well-cached agentic session by an order of
   magnitude. The brief flags this and it is confirmed verbatim in the docs.

2. **The 20-block cache lookback — the brief's biggest omission.** Each
   `cache_control` breakpoint walks backward **at most 20 content blocks** to
   find a prior entry. A single turn that emits more than 20 blocks — routine in
   an agentic loop with many `tool_use`/`tool_result` pairs — silently misses
   the previous turn's cache with no error (`shared/prompt-caching.md`). This is
   exactly the shape harness-maker generates (parallel reviewer fan-out, batched
   Bash calls). It is a *CLI-owned* breakpoint, so we cannot fix it — but it is a
   reason to prefer **fewer, larger** tool calls per turn over many small ones,
   which *is* a prompt-level instruction we control.

3. **Cache invalidation is tiered, not all-or-nothing.** Only tool-definition
   changes and model switches force a full rebuild. `tool_choice`, images, and
   toggling `thinking` preserve the tools+system cache; `speed` / web-search /
   citations toggles preserve tools (`shared/prompt-caching.md` § Invalidation
   hierarchy). Do not over-defend against the cheap ones.

4. **Parallel fan-out cannot share a cache write.** A cache entry is readable
   only once the first response *begins streaming*; N concurrent identical-prefix
   requests all pay full price. The documented fix is to send 1, await the first
   streamed token, then fire the remaining N−1. The brief states this correctly.
   **But:** harness-maker's own review Step 3 explicitly instructs "a single
   message with multiple Task tool uses for parallel execution" — the fan-out
   whose cache economics this pitfall describes. Whether Claude Code's subagent
   dispatch serializes the first call is unknown to us; do not assume a saving
   either way without measuring.

5. **Compaction silently drops governance, and the response contract is easy to
   break.** `compaction` blocks must be echoed back by appending the whole
   `response.content`, not just the text — extracting the text loses the state
   with no error (`shared/prompt-caching.md`, § Compaction). Separately,
   `context editing` (**clears** — beta `context-management-2025-06-27`, types
   `clear_tool_uses_20250919` / `clear_thinking_20251015`) and `compaction`
   (**summarizes** — beta `compact-2026-01-12`, type `compact_20260112`) are
   different features with different headers. The brief is correct on both counts.
   harness-maker already implements the mitigation the brief prescribes —
   re-injection files rather than trusting the summary — via the `flush_session`
   PreCompact hook and the memory tiers (`[wiki:architecture]
   session-tier-checkpoint-only`).

6. **Context rot is real but the specific numbers in the brief are not the ones
   the literature supports.** Chroma's 18-frontier-model study reports accuracy
   degrading **30%+ in mid-window positions** and **30–50% well before the
   documented limit**, with models typically breaking **30–40% before their
   claimed ceiling** (a 200K model unreliable around 130K). The brief's "200K
   model already 30–50% degraded at 50K" overstates the onset. Applied to our
   1M-window measurements, mean contexts of 291K–471K sit below the ~600–700K
   implied effective ceiling — but degradation is gradual, not a cliff, so
   `hm:wrapup` at 471K is the most exposed stage in the pipeline.

7. **The highest-context stage is also the one with the repo's most-recurring
   silent failure — labeled inference, not established cause.**
   `[fail:render] wrapup-eof-append-outside-marker` has `count:3` and is a
   precision failure: appending *past* a named marker line during a wrapup memory
   write, invisibly destroying 132 wiki entries. `hm:wrapup` runs at 470,901 mean
   context tokens, the highest in the pipeline. A precision-critical edit
   performed at the maximum context position is exactly the shape context-rot
   research predicts will degrade. This does not prove causation — the failure's
   own ledger attributes it to prose ambiguity around "append" — but it is a
   second, independent argument for the same fix (delegate wrapup's memory writes
   to a fresh-context subagent), and the ledger's own conclusion after 3
   recurrences was that another prose reminder will not work.

8. **Auto-compact threshold attribution is contested.** The brief attributes
   `window − min(max_output, 20K) − 13K` to Codex; multiple 2026 sources
   attribute the same formula to Claude Code (`effectiveWindow = contextWindow −
   max(maxOutputTokens, 20_000)`; `autoCompactThreshold = effectiveWindow −
   13_000`, ≈167K on a 200K window). Reported defaults also disagree (≈95% of
   window vs the formula's ≈83%). Treat the attribution as low-confidence. The
   actionable part is unambiguous and already in this user's global config:
   `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (currently 85).

9. **Do not reintroduce a cost-per-deliverable metric.** `[wiki:architecture]
   harness-economics-observability` records this as a load-bearing invariant
   (ADR-002): any such ratio puts verification spend in the numerator and nothing
   in the denominator, so a task that ran 3 review rounds and hardened a defect
   scores as *less* economic than one that skipped review. A token-reduction
   project is precisely the context in which someone will be tempted to add it.

## ❓ Open Questions

1. ~~**What is `(unattributed)`?**~~ **ANSWERED — closed during Step 1 of
   `/hm:spec`.** `PLAN-economics-attribution-and-carry` (status `complete`,
   2026-07-26) already diagnosed it: **Claude Code drops `attributionSkill` the
   moment the user speaks mid-stage**, so every `AskUserQuestion` answer, every
   "진행해", and every `<task-notification>` opens a new unattributed run.
   `(unattributed)` is therefore *mostly stage work*, and per-stage costs are
   **floors, not totals**. The recovery shipped and is measurably working:
   that plan measured 59% unattributed ($6,917 of $11,736); today's run measures
   **28.9%**. Residual open sub-question: is the remaining 28.9% the documented
   irreducible remainder (loop iterations are iteration-level only,
   `feature_branch_workflow: false` harnesses are exempt, Cursor/Codex have no
   session-end closure hook), or is there still recoverable attribution?

2. **Can harness-maker enforce a tool-result envelope at all?** The brief lists it
   as a must-do, but harness-maker has no runtime interception of tool *results* —
   `PostToolUse` hooks observe, and it is unverified whether they can rewrite a
   result before it enters context. If they cannot, the envelope is reduced to a
   prompt-level convention (which the `[wiki:gotcha]` on prose-vs-execution-surface
   warns is exactly the shape that ships silent-skip bugs). **This decides whether
   brief item #2 is buildable.**

3. **Which verification steps may be cut, and by whose decision?** Pass 1.5 and
   Pass 2 of the reviewer protocol are the largest single token line item and are
   backed by a measured +47pp precision claim. `plan-validator` ($262) overlaps
   with the plan-stage second opinion. These are quality-floor decisions, not
   optimizations — `/hm:plan` must put them to the user.

4. **Does the fused workflow actually cost more carried context than
   autopilot-chained atomic stages?** `exec-rev-wrap-ver` injects 30.4K tokens up
   front; autopilot invokes `Skill(hm:<next>)` per stage. Naively the atomic
   chain looks cheaper, but the earlier command bodies stay in the same
   conversation history, so the saving may be zero. Needs one measured A/B, not
   an argument.

5. **What is `estimator_coverage = 0.10`?** One tenth coverage on a signal the
   report emits without explanation. If it gates any of the numbers above,
   confidence in them drops.

6. **Is the `_THRESHOLDS` fix worth per-model exactness, or should it fail
   loudly instead?** Since the minimum is non-monotonic and new models keep
   shifting it, a hard-coded per-model map will go stale the same way
   `PRICE_TABLE` did. An explicit "unknown model → emit `unknown`, do not guess"
   branch may be more honest than a table that silently ages.

## 📎 Appendix A — Effort sweep methodology (user-supplied, 2026-07-27)

Added mid-`/hm:spec` by the user. **Out of the agreed SPEC scope (A+B+C+D)** —
recorded here so it is not lost, and so the follow-up has a method rather than a
guess. Two facts here change design, and one corrects this document.

**A.1 — Changing `effort` invalidates the cache.** The official effort doc states
that `effort` alters the rendered prompt, so varying it between requests does not
preserve the previous turn's cached prefix. Therefore "detect difficulty, raise
effort mid-conversation" is a design that **pays a full cache rebuild**; vary
effort **per route**, not dynamically within a conversation. (Note: the bundled
`shared/prompt-caching.md` invalidation-hierarchy table does not list `effort`
explicitly — it covers `tool_choice` / images / `thinking`. Treat the effort doc
as the more specific source; the two are consistent if `output_config` changes
invalidate the messages tier.)

**A.2 — Per-request and per-task measurement give opposite answers.** Raising
effort increases tokens *per request* but can reduce *total* cost by cutting turn
count. A JetBrains-family 80-pair comparison found **`low` effort was 7.6% more
expensive per task**, with **13.8% more turns and 14.3% more cache reads**. The
metric must therefore be **cost per correct answer, including retry cost** — never
tokens per request.

**A.3 — The external results genuinely contradict each other.**

| Source | Finding |
|---|---|
| Digital Applied (900 runs) | `high` gains 18–22pt on math, only 3–5pt on code refactor; cost 4–17×, TTFT 5–60× |
| Repetition-variance-controlled study (ReasonBENCH) | Quality differences across effort are **not statistically significant**; only output tokens rise monotonically |
| JetBrains pair comparison | `low` was **more** expensive per task |

Reconciliation: the gain is **domain-dependent** (large on math, small on code
refactor), small gains are **swamped by run-to-run variance**, and per-task
accounting can invert the per-request conclusion. Consequence: **do not import
anyone else's numbers.** Anthropic's own docs say the same — run a *fresh* effort
sweep rather than reusing a prior model's setting.

**A.4 — Method.**

| Step | Content |
|---|---|
| A.0 Precondition | Stabilize prompts first — **delete self-verification ("double-check") instructions**, move verbosity control into the prompt, common `max_tokens` ≥ 64K |
| A.1 Unit | Sweep per **route** (planner / coder / reviewer / subagent), not per model |
| A.2 Eval set | 12–20 tasks, **≥20% hard** (without hard tasks `low` always wins), auto-gradable |
| A.3 Metrics | success rate + **cost per correct** + p95 latency; count `usage.output_tokens` (thinking is billed even when `display: "omitted"`) |
| A.4 Arms | `low` / `medium` / `high` / `xhigh` (exclude `max`), **n ≥ 3**, bucket `stop_reason == "max_tokens"` separately |
| A.5 Decision | `argmin(cost)` subject to `success ≥ best − δ`, with δ fixed in advance; ties go to `low` |
| A.9 Minimum viable | 1 route × 10 tasks × 3 arms × n=2 = 60 runs, ~half a day |

**A.5 — Source conflict on the Opus 5 starting point, left open.** The user's
sources state Opus 5 starts at the **`high` default**, with `xhigh`-start being
the Opus 4.7/4.8 recommendation. The bundled `shared/model-migration.md` §
*Migrating to Claude Opus 5* instead says "Start at `xhigh` for coding/agentic and
`high` elsewhere, then sweep down." Both agree the API **default is `high`** and
that `low`/`medium` are unusually strong on this model; they disagree only on the
recommended *starting arm* for coding work. Not resolved here — and it does not
need to be, because A.4 replaces the starting-arm guess with a measured sweep.

**A.6 — Relevance to harness-maker.** harness-maker cannot set `effort` (no
request surface outside `llm_judge.py`); it is a CLI/user setting. Its reachable
contribution is (a) the A.0 precondition — **removing self-verification prose from
its own stage templates**, which is prompt content we do own, and (b) documenting
the method so a user can run the sweep. See ❓ Open Questions.

## 📚 Sources

- `claude-api` skill (bundled, cached 2026-06-24): `shared/prompt-caching.md`
  (prefix-match invariant, per-model minimum table, 1.25×/2× write & 0.1× read
  economics, 20-block lookback, invalidation hierarchy, concurrent-request
  timing, `max_tokens: 0` pre-warming, mid-conversation system messages),
  `shared/models.md` (Opus 5 = $5/$25, 1M ctx), `shared/model-migration.md`
  (Opus 5 effort ladder, low/medium unusually strong, thinking-on-by-default),
  `shared/tool-use-concepts.md` (`defer_loading` + tool search, mid-conversation
  tool changes `mid-conversation-tool-changes-2026-07-01`, context editing vs
  compaction), `shared/agent-design.md` (caching for agents).
- https://platform.claude.com/docs/en/build-with-claude/compaction
- https://arxiv.org/pdf/2606.22528 — *Governance Decay: How Context Compaction
  Silently Erases Safety Constraints in Long-Horizon LLM Agents*. The primary
  source for Pitfall 5; names the exact mechanism harness-maker mitigates with
  re-injection files rather than trusting the summary.
- https://platform.claude.com/docs/en/build-with-claude/effort — per-model
  starting points, cache invalidation on effort change, "run a fresh effort
  sweep" guidance (Appendix A).
- https://www.digitalapplied.com/blog/reasoning-effort-cost-vs-quality-benchmarks-2026
  — 900-run domain-split gains, cost-per-correct-answer framing (Appendix A).
- https://arxiv.org/html/2512.07795 — *ReasonBENCH: Benchmarking the
  (In)Stability of LLM Reasoning* (Appendix A).
- https://www.techtimes.com/articles/321223/20260721/rtk-raises-claude-code-costs-low-effort-jetbrains-benchmark-debunks-6090-claim.htm
  — the 80-pair comparison where `low` effort cost **more** per task (Appendix A).
- https://usagebox.com/articles/cost-per-task-workhorse-models-2026 — cost-per-task
  as the unit of account (Appendix A).
- https://www.morphllm.com/context-rot — Chroma 18-model study, 30%+ mid-window
  degradation.
- https://redis.io/blog/context-rot/
- https://www.tmls.nyc/research/context-rot-mechanistic
- https://zylos.ai/research/2026-01-19-llm-context-management/ — MECW, 30–40%
  gap between advertised and effective window.
- https://decodeclaude.com/compaction-deep-dive/ — Claude Code compaction system.
- https://claudefa.st/blog/guide/mechanics/context-buffer-management — ~33K buffer.
- https://claude-wiki.com/claude-code-auto-compact-window.html —
  `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`.
- Local measurement: `harness_maker.economics {report,stages} --root . --days 30`
  (196 files, 20,480 turns, coverage 1.0).

## 🔗 Related Internal Docs

- `[[wiki:architecture]] harness-economics-observability` — the spend model this
  research is built on; its ADR-002 no-ratio invariant constrains how success is
  measured here. Also records that `hm:wrapup` is the least economic stage and
  `hm:review` has the lowest carry — both reconfirmed by today's numbers.
- `[[fail:render]] wrapup-eof-append-outside-marker` (count:3) — the
  highest-context stage's recurring silent-corruption failure; cited as
  correlational support for delegating wrapup's memory writes.
- `[[wiki:architecture]] session-tier-checkpoint-only` — the existing
  compaction-checkpoint mechanism that already implements the brief's
  "re-injection file, not summary" prescription.
- `[[wiki:gotcha]] codex-exec-allow-rule-needs-bare-command` — precedent that a
  prose-only contract with no execution surface ships silent-skip bugs; directly
  relevant to Open Question 2.
- `CLAUDE.md` § "무언가를 고치거나 개선하기 전에" checkpoint 2 — a consumer that
  preprocesses content cannot be validated by inspecting the file on disk; applies
  to any measurement added under Approach C.
