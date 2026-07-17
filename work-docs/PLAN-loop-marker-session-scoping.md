---
type: plan
task_slug: loop-marker-session-scoping
status: complete
created: 2026-06-21
tags: [harness-maker, plan, python, jinja2, loop, concurrency, hooks]
research_doc: ""
status_note: "P1-P6 all implemented + GREEN 2026-06-21; feature complete, reviewed Grade A"
interview_rounds: 3
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Make /hm:loop fully parallel-safe by session-scoping loop-active state (kill the global .hm-loop-active)"
---

# PLAN — loop-marker-session-scoping

## 🎯 Executive Summary

**TL;DR.** `/hm:loop` is not safe to run in parallel across sessions because one
artifact — the hand-touched global `.hm-loop-active` file at the project root —
is session-blind. Two concurrent loops share that single file, producing two
cross-session bugs. This PLAN session-scopes loop-active state so N loops (and
any number of idle sessions) coexist with zero interference, with **no user
action required**.

**What / Why.**
- **Bug 1 (Stop-hook cross-kill):** session A's loop-close runs `rm -f
  .hm-loop-active`, which deletes the marker session B's loop still depends on →
  B's Stop-hook guard silently dies → B can terminate mid-loop.
- **Bug 2 (loop-mode false positive — severe):** a *standalone* `/hm:plan` in
  session B reads `<project-root>/.hm-loop-active`, sees session A's loop marker,
  and enters loop-mode → it **skips the deep interview** and writes a per-iter
  plan instead of a real one. Silent plan corruption.
- Same false-positive also wrongly suppresses START/END banners and the
  autopilot picker in unrelated sessions.

The per-session marker scheme `.claude/.hm-loop-{key}` already exists (ADR-006 of
PLAN-loop-stop-hook-enforcement) and `worktree_gate` already handles parallel
sessions correctly by globbing+unioning all such markers. The fix unifies the
remaining session-blind consumers onto a **session-scoped, `session_id`-keyed**
form of that same scheme and removes the global file from the primary path.

**Key decisions.**
- ADR-001 — Eliminate global `.hm-loop-active` from the primary path; unify all
  consumers on the existing `.claude/.hm-loop-*` per-session scheme.
- ADR-002 — Make loop-active state Claude-session-aware by embedding
  `claude_session_id` in the marker **content** (filenames stay worktree-keyed —
  no storage-contract break). The session's own Bash learns its id via a
  SessionStart hook that writes `HM_SESSION_ID` into `CLAUDE_ENV_FILE`; the
  Stop-hook reads `session_id` from its payload and matches it against marker
  *content*.
- ADR-003 — Explicit absent-case fallback (no `claude_session_id`): LLM detection
  falls back to cwd→worktree containment; Cursor/Codex use that scoped path (NOT
  the global). On Claude Code a missing `HM_SESSION_ID` is **loud** (startup check
  + `/hm:health` smoke), and only then writes the legacy global `.hm-loop-active`.
  Stop-hook order: content-match first, legacy-global only when no content match.
- ADR-004 — Auto-prune stale **session** markers (content-gated) at
  `worktree create`. The global `.hm-loop-active` is NOT auto-pruned (it carries
  no ownership proof) — loop-close owns its removal + a warning surfaces orphans.
- ADR-005 — Keep the Claude `session_id` (loop-marker identity, in content)
  strictly separate from the worktree dirname `session_uuid` (registry /
  finalize-stash identity, in filename). Enforced by NOT renaming filenames.
- ADR-006 — Sanitize/validate `session_id` (a hook payload field) before any
  filesystem use: strict hex/UUID allowlist, else `sha256(session_id)[:16]`.

**Estimated impact.** ~2 new/edited Python modules (1 new hook,
`worktree.py` marker helpers, `loop_gate.py`), 4 templates (`loop.md.j2`,
`plan.md.j2`, `step_manifest.md.j2`, `stage_end_summary.md.j2`), `hooks.json.j2`
(+ codex variant), CLAUDE.md, `/hm:health` smoke, snapshot regen, unit +
integration tests. No change to the worktree registry / 5-layer data-loss
defense.

## 🚧 Implementation Status (2026-06-21)

Executed in an isolated worktree (`--allow-dirty-base`, base HEAD `18c233e`).
First increment = the Python mechanism (the actual parallel-safety fix),
fully unit-tested + GREEN. Templates/docs/integration remain.

| Phase | Status | Notes |
|-------|--------|-------|
| (foundation) shared `loop_marker.py` | ✅ DONE | sanitizer + content schema + 3 parsers; 12 tests |
| P1 SessionStart env-file hook | ✅ DONE (code) | `hooks/sessionid_envfile.py` + 8 tests. **hooks.json.j2 registration deferred to P4** (snapshot change) |
| P2 worktree.py content schema | ✅ DONE | header in `_write_loop_marker`; `create`/CLI `--claude-session-id`; **all 4 readers** header-safe (`_read_active_worktrees`, `worktree_gate`, `_marker_referenced_paths`, `_session_worktrees`); 6 tests |
| P3 loop_gate Stop-hook content match | ✅ DONE | payload-first root + content session match + legacy-global fallback (H2 order); 8 tests |
| P4 templates + snapshots + SPEC-loop-gate | ✅ DONE | hooks.json.j2 (+codex) register `sessionid_envfile`; loop.md.j2 passes `--claude-session-id` + conditional global; plan.md.j2 + 2 partials detect via new `worktree loop-mode-active` CLI; 8 snapshots regenerated; SPEC-loop-gate AC-001 updated; 4 render-boundary tests + 5 CLI tests. **Feature now functional end-to-end.** |
| P5 CLAUDE.md + /hm:health loud smoke | ✅ DONE | CLAUDE.md `## Multi-session` → loop-marker session-scoping subsection; `readiness._dim_guardrails` `sessionid_envfile_registered` signal (loud on stale render); 3 unit tests |
| P6 parallel-session integration test | ✅ DONE | `tests/integration/test_loop_parallel_session.py` (HM_RUN_PARALLEL_SESSION-gated) — 4 real-subprocess scenarios: markers coexist, Stop-hook blocks only owner, loop-mode session-scoped, finalize leaves peer marker. All GREEN |

