"""Tests for non-mechanical AC forward-binding (property + parametric).

PLAN-nonmechanical-ac-binding:
- Phase 1: `select_pytest_bindable` selector + property write-back is type-agnostic.
- Phase 2: `load_golden_table` / `GoldenTableError` (parametric SSOT).
- Phase 3: the wrapup Production-block predicate (resolved-but-pending by collect, fail-closed).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from harness_maker.spec_machine import (
    AcceptanceCriterion,
    GoldenRow,
    SpecMachine,
    mark_tested,
)

# ---------------------------------------------------------------------------
# Phase 1 — select_pytest_bindable selector
# ---------------------------------------------------------------------------


def _ac(ac_id: str, ac_type: str, *, pending: bool = False) -> AcceptanceCriterion:
    """Construct a minimal AC of a given type (model construction does not gate
    per-type fields — that is `validate()`; the selector keys on `type` only)."""
    return AcceptanceCriterion(id=ac_id, title=f"{ac_type} ac", type=ac_type, pending_test=pending)


def _model(*acs: AcceptanceCriterion) -> SpecMachine:
    return SpecMachine(schema_version=2, spec_slug="demo", verification_tier=1, ac=list(acs))


def test_select_pytest_bindable_includes_deterministic_excludes_judgment() -> None:
    from harness_maker.spec_machine import select_pytest_bindable

    model = _model(
        _ac("AC-001", "mechanical"),
        _ac("AC-002", "property"),
        _ac("AC-003", "parametric"),
        _ac("AC-004", "judgment"),
    )
    got = {ac.id for ac in select_pytest_bindable(model)}
    assert got == {"AC-001", "AC-002", "AC-003"}, "judgment must be excluded; the other 3 included"


def test_select_pytest_bindable_pending_only_filter() -> None:
    from harness_maker.spec_machine import select_pytest_bindable

    model = _model(
        _ac("AC-001", "property", pending=True),
        _ac("AC-002", "parametric", pending=False),
        _ac("AC-003", "judgment", pending=True),  # judgment excluded regardless of pending
    )
    got = {ac.id for ac in select_pytest_bindable(model, pending_only=True)}
    assert got == {"AC-001"}, "pending_only keeps only pending closed-type ACs"


# ---------------------------------------------------------------------------
# Phase 1 — mark_tested is type-agnostic (property binds like mechanical)
# ---------------------------------------------------------------------------


def _property_yaml(tmp_path: Path) -> tuple[Path, Path]:
    """A v2 machine yaml + md with one pending property AC (test_ids empty = the miss shape)."""
    data = {
        "schema_version": 2,
        "spec_slug": "demo",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-001",
                "title": "reverse-sort invariant",
                "type": "property",
                "oracle_source": "property",
                "oracle_evidence": "metamorphic relation, implementation-independent",
                "input_domain": "lists of ints",
                "transformation": "sort then reverse",
                "expected_relation": "reverse(sort(x)) == sort(x, reverse=True)",
                "observable_output": "the ordered list",
                "pending_test": True,
            }
        ],
    }
    y = tmp_path / "SPEC-demo.machine.yaml"
    y.write_text(yaml.safe_dump(data))
    m = tmp_path / "SPEC-demo.md"
    m.write_text("---\ntier: 1\n---\n\n### AC-001\nreverse-sort invariant\n")
    return y, m


def test_mark_tested_binds_property_ac(tmp_path: Path) -> None:
    """A property AC flips pending->false + records test_ids exactly like a mechanical AC.

    validate_after=False isolates the flip/record contract from the pytest-collect
    gate (the collect resolution is mark_tested's existing behavior, exercised elsewhere)."""
    y, m = _property_yaml(tmp_path)
    errors = mark_tested(
        y,
        m,
        {"AC-001": ["tests/unit/test_demo.py::test_reverse_sort"]},
        validate_after=False,
    )
    assert errors == [], f"unexpected errors: {errors}"
    from harness_maker.spec_machine import load

    bound = load(y).ac[0]
    assert bound.pending_test is False, "property AC must flip pending->false"
    assert bound.test_ids == ["tests/unit/test_demo.py::test_reverse_sort"]


# ---------------------------------------------------------------------------
# Phase 2 — load_golden_table SSOT + GoldenTableError (ADR-003/006)
# ---------------------------------------------------------------------------


def _parametric_yaml(tmp_path: Path, golden: list[dict] | None = None) -> Path:
    data = {
        "schema_version": 2,
        "spec_slug": "demo",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-010",
                "title": "adder golden",
                "type": "parametric",
                "oracle_source": "golden",
                "oracle_evidence": "hand-curated golden rows",
                "golden_table": golden
                if golden is not None
                else [
                    {"input": {"a": 1, "b": 2}, "expected": 3},
                    {"input": {"a": -1, "b": 1}, "expected": 0, "edge": True, "note": "zero"},
                ],
            },
            {
                "id": "AC-011",
                "title": "a mechanical one",
                "type": "mechanical",
                "executable_predicate": "f(x) == 1",
            },
        ],
    }
    y = tmp_path / "SPEC-demo.machine.yaml"
    y.write_text(yaml.safe_dump(data))
    return y


