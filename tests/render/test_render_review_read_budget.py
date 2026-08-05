"""PLAN Phase 3 — AC-008 (reviewer read budget) and AC-009 (verification invariance).

AC-008 is a render-grep and is honest about it: it proves the instruction is PRESENT,
never that a reviewer obeys it (CLAUDE.md checkpoint 2 — behavioural confirmation is
Open Question 5, out of scope). What keeps it from being a tautology is the pair of
guards below, both of which an earlier draft of the AC lacked:

  * **non-emptiness** — `all()` over an empty set is True, so a discovery function that
    returned nothing would satisfy every arm. The site counts are asserted explicitly.
  * **discrimination** — `test_the_predicates_discriminate_against_the_pre_change_render`
    asserts the pre-change goldens FAIL the positive predicates and match the negative
    one. Without it, a predicate that is true of every document would pass here.

AC-009 is the invariance guard that lets AC-008 change reviewer prose without anyone
having to trust the change stayed narrow. Its reference is a committed pre-change
render — a genuine second sample of the same surface, produced before the edit existed.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, SecondOpinionConfig
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_FIXTURES = Path(__file__).parents[1] / "fixtures"

# The goldens were captured through THIS helper, so the before/after pair is guaranteed
# to differ only by the template edit. `second_opinion` is switched ON deliberately: with
# the synthesized default (no models) the render contains zero second-opinion dispatches,
# and AC-009's `second_opinion_invocation_points` conjunct would compare the empty set to
# the empty set in every possible world — the exact vacuity validator-3 H3 caught in the
# sibling `validator_invocation_points` conjunct. `test_the_invariance_guards_are_not_vacuous`
# is the standing check that it stays non-empty.
_SECOND_OPINION_MODELS = ["codex", "antigravity"]


def _profile(preset: Preset) -> ProjectProfile:
    return (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )


@cache
def _render_root(preset: Preset) -> Path:
    """Render once per preset for the whole module — a full render is not cheap."""
    profile = _profile(preset)
    answers = interview(profile, autoloop_mode=True)
    answers.second_opinion = SecondOpinionConfig(models=list(_SECOND_OPINION_MODELS))
    bp = synthesize(profile, answers, preset=preset)
    out = Path(mkdtemp(prefix="hm-read-budget-"))
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _command(preset: Preset, name: str) -> str:
    return (_render_root(preset) / "commands" / "hm" / name).read_text(encoding="utf-8")


def atomic_review_render() -> str:
    return _command(Preset.PRODUCTION, "review.md")


def single_reviewer_review_render() -> str:
    """The `{% else %}` branch at review.md.j2:217 — structurally unreachable under a
    multi-reviewer config, which is why the fourth dispatch site went unguarded."""
    return _command(Preset.SIDE, "review.md")


def rendered_plan_command() -> str:
    """Was `plan-exec-rev.md`; re-pointed to the atomic plan command when the fused axis
    was deleted (PLAN-harness-diet ADR-001). The fused body inlined this same stage, so
    the validator-invocation invariance it guards is unchanged."""
    return _command(Preset.PRODUCTION, "plan.md")


def reviewer_renders() -> tuple[str, ...]:
    return (atomic_review_render(),)


def _golden(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def golden_atomic() -> str:
    return _golden("review_command_pre_change.md")


def golden_fused() -> str:
    return _golden("review_command_fused_pre_change.md")


def golden_plan_bearing_fused() -> str:
    return _golden("plan_command_fused_pre_change.md")


# ------------------------------------------------------------------ golden hygiene


_GOLDEN_NAMES = (
    "review_command_pre_change.md",
    "review_command_fused_pre_change.md",
    "plan_command_fused_pre_change.md",
)


@pytest.mark.parametrize("name", _GOLDEN_NAMES)
def test_no_golden_bakes_a_machine_specific_absolute_path(name: str) -> None:
    """The gate `[fail:test] snapshot-regen-inside-worktree` never had, at count 12.

    A render produced from a `.worktrees/<x>/` checkout bakes that absolute path into
    `harness_maker_src_path`. The golden then encodes WHERE it was captured, so
    `test_verification_structure_unchanged` passes only in that worktree and goes red in
    CI and in the base repo once the worktree is landed and deleted.

    It happened here: the first capture of these three goldens carried 13 / 45 / 39
    occurrences of `reviewer-read-budget`, because `tests/render/` had no conftest and so
    inherited neither of the two places that pin the ref (`tests/snapshot/regenerate.py`
    and `tests/unit/conftest.py`). Verifying that the SNAPSHOT fixtures were clean and
    generalising that to these goldens is the step this test exists to make impossible.

    Checks the property (no absolute machine path) rather than the symptom (no
    `.worktrees`), so a capture from any other checkout location fails too. `$HOME/...`
    is the portable form `_portablize_ref` produces and is what a correct capture holds.
    """
    text = (_FIXTURES / name).read_text(encoding="utf-8")
    offenders = sorted(
        {
            m
            for m in re.findall(r"(?<![\w$])/(?:home|Users|root)/[\w.\-/]+", text)
            if "harness" in m or ".worktrees" in m
        }
    )
    assert not offenders, f"{name} bakes machine-specific absolute path(s): {offenders}"
    assert "$HOME/harness-maker" in text, (
        f"{name} has no portable install ref at all — was it captured with the pin?"
    )


# ------------------------------------------------------------------ discovery

# Terminates at the NEXT `### ` heading, whatever it is. An earlier draft used a
# `(?=^### (?!Step 3)|\Z)` lookahead, which failed to stop at `### Step 3.5` — that
# heading also starts with "Step 3" — so the two cross-model `####` blocks under Step 3.5
# were swallowed and the site count read 5 instead of 3. RED caught it; nothing else
# would have, because both extra blocks mention "reviewer" and looked like real sites.
_STEP3 = re.compile(
    r"^### Step 3 — Parallel reviewer invocation[^\n]*\n(?:(?!^### ).)*", re.M | re.S
)
_H4_BLOCK = re.compile(r"^#### .*?(?=^#### |\Z)", re.M | re.S)
_NAMES_A_REVIEWER = re.compile(r"reviewer|code-verifier")
_STAGE_SLICE = re.compile(r"^## Stage: review\b.*?(?=^## Stage: |\Z)", re.M | re.S)


def review_stage_slice(render_text: str) -> str:
    """A fused command concatenates several stages; AC-009's structural comparison is
    about the REVIEW stage only, so an unrelated stage's agent mention cannot move it."""
    found = _STAGE_SLICE.findall(render_text)
    return found[0] if found else render_text


