---
type: plan
task_slug: codex-target-support
status: complete
created: 2026-05-10
tags: [harness-maker, plan, codex, targets, cross-ide, openai, jinja2, python]
research_doc: "[[RESEARCH-codex-target-support]]"
interview_rounds: 4
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Add codex as 3rd target: 9 phases, AGENTS.md + agent TOML + skills dual-render + hooks"
---

# 🎯 Executive Summary

**What:** Add `codex` as a third value in `harness.yaml.targets` (alongside `claude-code` and `cursor`). When `codex` is selected, harness-maker generates the six new asset categories Codex needs, making all harness-maker workflows accessible via Codex's native skill system.

**Why:** OpenAI Codex CLI (released 2025, 80k+ GitHub stars) has emerged as a major AI coding agent alongside Claude Code. Users who work in both environments can't carry their harness configuration across — Codex reads different files from different paths. Full target support brings harness-maker's review workflows, hooks, and workflow guidance to Codex sessions without managing two separate setups.

**Key decisions:**
- ADR-001: `/hm:*` commands → `.agents/skills/hm-<stage>/SKILL.md` (lightweight ~20-line triggers, not full stage bodies)
- ADR-002: `AGENTS.md` at project root, full CLAUDE.md parity
- ADR-003 + ADR-007: Agent TOML via `_body.md.j2` partial refactor (clean frontmatter separation)
- ADR-006: Codex `PermissionRequest` event wired to `permission_gate` (bonus coverage)

**Impact:** New version 0.9.0. ~15 new templates, 3 modified Python modules, 1 modified gate.

---

## 📚 Prior Work

- **RESEARCH-codex-target-support.md** — full asset compatibility matrix, hooks event parity table, Ouroboros prior-art analysis. Key finding: Codex does NOT read `.claude/skills/` — dual-render to `.agents/skills/` is required.
- **PLAN-plugin-vs-generator-2026-05.md (ADR-001)** — generator model is locked in. Same reasoning applies to why Codex config files need static pre-render (hooks.json schema diverges; settings loaded before LLM runs).
- **[fail:render] hooks-cursor-schema-diverge** — Cursor hooks diverge from Claude Code (camelCase vs PascalCase). Codex hooks are PascalCase like Claude Code but have a `PermissionRequest` event and use `apply_patch` as the file-edit tool name. Each IDE owns its own hooks file.
- **[wiki:architecture] generator-not-runtime-config** — harness.yaml stays in `.claude/` regardless of targets. No Codex-specific config location.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Commands→Skills | Architecture | How to expose /hm:* in Codex (no command files)? | One skill per stage at `.agents/skills/hm-<stage>/` | ADR-001 |
| 1 | AGENTS.md depth | Architecture | How deep should AGENTS.md be? | Full CLAUDE.md parity (~400-500 lines) | ADR-002 |
| 2 | Agent TOML content | Contract | Markdown body → `developer_instructions` string strategy? | Full rendered Markdown (via _body.md.j2 partial) | ADR-003, ADR-007 |
| 2 | Skills scope | Scope | All 11 skills or subset to `.agents/skills/`? | All 11 | — |
| 2 | harness.yaml location | Architecture | Codex-only: `.claude/` or `.codex/`? | Always `.claude/harness.yaml` | — |
| 3 | PreCompact fallback | Contract | flush_session without PreCompact in Codex? | Map to Stop event (idempotent) | ADR-004 |
| 3 | worktree_gate | Risk | Include or omit from Codex hooks? | Omit (kernel sandbox; unverified worktree compat) | ADR-005 |
| 3 | PermissionRequest | Architecture | Wire permission_gate to PermissionRequest? | Yes — stronger Codex-specific enforcement | ADR-006 |
| 4 | Agent frontmatter | Contract | Prevent YAML frontmatter bleeding into TOML `developer_instructions`? | Refactor: split `_body.md.j2` per agent | ADR-007 |
| 4 | Stage skill content | Contract | Full stage body or lightweight trigger in SKILL.md? | Lightweight (~20 lines) + pointer to AGENTS.md | ADR-008 |

---

## 📐 Architecture Decision Records

