#!/usr/bin/env bash
# harness-maker statusline wrapper.
#
# Resolves the plugin install path at runtime so the command keeps working
# across plugin upgrades without re-rendering settings.json. Reads the
# project-scoped install (matched on `projectPath == cwd`) when present,
# otherwise falls back to the first registered install.

set -euo pipefail

plugin_dir=$(python3 - <<'PY' 2>/dev/null
import json
import os
import pathlib
import sys

manifest = pathlib.Path.home() / ".claude/plugins/installed_plugins.json"
if not manifest.exists():
    sys.exit(0)
data = json.loads(manifest.read_text(encoding="utf-8"))
entries = data.get("plugins", {}).get("harness-maker@harness-maker-local", [])
if not entries:
    sys.exit(0)
cwd = os.getcwd()
match = next((e for e in entries if e.get("projectPath") == cwd), entries[0])
print(match.get("installPath", ""))
PY
)

if [ -z "$plugin_dir" ] || [ ! -d "$plugin_dir" ]; then
    # Plugin not installed or manifest unreadable — emit nothing so Claude
    # Code's statusline area stays clean instead of showing an error.
    exit 0
fi

exec uv run --directory "$plugin_dir" python -m harness_maker.statusline "$@"
