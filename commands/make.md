# /harness-maker:make

Refresh, reconfigure, or extend the project's harness at `<cwd>/.claude/`.
Asks the user what they want to do before invoking the CLI.

## Procedure

You (Claude) act as the orchestrator. Follow these steps:

### 0. CI / test mode detection

If the prompt text contains `--ci`, extract inline params and skip all
`AskUserQuestion` calls. Parse `preset=`, `locale=`, `dev_mode=`,
`targets=` from the prompt; use defaults `Side` / `en` / `task` /
`claude-code` for any that are absent. Skip sections 2 and 3 entirely
and jump directly to section 4 (Dispatch → Fresh install or Update,
depending on whether `.claude/harness.yaml` exists).

Example invocation:
```
/harness-maker:make --ci preset=Side locale=en dev_mode=task targets=claude-code,cursor
```

### 0.5. `--reinterview` shortcut

If the prompt text contains `--reinterview` (and is not `--ci`), the user
wants a full interactive reconfigure. **Do not pass `--reinterview` through
to the CLI** — the CLI's interactive interview reads from stdin, which
falls back to autoloop defaults in the slash-command context (no TTY).
Instead, skip the menu in section 2 and jump straight to the **Full
reconfigure** branch in section 4, which drives `AskUserQuestion` here in
the slash command and dispatches with collected `--preset / --locale /
--dev-mode / --targets` flags.

### 1. Detect state

Resolve the plugin install path and check whether the project already has
a harness:

```bash
!plugin_dir=$(python3 -c "
import json, os, pathlib
data = json.load(open(pathlib.Path.home() / '.claude/plugins/installed_plugins.json'))
entries = data['plugins']['harness-maker@harness-maker-local']
cwd = os.getcwd()
match = next((e for e in entries if e.get('projectPath') == cwd), entries[0])
print(match['installPath'])
")
echo "PLUGIN_DIR=$plugin_dir"
[ -f "$(pwd)/.claude/harness.yaml" ] && echo "STATE=re-render" || echo "STATE=fresh-install"
```

### 2. If `STATE=re-render` — show current settings + ask intent

Read `.claude/harness.yaml` body (skip frontmatter) and surface to the user:
- preset, locale, dev_mode, default_workflow
- harness_maker_version (so they see how stale)
- count of enabled reviewers/skills

Then use `AskUserQuestion` with these options. **Order matters** — list
"Switch IDE targets" prominently right after Update, since it's the
most common reason existing 0.4.x/0.5.0 users return to this command:

- **Update** — re-render with the same settings; pick up new template
  improvements. (recommended after a `/plugin update`. Does **not** ask
  about Cursor — pick "Switch IDE targets" if you want to opt into Cursor
  on a previously claude-code-only install.)
- **Switch IDE targets** — pick `claude-code`, `cursor`, or both.
  Adding `cursor` renders `.cursor/rules/harness.mdc` + `.cursor/mcp.json`
  alongside the shared `.claude/` assets so the harness drives Cursor
  IDE 2.4+ natively. Removing leaves prior `.cursor/` files in place
  (delete manually if undesired).
- **Switch preset** — Side ↔ Production. Re-derives all preset-coupled
  defaults (security gates, worktree scope, default reviewer set).
- **Switch locale** — change the `locale` tag (en/ko/ja/...).
- **Switch dev_mode** — spec-driven ↔ task-driven.
- **Add a component** — install one extra reviewer / skill / domain pack.
- **Remove a component** — uninstall one reviewer / skill.
- **Full reconfigure** — drive a fresh interview here in the slash command
  (preset → locale → dev_mode → targets) and dispatch with all flags. No
  TTY required — works in slash-command context. (`--reinterview` typed
  directly in the prompt also routes here; see section 0.5.)
- **Audit only** — report status, do not change anything.

### 3. If `STATE=fresh-install` — ask first-time questions

Use `AskUserQuestion` to gather (in this order):
- preset (Side / Production)
- locale (en / ko / free-text)
- dev_mode (task-driven / spec-driven; Side default = task, Production = spec)
- targets (claude-code / cursor / claude-code,cursor — multi-select)

Then dispatch with `--preset / --locale / --dev-mode / --targets --autoloop`
so the CLI skips its own interview but uses the answers you collected.

