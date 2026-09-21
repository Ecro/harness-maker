"""Owners contract from HANDOFF sections 2/9, independently enumerated.

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

from harness_maker import intent, world
from harness_maker.models import Target
from tests.unit import world_fixture as fx
from tests.unit.test_render_intent_layer import _render_target


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


@pytest.mark.parametrize(
    "roles",
    [
        {"owner": "alice", "dri": "bob"},
        {"owner": "alice", "dri": "alice", "team": "builders"},
        {"owner": "Alice", "dri": "alice"},
    ],
)
def test_s3(tmp_path: Path, roles: dict[str, str]) -> None:
    doc = fx.intent_doc(fx.outcome())
    doc["owners"] = roles
    root = fx.build_root(tmp_path, intent=doc, objectives=[fx.objective()])
    proc = fx.run_cli(["objective", "approve", "OBJ-1", "--json"], root)
    expected = (0, True, True, True, True)
    result = (
        proc.returncode,
        "advisory" in proc.stderr,
        "unverified" in proc.stderr,
        "CODEOWNERS" in proc.stderr,
        "branch protection" in proc.stderr,
    )
    assert result == expected, (proc.stdout, proc.stderr)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True
    assert fx.stdout_json(proc)["objective"]["approval"]["approved_by"] == fx.GIT_NAME


@pytest.mark.parametrize(
    "roles",
    [
        None,
        {},
        [],
        {"owner": "alice"},
        {"owner": " alice ", "dri": "alice", "team": "alice"},
        {"owner": "", "dri": "alice", "team": "  "},
    ],
)
def test_s4(tmp_path: Path, roles: Any) -> None:
    doc = fx.intent_doc(fx.outcome())
    if roles is None:
        doc.pop("owners")
    else:
        doc["owners"] = roles
    root = fx.build_root(tmp_path, intent=doc, objectives=[fx.objective()])
    expected = roles if isinstance(roles, dict) else {}
    result = intent.load_intent(root / ".claude/intent.yaml").owners
    assert result == expected
    proc = fx.run_cli(["objective", "approve", "OBJ-1", "--json"], root)
    assert proc.returncode == 0, proc.stdout
    assert "advisory" not in proc.stderr
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True


@pytest.mark.parametrize(
    ("target", "path"),
    [
        (Target.CLAUDE_CODE, ".claude/skills/intent-layer/SKILL.md"),
        (Target.CODEX, ".agents/skills/intent-layer/SKILL.md"),
    ],
)
def test_s5(target: Target, path: str) -> None:
    text = _render_target([target])[path]
    expected = (True, True, True, True)
    result = (
        "Distinct nonblank `owners` roles trigger an advisory at approval, never a block." in text,
        "advisory" in text,
        "unverified" in text,
        "CODEOWNERS + branch protection" in text,
    )
    assert result == expected
