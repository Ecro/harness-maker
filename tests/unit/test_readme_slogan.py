"""SPEC-readme-slogan: the pre-registered slogan is in both READMEs; no stale not-shipped line."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
#: Fixed by intent/UNDERSTANDING-HANDOFF.md's pre-registered rule.
_SLOGAN = "Automate the work. Elevate the engineer."


@pytest.mark.parametrize("readme", ["README.md", "README.ko.md"])
def test_ac_001_readme_has_slogan_and_no_stale_line(readme: str) -> None:
    text = (_ROOT / readme).read_text(encoding="utf-8")
    assert 0 <= text.find(_SLOGAN) < text.find("> **Version**:"), readme
    assert "Not shipped yet" not in text, readme
    assert "아직 출하 전" not in text, readme
