"""The rendered dispatch blocks carry GROUPS, and both blocks carry the same ones.

Two assertions here cannot be satisfied by reading the current grouping. `test_restoring_the
_fan_out_reproduces_every_dispatch` swaps `LENS_GROUPS` for one entry per lens and demands the
full fan-out back — a template that hard-codes "four dispatches" passes every other test in
this file and fails that one, which is the only thing holding ADR-005's reversal claim honest.
And `test_no_lens_text_is_a_literal_in_the_template` reads the template SOURCE, so it is an
assertion about absence that the render cannot fake.

**Phase A.4 — 11 of 30 pass before the implementation exists; all 11 are negative invariants
whose forbidden construct THIS phase makes reachable.** Four groups:

- `test_every_core_lens_brief_survives_verbatim[*]` — forbids paraphrasing a brief while
  folding four of them into one dispatch string. Reachable: writing the merged brief by hand is
  the obvious way to do this phase, and a paraphrase renders fine.
- `test_no_lens_brief_tells_the_agent_to_write_anything[*]` — forbids a write verb in the new
  accountability line. Reachable: the line did not exist before this phase, and "…and write your
  findings to core.json" is the natural sentence to reach for.
- `test_the_confirmation_pass_groups_match_round_one[*]` — forbids updating Step 3 and leaving
  Step C2 behind. Reachable: they are two separate blocks, 700 lines apart.
- `test_no_lens_text_is_a_literal_in_the_template` — forbids hard-coding `"core"`, an agent name
  or a brief into either block. Reachable: the merged dispatch is where a literal is cheapest.

Their RED positive siblings — `test_the_core_lenses_leave_in_one_code_reviewer_dispatch`,
`test_the_rendered_groups_are_the_routers_groups`, `test_both_blocks_name_one_result_file_per_group`
— force the merged dispatch into existence, so none of the four is vacuous once Phase C lands.

**One test was rewritten during A.4 rather than justified.** The counterfactual was first written
as a single monkeypatched render, which passed today for the reason that makes it worthless: with
the pre-merge template nothing reads `LENS_GROUPS`, so swapping it changed nothing and the test
could not tell "reversal works" from "reversal was never wired". It now asserts the *contrast*
between the default and the swapped render, and is RED.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker import conditional_router as cr
from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

PRESETS = ("Side", "Production")

#: `description="lens <name>: {slug}"` for a singleton group, `lenses <a>+<b>…` for a merged
#: one. One regex reads both, so a group's size is data rather than two code paths.
_DESCRIPTION = re.compile(r'description="lens(?:es)? ([a-z+]+): \{slug\}"')

_ROUND_1 = "### Step 3 — Parallel reviewer invocation"
_STEP_C2 = "### Step C2 —"


def _render(tmp_path: Path, preset: str) -> str:
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    a.preset = Preset(preset)
    render(synthesize(p, a), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bodies(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return {p: _render(tmp_path_factory.mktemp(f"groups-{p}"), p) for p in PRESETS}


def _section(body: str, start: str) -> str:
    i = body.find(start)
    assert i != -1, f"rendered command has no section starting {start!r}"
    j = body.find("\n### ", i + len(start))
    return body[i:] if j == -1 else body[i:j]


def _groups(block: str) -> list[tuple[str, ...]]:
    """The lens sets each `Task(` line dispatches, in render order."""
    return [tuple(m.split("+")) for m in _DESCRIPTION.findall(block)]


def _agents(block: str) -> list[str]:
    return re.findall(r'Task\(subagent_type="([a-z-]+)"', block)


def _flat(text: str) -> str:
    """Collapse whitespace so a phrase split across a line wrap is still one phrase."""
    return " ".join(text.split())


def _paragraph(block: str, needle: str) -> str:
    """The blank-line-delimited paragraph of `block` containing `needle`, whitespace-flattened.

    Span matters: the count expression and the claim about how the lenses are dispatched are
    ONE paragraph in the template (`review.md.j2:208-210`). Asserting the positive and the
    negative over the whole section lets a correct count sit above a stale claim.

    **Each paragraph is flattened BEFORE the match**, not after the split point is found. The
    first version searched the raw block, so a needle the template happened to wrap across a
    line — which the current text does, at "one dispatch\nper lens" — was invisible here while
    the caller's own flattened check found it. That mismatch fails a CORRECT implementation with
    a message about a missing phrase. Flagged by A.5 round 4 as a non-blocking note.
    """
    for para in block.split("\n\n"):
        flat = _flat(para)
        if needle in flat:
            return flat
    raise AssertionError(f"no paragraph in this block contains {needle!r}")


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("section", [_ROUND_1, _STEP_C2])
def test_the_core_lenses_leave_in_one_code_reviewer_dispatch(
    bodies: dict[str, str], preset: str, section: str
) -> None:
    """SPEC AC-001 — one `code-reviewer` call, four dispatches in total."""
    block = _section(bodies[preset], section)
    agents = _agents(block)
    assert agents.count("code-reviewer") == 1, f"{section}: {agents}"
    assert len(agents) == len(cr.lens_dispatch_groups(preset))
    assert _groups(block)[0] == cr.CORE_LENSES


@pytest.mark.parametrize("preset", PRESETS)
def test_the_confirmation_pass_groups_match_round_one(bodies: dict[str, str], preset: str) -> None:
    """SPEC AC-002 — parity is structural: both blocks loop over the same function."""
    body = bodies[preset]
    assert _groups(_section(body, _STEP_C2)) == _groups(_section(body, _ROUND_1))
    assert _agents(_section(body, _STEP_C2)) == _agents(_section(body, _ROUND_1))


@pytest.mark.parametrize("preset", PRESETS)
def test_the_rendered_groups_are_the_routers_groups(bodies: dict[str, str], preset: str) -> None:
    """The render is compared against the function, never against a list re-typed here."""
    expected = [tuple(g["lenses"]) for g in cr.lens_dispatch_groups(preset)]
    assert _groups(_section(bodies[preset], _ROUND_1)) == expected


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("section", [_ROUND_1, _STEP_C2])
def test_every_core_lens_brief_survives_verbatim(
    bodies: dict[str, str], preset: str, section: str
) -> None:
    """SPEC AC-003 — byte-identical against `LENS_DISPATCH`, a module the template never writes."""
    block = _section(bodies[preset], section)
    for lens in cr.ALL_LENSES:
        brief = cr.LENS_DISPATCH[lens][1]
        assert brief in block, f"{section}: the {lens} brief was paraphrased or dropped"


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("section", [_ROUND_1, _STEP_C2])
def test_the_merged_dispatch_says_it_owns_every_lens_it_carries(
    bodies: dict[str, str], preset: str, section: str
) -> None:
    """Four questions in one call need an accountability line, or the agent picks one."""
    block = _section(bodies[preset], section)
    assert "ACCOUNTABLE for all" in block


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("section", [_ROUND_1, _STEP_C2])
def test_no_lens_brief_tells_the_agent_to_write_anything(
    bodies: dict[str, str], preset: str, section: str
) -> None:
    """The main loop owns result files. Mirrors `test_render_lens_dispatch.py`'s guard."""
    directive = re.compile(r"write\s+(your|the\s+result|it\s+to|to\s+\S+/)", re.IGNORECASE)
    for line in _section(bodies[preset], section).splitlines():
        if "Task(subagent_type=" not in line:
            continue
        assert directive.search(line) is None, f"{section}: a dispatch line says to write"


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("section", [_ROUND_1, _STEP_C2])
def test_both_blocks_name_one_result_file_per_group(
    bodies: dict[str, str], preset: str, section: str
) -> None:
    """The path listing follows the dispatch unit, or coverage asks for files nobody writes."""
    block = _section(bodies[preset], section)
    for group in cr.lens_dispatch_groups(preset):
        assert f"/{group['file']}.json" in block, f"{section}: no {group['file']}.json"
    merged = {
        lens
        for g in cr.lens_dispatch_groups(preset)
        if len(g["lenses"]) > 1
        for lens in g["lenses"]
    }
    for lens in merged:
        assert f"/{lens}.json" not in block, f"{section}: still asks for the pre-merge {lens}.json"


