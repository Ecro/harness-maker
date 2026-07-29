---
type: baseline
task_slug: workflow-step-audit
status: frozen
created: 2026-07-29
plan: "[[PLAN-workflow-step-audit]]"
research_doc: "[[RESEARCH-workflow-step-audit]]"
summary: "Pre-change measurement freeze + pre-registered direction for the round-trip reduction"
---

# BASELINE — workflow-step-audit (Phase 0)

**This document is frozen.** [ADR-011](PLAN-workflow-step-audit.md#adr-011) forbids
recomputing the baseline from post-change output; [ADR-012](PLAN-workflow-step-audit.md#adr-012)
requires the direction below to be registered *before* any post-change measurement
exists. Later phases append nothing here — Phase 7 writes its own receipt and compares
against this file.

## Re-freeze, 2026-07-29 — read this before citing any number below

The surface and instruction baselines were first frozen at `bc6932b2`, then **re-frozen
at `3f7d587b`** when a concurrent session landed `feat(delegation): make the wrapup gate
resolvable` on `main`. That commit edits `templates/stages/verify.md.j2` (+25 lines) and
`templates/stages/wrapup.md.j2` (+89 lines) — the two templates Phases 1 and 2 of this
PLAN cut.

This is not a violation of [ADR-011](PLAN-workflow-step-audit.md#adr-011)'s "never
recompute the baseline". It is the rule's purpose: a baseline is pre-change **with
respect to this PLAN's changes**, and at re-freeze time nothing had been cut. Keeping the
`bc6932b2` freeze would have made `test_aggregate_shipped_surface_does_not_grow` charge
another commit's +114 lines to this PLAN the moment it landed — risk **R13**, verbatim.

The re-freeze is legitimate exactly once, and only in this window. **After Phase 1 cuts
anything, a re-freeze is forbidden**; a later concurrent landing must be handled by
`task-refresh` plus a per-command floor adjustment owned by the phase that cut, per
ADR-011's re-baseline protocol.

The §2–§4 measurements below are unaffected: they come from the transcript corpus and
`economics`, neither of which depends on the render.

## Provenance

| Field | Value |
|---|---|
| Frozen at | 2026-07-29 (re-frozen — see above) |
| Render SHA | recorded in `tests/structural/surface_baseline.json` → `render_sha` |
| Machine surface baseline | `tests/structural/surface_baseline.json` |
| Generator | `tests/structural/_surface_baseline.py` (committed; Phase 6 re-invokes it) |
| Transcript window | 47 transcripts under `~/.claude/projects/-home-noel-harness-maker/` |
| Turn/cost instrument | `harness_maker.economics report --root .` |
| Carry instrument | `harness_maker.economics composition --root .` |
| Wall-clock instrument | active-time accumulation with a **300 s idle-gap cap** |

### Why the render is produced in-process

This repo gitignores `.claude/*`, so there is no committed rendered harness to measure
and a fresh worktree has none on disk at all. The generator therefore renders from the
repo's committed `.claude/harness.yaml` **in-process**, which makes the render fresh by
construction — the concern [[RESEARCH-workflow-step-audit]] Pitfall 9 raised (freezing a
baseline against a stale on-disk render, permanently crediting an earlier hoist to this
PLAN) cannot arise on this path. `render_sha` pins *which templates* produced the
numbers.

### Two target variants, not three

`.cursor/commands/` is dead code in the renderer (`src/harness_maker/render.py:571-582`
— "no template feeds `.cursor/commands/`"), so Cursor loads the Claude render and there
are exactly two distinct rendered artifacts: `.claude/commands/hm/*.md` and
`.agents/skills/hm-*/SKILL.md`. [ADR-011](PLAN-workflow-step-audit.md#adr-011)'s note
that "the Cursor variant is counted by the Claude rule" holds trivially — the Cursor
variant *is* the Claude file.

## 1. Per-stage turn share

`economics report --root .` → `by_stage`, summed over all four work categories.
n = 25,035 classified turns.

| Stage | Turns | Share |
|---|---:|---:|
| (unattributed) | 7,175 | 28.7% |
| `hm:execute` | 4,910 | 19.6% |
| `hm:review` | 4,835 | 19.3% |
| `hm:wrapup` | 3,051 | 12.2% |
| `hm:plan` | 2,769 | 11.1% |
| `hm:research` | 879 | 3.5% |
| `hm:make` | 398 | 1.6% |
| `harness-maker:make` | 342 | 1.4% |
| **`hm:verify`** | **243** | **1.0%** |
| `hm:spec` | 210 | 0.8% |
| `hm:metrics` | 193 | 0.8% |
| `claude-api` | 30 | 0.1% |

## 2. Active wall-clock and main-loop turns per run

300 s idle-gap cap; `runs` counts `<command-name>` occurrences in the transcript window.
Total active time across all stages: 4,196 min.

| Stage | Active min | Share | Runs | min/run | Assistant turns | **turns/run** |
|---|---:|---:|---:|---:|---:|---:|
| `/hm:execute` | 936 | 22.3% | 15 | 62.4 | 4,323 | **288.2** |
| `/hm:wrapup` | 587 | 14.0% | 17 | 34.5 | 3,079 | **181.1** |
| `/hm:research` | 506 | 12.1% | 12 | 42.2 | 1,880 | **156.7** |
| `/hm:plan` | 439 | 10.5% | 10 | 43.9 | 1,720 | **172.0** |
| `/hm:review` | 235 | 5.6% | 10 | 23.5 | 890 | **89.0** |

`/compact` accounts for a further 936 min (22.3%) at 358 turns/run. It is session
management, not a pipeline stage, and is listed here only so the shares above are read
against the right denominator.

`hm:verify` and `hm:spec` do not appear in this table: neither was invoked as a
standalone slash command inside the transcript window (both run fused inside
`exec-rev-wrap-ver`). Their turn counts in §1 are the attribution instrument's, not this
script's. **This is the reason the pre-registered direction in §5 is stated per run and
sourced from `economics`, not from this table.**

## 3. Scope split — main loop vs subagents

| Quantity | Main loop | Subagents |
|---|---:|---:|
| Wall-clock (s) | 257,612 | 55,555 |
| Wall-clock (min) | 4,293.5 | 925.9 |
| Spend (USD) | 5,101.63 | 728.51 |
| Share of spend | **87.5%** | 12.5% |

Total priced spend 5,830.14 USD over 25,032 turns.

## 4. Carried-context composition

`economics composition --root .`; total 25,098,634 chars of transcript.

| Component | Share |
|---|---:|
| **Carry ratio (main loop)** | **0.6585** |
| slash-command bodies | 17.44% |
| `grep`/`rg` output | 10.79% |
| file inspection (`cat`/`head`/`ls`/`find`) | 5.16% |
| assistant text | 5.52% |
| `harness_maker` CLI output | 4.34% |
| pytest output | 3.42% |
| git diff/show/log | 1.14% |
| git (other) | 1.13% |
| heredoc file-write | 1.09% |
| compaction summaries | 0.87% |
| human-typed | 0.14% |

`write_after_read`: 422 write calls, 2,992,576 chars, of which **845,652 chars (28.3%)
across 63 calls** are re-sends of content already in context.

## 5. Pre-registered direction (ADR-012)

Registered **before** any post-change measurement exists. Phase 7 must evaluate it.

> **PR-1 (binding).** `hm:verify` **main-loop turns per run** must be *strictly lower*
> post-change than pre-change, measured with the same instrument and the same 300 s
> idle-gap methodology.

If PR-1 does not hold, Phase 7's receipt must either explain the discrepancy or the
verify composite is reverted. Without a direction fixed in advance the receipt is a
description, not a check.

**Secondary, non-binding expectations** — recorded so that a surprise is visible as a
surprise rather than being reinterpreted after the fact. None of these can fail the
phase on their own:

- `hm:wrapup` main-loop turns per run: expected to fall (git tail 7 calls → 3).
- `hm:research` main-loop turns per run: expected to fall; **subagent turns expected to
  rise**, and total compute with them ([ADR-010](PLAN-workflow-step-audit.md#adr-010)).
- Carry ratio: **direction not predicted.** Three digests plus verbatim snippets re-enter
  the main-loop prefix, so the fan-out could move it either way. It is reported because
  it is the quantity most at risk, not because a direction is being claimed.
- Aggregate rendered surface: required to be lower, but that is
  [ADR-011](PLAN-workflow-step-audit.md#adr-011)'s ratchet arm, asserted by a test rather
  than observed in a receipt.

## 6. What Phase 7 must report

Per stage, pre and post, each with its own `n`, labelling any `n < 3`:

1. main-loop assistant turns per run,
2. subagent turns per run,
3. active wall-clock per run (300 s idle-gap cap),
4. mean context / carry ratio.

No single combined efficiency figure — a latency win paid for in compute or in carry
must be visible as exactly that.
