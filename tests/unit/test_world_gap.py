"""AC-001 / AC-002 (SPEC-objective-gap-proposal) — `world.gap_report` and `hm world gap`.

AC-001 is differential: the reference for the outcome subset is the shipped `status_report`
(its `gap` verdict per outcome) and for the objective set `load_world`; the `reason` field is
cross-checked against `last_value` / `LastValue.stale_definition` computed by the existing
helper, never by the function under test. AC-002 is a property: whatever world the fixture
builder produces, running the CLI leaves every byte under the checkout unchanged. Profiles:
`ci` (derandomized, the gate) and `dev` (broader) selected by HYPOTHESIS_PROFILE (default ci).

Phase A.4 note: `test_ac_001_status_report_payload_is_unchanged_by_the_new_reader` passes before
the implementation exists — deliberately. It is the negative invariant ADR-001 freezes (the
`status` payload must not grow when `gap_report` lands) and goes red the moment an implementer
extends `status_report` instead of adding the sibling reader; its RED positive siblings are the
five `gap_report` / CLI tests in this module.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import intent, world
from tests.unit import world_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=12, deadline=None)
settings.register_profile("dev", max_examples=60, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

REASONS = ("never_measured", "stale_definition", "measured")
STATES = ("proposed", "active", "closed", "dropped")


def _tree_hash(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _value_row(
    oid: str, value: float, *, stale: bool, higher_is_better: bool = False
) -> dict[str, Any]:
    """A row hashed against the outcome's CURRENT definition, or an older one when `stale`."""
    definition = fx.outcome(
        oid, higher_is_better=higher_is_better, how_measured=("old" if stale else "stopwatch")
    )
    return {
        "outcome_id": oid,
        "value": value,
        "observed_at": "2026-09-10T00:00:00Z",
        "evidence": "fixture",
        "definition_hash": fx.definition_hash(definition),
    }


def _objective_record(
    oid: str, state: str, *, rejected: list[str], outcome_id: str
) -> dict[str, Any]:
    rec = fx.objective(oid, state=state, outcome_id=outcome_id, rejected=rejected)
    if state == "active":
        rec = fx.approved(rec, 10)
    if state == "closed":
        rec["observed"] = "missed"
        rec["note"] = "fixture"
        rec["closed_at"] = "2026-09-12T00:00:00Z"
    return rec


def _s1_s2_root(tmp_path: Path) -> Path:
    """S1: a never measured, b stale, c measured below target.

    S2: OBJ-1 closed/missed, OBJ-2 active, OBJ-3 dropped.
    """
    a = fx.outcome("a", target=10, higher_is_better=False)
    b = fx.outcome("b", target=10, higher_is_better=False)
    c = fx.outcome("c", target=10, higher_is_better=True)
    return fx.build_root(
        tmp_path,
        intent=fx.intent_doc(a, b, c, unknowns=["u1"]),
        values=[
            _value_row("b", 3, stale=True),
            _value_row("c", 4, stale=False, higher_is_better=True),
        ],
        objectives=[
            _objective_record("OBJ-1", "closed", rejected=["x"], outcome_id="a"),
            _objective_record("OBJ-2", "active", rejected=["y"], outcome_id="c"),
            _objective_record("OBJ-3", "dropped", rejected=[], outcome_id="b"),
        ],
    )


# ── AC-001 ──────────────────────────────────────────────────────────────────


def test_ac_001_gap_reports_measurement_reason_per_outcome(tmp_path: Path) -> None:
    root = _s1_s2_root(tmp_path)
    report = world.gap_report(root)
    loaded = world.load_world(root)
    outcomes = report["outcomes"]
    assert set(outcomes) == {"a", "b", "c"}
    # reason is derived independently from the existing helper
    for oid, row in outcomes.items():
        lv = world.last_value(loaded, oid)
        expected = (
            "never_measured"
            if lv is None
            else ("stale_definition" if lv.stale_definition else "measured")
        )
        assert row["reason"] == expected, oid
        assert row["reason"] in REASONS
        assert row["how_measured"] == loaded.outcome_by_id[oid].how_measured
        assert row["higher_is_better"] == loaded.outcome_by_id[oid].higher_is_better
    assert outcomes["a"]["reason"] == "never_measured"
    assert outcomes["b"]["reason"] == "stale_definition"
    assert outcomes["c"]["reason"] == "measured"
    assert outcomes["c"]["gap"] == "below_target"
    # the shared keys agree with status_report (the differential reference)
    status = world.status_report(root)
    for oid, srow in status["outcomes"].items():
        for key in ("last", "target", "observed_at", "gap"):
            assert outcomes[oid][key] == srow[key], (oid, key)