### ADR-001: One skill per stage for Codex workflow invocation
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** Codex has no custom slash command file system. `/hm:*` workflows need a Codex-native invocation mechanism.
**Decision:** Each `/hm:*` stage generates `.agents/skills/hm-<stage>/SKILL.md`. Users invoke via `@hm-research <topic>`, `@hm-plan <slug>`, etc. or Codex picks the skill implicitly when the task matches the description.
**Consequences:**
- ✅ Native Codex skill model; explicit + implicit invocation
- ⚠️ UX change from `/hm:research` to `@hm-research` for Codex users
**Rejected alternatives:** Single router skill (implicit matching harder); AGENTS.md-only (not discretely invokable)
**Source:** Interview #1

### ADR-002: AGENTS.md with full CLAUDE.md parity
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** Codex reads `AGENTS.md` (project root) instead of `CLAUDE.md`. Content depth decision.
**Decision:** Render `AGENTS.md` from `templates/codex/AGENTS.md.j2` with full parity to CLAUDE.md (~400-500 lines). Include `<!-- @hm:user:* -->` HTML comment block-merge markers. Codex ignores HTML comments; block_merge still works.
**Consequences:**
- ✅ Consistent session behavior between Claude Code and Codex
- ⚠️ Near the 32 KiB Codex soft limit; monitor if truncation occurs in large projects
**Rejected alternatives:** Concise summary (loses workflow guidance)
**Source:** Interview #1

### ADR-003: Agent TOML `developer_instructions` = full Markdown body via `_body.md.j2` partial
**Status:** Accepted (2026-05-10, via /hm:plan interview + validator follow-up)
**Context:** Codex agents require `.codex/agents/<name>.toml` with a `developer_instructions` string. Current agents are 57-80 line Markdown files starting with YAML frontmatter. Direct `{% include %}` bleeds frontmatter into the TOML string.
**Decision:** Render `developer_instructions` using the agent's `_body.md.j2` partial (introduced in ADR-007). The partial contains only the behavioral instructions, no frontmatter. Codex treats Markdown headings as plain text — acceptable.
**Consequences:**
- ✅ Zero information loss; same behavioral guidance in both IDEs
- ✅ No frontmatter bleed
- ⚠️ Markdown in TOML string renders as plain text (not structured) in Codex
**Source:** Interview #2 + Interview #4

### ADR-004: `flush_session` mapped to Stop event for Codex
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** `flush_session` fires on `PreCompact` in Claude Code/Cursor. Codex does not document a `PreCompact` hook event.
**Decision:** Wire `flush_session` to Codex's `Stop` event in `.codex/hooks.json`. Stop fires at turn end (superset of PreCompact). `flush_session` is idempotent — extra firing is harmless.
**Consequences:**
- ✅ Loop context preserved at Codex turn boundaries
- ⚠️ Fires more often than needed (every turn, not just `/compact`)
**Source:** Interview #3

### ADR-005: `worktree_gate` omitted from initial Codex hooks
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** `worktree_gate` guards writes outside `.worktrees/` during autoloop. Codex uses kernel sandboxing (Seatbelt on macOS, Landlock on Linux). Whether `git worktree add` works inside Codex sandbox is unverified.
**Decision:** Omit `worktree_gate` from `.codex/hooks.json`. Kernel sandbox provides isolation. Add in a follow-up iteration once worktree behavior is empirically verified (add to `tests/codex-compat/`).
**Consequences:**
- ✅ Reduces unknown risk in initial implementation
- ⚠️ Autoloop write isolation not enforced in Codex until follow-up
**Source:** Interview #3

### ADR-006: `permission_gate` wired to Codex `PermissionRequest` event
**Status:** Accepted (2026-05-10, via /hm:plan interview)
**Context:** Codex has a `PermissionRequest` event (fires when Codex seeks approval) that Claude Code/Cursor lack. Current `permission_gate.py` uses `PreToolUse`.
**Decision:** Wire `permission_gate.py` to `PermissionRequest` in `.codex/hooks.json`. Add a Codex output branch in `permission_gate.py`: detect `hook_event_name == "PermissionRequest"` in stdin (`hook_event_name` is documented in Codex hooks common input fields); emit `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"|"deny"}}}`.
**Consequences:**
- ✅ Codex sessions get per-tool permission policy at both PreToolUse and PermissionRequest gates
- ⚠️ New output format branch in permission_gate.py — must not break Claude Code/Cursor paths
**Source:** Interview #3

