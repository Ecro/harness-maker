# /harness-maker:make

Refresh, reconfigure, or extend the project's harness at `<cwd>/.claude/`.
Asks the user what they want to do before invoking the CLI.

## Procedure

You (Claude) act as the orchestrator. Follow these steps:

### 0. CI / test mode detection

If the prompt text contains `--ci`, extract inline params and skip all
`AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) calls. Parse `preset=`, `locale=`, `dev_mode=`,
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
reconfigure** branch in section 5, which drives `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) here in
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

Use `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code):

- **English (`en`)** — default; best-supported public-plugin baseline.
- **Korean (`ko`)** — use Korean for the rest of this onboarding flow.
- **Other locale tag** — accept a free-text BCP-47-style tag; if no localized
  template exists, explain that runtime generated text may fall back to English.

Store the answer as `$LOCALE` and use it in every later dispatch unless the
user explicitly changes it.

### 2. Detect state

Resolve the harness-maker install path via the canonical `locate` resolver,
then check whether the project already has a harness.

```bash
# Step A — Claude Code plugin resolution (works when installed via /plugin).
# Bootstrap through the newest cache path, then let `harness-maker locate`
# apply the real priority rules: projectPath==cwd > user scope > installedAt.
!cache_bootstrap=$(ls -1d "$HOME"/.claude/plugins/cache/harness-maker*/harness-maker/[0-9]*.[0-9]*.[0-9]* 2>/dev/null | awk -F/ '{print $NF, $0}' | sort -V | tail -1 | cut -d' ' -f2-)
plugin_dir=""
if [ -n "$cache_bootstrap" ]; then
    plugin_dir=$(uv run --with "$cache_bootstrap" python -m harness_maker.cli locate --plain 2>/dev/null || true)
    if [ -z "$plugin_dir" ]; then
        plugin_dir="$cache_bootstrap"
    fi
fi

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

Then use `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) with these options. **Order matters** — list
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

#### 4.3 Structured question: Smart defaults confirm screen

Show a summary of the detected profile and smart defaults in `$LOCALE`.
Use `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code):

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
>   re-render when applicable. `.backup-*/` is auto-added to your `.gitignore`
>   so the safety net doesn't surface as repo clutter. Clean up old snapshots
>   with `harness-maker prune-backups [--keep-last N] [--keep-days D] [--apply]`
>   (read-only by default; pass `--apply` to actually delete).
> - User blocks marked `@hm:user:*` are preserved; reconcile may report `KEEP`,
>   `MERGE_BLOCK`, or `REPLACE`. See `docs/reference/preservation-matrix.md` for
>   the per-file-type preservation contract (markdown / TOML / sh / hooks.json /
>   settings.json / AGENTS.md / harness.yaml).
>
> Options:
> - **Looks right** — install with these settings
> - **Adjust a few things** — change specific dimensions
> - **Full setup** — answer all questions (locale, preset, dev_mode, targets, focus, grade, domains, model, wrapup docs, ref_folders, sibling_repos)

#### 4.4 Branch on confirm response

**"Looks right"** → Jump to Section 4.6 (Preview) with smart defaults.

**"Adjust a few things"** → Use `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) to ask which dimension(s)
to change (multi-select: preset, locale, dev_mode, targets, grade_threshold,
mechanical_checks, wrapup_docs, ref_folders, sibling_repos, second_brain). For each selected
dimension, show an `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) with the current smart default,
alternatives, and a one-line trade-off. Then jump to Section 4.6.

**"Full setup"** → Ask all dimensions in order:

1. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **locale confirmation** — keep `$LOCALE` or change it.
   This must remain first if the user enters Full setup directly.
2. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **preset** — `Side` or `Production` (show smart default
   and trade-off: Side is lighter; Production increases review coverage and strictness)
3. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **dev_mode** — `task-driven` or `spec-driven`
4. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **targets** — `claude-code`, `cursor`, `codex`, or any combination (multi-select)
5. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **review focus** — "What's your primary work on this project?"
   Options: `feature` (code + UX review), `bugfix` (code + test review),
   `security` (code + security + auditor), `performance` (code + perf review),
   `refactoring` (code + concurrency review). Maps to `--focus` flag.
6. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **mechanical_checks** — "Pre-review shell commands to
   run before LLM reviewers." Show detected_checks as suggestion. User can
   accept, edit, or clear. Semicolon-separated. Maps to `--mechanical-checks`.
7. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **grade_threshold** — `A` (strict, zero P0/P1), `B`
   (moderate, up to 2 P1), or `C` (relaxed). Maps to `--grade-threshold`.
8. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **domains + model** — comma-separated domain packs
   (python, react, tauri, ...) and preferred Claude model (opus/sonnet/haiku).
   Maps to `--domains` and `--recommended-model`.
9. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **wrapup documents** — "Additional documents that
   `/hm:wrapup` should update after each work unit (e.g. CHANGELOG.md,
   TODO.md, docs/decisions/index.md)." Semicolon-separated paths relative
   to project root, or "none". Maps to `--wrapup-docs`.
10. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **ref_folders** — "Reference documentation folders
   that the `refdocs-search` skill will index for skill-driven search."
   Show detected sibling dirs (`../docs`, `../specs`, etc.) from `ls ..`
   as suggestions. Format: `::` separates multiple entries, `;` separates
   path from glob within an entry (e.g. `../docs::../specs;**/*.pdf`).
   Default glob: `**/*.{md,txt,pdf}`. DOCX unsupported. "none" to skip.
   Maps to `--ref-folders`.
11. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **sibling_repos** — "Other repositories that form
   one logical project with this one (e.g. backend + frontend monorepo
   split). Entering them lets research and review agents cross-reference
   related code."
   Suggest sibling dirs visible via `ls ..` that look like git repos.
   Semicolon-separated relative paths (e.g. `../backend;../mobile`).
   "none" to skip. Maps to `--sibling-repos`.
12. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **Second Brain** — "Connect an Obsidian vault for
   stage-aware memory? This first setup is read-first: stages read typed notes
   (decision, preference, failure, reference, project) instead of loading the
   whole vault or configuring writable folders now."
   Ask: vault path (absolute or `~`-relative), or "none" to skip.
   If given: ask project_id (kebab-case, e.g. `my-app`; blank to omit).
   Maps to `--second-brain-vault-path` and `--second-brain-project-id`.
   Tell the user that `/hm:configure` can continue with deeper Second Brain
   setup after install, including write-capable allowlisted folders.
13. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **Cross-model second opinion** —
   "Enable a second-opinion model (Codex and/or Antigravity) to cast a real k-of-N consensus
   vote in /hm:review and reconcile in /hm:plan? A missing/unauthenticated/rate-limited CLI
   degrades gracefully (warn + skip)." Multi-select: `codex`, `antigravity`, or none.
   Prereqs: `codex login` (codex), an authenticated `agy` (antigravity). Before dispatch,
   `shutil.which` each selected model's CLI (`codex` / `agy`) and warn (non-blocking) if
   absent. Maps to `--second-opinion-models` (comma-separated; empty disables).
14. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **Autopilot** — "Auto-advance
   the stage pipeline this session (stages advance past two-way-door boundaries but always
   stop at the plan interview, a CHANGES_REQUESTED review, and the wrapup merge)?" Options:
   `gated` (off, default) / `auto_safe` / `full`; if enabled, ask whether to persist across
   sessions. Maps to `--autonomy-level` and `--autonomy-persistent` / `--no-autonomy-persistent`.

#### 4.5 Preview structured question

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

**Preview first when `.claude/` already exists & is non-empty** (re-render over
existing files — this is why make does NOT use a worktree: backup + reconcile +
a read-only preview cover the overwrite concern). Run `--dry-run`, surface the
NEW / REPLACE / KEEP / MERGE counts (KEEP = your edits preserved), then confirm
with `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) — Proceed / Cancel.
On a fresh install (no existing `.claude/`), skip the preview and apply directly.
**Run these with the Bash tool when you reach them — the apply must fire only AFTER
the Proceed confirm, so they are NOT `!`-autorun lines:**

```bash
# Preview (claude-code / cursor):
uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --dry-run
# Apply — only after the user confirms Proceed (claude-code / cursor):
uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)"
# CLI_FALLBACK:
harness-maker make "$(pwd)" --dry-run
harness-maker make "$(pwd)"
```

CLI prints `reusing settings from .claude/harness.yaml` and applies new
templates while preserving user `@hm:user:*` blocks via reconcile. After applying,
run the **git disposition** step (section 6.5).

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

Ask the user for the new ref_folders value with `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) (current
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

Ask the user for the new sibling_repos value with `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) (current
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

Drive the interview here in the slash command via `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) —
**do not** pass `--reinterview` to the CLI (its stdin-based interview
falls back to autoloop defaults in slash context). Ask each dimension
in turn, then dispatch with all collected flags:

1. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **locale confirmation** — keep `$LOCALE` from section 1
   or change it before asking any other setup question.
2. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **preset** — `Side` (1 reviewer, lean) or
   `Production` (5 reviewers, verify-required).
3. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **dev_mode** — `task-driven` (no spec gate) or
   `spec-driven` (spec_gate hook enforced).
4. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **targets** — `claude-code`, `cursor`, `codex`, or any combination
   (multi-select; `claude-code,cursor,codex` for all three).
5. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **review focus** — `feature` | `bugfix` | `security` |
   `performance` | `refactoring`. Maps to `--focus`.
6. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **mechanical_checks** — semicolon-separated commands.
   Show detected_checks from `profile --json` as suggestion. Maps to
   `--mechanical-checks`.
7. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **grade_threshold** — `A` | `B` | `C`. Maps to
   `--grade-threshold`.
8. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **domains + model** — comma-separated domain packs
   and preferred Claude model. Maps to `--domains` and `--recommended-model`.
9. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **wrapup documents** — semicolon-separated paths to
   docs that `/hm:wrapup` should update (e.g. `CHANGELOG.md;TODO.md`), or
   "none". Maps to `--wrapup-docs`.
10. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **ref_folders** — reference doc folders for the
   `refdocs-search` skill. Show sibling git repos visible via `ls ..` as
   suggestions. `::` separates entries, `;` separates path from glob within
   an entry (e.g. `../docs::../specs;**/*.pdf`). "none" to skip.
   Maps to `--ref-folders`.
11. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **sibling_repos** — other repos forming one logical
   project (e.g. `../backend;../mobile`). Show sibling git dirs as
   suggestions. Semicolon-separated relative paths, or "none".
   Maps to `--sibling-repos`.
12. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **Second Brain** — "Connect an Obsidian vault for
   stage-aware memory?" Ask for vault path (absolute or `~`-relative), or
   "none" to skip. If given: ask project_id (kebab-case, e.g. `my-app`).
   Maps to `--second-brain-vault-path` and `--second-brain-project-id`.
13. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **Cross-model second opinion** —
   multi-select `codex`, `antigravity`, or none. Graceful warn+skip on a missing/
   unauthenticated/rate-limited CLI. `shutil.which` each selected CLI (`codex` / `agy`) and
   warn (non-blocking) if absent. Maps to `--second-opinion-models` (comma-separated).
14. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): **Autopilot** — `gated` (off) /
   `auto_safe` / `full`; if enabled, ask whether to persist across sessions. Maps to
   `--autonomy-level` and `--autonomy-persistent` / `--no-autonomy-persistent`.

Then dispatch with the collected values:

```bash
# claude-code / cursor:
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID" \
  --second-opinion-models "$SECOND_OPINION_MODELS" --autonomy-level "$AUTONOMY_LEVEL"
# CLI_FALLBACK:
!harness-maker make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID" \
  --second-opinion-models "$SECOND_OPINION_MODELS" --autonomy-level "$AUTONOMY_LEVEL"
```

Omit `--second-brain-vault-path` when the user chose "none"; omit
`--second-brain-project-id` when the user left it blank. Omit
`--second-opinion-models` / `--autonomy-level` when the user left them at default.
Add `--autonomy-persistent` (or `--no-autonomy-persistent`) only when the user made an
explicit choice. Omit all other flags for dimensions the user skipped or left at default.

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

1. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): vault path — current value shown; enter new path, empty to keep,
   or "none" to disable.
