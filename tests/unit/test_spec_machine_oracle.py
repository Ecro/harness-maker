"""Phase 1 — schema v2: oracle_source + structured property AC + version-safe migration.

Covers PLAN-spec-tetrad-completeness ADR-001/006/007. The critical case is the
migration footgun: an OMITTED schema_version must pin to v1 (oracle_source NOT
required), never inherit the bumped SCHEMA_VERSION constant.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from harness_maker.spec_machine import (
    ORACLE_SOURCES,
    SCHEMA_VERSION,
    AcceptanceCriterion,
    OracleSource,
    SpecMachine,
    load,
    validate,
)


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "SPEC-x.machine.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _v2_base(**ac_overrides) -> dict:
    """A minimal explicit-v2 machine dict with one mechanical AC."""
    ac = {
        "id": "AC-001",
        "title": "render emits content_hash",
        "type": "mechanical",
        "test_ids": [],
        "pending_test": True,
        "executable_predicate": "'content_hash:' in render(answers())",
        "oracle_source": "differential",
        "oracle_evidence": "compared against the reference renderer golden bytes",
    }
    ac.update(ac_overrides)
    return {
        "schema_version": 2,
        "spec_slug": "render",
        "verification_tier": 1,
        "ac": [ac],
    }


# --- enum ------------------------------------------------------------------


def test_oracle_source_enum_has_six_values() -> None:
    expected = {"golden", "differential", "property", "rubric", "consensus", "legacy-unspecified"}
    assert set(ORACLE_SOURCES) == expected
    # OracleSource is a Literal alias usable in annotations.
    assert "legacy-unspecified" in ORACLE_SOURCES


def test_schema_version_constant_is_2() -> None:
    assert SCHEMA_VERSION == 2


# --- migration footgun (ADR-006) -------------------------------------------


def test_omitted_schema_version_pins_to_v1(tmp_path: Path) -> None:
    """The critical case: NO schema_version key → v1, oracle_source NOT required."""
    data = {
        "spec_slug": "legacy",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-001",
                "title": "legacy ac",
                "type": "mechanical",
                "pending_test": True,
                "executable_predicate": "x == 1",
            }
        ],
    }
    model = load(_write(tmp_path, data))
    assert model.schema_version == 1, "omitted version must default to literal 1"
    assert validate(model) == [], "v1 must NOT require oracle_source"


def test_explicit_v1_no_oracle_required(tmp_path: Path) -> None:
    data = {
        "schema_version": 1,
        "spec_slug": "legacy",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-001",
                "title": "legacy ac",
                "type": "mechanical",
                "pending_test": True,
                "executable_predicate": "x == 1",
            }
        ],
    }
    assert validate(load(_write(tmp_path, data))) == []


def test_v1_with_property_ac_is_rejected(tmp_path: Path) -> None:
    """Mixed-file footgun: a v1 file hand-edited to add a property AC must fail loud."""
    data = {
        "schema_version": 1,
        "spec_slug": "legacy",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-001",
                "title": "a property",
                "type": "property",
                "pending_test": True,
                "input_domain": "ints",
                "transformation": "sort",
                "expected_relation": "sorted(sort(x)) == sort(x)",
                "observable_output": "list",
            }
        ],
    }
    errors = validate(load(_write(tmp_path, data)))
    assert any("schema_version: 2" in e for e in errors), errors


# --- v2 oracle requirements (ADR-001/007) ----------------------------------


def test_v2_requires_explicit_oracle_source(tmp_path: Path) -> None:
    data = _v2_base(oracle_source="legacy-unspecified")
    errors = validate(load(_write(tmp_path, data)))
    assert any("oracle_source" in e for e in errors), errors


def test_v2_requires_oracle_evidence(tmp_path: Path) -> None:
    data = _v2_base(oracle_evidence="")
    errors = validate(load(_write(tmp_path, data)))
    assert any("oracle_evidence" in e for e in errors), errors


def test_v2_valid_mechanical_with_evidence(tmp_path: Path) -> None:
    assert validate(load(_write(tmp_path, _v2_base()))) == []


# --- structured property AC (ADR-001, C7) ----------------------------------


def test_property_ac_requires_structured_triple(tmp_path: Path) -> None:
    data = _v2_base(
        id="AC-001",
        type="property",
        oracle_source="property",
        oracle_evidence="metamorphic: roundtrip holds regardless of impl",
        input_domain="arbitrary bytes",
        transformation="encode then decode",
        # expected_relation missing → must error
        observable_output="bytes",
        executable_predicate=None,
    )
    errors = validate(load(_write(tmp_path, data)))
    assert any("expected_relation" in e for e in errors), errors


def test_property_ac_valid_with_full_structure(tmp_path: Path) -> None:
    data = _v2_base(
        id="AC-001",
        type="property",
        oracle_source="property",
        oracle_evidence="metamorphic: roundtrip holds regardless of impl",
        input_domain="arbitrary bytes",
        transformation="encode then decode",
        expected_relation="decode(encode(x)) == x",
        preconditions=["x is well-formed"],
        observable_output="bytes",
        executable_predicate=None,
    )
    assert validate(load(_write(tmp_path, data))) == []


def test_property_ac_defaults_are_backward_compatible() -> None:
    """Constructing an AC without the new fields must not raise (v1 model-level compat)."""
    ac = AcceptanceCriterion(
        id="AC-001", title="t", type="mechanical", executable_predicate="x == 1", pending_test=True
    )
    assert ac.oracle_source == "legacy-unspecified"
    assert ac.oracle_evidence is None


def test_spec_machine_field_default_is_literal_one() -> None:
    """A SpecMachine built without schema_version pins to 1 (not the bumped constant)."""
    m = SpecMachine(spec_slug="x", verification_tier=1)
    assert m.schema_version == 1


def _oracle_source_typing_alias() -> OracleSource:
    return "golden"
