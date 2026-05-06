# harness-maker

A plugin for **Claude Code and Cursor IDE** that **generates and refines a project-tailored `.claude/` harness** — commands, skills, agents, hooks, and observability — tuned to your stack, scale, and lifecycle. It does not run your project code; it builds the runtime that does. Anti-rot keeps the harness fresh against the moving Claude Code / Cursor ecosystem; worktree isolation and 5 security gates keep it safe; `/hm:ai-readiness` gives a scored, ranked action plan for improving AI-pair quality.

Single-source `.claude/` (agents / skills / hooks / commands) works in both IDEs; opt into the `cursor` target during the interview to additionally render `.cursor/rules/harness.mdc` and `.cursor/mcp.json`.

## Requirements

- **Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)** must be available wherever Claude Code runs against your project, even if the project's primary toolchain is Rust, Node, Go, or any non-Python language. The rendered harness installs hooks (`permission_gate`, optionally `spec_gate`, plus `telemetry`) that invoke `uv run python -m harness_maker.gates.<name>` at PreToolUse/PostToolUse boundaries; without `uv` + the `harness_maker` package on the path those hooks are silent no-ops.
  - **Today (pre-PyPI):** clone this repo and install editable into your project: `uv pip install -e /path/to/harness-maker`. Then load the plugin with `claude --plugin-dir /path/to/harness-maker`. PyPI publish is on the open-question list; until it lands, editable from a clone is the only supported install.
  - **Disabling hooks selectively:** set `dev_mode: task-driven` in `.claude/harness.yaml` to skip `spec_gate`; remove an entry from `.claude/hooks/hooks.json` to skip any hook. The base harness keeps working with no hooks installed.
- **Claude Code CLI** (with plugin + hook support) **and/or Cursor IDE 2.4+** — Cursor reads `.claude/agents/`, `.claude/skills/`, and Claude Code-format hooks natively (subagents + skills support shipped in Cursor 2.4). Opt into Cursor-specific assets (`.cursor/rules/`, `.cursor/mcp.json`) via the `targets` interview question.
- **Git** — every worktree-enabled preset (default for both `Side` and `Production`; opt out via `worktree.scope: []` in `harness.yaml`) uses `git worktree add` for `/hm:execute`.

## Quick Start

```bash
uv sync
claude --plugin-dir .
/harness-maker:make
```

A single command takes you from zero to a fully-rendered `.claude/` directory with workflow stages, reviewer agents, anti-rot pipeline, and a status line wired up. The interview asks for IDE `targets` — choose `claude-code`, `cursor`, or both (comma-separated). Single-source assets work in either IDE; Cursor-specific files are rendered only if `cursor` is selected.

Re-run with flags to evolve the harness:

- `/harness-maker:make --audit` — score the existing `.claude/` against the rubric
- `/harness-maker:make --add NAME` — graft on a single skill/agent/command
- `/harness-maker:make --remove NAME` — surgically remove one component
- `/harness-maker:make --promote NAME` — move an ad-hoc artifact into the harness

After install, the rendered harness exposes its own commands under `/hm:*`:

- `/hm:loop "<goal>"` — autoloop driver (token-unbounded, time/iter-bounded)
- `/hm:ai-readiness` — scored 3-layer readiness report + ranked action plan
- `/hm:refresh` — anti-rot crawl + manual confirm
- `/hm:research` · `/hm:spec` · `/hm:plan` · `/hm:execute` · `/hm:review` · `/hm:wrapup` · `/hm:verify` — atomic stages
- Fused workflows (stage combos, renameable at install):
  - **Side defaults:** `/hm:exec-rev` · `/hm:exec-rev-wrap` _(default)_ · `/hm:plan-exec-rev-wrap`
  - **Production defaults:** `/hm:exec-rev-wrap-ver` _(default)_ · `/hm:exec-rev-wrap` · `/hm:exec-rev` · `/hm:res-spec-plan`

## Features

- **Dual IDE — Claude Code + Cursor** — single-source `.claude/agents/`, `.claude/skills/`, `.claude/commands/`, and `.claude/hooks/hooks.json` drive both IDEs (Cursor 2.4+ reads `.claude/` natively). Opt into the `cursor` target to additionally render `.cursor/rules/harness.mdc` (always-on workflow rules) and `.cursor/mcp.json`. IDE-compatibility verification fixture under `tests/cursor-compat/` (`MANUAL_CHECKLIST.md` + `RESULTS.md`) for release-time regression checks.
- **Single command, no subcommand sprawl** — `/harness-maker:make` is the only entry point. Everything else is a flag.
- **Two presets, ten+ override dimensions** — pick `Side` (1 reviewer, lean) or `Production` (5 reviewers, verify-required); then tune workflow naming, models, autoloop, anti-rot, worktree, security, context-lint, memory, caching.
- **AI-readiness scoring** — `/hm:ai-readiness` runs a 3-layer composite: deterministic structural checks (70%), LLM rubric evaluation (25%), prompt-cache diagnostics (5%). Outputs a 0-100 score with P0/P1/P2 ranked actions and updates `.claude/observability/dashboard.md`. All telemetry stays local.
- **Anti-rot pipeline** — weekly crawl across 4 sources (Anthropic blog/changelog, GitHub releases, arxiv cs.SE/CL/CR, OSV.dev), LLM-scored with adaptive threshold, **always manual-confirmed** via `AskUserQuestion`. No silent overwrites.
- **Worktree isolation** — every `/hm:execute` (and optionally `/hm:plan`) runs in a fresh `git worktree` under `.claude/.worktrees/`. Successful runs cleanup; failures preserve evidence.
- **5 security gates** — secrets (regex + entropy), permissions (`settings.json` over-grant), hook injection (`hooks.json` AST scan), dependency CVEs (OSV.dev), prompt injection (hidden-instruction detection + privilege separation between reviewer and executor agents).
- **Brownfield-safe** — `Reconciler` indexes existing `.claude/`, hashes via provenance frontmatter, and offers per-conflict keep/replace/both. ADD-only apply with timestamped backups.
- **Provenance frontmatter** — every generated `.md`/`.json` carries `generated_by`, `harness_maker_version`, `content_hash`, `source_template`, `generated_at`, `provenance`. User edits are detected and never silently overwritten.

