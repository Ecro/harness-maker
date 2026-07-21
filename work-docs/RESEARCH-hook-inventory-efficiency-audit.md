---
type: research
task_slug: hook-inventory-efficiency-audit
status: complete
created: 2026-07-21
tags: [harness-maker, research, hooks, autopilot, performance, session-friction]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: []
summary: "autopilot_persistent:true is the root of the recurring Stop-block; drop autopilot_guard blocking + narrow telemetry to cut per-tool-call overhead"
---

# RESEARCH — Hook inventory & session-friction audit

## 🎯 Recommended Direction

**The recurring "Stop hook error" the user hit is not a bug — it is `autopilot_guard`
doing exactly what `autonomy.autopilot_persistent: true` tells it to.** Every
SessionStart re-arms a fresh `.claude/.hm-autopilot` marker (18h TTL), and while the
marker exists `autopilot_guard` (a) refuses to let the session Stop and (b) blocks a
class of "never-auto" ops on **every Bash/Write PreToolUse**. For a solo, interactive
operator the autopilot feature buys little (it auto-advances pipeline stages) but taxes
every session with blocking + false positives.

**Recommended:** turn autopilot off at the source — `autopilot_persistent: false` and,
unless the user actively wants auto-advance, remove `autopilot_guard` from the blocking
paths entirely. Separately, narrow the always-on `telemetry` PostToolUse hook (fires on
*every* tool call, local-only) and delete the already-retired dead `.claude/hooks/hooks.json`.
The binding cut depth is `/hm:plan`'s call — this is informational.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** + **Risk / session-friction**.
Not a `--deep` run — the topic (own harness hooks) is concrete and inspectable directly
from source, so no refinement interview.

## 🛠️ Complete hook inventory (what fires, where, cost)

Three independent sources register hooks in this session:

### A. harness-maker → rendered into `.claude/settings.json` (the live location)

| Event | Matcher | Module | Blocking? | Fires… |
|---|---|---|---|---|
| PostToolUse | `*` | `telemetry` | no | **after EVERY tool call** |
| PostToolUse | Write\|Edit\|MultiEdit | `post_write_reminder` | no | after each edit |
| PreToolUse | Bash | `gates.permission_gate` | **yes** | before EVERY Bash |
| PreToolUse | Bash | `hooks.autopilot_guard` | **yes** | before EVERY Bash |
| PreToolUse | Write\|Edit\|MultiEdit | `gates.worktree_gate` | **yes** | before EVERY edit |
| PreToolUse | Write\|Edit\|MultiEdit | `hooks.autopilot_guard` | **yes** | before EVERY edit |
| PreToolUse | Write\|Edit\|MultiEdit | `gates.spec_gate` | **yes** | edits, spec-driven mode only |
| PreCompact | auto/manual | `flush_session` | no | on compaction |
| SessionStart | — | `sessionid_envfile` | no | session start |
| SessionStart | — | `autopilot_autoarm` | no | session start (**re-arms marker**) |
| Stop | — | `loop_gate --mode stop-hook` | control-flow | session end |
| Stop | — | `autopilot_guard --mode stop-hook` | control-flow | session end (**blocks Stop**) |

### B. harness-maker plugin bundle → `hooks/hooks.json` (plugin root)

| Event | Module | Note |
|---|---|---|
| SessionStart | `sessionstart_drift` | Deliberately NOT in settings.json (ADR-010) to avoid double-register for plugin users |

### C. Codex companion plugin (external, not harness-maker)

| Event | Hook | Note |
|---|---|---|
| Stop | `scripts/stop-review-gate-hook.mjs` (node) | The 3rd Stop hook in the user's transcript. Toggle via `/codex:setup`. |

**Net per-action cold-start cost** (each entry = one `uv run --with <path> python -m …`
cold Python process; node for the codex one):
- **1 Bash call → 3 processes**: permission_gate + autopilot_guard (Pre) + telemetry (Post)
- **1 Write/Edit → 3–4 processes**: worktree_gate + autopilot_guard (+ spec_gate) (Pre) + telemetry (Post)
- **1 Read/Grep/Glob/etc → 1 process**: telemetry (Post `*` matches everything)
- **SessionStart → 3 processes**; **Stop → 3 processes** (2 python + 1 node)

On WSL2/NTFS a `uv run --with` cold start is not free; multiply by every tool call in a
session and this is the "느리고 헤매는" latency the user feels.

## ⚠️ Pitfalls / concrete findings (observed live this session)

