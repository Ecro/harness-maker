"""Phase 4a — Codex-finding -> reviewer-finding adapter (PLAN-crossmodel-codex-gaps ADR-001).

Two defects the validator caught (both pass-1 C2 + pass-2 critical) live here:
- severity-vocabulary mapping (Codex info/low/medium/high/critical -> reviewer P0..P3),
  without which Step 4a's "same severity tier" predicate blocks every Codex finding.
- null file/line flagged for the symbol/message-similarity surface-match relaxation
  (the prose half lands in P4b's consensus filter).
"""

from __future__ import annotations

import json

import pytest

from harness_maker import codex_adapter


@pytest.mark.parametrize(
    ("codex_sev", "expected"),
    [
        ("critical", "P0"),
        ("high", "P1"),
        ("medium", "P2"),
        ("low", "P3"),
        ("info", "P3"),
    ],
)
def test_severity_map(codex_sev: str, expected: str) -> None:
    assert codex_adapter.map_codex_severity(codex_sev) == expected


def test_severity_map_is_case_insensitive() -> None:
    assert codex_adapter.map_codex_severity("CRITICAL") == "P0"


def test_unknown_severity_raises() -> None:
    with pytest.raises(ValueError, match="unknown codex severity"):
        codex_adapter.map_codex_severity("blocker")


def test_adapt_precise_location() -> None:
    finding = {
        "severity": "high",
        "message": "unbounded retry loop",
        "evidence": "while True:",
        "file": "src/foo.py",
        "line": 42,
    }
    out = codex_adapter.adapt_codex_finding(finding)
    assert out["severity"] == "P1"
    assert out["file"] == "src/foo.py"
    assert out["line"] == 42
    assert out["source"] == "codex"
    assert out["needs_relaxation"] is False
    assert out["summary"] == "unbounded retry loop"


def test_adapt_null_location_flags_relaxation() -> None:
    finding = {
        "severity": "critical",
        "message": "secret committed",
        "evidence": None,
        "file": None,
        "line": None,
    }
    out = codex_adapter.adapt_codex_finding(finding)
    assert out["severity"] == "P0"
    assert out["needs_relaxation"] is True
    assert out["file"] is None


def test_adapt_partial_null_location_flags_relaxation() -> None:
    finding = {
        "severity": "low",
        "message": "style nit",
        "evidence": None,
        "file": "src/foo.py",
        "line": None,
    }
    out = codex_adapter.adapt_codex_finding(finding)
    assert out["needs_relaxation"] is True


def test_adapt_preserves_message_as_summary_for_relaxation() -> None:
    """Null-location relaxation matches on message/symbol — message must survive."""
    finding = {
        "severity": "medium",
        "message": "race on shared counter in increment()",
        "evidence": None,
        "file": None,
        "line": None,
    }
    out = codex_adapter.adapt_codex_finding(finding)
    assert "increment" in out["summary"]


def test_adapt_finding_list_from_findings_envelope() -> None:
    payload = {
        "findings": [{"severity": "high", "message": "m", "file": "a.py", "line": 1}],
        "summary": "s",
    }
    out = codex_adapter.adapt_finding_list(payload)
    assert len(out) == 1
    assert out[0]["severity"] == "P1"


def test_adapt_finding_list_from_bare_list() -> None:
    out = codex_adapter.adapt_finding_list(
        [{"severity": "low", "message": "m", "file": None, "line": None}]
    )
    assert out[0]["needs_relaxation"] is True


def test_cli_adapt_reads_stdin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """REVIEW round 3 finding C: the adapter is now actually invoked (CLI), not prose-only."""
    payload = json.dumps(
        {"findings": [{"severity": "critical", "message": "secret", "file": None, "line": None}]}
    )
    monkeypatch.setattr("sys.stdin", _StdinStub(payload))
    rc = codex_adapter.main(["adapt"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["severity"] == "P0"
    assert out[0]["source"] == "codex"
    assert out[0]["needs_relaxation"] is True


def test_cli_adapt_bad_json_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", _StdinStub("not json"))
    assert codex_adapter.main(["adapt"]) == 1


class _StdinStub:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> str:
        return self._payload
