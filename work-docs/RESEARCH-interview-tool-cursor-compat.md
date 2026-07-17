---
type: research
task_slug: interview-tool-cursor-compat
status: complete
created: 2026-05-12
tags: [harness-maker, research, cursor, codex, interview, AskQuestion, tool-compat]
mtime_warn_days: 14
libs_fetched: []
sources: []
related_docs: ["[[PLAN-install-without-claude-code]]", "[[wiki:pattern:codex-is-codex-flag]]"]
summary: "Template binary is_codex flag has no Cursor branch — AskUserQuestion not recognized by Cursor model"
---

## 🎯 Recommended Direction

**Add an `is_cursor` rendering branch** to stage/command templates that emits `AskQuestion` tool instructions with Cursor's native schema (`{questions: [{id, prompt, options: [{id, label}], allow_multiple}]}`), rather than the current fallback of either Claude Code's `AskUserQuestion` (unrecognized) or Codex's "Ask in your response" (no structured UI).

This is a rendering-layer fix — no Python runtime change needed. The model already has `AskQuestion` available when running in Cursor, but the prompt never tells it to use that tool.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation (primary) + User-workflow / product opportunity (secondary).

## 🛠️ Approaches Found

### Approach A: Add `is_cursor` flag — tri-state template branching

| Field | Content |
|-------|---------|
| Approach | New `is_cursor: bool` Jinja2 context variable, templates branch `{% if is_cursor %}...{% elif is_codex %}...{% else %}...{% endif %}` |
| Assumption | Cursor's `AskQuestion` tool is stable and available in Agent Mode (system prompt confirms it) |
| Evidence | This conversation's system prompt shows `AskQuestion` with schema `{questions: [{id, prompt, options: [{id, label}], allow_multiple}]}`. Cursor 2.4+ confirmed. |
| Trade-off | Template complexity increases (3 branches instead of 2). Every future template edit must maintain the new branch. |
| Compatibility | `.claude/commands/hm/*.md` (Cursor reads natively). Render-time detection: `targets` in harness.yaml already known. |
| Risk | low — additive change, no existing behavior altered |

**How it renders:**
- `is_codex=True` → "Ask in your response" (unchanged)
- `is_cursor=True` → "Use the `AskQuestion` tool with structured options: `{questions: [{id: ..., prompt: ..., options: [{id: ..., label: ...}]}]}`"
- Both false (Claude Code) → "Use `AskUserQuestion`" (unchanged)

**Where `is_cursor` gets set:**
- `.claude/commands/hm/*.md` are rendered once (not per-target) with `is_codex=False`. Need to either:
  - (a) Render two variants per command (one for CC, one for Cursor) — breaks single-source
  - (b) Use a **runtime-agnostic prompt** that works for both CC and Cursor (preferred)

### Approach B: IDE-agnostic "structured question" prompt pattern (RECOMMENDED)

| Field | Content |
|-------|---------|
| Approach | Replace `AskUserQuestion` literal in templates with a generic instruction like "Present structured multiple-choice" + schema hint that both CC and Cursor models can map to their available tool |
| Assumption | Claude (in both CC and Cursor) can infer the right tool from intent if prompted correctly |
| Evidence | `[wiki:pattern] codex-is-codex-flag` already handles Codex by stripping the tool name entirely. Same principle can unify CC/Cursor. The model in Cursor DOES have `AskQuestion` available — it just isn't being told to use it. |
| Trade-off | Slightly less deterministic than explicit tool names. May require a schema example in the template for Cursor to reliably produce the right shape. |
| Compatibility | Perfect single-source compatibility — `.claude/commands/hm/*.md` remains one file for both IDEs |
| Risk | medium — models might still just ask in plain text if prompt isn't explicit enough |

**Concrete pattern:**
```jinja2
{% if is_codex %}
Ask in your response (structured multiple-choice):
{% else %}
Use the structured question tool to present these as clickable options to the user:
{% endif %}
```

The model in both CC and Cursor sees "use the structured question tool" and maps to its available tool (`AskUserQuestion` in CC, `AskQuestion` in Cursor). Risk: the vague name might not trigger tool use reliably.

### Approach C: Explicit tool name per-IDE with `is_cursor` flag on render path

