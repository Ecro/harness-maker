"""SPEC-retired-text AC-007: the docs describe Maker without the retired autopilot grant."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_ac_007_docs_describe_maker_without_autopilot_grant() -> None:
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    texts = {
        "CLAUDE.md#World model": _section(claude, "## World model (Maker)"),
        "docs/ARCHITECTURE.md": (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8"),
        "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
        "README.ko.md": (ROOT / "README.ko.md").read_text(encoding="utf-8"),
    }
    assert {name for name, text in texts.items() if "autopilot narrow" in text} == set()
    world = (ROOT / "docs/reference/world-model.md").read_text(encoding="utf-8")
    assert "autopilot narrow:*" not in world
    assert "Maker runs `hm autopilot narrow" not in world
    assert "active Maker runs `hm autopilot narrow" not in world