def test_load_golden_table_happy(tmp_path: Path) -> None:
    from harness_maker.spec_machine import load_golden_table

    rows = load_golden_table(_parametric_yaml(tmp_path), "AC-010")
    assert [r.expected for r in rows] == [3, 0]
    assert all(isinstance(r, GoldenRow) for r in rows)
    assert rows[1].edge is True


def test_load_golden_table_unknown_id_raises(tmp_path: Path) -> None:
    from harness_maker.spec_machine import GoldenTableError, load_golden_table

    with pytest.raises(GoldenTableError) as ei:
        load_golden_table(_parametric_yaml(tmp_path), "AC-999")
    assert "AC-999" in str(ei.value)


def test_load_golden_table_non_parametric_raises(tmp_path: Path) -> None:
    from harness_maker.spec_machine import GoldenTableError, load_golden_table

    with pytest.raises(GoldenTableError) as ei:
        load_golden_table(_parametric_yaml(tmp_path), "AC-011")  # mechanical
    assert "AC-011" in str(ei.value)
    assert "parametric" in str(ei.value).lower()


def test_load_golden_table_empty_table_raises(tmp_path: Path) -> None:
    from harness_maker.spec_machine import GoldenTableError, load_golden_table

    y = _parametric_yaml(tmp_path, golden=[])
    with pytest.raises(GoldenTableError):
        load_golden_table(y, "AC-010")


def test_load_golden_table_nonexistent_path_raises(tmp_path: Path) -> None:
    from harness_maker.spec_machine import GoldenTableError, load_golden_table

    with pytest.raises(GoldenTableError):
        load_golden_table(tmp_path / "does-not-exist.machine.yaml", "AC-010")


# ---------------------------------------------------------------------------
# Phase 3 — wrapup Production-block predicate (resolved-but-pending by collect)
# ---------------------------------------------------------------------------


def test_find_unbound_closed_type_acs_flags_collectable_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A closed-type AC whose convention OR recorded test collects while pending = a miss."""
    from harness_maker import spec_machine

    y, m = _property_yaml(tmp_path)  # AC-001 property, pending, no test_ids

    # Pretend the convention-named test collects (ran cleanly → (set, True)).
    monkeypatch.setattr(
        spec_machine, "_collectable_ac_tests", lambda model, cwd: ({"AC-001"}, True)
    )
    misses = spec_machine.find_unbound_closed_type_acs(y, m.parent)
    assert "AC-001" in misses, "pending property AC with a collectable test is an unbound miss"


def test_find_unbound_closed_type_acs_skips_absent_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending AC with NO collectable test = future-PLAN work = safe skip."""
    from harness_maker import spec_machine

    y, m = _property_yaml(tmp_path)
    # Ran cleanly, nothing collectable → safe-skip (future work).
    monkeypatch.setattr(spec_machine, "_collectable_ac_tests", lambda model, cwd: (set(), True))
    misses = spec_machine.find_unbound_closed_type_acs(y, m.parent)
    assert misses == [], "no collectable test → future work → not a miss"


def test_find_unbound_closed_type_acs_fail_closed_on_malformed(tmp_path: Path) -> None:
    """A malformed machine.yaml raises yaml.YAMLError (Production caller fails closed)."""
    import yaml as _yaml

    from harness_maker.spec_machine import find_unbound_closed_type_acs

    bad = tmp_path / "SPEC-demo.machine.yaml"
    bad.write_text("ac: [: : :\n")  # invalid yaml
    with pytest.raises(_yaml.YAMLError):
        find_unbound_closed_type_acs(bad, tmp_path)


