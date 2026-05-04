"""Agent quality scoring — static + LLM judge → Platinum/Gold/Silver/Bronze."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_maker.agent_quality import score_agent

_RUBRIC_YAML = """\
dimension: context_quality
target: .claude/agents/*.md
rubrics:
  - id: contract_format
    description: contract format used?
    severity: P1
    action: restructure
  - id: output_format_specified
    description: output format explicit?
    severity: P1
    action: specify format
  - id: tools_scoped_minimally
    description: tools scoped?
    severity: P1
    action: restrict tools
"""


class _FakeJudge:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _make_rich_agent(path: Path) -> None:
    body_lines = ["---", "name: test-agent", "description: tests", "model: sonnet", "---", ""]
    body_lines += ["# Agent", ""]
    body_lines += [f"- bullet {i}" for i in range(120)]
    body_lines += ["", "```bash", "echo hi", "```", ""]
    path.write_text("\n".join(body_lines))


def _seed_rubric_dir(tmp_path: Path) -> Path:
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    (rubrics / "agent_prompt.yaml").write_text(_RUBRIC_YAML, encoding="utf-8")
    return rubrics


def _all_pass_response() -> str:
    return json.dumps(
        {
            "verdicts": [
                {
                    "rubric_id": "contract_format",
                    "passed": True,
                    "evidence": "ok",
                    "suggestion": None,
                },
                {
                    "rubric_id": "output_format_specified",
                    "passed": True,
                    "evidence": "ok",
                    "suggestion": None,
                },
                {
                    "rubric_id": "tools_scoped_minimally",
                    "passed": True,
                    "evidence": "ok",
                    "suggestion": None,
                },
            ]
        }
    )


def _all_fail_response() -> str:
    return json.dumps(
        {
            "verdicts": [
                {
                    "rubric_id": "contract_format",
                    "passed": False,
                    "evidence": "no",
                    "suggestion": "fix",
                },
                {
                    "rubric_id": "output_format_specified",
                    "passed": False,
                    "evidence": "no",
                    "suggestion": "fix",
                },
                {
                    "rubric_id": "tools_scoped_minimally",
                    "passed": False,
                    "evidence": "no",
                    "suggestion": "fix",
                },
            ]
        }
    )


# ── static-only path ───────────────────────────────────────────────────────


def test_no_client_returns_static_only(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    res = score_agent(agent)
    assert res["llm"] is None
    assert res["composite"] == res["static"]


def test_static_score_deterministic(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    a = score_agent(agent)
    b = score_agent(agent)
    assert a["composite"] == b["composite"]


def test_empty_agent_is_bronze(tmp_path: Path) -> None:
    agent = tmp_path / "empty.md"
    agent.write_text("")
    res = score_agent(agent)
    assert res["tier"] == "Bronze"
    assert res["composite"] == 0


# ── LLM-augmented path ────────────────────────────────────────────────────


def test_llm_all_pass_lifts_to_platinum(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    rubrics = _seed_rubric_dir(tmp_path)
    fake = _FakeJudge(_all_pass_response())
    res = score_agent(agent, rubric_dir=rubrics, client=fake)
    assert res["llm"] == 100
    assert res["composite"] >= 90
    assert res["tier"] == "Platinum"
    assert len(fake.calls) == 1


def test_llm_all_fail_drops_score(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    rubrics = _seed_rubric_dir(tmp_path)
    fake = _FakeJudge(_all_fail_response())
    res_with_llm = score_agent(agent, rubric_dir=rubrics, client=fake)
    res_static_only = score_agent(agent)
    assert res_with_llm["llm"] == 0
    # LLM score 0 averaged with static lifts can drop below static-only.
    assert res_with_llm["composite"] < res_static_only["composite"]


def test_llm_failure_falls_back_to_static(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    rubrics = _seed_rubric_dir(tmp_path)
    fake = _FakeJudge(RuntimeError("rate limited"))
    res = score_agent(agent, rubric_dir=rubrics, client=fake)
    assert res["llm"] is None
    assert res["composite"] == res["static"]


def test_invalid_json_falls_back_to_static(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    rubrics = _seed_rubric_dir(tmp_path)
    fake = _FakeJudge("not json at all")
    res = score_agent(agent, rubric_dir=rubrics, client=fake)
    # judge_file returns score=50 with error set; we treat error as fallback.
    assert res["llm"] is None
    assert res["composite"] == res["static"]


def test_missing_rubric_falls_back_to_static(tmp_path: Path) -> None:
    agent = tmp_path / "agent.md"
    _make_rich_agent(agent)
    empty_rubrics = tmp_path / "no_rubrics"
    empty_rubrics.mkdir()
    fake = _FakeJudge(_all_pass_response())
    res = score_agent(agent, rubric_dir=empty_rubrics, client=fake)
    assert res["llm"] is None
    assert fake.calls == []  # judge never called


def test_tier_thresholds_preserved() -> None:
    """Static + LLM averaging must keep ≥90 Platinum, ≥80 Gold, ≥70 Silver."""
    from harness_maker.agent_quality import _tier

    assert _tier(95) == "Platinum"
    assert _tier(90) == "Platinum"
    assert _tier(89) == "Gold"
    assert _tier(80) == "Gold"
    assert _tier(79) == "Silver"
    assert _tier(70) == "Silver"
    assert _tier(69) == "Bronze"
    assert _tier(0) == "Bronze"
