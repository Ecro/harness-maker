"""Phase A.5 fans out to three lenses in one message, and the round is merged before judging.

PLAN-multi-lens-review-round, Phase 2 + Phase 3 exit criteria.

**Every assertion here pins a relation — count, order, or locus — never the presence of a
token.** That rule is not stylistic. The parent task (`opus5-selfreview-vs-harness-gates`)
shipped a first draft whose render tests greped for words, and a second reviewer showed every
one of them would go inert the moment the words were typed: the test passes on the vocabulary
and says nothing about the structure. So `intersection` appearing somewhere in the file proves
nothing; `intersection` appearing in the `passing_tests` row of the merge table, in a block that
also says the field decides nothing, is a fact about the document.

The two anchors used throughout are real headings or real lines in the rendered body:
`#### Phase A.5` (a heading), the `Resolution:` line (prose, NOT a heading — `^#{2,6} ` will
never find it), and `#### Phase B` (a heading). Ranges are half-open on the anchors.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import InstrumentationConfig, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_A5 = "#### Phase A.5"
_PHASE_B = "#### Phase B"
_RESOLUTION = "\nResolution:"

_DISPATCH = re.compile(r'Task\(subagent_type="test-reviewer"')
_LENSES = ("red-correctness", "discrimination", "coverage")

#: The forbidden thing is CONDITIONING A REWRITE DECISION on `passing_tests`, so the left-hand
#: term has to be the action CLASS, not two literals. A `\brewrite|re-author\b` pattern let the
#: defect back in verbatim as "Do not modify anything in `passing_tests[]` — treat that list as
#: fixed": no `rewrite`, no `re-author`, zero offenders, green — the go-inert property this
#: module's docstring disowns.
_REWRITE_ACTION = re.compile(
    r"\b(re-?writes?|re-?author\w*|frozen|freeze|do not (modify|touch|change|re-author))\b",
    re.I,
)

#: A sentence can name a rewrite action AND `passing_tests` while stating the CORRECT rule —
#: "`passing_tests` is advisory and must not control rewrites" trips the action class on
#: `rewrites` and is exactly the wording this change installs. A negative lookbehind does not
#: reach that case (the action word is not adjacent to the negation), so the disclaimer is
#: matched explicitly instead. Accepted limit: prose that both forbids and re-imposes the
#: conditioning in one sentence would be exempted — no such shape is plausible here.
_ADVISORY_DISCLAIMER = re.compile(
    r"advisory|decides nothing|not frozen|must not control|does not decide", re.I
)


@cache
def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    # The ledger axis defaults OFF for a fresh install; the round-scoping assertions below
    # are about the emit guidance, so pin it ON or they would be vacuous.
    answers.instrumentation = InstrumentationConfig(stage_agent_ledger=True)
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-multilens-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def _bodies() -> dict[str, str]:
    """Every rendered document inlining the A.5 gate, discovered by content, not by path.

    Path-based discovery would silently miss the codex family, which is a separate synthesis
    path — the exact gap `test_stage_agent_ledger_wiring` exists to close for the ledger.
    """
    found = {
        str(p.relative_to(_render_root())): text
        for p in sorted(_render_root().rglob("*.md"))
        if _A5 in (text := p.read_text(encoding="utf-8"))
    }
    assert found, "no rendered document contains the A.5 gate — every assertion below is vacuous"
    return found


def test_all_three_targets_carry_the_a5_gate() -> None:
    """Positive control. Without it every assertion in this file is silently claude-only.

    `_bodies()` asserting merely non-empty is not a substitute: if the codex synthesis path
    stopped inlining the A.5 body, the dict would still hold the two claude entries, the
    parametrization would still be non-empty, and every test here would pass over a corpus with
    a codex-shaped hole in it — the exact failure `_bodies()`'s docstring claims to prevent.
    """
    for expected in (
        ".claude/commands/hm/execute.md",
        ".claude/stages/execute.md",
        ".agents/skills/hm-execute/SKILL.md",
    ):
        assert expected in _bodies(), f"{expected} does not carry the A.5 gate"


def _a5_region(text: str) -> str:
    """The A.5 gate body, bounded by two real headings."""
    start = text.index(_A5)
    end = text.index(_PHASE_B, start)
    return text[start:end]


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_three_lens_dispatches_precede_the_resolution(name: str) -> None:
    """Count AND order. Three is the point; before the merge is what makes them one round."""
    region = _a5_region(_bodies()[name])
    hits = [m.start() for m in _DISPATCH.finditer(region)]
    assert len(hits) == 3, f"{name}: {len(hits)} test-reviewer dispatch site(s), expected 3"
    resolution = region.index(_RESOLUTION)
    assert max(hits) < resolution, (
        f"{name}: a dispatch site appears after the Resolution — the round cannot be merged "
        "before it is judged if a lens is dispatched afterwards"
    )

    # CONTIGUITY is the property "in one message" actually means, and count+order do not imply
    # it: three dispatches split into three fenced blocks with "dispatch, await the verdict,
    # then the next" between them satisfy both and restore the serial gate this change exists
    # to replace — the +2 round-trip re-baseline was paid FOR the concurrency.
    # The property is ONE MESSAGE, i.e. one fenced block with nothing between the calls that
    # could serialise them. Requiring three CONSECUTIVE physical lines is stricter than that and
    # freezes formatting: a correct rewrite using multi-line `Task(...)` calls, or a comment
    # between them, is still one message and must stay green. So: same fence, and no prose line
    # between the first and last dispatch.
    lines = region.splitlines()
    idx = [i for i, ln in enumerate(lines) if _DISPATCH.search(ln)]
    fences = [i for i, ln in enumerate(lines) if ln.startswith("```")]
    assert [f for f in fences if f < idx[0]], f"{name}: no fence opens before the dispatch lines"
    assert [f for f in fences if f > idx[-1]], f"{name}: no fence closes after the dispatch lines"
    assert not [f for f in fences if idx[0] < f < idx[-1]], (
        f"{name}: a fence boundary sits between the dispatch lines — they are not one message, "
        "and separate blocks are how a fan-out silently becomes a serial retry"
    )
    between = [
        ln
        for ln in lines[idx[0] : idx[-1]]
        if ln.strip() and not ln.lstrip().startswith(("Task(", ")", "#", '"', "'"))
    ]
    assert not between, (
        f"{name}: prose sits between the dispatch lines ({between[:2]!r}) — text like 'await the "
        "verdict, then dispatch the next' turns the fan-out back into the serial gate this "
        "change replaced, while count and order still pass"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_each_lens_owns_exactly_one_dispatch(name: str) -> None:
    """Three dispatches that all carry the same lens would satisfy a bare count of three.

    The unit is the dispatch LINE, not the block: a lens legitimately appears twice within its
    own line (once in `description=`, once in the prompt's `Your lens:`), so a block-wide
    `count(lens) == 1` fails on a correct template — it did, on the first draft of this test.
    """
    region = _a5_region(_bodies()[name])
    block = region[region.index('Task(subagent_type="test-reviewer"') : region.index(_RESOLUTION)]
    lines = [ln for ln in block.splitlines() if _DISPATCH.search(ln)]
    assert len(lines) == 3, f"{name}: {len(lines)} dispatch line(s), expected 3"
    # Scope the count to the two SEGMENTS that name the lens, not to the whole line. Whole-line
    # membership pins vocabulary uniqueness: it breaks the moment a correct rewrite inlines the
    # shared brief (which contains "coverage holes" and "duplication") into all three prompts,
    # and it cannot see the real degenerate case — three distinct `description=` labels with one
    # prompt body copied to all three, reviewing one thing thrice under three names.
    segments = []
    for ln in lines:
        head, sep, tail = ln.partition("Your lens:")
        assert sep, f"{name}: a dispatch line has no `Your lens:` segment: {ln[:80]!r}"
        label = head.partition("description=")[2]
        segments.append((label, tail.partition("—")[0]))

    for lens in _LENSES:
        labelled = [i for i, (label, _) in enumerate(segments) if lens in label]
        asked = [i for i, (_, body) in enumerate(segments) if lens in body]
        assert len(labelled) == 1, (
            f"{name}: lens {lens!r} labels {len(labelled)} dispatch(es), expected 1 — "
            "two dispatches carrying the same lens is a fan-out that reviews one thing thrice"
        )
        assert labelled == asked, (
            f"{name}: {lens!r} is labelled on dispatch {labelled} but asked for on {asked} — "
            "the label and the prompt disagree, so this dispatch reviews something other than "
            "what it is named"
        )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_passing_tests_is_the_one_advisory_row_of_the_merge_table(name: str) -> None:
    """Locus, not token. `intersection` anywhere proves nothing about which field it governs.

    `passing_tests[]` carries bare function names with no `test_file`, so it cannot identify a
    test; conditioning a rewrite on it would freeze the wrong one. The merge table must say so
    in the row that governs it, and `blocking_issues` must be the authoritative one.
    """
    region = _a5_region(_bodies()[name])
    rows = [ln for ln in region.splitlines() if ln.startswith("| `")]
    assert len(rows) >= 5, f"{name}: merge table has {len(rows)} field rows, expected >= 5"

    passing = [r for r in rows if r.startswith("| `passing_tests")]
    assert len(passing) == 1, f"{name}: {len(passing)} passing_tests rows, expected exactly 1"
    assert "advisory" in passing[0], f"{name}: passing_tests row does not call itself advisory"
    assert "decides nothing" in passing[0], (
        f"{name}: passing_tests row does not say it decides nothing — the shipped "
        "`FROZEN — do not re-author` reading survives"
    )

    blocking = [r for r in rows if r.startswith("| `blocking_issues")]
    assert len(blocking) == 1, f"{name}: {len(blocking)} blocking_issues rows, expected exactly 1"
    assert "Authoritative" in blocking[0], (
        f"{name}: blocking_issues row is not marked authoritative — nothing then says which "
        "field the retry rewrites from"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_no_rewrite_sentence_is_conditioned_on_passing_tests(name: str) -> None:
    """A bounded per-sentence relation, not a semantic universal over the whole document.

    The shipped bullet held BOTH the rewrite rule and `passing_tests[] is FROZEN — do not
    re-author them` in one sentence. Under three lenses the intersection is strictly narrower
    than any single lens's list, so leaving that clause in place would tell the executor two
    different things about the same set.
    """
    region = _a5_region(_bodies()[name])
    sentences = re.split(r"(?<=[.!?])\s+", region)
    # The forbidden thing is CONDITIONING A REWRITE DECISION on `passing_tests`, so the left-hand
    # term has to be the action class, not two literals. `\brewrite|re-author\b` let the defect
    # back in verbatim as "Do not modify anything in `passing_tests[]` — treat that list as
    # fixed": no `rewrite`, no `re-author`, zero offenders, green — the go-inert property this
    # module's docstring disowns.
    offenders = [
        s
        for s in sentences
        if _REWRITE_ACTION.search(s) and "passing_tests" in s and not _ADVISORY_DISCLAIMER.search(s)
    ]
    assert not offenders, (
        f"{name}: a rewrite instruction is conditioned on passing_tests: {offenders!r}"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_the_retry_hands_over_both_arms_and_uses_no_git(name: str) -> None:
    """Phase 3. Two arms, because the retry does two things — and neither is a `git diff`.

    `execute.md.j2` mandates rewriting `blocking_issues[]` tests AND authoring one per
    `scenarios_missing[]`. A selector keyed only on blocking entries cannot reach the authored
    ones, and the coverage lens — the one that produced `scenarios_missing` — is exactly the
    lens re-dispatched to judge them. `git diff` reaches neither: Phase A's files are usually
    untracked, so it returns nothing for precisely the tests in question.
    """
    region = _a5_region(_bodies()[name])
    retry = region[region.index(_RESOLUTION) :]

    handoff = [s for s in re.split(r"(?<=[.!?])\s+", retry) if "test_function" in s]
    assert handoff, f"{name}: the retry names no file+function selector for the handoff"
    assert any("test_file" in s for s in handoff), (
        f"{name}: the selector names test_function without test_file — a bare function name "
        "cannot identify a test across files"
    )
    # Sentence-scoped, like the selector arm above. A bare `"scenarios_missing" in retry` is
    # INERT: the ordinary fix instruction ("author one test per `scenarios_missing[]`") already
    # supplies the token, so the handoff arm could be deleted outright and the check stay green.
    authored = [s for s in handoff if "scenarios_missing" in s]
    assert authored, (
        f"{name}: no handoff sentence mentions scenarios_missing — tests authored in response "
        "to the coverage lens would be handed back to it unannounced, and the token elsewhere "
        "in the region does not make that instruction exist"
    )
    assert any("after-only" in s or "after only" in s for s in authored), (
        f"{name}: the scenarios_missing arm does not say it is after-only — an authored test "
        "has no 'before', and implying one invites a fabricated diff"
    )
    # An INVOCATION, not the word. The retry prose deliberately *names* `git diff` in order to
    # forbid it, so a bare `\bgit\b` search fails on the very text that fixes the defect — it
    # did, on the first draft of this test. An invocation is a `!`-prefixed line or a line
    # inside a fenced block; prose mentioning git is fine and is the point.
    # Three call shapes, because this file is parametrized over BOTH renders: the claude arm
    # writes `!… git …`, a bare fenced line writes `git …`, and the codex arm writes
    # `Bash("cd <WT> && git diff")` — which matches neither of the first two, so a two-shape
    # matcher enforces the rule on the claude artifacts only and is structurally unable to fire
    # on the codex half of its own parametrization.
    invocations = [
        ln
        for ln in retry.splitlines()
        if re.match(r"\s*!.*\bgit\b", ln)
        or re.match(r"\s*git\s+\w", ln)
        or re.match(r'\s*Bash\("[^"]*\bgit\s+\w', ln)
    ]
    assert not invocations, (
        f"{name}: the retry region invokes git ({invocations!r}) — `git diff` is empty for the "
        "untracked files Phase A authors, so the handoff would silently carry nothing"
    )


@pytest.mark.parametrize("name", sorted(_bodies()))
def test_the_retry_states_the_round_budget_and_the_no_carry_rule(name: str) -> None:
    """Both rules live between the merge table and the ledger step — locus, not presence."""
    region = _a5_region(_bodies()[name])
    retry = region[region.index(_RESOLUTION) :]
    ledger = retry.find("stage_agent_ledger")
    window = retry if ledger == -1 else retry[:ledger]
    assert "2 rounds" in window, (
        f"{name}: the retry budget is not restated in rounds — under three dispatches per "
        "attempt, `2 attempts` silently means something new"
    )
    assert "No verdict carries" in window, (
        f"{name}: the no-carry rule is missing — a retired lens's PASS describes the pre-fix "
        "file, so carrying it can freeze a test another lens's fix rewrote"
    )
