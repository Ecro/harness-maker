---
type: plan
task_slug: loop-longevity-strategies
status: planning
created: 2026-05-09
tags: [harness-maker, plan, autoloop, loop-longevity, stop-hook, cursor]
research_doc: "[[RESEARCH-loop-longevity-strategies]]"
interview_rounds: 5
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Stop hook exit 2 (CC) + PreToolUse Bash (Cursor) + parameter defaults + /compact advisory"
---

# 🎯 Executive Summary

**What:** Add loop longevity mechanisms to harness-maker's `/hm:loop` for both Claude Code and Cursor targets.

**Why:** Research (RESEARCH-loop-longevity-strategies.md) identified 7 gaps vs. Ralph Loop / yaoshengzhe/autoloop / alfredolopez80 implementations. This plan addresses 4: Stop hook forced-continuation (G1), conservative safety caps (G3+G4), and compaction advisory (G6). G2/G5/G7 explicitly deferred.

**Key Decisions:**
- **ADR-001**: Claude Code `Stop` hook → `exit 2` + escape-hatch message (`.hm-loop-active` lifecycle)
- **ADR-002**: Cursor `preToolUse` Bash injection — advisory only, 100% every Bash call
- **ADR-003**: Single `harness_maker.hooks.loop_gate` module with `--mode stop-hook|pretooluse`
- **ADR-004**: `.hm-loop-active` marker file as binary loop state signal
- **ADR-005**: G6 via `/compact` advisory text in loop command (env var is startup-only)

**Estimated impact:** Claude Code loops > 15 iterations no longer break on natural session termination. Cursor loops continue via reminder injection. Both IDEs benefit from relaxed caps (failed_streak 3→5, max_iter 30→50).

---

## 📚 Prior Work

- **RESEARCH-loop-longevity-strategies.md** — 7 gaps identified via Ralph/autoloop comparison. This plan covers G1+G3+G4+G6.
- **autoloop-pattern.md** — current `/hm:loop` reference. `"Stop": []` already in hooks.json.j2 (empty). `src/harness_maker/hooks/` directory exists.
- **CLAUDE.md §실행 주의** — `.hm-loop-active` must be gitignore'd at worktree.create time. Existing idempotent line-append logic already handles this.
- **tests/cursor-compat/results-2026-05-08.md** — Cursor reads `.cursor/hooks.json` natively (lowercase camelCase schema). Dual-render is intentional design.
- **wiki.md `[wiki:architecture] generator-not-runtime-config`** — harness-maker is a generator; hooks are pre-rendered Jinja2, not runtime-injected.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice |
|---|-------|----------|----------|--------|
| 1 | Scope | Scope | Which of 7 research gaps to implement | G1+G3+G4+G6 (G2/G5/G7 deferred) |
| 2 | Cursor strategy | Architecture | Loop continuation mechanism for Cursor | `preToolUse` hook on Bash |
| 3 | Hook impl | Architecture | Python module design | `harness_maker.hooks.loop_gate` new module |
| 4 | State detection | Architecture | How hook detects loop active | `.hm-loop-active` marker file |
| 5 | Cursor trigger | Architecture | Which tools / frequency | Bash only, 100% every call, no matcher |
| 6 | Phase layout | Phasing | G6 placement with G1 | Phase 1a (G3+G4+G6) + Phase 1b (G1 hook infra) |
| 7 | loop_gate mode | Architecture | Single or separate module for two IDEs | Single module + `--mode stop-hook\|pretooluse` |
| 8 | G6 impl | Architecture | Compaction (env var startup-only) | `/compact` advisory in loop template |
| C1 | Phase split | Phasing | Validator: single rollback point too risky | Split confirmed: 1a vs. 1b |
| C2 | Stale marker | Risk | Permanent block if crash before cleanup | Exit-2 JSON includes `rm .hm-loop-active` recovery |
| C3 | Cursor rate-limit | Architecture | Injection frequency | 100% every Bash call (noise accepted) |
| C5 | G7 | Scope | per-iter learning append — design unspecified | G7 permanently deferred (never implement) |

---

## 📐 Architecture Decision Records

