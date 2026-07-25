---
type: research
task_slug: harness-economics-observability
status: complete
created: 2026-07-25
tags: [harness-maker, research, observability, cost, telemetry, python]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://docs.anthropic.com/en/docs/claude-code/monitoring-usage
  - https://github.com/ryoppippi/ccusage
  - https://github.com/badlogic/cccost
  - https://github.com/ColeMurray/claude-code-otel
  - https://signoz.io/docs/claude-code-monitoring/
  - https://aws.amazon.com/blogs/mt/analyzing-claude-code-usage-with-cloudwatch-and-opentelemetry/
related_docs:
  - "[[PLAN-locale-and-command-observability]]"
  - "[[PLAN-session-tier-slim]]"
  - "[[PLAN-cfr-churn-metrics]]"
summary: "Read cost from Claude Code transcript JSONL (attributionSkill/Agent) — the hook telemetry records zero tokens"
---

# RESEARCH — Harness economics observability

## 🎯 Recommended Direction

**Build the economics model as a post-hoc reader over Claude Code's own session
transcripts (`~/.claude/projects/<enc-cwd>/*.jsonl` + `<sessionId>/subagents/agent-*.jsonl`),
not over the harness's existing `PostToolUse` telemetry hook.**

Rationale: the transcript is the only local artifact that actually carries token
counts, and it already carries harness-native attribution fields
(`attributionSkill` = `hm:<stage>`, `attributionAgent` = reviewer name,
`attributionPlugin` = `hm`, plus `cwd` / `gitBranch` which resolve to the task
slug). That is a complete join key set for "cost per stage, per agent, per task"
with **zero new instrumentation**. The existing hook path cannot be fixed into a
cost source — see the blocking measurement below.

### Blocking measurement (this is the headline finding)

`src/harness_maker/telemetry.py` writes `input_tokens` / `output_tokens` /
`cache_read_tokens` / `cache_creation_tokens` per `PostToolUse` event, and
`COST_PER_MTK` already prices opus/sonnet/haiku. Measured on this repo's own
data:

```
2175 telemetry lines (metrics-2026-07-{17,18,21,24}.jsonl)
    → 0 lines with any non-zero token field
```

The Claude Code `PostToolUse` payload has no `usage` key, so every write is
`0`.

Downstream consequence — **corrected 2026-07-25 after a live run**, because the
first reading of this was wrong and the correction changes what the bug is.
`cache_diagnostics.py:235-241` skips any entry whose four token fields are all
zero *before* classification runs, so the entry list ends up empty and
`diagnose_cache` returns `_no_data`. Measured on this repo:

```
diagnose_cache(...) → hit_rate=0, score=50 (neutral), sample_size=0,
                      primary_failure="no_data"
```

`improvement.py:177-179` emits no ActionItem for `no_data`. So `ai_readiness`
Layer 3 (`cache_efficiency`, 5 % of the composite) is **inert — permanently
neutral and silent — not wrong**. The earlier claim here that it "classifies
every turn as a miss" was an inference from the hit test (`cache_read_tokens > 0`)
without reading the guard 150 lines below it, and is retracted.

The failure family is still
`[wiki:architecture] hooks-load-from-settings-not-hooksjson` — a field assumed to
exist, never verified against a live payload — and the retraction above is the
same class of error one level up: a behaviour inferred from one line instead of
executed. Both are why the plan built on this data requires a live smoke.

### Measured baseline (why this matters right now)

Ground truth from the transcript store for this repo, Opus list pricing
(`$15/$75/$1.50/$18.75` per Mtok in/out/cache-read/cache-write):

| scope | turns | cache-read | cache-write | output | cost |
|---|---:|---:|---:|---:|---:|
| 6 recent sessions, main loop | 622 | 214.7 M | 2.19 M | 1.03 M | **$440** |
| same 6 sessions, subagents | 74 | 4.82 M | 0.81 M | 0.04 M | **$25** |
| single largest session (17.7 h) | 1779 | 829.6 M | 8.54 M | 1.79 M | **$1 539** ($87/h) |