### ADR-007: Agent templates refactored to `<name>_body.md.j2` partials
**Status:** Accepted (2026-05-10, via /hm:plan interview — validator follow-up)
**Context:** ADR-003 requires rendering agent Markdown body into a TOML `developer_instructions` string without including YAML frontmatter. Agent `.md.j2` files currently open with `---\nname: ...\n---` frontmatter.
**Decision:** Refactor all 12 agent templates. Extract behavioral body into `templates/agents/<name>_body.md.j2`. The existing `<name>.md.j2` adds frontmatter + `{% include "<name>_body.md.j2" %}`. The Codex TOML template includes only `<name>_body.md.j2`. No behavioral content change; Claude Code/Cursor output unchanged.
**Consequences:**
- ✅ Clean separation; reusable body across Claude/Codex without coupling
- ✅ Future IDE targets can include body without frontmatter concerns
- ⚠️ One-time 12-file refactor; all agent snapshot tests must pass unchanged
**Source:** Interview #4

### ADR-008: Stage skills are lightweight triggers (~20 lines), not full stage bodies
**Status:** Accepted (2026-05-10, via /hm:plan interview — validator follow-up)
**Context:** Stage templates (50-150 lines) are designed for slash command invocation with `$ARGUMENTS`. SKILL.md files activate descriptively — there is no `$ARGUMENTS` injection. Embedding full stage bodies in skills changes the contract and creates two sources of truth vs. AGENTS.md.
**Decision:** Each `hm-<stage>` SKILL.md is ~20 lines: a `description:` field optimized for implicit triggering + instructions telling Codex "follow the `<stage>` stage procedure documented in AGENTS.md, using the user's input as the topic/goal." AGENTS.md (ADR-002) carries the full procedure.
**Consequences:**
- ✅ Single source of truth for stage procedures (AGENTS.md)
- ✅ Minimal stage skill templates; low maintenance
- ⚠️ Codex must have loaded AGENTS.md for the reference to work (standard Codex behavior)
**Source:** Interview #4

---

## 🏗️ Technical Design

### Current State

```
harness-maker targets:
  claude-code → .claude/ (all assets)
  cursor      → .claude/ (agents, skills, commands, hooks native)
              + .cursor/rules/harness.mdc
              + .cursor/hooks.json  (camelCase schema)
              + .cursor/mcp.json

resolve_output_path():
  ".cursor/*" → target_dir.parent / path
  else        → target_dir / path  (target_dir = <project>/.claude)
```

### New State (after codex target)

```
codex target adds:
  AGENTS.md              → project root (target_dir.parent/AGENTS.md)
  .codex/config.toml     → project root sibling
  .codex/hooks.json      → project root sibling
  .codex/agents/*.toml   → project root sibling
  .agents/skills/*/SKILL.md    → project root sibling (all 11 existing skills)
  .agents/skills/hm-*/SKILL.md → project root sibling (7 stage skills)

harness.yaml stays: .claude/harness.yaml (always, regardless of targets)
```

### Affected Components

| Component | Change |
|-----------|--------|
| `models.py` | Add `Target.CODEX = "codex"` |
| `interview.py` | Add `codex` to `_ask_targets()` options; `_parse_targets()` recognizes "codex"; `answers_from_harness_yaml()` round-trips CODEX |
| `synthesize.py` | Add `_codex_target_files()`, `_codex_agent_files()`, `_codex_stage_skills()` |
| `render.py` | Extend `resolve_output_path()` for `.codex/`, `.agents/`, `AGENTS.md`; add `_is_codex_hooks_json()`, `_is_codex_config_toml()`, `_is_codex_agent_toml()`, `_is_agents_md()` predicates; add `_render_pure_toml()` with `tomllib.loads()` validation; add `_render_agents_md()` (HTML-comment metadata, always-merge for block-merge) |
| `gates/permission_gate.py` | Add PermissionRequest output branch |
| `templates/agents/*_body.md.j2` | 12 new body partial files (refactor) |
| `templates/codex/*` | ~15 new templates |
| `tests/unit/test_synthesize_codex.py` | New test module |
| `.codex-plugin/plugin.json` | New file in harness-maker root |
| `CLAUDE.md` | Codex target section; version sync 5 files |

