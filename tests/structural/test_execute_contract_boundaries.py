"""Phase 2 of PLAN-ai-work-boundaries — execute loads, cites and checks the boundaries.

The positives prove the instruction shipped in both variants; the negatives are the reason this
file exists rather than a grep. Counting them here would be a second source of truth, so each is
named by role below instead.

**Placement is the load-bearing positive.** ADR-003 puts the load at Step 1, not at Phase C.0,
because C.0's trigger is defect-repair only ("Pure new-feature work skips this") — hanging the
contract off C.0 would leave every new-feature task unconstrained while the section claims to
constrain "the implementation". A test that merely finds the words anywhere cannot tell those
two designs apart, so the Step 1 assertion is scoped to Step 1's own block.

**The scoped negatives** enforce ADR-003's report-not-gate invariant. They read ONLY the
paragraphs this change introduces — the rendered execute command legitimately contains many
unrelated failure and stop instructions, so an unscoped search for `fail the stage` would be red
for reasons that have nothing to do with this PLAN. The invariant is a property of the whole
feature, so it is asserted at **all three** sites the change touches: the anchored Step 4 region,
the Phase C.0 block, and the Step 1 boundary paragraph. That last one is sliced from the
paragraph's own first line rather than taken as the whole Step 1 block, because Step 1's
pre-existing missing-PLAN guard legitimately carries `exit 1`.

**The review-untouched negative** pins ADR-004's scope cut with a predicate rather than a
phrase. `surface_baseline.json` is a ratchet that permits shrink, not an equality pin, and no
rendered-review snapshot exists in the tree, so "unchanged from baseline" was not a check that
could be written; `git diff --quiet` against the merge-base is.

**Phase A.4 justified pass — `test_review_surface_is_untouched_by_this_plan`.** GREEN before
the template change, and legitimately so: it is a NEGATIVE invariant on a scope boundary. It is
vacuously true while no review-side edit exists, and it goes red the instant one appears. It has
no construct-forcing RED sibling by design — nothing in this PLAN should ever make it fail, and
a sibling that forced a review edit into existence would be the violation itself. Recorded here
because A.4 forbids carrying an unexplained pass into A.5.
"""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_REPO_ROOT = Path(__file__).parents[2]

#: The anchor the Phase 2 paragraphs carry, so the negative assertion reads them and nothing
#: else. A comment rather than a heading: it must survive in both variants and must not add a
#: numbered step to a command whose step numbering is asserted elsewhere.
_ANCHOR_OPEN = "<!-- @hm:boundaries -->"
_ANCHOR_CLOSE = "<!-- @hm:/boundaries -->"

#: ADR-009's concrete emitted line. A bare `"predates" in block` is satisfied equally by this
#: line and by "a PLAN that predates the section is treated as `none`" — the absent-case black
#: hole the ADR exists to close (failures.md count:8). The literal decides; the token cannot.
_ABSENT_LINE = "[boundaries] PLAN predates the contract-boundaries section — none loaded"

#: The two shipped sentences Phase 2 falsifies and therefore rewrites (ADR-003). Pinned as
#: ABSENCES: an additive-only citation clause leaves both in place, one paragraph above the
#: clause that contradicts them.
_FALSIFIED = (
    "**Declare all three; do not look any of them up.**",
    "Nothing verifies afterwards that you respected what you declared",
)

#: ADR-003's specified sentence, asserted POSITIVELY. Inferring "does this gate?" from tokens
#: failed twice: a flat token list made the correct wording red (round 1), and a per-line
#: negation heuristic then both excused a real gate carrying `cannot` and mis-fired when the
#: hard-wrapped template split the negator from its token across lines (round 2). A specified
#: sentence has no such failure mode — you assert the thing itself.
_ADR003_SENTENCE = "reported, never auto-reverted, and never fail the stage"

