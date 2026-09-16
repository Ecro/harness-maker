"""AC-007 and AC-018 — human-recorded outcome values.

AC-007: six defect classes refused by field name with the file bytes untouched; a complete
record with a non-zero offset persists in UTC `Z` form carrying the TEST-computed definition
hash. AC-018: latest-value selection by normalised instant (ties → later index), staleness by
definition hash, gap by direction — expected values computed test-side (`world_fixture`).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import world
from tests.unit import world_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

GOOD: dict[str, Any] = {
    "outcome_id": "onboarding_minutes",
    "value": 17,
    "observed_at": "2026-09-10T09:00:00+09:00",
    "evidence": "timed three onboardings",
}


@pytest.mark.parametrize(
    ("over", "expected_field"),
    [
        ({"observed_at": None}, "observed_at"),
        ({"observed_at": "yesterday"}, "observed_at"),
        ({"observed_at": "2026-09-10T09:00:00"}, "observed_at"),
        ({"evidence": None}, "evidence"),
        ({"evidence": ""}, "evidence"),
        ({"value": "seventeen"}, "value"),
        ({"outcome_id": "nope"}, "outcome_id"),
    ],
    ids=[
        "ts-missing",
        "ts-not-iso",
        "ts-naive",
        "evidence-missing",
        "evidence-empty",
        "value-non-numeric",
        "outcome-unknown",
    ],
)
def test_ac_007_each_defect_is_refused_by_field_and_writes_nothing(
    tmp_path: Path, over: dict[str, Any], expected_field: str
) -> None:
    root = fx.build_root(tmp_path, git=False)
    before = fx.outcomes_path(root).read_bytes()
    rec = {**GOOD, **over}
    with pytest.raises(world.WorldError) as exc:
        world.record_value(root, **rec)
    assert exc.value.field == expected_field
    assert fx.outcomes_path(root).read_bytes() == before


def test_ac_007_complete_record_persists_in_utc_z_with_the_test_computed_hash(
    tmp_path: Path,
) -> None:
    root = fx.build_root(tmp_path, git=False)
    world.record_value(root, **GOOD)
    rows = fx.load(fx.outcomes_path(root))["values"]
    assert len(rows) == 1
    assert rows[0]["observed_at"] == "2026-09-10T00:00:00Z"
    assert rows[0]["value"] == 17
    assert rows[0]["definition_hash"] == fx.definition_hash(fx.outcome())


_FORMS = ("Z", "+00:00", "+09:00", "-05:30", "frac")


def _render(instant: datetime, form: str) -> str:
    if form == "Z":
        return instant.strftime("%Y-%m-%dT%H:%M:%SZ")
    if form == "+00:00":
        return instant.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    if form == "frac":
        return instant.strftime("%Y-%m-%dT%H:%M:%S.500000Z")
    sign, hh, mm = ("+", 9, 0) if form == "+09:00" else ("-", 5, 30)
    delta = timedelta(hours=hh, minutes=mm)
    local = instant + delta if sign == "+" else instant - delta
    return local.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{hh:02d}:{mm:02d}"


@given(
    seconds=st.lists(st.integers(min_value=0, max_value=3600 * 24 * 30), min_size=1, max_size=8),
    forms=st.lists(st.sampled_from(_FORMS), min_size=8, max_size=8),
    values=st.lists(st.integers(min_value=0, max_value=100), min_size=8, max_size=8),
    flip_direction=st.booleans(),
)
def test_ac_018_latest_by_instant_ties_to_later_index_and_staleness_by_hash(
    tmp_path_factory: Any,
    seconds: list[int],
    forms: list[str],
    values: list[int],
    flip_direction: bool,
) -> None:
    root = fx.build_root(tmp_path_factory.mktemp("w"), git=False)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    records: list[dict[str, Any]] = []
    for i, s in enumerate(seconds):
        instant = base + timedelta(seconds=s)
        frac = 0.5 if forms[i] == "frac" else 0.0
        rendered = _render(instant, forms[i])
        world.record_value(
            root,
            outcome_id="onboarding_minutes",
            value=values[i],
            observed_at=rendered,
            evidence="e",
        )
        records.append(
            {"observed_at": (instant + timedelta(seconds=frac)).isoformat(), "value": values[i]}
        )
    expected_idx = fx.argmax_latest(records)
    assert expected_idx is not None
    if flip_direction:
        doc = fx.load(root / ".claude" / "intent.yaml")
        doc["outcomes"][0]["higher_is_better"] = True
        fx.dump(root / ".claude" / "intent.yaml", doc)
    out = fx.stdout_json(fx.run_cli(["status", "--json"], cwd=root))["outcomes"][
        "onboarding_minutes"
    ]
    exp = records[expected_idx]
    assert out["last"] == exp["value"]
    assert datetime.fromisoformat(out["observed_at"]).astimezone(UTC) == datetime.fromisoformat(
        exp["observed_at"]
    )
    assert out["observed_at"].endswith("Z")
    assert out["stale_definition"] is flip_direction
    if flip_direction:
        assert out["gap"] == "unevaluable"
    else:
        # lower is better, target 10
        assert out["gap"] == ("at_or_better" if exp["value"] <= 10 else "above_target")