def reviewer_dispatch_sites(render_text: str) -> list[str]:
    """Every `####` heading block inside the reviewer-dispatch step whose body names a
    reviewer agent to run (AC-008's discovery definition).

    Anchored on a heading shape that exists BEFORE the edit, so the site count cannot be
    tuned by the change under test. Measured on the pre-change renders: 3 under a
    multi-reviewer config (Pass 1 / Pass 1.5 / Pass 2) and 1 under single-reviewer
    (Direct review) — four distinct sites across the template, as ADR-011 states.
    """
    sites: list[str] = []
    for step in _STEP3.findall(review_stage_slice(render_text)):
        for block in _H4_BLOCK.findall(step):
            body = block.split("\n", 1)[1] if "\n" in block else ""
            if _NAMES_A_REVIEWER.search(body):
                sites.append(block)
    return sites


# ------------------------------------------------------------------ AC-008 predicates

# The pre-change instruction, pinned WHITESPACE-NORMALIZED. In the template the sentence
# wraps between "changed files" and "end-to-end" and its verb is "Reads", not "Read" — an
# earlier draft of this AC pinned an unwrapped "Read the diff …" that appears nowhere in
# the source, so the negative arm could never match and always passed (validator-3 M6).
_UNCONDITIONAL_FULL_READ = (
    "Reads the diff with full context (use Read on changed files end-to-end, not just the patch)."
)


