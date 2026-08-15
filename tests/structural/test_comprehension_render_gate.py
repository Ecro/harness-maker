"""Phase 2 render gate — AC-001, AC-002, AC-003, AC-006 plus ADR-007/008.

Every assertion here reads a REAL render produced by ``_surface_baseline.render_surface``,
the same function the golden and the surface baseline go through, so "pre" and "post" are
the same quantity by construction rather than by assertion.
"""

from __future__ import annotations

import pytest

from ._comprehension_golden import TRACKED_COMMANDS
from ._surface_baseline import CLAUDE_VARIANT, render_surface

BRIEF = "<!-- @hm:comprehension:brief -->"
ROUND_STATE = "<!-- @hm:comprehension:round_state -->"
DECISION_DEPTH = "<!-- @hm:comprehension:decision_depth -->"
TEACH_BACK = "<!-- @hm:comprehension:teach_back -->"

ALL_MARKERS = (BRIEF, ROUND_STATE, DECISION_DEPTH, TEACH_BACK)

#: ADR-008 — the sentence the depth branch REPLACES at standard/deep.
OPTIONAL_SENTENCE = "visualization OPTIONAL"

_STAGES = ("plan", "spec")


@pytest.fixture(scope="module")
def rendered() -> dict[str, dict[str, dict[str, str]]]:
    """One render per depth, reused across the module — each render is not cheap."""
    return {
        depth: render_surface(depth_override=depth) for depth in ("minimal", "standard", "deep")
    }


def _markers(text: str) -> set[str]:
    return {m for m in ALL_MARKERS if m in text}


# ---------------------------------------------------------------------------
# AC-001 / AC-002 — the enabled block set per level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", _STAGES)
def test_standard_renders_brief_and_round_state_only(
    rendered: dict[str, dict[str, dict[str, str]]], stage: str
) -> None:
    text = rendered["standard"][CLAUDE_VARIANT][stage]
    assert _markers(text) == {BRIEF, ROUND_STATE}, (
        f"{stage}: standard must enable exactly brief + round_state, got {_markers(text)}"
    )


@pytest.mark.parametrize("stage", _STAGES)
def test_deep_renders_all_four_blocks(
    rendered: dict[str, dict[str, dict[str, str]]], stage: str
) -> None:
    text = rendered["deep"][CLAUDE_VARIANT][stage]
    assert _markers(text) == set(ALL_MARKERS), (
        f"{stage}: deep must enable all four blocks, got {_markers(text)}"
    )


def test_teach_back_states_it_is_output_only_and_creates_no_gate(
    rendered: dict[str, dict[str, dict[str, str]]],
) -> None:
    """SPEC S2's second Then. A readback that silently became a gate would change the
    autopilot contract — the Non-Goals say no mandatory gate is added."""
    text = rendered["deep"][CLAUDE_VARIANT]["plan"]
    block = text.split(TEACH_BACK, 1)[1][:1200].lower()
    assert "no response" in block or "requires no user response" in block, block[:300]
    assert "no gate" in block or "not a gate" in block, block[:300]


def test_the_levels_are_ordered_not_merely_distinct(
    rendered: dict[str, dict[str, dict[str, str]]],
) -> None:
    """ADR-001 calls the axis an ORDINAL: each level enables everything below it."""
    for stage in _STAGES:
        minimal = _markers(rendered["minimal"][CLAUDE_VARIANT][stage])
        standard = _markers(rendered["standard"][CLAUDE_VARIANT][stage])
        deep = _markers(rendered["deep"][CLAUDE_VARIANT][stage])
        assert minimal < standard < deep, f"{stage}: {minimal} !< {standard} !< {deep}"


# ---------------------------------------------------------------------------
# AC-003 — minimal is byte-identical to the pre-change render
# ---------------------------------------------------------------------------


def test_minimal_renders_nothing_and_costs_zero_bytes(
    rendered: dict[str, dict[str, dict[str, str]]],
) -> None:
    """The mechanical evidence that a third-party opt-out install pays nothing.

    **Narrowed 2026-08-15, and the narrowing matters.** This asserted that the whole `plan` and
    `spec` documents were byte-identical to a frozen pre-change digest. That is a strictly
    stronger claim than AC-003 makes, and the extra strength is not a safety margin — it froze
    two shipped templates permanently. Any later, unrelated edit to `plan.md.j2` fails it, and
    the only ways out are to abandon the edit or to regenerate the oracle, which
    `test_comprehension_zero_cost_golden` correctly forbids. The first stage edit to arrive
    after the comprehension work landed (AC-010, terminal re-validation) hit exactly that wall.

    The claim AC-003 actually makes is that **the partial contributes zero bytes at minimal**.
    That is now checked at the partial itself (`..._emits_the_empty_string_at_minimal` below),
    which is a same-commit oracle: it needs no frozen snapshot, catches the real hazard — a
    stray newline left by a false Jinja branch — precisely rather than incidentally, and stays
    true however the enclosing document evolves.

    What survives here is the enclosing-document half: at minimal none of the partial's markers
    reach the render.
    """
    for variant, names in TRACKED_COMMANDS.items():
        for name in names:
            text = rendered["minimal"][variant][name]
            assert not _markers(text), f"{variant}/{name}: minimal emitted {_markers(text)}"


def test_the_partial_emits_the_empty_string_at_minimal() -> None:
    """AC-003's real content, checked where the bytes are produced.

    Marker-absence alone would pass a partial that emitted a bare newline — the exact hazard
    the original SHA comparison existed to catch. Rendering the partial standalone at
    `minimal` and requiring `""` catches it directly, and cannot be broken by an edit
    elsewhere in `plan.md.j2`.
    """
    from harness_maker.render import _make_env

    env = _make_env()
    tmpl = env.get_template("agents/_partials/comprehension_block.md.j2")
    config = {"interview": {"comprehension": {"depth": "minimal"}}, "locale": "en"}
    for stage in _STAGES:
        for block in ("brief", "round_state", "decision_depth", "teach_back"):
            out = tmpl.render(config=config, block=block, stage=stage)
            assert out == "", (
                f"{stage}/{block}: the comprehension partial emits bytes at depth=minimal, "
                f"so the opt-out is not free: {out!r}"
            )