#: The only unconditional negatives left: imperative forms that no correct negation contains.
#: `stop` stays out — a report line may legitimately say "continue" — but the rest are matched
#: by REGEX, not substring. The round-4 token list was `("exit 1", "BLOCKED")`, and neither of
#: the two wrong implementations its own comment named could trip it: "the stage exits 1" does
#: not contain "exit 1", and "files a blocker" does not contain "BLOCKED". A negative nothing
#: can redden reports an invariant as enforced while enforcing nothing.
_ALWAYS_GATE = (
    re.compile(r"\bexits?\s+1\b"),
    re.compile(r"\bBLOCKED\b"),
    re.compile(r"\bblocker\b", re.I),
    re.compile(r"\bhalts?\s+the\s+stage\b", re.I),
)

#: Rejection, proved rather than asserted — the same move `_WRONG_IMPLEMENTATIONS` makes in the
#: sibling file. Each is a gating rewrite of a real boundary paragraph; every one of them passed
#: the round-4 token list.
_GATING_REWRITES = (
    "a crossing files a blocker and the stage exits 1",
    "a crossing is BLOCKED until the human clears it",
    "if the list is unparseable, this halts the stage",
)


def _gates(flat: str) -> bool:
    return any(p.search(flat) for p in _ALWAYS_GATE)


def _flat(text: str) -> str:
    """Whitespace-normalised, so a hard wrap cannot decide whether an assertion holds."""
    return " ".join(text.split())


_REVIEW_UNTOUCHED = (
    "src/harness_maker/templates/stages/review.md.j2",
    "src/harness_maker/review_consensus.py",
)


def _render_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-exec-boundaries-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def _execute_variants() -> dict[str, str]:
    root = _render_root()
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.endswith("commands/hm/execute.md"):
            out["claude"] = path.read_text(encoding="utf-8")
        elif "skills/hm-execute/" in rel:
            out["codex"] = path.read_text(encoding="utf-8")
    return out


def _block(text: str, start: str, end: re.Pattern[str]) -> str:
    assert start in text, f"anchor not found: {start!r}"
    tail = text.split(start, 1)[1]
    m = end.search(tail)
    return tail[: m.start()] if m else tail


def _step1_block(text: str) -> str:
    return _block(text, "### Step 1 — Load PLAN", re.compile(r"^### Step 1\.5", re.M))


def _step4_block(text: str) -> str:
    return _block(text, "### Step 4 — Stage exit", re.compile(r"^### Step 4\.5", re.M))


def _phase_c0_block(text: str) -> str:
    return _block(text, "#### Phase C.0", re.compile(r"^#### Phase C —", re.M))


