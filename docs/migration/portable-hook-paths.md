# Migration — portable hook / command paths (`$HOME`)

**Applies to:** any repo where `.claude/settings.json` (and/or `.cursor/hooks.json`,
`.codex/hooks.json`, `.claude/commands/`) is **committed and shared by a team**.
**Fixed in:** 0.42.0.

## Symptom

`.claude/settings.json` keeps showing up as locally modified after every rebase / re-render,
and the diff is only a home-directory path swap:

```diff
-  "command": "uv run --with '/home/dongjin/.claude/plugins/cache/harness-maker/harness-maker/0.41.1' python -m harness_maker.telemetry"
+  "command": "uv run --with '/home/noel/.claude/plugins/cache/harness-maker/harness-maker/0.41.1' python -m harness_maker.telemetry"
```

Committing it just moves the breakage to the next teammate — an **infinite flip-flop**.

## Root cause

Before 0.42.0 the renderer baked an **absolute, home-prefixed** plugin-cache path into every
hook command and every slash-command / skill body (`_compute_install_ref` returned the
`file://` path from the plugin's `direct_url.json`). The only machine-varying segment is the
home-dir prefix (`/home/<user>`), so a committed `settings.json` is rewritten to each dev's
home on re-render. Started at the commit that first committed the rendered `settings.json`.

## The fix (0.42.0)

`_compute_install_ref` now substitutes the render-machine home prefix with the literal
`$HOME` (`synthesize._portablize_ref`), and the hook-JSON `--with` argument is double-quoted
so the IDE's shell expands `$HOME` at hook-execution time:

```
uv run --with "$HOME/.claude/plugins/cache/harness-maker/harness-maker/0.42.0" python -m harness_maker.telemetry
```

The path keeps pointing at the **local** plugin cache (no network, exact installed version) but
is now machine-portable: every teammate's `$HOME` resolves to their own home, and the cache
sub-path is identical for the same installed plugin version. Applies to all three IDE hook
surfaces (`.claude/settings.json`, `.cursor/hooks.json`, `.codex/hooks.json`) and to
command / skill bodies.

## How to migrate a team repo (recommended: keep it committed)

The hook identity is path-agnostic, so **a plain re-render replaces the old absolute path with
the portable form** — no manual JSON editing:

1. `/plugin update` (Claude Code) — or update the Cursor / Codex marketplace plugin — to 0.42.0+.
2. Re-render the harness: `/harness-maker:make --update` (or your usual make flow).
3. Confirm the diff now shows the portable form:
   ```bash
   git diff .claude/settings.json   # every hook --with is now "$HOME/..."
   ```
4. Commit **once**. That commit is portable — it will not flip-flop again.
5. Teammates: `git pull`, `/plugin update`, done. Hooks work immediately on a fresh clone (no
   re-render needed), because `$HOME` resolves per-machine at run time.

### Requirements / scope

- Every teammate must have the plugin installed at the **standard cache path**
  (`$HOME/.claude/plugins/cache/...`) — true for marketplace installs. A non-home / system-wide
  install (`/opt/...`) is left absolute (still works locally, legitimately non-portable).
- **POSIX shells only** (Linux / WSL / macOS). `$HOME` expansion in a Windows `cmd` /
  PowerShell hook runner is **out of scope** for this fix — do not rely on portability there yet.

## Alternative: don't commit `settings.json` at all

If your team prefers per-machine config instead of a shared committed file, add it to the repo's
`.gitignore` yourself:

```gitignore
.claude/settings.json
```

Trade-off: you lose the shared `permissions` / `preset` / `hooks`, and each teammate must
`/harness-maker:make` once after cloning to render their own local `settings.json`. harness-maker
does **not** gitignore it for you (the committed-and-portable model is the default).

## Known harmless side effect

If your repo still has a stale, never-read `.claude/hooks/hooks.json` from an older harness, the
0.42.0 re-render may print a one-line `WARN: kept .claude/hooks/hooks.json ...` (its pristine
bytes changed with the path form, so the auto-retire byte-match no longer fires). It is dead
weight Claude Code never reads; delete it manually if you like:

```bash
rm .claude/hooks/hooks.json
```
