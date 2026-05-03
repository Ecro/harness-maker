"""Agent quality scoring tests (per amendment §G)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.agent_quality import score_agent


class _MockJudge:
    """Test double; never imports anthropic SDK."""

    def __init__(self, value: int) -> None:
        self._value = value

    def judge(self, prompt: str) -> int:  # noqa: ARG002
        return self._value


def _make_rich_agent(path: Path) -> None:
    body_lines = ["---", "name: test-agent", "model: sonnet", "---", ""]
    body_lines += ["# Agent", ""]
    body_lines += [f"- bullet {i}" for i in range(120)]
    body_lines += ["", "```bash", "echo hi", "```", ""]
    path.write_text("\n".join(body_lines))


def test_mock_judge_high_score_yields_gold_or_better(tmp_path: Path) -> None:
    agent = tmp_path / "rich.md"
    _make_rich_agent(agent)
    res = score_agent(agent, judge=_MockJudge(85))
    assert res["llm"] == 85
    assert res["tier"] in {"Gold", "Platinum"}


def test_no_judge_returns_static_only_deterministic(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    res1 = score_agent(agent)
    res2 = score_agent(agent)
    assert res1["llm"] is None
    assert res1["composite"] == res2["composite"]
    assert res1["tier"] == res2["tier"]


def test_empty_agent_is_bronze(tmp_path: Path) -> None:
    agent = tmp_path / "empty.md"
    agent.write_text("")
    res = score_agent(agent)
    assert res["tier"] == "Bronze"
    assert res["composite"] == 0


def test_tier_thresholds(tmp_path: Path) -> None:
    agent = tmp_path / "x.md"
    _make_rich_agent(agent)
    # static likely 100; with judge 100 → composite = 100*0.4 + 100*0.3 + 100*0.3 = 100
    res = score_agent(agent, judge=_MockJudge(100))
    assert res["tier"] == "Platinum"
    assert res["composite"] >= 90