def _step1_boundary_paragraph(text: str) -> str:
    """Step 1's boundary bullet ONLY — never the whole Step 1 block.

    Step 1 opens with a pre-existing missing-PLAN guard that legitimately carries `exit 1`, so
    running the report-not-gate negative over the whole block would be red for a rule this
    change never touched. The paragraph starts at its own first line.
    """
    block = _step1_block(text)
    assert "`## 🚧 Contract Boundaries`" in block, "Step 1 lost its boundary paragraph"
    tail = block.split("`## 🚧 Contract Boundaries`", 1)[1]
    end = re.search(r"\n[ \t]*\n", tail)
    # Loud, not silent: `_block` returns the WHOLE tail when its end pattern misses, which would
    # quietly turn this paragraph slicer into a rest-of-Step-1 slicer. The round-4 pattern was
    # `^\n\n` under re.M — that needs THREE consecutive newlines, and it matched only because
    # `trim_blocks=False` happens to emit a stray blank line at the neighbouring `is_codex` tag.
    assert end is not None, "Step 1 boundary paragraph has no terminating blank line"
    return tail[: end.start()]


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_step1_loads_the_do_not_change_list(variant: str) -> None:
    """ADR-003 — the load sits on the path EVERY invocation takes, not the repair path."""
    block = _flat(_step1_block(_execute_variants()[variant]))
    assert "Do not change" in block, f"{variant}: Step 1 does not load the Do-not-change list"
    # The noun alone is satisfied by a POINTER — "the Do not change list is handled at C.0" —
    # which is exactly the design ADR-003 rejected. Assert the imperative that makes the load
    # happen here.
    assert "Restate it once" in block, f"{variant}: Step 1 points at the list without loading it"
    flat = block
    # The two decisions that make the loaded data usable. Unpinned, a trim ships an execute
    # stage that consumes the `none` sentinel as a path prefix — the absent-case class ADR-009
    # exists to close, one instruction earlier.
    assert "never a prefix" in flat, f"{variant}: Step 1 lets the `none` sentinel act as a prefix"
    # The CONTIGUOUS clause. Two independent memberships over a ~1kB block is conjunction, not
    # adjacency: "an `Advisory:` line is informational" in one sentence plus "honor the ADRs" in
    # another satisfied both — the precise counterexample the round-4 comment described.
    assert "an `Advisory:` line is a constraint you **honor**" in flat, (
        f"{variant}: Step 1 leaves Advisory entries non-actionable"
    )
    assert "unparseable" in flat, f"{variant}: Step 1 has no branch for a malformed list"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_phase_c0_cites_the_loaded_list(variant: str) -> None:
    """The IMPERATIVE, not the noun — the C.0 block carries `Do not change` twice.

    The second copy is the pre-existing "what checks it afterwards" sentence, which no edit to
    the citation clause can remove. So `"Do not change" in block` was discharged by text this
    test was not written for: softening the imperative to an optional mention left it green,
    and C.0's real coverage came from an unrelated reflow pin on `re-Read`.
    """
    flat = _flat(_phase_c0_block(_execute_variants()[variant]))
    assert "cite the `Do not change` list loaded at Step 1" in flat, (
        f"{variant}: Phase C.0 does not INSTRUCT the citation"
    )


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_falsified_sentences_are_gone(variant: str) -> None:
    """ADR-003 rewrites them; an additive-only edit leaves a self-contradiction shipping.

    'do not look any of them up' one paragraph above 'cite the list loaded at Step 1' is R10
    unmitigated, in the most-invoked stage in the harness.
    """
    block = _phase_c0_block(_execute_variants()[variant])
    for sentence in _FALSIFIED:
        assert sentence not in _flat(block), (
            f"{variant}: falsified sentence survives — {sentence!r}"
        )
    # Absence alone accepts DELETION, and Phase 2 asks for replacement: the `:408` half must
    # still say what stage exit compares, or C.0 goes silent about it in the most-invoked
    # stage. A negative pin cannot tell removal from rewrite; this positive one can.
    flat = _flat(block)
    assert "stage exit" in flat, f"{variant}: C.0 no longer states what stage exit compares"
    assert "Do not change" in flat, f"{variant}: C.0's corrected statement lost the list"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_c0_enumeration_is_still_three_items(variant: str) -> None:
    """Scope-out: the rewrite touches the rationale, never the enumeration.

    Those three items are PLAN-self-induced-regression-gate ADR-002's, and losing one to a
    rewrite is the silent way this change would break a decision it promised to preserve.
    """
    block = _phase_c0_block(_execute_variants()[variant])
    items = re.findall(r"^\d+\. \*\*", block, re.M)
    assert len(items) == 3, f"{variant}: C.0 enumeration has {len(items)} items, expected 3"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_step4_compares_against_the_list(variant: str) -> None:
    block = _step4_block(_execute_variants()[variant])
    flat = _flat(block)
    assert "Do not change" in flat, f"{variant}: stage exit does not compare against the list"
    # The noun alone is satisfied by a pointer. Pin the three decisions the paragraph carries.
    assert "the same set item 1 inspects" in flat, f"{variant}: Step 4 operand is not item 1's set"
    assert "crossing" in flat, f"{variant}: Step 4 never names a crossing"
    # The DISTINCTION, not one sentence's phrasing. This pinned "the section was absent"
    # verbatim and went red when the branch list was tightened to "absent (unknown), an explicit
    # `none`, …" — a rewrite that preserves the distinction exactly. A pin that reddens on a
    # correct edit is the one that gets deleted next time; assert both poles instead.
    assert "absent" in flat, f"{variant}: Step 4 drops the absent case"
    assert "explicit `none`" in flat, f"{variant}: Step 4 collapses absent-vs-none"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_absent_section_is_distinguished_from_none(variant: str) -> None:
    """ADR-009 — a PLAN predating the section must not read as 'no boundaries'."""
    block = _flat(_step1_block(_execute_variants()[variant]))
    assert _ABSENT_LINE in block, f"{variant}: ADR-009's emitted line is not stated verbatim"


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_round2_prose_repairs_are_pinned(variant: str) -> None:
    """Each round-2 repair is ONE sentence in a hard-wrapped, budget-squeezed template.

    Unpinned, the next reflow or trim deletes it with every gate green — which is exactly how
    `, with or without TDD` was lost in the first place. These assertions exist so that class
    of silent removal costs a red test.
    """
    text = _execute_variants()[variant]
    c0 = _flat(_phase_c0_block(text))
    assert "with or without TDD" in c0, f"{variant}: C.0 lost its --no-tdd anchor again"
    assert "re-Read" in c0, f"{variant}: C.0 has no recovery branch when the list is unavailable"
    step4 = _flat(_step4_block(text))
    assert "comparison not performed" in step4, f"{variant}: Step 4 can report a partial silently"
    assert "renamed or deleted" in step4, f"{variant}: Step 4's operand excludes delete/rename"
    # The blocked path is where edits exist and no comparison runs; C.0 cannot carry this
    # because pure new-feature work skips C.0 entirely. Scoped to the Step 4 block and pinned on
    # the emitted literal: a whole-document `"blocked exit" in text` was discharged by a stray
    # copy of the phrase in C.0, so deleting the blocked-path item left the suite green.
    assert "comparison not performed — blocked exit" in step4, (
        f"{variant}: the blocked path's disclosure is not in the Step 4 block"
    )