### ADR-001: Stop hook `exit 2` for Claude Code loop gate
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** Claude Code can terminate a session naturally between loop iterations. No mechanism currently prevents early termination when `.hm-loop-active` signals an active loop.
**Decision:** Add `harness_maker.hooks.loop_gate --mode stop-hook` to the `"Stop"` event in `templates/hooks/hooks.json.j2`. When `.hm-loop-active` exists and `stop_hook_active` is absent/false in stdin JSON, module outputs `{"decision": "block", "reason": "Loop active. To unblock: rm .hm-loop-active"}` and exits 2.
**Consequences:**
- ✅ Hard block on session termination while loop is active
- ✅ Escape-hatch visible in Claude Code UI on exit-2 block
- ⚠️ Crash/Ctrl-C before step 7 leaves `.hm-loop-active` → permanent block until user runs `rm`
**Rejected alternatives:**
- Inline `python -c` script — untestable, violates CLAUDE.md `shell=True` prohibition
- Template-rendered `.claude/lib/loop_gate.py` — no package import path, no mypy
**Source:** Interview #3, C2

### ADR-002: Cursor `preToolUse` Bash injection, 100% frequency, advisory only
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** Cursor has no `Stop` event equivalent. `preToolUse` is the closest available lifecycle point.
**Decision:** Add `loop_gate --mode pretooluse` to `"preToolUse": [{"matcher": "Bash", ...}]` in `templates/cursor/hooks.json.j2`. Fires on every Bash call when `.hm-loop-active` exists; outputs reminder text; always exits 0. No rate-limiting — 100% injection, noise accepted.
**Consequences:**
- ✅ Claude in Cursor receives constant loop-active reminder — highest certainty of loop continuation
- ✅ Compatible with Cursor lowercase camelCase schema (verified empirically 2026-05-08)
- ⚠️ Every Bash call triggers a hook invocation (overhead: ~5-10ms per call)
- ⚠️ Advisory only — cannot hard-block session end in Cursor
**Success signal (MANUAL_CHECKLIST):** When `.hm-loop-active` exists and Cursor makes any Bash tool call, the tool result context includes "⚡ hm-loop active" reminder text.
**Rejected alternatives:**
- `Bash + completion pattern matcher` — fragile string matching, maintenance burden
- MCP tool approach — prompt-level, not hook-level; misses non-prompted executions
**Source:** Interview #2, #5, C3

### ADR-003: Single `loop_gate` module with `--mode` flag
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** Two IDEs need different exit behaviors (exit 2 vs. exit 0) from the same `.hm-loop-active` check logic.
**Decision:** `src/harness_maker/hooks/loop_gate.py` with `--mode stop-hook|pretooluse` CLI flag. Shared state-detection logic (`.hm-loop-active` read, `stop_hook_active` stdin parse) in one function.
**Consequences:**
- ✅ Single test suite covers both modes
- ✅ No duplication in state-detection logic
**Rejected alternatives:**
- Two separate files — code duplication in shared `.hm-loop-active` check
**Source:** Interview #7

### ADR-004: `.hm-loop-active` as binary hook signal with escape-hatch message
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** Hook needs a fast, reliable signal for loop active state. Two alternatives exist: rich JSON state file, or binary marker file.
**Decision:** `.hm-loop-active` marker file. Created at loop step 5 (worktree engage) in `loop.md.j2`; deleted at step 7 (loop close). On exit 2, the block message includes: `"To unblock if loop ended unexpectedly: rm .hm-loop-active"`.
**Consequences:**
- ✅ Already referenced in CLAUDE.md; gitignore auto-add already wired
- ✅ O(1) check — no JSON parse in hot path
- ⚠️ Crash/Ctrl-C before cleanup: user must manually `rm` to unblock
**Rejected alternatives:**
- `loop-state.json` — JSON parse overhead, rich fields not needed for binary check
- Environment variable — subprocess isolation breaks cross-process visibility
- `flush_session.py` cleanup on PreCompact — only fires if Claude also triggers compaction (not guaranteed on Ctrl-C)
**Source:** Interview #4, C2

### ADR-005: G6 implemented as `/compact` advisory in loop command template
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` is read at Claude Code startup; cannot be changed mid-session via subprocess. G6's goal is to prevent spec loss due to context compaction during long loops.
**Decision:** Insert advisory text in `loop.md.j2` iteration body (step 6): "Every 10 iterations OR when context usage exceeds 60%, run `/compact` before continuing the next iteration."
**Consequences:**
- ✅ Zero code changes — entirely prompt-driven
- ⚠️ Relies on Claude following the advisory; no enforcement
**Rejected alternatives:**
- `!export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=60` — subprocess cannot modify parent Claude Code process env
- `context_lint` 30% threshold — separate subsystem, separate plan
**Source:** Interview #8

---

## 🏗️ Technical Design

### Current State

| Component | Current | Gap |
|-----------|---------|-----|
| `hooks.json.j2` `"Stop"` | `[]` (empty) | No loop continuation guard |
| `cursor/hooks.json.j2` `preToolUse` | permission_gate + worktree_gate only | No loop continuation |
| `autoloop_driver.py` | `failed_streak >= 3`, `max_iter=30` | Stops too early |
| `loop.md.j2` | No `.hm-loop-active` lifecycle | No marker management |
| `src/harness_maker/hooks/` | `flush_session.py`, `post_write_reminder.py`, `sessionstart_drift.py` | `loop_gate.py` missing |

### Affected Components

```
src/harness_maker/hooks/
  loop_gate.py                          ← NEW