Cost composition of that single session: **cache-read 81 %**, cache-write 10 %,
output 9 %. Input (uncached) is a rounding error.

Per-stage split across the 6 recent sessions:

| attributionSkill | msgs | output tok | cache-read | $ | $/msg |
|---|---:|---:|---:|---:|---:|
| *(no skill — plain chat / post-stage turns)* | 347 | 559 039 | 151.2 M | 281.27 | 0.81 |
| `hm:execute` | 84 | 138 280 | 23.0 M | 50.24 | 0.60 |
| `hm:wrapup` | 41 | 47 794 | 17.7 M | 32.37 | 0.79 |
| `hm:research` | 59 | 99 821 | 4.57 M | 25.21 | 0.43 |
| `hm:review` | 31 | 43 715 | 11.6 M | 22.66 | 0.73 |
| `hm:plan` | 35 | 127 954 | 4.97 M | 22.30 | 0.64 |
| `hm:make` | 19 | 7 511 | 1.10 M | 4.87 | 0.26 |

### The cost law the model must expose

Because 81 % of spend is cache-read, **cost ≈ Σ over turns of (context size at
that turn)**. Context grows monotonically within a session — measured curve in
the largest session: 70 k → 234 k → 397 k → 524 k → 656 k → 865 k tokens before
the first compaction, then 136 k → 595 k after. Mean 471 k, median 454 k, max
944 k tokens **per turn**.

Two consequences, both directly relevant to the reported "spec-driven / test mode
burns tokens and takes long" feedback:

1. **A stage that adds turns is charged super-linearly**, because each added turn
   pays for a context that is itself larger than the previous turn's. Adding a
   stage late in a workflow is much more expensive than the same stage early.
   Measured: the first 25 % of turns account for 17 % of context-cost, the last
   25 % for 24 %.
2. **Subagent turns are 5–7× cheaper per turn than main-loop turns** —
   `code-reviewer` averaged 85.6 k context/msg and `plan-validator` 62.7 k, versus
   471 k in the main loop. Delegation is an economic lever, not just a quality
   lever. Total subagent spend was 5 % of main-loop spend.

The observability model should therefore report, per stage: **turns, mean context
per turn, output tokens, wall-clock, and cost — with cost decomposed into
carry (cache-read) vs. new work (cache-write + output)**. A stage with high
carry and low output is paying rent on context it is not using.

---

## 🔍 Refinement Decisions

`--deep` was not set; Phase 0 / Phase 0.5 skipped.

**Discovery lens:** *Technical architecture / implementation* (primary — where do
token counts physically exist, and what attribution can be joined) +
*User-workflow / product opportunity* (secondary — what cost artifacts harness
users already have, and what the harness can add that generic tools cannot).

**User-supplied motivation (mid-turn):** the first external feedback on
harness-maker reports that spec-driven mode — and even test mode — consumes a
large number of tokens and takes a long time. The model must therefore be able to
answer *"which stage in which mode is uneconomic"*, not merely *"how much did I
spend"*.

### Local capability × user artifact matrix

| User already has | Generic tools give them | What this harness can add |
|---|---|---|
| `~/.claude/projects/**/*.jsonl` transcripts | `ccusage`: per-day / per-session / per-model totals | per-**stage** and per-**agent** totals via `attributionSkill` / `attributionAgent` |
| `/cost` in-session command | current session's running total | cost attributed to the *task slug* via `cwd` → `.worktrees/<slug>` / `gitBranch` → `hm/<slug>` |
| `work-docs/PLAN-*.md`, `SPEC-*.md`, commits | nothing — no link to spend | ~~cost per deliverable: $ per landed commit, per SPEC AC, per confirmed review finding~~ — **SUPERSEDED by PLAN ADR-002, do not implement** (see note below) |
| `.claude/observability/*.jsonl`, `delivery_metrics` (CFR / churn) | — | join cost against CFR/churn → cost per *successful* change, not per change |
| OTel exporter (beta) | dashboards, org-wide rollups | requires a collector; conflicts with the harness's 100 %-local rule |

The differentiator is **attribution**, not token counting — token counting is
already solved by `ccusage`.