@pytest.mark.parametrize("variant", ["claude", "codex"])
def test_the_new_paragraphs_do_not_gate_the_stage(variant: str) -> None:
    """ADR-003's report-not-gate invariant, asserted rather than described.

    Scoped to the anchored paragraphs: the rendered command is full of legitimate failure
    instructions belonging to other steps, and an unscoped search would fail on those.
    """
    text = _execute_variants()[variant]
    assert _ANCHOR_OPEN in text, f"{variant}: opening anchor missing"
    assert _ANCHOR_CLOSE in text, f"{variant}: closing anchor missing"
    regions = [c.split(_ANCHOR_CLOSE, 1)[0] for c in text.split(_ANCHOR_OPEN)[1:]]
    assert len(regions) >= 1, f"{variant}: no anchored boundary region"
    # EVERY region states the invariant. Round 2 weakened this to `any()`, which let a second
    # region be inverted while borrowing the first region's copy of the sentence. `every` is what
    # makes that impossible, and it is asserted regardless of how many regions exist — do not
    # weaken it on the argument that there is currently only one. `stop` is deliberately not in
    # _ALWAYS_GATE: a report line may legitimately say "continue".
    for region in regions:
        flat = _flat(region)
        assert _ADR003_SENTENCE in flat, (
            f"{variant}: a boundary paragraph omits ADR-003's report-not-gate invariant"
        )
        assert not _gates(flat), f"{variant}: an anchored boundary paragraph gates the stage"

    # The other two sites this change touches. The anchors wrap only the Step 4 paragraph, so a
    # gating rewrite at C.0 or at the Step 1 load passed every assertion above. ADR-003's
    # invariant is a property of the feature, not of one paragraph.
    for site, block in (
        ("Phase C.0", _phase_c0_block(text)),
        ("Step 1 boundary paragraph", _step1_boundary_paragraph(text)),
    ):
        assert not _gates(_flat(block)), f"{variant}: {site} gates the stage"


