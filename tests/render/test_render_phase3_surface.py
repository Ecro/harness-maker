"""Phase 3 of PLAN-self-induced-regression-gate — what the two stage templates must render.

Six things land here, and each has a reason the assertion is shaped the way it is:

* **ADR-002** — a three-line declaration before Phase C. Asserted by CONTENT, not by a marker,
  because the failure mode is wording that turns a declaration back into a lookup ("re-confirm
  the SPEC's Non-Goals"), which reintroduces the absent case that killed revision 1.
* **ADR-008 (revised)** — **neither stage touches the verification cache at all.** The original
  decision was a `check` in both with no `mark-pass` in either: `is_fresh` never compares check
  sets, so a `mark-pass` after a TARGETED run stamps a full-run marker that lets `verify` and
  `wrapup` skip the whole suite. But a consumer with no producer cannot hit — both stages change
  files before the read, so `check` returns 1 on essentially every call — and a read whose answer
  is fixed is surface with no behaviour. Review found this and the read was removed. Only a
  negative assertion holds a negative decision, so what remains is the negative one.
* **ADR-006 follow-through** — Phase D's full-mode paragraph must stop naming the four config
  shapes, which no longer produce `mode: full`.
* **ADR-010** — exactly ONE `test-reviewer` dispatch in Phase A.5, carrying all three lens
  questions.
* **ADR-003** — `review_run open` once, `close` on every terminal branch, and no surviving
  instruction to mint a `<run-id>`.
* **the Phase D pointer** — Phase D must name `targeted-test-selection`, the way the auto-fix
  loop already does. Not a new policy; the skill owns it.

**Phase A.4 — six of these pass against the unedited templates, and both groups are negative
invariants with RED positive siblings:**

* `test_the_stage_does_not_touch_the_verification_cache` (4 cases) forbids both halves. It
  passed against the unedited templates too, and it goes red the moment either half is added
  back — the producer, which a first revision of the PLAN did add and which `is_fresh` makes
  unsafe, or the producer-less consumer this task shipped and then removed.
* `test_the_single_a5_dispatch_still_asks_all_three_lens_questions` (2 cases) passes because the
  three lens names occur inside the A.5 section. **An earlier draft of this note said they come
  from the dispatch table, and that was wrong** — they also appear in the retry-scope prose, so
  the first version of this test scanned the whole body and stayed green even when the two extra
  dispatches AND their lens lines were deleted. It is now scoped to the A.5 block. Its sibling
  `test_phase_a5_dispatches_exactly_one_test_reviewer` is RED.

Every assertion here that looks for a substring is scoped to a bounded window for that reason.
The first A.5 round on this file returned five blocking issues and all five were the same
defect: a body-wide substring satisfied by prose the implementation never touches.

`close`'s contract is asserted as an ENUMERATION rather than a call count. Counting occurrences
of a recipe scattered through prose is brittle against any rewording, and the defect this guards
is not "too few calls" but "the wrong branches" — two review findings each named a different set
and neither matched the template. The enumeration is the artefact a reader and the stage both
act on, so it is the thing to pin.
"""

from __future__ import annotations

import re
import tempfile
from functools import cache
from pathlib import Path

import pytest