### Architecture: render.py path routing extension

```python
def resolve_output_path(target_dir: Path, fe_path: Path) -> Path:
    path_str = str(fe_path)
    if path_str.startswith(".cursor/") or path_str.startswith(".codex/") \
            or path_str.startswith(".agents/") or path_str == "AGENTS.md":
        return target_dir.parent / fe_path
    return target_dir / fe_path
```

### Architecture: hooks.json parity table

| Hook | Claude Code | Cursor | Codex |
|------|------------|--------|-------|
| sessionstart_drift | SessionStart | — | SessionStart |
| loop_gate | PreToolUse(Bash) | preToolUse(Bash) | PreToolUse(Bash) |
| permission_gate | PreToolUse(Bash) | preToolUse(Bash) | PreToolUse(Bash) + **PermissionRequest** |
| worktree_gate | PreToolUse(Write\|Edit) | preToolUse(Write\|Edit) | **omitted** (ADR-005) |
| spec_gate | PreToolUse(Write\|Edit) | preToolUse(Write\|Edit) | PreToolUse(apply_patch) [spec-driven only] |
| telemetry | PostToolUse(*) | postToolUse(*) | PostToolUse(*) |
| post_write_reminder | PostToolUse(Write\|Edit) | postToolUse(Write\|Edit) | PostToolUse(apply_patch) |
| loop_gate stop | Stop | stop | Stop |
| flush_session | PreCompact | preCompact | **Stop** (ADR-004) |
| sessionstart_drift | SessionStart | — | SessionStart |

### Architecture: agent TOML structure

```toml
# .codex/agents/code-reviewer.toml
name = "code-reviewer"
description = "Reviews code changes for correctness, readability, ..."
model = "gpt-5.4"

developer_instructions = """
[full rendered content of templates/agents/code-reviewer_body.md.j2]
"""
```

### AGENTS.md reconcile strategy (MVP)

AGENTS.md is rendered as pure text (no YAML frontmatter — Codex would show it as literal text). Metadata stored in a leading HTML comment: `<!-- harness-maker: content_hash=<sha256> version=0.9.0 -->`. Block-merge works via `<!-- @hm:user:* -->` HTML blocks (already supported by block_merge module). Content-hash reconcile (KEEP/REPLACE) deferred to follow-up — MVP always re-merges using block_merge markers.

---

## 📝 Implementation Plan

### Phase 1 — Foundation: models + interview + synthesize scaffold + render routing
**Scope IN:** `models.py` (Target.CODEX), `interview.py` (_ask_targets + _parse_targets + answers_from_harness_yaml), `synthesize.py` (empty _codex_target_files stub, _codex_agent_files stub, _codex_stage_skills stub wired into synthesize()), `render.py` (extend resolve_output_path for .codex/ .agents/ AGENTS.md prefixes)
**Scope OUT:** All templates
**Exit criterion:** `uv run pytest tests/unit/test_models.py tests/unit/test_interview.py -q` pass; `uv run pytest tests/unit/test_synthesize.py -k "codex"` pass (stub emits empty list for codex target); `uv run pytest tests/unit/test_render.py -k "codex or agents_md"` pass (path routing tests)
**Risk:** low
**Rollback:** revert to prior commit (no templates changed)

### Phase 2 — Render infrastructure: TOML dispatch + predicates
**Scope IN:** `render.py`: add `_is_codex_hooks_json()`, `_is_codex_config_toml()`, `_is_codex_agent_toml()`, `_is_agents_md()` predicates; add `_render_pure_toml()` with `tomllib.loads()` validation (raises on parse failure, like `_render_pure_json`); add `_render_agents_md()` (pure text, HTML-comment metadata, always-merge); wire into `render_blueprint()`
**Scope OUT:** All templates, synthesize changes
**Exit criterion:** `uv run pytest tests/unit/test_render.py -q` pass; direct `_render_pure_toml()` call with invalid TOML raises `ValueError` with template name in message
**Risk:** low
**Rollback:** Phase 1

