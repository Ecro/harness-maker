"""Phase 2 — high-diff detector deterministic path (PLAN-crossmodel-codex-gaps ADR-003).

Numeric/path criteria are deterministic and fully unit-tested here. The LLM-boundary
judgment is exercised separately under INTEGRATION=1 (tests/integration/test_high_diff_boundary.py).
"""

from __future__ import annotations

import json

import pytest

from harness_maker import high_diff


def test_more_than_three_files_is_high() -> None:
    res = high_diff.classify_paths(["a.py", "b.py", "c.py", "d.py"])
    assert res.is_high
    assert any("file" in r for r in res.reasons)


def test_exactly_three_files_not_high_by_count() -> None:
    res = high_diff.classify_paths(["a.py", "b.py", "c.py"])
    assert not any("file count" in r for r in res.reasons)


def test_security_path_is_high_even_single_file() -> None:
    res = high_diff.classify_paths(["src/auth/login.py"])
    assert res.is_high
    assert any("security" in r for r in res.reasons)


def test_one_line_security_change_is_high() -> None:
    """The validator's worried case: a 1-line security touch must still trip high."""
    res = high_diff.classify_paths([".claude/settings.json"], added_lines=1)
    assert res.is_high


def test_contract_path_is_high() -> None:
    res = high_diff.classify_paths(["src/harness_maker/templates/schemas/foo.schema.json"])
    assert res.is_high
    assert any("contract" in r for r in res.reasons)


def test_models_py_is_contract() -> None:
    res = high_diff.classify_paths(["src/harness_maker/models.py"])
    assert res.is_high


def test_small_ordinary_change_is_low() -> None:
    res = high_diff.classify_paths(["README.md"], added_lines=3)
    assert not res.is_high
    assert not res.boundary


def test_large_single_file_is_boundary() -> None:
    """A sizable non-sensitive change numbers can't classify -> defer to LLM."""
    res = high_diff.classify_paths(["src/harness_maker/util.py"], added_lines=180)
    assert not res.is_high
    assert res.boundary


def test_boundary_false_when_already_high() -> None:
    res = high_diff.classify_paths(["src/auth/x.py"], added_lines=500)
    assert res.is_high
    assert not res.boundary


def test_empty_diff_is_low() -> None:
    res = high_diff.classify_paths([])
    assert not res.is_high
    assert not res.boundary


def test_cli_classify_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin", _StdinStub("a.py\nb.py\nc.py\nd.py\n"))
    rc = high_diff.main(["classify"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["is_high"] is True


def test_cli_classify_with_added_lines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin", _StdinStub("src/harness_maker/util.py\n"))
    rc = high_diff.main(["classify", "--added-lines", "180"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["is_high"] is False
    assert out["boundary"] is True


class _StdinStub:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> str:
        return self._payload
