"""AC-016 — a missing or foreign-major schema_version is refused naming the file and both versions.

Property over the four file kinds × three defects (missing, older major, newer major), loaded
through each kind's own loader.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import intent, world
from tests.unit import world_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

KINDS = ("intent", "assumptions", "outcomes", "objective")


def _path(root: Path, kind: str) -> Path:
    return {
        "intent": root / ".claude" / "intent.yaml",
        "assumptions": fx.assumptions_path(root),
        "outcomes": fx.outcomes_path(root),
        "objective": fx.objective_doc_path(root, "OBJ-1"),
    }[kind]


def _errors(root: Path, kind: str) -> list[Any]:
    p = _path(root, kind)
    if kind == "intent":
        return intent.validate_intent(p)
    if kind == "assumptions":
        return world.validate_assumptions(p)
    if kind == "outcomes":
        return world.validate_outcomes(p, intent_outcomes={})
    return world.validate_objective(
        p, intent_outcomes={"onboarding_minutes": 10}, assumption_ids=set()
    )


@given(
    kind=st.sampled_from(KINDS),
    defect=st.sampled_from(("missing", "older", "newer")),
    delta=st.integers(min_value=1, max_value=40),
)
def test_ac_016_foreign_or_missing_version_is_refused_naming_path_and_versions(
    tmp_path_factory: Any, kind: str, defect: str, delta: int
) -> None:
    root = fx.build_root(
        tmp_path_factory.mktemp("v"), git=False, objectives=[fx.objective("OBJ-1")]
    )
    p = _path(root, kind)
    doc = fx.load(p)
    if defect == "missing":
        doc.pop("schema_version")
        found_repr = "missing"
    elif defect == "older":
        doc["schema_version"] = fx.KNOWN_MAJOR - delta
        found_repr = str(doc["schema_version"])
    else:
        doc["schema_version"] = fx.KNOWN_MAJOR + delta
        found_repr = str(doc["schema_version"])
    fx.dump(p, doc)
    errors = _errors(root, kind)
    assert errors, (kind, defect)
    first = errors[0]
    assert first.field == "schema_version"
    assert str(p) in first.message
    assert found_repr in first.message
    assert str(fx.KNOWN_MAJOR) in first.message
