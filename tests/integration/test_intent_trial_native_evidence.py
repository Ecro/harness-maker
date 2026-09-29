"""Independent replay checks over captured native Codex session A/B executions.

`test_s1_trial_procedure_renders_both_supported_hosts` was retired by
SPEC-intent-layer-improvements (2026-09-29): the trial is frozen and AC-007 requires that no
rendered reference carries the trial procedure. The captured sessions remain historical evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[2]
CAPTURE: dict[str, Any] = json.loads(
    (ROOT / "tests/fixtures/intent_feedback_continuity_native_observed.json").read_text()
)
EDGE: dict[str, Any] = json.loads(
    (ROOT / "tests/fixtures/intent_feedback_continuity_native_edge_observed.json").read_text()
)


def test_s1_native_stage_entry_recovers_prior_session_without_repair_prompt() -> None:
    # The capture ran against the Real-task trial protocol that SPEC-intent-layer-improvements
    # retired (trial frozen, 2026-09-29). Its exact bytes are kept as a fixture so this historical
    # evidence stays bound to the protocol it observed rather than to the live template.
    protocol = ROOT / "tests/fixtures/workflow-feedback-trial-protocol.md.j2.txt"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == CAPTURE["protocol_sha256"]
    assert CAPTURE["session_a"]["exit"] == 0
    assert CAPTURE["session_b"]["exit"] == 0
    assert CAPTURE["status_before_b"]["candidates"] == ["a"]
    assert CAPTURE["status_before_b"]["cohort"] == []
    assert "trial_feedback:" in CAPTURE["source_doc_after_a"]
    assert "a-observation" in CAPTURE["source_doc_after_a"]
    assert any(
        "harness_maker.hm intent --root" in command and " trial reconcile " in command
        for command in CAPTURE["session_b"]["commands"]
    )
    assert CAPTURE["status_after_b"]["cohort"] == ["a"]
    assert CAPTURE["status_after_b"]["outcome"] == "pending"
    trial = yaml.safe_load(CAPTURE["trial_doc_after_b"].split("---", 2)[1])["trial"]
    assert [member["task"] for member in trial["members"]] == ["a"]
    assert trial["decisions"] == []


def test_s1_removing_stage_entry_trigger_breaks_same_recovery_assertion() -> None:
    assert CAPTURE["control"]["exit"] == 0
    assert CAPTURE["control_status"]["cohort"] == []
    assert not any(" trial reconcile " in command for command in CAPTURE["control"]["commands"])
    path = "work-docs/PLAN-field-trial.md"
    assert CAPTURE["source_hash_before"][path] != CAPTURE["source_hash_after"][path]
    assert CAPTURE["source_hash_before"][path] == CAPTURE["control_hash_after"][path]


def test_s1_native_closeout_preserves_terminal_evidence_and_pending_judgment() -> None:
    case = EDGE["closeout"]
    assert case["actor"]["exit"] == 0
    assert "a-terminal" in case["source_doc"]
    assert "conversation:a:terminal" in case["source_doc"]
    assert case["state"]["tasks"]["a"]["terminal"] is True
    assert case["state"]["cohort"] == ["a"]
    assert case["state"]["outcome"] == "pending"
    assert case["before_hash"] != case["after_hash"]
    assert any(" trial reconcile " in command for command in case["actor"]["commands"])


def test_s3_native_revocation_and_unavailable_source_leave_trial_unchanged() -> None:
    revoked = EDGE["revoked"]
    unavailable = EDGE["unavailable"]
    for case in (revoked, unavailable):
        assert case["actor"]["exit"] == 0
        assert case["state"]["cohort"] == []
        assert case["before_hash"] == case["after_hash"]
        assert not any(" trial reconcile " in command for command in case["actor"]["commands"])
    assert revoked["state"]["reason"] == "authority_required"
    assert unavailable["state"]["reason"] == "source_incomplete"
    assert ".worktrees/evidence" in unavailable["state"]["source"]
