"""AC-002 — make creates the typed skeleton and the strict loader accepts it as not_filled_in.

Module-level half of the predicate: raw YAML types, key set, `schema_version` filled, the same
`validate_intent` AC-001 uses accepts the file, `is_not_filled_in` is true, and the half-filled
file (empty mission, one outcome) is an error naming `mission`. The `hm world status --json`
clauses of AC-002 are exercised in `test_world_status_and_revisit.py` once the `world` module
exists (PLAN P2) — the skeleton must not be judged through a CLI that P1 does not ship.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from harness_maker import intent

REQUIRED = {"schema_version", "mission", "outcomes"}
OPTIONAL = {"vision", "non_negotiables", "non_scope", "unknowns", "owners"}
LIST_FIELDS = {"outcomes", "non_negotiables", "non_scope", "unknowns", "owners"}
KNOWN_MAJOR = 1


def test_ac_002_skeleton_is_typed_empty_and_loads_under_the_strict_validator(
    tmp_path: Path,
) -> None:
    made = tmp_path / ".claude" / "intent.yaml"
    assert intent.write_skeleton_if_absent(made) is True
    raw = yaml.safe_load(made.read_text(encoding="utf-8"))
    assert set(raw) == REQUIRED | OPTIONAL
    assert raw["mission"] == ""
    assert raw["vision"] == ""
    assert all(raw[k] == [] for k in LIST_FIELDS)
    assert raw["schema_version"] == KNOWN_MAJOR
    assert intent.validate_intent(made) == []
    assert intent.is_not_filled_in(intent.load_intent(made)) is True


def test_ac_002_skeleton_carries_no_generated_prose_only_comments_and_empties(
    tmp_path: Path,
) -> None:
    made = tmp_path / "intent.yaml"
    intent.write_skeleton_if_absent(made)
    body = [
        line
        for line in made.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    # Every non-comment line is a key with an empty value or the version — no prose.
    for line in body:
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        assert key.strip() in REQUIRED | OPTIONAL, line
        assert value.strip() in {"", '""', "[]", str(KNOWN_MAJOR)}, line


def test_ac_002_half_filled_file_is_an_error_naming_mission_not_a_skeleton(tmp_path: Path) -> None:
    p = tmp_path / "intent.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "mission": "",
                "outcomes": [
                    {
                        "id": "x",
                        "description": "d",
                        "target": 1,
                        "higher_is_better": True,
                        "how_measured": "m",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    errors = intent.validate_intent(p)
    assert errors
    assert errors[0].field == "mission"