def _normalized(text: str) -> str:
    """Collapse whitespace AND strip blockquote markers.

    The budget clause is a `>` blockquote, so a phrase wrapping across two lines becomes
    `... or > to files ...` if only whitespace is collapsed — which silently defeats
    every contiguous-phrase anchor below. Caught by RED when the anchors were introduced.
    """
    unquoted = [re.sub(r"^\s*>+\s?", "", line) for line in text.splitlines()]
    return " ".join(" ".join(unquoted).split())


# All predicates match WHITESPACE-NORMALIZED, for the same reason the negative arm does:
# the clause is line-wrapped prose inside a blockquote, so any phrase long enough to be
# meaningful WILL be split across lines and a raw substring test would silently fail.


# Polarity, not just presence. The first draft used bare substring checks, and a review
# constructed a blockquote that satisfied ALL FOUR while inverting the intent:
#   "Use only the diff. You may read up to **0** lines of surrounding context; this is
#    not a ceiling on the diff itself. Never escalate. Files outside the diff are
#    off-limits. Do not emit [elided: ...] markers."
# Two changes close it: a numeric FLOOR (a budget of 0 is a prohibition, not a budget),
# and contiguous affirmative phrase anchors plus an explicit negation guard.
#
# This is still a render-grep and still cannot prove a reviewer OBEYS the budget —
# AC-008 says so outright. It can now only be satisfied by prose that at least *reads*
# as the intended instruction.
_MIN_BUDGET_LINES = 100

_NEGATORS = ("never escalate", "do not escalate", "off-limits", "do not emit")


def has_bounded_read_default(site: str) -> bool:
    flat = _normalized(site)
    m = re.search(r"up to \*\*(\d+)\*\* lines", flat)
    return bool(m) and int(m.group(1)) >= _MIN_BUDGET_LINES and "not a ceiling" in flat


def has_escalation_clause(site: str) -> bool:
    flat = _normalized(site).lower()
    if any(neg in flat for neg in _NEGATORS):
        return False
    return "escalate to the rest of a file" in flat


def requires_visible_elision_marker(site: str) -> bool:
    flat = _normalized(site)
    if any(neg in flat.lower() for neg in _NEGATORS):
        return False
    return "[elided:" in flat


def states_outside_diff_scope(site: str) -> bool:
    flat = _normalized(site)
    if any(neg in flat.lower() for neg in _NEGATORS):
        return False
    return "or to files **outside the diff**" in flat


def contains_unconditional_full_file_read(site: str) -> bool:
    return _normalized(_UNCONDITIONAL_FULL_READ) in _normalized(site)


def states_precedence_over_agent_body(site: str) -> bool:
    """The budget must say it BEATS the agent definition, or it loses to it.

    Six reviewer agent bodies still carry `**Read changed files end-to-end** before
    forming a hypothesis`, and PLAN Phase 3 puts agent definitions out of scope. An agent
    treats its own body as durable role instruction and the stage text as transient task
    context, so with no stated precedence the older, persistent one wins and the budget
    is decorative. Added after a review found the phase's outcome was defeated by six
    copies of the instruction the negative arm only removed from one place.
    """
    return "budget overrides the `Read changed files end-to-end` bullet" in _normalized(site)


_POSITIVE_PREDICATES = (
    has_bounded_read_default,
    has_escalation_clause,
    requires_visible_elision_marker,
    states_outside_diff_scope,
    states_precedence_over_agent_body,
)


# ------------------------------------------------------------------ AC-009 extractors


def reviewer_pass_count(render_text: str) -> int:
    return len(reviewer_dispatch_sites(render_text))


