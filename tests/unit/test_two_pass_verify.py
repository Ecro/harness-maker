"""Phase A2 — verify() subcommand: reduce-only verifier with fallback.

PLAN-llm-code-review-2026 ADR-002 inserts the verifier at Pass 1.5. Required
unit coverage per the PLAN A2 exit criterion: 5 cases listed below.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Any

import pytest

from harness_maker.two_pass_review import (
    ModelUnavailableError,
    VerifierClient,
    verify_findings,
)

PASS1_CONTEXT = {
    "pr_title": "[REDACTED]",
    "pr_description": "[REDACTED]",
    "author": "[REDACTED]",
    "diff": "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
}

REAL_FINDING = {
    "severity": "P0",
    "file": "x.py",
    "line": 1,
    "summary": "Off-by-one in loop",
    "suggestion": "Use range(n) not range(n+1)",
    "reasoning": (
        "OBSERVE: range(n+1) iterates n+1 times. "
        "INFER: last iteration accesses [n]. CONCLUDE: IndexError."
    ),
}

SPURIOUS_FINDING = {
    "severity": "P0",
    "file": "x.py",
    "line": 1,
    "summary": "Missing input validation",
    "suggestion": "Validate input",
    "reasoning": (
        "OBSERVE: function takes user data. "
        "INFER: could be malformed. CONCLUDE: might crash."
    ),
}


class _FakeClient:
    """Records the prompt and returns a canned response."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[tuple[str, str, str]] = []

    def verify(self, system: str, user: str, model: str) -> str:  # noqa: D401
        self.calls.append((system, user, model))
        return self._response


class _RaisingClient:
    """Always raises ModelUnavailableError."""

    def verify(self, system: str, user: str, model: str) -> str:  # noqa: D401
        raise ModelUnavailableError("403 forbidden: model not enabled for account")


def test_verify_drops_unverified_inference() -> None:
    """When the LLM returns DROP for the spurious finding, kept must omit it."""
    response = json.dumps(
        {
            "decisions": [
                {"index": 0, "action": "drop", "reason": "INFER not supported by diff alone"},
            ]
        }
    )
    client: VerifierClient = _FakeClient(response)

    result = verify_findings([SPURIOUS_FINDING], PASS1_CONTEXT, client=client)

    assert result["stats"]["input_n"] == 1
    assert result["stats"]["kept_n"] == 0
    assert result["stats"]["dropped_n"] == 1
    assert result["kept"] == []
    assert result["dropped"][0]["finding"] == SPURIOUS_FINDING
    assert "INFER" in result["dropped"][0]["reason"]


def test_verify_handles_empty_findings() -> None:
    """Empty input → all-zero stats, no LLM call."""
    client: VerifierClient = _FakeClient("UNUSED")
    result = verify_findings([], PASS1_CONTEXT, client=client)

    assert result["kept"] == []
    assert result["dropped"] == []
    assert result["stats"] == {"input_n": 0, "kept_n": 0, "dropped_n": 0, "demoted_n": 0}
    # No LLM should be called for empty input.
    assert client.calls == []  # type: ignore[attr-defined]


def test_verify_preserves_kept_finding_fields() -> None:
    """KEEP path returns the original finding record unchanged (field-for-field)."""
    response = json.dumps(
        {"decisions": [{"index": 0, "action": "keep", "reason": "diff-cited reasoning"}]}
    )
    client: VerifierClient = _FakeClient(response)

    result = verify_findings([REAL_FINDING], PASS1_CONTEXT, client=client)

    assert result["stats"]["kept_n"] == 1
    kept = result["kept"][0]
    for field in ("severity", "file", "line", "summary", "suggestion", "reasoning"):
        assert kept[field] == REAL_FINDING[field], f"{field} mutated"


def test_verify_invariant_no_introduction() -> None:
    """Out-of-range / fabricated indices in LLM response must be silently dropped.

    The verifier role is reduce-only — kept ⊆ input. If the LLM hallucinates
    a finding (index out of bounds), it MUST NOT appear in the kept list.
    """
    response = json.dumps(
        {
            "decisions": [
                {"index": 0, "action": "keep"},
                # Fabricated index 5 — not in the 1-element input.
                {"index": 5, "action": "keep", "reason": "hallucinated finding"},
            ]
        }
    )
    client: VerifierClient = _FakeClient(response)

    result = verify_findings([REAL_FINDING], PASS1_CONTEXT, client=client)

    # Exactly one input → kept must be ≤ 1.
    assert result["stats"]["kept_n"] == 1
    assert len(result["kept"]) == 1
    # The kept record is identifiable as the input, not the fabrication.
    assert result["kept"][0] == REAL_FINDING


