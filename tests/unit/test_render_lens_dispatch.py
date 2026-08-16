"""Phase 4 — the rendered /hm:review declares a failure space and gates approval on it.

**Why every assertion here is anchored to a bounded slice and to a token prose cannot supply.**
Five A.5 rounds killed five weaker generations of this file. Each round's finding is recorded
at the test it killed; the pattern across all five is one thing:

> Every generation carried a docstring asserting that its anchor was strong. Three of those
> claims were false, and the claim is what let the weak anchor ship. Rounds 3 and 4 both
> found a *repair* that had covered its defect with a stronger-sounding sentence rather than
> closing it. Nothing below claims an anchor is sufficient unless the alternative was
> actually enumerated and ruled out.

Refuted claims, kept here because their replacements depend on knowing they are refuted:

- *"A bare lens name goes red for a dropped dispatch."* — No. The shipped template already
  says "failure mode" and "unit tests" (round 1).
- *"Slicing to the next `##` narrows a `###` section."* — No. `### Step 3` runs 120 lines to
  `## Grade Computation`, swallowing three sibling steps (round 2). `_section` now takes a
  mandatory `stop`.
- *"`blocks_approval` and `missing` are CLI keys, so naming them proves CLI consumption."* —
  Half true. `blocks_approval` cannot occur incidentally; **`missing` is an ordinary English
  word** and appears in this template already (round 3). Backticking it does not fix that —
  backticks are markdown emphasis (round 4). `_names_cli_key` is therefore a *necessary*
  condition only, and every call site pairs it with a second anchor.

What does the discriminating work now: a fenced block (one code fence carrying a `Task(` call
per lens — a serial dispatch renders as separate fences), the unforgeable `blocks_approval`
identifier, and `_gate_conditions`, which reads a condition out of the gate's pseudocode so that
neither prose nor a `#` comment can stand in for a decision.

The AC-003 assertions render at `grade_threshold` A, B and C. An earlier draft pinned the
wording with `"below A" not in body`, which is unsound both ways: "caps the grade at B" passes
it, and the correct sentence for an A-threshold harness fails it.

**Two tests are GREEN before implementation, and cannot be otherwise.** Both are absence
assertions — `test_the_lens_agents_are_not_told_to_write_their_own_result` and
`test_the_coverage_blocker_is_not_emitted_as_an_ordinary_finding`. A negative invariant is
vacuously true while the construct it constrains does not exist. Neither is a tautology: each
goes red the moment the wrong implementation appears, and each is paired with a RED positive
sibling that forces the construct into existence (`..._is_dispatched_not_merely_named` and
`..._carries_lens_id_and_attempt_count` respectively). Two GREEN is the expected state, not a
shortfall.

**Not covered here, deliberately.** `refs/hm-freeze/v1/*` faithfulness is AC-004 and is
verified against real git objects in `tests/unit/test_freeze_commit.py`; a render grep cannot
observe which commit a ref names. "The results directory is never reused" was a quoted
sentence with no anchor — its verifiable content is that the path carries the round number and
the CLI is called with `--round` **and** `--run-id`, which two tests below assert directly.
(Round keying alone was not enough: F2 measured a second `/hm:review` on the same slug reusing
round 1's directory, four dead lenses vouched for by the prior invocation.)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.conditional_router import OPTIONAL_REVIEWERS, mandatory_lenses
from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

RESULTS_ROOT = ".claude/observability/.hm-lens-results"

#: `_render` below builds the default profile, which is a Side harness, so the mandatory set is
#: the six core categories — the three domain lenses are routable there and mandatory only on
#: Production. Reading it from the same function the renderer calls keeps this file from
#: re-typing the axis; `tests/unit/test_render_lens_axis.py` covers both presets.
MANDATORY_LENSES = mandatory_lenses(Preset.SIDE.value)


def _render(tmp_path: Path, grade_threshold: str = "A") -> Path:
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    a.grade_threshold = grade_threshold
    bp = synthesize(p, a)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _section(body: str, start: str, *, stop: str) -> str:
    """Slice the block introduced by `start`, so membership means "in THIS block".

    `stop` is mandatory: the round-2 defect was a default that let a `###` section run to the
    next `##`, swallowing three sibling steps.
    """
    i = body.find(start)
    assert i != -1, f"rendered command has no section starting {start!r}"
    j = body.find(stop, i + len(start))
    return body[i:] if j == -1 else body[i:j]


def _fenced_blocks(text: str) -> list[str]:
    """Every ``` -delimited block, so "one message" is checkable rather than quotable."""
    return re.findall(r"^```[^\n]*\n(.*?)^```", text, flags=re.S | re.M)


def _names_cli_key(text: str, key: str) -> bool:
    """True iff `key` appears as a quoted/code-span identifier, not as bare running English.

    Round-3 defect: `"missing" in block` is satisfied by prose, and this very template already
    says "reasoning is missing on one side" at Step 4.

    **This is a necessary condition, not a sufficient one.** Round 4 refuted the stronger claim
    the previous docstring made: backticks are ordinary markdown emphasis, so a sentence like
    "say that a mandatory lens is `missing`" satisfies this while reading no CLI output. Every
    call site therefore pairs it with a second, unforgeable anchor (`blocks_approval`, or the
    CLI's module name). Do not use it alone.
    """
    return re.search(rf"[`\"']{re.escape(key)}[`\"']", text) is not None


