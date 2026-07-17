---
type: research
task_slug: codex-loop-execute-gaps
status: complete
created: 2026-05-10
tags: [harness-maker, codex, loop, execute, worktree, interview, adr]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[PLAN-codex-target-support]]"
  - "[[RESEARCH-codex-target-support]]"
  - "[[REVIEW-codex-target-support-2026-05-10]]"
summary: "ADR-002+ADR-008 design chain broken: AGENTS.md.j2 is a 29-line stub, stage skills have no procedure to follow"
---

# 🎯 Recommended Direction

**Fix ADR-002 first** — expand `AGENTS.md.j2` to include the full stage procedure bodies (loop + all 7 atomic stages). Stage skills (ADR-008) are correctly designed as lightweight triggers; the failure is that the content they point to doesn't exist yet.

Secondary: fix the `.codex/hooks.json` version mismatch (0.9.0 → 0.9.3) and verify ADR-005 (git worktree compat in Codex sandbox).

---

## 🔍 Problem Statement

Two confirmed symptoms from user testing:
1. `@hm-loop` (Codex) — **no interview** before starting iterations
2. `@hm-execute` (Codex) — **no worktree created** before editing files

Both trace to the same architectural gap.

---

## 🛠️ Gap Analysis — All Deficiencies Found

### Gap 1 (CRITICAL) — ADR-002 not implemented: AGENTS.md is a 29-line stub

**File**: `src/harness_maker/templates/codex/AGENTS.md.j2`
**Current**: 29 lines — workflow/reviewer/caching headings only, no stage procedures
**ADR-002 promised**: "full parity to CLAUDE.md (~400-500 lines). Include all stage procedures."
**Impact**: ADR-008 stage skills say "follow AGENTS.md", but AGENTS.md has nothing to follow.

```
AGENTS.md.j2 current content (verbatim):
  - ## Workflow (4 lines)
  - ## Reviewers (2 lines)
  - ## Caching (2 lines)
  - ## Autoloop / Worktree: "toggles live in .claude/harness.yaml" (2 lines)
  - user block markers (8 lines)
```

**What is missing from AGENTS.md**: Every stage procedure. Specifically:
- `/hm:loop` Steps 1–9 (parse args → detect mode → resolve spec → adaptive interview → engage worktree → loop body → convergence → marker → wrapup)
- `/hm:execute` Steps 0–5 (worktree isolation CLI → load PLAN → TDD phases A/A.5/B/C/D → finalize)
- `/hm:research`, `/hm:spec`, `/hm:plan`, `/hm:review`, `/hm:verify`, `/hm:wrapup` procedures

The exact content that must enter AGENTS.md is already written — it lives in:
- `src/harness_maker/templates/commands/hm/loop.md.j2` (709 lines) → loop procedure
- `src/harness_maker/templates/stages/execute.md.j2` (238 lines) → execute procedure
- `src/harness_maker/templates/stages/{research,spec,plan,review,verify,wrapup}.md.j2` → other stages

---

### Gap 2 (CRITICAL) — `hm-loop` SKILL.md: 40 lines, no procedure

**File**: `.agents/skills/hm-loop/SKILL.md` (template: `codex/loop_skill.md.j2`)
**Current**: 40 lines — 4-bullet summary + "follow AGENTS.md and autoloop-driver skill"
**Claude Code equivalent**: `.claude/commands/hm/loop.md` = 717 lines (full step-by-step)

**Specifically missing** (by step):
| Step | Content | Status |
|------|---------|--------|
| Step 4 | Adaptive interview (5 dimensions: purpose/invariants/priority/test_reliability/stopping_criteria) | ❌ absent |
| Step 4-G | loop_intensity + exit_criteria_checklist AskUserQuestion | ❌ absent |
| Step 4-H | Deep interview gate (3-layer: GCIC/Implicit/Score) | ❌ absent |
| Step 5 | Worktree engagement: `!uv run --with <path> python -m harness_maker.worktree create execute "$(pwd)"` | ❌ absent |
| Step 5 | Marker file write: `.claude/.hm-loop-<wt-name>` | ❌ absent |
| Steps 6–8 | Per-iteration workflow invocation + 4-gate convergence | ❌ absent |
| Step 9 | Wrapup + marker cleanup | ❌ absent |

Note: `autoloop-driver/SKILL.md` (163 lines, dual-rendered, full content) has the **rationale** (WHY) for the loop design, including 4-gate convergence schema and interview dimensions. But it explicitly says: "Command: `commands/hm/loop.md` (full per-step procedure)" — a Claude Code-only path that Codex can't surface to users.

---

### Gap 3 (CRITICAL) — `hm-execute` SKILL.md: 25 lines, missing worktree + TDD procedure

**File**: `.agents/skills/hm-execute/SKILL.md` (template: `codex/stage_skill.md.j2`)
**Current**: 25 lines — "Follow execute stage documented in AGENTS.md"
**Claude Code equivalent**: `.claude/commands/hm/execute.md` = 237 lines

