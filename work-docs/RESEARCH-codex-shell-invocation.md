---
type: research
task_slug: codex-shell-invocation
status: complete
created: 2026-05-17
tags: [harness-maker, research, codex, cli, shell, headless, non-interactive]
mtime_warn_days: 30
libs_fetched: []
sources:
  - https://developers.openai.com/codex/noninteractive
  - https://developers.openai.com/codex/cli/reference
  - https://deepwiki.com/openai/codex/4.2-headless-execution-mode-(codex-exec)
  - https://github.com/openai/codex/issues/1340
  - https://github.com/openai/codex/issues/1080
  - https://github.com/openai/codex/discussions/1174
  - https://github.com/openai/codex/blob/main/docs/exec.md
related_docs:
  - "[[RESEARCH-codex-usage-guide]]"
  - "[[PLAN-codex-target-support]]"
summary: "Yes — codex exec 'prompt' is the claude -p equivalent; -p is --profile (wrong flag)"
---

# 🎯 Recommended Direction

**`codex exec "prompt"`** is the correct `claude -p` equivalent as of May 2026.
It runs non-interactively, streams progress to stderr, and prints the final agent
response to stdout. The flag `-p` is **NOT** a prompt flag — it is `--profile`
(config profile selection). Passing a prompt via `-p` silently loads a nonexistent
profile name instead of running the prompt.

For harness-maker's shell dispatch use case (invoking Codex from Claude Code's
Bash tool or from a shell hook):

```bash
codex exec --sandbox workspace-write --ask-for-approval never "{{ prompt }}"
```

Or the short form (no guardrails — only for trusted automated contexts):

```bash
codex exec --yolo "{{ prompt }}"
```

---

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** — the question is purely
about CLI interface, not user workflow patterns.

---

## 🛠️ Approaches Found

### Approach 1 — `codex exec` (the correct answer)

| Field | Content |
|-------|---------|
| Approach | `codex exec "prompt"` subcommand |
| Assumption | Codex CLI ≥ any 2025 version is installed |
| Evidence | Official OpenAI docs, DeepWiki source analysis, confirmed flags below |
| Trade-off | Must set approval/sandbox flags explicitly for automation; stdout is only the final message |
| Compatibility | Pipe-safe: stdout = final message, stderr = progress. `--json` for JSONL stream. |
| Risk | low |

**Key flags for `codex exec`:**

| Flag | Short | Notes |
|------|-------|-------|
| `PROMPT` (positional) | — | `codex exec "do X"` or `-` to read from stdin |
| `--sandbox` | `-s` | `read-only` (default) \| `workspace-write` \| `danger-full-access` |
| `--ask-for-approval` | `-a` | `untrusted` \| `on-request` \| `never` |
| `--yolo` | — | Alias for `--sandbox workspace-write --ask-for-approval never` |
| `--json` | — | JSONL event stream to stdout (machine-readable) |
| `--output-last-message` | `-o <path>` | Write final message to file |
| `--output-schema <path>` | — | Enforce JSON Schema on response |
| `--ephemeral` | — | No session persistence |
| `--model` | `-m` | Override model |
| `--profile` | **`-p`** | Load config profile (⚠️ NOT a prompt flag) |
| `--skip-git-repo-check` | — | For non-repo directories |
| `--last` | — | Resume most recent session |

### Approach 2 — `codex --quiet` (broken, avoid)

| Field | Content |
|-------|---------|
| Approach | `codex --quiet "prompt"` on the interactive TUI command |
| Assumption | `--quiet` suppresses TUI and behaves like exec mode |
| Evidence | GitHub Issue #1340 (filed ~May 2025, closed without resolution): quiet mode still prompts `y/n` outside git repos. Issue #1080: `codex` crashes in CI/non-tty environments even with `CODEX_QUIET_MODE=1` and `--quiet`. |
| Trade-off | Inconsistent — works in some terminals, hangs in CI, crashes in GitHub Actions |
| Compatibility | ❌ Not suitable for shell scripting or harness dispatch |
| Risk | high |

