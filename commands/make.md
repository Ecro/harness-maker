# /harness-maker:make

Refresh, reconfigure, or extend the project's harness at `<cwd>/.claude/`.
Asks the user what they want to do before invoking the CLI.

## Procedure

You (Claude) act as the orchestrator. Follow these steps:

### 0. CI / test mode detection

If the prompt text contains `--ci`, extract inline params and skip all
`AskUserQuestion` calls. Parse `preset=`, `locale=`, `dev_mode=`,
`targets=` from the prompt; use defaults `Side` / `en` / `task` /
`claude-code` for any that are absent. Skip the live locale question and
jump directly to section 5 (Dispatch → Fresh install or Update,
depending on whether `.claude/harness.yaml` exists).

Example invocation:
```
/harness-maker:make --ci preset=Side locale=en dev_mode=task targets=claude-code,cursor,codex
```

### 0.5. `--reinterview` shortcut

If the prompt text contains `--reinterview` (and is not `--ci`), the user
wants a full interactive reconfigure. **Do not pass `--reinterview` through
to the CLI** — the CLI's interactive interview reads from stdin, which
falls back to autoloop defaults in the slash-command context (no TTY).
Instead, skip the menu in section 3 and jump straight to the **Full
reconfigure** branch in section 5, which drives `AskUserQuestion` here in
the slash command and dispatches with collected `--preset / --locale /
--dev-mode / --targets` flags.

### 1. Choose live locale

Default is `en`, but the first interactive decision must be the user's live
onboarding language. Ask this before profile detection, preset selection,
dev_mode, targets, or any setup confirmation. All subsequent live onboarding prose,
question text, option labels, trade-off explanations, and decision
summaries must use the selected locale. Persisted generated documents may still
follow their own template rules; this section controls the live setup
conversation.

Use `AskUserQuestion`:

- **English (`en`)** — default; best-supported public-plugin baseline.
- **Korean (`ko`)** — use Korean for the rest of this onboarding flow.
- **Other locale tag** — accept a free-text BCP-47-style tag; if no localized
  template exists, explain that runtime generated text may fall back to English.

Store the answer as `$LOCALE` and use it in every later dispatch unless the
user explicitly changes it.

### 2. Detect state

Resolve the harness-maker install path via a 3-step fallback, then check
whether the project already has a harness.

```bash
# Step A — Claude Code plugin resolution (works when installed via /plugin)
!plugin_dir=$(python3 -c "
import json, os, pathlib
try:
    data = json.load(open(pathlib.Path.home() / '.claude/plugins/installed_plugins.json'))
    entries = data['plugins']['harness-maker@harness-maker-local']
    cwd = os.getcwd()
    match = next((e for e in entries if e.get('projectPath') == cwd), entries[0])
    print(match['installPath'])
except Exception:
    print('')
" 2>/dev/null)

if [ -n "$plugin_dir" ]; then
    RESOLVE_MODE="claude-code"
    echo "RESOLVE_MODE=claude-code  PLUGIN_DIR=$plugin_dir"
else
    # Step B — Cursor local plugin directory
    cursor_local="$HOME/.cursor/plugins/local/harness-maker"
    if [ -d "$cursor_local" ] && [ -f "$cursor_local/pyproject.toml" ]; then
        plugin_dir="$cursor_local"
        RESOLVE_MODE="cursor"
        echo "RESOLVE_MODE=cursor  PLUGIN_DIR=$plugin_dir"
    else
        # Step C — CLI fallback (console_scripts or uv tool)
        cli_path=$(command -v harness-maker 2>/dev/null || true)
        if [ -n "$cli_path" ]; then
            RESOLVE_MODE="CLI_FALLBACK"
            echo "RESOLVE_MODE=CLI_FALLBACK  CLI_PATH=$cli_path"
        else
            echo "ERROR: harness-maker not found. Install with: uv tool install harness-maker  OR  pip install harness-maker"
            exit 1
        fi
    fi
fi

[ -f "$(pwd)/.claude/harness.yaml" ] && echo "STATE=re-render" || echo "STATE=fresh-install"
```