**P4 review-fix addendum (post k-of-3):** the unanimous review (cr×2 + concurrency
+ Codex) graded the P1-P3-only increment **D** — feature dead without wiring. P4
resolves consensus C1/C2/C3 (hook registration, `--claude-session-id`, conditional
global). Distinguishing signal: ONLY `loop.md.j2` passes `--claude-session-id`, so
a standalone `/hm:execute` worktree (empty content header) never trips the
Stop-hook — only loops do. New shared helper `loop_marker.marker_dir_has_session`
backs both the Stop-hook and the `loop-mode-active` CLI (one content-match rule).

**Verification this increment:** full unit suite exit 0; `ruff check` clean;
`mypy --strict` 111 files clean. **Validator W1 vindicated mid-execute** — the
`_session_worktrees` reader (a 4th marker reader not in the original phase list)
ingested the new header as a phantom worktree path and broke two finalize-stash
tests until switched to the explicit `startswith("/")` rule; this is exactly the
"header-skip must be explicit across ALL readers" warning.

## 📚 Prior Work

- **PLAN-loop-stop-hook-enforcement** — introduced the Stop-hook guard and the
  ADR-006 per-session `.claude/.hm-loop-{wt_name}` marker that `worktree_gate`
  reads. This PLAN extends that scheme's keying to `session_id` and migrates the
  last global consumers onto it.
- **PLAN-loop-mid-stop-and-review-skip** — owns the `plan.md.j2` Step 1.5
  loop-mode detection and the `.current-iter` Gate-0 contract. The detection's
  reliance on the global marker is exactly Bug 2.
- **PLAN-multisession-worktree-concurrency** / **-cross-session-data-loss-defense**
  — established session-UUID discipline and that the worktree dirname embeds a
  generated `session_uuid` (registry identity). ADR-005 here preserves that
  separation.
- **Session log callouts** — 2026-06 wrapups repeatedly flagged "the
  `.hm-loop-active` not-session-scoped gap (a single global marker)" as a real
  follow-up (P5, P6, P7 entries). This PLAN closes it.
- **CLAUDE.md absent-case mandate (count:8)** — any feature gating on an optional
  field MUST define the absent case explicitly. ADR-003 + a dedicated
  absent-case test satisfy it.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Marker architecture | Architecture | Unify loop-active state how? | **Eliminate global marker, reuse per-session `.claude/.hm-loop-*`** (vs keep root marker per-session / vs refcount) | ADR-001 |
| 2 | Stop-hook session identity | Contract | How does the Stop-hook tell "loop driver" from "idle session" at cwd=root? | **session_id via SessionStart env-file** (vs worktree-cwd correlation requiring driver to persist-cd into WT) | ADR-002, ADR-003 |
| 3 | Legacy + stale handling | Risk | How to handle existing global `.hm-loop-active` + crashed stale markers? | **Auto-migration + auto-prune** (vs legacy read-compat soak) | ADR-004 |

**User steer (verbatim intent):** "최대한 심플하면서 깔끔하고 유저가 전혀
신경 안써도 되도록" — maximally simple/clean, user must not have to care at all.
This biased every choice toward the option with the least user-facing surface
(automatic lifecycle, invisible hook, auto-migration).

**Pre-interview research that removed candidate ambiguities (not asked):**
- `.hm-session-uuid` is **project-scoped** (one shared file), so it cannot serve
  as a per-session key under concurrency — verified in `worktree.py:934`.
- `CLAUDE_SESSION_ID` is **not** an env var for slash-command Bash; `session_id`
  reaches Bash only via a SessionStart hook → `CLAUDE_ENV_FILE` (verified via
  claude-code-guide against official hooks docs). This made ADR-002's mechanism
  the only viable session_id source on the creation side.
