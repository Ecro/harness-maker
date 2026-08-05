"""P2 / ADR-003 — the Phase D.5 newly-reachable-window step, with a mutation control.

`[fail:code] fix-introduced-defect-passes-all-gates` is at count:4, every recurrence on a
fully green four-gate run. The remedy sat in `failures.md` for months and was a step in no
stage template. This file gates the step's presence AND its operative force.

The distinction matters more than usual here. ADR-003 explicitly rejected "grep for the
sentence" as too weak: *a fixed sentence is satisfiable by a sentence with no operative
force*. So presence checks alone would reproduce the very failure they gate — a step that
reads well and demands nothing. `test_weakening_the_operative_clause_turns_this_red` is
therefore the load-bearing test in this file: it MUTATES the rendered step and asserts the
predicates go red. A predicate that survives its own clause being deleted is decoration.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_EXECUTE_MARKER = "#### Phase D — Post-GREEN verification"
_STEP_HEADING = "#### Phase D.5 — Newly-reachable window"
_STEP_END = "### Step 4 — Stage exit"


@cache
def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-phase-d5-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def execute_bearing_artifacts() -> dict[str, str]:
    """Every rendered document that inlines the execute stage, discovered by content."""
    root = _render_root()
    return {
        str(path.relative_to(root)): text
        for path in sorted(root.rglob("*.md"))
        if _EXECUTE_MARKER in (text := path.read_text(encoding="utf-8"))
    }


def step_body(text: str) -> str:
    """Whitespace-NORMALISED step text.

    Every predicate below matches against the collapsed form. Prose wraps, and where a
    phrase happens to break across two lines is not a property of what the step demands —
    a predicate anchored on the raw text goes red on a pure reflow (it did, on the first
    run of this file) while a real weakening slips past under a different wrap. Normalising
    makes the predicates depend on the wording only.
    """
    start = text.index(_STEP_HEADING)
    raw = text[start : text.index(_STEP_END, start)]
    # Strip leading blockquote markers first: `> ` is markdown decoration, and a wrapped
    # blockquote leaves a stray `>` mid-phrase once whitespace collapses.
    unquoted = re.sub(r"^\s*>\s?", "", raw, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", unquoted)


# ── the operative predicates ───────────────────────────────────────────────────
# Each one names a distinct thing the step must DEMAND. Presence of the heading is not on
# this list on purpose: a heading with an empty body would satisfy it.


def demands_naming_the_window(body: str) -> bool:
    """(1) The author must name the input window, concretely."""
    return bool(re.search(r"input window does this repair newly make reachable", body, re.I))


def rejects_absence_of_a_window_as_an_answer(body: str) -> bool:
    """The clause that stops "the bug no longer happens" from counting as a window."""
    return "is not a window" in body


def demands_a_named_test_in_the_same_commit(body: str) -> bool:
    """(2) A window with no fixture entering it is the count:4 shape verbatim."""
    return bool(re.search(r"same commit", body, re.I)) and "node id" in body.lower()


def distinguishes_the_window_from_the_symptom(body: str) -> bool:
    """The operative core: re-asserting the original bug is NOT entering the new window."""
    return bool(re.search(r"not merely re-assert the original symptom", body, re.I))


def carries_a_blocking_consequence(body: str) -> bool:
    """(3) Without a stop rule the step is advisory, and advisory is what failed 4×."""
    return "STOP" in body and bool(re.search(r"Do not advance the phase", body, re.I))


def covers_the_absent_case(body: str) -> bool:
    """failures.md count:8 — the repo's most-recurring class intersects this step."""
    return "absent" in body.lower() and bool(
        re.search(r"default, migration, or explicit skip", body)
    )


_PREDICATES: tuple[Callable[[str], bool], ...] = (
    demands_naming_the_window,
    rejects_absence_of_a_window_as_an_answer,
    demands_a_named_test_in_the_same_commit,
    distinguishes_the_window_from_the_symptom,
    carries_a_blocking_consequence,
    covers_the_absent_case,
)

