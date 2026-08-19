"""Phase 1 of PLAN-ai-work-boundaries — the `## 🚧 Contract Boundaries` required section.

Two things are proved here, and they are different in kind.

**The render assertions** prove the instruction shipped, in BOTH variants. That is all a
render-grep can prove (CLAUDE.md checkpoint 2): it cannot show that an author fills the
section, only that the command asks for it. The Codex arm is asserted explicitly because
`is_codex` is derived from the output path and a variant-blind test is the documented way
this class of change ships half-done.

**Phase A.4 justified pass — `test_this_plan_satisfies_the_rule_it_introduces`.** It is
GREEN before the template change, and that is not a false RED. Its subject is a different
artifact: `work-docs/PLAN-ai-work-boundaries.md`, which was written during `/hm:plan` and
already complies. It goes red the moment a Do-not-change bullet drifts out of the grammar —
which it did, on that PLAN's own fourth bullet, during plan validation. Its RED positive
sibling is `test_entry_grammar_is_stated`: until the template states the grammar, this
check enforces a rule the harness never published, so the two ship together or not at all.
Recorded here because A.4 forbids carrying an unexplained pass into A.5.

**The self-compliance assertion** is executable rather than textual. It parses THIS repo's
own `PLAN-ai-work-boundaries.md` against ADR-008's grammar, so the grammar is decided by a
function instead of by reading. It earns its place: it went red on the fourth bullet of that
PLAN's own Do-not-change list during plan validation, which is exactly the defect no amount
of prose review had caught.
"""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path, PurePosixPath
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO_ROOT = Path(__file__).parents[2]
_PLAN_DOC = _REPO_ROOT / "work-docs" / "PLAN-ai-work-boundaries.md"

_SUBLIST_PIN = "Do not change"

#: The literal an author writes when a sub-list is genuinely empty (ADR-002).
_NONE_RULE = "none — this task has no contract boundaries"

#: Anchored at line start: the Executive Summary names the heading inline, and an
#: unanchored split lands on that prose instead of on the section.
_SECTION_RE = re.compile(r"^## 🚧 Contract Boundaries\s*$", re.M)

#: Forms (a) and (b) of ADR-008's three; form (c) is `_NONE_BULLET` below. An entry matching
#: none of the three is undecidable, which is worse than an absent one — a consumer silently
#: drops it.
#: End-anchored, because the grammar closes with "**Exactly three admitted forms**, one per
#: `- ` bullet": without the `$` a bullet like `` - `src/x.py` and also whatever `` parsed as
#: conforming, so the gate admitted exactly the free-form entry the grammar forbids. The only
#: admitted suffix is the em-dash rationale — plus trailing whitespace, because markdown's
#: two-space hard break is a conforming bullet and a gate stricter than its contract produces
#: false REDs on clean documents.
_PATH_BULLET = re.compile(r"^- `([\w./-]+)`(?: — \S.*?)?\s*$")
_ADVISORY_BULLET = re.compile(r"^- Advisory: \S")

#: Form (c) of the published grammar — the empty sentinel. It is neither a path nor an
#: Advisory: line, so before this was named the template mandated a line its own grammar
#: called a violation, and the parser rejected the one form ADR-002 requires.
_NONE_BULLET = re.compile(r"^- none — this task has no contract boundaries\s*$")


def _is_repo_relative(candidate: str) -> bool:
    """ADR-008 says repo-relative; the regex alone does not.

    `Path(root) / "/etc/passwd"` DISCARDS the root — absolute right operands win — so an
    absolute entry resolved outside the repo and `.exists()` returned True for it. A `..`
    entry escapes the same way and only fails by luck of what is on disk.
    """
    posix = PurePosixPath(candidate)
    return not posix.is_absolute() and ".." not in posix.parts