def test_verify_falls_back_on_model_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the verifier client raises ModelUnavailableError, returns input unchanged.

    Guards failures.md [fail:review] reviewer-subagent-model-unsupported (2026-05-11).
    """
    client: VerifierClient = _RaisingClient()

    with caplog.at_level(logging.WARNING, logger="harness_maker.two_pass_review"):
        result = verify_findings([REAL_FINDING], PASS1_CONTEXT, client=client)

    # Fallback contract: kept == input, dropped == [], fallback marker present.
    assert result["kept"] == [REAL_FINDING]
    assert result["dropped"] == []
    assert result["stats"]["input_n"] == 1
    assert result["stats"]["kept_n"] == 1
    assert result["stats"]["dropped_n"] == 0
    assert result["stats"].get("fallback") == "model_unavailable"
    # Warning emitted so operators see the degraded path in logs.
    assert any("model unavailable" in rec.message.lower() for rec in caplog.records), (
        "warning log must mention model unavailability"
    )


# ── CLI subcommand surface ────────────────────────────────────────────────────


def _run_cli(stdin: str, *argv: str) -> subprocess.CompletedProcess[str]:
    """Run `python -m harness_maker.two_pass_review verify` as a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.two_pass_review", *argv],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_verify_cli_rejects_missing_stdin() -> None:
    proc = _run_cli("", "verify")
    assert proc.returncode != 0
    assert "stdin" in proc.stderr.lower() or "invalid" in proc.stderr.lower()


def test_verify_cli_rejects_malformed_payload() -> None:
    proc = _run_cli('{"pass1_findings": "not-a-list"}', "verify")
    assert proc.returncode != 0
    assert "list" in proc.stderr.lower()


# ── shape contracts for downstream consumers ────────────────────────────────


def test_verify_stats_invariant_input_equals_kept_plus_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """input_n == kept_n + dropped_n — the structural guarantee of reduce-only."""
    findings = [REAL_FINDING, SPURIOUS_FINDING]
    response = json.dumps(
        {
            "decisions": [
                {"index": 0, "action": "keep"},
                {"index": 1, "action": "drop", "reason": "speculative"},
            ]
        }
    )
    client: VerifierClient = _FakeClient(response)

    result = verify_findings(findings, PASS1_CONTEXT, client=client)

    s: dict[str, Any] = result["stats"]
    assert s["input_n"] == s["kept_n"] + s["dropped_n"]


# ── DEMOTE branch coverage (code-reviewer P1 + security-reviewer P1) ──────────


def test_verify_demote_with_valid_lower_tier_applies() -> None:
    """LLM-supplied new_severity that's strictly lower-tier than current applies."""
    p1 = {**REAL_FINDING, "severity": "P0"}
    response = json.dumps(
        {
            "decisions": [
                {
                    "index": 0,
                    "action": "demote",
                    "new_severity": "P1",
                    "reason": "blast radius overstated",
                }
            ]
        }
    )
    result = verify_findings([p1], PASS1_CONTEXT, client=_FakeClient(response))

    assert result["stats"]["kept_n"] == 1
    assert result["stats"]["demoted_n"] == 1
    kept = result["kept"][0]
    assert kept["severity"] == "P1"
    assert "verifier_note" in kept
    assert "demoted" in kept["verifier_note"]


def test_verify_demote_rejects_promotion_attempt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reduce-only invariant: a demote action with a HIGHER tier must NOT promote.

    Guards security-reviewer P1: a jailbroken verifier response
    {"action":"demote","new_severity":"P0"} on a P2 finding must NOT silently
    promote it to P0.
    """
    p2 = {**REAL_FINDING, "severity": "P2"}
    response = json.dumps(
        {"decisions": [{"index": 0, "action": "demote", "new_severity": "P0"}]}
    )
    with caplog.at_level(logging.WARNING, logger="harness_maker.two_pass_review"):
        result = verify_findings([p2], PASS1_CONTEXT, client=_FakeClient(response))

    # Promotion rejected → falls back to one-tier demote (P2 → P3).
    assert result["kept"][0]["severity"] == "P3", "promotion attempt must not stand"
    assert any(
        "promote" in r.message.lower() for r in caplog.records
    ), "warning must be emitted when promotion is attempted"


def test_verify_demote_with_missing_new_severity_no_silent_lie() -> None:
    """Demote without new_severity that can't actually change severity must NOT inflate demoted_n.

    Guards code-reviewer P1: the prior fallback could record a demotion that
    didn't actually change severity (e.g. P3 → P3). After the fix, this is
    recorded as plain KEEP (no demoted_n bump).
    """
    p3 = {**REAL_FINDING, "severity": "P3"}  # already at the lowest tier
    response = json.dumps(
        {"decisions": [{"index": 0, "action": "demote"}]}  # no new_severity
    )
    result = verify_findings([p3], PASS1_CONTEXT, client=_FakeClient(response))

    # P3 → P3 (no real demotion possible) — must NOT inflate demoted_n.
    assert result["kept"][0]["severity"] == "P3"
    assert result["stats"]["demoted_n"] == 0, (
        "demoted_n must not inflate when severity didn't actually change"
    )


def test_verify_demote_invalid_severity_string_falls_back() -> None:
    """An invalid new_severity (e.g. 'CRITICAL') falls back to deterministic demote."""
    p0 = {**REAL_FINDING, "severity": "P0"}
    response = json.dumps(
        {"decisions": [{"index": 0, "action": "demote", "new_severity": "CRITICAL"}]}
    )
    result = verify_findings([p0], PASS1_CONTEXT, client=_FakeClient(response))

    # Invalid string ignored, one-tier demote applied (P0 → P1).
    assert result["kept"][0]["severity"] == "P1"
    assert result["stats"]["demoted_n"] == 1