_REVIEWER_AGENTS = re.compile(
    r"\b(code-reviewer|security-reviewer|security-auditor|performance-reviewer"
    r"|ux-reviewer|concurrency-reviewer|consensus-arbiter|code-verifier)\b"
)


def enabled_reviewer_set(render_text: str) -> frozenset[str]:
    return frozenset(_REVIEWER_AGENTS.findall(review_stage_slice(render_text)))


# Two sources, deliberately: the ADR-006 second-opinion sentence (present only when
# `second_opinion.models` is non-empty) AND the stage's own Configuration line, which is
# always rendered. With only the former this conjunct was ∅ == ∅ for any harness with
# second opinion off — the same vacuity the golden re-capture was meant to remove
# (review P2).
_CONSENSUS_K = re.compile(
    r"consensus threshold stays \*\*K = (\d+)\*\*"
    r"|K = (\d+) \(any"
    r"|(`consensus` — `single` \| `cross-check \(2/3\)` \| `k-of-n`)"
)


def consensus_threshold(render_text: str) -> tuple[str, ...]:
    slice_ = review_stage_slice(render_text)
    return tuple(sorted({m for pair in _CONSENSUS_K.findall(slice_) for m in pair if m}))


_SECOND_OPINION_DISPATCH = re.compile(r"second_opinion_invoke --model (\S+)")


def second_opinion_invocation_points(render_text: str) -> tuple[str, ...]:
    return tuple(sorted(_SECOND_OPINION_DISPATCH.findall(review_stage_slice(render_text))))


_VALIDATOR_DISPATCH = re.compile(r'subagent_type="plan-validator"|`plan-validator`')


def validator_invocation_points(render_text: str) -> tuple[str, ...]:
    """The enclosing heading for each dispatch — position-INDEPENDENT witnesses.

    An earlier draft returned raw character offsets. That made the conjunct fail on any
    edit that changed the render's length before the matches, and Phase 4 hoists shared
    partials out of the plan and execute stages — both of which precede every
    `plan-validator` match in the plan-bearing golden. AC-009 would have gone red in
    Phase 4 for a length change rather than for a deleted dispatch, breaking ADR-011's
    "must stay green through Phase 4". Headings still move when a dispatch is deleted or
    relocated to a different step, which is the sensitivity the offsets were bought for.
    """
    witnesses: list[str] = []
    for m in _VALIDATOR_DISPATCH.finditer(render_text):
        heading = "<no-heading>"
        for h in re.finditer(r"^#{2,4} .*$", render_text[: m.start()], re.M):
            heading = h.group(0).strip()
        witnesses.append(heading)
    return tuple(sorted(witnesses))


def paired_review_renders_against_goldens() -> tuple[tuple[str, str], ...]:
    # The fused pair went with the fused axis (ADR-001); the atomic pair is the whole
    # comparison now. `golden_fused()` is still read by the goldens-exist arm below.
    return ((atomic_review_render(), golden_atomic()),)


# ------------------------------------------------------------------ AC-008


def test_bounded_read_with_escalation() -> None:
    """AC-008's executable predicate, evaluated against the real renders.

    The two leading non-emptiness conjuncts are the whole reason this is not vacuous:
    `all()` over an empty discovery is True, so without them a broken
    `reviewer_dispatch_sites` would satisfy every arm below.
    """
    assert all(len(reviewer_dispatch_sites(r)) >= 1 for r in reviewer_renders())
    assert len(reviewer_dispatch_sites(single_reviewer_review_render())) >= 1

    assert all(
        has_bounded_read_default(site)
        and has_escalation_clause(site)
        and requires_visible_elision_marker(site)
        and states_outside_diff_scope(site)
        and not contains_unconditional_full_file_read(site)
        for render_text in reviewer_renders()
        for site in reviewer_dispatch_sites(render_text)
    )