### Approach 3 — stdin pipe (works with `-` argument)

| Field | Content |
|-------|---------|
| Approach | `echo "prompt" \| codex exec -` |
| Assumption | Need to pass prompt from a variable or heredoc |
| Evidence | `codex exec` accepts `-` as positional argument to read stdin (per docs + source analysis) |
| Trade-off | Works cleanly for multi-line prompts; no different behavior from positional form |
| Compatibility | Fully compatible; useful when the prompt is constructed programmatically |
| Risk | low |

---

## ⚠️ Pitfalls

1. **`-p` is `--profile`, NOT `--prompt`.** This is the single most common mistake.
   `codex -p "fix the bug"` loads a config profile named `"fix the bug"` (no-op or error),
   not a prompt. There is **no `-p` / `--prompt` flag** on `codex` or `codex exec`.
   Source: CLI reference (developers.openai.com/codex/cli/reference).

2. **Approval requests block silently.** Default `--ask-for-approval on-request` causes
   `codex exec` to pause and wait for terminal input in automated contexts. Always pass
   `--ask-for-approval never` or `--yolo` for non-interactive use.
   Source: DeepWiki source analysis, GitHub Issue #1340.

3. **`codex` (interactive) vs `codex exec` are different entrypoints.** The interactive
   TUI (`codex`) does NOT support headless invocation reliably. Only `codex exec` is the
   correct headless entrypoint. Do not route through the TUI with flags like `--quiet`.
   Source: Issue #1080 (TUI Ink crashes in non-tty), Issue #1340 (quiet mode hang).

4. **Git repo check.** `codex exec` defaults to requiring a git repo. If invoking from a
   harness hook or non-repo directory, add `--skip-git-repo-check`.
   Source: CLI reference.

5. **Rust rewrite in progress.** The current CLI is TypeScript/Node. A Rust rewrite is
   announced (Discussion #1174 "Codex CLI is Going Native"). Flag signatures may change
   on the stable Rust release — validate when migrating.
   Source: GitHub Discussion #1174.

6. **`--full-auto` is deprecated.** Legacy flag still works as alias but prints warnings.
   Replace with `--sandbox workspace-write --ask-for-approval never` or `--yolo`.

7. **Auth in automation.** Use `CODEX_API_KEY=<key>` env var. The interactive mode
   does not support this env var; `codex exec` does.

---

## ❓ Open Questions

1. Does harness-maker need to generate `codex exec` dispatch in any template or hook?
   (If yes, the correct template is `codex exec --sandbox workspace-write --ask-for-approval never "{{ prompt }}"`)
2. When the Rust CLI lands, will `codex exec` flags change? The `--yolo` shorthand
   and positional prompt form are likely stable, but `--json` JSONL format may evolve.
3. Is there a `codex exec --output-schema` use case for structured harness responses
   (e.g., review grade JSON)?

---

## 📚 Sources

- Non-interactive mode (official docs): https://developers.openai.com/codex/noninteractive
- CLI reference (flags): https://developers.openai.com/codex/cli/reference
- DeepWiki headless exec analysis: https://deepwiki.com/openai/codex/4.2-headless-execution-mode-(codex-exec)
- GitHub Issue #1340 (quiet mode bug): https://github.com/openai/codex/issues/1340
- GitHub Issue #1080 (CI TUI crash): https://github.com/openai/codex/issues/1080
- GitHub Discussion #1174 (Rust rewrite): https://github.com/openai/codex/discussions/1174
- docs/exec.md: https://github.com/openai/codex/blob/main/docs/exec.md

---

## 🔗 Related Internal Docs

- `[[RESEARCH-codex-usage-guide]]`: General Codex CLI usage patterns, AGENTS.md, skills, MCP.
- `[[PLAN-codex-target-support]]`: ADR for Codex target assets in harness-maker.
