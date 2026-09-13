"""The dispatch-grouping function: one entry per subagent call, not per lens.

Restoring the fan-out means changing `LENS_GROUPS` to one entry per lens and nothing
else — `test_restoring_the_fan_out_is_one_constant` is the counterfactual that holds
that claim honest, because every other assertion here passes under either grouping.

**Phase A.5 round 1 rewrote one test.** `test_lens_dispatch_still_returns_one_entry_per_lens`
was authored as a pure preservation invariant and therefore passed before Phase C wrote
anything — it could not tell "AC-008 done" from "AC-008 not started". It now asserts the
*granularity split* between the two functions, which requires `lens_dispatch_groups` to exist
(so it is RED pre-implementation) and still goes red if someone merges in place by rewriting
`lens_dispatch` to return groups (then the two counts coincide). That in-place rewrite is the
failure mode SPEC AC-008's second half names: `lens_coverage` derives the mandatory set from
`lens_dispatch`, so changing it silently moves the required set.
"""

from __future__ import annotations

import pytest

from harness_maker import conditional_router as cr
from harness_maker.template_globals import TEMPLATE_GLOBALS

PRESETS = ("Production", "Side")


@pytest.mark.parametrize("preset", PRESETS)
def test_the_four_core_lenses_travel_in_one_group(preset: str) -> None:
    groups = cr.lens_dispatch_groups(preset)
    core = [g for g in groups if g["agent"] == "code-reviewer"]
    assert len(core) == 1, f"core lenses must share ONE dispatch, got {len(core)}"
    assert tuple(core[0]["lenses"]) == cr.CORE_LENSES
    assert core[0]["file"] == "core"


@pytest.mark.parametrize("preset", PRESETS)
def test_the_domain_lenses_stay_one_dispatch_each(preset: str) -> None:
    groups = cr.lens_dispatch_groups(preset)
    singles = {g["file"]: g for g in groups if g["agent"] != "code-reviewer"}
    assert set(singles) == set(cr.DOMAIN_LENSES)
    for lens, group in singles.items():
        assert tuple(group["lenses"]) == (lens,), "a domain lens has no one to merge with"
        assert group["agent"] == cr.LENS_DISPATCH[lens][0]


@pytest.mark.parametrize("preset", PRESETS)
def test_every_dispatched_lens_lands_in_exactly_one_group(preset: str) -> None:
    dispatched = [d["lens"] for d in cr.lens_dispatch(preset)]
    grouped = [lens for g in cr.lens_dispatch_groups(preset) for lens in g["lenses"]]
    assert sorted(grouped) == sorted(dispatched), "a lens was dropped or duplicated"
    assert len(grouped) == len(set(grouped))


@pytest.mark.parametrize("preset", PRESETS)
def test_each_brief_is_the_one_the_dispatch_table_holds(preset: str) -> None:
    """Byte-identical, against the constant rather than against a copy of the grouping."""
    for group in cr.lens_dispatch_groups(preset):
        for lens, brief in zip(group["lenses"], group["briefs"], strict=True):
            assert brief == cr.LENS_DISPATCH[lens][1]


@pytest.mark.parametrize("preset", PRESETS)
def test_lens_dispatch_still_returns_one_entry_per_lens(preset: str) -> None:
    """SPEC AC-008's second half: grouping is ADDITIVE — `lens_dispatch` does not move.

    The observable is the granularity split, not either function alone: `lens_dispatch` stays
    per-lens while `lens_dispatch_groups` is per-dispatch, so the two counts must differ. An
    implementation that "merges" by rewriting `lens_dispatch` in place satisfies every other
    test in this file and fails here, because the counts would then coincide.
    """
    entries = cr.lens_dispatch(preset)
    assert [d["lens"] for d in entries] == [
        *cr.mandatory_lenses(preset),
        *[x for x in cr.routable_lenses(preset) if x not in cr.mandatory_lenses(preset)],
    ]
    assert len(entries) == len(cr.ALL_LENSES)
    assert len(cr.lens_dispatch_groups(preset)) < len(entries), (
        "lens_dispatch must stay per-lens while the grouping function is per-dispatch; "
        "equal counts mean the merge was done by rewriting lens_dispatch in place"
    )


def test_a_result_file_stem_resolves_to_the_lenses_it_vouches_for() -> None:
    assert cr.lenses_for_result_file("core") == cr.CORE_LENSES
    assert cr.lenses_for_result_file("security") == ("security",)


@pytest.mark.parametrize("lens", cr.CORE_LENSES)
def test_a_per_lens_stem_still_resolves_for_an_un_re_rendered_harness(lens: str) -> None:
    """SPEC AC-004's backward-compatibility clause, at the vocabulary layer."""
    assert cr.lenses_for_result_file(lens) == (lens,)


@pytest.mark.parametrize("stem", ["", "core.json", "CORE", "design/../core", "made-up"])
def test_an_unknown_stem_vouches_for_nothing(stem: str) -> None:
    """Fail-closed: 'cannot tell' must never resolve to 'exercised'."""
    assert cr.lenses_for_result_file(stem) == ()


def test_restoring_the_fan_out_is_one_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-005's claim, made falsifiable.

    Every other test here passes under a template that hard-codes four groups. This one
    does not: it swaps `LENS_GROUPS` for one entry per lens and requires the full fan-out
    back, which is exactly the edit a future reader restoring it would make.
    """
    monkeypatch.setattr(cr, "LENS_GROUPS", {lens: (lens,) for lens in cr.ALL_LENSES})
    groups = cr.lens_dispatch_groups("Production")
    assert len(groups) == len(cr.ALL_LENSES)
    assert [g["file"] for g in groups] == list(cr.ALL_LENSES)
    assert all(len(g["lenses"]) == 1 for g in groups)


def test_a_group_spanning_two_agents_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A silently wrong dispatch is worse than a loud one — the agent is per group."""
    monkeypatch.setattr(cr, "LENS_GROUPS", {"bad": ("design", "security")})
    with pytest.raises(ValueError, match="one agent"):
        cr.lens_dispatch_groups("Production")


def test_the_grouping_function_is_exported_to_templates() -> None:
    """A template cannot call what `_make_env` never installed."""
    assert TEMPLATE_GLOBALS["lens_dispatch_groups"] is cr.lens_dispatch_groups
