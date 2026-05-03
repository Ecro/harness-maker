"""Tests for harness_maker.gates.spec_gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.gates.spec_gate import (
    GateDecision,
    Severity,
    derive_test_slug,
    evaluate,
    find_spec_for_test,
    is_test_path,
)

# ──────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "tests/unit/test_foo.py",
        "tests/test_bar.py",
        "test_baz.py",
        "src/qux/test_qux.py",
        "src/foo/foo_test.py",
        "tests/integration/test_e2e_flow.py",
    ],
)
def test_is_test_path_positive(path: str) -> None:
    assert is_test_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/harness_maker/models.py",
        "docs/README.md",
        "tests/fixtures/sample.txt",
        "specs/SPEC-foo.md",
    ],
)
def test_is_test_path_negative(path: str) -> None:
    assert not is_test_path(path)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/unit/test_spec_gate.py", "spec_gate"),
        ("tests/test_foo.py", "foo"),
        ("test_bar.py", "bar"),
        ("src/qux/qux_test.py", "qux"),
        ("tests/unit/whatever.py", "whatever"),
    ],
)
def test_derive_test_slug(path: str, expected: str) -> None:
    assert derive_test_slug(path) == expected


def test_find_spec_matches_by_test_path(tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "SPEC-foo.md").write_text(
        "# SPEC-foo\n\nVerified by tests/unit/test_foo.py\n",
    )
    found = find_spec_for_test(spec_dir, "tests/unit/test_foo.py")
    assert found is not None
    assert found.name == "SPEC-foo.md"


def test_find_spec_matches_by_slug(tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "SPEC-bar.md").write_text(
        "# SPEC-bar\n\nThe `bar` module is exercised through unit tests.\n",
    )
    found = find_spec_for_test(spec_dir, "tests/unit/test_bar.py")
    assert found is not None


def test_find_spec_returns_none_when_dir_missing(tmp_path: Path) -> None:
    assert find_spec_for_test(tmp_path / "nope", "tests/test_x.py") is None


def test_find_spec_returns_none_when_no_match(tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "SPEC-other.md").write_text("# Unrelated\n")
    assert find_spec_for_test(spec_dir, "tests/unit/test_missing.py") is None


# ──────────────────────────────────────────────────────────────────────────────
# evaluate() — full decision logic
# ──────────────────────────────────────────────────────────────────────────────


def _write_harness_yaml(project_dir: Path, body: str) -> None:
    (project_dir / ".claude").mkdir(parents=True, exist_ok=True)
    (project_dir / ".claude" / "harness.yaml").write_text(body)


def _spec_driven_yaml(severity: str = "warn", *, locale: str = "en") -> str:
    return (
        f"locale: {locale}\n"
        "dev_mode: spec-driven\n"
        "spec:\n"
        "  dir: specs/\n"
        "security:\n"
        "  gates:\n"
        f"    spec_gate: {severity}\n"
    )


def test_evaluate_non_test_path_is_noop(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("block"))
    decision = evaluate(
        "Write",
        {"file_path": "src/harness_maker/cli.py"},
        tmp_path,
    )
    assert decision == GateDecision(allow=True, severity=Severity.WARN, message="")


def test_evaluate_non_write_tool_is_noop(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("block"))
    decision = evaluate("Read", {"file_path": "tests/test_x.py"}, tmp_path)
    assert decision.allow is True
    assert decision.message == ""


def test_evaluate_task_driven_is_noop_even_for_test(tmp_path: Path) -> None:
    """Defense in depth: hooks.json shouldn't register us, but if it does we stay silent."""
    _write_harness_yaml(tmp_path, "locale: en\ndev_mode: task-driven\n")
    decision = evaluate(
        "Write",
        {"file_path": "tests/unit/test_foo.py"},
        tmp_path,
    )
    assert decision.allow is True
    assert decision.message == ""


def test_evaluate_spec_present_is_allow(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("block"))
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "SPEC-foo.md").write_text("Tests live in tests/unit/test_foo.py\n")
    decision = evaluate(
        "Write",
        {"file_path": "tests/unit/test_foo.py"},
        tmp_path,
    )
    assert decision.allow is True
    assert decision.message == ""


def test_evaluate_spec_missing_warn_allows_with_message(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("warn"))
    decision = evaluate(
        "Write",
        {"file_path": "tests/unit/test_foo.py"},
        tmp_path,
    )
    assert decision.allow is True
    assert decision.severity == Severity.WARN
    assert "test_foo.py" in decision.message
    assert "specs/" in decision.message


def test_evaluate_spec_missing_block_denies(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("block"))
    decision = evaluate(
        "Edit",
        {"file_path": "tests/unit/test_bar.py"},
        tmp_path,
    )
    assert decision.allow is False
    assert decision.severity == Severity.BLOCK
    assert "test_bar.py" in decision.message


def test_evaluate_korean_message_when_locale_ko(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("warn", locale="ko"))
    decision = evaluate(
        "Write",
        {"file_path": "tests/unit/test_foo.py"},
        tmp_path,
    )
    # Korean translation contains 한글 — verifying locale plumbing end-to-end.
    assert any("가" <= ch <= "힯" for ch in decision.message)


def test_evaluate_unknown_locale_falls_back_to_en(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("warn", locale="ja"))
    decision = evaluate(
        "Write",
        {"file_path": "tests/unit/test_foo.py"},
        tmp_path,
    )
    assert "spec-gate" in decision.message
    # English fallback uses 'no SPEC' phrasing.
    assert "no SPEC" in decision.message


def test_evaluate_no_yaml_is_noop(tmp_path: Path) -> None:
    """No harness.yaml present — gate stays out of the way (most projects)."""
    decision = evaluate(
        "Write",
        {"file_path": "tests/unit/test_foo.py"},
        tmp_path,
    )
    assert decision.allow is True
    assert decision.message == ""


# ──────────────────────────────────────────────────────────────────────────────
# main() entry — exercised via subprocess so exit code + stderr are real
# ──────────────────────────────────────────────────────────────────────────────


def _run_gate(payload: dict[str, object], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — well-formed argv, no shell
        [sys.executable, "-m", "harness_maker.gates.spec_gate"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
        check=False,
    )


def test_main_block_exits_2_on_missing_spec(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("block"))
    proc = _run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "tests/unit/test_x.py"}},
        tmp_path,
    )
    assert proc.returncode == 2
    assert "test_x.py" in proc.stderr


def test_main_warn_exits_0_with_stderr(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, _spec_driven_yaml("warn"))
    proc = _run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "tests/unit/test_x.py"}},
        tmp_path,
    )
    assert proc.returncode == 0
    assert "test_x.py" in proc.stderr


def test_main_malformed_stdin_is_silent_allow(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "harness_maker.gates.spec_gate"],
        input="not-json{",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stderr == ""
