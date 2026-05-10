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
/harness-maker:make --ci preset=Side locale=en dev_mode=task targets=claude-code,cursor,codex
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
"Switch runtime targets" prominently right after Update, since it's the
most common reason existing 0.4.x/0.5.0 users return to this command:

- **Update** — re-render with the same settings; pick up new template
  improvements. (recommended after a `/plugin update`. Does **not** ask
  about extra runtimes — pick "Switch runtime targets" if you want to opt into
  Cursor or Codex on a previously claude-code-only install.)
- **Switch runtime targets** — pick `claude-code`, `cursor`, `codex`, or any combination.
  Adding `cursor` renders `.cursor/rules/harness.mdc` + `.cursor/mcp.json`
  alongside the shared `.claude/` assets so the harness drives Cursor
  IDE 2.4+ natively. Adding `codex` renders `AGENTS.md`, `.codex/`, and
  `.agents/skills/` assets. Removing a target leaves prior target-specific
  files in place (delete manually if undesired).
- **Switch preset** — Side ↔ Production. Re-derives all preset-coupled
  defaults (security gates, worktree scope, default reviewer set).
- **Switch locale** — change the `locale` tag (en/ko/ja/...).
- **Switch dev_mode** — spec-driven ↔ task-driven.
- **Add a component** — install one extra reviewer / skill / domain pack.
- **Remove a component** — uninstall one reviewer / skill.
- **Manage ref_folders** — add, remove, or clear reference document folders
  that the `refdocs-search` skill indexes. Ask the user for new folder paths.
- **Manage sibling_repos** — add, remove, or clear sibling repo relative paths
  that provide cross-repo context during research and review.
- **Full reconfigure** — drive a fresh interview here in the slash command
  (preset → locale → dev_mode → targets → ref_folders → sibling_repos) and
  dispatch with all flags. No TTY required — works in slash-command context.
  (`--reinterview` typed directly in the prompt also routes here; see section 0.5.)
- **Audit only** — report status, do not change anything.

### 3. If `STATE=fresh-install` — smart defaults + confirm

#### 3.1 Run profile scan

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli profile "$(pwd)" --json
```

Parse the JSON output. Extract: `stack`, `scale`, `lifecycle`, `detected_checks`.

#### 3.2 Compute smart defaults

Based on the profile, derive:
- **preset**: `Production` if (scale=medium/large OR lifecycle=active), else `Side`
- **preset reason**: e.g. "stack=Python+FastAPI, scale=medium, lifecycle=active → Production recommended"
- **reviewer_list**: Side = `[code-reviewer]`; Production = `[code-reviewer, security-reviewer, performance-reviewer, ux-reviewer, concurrency-reviewer]`
- **detected_checks**: from profile scan (may be empty)
- **grade_threshold**: `A` if Production, else `B`
- **locale**: `en` (default)
- **dev_mode**: `spec-driven` if Production, else `task-driven`
- **targets**: `claude-code` (default)

#### 3.3 AskUserQuestion: Smart defaults confirm screen

Show a summary of the detected profile and smart defaults. Use `AskUserQuestion`:

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
>
> Options:
> - **Looks right** — install with these settings
> - **Adjust a few things** — change specific dimensions
> - **Full setup** — answer all questions (preset, locale, dev_mode, targets, focus, grade, domains, model, wrapup docs, ref_folders, sibling_repos)

#### 3.4 Branch on confirm response

**"Looks right"** → Jump to Section 3.6 (Preview) with smart defaults.

**"Adjust a few things"** → Use `AskUserQuestion` to ask which dimension(s)
to change (multi-select: preset, locale, dev_mode, targets, grade_threshold,
mechanical_checks, wrapup_docs, ref_folders, sibling_repos). For each selected
dimension, show an `AskUserQuestion` with the current smart default and
alternatives. Then jump to Section 3.6.

**"Full setup"** → Ask all dimensions in order:

1. `AskUserQuestion`: **preset** — `Side` or `Production` (show smart default)
2. `AskUserQuestion`: **locale** — `en`, `ko`, or free-text
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

#### 3.5 Preview AskUserQuestion

Before dispatch, show a preview:

> **Will install 40+ files under .claude/.** Key capabilities:
> - {count} slash commands ({workflow_names})
> - {reviewer_count} reviewers active
> - {skill_count} skills enabled
> - Mechanical checks: {checks or "(none)"}
>
> Options:
> - **Proceed** — install now
> - **Cancel** — abort

If "Cancel": exit without dispatch.

#### 3.6 Dispatch with collected values

Jump to Section 4 → Fresh install branch, passing all collected flags.

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

#### Switch runtime targets

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" --targets claude-code,cursor,codex
```

(or `--targets cursor` for Cursor-only, `--targets codex` for Codex-only,
`--targets claude-code` to drop back to Claude-Code-only.) Adding `cursor`
renders `.cursor/rules/harness.mdc` + `.cursor/mcp.json`; adding `codex`
renders `AGENTS.md`, `.codex/`, and `.agents/skills/`. Dropping a target
does **not** delete previously rendered target-specific files — remove them
manually if you want a clean slate.

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

#### Manage ref_folders

Ask the user for the new ref_folders value with `AskUserQuestion` (current
value shown from harness.yaml), then dispatch:

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --ref-folders "$REF_FOLDERS"
```

`$REF_FOLDERS` uses `::` between entries and `;` between path and glob within
an entry (e.g. `../docs::../specs;**/*.pdf`). Pass the empty string to clear.

#### Manage sibling_repos

Ask the user for the new sibling_repos value with `AskUserQuestion` (current
value shown from harness.yaml), then dispatch:

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --sibling-repos "$SIBLING_REPOS"
```

`$SIBLING_REPOS` is semicolon-separated relative paths (e.g. `../backend;../mobile`).
Pass the empty string to clear.

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

Then dispatch with the collected values:

```bash
!uv run --directory "$plugin_dir" python -m harness_maker.cli make "$(pwd)" \
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS"
```

Omit flags for any dimension the user skipped or left at default.

Existing settings outside these dimensions (workflow naming, anti-rot
config, etc.) are reused from `.claude/harness.yaml`. For a deeper reset
that re-asks those too, run from a real terminal:
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
  --preset "$PRESET" --locale "$LOCALE" --dev-mode "$DEV_MODE" --targets "$TARGETS" \
  --focus "$FOCUS" --grade-threshold "$GRADE" --domains "$DOMAINS" \
  --mechanical-checks "$CHECKS" --recommended-model "$MODEL" --wrapup-docs "$WRAPUP_DOCS" \
  --ref-folders "$REF_FOLDERS" --sibling-repos "$SIBLING_REPOS" --autoloop
```

Substitute the values collected in step 3. Omit flags the user didn't set
or left at smart defaults (the CLI applies preset defaults for unset flags).
`$TARGETS` is the comma-joined multi-select — e.g. `claude-code`,
`claude-code,cursor`, or `claude-code,cursor,codex`.

### 5. Report + Quick start

After dispatch, summarize what changed:
- Files: how many REPLACE / MERGE_BLOCK / KEEP (the CLI prints this)
- Whether the chosen intent landed (e.g., "preset is now Production")
- Backup directory path for recovery

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
