"""Tests for sibling_repos support in interview.py (Phase 5)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from harness_maker import interview
from harness_maker.models import InterviewAnswers


def _answers_from_yaml(text: str, tmp_path: Path) -> InterviewAnswers | None:
    p = tmp_path / "harness.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return interview.answers_from_harness_yaml(p)


# ── _ask_sibling_repos ────────────────────────────────────────────────────────


def test_ask_sibling_repos_empty_input_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blank first line → skip, return empty list."""
    monkeypatch.setattr("harness_maker.interview._input_or_empty", lambda _: "")
    result = interview._ask_sibling_repos()
    assert result == []


def test_ask_sibling_repos_relative_path_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative path input → accepted and returned."""
    responses = iter(["../repo-b", ""])
    monkeypatch.setattr("harness_maker.interview._input_or_empty", lambda _: next(responses))
    result = interview._ask_sibling_repos()
    assert result == ["../repo-b"]


def test_ask_sibling_repos_absolute_path_rejected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Absolute path → rejected with error message; loop continues."""
    responses = iter(["/absolute/path", ""])
    monkeypatch.setattr("harness_maker.interview._input_or_empty", lambda _: next(responses))
    result = interview._ask_sibling_repos()
    assert result == []
    out = capsys.readouterr().out
    assert "absolute" in out.lower() or "relative" in out.lower()


def test_ask_sibling_repos_multiple_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple relative paths accepted until blank line."""
    responses = iter(["../repo-b", "../repo-c", ""])
    monkeypatch.setattr("harness_maker.interview._input_or_empty", lambda _: next(responses))
    result = interview._ask_sibling_repos()
    assert result == ["../repo-b", "../repo-c"]


# ── answers_from_harness_yaml round-trip ─────────────────────────────────────


def test_answers_from_yaml_reads_sibling_repos(tmp_path: Path) -> None:
    """sibling_repos field is restored from harness.yaml."""
    answers = _answers_from_yaml(
        """
        preset: Side
        locale: en
        targets: [claude-code]
        sibling_repos:
          - ../repo-b
          - ../repo-c
        """,
        tmp_path,
    )
    assert answers is not None
    assert answers.sibling_repos == ["../repo-b", "../repo-c"]


def test_answers_from_yaml_missing_sibling_repos_defaults_empty(tmp_path: Path) -> None:
    """Old harness.yaml without sibling_repos → empty list (schema gap fallback)."""
    answers = _answers_from_yaml(
        """
        preset: Side
        locale: en
        targets: [claude-code]
        """,
        tmp_path,
    )
    assert answers is not None
    assert answers.sibling_repos == []


def test_answers_from_yaml_empty_sibling_repos_returns_empty(tmp_path: Path) -> None:
    """sibling_repos: [] → empty list (not None)."""
    answers = _answers_from_yaml(
        """
        preset: Side
        locale: en
        targets: [claude-code]
        sibling_repos: []
        """,
        tmp_path,
    )
    assert answers is not None
    assert answers.sibling_repos == []
