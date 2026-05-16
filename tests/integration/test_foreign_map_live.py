"""Live integration test for ``foreign_config.llm_map`` (Phase 6).

Gated by ``INTEGRATION=1`` per CLAUDE.md §테스트 정책. For each of the six
golden fixtures, calls the real Anthropic API and asserts the response
parses to ``AxisMapping`` with at least one mapping. NOT brittle exact-match
— the LLM is allowed to surface any sensible axis from the file.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_maker.foreign_config import (
    AxisMapping,
    ForeignConfig,
    llm_map,
)
from harness_maker.models import Confidence

_INTEGRATION_ENABLED = os.environ.get("INTEGRATION") == "1"


_FIXTURE_BY_TYPE: dict[str, tuple[str, str]] = {
    "cursor_rules": ("cursor_rules.mdc", ".cursor/rules/main.mdc"),
    "claude_md": ("claude_md.md", "CLAUDE.md"),
    "codex_agents": ("agents_md.md", "AGENTS.md"),
    "continue": ("continue_config.json", ".continue/config.json"),
    "aider": ("aider_conf.yml", ".aider.conf.yml"),
    "copilot": ("copilot_instructions.md", ".github/copilot-instructions.md"),
}


@pytest.mark.skipif(not _INTEGRATION_ENABLED, reason="INTEGRATION=1 required for live LLM tests")
@pytest.mark.parametrize("type_label", list(_FIXTURE_BY_TYPE.keys()))
def test_llm_map_live_for_each_type(tmp_path: Path, type_label: str) -> None:
    fixture_name, target_rel = _FIXTURE_BY_TYPE[type_label]
    src = Path(__file__).parent.parent / "unit" / "fixtures" / "foreign_configs" / fixture_name
    body = src.read_bytes()
    target = tmp_path / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    fc = ForeignConfig(
        path=target_rel,
        type=type_label,
        size=len(body),
        confidence=Confidence.HIGH,
    )
    result = llm_map(fc, tmp_path)
    assert isinstance(result, AxisMapping)
    assert len(result.mappings) >= 1, f"expected ≥1 axis mapping for {type_label}, got 0"
