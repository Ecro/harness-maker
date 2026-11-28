"""AC-016 — a missing or foreign-major schema_version is refused naming the file and both versions.

Property over the three file kinds × three defects (missing, older major, newer major), loaded
through each kind's own validator. SPEC-intent-lean: the legacy assumptions file is gone, the
outcomes ledger is `.claude/intent/metrics.yaml` and the record is `intent/<ID>.md`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import intent, intent_cli
from tests.unit import intent_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

KINDS = ("intent", "metrics", "record")


def _path(root: Path, kind: str) -> Path:
    return {
        "intent": root / ".claude" / "intent.yaml",
        "metrics": fx.metrics_path(root),
        "record": fx.record_path(root, "OBJ-1"),
    }[kind]


def _errors(root: Path, kind: str) -> list[Any]:
    p = _path(root, kind)
    if kind == "intent":
        return intent.validate_intent(p)
    if kind == "metrics":
        return intent_cli.metrics_errors(p, fx.load(p), set())[0]
    return intent_cli.record_errors(p, fx.load(p), {"onboarding_minutes"})


@given(
    kind=st.sampled_from(KINDS),
    defect=st.sampled_from(("missing", "older", "newer")),
    delta=st.integers(min_value=1, max_value=40),
)
def test_ac_016_foreign_or_missing_version_is_refused_naming_path_and_versions(
    tmp_path_factory: Any, kind: str, defect: str, delta: int
) -> None:
    root = fx.build_root(tmp_path_factory.mktemp("v"), git=False, records=[fx.record("OBJ-1")])
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