> ⚠️ **Superseded — read before implementing anything from this section.**
> The "deliverable linkage" / cost-per-deliverable idea above was rejected during
> `/hm:plan` and is **forbidden by PLAN ADR-002**. Any cost ÷ deliverable-count
> ratio makes verification spend (review rounds that harden security or
> performance) score as uneconomic, because hardening lands in the numerator and
> never in the denominator. The shipped model classifies spend by *function*
> instead and reports the mix; deliverable-linked yield is permitted **only** as
> an aggregate-over-many-runs figure, never per run. Do not resurrect this row.

---

## 🛠️ Approaches Found

### Approach A — Transcript-JSONL post-hoc analyzer *(recommended)*

| Field | Content |
|---|---|
| Approach | New `harness_maker.economics` module reads `~/.claude/projects/<enc-cwd>/<sid>.jsonl` and `<sid>/subagents/agent-*.jsonl`, aggregates `message.usage` by `attributionSkill` / `attributionAgent` / task slug, prices with the existing `COST_PER_MTK`, surfaced by a new or extended `/hm:metrics` mode. |
| Assumption | Transcripts persist locally and retain `attributionSkill` / `attributionAgent` / `usage`. Verified empirically on 50 session files (101 MB) in this repo. |
| Evidence | Confirmed field set per assistant line: `message.model`, `message.usage.{input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, cache_creation.ephemeral_{5m,1h}_input_tokens}`, `attributionSkill`, `attributionAgent`, `attributionPlugin`, `effort`, `timestamp`, `cwd`, `gitBranch`, `isSidechain`, `requestId`. Subagent example line carries `attributionAgent: "security-reviewer"` + `attributionSkill: "hm:review"`. |
| Trade-off | Post-hoc only — cannot gate a running stage. Reads outside the project root (`~/.claude/`), which no current harness reader does. Undocumented internal format that can change without notice. |
| Compatibility | High. 100 % local (CLAUDE.md rule preserved), pure-Python, reuses `COST_PER_MTK`, `_metrics_io`-style sharded reading, and `delivery_metrics`' git side for the deliverable join. No hooks, no new permissions, no render changes beyond one command template. |
| Risk | **medium** — format drift is the standing risk; mitigate with a defensive parser (unknown keys ignored, missing `usage` → skip line, never crash) and a `/hm:health` signal that fails loudly when 0 priced turns are found (the exact silent-degradation this research just caught in the hook path). |

### Approach B — OpenTelemetry export

| Field | Content |
|---|---|
| Approach | Set `CLAUDE_CODE_ENABLE_TELEMETRY=1` and consume `claude_code.token.usage` plus the `api_request` / `skill_activated` / `tool_decision` events. |
| Assumption | The user is willing to run a collector, and per-request cost from the vendor is preferable to locally-priced tokens. |
| Evidence | Officially documented and explicitly supports breakdown by model and **subagent**; `api_request` events carry per-call cost. Currently **beta, subject to change**. Mature third-party stacks exist (SigNoz, Grafana, CloudWatch Coding Agent Insights, `claude-code-otel`). |
| Trade-off | Authoritative cost and live streaming, but requires an OTLP endpoint; the default integrations ship data off-machine, which contradicts the harness's "100 % 로컬 telemetry — 외부 전송 금지" rule. A file/stdout exporter keeps it local but adds an env-var + process-lifecycle dependency the harness cannot verify at render time. |
| Compatibility | Medium — orthogonal to everything the harness renders; would be an opt-in `harness.yaml` block, not a default. |
| Risk | **medium-high** for a default; **low** as an opt-in escape hatch for org-level rollups. |

### Approach C — Repair the existing hook telemetry