src/harness_maker/
  autoloop_driver.py                    ← failed_streak_cap param + max_iter default

src/harness_maker/templates/
  hooks/hooks.json.j2                   ← "Stop": [] → add loop_gate entry
  cursor/hooks.json.j2                  ← preToolUse: add loop_gate Bash entry
  commands/hm/loop.md.j2               ← defaults + .hm-loop-active lifecycle + G6
  skills/autoloop-driver/SKILL.md.j2   ← safety rails text update

tests/unit/hooks/
  __init__.py                           ← NEW
  test_loop_gate.py                     ← NEW

tests/unit/
  test_autoloop_driver.py              ← update for new defaults + param

tests/cursor-compat/
  MANUAL_CHECKLIST.md                  ← add PreToolUse loop_gate item

Snapshot fixtures (update only, not listed individually)
```

### Architecture

```
Claude Code session
  ├── loop starts → loop.md creates .hm-loop-active
  ├── per-iter: exec-rev workflow
  └── session tries to stop
        └── Stop hook fires
              └── python -m harness_maker.hooks.loop_gate --mode stop-hook
                    ├── stdin: {"stop_hook_active": false/absent}
                    ├── .hm-loop-active: exists
                    └── → exit 2  {"decision":"block","reason":"Loop active. To unblock: rm .hm-loop-active"}

Cursor session
  ├── loop starts → loop.md creates .hm-loop-active
  ├── per-iter: any Bash tool call
  │     └── preToolUse hook fires
  │           └── python -m harness_maker.hooks.loop_gate --mode pretooluse
  │                 ├── .hm-loop-active: exists
  │                 └── → exit 0, stdout: "⚡ hm-loop active — continue to next iteration"
  └── loop close → loop.md deletes .hm-loop-active
```

### `loop_gate.py` Interface

```python
# python -m harness_maker.hooks.loop_gate --mode stop-hook
# stdin: Claude Code Stop hook JSON payload {"stop_hook_active": bool, ...}
# Returns:
#   exit 0: no .hm-loop-active OR stop_hook_active=true → allow stop
#   exit 2: loop active, not stop_hook_active → block stop
#   stdout on exit 2: {"decision": "block", "reason": "...rm .hm-loop-active..."}

# python -m harness_maker.hooks.loop_gate --mode pretooluse
# stdin: (ignored)
# Returns:
#   exit 0 always
#   stdout when loop active: "⚡ hm-loop active — continue to next iteration"
#   stdout when loop inactive: (empty)
```

### `autoloop_driver.py` Changes

```python
# run() signature change:
def run(
    goal: str | None = None,
    *,
    spec: LoopSpec | None = None,
    time_h: float = 8.0,
    max_iter: int = 50,          # ← was 30
    failed_streak_cap: int = 5,  # ← new param, was hardcoded 3
    dry_run: bool = False,
    ...
) -> AutoloopState: ...

# Loop body:
if state.failed_streak >= failed_streak_cap:
    state.stop_reason = f"{failed_streak_cap} consecutive failures"
    break