def test_ac_001_gap_lists_every_objective_state_with_rejected(tmp_path: Path) -> None:
    root = _s1_s2_root(tmp_path)
    report = world.gap_report(root)
    loaded = world.load_world(root)
    assert set(report["objectives"]) == set(loaded.objectives) == {"OBJ-1", "OBJ-2", "OBJ-3"}
    for oid, row in report["objectives"].items():
        rec = loaded.objectives[oid]
        assert row["state"] == rec["state"]
        assert row["title"] == rec["title"]
        assert row["rejected"] == rec["rejected"]
        assert row["observed"] == rec.get("observed")
        assert row["outcome_id"] == rec["outcome_id"]
        assert row["scope"] == rec["scope"]
        assert row["non_scope"] == rec["non_scope"]
        assert row["hypothesis"] == rec["hypothesis"]
    assert report["objectives"]["OBJ-1"]["observed"] == "missed"
    assert report["objectives"]["OBJ-1"]["rejected"] == ["x"]
    assert report["unknowns"] == ["u1"]
    assert report["state"] == "ok"
    assert report["mission"] == loaded.intent.mission
    for key in ("conflicts", "fired_revisits", "broken_references"):
        assert key in report


def test_ac_001_status_report_payload_is_unchanged_by_the_new_reader(tmp_path: Path) -> None:
    """ADR-001: `status` still omits closed/dropped records and keeps its key set."""
    root = _s1_s2_root(tmp_path)
    status = world.status_report(root)
    assert set(status) == {
        "state",
        "mission",
        "outcomes",
        "active",
        "proposed",
        "unknowns",
        "conflicts",
        "fired_revisits",
        "broken_references",
    }
    assert set(status["active"]) == {"OBJ-2"}
    assert status["proposed"] == []
    assert set(status["outcomes"]["b"]) == {
        "last",
        "target",
        "observed_at",
        "gap",
        "stale_definition",
    }
    assert status["outcomes"]["a"]["gap"] == "unevaluable"
    assert status["outcomes"]["b"]["gap"] == "unevaluable"


def test_ac_001_an_invalid_world_returns_the_status_invalid_payload_verbatim(
    tmp_path: Path,
) -> None:
    # outcomes present but mission empty → IntentInvalidError in load_world
    root = fx.build_root(tmp_path, intent=fx.intent_doc(fx.outcome("a"), mission=""))
    status = world.status_report(root)
    assert status["state"] == "invalid"
    assert world.gap_report(root) == status


def test_ac_001_cli_gap_json_equals_the_library_report(tmp_path: Path) -> None:
    root = _s1_s2_root(tmp_path)
    out = fx.stdout_json(fx.run_cli(["gap", "--json"], cwd=root))
    assert out == json.loads(json.dumps(world.gap_report(root)))


def test_ac_001_cli_gap_on_the_skeleton_prints_not_filled_in(tmp_path: Path) -> None:
    root = tmp_path
    intent.write_skeleton_if_absent(root / ".claude" / "intent.yaml")
    out = fx.stdout_json(fx.run_cli(["gap", "--json"], cwd=root))
    assert out["state"] == "not_filled_in"
    assert out["outcomes"] == {}
    assert out["objectives"] == {}


# ── AC-002 (property) ───────────────────────────────────────────────────────


def _build_world(root: Path, reasons: list[str], states: list[str]) -> Path:
    outcomes = [
        fx.outcome(f"o{i}", target=10, higher_is_better=bool(i % 2)) for i in range(len(reasons))
    ]
    values = []
    for i, reason in enumerate(reasons):
        if reason == "stale_definition":
            values.append(_value_row(f"o{i}", 5, stale=True, higher_is_better=bool(i % 2)))
        elif reason == "measured":
            values.append(_value_row(f"o{i}", 5, stale=False, higher_is_better=bool(i % 2)))
    objectives = []
    for j, state in enumerate(states):
        oid_out = f"o{j % len(reasons)}" if reasons else None
        if oid_out is None:
            break
        objectives.append(
            _objective_record(f"OBJ-{j + 1}", state, rejected=[f"r{j}"], outcome_id=oid_out)
        )
    return fx.build_root(
        root,
        intent=fx.intent_doc(*outcomes) if outcomes else fx.intent_doc(mission="ship it"),
        values=values,
        objectives=objectives,
    )


@given(
    reasons=st.lists(st.sampled_from(REASONS), min_size=1, max_size=3),
    states=st.lists(st.sampled_from(STATES), min_size=0, max_size=4),
)
def test_ac_002_gap_writes_nothing(
    tmp_path_factory: pytest.TempPathFactory, reasons: list[str], states: list[str]
) -> None:
    root = _build_world(tmp_path_factory.mktemp("gap"), reasons, states)
    world.load_world(root)  # precondition: loadable
    before = _tree_hash(root)
    proc = fx.run_cli(["gap", "--json"], cwd=root)
    assert proc.returncode == 0, proc.stderr
    assert _tree_hash(root) == before
