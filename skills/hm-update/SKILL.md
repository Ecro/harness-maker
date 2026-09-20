---
name: hm-update
description: Update the installed harness-maker Codex plugin, its matching Python engine, and the current project's generated harness while preserving user configuration.
---

Resolve the installed plugin root from this skill file: two parent directories above `skills/hm-update/`. Use the requested project directory and existing configuration. Python 3, uv, and a Codex CLI supporting `plugin marketplace upgrade` and `plugin add` must be available.

Run `python3 "<installed-plugin-root>/scripts/codex_setup.py" update "<project>"`. If installed from a differently named marketplace, pass its actual name with `--marketplace`. The script refreshes the registered marketplace, reinstalls `harness-maker@<marketplace>`, reads the returned installed root/version, and runs the new package's helper with its matching published engine to regenerate the project.

Inspect `plugin`, `engine`, `project`, and `pending` independently. Only `state: complete` means all three match. On failure, report the fixed error code and completed/pending layers; resolve the cause before retrying. Do not fall back to an unpinned engine or report marketplace refresh alone as completion. Existing projects keep their targets and custom blocks. For a project without a harness, use hm-make first.

Start a new Codex thread to reload refreshed skills. Development cachebusters identify local plugin builds; the engine still uses the underlying stable release. A missing published release is an explicit failure, not permission to use a different engine.