#: The required-sections list is a numbered `N. **<heading>** — …` construct. Collected
#: over the WHOLE command this pattern also matches the visualization list and the
#: 5-term gate list (19 hits against a stated 10), so every count MUST be taken over the
#: sliced region below. A whole-file count is red for the wrong reason and goes green by
#: narrowing the regex rather than by renumbering anything.
_NUMBERED_ENTRY = re.compile(r"^(\d+)\. \*\*([^*]+)\*\* —", re.M)
_REQUIRED_ENTRY = re.compile(r"^\d+\. \*\*🚧 Contract Boundaries\*\*", re.M)

#: 10 shipped sections + the one this PLAN adds, IN ORDER. A count alone is blind to the
#: renumbering this phase exists to perform: a list reading 1,2,3,4,5,6,7,7,8,9,10 — the
#: entry inserted at #7 with the following four left unrenumbered — has eleven matching
#: lines. The list title is "Required sections (in this order)" and the Technical Design
#: table fixes the position, so the ordinal and the heading at each index are both under test.
_EXPECTED_ORDER: tuple[str, ...] = (
    "🎯 Executive Summary",
    "📚 Prior Work",
    "🎙️ Interview Transcript",
    "📐 Architecture Decision Records",
    "🏗️ Technical Design",
    "📝 Implementation Plan",
    "🚧 Contract Boundaries",
    "🧪 Testing Strategy",
    "⚠️ Risks & Mitigation",
    "✅ Success Criteria",
    "🔍 Plan Validation",
)
_EXPECTED_SECTIONS = len(_EXPECTED_ORDER)

#: The order THIS PLAN was written to, written out LITERALLY rather than derived. A previous
#: attempt bound this name to `_EXPECTED_ORDER` — the same object — so the decoupling it claimed
#: never existed and five reviewers caught it. Extending the live contract for a 12th section
#: must not redden a landed document that legitimately predates it.
_PLAN_DOC_ORDER: tuple[str, ...] = (
    "🎯 Executive Summary",
    "📚 Prior Work",
    "🎙️ Interview Transcript",
    "📐 Architecture Decision Records",
    "🏗️ Technical Design",
    "📝 Implementation Plan",
    "🚧 Contract Boundaries",
    "🧪 Testing Strategy",
    "⚠️ Risks & Mitigation",
    "✅ Success Criteria",
    "🔍 Plan Validation",
)


def parse_required_entries(block: str) -> list[tuple[int, str]]:
    """(ordinal, heading) for each numbered entry — the free symbol both gates share."""
    return [(int(n), h.strip()) for n, h in _NUMBERED_ENTRY.findall(block)]


def _slice(text: str, start: str, end: re.Pattern[str]) -> str:
    """The region between an anchor and the next structural boundary.

    Every presence assertion in this file is scoped through here. An unscoped `in text`
    is satisfiable by a mention the phase makes ELSEWHERE — Phase 1 edits the Outputs
    line and the Quality Bar too, so a tail that reaches them lets a sibling edit turn a
    Step 6 assertion green.
    """
    assert start in text, f"anchor not found: {start!r}"
    tail = text.split(start, 1)[1]
    m = end.search(tail)
    return tail[: m.start()] if m else tail


_NEXT_H2 = re.compile(r"^## ", re.M)
_REQUIRED_ANCHOR = "**Required sections (in this order):**"
_STEP6_ANCHOR = "### Step 6"


def _required_block(text: str) -> str:
    return _slice(text, _REQUIRED_ANCHOR, re.compile(rf"^{_STEP6_ANCHOR}", re.M))


def _step6_block(text: str) -> str:
    return _slice(text, _STEP6_ANCHOR, _NEXT_H2)