The variable `$RESOLVE_MODE` (`claude-code`, `cursor`, or `CLI_FALLBACK`)
determines the dispatch shape in section 5.

### 3. If `STATE=re-render` — show current settings + ask intent

Read `.claude/harness.yaml` body (skip frontmatter) and surface to the user:
- preset, locale, dev_mode, default_workflow
- harness_maker_version (so they see how stale)
- count of enabled reviewers/skills

Then use `AskUserQuestion` with these options. **Order matters** — list
"Switch runtime targets" prominently right after Update, since it's the
most common reason existing 0.4.x/0.5.0 users return to this command:

- **Update** — re-render with the same settings; pick up new template
  improvements. (recommended after a `/plugin update`. Does **not** ask
  about extra runtimes — pick "Switch runtime targets" if you want to opt into
  Cursor or Codex on a previously claude-code-only install.) Explain that the
  CLI backs up the current generated harness state under `.backup-<timestamp>`
  before rendering when existing files are present.
- **Switch runtime targets** — pick `claude-code`, `cursor`, `codex`, or any combination.
  Adding `cursor` renders `.cursor/rules/harness.mdc` + `.cursor/mcp.json`
  alongside the shared `.claude/` assets so the harness drives Cursor
  IDE 2.4+ natively. Adding `codex` renders `AGENTS.md`, `.codex/`, and
  `.agents/skills/` assets. Dropping a target does not delete previously
  rendered target-specific files; it leaves them in place so user edits are not
  destroyed. Remove them manually or with uninstall if you want a clean slate.
- **Switch preset** — Side ↔ Production. Re-derives all preset-coupled
  defaults (security gates, worktree scope, default reviewer set). Trade-off:
  Production increases review coverage and strictness; Side is lighter.
- **Switch locale** — change the `locale` tag (en/ko/ja/...).
- **Switch dev_mode** — spec-driven ↔ task-driven.
- **Add a component** — install one extra reviewer / skill / domain pack.
- **Remove a component** — uninstall one reviewer / skill.
- **Manage ref_folders** — add, remove, or clear reference document folders
  that the `refdocs-search` skill indexes. Ask the user for new folder paths.
- **Manage sibling_repos** — add, remove, or clear sibling repo relative paths
  that provide cross-repo context during research and review.
- **Manage Second Brain** — enable, disable, or update the Obsidian vault
  connection. Ask for `vault_path` and `project_id`; dispatches with
  `--second-brain-vault-path` (pass empty string to disable). Explain that
  first setup is read-first: stages search configured project memory rather
  than writing arbitrary vault files; deeper writable-folder setup continues in
  `/hm:configure`.
- **Full reconfigure** — drive a fresh interview here in the slash command
  (locale → preset → dev_mode → targets → ref_folders → sibling_repos →
  second_brain) and dispatch with all flags. No TTY required — works in
  slash-command context.
  (`--reinterview` typed directly in the prompt also routes here; see section 0.5.)
- **Audit only** — report status, do not change anything.

### 4. If `STATE=fresh-install` — smart defaults + confirm

