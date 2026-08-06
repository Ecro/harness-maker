# Surface-budget ledger — PLAN-onboarding-interview-ux Phases 5–6

Measured 2026-08-06 via `tests/structural/_surface_baseline.measure_surface()`, the same
generator `test_aggregate_shipped_surface_does_not_grow` uses.

## Variant scope

| Variant | Contains `configure` / `health`? | Delta |
|---|---|---|
| `claude` (`.claude/commands/hm/*.md`) | yes | see below |
| `codex` (`.agents/skills/hm-*/SKILL.md`) | **no** | **0, structurally** |

`synthesize._base_files` renders `configure.md.j2` and `health.md.j2` into the claude set
only; `_codex_target_files` carries the seven stage skills plus loop, loop-p5-batch and help.
So the per-variant analysis ADR-005 originally called for is vacuous for these two files, and
every number below is claude-only. Confirmed empirically at each pass: codex delta stayed 0.

## What was added

| Item | Surface | Ratchet-visible? |
|---|---|---|
| `/hm:configure` — three menu entries (second opinion, autopilot, locale) | `configure.md.j2` | yes |
| `/hm:configure` — dispatch appendix with clear-vs-preserve semantics | `configure.md.j2` | yes |
| `/hm:health` — installed-but-disabled advisory | `health.md.j2` | **no — see below** |

The advisory is wrapped in `{% if not (config.second_opinion and config.second_opinion.models) %}`.
The baseline renders **this repo's** `harness.yaml`, whose `models` is `["codex","antigravity"]`,
so the block is absent from the measured surface. Its measured contribution is **+1 char** — a
newline, not content. Its correctness is therefore proven by
`tests/unit/test_render_configure_health_second_opinion.py`, never by a green aggregate test.
That blind spot is recorded as R8 in the PLAN.

## Compaction

| Pass | claude delta | Cut |
|---|---|---|
| raw addition | **+1162** | — |
| 1 | +847 (−27%) | `Default model` orphaned continuation (a dangling fragment after a full stop); `Delivery metrics tuning` 7 lines → 5; the four repeated "Omit `--x` when … ; pass `\"\"` to clear" sentences → one rule |
| 2 | +711 (−39% cum.) | the three new entries themselves tightened; `Worktree isolation`, `Reference folders`, `Sibling repos` trade-off clauses |
| 3 | **+604 (−48% cum.)** | §3's `Reference folders` / `Sibling repos` numbered sub-blocks → prose |

## Residue: +604, and why compressing it further would delete correctness

Judged per item, against the bar the four prior raises set:

- **`second_opinion` entry** — before this, `/hm:configure` named the axis nowhere, so a
  harness installed with it off could only be changed by hand-editing `harness.yaml`. This is
  the *only discoverable way* to change it — the same sentence the `configure +210` raise of
  2026-08-06 used, and it is literally true again here.
- **`autonomy` entry** — same, plus the mandatory-gate list. Dropping that list invites the
  reading that `full` skips the plan interview and the wrapup merge, which it does not.
- **`locale` entry** — the shortest of the three; already one sentence.
- **clear-vs-preserve appendix** — omit-preserves / `""`-clears is a data-loss boundary. An
  executor that guesses wrong silently wipes a neighbouring setting (codex `4ee3418e`).
- **`detect-tools` + "presence, not authentication"** — without it, "detected" reads as
  "ready", and the user enables a model whose first real call degrades to a skip.

What was cut instead was prose that restated the same fact twice, numbered a single question,
or repeated a rule per-flag that holds for all flags.

## Raise applied

`tests/structural/surface_baseline.json`, four coupled fields (there is no constant in
`test_command_size_budget.py` — that file holds only the prose precedents and
`_ATOMIC_RATCHET`, which excludes `configure` and `health` entirely):

| Field | Before | After (Phase 6) | Final (after review rounds 2–3) |
|---|---|---|---|
| `surface.claude.configure.chars` | 9910 | 10513 | **10746** |
| `surface.claude.health.chars` | 9815 | 9816 | 9816 |
| `aggregate_chars.claude` | 361582 | 362186 | **362419** |
| `payload_digest` | — | recomputed | recomputed via `_surface_baseline.payload_digest` |

### Review rounds 2–3: +233 more (raw +233 → compacted → +233 net after two corrections)

`/hm:review` graded the Phase-6 text **D** and the fixes cost more bytes. Accounting, same bar:

| Pass | claude delta over the Phase-6 baseline | Cause |
|---|---|---|
| round 2 raw | +233 | `uv run --with` resolution prefix (the bare `hm cli detect-tools` call was unrunnable in the default install shape); its degrade clause; corrected cost statement; egress disclosure |
| round 2 compaction | +158 (−32%) | tightened the same entry |
| round 3 | +67 | preset-qualified the cost line (Production every time, Side high-diff only) and moved the call into a fenced `!` block — an inline `!uv run` inside a sentence is not autorun, and `bash` reads `!uv` as a command word |
| round 3 reflow | +8 above that | kept "presence, not authentication" on one line; a wrap between the two words broke the render assertion that checks the phrase is present |

**Why this residue is not prose either.** Each item is a confirmed review finding: a call that
would have failed with `command not found`, a cost figure that was wrong in two directions
(per-model, and plan as well as review), a data-egress disclosure the consent surface omitted
while `PRIVACY.md` tells the same user nothing leaves the machine, and a `!` that did not
execute. Compressing any of them restores a defect.

**A sixth gate fired here** and is worth recording next to the ratchet: `test_roundtrip_budget`
counts mandated CLI round-trips per command. Moving the call from an inline backtick into a
fenced `!` block made it countable — `configure` 3→4, shipped total 130→131 — re-baselined with
a named cause in that file. `health` stayed at 7 because its identical call renders under
`{% if not config.second_opinion.models %}` and this fixture's harness has models set.

`render_sha` deliberately unchanged: this is a targeted raise, not a re-freeze.
`build_baseline()` was **not** invoked — `assert_sha_is_durable` hard-refuses from a task
branch, and a full re-freeze is a base-checkout operation.
