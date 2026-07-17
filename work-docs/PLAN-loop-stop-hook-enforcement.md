---
type: plan
task_slug: loop-stop-hook-enforcement
status: complete
created: 2026-05-11
tags: [harness-maker, loop, hooks, codex, claude-code, cursor, worktree]
interview_rounds: 2
adrs: 2
validator_outcome: APPROVED
summary: "Make loop Stop-hook enforcement shared, worktree-aware, and strict until convergence or explicit override"
---

# 🎯 Executive Summary

**What**: Strengthen `/hm:loop` termination enforcement so supported targets
cannot silently stop while `.hm-loop-active` is present, including when the
active loop runs inside a git worktree.

**Why**: The observed Codex failure was not that Codex lacks hooks. Codex renders
`.codex/hooks.json` with `features.hooks = true` and a `Stop` hook. The weak points
are shared: marker discovery can miss the project-root marker from inside a
worktree, and the loop procedure can remove the marker on non-converged halts.

**Key decisions**:
- ADR-001: fix shared loop core, with target-specific adapters.
- ADR-002: keep `.hm-loop-active` on every non-converged halt until explicit
  user override or convergence.

**Estimated impact**: Codex and Claude Code get hard Stop-hook blocking when
installed; Cursor remains advisory-only unless separately proven to hard-block.

---

## 📚 Prior Work

- `work-docs/PLAN-codex-loop-execute-gaps.md` established that Codex stage skills
  embed full procedures and that Codex has a dedicated `.codex/hooks.json`.
- `work-docs/REVIEW-codex-loop-execute-gaps-2026-05-11.md` approved the prior
  Codex target support changes after config propagation fixes.
- `src/harness_maker/hooks/loop_gate.py` already implements Stop-hook blocking
  by returning exit code 2 and JSON `{decision: "block"}` when a marker is found.
- `src/harness_maker/templates/codex/hooks.json.j2` already wires `Stop` to
  `harness_maker.hooks.loop_gate --mode stop-hook`.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Target scope | Scope boundaries | Is this Codex-only or shared loop enforcement? | A: Shared core fix, target-specific adapters | Codex has hooks; the defect is marker lifecycle/discovery and target semantics. | ADR-001 |
| 2 | Non-converged halt policy | Risk tolerance | What happens on max-iter/time-cap/failed-streak/hard error? | A: Strict until convergence or explicit override | Do not delete `.hm-loop-active` on non-convergence; user must choose override/abort. | ADR-002 |

Ambiguity Score: 0.90/1.0
  Goals:             0.9/1.0 ✅
  Constraints:       0.9/1.0 ✅
  Success Criteria:  0.9/1.0 ✅
  Weighted total:    0.90
  → PASS

---

## 📐 Architecture Decision Records

### ADR-001: Shared Core Fix with Target-Specific Adapters

**Status:** Accepted (2026-05-11, via /hm:plan interview)

**Context:** Codex supports hooks and already has a Stop hook rendered. The same
underlying marker logic is shared by Codex, Claude Code, and Cursor-advisory paths.
Fixing only Codex would leave the shared `loop_gate` worktree marker bug intact.

**Decision:** Fix loop enforcement in shared code first:
- `loop_gate._find_marker()` must locate the project-root marker even when cwd is
  a git worktree under `.worktrees/<name>`.
- Loop procedure templates must describe target-specific hook semantics accurately.
- Codex and Claude Code hard-block via Stop hooks when installed.
- Cursor remains advisory-only unless separate evidence proves hard blocking.

**Consequences:**
- ✅ One enforcement contract for supported hard-block targets.
- ✅ Codex is treated as a first-class hook target, not as “hookless”.
- ⚠️ Cursor behavior intentionally differs; docs must not overpromise hard block.

**Rejected alternatives:**
- Codex-only patch — faster, but leaves shared marker discovery broken.
- Uniform hard-block for all targets — unsupported by current Cursor evidence.
- Docs-only clarification — does not prevent recurrence.

**Source:** Interview #1

### ADR-002: Non-Converged Loops Keep the Active Marker

**Status:** Accepted (2026-05-11, via /hm:plan interview)

**Context:** The Stop hook can only enforce continuation while `.hm-loop-active`
exists. Removing the marker on max-iter, time cap, failed-streak, hard error, or
unresolved checklist failure converts a non-converged loop into a normal stop.

**Decision:** Remove `.hm-loop-active` only after:
- `converged=True` and final checklist gate passes, or
- the user explicitly chooses an override/abort escape hatch.

Safety-rail halts become **blocked review states**: report the halt reason and
ask for explicit next action while keeping the marker in place.

**Consequences:**
- ✅ Matches “do not stop until mission complete” semantics.
- ✅ Prevents accidental final response from bypassing Stop-hook enforcement.
- ⚠️ Users need clear escape instructions: `rm .hm-loop-active` remains the
  manual emergency break.

**Rejected alternatives:**
- Remove marker on safety rails — easier to stop but violates the stated loop
  guarantee.
- Two-marker model (`.hm-loop-active` + `.hm-loop-paused`) — potentially useful
  later, but unnecessary for this fix.

**Source:** Interview #2

---

## 🏗️ Technical Design

### Current State

`loop_gate._find_marker()` walks from cwd upward and stops at `.git`. In a normal
repo this is fine. In a git worktree, `.git` is a file at the worktree root, so
the walk can stop before reaching the parent repository marker at
`<repo>/.hm-loop-active`.

`commands/hm/loop.md.j2` currently says to delete the marker after convergence
**or after a safety rail fires**. That makes non-converged halts unenforceable.

### Affected Components