def test_the_single_reviewer_branch_is_guarded_too() -> None:
    """The fourth site lives in a `{% else %}` this harness's own config cannot emit.

    Named separately, per ADR-011: folding it into `reviewer_renders()` would let an
    empty discovery on this render alone hide behind the other two.
    """
    sites = reviewer_dispatch_sites(single_reviewer_review_render())
    assert len(sites) == 1, f"expected the Direct-review site only, got {len(sites)}"
    for predicate in _POSITIVE_PREDICATES:
        assert predicate(sites[0]), f"{predicate.__name__} missing from the single-reviewer site"
    assert not contains_unconditional_full_file_read(sites[0])


def test_the_agent_body_precedence_is_stated_at_every_site() -> None:
    """Separate from `test_bounded_read_with_escalation`, which is AC-008 verbatim.

    The precedence sentence is NOT part of AC-008's `executable_predicate` — it was added
    after review found six reviewer agent bodies still ordering unbounded end-to-end
    reads — so it must not be smuggled into the AC test. It still needs a gate on EVERY
    render: `_POSITIVE_PREDICATES` only reaches the single-reviewer site, so without this
    a deletion from the multi-reviewer branch alone would pass everything.
    """
    for render_text in (*reviewer_renders(), single_reviewer_review_render()):
        sites = reviewer_dispatch_sites(render_text)
        assert sites
        for site in sites:
            assert states_precedence_over_agent_body(site), (
                f"a dispatch site does not state precedence over the agent body: "
                f"{site.splitlines()[0]}"
            )


def test_the_site_count_matches_the_pre_change_anchor() -> None:
    """Non-emptiness is a floor; this pins the exact shape the discovery is anchored on.

    Measured on the goldens BEFORE the edit: 3 sites per multi-reviewer render. If the
    edit had to add or move a `####` block to make AC-008 pass, that would show up here
    rather than being absorbed silently.
    """
    for render_text in reviewer_renders():
        assert reviewer_pass_count(render_text) == 3
    for golden in (golden_atomic(),):
        assert reviewer_pass_count(golden) == 3


def test_the_predicates_discriminate_against_the_pre_change_render() -> None:
    """The anti-tautology arm: every positive predicate must FAIL on the goldens.

    A predicate that is true of any document would pass `test_bounded_read_with_escalation`
    while gating nothing. The negative predicate is checked in the opposite direction on
    the one site that carried the pinned sentence.
    """
    for golden in (golden_atomic(),):
        sites = reviewer_dispatch_sites(golden)
        assert sites
        for predicate in _POSITIVE_PREDICATES:
            assert not any(predicate(s) for s in sites), (
                f"{predicate.__name__} is already true pre-change — it discriminates nothing"
            )

    pass_one = reviewer_dispatch_sites(golden_atomic())[0]
    assert contains_unconditional_full_file_read(pass_one), (
        "the negative arm's pinned sentence is not in the pre-change Pass 1 site; "
        "it would then be unable to fail in any possible world"
    )


# ------------------------------------------------------------------ AC-009


def test_verification_structure_unchanged() -> None:
    """AC-009's executable predicate — the diff changed reviewer prose and nothing else."""
    assert all(
        reviewer_pass_count(after) == reviewer_pass_count(golden)
        and enabled_reviewer_set(after) == enabled_reviewer_set(golden)
        and consensus_threshold(after) == consensus_threshold(golden)
        and second_opinion_invocation_points(after) == second_opinion_invocation_points(golden)
        for after, golden in paired_review_renders_against_goldens()
    )
    after_validator = validator_invocation_points(rendered_plan_command())
    golden_validator = validator_invocation_points(golden_plan_bearing_fused())
    assert after_validator == golden_validator
    assert len(golden_validator) >= 1


