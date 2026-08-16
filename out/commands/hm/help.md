---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/help.en.md.j2
provenance: official
description: 'List the /hm: commands and what each one is for.'
content_hash: c5eb314dedca095cbed27aa34bcfadd2af0a1729c62308ee1c78252231001133
---
# /hm:help — harness-maker (en)

> One-screen overview of every `/hm:*` command you can run, the recommended
> workflow path, and your current harness settings. For per-command details,
> open `.claude/commands/hm/<name>.md`.

## 📋 Available commands

### Atomic stages (7)

| Command | Purpose |
|---|---|
| `/hm:research` | Gather context, prior art, library docs |
| `/hm:spec`     | Lock acceptance criteria (intent / outcomes / scenarios) |
| `/hm:plan`     | Deep interview → ADRs → phase decomposition |
| `/hm:execute`  | TDD machine — RED → GREEN per PLAN phase |
| `/hm:review`   | Multi-reviewer consensus + grade gate + auto-fix |
| `/hm:wrapup`   | Single commit, CHANGELOG, doc updates |
| `/hm:verify`   | Independent pre-wrapup invariant checks |

### Meta

| Command | Purpose |
|---|---|
| `/hm:make`      | Full re-render (interactive) |
| `/hm:configure` | Targeted setting change (no full re-interview) |
| `/hm:health`    | 3-layer audit (structural / external / personalization) |
| `/hm:loop`      | Bounded autoloop with safety rails |
| `/hm:uninstall` | Remove the harness |
| `/hm:help`      | (this command) |
| `/hm:metrics`   | Delivery metrics — CFR + churn trend, LLM interpretation (manual, read-only) |
## 🔁 Recommended workflow

```
  research ─► spec ─► plan ─► execute ─► review ─► verify ─► wrapup
```

Stages are chained by `/hm:loop` or by autopilot — there is no fused workflow command. <!-- @hm:axis-removed -->

## ⚙️ Your current settings

| Key | Value |
|---|---|
| preset | `Side` |
| locale | `en` |
| targets | `claude-code, codex` |
| autopilot | `ask`, re-armed every session |

> **Codex CLI:** invoke as `@hm-*` (e.g. `@hm-help`, `@hm-execute`). Skills live under `.agents/skills/`.


## 💡 Next steps

- New to this harness?  →  run `/hm:research`, then follow the stage order above
- Change a setting?     →  run `/hm:configure`
- Audit harness health? →  run `/hm:health`