| Field | Content |
|-------|---------|
| Approach | Split the template conditional to three cases. For Cursor path, explicitly name `AskQuestion` tool and include schema. |
| Assumption | `.claude/commands/hm/*.md` can carry Cursor-specific instructions without confusing Claude Code |
| Evidence | Since Cursor reads `.claude/commands/hm/*.md` natively (single-source), the same file must work for both. But Claude Code doesn't have `AskQuestion` and Cursor doesn't have `AskUserQuestion`. |
| Trade-off | **Breaks single-source for commands.** Would need either dual-render or runtime detection inside the prompt. |
| Compatibility | Conflicts with single-source principle. Would require `.cursor/commands/` after all, or a preamble that says "if you have AskQuestion, use it; otherwise use AskUserQuestion" |
| Risk | high — architectural regression, contradicts kairos 0.5.7 forensic finding |

## ⚠️ Pitfalls

1. **Tool name mismatch is silent.** When the prompt says "use `AskUserQuestion`" but the model only has `AskQuestion` available, the model doesn't error — it just falls back to asking questions in plain text. This makes the bug invisible unless you specifically look for the structured UI.

2. **Single-source `.claude/commands/` constraint.** The entire Cursor target architecture is built on "Cursor reads `.claude/commands/hm/*.md` natively" (kairos forensic). Any fix that requires per-IDE command files would be a major architectural regression.

3. **Codex already solved this differently.** The `is_codex` flag was added because Codex has NO structured question tool at all. But Cursor DOES have one — it's just named differently. The fix should leverage Cursor's tool, not downgrade to Codex's "ask in response" pattern.

4. **Schema difference matters.** Even if the model recognizes it should use a tool, Claude Code's `AskUserQuestion` and Cursor's `AskQuestion` have different schemas:
   - CC `AskUserQuestion`: single question, flat options list
   - Cursor `AskQuestion`: `{questions: [{id, prompt, options: [{id, label}], allow_multiple}]}` — array of questions, each option needs `{id, label}`

5. **`.agents/skills/hm-*/SKILL.md` always uses `is_codex=True`.** These Codex-targeted skills say "Ask in your response" — which is fine for Codex but suboptimal for Cursor. Cursor users who trigger skills instead of slash commands will always get plain text questions regardless of fix.

## ❓ Open Questions

1. **Which path does Cursor actually invoke?** When user types `/hm:plan` in Cursor, does Cursor load `.claude/commands/hm/plan.md` (slash command) or `.agents/skills/hm-plan/SKILL.md` (skill)? The answer determines whether the fix needs to cover commands only, skills only, or both.

2. **Can a single prompt work for both CC and Cursor?** A prompt like "Present as structured multiple-choice using the available question tool" — would both models reliably map this to their respective tools? Or is explicit tool naming required?

3. **What about `/harness-maker:make`?** The plugin-level `commands/make.md` uses `AskUserQuestion` without any `is_codex` conditional. This is the initial setup interview. Does it work in Cursor at all?

4. **Is a per-target render acceptable for commands?** Currently commands are rendered once. If we need `is_cursor` in the template, we need to know the target at render time for `.claude/commands/`. Could use a hybrid approach: embed both tool names with a runtime selector comment.

## 📚 Sources

- `src/harness_maker/templates/stages/plan.md.j2` lines 102, 116, 151, 157, 260 — `is_codex` conditionals
- `src/harness_maker/templates/stages/spec.md.j2` line 78, 133, 155 — same pattern
- `src/harness_maker/templates/stages/research.md.j2` line 94, 143 — same pattern
- `src/harness_maker/templates/commands/hm/loop.md.j2` — 10+ instances
- `src/harness_maker/synthesize.py` — `is_codex` set to False for non-Codex renders
- `tests/unit/test_codex_stage_procedures.py` — guards that Codex renders have no `AskUserQuestion`
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — A4.plan-mode-askquestion (TBD, never verified)
- `[wiki:pattern] codex-is-codex-flag` — documents the existing adaptation strategy
- System prompt of this Cursor session — confirms `AskQuestion` tool availability and schema

## 🔗 Related Internal Docs

- `[[PLAN-install-without-claude-code]]` — IDE-agnostic bootstrap, adjacent concern
- `[[wiki:pattern:codex-is-codex-flag]]` — existing tool adaptation pattern for Codex
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — A4 test case for Q&A loop (never executed)
- `tests/cursor-compat/RESULTS.md` — all TBD, no manual verification done yet