**Specifically missing**:
| Step | Content | Status |
|------|---------|--------|
| Step 0 | Worktree isolation via CLI (deterministic): `!uv run --with <path> python -m harness_maker.worktree create execute "$(pwd)"` | ❌ absent |
| Step 0 | Multi-line output parsing (empty=no isolation, 1 path=single-repo, N paths=multi-repo) | ❌ absent |
| Step 1 | Load + parse PLAN file | ❌ absent |
| Step 2 | Resolve SPEC + RESEARCH cache | ❌ absent |
| Step 3 | TDD machine: Phase A (author tests) → A.5 (test-reviewer gate) → B (RED gate) → C (implement) → D (verify GREEN) | ❌ absent |
| Step 4 | Stage exit: NO commit (wrapup owns commits) | ❌ absent |
| Step 5 | Worktree finalize: `!uv run ... worktree finalize <WT> stage-only` or `fail` | ❌ absent |

Additionally: the `worktree-isolator` SKILL.md (97 lines, dual-rendered) shows Python API (`worktree.create()`) rather than the CLI invocation. The Claude Code `execute.md` explicitly warns: *"The worktree-isolator skill is documentation-only — its trigger-based dispatch is probabilistic in Cursor IDE and can silently skip. Invoke the worktree CLI directly so isolation is deterministic across both IDEs."* This applies equally to Codex.

---

### Gap 4 (HIGH) — All 6 remaining stage skills are identical stubs

**Files**: `.agents/skills/hm-{research,spec,plan,review,verify,wrapup}/SKILL.md`
**Template**: `codex/stage_skill.md.j2` (17-line generic stub, same for all 7 stages)
**Impact**: `@hm-research`, `@hm-plan`, etc. have no procedure content either

Each of these stages has a full template (`src/harness_maker/templates/stages/<stage>.md.j2`) that is 100-250 lines. None of that content reaches Codex.

---

### Gap 5 (HIGH) — Workflow skills are stubs with no fusion procedure

**Files**: `.agents/skills/hm-exec-rev/SKILL.md`, `hm-exec-rev-wrap/SKILL.md`, `hm-exec-rev-wrap-ver/SKILL.md`
**Template**: `codex/workflow_skill.md.j2` (17-line stub)
**Missing**: How stages hand off between each other, stop-on-fail behavior, what the fused workflow emits

---

### Gap 6 (MEDIUM) — `.codex/hooks.json` version mismatch: 0.9.0 → 0.9.3

**File**: `.codex/hooks.json`
**All 6 hook commands reference**: `/harness-maker/0.9.0/`
**Current package version**: 0.9.3
**Root cause**: `.codex/hooks.json` was rendered when version was 0.9.0; subsequent `hm:make --update` runs did not update it (or were not run after each version bump).
**Severity assessment**: NOT immediately blocking — 0.9.0 IS still in `~/.claude/plugins/cache/harness-maker-local/harness-maker/0.9.0/`. Hook commands succeed because the old binary is cached. However:
  - Fixes in 0.9.1/0.9.2/0.9.3 Python code (e.g., worktree timeout, TOML section quoting) are bypassed
  - If the 0.9.0 cache is cleared, all Codex hooks break silently

**Responsible template**: `codex/hooks.json.j2` uses `{{ harness_maker_src_path }}`. This variable resolves to an absolute path based on the installed package location. Re-rendering with 0.9.3 installed would fix this.

---

### Gap 7 (LOW) — ADR-005 unresolved: Codex sandbox + git worktree compat not verified

**ADR-005 Status**: "Accepted — Omit `worktree_gate`. Verify empirically later."
**Current state**: No test in `tests/codex-compat/` for worktree behavior.
**Impact**: Even if we add worktree creation steps to skills/AGENTS.md, we don't know if `git worktree add` succeeds inside Codex's Seatbelt (macOS) or Landlock (Linux) sandbox.
**Where to verify**: Add a `tests/codex-compat/test_worktree_create.sh` fixture that runs `git worktree add` under simulated sandbox constraints.

---

### Gap 8 (LOW) — autoloop-driver SKILL.md cross-reference points to Claude Code path

**File**: `.agents/skills/autoloop-driver/SKILL.md` (last section)
**Content**: "Command: `commands/hm/loop.md` (full per-step procedure)"
**Problem**: `commands/hm/loop.md` is at `.claude/commands/hm/loop.md` — a Claude Code location. Codex users can't directly access this. After ADR-002 is implemented, the reference should point to "see AGENTS.md § Loop Procedure".

---

## 📊 Summary Table

| Gap | File | Severity | Root Cause |
|-----|------|----------|------------|
| G1 | `codex/AGENTS.md.j2` (29 lines) | CRITICAL | ADR-002 not implemented — stage procedures absent |
| G2 | `hm-loop/SKILL.md` (40 lines) | CRITICAL | Depends on G1; ADR-008 strategy fails without AGENTS.md content |
| G3 | `hm-execute/SKILL.md` (25 lines) | CRITICAL | Same; worktree isolation step missing |
| G4 | All 6 other stage SKILL.md stubs | HIGH | Same `stage_skill.md.j2` generic template |
| G5 | Workflow skill stubs | HIGH | `workflow_skill.md.j2` generic template |
| G6 | `.codex/hooks.json` version 0.9.0 | MEDIUM | Re-render not triggered on version bumps |
| G7 | ADR-005 unverified | LOW | No empirical test of git worktree in Codex sandbox |
| G8 | autoloop-driver cross-reference | LOW | Points to Claude Code path, not Codex-accessible path |

