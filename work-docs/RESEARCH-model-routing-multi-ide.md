---
type: research
task_slug: model-routing-multi-ide
status: complete
created: 2026-05-17
tags: [harness-maker, research, model-routing, token-optimization, claude-code, cursor, codex]
mtime_warn_days: 7
libs_fetched:
  - claude-code/model-config
  - claude-code/sub-agents
  - claude-code/fast-mode
  - cursor/subagents
  - cursor/hooks
  - cursor/models-and-pricing
  - codex/config-reference
  - codex/subagents
  - codex/config-schema-json
sources:
  - https://code.claude.com/docs/en/model-config
  - https://code.claude.com/docs/en/sub-agents
  - https://code.claude.com/docs/en/fast-mode
  - https://code.claude.com/docs/en/changelog
  - https://github.com/anthropics/claude-code/issues/43869
  - https://cursor.com/docs/context/subagents
  - https://cursor.com/docs/hooks
  - https://cursor.com/docs/models-and-pricing
  - https://cursor.com/changelog
  - https://forum.cursor.com/t/extend-mdc-rule-frontmatter-with-a-model-field-for-cost-efficient-agentic-workflows/156812
  - https://forum.cursor.com/t/subagent-fast-model-doesnt-work/149755
  - https://forum.cursor.com/t/subagent-task-tool-ignores-model-specific-subagent-type-routing-all-subagents-inherit-parent-model-instead-of-using-their-designated-models-opus-codex/151917
  - https://developers.openai.com/codex/config-reference
  - https://developers.openai.com/codex/config-advanced
  - https://developers.openai.com/codex/subagents
  - https://developers.openai.com/codex/models
  - https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json
  - https://aider.chat/docs/config/options.html
  - https://aider.chat/docs/usage/modes.html
  - https://docs.plandex.ai/models/roles/
  - https://docs.plandex.ai/models/built-in/built-in-packs/
  - https://docs.continue.dev/customize/model-roles
  - https://docs.cline.bot/features/plan-and-act
  - https://roocodeinc.github.io/Roo-Code/features/custom-modes
  - https://opencode.ai/docs/config/
  - https://opencode.ai/docs/agents/
  - https://ampcode.com/manual
  - https://github.com/block/goose/issues/4036
  - https://docs.openhands.dev/openhands/usage/llms/custom-llm-configs
  - https://kilo.ai/docs/code-with-ai/agents/auto-model
related_docs:
  - work-docs/RESEARCH-codex-plan-validator-model-unavailable.md
  - .claude/memory/project_cursor_model_policy.md
  - .claude/memory/project_targets_axis.md
summary: "Per-agent routing is the right abstraction, but Claude Code's is silently broken (#43869) and our harness already has the schema gap that other OSS harnesses ship around."
---

# RESEARCH — Model routing for token optimization across Claude Code / Cursor / Codex

## 🎯 Recommended Direction

**Per-agent model pinning in `harness.yaml`, with preset-aware defaults (Production vs Side ship different cost/quality baselines), rendered per-IDE-correctly, and the silent-failure gotchas surfaced in `/hm:health` so users know which routing actually fires.**

User-confirmed shape (2026-05-17): "각 agent 별 모델을 정할수 있으면 좋을 듯 preset 은 product 과 side 에 맞게 있고". Translation:

1. **Per-agent model pin** — each of our 14 agents (or future user-added agents) gets its own `model:` knob. Not role aggregation; full per-agent control. Matches our existing `templates/agents/*.md.j2` shape, but with the values flowing from `harness.yaml` instead of hardcoded.
2. **Preset-aware defaults** — Production and Side presets each ship a sensible per-agent default map. Side leans cheap (Sonnet across the board, Haiku for cheap aux), Production leans toward correctness (Opus for reasoning, Sonnet for reviewers). User overrides individual agents from the preset baseline.

Today harness-maker has `HarnessConfig.recommended_model = "claude-opus-4-7"` — one global string. Claude agent templates already hardcode `model: opus | sonnet` per agent (3 opus, 11 sonnet). That **looks like** working routing, but:

