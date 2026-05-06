---
name: phase1-test-agent
description: Phase 1 cross-compat fixture. Outputs a single PASS line when invoked. Use proactively when the user mentions "phase 1 agent test".
model: claude-opus-4-7
is_background: false
readonly: true
---

# Phase 1 Cross-Compat Test Agent

Verifies that harness-maker's single-source `.claude/agents/` location works in Cursor IDE (which natively reads this directory) as well as Claude Code.

## Mission

When invoked, output exactly this single line and stop:

```
PHASE-1 A1 PASSED — agent dispatched from .claude/agents/ in <IDE-name>
```

Replace `<IDE-name>` with the current runtime (`Claude Code` or `Cursor`).

No analysis. No tool calls. No additional output.

## Frontmatter cross-compat checkpoints

- `name`, `description`, `model` — common to both IDEs
- `is_background: false`, `readonly: true` — Cursor-specific keys

If both IDEs load this frontmatter without strict-rejection, the single-source assumption passes its first gate. (Production reviewer agents include `tools: Read, Grep, Glob` — this fixture omits `tools` deliberately because the agent does not call any tool.)
