# /harness-maker:make

Refresh, reconfigure, or extend the project's harness at `<cwd>/.claude/`.
Asks the user what they want to do before invoking the CLI.

## Procedure

You (Claude) act as the orchestrator. Follow these steps:

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

Then use `AskUserQuestion` with these options:

- **Update** — re-render with the same settings; pick up new template
  improvements. (recommended after a `/plugin update`)
- **Switch preset** — Side ↔ Production. Re-derives all preset-coupled
  defaults (security gates, worktree scope, default reviewer set).
- **Switch locale** — change the `locale` tag (en/ko/ja/...).
- **Switch dev_mode** — spec-driven ↔ task-driven.
- **Add a component** — install one extra reviewer / skill / domain pack.
- **Remove a component** — uninstall one reviewer / skill.
- **Full reconfigure** — re-run the entire interview (only works in a real
  terminal; from the slash command it falls back to defaults).
- **Audit only** — report status, do not change anything.

### 3. If `STATE=fresh-install` — ask first-time questions

Use `AskUserQuestion` to gather:
- preset (Side / Production)
- locale (en / ko / free-text)
- dev_mode (task-driven / spec-driven; Side default = task, Production = spec)

Then dispatch with `--preset / --locale / --dev-mode --autoloop` so the CLI
skips its own interview but uses the answers you collected.

### 3.5. Detect custom statusLine and ask policy

Before dispatching, look at `statusLine.command` in:

1. `.claude/settings.json` (project-level — wins by Claude Code precedence)
2. `~/.claude/settings.json` (user-global — shadowed if we write to project)

Outcomes:

- Both empty / missing → CLI installs harness-maker's wrapper. No question.
- Project-level matches `uv run python -m harness_maker.statusline` (broken
  v0.3.0 default) or `bash .claude/lib/run-statusline.sh` (current simple
  wrapper) → CLI auto-upgrades silently. No question.
- Project-level matches `bash .claude/lib/run-statusline-combined.sh`
  (combined wrapper from a prior "combine" choice) → preserve as-is. No
  question.
- Project-level is custom OR project-level is empty but global is custom
  → user has a statusLine that would be **shadowed** if we write one. Use
  `AskUserQuestion`:

  > "Custom statusLine detected: `<command>`. What should happen?"
  >
  > - **Keep mine** — preserve my custom statusLine, don't install harness-maker's.
  > - **Combine** — render a wrapper that runs both my command and harness-maker's metrics, joining outputs with ` | `.
  > - **Use harness-maker** — overwrite my custom one with harness-maker's wrapper.

Map the answer to a flag and append it to the dispatch invocation:

| Answer            | Flag                                  |
|-------------------|---------------------------------------|
| Keep mine         | `--statusline-policy keep`            |
| Combine           | `--statusline-policy combine`         |
| Use harness-maker | `--statusline-policy overwrite`       |

The `combine` policy creates `.claude/lib/user-statusline.sh` (one-shot,
holds your original command — edit freely; harness-maker won't touch it
again) and `.claude/lib/run-statusline-combined.sh` (the wrapper that
joins outputs). When the source command came from the user-global
settings, that's what gets captured.

The `keep` policy on a global-only statusLine drops the statusLine key
from the project's `settings.json` entirely so Claude Code falls back to
the global one — your existing statusline stays untouched.

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

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --reinterview
```

Only effective from a real terminal. From the slash command, the non-tty
fallback kicks in and the CLI uses defaults — recommend to the user that
they run from a terminal for this option.

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
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --autoloop
```

(Substitute the values collected in step 3.)

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
- The CLI's `--reinterview` is the escape hatch for users in a real
  terminal who want the full interactive interview.
- `--preset / --locale / --dev-mode` are the in-band override flags;
  prefer these for slash-command-driven reconfiguration since they don't
  need a TTY.
- `@hm:user:*` block markers preserve user content during re-render —
  separate from interview answers.
