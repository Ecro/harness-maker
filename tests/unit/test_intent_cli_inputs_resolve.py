"""SPEC-intent-layer-improvements AC-008/009/010 — stdin values, observed-at default, resolve.

Expected values are written from the SPEC (scalar = text without trailing newlines; list = the
non-empty stripped lines), never read back from the file path, so a normaliser shared by the file
and stdin paths cannot satisfy the oracle. Refusals are checked by byte-comparing the root.

Phase A.4 (measured 21 failed, 5 passed): the five passes are preservation guards.
`test_add_without_text_writes_no_evidence` goes red if the observed-at default starts writing an
evidence entry when no text was given; its RED sibling is `test_observed_at_defaults_to_now`.
The four allowed `test_resolve_lifecycle` pairs pass under today's any-to-any rewrite and go red
if the new restriction over-refuses; their RED siblings are the five refused pairs.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.unit import world_fixture as fx
from tests.unit.test_intent_file_inputs import (
    _LIST_FLAGS,
    _TEXT,
    CASES,
    _fill,
    _fresh,
    _intent,
    _ok,
    _question,
    _run,
    _snapshot,
)


class _Stdin(io.TextIOWrapper):
    """A text stdin whose `.buffer` holds exactly the given bytes."""

    def __init__(self, data: bytes) -> None:
        super().__init__(io.BytesIO(data), encoding="utf-8")


def _stdin_argv(name: str) -> list[str]:
    return [
        "-" if token == "__STDIN__" else token
        for token in _fill(CASES[name], path=Path("__STDIN__"))
    ]


# ── AC-008 ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(CASES))
@settings(
    max_examples=5,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(x=_TEXT, newlines=st.integers(0, 2))
def test_stdin_matches_file_semantics(
    name: str, x: str, newlines: int, tmp_path_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = x + "\n" * newlines
    expected = raw.rstrip("\n")
    if not expected:
        return
    case = CASES[name]
    root = _fresh(case.template, tmp_path_factory.mktemp("stdin"))
    monkeypatch.setattr("sys.stdin", _Stdin(raw.encode("utf-8")))
    _ok(root, *_stdin_argv(name))
    assert case.stored(root) == expected


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("edge", [" ", "\t", "  \t "])
def test_stdin_keeps_boundary_whitespace(
    name: str, edge: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = CASES[name]
    root = _fresh(case.template, tmp_path)
    monkeypatch.setattr("sys.stdin", _Stdin(f"{edge}body{edge}\n\n".encode()))
    _ok(root, *_stdin_argv(name))
    assert case.stored(root) == f"{edge}body{edge}"


@pytest.mark.parametrize("flag", sorted(_LIST_FLAGS))
def test_stdin_list_flags(flag: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fresh("fresh", tmp_path)
    raw = "  alpha item \n\n\tbeta item\n"
    expected = ["alpha item", "beta item"]
    argv = ["new", "N", "--title", "t", "--statement", "s", "--metric", "latency"]
    if flag != "scope":
        argv += ["--scope", "p"]
    if flag == "declined":
        argv += ["--from-proposal", "--candidates", "3"]
    monkeypatch.setattr("sys.stdin", _Stdin(raw.encode("utf-8")))
    _ok(root, *argv, f"--{flag}-file", "-")
    assert _intent(root, "N")[_LIST_FLAGS[flag]] == expected


def test_two_stdin_values_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fresh("fresh", tmp_path)
    before = _snapshot(root)
    monkeypatch.setattr("sys.stdin", _Stdin(b"one\n"))
    rc, _out, err = _run(
        root,
        "new",
        "N",
        "--title-file",
        "-",
        "--statement-file",
        "-",
        "--scope",
        "p",
        "--metric",
        "latency",
    )
    assert rc != 0
    assert "stdin" in err
    assert _snapshot(root) == before


# ── AC-009 ───────────────────────────────────────────────────────────────────

_Case = tuple[str, list[str], Callable[[Path], Any]]

_NO_AT: dict[str, _Case] = {
    "observe": (
        "question",
        ["question", "observe", "runtime", "--relation", "confirms", "--text", "seen", "--json"],
        lambda r: _question(r)["evidence"][-1]["observed_at"],
    ),
    "add-with-text": (
        "fresh",
        ["question", "add", "q1", "--claim", "c", "--status", "open", "--text", "why", "--json"],
        lambda r: _question(r, "q1")["evidence"][-1]["observed_at"],
    ),
    "metric-record": (
        "fresh",
        ["metric", "record", "latency", "--value", "8", "--evidence", "e", "--json"],
        lambda r: fx.load(r / ".claude/intent/metrics.yaml")["values"][-1]["observed_at"],
    ),
}


@pytest.mark.parametrize("name", sorted(_NO_AT))
def test_observed_at_defaults_to_now(name: str, tmp_path: Path) -> None:
    template, argv, stored = _NO_AT[name]
    root = _fresh(template, tmp_path)
    t0 = datetime.now(UTC)
    _ok(root, *argv)
    t1 = datetime.now(UTC)
    value = datetime.fromisoformat(str(stored(root)).replace("Z", "+00:00"))
    assert value.tzinfo is not None
    assert t0 <= value <= t1


def test_add_without_text_writes_no_evidence(tmp_path: Path) -> None:
    root = _fresh("fresh", tmp_path)
    _ok(root, "question", "add", "q1", "--claim", "c", "--status", "open", "--json")
    assert not _question(root, "q1").get("evidence")


# ── AC-010 ───────────────────────────────────────────────────────────────────

_ALLOWED = {("open", "confirmed"), ("open", "wrong"), ("wrong", "confirmed"), ("wrong", "open")}
_STATUSES = ("open", "confirmed", "wrong")


@pytest.mark.parametrize("target", _STATUSES)
@pytest.mark.parametrize("source", _STATUSES)
def test_resolve_lifecycle(source: str, target: str, tmp_path: Path) -> None:
    root = _fresh("fresh", tmp_path)
    _ok(root, "question", "add", "q1", "--claim", "c", "--status", source, "--json")
    before = (root / ".claude/intent.yaml").read_bytes()
    rc, out, err = _run(
        root, "question", "resolve", "q1", "--status", target, "--claim", "settled", "--json"
    )
    if (source, target) in _ALLOWED:
        assert rc == 0, err
        assert _question(root, "q1")["status"] == target
        assert _question(root, "q1")["claim"] == "settled"
    else:
        assert rc != 0
        # The CLI reports refusals on stdout as {"error": ...}; either stream counts.
        assert "observe --relation" in out + err
        assert (root / ".claude/intent.yaml").read_bytes() == before


class _Tty(_Stdin):
    def isatty(self) -> bool:
        return True


@pytest.mark.parametrize(
    ("label", "stdin", "needle"),
    [
        ("not-utf8", _Stdin(b"\xff\xfe"), "not UTF-8"),
        ("empty", _Stdin(b"\n\n"), "empty"),
        ("terminal", _Tty(b"body\n"), "not a terminal"),
    ],
    ids=["not-utf8", "empty", "terminal"],
)
def test_stdin_refusals_write_nothing(
    label: str,
    stdin: io.TextIOWrapper,
    needle: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _fresh("fresh", tmp_path)
    before = _snapshot(root)
    monkeypatch.setattr("sys.stdin", stdin)
    rc, out, err = _run(
        root, "question", "add", "q1", "--claim-file", "-", "--status", "open", "--json"
    )
    assert rc != 0, label
    assert needle in out + err
    assert _snapshot(root) == before


_EXPLICIT_AT: dict[str, _Case] = {
    "observe": (
        "question",
        ["question", "observe", "runtime", "--relation", "confirms", "--text", "seen"],
        lambda r: _question(r)["evidence"][-1]["observed_at"],
    ),
    "add-with-text": (
        "fresh",
        ["question", "add", "q1", "--claim", "c", "--status", "open", "--text", "why"],
        lambda r: _question(r, "q1")["evidence"][-1]["observed_at"],
    ),
    "metric-record": (
        "fresh",
        ["metric", "record", "latency", "--value", "8", "--evidence", "e"],
        lambda r: fx.load(r / ".claude/intent/metrics.yaml")["values"][-1]["observed_at"],
    ),
}


@pytest.mark.parametrize("name", sorted(_EXPLICIT_AT))
def test_explicit_observed_at_is_kept(name: str, tmp_path: Path) -> None:
    template, argv, stored = _EXPLICIT_AT[name]
    root = _fresh(template, tmp_path)
    _ok(root, *argv, "--observed-at", "2026-01-02T03:04:05Z", "--json")
    assert stored(root) == "2026-01-02T03:04:05Z"


def test_missing_stdin_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _fresh("fresh", tmp_path)
    before = _snapshot(root)
    monkeypatch.setattr("sys.stdin", None)
    rc, out, err = _run(
        root, "question", "add", "q1", "--claim-file", "-", "--status", "open", "--json"
    )
    assert rc != 0
    assert "none is attached" in out + err
    assert _snapshot(root) == before
