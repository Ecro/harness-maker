"""Replay independent assertions over captured native protocol executions.

This is finite empirical evidence, not a replacement for future live trials.
The expected outcomes were authored before the acting model saw the inputs.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CAPTURE: dict[str, Any] = json.loads(
    (ROOT / "tests/fixtures/world_intent_protocol_observed.json").read_text()
)


def test_capture_is_bound_to_current_protocol() -> None:
    source = ROOT / (
        "src/harness_maker/templates/skills/intent-layer/references/workflow-feedback.md.j2"
    )
    normalized = (source.read_text().rstrip() + "\n").encode()
    assert hashlib.sha256(normalized).hexdigest() == CAPTURE["protocol_sha256_normalized"]
    assert not CAPTURE["errors"]


@pytest.mark.parametrize(
    ("case", "rows", "collection", "outcome"),
    [
        ("ordered_resume", ["a", "b", "c"], "collecting", "pending"),
        ("aborted_missing", ["a", "b", "c"], "complete", "insufficient_evidence"),
        ("failure_open", ["a", "b"], "collecting", "failed"),
        ("denied_reset", ["a", "b", "c"], "complete", "failed"),
        ("successful_abort", ["a", "b", "c"], "complete", "passed"),
        ("noncollector", ["a", "b"], "collecting", "pending"),
        ("incomplete_sources", [], "collecting", "pending"),
    ],
)
def test_native_trial_disposition(
    case: str, rows: list[str], collection: str, outcome: str
) -> None:
    # Parse actual output documents, rather than trusting model summary fields.
    plan: str = CAPTURE["trial_results"][case]["plan"]
    cells = [[c.strip() for c in line.strip("|").split("|")] for line in plan.splitlines()]
    actual_rows = [row[1] for row in cells if len(row) == 5 and row[0].isdigit()]
    assert actual_rows == rows
    assert f"Collection: {collection}" in plan.splitlines()
    assert f"Outcome: {outcome}" in plan.splitlines()


def test_uncertain_evidence_never_becomes_success_or_an_unauthorized_probe() -> None:
    decisions = {d["id"]: d for d in CAPTURE["feedback_results"]}
    assert set(decisions) == {"missing", "stale", "conflict", "window", "terminal"}
    for name, decision in decisions.items():
        assert decision["dependent_success"] is False
        assert decision["measurement_runs"] == 0
        assert CAPTURE["feedback_plans"][f"PLAN-feedback-{name}"]
    for name in ("missing", "stale", "conflict"):
        assert decisions[name]["disposition"] == "pending"
        assert decisions[name]["question"]
    assert decisions["window"]["disposition"] == "deferred"
    assert decisions["window"]["deferred_until"] == "2026-10-06T00:00:00Z"
    assert decisions["window"]["next_trigger"]
    assert decisions["terminal"]["disposition"] == "proposal_pending"
    assert CAPTURE["terminal_before"] == CAPTURE["terminal_after"]


@pytest.mark.parametrize("trigger", ["entry", "observation", "close"])
def test_native_trigger_removal_fails_the_same_feedback_assertion(trigger: str) -> None:
    capture = json.loads((ROOT / "tests/fixtures/world_intent_triggers_observed.json").read_text())
    positive = capture["runs"][f"{trigger}_present"]
    negative = capture["runs"][f"{trigger}_removed"]
    if trigger == "observation":
        assert "Stage entry is already complete" in positive["prompt"]
        assert "this is not task closeout" in positive["prompt"]
    # The ordinary task/context/provisioning prefix is identical; only the stage
    # procedure at the end of the prompt differs.
    assert positive["prompt"].split("\n\n", 1)[0] == negative["prompt"].split("\n\n", 1)[0]

    def feedback_completed(run: dict[str, Any]) -> bool:
        before, after = run["hashes"]["before"], run["hashes"]["after"]
        plan_path = "work-docs/PLAN-fixture-task.md"
        plan: str = run["plan"].lower()
        if before[plan_path] == after[plan_path] or "latency" not in plan:
            return False
        if trigger == "close":
            return "declin" in plan and all(
                before[path] == after[path] for path in before if path != plan_path
            )
        records = yaml.safe_load(run["metrics"])["values"]
        return (
            len(records) == 1
            and records[0]["metric_id"] == "latency"
            and records[0]["value"] == 7
            and "readback" in plan
        )

    assert feedback_completed(positive)
    assert not feedback_completed(negative)
    assert negative["hashes"]["before"] == negative["hashes"]["after"]
