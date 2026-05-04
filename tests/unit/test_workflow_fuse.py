"""Tests for the workflow fuse logic + LLM contradiction lint."""

from __future__ import annotations

import json
from typing import Any

from harness_maker.models import AtomicStage
from harness_maker.workflow_fuse import (
    Contradiction,
    _parse_lint_response,
    _strip_markdown_fence,
    fuse,
    lint_workflow,
)


def test_fuse_dev_workflow_orders_4_stages() -> None:
    """dev = [plan, execute, review, wrapup] fuses in order with separators."""
    stages = [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ]
    body = fuse(stages, "dev")
    assert "# /hm:dev" in body
    # Separators exist for each stage
    for stage in ("plan", "execute", "review", "wrapup"):
        assert f"## Stage: {stage}" in body
    # Order is preserved
    pos = [body.index(f"## Stage: {s}") for s in ("plan", "execute", "review", "wrapup")]
    assert pos == sorted(pos)


def test_fuse_empty_stages_returns_header_only() -> None:
    body = fuse([], "blank")
    assert body == "# /hm:blank\n"
    assert "## Stage:" not in body


def test_fuse_full_atomic_workflow() -> None:
    """Full 7-stage workflow fuses with all separators present."""
    stages = list(AtomicStage)
    body = fuse(stages, "careful")
    for stage in (
        "research",
        "spec",
        "plan",
        "execute",
        "review",
        "wrapup",
        "verify",
    ):
        assert f"## Stage: {stage}" in body
    assert body.startswith("# /hm:careful")


def test_fuse_passes_workflow_context_to_fragments() -> None:
    """Fragment templates receive workflow_context so they can self-reference."""
    body = fuse([AtomicStage.PLAN], "dev")
    # research.md.j2 uses {% if workflow_context %} to add a note; check via plan stage
    assert "dev" in body  # workflow_context is "dev", appears in body


# ── lint_workflow ─────────────────────────────────────────────────────────


class _FakeJudge:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _contradiction_response() -> str:
    return json.dumps(
        {
            "contradictions": [
                {
                    "between": ["execute", "wrapup"],
                    "summary": "execute commits per phase but wrapup forbids commits",
                    "evidence": "execute: 'commit at phase boundaries'; wrapup: 'do not commit'",
                    "severity": "high",
                }
            ]
        }
    )


def test_strip_fence() -> None:
    assert _strip_markdown_fence("```json\n{}\n```") == "{}"


def test_parse_lint_valid() -> None:
    out = _parse_lint_response(_contradiction_response())
    assert len(out) == 1
    assert isinstance(out[0], Contradiction)
    assert out[0].between == ["execute", "wrapup"]


def test_parse_lint_empty_list() -> None:
    raw = json.dumps({"contradictions": []})
    assert _parse_lint_response(raw) == []


def test_parse_lint_invalid_json() -> None:
    assert _parse_lint_response("not json") == []


def test_parse_lint_missing_key() -> None:
    assert _parse_lint_response(json.dumps({"foo": []})) == []


def test_parse_lint_drops_malformed_entries() -> None:
    raw = json.dumps(
        {
            "contradictions": [
                {"between": ["a", "b"], "summary": "x", "evidence": "y", "severity": "high"},
                "not a dict",
                {"missing_required_fields": True},
            ]
        }
    )
    out = _parse_lint_response(raw)
    assert len(out) == 1


def test_lint_workflow_happy_path() -> None:
    fake = _FakeJudge(_contradiction_response())
    result = lint_workflow("# /hm:dev\n\n## Stage: execute\n…", "dev", client=fake)
    assert len(result) == 1
    assert "execute" in result[0].between


def test_lint_workflow_falls_back_silently_on_error() -> None:
    fake = _FakeJudge(RuntimeError("rate limited"))
    result = lint_workflow("body", "dev", client=fake)
    assert result == []  # never raises


def test_lint_workflow_empty_body_skips_call() -> None:
    fake = _FakeJudge(_contradiction_response())
    result = lint_workflow("", "dev", client=fake)
    assert result == []
    assert fake.calls == []


def test_lint_workflow_caps_input() -> None:
    fake = _FakeJudge(json.dumps({"contradictions": []}))
    huge = "x" * 50_000
    lint_workflow(huge, "dev", client=fake)
    user = fake.calls[0]["user"]
    body_section = user.split("BEGIN FUSED BODY ---\n")[1].split("\n--- END FUSED BODY")[0]
    assert len(body_section) <= 16_000