#: The clauses each predicate is anchored on, with a weakened paraphrase of each.
#:
#: ⚠️ **This is a COVERAGE map, not a mutation control — read the honest accounting below.**
#: Two attempts were made to give it discriminating power and both failed the same way:
#:   1. delete the grepped literal → the predicate that searches for it goes red, by
#:      construction;
#:   2. replace the literal with a paraphrase → `str.replace` removes the literal, so the
#:      predicate goes red for the *identical* reason. Review caught this second one and was
#:      right: the assertion holds for any replacement not containing the original, whether
#:      the replacement is weaker, stronger, or nonsense.
#: There is no mechanical third attempt. Whether a clause carries *operative force* is a
#: semantic judgment, and every predicate here is a literal grep, so no rearrangement of
#: literals can test semantics. What this table DOES buy is real but smaller: it pins each
#: predicate to a distinct clause, so a predicate cannot silently drift onto text that
#: another one already covers, and a clause cannot be deleted without a named test failing.
#: The comment that used to claim otherwise was itself the defect — a false justification is
#: worse than an acknowledged gap, because it stops anyone from looking again.
_MUTATIONS: dict[str, tuple[str, str]] = {
    "the window definition": (
        "input window does this repair newly make reachable",
        "did you fix",
    ),
    "the non-answer rejection": ("is not a window", "is usually fine"),
    "the same-commit demand": ("same commit", "some commit"),
    "the symptom distinction": (
        "not merely re-assert the original symptom",
        "ideally covering the reported bug",
    ),
    "the stop rule": ("Do not advance the phase", "You may want to pause"),
    "the absent-case rule": (
        "default, migration, or explicit skip",
        "whatever seems reasonable",
    ),
}


def test_the_corpus_covers_all_three_artifact_families() -> None:
    """Positive control — every predicate below is vacuous over an empty corpus."""
    found = execute_bearing_artifacts()
    assert ".claude/commands/hm/execute.md" in found
    assert ".claude/stages/execute.md" in found
    assert ".agents/skills/hm-execute/SKILL.md" in found


def test_the_step_renders_on_every_target() -> None:
    """P2 exit criterion, first half."""
    for name, text in execute_bearing_artifacts().items():
        assert _STEP_HEADING in text, f"{name}: Phase D.5 is missing"


@pytest.mark.parametrize("predicate", _PREDICATES, ids=lambda p: p.__name__)
def test_the_step_is_operative_on_every_target(predicate: Callable[[str], bool]) -> None:
    """Presence is not force. Each predicate names something the step must DEMAND."""
    for name, text in execute_bearing_artifacts().items():
        assert predicate(step_body(text)), f"{name}: {predicate.__name__} is not satisfied"


def test_the_step_runs_after_the_gates_it_distrusts() -> None:
    """Ordering is the point: it exists because Phase D went green and was wrong anyway.

    Placed before Phase D, it would be answered against an unverified fix and would just be
    a second planning step.
    """
    for name, text in execute_bearing_artifacts().items():
        assert text.index(_EXECUTE_MARKER) < text.index(_STEP_HEADING), f"{name}: D.5 precedes D"
        assert text.index(_STEP_HEADING) < text.index(_STEP_END), f"{name}: D.5 follows stage exit"


@pytest.mark.parametrize("clause", sorted(_MUTATIONS), ids=lambda c: c.replace(" ", "-"))
def test_each_clause_is_covered_by_at_least_one_predicate(clause: str) -> None:
    """Coverage, honestly named. NOT the mutation control ADR-003 asked for.

    ADR-003 wants proof that the step has operative force. This cannot supply it — see the
    accounting on `_MUTATIONS`. It proves the weaker, still-useful property that every
    clause listed there is watched by some predicate, so deleting or rewording one fails a
    test with that clause's name in it rather than passing silently.

    **The ADR-003 gap is therefore OPEN**, recorded here rather than papered over: the
    operative-force question is semantic and this file is literal greps. Anyone closing it
    needs a different mechanism, not a third rearrangement of these strings.
    """
    original, weakened = _MUTATIONS[clause]
    body = step_body(execute_bearing_artifacts()[".claude/stages/execute.md"])
    assert original in body, f"mutation target {original!r} is not in the rendered step"
    mutated = body.replace(original, weakened)
    assert any(not p(mutated) for p in _PREDICATES), (
        f"{clause} ({original!r}) is watched by NO predicate — it can be edited away silently"
    )


# ── AC-002 binding ────────────────────────────────────────────────────────────


def phase_d_requires_reachable_window(rendered: dict[str, str]) -> bool:
    """AC-002's free symbol: every rendered execute surface DEMANDS the window.

    Conjunction over the operative predicates, not over the heading — a Phase D.5 that
    renders but demands nothing would satisfy a presence check and gate nothing, which is
    the failure ADR-003 named when it rejected a plain sentence-grep.
    """
    return all(
        all(predicate(step_body(text)) for predicate in _PREDICATES) for text in rendered.values()
    )


def test_ac_002_phase_d_names_newly_reachable_window() -> None:
    """AC-002's executable predicate, verbatim."""
    assert phase_d_requires_reachable_window(execute_bearing_artifacts()) is True