## How It Compares

Other Claude Code harnesses pick a niche; harness-maker is the **meta-tool** that builds them.

| Project | Scope | What harness-maker adds |
|---|---|---|
| **ohmyclaudecode** | Curated commands/agents (skills bundle) | Project-tailored synthesis (preset + 10+ override dims), brownfield reconcile, provenance, anti-rot pipeline |
| **superpowers** | Powerful sub-agents and workflows | Single-command entry, ai-readiness scoring, worktree isolation by default, privilege-separated reviewer/executor |
| **Archon** | Knowledge-base + RAG-backed planning | Stack/scale/lifecycle profiler, atomic+fused workflow engine, conditional reviewer routing, 5 security gates |

harness-maker treats the `.claude/` directory itself as the artifact and gives it a lifecycle: profile → interview → synthesize → render → reconcile → verify → refresh.

## Cursor target

Run `/harness-maker:make` and pick `targets: [cursor]` or `[claude-code, cursor]` at the interview. The renderer adds:

- `.cursor/rules/harness.mdc` — always-on workflow rules (LLM-first design, agent dispatch, slash commands, security gates, models, memory, anti-rot — Cursor frontmatter `description` / `globs: []` / `alwaysApply: true`)
- `.cursor/mcp.json` — Cursor MCP server config (default `{"mcpServers": {}}`, user-tunable)

`.claude/agents/`, `.claude/skills/`, `.claude/commands/`, and `.claude/hooks/hooks.json` are single-source — Cursor 2.4+ reads them natively, so the same files drive both IDEs without duplication.

### Reconcile KEEP rule trade-off (read before re-rendering)

Re-running `/harness-maker:make` against an existing harness uses a hash-driven KEEP rule that protects user edits. Trade-off: when harness-maker bumps a template (e.g. adds a yaml key on a minor release), the existing file's `content_hash` frontmatter no longer matches the new template's hash, so reconcile picks **KEEP** even if you didn't edit the file — the rendered yaml stays on the old template.

To pick up template updates manually after a harness-maker bump:

```bash
# Force-update the harness manifest after bumping harness-maker version:
rm .claude/harness.yaml
/harness-maker:make
# (the previous file is auto-backed up to .backup-<ISO>/.claude/harness.yaml)
```

Cursor's `.cursor/rules/*.mdc` follow the same KEEP behavior (no `content_hash` frontmatter, to avoid Cursor's strict-reject of unknown keys). A future phase introduces a sidecar `.hm-meta.yaml` so harness-maker can hash-track Cursor assets without polluting the Cursor frontmatter.

### Recommended model

`harness.yaml.recommended_model` defaults to `claude-opus-4-7` and propagates to agent frontmatter. Cursor users may override model selection in their IDE, but prompts contain Claude-specific patterns (`<thinking>` blocks, role framing) so quality may degrade on other models. The harness does **not** model-agnostically rewrite prompts — that's a deliberate tradeoff in favor of polish on the recommended model.

### Verification

For first-release dogfooding and per-release regression:

- `tests/cursor-compat/MANUAL_CHECKLIST.md` — A1–A4 (agent dispatch, hook fire, skill auto-discovery, slash command + Q&A loop) + Phase 2.8 (production hook command runs) covering both IDEs.
- `tests/cursor-compat/RESULTS.md` — meta + PASS/FAIL/PARTIAL grid you fill while running the checklist.
- `tests/cursor-compat/fixture/` — minimal `.claude/` for opening directly in either IDE (gitignore protects against IDE-generated metadata pollution).

## Marketplace

Both manifests are marketplace-ready:

- `.claude-plugin/plugin.json` — Claude Code marketplace spec: <https://code.claude.com/docs/en/plugin-marketplaces>
- `.cursor-plugin/plugin.json` — Cursor Marketplace spec: <https://cursor.com/docs/plugins/building>; submit at <https://cursor.com/marketplace/publish>

Listing on either marketplace is pending. Until then, install locally with `claude --plugin-dir .` from the repo root, or open the repo as a folder in Cursor and use it as a workspace plugin.

## Development

```bash
uv sync
uv run pytest                       # full suite
uv run ruff check src/ tests/       # lint
uv run ruff format src/ tests/      # format
uv run mypy --strict src/           # type
bash .claude-verify.sh all          # phase-by-phase exit criteria + final acceptance
```

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for adding skills/agents/presets and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the 13 mechanisms (M1-M13) behind the system.

## License

MIT — see [LICENSE](LICENSE).
