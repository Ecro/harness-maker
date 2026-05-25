"""Static guard for the plugin-level /harness-maker:make resolver."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKE_COMMAND = REPO_ROOT / "commands" / "make.md"


def test_make_command_uses_canonical_locate_resolver() -> None:
    text = MAKE_COMMAND.read_text(encoding="utf-8")

    assert "harness_maker.cli locate --plain" in text
    assert "projectPath==cwd > user scope > installedAt" in text


def test_make_command_has_no_entries_zero_fallback() -> None:
    text = MAKE_COMMAND.read_text(encoding="utf-8")

    assert "entries[0]" not in text
    assert "harness-maker@harness-maker-local" not in text