def test_the_invariance_guards_are_not_vacuous() -> None:
    """Every AC-009 extractor must return something on the goldens.

    An invariance check between two empty sets holds in every possible world, including
    one where the thing being guarded was deleted. AC-009 carries a `>= 1` for
    `validator_invocation_points` because validator-3 H3 caught exactly that; the other
    three conjuncts have no such guard in the predicate, so they get one here.
    `second_opinion_invocation_points` is the reason `_SECOND_OPINION_MODELS` is non-empty.
    """
    for golden in (golden_atomic(),):
        assert reviewer_pass_count(golden) >= 1
        assert enabled_reviewer_set(golden)
        assert consensus_threshold(golden)
        assert second_opinion_invocation_points(golden)
    assert validator_invocation_points(golden_plan_bearing_fused())
    assert not validator_invocation_points(golden_atomic()), (
        "a review render containing a plan-validator dispatch would mean the third "
        "golden is no longer the only witness, and H3's rationale needs re-checking"
    )


@pytest.mark.parametrize(
    ("extractor", "mutate"),
    [
        # Deleting the HEADING, not renaming it: a renamed heading still opens a block
        # whose body names `code-verifier`, so it stays a discovered site and the count
        # never moves. Removing the heading merges the body into Pass 1 — 3 sites -> 2.
        (
            reviewer_pass_count,
            lambda t: t.replace("#### Pass 1.5 — verifier (active, ADR-008)\n", "", 1),
        ),
        (
            enabled_reviewer_set,
            lambda t: t.replace("code-verifier", "code-verifiXr"),
        ),
        (
            second_opinion_invocation_points,
            lambda t: t.replace("second_opinion_invoke --model codex", "echo skipped", 1),
        ),
        # ADR-010: these two shipped with no deletion-check in the first draft, and
        # `validator_invocation_points` is the conjunct validator-3 H3 added an entire
        # third golden for — the one extractor whose regex, if it silently matched
        # nothing, would report a stable value forever. That is H3's failure mode in a
        # new form (review P1).
        (
            consensus_threshold,
            lambda t: t.replace("K = 2", "K = 3").replace(
                "`consensus` — `single` | `cross-check (2/3)` | `k-of-n`", "(removed)"
            ),
        ),
    ],
)
def test_each_invariance_extractor_detects_its_own_deletion(
    extractor: object, mutate: object
) -> None:
    """Removing what an extractor measures must move its value.

    Without this, an extractor whose regex never matched would report a stable empty
    value forever and AC-009 would certify a structure it never read.
    """
    golden = golden_atomic()
    damaged = mutate(golden)  # type: ignore[operator]
    assert damaged != golden, "the mutation did not apply — the anchor moved"
    assert extractor(damaged) != extractor(golden)  # type: ignore[operator]


def test_the_validator_extractor_detects_its_own_deletion() -> None:
    """Separate from the parametrized cases because it needs the THIRD golden.

    `golden_atomic()` contains no `plan-validator` dispatch at all (asserted in
    `test_the_invariance_guards_are_not_vacuous`), so a mutation case pointed at it
    would compare () to () and prove nothing — the ∅ == ∅ shape validator-3 H3 caught
    in the AC itself, reproduced in the test that is supposed to guard it.
    """
    golden = golden_plan_bearing_fused()
    damaged = golden.replace('subagent_type="plan-validator"', 'subagent_type="none"', 1)
    assert damaged != golden, "the mutation did not apply — the anchor moved"
    assert validator_invocation_points(damaged) != validator_invocation_points(golden)


def test_the_polarity_guards_reject_an_inverted_budget() -> None:
    """The adversarial block a review built to defeat the first draft's predicates."""
    inverted = (
        "#### Pass X — reviewer\n\n"
        "> Read budget. Use only the diff. You may read up to **0** lines of surrounding\n"
        "> context per changed file; this is not a ceiling on the diff itself. Never\n"
        "> escalate. Files outside the diff are off-limits. Do not emit\n"
        "> [elided: <path>] markers.\n"
    )
    for predicate in _POSITIVE_PREDICATES:
        assert not predicate(inverted), f"{predicate.__name__} accepts an inverted budget"