```

### `hooks.json.j2` Change (Claude Code)

```jinja
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "uv run --with {{ harness_maker_src_path }} python -m harness_maker.hooks.loop_gate --mode stop-hook",
        "timeout": 10
      }
    ]
  }
]
```

### `cursor/hooks.json.j2` Change (Cursor)

New entry added to existing `preToolUse` array:
```json
{
  "matcher": "Bash",
  "command": "CLAUDE_PROJECT_DIR=\"${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$PWD}}\" PATH=\"$HOME/.local/bin:$PATH\" uv run --with {{ harness_maker_src_path }} python -m harness_maker.hooks.loop_gate --mode pretooluse"
}
```

### `loop.md.j2` Changes

1. Usage section: `--max-iter 30` → `--max-iter 50`; add `--failed-streak-cap N` flag (default 5)
2. Safety rails in step 6: "3 consecutive failures" → "`--failed-streak-cap` (default 5) consecutive failures"
3. Step 5 (worktree engage): add `.hm-loop-active` creation
4. Step 7 (loop close): add `.hm-loop-active` deletion
5. Step 6 (iteration body): add G6 advisory paragraph

### `autoloop-driver/SKILL.md.j2` Change

Safety rail #3: `failed_streak >= 3` → `failed_streak >= N (default 5, configurable via --failed-streak-cap)`

---

## 📝 Implementation Plan

### Phase 1a — Parameter Defaults + /compact Advisory

**Scope IN:**
- `src/harness_maker/autoloop_driver.py` — add `failed_streak_cap: int = 5` param, `max_iter: int = 50` default, dynamic stop_reason string
- `src/harness_maker/templates/commands/hm/loop.md.j2` — update `--max-iter` default (30→50), add `--failed-streak-cap` flag, update safety rail text, add G6 `/compact` advisory to step 6
- `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2` — update safety rail #3 text
- `tests/unit/test_autoloop_driver.py` — update `test_failed_streak_3_halts_loop` to pass `failed_streak_cap=3` explicitly; add `test_failed_streak_cap_default_5` and `test_max_iter_default_50`
- Snapshot regeneration for `loop.md` and `autoloop-driver/SKILL.md` renders

**Scope OUT:** Any hook files, loop_gate.py, cursor templates, `.hm-loop-active` lifecycle

**Exit criterion:**
```bash
uv run pytest tests/unit/test_autoloop_driver.py -v  # all pass
# Grep audit: no unintentional literal "30" or hardcoded "3" remaining:
grep -rn "\bmax_iter=30\b\|failed_streak >= 3\b" \
     src/harness_maker/ templates/ \
     --include="*.py" --include="*.j2" --include="*.md"