---

## ⚠️ Pitfalls

**P1 — Don't embed full stage bodies in SKILL.md files (ADR-008 held)**
ADR-008 correctly rejected embedding 200-700 lines per skill — it would create two sources of truth and exceed SKILL.md line limits (context_lint: 150 lines for Production). The fix is to put content in AGENTS.md (single source), not in individual skills.

**P2 — AGENTS.md line limit is 500 (Production)**
`context_lint.py` threshold: CLAUDE.md Side 200 / Production 500. AGENTS.md uses the CLAUDE.md threshold. With full stage procedures added, AGENTS.md will approach 1000-1500 lines — **well over the 500-line limit**. Options:
  - Split: `AGENTS.md` + `AGENTS.context.md` (referenced inline) — already anticipated in TECH_SPEC §"AGENTS.md 32 KiB Codex soft limit": "split if needed"
  - Or: Codex reads all `.md` files at project root, so `AGENTS-loop.md` + `AGENTS-execute.md` are valid
  - Or: Compress procedures using tighter prose (no bullet-per-word), target 300-400 lines total

**P3 — `$ARGUMENTS` injection doesn't work in Codex skills**
Claude Code slash commands receive `$ARGUMENTS` (the text after the command name). Codex skills activate descriptively — no `$ARGUMENTS` injection. The loop template uses `$ARGUMENTS` for `--spec`, `--mode`, `--time`, etc. In Codex, these flags must be passed as natural language in the user's prompt and parsed by the LLM. The procedure in AGENTS.md must instruct "parse flags from the user's input as natural-language tokens, not as `$ARGUMENTS`."

**P4 — `!uv run` shell prefix not available in Codex**
Claude Code slash commands use `!` prefix for shell commands. Codex skills use Bash tool invocations. The worktree CLI call in execute.md reads: `!uv run --with {{ harness_maker_src_path }} python -m harness_maker.worktree create execute "$(pwd)"`. In AGENTS.md, this must be expressed as a `Bash` tool call with full command string, not `!` prefix.

**P5 — `.codex/hooks.json` format difference from Claude Code hooks**
Already handled correctly: Codex hooks use PascalCase + `PermissionRequest` event. But the `Stop` hook fires `loop_gate --mode stop-hook`. If the worktree marker (`.claude/.hm-loop-<name>`) is never written (because the loop procedure is absent), the Stop hook will never block — meaning the safety guard is effectively dead without fixing G1/G2 first.

---

## ❓ Open Questions for Plan

1. **AGENTS.md line budget**: How to fit 7 stage procedures + loop procedure into ≤500 lines? Options: (a) split files, (b) compress prose, (c) raise lint threshold for AGENTS.md specifically. Which approach?

2. **`$ARGUMENTS` rewrite scope**: How much of the stage templates needs rewriting to replace `$ARGUMENTS` with "parse from user input"? Is this a template-level change or a AGENTS.md-level instruction?

3. **ADR-005 test priority**: Should we verify git worktree compat in Codex sandbox as a blocking precondition before fixing G1-G3, or proceed with the assumption it works (consistent with ADR-005's original "proceed, verify later")?

4. **Loop procedure granularity in AGENTS.md**: Should AGENTS.md contain the full 717-line loop procedure (compressed), or a shorter summary that delegates detail to autoloop-driver SKILL.md? The autoloop-driver SKILL.md already has rationale but not steps — could it be expanded to carry the step-by-step?

5. **Hooks version re-render trigger**: Should the version bump checklist in CLAUDE.md §버전업 정책 explicitly include "`hm:make --update` in all target projects"? Currently only mentions the 5 version files.

---

## 📚 Sources

- `src/harness_maker/templates/commands/hm/loop.md.j2` (709 lines) — full Claude Code loop procedure
- `src/harness_maker/templates/stages/execute.md.j2` (238 lines) — execute stage procedure
- `src/harness_maker/templates/codex/AGENTS.md.j2` (29 lines) — current stub
- `src/harness_maker/templates/codex/loop_skill.md.j2` (29 lines) — current stub
- `src/harness_maker/templates/codex/stage_skill.md.j2` (17 lines) — current stub
- `work-docs/PLAN-codex-target-support.md` — ADR-002, ADR-008 source
- `.agents/skills/autoloop-driver/SKILL.md` (163 lines) — has rationale, not steps
- `.agents/skills/worktree-isolator/SKILL.md` (97 lines) — shows Python API, not CLI
- `.codex/hooks.json` — version 0.9.0 mismatch confirmed

## 🔗 Related Internal Docs

- [[PLAN-codex-target-support]] — original ADR decisions
- [[RESEARCH-codex-target-support]] — original Codex feasibility research
- [[REVIEW-codex-target-support-2026-05-10]] — post-implementation review