def _gate_conditions(gate: str, outcome: str) -> list[str]:
    """The CONDITION of every `IF` arm in the gate's pseudocode whose body reaches `outcome`.

    Four generations of this helper failed, each in a way the next had to be told about:

    - `"grade_threshold" in approved_slice` was tautological — the slice began with the
      search literal, so it was true whenever the slice existed (round 3).
    - Any *line* carrying both identifiers was satisfied by one narrative sentence in the
      gate's prose half, and was false-RED against a two-line condition (round 4).
    - Slicing from the arm's `IF` up to the outcome token returned the condition **plus the
      body lines preceding it**, because the outcome sits inside the body (`→ Status =
      APPROVED`). A gate that merely *printed* `blocks_approval` therefore passed (round 5).
    - Taking the FIRST occurrence of the outcome bound the assertion to arm ordering. The gate
      has two `CHANGES_REQUESTED` arms; the first is AC-007's `auto_fix disabled`, not
      AC-013's budget arm, and the SPEC states the rule order-independently (round 5).

    So: parse arms, keep only the `IF` header up to the `:` that closes it (a wrapped
    condition survives; body lines cannot leak in), strip comments including trailing ones,
    and return **every** matching arm so the caller asserts over all of them.
    """
    pseudo = "\n".join(_fenced_blocks(gate))
    lines = pseudo.splitlines()
    starts = [n for n, line in enumerate(lines) if line.startswith(("IF ", "ELSE"))]
    conditions: list[str] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        arm = lines[start:end]
        if not any(outcome in line for line in arm):
            continue
        header: list[str] = []
        for line in arm:
            stripped = line.split("#", 1)[0].rstrip()
            header.append(stripped)
            if stripped.endswith(":"):
                break
        conditions.append("\n".join(header))
    return conditions


@pytest.fixture(scope="module")
def review_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = _render(tmp_path_factory.mktemp("rendered-a"))
    f = out / "commands" / "hm" / "review.md"
    assert f.is_file(), f"missing rendered command file: {f}"
    return f.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def round_one_block(review_body: str) -> str:
    return _section(review_body, "## Procedure — Round 1", stop="\n## ")


@pytest.fixture(scope="module")
def selection_block(review_body: str) -> str:
    return _section(review_body, "### Step 1 — Reviewer set selection", stop="\n### ")


@pytest.fixture(scope="module")
def dispatch_block(review_body: str) -> str:
    return _section(review_body, "### Step 3 — Parallel reviewer invocation", stop="\n### ")


@pytest.fixture(scope="module")
def report_block(review_body: str) -> str:
    return _section(review_body, "### Step 5 — Write REVIEW report", stop="\n## ")


@pytest.fixture(scope="module")
def gate_block(review_body: str) -> str:
    return _section(review_body, "## Grade Gate", stop="\n## ")


@pytest.fixture(scope="module")
def autofix_block(review_body: str) -> str:
    return _section(review_body, "## Auto-Fix Loop", stop="\n## ")


@pytest.fixture(scope="module")
def telemetry_block(review_body: str) -> str:
    return _section(review_body, "## Telemetry Emit", stop="\n## ")


# ── AC-002: the declared space is dispatched on round 1, in one message ───────