### Phase 3 — Agent body refactor (`_body.md.j2` partials)
**Scope IN:** Create `templates/agents/<name>_body.md.j2` for all 12 agents (extract body content below the `---\n...\n---` frontmatter block); update `templates/agents/<name>.md.j2` to `{% include "<name>_body.md.j2" %}` where the body was
**Scope OUT:** Codex templates, synthesize changes
**Exit criterion:** `uv run pytest tests/snapshot/ -q` pass UNCHANGED (all existing snapshots identical — this is a pure refactor with zero behavioral change for Claude Code/Cursor output)
**Risk:** medium — 12-file refactor; snapshot diff must be exactly zero
**Rollback:** Phase 2 (revert agent templates only)

### Phase 4 — Core Codex templates: `config.toml` + `AGENTS.md`
**Scope IN:** `templates/codex/config.toml.j2` (`[features] codex_hooks = true`, `[mcp_servers.<name>]` from answers.mcp_servers); `templates/codex/AGENTS.md.j2` (adapted from Production.en.md.j2 — strip Jinja2 Claude-specific blocks, add HTML `<!-- @hm:user:* -->` blocks); reconcile.py: add AGENTS.md to merge-eligible set; synthesize.py: update _codex_target_files() with these 2 entries
**Exit criterion:** Snapshot shows `.codex/config.toml` (validates via `tomllib.loads()`) and `AGENTS.md` at project root; block_merge round-trip test: AGENTS.md with user block survives regeneration
**Risk:** low
**Rollback:** Phase 3

### Phase 5 — Codex hooks: `.codex/hooks.json` + `permission_gate` PermissionRequest
**Scope IN:** `templates/codex/hooks.json.j2` (events: SessionStart/PreToolUse/PostToolUse/Stop/PermissionRequest per architecture table); `gates/permission_gate.py`: detect `hook_event_name == "PermissionRequest"` in stdin → emit `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"|"deny"}}}` — fallback dispatch: `event_name = parsed.get("hook_event_name", "PreToolUse")`; synthesize.py: add hooks.json to _codex_target_files()
**Exit criterion:** Snapshot `.codex/hooks.json`; `json.loads()` validates; unit test: PermissionRequest stdin → Codex output shape; unit test: PreToolUse stdin → existing Claude Code exit-code output (regression guard)
**Risk:** medium — permission_gate output fork must not break existing paths
**Rollback:** Phase 4

### Phase 6 — Agent TOML templates
**Scope IN:** `templates/codex/agents/<name>.toml.j2` per agent (name, description, optional model from agent frontmatter, `developer_instructions = """{% include "<name>_body.md.j2" %}"""`); synthesize.py: `_codex_agent_files()` registered in _codex_target_files()
**Exit criterion:** Snapshot `.codex/agents/*.toml` for all 12 agents; each validates via `tomllib.loads()`; `developer_instructions` field does NOT contain `---\nname:` frontmatter header (regression guard from ADR-007)
**Risk:** medium — `{% include %}` in TOML template string requires careful Jinja2 handling of triple-quote delimiters
**Rollback:** Phase 5

### Phase 7 — Skills dual-render + stage skills
**Scope IN:** synthesize.py: `_codex_skill_files()` — all 11 existing skills with output `.agents/skills/<n>/SKILL.md` (same template, new output path); `_codex_stage_skills()` — 7 stages (research/spec/plan/execute/review/wrapup/verify) with output `.agents/skills/hm-<stage>/SKILL.md` from `templates/codex/stage_skill.j2` (~20-line template per stage); register both in _codex_target_files()
**Exit criterion:** Snapshot `.agents/skills/` shows 11 + 7 = 18 directories; each SKILL.md has valid `name:` and `description:` frontmatter; `hm-research/SKILL.md` description mentions "harness-maker research stage" and "AGENTS.md"
**Risk:** low
**Rollback:** Phase 6

