---
type: plan
task_slug: codex-loop-execute-gaps
status: complete
created: 2026-05-10
tags: [harness-maker, codex, loop, execute, worktree, interview, templates, jinja2]
research_doc: "[[RESEARCH-codex-loop-execute-gaps]]"
interview_rounds: 2
adrs: 3
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Override ADR-008: expand all Codex stage skills with is_codex=True template flag; fix hooks version; add worktree fallback"
---

# 🎯 Executive Summary

**What**: Codex `@hm-loop` runs no interview and `@hm-execute` creates no worktree because the hm-loop and hm-execute skill files are 25-40 line stubs pointing to an empty AGENTS.md. All 8 gaps (G1-G8 in RESEARCH doc) share the same root: ADR-002 (AGENTS.md carries procedures) was never implemented.

**Why now**: Two confirmed user-facing failures in Codex sessions. The issue has been in production since 0.9.0.

**Key decisions**:
- ADR-001: Override ADR-008 — procedures go **in each stage skill**, not AGENTS.md
- ADR-002: `is_codex=True` Jinja2 flag adapts existing stage templates for Codex (no duplicate templates)
- ADR-003: hm-loop/SKILL.md accepted to exceed 150-line context_lint limit

**Impact**: After this plan, `@hm-execute` deterministically creates a worktree before editing; `@hm-loop` runs the adaptive interview and creates a worktree at Step 5. Claude Code rendering unchanged.

---

## 📚 Prior Work

From RESEARCH-codex-loop-execute-gaps.md:
- 8 gaps found. G1-G5 are template/content gaps; G6 is hooks version; G7 is ADR-005 unverified; G8 is stale cross-reference.
- stage templates total 1885 lines. loop template is 709 lines. These are the source of truth — no new prose to write, just adaptation.

From `failures.md`:
- `[fail:render] yaml-colon-in-unquoted-frontmatter-description` — any description containing `: ` must be double-quoted
- `[fail:test] snapshot-regen-inside-worktree` — regen must run from main repo root
- `[fail:design] return-type-change-breaks-callers` — grep ALL callers when changing function signatures

