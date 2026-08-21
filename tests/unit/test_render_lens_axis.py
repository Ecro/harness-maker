"""Phase 2 — the lens axis, rendered identically at both dispatch sites.

The defect class this file guards is not "a lens is missing from the prose". It is that the
rendered dispatch list and `hm lens_coverage check` can disagree about what the mandatory set
is — and when they do, the symptom is not a visible drift but a review that can never be
approved, because the CLI reports a lens missing that the command never told anyone to run.
So every assertion here compares a **rendered** artifact against the Python constant the CLI
reads, never against a list re-typed in the test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.conditional_router import (
    ALL_LENSES,
    CORE_LENSES,
    DOMAIN_LENSES,
    mandatory_lenses,
    routable_lenses,
)
from harness_maker.interview import interview
from harness_maker.lens_coverage import coverage_verdict
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

PRESETS = ("Side", "Production")


def _render(tmp_path: Path, preset: str) -> str:
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    a.preset = Preset(preset)
    render(synthesize(p, a), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bodies(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return {p: _render(tmp_path_factory.mktemp(f"axis-{p}"), p) for p in PRESETS}


def _section(body: str, start: str, *, stop: str) -> str:
    i = body.find(start)
    assert i != -1, f"rendered command has no section starting {start!r}"
    j = body.find(stop, i + len(start))
    return body[i:] if j == -1 else body[i:j]


def _dispatched(block: str) -> set[str]:
    """Lens names taken from the `Task(` lines, not from prose.

    Prose mentions a lens for many reasons; only a `Task(` line causes one to run.
    """
    return set(re.findall(r'description="lens ([a-z]+): \{slug\}"', block))


# ── AC-001: round 1 renders the preset's set, and it is the CLI's set ─────────


def _expected_dispatch(preset: str) -> set[str]:
    """Mandatory PLUS routable. A router can only drop what was dispatched.

    On Side the three domain lenses are routable, which means opt-OUT: they render, and the
    conditional router may drop them. Rendering only the mandatory six meant a Side harness could
    never run `security`/`concurrency`/`tests` at all, while the same command's routing bullet
    said the router "may drop" them — subtraction from a set the renderer never produced.
    """
    return set(mandatory_lenses(preset)) | set(routable_lenses(preset))


def test_the_axis_itself_is_pinned_as_a_literal() -> None:
    """AC-001's declared oracle is `golden`, and every OTHER arm here is a consistency oracle.

    They compare the render to `mandatory_lenses()` — the same production function the renderer
    reads — which is the right oracle for the defect this file targets (render vs CLI disagreeing)
    but cannot fail when the axis itself changes: rename a lens and the constant, the renderer,
    the coverage CLI, the telemetry validator and every derived expectation move together, green.
    This one line is the independent expectation, so "which categories" has a real oracle.
    """
    assert set(mandatory_lenses("Production")) == {
        "design",
        "functionality",
        "robustness",
        "consistency",
        "security",
        "concurrency",
        "tests",
    }
    assert set(mandatory_lenses("Side")) == {
        "design",
        "functionality",
        "robustness",
        "consistency",
    }


@pytest.mark.parametrize("preset", PRESETS)
def test_round1_lens_set_matches_preset(bodies: dict[str, str], preset: str) -> None:
    block = _section(bodies[preset], "### Step 3 — Parallel reviewer invocation", stop="\n### ")
    assert _dispatched(block) == _expected_dispatch(preset)


@pytest.mark.parametrize("preset", PRESETS)
def test_every_lens_the_router_may_drop_was_actually_dispatched(
    bodies: dict[str, str], preset: str
) -> None:
    """The routing bullet promises subtraction; this pins that there is something to subtract."""
    block = _section(bodies[preset], "### Step 3 — Parallel reviewer invocation", stop="\n### ")
    assert set(routable_lenses(preset)) <= _dispatched(block)


@pytest.mark.parametrize("preset", PRESETS)
def test_mandatory_is_a_subset_of_dispatched(preset: str) -> None:
    """Dispatched ⊇ mandatory, always — approval cannot require a lens nobody was told to run."""
    assert set(mandatory_lenses(preset)) <= _expected_dispatch(preset)


@pytest.mark.parametrize("preset", PRESETS)
def test_the_retired_lenses_are_not_dispatched(bodies: dict[str, str], preset: str) -> None:
    """`correctness` and `failure` are replaced, not joined.

    An implementer reading "adopt the six categories" could append them to the existing five
    and produce eleven. Nothing else in this file would notice: every other assertion is a
    superset check that eleven also satisfies.
    """
    block = _section(bodies[preset], "### Step 3 — Parallel reviewer invocation", stop="\n### ")
    assert "correctness" not in _dispatched(block)
    assert "failure" not in _dispatched(block)


# ── AC-002: presets differ in mandatory-ness, never in availability ───────────


def test_side_mandatory_is_subset_of_production() -> None:
    assert set(mandatory_lenses("Side")) <= set(mandatory_lenses("Production"))
    assert set(CORE_LENSES) | set(DOMAIN_LENSES) == set(ALL_LENSES)


def test_an_unknown_preset_resolves_to_the_larger_set() -> None:
    """Fail-closed. A typo'd preset silently dropping three lenses is a false clean bill."""
    assert mandatory_lenses("Producton") == mandatory_lenses("Production")