- The loop driver keeps cwd=project-root (per-command `cd <WT> &&` subshells,
  `loop.md.j2`), so cwd-correlation alone cannot identify the driver session —
  the decisive fact behind rejecting the worktree-cwd-only option.

## 📐 Architecture Decision Records

### ADR-001: Eliminate the global `.hm-loop-active` from the primary path
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** A single global `.hm-loop-active` at the project root is shared by
every session, causing Stop-hook cross-kill and loop-mode false-positives.
**Decision:** All loop-active consumers (Stop-hook + the 3 LLM-facing templates)
resolve loop-active state from the existing `.claude/.hm-loop-*` per-session
markers (Claude-session-aware via marker *content*, ADR-002). The global file is
no longer written on the primary (Claude Code, SessionStart-present) path.
**Consequences:**
- ✅ N concurrent loops + M idle sessions coexist; no shared mutable file.
- ✅ Reuses the existing `.claude/.hm-loop-*` scheme + `worktree_gate` glob.
- ✅ Filenames are UNCHANGED → `_owned_session_uuids`, stash-ref recording, and
  prune content-gates keep working (addresses Codex H1).
**Rejected alternatives:**
- Keep a root marker but make it per-session (`.hm-loop-active-{id}`) — a second
  parallel scheme alongside `.claude/.hm-loop-*`; more code, two mechanisms.
- Refcount the single global file — fixes Stop-hook cross-kill but NOT the
  loop-mode false-positive (still "any session active"); fragile.
**Source:** Interview #1.

### ADR-002: Session-awareness via marker CONTENT + a SessionStart env-file hook
**Status:** Accepted (2026-06-21, via /hm:plan interview; revised per Codex H1)
**Context:** The Stop-hook fires at cwd=project-root for the loop driver, so cwd
cannot distinguish a loop driver from an idle session; `session_id` is the only
per-session signal in the Stop payload, but slash-command Bash cannot read its
own `session_id` directly. **Codex H1**: renaming the marker *filename* from
`{wt_name}` to `{session_id}` would break the existing storage contract
(`_owned_session_uuids` extracts the worktree UUID from the suffix; stash refs
record the marker path).
**Decision:**
1. A new SessionStart hook (`harness_maker.hooks.sessionid_envfile`) reads
   `session_id` from stdin and writes `HM_SESSION_ID=<id>` to `$CLAUDE_ENV_FILE`
   (idempotent). Every later Bash subprocess in that session sees `$HM_SESSION_ID`.
2. Marker **filenames stay worktree-keyed** (`.claude/.hm-loop-{wt_name}`). The
   Claude `session_id` is written as a **content header line**
   (`claude_session_id: <sanitized-id>`) above the worktree path list.
3. The Stop-hook reads `session_id` from its payload and **blocks iff some
   `.claude/.hm-loop-*` marker's content declares that `claude_session_id`** —
   never on another session's marker.
4. **No-isolation loops** (no worktree) write a content-only marker
   `.claude/.hm-loop-session-{sanitized-id}` (sanitized per ADR-006; the name
   cannot collide with the worktree-UUID extraction regex). `worktree_gate` reads
   no WT paths from it → imposes no write restriction (correct).
**Consequences:**
- ✅ Correctly guards the *driver* session at root, by content match.
- ✅ Works for isolation and no-isolation loops; one mechanism, content-keyed.
- ✅ Zero change to filename-suffix consumers (Codex H1 resolved).
- ⚠️ Claude-Code-specific (`CLAUDE_ENV_FILE`); Cursor/Codex → ADR-003 scoped path.
- ⚠️ SessionStart re-fires on resume/compact; the hook must overwrite, not append.
**Rejected alternatives:**
- Filename keyed by `session_id` — breaks the storage contract (Codex H1).
- worktree-cwd correlation only — fails for the driver at cwd=root; no-isolation
  loops get no guard.
**Source:** Interview #2 + Codex H1.

### ADR-003: Explicit absent-case fallback when `claude_session_id` is unavailable
**Status:** Accepted (2026-06-21, via /hm:plan interview; revised per Codex H2/H3)
**Context:** `HM_SESSION_ID` may be empty (SessionStart didn't fire, resume
before the hook, Cursor/Codex, stripped CI). Per CLAUDE.md count:8 the absent
case must be defined, not silently no-op. **Codex H2**: producer (loop start) and
consumer (Stop time) can disagree — the loop may write the legacy global while
the Stop-hook still receives a `session_id` on stdin. **Codex H3**: the legacy
global is itself not parallel-safe, so a silent degrade hides risk.
**Decision:**
- **Stop-hook order (resolves H2):** (1) if any marker content matches the
  payload `session_id` → block; (2) else if a legacy global `.hm-loop-active`
  exists → block; (3) else allow. The hook ALWAYS checks both, so a
  content-absent / global-present loop is still guarded.
