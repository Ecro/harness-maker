---
name: phase1-test-skill
description: Phase 1 cross-compat fixture. Outputs a single PASS line when invoked. Tests Anthropic SKILL.md standard frontmatter compatibility across IDEs.
when_to_use: When the user says "phase 1 skill test" or "test the phase 1 skill"
user-invocable: true
---

# Phase 1 Cross-Compat Test Skill

Verifies that harness-maker's `.claude/skills/<name>/SKILL.md` is recognized by both Claude Code and Cursor 2.4+ (which adopted the Anthropic SKILL.md standard).

## Mission

When this skill is invoked, output exactly this single line and stop:

```
PHASE-1 A3 PASSED — skill loaded from .claude/skills/test-skill/ in <IDE-name>
```

Replace `<IDE-name>` with the current IDE.

No additional work. No tool calls.

## Frontmatter cross-compat checkpoints

- `name` (required) — kebab-case identifier
- `description` (required) — one-sentence summary used for auto-dispatch
- `when_to_use` — Anthropic standard trigger condition
- `user-invocable: true` — Anthropic standard, exposes the skill as a slash command

If both IDEs accept all four keys without strict-rejection AND auto-discovery fires on the trigger phrase, A3 passes.
