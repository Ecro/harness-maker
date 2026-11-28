"""AC-001 (intent half) — an invalid intent file is refused with the offending field named.

Property over the defect classes of the canonical `intent.yaml` (SPEC-intent-lean): unknown
top-level key, missing required key, duplicate metric id, non-numeric target, missing metric
sub-field, empty purpose statement beside non-empty metrics. The expected field name is the
input's own, so the oracle never reads the validator.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import intent

settings.register_profile("ci", derandomize=True, max_examples=60, deadline=None)
settings.register_profile("dev", max_examples=300, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

# The reference field sets are restated HERE from the SPEC Constraints table, not imported,
# so a validator that shrinks its own constants cannot shrink the oracle with them.
REQUIRED = ("schema_version", "purpose", "metrics")
OPTIONAL = ("rules", "out_of_scope", "open_questions", "owners")
LEGACY = ("mission", "vision", "outcomes", "non_negotiables", "non_scope", "unknowns")
OUTCOME_FIELDS = ("id", "description", "target", "higher_is_better", "how_measured")


def _outcome(i: int, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": f"outcome_{i}",
        "description": f"outcome {i}",
        "target": 10 + i,
        "higher_is_better": bool(i % 2),
        "how_measured": "hm economics stages",
    }
    base.update(over)
    return base


def _valid(n_outcomes: int, optional_subset: tuple[str, ...]) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": 1,
        "purpose": {"statement": "ship a harness people keep", "vision": ""},
        "metrics": [_outcome(i) for i in range(n_outcomes)],
    }
    for k in optional_subset:
        doc[k] = {} if k == "owners" else []
    return doc


def _write(tmp_path: Path, doc: dict[str, Any]) -> Path:
    p = tmp_path / "intent.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return p


_defect = st.sampled_from(
    [
        "unknown_key",
        "missing_required",
        "duplicate_metric_id",
        "non_numeric_target",
        "missing_outcome_subfield",
        "empty_statement_with_metrics",
    ]
)


@given(
    defect=_defect,
    n=st.integers(min_value=1, max_value=3),
    which_required=st.sampled_from(REQUIRED),
    which_sub=st.sampled_from(OUTCOME_FIELDS),
    unknown=st.from_regex(r"[a-z]{3,8}", fullmatch=True).filter(
        lambda k: k not in REQUIRED + OPTIONAL + LEGACY
    ),
)
def test_ac_001_intent_defect_names_its_field(
    tmp_path_factory: Any,
    defect: str,
    n: int,
    which_required: str,
    which_sub: str,
    unknown: str,
) -> None:
    tmp_path = tmp_path_factory.mktemp("intent")
    doc = _valid(n, OPTIONAL)
    if defect == "unknown_key":
        doc[unknown] = "x"
        expected = unknown
    elif defect == "missing_required":
        del doc[which_required]
        expected = which_required
    elif defect == "duplicate_metric_id":
        doc["metrics"].append(_outcome(0))
        expected = "metrics[].id"
    elif defect == "non_numeric_target":
        doc["metrics"][0]["target"] = "ten"
        expected = "metrics[0].target"
    elif defect == "missing_outcome_subfield":
        del doc["metrics"][0][which_sub]
        expected = f"metrics[0].{which_sub}"
    else:
        doc["purpose"]["statement"] = ""
        expected = "purpose.statement"
    errors = intent.validate_intent(_write(tmp_path, doc))
    assert errors, f"{defect}: accepted a defective file"
    assert errors[0].field == expected, (defect, errors[0])


@given(
    n=st.integers(min_value=0, max_value=3),
    subset=st.lists(st.sampled_from(OPTIONAL), unique=True).map(tuple),
)
def test_ac_001_valid_file_with_optional_keys_absent_passes(
    tmp_path_factory: Any, n: int, subset: tuple[str, ...]
) -> None:
    tmp_path = tmp_path_factory.mktemp("intent")
    assert intent.validate_intent(_write(tmp_path, _valid(n, subset))) == []


# ── AC-008 (SPEC-playbook-alignment): validate and load share one major parser ──────────────


@pytest.mark.parametrize(("version", "loads"), [("1.0", True), ("1", True), ("2.0", False)])
def test_ac_008_schema_version_string_loads_when_it_validates(
    tmp_path: Path, version: str, loads: bool
) -> None:
    """The review probe recorded `validate_intent == []` while `load_intent` raised `ValueError`
    for `"1.0"`; the two must agree in both directions."""
    doc = _valid(1, ())
    doc["schema_version"] = version
    p = _write(tmp_path, doc)
    errors = intent.validate_intent(p)
    if loads:
        assert errors == []
        assert intent.load_intent(p).schema_version == 1
    else:
        assert errors
        assert errors[0].field == "schema_version"
        with pytest.raises(intent.IntentInvalidError):
            intent.load_intent(p)
