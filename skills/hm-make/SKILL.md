---
name: hm-make
description: Set up a project's harness from the installed Codex plugin, using its matching Python engine and generating Codex agents and workflow skills.
---

Resolve the installed plugin root from this skill file: two parent directories above `skills/hm-make/`. Use that absolute path; do not search another runtime's cache.

Use the requested project directory. Reuse existing configuration. For a new project, collect any missing meaningful preferences (Side or Production preset, locale, task-driven or spec-driven); respect preferences already given. The script requires Python 3 and uv on PATH.

Run `python3 "<installed-plugin-root>/scripts/codex_setup.py" make "<project>"` with explicit `--preset`, `--locale`, and `--dev-mode` when chosen. The bundled bootstrap selects the published engine version matching the plugin release and generates Codex assets through the engine's normal generator.

Read the JSON receipt. Report completion only when `state` is `complete`; otherwise identify the pending layers and fixed error code. Do not interpret plugin installation alone as project setup. Preserve existing targets and custom blocks. Start a new Codex thread if newly generated skills are not yet discovered.