1. **`autopilot_persistent: true` = unkillable friction** (harness.yaml:174). Removing the
   marker does not fix it — the next SessionStart re-arms it. This is *by design* per the
   Production.json.j2 header comment ("with `autopilot_persistent: true`, autopilot_autoarm
   re-arms a marker at every SessionStart, so the block is unconditional for that population").
   Root cause of "자꾸 이렇게 반복."
2. **autopilot_guard false-positives on read-only inspection.** Twice this session it blocked
   benign commands — a `python3 -c "import json…"` dump of settings.json, and an `ls`/`find`
   over `.claude/plugins` — as `permission-surface-write`. The classifier is meant to be a
   read-only ALLOWLIST (Production.json.j2:36–42) but still trips on compound read-only
   commands that merely *name* permission-surface paths. It actively obstructed this research.
3. **The in-session off-switch exists but is undiscoverable.** The guard's own message
   says "Remove the `.claude/.hm-autopilot` marker" — which points at `rm` (in
   `permissions.deny` AND guarded → dead end). The *actual* clean remedy is
   `uv run --with <src> python -m harness_maker.autopilot off` (verified this session:
   exit 0, marker cleared, guard did NOT block it — `off` is not a "never-auto op"). The
   guard message should surface THIS command, not an `rm` that is fenced off. Doc-fix +
   guard-message fix candidate for the plan.
4. **Autopilot on a non-pipeline command has no advance target.** `/harness-maker:make --update`
   is not a pipeline stage, so the guard blocks Stop with nothing to advance to — pure dead
   friction, exactly the user's scenario.
5. **Stale dead `.claude/hooks/hooks.json` still on disk** — pinned to `0.39.0`, retired in
   0.42 (its FileSpec removed, ADR P0 #1). Claude Code never reads it (confirmed 2026-07-17
   experiment; see [[project_hooks_json_not_read_by_claude]]). Pure dead weight + a reader trap.
6. **`telemetry` PostToolUse on `*`** fires after every single tool call and is 100% local
   (no external send). `metrics.jsonl` is a known legacy trap ([[project_hooks_json_not_read_by_claude]]).
   Highest-frequency hook in the session; its marginal value for a solo operator is low.
7. **Three Stop hooks stack** (loop_gate + autopilot_guard + codex mjs). Only loop_gate has a
   real interactive purpose (letting `/hm:loop` reach iteration 2), and it no-ops outside loops.

## ✅ Decisions locked (2026-07-21, user)

- **Scope: "autopilot 근원 제거"** — `autonomy.autopilot_persistent: false` AND remove
  `autopilot_guard` from both PreToolUse groups (Bash, Write|Edit|MultiEdit) **and** the
  Stop group. Keep `loop_gate` (Stop) and `permission_gate`/`worktree_gate` (PreToolUse).
- **Apply depth: templates source (ship to all harnesses)** — edit
  `templates/settings/{Production,Side}.json.j2` + the interview/synthesize default for
  `autopilot_persistent`. This is a shipped behavior change → 5-file version bump + release
  path (CLAUDE.md §버전업/§릴리스). Also re-render this repo's own `.claude/settings.json`.
- **Follow-on (not yet decided, defer to plan):** telemetry `*` narrowing, dead
  `.claude/hooks/hooks.json` deletion, codex Stop gate — user chose the focused
  "근원 제거", not the full "전면 감사". Plan may include the dead-hooks.json deletion as a
  trivial rider but should NOT expand into telemetry/codex without a further OK.

## ❓ Open Questions (for `/hm:plan` to lock)

1. **Autopilot: off or narrow?** Options: (a) `autopilot_persistent: false` only — keeps
   opt-in per-session picker but stops auto re-arm; (b) additionally drop `autopilot_guard`
   from the 2 PreToolUse groups + Stop (keep the feature dormant/removed). How aggressive?
2. **Telemetry: keep, narrow, or drop?** If local metrics are unused, drop the `*` PostToolUse
   hook (biggest per-call win). Or narrow matcher to Write\|Edit only.
3. **Do these changes go to the rendered `.claude/settings.json` (this repo's own harness) only,
   or into the `templates/settings/*.json.j2` source** (so every user harness inherits the
   change)? The user works ON harness-maker, so likely both — but that is a shipped behavior
   change needing the version-bump + release path.
4. **Immediate unblock — SOLVED this session:** `uv run --with <src> python -m
   harness_maker.autopilot off` clears the marker in-session (guard allows it). Plan should
   (a) fix the guard's Stop/block message to print THIS command instead of the dead `rm`
   hint, and (b) decide whether `/hm:health` or help should surface it.
5. **Codex Stop gate** — keep or disable via `/codex:setup`? Out of harness-maker scope but
   part of the felt friction.

## 📚 Sources

- Direct source inspection (no external fetch): `.claude/settings.json`,
  `src/harness_maker/templates/settings/Production.json.j2`, `hooks/hooks.json`,
  `src/harness_maker/hooks/*.py`, `.claude/harness.yaml` autonomy block.
- Live reproduction: `autopilot_guard` blocked two read-only Bash calls during this session.

## 🔗 Related Internal Docs

- [[project_hooks_json_not_read_by_claude]] — `.claude/hooks/hooks.json` not read by Claude Code; metrics.jsonl legacy trap.
- CLAUDE.md §Plugin 구조 (hooks schema divergence, 2026-07-17 correction), §autopilot picker/advance in `templates/commands/hm/research.md.j2`.
- `PLAN-permission-deny-and-hooks-wiring` (ADR-006 staging, ADR-010 sessionstart_drift dedup).
