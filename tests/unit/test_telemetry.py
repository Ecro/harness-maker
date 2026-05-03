"""Telemetry hook tests (per amendment §H)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from harness_maker import telemetry


def _run_main_with_stdin(monkeypatch: pytest.MonkeyPatch, stdin: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return telemetry.main()


def test_appends_jsonl_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "workspace": {"current_dir": str(tmp_path)},
        "tool_name": "Bash",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_read_input_tokens": 5,
        },
    }
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    metrics = tmp_path / ".claude" / "observability" / "metrics.jsonl"
    assert metrics.is_file()
    line = metrics.read_text().strip()
    entry = json.loads(line)
    assert entry["input_tokens"] == 10
    assert entry["output_tokens"] == 20
    assert entry["cache_read_tokens"] == 5
    assert entry["tool_name"] == "Bash"
    assert "timestamp" in entry


def test_creates_parent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"workspace": {"current_dir": str(tmp_path)}}
    rc = _run_main_with_stdin(monkeypatch, json.dumps(payload))
    assert rc == 0
    assert (tmp_path / ".claude" / "observability").is_dir()


def test_malformed_stdin_does_not_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = _run_main_with_stdin(monkeypatch, "not json {{{")
    assert rc == 0
    metrics = tmp_path / ".claude" / "observability" / "metrics.jsonl"
    # Even on malformed input, we still write an empty entry
    assert metrics.is_file()


def test_empty_stdin_writes_default_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = _run_main_with_stdin(monkeypatch, "")
    assert rc == 0
    metrics = tmp_path / ".claude" / "observability" / "metrics.jsonl"
    assert metrics.is_file()
    entry = json.loads(metrics.read_text().strip())
    assert entry["input_tokens"] == 0