#### 4.1 Run profile scan

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli profile "$(pwd)" --json
# CLI_FALLBACK:
!harness-maker profile "$(pwd)" --json
```

Parse the JSON output. Extract: `stack`, `scale`, `lifecycle`, `detected_checks`.

#### 4.2 Compute smart defaults

Based on the profile, derive:
- **preset**: `Production` if (scale=medium/large OR lifecycle=active), else `Side`
- **preset reason**: e.g. "stack=Python+FastAPI, scale=medium, lifecycle=active → Production recommended"
- **reviewer_list**: Side = `[code-reviewer]`; Production = `[code-reviewer, security-reviewer, performance-reviewer, ux-reviewer, concurrency-reviewer]`
- **detected_checks**: from profile scan (may be empty)
- **grade_threshold**: `A` if Production, else `B`
- **locale**: `$LOCALE` from section 1 (`en` when the user accepted the default)
- **dev_mode**: `spec-driven` if Production, else `task-driven`
- **targets**: `claude-code` (default)

#### 4.3 AskUserQuestion: Smart defaults confirm screen

Show a summary of the detected profile and smart defaults in `$LOCALE`.
Use `AskUserQuestion`:

> **Project profile detected:**
> - Stack: {stack}
> - Scale: {scale} ({file_count} files)
> - Lifecycle: {lifecycle}
>
> **Recommended setup:**
> - Preset: {preset} — {reason}
> - Reviewers: {reviewer_list}
> - Mechanical checks: {detected_checks or "(none detected — add manually later)"}
> - Grade threshold: {grade_threshold}
> - Auto-fix: enabled
> - Review trade-off: stricter gates, more reviewers, and mechanical checks
>   increase confidence and may increase review work; this flow explains the
>   trade-off without predicting exact review time.
>
> **Safety receipt preview:**
> - Generated roots may include `.claude/`, `.cursor/`, `.codex/`,
>   `.agents/skills/`, and `AGENTS.md`, depending on selected targets.
> - Existing generated state is backed up under `.backup-<timestamp>` before
>   re-render when applicable.
> - User blocks marked `@hm:user:*` are preserved; reconcile may report `KEEP`,
>   `MERGE_BLOCK`, or `REPLACE`.
>
> Options:
> - **Looks right** — install with these settings
> - **Adjust a few things** — change specific dimensions
> - **Full setup** — answer all questions (locale, preset, dev_mode, targets, focus, grade, domains, model, wrapup docs, ref_folders, sibling_repos)

#### 4.4 Branch on confirm response

**"Looks right"** → Jump to Section 4.6 (Preview) with smart defaults.

**"Adjust a few things"** → Use `AskUserQuestion` to ask which dimension(s)
to change (multi-select: preset, locale, dev_mode, targets, grade_threshold,
mechanical_checks, wrapup_docs, ref_folders, sibling_repos, second_brain). For each selected
dimension, show an `AskUserQuestion` with the current smart default,
alternatives, and a one-line trade-off. Then jump to Section 4.6.

**"Full setup"** → Ask all dimensions in order:

1. `AskUserQuestion`: **locale confirmation** — keep `$LOCALE` or change it.
   This must remain first if the user enters Full setup directly.
2. `AskUserQuestion`: **preset** — `Side` or `Production` (show smart default
   and trade-off: Side is lighter; Production increases review coverage and strictness)
3. `AskUserQuestion`: **dev_mode** — `task-driven` or `spec-driven`
4. `AskUserQuestion`: **targets** — `claude-code`, `cursor`, `codex`, or any combination (multi-select)
5. `AskUserQuestion`: **review focus** — "What's your primary work on this project?"
   Options: `feature` (code + UX review), `bugfix` (code + test review),
   `security` (code + security + auditor), `performance` (code + perf review),
   `refactoring` (code + concurrency review). Maps to `--focus` flag.
6. `AskUserQuestion`: **mechanical_checks** — "Pre-review shell commands to
   run before LLM reviewers." Show detected_checks as suggestion. User can
   accept, edit, or clear. Semicolon-separated. Maps to `--mechanical-checks`.
7. `AskUserQuestion`: **grade_threshold** — `A` (strict, zero P0/P1), `B`
   (moderate, up to 2 P1), or `C` (relaxed). Maps to `--grade-threshold`.
8. `AskUserQuestion`: **domains + model** — comma-separated domain packs
   (python, react, tauri, ...) and preferred Claude model (opus/sonnet/haiku).
   Maps to `--domains` and `--recommended-model`.
9. `AskUserQuestion`: **wrapup documents** — "Additional documents that
   `/hm:wrapup` should update after each work unit (e.g. CHANGELOG.md,
   TODO.md, docs/decisions/index.md)." Semicolon-separated paths relative
   to project root, or "none". Maps to `--wrapup-docs`.
10. `AskUserQuestion`: **ref_folders** — "Reference documentation folders
   that the `refdocs-search` skill will index for skill-driven search."
   Show detected sibling dirs (`../docs`, `../specs`, etc.) from `ls ..`
   as suggestions. Format: `::` separates multiple entries, `;` separates
   path from glob within an entry (e.g. `../docs::../specs;**/*.pdf`).
   Default glob: `**/*.{md,txt,pdf}`. DOCX unsupported. "none" to skip.
   Maps to `--ref-folders`.
11. `AskUserQuestion`: **sibling_repos** — "Other repositories that form
   one logical project with this one (e.g. backend + frontend monorepo
   split). Entering them lets research and review agents cross-reference
   related code."
   Suggest sibling dirs visible via `ls ..` that look like git repos.
   Semicolon-separated relative paths (e.g. `../backend;../mobile`).
   "none" to skip. Maps to `--sibling-repos`.
12. `AskUserQuestion`: **Second Brain** — "Connect an Obsidian vault for
   stage-aware memory? This first setup is read-first: stages read typed notes
   (decision, preference, failure, reference, project) instead of loading the
   whole vault or configuring writable folders now."
   Ask: vault path (absolute or `~`-relative), or "none" to skip.
   If given: ask project_id (kebab-case, e.g. `my-app`; blank to omit).
   Maps to `--second-brain-vault-path` and `--second-brain-project-id`.
   Tell the user that `/hm:configure` can continue with deeper Second Brain
   setup after install, including write-capable allowlisted folders.

#### 4.5 Preview AskUserQuestion

Before dispatch, show a preview:

> **Will install/update harness files.** Key capabilities and safety receipt:
> - {count} slash commands ({workflow_names})
> - {reviewer_count} reviewers active
> - {skill_count} skills enabled
> - Mechanical checks: {checks or "(none)"}
> - Target roots: `.claude/` always; `.cursor/`, `.codex/`, `.agents/skills/`,
>   and `AGENTS.md` when those targets are selected.
> - Backup: existing generated state is copied to `.backup-<timestamp>` before
>   re-render when applicable.
> - Preservation: `@hm:user:*` blocks are preserved; reconcile reports `KEEP`,
>   `MERGE_BLOCK`, or `REPLACE` from the CLI output.
> - Target removal: dropping a target does not delete old target-specific files.
> - Review trade-off: more reviewers, stricter grade thresholds, and mechanical
>   checks increase confidence and can add review work, without predicting exact
>   review time.
>
> Options:
> - **Proceed** — install now
> - **Cancel** — abort

If "Cancel": exit without dispatch.

#### 4.6 Dispatch with collected values

Jump to Section 5 → Fresh install branch, passing all collected flags.

### 5. Dispatch — pick the right CLI invocation

Branch on the chosen intent. Use `$plugin_dir` and `$RESOLVE_MODE` from section 2.

**Dispatch shape by RESOLVE_MODE:**
- `claude-code` or `cursor`: `uv run --directory "$plugin_dir" python -m harness_maker.cli <args>`
- `CLI_FALLBACK`: `harness-maker <args>` (direct CLI — console_scripts entry point)

#### Update (re-render same settings)

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)"
# CLI_FALLBACK:
!harness-maker make "$(pwd)"
```