@pytest.mark.parametrize("preset", PRESETS)
def test_the_stamp_instruction_states_both_levels(bodies: dict[str, str], preset: str) -> None:
    """ADR-007 — no SPEC AC backs this, so the assertion lives here instead of in the machine SPEC.

    The file-level `lens` is the group; each finding carries the member lens that raised it.
    Stamping the group name on every finding is what the old sentence said, and it would end
    the solo-lens vote the paragraph beneath it exists to make decidable.
    """
    body = bodies[preset]
    para = _paragraph(_section(body, "### Step 3 —"), "You write the result files")
    assert "member lens" in para

    # Anchored on the list the template actually renders, not on four free-floating substrings
    # over a fixed window. The window version could be satisfied by a neighbouring paragraph
    # that happens to mention the same names — and the paragraph right after this one does
    # exactly that, so the weaker form was one reordering away from vacuous.
    for group in cr.lens_dispatch_groups(preset):
        if len(group["lenses"]) == 1:
            continue
        enumerated = " ".join(f"`{lens}`" for lens in group["lenses"])
        assert enumerated in para, (
            f"the stamp instruction does not enumerate {group['file']!r}'s admissible "
            f"per-finding values as {enumerated!r}"
        )


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("section", [_ROUND_1, _STEP_C2])
def test_the_count_sentence_agrees_with_the_axis(
    bodies: dict[str, str], preset: str, section: str
) -> None:
    """R14 — the command must not contradict itself about the size of its own axis.

    Both blocks render their own `{{ lenses | length }}`, so both can drift, and Step C2's is
    700 lines from Step 3's. Step 1 counts the axis from a different binding entirely
    (`mandatory_lenses`), which is what makes a silent disagreement possible at all.
    """
    lenses = len(cr.mandatory_lenses(preset)) + len(
        [x for x in cr.routable_lenses(preset) if x not in cr.mandatory_lenses(preset)]
    )
    groups = len(cr.lens_dispatch_groups(preset))
    assert f"{lenses} lenses as {groups} dispatches" in _flat(_section(bodies[preset], section))


