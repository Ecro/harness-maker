---
type: research
task_slug: codex-target-support
status: complete
created: 2026-05-10
tags: [harness-maker, research, codex, targets, cross-ide, openai]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://developers.openai.com/codex/config-reference
  - https://developers.openai.com/codex/guides/agents-md
  - https://developers.openai.com/codex/cli/slash-commands
  - https://developers.openai.com/codex/subagents
  - https://developers.openai.com/codex/hooks
  - https://developers.openai.com/codex/plugins
  - https://developers.openai.com/codex/skills
  - https://developers.openai.com/codex/mcp
  - https://developers.openai.com/codex/custom-prompts
  - https://agents.md/
  - https://cursor.com/docs/skills
  - https://codersera.com/blog/claude-code-vs-openai-codex-2026/
  - https://github.com/anthropics/claude-code/issues/31005
related_docs:
  - "[[PLAN-plugin-vs-generator-2026-05]]"
  - "[[RESEARCH-multi-repo-mgmt-2026-05]]"
summary: "Dual-render 6 new Codex asset categories; commands→skills is the biggest gap requiring arch decision"
---

# 🎯 Recommended Direction

**Add `codex` as a third target value alongside `claude-code` and `cursor`.** When `targets` includes `codex`, render 6 new asset categories under `.agents/`, `.codex/`, and project root. The SKILL.md format is already cross-compatible; the main delta is new discovery paths, a TOML config format, agent TOML conversion, and replacing `/hm:*` commands with `.agents/skills/` skills (since Codex has no custom command file system).

**Binding trade-off**: Commands-as-skills changes the user invocation model from `/hm:research` to something like `$hm:research` or explicit `@hm:research` — a UX break for Codex users relative to Claude Code / Cursor. The alternative (no workflow commands in Codex at all) is worse.

---

## 🛠️ Approaches Found

### Approach A — Full target parity with dual-render (Recommended)

**Assumption**: All harness-maker capabilities should work in Codex, even if the invocation UX differs per IDE.

**What it adds when `codex` in `targets`:**

| New file | Template needed | Source |
|----------|----------------|--------|
| `AGENTS.md` (project root) | `codex/AGENTS.md.j2` | Adapted from CLAUDE.md template; HTML comment `@hm:user:*` blocks preserved (Codex ignores HTML comments) |
| `.agents/skills/<name>/SKILL.md` | mirror of existing SKILL.md templates | Same file content, different discovery path |
| `.codex/agents/<name>.toml` | `codex/agents/<name>.toml.j2` | Agent behavioral content from `.md` → TOML `developer_instructions` field |
| `.codex/hooks.json` | `codex/hooks.json.j2` | PascalCase nested schema, close to Claude Code but `apply_patch` + no `preset` field + `PermissionRequest` event |
| `.codex/config.toml` | `codex/config.toml.j2` | `[features] codex_hooks = true` + `[mcp_servers]` section |
| `.agents/skills/hm-<stage>/SKILL.md` | `codex/commands-as-skills/<stage>.j2` | Each `/hm:*` workflow exposed as a skill (explicit invocation: `@hm:research`) |

Also: `.codex-plugin/plugin.json` → version-sync expands from 4 to 5 files.

**Evidence**: All 6 asset categories have official Codex documentation and clear schemas. No speculative API.

**Trade-off**: Significant new template surface (~15 new templates). Agent TOML conversion is lossy (rich Markdown structure → flat `developer_instructions` string). Commands-as-skills changes invocation UX.

**Risk**: medium — scope is well-defined but agent TOML conversion needs careful testing.

---

### Approach B — Shallow target (AGENTS.md + hooks + config only)

Render only the runtime-critical files (AGENTS.md, .codex/hooks.json, .codex/config.toml) and skip skills-as-commands + agent TOML conversion.

**Trade-off**: Codex sessions get hooks protection and project context, but no `/hm:*` equivalent workflow guidance and no sub-agent dispatch. Codex target degrades to "hooks-only" — not "all operations working."

**Risk**: low — small scope, but violates the user's stated requirement ("모든 동작들이 모두 완벽하게 codex 에서 동작되어야 해").

---

### Approach C — `.agents/` as single source (migration)