| Field | Content |
|---|---|
| Approach | Keep `telemetry.py`'s `PostToolUse` writer and find another way to populate the token fields. |
| Assumption | Some hook event exposes `usage`. |
| Evidence | Refuted for `PostToolUse` by direct measurement (0/2175 lines non-zero). The `Stop` hook payload carries `transcript_path`, so a Stop-hook variant could read the transcript — but that is Approach A with a worse trigger (fires per turn, re-reads a file that grows to ~10 MB). Cursor surfaces no token data in any hook event at all (already documented in `telemetry.py`'s own docstring). |
| Trade-off | No path to correctness that is cheaper than A. |
| Compatibility | — |
| Risk | **high** — leaving it as-is keeps `cache_diagnostics` and `ai_readiness` Layer 3 scoring on zeros. Even if the economics model goes elsewhere, that phantom scorer must be either fixed or explicitly marked N/A. |

---

## ⚠️ Pitfalls

1. **Total tokens is not cost.** Input, output, cache-read, and cache-write differ
   by up to 50× in price. A "tokens used" chart ranks stages wrongly — in the
   measured data `hm:plan` produces 2.6× the output tokens of `hm:wrapup` yet
   costs less, because `hm:wrapup` runs on a much larger carried context. Every
   number the model reports must be priced, and priced per token *type*.
   (Corroborated by the SigNoz/Grafana write-ups on `claude_code.token.usage`.)
2. **64 % of measured spend has no `attributionSkill`.** 347 of 622 main-loop
   turns attributed to no skill and cost $281 of $440. Attribution appears to
   cover turns while a skill is active, not the free-form turns around it. A
   per-stage report that silently drops these looks precise and is wrong by a
   factor of ~3. The model must show an explicit *unattributed* bucket and never
   normalise it away.
3. **Pricing tier assumptions.** `COST_PER_MTK` uses public list prices, but this
   project runs on a Claude Code subscription where marginal cash cost is not
   list price. Report list-price-equivalents as a *relative* economics signal
   (comparing stages against each other) and label them as such, or the numbers
   read as a bill that does not exist.
4. **Goodhart, again.** `/hm:metrics` already carries an explicit non-gate
   warning for CFR/churn. Cost is far more gameable — the cheapest workflow is
   one that produces nothing. Any cost figure must be paired with an output
   figure (deliverables, landed commits, confirmed findings), and must never
   become a gate. This is the same guidance the existing metrics command states
   in its own header.
5. **Reading `~/.claude/` breaks the project-local assumption.** Every current
   reader is rooted at the project. A transcript reader needs the cwd→dir
   encoding (`/home/noel/harness-maker` → `-home-noel-harness-maker`), and must
   degrade to "no data" rather than crash when the directory is absent (fresh
   clone, CI, Cursor, Codex).
6. **Session-file ≠ workflow.** One 17.7 h session spanned research → plan →
   execute across multiple compactions. Slicing "cost per workflow" by session
   file over-counts; slice by task slug (`cwd` / `gitBranch`) and by contiguous
   `attributionSkill` runs instead.
7. **Compaction hides the growth curve.** After a compaction the context drops
   from 865 k to 136 k and starts climbing again. A mean-context statistic
   averages across that discontinuity and understates the pre-compaction peak,
   which is where the expensive turns actually are. Report the per-turn curve or
   the peak, not just the mean.
8. **Don't re-litigate what `ccusage` already does.** Daily/monthly/per-model
   totals from local JSONL are a solved, 4.8k-star problem. Duplicating it is
   wasted work; the harness's contribution is stage/agent/task attribution and
   the deliverable join.

---

## ❓ Open Questions

*(For `/hm:plan` to lock down.)*

1. **Scope of the deliverable side.** Does "산출물" mean (a) files written per
   stage, (b) landed commits / LOC, (c) SPEC ACs satisfied and review findings
   confirmed, or (d) all three? This decides whether the model joins against
   `delivery_metrics`, `review_telemetry`, `spec_inventory`, or just the
   filesystem.
2. **Surface.** New `/hm:economics` command, a new mode on `/hm:metrics`
   (`--economics`), or a `/hm:health` dimension? `/hm:metrics` is already framed
   as read-only reflection input and would inherit the correct non-gate framing.
3. **Fate of the zero-token telemetry path.** Three options: delete the four token
   fields from `telemetry.py`; keep them and mark `cache_diagnostics` /
   `ai_readiness` Layer 3 as N/A; or re-point `cache_diagnostics` at the
   transcript reader so cache-efficiency becomes real. This is a correctness bug
   independent of the new feature and should be decided explicitly.
4. **Budget / advisory behaviour.** Read-only reporting, or a soft in-stage
   advisory ("this stage has consumed N turns at ~X k context")? An advisory
   needs a live signal, which only `Stop`-hook-plus-transcript can provide, and
   risks becoming a gate through the back door.
5. **Whether to act on the findings in the same task.** The measurements point at
   concrete levers — fused workflow command files are large
   (`exec-rev-wrap-ver.md` ≈ 29.7 k tokens, `plan-exec-rev.md` ≈ 26.4 k, and
   `CLAUDE.md` ≈ 12.8 k, all resident for the whole session), and subagent turns
   are 5–7× cheaper than main-loop turns. Is this task *observe only*, or
   observe-then-optimise?
6. **Multi-project rollup.** Is the model per-project (this repo) or across every
   project directory under `~/.claude/projects/`? The latter answers "what does
   harness-maker cost me overall" but leaves the project-local convention.
7. **Cost model for the second-opinion path.** `second_opinion.models` shells out
   to `codex` and `agy`, whose token usage never enters the Claude transcript at
   all. Accept as unmeasured, or record a per-invocation row in
   `second-opinion.jsonl`?

---

## 📚 Sources

- [Claude Code — Monitoring usage (OpenTelemetry)](https://docs.anthropic.com/en/docs/claude-code/monitoring-usage) — `claude_code.token.usage`, breakdown by model/subagent, `api_request` / `skill_activated` events; beta.
- [ryoppippi/ccusage](https://github.com/ryoppippi/ccusage) — prior art: local-JSONL cost analysis, per-model breakdown, offline cached pricing, 5-hour billing windows.
- [badlogic/cccost](https://github.com/badlogic/cccost) — instruments Claude Code for actual token/cost tracking.
- [ColeMurray/claude-code-otel](https://github.com/ColeMurray/claude-code-otel) — reference OTel observability stack.
- [SigNoz — Claude Code monitoring](https://signoz.io/docs/claude-code-monitoring/) — PromQL naming caveat; "total tokens tells you nothing about cost, prices differ by 50×".
- [AWS — Analyzing Claude Code usage with CloudWatch and OpenTelemetry](https://aws.amazon.com/blogs/mt/analyzing-claude-code-usage-with-cloudwatch-and-opentelemetry/) — org-scale rollup pattern; CloudWatch Coding Agent Insights (July 2026).

**Local evidence (measured during this research, not cited from the web):**
`~/.claude/projects/-home-noel-harness-maker/` — 50 session files, 101 MB;
`.claude/observability/metrics-2026-07-*.jsonl` — 2175 lines, 0 with non-zero
token fields; `src/harness_maker/telemetry.py:COST_PER_MTK`;
`src/harness_maker/cache_diagnostics.py` hit-test; rendered command sizes under
`.claude/commands/hm/`.

---

## 🔗 Related Internal Docs

- [[PLAN-cfr-churn-metrics]] — `/hm:metrics`, `delivery_metrics.py`; the existing
  read-only, explicitly-non-gate metrics surface and the natural host for a cost
  dimension. Its Goodhart framing applies verbatim.
- [[PLAN-locale-and-command-observability]] — established the command/banner
  observability injection mechanism and the `/hm:health` presence-audit pattern
  a cost-signal smoke test would follow.
- [[PLAN-session-tier-slim]] — precedent for removing a write-heavy, read-thin
  telemetry tier once it was shown to have no machine consumers; the same
  question now applies to the zero-token fields in `telemetry.py`.
- `[wiki:architecture] hooks-load-from-settings-not-hooksjson` — the prior
  instance of "a hook path was assumed to carry data it never carried"; the
  zero-token `PostToolUse` payload is the same failure class.
- `[fail:design] namespace-prefix-mistaken-for-authorship` — precedent that an
  inferred property (here: "the payload has `usage`") must be verified against a
  live artifact before anything is built on it.
