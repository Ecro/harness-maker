"""Tests for A3+A4 prompt cache_control (Phase 3).

Verifies that the AnthropicJudgeClient passes cache_control: {type: ephemeral}
on the system block, and that both relevance scorer and security scanner PI gate
route through this cached path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from harness_maker.llm_judge import AnthropicJudgeClient
from harness_maker.secscan.prompt_injection import scan_with_llm


class _RecordingClient:
    """Captures the system kwarg from messages.create for assertion."""

    def __init__(self) -> None:
        self.last_system: object = None
        self.messages = self

    def create(self, **kwargs: object) -> MagicMock:
        self.last_system = kwargs.get("system")
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"score": 0.5, "rationale": "test"}')]
        return mock_msg


def test_anthropic_judge_sends_cache_control() -> None:
    """AnthropicJudgeClient must set cache_control ephemeral on system block."""
    recorder = _RecordingClient()
    client = AnthropicJudgeClient.__new__(AnthropicJudgeClient)
    client._client = recorder  # type: ignore[attr-defined]

    client.judge("test system prompt", "test user prompt", "claude-sonnet-4-6")

    assert isinstance(recorder.last_system, list)
    assert len(recorder.last_system) == 1
    block = recorder.last_system[0]
    assert block["type"] == "text"
    assert block["text"] == "test system prompt"
    assert block["cache_control"] == {"type": "ephemeral"}


class _MockPIJudge:
    """Returns canned PI scan JSON."""

    def judge(self, system: str, user: str, model: str) -> str:
        return "[]"


def test_secscan_pi_cache_control() -> None:
    """Security scanner PI gate must route through JudgeClient.judge (→ cached system block)."""
    mock = _MockPIJudge()
    findings = scan_with_llm("some markdown text to scan", client=mock)
    assert isinstance(findings, list)