CLI prints `reusing settings from .claude/harness.yaml` and applies new
templates while preserving user `@hm:user:*` blocks via reconcile.

#### Switch preset

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --preset Production
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --preset Production
```

(or `--preset Side` for the reverse). Other dimensions stay as before.
Explain the trade-off without predicting exact review time: Production usually
enables broader review and stricter gates; Side is lighter.

#### Switch locale

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --locale ko
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --locale ko
```

#### Switch dev_mode

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --dev-mode spec-driven
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --dev-mode spec-driven
```

#### Switch runtime targets

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --targets claude-code,cursor,codex
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --targets claude-code,cursor,codex
```

(or `--targets cursor` for Cursor-only, `--targets codex` for Codex-only,
`--targets claude-code` to drop back to Claude-Code-only.) Adding `cursor`
renders `.cursor/rules/harness.mdc` + `.cursor/mcp.json`; adding `codex`
renders `AGENTS.md`, `.codex/`, and `.agents/skills/`. Dropping a target
does **not** delete previously rendered target-specific files — remove them
manually if you want a clean slate.

#### Add / remove a component

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --add reviewer:security
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --remove skill:research-crawler
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --add-domain tauri
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --add reviewer:security
!harness-maker make "$(pwd)" --remove skill:research-crawler
!harness-maker make "$(pwd)" --add-domain tauri
```

Available reviewers: `code`, `security`, `performance`, `concurrency`, `ux`,
`security-auditor`, `consensus-arbiter`, `executor`, `autoloop-coder`.
Available skills: see `.claude/harness.yaml` `skills.installed`. Domain
packs ship: `python` (others get a user-side stub).

#### Manage ref_folders

Ask the user for the new ref_folders value with `AskUserQuestion` (current
value shown from harness.yaml), then dispatch:

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --ref-folders "$REF_FOLDERS"
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --ref-folders "$REF_FOLDERS"
```