def test_the_non_minimal_levels_actually_grow_the_render(
    rendered: dict[str, dict[str, dict[str, str]]],
) -> None:
    """Guards the inverse tautology: a partial that emits nothing at EVERY depth would
    satisfy AC-003 perfectly and ship a feature that does nothing."""
    for stage in _STAGES:
        minimal = rendered["minimal"][CLAUDE_VARIANT][stage]
        for depth in ("standard", "deep"):
            assert len(rendered[depth][CLAUDE_VARIANT][stage]) > len(minimal), (
                f"{stage}: depth={depth} did not grow the render relative to minimal"
            )


# ---------------------------------------------------------------------------
# AC-006 / ADR-007 — same source, same enabled block set, stage-specific subject
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("depth", ["standard", "deep"])
def test_spec_stage_carries_the_same_block_set(
    rendered: dict[str, dict[str, dict[str, str]]], depth: str
) -> None:
    plan = _markers(rendered[depth][CLAUDE_VARIANT]["plan"])
    spec = _markers(rendered[depth][CLAUDE_VARIANT]["spec"])
    assert plan == spec, f"depth={depth}: plan enables {plan}, spec enables {spec}"


def test_the_brief_subject_differs_by_stage(
    rendered: dict[str, dict[str, dict[str, str]]],
) -> None:
    """ADR-007. `/hm:spec` has no pre-interview architecture draft to disclose, so identical
    TEXT would instruct it to show an artifact it never produces. Identity is on the block
    SET (asserted above), not on the prose."""
    plan_brief = rendered["standard"][CLAUDE_VARIANT]["plan"].split(BRIEF, 1)[1][:1500]
    spec_brief = rendered["standard"][CLAUDE_VARIANT]["spec"].split(BRIEF, 1)[1][:1500]
    assert plan_brief != spec_brief, (
        "the brief is stage-blind — spec would disclose a draft it has none of"
    )
    assert "Step 1" in plan_brief, "the plan brief must name the internal draft it discloses"
    assert "SPEC" in spec_brief or "acceptance" in spec_brief.lower(), (
        "the spec brief must name what /hm:spec actually has to disclose"
    )


@pytest.mark.parametrize("stage", _STAGES)
@pytest.mark.parametrize("depth", ["minimal", "standard", "deep"])
def test_each_stage_emits_exactly_one_round_state_instruction(
    rendered: dict[str, dict[str, dict[str, str]]], stage: str, depth: str
) -> None:
    """ADR-007/ADR-008. BOTH stages already render a 'Decisions locked in so far' preamble;
    the partial must SUBSUME it, not stack a second one on top.

    **Parametrized over stage after a spec-only version shipped the defect it was written
    to catch.** `spec.md.j2` was gated; `plan.md.j2` was not, so at standard/deep `/hm:plan`
    — the higher-traffic stage — carried two contradicting preambles with different
    empty-state rules ("skip the block" vs "say no change since last round"), and which one
    an LLM follows is nondeterministic. That is verbatim the rationale ADR-008 gives for
    replacing rather than appending, violated in the stage ADR-008 is about.
    """
    text = rendered[depth][CLAUDE_VARIANT][stage]
    assert text.count("Decisions locked in so far") == 1, (
        f"{stage} at depth={depth} renders {text.count('Decisions locked in so far')} "
        "round-state preambles — the partial stacked instead of subsuming"
    )


# ---------------------------------------------------------------------------
# ADR-008 — the Step A optionality sentence is REPLACED under the branch
# ---------------------------------------------------------------------------


def test_the_optional_sentence_survives_at_minimal(
    rendered: dict[str, dict[str, dict[str, str]]],
) -> None:
    assert OPTIONAL_SENTENCE in rendered["minimal"][CLAUDE_VARIANT]["plan"]


@pytest.mark.parametrize("depth", ["standard", "deep"])
def test_the_optional_sentence_is_gone_at_standard_and_deep(
    rendered: dict[str, dict[str, dict[str, str]]], depth: str
) -> None:
    """Two contradicting instructions in one command leave the model to pick, and which one
    it picks is nondeterministic."""
    assert OPTIONAL_SENTENCE not in rendered[depth][CLAUDE_VARIANT]["plan"], (
        f"depth={depth}: 'visualization OPTIONAL' still ships alongside required-when-changed"
    )


# ---------------------------------------------------------------------------
# The round-trip gates must stay GREEN — the partial adds no call site
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("depth", ["standard", "deep"])
def test_the_partial_adds_no_round_trip(
    rendered: dict[str, dict[str, dict[str, str]]], depth: str
) -> None:
    """`test_round_trip_counts_match_the_live_render` and `test_roundtrip_budget.py` are
    EXACT, not ratchets: a `^!` line or a `Task(` token added by the partial trips both. Fail
    here instead, where the message names the cause."""
    from ._surface_baseline import count_round_trips

    for stage in _STAGES:
        minimal = count_round_trips(rendered["minimal"][CLAUDE_VARIANT][stage], CLAUDE_VARIANT)
        actual = count_round_trips(rendered[depth][CLAUDE_VARIANT][stage], CLAUDE_VARIANT)
        assert actual == minimal, (
            f"{stage} at depth={depth}: the partial added {actual - minimal} round-trip(s); "
            "it must contain no `^!` line and no `Task(` token"
        )
