---
type: research
task_slug: stale-install-recovery
created: 2026-11-19
summary: A settings.json hook edit made by a SessionStart hook takes effect later in the same Claude Code session (2.1.328, headless).
---

# RESEARCH — Does a SessionStart edit to settings.json apply in the same session?

## Question

SPEC-stale-install-recovery AC-011: the self-heal rewrites `.claude/settings.json` from the
plugin's SessionStart hook. Does the running session pick up the rewritten hook commands, or
only the next session?

## Experiment (2026-11-19, Claude Code 2.1.328)

A scratch git repo with this `.claude/settings.json`:

- `SessionStart` → `uv run --no-project python swap.py`, which replaces `MARK_OLD` with
  `MARK_NEW` in `.claude/settings.json` and appends `sessionstart-ran` to `log.txt`.
- `PreToolUse` (matcher `Bash`) → `echo MARK_OLD >> log.txt`.

Run: `claude -p "Run the bash command: echo hello" --allowedTools "Bash(echo hello)"`.

Observed `log.txt`:

```
sessionstart-ran
MARK_NEW
```

The PreToolUse hook that ran was the **rewritten** one. The SessionStart edit took effect for a
tool call in the same session.

## Conclusion and limits

- Same-session effect: **yes**, on Claude Code 2.1.328 in headless (`-p`) mode. The heal message
  says no restart is needed and to restart only if a hook still fails.
- Not measured: interactive mode, or other Claude Code versions. If a later version snapshots
  hooks at startup, the heal still repairs the file and the next session runs the repaired hooks;
  the "restart only if a hook still fails" wording covers that case.
- Codex: not applicable. The heal does not run in Codex (no plugin-level hook).