From `wiki.md`:
- `[wiki:architecture] generator-not-runtime-config` — harness-maker is pre-render, no runtime imports
- `[wiki:pattern] loop-gate-stop-hook-guard` — marker file must be written before wrapup

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| R1-1 | Procedure placement | Architecture | Where do stage procedures go in Codex? (AGENTS.md vs skill files vs hybrid) | C: All stage skills expanded — override ADR-008 entirely | ADR-001 |
| R1-2 | ADR-005 priority | Risk | Codex worktree compat verification — block or parallel? | Non-blocking, parallel with procedure additions | — |
| R1-3 | Hooks version | Scope | Include .codex/hooks.json re-render in this plan? | Yes, include in this plan | — |
| R2-1 | Template strategy | Architecture | How do stage bodies get into skill templates? | A: Reuse stages/*.md.j2 with `is_codex=True` flag — conditional branches | ADR-002 |
| R2-2 | Workflow skills | Scope | Expand hm-exec-rev etc.? | Yes, add stage-chaining procedure | — |
| R2-3 | Exit | — | Continue interview? | Plan sufficiently clear — end | — |

---

## 📐 Architecture Decision Records

### ADR-001: Override ADR-008 — Procedures in stage skills, not AGENTS.md
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** ADR-008 (lightweight stage skills pointing to AGENTS.md) depended on ADR-002 (AGENTS.md carries all procedures). ADR-002 was never implemented — AGENTS.md is 22 lines with no procedures. The design chain is broken.
**Decision:** Override ADR-008. Each stage skill (hm-execute, hm-loop, hm-research, hm-spec, hm-plan, hm-review, hm-verify, hm-wrapup) embeds its own adapted procedure body. AGENTS.md shrinks to an ~80-line workflow navigation overview.

**Expected sizes (compressed with is_codex=True):**
| Skill | Expected lines | Source template lines |
|-------|----------------|----------------------|
| hm-loop | ~200-270 | 709 (loop.md.j2) |
| hm-execute | ~100-130 | 238 |
| hm-plan | ~110-140 | 358 |
| hm-review | ~110-140 | 331 |
| hm-research | ~90-120 | 242 |
| hm-spec | ~80-110 | 292 |
| hm-wrapup | ~80-100 | 230 |
| hm-verify | ~70-100 | 194 |
| hm-exec-rev | ~40-60 | (15-line stub → chaining procedure) |
| **Total** | **~900-1200 lines** | |

Context cost tradeoff: a Codex session that loads all 8 stage skills + 3 workflow skills incurs ~1200 lines of skill context. This is acceptable — Codex loads skills descriptively (only matched skills load per invocation), so a typical session loads 1-3 skills.

**Tripwire for re-evaluation**: If sum of loaded skill lines exceeds 500 lines in a typical fused-workflow session (3 skills × ~165 avg), revisit AGENTS.md-only approach.

**Consequences:**
- ✅ Each skill is self-contained — works without loading AGENTS.md
- ✅ Eliminates AGENTS.md line-budget problem (procedure → skills, overview → AGENTS.md)
- ⚠️ hm-loop/SKILL.md exceeds 150-line context_lint threshold (accepted, see ADR-003)
- ⚠️ Maintaining parity: when stage templates change, Codex skills auto-update via is_codex rendering (no manual sync)

**Rejected alternatives:**
- AGENTS.md-only (ADR-002 approach) — 5:1 compression of 1885-line stage corpus into 400 lines risks losing critical CLI details (exact worktree command, AskUserQuestion replacement pattern)
- Separate Codex template copies — two template trees, drift risk when Claude Code templates evolve

**Source:** Interview Round 1, choice C

---

### ADR-002: `is_codex=True` Jinja2 flag for Claude Code → Codex adaptation
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** Stage templates (stages/*.md.j2) and loop template use three Claude Code-specific constructs: `$ARGUMENTS` injection (Codex has no slash-command args), `!` shell prefix (Codex uses Bash tool calls), and `AskUserQuestion` UI tool (Codex uses natural-language responses in the chat stream).
**Decision:** Add `is_codex: bool = False` to the Jinja2 rendering context. Templates use `{% if is_codex %}` conditionals to emit Codex-native alternatives. Default `False` preserves all existing Claude Code rendering. Codex stage skill rendering passes `is_codex=True`.

**Three adaptations required per template:**

| Construct | Claude Code form | Codex form |
|-----------|------------------|-----------|
| Input parsing | `$ARGUMENTS` references | "Parse from user's natural-language input:" |
| Shell calls | `!uv run ...` / `!cd <WT> && ...` | `Bash("uv run ...")` / `Bash("cd <WT> && ...")` |
| User interaction | `AskUserQuestion(...)` | "Ask in your response:" + question text |
| Cross-stage refs | `/hm:execute` | `@hm-execute` |

**Consequences:**
- ✅ Single template source — Claude Code and Codex stay in sync automatically
- ⚠️ Templates grow more complex with `{% if is_codex %}` blocks
- ⚠️ Template authors must remember to add both branches for new shell calls or user interactions

**Rejected alternatives:**
- Separate Codex template copies (codex/stages/<stage>.md.j2) — two-tree drift risk, no auto-sync when Claude Code templates evolve
- Post-render Python transform (str.replace/re.sub) — fragile string matching, risk of unintended replacements in non-command contexts (e.g., documentation text referencing `$ARGUMENTS`)

**Source:** Interview Round 2, choice A

---

### ADR-003: Accept context_lint warning for hm-loop/SKILL.md (>150 lines)
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** The loop procedure (5-dimension adaptive interview, worktree creation with Bash tool call, per-iteration workflow execution, 4-gate convergence, wrapup + marker cleanup) cannot be losslessly compressed to 150 lines. The `autoloop-driver/SKILL.md` is already 163 lines and ships in production.
**Decision:** Accept context_lint warning for hm-loop/SKILL.md. Target ~200-270 lines. The warning is non-blocking (context_lint returns list[str] warnings, does not fail render). Document exception in CLAUDE.md context lint section.
**Consequences:**
- ⚠️ context_lint warns on every render of hm-loop/SKILL.md
- ✅ Loop procedure is complete and functional for Codex users
**Rejected alternatives:**
- Split into hm-loop + hm-loop-procedure skills — awkward user experience; references between skills require loading both
**Source:** Research finding P2; validator critique acknowledged

---

## 🏗️ Technical Design

### Current State

```
.agents/skills/
├── hm-loop/SKILL.md          — 40 lines, stub, "follow AGENTS.md" (broken)
├── hm-execute/SKILL.md       — 25 lines, stub, "follow AGENTS.md" (broken)
├── hm-{research..}/SKILL.md  — 25 lines each, stubs (broken)
├── hm-exec-rev/SKILL.md      — 25 lines, stub (broken)
├── autoloop-driver/SKILL.md  — 163 lines, full content ✅
└── worktree-isolator/SKILL.md — 97 lines, full content ✅

AGENTS.md                     — 22 lines, no procedures (broken)
.codex/hooks.json             — references version 0.9.0 (stale)
```

### Affected Components

| Component | Change | Phase |
|-----------|--------|-------|
| `src/harness_maker/synthesize.py` | `_codex_stage_skills()`, `_codex_target_files()`, `_codex_workflow_skills()` — render body with `is_codex=True` | 1 |
| `src/harness_maker/templates/codex/stage_skill.md.j2` | Embed `{{ stage_body }}` | 1 |
| `src/harness_maker/templates/codex/loop_skill.md.j2` | Embed `{{ loop_body }}` | 1 |
| `src/harness_maker/templates/codex/workflow_skill.md.j2` | Add stage-chaining procedure | 1 |
| `src/harness_maker/templates/stages/*.md.j2` (7 files) | Add `is_codex` conditional branches | 2 |
| `src/harness_maker/templates/commands/hm/loop.md.j2` | Add `is_codex` branches + worktree fallback | 3 |
| `src/harness_maker/templates/codex/AGENTS.md.j2` | Trim to ~80-line overview | 4 |
| `.codex/hooks.json` | Re-render with 0.9.3 path | 5a |
| `tests/unit/test_codex_phase7.py` | Add content assertions for all stages | 5b |
| `src/harness_maker/synthesize.py` | Add hooks version assertion test | 5b |
| `tests/codex-compat/test_worktree_create.md` | ADR-005 verification checklist | 6 |
| `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2` | Update cross-reference | 7 |
| `src/harness_maker/templates/skills/worktree-isolator/SKILL.md.j2` | Add CLI pattern | 7 |
| Snapshot files | Regenerate from main repo root | 8 |

### Architecture / Data Flow

**Codex skill rendering flow (after this plan):**

```
synthesize._codex_stage_skills()
  │
  ├─ for each stage:
  │    tpl = env.get_template(f"stages/{s}.md.j2")
  │    body = tpl.render(is_codex=True, harness_maker_src_path=..., ...)
  │    FileSpec = ("codex/stage_skill.md.j2", ".agents/skills/hm-{s}/SKILL.md",
  │                {"stage": s, "stage_body": body})
  │
synthesize._codex_target_files()
  │
  ├─ loop_body = env.get_template("commands/hm/loop.md.j2").render(is_codex=True, ...)
  │    FileSpec = ("codex/loop_skill.md.j2", ".agents/skills/hm-loop/SKILL.md",
  │                {"loop_body": loop_body})
  │
  └─ AGENTS.md: env.get_template("codex/AGENTS.md.j2").render(...)  ← ~80-line overview

render.py dispatches → FileEntry → rendered SKILL.md written to disk
```

### `is_codex` Conditional Pattern in Templates

```jinja2
{# Input parsing #}
{% if is_codex %}
Parse from the user's natural-language input: look for a slug as the first
token, and `no-tdd` keyword to set tdd_active=False.
{% else %}
`$ARGUMENTS` is parsed positionally + by flag:
- `<slug>` — task identifier. Required.
- `--no-tdd` — skip Phase A, A.5, B.
{% endif %}

{# Shell calls #}
{% if is_codex %}
```bash
Bash("uv run --with {{ harness_maker_src_path }} python -m harness_maker.worktree create execute $(pwd)")
```
{% else %}
```bash
!uv run --with {{ harness_maker_src_path }} python -m harness_maker.worktree create execute "$(pwd)"
```
{% endif %}

{# User interaction — AskUserQuestion → "ask in response" #}
{% if is_codex %}
Ask in your response: "What is the loop goal or mode (feature/improve)? [free-form]"
Wait for the user's reply before continuing.
{% else %}
AskUserQuestion({questions: [{question: "...", header: "...", options: [...]}]})
{% endif %}
```

### Worktree Fallback (loop template, Phase 3)

Loop Step 5 must include:
```
If `Bash("uv run ... worktree create ...")` fails (non-zero exit or git worktree add error):
  - Log: "Worktree creation failed. Proceeding in-place (no isolation). Risk: edits land on main branch directly."
  - Set <WT> = $(pwd) (current directory).
  - Continue with the loop — do NOT halt.
```

This satisfies ADR-005 non-blocking policy while providing a safe fallback.

---

## 📝 Implementation Plan

### Phase 1 — Template contract + synthesize wiring (merge of original 1+4)

**Scope IN:**
- `src/harness_maker/templates/codex/stage_skill.md.j2`
- `src/harness_maker/templates/codex/loop_skill.md.j2`
- `src/harness_maker/templates/codex/workflow_skill.md.j2`
- `src/harness_maker/synthesize.py`

**Scope OUT:** Stage template content changes (Phase 2), loop adaptation (Phase 3)

**Changes:**
1. Rewrite `codex/stage_skill.md.j2`:
   ```jinja2
   ---
   name: hm-{{ stage }}
   description: "harness-maker {{ stage }} stage. Invoke when task requires {{ stage }}."
   ---
   {{ stage_body }}
   <!-- @hm:user:extensions -->...<!-- @hm:/user:extensions -->
   ```
2. Rewrite `codex/loop_skill.md.j2`: embed `{{ loop_body }}`
3. Rewrite `codex/workflow_skill.md.j2`: embed `{{ workflow_body }}` (15-line stage-chaining procedure)
4. Update `_codex_stage_skills()` in synthesize.py: render `stages/<stage>.md.j2` with `is_codex=True, harness_maker_src_path=...`, pass `stage_body`
5. Update `_codex_target_files()`: render `commands/hm/loop.md.j2` with `is_codex=True`, pass `loop_body`
6. Update `_codex_workflow_skills()`: add `workflow_body` with 15-line chaining description

**Exit criterion:**
```bash
# Sentinel round-trip: stage body passed through
uv run python -c "
from harness_maker.synthesize import _codex_stage_skills
specs = _codex_stage_skills()
execute_spec = next(s for s in specs if 'hm-execute' in s[1])
assert execute_spec[2].get('stage_body'), 'stage_body must be non-empty after Phase 2'
print('stage_body present:', len(execute_spec[2]['stage_body']), 'chars')
"
# AND: existing tests pass
uv run pytest tests/unit/test_codex_phase7.py tests/unit/test_synthesize_codex.py -q
```

**Risk:** medium — wiring contract between templates and synthesize.py
**Rollback:** `git checkout HEAD -- src/harness_maker/synthesize.py src/harness_maker/templates/codex/stage_skill.md.j2 src/harness_maker/templates/codex/loop_skill.md.j2 src/harness_maker/templates/codex/workflow_skill.md.j2`

---

### Phase 2 — stages/*.md.j2: Add `is_codex` conditional branches

**Scope IN:** 7 files:
- `src/harness_maker/templates/stages/execute.md.j2`
- `src/harness_maker/templates/stages/plan.md.j2`
- `src/harness_maker/templates/stages/research.md.j2`
- `src/harness_maker/templates/stages/review.md.j2`
- `src/harness_maker/templates/stages/spec.md.j2`
- `src/harness_maker/templates/stages/verify.md.j2`
- `src/harness_maker/templates/stages/wrapup.md.j2`

**Changes per template:**
- `## Usage` section: wrap slash-command version under `{% if not is_codex %}`, add Codex invocation above under `{% if is_codex %}`
- All `$ARGUMENTS` blocks: wrap under `{% if not is_codex %}`, add natural-language parsing instructions under `{% if is_codex %}`
- `!uv run ...` / `!cd ...` shell calls: conditional `Bash(...)` form for Codex
- `AskUserQuestion(...)` calls: conditional "Ask in your response:" form for Codex
- `/hm:<stage>` cross-refs: conditional `@hm-<stage>` for Codex

**Exit criterion:**
```bash
# execute: Codex render has worktree, no $ARGUMENTS; Claude Code render unchanged
uv run python -c "
from harness_maker.render import _make_env
from harness_maker.models import HarnessConfig
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT
env = _make_env(); cfg = HarnessConfig().model_dump(mode='json')
def render(is_c):
    return env.get_template('stages/execute.md.j2').render(
        stage='execute', workflow_context='', project_name='', feature='',
        config=cfg, harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT, is_codex=is_c)
codex = render(True); cc = render(False)
assert 'worktree' in codex, 'Codex render must mention worktree'
assert '\$ARGUMENTS' not in codex, 'Codex render must not contain \$ARGUMENTS'
assert '\$ARGUMENTS' in cc, 'Claude Code render must preserve \$ARGUMENTS'
assert '!uv run' in cc, 'Claude Code render must preserve ! prefix'
assert 'Bash(' in codex or 'Bash(\"' in codex, 'Codex render must use Bash tool form'
print('Phase 2 exit criterion: PASS')
"
```

**Risk:** medium — 7 templates, each with multiple substitution points; careful not to break Claude Code
**Rollback:** `git checkout HEAD -- src/harness_maker/templates/stages/`

---

### Phase 3 — commands/hm/loop.md.j2: `is_codex` adaptation + worktree fallback

**Scope IN:** `src/harness_maker/templates/commands/hm/loop.md.j2`

**Key adaptations:**
- Step 1 `$ARGUMENTS` parsing → Codex natural-language equivalent
- Step 4 (Adaptive interview) all `AskUserQuestion(...)` calls → "Ask in your response:" pattern
- Step 5 worktree creation → `Bash("uv run ... worktree create ...")` + fallback path
- Step 5 marker file write → `Bash("echo ... > .claude/.hm-loop-...")`
- All `!` prefix shell calls → `Bash("...")`
- `/hm:` references → `@hm-`

**Worktree fallback addition at Step 5:**
```
If the Bash worktree create command fails (non-zero exit):
  Warn the user: "Worktree creation failed — proceeding in-place (no isolation)."
  Set <WT> = the current working directory. Continue.
```

**Exit criterion:**
```bash
uv run python -c "
from harness_maker.render import _make_env
from harness_maker.models import HarnessConfig
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT
env = _make_env(); cfg = HarnessConfig().model_dump(mode='json')
def render_loop(is_c):
    return env.get_template('commands/hm/loop.md.j2').render(
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT, is_codex=is_c, config=cfg)
codex = render_loop(True); cc = render_loop(False)
# Critical assertions (validator critique C3)
assert 'AskUserQuestion' not in codex, 'Codex loop must not contain AskUserQuestion'
assert 'ask' in codex.lower() or 'in your response' in codex.lower(), 'Codex interview must use response-based pattern'
assert codex.count('Bash(') >= 3, 'At least 3 Bash tool calls expected in Codex loop (worktree, marker, finalize)'
assert 'worktree create fails' in codex.lower() or 'in-place' in codex.lower(), 'Fallback path must be documented'
# Claude Code regression check
assert '\$ARGUMENTS' in cc
assert '!uv run' in cc
assert 'AskUserQuestion' in cc
print('Phase 3 exit criterion: PASS')
"
```

**Risk:** high — 709-line template, multiple AskUserQuestion → response conversions
**Rollback:** `git checkout HEAD -- src/harness_maker/templates/commands/hm/loop.md.j2`

---

### Phase 4 — codex/AGENTS.md.j2: Trim to ~80-line workflow overview

**Scope IN:** `src/harness_maker/templates/codex/AGENTS.md.j2`

**Changes:**
- Remove: "autoloop / worktree toggles live in `.claude/harness.yaml`" (Claude Code-specific path)
- Add: Stage navigation list (`@hm-research`, `@hm-spec`, `@hm-plan`, `@hm-execute`, `@hm-review`, `@hm-verify`, `@hm-wrapup`)
- Add: Workflow navigation (`@hm-exec-rev`, `@hm-exec-rev-wrap`, `@hm-exec-rev-wrap-ver`)
- Keep: user block markers (`<!-- @hm:user:project-rules -->`, `<!-- @hm:user:extensions -->`)

**Exit criterion:**
```bash
uv run python -c "
from harness_maker.render import _make_env
env = _make_env()
rendered = env.get_template('codex/AGENTS.md.j2').render()
lines = rendered.strip().splitlines()
assert len(lines) <= 80, f'AGENTS.md must be ≤ 80 lines, got {len(lines)}'
assert '@hm-execute' in rendered, 'Must reference @hm-execute'
assert '@hm-loop' in rendered, 'Must reference @hm-loop'
assert '<!-- @hm:user:extensions -->' in rendered, 'User block markers must be preserved'
print(f'AGENTS.md: {len(lines)} lines. Phase 4 exit criterion: PASS')
"
```

**Risk:** low — small template
**Rollback:** `git checkout HEAD -- src/harness_maker/templates/codex/AGENTS.md.j2`

---

### Phase 5a — Hooks version fix: Re-render .codex/hooks.json (0.9.0 → 0.9.3)

**Scope IN:** `.codex/hooks.json` (harness-maker project's own file)

**Change:** Re-render from `codex/hooks.json.j2` template with current `harness_maker_src_path` (which resolves to 0.9.3 path).

```bash
# Verify the template renders with current version
uv run python -m harness_maker.cli make --dry-run 2>&1 | grep hooks
# Then trigger actual re-render by running make --update
uv run python -m harness_maker.cli make --update
```

**Exit criterion:** `grep "0.9.3" .codex/hooks.json` returns at least 6 matches (one per hook command)
**Risk:** low
**Rollback:** `git checkout HEAD -- .codex/hooks.json`

---

### Phase 5b — Programmatic hooks version assertion test

**Scope IN:** `tests/unit/test_codex_phase4.py` (or new test file `tests/unit/test_codex_hooks_version.py`)

**Change:** Add a test that:
1. Renders `.codex/hooks.json` from template
2. Asserts all hook command paths contain the current `__version__`

```python
def test_codex_hooks_reference_current_version() -> None:
    """All .codex/hooks.json hook commands must reference the current harness-maker version."""
    from harness_maker import __version__
    rendered = render_codex_hooks_json()  # helper or fixture
    # Every 'command' value should contain __version__
    import json
    data = json.loads(rendered)
    commands = [h['command'] for event in data['hooks'].values() 
                for block in event for h in block['hooks']]
    for cmd in commands:
        assert __version__ in cmd, f"Hook command references old version: {cmd}"
```

**Exit criterion:** `uv run pytest tests/unit/test_codex_hooks_version.py -q` passes
**Risk:** low
**Rollback:** `git checkout HEAD -- tests/unit/test_codex_hooks_version.py`

---

### Phase 6 — ADR-005: Codex worktree compat verification (non-blocking)

**Scope IN:** `tests/codex-compat/test_worktree_create.md`

**Content:** Manual verification checklist:
- Open a Codex session in a git repo
- Trigger `@hm-loop "test goal"` — verify Step 5 runs `Bash("git worktree add ...")`
- Record: ✅ succeeds / ❌ blocked by sandbox
- If blocked: confirm fallback ("Proceeding in-place") message appears

**Exit criterion:** File exists at `tests/codex-compat/test_worktree_create.md`
**Risk:** low (doc-only)
**Rollback:** `git rm tests/codex-compat/test_worktree_create.md`

---

### Phase 7 — Cross-reference fixes in skill templates

**Scope IN:**
- `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2`
- `src/harness_maker/templates/skills/worktree-isolator/SKILL.md.j2`

**Changes:**
- autoloop-driver: Replace `"Command: \`commands/hm/loop.md\` (full per-step procedure)"` with `"Claude Code: \`commands/hm/loop.md\` · Codex: \`@hm-loop\` skill"`
- worktree-isolator: Add CLI invocation example alongside existing Python API example:
  ```bash
  # CLI (deterministic — prefer this over Python API for stage scripts)
  uv run python -m harness_maker.worktree create execute "$(pwd)"
  ```

**Exit criterion:**
```bash
grep -q "@hm-loop" src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2
grep -q "uv run python -m harness_maker.worktree" src/harness_maker/templates/skills/worktree-isolator/SKILL.md.j2
```

**Risk:** low
**Rollback:** `git checkout HEAD -- src/harness_maker/templates/skills/`

---

### Phase 8 — Tests: Content assertions + snapshot regeneration

**Scope IN:** `tests/unit/test_codex_phase7.py`, snapshot files

**New tests:**

```python
@pytest.mark.parametrize("stage,must_contain", [
    ("execute", "worktree"),
    ("research", "sources"),
    ("spec", "scenario"),
    ("plan", "phase"),
    ("review", "grade"),
    ("verify", "criterion"),
    ("wrapup", "commit"),
])
def test_codex_stage_skill_has_procedure_content(stage: str, must_contain: str) -> None:
    """All 7 Codex stage skills must contain stage-specific procedure content."""
    specs = _codex_stage_skills()
    spec = next(s for s in specs if f"hm-{stage}" in s[1])
    body = spec[2].get("stage_body", "")
    assert must_contain in body.lower(), f"hm-{stage} skill missing '{must_contain}'"

def test_loop_skill_has_adaptive_interview() -> None:
    """hm-loop/SKILL.md must contain the adaptive interview procedure."""
    # Read from rendered file or render inline
    content = _render_loop_skill_codex()
    assert "interview" in content.lower() or "adaptive" in content.lower()
    assert "AskUserQuestion" not in content  # Codex-adapted: no CC-only tool

def test_codex_stage_skills_no_dollar_arguments() -> None:
    """No Codex stage skill should contain '$ARGUMENTS'."""
    for spec in _codex_stage_skills():
        body = spec[2].get("stage_body", "")
        assert "$ARGUMENTS" not in body, f"{spec[1]} contains $ARGUMENTS"

def test_claude_code_stage_render_unchanged() -> None:
    """Rendering stages with is_codex=False (default) must match prior behavior."""
    # Spot-check execute: $ARGUMENTS present, AskUserQuestion present where expected
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    rendered = env.get_template("stages/execute.md.j2").render(
        stage="execute", workflow_context="", project_name="", feature="",
        config=cfg, harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT
        # is_codex NOT passed → defaults to False
    )
    assert "$ARGUMENTS" in rendered
    assert "!uv run" in rendered
```

**Snapshot regeneration** (from main repo root — see `[fail:test] snapshot-regen-inside-worktree`):
```bash
# Must run from /home/noel/harness-maker/, not from .worktrees/
uv run python tests/snapshot/regenerate.py
```

**Exit criterion:**
```bash
uv run pytest tests/ -q          # all pass
uv run mypy --strict src/        # clean
uv run ruff check src/           # clean
```

**Risk:** low
**Rollback:** `git checkout HEAD -- tests/unit/test_codex_phase7.py tests/snapshot/`

---

## 🧪 Testing Strategy

| Layer | What | When |
|-------|------|------|
| Unit — sentinel | `stage_body` non-empty after Phase 1 wiring | End Phase 1 |
| Unit — content | Execute/loop/all-stages content presence assertions | End Phase 8 |
| Unit — regression | Claude Code rendering unchanged (`is_codex=False`) | End Phase 8 |
| Unit — hooks version | .codex/hooks.json commands reference current version | End Phase 5b |
| Integration — snapshot | Rendered .agents/skills/* compared to stored snapshots | End Phase 8 |
| Manual — Codex session | `@hm-execute` creates worktree; `@hm-loop` runs interview | Post-merge |
| Manual — ADR-005 | Codex sandbox worktree compat check | Phase 6 checklist |

---

## ⚠️ Risks & Mitigation

| Risk | Severity | Phase | Mitigation |
|------|----------|-------|------------|
| hm-loop/SKILL.md > 150 lines | Med | 3 | ADR-003 accepted; context_lint warns, not errors |
| Phase 3 loop template complexity breaks CC rendering | High | 3 | Exit criterion explicitly checks CC render (is_codex=False) |
| AskUserQuestion references survive loop adaptation | High | 3 | Exit criterion asserts zero `AskUserQuestion` in Codex render |
| git worktree add blocked by Codex sandbox | Med | 3, 6 | Step 5 fallback path (in-place with warning); Phase 6 verification |
| Snapshot regen from worktree embeds wrong paths | Med | 8 | Exit criterion: must run from /home/noel/harness-maker/ main repo |
| Phase 2 breaks one of 7 stage templates silently | Med | 2, 8 | Parametrized test covers all 7 stages with must-contain strings |

---

## ✅ Success Criteria

- [x] `@hm-loop <goal>` in Codex session: adaptive interview fires (5 dimensions asked), worktree created at Step 5, marker file written
- [x] `@hm-execute <slug>` in Codex session: worktree created before any file edit (or in-place fallback logged)
- [x] Claude Code `/hm:execute` and `/hm:loop` rendering unchanged (Phase 8 regression test)
- [x] All 7 Codex stage skills contain stage-specific procedure content
- [x] `.codex/hooks.json` references 0.9.3 (not 0.9.0)
- [x] `uv run pytest tests/ -q` — all pass
- [x] `uv run mypy --strict src/` — clean
- [x] `uv run ruff check src/` — clean

---

## 🔍 Plan Validation

**Validator outcome: MAJOR_REVISION → RESOLVED**

| Critique | Resolution |
|----------|-----------|
| C1: Phase 1 exit criterion tautological | Merged Phase 1+4; exit criterion now tests `stage_body` non-empty in FileSpec context |
| C2: Phase ordering broken (Phase 4 must precede Phase 1) | Merged into single Phase 1 (templates + synthesize.py in one phase) |
| C3: Phase 3 exit criterion missing AskUserQuestion check | Added 3 explicit assertions: zero `AskUserQuestion`, presence of response-ask pattern, `Bash(` count |
| C4: Worktree blocking risk mitigation is docs-only | Added explicit worktree fallback path in Phase 3 scope; exit criterion asserts fallback present |
| W5: Rollback chain linear | Changed all rollbacks to per-file `git checkout HEAD --` |
| W6: ADR-001 missing quantification | Added expected line count table + context load tripwire threshold |
| W7: Phase 6 conflates hooks re-render + policy change | Split into Phase 5a (file fix) + Phase 5b (programmatic test) |
| W8: Phase 9 test list incomplete (6/7 stages uncovered) | Added parametrized `test_codex_stage_skill_has_procedure_content` covering all 7 stages |
| S9: AGENTS.md 50 vs 80 line inconsistency | Standardized to 80 lines throughout |
