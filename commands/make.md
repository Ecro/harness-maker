# /harness-maker:make

Generate or refine a project-tailored Claude Code harness at `<cwd>/.claude/`.

## Usage

```
/harness-maker:make [target] [--reinterview] [--autoloop] [--add NAME] [--remove NAME] [--add-domain NAME]
```

`target` defaults to the current working directory.

## Behavior

The command runs the `harness_maker.cli make` Typer entry point. The flow
adapts to whether a prior harness exists:

| State | Behavior |
|---|---|
| No `<target>/.claude/harness.yaml` (fresh install) | Interactive interview unless `--autoloop` is passed |
| Existing `<target>/.claude/harness.yaml` (re-render) | **Silently reuses prior answers** — no prompts, no `--autoloop` needed |
| `--reinterview` flag | Forces fresh interview even when harness.yaml exists |

Re-render preserves: `locale`, `preset`, `dev_mode`, custom workflow names +
stages, `default_workflow`, `consensus`, `caching`, enabled reviewers/skills,
and the v0.3.0+ review-stage knobs (`auto_fix`, `grade_threshold`,
`max_review_rounds`). Block-marker user content (`<!-- @hm:user:* -->`) is
preserved by reconcile/render — separately from interview reuse.

## Run

Resolve the plugin's install path from `~/.claude/plugins/installed_plugins.json`
and invoke the CLI. Pass through `$ARGUMENTS` so flags like `--reinterview`
or `--add-domain` reach the typer entry point.

```bash
!plugin_dir=$(python3 -c "
import json, pathlib
data = json.load(open(pathlib.Path.home() / '.claude/plugins/installed_plugins.json'))
entries = data['plugins']['harness-maker@harness-maker-local']
# Prefer the entry whose projectPath matches the current cwd; else first.
import os
cwd = os.getcwd()
match = next((e for e in entries if e.get('projectPath') == cwd), entries[0])
print(match['installPath'])
")
uv run --directory "$plugin_dir" python -m harness_maker.cli make "$@"
```

## Notes

- On re-render, the CLI prints `reusing settings from .claude/harness.yaml`
  so the user can see prior answers were honored.
- `--autoloop` only applies on first install (no harness.yaml yet) — there it
  uses preset-derived defaults silently.
- `--reinterview` is the escape hatch: forces a full fresh interview even
  when an existing harness.yaml is present. Useful when the user wants to
  change `locale`, `preset`, or `dev_mode`.
- Modular flags `--add reviewer:<name>` / `--remove reviewer:<name>` /
  `--add-domain <name>` apply on top of the (reused or fresh) answers.