from harness_maker.models import (
    DevMode,
    InstrumentationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref

_ALL_TARGETS = (Target.CLAUDE_CODE, Target.CODEX)


@cache
def _surfaces(ledger: bool = False) -> dict[str, str]:
    """Both variants of both stages, keyed `claude:<stage>` / `codex:<stage>`.

    Codex is rendered too because the two variants branch on `is_codex` and this repo has
    already shipped a defect where every Codex file was rendered with the flag hardcoded false
    — a template that reads correctly while the output takes the other arm.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(
                        preset=Preset.PRODUCTION,
                        targets=list(_ALL_TARGETS),
                        dev_mode=DevMode.TASK_DRIVEN,
                        worktree={"enabled": True},
                        instrumentation=InstrumentationConfig(stage_agent_ledger=ledger),
                    ),
                ),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        out: dict[str, str] = {}
        for stage in ("execute", "review"):
            claude = root / ".claude" / "commands" / "hm" / f"{stage}.md"
            assert claude.is_file(), f"missing {claude}"
            out[f"claude:{stage}"] = claude.read_text(encoding="utf-8")
            codex = root / ".agents" / "skills" / f"hm-{stage}" / "SKILL.md"
            assert codex.is_file(), f"missing {codex}"
            out[f"codex:{stage}"] = codex.read_text(encoding="utf-8")
        return out


def _body(key: str, ledger: bool = False) -> str:
    return _surfaces(ledger)[key]


#: The two dispatch forms the renderer emits — `Task(subagent_type=…)` for Claude,
#: `spawn_agent(agent_type=…)` for Codex. Anchoring on the bare name `test-reviewer` instead
#: lands on a PROSE mention ("Phase A.5 (test-reviewer gate)") 9 lines into the document, and a
#: fence taken around that is an unrelated block — an assertion red for the wrong reason, which
#: a falsifiability probe alone reports as healthy.
_DISPATCH_LINE = re.compile(r'^.*(?:subagent_type|agent_type)="test-reviewer".*$', re.M)


def _dispatch_lines(body: str) -> list[str]:
    lines = _DISPATCH_LINE.findall(body)
    assert lines, "no `test-reviewer` dispatch line in the rendered stage"
    return lines


def _window(body: str, anchor: str, span: int = 1800) -> str:
    """A bounded slice around `anchor`.

    Every blocking issue this file's first A.5 round returned was the same defect: an assertion
    scoped to the WHOLE rendered body, satisfied by prose the implementation never touches. A
    substring test is only as strong as the region it looks in.
    """
    i = body.find(anchor)
    assert i != -1, f"anchor not found: {anchor!r}"
    return body[i : i + span]


VARIANTS = ("claude", "codex")


# ── ADR-002: the pre-repair declaration ──────────────────────────────────────


def _declaration_block(body: str) -> str:
    """The declaration's own text, bounded by the headings around it.

    Every assertion about the declaration is scoped through here. Character windows were used
    before and both failure modes showed up: a `.{0,1200}` window ran past the block into Phase C,
    and a `hypothesis.{0,600}scope` window coupled the assertion to the ORDER of the items and to
    the LENGTH of the prose between them — a faithful implementation that reorders them, or that
    words the middle item 60 characters longer, goes RED. An assertion red under a correct
    implementation drives a wrong edit, which is the defect class this whole file is about.

    Returned in the template's own case — `test_the_pre_repair_block_avoids_the_two_collided_words`
    needs to tell `Hypothesis` from `hypothesis`.
    """
    lowered = body.lower()
    start = lowered.find("state three things")
    end = lowered.find("#### phase c", start)
    assert start != -1, "the declaration's opening line is gone"
    assert end > start, "the declaration is not bounded by Phase C"
    return body[start:end]


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_pre_repair_block_declares_all_three_items(variant: str) -> None:
    """Presence of all three inside the block — not their order, not their spacing."""
    block = _declaration_block(_body(f"{variant}:execute")).lower()
    assert "root-cause hypothesis" in block, "the one genuinely new item is missing"
    assert "non-goal" in block, "the scope brake ADR-002 restored in round 6 is missing"
    assert "scope" in block, "the declaration does not name the repair's scope"


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_pre_repair_block_declares_rather_than_dereferences(variant: str) -> None:
    """The absent case belongs to the REFERENCE, not the content. Revision 1 pointed at the
    SPEC's Non-Goals and the properties Phase A's tests pin; a task-driven PLAN has no SPEC and
    `--no-tdd` has no Phase A, so two thirds of the block had no referent. Wording that
    reintroduces the lookup reintroduces the hole."""
    text = _declaration_block(_body(f"{variant}:execute")).lower()
    for banned in ("spec's non-goals", "spec's `## 🚫 non-goals`", "phase a's tests pin"):
        assert banned not in text, (
            f"the declaration dereferences an artefact that may be absent: {banned!r}"
        )


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_pre_repair_block_avoids_the_two_collided_words(variant: str) -> None:
    """`Hypothesis` is the Python property-testing library in this same stage, and `invariant`
    already means a metamorphic relation here. The declaration must not add a second sense."""
    text = _declaration_block(_body(f"{variant}:execute"))
    assert not re.search(r"(?<!root-cause )\bHypothesis\b", text), (
        "bare `Hypothesis` collides with the property-testing library named in Phase A"
    )
    assert "invariant" not in text.lower(), (
        "`invariant` already denotes a metamorphic relation in this stage"
    )


# ── ADR-008 (revised): neither stage touches the verification cache ──────────


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("stage", ["execute", "review"])
def test_the_stage_does_not_touch_the_verification_cache(variant: str, stage: str) -> None:
    """ADR-008 originally put a `check` in both stages with **no** `mark-pass` in either, because
    `is_fresh` returns on `passed` alone and never compares the recorded `checks` against the
    requested ones — a `mark-pass` after a TARGETED run stamps the key a FULL run would, and the
    next `verify`/`wrapup` skips the whole suite on it. Removing the producer left a consumer that
    cannot hit: both stages change files before they reach the read, so the fingerprint has always
    moved and `check` returns 1 on essentially every call. A read whose answer is fixed is surface
    with no behaviour behind it, so the read is gone too.

    `verify`, `wrapup` and the `verify-before-completion` skill keep the cache — they hold BOTH
    halves, so theirs can actually hit. This asserts only that these two stages stay out of it;
    re-adding a read here without a producer is the regression."""
    body = _body(f"{variant}:{stage}")
    assert "verification_cache" not in body, (
        f"{stage} touches the verification cache. A read here cannot hit (the fingerprint always "
        "moved) and a write here would poison `verify`/`wrapup` — see this test's docstring"
    )


# ── ADR-006 follow-through: the full-mode paragraph ──────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_phase_d_no_longer_names_the_config_shapes_as_full_mode_triggers(variant: str) -> None:
    """After Phase 1 none of the four produces `mode: full`. Leaving the list makes the prompt
    describe a selector that no longer exists, on the exact class ADR-006 changed."""
    body = _body(f"{variant}:execute")
    para = re.search(r"`mode: full`.{0,700}", body, re.S)
    assert para is not None, "the Phase D full-mode paragraph is gone entirely"
    text = para.group(0)
    for shape in ("pyproject.toml", "uv.lock", "harness.yaml", "CI workflow"):
        assert shape not in text, f"the full-mode paragraph still names {shape}"


@pytest.mark.parametrize("variant", VARIANTS)
def test_phase_d_points_at_the_targeted_test_selection_skill(variant: str) -> None:
    """The stage's two verification paths disagreed by omission: the auto-fix loop names the
    skill, Phase D wrote its own command shape and named nothing — no `rerun_failed`, no
    parallel flag, no `test_runners plan`."""
    body = _body(f"{variant}:execute")
    start = body.find("Phase D — Post-GREEN verification")
    assert start != -1, "no Phase D heading"
    end = body.find("Phase D.5", start)
    block = body[start : end if end != -1 else len(body)]
    assert "targeted-test-selection" in block, "Phase D does not name the skill that owns this"


# ── ADR-010: one A.5 dispatch, three questions ───────────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_phase_a5_dispatches_exactly_one_test_reviewer(variant: str) -> None:
    body = _body(f"{variant}:execute")
    dispatches = len(_dispatch_lines(body))
    assert dispatches == 1, f"expected one test-reviewer dispatch, found {dispatches}"


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_single_a5_dispatch_still_asks_all_three_lens_questions(variant: str) -> None:
    """Collapsing the fan-out drops the three contexts, not the three questions. The round that
    measured this found six blocking issues and all six were solo finds."""
    body = _body(f"{variant}:execute")
    dispatched = "\n".join(_dispatch_lines(body)).lower()
    for lens in ("red-correctness", "discrimination", "coverage"):
        assert lens in dispatched, (
            f"the A.5 dispatch no longer asks about {lens}. Scoped to the dispatch LINES, not to "
            "the section or a fence around a prose mention: the section carries retry-scope prose "
            "naming every lens, which kept this assertion green through a collapse that dropped "
            "all three."
        )


# ── ADR-003: run identity in the review stage ────────────────────────────────


@pytest.mark.parametrize("ledger", [False, True])
def test_review_opens_a_run_once(ledger: bool) -> None:
    """Both ledger configs. The two-`open` defect — one inside the
    `instrumentation.stage_agent_ledger` conditional and one outside — renders exactly ONE
    occurrence with the ledger off, so counting only there is counting in the render the defect
    hides from."""
    for variant in VARIANTS:
        body = _body(f"{variant}:review", ledger=ledger)
        assert "review_run open" in body, f"{variant}: review never opens a run"
        calls = body.count("review_run open")
        assert calls == 1, (
            f"{variant}: `review_run open` renders {calls} times. Two calls mint two ids in one "
            "review and split `.hm-lens-results/<slug>/<run-id>/` across them — the same end "
            "state as the minting instruction this PLAN removes"
        )


def test_review_no_longer_tells_the_model_to_mint_a_run_id() -> None:
    """`<run-id>` is now read from `open`. A surviving minting instruction is the bypass.

    Anchored on `fresh utc` — the distinctive half — after stripping the line wrap and the
    blockquote marker. Phase A.4 caught this assertion three times: the naive substring missed
    the wrap, whitespace-only normalisation left `utc > stamp`, and the guessed noun was
    "timestamp" when the template says "stamp". Each version read as a guard and detected
    nothing. The lesson is the cheap one — read the rendered text before asserting on it.

    Rendered with the ledger **ON**, because that is the only config the sentence appears in at
    all: it sits inside the `instrumentation.stage_agent_ledger` conditional. Asserting it in
    the default (ledger-off) render is vacuous — the phrase count there is zero while `<run-id>`
    still appears 19 times, which is its own defect and has its own test below.
    """
    for variant in VARIANTS:
        raw = _body(f"{variant}:review", ledger=True).lower()
        body = re.sub(r"\s+", " ", re.sub(r"^\s*>+", " ", raw, flags=re.M))
        assert "fresh utc" not in body, f"{variant}: the run-id minting instruction survived"


def test_review_enumerates_every_terminal_branch_that_must_close() -> None:
    """Asserted as an enumeration, not a call count: two review findings each named a different
    terminal set and neither matched the template. The four APPROVE-side Grade Gate exits are
    NOT terminal — the Confirmation Pass gates itself on "only when the gate would APPROVE", so
    closing there releases the slug while C1-C3 still use the id."""
    for variant in VARIANTS:
        body = _body(f"{variant}:review")
        assert "review_run close" in body, f"{variant}: review never closes a run"
        # Anchored on the recipe, not on the whole body: those four tokens already occur 24
        # times in the unedited template — three of them in ONE pre-existing sentence — so an
        # unanchored assertion is satisfied by prose the implementation never touches, and a
        # `close` rendered on the APPROVE-side exit would pass it.
        # Each branch paired to SOME close, not all four to one window. `:867-868` is one
        # pre-existing sentence carrying three of the four tokens, so a single close rendered
        # anywhere before it satisfied a one-window form with nothing enumerated.
        lowered = body.lower()
        closes = [m for m in range(len(lowered)) if lowered.startswith("review_run close", m)]
        assert closes, f"{variant}: review never closes a run"
        # Well-formedness, on the close's OWN line. A bare token match shipped four recipes
        # missing `--slug`/`--run-id`, both of which `review_run.main` requires -- argparse
        # exits, `main` returns 2, and the state file is never unlinked. The presence of the
        # verb says nothing about whether the verb can run.
        for c in closes:
            line = lowered[lowered.rfind("\n", 0, c) + 1 : lowered.find("\n", c)]
            missing_flags = [f for f in ("--slug", "--run-id") if f not in line]
            assert not missing_flags, (
                f"{variant}: a `review_run close` renders without {missing_flags}: "
                f"{line.strip()!r}. Both are required; the command exits 2 and the run stays open"
            )
        # Ownership, not proximity. A +/-400 window let ONE close in a pre-existing sentence
        # ("stopping for `max_review_rounds`, for the no-progress invariant, or with `auto_fix`
        # disabled") satisfy three branches at once -- the assertion passed with zero closes on
        # any Grade Gate branch. Each close is attributed to the nearest branch identifier ABOVE
        # it, so one close can own at most one branch and the enumeration is real.
        branches = ("no-progress", "max_review_rounds", "auto_fix", "step c3")
        owned = set()
        for c in closes:
            above = [(lowered.rfind(b, 0, c), b) for b in branches]
            pos, branch = max(above)
            if pos != -1:
                owned.add(branch)
        missing = [b for b in branches if b not in owned]
        assert not missing, (
            f"{variant}: no `review_run close` sits ON the {missing!r} branch(es). The contract "
            "is a close on each terminal branch, not four names in one neighbourhood"
        )
        # The APPROVE-side exclusion is a property of the Grade Gate's approve ARM, not of a
        # span around the closes. A span form was RED for the CORRECT implementation too: PLAN
        # item 6 puts the first close at the `auto_fix disabled` exit, ~120 chars below
        # `STOP. Proceed to wrapup.`, so a +/-400 window around it always contained forbidden
        # prose the PLAN requires to stay. An assertion red under the mutant AND under the
        # intended implementation reads as falsifiable and drives a wrong edit.
        # `if grade ≥` rather than `if grade`: the bare phrase is generic enough that any future
        # prose using it ABOVE the real arm silently widens the excluded span, and a widened
        # exclusion fails open — it stops looking exactly where the defect would be.
        arm_start = lowered.find("if grade ≥")
        arm_end = lowered.find("if auto_fix disabled")
        assert arm_start != -1, f"{variant}: no Grade Gate approve-side arm"
        assert arm_end > arm_start, f"{variant}: the approve-side arm has no lower bound"
        assert "review_run close" not in lowered[arm_start:arm_end], (
            f"{variant}: a close renders inside the Grade Gate's APPROVE-side arm. The "
            "Confirmation Pass is gated on 'only when the gate would APPROVE', so closing there "
            "releases the slug while C1-C3 still use the id and lets the next invocation mint a "
            "fresh id mid-review. (`close` is idempotent — a double close is not one of the harms)"
        )
        # The OTHER non-terminal arm, and the one where releasing hurts most. C3's `confirm-1`
        # arm enters a repair round and dispatches confirm-2, so it is mid-pass, not an exit —
        # but the sentence above the block used to say "every arm below is stage-terminal",
        # which instructs a close there. The enumeration above cannot see it: requiring >=1
        # close per branch name is satisfied whether or not an extra close renders here.
        c1_start = lowered.find("else if this was confirm-1")
        assert c1_start != -1, f"{variant}: no confirm-1 arm in Step C3"
        c1_end = lowered.find("else:", c1_start)
        assert c1_end > c1_start, f"{variant}: the confirm-1 arm has no lower bound"
        assert "review_run close" not in lowered[c1_start:c1_end], (
            f"{variant}: a close renders on C3's `confirm-1` arm, which is NOT terminal — it "
            "enters a repair round and dispatches confirm-2. Closing there releases the slug "
            "mid-pass while <run-id> is still the join key for the lens-results tree, the ledger "
            "rows and the freeze refs"
        )


def test_review_reads_the_run_id_from_open_at_every_consumer() -> None:
    """Measured, not hypothetical. In the DEFAULT render (ledger off) the current template emits
    `<run-id>` **19 times** and the sentence that says what to put there **zero** times — it
    lives inside the `instrumentation.stage_agent_ledger` conditional while the consumers
    (lens-results path, `lens_coverage`, the confirmation-pass paths) sit outside it. So the
    id-source sentence must render unconditionally, and this asserts it in the config where the
    old one was absent."""
    for variant in VARIANTS:
        body = _body(f"{variant}:review")
        assert "<run-id>" in body, f"{variant}: no consumers — this test has stopped testing"
        source = re.search(r"read it from `?open`?|id from `?review_run open`?", body, re.I)
        assert source is not None, (
            f"{variant}: `<run-id>` has consumers but nothing says where the value comes from"
        )
        # Bound to the FIRST consumer, not merely present somewhere: an existence check over a
        # 60KB body is satisfied by a sentence 400 lines away from every use, which differs only
        # cosmetically from the sentence-inside-the-conditional defect this test was written for.
        assert source.start() < body.index("<run-id>"), (
            f"{variant}: the id-source sentence renders AFTER the first `<run-id>` consumer"
        )