def test_find_unbound_fails_closed_when_pytest_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pytest unavailable + a pending closed-type AC = unknown state = RAISE (k-of-3 P0/P1).

    The bug the review caught: `_pytest_collect_nodeids` returning ran=False was
    collapsed to an empty set → exit 0 (false PASS). It must fail closed instead."""
    from harness_maker import spec_machine

    y, m = _property_yaml(tmp_path)  # AC-001 pending property
    monkeypatch.setattr(spec_machine, "_pytest_collect_nodeids", lambda cwd: ([], False))
    with pytest.raises(spec_machine.BindingGateUnavailableError):
        spec_machine.find_unbound_closed_type_acs(y, m.parent)


def test_collectable_ac_tests_union_and_no_prefix_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The REAL union logic (non-mocked): recorded_hit AND convention_hit resolve;
    a mixed-width id (AC-001 vs AC-0012) does NOT cross-attribute (boundary match)."""
    from harness_maker.spec_machine import AcceptanceCriterion, SpecMachine, _collectable_ac_tests

    model = SpecMachine(
        schema_version=2,
        spec_slug="demo",
        verification_tier=1,
        ac=[
            # convention-named test collects (empty test_ids).
            AcceptanceCriterion(id="AC-001", title="conv", type="property", pending_test=True),
            # recorded test_ids node collects (non-convention name).
            AcceptanceCriterion(
                id="AC-002",
                title="rec",
                type="parametric",
                test_ids=["tests/x.py::test_weird_name"],
                pending_test=True,
            ),
            # AC-0012: only AC-001's test collects → must NOT falsely attribute to AC-0012.
            AcceptanceCriterion(id="AC-0012", title="collide", type="property", pending_test=True),
        ],
    )
    nodeids = ["tests/y.py::test_ac_001_adder", "tests/x.py::test_weird_name"]
    monkeypatch.setattr(
        "harness_maker.spec_machine._pytest_collect_nodeids", lambda cwd: (nodeids, True)
    )
    got, ran = _collectable_ac_tests(model, tmp_path)
    assert ran is True
    assert got == {"AC-001", "AC-002"}, "union of convention+recorded; AC-0012 not cross-attributed"


# ---------------------------------------------------------------------------
# find-unbound CLI (subprocess) — absent=skip(0), malformed=fail-closed(1)
# ---------------------------------------------------------------------------


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_find_unbound_cli_absent_yaml_exits_zero(tmp_path: Path) -> None:
    cp = _run_cli("find-unbound", "--yaml", str(tmp_path / "nope.machine.yaml"), cwd=tmp_path)
    assert cp.returncode == 0, cp.stderr
    assert "nothing to check" in cp.stderr


def test_find_unbound_cli_malformed_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "SPEC-demo.machine.yaml"
    bad.write_text("ac: [: : :\n")
    cp = _run_cli("find-unbound", "--yaml", str(bad), cwd=tmp_path)
    assert cp.returncode == 1, "malformed machine SPEC must fail-closed (exit 1)"
    assert "fail-closed" in cp.stderr.lower()


# ---------------------------------------------------------------------------
# INTEGRATION — full cross-stage loop (author parametric → collect → mark_tested
# → find-unbound). CLAUDE.md #8: the cwd/collection boundary unit tests can't prove.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not os.getenv("INTEGRATION"), reason="INTEGRATION=1 to run")
def test_integration_parametric_loop(tmp_path: Path) -> None:
    from harness_maker.spec_machine import find_unbound_closed_type_acs, load, mark_tested

    specs = tmp_path / "specs"
    specs.mkdir()
    y = specs / "SPEC-demo.machine.yaml"
    m = specs / "SPEC-demo.md"
    y.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "spec_slug": "demo",
                "verification_tier": 1,
                "ac": [
                    {
                        "id": "AC-001",
                        "title": "adder golden",
                        "type": "parametric",
                        "oracle_source": "golden",
                        "oracle_evidence": "curated golden rows",
                        "golden_table": [
                            {"input": {"a": 1, "b": 2}, "expected": 3, "note": "pos"},
                            {"input": {"a": -1, "b": 1}, "expected": 0, "note": "zero"},
                        ],
                        "pending_test": True,
                    }
                ],
            }
        )
    )
    m.write_text("---\ntier: 1\n---\n\n### AC-001\nadder golden\n")

    # Author the convention-named parametric test that loads the golden_table SSOT.
    (tmp_path / "test_ac_001_adder.py").write_text(
        "from pathlib import Path\n"
        "import pytest\n"
        "from harness_maker.spec_machine import load_golden_table\n"
        "_Y = Path(__file__).parent / 'specs/SPEC-demo.machine.yaml'\n"
        "_ROWS = load_golden_table(_Y, 'AC-001')\n"
        "def _add(a, b):\n    return a + b\n"
        "@pytest.mark.parametrize('row', _ROWS, ids=[r.note for r in _ROWS])\n"
        "def test_ac_001_adder(row):\n    assert _add(**row.input) == row.expected\n"
    )

    # The test collects + passes (GREEN), but the AC is still pending → a MISS.
    collect = subprocess.run(
        ["pytest", "--collect-only", "-q", "--no-header"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "test_ac_001_adder" in collect.stdout, collect.stdout + collect.stderr
    assert find_unbound_closed_type_acs(y, tmp_path) == ["AC-001"], "pending+collectable = miss"

    # Bind it (the write-back) → no longer a miss.
    errors = mark_tested(
        y, m, {"AC-001": ["test_ac_001_adder.py::test_ac_001_adder"]}, validate_after=False
    )
    assert errors == [], errors
    assert load(y).ac[0].pending_test is False
    assert find_unbound_closed_type_acs(y, tmp_path) == [], "bound AC is no longer a miss"