### Phase 8 — `.codex-plugin/plugin.json` + version bump to 0.9.0
**Scope IN:** New `.codex-plugin/plugin.json` in harness-maker root (same structure as `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`); version bump to 0.9.0 across 5 files: `pyproject.toml`, `src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`; update CLAUDE.md §버전업 정책 from 4-file to 5-file rule; update drift-monitor/version-sync assertions if any
**Exit criterion:** `grep -r '"version"' .claude-plugin/ .cursor-plugin/ .codex-plugin/ pyproject.toml src/harness_maker/__init__.py` all show 0.9.0; `python -c "import harness_maker; assert harness_maker.__version__ == '0.9.0'"` passes
**Risk:** low
**Rollback:** Phase 7 (version bump is last commit in this phase, revert if needed)

### Phase 9 — Tests + snapshots + context lint + docs
**Scope IN:** `tests/unit/test_synthesize_codex.py` (codex target full blueprint assertions); `tests/codex-compat/` directory with hook stdin/output contract fixtures; snapshot regeneration from main repo root (IMPORTANT: run from root, not worktree — per [fail:test] snapshot-regen-inside-worktree); `context_lint.py` threshold for AGENTS.md (≤ 500 lines per Production preset); CLAUDE.md codex target section; `uv run ruff check src/` + `mypy --strict src/` clean
**Exit criterion:** `uv run pytest -q` green (run in background per memory); `uv run mypy --strict src/` 0 errors; `uv run ruff check src/` 0 errors; snapshot baselines committed from main repo root; CLAUDE.md contains `codex` in Targets section
**Risk:** low
**Rollback:** Phase 8

---

## 🧪 Testing Strategy

**Unit tests:**
- `test_models.py`: Target.CODEX in enum, harness.yaml round-trip with codex target
- `test_interview.py`: _ask_targets includes "codex"; answers_from_harness_yaml deserializes CODEX
- `test_render.py`: resolve_output_path for `.codex/`, `.agents/`, `AGENTS.md`; `_render_pure_toml` validation; `_render_agents_md` HTML-comment metadata
- `test_synthesize_codex.py`: _codex_target_files() returns expected FileSpec list; no codex files emitted when only claude-code target; all 18 skills emitted when codex target
- `test_permission_gate.py`: PermissionRequest stdin → Codex output shape; PreToolUse stdin → unchanged Claude Code behavior

**Snapshot tests:**
- Regenerate all snapshots from main repo root after Phase 3 (agent refactor) and after Phase 9 (final state)
- New snapshots: `.codex/config.toml`, `AGENTS.md`, `.codex/hooks.json`, `.codex/agents/*.toml`, `.agents/skills/*`

**Integration tests:**
- `tests/codex-compat/`: capture representative hook stdin samples; assert output shapes

**Manual checklist (no Codex CLI automation in CI):**
- Install harness with `targets: [codex]`; verify AGENTS.md appears at project root
- Start Codex session; verify `@hm-research` triggers skill; verify hooks fire (SessionStart appears in observability metrics)
- Verify `.codex/config.toml` is accepted by Codex (no parse errors at startup)

---

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Agent TOML Jinja2 triple-quote conflict | Medium | Use TOML literal strings `'''...'''` if `"""` causes issues; pin snapshot test for agent with code fences |
| AGENTS.md 32 KiB Codex soft limit | Low | Monitor rendered size; split into AGENTS.md + AGENTS.context.md if needed |
| Codex doesn't read `.agents/skills/` (path wrong) | Low | Verified in Codex official docs. Add to `tests/codex-compat/` for empirical confirmation |
| PreCompact-as-Stop over-fires flush_session | Low | flush_session is idempotent; extra Stop fires add latency but no correctness risk |
| Phase 3 agent refactor breaks snapshot tests | Medium | Exit criterion: zero snapshot diff. Diff any failure immediately. |
| permission_gate PermissionRequest breaks PreToolUse path | Medium | Fallback dispatch default = "PreToolUse"; regression test for existing Claude Code behavior |
| skills duplication drift (.claude/skills/ vs .agents/skills/) | Low | Both outputs from same SKILL.md template — no divergence path. Claude Code #31005 (no .agents/ support) tracked; if Anthropic ships support, remove duplication in a follow-up. |

