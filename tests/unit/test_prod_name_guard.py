"""Tests for production-name guard (Phase 8)."""

from __future__ import annotations

from harness_maker.secscan.prod_name_guard import scan_sequence, scan_tool_call


def test_detects_prod_db_in_args() -> None:
    findings = scan_tool_call("Read", {"path": "/data/prod.db"})
    assert len(findings) >= 1
    assert findings[0].severity == "P0"
    assert findings[0].category == "prod_name_guard"


def test_detects_production_env() -> None:
    findings = scan_tool_call("Read", {"file": "production.env"})
    assert len(findings) >= 1


def test_detects_prod_server() -> None:
    findings = scan_tool_call("Bash", {"command": "ssh prod-server"})
    assert len(findings) >= 1


def test_allows_test_db() -> None:
    findings = scan_tool_call("Read", {"path": "/data/test.db"})
    assert findings == []


def test_allows_staging() -> None:
    findings = scan_tool_call("Read", {"path": "/staging/data.db"})
    assert findings == []


def test_read_write_sequence_detected() -> None:
    calls = [
        {"tool_name": "Read", "args": {"path": "prod.db"}},
        {"tool_name": "Write", "args": {"path": "prod.db"}},
    ]
    findings = scan_sequence(calls)
    assert len(findings) >= 1
    assert findings[0].severity == "P0"
    assert "Read" in findings[0].evidence
    assert "Write" in findings[0].evidence


def test_read_edit_sequence_detected() -> None:
    calls = [
        {"tool_name": "Read", "args": {"path": "config.prod.yaml"}},
        {"tool_name": "Edit", "args": {"path": "config.prod.yaml"}},
    ]
    findings = scan_sequence(calls)
    assert len(findings) >= 1


def test_read_write_different_targets_no_finding() -> None:
    calls = [
        {"tool_name": "Read", "args": {"path": "prod.db"}},
        {"tool_name": "Write", "args": {"path": "test.db"}},
    ]
    findings = scan_sequence(calls)
    assert findings == []


def test_non_prod_sequence_p1() -> None:
    calls = [
        {"tool_name": "Read", "args": {"path": "data.db"}},
        {"tool_name": "Write", "args": {"path": "data.db"}},
    ]
    findings = scan_sequence(calls)
    assert len(findings) >= 1
    assert findings[0].severity == "P1"


def test_sequence_beyond_window_not_detected() -> None:
    calls = [
        {"tool_name": "Read", "args": {"path": "prod.db"}},
        *[{"tool_name": "Other", "args": {"path": f"file{i}.txt"}} for i in range(10)],
        {"tool_name": "Write", "args": {"path": "prod.db"}},
    ]
    findings = scan_sequence(calls, window=3)
    assert findings == []


def test_single_call_no_sequence() -> None:
    calls = [{"tool_name": "Read", "args": {"path": "prod.db"}}]
    assert scan_sequence(calls) == []


def test_prod_regex_case_insensitive() -> None:
    findings = scan_tool_call("Read", {"path": "PRODUCTION.ENV"})
    assert len(findings) >= 1