# Expected: 0 matches
# Snapshot: loop.md render shows "--max-iter 50" in Usage + /compact advisory in step 6
```

Risk: **low** — Python parameter addition + template text change only
Rollback: `git revert` Phase 1a commit; isolated from hook infra

---

### Phase 1b — Stop Hook + Cursor PreToolUse + .hm-loop-active Lifecycle

**Scope IN:**
- `src/harness_maker/hooks/loop_gate.py` — NEW: `--mode stop-hook|pretooluse`; `stop_hook_active` guard; escape-hatch in exit-2 reason; test for stale-marker recovery message
- `tests/unit/hooks/__init__.py` — NEW (empty)
- `tests/unit/hooks/test_loop_gate.py` — NEW (5 tests listed below)
- `src/harness_maker/templates/hooks/hooks.json.j2` — `"Stop": []` → add loop_gate entry
- `src/harness_maker/templates/cursor/hooks.json.j2` — add `preToolUse` Bash entry for loop_gate
- `src/harness_maker/templates/commands/hm/loop.md.j2` — add `.hm-loop-active` create/delete at steps 5 and 7
- Snapshot regeneration for `hooks.json` and `.cursor/hooks.json` renders
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — add PreToolUse loop_gate verification item

**Scope OUT:** Phase 1a files (already merged), G2, G5, G7, cli.py, interview.py, synthesize.py

**Exit criterion:**
```bash
uv run pytest tests/unit/hooks/ -v  # all 5 tests pass
# Smoke tests (manual):
python -m harness_maker.hooks.loop_gate --mode stop-hook
# → exit 0 (no .hm-loop-active)
touch .hm-loop-active
python -m harness_maker.hooks.loop_gate --mode stop-hook
# → exit 2, stdout contains "rm .hm-loop-active"
echo '{"stop_hook_active":true}' | python -m harness_maker.hooks.loop_gate --mode stop-hook
# → exit 0 (infinite loop guard)
python -m harness_maker.hooks.loop_gate --mode pretooluse
# → exit 0, no stdout (no .hm-loop-active)
python -m harness_maker.hooks.loop_gate --mode pretooluse
# → exit 0, stdout contains "⚡ hm-loop active" (.hm-loop-active present)
rm .hm-loop-active
# Snapshot: hooks.json render has "Stop" entry with loop_gate command
# Snapshot: .cursor/hooks.json preToolUse has loop_gate Bash entry
```

Risk: **medium** — new hook module, dual-template schema changes, novel Stop hook infra
Rollback: `git revert` Phase 1b commit; Phase 1a unaffected (independent commits)

---

## 🧪 Testing Strategy

### Unit tests — Phase 1a

- `test_max_iter_default_50` — `run("a")` default max_iter is 50
- `test_failed_streak_cap_default_5` — default `failed_streak_cap` is 5
- `test_failed_streak_3_halts_loop` → updated: explicit `failed_streak_cap=3`
- `test_failed_streak_5_cap` — `failed_streak_cap=5` halts at 5 failures

### Unit tests — Phase 1b (new `tests/unit/hooks/test_loop_gate.py`)

- `test_stop_hook_no_active_exits_0` — no `.hm-loop-active` → exit 0, no output
- `test_stop_hook_active_exits_2` — `.hm-loop-active` present, no `stop_hook_active` → exit 2, `"rm .hm-loop-active"` in stdout
- `test_stop_hook_active_guard_exits_0` — `.hm-loop-active` + `{"stop_hook_active":true}` stdin → exit 0 (infinite loop prevention)
- `test_pretooluse_no_active_exits_0_silent` — no `.hm-loop-active` → exit 0, empty stdout
- `test_pretooluse_active_reminder` — `.hm-loop-active` present → exit 0, `"⚡ hm-loop active"` in stdout

### Snapshot tests

Both phases regenerate snapshots for affected renders. Use `normalize_for_snapshot()` to mask `generated_at`.

### Manual (Cursor)

`tests/cursor-compat/MANUAL_CHECKLIST.md` new item:
> **loop_gate PreToolUse** — with `.hm-loop-active` present, make any Bash call in Cursor. Verify tool result context shows "⚡ hm-loop active" advisory text. Without `.hm-loop-active`, no advisory appears.

---

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| `.hm-loop-active` not deleted on crash/Ctrl-C → permanent Stop block | high | exit-2 message includes `rm .hm-loop-active` escape-hatch; MANUAL_CHECKLIST item |
| `stop_hook_active` not checked → infinite Stop loop | high | Explicit unit test `test_stop_hook_active_guard_exits_0` in exit criterion |
| `max_iter=50` default breaks tests expecting 30 | medium | Phase 1a exit criterion: grep audit for literal "30" |
| Cursor PreToolUse fires on every Bash call → noise | accepted | C3: user accepted noise. Advisory exits 0 with minimal overhead (~5-10ms) |
| Snapshot tests fail on Stop hook entry format | low | Regenerate snapshots as part of Phase 1b |
| Cursor `stop` event (lowercase) has no loop_gate — session may still end | known gap | Cursor lacks true Stop-equivalent; advisory approach is best-effort. Documented in ADR-002 |

---

## ✅ Success Criteria

- [ ] `uv run pytest tests/unit/hooks/ tests/unit/test_autoloop_driver.py -v` — all pass
- [ ] No literal `max_iter=30` or `failed_streak >= 3` in templates or source
- [ ] Claude Code Stop hook entry present in rendered `hooks.json` with loop_gate command
- [ ] Cursor `preToolUse` Bash entry present in rendered `.cursor/hooks.json`
- [ ] `--mode stop-hook` exits 2 with `.hm-loop-active` + no `stop_hook_active`
- [ ] `--mode stop-hook` exits 0 with `{"stop_hook_active":true}` stdin (infinite loop guard)
- [ ] `--mode pretooluse` outputs `"⚡ hm-loop active"` when `.hm-loop-active` present, silent otherwise
- [ ] exit-2 block message contains `rm .hm-loop-active`
- [ ] `tests/cursor-compat/MANUAL_CHECKLIST.md` includes PreToolUse loop_gate item
- [ ] `ruff check` + `mypy --strict` pass on new `loop_gate.py`

---

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → resolved

| Critique | Severity | Resolution |
|----------|----------|------------|
| C1: single phase — one rollback point | warning | **Accepted: split** — Phase 1a (G3+G4+G6) + Phase 1b (G1) with independent rollbacks |
| C2: stale marker permanent block | critical | **Fixed** — exit-2 JSON includes `rm .hm-loop-active` recovery text (Interview round C2) |
| C3: Cursor rate-limit undefined | warning | **Fixed** — 100% every Bash call, noise accepted (Interview round C3); MANUAL_CHECKLIST success signal defined in ADR-002 |
| C4: default-bump propagation incomplete | warning | **Fixed** — Phase 1a exit criterion includes grep audit for literal 30/3 across all surfaces |
| C5: G7 no ADR | warning | **Resolved** — G7 permanently deferred (Interview round C5); removed from scope entirely |
| C6: stdin JSON guard not in exit criterion | warning | **Fixed** — `echo '{"stop_hook_active":true}' \| ...` smoke test added to Phase 1b exit criterion |
