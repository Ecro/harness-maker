---
type: baseline-delta
task_slug: pipeline-env-fixes
created: 2026-11-10
owns: [surface_baseline]
summary: "SPEC-pipeline-env-fixes' shipped-surface growth: `--no-project` in every rendered harness-maker invocation, wrapup's exit-2 rule and full observe example"
---

# Baseline delta — PLAN-pipeline-env-fixes

The shipped surface **grew** by 294 chars (claude) and 112 chars (codex). Every rendered
harness-maker invocation gains `--no-project ` (13 chars): without it uv created `.venv` and an
untracked `uv.lock` in the user's project, and `task-land` then refused forever (IRR-001). Wrapup
also gains the exit-2 rule (`2: fix the call; `, 17 chars) and the full `observe` example
(`--relation <confirms|supersedes|contradicts>` replaces `…`, +43), which is AC-007.

Nothing was trimmed to pay for it: the flag is a fixed token at each call site, and the DRI chose to
raise the budgets by the measured growth only (decision card, 2026-11-10).

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`). "Before" is the surface after PLAN-hm-cost-p4 (its fold re-freezes the
baseline to these numbers).

| variant | command | before (chars) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 7 989 | 8 002 | the CLI prefix line |
| claude | `execute` | 9 219 | 9 232 | the CLI prefix line |
| claude | `research` | 4 879 | 4 892 | the CLI prefix line |
| claude | `wrapup` | 6 300 | 6 373 | prefix (+13), exit-2 rule (+17), observe example (+43) |
| claude | `metrics` | 2 968 | 2 981 | one invocation |
| claude | `health` | 7 449 | 7 514 | five invocations |
| claude | `make` | 6 606 | 6 671 | five invocations |
| claude | `uninstall` | 1 691 | 1 730 | three invocations |
| codex | `hm-spec` | 8 083 | 8 096 | same text as the Claude command |
| codex | `hm-execute` | 9 222 | 9 235 | same |
| codex | `hm-research` | 4 936 | 4 949 | same |
| codex | `hm-wrapup` | 6 382 | 6 455 | same |

| key | before | after | Δ |
|---|---|---|---|
| `aggregate_chars`.claude | 48 965 | 49 259 | +294 |
| `aggregate_chars`.codex | 30 420 | 30 532 | +112 |

Round trips are unchanged in every command.

AC-004 stage budgets (`tests/unit/test_overhaul_p1_surface.py`): spec 6 950 → 6 963, execute
7 610 → 7 623, wrapup 3 900 → 3 973; the commands compared with the db19f023 reference render get
13 chars per harness-maker invocation they carry. The Maker skill's cap (`_MAKER_CAP`, CLAUDE.md, `docs/reference/world-model.md`) rises
4 500 → 4 539 for its three invocations; no wording was trimmed. The growth is held as this PLAN's
`surface_allowance` until the task lands; the baseline is then re-frozen from main in a fold commit.

Per ADR-010 the task that moved the surface owns its attribution, and writing it next to the
allowance and the later re-freeze is what keeps this out of `ratchet-rebaselined-by-its-own-subject`.
The surface rose (+0.6% claude, +0.4% codex) only by the `--no-project ` flag at each harness-maker
call plus wrapup's exit-2 rule and `observe --relation` example; nothing else in the prose changed.

## Folded into the baseline from main

After PR #48 squash-merged the task as 636e9f49 the PLAN was marked complete, which expires its
allowance, so the growth was folded on main: `tests/structural/surface_baseline.json` re-frozen by the
generator at 636e9f498813 (claude 49 259, codex 30 532, the after column above; `render_sha` and
`payload_digest` moved mechanically with the re-freeze). `_ATOMIC_RATCHET` is unchanged: the atomic
renders grew by 13 (execute, spec) and 73 (wrapup) chars, inside its ±2% band. The bench rows
measured before this task keep `bench_hash` 569e17ef29ab and need no alias: no measurement ran on the
task branch.