2. `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code): project_id — current value shown; enter new value or blank to keep.
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
  --second-opinion-models "$SECOND_OPINION_MODELS" --autonomy-level "$AUTONOMY_LEVEL" \
  --autoloop
# CLI_FALLBACK:
!harness-maker make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" \
  --second-brain-vault-path "$SB_VAULT_PATH" --second-brain-project-id "$SB_PROJECT_ID" \
  --second-opinion-models "$SECOND_OPINION_MODELS" --autonomy-level "$AUTONOMY_LEVEL" \
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

If something's unclear, prompt the user with `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) rather than
guessing.

### 6.5 Git disposition — the last mile (after any install / update)

The harness files are written but the user still has to decide whether they go
into version control. Guide that decision **neutrally** — present the two options
as equals, with no recommended marker and no preference ordering (the order they
appear below is not a recommendation). **Run each command block below with the Bash
tool when you reach it — these are gated steps, NOT `!`-autorun lines: the commit /
gitignore actions must fire only AFTER the user has explicitly chosen.** First read
the state (dispatch shape per `$RESOLVE_MODE`):

```bash
# claude-code / cursor:
uv run --directory "$plugin_dir" python -m harness_maker.cli git-status "$(pwd)"
# CLI_FALLBACK:
harness-maker git-status "$(pwd)"
```

Read the JSON and branch on `is_git` / `decision_needed` / `offer_stage` /
`prior_decision`:

- **`is_git: false`** — not a git repository. Tell the user the harness files are
  not under version control; if they want to track them, they can run `git init`
  and re-run `/harness-maker:make`. Run no git commands. Done.
- **`decision_needed: true`** — ask with `AskQuestion` (Cursor) / `AskUserQuestion`
  (Claude Code), in the user's locale, the two options **as equals**:
  - **Commit them** — the harness roots are added to git and committed, so anyone
    who clones the repo gets the harness (churn + `.backup-*` are already
    gitignored, so the commit is clean). On this choice run (scopes both the add
    AND the commit to only the existing roots — the `-- $roots` pathspec keeps any
    unrelated pre-staged work OUT of the harness commit):
    ```bash
    roots=""; for r in .claude .cursor .codex .agents AGENTS.md; do [ -e "$r" ] && roots="$roots $r"; done; git add $roots && git commit -m "chore: add harness-maker harness" -- $roots
    ```
  - **Gitignore them** — the roots are added to `.gitignore` and kept local
    (fails loudly if the write does not take effect):
    ```bash
    # claude-code / cursor:
    uv run --directory "$plugin_dir" python -m harness_maker.cli git-ignore-roots "$(pwd)"
    # CLI_FALLBACK:
    harness-maker git-ignore-roots "$(pwd)"
    ```
- **`offer_stage: true`** — already committing, and new harness files appeared. Ask
  "Stage the new harness files into a commit?"; on yes, `git add` the
  `untracked_files` then commit **scoped to those paths**:
  `git commit -m "chore: update harness-maker harness" -- <untracked_files>` (the
  `-- <paths>` keeps unrelated staged work out); on no, skip.
- **`prior_decision: "commit"` (no `offer_stage`), `"ignore"`, or no rendered roots
  present** — already decided (or nothing to dispose). Say one line ("harness
  already tracked" / "already gitignored — nothing to do") and finish. **Do NOT
  re-prompt** — the decision is inferred from git state, so a re-render never
  re-nags.

## Notes

- The CLI's `--autoloop` skips its interview using preset defaults — only
  use this for fresh installs where you've already collected answers via
  `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code).
- **Never pass `--reinterview` from the slash command.** It only works on
  a real TTY; in slash context it silently falls back to `--autoloop`
  defaults. If the user types `--reinterview` in their prompt, route them
  to the **Full reconfigure** branch (section 0.5) which drives
  `AskQuestion` (Cursor) / `AskUserQuestion` (Claude Code) here. `--reinterview` from a real terminal still
  works for users who want the full interactive interview that re-asks
  every dimension (workflows, reviewer enablement, anti-rot, etc.) —
  the slash-command Full reconfigure covers preset / locale / dev_mode /
  targets / ref_folders / sibling_repos (not workflows or reviewer enablement).
- `--preset / --locale / --dev-mode / --targets` are the in-band override
  flags; prefer these for slash-command-driven reconfiguration since they
  don't need a TTY.
- `@hm:user:*` block markers preserve user content during re-render —
  separate from interview answers.