@pytest.mark.parametrize("lens", MANDATORY_LENSES)
def test_each_mandatory_lens_is_dispatched_not_merely_named(dispatch_block: str, lens: str) -> None:
    """Anchored to the per-lens result path, which no incidental prose can produce.

    `lens in review_body` was GREEN for `failure` before any implementation existed.
    """
    assert f"{lens}.json" in dispatch_block, (
        f"lens {lens!r} has no result-file instruction in the round-1 dispatch block"
    )


def test_the_result_file_is_written_only_for_a_returned_dispatch(dispatch_block: str) -> None:
    """AC-011's other conjunct — without it the whole coverage gate is inert.

    SPEC:350 — "a dispatch that returns nothing produces no file." An instruction to write
    `<lens>.json` for every *dispatched* lens satisfies every other assertion in this file
    while making `missing` permanently empty and `blocks_approval` permanently false. The
    self-report hole would simply have moved from the subagent to the main loop.

    Golden by construction: the wording is fixed by the SPEC before the template is written,
    the same basis as AC-013's blocker string.

    Round 4: the bare phrase `"returns nothing"` was polarity-blind — "a dispatch that returns
    nothing **still produces a file** recording the failure" satisfied it while implementing
    the defect. The whole clause is matched instead, so the negation cannot pass.
    """
    normalized = " ".join(dispatch_block.split())
    assert re.search(r"returns nothing\s+produces no file", normalized), (
        "the dispatch block instructs an unconditional result-file write; a lens that "
        "returns nothing would still be counted as exercised, leaving `missing` permanently "
        "empty and the coverage gate inert"
    )


def test_round_one_dispatches_the_mandatory_set_in_one_message(dispatch_block: str) -> None:
    """One fence, one `Task(` per lens — the same shape Phase A.5 uses for its three lenses.

    "in parallel" as a phrase is already in the shipped template (the 2-pass instruction), so
    quoting it can never go red. A serial dispatch, or one that defers lenses to round 2,
    renders as separate fences and fails here.
    """
    fences = _fenced_blocks(dispatch_block)
    for fence in fences:
        if fence.count("Task(") < len(MANDATORY_LENSES):
            continue
        if all(lens in fence for lens in MANDATORY_LENSES):
            return
    raise AssertionError(
        "no single fenced block in the round-1 dispatch carries a Task( call for each of "
        f"{list(MANDATORY_LENSES)}; found {len(fences)} fences with "
        f"{[f.count('Task(') for f in fences]} Task( calls"
    )


def test_the_selection_step_enumerates_the_mandatory_set(selection_block: str) -> None:
    """Routing is chosen in Step 1; the set that routing may not shrink has to be stated there.

    Scoped to Step 1 (11 lines in the shipped template) rather than the whole document, where
    four of the five words occur incidentally.
    """
    missing = [lens for lens in MANDATORY_LENSES if lens not in selection_block]
    assert not missing, f"Step 1 does not name mandatory lens(es) {missing}"


def test_review_base_is_resolved_and_stored_at_round_one(round_one_block: str) -> None:
    """AC-002's other clause, scoped to round 1 — which is the whole content of the clause.

    Over the whole document these two substrings are satisfied by a template that resolves
    `review_base` lazily inside the Phase 5 confirmation-pass block. That is precisely what
    the Definitions row forbids: resolved ONCE at round 1, because a value with no round-1
    store is a free variable each pass re-resolves, drifting as new commits land. AC-004's
    test works on git objects and cannot observe where the resolution is instructed, so
    nothing else covers the placement.

    Round 4: the store half was a bare `"-base"` substring, which the resolution recipe's own
    `git merge-base` satisfies — so after implementation it could no longer distinguish the
    `<slug>-base` store from the AC-004 freeze-commit refs in the same namespace, or from no
    store at all. The two are now one anchored match.
    """
    assert "review_base" in round_one_block, (
        "round 1 never mentions review_base; a later pass would re-resolve it and drift"
    )
    assert re.search(r"refs/hm-freeze/v1/[^\s`\"']*-base", round_one_block), (
        "round 1 does not write review_base to its store refs/hm-freeze/v1/<slug>-base; "
        "without the store each pass re-resolves the base and it drifts as commits land"
    )