### 4. Dispatch — pick the right CLI invocation

Branch on the chosen intent. Use `$plugin_dir` from step 1.

#### Update (re-render same settings)

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)"
```

CLI prints `reusing settings from .claude/harness.yaml` and applies new
templates while preserving user `@hm:user:*` blocks via reconcile.

#### Switch preset

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --preset Production
```

(or `--preset Side` for the reverse). Other dimensions stay as before.

#### Switch locale

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --locale ko
```

#### Switch dev_mode

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --dev-mode spec-driven
```

#### Switch IDE targets

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --targets claude-code,cursor
```

(or `--targets cursor` for Cursor-only, `--targets claude-code` to drop
back to Claude-Code-only.) Adding `cursor` renders `.cursor/rules/harness.mdc`
+ `.cursor/mcp.json`. Dropping `cursor` does **not** delete previously
rendered `.cursor/` files — remove them manually if you want a clean slate.

#### Add / remove a component

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --add reviewer:security
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --remove skill:research-crawler
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --add-domain tauri
```

Available reviewers: `code`, `security`, `performance`, `concurrency`, `ux`,
`security-auditor`, `consensus-arbiter`, `executor`, `autoloop-coder`.
Available skills: see `.claude/harness.yaml` `skills.installed`. Domain
packs ship: `python` (others get a user-side stub).

#### Full reconfigure

Drive the interview here in the slash command via `AskUserQuestion` —
**do not** pass `--reinterview` to the CLI (its stdin-based interview
falls back to autoloop defaults in slash context). Ask each dimension
in turn, then dispatch with all collected flags:

1. `AskUserQuestion`: **preset** — `Side` (1 reviewer, lean) or
   `Production` (5 reviewers, verify-required).
2. `AskUserQuestion`: **locale** — `en`, `ko`, or other free-text tag.
3. `AskUserQuestion`: **dev_mode** — `task-driven` (no spec gate) or
   `spec-driven` (spec_gate hook enforced).
4. `AskUserQuestion`: **targets** — `claude-code`, `cursor`, or both
   (multi-select; `claude-code,cursor` for both).

Then dispatch with the collected values:

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS"
```

Existing settings outside these four dimensions (workflow naming, reviewer
enablement, anti-rot config, etc.) are reused from `.claude/harness.yaml`.
For a deeper reset that re-asks those too, run from a real terminal:
`uv run --directory <plugin_dir> python -m harness_maker.cli make <project> --reinterview`.

#### Audit only

Read `.claude/harness.yaml`, render no files, report:
- harness_maker_version vs installed plugin version (drift)
- file count under `.claude/`
- last `.backup-*` timestamp (recovery point)
- summary of active reviewers / skills / domains

Use Read + Bash; no CLI invocation.

#### Fresh install

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" --autoloop
```

(Substitute the values collected in step 3. `$TARGETS` is the
comma-joined multi-select — e.g. `claude-code` or `claude-code,cursor`.)

### 5. Report

After dispatch, summarize what changed:
- Files: how many REPLACE / MERGE_BLOCK / KEEP (the CLI prints this)
- Whether the chosen intent landed (e.g., "preset is now Production")
- Backup directory path for recovery

If something's unclear, prompt the user with `AskUserQuestion` rather than
guessing.

## Notes

- The CLI's `--autoloop` skips its interview using preset defaults — only
  use this for fresh installs where you've already collected answers via
  `AskUserQuestion`.
- **Never pass `--reinterview` from the slash command.** It only works on
  a real TTY; in slash context it silently falls back to `--autoloop`
  defaults. If the user types `--reinterview` in their prompt, route them
  to the **Full reconfigure** branch (section 0.5) which drives
  `AskUserQuestion` here. `--reinterview` from a real terminal still
  works for users who want the full interactive interview that re-asks
  every dimension (workflows, reviewer enablement, anti-rot, etc.) —
  the slash-command Full reconfigure is a slimmer 4-dimension reset
  (preset / locale / dev_mode / targets).
- `--preset / --locale / --dev-mode / --targets` are the in-band override
  flags; prefer these for slash-command-driven reconfiguration since they
  don't need a TTY.
- `@hm:user:*` block markers preserve user content during re-render —
  separate from interview answers.
