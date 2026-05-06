# /hm:test-research

harness-maker Phase 1 fixture for verifying that **slash commands and Q&A loops work in both IDEs**.

## Mission

Follow this procedure exactly.

### Step 1 — Ask the user

Ask the user the following question:

> "Phase 1 A4 verification — Which IDE / mode is running this command?
>
> 1. Claude Code
> 2. Cursor (Plan Mode, entered via Shift+Tab)
> 3. Cursor (Agent Mode, default)
> 4. Other (free-text)"

Question-tool selection:
- **Claude Code** — use `AskUserQuestion` (structured 4-option select)
- **Cursor Plan Mode** — Cursor's native AskQuestion tool fires automatically
- **Cursor Agent Mode** — fall back to natural-language chat (PASS if it works equivalently)

### Step 2 — Output a single line

Once the answer is in, output exactly:

```
PHASE-1 A4 PASSED — slash command + Q&A loop works in <user answer>
```

### Step 3 — Stop

No additional work. No analysis. No further tool calls.

## Verification points

- **Command discovery**: when the user types `/hm:test-research`, the IDE shows it in the slash-command dropdown
- **Q&A loop**: an interview-style question receives a user response and the command flow continues
- **Natural-language fallback**: if structured Q&A tools are unavailable, plain chat works equivalently

## Note

This fixture lives at `.claude/commands/hm/`. If Cursor does not recognize this location (i.e. command does not appear in the dropdown), a separate render to `.cursor/commands/` will be required (Phase 2 design decision).