def test_no_lens_text_is_a_literal_in_the_template() -> None:
    """SPEC AC-008 — the grouping function is the SOLE producer.

    An assertion about the template source, not the render: a block holding a literal lens
    name renders correctly today and stops tracking the function the moment it changes.
    """
    src = Path("src/harness_maker/templates/stages/review.md.j2").read_text(encoding="utf-8")
    for section in (_ROUND_1, _STEP_C2):
        i = src.find(section)
        assert i != -1, f"template has no {section!r}"
        j = src.find("\n### ", i + len(section))
        block = src[i:] if j == -1 else src[i:j]
        for lens in cr.ALL_LENSES:
            assert f'"{lens}"' not in block, f"{section}: literal lens name {lens!r}"
            assert cr.LENS_DISPATCH[lens][1] not in block, f"{section}: literal {lens} brief"
        for agent in {a for a, _ in cr.LENS_DISPATCH.values()}:
            assert f'"{agent}"' not in block, f"{section}: literal agent name {agent!r}"


def test_the_render_tracks_the_grouping_constant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-005's reversal, at the render layer — asserted as a CONTRAST, not a single render.

    Parity and no-literals are both satisfied by two blocks that depend identically on a fixed
    group count. So is a one-render counterfactual: with today's template the swapped constant
    changes nothing, because nothing reads it. The observable has to be the *difference* between
    the two renders — merged by default, and the full seven-dispatch fan-out once the constant
    says one entry per lens. That is exactly the edit a future reader restoring it would make.
    """
    merged = _render(tmp_path / "merged", "Production")
    monkeypatch.setattr(cr, "LENS_GROUPS", {lens: (lens,) for lens in cr.ALL_LENSES})
    restored = _render(tmp_path / "restored", "Production")

    for section in (_ROUND_1, _STEP_C2):
        merged_block, restored_block = _section(merged, section), _section(restored, section)
        assert _groups(merged_block) == [cr.CORE_LENSES, *[(x,) for x in cr.DOMAIN_LENSES]]
        assert _groups(restored_block) == [(lens,) for lens in cr.ALL_LENSES]
        assert len(_agents(restored_block)) == len(_agents(merged_block)) + 3
        for lens in cr.ALL_LENSES:
            assert f"/{lens}.json" in restored_block
        assert "/core.json" in merged_block
        assert "/core.json" not in restored_block


#: The two claims the pre-merge template actually shipped. An exact-match regression guard,
#: NOT a truth check — see the test docstring for why the difference is the whole point.
_SHIPPED_STALE_CLAIMS = (
    "one dispatch per lens",
    "distinguished only by the lens line",
)


@pytest.mark.parametrize("preset", PRESETS)
def test_step_3_states_the_grouping_and_drops_the_claims_it_replaces(
    bodies: dict[str, str], preset: str
) -> None:
    """Two mechanical facts about ONE paragraph. Deliberately NOT a truth check.

    Three A.5 rounds were spent trying to make a regex adjudicate whether a sentence about
    dispatch grouping is *true*. It cannot: a keyword catalogue is enumerable-around (the
    reviewer produced "every lens receives its own invocation", which evaded six alternatives
    while asserting exactly the banned claim) and simultaneously over-broad (`its own dispatch`
    is a **correct** thing to say about the three domain lenses, which keep individual calls).
    CLAUDE.md's first principle says not to attempt this with pattern matching, and this file
    now obeys it.

    What is left is what is mechanically decidable, over one paragraph so a correct count
    cannot sit above a stale claim:
      - the paragraph states the axis size and the dispatch count, derived from the router;
      - neither string the pre-merge template shipped survives in it.

    **Whether newly-written prose is true is a `/hm:review` question, and PLAN risk R15 records
    that as an accepted residual** — the same treatment R13 already gives the auto-fix
    re-dispatch wording. The anchor is the computed count string, not a phrase borrowed from
    today's wording, so rewording the paragraph does not misattribute the failure.
    """
    lenses = len(cr.mandatory_lenses(preset)) + len(
        [x for x in cr.routable_lenses(preset) if x not in cr.mandatory_lenses(preset)]
    )
    groups = len(cr.lens_dispatch_groups(preset))
    count_phrase = f"{lenses} lenses as {groups} dispatches"

    section = _section(bodies[preset], _ROUND_1)
    assert count_phrase in _flat(section), f"Step 3 never states the axis size: {section[:400]!r}"
    para = _paragraph(section, count_phrase)
    for stale in _SHIPPED_STALE_CLAIMS:
        assert stale not in para, f"the pre-merge claim {stale!r} survived beside the new count"


@pytest.mark.parametrize("preset", PRESETS)
def test_step_1_says_the_core_lenses_share_a_dispatch(bodies: dict[str, str], preset: str) -> None:
    """Step 1 introduces the axis and is the first thing the operator reads.

    It described the core lenses as sharing an agent and being "told apart only by the lens
    line in their brief" — true of the fan-out, and an understatement once they also share a
    call. A reader who stops at Step 1 would expect four `code-reviewer` results.
    """
    i = bodies[preset].find("**The discovery axis**")
    assert i != -1, "Step 1 no longer introduces the axis"
    para = _flat(bodies[preset][i : i + 900])
    assert "one dispatch" in para
    assert "told apart only by the lens line in their brief" not in para