def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-boundaries-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def _plan_variants() -> dict[str, str]:
    """The rendered `/hm:plan` surface, keyed by variant.

    Keyed rather than merged so a missing Codex arm is a KeyError naming the variant,
    not a silently smaller corpus that still passes every `any(...)`.
    """
    root = _render_root()
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.endswith("commands/hm/plan.md"):
            out["claude"] = path.read_text(encoding="utf-8")
        elif "skills/hm-plan/" in rel:
            out["codex"] = path.read_text(encoding="utf-8")
    return out


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_required_sections_list_names_the_section(variant: str) -> None:
    """Membership in the numbered list — not a substring anywhere in the command.

    A template that names the section in a Step 6 bullet, the Quality Bar, or an aside
    satisfies `_SECTION_HEADING in text` while the required list sits untouched at ten
    entries. That is exactly the wrong implementation Phase 1 exists to prevent.
    """
    block = _required_block(_plan_variants()[variant])
    assert _REQUIRED_ENTRY.search(block), f"{variant}: not a numbered required-list entry"
    entries = parse_required_entries(block)
    expected = list(enumerate(_EXPECTED_ORDER, start=1))
    assert entries == expected, f"{variant}: required list is {entries}"
    assert _SUBLIST_PIN in block, f"{variant}: 'Do not change' sub-list missing"


def _fake_block(pairs: list[tuple[int, str]]) -> str:
    return "\n".join(f"{n}. **{h}** — …" for n, h in pairs)


#: The two wrong implementations A.5 named. Both have ELEVEN entries, so a length check
#: accepts both; the tuple equality must reject both. This is the mutation proof that
#: discharged the A.5 gate in place of a third reviewer round — a negative case is cheaper
#: and more reviewable than a verdict, and twice today an assertion that read correctly
#: was not.
_WRONG_IMPLEMENTATIONS = {
    "duplicate-ordinal": [
        (n, h) for n, h in zip([1, 2, 3, 4, 5, 6, 7, 7, 8, 9, 10], _EXPECTED_ORDER, strict=True)
    ],
    "appended-last": [
        *enumerate([h for h in _EXPECTED_ORDER if h != "🚧 Contract Boundaries"], start=1),
        (11, "🚧 Contract Boundaries"),
    ],
}


@pytest.mark.parametrize("name", sorted(_WRONG_IMPLEMENTATIONS))
def test_parser_rejects_the_half_done_renumberings(name: str) -> None:
    """Fault-sensitivity, proved rather than asserted.

    `duplicate-ordinal` is the entry inserted at #7 with 7,8,9,10 left alone;
    `appended-last` is the entry tacked on after Plan Validation with no renumbering,
    which also moves it off the position the Technical Design table fixes. Eleven entries each.
    """
    parsed = parse_required_entries(_fake_block(_WRONG_IMPLEMENTATIONS[name]))
    assert len(parsed) == _EXPECTED_SECTIONS, "the fixture must defeat a length check"
    assert parsed != list(enumerate(_EXPECTED_ORDER, start=1)), f"{name} was accepted"


#: The grammar oracle's fault-sensitivity, independent of any document. Its only other caller
#: parses this repo's own PLAN and is retired by `_skip_if_plan_has_landed` at land, so without
#: this table the end-anchor — and `_is_repo_relative`, and the sole-bullet rule — would be
#: exercised by nothing at all after wrapup, and reverting any of them would stay green forever.
_WRONG_BULLETS = {
    "trailing-garbage": "- `src/x.py` and also whatever",
    "absolute": "- `/etc/passwd`",
    "dotdot": "- `../x.py`",
    "glob": "- `src/**/x.py`",
    "unquoted": "- src/x.py",
    "advisory-empty": "- Advisory:",
}
_RIGHT_BULLETS = {
    "file": "- `src/pkg/mod.py`",
    "dir": "- `src/pkg/`",
    "with-why": "- `src/pkg/mod.py` — the contract this task must not move",
    "hard-break": "- `src/pkg/mod.py`  ",
    "advisory": "- Advisory: keep the three-item enumeration intact",
    "none": "- none — this task has no contract boundaries",
}


def _admitted(bullet: str) -> bool:
    """One decision function, so the table and the document gate cannot drift apart."""
    m = _PATH_BULLET.match(bullet)
    if m is not None:
        return _is_repo_relative(m.group(1))
    return bool(_ADVISORY_BULLET.match(bullet) or _NONE_BULLET.match(bullet))


@pytest.mark.parametrize("name", sorted(_WRONG_BULLETS))
def test_the_grammar_rejects_non_conforming_bullets(name: str) -> None:
    assert not _admitted(_WRONG_BULLETS[name]), f"{name} was admitted: {_WRONG_BULLETS[name]!r}"


