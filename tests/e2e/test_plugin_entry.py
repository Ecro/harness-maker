"""Plugin entry e2e — apply harness-maker via the CLI to a separate sandbox.

Validates that:
- ``.claude-plugin/plugin.json`` exists at repo root (Phase 1 plugin manifest).
- Running ``python -m harness_maker.cli make`` against ``sandbox-plugin-test``
  produces an equivalent ``.claude/`` tree to the regular CLI entry, exercising
  the same code path the Claude Code plugin will route to.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SANDBOX = REPO_ROOT / "tests" / "e2e" / "sandbox-plugin-test"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"


def _ensure_plugin_sandbox() -> None:
    """Create a minimal Python project + git init for the plugin entry test."""
    PLUGIN_SANDBOX.mkdir(parents=True, exist_ok=True)
    pyproject = PLUGIN_SANDBOX / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(
            '[project]\nname = "sandbox-plugin-test"\nversion = "0.1.0"\n'
            'requires-python = ">=3.12"\n',
            encoding="utf-8",
        )
    hello = PLUGIN_SANDBOX / "hello_world.py"
    if not hello.exists():
        hello.write_text(
            'def main() -> None:\n    print("hello, plugin sandbox")\n',
            encoding="utf-8",
        )
    if not (PLUGIN_SANDBOX / ".git").exists():
        subprocess.run(  # noqa: S603,S607
            ["git", "init", "-b", "main"],
            cwd=PLUGIN_SANDBOX,
            check=True,
            capture_output=True,
        )


def test_plugin_manifest_exists() -> None:
    """``.claude-plugin/plugin.json`` is the Phase 1 plugin entry artifact."""
    assert PLUGIN_MANIFEST.is_file(), (
        f"plugin manifest missing at {PLUGIN_MANIFEST} — Phase 1 deliverable"
    )


def test_plugin_entry_make_writes_harness_yaml() -> None:
    """Running the CLI against sandbox-plugin-test must produce .claude/harness.yaml.

    This is the same code path the Claude Code plugin (plugin.json) routes
    ``/harness-maker:make`` to, so we exercise it directly via subprocess for
    e2e isolation rather than driving Claude Code itself.
    """
    _ensure_plugin_sandbox()

    cp = subprocess.run(  # noqa: S603
        [
            "uv",
            "run",
            "python",
            "-m",
            "harness_maker.cli",
            "make",
            str(PLUGIN_SANDBOX),
            "--autoloop",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, (
        f"plugin-entry make failed: rc={cp.returncode}\n"
        f"stdout={cp.stdout}\nstderr={cp.stderr}"
    )

    harness_yaml = PLUGIN_SANDBOX / ".claude" / "harness.yaml"
    assert harness_yaml.is_file(), (
        f"missing harness.yaml after plugin-entry make: {harness_yaml}"
    )

    # Sanity: the plugin entry must produce the same minimum file count as the
    # regular CLI entry (≥25 per phase_11_apply gate).
    file_count = sum(1 for _ in (PLUGIN_SANDBOX / ".claude").rglob("*") if _.is_file())
    assert file_count >= 25, (
        f"plugin-entry make produced {file_count} files, expected ≥25"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
