---
type: baseline-delta
task_slug: codex-lens-dispatch
created: 2026-08-16
owns: [surface_baseline.json]
summary: "Baseline movement from rendering Codex-native spawn_agent instead of Claude-only Task("
---

# Baseline delta — codex-lens-dispatch

Baseline ownership follows **ADR-010**: one phase owns the ratchet, and a phase that
re-baselines the guard it tripped is `ratchet-rebaselined-by-its-own-subject` (count:2).
This document is this task's own attribution — it does not amend any previous task's.

Figures written **after** the final regeneration, which for this task meant regenerating
twice: once after the template migration and again after `count_round_trips` changed. The
first set was stale within the same session. That ordering trap is documented four times in
`BASELINE-DELTA-validator-pass-cap.md` and it fired here too.

## 1. Aggregate

| | Before | After | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 416 951 | 417 164 | **+213** |
| `aggregate_chars.codex` | 344 923 | 349 105 | **+4 182** |

**Direction: the shipped surface got LARGER, asymmetrically — and the asymmetry is the point.**
The Codex arm grows ~8× the Claude arm because the intent sentence ADR-002 makes normative
renders **only** on the Codex arm. That is the mitigation for a real, measured risk: two
`spawn_agent` schemas exist in Codex CLI 0.147.0 (`agent_type`/`message` from the live
`codex exec` probe, `task_name`/`fork_turns` in the shipped `multi_agents_v2` handlers), only
one is verified, and a hardcoded literal that drifts fails **silently** — which is the failure
this whole task exists to remove. The Claude arm pays **+205 for the macro's line-shape changes and +8 for the round-3 Pass-1
rewording** (`review.md.j2:270-271`, 46→54 chars — which is why both arms move by the same 8),
and nothing for the **Codex** intent sentence; `dispatch_intro` does emit a one-line Claude sentence ("Dispatch each item
below with the `Task` tool."), which is part of that +213.

**Review round 1 raised the Codex figure from +1 635 to +4 174, and round 3 added the last +8.**
Round 1's ~2.5k is one paragraph — the **join contract**; round 3's +8 is the Pass-1 rewording,
not the join. (The figures were re-measured after each round and the surrounding attribution was
not, which is the same defect this document records twice above.) `spawn_agent` returns when an agent *starts*, not when it
answers — collection is a separate step. The stage prose then declares "a dispatch that returns
nothing produces no file; that absence is the signal", so on the runtime where this fan-out has
never actually run, a still-in-flight agent would have been read as a dead lens — reproducing
the exact symptom this task fixes, now with seven sub-agents genuinely running. Specifying the
fork without the join was the defect; the paragraph is the fix, and it renders once per dispatch
block on the Codex arm only.

`render_sha` and `payload_digest` moved as well. Both are mechanical: they are content hashes
of the render, so any byte change moves them by construction. They carry no independent
information about this task and are listed here only so their movement is attributed rather
than unexplained.

## 2. Attribution by phase

| Phase | What moved the baseline | Direction |
|---|---|---|
| 1 | `agents/_partials/dispatch.md.j2` (new). Renders nothing on its own. | 0 |
| 2 | 5 templates migrated to the macro. Adds `dispatch_intro` once per dispatch block on the Codex arm; collapses two multi-line `Task(` calls to one line on both. | Codex ↑, Claude ≈0 |
| 3 | `step_manifest.md.j2`'s autopilot picker names the runtime's own question tool (`request_user_input` on Codex). | ~0, both |
| 6 | `Next:` banner rewritten through `stage_invocation` — `@hm-execute` on Codex. Same length, different bytes. | ~0 |

## 3. Round-trip counts — a rule correction, not a behaviour change

`_CLAUDE_ROUND_TRIPS`: `loop` 12→10, `plan` 18→15, `review` 37→36, total **165→159**.
Codex total **133→127**.

> **Corrected in review round 1 — this said `110→127`.** 110 was the OLD rule applied to the
> NEW render, i.e. a hypothetical, not the committed before-value. The committed baseline's
> Codex column sums to **133**, which §4's per-skill table shows directly. So the movement is
> a **−6 drop**, not a +17 rise, and the earlier text reported a shrink as growth — in a
> document whose whole job is to attribute the ratchet's movement.

**No mandated call was added or removed.** `count_round_trips` used a bare
`text.count("Task(")` for both variants, which was wrong twice:

- it charged backticked **prose** as a round trip — a paragraph reading "retry the
  `Task(...)` call" cost one, and rewriting that sentence runtime-neutrally is why `loop`
  dropped by 2 without a single call changing;
- it named the **Claude** tool for both arms. That was harmless only while Codex output still
  carried `Task(` — the old baseline scored `hm-review` at 33, so the counter was **not**
  previously blind. **This task is what stops Codex carrying `Task(`.** Left alone, the rule
  would have scored that fourteen-dispatch fan-out at **zero** from this commit onward: a
  budget going blind at the exact moment the thing it measures changed spelling.

> **Corrected twice.** The `hm-review: 32` figure above was wrong: 32 was that skill's
> all-markers, both-presets total transcribed as a `Task(`-only count, and the committed
> baseline refutes it. And the first version of this section claimed the Codex arm had *always*
> counted zero. It had not — 33 is in the committed baseline. The defect is prospective, not
> historical, and overstating it would have made the rule change look like a bug fix when it
> is a guard against one this task would otherwise have introduced.

Both arms now count their own call-site form, so prose is excluded on both and neither
runtime's dispatches are invisible.

## 4. Per-command rows

Claude variant (`.claude/commands/hm/*.md`):

| Command | chars | Δ | round_trips | Δ |
|---|---|---|---|---|
| `execute` | 42 617 → 42 664 | +47 | 18 → 18 | 0 |
| `loop` | 52 897 → 52 893 | −4 | 12 → 10 | −2 |
| `plan` | 59 075 → 59 096 | +21 | 18 → 15 | −3 |
| `research` | 26 176 → 26 175 | −1 | 8 → 8 | 0 |
| `review` | 82 276 → 82 389 | +113 | 37 → 36 | −1 |
| `spec` | 31 853 → 31 852 | −1 | 6 → 6 | 0 |
| `verify` | 22 226 → 22 225 | −1 | 13 → 13 | 0 |
| `wrapup` | 47 558 → 47 597 | +39 | 29 → 29 | 0 |

Codex variant (`.agents/skills/hm-*/SKILL.md`):

| Skill | chars | Δ | round_trips | Δ |
|---|---|---|---|---|
| `hm-execute` | 39 702 → 40 564 | +862 | 17 → 17 | 0 |
| `hm-loop` | 51 805 → 51 801 | −4 | 13 → 11 | −2 |
| `hm-plan` | 52 442 → 53 351 | +909 | 17 → 14 | −3 |
| `hm-research` | 23 780 → 23 782 | +2 | 7 → 7 | 0 |
| `hm-review` | 76 210 → 77 698 | +1 488 | 33 → 32 | −1 |
| `hm-spec` | 29 122 → 29 124 | +2 | 5 → 5 | 0 |
| `hm-verify` | 19 616 → 19 618 | +2 | 12 → 12 | 0 |
| `hm-wrapup` | 44 885 → 45 806 | +921 | 29 → 29 | 0 |

The four Codex skills with a **+860…+1 488** char move are exactly the four that carry a
dispatch block (`hm-execute`, `hm-plan`, `hm-review`, `hm-wrapup`); the growth is
`dispatch_intro`, once per block. `hm-review` carries two blocks and grows most. The ±1…4
moves elsewhere are the `Next:` banner and the picker's tool name — same length class, changed
bytes. `hm-loop` shrinks on both arms because its two `Task(...)` prose mentions became
runtime-neutral wording.

## 5. What this bought

The defect, measured on this repo's own render before the fix: Codex output carried `Task(`
**18** times across 9 files per preset — 36 across the two rendered presets — with `hm-review`
carrying **14** of them (seven lenses x two dispatch blocks). A tool Codex does not have. Observed
consequence in a real user harness (`~/strange_chess`): a Codex `/hm:review` wrote **zero**
lens result files, so `hm lens_coverage check` reported all four mandatory Side lenses missing
and the review was permanently unapprovable. After: `Task(` **0**, `AskUserQuestion` 15→**1** per preset (30→2 across both — one
deliberate documentation line naming both tools, allowlisted), `Skill(` 0.