@pytest.mark.parametrize("name", sorted(_RIGHT_BULLETS))
def test_the_grammar_admits_every_published_form(name: str) -> None:
    assert _admitted(_RIGHT_BULLETS[name]), f"{name} was rejected: {_RIGHT_BULLETS[name]!r}"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_explicit_none_rule_is_stated(variant: str) -> None:
    """ADR-002 — emptiness must be WRITTEN, so absent and none are distinguishable.

    Asserts the RULE, not the word. A bare `"none" in text` passed against the unmodified
    command (Phase A.4 caught it): the word already appears for unrelated reasons, so it
    could never have gone red for the defect it names.
    """
    block = _required_block(_plan_variants()[variant])
    assert _NONE_RULE in block, f"{variant}: the explicit-`none` rule is not stated"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_entry_grammar_is_stated(variant: str) -> None:
    """ADR-008 — one grammar, and the advisory marker is named."""
    block = _required_block(_plan_variants()[variant])
    assert "Advisory:" in block, f"{variant}: the advisory marker is not named"
    assert "repo-relative" in block, f"{variant}: the path grammar is not stated"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_step6_verification_asserts_the_section(variant: str) -> None:
    block = _step6_block(_plan_variants()[variant])
    assert "Contract Boundaries" in block, f"{variant}: Step 6 does not verify the section"
    assert "non-empty" in block, f"{variant}: Step 6 does not assert sub-list non-emptiness"
    assert "admitted forms" in block, f"{variant}: Step 6 does not check the entry grammar"
    # Self-repair, never a stage halt: the grammar bullet must say so, or Step 6's
    # retry-once-then-stop rule silently claims it and /hm:plan halts on prose formatting.
    assert "self-repaired inline" in block, f"{variant}: grammar bullet's gate semantics undefined"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_outputs_section_count_matches_the_required_list(variant: str) -> None:
    """The renumbering has to reach the Outputs line, which states a count of its own.

    Asserts the ABSOLUTE count as well as agreement: a pure self-consistency check is
    satisfied by 10 == 10, so it would never notice a template that added the section
    nowhere. Both variants — a Codex-only omission is the documented half-ship.
    """
    text = _plan_variants()[variant]
    numbered = _NUMBERED_ENTRY.findall(_required_block(text))
    assert len(numbered) == _EXPECTED_SECTIONS, f"{variant}: {len(numbered)} required entries"
    outputs = _slice(text, "## Outputs", _NEXT_H2)
    stated = re.search(r"frontmatter \+ (\d+) sections above", outputs)
    assert stated is not None, f"{variant}: Outputs no longer states a section count"
    assert int(stated.group(1)) == _EXPECTED_SECTIONS, (
        f"{variant}: Outputs says {stated.group(1)}, required list has {_EXPECTED_SECTIONS}"
    )