Move skills from `.claude/skills/` to `.agents/skills/` as the canonical location. Claude Code currently does NOT support `.agents/skills/` (GitHub issue #31005 open, no Anthropic response as of March 2026), so this would break Claude Code until Anthropic ships that feature.

**Trade-off**: Cleaner long-term, but requires Claude Code to first implement `.agents/skills/` discovery. Premature now.

**Risk**: high — breaks Claude Code today.

---

## ⚠️ Pitfalls

### P1. Claude Code does NOT read `.agents/skills/`
As of March 2026, Claude Code only discovers skills at `.claude/skills/`. GitHub issue #31005 was open with no official response. **Do not move skills to `.agents/skills/` as a single source** — dual-render is required when Codex target is selected. ([source](https://github.com/anthropics/claude-code/issues/31005))

### P2. Codex agent format is TOML, not Markdown
`.codex/agents/<name>.toml` requires specific fields: `name`, `description`, `developer_instructions` (string). The current Markdown agents use multi-section headings, `<!-- -->` comments, and frontmatter that are Claude Code-specific. A Jinja2 template must flatten the complex agent content into a single `developer_instructions` string. Test that long agent prompts (e.g., `autoloop-coder.md` is 180+ lines) don't hit Codex agent file size limits. ([source](https://developers.openai.com/codex/subagents))

### P3. Codex hooks require explicit opt-in in config.toml
Hooks are experimental and disabled by default. The rendered `.codex/config.toml` MUST include `[features]\ncodex_hooks = true` or no hooks fire — silently. This is not true for Claude Code or Cursor. ([source](https://developers.openai.com/codex/config-advanced))

### P4. `PreCompact` event not documented for Codex
The harness-maker `flush_session` hook fires on Claude Code's `PreCompact` and Cursor's `preCompact` events. This event is NOT documented in Codex hooks. Codex has a `/compact` slash command, but whether it triggers a `PreCompact` hook event is unknown. The `flush_session` hook may need to move to `Stop` for Codex, accepting a slightly different flush timing.

### P5. Tool names differ: `apply_patch` not `Edit`/`Write`
Codex uses `apply_patch` for file edits (not `Edit`, `Write`, `MultiEdit`). The `worktree_gate` and `spec_gate` hooks that match `Write|Edit` must add `apply_patch` as a Codex matcher. ([source: Codex hooks docs PreToolUse section])

### P6. No custom slash command files in Codex
Codex has no `.codex/commands/*.md` equivalent. Custom prompts (deprecated since ~late 2025) required user-level `~/.codex/prompts/` and were project-non-shareable. **Skills are the canonical replacement**, but they change the invocation UX: `/hm:research` → `@hm:research` or `/skills hm:research`. The user must be informed of this at interview time. ([source](https://developers.openai.com/codex/custom-prompts))

### P7. Version sync expands to 5 files
Current: `pyproject.toml` + `__init__.py` + `.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json`.
With Codex: add `.codex-plugin/plugin.json`. Missing any one causes a marketplace "already at latest" false positive. ([source: CLAUDE.md §버전업 정책])

### P8. AGENTS.md has no `@hm:user:*` block-merge standard
Codex's `AGENTS.md` has no block-merge mechanism. However, HTML comments are valid Markdown and Codex ignores them. The existing `<!-- @hm:user:* -->` pattern will work in AGENTS.md without modification — Codex renders the visible text only. This is inference; verify empirically.

### P9. Worktree sandboxing conflict
Codex uses kernel-level sandboxing (Seatbelt on macOS, Landlock on Linux). The harness-maker worktree system creates git worktrees in `.worktrees/` and uses file-system gates to restrict writes. Codex's sandbox may prevent `git worktree add` or may restrict access to parent directories needed for worktree creation. This is an **unknown** — needs manual verification on Codex before implementing worktree gate for Codex target.

---

## ❓ Open Questions (for `/hm:plan`)

1. **Commands-as-skills UX**: What's the Codex invocation pattern for `/hm:*` workflows? Is `@hm:research <topic>` acceptable, or does it need a different convention (e.g., single top-level "harness" skill with routing)?

2. **`PreCompact` alternative**: For `flush_session` in Codex, does Codex fire any pre-compaction hook? If not, should `flush_session` move to `Stop` for Codex only, or be dropped?

3. **Agent TOML content strategy**: The 12 agents have complex Markdown bodies (180–300 lines each). A flat `developer_instructions` string loses heading structure. Should we: (a) dump full Markdown as the string value, (b) strip headings and inline content, or (c) generate a condensed Codex-specific agent summary?

4. **`.agents/skills/` naming conflict with existing `.claude/commands/`**: The harness-maker already has skills (in `.claude/skills/`) AND commands (in `.claude/commands/hm/`). For Codex, workflows become skills too. Should Codex-target skills use a `hm-` prefix (e.g., `.agents/skills/hm-research/`) to avoid collision with the existing skill category?

5. **Worktree gate feasibility**: Does Codex's sandbox allow `git worktree add` operations? If not, should the `worktree_gate` hook be a no-op for Codex target (render with empty matcher), or skipped entirely?

6. **`harness.yaml` location for Codex**: Currently `.claude/harness.yaml`. Should a Codex-only install (no claude-code target) still use `.claude/harness.yaml`, or move to `.codex/harness.yaml`? The generator needs a canonical config location regardless of target.

7. **`AGENTS.md` scope**: Should harness-maker render `AGENTS.md` only at project root, or also at top-level `~/.codex/AGENTS.md` for user-level instructions (like CLAUDE.md global)?

---

## 📊 Full Asset Compatibility Matrix (May 2026)

| Asset | Claude Code | Cursor | Codex | Single-source possible? |
|-------|------------|--------|-------|------------------------|
| Instructions | `CLAUDE.md` | `.cursor/rules/*.mdc` | `AGENTS.md` | No — 3 different formats |
| Hooks | `.claude/hooks/hooks.json` (PascalCase nested) | `.cursor/hooks.json` (camelCase flat) | `.codex/hooks.json` (PascalCase nested, close to CC) | No — 3 schemas |
| Settings/Config | `.claude/settings.json` (JSON) | — (Cursor reads Claude) | `.codex/config.toml` (TOML) | No |
| MCP Servers | In settings | `.cursor/mcp.json` | `.codex/config.toml [mcp_servers]` | No |
| Sub-agents | `.claude/agents/*.md` (Markdown) | `.claude/agents/*.md` (shared) | `.codex/agents/*.toml` (TOML!) | No — format diverges |
| Skills | `.claude/skills/<n>/SKILL.md` | `.claude/skills/<n>/SKILL.md` (compat) + `.agents/skills/<n>/SKILL.md` (primary) | `.agents/skills/<n>/SKILL.md` | **SKILL.md format is same**; path differs → dual-render |
| Slash Commands | `.claude/commands/hm/*.md` | Dead (`.cursor/commands/` unverified) | Skills at `.agents/skills/hm-*/SKILL.md` | No — different mechanism |
| Plugin Manifest | `.claude-plugin/plugin.json` | `.cursor-plugin/plugin.json` | `.codex-plugin/plugin.json` | No — 3 manifests |
| harness.yaml | `.claude/harness.yaml` | `.claude/harness.yaml` | `.claude/harness.yaml` (no Codex native) | Yes — stays in `.claude/` |

### Hooks event parity

| Event | Claude Code | Cursor | Codex | harness-maker usage |
|-------|------------|--------|-------|---------------------|
| SessionStart | ✓ | ✗ | ✓ | `sessionstart_drift` |
| PreToolUse | ✓ (Bash, Write, Edit) | ✓ (preToolUse camelCase) | ✓ (Bash, apply_patch) | `loop_gate`, `permission_gate`, `worktree_gate`, `spec_gate` |
| PostToolUse | ✓ | ✓ | ✓ | `telemetry`, `post_write_reminder` |
| Stop | ✓ | ✓ | ✓ | `loop_gate --mode stop-hook` |
| PreCompact | ✓ | ✓ (preCompact) | **Unknown** | `flush_session` |
| PermissionRequest | ✗ | ✗ | ✓ | Not currently used — opportunity |

---

## 📚 Sources

- [Codex Configuration Reference](https://developers.openai.com/codex/config-reference)
- [AGENTS.md Guide – Codex](https://developers.openai.com/codex/guides/agents-md)
- [Codex CLI Slash Commands](https://developers.openai.com/codex/cli/slash-commands)
- [Codex Subagents](https://developers.openai.com/codex/subagents)
- [Codex Hooks](https://developers.openai.com/codex/hooks)
- [Codex Plugins](https://developers.openai.com/codex/plugins)
- [Codex Agent Skills](https://developers.openai.com/codex/skills)
- [Codex MCP](https://developers.openai.com/codex/mcp)
- [Codex Custom Prompts (deprecated)](https://developers.openai.com/codex/custom-prompts)
- [AGENTS.md Open Standard](https://agents.md/)
- [Cursor Agent Skills Docs](https://cursor.com/docs/skills)
- [Claude Code vs Codex 2026 – Codersera](https://codersera.com/blog/claude-code-vs-openai-codex-2026/)
- [Claude Code `.agents/skills/` support issue #31005](https://github.com/anthropics/claude-code/issues/31005)

---

## 🔗 Related Internal Docs

- [[PLAN-plugin-vs-generator-2026-05]] — ADR-001 explains why harness-maker must remain a generator; hooks.json schema divergence is exhibit A. Same pattern applies to Codex config.toml.
- [[RESEARCH-multi-repo-mgmt-2026-05]] — sibling repo + worktree architecture; Codex sandboxing interacts with `.worktrees/` isolation model.