- **LLM-facing detection** falls back to **cwd→worktree containment** (a stage is
  in loop-mode iff its cwd is inside a `.worktrees/<name>/` listed in an active
  marker). Standalone plan at cwd=root never matches.
- **Cursor/Codex** use the cwd→WT scoped path, **never** the global (resolves H3
  for those targets; Cursor never had a Stop guard anyway — advisory only).
- **Claude Code with a missing `HM_SESSION_ID` is LOUD, not silent (resolves
  H3/H6):** the loop startup prints a degraded-mode warning and `/hm:health`
  smoke-fails the env-file wiring. Only in that explicitly-surfaced degraded mode
  does the loop write the legacy global as a last resort.
- **Loop-invoked stages get the marker reference passed explicitly** (the driver
  already substitutes `<WT>`; it also passes the marker path / `HM_SESSION_ID`),
  so cwd-containment is a last resort, never the sole loop-mode signal (Codex H8).
**Consequences:**
- ✅ Primary (Claude Code) path fully session-scoped; both bugs fixed.
- ✅ Degraded mode is visible, not silent; Cursor/Codex stay scoped.
- ⚠️ Two code paths → the absent-case test (HM_SESSION_ID missing at create,
  `session_id` present at Stop) is mandatory.
**Rejected alternatives:**
- Hard-require `HM_SESSION_ID` — breaks resume / Cursor / Codex.
- Silent global fallback — Codex H3: hides an unproven-propagation risk.
**Source:** Interview #2 + Codex H2/H3/H6/H8.