def test_the_harness_yaml_routing_block_carries_the_rule(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The rule must be visible where routing is configured, not only where it is executed.

    Scoped to the `reviewers:` block: a whole-file word match passes on any unrelated use of
    "mandatory" elsewhere in a 150-line config.

    Round 5 removed an `assert "routing:" in reviewers`. AC-002 asks for a *comment*; no AC
    asks for a persisted `routing` key, no template renders one, and `ReviewersConfig` has no
    such field. That assertion was false-RED — a SPEC-faithful implementation could not turn
    it green without shipping an unspecified schema change, and its failure message named a
    defect ("does not configure routing at all") that is not an AC-002 finding.

    The surviving assertion pairs the word with a lens id from the constant, so an unrelated
    use of "mandatory" in the config cannot satisfy it.
    """
    out = _render(tmp_path_factory.mktemp("rendered-yaml"))
    harness_yaml = (out / "harness.yaml").read_text(encoding="utf-8")
    reviewers = _section(harness_yaml, "\nreviewers:", stop="\nskills:")
    assert "mandatory" in reviewers.lower(), (
        "the reviewers block does not state that a mandatory lens may not be routed away"
    )
    named = [lens for lens in MANDATORY_LENSES if lens in reviewers]
    assert named, (
        "the reviewers block says 'mandatory' without naming any lens from MANDATORY_LENSES, "
        "so the comment does not identify the set routing may not shrink"
    )


def test_route_reviewers_never_drops_a_non_optional_preset_reviewer() -> None:
    """AC-002's Python half, stated as the invariant rather than as a name list.

    The previous generation asserted `lens in selected` for each of MANDATORY_LENSES. That
    passes for a WRONG implementation — the cheapest satisfaction is `selected |=
    set(MANDATORY_LENSES)`, which injects failure-mode ids into a list of agent names and
    contradicts ADR-002 and the constant's own docstring. The real rule is subtractive:
    conditional routing may drop OPTIONAL_REVIEWERS and nothing else.

    Round 3 caught the mirror image of that defect: a one-sided "nothing is dropped" assertion
    is satisfied most cheaply by deleting the `routing != "conditional"` branch entirely, so
    the router returns the preset unchanged and conditional routing becomes a no-op. Both
    halves are therefore asserted — the optional pair must still be droppable — and only the
    narrowing AC-002 describes satisfies both.
    """
    from harness_maker.conditional_router import route_reviewers

    preset = [
        "code-reviewer",
        "security-reviewer",
        "concurrency-reviewer",
        "performance-reviewer",
        "ux-reviewer",
    ]
    # A path no rule in _RULES matches, so the router has no reason of its own to keep any
    # specialist — the pre-change implementation returns ["code-reviewer"] alone.
    selected = route_reviewers([Path("src/anything.py")], preset, routing="conditional")

    dropped = [r for r in preset if r not in selected and r not in OPTIONAL_REVIEWERS]
    assert not dropped, f"conditional routing dropped non-optional reviewer(s) {dropped}"

    kept_optional = [r for r in preset if r in selected and r in OPTIONAL_REVIEWERS]
    assert kept_optional == [], (
        "conditional routing kept an optional reviewer on a diff no rule matches: "
        f"{kept_optional}. Round 5: `len(kept) < 2` was satisfied by dropping ONE, so an "
        "implementation that keeps ux-reviewer unconditionally passed"
    )

    # Round 4: both halves above are evaluated on the SAME non-matching diff, so
    # `[r for r in preset if r not in OPTIONAL_REVIEWERS]` satisfies them while making
    # `_RULES` dead code — a .tsx diff could never reach ux-reviewer again. AC-002 and the
    # OPTIONAL_REVIEWERS docstring both say routing may *add or drop* the optional pair, so
    # the add direction needs its own input.
    # Round 5: asserting the add direction for ONE optional reviewer left the other's rule
    # unexercised in both directions, so `keep ux always, strip performance always` passed.
    # Both rules are now driven.
    ui = route_reviewers([Path("src/ui/widget.tsx")], preset, routing="conditional")
    assert "ux-reviewer" in ui, (
        "a .tsx/ui diff no longer routes to ux-reviewer — conditional routing has become an "
        "unconditional strip of the optional reviewers, and _RULES is dead code"
    )
    assert "performance-reviewer" not in ui, (
        "a .tsx diff routed to performance-reviewer, so the optional reviewers are being kept "
        "unconditionally rather than by rule"
    )

    perf = route_reviewers([Path("src/perf/hot_loop.c")], preset, routing="conditional")
    assert "performance-reviewer" in perf, "_RULES' /perf/ entry is dead code"
    assert "ux-reviewer" not in perf, (
        "a /perf/ diff routed to ux-reviewer — the two optional rules are not independent"
    )


# ── AC-011: the coverage verdict is produced by the CLI, and only by it ───────


@pytest.mark.parametrize("flag", ["--results-dir", "--slug", "--round", "--run-id"])
def test_the_coverage_call_carries_its_full_flag_set(review_body: str, flag: str) -> None:
    """Without `--round` the per-round directory cannot be addressed, which makes both the
    re-dispatch rule and the attempt counter unenforceable.

    `--run-id` closes what `--round` alone does not (F2): the directory is keyed by slug and
    round, so a SECOND `/hm:review` on the same slug lands in the same place and the previous
    invocation's files vouch for lenses that did not run this time. Measured before the fix:
    four dead lenses, `blocks_approval: false`."""
    # An INVOCATION line, not a mention. The gate's blocker paragraph refers to the CLI by name
    # in prose ("Whenever `hm lens_coverage check` reports ...") and must not be read as a call
    # that forgot its flags — the first version of this repair failed on exactly that sentence.
    calls = [
        line
        for line in review_body.splitlines()
        if "hm lens_coverage check" in line and ("!uv run" in line or 'Bash("' in line)
    ]
    assert calls, "the rendered command never invokes the coverage CLI"
    for call in calls:
        assert flag in call, (
            f"a coverage-CLI invocation omits {flag}: {call.strip()!r}. Round 5: slicing the "
            "FIRST occurrence anywhere in the document let a Configuration paragraph document "
            "the full invocation while the real call omitted a flag"
        )


def test_the_result_path_is_per_slug_and_per_round(dispatch_block: str) -> None:
    """The round segment is what makes the directory unreusable; asserting the segment is
    verifiable, whereas asserting the sentence "never reused" is not."""
    assert f"{RESULTS_ROOT}/<slug>/<round>/" in dispatch_block, (
        "the write instruction does not name the full per-round path. Round 5: asserting "
        f"{RESULTS_ROOT!r} and '<slug>/<round>/' as two independent whole-document substrings "
        "passed a template whose write instruction omitted the round segment while a separate "
        "rationale sentence quoted it — and the directory is then reusable across rounds"
    )


def test_the_lens_agents_are_not_told_to_write_their_own_result(dispatch_block: str) -> None:
    """A lens subagent that writes its own attendance file restores the self-report hole.

    Round 5: forbidding the literal `.json` inside a `Task(` fence was too narrow in two ways.
    A brief could name the directory without the extension (`write your result to
    $RESULTS_DIR/<lens-id>`), and a brief written as prose *outside* any fence was not looked
    at at all — while SPEC:350 forbids the subagent writing the file, not writing it from
    inside a code block.

    So: the results root must not appear anywhere in the dispatch block except in the main
    loop's own write instruction, and no `Task(` fence may carry it or a write verb aimed at
    the agent.
    """
    offenders = [
        f
        for f in _fenced_blocks(dispatch_block)
        if "Task(" in f and (RESULTS_ROOT in f or ".json" in f)
    ]
    assert not offenders, (
        "a lens dispatch brief names a result path — the subagent, not the main loop, is "
        f"being told to write it: {offenders[0][:300]!r}"
    )

    # The prose half. Every sentence that hands out the results root must address the main
    # loop; a second-person instruction inside the lens brief would read as the agent's job.
    # A DIRECTIVE, not the word. The first version of this check forbade the substring "write"
    # and went red on `partial-write`, which is the failure lens's own topic name — an
    # over-broad negative is a false-RED against a correct template, the same defect as an
    # over-broad positive, just pointing the other way.
    directive = re.compile(r"write\s+(your|the\s+result|it\s+to|to\s+\S+/)", re.IGNORECASE)
    for brief in (f for f in _fenced_blocks(dispatch_block) if "Task(" in f):
        found = directive.search(brief)
        assert found is None, (
            "a lens brief tells the agent to write something; the main loop owns the result "
            f"files (SPEC AC-011): {found.group(0)!r}"
        )


def test_a_missing_lens_is_redispatched_from_the_cli_missing_key(autofix_block: str) -> None:
    """The re-dispatch input must provably be the CLI's verdict, not the model's recollection.

    Round 3 killed the previous form, `"missing" in autofix_block`: `missing` is an ordinary
    English word and this very template already writes "reasoning is missing on one side" at
    Step 4, so the assertion could not distinguish "read the CLI's `missing` list" from any
    sentence mentioning a missing anything. Two anchors now: the key as a quoted identifier,
    and the CLI's own module name in the same block.
    """
    assert "lens_coverage" in autofix_block, (
        "the auto-fix loop re-dispatches without consulting the coverage CLI at all"
    )
    assert _names_cli_key(autofix_block, "missing"), (
        "the auto-fix loop does not name the CLI's `missing` key as its re-dispatch input; "
        "prose naming a missing lens leaves the model deciding which one"
    )


# ── AC-003: the approval condition, at every threshold ───────────────────────


@pytest.mark.parametrize("threshold", ["A", "B", "C"])
def test_approval_requires_both_conjuncts_at_every_threshold(
    tmp_path_factory: pytest.TempPathFactory, threshold: str
) -> None:
    """The defect this pins: expressed as a grade cap, the rule is inert at B and C.

    Both cross-model reviewers refuted the cap wording independently. Two weaker forms died
    first — see `_gate_conditions`, which is where the reasoning now lives. Asserted against the
    APPROVED arm's *condition* inside the pseudocode fence: prose cannot reach it, an
    explanatory comment cannot stand in for it, and a condition wrapped across lines passes.
    """
    out = _render(tmp_path_factory.mktemp(f"rendered-{threshold}"), grade_threshold=threshold)
    gate = _section(
        (out / "commands" / "hm" / "review.md").read_text(encoding="utf-8"),
        "## Grade Gate",
        stop="\n## ",
    )
    conditions = _gate_conditions(gate, "APPROVED")
    assert conditions, "no gate arm reaches APPROVED"
    assert all("grade_threshold" in c for c in conditions), (
        "an arm reaches APPROVED without testing the grade at all"
    )
    assert all("blocks_approval" in c for c in conditions), (
        "an arm reaches APPROVED without its condition reading the coverage verdict; a rule "
        f"stated only as a grade cap is inert at grade_threshold={threshold}"
    )


def test_the_gate_reports_which_lens_is_unexercised(gate_block: str) -> None:
    """A blocker the operator cannot attribute is not actionable.

    Round 3: `"missing" in gate_block` is an ordinary-English match over ~50 lines and passes
    against a gate that prints a bare boolean and never names a lens.

    Round 4: the quoted-identifier repair was not sufficient on its own either — backticks are
    markdown emphasis, so "say that a mandatory lens is `missing`" passed while reading no CLI
    output. The CLI's module name is the second anchor; together they can only be satisfied by
    a gate that consumes the verdict it reports.
    """
    assert "lens_coverage" in gate_block, (
        "AC-003: the gate reports a coverage blocker without referring to the CLI that produced it"
    )
    assert _names_cli_key(gate_block, "missing"), (
        "AC-003: the gate blocks without naming the unexercised lens — it does not read the "
        "coverage CLI's `missing` key"
    )


# ── AC-013: the terminal coverage blocker ────────────────────────────────────


def test_the_coverage_blocker_carries_lens_id_and_attempt_count(review_body: str) -> None:
    """Golden by construction: SPEC S2a fixes this wording before the template is written, and
    the machine SPEC's AC-013 predicate names the same string."""
    assert "did not deliver a result in" in review_body
    assert "attempts" in review_body


def test_budget_exhaustion_with_incomplete_coverage_requests_changes(gate_block: str) -> None:
    """S2a's Then: the stage terminates CHANGES_REQUESTED, not merely that a blocker is worded.

    Round 4: the previous form was a disjunction of two paragraph slices taken from the first
    occurrence of a phrase anywhere in the document. It failed both ways — one descriptive
    sentence greened it while the gate never branched on coverage, and a correct template that
    words the blocker in the report and sets the status in the gate (different paragraphs, and
    the shape the sibling absence test requires) stayed red. Scoped to the gate arm instead,
    which is where the terminal status is actually decided.
    """
    conditions = _gate_conditions(gate_block, "CHANGES_REQUESTED")
    assert conditions, "no gate arm reaches CHANGES_REQUESTED"
    assert any("blocks_approval" in c for c in conditions), (
        "no CHANGES_REQUESTED arm is guarded by the coverage verdict, so exhausting the "
        "round budget with an unexercised lens does not terminate the review"
    )


def test_the_coverage_blocker_is_not_emitted_as_an_ordinary_finding(report_block: str) -> None:
    """A delivery failure formatted as a finding sends auto-fix churning on it and never
    reaches the operator as terminal.

    Stated as an absence from the findings-report step, which is falsifiable, rather than as
    the presence of the word "distinct", which any sentence supplies.
    """
    assert "did not deliver a result" not in report_block, (
        "the coverage blocker is emitted from the findings-report step, where auto-fix will "
        "treat it as a fixable finding"
    )


# ── AC-005 (emission half) ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field",
    ["lenses_exercised", "confirm_pass_ran", "confirm_pass_new_severe_n"],
)
def test_the_telemetry_emit_field_list_carries_the_new_fields(
    telemetry_block: str, field: str
) -> None:
    """Scoped to the Emit block: a field named in a rationale paragraph elsewhere would
    satisfy a whole-body assertion while the emitted row omits it."""
    assert field in telemetry_block


