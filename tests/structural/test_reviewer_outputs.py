"""Phase A5 — verifier behavior on the labeled adversarial fixture.

PLAN-llm-code-review-2026 ADR-005: labeled-fixture mode lets us compute the
verifier's incorrect-rate without depending on a live LLM at CI time. The
fixture has ground-truth labels; this test runs verify_findings() with a
deterministic mock that mirrors the verifier's intended behavior and asserts
the structural invariants:

1. ``set(kept ∪ dropped.finding) == set(input)`` (no introduction).
2. The verifier's drops cover only ground_truth='spurious' findings.
3. The verifier's keeps cover only ground_truth='real' findings.
4. Telemetry-shape integers add up: ``input_n == kept_n + dropped_n``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.two_pass_review import VerifierClient, verify_findings

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "adversarial_findings.json"


@pytest.fixture(scope="module")
def adversarial() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


class _LabeledOracleClient:
    """Deterministic verifier — drops every spurious record, keeps every real one.

    Mirrors the role described in ``code-verifier_body.md.j2``; lets us run
    invariant checks without a live LLM call.
    """

    def __init__(self, findings: list[dict[str, Any]]) -> None:
        self._findings = findings

    def verify(self, system: str, user: str, model: str) -> str:  # noqa: D401
        decisions = []
        for i, f in enumerate(self._findings):
            if f.get("ground_truth") == "spurious":
                decisions.append(
                    {"index": i, "action": "drop", "reason": "ground_truth=spurious"}
                )
            else:
                decisions.append({"index": i, "action": "keep"})
        return json.dumps({"decisions": decisions})


def test_adversarial_fixture_present_and_well_formed(adversarial: dict[str, Any]) -> None:
    assert adversarial["fixture_label"] == "adv-fix-001"
    findings = adversarial["pass1_findings"]
    assert len(findings) >= 3, "fixture must have at least 3 findings to exercise drops"
    # Every finding must carry a ground-truth label.
    for f in findings:
        assert f["ground_truth"] in {"real", "spurious"}, f
        assert {"severity", "file", "line", "summary", "reasoning"}.issubset(f.keys())


def test_verifier_drops_all_spurious(adversarial: dict[str, Any]) -> None:
    findings = adversarial["pass1_findings"]
    client: VerifierClient = _LabeledOracleClient(findings)
    result = verify_findings(findings, adversarial["pass1_context"], client=client)

    kept_ids = {k["id"] for k in result["kept"]}
    dropped_ids = {d["finding"]["id"] for d in result["dropped"]}
    assert kept_ids == set(adversarial["expected_keep_ids"]), (
        f"unexpected kept set: {kept_ids}"
    )
    assert dropped_ids == set(adversarial["expected_drop_ids"]), (
        f"unexpected dropped set: {dropped_ids}"
    )


def test_verifier_invariant_no_introduction_on_fixture(adversarial: dict[str, Any]) -> None:
    """The reduce-only invariant must hold for every fixture run."""
    findings = adversarial["pass1_findings"]
    client: VerifierClient = _LabeledOracleClient(findings)
    result = verify_findings(findings, adversarial["pass1_context"], client=client)

    input_ids = {f["id"] for f in findings}
    output_ids = {k["id"] for k in result["kept"]} | {
        d["finding"]["id"] for d in result["dropped"]
    }
    assert output_ids == input_ids, (
        f"set(kept ∪ dropped) != input: extra {output_ids - input_ids}, "
        f"missing {input_ids - output_ids}"
    )


def test_verifier_stats_arithmetic(adversarial: dict[str, Any]) -> None:
    findings = adversarial["pass1_findings"]
    client: VerifierClient = _LabeledOracleClient(findings)
    result = verify_findings(findings, adversarial["pass1_context"], client=client)

    s = result["stats"]
    assert s["input_n"] == len(findings)
    assert s["input_n"] == s["kept_n"] + s["dropped_n"]
    # Drops a strict superset of {spurious findings} → at least 1 drop on fixture-001.
    assert s["dropped_n"] >= len(adversarial["expected_drop_ids"])
