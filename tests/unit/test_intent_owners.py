"""Owners contract from HANDOFF sections 2/9, independently enumerated.

SPEC-intent-lean removed the approval stamp, so S3/S4 (owners advisory at approval) and S5 (its
skill prose) went with it; S1/S2 (the role map and its validation) stay.

S4's absent/legacy cases assert the normalized map before approving: the old tuple
cannot satisfy them. S2 pins field-specific failures rather than mere rejection.
Its malformed legacy list/string cases pass before implementation: these negative
compatibility invariants
must reject the wrong permissive/coercing implementation once the RED positive sibling
S1[value2-expected2] forces legacy-to-role-map normalization into existence.
"""

from pathlib import Path
from typing import Any

import pytest

from harness_maker import intent
from tests.unit import intent_fixture as fx


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            {"owner": "alice", "dri": "bob", "team": "builders"},
            {"owner": "alice", "dri": "bob", "team": "builders"},
        ),
        ({"dri": "alice"}, {"dri": "alice"}),
        (["alice", "bob"], {"team": "alice, bob"}),
        ([], {}),
        ({}, {}),
    ],
)
def test_s1(tmp_path: Path, value: Any, expected: dict[str, str]) -> None:
    doc = fx.intent_doc(fx.outcome())
    doc["owners"] = value
    path = tmp_path / "intent.yaml"
    fx.dump(path, doc)
    result = intent.load_intent(path).owners
    assert result == expected
    assert intent.load_intent(path).schema_version == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"approver": "alice"}, "owners.approver"),
        ({"dri": 7}, "owners.dri"),
        ({"owner": None}, "owners.owner"),
        (["alice", 7], "owners[1]"),
        ("alice", "owners"),
    ],
)
def test_s2(tmp_path: Path, value: Any, expected: str) -> None:
    doc = fx.intent_doc(fx.outcome())
    doc["owners"] = value
    path = tmp_path / "intent.yaml"
    fx.dump(path, doc)
    errors = intent.validate_intent(path)
    result = errors[0].field
    assert result == expected
    with pytest.raises(intent.IntentInvalidError):
        intent.load_intent(path)
