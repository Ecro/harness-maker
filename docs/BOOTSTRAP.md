# Bootstrapping harness-maker in a fresh project

Canonical onboarding reference for **Claude Code**, **Cursor**, and **Codex CLI**.
Paste the IDE-matching snippet into your agent's onboarding meta-prompt instead
of re-implementing a plugin-cache resolver — that path is a known footgun (see
[Anti-pattern](#anti-pattern-do-not-do-this) below).

> **Why this exists:** the `~/.claude/plugins/installed_plugins.json` file
> accumulates many cached versions over time (one per project that ever installed
> harness-maker). A naive resolver that picks `entries[0]` or sorts by glob can
> silently bind to an old version's CLI, then every command in the bootstrap
> fails with cryptic "unknown command/option/skill" errors. Use
> `harness-maker locate` so the resolution rules are centralized.

---

## Step 1 — Install the plugin (per IDE)

### Claude Code

```bash
claude plugin marketplace add Ecro/harness-maker
claude plugin install harness-maker@harness-maker
```

Then in Claude Code, run `/reload-plugins` once. After that, the plugin's CLI
is available as `harness-maker` (and `python -m harness_maker.cli`) within
`uv run --with` invocations resolved through the install path.

### Cursor

```bash
git clone --depth 1 https://github.com/Ecro/harness-maker.git \
    ~/.cursor/plugins/local/harness-maker
```

Then reload the Cursor window (`Ctrl+Shift+P` → **Reload Window**) so it picks
up the plugin's skills, agents, and commands.

> **Note for Cursor users:** the git-clone install does NOT write to
> `~/.claude/plugins/installed_plugins.json` (which is Claude Code's plugin
> registry). Therefore `harness-maker locate` (Step 2) will return exit 3 in
> this setup. For Cursor-only environments, use the cloned path directly:
> ```bash
> HM_DIR="$HOME/.cursor/plugins/local/harness-maker"
> ```
> Then skip to Step 4. If you also use Claude Code from the same machine, the
> Claude Code install will satisfy `locate` for both IDEs.

### Codex CLI

**Recent Codex CLI (verified on 0.144.4) installs this plugin natively** — `codex plugin marketplace add Ecro/harness-maker` then `codex plugin add harness-maker@harness-maker` succeeds, cloning the repo into `~/.codex/plugins/cache/`. But that clone does **not** install the Python engine (`harness-maker` / `python -m harness_maker`) that renders the harness — so native `plugin add` alone is not enough. Install the engine via one of the two paths below (a native `codex plugin add` is optional on top):

**A. Claude Code marketplace (if Claude Code is on the same machine):**

```bash
claude plugin marketplace add Ecro/harness-maker
claude plugin install harness-maker@harness-maker
```

This is the canonical path — the rendered `.codex/` artifacts reference the Python source cached under `~/.claude/plugins/cache/harness-maker-local/`.

**B. PyPI (Codex-only, no Claude Code subscription):**

```bash
uv tool install harness-maker
```

The `harness-maker` CLI is installed via `uv`; `harness-maker make` then renders `.codex/` artifacts that reference the uv-tool install path. Codex CLI does NOT need a plugin reload step — `.codex/` artifacts are pure files on disk that Codex reads at session start.

---

## Step 2 — Resolve the active install (the one-line bootstrap)

After Step 1, your agent script needs to know **where** the just-installed
plugin lives on disk so it can `uv run --with <path>` against it. Use the
`locate` subcommand — it is the single source of truth.

```bash
# Plain installPath — for shell scripts that just need the directory.
HM_DIR=$(harness-maker locate --plain) || { echo "harness-maker not installed"; exit $?; }
echo "active plugin: $HM_DIR"
```

```bash
# Structured output — for agents that need version + scope + marketplace.
harness-maker locate
# {
#   "marketplace": "harness-maker",
#   "version": "0.20.0",
#   "scope": "user",
#   "installPath": "/home/.../cache/harness-maker/harness-maker/0.20.0",
#   "gitCommitSha": "...",
#   "installedAt": "..."
# }
```

### Resolution rules

`harness-maker locate` walks `~/.claude/plugins/installed_plugins.json` and
picks the highest-priority entry for the active cwd:

| Tier | Rule | Wins when… |
|------|------|------------|
| 1 | `projectPath == cwd` | The current project has its own pinned project-scope install |
| 2 | `scope == "user"` | Falls back to the user-global install |
| —  | `installedAt` desc | Tiebreak within the same tier (most recent wins) |

No tier-3 fallback to "most recent project-scope of another project" — that
would silently re-introduce the kairos@0.7.3 footgun (see Anti-pattern below).
Resolver returns nothing (`exit 3`) when neither tier-1 nor tier-2 matches;
the correct fix is to install the plugin to user scope, not to silently bind
some other project's pinned version.

---

## Step 3 — Fail fast on stale versions

Pair `locate` with `--require-version X.Y` so the bootstrap stops with a clear
message when the active install is too old to satisfy your script's
expectations. Semantics: `>=X.Y` only.

```bash
harness-maker locate --plain --require-version 0.20 || exit $?
# On mismatch, stderr reads:
#   harness-maker installed=0.7.3 required=>=0.20 — run: claude plugin update harness-maker
# and the process exits with code 2.
```

### Exit codes (stable contract)

| Code | Meaning | Recovery (Claude Code / Cursor / Codex) |
|------|---------|------------------------------------------|
| 0 | Found and (if requested) version OK | proceed |
| 2 | Version mismatch — installed is older than `--require-version X.Y` | Claude Code: `claude plugin update harness-maker` · Cursor (git clone): `git -C ~/.cursor/plugins/local/harness-maker pull` · Codex: `codex plugin update harness-maker` |
| 3 | No installed plugin entry found for cwd | Install per Step 1 above for your IDE, or install user-scope: `claude plugin install harness-maker@harness-maker` |

Use `exit 2` and `exit 3` in your shell branches when handling the failure
cases — they are stable across harness-maker minor versions:

```bash
harness-maker locate --require-version 0.20
case $? in
  0) echo "active install OK" ;;
  2) echo "stale install — please update" ;;
  3) echo "no install — please install harness-maker" ;;
esac
```

Both `locate` and `make` accept `--require-version`. The `make` gate fires
**before any disk writes**, so a stale-version bootstrap never partially
creates a `.claude/`.

---

## Step 4 — Drive the interview

Once Steps 1–3 succeed, hand control to harness-maker's own slash command:

```text
/harness-maker:make    # in Claude Code or Cursor
```

or, from a shell:

```bash
harness-maker make .
```

Subsequent stage commands (`/hm:plan`, `/hm:execute`, `/hm:review`, ...) become
available after the make completes.

---

## Anti-pattern (do NOT do this) <!-- ANTI-PATTERN: legacy-resolver -->

The following pattern appears in many older onboarding meta-prompts and
**silently picks the wrong plugin version**. Treat it as a regression:

```python
# ❌ BROKEN — picks entries[0] when cwd is not in the entry list,
#    which happens on every first-install of a NEW project.
import json, pathlib, os
data = json.load(open(pathlib.Path.home() / '.claude/plugins/installed_plugins.json'))
plugins = data.get('plugins', {})
for key in ['harness-maker@harness-maker-local', 'harness-maker@harness-maker']:
    if key in plugins:
        entries = plugins[key]
        break
cwd = os.getcwd()
match = next((e for e in entries if e.get('projectPath') == cwd), entries[0])  # ← BUG
plugin_dir = match['installPath']  # → wrong version from some unrelated project
```

**What goes wrong**: when the current project is not in the entries list
(typical fresh install), the `next(..., entries[0])` fallback returns the
FIRST entry across **all** other projects — which may be an ancient pinned
version (e.g., `kairos@0.7.3` from 2026-01-01). Every downstream command in
the bootstrap then 404s because the old CLI doesn't have the subcommands /
flags / skills the script expects.

**Fix**: replace the whole resolver with one call:

```bash
HM_DIR=$(harness-maker locate --plain --require-version 0.20) || exit $?
```

---

## Migrating from legacy meta-prompts

If your onboarding script currently embeds the anti-pattern resolver, swap it
out as follows.

### Bash (most common)

**Before** (buggy — re-implements resolver):

```bash
plugin_dir=$(python3 -c "...30-line resolver...")
```

**After** (use the canonical `locate` CLI):

```bash
plugin_dir=$(harness-maker locate --plain --require-version 0.20) || exit $?
```

### Python (in-agent helper)

**Before** (manual JSON parsing):

```python
import json, pathlib, os
data = json.load(open(pathlib.Path.home() / '.claude/plugins/installed_plugins.json'))
# ...30 lines of resolver logic...
```

**After** (delegate to the CLI):

```python
import subprocess, json
entry = json.loads(subprocess.check_output(["harness-maker", "locate"]))
plugin_dir = entry["installPath"]
# Optional: require a minimum version
subprocess.check_call(["harness-maker", "locate", "--require-version", "0.20"])
```

After migrating, re-run your bootstrap once on a fresh project to confirm the
new flow exits cleanly when `--require-version` is satisfied.

---

## See also

- [`PLAN-locate-cli-version-gate.md`](../work-docs/PLAN-locate-cli-version-gate.md)
  — the design history (ADRs explain why JSON-default, why no separate `check`
  subcommand, why this doc instead of a `/hm:bootstrap` slash command).
- [`CHANGELOG.md`](../CHANGELOG.md) — `locate` shipped in `0.20.0`.
