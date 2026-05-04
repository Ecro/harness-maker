"""plan_verify — LLM-judged PLAN fulfillment, hard-fail on LLM error."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.plan_verify import (
    PlanVerification,
    PlanVerifyError,
    _parse_response,
    _strip_markdown_fence,
    verify_plan,
)


class _FakeJudge:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _seed_plan(tmp_path: Path, body: str = "# PLAN\n- [x] add tests\n- [x] add ci\n") -> Path:
    p = tmp_path / "PLAN-x.md"
    p.write_text(body, encoding="utf-8")
    return p


def _all_fulfilled() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "text": "- [x] add tests",
                    "fulfilled": True,
                    "evidence": "tests/test_x.py:1-20",
                    "reason": "added two new pytest functions",
                },
                {
                    "text": "- [x] add ci",
                    "fulfilled": True,
                    "evidence": ".github/workflows/ci.yml:1-15",
                    "reason": "new workflow",
                },
            ],
            "overall_pass": True,
        }
    )


def _partial_fulfilled() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "text": "- [x] add tests",
                    "fulfilled": True,
                    "evidence": "tests/test_x.py:1-20",
                    "reason": "added",
                },
                {
                    "text": "- [x] add ci",
                    "fulfilled": False,
                    "evidence": "-",
                    "reason": "no workflow file in diff",
                },
            ],
            "overall_pass": False,
        }
    )


# ── _strip_markdown_fence ──────────────────────────────────────────────────


def test_strip_fence() -> None:
    assert _strip_markdown_fence('```json\n{"x":1}\n```') == '{"x":1}'
    assert _strip_markdown_fence('{"x":1}') == '{"x":1}'


# ── _parse_response ────────────────────────────────────────────────────────


def test_parse_all_fulfilled(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    result = _parse_response(_all_fulfilled(), plan)
    assert isinstance(result, PlanVerification)
    assert result.overall_pass
    assert len(result.items) == 2
    assert all(it.fulfilled for it in result.items)


def test_parse_partial_fulfilled(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    result = _parse_response(_partial_fulfilled(), plan)
    assert not result.overall_pass


def test_parse_invalid_json_raises(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    with pytest.raises(PlanVerifyError, match="non-JSON"):
        _parse_response("not json", plan)


def test_parse_missing_items_key_raises(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    with pytest.raises(PlanVerifyError, match="missing 'items'"):
        _parse_response(json.dumps({"foo": []}), plan)


def test_parse_items_not_list_raises(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    with pytest.raises(PlanVerifyError, match="not a list"):
        _parse_response(json.dumps({"items": "oops"}), plan)


def test_parse_overrides_overall_pass_when_item_failed(tmp_path: Path) -> None:
    """Defensive: even if model says overall_pass=true, distrust when any item failed."""
    plan = _seed_plan(tmp_path)
    raw = json.dumps(
        {
            "items": [
                {
                    "text": "x",
                    "fulfilled": False,
                    "evidence": "-",
                    "reason": "missing",
                },
            ],
            "overall_pass": True,  # lying!
        }
    )
    result = _parse_response(raw, plan)
    assert not result.overall_pass


def test_parse_invalid_item_shape_raises(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    raw = json.dumps(
        {
            "items": [{"text": "x", "fulfilled": "not-a-bool", "evidence": "-", "reason": "x"}],
            "overall_pass": False,
        }
    )
    with pytest.raises(PlanVerifyError, match="failed validation"):
        _parse_response(raw, plan)


# ── verify_plan integration ────────────────────────────────────────────────


def test_verify_plan_happy_path(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    fake = _FakeJudge(_all_fulfilled())
    result = verify_plan(plan, "diff content", client=fake)
    assert result.overall_pass
    assert len(fake.calls) == 1
    assert "BEGIN PLAN" in fake.calls[0]["user"]
    assert "BEGIN DIFF" in fake.calls[0]["user"]


def test_verify_plan_truncates_huge_diff(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    huge_diff = "x" * 100_000
    fake = _FakeJudge(_all_fulfilled())
    verify_plan(plan, huge_diff, client=fake)
    user = fake.calls[0]["user"]
    # diff truncated to 32k cap
    diff_section = user.split("BEGIN DIFF ---\n")[1].split("\n--- END DIFF")[0]
    assert len(diff_section) <= 32_000


def test_verify_plan_missing_file_raises(tmp_path: Path) -> None:
    fake = _FakeJudge(_all_fulfilled())
    with pytest.raises(PlanVerifyError, match="not found"):
        verify_plan(tmp_path / "missing.md", "diff", client=fake)


def test_verify_plan_llm_failure_propagates(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    fake = _FakeJudge(RuntimeError("rate limited"))
    with pytest.raises(PlanVerifyError, match="LLM call failed"):
        verify_plan(plan, "diff", client=fake)


def test_verify_plan_with_partial_fulfillment_blocks(tmp_path: Path) -> None:
    plan = _seed_plan(tmp_path)
    fake = _FakeJudge(_partial_fulfilled())
    result = verify_plan(plan, "diff", client=fake)
    assert not result.overall_pass
    failed = [it for it in result.items if not it.fulfilled]
    assert len(failed) == 1
    assert failed[0].text == "- [x] add ci"