def test_the_gate_predicate_rejects_real_gating_rewrites() -> None:
    """Fault-sensitivity for the negative above, which is otherwise unfalsifiable.

    A negative assertion over prose is green when the rule holds AND when the predicate is
    broken, and those look identical from a passing suite. These three are the rewrites the
    round-4 token list accepted, so this is the regression test for that gate itself.
    """
    for rewrite in _GATING_REWRITES:
        assert _gates(_flat(rewrite)), f"the gate predicate accepts a gating rewrite: {rewrite!r}"
    # ...and does not fire on the CORRECT wording, or the pin becomes unsatisfiable.
    assert not _gates(_flat(_ADR003_SENTENCE)), "the predicate reddens ADR-003's own sentence"


def test_review_surface_is_untouched_by_this_plan() -> None:
    """ADR-004 cut review-side consumption; pinned so a later edit cannot reintroduce it."""
    # LOCAL `main` first, `origin/main` as the fallback — the ordering `_comprehension_golden`
    # and `_surface_baseline` use. `task-land` squash-lands onto local `main` while pushing to
    # `origin` is manual, so `origin/main` lags by however many tasks have landed since the last
    # push; merge-base against the lagging ref reaches BACK past the fork point and blames this
    # PLAN for a peer's landed edits. A bare `main` simply fails to resolve in a CI checkout,
    # and the loop falls through — which is why local-first still fixes the green-by-skip.
    base = None
    for ref in ("main", "origin/main"):
        probe = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if probe.returncode == 0:
            base = probe
            break
    if base is None:  # neither ref resolves — say so, do not pass silently
        pytest.skip("no merge-base with main or origin/main in this checkout")

    # Retire when the PLAN is IN THE MERGE-BASE — i.e. it has landed. Two earlier predicates
    # were wrong in opposite directions: keying on `status: planning` retired at wrapup's Step 4,
    # one step BEFORE the landing commit; keying on the file's absence never retired at all,
    # because wrapup commits PLAN docs and 123 landed ones sit in `work-docs/` today. Presence
    # in the merge-base is the fact that actually changes at land: on this branch the PLAN
    # exists in the tree and NOT in base, so the pin binds; on any later branch it is in base,
    # so the pin is gone and cannot blame this PLAN for someone else's review-surface edit.
    # BRANCH MEMBERSHIP. A peer `hm/<slug>` branch forked
    # before this PLAN lands has it in neither the tree nor the base, so the retirement probe
    # below leaves the pin ARMED and the peer's own legitimate review-surface edit fails with a
    # message about a PLAN it never touched. The pin is this branch's, so it binds only where
    # the PLAN is.
    if not (_REPO_ROOT / "work-docs" / "PLAN-ai-work-boundaries.md").exists():
        pytest.skip("this branch does not carry PLAN-ai-work-boundaries — pin does not apply")

    landed = subprocess.run(
        ["git", "cat-file", "-e", f"{base.stdout.strip()}:work-docs/PLAN-ai-work-boundaries.md"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if landed.returncode == 0:
        pytest.skip("PLAN-ai-work-boundaries is in the merge-base — it has landed, pin retired")
    # `git diff --quiet <commit> -- nosuchpath` exits 0 with no diagnostic, so a typo or a
    # rename would silently reduce this pin to checking nothing while staying green.
    for pinned in _REVIEW_UNTOUCHED:
        assert (_REPO_ROOT / pinned).exists(), f"pin operand no longer names a file: {pinned}"
    diff = subprocess.run(
        ["git", "diff", "--quiet", base.stdout.strip(), "--", *_REVIEW_UNTOUCHED],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert diff.returncode == 0, (
        "ADR-004 cut review-side consumption from this PLAN, but the review surface moved: "
        f"{', '.join(_REVIEW_UNTOUCHED)}"
    )
