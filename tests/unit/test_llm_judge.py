"""Layer-2 LLM judge — fake JudgeClient drives deterministic tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.llm_judge import (
    JudgeClient,
    JudgeResult,
    RubricVerdict,
    _build_system_prompt,
    _build_user_prompt,
    _parse_response,
    _strip_markdown_fence,
    _weighted_score,
    judge_file,
    judge_target,
)
from harness_maker.rubric_loader import Rubric, RubricFile


def _rubric() -> RubricFile:
    return RubricFile(
        dimension="context_quality",
        target="CLAUDE.md",
        rubrics=[
            Rubric(id="r0", description="check 0", severity="P0", action="fix 0"),
            Rubric(id="r1", description="check 1", severity="P1", action="fix 1"),
            Rubric(id="r2", description="check 2", severity="P2", action="fix 2"),
        ],
    )


class _FakeClient:
    """Configurable judge client — captures call args, returns canned response."""

    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


# ── _build_system_prompt / _build_user_prompt ──────────────────────────────


def test_system_prompt_includes_rubric_ids() -> None:
    sys = _build_system_prompt(_rubric())
    assert "r0" in sys
    assert "r1" in sys
    assert "r2" in sys
    assert "context_quality" in sys
    assert "CLAUDE.md" in sys


def test_user_prompt_includes_file_path_and_body(tmp_path: Path) -> None:
    p = tmp_path / "CLAUDE.md"
    user = _build_user_prompt(p, "# project\nstack\n")
    assert str(p) in user
    assert "# project" in user


# ── _strip_markdown_fence ──────────────────────────────────────────────────


def test_strip_fence_with_json_block() -> None:
    raw = '```json\n{"verdicts": []}\n```'
    assert _strip_markdown_fence(raw) == '{"verdicts": []}'


def test_strip_fence_passes_through_plain_json() -> None:
    raw = '{"verdicts": []}'
    assert _strip_markdown_fence(raw) == '{"verdicts": []}'


# ── _parse_response ────────────────────────────────────────────────────────


def test_parse_all_passed() -> None:
    rubric = _rubric()
    raw = json.dumps(
        {
            "verdicts": [
                {"rubric_id": "r0", "passed": True, "evidence": "good", "suggestion": None},
                {"rubric_id": "r1", "passed": True, "evidence": "good", "suggestion": None},
                {"rubric_id": "r2", "passed": True, "evidence": "good", "suggestion": None},
            ]
        }
    )
    verdicts, err = _parse_response(raw, rubric)
    assert err is None
    assert len(verdicts) == 3
    assert all(v.passed for v in verdicts)


def test_parse_backfills_missing_rubric() -> None:
    rubric = _rubric()
    raw = json.dumps(
        {
            "verdicts": [
                {"rubric_id": "r0", "passed": True, "evidence": "ok", "suggestion": None},
                # r1 + r2 missing
            ]
        }
    )
    verdicts, err = _parse_response(raw, rubric)
    assert err is None  # backfill is non-fatal
    assert len(verdicts) == 3
    by_id = {v.rubric_id: v for v in verdicts}
    assert by_id["r0"].passed is True
    assert by_id["r1"].passed is False
    assert "did not return a verdict" in by_id["r1"].evidence


def test_parse_invalid_json() -> None:
    verdicts, err = _parse_response("not json", _rubric())
    assert verdicts == []
    assert err is not None
    assert "non-JSON" in err


def test_parse_missing_verdicts_key() -> None:
    verdicts, err = _parse_response(json.dumps({"foo": []}), _rubric())
    assert verdicts == []
    assert "missing 'verdicts'" in (err or "")


def test_parse_verdicts_not_a_list() -> None:
    verdicts, err = _parse_response(json.dumps({"verdicts": "oops"}), _rubric())
    assert verdicts == []
    assert "not a list" in (err or "")


def test_parse_skips_invalid_verdict_items() -> None:
    rubric = _rubric()
    raw = json.dumps(
        {
            "verdicts": [
                {"rubric_id": "r0", "passed": True, "evidence": "ok", "suggestion": None},
                "this is not a dict",
                {"rubric_id": "r1", "missing_required_fields": True},
            ]
        }
    )
    verdicts, err = _parse_response(raw, rubric)
    # err is None because we got at least one valid verdict; missing ones are backfilled.
    assert err is None
    by_id = {v.rubric_id: v for v in verdicts}
    assert by_id["r0"].passed is True
    assert by_id["r1"].passed is False  # backfilled


# ── _weighted_score ────────────────────────────────────────────────────────


def test_weighted_score_all_passed() -> None:
    rubric = _rubric()
    verdicts = [
        RubricVerdict(
            rubric_id=r.id, severity=r.severity, passed=True, evidence="ok", suggestion=None
        )
        for r in rubric.rubrics
    ]
    assert _weighted_score(verdicts) == 100


def test_weighted_score_all_failed() -> None:
    rubric = _rubric()
    verdicts = [
        RubricVerdict(
            rubric_id=r.id, severity=r.severity, passed=False, evidence="bad", suggestion="fix"
        )
        for r in rubric.rubrics
    ]
    assert _weighted_score(verdicts) == 0


def test_weighted_score_p0_dominates() -> None:
    """Failing P0 (weight 3) hurts more than failing P2 (weight 1)."""
    fail_p0 = [
        RubricVerdict(
            rubric_id="r0", severity="P0", passed=False, evidence="bad", suggestion="fix"
        ),
        RubricVerdict(rubric_id="r1", severity="P1", passed=True, evidence="ok", suggestion=None),
        RubricVerdict(rubric_id="r2", severity="P2", passed=True, evidence="ok", suggestion=None),
    ]
    fail_p2 = [
        RubricVerdict(rubric_id="r0", severity="P0", passed=True, evidence="ok", suggestion=None),
        RubricVerdict(rubric_id="r1", severity="P1", passed=True, evidence="ok", suggestion=None),
        RubricVerdict(
            rubric_id="r2", severity="P2", passed=False, evidence="bad", suggestion="fix"
        ),
    ]
    assert _weighted_score(fail_p0) < _weighted_score(fail_p2)


# ── judge_file integration ─────────────────────────────────────────────────


def test_judge_file_happy_path(tmp_path: Path) -> None:
    p = tmp_path / "CLAUDE.md"
    p.write_text("# project\nstack: python\n", encoding="utf-8")
    raw = json.dumps(
        {
            "verdicts": [
                {
                    "rubric_id": "r0",
                    "passed": True,
                    "evidence": "stack present",
                    "suggestion": None,
                },
                {
                    "rubric_id": "r1",
                    "passed": False,
                    "evidence": "no commands",
                    "suggestion": "add cmds",
                },
                {"rubric_id": "r2", "passed": True, "evidence": "ok", "suggestion": None},
            ]
        }
    )
    client = _FakeClient(response=raw)
    res = judge_file(p, _rubric(), client=client)
    assert isinstance(res, JudgeResult)
    assert res.error is None
    assert len(res.verdicts) == 3
    # P1 failed → score = (3 + 0 + 1) / (3 + 2 + 1) = 4/6 ≈ 67
    assert res.score == 67


def test_judge_file_missing_file_returns_error(tmp_path: Path) -> None:
    res = judge_file(tmp_path / "missing.md", _rubric(), client=_FakeClient(""))
    assert res.error is not None
    assert res.score == 50


def test_judge_file_handles_llm_exception(tmp_path: Path) -> None:
    p = tmp_path / "CLAUDE.md"
    p.write_text("# project\n")
    res = judge_file(p, _rubric(), client=_FakeClient(RuntimeError("rate limited")))
    assert res.error is not None
    assert "rate limited" in res.error
    assert res.score == 50


def test_judge_file_handles_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "CLAUDE.md"
    p.write_text("# project\n")
    res = judge_file(p, _rubric(), client=_FakeClient("not even close to json"))
    assert res.error is not None
    assert res.score == 50
    assert res.verdicts == []


def test_judge_file_passes_rubric_in_system_prompt(tmp_path: Path) -> None:
    p = tmp_path / "CLAUDE.md"
    p.write_text("# project\n")
    fake = _FakeClient(json.dumps({"verdicts": []}))
    judge_file(p, _rubric(), client=fake)
    assert len(fake.calls) == 1
    assert "r0" in fake.calls[0]["system"]
    assert str(p) in fake.calls[0]["user"]
    assert fake.calls[0]["model"] == "claude-sonnet-4-6"


def test_judge_target_with_glob(tmp_path: Path) -> None:
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "a.md").write_text("# a")
    (agents / "b.md").write_text("# b")
    rubric = RubricFile(
        dimension="context_quality",
        target=".claude/agents/*.md",
        rubrics=_rubric().rubrics,
    )
    fake = _FakeClient(json.dumps({"verdicts": []}))
    results = judge_target(tmp_path, rubric, client=fake)
    assert len(results) == 2
    assert {r.file for r in results} == {str(agents / "a.md"), str(agents / "b.md")}


def test_judge_target_for_missing_file_returns_empty(tmp_path: Path) -> None:
    rubric = RubricFile(
        dimension="context_quality",
        target="CLAUDE.md",
        rubrics=_rubric().rubrics,
    )
    fake = _FakeClient("{}")
    results = judge_target(tmp_path, rubric, client=fake)
    assert results == []


def test_judge_client_protocol_satisfied_by_fake() -> None:
    """Smoke check that _FakeClient is structurally a JudgeClient."""
    fake: JudgeClient = _FakeClient("")
    assert callable(getattr(fake, "judge", None))


# ── Anthropic client construction (smoke, no network) ──────────────────────


def test_anthropic_judge_client_lazy_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructing AnthropicJudgeClient should import anthropic lazily."""
    from harness_maker import llm_judge

    captured: dict[str, Any] = {}

    class _StubAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            captured["init_kwargs"] = kwargs

    monkeypatch.setattr("anthropic.Anthropic", _StubAnthropic)
    client = llm_judge.AnthropicJudgeClient(api_key="test-key")
    assert isinstance(client, llm_judge.AnthropicJudgeClient)
    assert captured["init_kwargs"] == {"api_key": "test-key"}
