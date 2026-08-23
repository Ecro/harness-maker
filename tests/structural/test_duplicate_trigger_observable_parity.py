"""The Phase A.5 duplication trigger is stated per OBSERVABLE, at every site that states it.

`test-reviewer_body.md.j2` required "at least one dedicated test function" per In-Scope Scenario
and, in the same file, blocked when "a scenario covered twice". Those cannot both hold. The
qualifier that reconciles them — duplication is duplication of one *observable* — existed only in
the Phase A authoring rule of `execute.md.j2`, which the reviewer agent never reads. Observed on a
consuming project at 0.54.0: five tests asserting five different observables under one scenario ID
blocked `/hm:execute` for two rounds.

**Every assertion here pins a relation — a count, or a locus — never the bare presence of a
token**, the rule `test_multi_lens_a5.py` states for the same corpus. Two relations carry this
module:

1. **Per-body occurrence counts.** The execute body must carry the literal exactly four times
   (three trigger sites plus the pre-existing Phase A authoring rule) and the reviewer body
   exactly once. A count moves when a site is added or dropped; a token-presence check does not.
2. **Arm separation.** The routing rule carries two unrelated defects — same-observable
   duplication, and a test whose name claims one scenario while its assertions cover another.
   The qualifier attaches to the first arm ONLY. Scenario-ID mismatch is banned pattern 5 and is a
   defect regardless of observable, so a qualifier scoping the whole disjunction would licence
   mislabelled tests — a coverage regression from a change whose goal is to stop over-blocking.
   **The duplication arm is derived by elimination**, never located by a marker of its own: the
   defect is stated as a **window exclusion, with no clause tokenizing at all**: the qualifier must
   not fall between the scenario-ID-mismatch predicate and its routing target. Four A.5 rounds
   across two budgets were spent re-tuning a clause splitter, and no two of them failed for the
   same reason — ADR-004 locks the qualifier's placement semantically but prescribes no separator,
   arm order or clause shape, so inferring a boundary from punctuation is under-determined and
   coining one is a circular oracle. Both earlier helpers were deleted rather than refined.
   **Nothing in this module is an expected literal that does not already exist in the templates it
   reads.** The window's named residual — a qualifier trailing after the closing `per_scenario`
   mention — is recorded in `_assert_qualifier_placement`'s docstring rather than claimed away.

3. **Boundaries are structural, never keyword-anchored.** Every keyword in the `<brief>` recurs
   elsewhere in the same A.5 region — `scenarios_missing` appears in the merge-rules table and
   four times in the `Resolution:` paragraph, which carries its own unedited "test aimed at
   another scenario" that the PLAN's four-site table never schedules for editing. A draft anchored
   on that keyword pulled the Resolution text in as a fifth site and became unsatisfiable by the
   correct fix. `_brief_block()` bounds on the brief's own opening line and the dispatch that
   sends it, so both are excluded by construction.

**Assertions run over RENDERED bodies, not `.j2` source** (ADR-005 of the PLAN). CLAUDE.md records
a shipped instance — `is_codex` — where every template read as correct, every render-grep passed,
and the render CONTEXT was wrong, so one arm's output diverged from its source. A source-only
oracle is structurally blind to that class.

Drift protection is **known-site only**: the anchor tuple is a fixed list, so a fifth trigger site
in a THIRD file is invisible here. A fifth site inside these two bodies does move the counts.

**Phase A.4 justification — `test_ac_003_*` passes before the implementation exists, on purpose.**
It is a *negative* invariant: rubric section 1 must still say "at least one dedicated test
function" and must never say "exactly one". Tightening it to "exactly one" was the rejected arm of
this change — it would re-create the contradiction from the other side, making a SPEC edit the only
legal repair for a test-quality gate that cannot edit SPECs. The construct it forbids does not
exist yet, so it is vacuously true today; it goes RED the moment the wrong implementation appears.
Its RED positive siblings are the `test_ac_001_*` cases, which fail against the same file and
therefore force the reviewer body to be edited — the construct cannot come into existence without
passing under this guard.
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

#: The one qualifier, reused verbatim from the Phase A authoring rule that predates this change
#: (ADR-004). A phrase coined for the clause under test would make the expected value
#: self-referential — the circular oracle the spec stage rejects by policy.
QUALIFIER = "for the same observable"

#: Phrases that state the trigger as a count. They are a defect only when they are **bare** — see
#: `_assert_no_bare_cardinality`. A blanket substring ban was tried and withdrawn: AC-001's Then
#: clause is semantic ("states the trigger as a count of tests sharing a scenario ID") while a
#: substring test is lexical, and the two diverge in BOTH directions. "covered twice for the same
#: observable" is SPEC-correct and contains "covered twice"; "no duplicate" is pre-existing generic
#: coverage-lens English at `execute.md.j2:275` and `:302` — two of the four sites being edited.
#: Banning the substrings forces a rewording chosen only to dodge them, which is the invented-
#: oracle shape the rest of this module is built to avoid.
_CARDINALITY_PHRASINGS = ("covered twice", "no duplicate")

#: The scenario-ID-mismatch arm, located by text that ALREADY EXISTS at both sites today —
#: "aimed at a different scenario" (reviewer bullet) and "aimed at another scenario" (brief), of
#: which this is the common prefix. Every expected literal in this module predates the change, so
#: nothing here is a phrase coined for the file under test (ADR-004's rejected alternative).
_MISMATCH_LOCATOR = "aimed at a"

#: There is deliberately NO marker for what the mismatch arm must SAY. SPEC AC-001's Then clause
#: requires only that the arm "carries no such qualifier" — it prescribes no wording. A draft
#: pinned "regardless of observable" here, sourced from ADR-004's justification prose rather than
#: from the SPEC or from either template; that is the same invented-literal defect as the
#: withdrawn duplication marker, one arm over. A correct fix that simply leaves the mismatch arm
#: reading as it does today satisfies the SPEC and must not go RED for wording.

#: The brief's own opening line, pre-existing template text. Used as the start boundary rather
#: than a keyword, because every keyword in the brief recurs elsewhere in the same region.
_BRIEF_OPENING = "below is the same for all three"

#: The routing destination both sites already name, used as the window's closing anchor. Like
#: every other expected string in this module, it exists in the templates today.
_ROUTING_TARGET = "per_scenario"

#: The Phase A authoring rule — site 4, and the qualifier's provenance (ADR-004). Pre-existing
#: text, like every other expected string here.
_AUTHORING_RULE_LOCATOR = "the Phase A.5 test-reviewer adjudicates"

_A5 = "#### Phase A.5"
_PHASE_B = "#### Phase B"

#: Runtime-agnostic: Claude Code dispatches with `Task(subagent_type=…)`, Codex with
#: `spawn_agent(agent_type=…)`. A pattern naming only the first counts ZERO on every Codex skill.
_DISPATCH = re.compile(r'(?:Task\(subagent_type|spawn_agent\(agent_type)="test-reviewer"')

#: Expected occurrences of QUALIFIER, per rendered body. Four in execute: the coverage-lens table
#: row, the `<brief>` routing sentence, the dispatch string, and the Phase A authoring rule that
#: already carried it. One in the reviewer body: the Hard Rule routing bullet.
_EXPECTED_EXECUTE_OCCURRENCES = 4
_EXPECTED_REVIEWER_OCCURRENCES = 1


@cache
def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    answers.instrumentation = InstrumentationConfig(stage_agent_ledger=True)
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-dupobs-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def _execute_bodies() -> dict[str, str]:
    """Every rendered document inlining the A.5 gate, discovered by content, not by path.

    Path-based discovery would silently miss the codex family, a separate synthesis path.
    """
    found = {
        str(p.relative_to(_render_root())): text
        for p in sorted(_render_root().rglob("*.md"))
        if _A5 in (text := p.read_text(encoding="utf-8"))
    }
    assert found, "no rendered document carries the A.5 gate — every assertion here is vacuous"
    return found


@cache
def _reviewer_bodies() -> dict[str, str]:
    """Every rendered form of the test-reviewer agent prompt, discovered by content.

    harness-maker does not render its own agents to disk, so there is no `.claude/agents/` to
    read in this repo — the subject only exists inside a render root.
    """
    needle = "Banned-patterns list is authoritative"
    found = {
        str(p.relative_to(_render_root())): text
        for p in sorted(_render_root().rglob("*"))
        if p.is_file()
        and p.suffix in {".md", ".mdc", ".toml"}
        and needle in (text := p.read_text(encoding="utf-8", errors="ignore"))
    }
    assert found, "no rendered document carries the test-reviewer Hard Rules — vacuous otherwise"
    return found


def _a5_region(text: str) -> str:
    """The A.5 gate body, bounded by two real headings."""
    start = text.index(_A5)
    return text[start : text.index(_PHASE_B, start)]


def _assert_no_bare_cardinality(name: str, where: str, text: str) -> None:
    """Every cardinality phrase is qualified before its clause ends; a bare one is the defect.

    The window runs from the end of the phrase to whichever comes first: the routing target, or
    end of line (the coverage-lens table row is one line and names no routing target). A site that
    drops the phrase entirely is trivially clean — the loop does not fire — so both a qualified
    rewrite and a full rephrasing are accepted, and only the bare count survives as a failure.

    **Blind to negation, like its sibling below.** `QUALIFIER in window` is substring containment:
    prose that qualifies the cardinality phrase and then negates the qualifier inside the same
    window passes. Disclosed rather than fixed — no mechanical predicate over natural language
    decides it, and pretending otherwise is what the abandoned splitters did.
    """
    for phrasing in _CARDINALITY_PHRASINGS:
        for m in re.finditer(re.escape(phrasing), text):
            ends = (text.find(_ROUTING_TARGET, m.end()), text.find("\n", m.end()))
            bounds = [b for b in ends if b != -1]
            window = text[m.end() : min(bounds) if bounds else len(text)]
            assert QUALIFIER in window, (
                f"{name}: {where} still states the trigger as {phrasing!r} with no qualifier "
                "before the clause ends — that is a count of tests sharing a scenario ID, which "
                "is the reading that blocked N tests asserting N different observables"
            )


def _assert_qualifier_placement(name: str, where: str, text: str) -> None:
    """The qualifier is present, and it does NOT scope the scenario-ID-mismatch predicate.

    **Nothing here tokenizes clauses**, and that is the whole point. Four A.5 rounds across two
    budgets established that a prose splitter has no fixed point under this task's constraints:
    ADR-004 locks the qualifier's placement *semantically* but prescribes no separator, arm order
    or clause shape, so inferring a boundary from punctuation is under-determined (an
    implementation straddles it — rounds 1 and 4) and coining one is a circular oracle (a
    correctly-phrased fix goes RED — rounds 2 and 3). Both earlier helpers were deleted rather
    than re-tuned.

    The window runs from `_MISMATCH_LOCATOR` — text present at both sites today — to the next
    `_ROUTING_TARGET` after it, the routing destination both sites already name. ADR-004's own
    rejected phrasing ("... aimed at a different scenario, for the same observable -> a
    `per_scenario` entry") lands the qualifier inside that window and goes RED. A scope-compliant
    fix goes GREEN in any punctuation, any arm order, any wrapping.

    **Named residual, and it is NOT narrower — an earlier draft claimed that and was wrong.** A
    qualifier trailing AFTER the window's closing `per_scenario` mention — "... is a
    `per_scenario` entry for that scenario with quality FAIL for the same observable" — escapes
    the window, and appended to the shared consequence it reads as scoping BOTH arms. That is the
    same whole-disjunction defect ADR-004 rejects, relocated past the window's right edge.

    **No boundary tried so far separates it, and that is a checkable claim rather than an
    excuse.** Extending the
    right edge to the end of the bullet would catch it — and would also reject the correct
    mismatch-arm-first phrasing, because the two are lexically indistinguishable:

        correct  "a test aimed at a different scenario -> the same `per_scenario` FAIL; two tests
                  asserting one scenario for the same observable -> a `per_scenario` entry"
        wrong    "... or a test aimed at a different scenario -> is a `per_scenario` entry for
                  that scenario with quality FAIL for the same observable"

    Both give the token order LOCATOR -> ROUTING TARGET -> QUALIFIER. No predicate over those
    three positions separates them. **That shows the residual survives the boundaries tried so
    far — end-of-bullet, and the splitters the earlier rounds burned through — not that no
    boundary can exist.** A narrower one (the next `;` after the routing target, say) was never
    evaluated against the real templates, and it belongs to exactly the fragile-splitter class
    this module abandoned; a reader deciding whether to re-attempt should weigh the round history
    rather than read this paragraph as a proof of impossibility.

    Separating them needs either a prescribed clause shape (an ADR this PLAN does not have) or a
    rubric judgment (AC-004). Until one exists, this residual is the accepted cost of removing the
    splitter, stated so a reader inherits the limit rather than rediscovering it.

    **Second residual, disclosed for symmetry: this predicate is blind to negation.** It asks only
    whether the literal falls inside a window, so it cannot tell a qualifier that narrows the
    trigger from prose that places the qualifier and then takes it back — "for the same observable
    (and, for clarity, this still applies even when the observables differ)". That shape satisfies
    every check here while describing the coarse trigger this change exists to remove. No
    mechanical predicate over natural language decides it; AC-004's rubric judgment is the only
    reader that can, and it covers the reviewer body only.
    """
    assert QUALIFIER in text, (
        f"{name}: {where} does not carry {QUALIFIER!r} at all — two tests sharing one observable "
        "route nowhere, and N tests asserting N different observables still block"
    )
    positions = [m.start() for m in re.finditer(re.escape(_MISMATCH_LOCATOR), text)]
    assert positions, (
        f"{name}: {where} has no scenario-ID-mismatch predicate — {_MISMATCH_LOCATOR!r} is text "
        "that exists there today, so its disappearance means the predicate was dropped"
    )
    for start in positions:
        close = text.find(_ROUTING_TARGET, start)
        window = text[start : close if close != -1 else len(text)]
        assert QUALIFIER not in window, (
            f"{name}: in {where} the qualifier falls between the scenario-ID-mismatch predicate "
            f"and its routing target, so it scopes that predicate too. Scenario-ID mismatch is "
            "banned pattern 5 — a defect whether or not the mislabelled test happens to assert a "
            "different observable — and forgiving it is a coverage regression from a change whose "
            "goal is to stop over-blocking"
        )


def _routing_bullet(text: str) -> str:
    """The Hard Rule bullet that routes an out-of-category finding into a schema field.

    The end boundary takes the NEAREST of the next bullet and the next section heading. Bounding
    on the next bullet alone silently ran to end-of-file whenever this was the last bullet in the
    section — which it is today — so the helper's window was broader than its name, and prose
    appended after it would have been absorbed without any test noticing.
    """
    marker = "Banned-patterns list is authoritative"
    start = text.index(marker)
    ends = [e for e in (text.find("\n- ", start), text.find("\n#", start)) if e != -1]
    return text[start : min(ends) if ends else len(text)]


def _brief_block(region: str) -> str:
    """The `<brief>` string itself, bounded by its own opening line and the dispatch that sends it.

    A draft anchored this on paragraphs containing `scenarios_missing`. That substring is NOT
    unique to the brief: in `execute.md.j2` it also appears in the merge-rules table row and four
    times in the `Resolution:` repair-arm paragraph — and that paragraph carries its own
    unedited "test aimed at another scenario". Joining it in made the Resolution text a
    `_MISMATCH_LOCATOR` hit inside a site the PLAN's four-site table never schedules for editing,
    so the oracle became unsatisfiable by the correct, scope-compliant fix. Both boundaries below
    precede the dispatch, so the table and the Resolution paragraph are out by construction, and
    the end boundary is the dispatch match itself rather than a runtime-specific heading.
    """
    start = region.index(_BRIEF_OPENING)
    match = _DISPATCH.search(region, start)
    assert match, "no test-reviewer dispatch follows the <brief> opening — the region is malformed"
    return region[start : match.start()]


# --------------------------------------------------------------------------------------- AC-001


@pytest.mark.parametrize("name", sorted(_reviewer_bodies()))
def test_ac_001_reviewer_hard_rule_is_observable_qualified(name: str) -> None:
    """The reviewer's own routing rule states duplication per observable, and only there.

    The reviewer agent is the only reader whose verdict blocks Phase B, and it does not read the
    stage template — so the qualifier living in `execute.md.j2` alone left this clause coarse.
    """
    body = _reviewer_bodies()[name]

    assert body.count(QUALIFIER) == _EXPECTED_REVIEWER_OCCURRENCES, (
        f"{name}: {body.count(QUALIFIER)} occurrence(s) of {QUALIFIER!r}, expected "
        f"{_EXPECTED_REVIEWER_OCCURRENCES} — the routing bullet's duplication arm, and nowhere "
        "else. This is the fifth of AC-002's five occurrences and it closes the padding hole: "
        "without it a second copy elsewhere in this body satisfies every other check here"
    )

    _assert_no_bare_cardinality(name, "the rendered reviewer body", body)

    bullet = _routing_bullet(body)
    assert QUALIFIER in bullet, (
        f"{name}: the body's single qualifier is not in the routing bullet — the bullet is the "
        "clause that decides a per_scenario verdict, so the qualifier is inert anywhere else"
    )
    _assert_qualifier_placement(name, "the routing bullet", bullet)


# --------------------------------------------------------------------------------------- AC-002


@pytest.mark.parametrize("name", sorted(_execute_bodies()))
def test_ac_002_execute_body_carries_the_qualifier_at_every_trigger_site(name: str) -> None:
    """Three trigger sites plus the pre-existing authoring rule — a count, not a token check."""
    body = _execute_bodies()[name]

    assert body.count(QUALIFIER) == _EXPECTED_EXECUTE_OCCURRENCES, (
        f"{name}: {body.count(QUALIFIER)} occurrence(s) of {QUALIFIER!r}, expected "
        f"{_EXPECTED_EXECUTE_OCCURRENCES} (coverage-lens row, <brief> routing sentence, dispatch "
        "string, Phase A authoring rule). A different count means a site was added or dropped"
    )

    region = _a5_region(body)

    # Each of the three edited sites gets its OWN locus assertion. The aggregate count above is
    # not a substitute: an implementation can reach 4 by writing the qualifier twice into one line
    # and leaving another site bare, so the sum is satisfied while a site a reviewer actually
    # reads is still coarse. The `== 1` counts close the padding half of the same hole.
    lens_rows = [ln for ln in region.splitlines() if ln.startswith("| `coverage`")]
    assert len(lens_rows) == 1, f"{name}: {len(lens_rows)} coverage-lens table row(s), expected 1"
    assert lens_rows[0].count(QUALIFIER) == 1, (
        f"{name}: the coverage lens question carries {lens_rows[0].count(QUALIFIER)} copies of the "
        "qualifier, expected exactly 1 — it must ask duplicate of WHAT, once"
    )

    dispatch_lines = [ln for ln in region.splitlines() if _DISPATCH.search(ln)]
    assert len(dispatch_lines) == 1, (
        f"{name}: {len(dispatch_lines)} test-reviewer dispatch site(s), expected 1"
    )
    assert dispatch_lines[0].count(QUALIFIER) == 1, (
        f"{name}: the dispatch string carries {dispatch_lines[0].count(QUALIFIER)} copies of the "
        "qualifier, expected exactly 1 — that string is what the reviewer is accountable for"
    )

    # The <brief> routing sentence: the site the reviewer actually reads when deciding a
    # per_scenario verdict, and the one an aggregate count leaves unpinned. Isolated by
    # `scenarios_missing`, which the routing paragraph carries today and neither the lens row nor
    # the dispatch line does — so this cannot be satisfied by the other two sites' qualifiers.
    _assert_qualifier_placement(name, "the <brief> block", _brief_block(region))

    # Site 4 — the Phase A authoring rule, which already carried the qualifier before this change.
    # It sits ABOVE the A.5 region, so none of the three assertions above can reach it, and for one
    # round it was covered only by the aggregate: a mutation stripping the qualifier there while
    # leaving any stray copy elsewhere in the body kept the count at four and passed everything.
    # A count invariant standing in for a locus check it does not perform is the same substitution
    # this module rejects everywhere else.
    authoring = [ln for ln in body.splitlines() if _AUTHORING_RULE_LOCATOR in ln]
    assert len(authoring) == 1, (
        f"{name}: {len(authoring)} Phase A authoring-rule line(s), expected 1 — the locator is "
        "text that exists there today, so a different count means the rule moved or was dropped"
    )
    assert QUALIFIER in authoring[0], (
        f"{name}: the Phase A authoring rule no longer says duplication is duplication of the "
        "same observable — it is where the qualifier's provenance lives (ADR-004), so losing it "
        "there makes every other site's expected value self-referential"
    )


@pytest.mark.parametrize("name", sorted(_execute_bodies()))
def test_ac_002_no_cardinality_phrasing_survives_in_the_a5_region(name: str) -> None:
    """The coarse reading must be gone from the region, not merely outnumbered by the new one."""
    _assert_no_bare_cardinality(name, "the A.5 region", _a5_region(_execute_bodies()[name]))


@pytest.mark.parametrize("name", sorted(_execute_bodies()))
def test_ac_002_brief_keeps_the_mismatch_arm_unqualified(name: str) -> None:
    """Same arm separation as AC-001, on the copy of the rule that travels in the brief.

    Kept as its own function though it now shares a helper with the site-coverage test: they
    assert DIFFERENT observables of the same body — one that every trigger site carries the
    qualifier, one that the two arms stay separate. Per the SPEC being implemented here,
    duplication is duplication of one observable, not two tests sharing an AC id.
    """
    _assert_qualifier_placement(
        name, "the <brief> block", _brief_block(_a5_region(_execute_bodies()[name]))
    )


# --------------------------------------------------------------------------------------- AC-003


@pytest.mark.parametrize("name", sorted(_reviewer_bodies()))
def test_ac_003_rubric_keeps_at_least_one_dedicated_test(name: str) -> None:
    """Regression guard on the clause the narrowing exists to make true.

    Tightening this to "exactly one" was the rejected arm: it makes splitting the SPEC the only
    legal repair for a test-quality gate, and `/hm:execute` cannot edit a SPEC.
    """
    body = _reviewer_bodies()[name]
    assert "at least one dedicated test function" in body, (
        f"{name}: rubric section 1 no longer says 'at least one dedicated test function' — N "
        "tests per scenario is what the narrowed trigger is designed to permit"
    )
    assert "exactly one dedicated test function" not in body, (
        f"{name}: rubric section 1 was tightened to 'exactly one', which re-creates the "
        "contradiction from the other side"
    )