`$REF_FOLDERS` uses `::` between entries and `;` between path and glob within
an entry (e.g. `../docs::../specs;**/*.pdf`). Pass the empty string to clear.

#### Manage sibling_repos

Ask the user for the new sibling_repos value with `AskUserQuestion` (current
value shown from harness.yaml), then dispatch:

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --sibling-repos "$SIBLING_REPOS"
# CLI_FALLBACK:
!harness-maker make "$(pwd)" --sibling-repos "$SIBLING_REPOS"
```

`$SIBLING_REPOS` is semicolon-separated relative paths (e.g. `../backend;../mobile`).
Pass the empty string to clear.

#### Full reconfigure

Drive the interview here in the slash command via `AskUserQuestion` —
**do not** pass `--reinterview` to the CLI (its stdin-based interview
falls back to autoloop defaults in slash context). Ask each dimension
in turn, then dispatch with all collected flags:

1. `AskUserQuestion`: **locale confirmation** — keep `$LOCALE` from section 1
   or change it before asking any other setup question.
2. `AskUserQuestion`: **preset** — `Side` (1 reviewer, lean) or
   `Production` (5 reviewers, verify-required).
3. `AskUserQuestion`: **dev_mode** — `task-driven` (no spec gate) or
   `spec-driven` (spec_gate hook enforced).
4. `AskUserQuestion`: **targets** — `claude-code`, `cursor`, `codex`, or any combination
   (multi-select; `claude-code,cursor,codex` for all three).
5. `AskUserQuestion`: **review focus** — `feature` | `bugfix` | `security` |
   `performance` | `refactoring`. Maps to `--focus`.
6. `AskUserQuestion`: **mechanical_checks** — semicolon-separated commands.
   Show detected_checks from `profile --json` as suggestion. Maps to
   `--mechanical-checks`.
7. `AskUserQuestion`: **grade_threshold** — `A` | `B` | `C`. Maps to
   `--grade-threshold`.
8. `AskUserQuestion`: **domains + model** — comma-separated domain packs
   and preferred Claude model. Maps to `--domains` and `--recommended-model`.
9. `AskUserQuestion`: **wrapup documents** — semicolon-separated paths to
   docs that `/hm:wrapup` should update (e.g. `CHANGELOG.md;TODO.md`), or
   "none". Maps to `--wrapup-docs`.
10. `AskUserQuestion`: **ref_folders** — reference doc folders for the
   `refdocs-search` skill. Show sibling git repos visible via `ls ..` as
   suggestions. `::` separates entries, `;` separates path from glob within
   an entry (e.g. `../docs::../specs;**/*.pdf`). "none" to skip.
   Maps to `--ref-folders`.
11. `AskUserQuestion`: **sibling_repos** — other repos forming one logical
   project (e.g. `../backend;../mobile`). Show sibling git dirs as
   suggestions. Semicolon-separated relative paths, or "none".
   Maps to `--sibling-repos`.
12. `AskUserQuestion`: **Second Brain** — "Connect an Obsidian vault for
   stage-aware memory?" Ask for vault path (absolute or `~`-relative), or
   "none" to skip. If given: ask project_id (kebab-case, e.g. `my-app`).
   Maps to `--second-brain-vault-path` and `--second-brain-project-id`.

Then dispatch with the collected values:

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID"
# CLI_FALLBACK:
!harness-maker make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID"
```

Omit `--second-brain-vault-path` when the user chose "none"; omit
`--second-brain-project-id` when the user left it blank. Omit all other
flags for dimensions the user skipped or left at default.

Existing settings outside these dimensions (workflow naming, anti-rot
config, etc.) are reused from `.claude/harness.yaml`. For a deeper reset
that re-asks those too, run from a real terminal:
`harness-maker make <project> --reinterview` (or
`uv run --directory <plugin_dir> python -m harness_maker.cli make <project> --reinterview`).

#### Audit only

Read `.claude/harness.yaml`, render no files, report:
- harness_maker_version vs installed plugin version (drift)
- file count under `.claude/`
- last `.backup-*` timestamp (recovery point)
- summary of active reviewers / skills / domains

Use Read + Bash; no CLI invocation.

#### Manage Second Brain

Read `.claude/harness.yaml` for current `second_brain` settings (enabled, vault_path,
project_id). Show them, explain this is the advanced path after read-first
setup, then ask:

1. `AskUserQuestion`: vault path — current value shown; enter new path, empty to keep,
   or "none" to disable.
2. `AskUserQuestion`: project_id — current value shown; enter new value or blank to keep.
3. Explain that write-capable folders are constrained by allowlist,
   Markdown/frontmatter validation, and `project_id` namespace rules.

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID"
# CLI_FALLBACK:
!harness-maker make "$(pwd)" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID"
```

Pass empty string `""` for `--second-brain-vault-path` to disable. Omit
`--second-brain-project-id` if the user left it unchanged.

#### Fresh install

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID" \
  --autoloop
# CLI_FALLBACK:
!harness-maker make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID" \
  --autoloop
```

Substitute the values collected in section 4. Omit flags the user didn't set
or left at smart defaults (the CLI applies preset defaults for unset flags).
`$TARGETS` is the comma-joined multi-select — e.g. `claude-code`,
`claude-code,cursor`, or `claude-code,cursor,codex`.

### 6. Report + Quick start

After dispatch, summarize what changed:
- Files: how many REPLACE / MERGE_BLOCK / KEEP (the CLI prints this)
- Whether the chosen intent landed (e.g., "preset is now Production")
- Backup directory path for recovery
- What target roots are now active and which previously rendered target files
  were intentionally left in place
- For Second Brain: whether it is disabled, read-first, or ready for deeper
  `/hm:configure` setup

Then show a **quick-start** guide:

> **Harness installed!** Here's what to try first:
> - Run `/hm:execute <task>` to implement a feature with TDD
> - Run `/hm:ai-readiness` to see your project's AI-readiness score
> - Run `/hm:configure` to adjust settings later
> - Run `/hm:make` after a plugin update for a quick re-render

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
  the slash-command Full reconfigure covers preset / locale / dev_mode /
  targets / ref_folders / sibling_repos (not workflows or reviewer enablement).
- `--preset / --locale / --dev-mode / --targets` are the in-band override
  flags; prefer these for slash-command-driven reconfiguration since they
  don't need a TTY.
- `@hm:user:*` block markers preserve user content during re-render —
  separate from interview answers.