#: Every `hm` module whose paths are worktree-relative, so an invocation of it that runs at the
#: base repo operates on the wrong tree. Membership is the point of the test below; a module added
#: here with no prefix in the template fails immediately.
_WORKTREE_RELATIVE_MODULES = (
    "freeze",
    "lens_coverage",
    "review_churn",
    "review_consensus",
    "stage_agent_ledger",
)


def _render_both_variants(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """The claude command AND the codex skill, rendered with worktree ON.

    Both, because the codex half is where the previous guard was blind: its offender predicate
    already had a `Bash("uv run` arm, and that arm was dead code because the test only ever read
    `commands/hm/review.md`, where `is_codex` is false. Six calls shipped unprefixed on the codex
    target under exactly that blind spot.

    Worktree ON, because the prefix renders as the empty string when it is off — a test written
    against the default fixture is green against the broken template.
    """
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    a.worktree["enabled"] = True
    a.targets = [Target.CLAUDE_CODE, Target.CODEX]
    out = tmp_path_factory.mktemp("wt-on")
    render(synthesize(p, a), out, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        "claude": (out / "commands" / "hm" / "review.md").read_text(encoding="utf-8"),
        "codex": (out / ".." / ".agents" / "skills" / "hm-review" / "SKILL.md")
        .resolve()
        .read_text(encoding="utf-8")
        if (out / ".." / ".agents" / "skills" / "hm-review" / "SKILL.md").exists()
        else "",
    }


def test_every_new_cli_call_runs_in_the_worktree(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Round-1 review P0, and its round-2 recurrence on the other target.

    Under `worktree.enabled: true` (the Production default) the review and its auto-fix edits
    happen inside `.worktrees/<slug>/`, while slash-command Bash starts at the project root.
    `freeze.py` defaults `--root` to `"."`, so an unprefixed `hm freeze commit` froze the BASE
    working tree — which contains none of the fixes the confirmation pass exists to examine.
    Refs are shared, so it printed a plausible commit and span, the lenses found nothing new,
    and the gate returned APPROVED. The fail-open this whole mechanism was built to close,
    reintroduced at the plumbing layer.

    Not one of this file's other tests could see it: they all assert what a command SAYS, and the
    defect was where it RUNS.
    """
    bodies = _render_both_variants(tmp_path_factory)
    offenders = [
        f"{variant}: {line.strip()}"
        for variant, body in bodies.items()
        for line in body.splitlines()
        if any(f"hm {m} " in line for m in _WORKTREE_RELATIVE_MODULES)
        and ("!uv run" in line or 'Bash("uv run' in line)
    ]
    assert not offenders, (
        "an invocation runs without the worktree prefix, so it operates on the base repo "
        f"instead of the tree under review: {offenders}"
    )


def test_the_codex_variant_is_actually_scanned(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Non-vacuity guard for the arm above.

    The previous version of that test carried a `Bash("uv run` predicate it could never exercise,
    so it read as covering both targets while covering one. If the codex body is empty or carries
    no invocations, the offender scan above is silently half-blind again.
    """
    bodies = _render_both_variants(tmp_path_factory)
    assert bodies["codex"], "the codex skill did not render, so the codex arm scans nothing"
    assert 'Bash("' in bodies["codex"]


# ── The seam that let round 1's P0 ship green: nothing bound the CLI to the render ──


def test_the_rendered_stage_invokes_review_consensus(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """`review_consensus` exists to be CALLED by the stage; nothing asserted that it is.

    This is the root cause of the round-1 P0 rather than one of its symptoms. Deleting all three
    calls and reverting Step 4 to prose failed exactly one test — a round-trip COUNT — whose
    message invites re-baselining the number, and a count is satisfied by any four calls. The
    module's own docstring states the contract as "the arithmetic lives here and the stage calls
    it"; the first half was thoroughly tested and the second half was not tested at all.
    """
    bodies = _render_both_variants(tmp_path_factory)
    for variant, body in bodies.items():
        calls = [ln for ln in body.splitlines() if "hm review_consensus finalize " in ln]
        assert calls, f"{variant}: the rendered stage never invokes `review_consensus finalize`"
        assert all("--file " in ln for ln in calls), f"{variant}: finalize invoked without --file"


def test_the_retired_chained_verbs_are_not_invoked(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """`tag`/`record`/`grade` were folded into one stateless verb; a caller of them is a revert.

    They chained by rewriting the findings file so each could see the previous one's column, and
    that write was the defect generator — file destruction, envelope loss, no containment on a
    model-substituted path, a `record` that went green on a blind retry. A rendered call to any of
    the three means the statefulness came back.
    """
    bodies = _render_both_variants(tmp_path_factory)
    offenders = [
        f"{variant}: {ln.strip()}"
        for variant, body in bodies.items()
        for ln in body.splitlines()
        for verb in ("tag", "record", "grade")
        if f"hm review_consensus {verb} " in ln
    ]
    assert not offenders, offenders


def test_finalize_is_invoked_exactly_once_per_site(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """One call, not three. Two calls over one path is the chaining coming back by another name."""
    bodies = _render_both_variants(tmp_path_factory)
    for variant, body in bodies.items():
        calls = [ln for ln in body.splitlines() if "hm review_consensus finalize " in ln]
        assert len(calls) == 1, f"{variant}: expected one finalize invocation, got {len(calls)}"


def test_the_rendered_stage_pins_both_churn_endpoints_and_measures_between_them(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Measurement that is never invoked measures nothing (Phase 5).

    Both pins are asserted, not just the `measure`: with only the post pin the `--pre` ref
    would resolve to a stale endpoint from an earlier round — the ratio would still be a
    number, and a call-count assertion would still pass. The `--pre`/`--post` refs are
    asserted to name the SAME round as the pins for the same reason: a measure spanning
    r1-pre..r2-post is well-formed, wrong, and silent.
    """
    bodies = _render_both_variants(tmp_path_factory)
    for variant, body in bodies.items():
        assert "hm review_churn pin --slug {slug} --label r{N}-pre" in body, (
            f"{variant}: the pre-fix endpoint is never pinned"
        )
        assert "hm review_churn pin --slug {slug} --label r{N}-post" in body, (
            f"{variant}: the post-fix endpoint is never pinned"
        )
        measures = [ln for ln in body.splitlines() if "hm review_churn measure " in ln]
        assert len(measures) == 1, f"{variant}: expected one measure call, got {len(measures)}"
        assert "--pre refs/hm-churn/v1/{slug}-r{N}-pre" in measures[0], measures[0]
        assert "--post refs/hm-churn/v1/{slug}-r{N}-post" in measures[0], measures[0]


def test_the_churn_gate_is_a_render_time_branch_with_a_working_off_switch(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Phase 5 asserted the stage did NOT read the gate key; Phase 6 ships the read.

    That guard was a phase boundary, and this is what it becomes — retired in the phase
    that legitimately crosses it rather than left to fail as noise. The invariant that
    survives is the one worth keeping: the gate is resolved at RENDER time, so
    `rereview_churn_gate: false` produces the pre-gate text rather than a runtime flag the
    prose merely mentions. `tests/unit/test_review_churn_gate.py` asserts the off-render
    directly; here we only require the on-render to carry the branch.
    """
    bodies = _render_both_variants(tmp_path_factory)
    for variant, body in bodies.items():
        assert "Re-review (gated" in body, f"{variant}: the gate branch is not rendered"
        assert "as if the gate were off" in body, (
            f"{variant}: the null-ratio case is not stated, so an unmeasurable round "
            "reads as below-threshold and is silently skipped"
        )