def _git(argv: list[str]) -> subprocess.CompletedProcess[str] | None:
    """None means "could not ask" — never "the answer is no"."""
    try:
        return subprocess.run(argv, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None


def _skip_if_plan_has_landed() -> None:
    """These three gates pin ONE historical document; retire them like their sibling.

    `test_execute_contract_boundaries.py` retires its pin once the PLAN is in the merge-base.
    These did not, so a landed deliverable would stay a permanent brake on the next required-
    section change and on any rename of a path it pins. Two policies for one class of pin
    inside a single change is the second-source-of-truth shape, so they now share one.
    """
    if not _PLAN_DOC.exists():
        pytest.skip("this branch does not carry PLAN-ai-work-boundaries")
    # UNRESOLVABLE == unknown == skip, matching the sibling helper. Round 4 left the two files
    # taking opposite directions on the same condition: in a shallow clone this one bound (so a
    # landed PLAN stayed a permanent brake, the exact outcome the helper exists to remove) while
    # the sibling skipped. A retirement probe that cannot run has not established that the pin
    # should bind. Subprocess failure is the same unknown — an absent `git` should not turn a
    # probe into a test ERROR.
    for ref in ("main", "origin/main"):
        probe = _git(["git", "merge-base", "HEAD", ref])
        if probe is None or probe.returncode != 0:
            continue
        obj = f"{probe.stdout.strip()}:work-docs/PLAN-ai-work-boundaries.md"
        landed = _git(["git", "cat-file", "-e", obj])
        if landed is None:
            break
        if landed.returncode == 0:
            pytest.skip("PLAN-ai-work-boundaries is in the merge-base — it has landed")
        return
    pytest.skip("no merge-base with main or origin/main — cannot decide whether the PLAN landed")


def _boundaries_section() -> str:
    _skip_if_plan_has_landed()
    body = _PLAN_DOC.read_text(encoding="utf-8")
    m = _SECTION_RE.search(body)
    assert m is not None, "PLAN-ai-work-boundaries has no Contract Boundaries section"
    return body[m.end() :].split("\n## ", 1)[0]


def _has_content(region: str) -> bool:
    """Non-blank content that is not itself a heading.

    Accepts a table row as readily as a bullet: an author may write the list as a table
    (path / why pinned), and a bullets-only predicate would call a filled table empty.
    """
    return any(line.strip() and not line.lstrip().startswith("#") for line in region.splitlines())


def _do_not_change_bullets() -> list[str]:
    section = _boundaries_section()
    pin = section.split(f"### {_SUBLIST_PIN}", 1)
    assert len(pin) > 1, "the Do not change sub-list is missing"
    # `lstrip` because plan.md.j2 renders its own examples as an INDENTED nested list; a
    # column-0 filter cannot see them, so an indented `- none` would bypass both the grammar
    # check and the sole-bullet cardinality rule.
    return [ln.lstrip() for ln in pin[1].splitlines() if ln.lstrip().startswith("- ")]


def test_the_pinned_list_is_non_empty() -> None:
    """ADR-002 — emptiness must be WRITTEN.

    A bare `"Do not change" in section` is satisfied by a bare heading with nothing under
    it, which is the false negative the explicit-`none` rule exists to close. Non-emptiness
    is the property; heading presence is not a proxy for it.
    """
    section = _boundaries_section()
    pin = section.split(f"### {_SUBLIST_PIN}", 1)
    assert len(pin) > 1, "the Do not change sub-list is missing"
    assert _has_content(pin[1]), "the Do not change sub-list is empty — write `none` explicitly"


def test_this_plan_is_in_the_mandated_section_order() -> None:
    """The exemplar has to obey the order it publishes, or it teaches the wrong placement.

    Nothing checked position before this, and the PLAN was in fact wrong: it placed the
    section 5th, following ADR-001's prose ("beside the ADRs"), while the template mandates
    #7. Two sources of truth for one decision, and the reference instance followed the one
    the template does not implement.
    """
    _skip_if_plan_has_landed()
    body = _PLAN_DOC.read_text(encoding="utf-8")
    headings = [h.strip() for h in re.findall(r"^## (.+)$", body, re.M)]
    assert headings == list(_PLAN_DOC_ORDER), f"PLAN section order is {headings}"


def test_this_plan_satisfies_the_rule_it_introduces() -> None:
    """Self-compliance, decided by parsing rather than by reading (ADR-008)."""
    bullets = _do_not_change_bullets()
    assert bullets, "the Do not change sub-list is empty — write `none` explicitly"
    if len(bullets) == 1 and _NONE_BULLET.match(bullets[0]):
        return  # form (c): the author asserted there are none — nothing further to check
    for bullet in bullets:
        path_hit = _PATH_BULLET.match(bullet)
        assert path_hit or _ADVISORY_BULLET.match(bullet), (
            f"none of the three admitted forms — {bullet[:80]!r}"
        )
        if path_hit:
            candidate = path_hit.group(1)
            assert _is_repo_relative(candidate), f"not repo-relative: {candidate!r}"
            # No `.exists()` check. The published grammar states repo-relative and nothing more,
            # and this PLAN pins paths that a later refactor may legitimately rename — an
            # existence assertion would turn a landed document into a permanent brake on them.