- **Claude Code**: subagent `model:` frontmatter is *documented but non-functional* — every subagent inherits the parent's model (Anthropic issue [#43869](https://github.com/anthropics/claude-code/issues/43869), unpatched as of 2026-05). Our 14 routed agents all silently run on whatever the parent session selected.
- **Cursor**: subagent `model:` *does* work, but only on **Cursor 3.3+** (released 2026-05-07). On 2.4–3.2 only concrete IDs resolve, not the bare `sonnet`/`opus` aliases we render. Our templates ship the broken alias form.
- **Codex**: `model_reasoning_effort` (`minimal|low|medium|high|xhigh`) is a tier-agnostic cost lever that our templates don't touch — we just omit `model =` and inherit the default, which means *no* differentiation between a 10-line autocompletion-style turn and a 200-file plan-validator review.

The competitive opening (confirmed by surveying 10 OSS harnesses) is a **declarative per-agent map with preset-aware defaults** that renders per-IDE-correctly. No harness ships this exact shape today — closest is opencode's per-agent markdown frontmatter, but they have no preset axis.

---

## 🔍 Refinement Decisions

`--deep` not used. Discovery lenses: **technical architecture / implementation** (config schemas of the three IDEs) + **user-workflow / product opportunity** (how other harnesses ship cost optimization and what the convergent role taxonomy is).

**User direction lock-in (mid-research, 2026-05-17)**: per-agent pinning + preset-aware defaults. This **upgraded Approach A** (originally 4-role taxonomy) into the new recommended shape — see updated approach below. Approach A as originally written (role aggregation) is dropped because the user explicitly chose finer granularity.

---

## 🛠️ Approaches Found

### Approach A (user-confirmed) — Per-agent model map in `harness.yaml`, preset-aware defaults, IDE-correct rendering

