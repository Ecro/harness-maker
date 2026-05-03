# harness-maker

Project-tailored Claude Code harness generator with anti-rot, monitoring, and autoloop integration.

## Purpose

`harness-maker` is a meta-tool: a Claude Code plugin that generates and refines a per-project `.claude/` harness (commands, skills, agents, hooks, observability) tuned to the project's stack, scale, and lifecycle. It does not run your project code — it builds the runtime that does.

## Quick Start

> Phase 1 skeleton — full workflow lands in Phase 2+.

Once installed as a Claude Code plugin:

```
/harness-maker:make
```

Flags (all Phase 2+):

- `--audit` — audit the existing `.claude/` structure
- `--add NAME` — add a component
- `--remove NAME` — remove a component
- `--promote NAME` — promote a component to the harness

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run mypy --strict src/
```

## License

MIT — see [LICENSE](LICENSE).