### ADR-004: Auto-prune session markers; do NOT auto-prune the global
**Status:** Accepted (2026-06-21, via /hm:plan interview; revised per Codex H4)
**Context:** Crashed loops leave stale `.claude/.hm-loop-*` markers and possibly a
stale global `.hm-loop-active`. **Codex H4**: the global marker has no ownership
payload, so prune cannot prove it is stale vs. owned by a live fallback session.
**Decision:** Extend `prune_stale` (already invoked at `worktree create`) to
delete only **worktree-backed session markers whose listed worktree paths no
longer exist** (content-gated — same predicate as today). Three marker forms have
an EXPLICIT handling each (validator warning #3, CLAUDE.md count:8):
1. **Worktree-backed** `.hm-loop-{wt_name}` → content-gated auto-prune (as above).
2. **No-isolation** path-less `.hm-loop-session-{id}` → loop-close owns removal;
   a crashed orphan is **explicitly an accepted, benign leak** (its session_id is
   unique → never re-matches a future Stop payload, and it lists no WT paths → it
   contributes nothing to `worktree_gate`'s union). `prune_stale` **warns** on
   such orphans but does NOT delete them (no liveness oracle for a Claude session;
   time-based reap is banned per CLAUDE.md no-time-hooks). Documented limitation.
3. **Global** `.hm-loop-active` → NOT auto-deleted (no ownership payload, Codex
   H4); loop-close owns `rm -f`; `prune_stale` only **warns** on an orphan.
**Consequences:**
- ✅ Self-healing for worktree-backed markers; users never manually `rm` them.
- ✅ No risk of deleting a live fallback session's global (Codex H4 resolved).
- ⚠️ Path-less no-isolation orphans + orphan globals persist until next loop-close
  or manual cleanup — surfaced by warnings (benign; safety over tidiness).
**Rejected alternatives:**
- Auto-delete the global on "no session marker" — unsafe under concurrent
  fallback sessions (Codex H4).
- Legacy read-compat soak — keeps the cross-session bug alive; user chose
  auto-migration.
**Source:** Interview #3 + Codex H4.

### ADR-005: Keep Claude `session_id` separate from worktree `session_uuid`
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** `worktree.py` already embeds a generated `session_uuid` in the WT
dirname (`execute-{uuid}-{ts}`) for registry / finalize-stash ownership. It is
NOT Claude's `session_id`.
**Decision:** Claude `session_id` lives only in marker **content**
(`claude_session_id:`); the worktree dirname `session_uuid` stays in the
**filename** and continues to own registry / 5-layer data-loss concerns. The two
never merge. Enforced structurally by not renaming filenames (ADR-002).
**Consequences:**
- ✅ No disturbance to the shipped cross-session data-loss defense.
- ⚠️ Two "session" identifiers exist; code + docs must name them distinctly
  (`claude_session_id` vs `worktree_session_uuid`).
**Source:** Interview #2 (clarifying scope).

### ADR-006: Sanitize `session_id` before any filesystem use
**Status:** Accepted (2026-06-21, via Codex H7)
**Context:** `session_id` is an external hook-payload field; using it raw as a
filename fragment (no-isolation marker) or matching it from content is a path /
injection risk if the value is ever non-tame.
**Decision:** Validate `session_id` against a strict allowlist
(`^[0-9a-fA-F-]{8,64}$`, covering UUID + hex forms). If it matches, use it
verbatim; otherwise use `sha256(session_id)[:16]`. Apply at the SessionStart
hook (before writing `HM_SESSION_ID`), at marker write, and at Stop-hook compare
(compare the sanitized forms on both sides).
**Consequences:**
- ✅ Hook payload never becomes an untrusted path fragment.
- ⚠️ The sanitizer must be ONE shared helper used by producer + consumer, or the
  two sides can disagree.
**Rejected alternatives:**
- Trust the field as-is — Codex H7 (defense-in-depth violation).
**Source:** Codex H7.

## 🏗️ Technical Design

### Current State
- **Global marker** `<root>/.hm-loop-active`: created by `loop.md.j2` `!touch`,
  removed by `!rm -f`. Read by `loop_gate._stop_hook` (via `_find_marker`
  ancestor-walk incl. `_worktree_parent_marker`) and by `plan.md.j2` Step 1.5 +
  `step_manifest.md.j2` + `stage_end_summary.md.j2` (LLM string checks).
- **Per-session marker** `.claude/.hm-loop-{wt_name}`: created by `worktree
  create` (`_write_loop_marker`), removed by `worktree finalize`
  (`_clear_loop_marker`). Read by `worktree_gate._read_active_worktrees` (glob +
  union) and `worktree._read_active_worktrees`. Already parallel-safe.
- **Session identifiers**: `.hm-session-uuid` (project-scoped file, NOT per
  Claude session); worktree dirname embeds a fresh `session_uuid` (registry).

### Marker content schema (ADR-002, new)
A worktree marker `.claude/.hm-loop-{wt_name}` becomes:
```
claude_session_id: <sanitized-id-or-empty>
<absolute WT path 1>
<absolute WT path 2 …>
```
Line 1 is the new header (parsed by the Stop-hook). **Path lines are always
absolute, so the parsing rule is explicit, not incidental: a content line is a
worktree path iff `line.lstrip().startswith("/")`.** All THREE readers must adopt
this prefix rule — today two of them
(`worktree.py:_read_active_worktrees`:~2166, `worktree_gate.py:_read_active_worktrees`:85-91)
drop non-path lines only by *accident* (the header doesn't resolve to an existing
path), while only `worktree.py:_marker_referenced_paths`:1501-1504 already uses
`startswith("/")`. Relying on existence-filtering is a silent-corruption risk
(validator warning #1) — the header MUST be dropped by the prefix rule.
A no-isolation marker `.claude/.hm-loop-session-{sanitized-id}` has the header
line and no path lines.

### Affected Components
| File | Change |
|------|--------|
| `src/harness_maker/hooks/sessionid_envfile.py` | **NEW** — SessionStart hook writing sanitized `HM_SESSION_ID` to `CLAUDE_ENV_FILE` (idempotent) |
| `src/harness_maker/worktree.py` (shared sanitizer helper) | `_sanitize_session_id` (ADR-006) used by producer + consumer |
| `src/harness_maker/hooks/loop_gate.py` | Stop-hook: payload `session_id` → match marker **content** header; then legacy-global; never block on another session's marker |
| `src/harness_maker/worktree.py` | `_write_loop_marker` prepends `claude_session_id:` header; `_read_active_worktrees`/content readers skip the header; `create`/`finalize`+CLI accept `--claude-session-id` (written to content, NOT filename); no-isolation marker writer; `prune_stale` prunes stale session markers + warns on orphan global |
| `templates/hooks/hooks.json.j2` (+ `templates/codex/hooks.json.j2`) | register the new SessionStart hook |
| `templates/commands/hm/loop.md.j2` | pass `--claude-session-id "$HM_SESSION_ID"` to create/finalize; no-isolation marker write; loud degraded warning when `$HM_SESSION_ID` empty on Claude Code; legacy global only in that surfaced degraded mode; recovery text |
| `templates/stages/plan.md.j2` | Step 1.5 detection → content-/cwd-scoped; accept driver-passed marker reference |
| `templates/agents/_partials/step_manifest.md.j2` | banner-suppression + autopilot-picker detection → content-/cwd-scoped |
| `templates/agents/_partials/stage_end_summary.md.j2` | END-banner suppression detection → content-/cwd-scoped |
| `CLAUDE.md` | Multi-session section + marker references |
| `/hm:health` (`hm/health` skill + `readiness`/health module) | smoke: SessionStart env-file hook wired + `HM_SESSION_ID` resolvable (loud on degrade) |
| `specs/SPEC-loop-gate.md` + `specs/SPEC-loop-gate.machine.yaml` | update AC-001 — the gate contract changes from "global `.hm-loop-active`" to content-based session match (validator warning #2) |
| **sweep** (Codex H5) | `rg "hm-loop-active"` over `src/`, **`specs/`**, generated `.agents/skills/*`, `tests/`, `tests/cursor-compat/`, docs — each hit classified migrated / fallback-only / fixture / doc |

### Data Flow (primary path, Claude Code)
1. Session start → SessionStart hook writes `HM_SESSION_ID=<sanitized-sid>` to
   `$CLAUDE_ENV_FILE`.
2. `/hm:loop` → `worktree create --claude-session-id "$HM_SESSION_ID"` writes
   `.claude/.hm-loop-{wt_name}` whose **content** header is `claude_session_id:
   <sid>` (no-isolation: a `.hm-loop-session-{sid}` content-only marker).
3. Loop runs; dispatched stages detect loop-mode via the driver-passed marker
   reference / `$HM_SESSION_ID` content match (fallback cwd→WT). A standalone
   `/hm:plan` in another session has a *different* `$HM_SESSION_ID` → no marker
   declares it → correctly not loop-mode.
4. Stop event in the driver session → `loop_gate` reads payload `session_id` →
   some marker's content header equals it → block. Idle session B → no marker
   declares B's `session_id` → allow. **No cross-session interference.**
5. Loop close → `worktree finalize --claude-session-id "$HM_SESSION_ID"` removes
   only this session's marker. Other sessions' markers untouched.

### API / Contract Changes
- `worktree create` / `finalize` CLI: new optional `--claude-session-id <id>`
  (written to marker **content**, never the filename). Absent → header empty;
  existing tests/behaviour unchanged.
- New env var contract `HM_SESSION_ID` (sanitized Claude session_id, set by
  SessionStart hook). Harness-internal.
- Marker **content** grammar gains a `claude_session_id:` header line; filenames
  are UNCHANGED. `worktree_gate`'s `.hm-loop-*` glob + path parse still work once
  the header line is skipped.

## 📝 Implementation Plan

### Phase 1 — SessionStart env-file hook
- `depends_on`: []
- `parallel_group`: foundation
- `merge_hazards`: `hooks.json.j2` + `codex/hooks.json.j2` (snapshot) — none vs P2
- **Scope (in):** new `src/harness_maker/hooks/sessionid_envfile.py`; register in
  `templates/hooks/hooks.json.j2` SessionStart array (+ codex variant if it has a
  SessionStart channel); unit tests `tests/unit/test_sessionid_envfile.py`.
- **Scope (out):** marker keying (P2), Stop-hook (P3).
- Behavior: read stdin JSON; extract + **sanitize** `session_id` (ADR-006 shared
  helper); if `$CLAUDE_ENV_FILE` set and id present, idempotently write/replace the
  `HM_SESSION_ID=<sanitized-id>` line (atomic). Missing env-file / bad JSON /
  absent id → exit 0 no-op (never block session start). Re-fire on
  resume/compact overwrites, not duplicates.
- **Exit:** `uv run pytest tests/unit/test_sessionid_envfile.py` green; rendered
  hooks.json contains the new SessionStart entry; snapshot regen clean.
- **Risk:** low. **Rollback:** revert Phase 1 (hook absent → ADR-003 path).

### Phase 2 — Marker content schema + sanitizer in worktree.py
- `depends_on`: []
- `parallel_group`: foundation
- `merge_hazards`: `worktree.py` (shared with P3) → serialize P2 before P3.
- **Scope (in):** add `_sanitize_session_id` (ADR-006, shared by producer +
  consumer); `_write_loop_marker` prepends a `claude_session_id:` header (filename
  UNCHANGED); **all three content readers (`worktree.py:_read_active_worktrees`,
  `worktree_gate.py:_read_active_worktrees`, `worktree.py:_marker_referenced_paths`)
  adopt the explicit `startswith("/")` path-line rule** (validator warning #1) so
  the header is dropped by prefix, not by existence; `create`/`finalize` +
  `_cli_create`/`_cli_finalize` accept
  `--claude-session-id` (→ content, not filename); no-isolation marker writer
  (`.hm-loop-session-{sanitized-id}`); extend `prune_stale` to prune stale session
  markers (content-gate, unchanged predicate) + **warn** on orphan global (NO
  auto-delete of global — ADR-004). Unit tests.
- **Scope (out):** Stop-hook (P3), templates (P4).
- **Exit:** new unit tests (content header round-trips; **header dropped by the
  explicit `startswith("/")` rule — assert a header-shaped line that DOES resolve
  to a path is still excluded, proving prefix-not-existence**; all 3 readers;
  `_owned_session_uuids`/stash-ref/`worktree_gate` path-parse UNCHANGED; prune
  removes stale session markers, preserves live, warns-not-deletes global;
  sanitizer hex-passthrough + non-tame→hash) green; existing `test_worktree_*` +
  `test_worktree_gate*` green.
- **Risk:** medium (touches data-loss-adjacent prune + the shared marker format).
  **Rollback:** Phase 1.

### Phase 3 — Stop-hook content-based session matching
- `depends_on`: [2]
- `parallel_group`: serial-stophook
- `merge_hazards`: `loop_gate.py` (after P2's worktree changes land logically).
- **Scope (in):** rewrite `loop_gate._stop_hook`: (0) resolve project root via the
  **payload-first order** (`workspace.current_dir` → `cwd` → `CLAUDE_PROJECT_DIR`
  → `CURSOR_PROJECT_DIR` → `getcwd`) reused from `worktree_gate._project_root`
  (validator suggestion #5 — avoids the env-only misroute). (1) read payload
  `session_id` + `cwd`; sanitize id (shared helper). (2) Block iff some
  `.claude/.hm-loop-*`
  marker's **content** header equals the sanitized id. (3) Else if a legacy global
  `.hm-loop-active` exists → block (ADR-003 H2 order: content-first,
  global-second, ALWAYS both checked). (4) Else allow. Never block solely because
  *another* session's marker exists. Keep `_pretooluse` advisory variant consistent.
- **Scope (out):** LLM templates (P4).
- **Exit:** unit tests: own-session content match→block; other-session-only→allow;
  no-marker→allow; **HM_SESSION_ID-missing-at-create-but-session_id-present-at-Stop
  with global present→block** (Codex H2 case); cwd-inside-WT→block. Mandatory
  **absent-case** test included.
- **Risk:** medium (correctness core). **Rollback:** Phase 2.

### Phase 4 — LLM-facing detection rewrite (templates)
- `depends_on`: [1, 2]
- `parallel_group`: serial-templates
- `merge_hazards`: ALL snapshot expected files (template hashes move) → owns
  snapshot regen; serialize.
- **Scope (in):** `plan.md.j2` Step 1.5; `step_manifest.md.j2` (START banner +
  autopilot picker); `stage_end_summary.md.j2` (END banner); `loop.md.j2`
  (pass `--claude-session-id "$HM_SESSION_ID"` to create/finalize; no-isolation
  marker write **inline by the driver, BEFORE the first blocking turn, replacing
  the `!touch .hm-loop-active` on the no-iso path** so the Stop-hook never fires
  before the marker exists (validator suggestion #4); **loud degraded warning** +
  legacy-global ONLY when
  `$HM_SESSION_ID` empty on Claude Code; recovery text). Detection contract:
  driver passes the marker reference to dispatched stages (Codex H8); a stage
  is loop-mode iff a marker content-declares `$HM_SESSION_ID`, else cwd→WT
  containment. Regenerate snapshots.
- **Scope (out):** health smoke (P5).
- **Exit:** `regenerate.py` from main root → snapshot diff only on intended
  command hashes; rendered commands carry session-scoped detection;
  `specs/SPEC-loop-gate.{md,machine.yaml}` AC-001 updated to the content-match
  contract; the `rg "hm-loop-active"` **sweep** (Codex H5) over `src/`, `specs/`,
  generated `.agents/skills/*`, `tests/cursor-compat/`, docs shows every remaining
  hit classified (migrated / fallback-only / fixture / doc).
- **Risk:** medium. **Rollback:** Phase 2.

### Phase 5 — Cleanup, docs, /hm:health loud smoke
- `depends_on`: [1, 2, 3, 4]
- `parallel_group`: serial-finish
- `merge_hazards`: CLAUDE.md, health module.
- **Scope (in):** CLAUDE.md Multi-session section + marker refs;
  `/hm:health` smoke that **fails loudly** when the SessionStart env-file hook is
  absent or `HM_SESSION_ID` is unresolvable on Claude Code (Codex H3/H6 — not a
  silent degrade), following the auto-advance smoke precedent; confirm gitignore
  covers `.hm-loop-*` (already) + the env-file path if persisted; finalize any
  prune wiring not in P2.
- **Exit:** full suite + mypy + ruff green; `/hm:health` reports the new check and
  fails on a simulated missing hook; CLAUDE.md within Production 500-line lint.
- **Risk:** low. **Rollback:** Phase 4.

### Phase 6 — Parallel-session integration test
- `depends_on`: [3, 4]
- `parallel_group`: serial-finish
- `merge_hazards`: new test file only.
- **Scope (in):** `tests/integration/test_loop_parallel_session.py`
  (`INTEGRATION`/`HM_RUN_PARALLEL_SESSION` gated): two sessions with distinct
  `session_id`s — assert markers coexist; Stop-hook blocks A on A's marker but
  allows B when B is idle; A's finalize leaves B's marker; standalone plan
  detection in B (no marker) is not loop-mode while A's loop is active.
- **Exit:** integration test green under its gate; documents what the unit tests
  cannot (real cross-session FS interaction).
- **Risk:** low. **Rollback:** n/a (test-only).

## 🧪 Testing Strategy
- **Unit (mock-first, deterministic):** sessionid_envfile (write/replace/no-op);
  worktree marker keying + prune migration; loop_gate matrix incl. absent-case.
- **Snapshot:** regen after P4; assert only intended command hashes move
  (regen from the main repo root to avoid the known worktree-path contamination
  trap).
- **Integration (gated):** the P6 two-session scenario; real FS, real hook
  subprocess invocation for the Stop-hook.
- **Absent-case (mandated, count:8):** explicit tests that empty `HM_SESSION_ID`
  takes the documented fallback (not a silent no-op) in both the Stop-hook and
  the LLM detection contract (assert the rendered template carries the fallback).

## ⚠️ Risks & Mitigation
| Risk | Severity | Mitigation |
|------|----------|------------|
| `CLAUDE_ENV_FILE` propagation differs from docs | high | NOT a silent degrade — `/hm:health` smoke + loop-startup check fail LOUD on Claude Code (Codex H3/H6); P6 integration exercises the real hook |
| Prune deletes a live loop's marker | high | content-gate (listed WT must be gone); the global is NEVER auto-deleted, only warned (ADR-004, Codex H4); unit test for live-preserve |
| Producer/consumer disagree on absent-case (global written, Stop sees session_id) | high | Stop checks content-match THEN global, always both (ADR-003 H2); dedicated test |
| Renaming marker breaks `_owned_session_uuids`/stash-refs | high | filenames UNCHANGED; session id in content only (ADR-002/005, Codex H1); regression test on filename-suffix consumers |
| Untrusted `session_id` as path fragment | med | `_sanitize_session_id` allowlist-or-hash, ONE shared helper (ADR-006, Codex H7) |
| Missed global-marker consumer (skills/tests/docs) | med | `rg "hm-loop-active"` sweep exit criterion in P4 (Codex H5) |
| cwd-containment fallback false-negative inside loop | med | driver passes marker reference to dispatched stages; cwd is last resort (ADR-003, Codex H8) |
| SessionStart re-fire on resume duplicates env line | low | idempotent overwrite; unit test |
| Snapshot contamination from regen inside a worktree | med | regen from main root + diff-from-canonical-root check (known trap, count:7) |

## ✅ Success Criteria
- [x] Two concurrent `/hm:loop` sessions: neither's close removes the other's marker.
- [x] A standalone `/hm:plan` in session B runs the **full interview** while
      session A's loop is active (no false loop-mode). *(normal path; degraded
      no-id path is the accepted ADR-003 limitation.)*
- [x] Idle session B is never blocked from terminating by session A's loop.
      *(re-review R1: valid-id sessions ignore a foreign global.)*
- [x] No user action required at any point (no manual `touch`/`rm`);
      **worktree-backed** stale markers self-heal at next `worktree create`
      (path-less no-isolation orphans + orphan globals are benign and warned, not
      auto-deleted — ADR-004).
- [x] Absent-case (`HM_SESSION_ID` empty) takes the documented fallback, proven
      by test — never a silent no-op.
- [x] Full suite + mypy --strict + ruff green; snapshots regenerated; CLAUDE.md
      updated + `/hm:health` reports the `sessionid_envfile_registered` smoke
      *(P5 DONE)*; parallel-session integration test *(P6 DONE)*.

## 🔍 Plan Validation

**Codex second opinion:** `codex_status: invoked` (exit 0, Production-mandatory).
8 findings; 7 incorporated, 1 (H5 scope) surfaced + fixed during validator
reconciliation. No skip relay needed.

**plan-validator (opus):** `NEEDS_REVISION` — 0 critical, 3 warnings + 2
suggestions. All 8 Codex findings reconciled (7 KEEP, H5 unresolved→fixed). The
two cross-session bugs are confirmed closed by the ADRs without reintroduction;
H1/H4 storage-contract concerns verified resolved against the real code
(filenames unchanged, global excluded from prune).

**Resolution (all revised in-place — warnings only, no user trade-off, so no
follow-up interview round per the stage's "defensible default" guidance):**

| # | Validator finding | Resolution |
|---|-------------------|------------|
| W1 | Header-skip is accidental existence-filtering in 2 of 3 readers | Marker schema + P2 now MANDATE the explicit `startswith("/")` path-line rule for all 3 readers + a regression test proving prefix-not-existence |
| W2 | `specs/SPEC-loop-gate.{md,machine.yaml}` missed in sweep | added `specs/` to the sweep target + SPEC AC-001 update to Phase 4 scope/exit |
| W3 | No-isolation path-less marker never pruned (count:8 gap) | ADR-004 now gives all 3 marker forms explicit handling; path-less orphan = documented benign accepted-leak + warn |
| S4 | No-isolation marker write-point ordering unspecified | P4 specifies inline driver write BEFORE first blocking turn, replacing `!touch` on the no-iso path |
| S5 | loop_gate root resolution unspecified | P3 reuses `worktree_gate._project_root` payload-first order |

**Codex reconciliation:** H1 KEEP, H2 KEEP, H3 KEEP, H4 KEEP, H5 unresolved→now
fixed (W2), H6 KEEP, H7 KEEP, H8 KEEP.

**Outcome:** NEEDS_REVISION_RESOLVED. Re-run of the validator is not required
(warnings only, not MAJOR_REVISION).