def test_the_domain_lenses_are_routable_on_side_only() -> None:
    assert set(routable_lenses("Side")) == set(DOMAIN_LENSES)
    assert routable_lenses("Production") == ()


# ── AC-015: the confirmation pass dispatches exactly the round-1 set ──────────


@pytest.mark.parametrize("preset", PRESETS)
def test_confirmation_pass_uses_same_mandatory_set(bodies: dict[str, str], preset: str) -> None:
    """Set equality between two independently rendered lists.

    Not "the pass dispatches at least the mandatory set" — a pass over a superset re-confirms
    work round 1 never did, and a pass over a subset confirms a subset while the coverage CLI
    still demands the whole thing, which is a permanent `blocks_approval: true`.
    """
    body = bodies[preset]
    round1 = _section(body, "### Step 3 — Parallel reviewer invocation", stop="\n### ")
    confirm = _section(body, "### Step C2 —", stop="\n### ")
    assert _dispatched(confirm) == _dispatched(round1)
    assert _dispatched(confirm) == _expected_dispatch(preset)


@pytest.mark.parametrize("preset", PRESETS)
def test_both_sites_write_a_result_file_per_lens(bodies: dict[str, str], preset: str) -> None:
    body = bodies[preset]
    for section, stop in (
        ("### Step 3 — Parallel reviewer invocation", "\n### "),
        ("### Step C2 —", "\n### "),
    ):
        block = _section(body, section, stop=stop)
        for lens in mandatory_lenses(preset):
            assert f"/{lens}.json" in block, f"{section} does not write {lens}.json"


@pytest.mark.parametrize("preset", PRESETS)
def test_the_coverage_call_is_told_the_preset(bodies: dict[str, str], preset: str) -> None:
    """Without this the CLI defaults to Production and a Side review is unapprovable."""
    lines = [
        ln
        for ln in bodies[preset].splitlines()
        if ln.lstrip().startswith("!") and "hm lens_coverage check" in ln
    ]
    assert lines, "no runnable coverage call in the rendered command"
    for line in lines:
        assert f"--preset {preset}" in line, line


# ── AC-003: a missing mandatory lens blocks approval ─────────────────────────


def _write_results(d: Path, lenses: object, run: str = "run-a") -> None:
    d.mkdir(parents=True, exist_ok=True)
    for lens in lenses:  # type: ignore[attr-defined]
        (d / f"{lens}.json").write_text(
            f'{{"lens": "{lens}", "run_id": "{run}", "findings": []}}', encoding="utf-8"
        )


@pytest.mark.parametrize("missing", ["consistency", "security"])
def test_missing_new_mandatory_lens_blocks_approval(tmp_path: Path, missing: str) -> None:
    """A new core lens blocks exactly as a legacy domain lens does.

    `security` is the differential arm: it has blocked approval since the coverage gate
    shipped, so the oracle for `consistency` is already-shipped behaviour rather than an
    expectation authored alongside this change.
    """
    _write_results(tmp_path, [x for x in ALL_LENSES if x != missing])
    verdict = coverage_verdict(tmp_path, "run-a", probe=None)
    assert verdict["blocks_approval"] is True
    assert verdict["missing"] == [missing]


def test_a_side_review_is_not_blocked_by_an_unrouted_domain_lens(tmp_path: Path) -> None:
    """The preset split is only real if the CLI honours it.

    Side requires the core set only; demanding the domain lenses too would make every Side
    review permanently unapprovable, which is the failure the preset argument exists to prevent.
    """
    _write_results(tmp_path, CORE_LENSES)
    assert coverage_verdict(tmp_path, "run-a", "Side", probe=None)["blocks_approval"] is False
    assert coverage_verdict(tmp_path, "run-a", "Production", probe=None)["blocks_approval"] is True


# ── AC-017: the two brief clauses survive the axis rewrite ────────────────────


@pytest.mark.parametrize("preset", PRESETS)
def test_briefs_carry_contract_clause_and_test_carve_out(
    bodies: dict[str, str], preset: str
) -> None:
    """Both clauses read off the rendered artifact a consumer sees, not off a template var."""
    # Drop blockquote markers before flowing: both clauses live inside a `>` block, so their
    # continuation lines carry a `>` that would otherwise land mid-sentence.
    stripped = "\n".join(
        ln.lstrip().removeprefix(">").strip() for ln in bodies[preset].splitlines()
    )
    flowed = " ".join(stripped.split())
    assert "the public contract is fixed and out of scope" in flowed
    assert "must not edit a test file to resolve a finding whose target is not that test" in flowed
    assert "a finding whose own target is the test may be fixed" in flowed


def test_a_routed_in_domain_lens_is_reported_as_exercised_on_side(tmp_path: Path) -> None:
    """The preset scopes what is REQUIRED, never what counts as a real result.

    Side's router may pull `security` in. Scoping the exercised set to the mandatory six would
    discard that lens's result file — `exercised` would under-report and
    `review_telemetry.lenses_exercised` would lose a lens that actually ran.
    """
    _write_results(tmp_path, [*CORE_LENSES, "security"])
    verdict = coverage_verdict(tmp_path, "run-a", "Side", probe=None)
    assert verdict["blocks_approval"] is False
    exercised = verdict["exercised"]
    assert isinstance(exercised, list)
    assert "security" in exercised
