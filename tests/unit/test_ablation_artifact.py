"""P5 exit criteria — the ablation artifact's shape, not its conclusions.

What this file gates is narrow on purpose. The honesty of the run is an **accepted waiver**
(SPEC AC-005, interview #10), so no test here can or should assert that the measurement was
taken faithfully. What it CAN assert is the structure that makes the waiver survivable:

  * the pre-registration block exists and names every parameter ADR-007 requires;
  * the arm mismatch against the inherited "+47pp" claim is stated;
  * `reproduced` is documented as per-expected-id with causes, never a bare boolean;
  * the natural-experiment analysis says, in the artifact itself, that it does not gate.

The result keys are checked only once the artifact declares `status: complete`. Asserting
them while it is `pre-registered` would force the executor to zero-fill them to go green —
manufacturing exactly the "measured zero vs never measured" conflation that §3.2(c) of the
artifact documents as a real, shipped defect in this repo's own ledger.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_ARTIFACT = Path(__file__).resolve().parents[2] / "work-docs" / "ABLATION-pass2-2026-08-05.md"

_PREREGISTERED_PARAMS = (
    "Corpus",
    "Run count",
    "Arms",
    "Model / prompt version",
    "Cache handling",
    "Cost computation",
    "Tolerated delta",
    "Stage-2 decision rule",
)

_RESULT_KEYS = ("diffs", "pass1_only", "pass1_plus_pass2", "delta", "reproduced")


def _text() -> str:
    assert _ARTIFACT.exists(), f"P5 artifact missing at {_ARTIFACT}"
    return _ARTIFACT.read_text(encoding="utf-8")


def _frontmatter() -> dict[str, object]:
    text = _text()
    assert text.startswith("---\n"), "artifact has no frontmatter"
    parsed = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(parsed, dict)
    return parsed


def test_the_artifact_declares_the_post_removal_arm() -> None:
    """ADR-007: an unqualified result cannot distinguish a wrong claim from a changed pipeline."""
    assert _frontmatter().get("arm") == "post-removal"


def test_the_status_is_one_of_the_two_declared_states() -> None:
    assert _frontmatter().get("status") in {"pre-registered", "complete"}


@pytest.mark.parametrize("param", _PREREGISTERED_PARAMS)
def test_every_preregistered_parameter_is_named(param: str) -> None:
    """ADR-007 enumerates these. A missing one is a parameter free to move after the fact."""
    body = _text()
    section = body[body.index("## 1. Pre-registration") : body.index("## 2. Result")]
    assert f"**{param}**" in section, f"pre-registration does not name {param!r}"


def test_the_arm_mismatch_against_the_inherited_claim_is_stated() -> None:
    """P5 exit criterion 3. The +47pp figure must be named, not alluded to."""
    body = _text()
    assert "+47pp" in body
    assert "arm-mismatch" in body, "the expected-id failure cause for the arm change is missing"


def test_reproduced_is_documented_as_per_id_with_causes() -> None:
    """A bare boolean collapses three meanings, one of which is expected in this arm."""
    body = _text()
    for cause in ("arm-mismatch", "not-reproduced", "not-measurable"):
        assert cause in body, f"failure cause {cause!r} is not defined"


def test_the_natural_experiment_disclaims_gating_in_the_artifact_itself() -> None:
    """ADR-006: n≈6 vs 54, observational, confounded.

    The disclaimer has to live in the artifact, not only in the PLAN — a stage-2 reader
    opens this file, and a table of ratios with no caveat reads as a result.
    """
    body = _text()
    section = body[body.index("## 3. Natural-experiment") : body.index("## 4. Arm mismatch")]
    assert re.search(r"non-?blocking", section, re.IGNORECASE)
    assert "does not gate" in section.lower()


def test_the_severity_gap_is_recorded_rather_than_filled_in() -> None:
    """The ledger has no severity field, so P5's severity comparison is not computable.

    The failure mode this guards is a *plausible* severity table reconstructed from REVIEW
    prose — which would make the executor author the oracle it is graded against. The
    artifact must say the field is absent.
    """
    body = _text()
    assert "no severity field" in body.lower()


def test_result_keys_are_present_once_the_run_is_declared_complete() -> None:
    """Conditional by design — see this module's docstring.

    While `pre-registered`, the keys must be ABSENT, not zero-filled. That direction is
    asserted too: a zero-filled 'complete-looking' result under a pre-registered status is
    the shape that would let an unrun ablation pass for a run one.
    """
    status = _frontmatter().get("status")
    body = _text()
    result = body[body.index("## 2. Result") : body.index("## 3. Natural-experiment")]
    if status == "complete":
        for key in _RESULT_KEYS:
            assert key in result, f"status is complete but result key {key!r} is missing"
    else:
        assert "NOT YET RUN" in result, "a pre-registered artifact must say the run has not run"


def test_the_corpus_is_frozen_before_the_run() -> None:
    """A corpus chosen after seeing a result is not a corpus.

    §1.1 is the gate: `complete` requires the commit ranges to be written down.
    """
    body = _text()
    section = body[body.index("### 1.1 Frozen corpus") : body.index("### 1.2")]
    if _frontmatter().get("status") == "complete":
        assert "NOT YET SELECTED" not in section, "the run completed against an unfrozen corpus"
    else:
        assert "NOT YET SELECTED" in section
