"""AC-001 / AC-005 (SPEC-outcome-measure) — the `measure` block validates with the outcome and
joins the definition hash only when present.

AC-001's oracle is golden: every refused fixture is hand-written from SPEC S1's list and the
field name is fixed by the SPEC (`outcomes[i].measure.<field>`), never read back from the
validator. AC-005 is differential: the reference for "stale" is the shipped `gap_report`
reason, and the block-less hash is a literal taken from HEAD before this change
(`definition_hash(10, "stopwatch", False)` at 6ef0bcf9) so the new hashing cannot move it.

Phase A.4 note: `test_ac_005_a_block_less_outcome_hashes_exactly_as_before` passes before the
implementation exists — deliberately. It is the absent-case negative invariant (ADR-002: a
block-less outcome must hash exactly as today, so no pre-existing row goes `stale_definition`
on upgrade) and goes red the moment an implementer adds a `measure: null` key to the payload;
its RED positive siblings are `test_ac_005_editing_measure_stales_history` and
`test_ac_005_every_measure_field_is_hashed`, which force the `measure` key into existence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker import intent, world
from tests.unit import world_fixture as fx

LEGACY_HASH_WITHOUT_MEASURE = "43b3d603a9ba25f94acd47be9bf220585ee5d47525127d68a9685279618fcd61"

GOOD_MEASURE: dict[str, Any] = {
    "cmd": "python probe.py",
    "select": "json:report.carry_ratio",
    "cwd": "base",
}


def _write_intent(path: Path, measure: Any) -> Path:
    doc = fx.intent_doc(fx.outcome("carry", measure=measure))
    fx.dump(path, doc)
    return path


# ── AC-001 ───────────────────────────────────────────────────────────────────


def test_ac_001_measure_block_validates_with_the_outcome(tmp_path: Path) -> None:
    good = _write_intent(tmp_path / "good.yaml", GOOD_MEASURE)
    loaded = intent.load_intent(good)
    block = loaded.outcomes[0].measure
    assert block is not None
    assert block.cmd == "python probe.py"
    assert block.select == "json:report.carry_ratio"
    assert block.cwd == "base"
    assert block.timeout_s == 300
    assert intent.validate_intent(good) == []

    bad_blocks: list[Any] = [
        {**GOOD_MEASURE, "cmd": ""},  # empty cmd
        {**GOOD_MEASURE, "cmd": "-c print(1)"},  # option-shaped first token
        {**GOOD_MEASURE, "select": "xml:root/value"},  # unknown select prefix
        {**GOOD_MEASURE, "select": "last-numberXYZ"},  # not exactly last-number
        {**GOOD_MEASURE, "select": "regex:carry=[0-9.]+"},  # regex without one group
        {**GOOD_MEASURE, "cwd": "elsewhere"},  # cwd outside base|checkout
        {**GOOD_MEASURE, "timeout_s": 0},  # non-positive timeout
        {**GOOD_MEASURE, "shell": True},  # unknown measure field
        "python probe.py",  # non-mapping measure
    ]
    bad_paths = [_write_intent(tmp_path / f"bad{i}.yaml", b) for i, b in enumerate(bad_blocks)]
    assert all(
        any(e.field.startswith("outcomes[0].measure") for e in intent.validate_intent(bad))
        for bad in bad_paths
    ), [[e.field for e in intent.validate_intent(bad)] for bad in bad_paths]


def test_ac_001_a_measurable_outcome_keeps_status_ok_through_the_cli(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path, intent=fx.intent_doc(fx.outcome("carry", measure=GOOD_MEASURE)))
    proc = fx.run_cli(["--root", str(root), "status", "--json"], cwd=root)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["state"] == "ok"


def test_ac_001_defaults_and_overrides_load(tmp_path: Path) -> None:
    path = _write_intent(
        tmp_path / "i.yaml",
        {"cmd": "python probe.py", "select": "last-number", "cwd": "checkout", "timeout_s": 5},
    )
    block = intent.load_intent(path).outcomes[0].measure
    assert block is not None
    assert (block.cwd, block.timeout_s) == ("checkout", 5)
    minimal = _write_intent(
        tmp_path / "m.yaml", {"cmd": "python probe.py", "select": "last-number"}
    )
    block = intent.load_intent(minimal).outcomes[0].measure
    assert block is not None
    assert (block.cwd, block.timeout_s) == ("base", 300)
    fx.dump(tmp_path / "a.yaml", fx.intent_doc(fx.outcome("carry")))
    assert intent.load_intent(tmp_path / "a.yaml").outcomes[0].measure is None


# ── AC-005 ───────────────────────────────────────────────────────────────────


def _measured_row(outcome_doc: dict[str, Any], value: float = 0.5) -> dict[str, Any]:
    return {
        "outcome_id": outcome_doc["id"],
        "value": value,
        "observed_at": "2026-09-10T00:00:00Z",
        "evidence": "fixture",
        "definition_hash": fx.definition_hash(outcome_doc),
    }


def _edit_measure(root: Path, **over: Any) -> None:
    path = root / ".claude" / "intent.yaml"
    doc = fx.load(path)
    doc["outcomes"][0]["measure"] = {**doc["outcomes"][0]["measure"], **over}
    fx.dump(path, doc)


def test_ac_005_editing_measure_stales_history(tmp_path: Path) -> None:
    outcome_doc = fx.outcome("carry", measure=dict(GOOD_MEASURE))
    root = fx.build_root(
        tmp_path, intent=fx.intent_doc(outcome_doc), values=[_measured_row(outcome_doc)]
    )
    assert world.gap_report(root)["outcomes"]["carry"]["reason"] == "measured"

    _edit_measure(root, cmd="python other.py")
    gap_after_edit = world.gap_report(root)
    assert gap_after_edit["outcomes"]["carry"]["reason"] == "stale_definition"

    _edit_measure(root, cmd="python probe.py")
    gap_after_revert = world.gap_report(root)
    assert gap_after_revert["outcomes"]["carry"]["reason"] == "measured"

    assert (
        world.definition_hash(10, "stopwatch", False, measure=None) == LEGACY_HASH_WITHOUT_MEASURE
    )


@pytest.mark.parametrize(
    "edit",
    [{"select": "last-number"}, {"cwd": "checkout"}, {"timeout_s": 7}],
    ids=["select", "cwd", "timeout_s"],
)
def test_ac_005_every_measure_field_is_hashed(tmp_path: Path, edit: dict[str, Any]) -> None:
    outcome_doc = fx.outcome("carry", measure=dict(GOOD_MEASURE))
    root = fx.build_root(
        tmp_path, intent=fx.intent_doc(outcome_doc), values=[_measured_row(outcome_doc)]
    )
    _edit_measure(root, **edit)
    assert world.gap_report(root)["outcomes"]["carry"]["reason"] == "stale_definition"


def test_ac_005_a_block_less_outcome_hashes_exactly_as_before(tmp_path: Path) -> None:
    """Absent-case: rows recorded before this change must not go stale on upgrade."""
    outcome_doc = fx.outcome(
        "carry"
    )  # target 10, stopwatch, lower is better — the literal's inputs
    legacy_row = {
        "outcome_id": "carry",
        "value": 9,
        "observed_at": "2026-09-10T00:00:00Z",
        "evidence": "fixture",
        "definition_hash": LEGACY_HASH_WITHOUT_MEASURE,
    }
    root = fx.build_root(tmp_path, intent=fx.intent_doc(outcome_doc), values=[legacy_row])
    assert world.gap_report(root)["outcomes"]["carry"]["reason"] == "measured"
    assert fx.definition_hash(outcome_doc) == LEGACY_HASH_WITHOUT_MEASURE