| Field | Content |
|-------|---------|
| Approach | Replace `recommended_model: str` with `agent_models: dict[str, AgentModelSpec]` keyed by agent slug (`autoloop-coder`, `code-reviewer`, `plan-validator`, …). Each `AgentModelSpec` carries `{claude: str?, cursor: str?, codex: str?, codex_reasoning_effort: str?}`. Presets ship a preset-tuned default map: `Production` → opus on reasoning agents + sonnet reviewers + reasoning_effort=high; `Side` → sonnet across the board + reasoning_effort=medium, with a small cheap-aux slot for statusline / commit messages. User-added agents inherit a preset default (likely `sonnet` / `medium`) until overridden. Single `default_model: str` (replaces `recommended_model`) is the floor fallback when an agent isn't listed. |
| Assumption | (a) Users want named per-agent control matching the existing per-agent template structure. (b) Preset already exists as the cost/quality axis (Side = lighter, Production = heavier), and users expect new knobs to honor preset baselines without re-declaring per agent. (c) Most users will accept preset defaults and only override 1–2 agents — interview should optimize for that. |
| Evidence | User explicitly chose this shape (2026-05-17). 10-harness survey confirms per-agent pinning is convergent (opencode `mode: subagent` + `model:` in frontmatter; Plandex per-role; OpenHands `[agent.X] llm_config`). No harness layers presets on top of per-agent pinning — that's the harness-maker differentiator and slots into our existing preset axis. Our `templates/agents/*.md.j2` already has the per-agent frontmatter shape; only the data source changes from hardcoded → `harness.yaml`-driven. |
| Trade-off | Bigger schema than role aggregation (Approach B). Interview needs to be smart: ask "accept preset defaults? (Y/n)" and only branch into per-agent picker on N. 14 agents × 3 targets = 42-cell config matrix in worst case — interview must not exhaust the user. Reverse mapper (`answers_from_harness_yaml`) needs to round-trip per-agent overrides distinctly from preset defaults so users see "what they changed" vs "what came from preset". |
| Compatibility | Preset axis already exists (CLAUDE.md §dev_mode + presets). Maps cleanly: Claude → `model:` frontmatter (knowing #43869 limits this); Cursor → concrete IDs (floor-compat with 2.4–3.2) or aliases (3.3+); Codex → omit `model =` + render `model_reasoning_effort` per agent TOML + `[profiles.cheap]`/`[profiles.deep]` in `.codex/config.toml` for invocation-time switching. Foreign-config templates (5 surfaces) keep showing `default_model` as a single doc hint. |
| Risk | medium-high — schema migration (recommended_model → default_model + agent_models map), interview UX design, and per-preset default-map authoring all need care. Mitigated by: silent fallback for absent `agent_models` block; preset defaults shipped as code in `presets.py` (not user-input), so authors keep control; round-trip test pins the override-vs-preset distinction. |

### Approach B — Add `model_reasoning_effort` per Codex agent without changing Claude/Cursor

| Field | Content |
|-------|---------|
| Approach | Leave `recommended_model` alone for Claude/Cursor. Add a Codex-only `codex_reasoning_effort` map (per-agent-role → enum) and render into `.codex/agents/*.toml`. Closes the biggest currently-untapped cost lever. |
| Assumption | Per-tier cost differentiation matters most on Codex (because `model_reasoning_effort` is officially documented and tier-agnostic) and Claude Code's broken subagent routing means changes there don't pay off until #43869 lands. |
| Evidence | Codex `config.schema.json` confirms `ReasoningEffort` enum (`none|minimal|low|medium|high|xhigh`). OpenAI platform docs say `minimal` skips the reasoning step entirely (the dominant cost driver on reasoning models). Codex pricing pages don't quantify the savings — but the structural claim is verifiable from the schema. |
| Trade-off | Doesn't fix the silent-failure status of our Claude routing. Doesn't help Cursor cost split. Solves 1/3 of the surface. |
| Compatibility | Trivial — additive, no schema churn for non-Codex users. |
| Risk | low — narrow scope. |

### Approach C — Wait for Claude Code #43869 to land, then ship full per-agent routing

| Field | Content |
|-------|---------|
| Approach | Don't change `harness.yaml` schema. Document the broken state. Re-evaluate when Anthropic ships the fix. |
| Assumption | Anthropic will fix #43869 soon and we'd be re-doing work if we ship a workaround now. |
| Evidence | No public ETA on #43869 (open since ≤ 2026-05-17). Workarounds in the field route around it (custom scripts using Anthropic SDK directly), but those are user-side, not config-side. |
| Trade-off | We stay decorative. Users keep paying Opus prices for sonnet-class reviewers because parent-session inheritance dominates. Cursor + Codex remain unaddressed even though their routing *does* work. |
| Compatibility | N/A — no change. |
| Risk | high — assumes Anthropic ships in a relevant timeframe. Also leaves 2/3 of the surface (Cursor, Codex) unaddressed indefinitely. |

### Approach D — Adopt OpenHands' named-config inheritance pattern

| Field | Content |
|-------|---------|
| Approach | Top-level `[llm.default]` + `[llm.<name>]` blocks in `harness.yaml`; each agent binds via `llm_config: "<name>"`. Maximum composability — users define their own arbitrary tiers (e.g., `[llm.security_reviewer]` distinct from `[llm.code_reviewer]`). |
| Assumption | Users want fine-grained per-agent control, not pre-baked roles. |
| Evidence | OpenHands is the only harness with this pattern; it's cleaner than role enums but no harness has copied it. Continue.dev's `models: []` array is the next-closest. |
| Trade-off | More schema, more interview questions, more renderer branches. Power users gain a lot; common users gain little (defaults already work). Violates CLAUDE.md "no premature abstraction". |
| Compatibility | Significant schema change. Reverse mapper non-trivial. |
| Risk | medium — over-engineers for the 90% case. |

---

## ⚠️ Pitfalls

- **Claude Code subagent routing is silently broken** ([#43869](https://github.com/anthropics/claude-code/issues/43869)). Per-agent `model:` frontmatter, `CLAUDE_CODE_SUBAGENT_MODEL` env var, and the Task tool's model parameter are all accepted but ignored. Our `templates/agents/*.md.j2` currently relies on this for the opus/sonnet split. **Lesson**: any frontmatter we render should be matched against an actual behavior check, not just spec compliance. (Mirrors CLAUDE.md checklist item 8 — "module import passes, real boundary fails.")
- **Cursor `fast` alias was removed**. Forum confirms `model: fast` now errors with `Error: [unavailable]`. If any template ever lands `model: fast`, every Cursor user breaks. Defense: snapshot test that no rendered agent uses removed aliases.
- **Cursor `.mdc` `model:` is not a thing** (forum FR [156812](https://forum.cursor.com/t/extend-mdc-rule-frontmatter-with-a-model-field-for-cost-efficient-agentic-workflows/156812), Cursor team says use subagents instead). Our `.mdc` rules can carry `recommended_model:` as a documentation field but Cursor won't act on it.
- **Cursor 3.3 (2026-05-07) is the floor for alias support** (`model: opus`). On 2.4–3.2 you need concrete IDs (`claude-4-7-opus`). Mixed-version teams hit silent-fallback. Choice: pin concrete IDs (works everywhere) or bump min-Cursor to 3.3 (uses aliases, easier to track latest minor). CLAUDE.md says min 2.4 today.
- **Codex ChatGPT-tier rejects `o4` / `gpt-5-codex` / `gpt-5.5-codex`** (already known from prior research, see `RESEARCH-codex-plan-validator-model-unavailable.md`). Our current omit-`model=` policy is correct and should not change. The cost-differentiation lever is `model_reasoning_effort`, not the model string.
- **No IDE's hook system can select a model for the hook callback**. Claude Code hooks, Cursor `.cursor/hooks.json`, and Codex hooks all lack a `model` field. Cheap-precheck patterns must be implemented as a `command` hook that shells out to a separate cheap invocation (e.g., `codex exec -p cheap ...`), not as native config.
- **`recommended_model` propagates to 5 foreign-config templates** (Cursor `.mdc`, Copilot, AGENTS.md, Aider, Continue) as a *documentation hint only*. Migrating it to a structured shape needs those 5 templates to keep rendering the most-useful single field (likely `execute` tier) for the human reader, while richer role data goes into the actual IDE config files.
- **Claude Code's `ANTHROPIC_SMALL_FAST_MODEL` was renamed** to `ANTHROPIC_DEFAULT_HAIKU_MODEL`. Our docs don't currently reference either, but if we add env-var-based fallback guidance to `/hm:configure`, use the new name.
- **No harness ships cost-budget-aware routing.** That's not a pitfall — it's a gap (see below) — but also tempting to over-design. Don't add a budget knob in this iteration; nobody else has it for a reason (no convergent design exists yet).

---

## ❓ Open Questions

1. **Preset default maps — concrete authoring**. Need the exact per-agent default map for **Production** and **Side**. Strawman:
   - **Production**: `autoloop-coder/plan-validator/stuck → opus`; 11 reviewers → `sonnet`; statusline/commit hooks → `haiku` if added. Codex `model_reasoning_effort`: reasoning agents `high`, reviewers `medium`, statusline `minimal`.
   - **Side**: everything → `sonnet`; statusline/commit hooks → `haiku`. Codex effort: reasoning `medium`, reviewers `low`, statusline `minimal`.
   - Decision (per-preset, per-agent, per-IDE values) locked in `/hm:plan`.
2. **Schema shape — flat or nested?** Two candidates: (a) flat `agent_models.<slug>.<target> = "<id>"` (3 keys per agent), (b) nested `agent_models.<slug> = {claude: ..., cursor: ..., codex: {model: ..., reasoning_effort: ...}}`. Codex needs the nested form for `reasoning_effort` — likely (b).
3. **Interview UX**. With 14 agents × 3 targets, full interactive override is 42 questions. Proposal: ask "accept preset defaults? (Y/n)"; on N, only ask per-agent for the agents the user names. Confirm in plan.
4. **Cursor floor: pin concrete IDs or bump to 3.3?** Concrete IDs work on 2.4–3.2 but drift annually; 3.3 aliases stay current but exclude pre-2026-05 Cursor users. CLAUDE.md says min 2.4 today.
5. **Should we render `[profiles.cheap]` / `[profiles.deep]` in `.codex/config.toml`?** Enables `codex -p cheap` invocation pattern. Useful for hooks that want cheap precheck (since Codex hooks can't pick model natively).
6. **Migration of old `recommended_model`** — silent fallback per CLAUDE.md item 6: `recommended_model: foo` → `default_model: foo` + empty `agent_models` map + warn that preset-defaults will be used until explicitly overridden. Confirm.
7. **5 LLM-judgment skills (per ADR-005)** — should they also pin per-skill models (same shape as agents), or piggyback on the host agent's model? They currently inherit harness-wide.
8. **`/hm:health` Layer 1 gate addition** — `model_routing_actionable` sub-check that flags: (a) Claude Code subagent routing relied on without disclaimer (#43869), (b) Cursor `model:` aliases on < 3.3, (c) Codex agents with neither `model_reasoning_effort` nor profile binding. Surface as silent-miss item.
9. **Foreign-config docs** (Cursor `.mdc`, Copilot, AGENTS.md, Aider, Continue) — keep showing `default_model` as a single doc field (per-agent map is too verbose for a human-readable hint)?

---

## 📚 Sources

### Claude Code
- [Model configuration](https://code.claude.com/docs/en/model-config) — aliases, env vars, precedence
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — frontmatter `model:` (documented)
- [Speed up responses with fast mode](https://code.claude.com/docs/en/fast-mode) — `/fast` is Opus on speed config
- [Changelog](https://code.claude.com/docs/en/changelog)
- [GitHub #43869 — subagent routing broken](https://github.com/anthropics/claude-code/issues/43869) — the silent-failure root cause

### Cursor
- [Subagents](https://cursor.com/docs/context/subagents) — `model: inherit` default, accepted values
- [Hooks](https://cursor.com/docs/hooks) — no model field
- [Models and pricing](https://cursor.com/docs/models-and-pricing) — Auto is unlimited on Pro
- [Changelog 3.3](https://cursor.com/changelog) — general alias support (2026-05-07)
- [Forum: `.mdc` model field FR](https://forum.cursor.com/t/extend-mdc-rule-frontmatter-with-a-model-field-for-cost-efficient-agentic-workflows/156812)
- [Forum: `fast` alias removed](https://forum.cursor.com/t/subagent-fast-model-doesnt-work/149755)
- [Forum: subagent routing bug in MAX mode](https://forum.cursor.com/t/subagent-task-tool-ignores-model-specific-subagent-type-routing-all-subagents-inherit-parent-model-instead-of-using-their-designated-models-opus-codex/151917)

### Codex CLI
- [Configuration Reference](https://developers.openai.com/codex/config-reference) — `model_reasoning_effort` enum
- [Advanced Configuration](https://developers.openai.com/codex/config-advanced) — profiles + `--profile/-p`
- [Subagents](https://developers.openai.com/codex/subagents) — per-agent TOML schema honors `model` + `model_reasoning_effort`
- [Models](https://developers.openai.com/codex/models) — official model list
- [config.schema.json](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json) — `ReasoningEffort` enum, `HookHandlerConfig` (no model field)

### OSS harness landscape
- [aider — options](https://aider.chat/docs/config/options.html), [aider — chat modes](https://aider.chat/docs/usage/modes.html) — `--weak-model` + main/editor split
- [Plandex — model roles](https://docs.plandex.ai/models/roles/), [Plandex — built-in packs](https://docs.plandex.ai/models/built-in/built-in-packs/) — 11-role schema, the deepest in the field
- [Continue.dev — model roles](https://docs.continue.dev/customize/model-roles) — 7-role `roles: []` array
- [Cline — Plan & Act](https://docs.cline.bot/features/plan-and-act) — 2-mode toggle
- [Roo Code — custom modes](https://roocodeinc.github.io/Roo-Code/features/custom-modes) — sticky-model memory per mode
- [opencode — config](https://opencode.ai/docs/config/), [opencode — agents](https://opencode.ai/docs/agents/) — `small_model` slot
- [Sourcegraph Amp — manual](https://ampcode.com/manual) — opaque server-side routing across 3 modes
- [Goose — lead/worker RFC #4036](https://github.com/block/goose/issues/4036), [Goose — recipes](https://block.github.io/goose/docs/guides/recipes/) — temporal routing (lead-for-first-N-turns)
- [OpenHands — custom LLM configs](https://docs.openhands.dev/openhands/usage/llms/custom-llm-configs) — named-config inheritance (cleanest schema)
- [Kilocode — auto model](https://kilo.ai/docs/code-with-ai/agents/auto-model) — server-side adaptive via gateway header

---

## 🔗 Related Internal Docs

- [[RESEARCH-codex-plan-validator-model-unavailable]] — prior decision to omit `model =` from Codex agent TOMLs (still valid)
- [[project_cursor_model_policy]] — memory: keep prompts model-agnostic, recommend `claude-opus-4-7`
- [[project_targets_axis]] — codex / cursor / claude-code multi-target axis
- `src/harness_maker/models.py:440` — `HarnessConfig.recommended_model = "claude-opus-4-7"` (current single-field state)
- `src/harness_maker/templates/agents/*.md.j2` — 14 agent templates with hardcoded `model: opus | sonnet`
- `src/harness_maker/templates/foreign-configs/*.j2` — 5 surfaces propagating `recommended_model`