| Component | Change |
|---|---|
| `src/harness_maker/hooks/loop_gate.py` | Make marker discovery worktree-aware. |
| `tests/unit/hooks/test_loop_gate.py` | Add worktree-parent marker and Stop-hook blocking regression tests. |
| `src/harness_maker/templates/commands/hm/loop.md.j2` | Keep marker on non-converged halts; require explicit user override/abort before removal. |
| `src/harness_maker/templates/codex/loop_skill.md.j2` | Inherits updated loop procedure body. |
| `src/harness_maker/templates/codex/hooks.json.j2` | Keep Stop hook wired to `loop_gate --mode stop-hook`; add/adjust tests that assert loop_gate is present, not only `flush_session`. |
| `tests/unit/test_codex_phase5.py` | Assert Codex Stop hook includes `loop_gate --mode stop-hook`. |
| `tests/unit/test_codex_stage_procedures.py` | Assert Codex loop rendering states strict marker lifecycle. |

### Marker Discovery Algorithm

1. Search cwd and parents for `.hm-loop-active`.
2. If a `.git` directory is reached, stop after checking that directory.
3. If a `.git` file is reached and its contents point to a worktree gitdir,
   infer the common repository root for harness-maker worktrees:
   - for cwd under `<repo>/.worktrees/<name>`, also check `<repo>/.hm-loop-active`.
4. Never search outside the project/worktree relationship arbitrarily; avoid
   accidentally honoring an unrelated marker above the repo.

### Loop Close Semantics

Replace the current marker deletion rule with:

- If `converged=True`: delete marker, run wrapup, finalize success.
- If user chooses explicit abort/override: delete marker, finalize fail or
  accepted success per chosen escape hatch.
- If safety rail or hard error fires without explicit user decision: keep marker,
  report blocked state, preserve worktree, and ask for next action.

---

## 📝 Implementation Plan

### Phase 1 — Make `loop_gate` Worktree-Aware

**Scope**
- In: `src/harness_maker/hooks/loop_gate.py`
- In: `tests/unit/hooks/test_loop_gate.py`
- Out: hook templates and loop docs

**Exit criterion**
- `uv run pytest tests/unit/hooks/test_loop_gate.py -q --tb=short`

**Risk:** medium

**Rollback point:** revert Phase 1 files only.

### Phase 2 — Tighten Loop Marker Lifecycle in Templates

**Scope**
- In: `src/harness_maker/templates/commands/hm/loop.md.j2`
- In: Codex loop render tests that consume that template
- Out: worktree CLI implementation

**Exit criterion**
- `uv run pytest tests/unit/test_codex_stage_procedures.py -q --tb=short`

**Risk:** medium

**Rollback point:** revert Phase 2 files; Phase 1 remains independently useful.

### Phase 3 — Assert Codex Stop Hook Actually Runs `loop_gate`

**Scope**
- In: `src/harness_maker/templates/codex/hooks.json.j2` only if wording/comments need update
- In: `tests/unit/test_codex_phase5.py`
- Out: Cursor hook schema

**Exit criterion**
- `uv run pytest tests/unit/test_codex_phase5.py -q --tb=short`

**Risk:** low

**Rollback point:** revert Phase 3 tests/template comment changes.

### Phase 4 — Verification and Regression Sweep

**Scope**
- In: affected loop/hook tests
- Out: unrelated full-suite type cleanup

**Exit criterion**
- `uv run pytest tests/unit/hooks/test_loop_gate.py tests/unit/test_codex_phase5.py tests/unit/test_codex_stage_procedures.py -q --tb=short`
- `uv run ruff check src/harness_maker/hooks/loop_gate.py tests/unit/hooks/test_loop_gate.py tests/unit/test_codex_phase5.py tests/unit/test_codex_stage_procedures.py`
- `uv run mypy --strict src/harness_maker/hooks/loop_gate.py`

**Risk:** low

**Rollback point:** revert all files in this plan.

---

## 🧪 Testing Strategy

- Unit test `_find_marker()` from:
  - normal repo root,
  - normal subdirectory,
  - git worktree subdirectory with marker only in parent repo root,
  - unrelated parent marker above a `.git` boundary, which must stay ignored.
- Unit test `_stop_hook()` returns exit code 2 and block JSON when invoked from
  a worktree and only the parent repo marker exists.
- Template tests:
  - Codex hooks include both `loop_gate --mode stop-hook` and `flush_session`.
  - Codex loop procedure says non-converged halts keep the marker.

---

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Worktree root inference accidentally honors unrelated parent markers | False Stop-hook blocking | Only check the known `.worktrees/<name>` parent repo pattern; do not blindly continue above `.git`. |
| Loop can become annoying to exit on repeated failures | User friction | Preserve manual emergency break in Stop-hook reason and explicit abort/override path in loop docs. |
| Cursor users expect hard block after reading shared docs | Misleading UX | Keep Cursor advisory-only callout in loop docs. |
| Existing staged changes are present during implementation | Accidental scope mix | Modify only hook/loop/template test files for this plan; do not touch existing staged CLI changes unless explicitly requested. |

---

## ✅ Success Criteria

- `_find_marker()` finds root `.hm-loop-active` from inside `.worktrees/execute-*`.
- `_find_marker()` does not cross arbitrary git boundaries to unrelated markers.
- `Stop` hook blocks from worktree cwd when parent repo marker exists.
- Loop docs remove marker only on convergence or explicit user override/abort.
- Codex hook template regression test asserts `loop_gate --mode stop-hook`.
- Cursor remains documented as advisory-only.
- Targeted tests, Ruff, and mypy for changed production code pass.

---

## 🔍 Plan Validation

Validator outcome: APPROVED.

Self-check:
- Every phase has scope, exit criterion, risk, and rollback point.
- ADR count in frontmatter is 2 and two ADRs are present.
- No deferred-decision checklist language remains in the implementation plan.