---

## ✅ Success Criteria

- [x] `Target.CODEX` in enum; `interview._ask_targets()` includes "codex"
- [x] `harness-maker make` with `targets: [codex]` generates all 6 new asset categories
- [x] `AGENTS.md` at project root passes `block_merge` round-trip (user blocks preserved)
- [x] `.codex/config.toml` validates with `tomllib.loads()`
- [x] `.codex/hooks.json` validates with `json.loads()`; all 5 events present (SessionStart, PreToolUse, PostToolUse, Stop, PermissionRequest)
- [x] `.codex/agents/*.toml` validates with `tomllib.loads()`; `developer_instructions` contains no `---\nname:` frontmatter header
- [x] `.agents/skills/` contains 18 directories (11 existing + 7 hm-stage)
- [x] `permission_gate.py` emits correct Codex output for PermissionRequest; unchanged for PreToolUse
- [x] `.codex-plugin/plugin.json` version == `pyproject.toml` version == `__version__` == 0.9.0
- [x] All 5 plugin manifests sync to 0.9.0
- [x] `uv run pytest -q` green; `mypy --strict src/` 0 errors; `ruff check src/` 0 errors
- [x] Manual: Codex session loads AGENTS.md without error; `@hm-research` skill triggers

---

## 🔍 Plan Validation

**Validator outcome: MAJOR_REVISION → RESOLVED**

| Critique | Severity | Resolution |
|----------|----------|-----------|
| `.agents/skills/` path unverified | Critical | Cited from Codex official docs: "Repository-level: `.agents/skills` in CWD up to repo root" (developers.openai.com/codex/skills). Added citation in design section. |
| PermissionRequest `hook_event_name` field name | Critical | Confirmed from Codex hooks docs: "All hooks receive: `hook_event_name: Current event name`". Fallback dispatch added to Phase 5 scope. |
| Agent TOML frontmatter bleed + triple-quote | Critical | Resolved via ADR-007 (refactor to `_body.md.j2` partials). Phase 3 added for this refactor. TOML literal strings `'''` as fallback noted in risks. |
| Stage skills semantics ($ARGUMENTS mismatch) | Critical | Resolved via ADR-008 (lightweight 20-line triggers pointing to AGENTS.md). Phase 7 updated. |
| spec_gate missing from Codex hooks | Critical | Added to Phase 5 scope: spec_gate included with `apply_patch` matcher (conditional on dev_mode==spec-driven, like Claude Code). |
| `_render_pure_toml` missing | Critical | Phase 2 added. Includes `tomllib.loads()` validation on render, exit criteria updated. |
| AGENTS.md reconcile/merge path | Warning | Phase 4 scope: AGENTS.md added to reconcile merge-eligible set; HTML comment `content_hash` added to metadata. |
| Phase 1 exit too narrow | Warning | Phase 1 exit expanded: synthesize codex stub test + render path routing tests. |
| `.codex-plugin/plugin.json` schema | Warning | Noted as speculative; using same structure as existing `.claude-plugin/`. Codex marketplace spec cited where available. |
| Missing Codex compat verification fixture | Warning | `tests/codex-compat/` directory added in Phase 9 scope. |
| Version bump ordering | Warning | Version bump moved to Phase 8 (after Phase 7 features stable), before Phase 9 (final test + snapshot). |
| Skills duplication justification | Warning | Explicitly documented: Codex does NOT read `.claude/skills/`. GitHub issue #31005 tracked for future cleanup. |
| harness.yaml round-trip | Warning | Explicitly added to Phase 1 scope: `answers_from_harness_yaml` round-trip test for CODEX target. |
| Phase 9 scope underspecified | Warning | Split into explicit steps: snapshot regen, full pytest, mypy, ruff, e2e. |
| Permissions/sandbox parity | Warning | Documented as out of scope for this plan; added as follow-up item (Codex per-agent sandbox mapping unresolved in Codex docs). |
