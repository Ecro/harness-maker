# harness-maker

A Claude Code plugin that **generates and refines a project-tailored `.claude/` harness** — commands, skills, agents, hooks, and observability — tuned to your stack, scale, and lifecycle. It does not run your project code; it builds the runtime that does. Anti-rot keeps the harness fresh against the moving Claude Code ecosystem; worktree isolation and 5 security gates keep it safe; built-in monitoring (효율 / Health / fresh) keeps it honest.

## Requirements

- **Python 3.12+ and `uv`** are required in your project's environment, even if your project's primary toolchain is Rust, Node, Go, or anything non-Python. This is because the rendered harness wires hooks (e.g. `permission_gate`, `spec_gate`, `telemetry`) that execute via `uv run python -m harness_maker.gates.<name>` at PreToolUse/PostToolUse boundaries.
  - Easiest: install [`uv`](https://docs.astral.sh/uv/) once, then `uv tool install harness-maker` (or add as a dev dep via `uv sync`) so the `harness_maker` Python package resolves on every Claude Code invocation.
  - You can disable hooks selectively: `dev_mode: task-driven` in `harness.yaml` skips `spec_gate`; commenting out an entry in `.claude/hooks/hooks.json` skips that hook. The harness still works without any hook installed.
  - A self-contained binary distribution that removes the Python+uv requirement is on the roadmap; until then, treat harness-maker as a Python dev dep of your project.
- **Claude Code CLI** (any recent version with plugin + hook support).
- **Git** (worktree isolation in Production preset uses `git worktree add`).

## Quick Start

```bash
uv sync
claude --plugin-dir .
/harness-maker:make
```

A single command takes you from zero to a fully-rendered `.claude/` directory with workflow stages, reviewer agents, anti-rot pipeline, and a status line wired up. Re-run with flags to evolve the harness:

- `/harness-maker:make --audit` — score the existing `.claude/` against the rubric
- `/harness-maker:make --add NAME` — graft on a single skill/agent/command
- `/harness-maker:make --remove NAME` — surgically remove one component
- `/harness-maker:make --promote NAME` — move an ad-hoc artifact into the harness

After install, the rendered harness exposes its own commands under `/hm:*`:

- `/hm:loop "<goal>"` — autoloop driver (token-unbounded, time/iter-bounded)
- `/hm:monitor` — open the dashboard
- `/hm:refresh` — anti-rot crawl + manual confirm
- `/hm:research` · `/hm:spec` · `/hm:plan` · `/hm:execute` · `/hm:review` · `/hm:wrapup` · `/hm:verify` — atomic stages
- Plus user-named workflows fused from those stages (e.g. `/hm:dev`, `/hm:careful`)

## Features

- **Single command, no subcommand sprawl** — `/harness-maker:make` is the only entry point. Everything else is a flag.
- **Two presets, ten+ override dimensions** — pick `Side` (1 reviewer, lean) or `Production` (5 reviewers, verify-required); then tune workflow naming, models, autoloop, anti-rot, worktree, security, context-lint, memory, caching.
- **Three live metrics** — 효율 (cache hit %), Health (0-100 across 6 dimensions + Agent quality drill-down), fresh (days since refresh). All telemetry stays local.
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
| **superpowers** | Powerful sub-agents and workflows | Single-command entry, monitoring (3 metrics), worktree isolation by default, privilege-separated reviewer/executor |
| **Archon** | Knowledge-base + RAG-backed planning | Stack/scale/lifecycle profiler, atomic+fused workflow engine, conditional reviewer routing, 5 security gates |

harness-maker treats the `.claude/` directory itself as the artifact and gives it a lifecycle: profile → interview → synthesize → render → reconcile → verify → refresh.

## Marketplace

> Marketplace listing coming soon. The plugin manifest at `.claude-plugin/plugin.json` is marketplace-ready (Claude Code marketplace spec: <https://code.claude.com/docs/en/plugin-marketplaces>).
>
> Until then, install locally with `claude --plugin-dir .` from the repo root.

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
