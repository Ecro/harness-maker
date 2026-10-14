"""HM-LIGHT-LANE — small single-session tasks take a light lane through spec, execute and review.

On the 2026-10-14 bench (work-docs/RESEARCH-hm-light-lane.md) the full pipeline cost x22 a plain
run on single-session tasks with no hidden-test gain, and both of its failures were Phase A.5
self-blocks. The lane is decided once, in spec Step 0, and carried in the SPEC frontmatter.

What must hold: the deterministic oracles (Phase A tests, A.4, Phase B) and the review lens axis
survive the light lane; only A.5 and review repetition go. A SPEC without `lane:` reads as `full`,
so every SPEC written before this change keeps the full pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def bodies(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    out = tmp_path_factory.mktemp("rendered-light-lane")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(synthesize(p, interview(p, autoloop_mode=True)), out, freeze_time=DEFAULT_FREEZE_TIME)
    rendered = {
        stage: (out / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")
        for stage in ("spec", "execute", "review")
    }
    # Production, for review's Pass 1, which renders only with several enabled reviewers.
    from harness_maker.interview import _build_answers

    other = tmp_path_factory.mktemp("rendered-light-lane-prod")
    answers = _build_answers(locale="en", targets=[Target.CLAUDE_CODE], preset=Preset.PRODUCTION)
    render(
        synthesize(ProjectProfile(), answers, preset=Preset.PRODUCTION),
        other,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    rendered["review@other"] = (other / "commands" / "hm" / "review.md").read_text(encoding="utf-8")
    return rendered


def _section(body: str, start: str, stop: str) -> str:
    i = body.find(start)
    assert i != -1, f"missing anchor {start!r}"
    j = body.find(stop, i + len(start))
    assert j != -1, f"missing end anchor {stop!r} after {start!r}"
    return body[i:j]


def test_spec_step_0_decides_the_lane_and_writes_it(bodies: dict[str, str]) -> None:
    step0 = _section(bodies["spec"], "### Step 0 —", "### Step 0.5")
    assert "`lane: light`" in step0, "the trivial skip path must be light, not unset (= full)"
    # The skip paragraph above already says "irreversible" and "Refinement Decisions"; anchor on
    # the lane paragraph so its three conditions and its log obligation are what is pinned.
    lane = _section(step0, "**Not skipped → pick the lane.**", "On `light`, Step 2")
    assert "about five files or fewer, one session, and no irreversible decision" in lane
    assert "Otherwise, or in doubt, `full`" in lane
    assert "one-line reason to Refinement Decisions" in lane


def test_light_spec_keeps_the_oracle_irreversible_list_and_approval(bodies: dict[str, str]) -> None:
    """One round must still elicit the oracle and list irreversible decisions, and must offer the
    only approval, or every light SPEC ends unstamped and autopilot stops at spec."""
    body = bodies["spec"]
    step0 = _section(body, "**Not skipped → pick the lane.**", "### Step 0.5")
    assert "the 2.1.5 oracle and the irreversible-decision" in step0
    # Approval must follow the content it binds, never sit beside the questions producing it.
    assert (
        "one closing question that shows the drafted oracle, the list and the lane and offers"
        in step0
    )
    assert "From Round 2 onward (on `light`, the closing question)" in body
    assert "A non-empty list turns `lane: light`\ninto `full` before Step 3 writes it" in body


def test_spec_frontmatter_carries_the_lane(bodies: dict[str, str]) -> None:
    step3 = _section(bodies["spec"], "### Step 3 —", "### Step 3.5")
    assert "lane: {light | full}" in step3


def test_execute_skips_only_a5_on_light(bodies: dict[str, str]) -> None:
    body = bodies["execute"]
    a5 = _section(body, "#### Phase A.5", "#### Phase B")
    assert "`lane: light` → skip to Phase B" in a5
    assert "A, A.4 and B are the deterministic oracles" in a5, "the survivors must be named"
    # A deliberate skip has no retry: terminal, or the run reads as incomplete in the ledger.
    assert "`--pass 1 --verdict dispatch-skipped --reason 'lane light' --terminal`" in a5
    # A.4 and Phase B are untouched: no lane clause inside them.
    assert "lane" not in _section(body, "#### Phase A.4", "#### Phase A.5")
    assert "lane" not in _section(body, "#### Phase B", "#### Phase C.0")


def test_execute_quality_bar_admits_the_light_lane(bodies: dict[str, str]) -> None:
    assert "PASS (or `--no-tdd` was set, or `lane: light`)" in bodies["execute"]


def test_execute_reads_a_missing_lane_as_full(bodies: dict[str, str]) -> None:
    step2 = _section(bodies["execute"], "### Step 2 —", "### Step 3 —")
    assert "missing → `full`" in step2
    # Only the exact value lowers a gate; a typo must fail closed.
    assert "any value but exactly `light` is `full`" in step2
    # The spec-time guess is re-checked once the PLAN exists.
    assert "touch well over five files reads as `full`" in step2


def test_review_light_lane_keeps_the_lens_axis_and_gate(bodies: dict[str, str]) -> None:
    body = bodies["review"]
    config = _section(body, "## Configuration", "## Procedure")
    assert "`lane: light`" in config
    assert "keeps the lens axis, coverage check and" in config
    assert "missing → `full`" in config
    assert "a diff well over five files reads as `full`" in config
    assert "any value but exactly `light`" in config
    assert "`max_review_rounds` caps at 2" in config
    assert "default `3`; at most `2` on `lane: light`" in config, "the cap sits at the knob"


def test_review_light_lane_skips_pass_1_and_the_unchanged_confirmation(
    bodies: dict[str, str],
) -> None:
    body = bodies["review"]
    # Pass 1 renders only with more than one enabled reviewer; with one, review is already
    # single-pass and the clause has nothing to skip. At least one preset must render it.
    two_pass = [b for b in (body, bodies["review@other"]) if "#### Pass 1 —" in b]
    assert two_pass, "no preset renders Pass 1 — this assertion would be vacuous"
    for b in two_pass:
        assert "`lane: light` → the Round 1 dispatch above is the only one" in b
        assert "then skip Pass 1 and Pass 2" in b
    confirm = _section(body, "## Confirmation Pass", "### Step C1")
    assert "`lane: light` with round 1 approved and no fix applied" in confirm
    # Skipping C3 must not leak the open run or the round-1 freeze ref into the next review.
    assert (
        "run `hm freeze reap --slug <slug>`, then close the run (`--outcome APPROVED`)" in confirm
    )
    assert "read it from the SPEC frontmatter before Step 1" in body
    gate = _section(body, "## Grade Gate", "## Auto-Fix Loop")
    assert "each close below runs `hm freeze reap --slug <slug>` first" in gate


# ── lever 5: typed-only skills and commands leave the always-loaded listing ────────────────

_HIDDEN_SKILLS = (
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "autoloop-driver",
    "context-linter",
    "worktree-isolator",
)
#: Each is reached by name from a stage prompt or is meant to self-trigger, so hiding it would
#: silently break that path.
_VISIBLE_SKILLS = (
    "second-opinion-gate",
    "targeted-test-selection",
    "verify-before-completion",
    "security-scanner",
)
_HIDDEN_COMMANDS = ("make", "configure", "uninstall", "help", "metrics")
#: Rendered only with `loop.enabled`; covered by their own fixture below.
_HIDDEN_LOOP_COMMANDS = ("loop", "loop-p5-batch")
_VISIBLE_COMMANDS = ("health", "spec", "execute", "review", "verify", "wrapup", "research")


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered-lever5")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(synthesize(p, interview(p, autoloop_mode=True)), out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    return text.split("\n---\n", 1)[0]


@pytest.mark.parametrize("name", _HIDDEN_SKILLS)
def test_internal_skill_is_typed_only(tree: Path, name: str) -> None:
    assert "disable-model-invocation: true" in _frontmatter(tree / "skills" / name / "SKILL.md")


@pytest.mark.parametrize("name", _VISIBLE_SKILLS)
def test_skill_reached_by_name_stays_invocable(tree: Path, name: str) -> None:
    assert "disable-model-invocation" not in _frontmatter(tree / "skills" / name / "SKILL.md")


@pytest.mark.parametrize("name", _HIDDEN_COMMANDS)
def test_user_typed_command_is_typed_only(tree: Path, name: str) -> None:
    fm = _frontmatter(tree / "commands" / "hm" / f"{name}.md")
    assert "disable-model-invocation: true" in fm
    assert "description:" in fm, "users still see the description in the / menu"


@pytest.mark.parametrize("name", _VISIBLE_COMMANDS)
def test_stage_and_health_commands_stay_invocable(tree: Path, name: str) -> None:
    """Auto-advance runs stages through the Skill tool; verify Check 2 runs /hm:health."""
    assert "disable-model-invocation" not in _frontmatter(tree / "commands" / "hm" / f"{name}.md")


@pytest.fixture(scope="module")
def loop_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from harness_maker import models

    out = tmp_path_factory.mktemp("rendered-lever5-loop")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"loop": models.LoopConfig(enabled=True)}
    )
    render(synthesize(p, a), out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


@pytest.mark.parametrize("name", _HIDDEN_LOOP_COMMANDS)
def test_loop_commands_are_typed_only(loop_tree: Path, name: str) -> None:
    fm = _frontmatter(loop_tree / "commands" / "hm" / f"{name}.md")
    assert "disable-model-invocation: true" in fm


def test_the_typed_only_command_set_is_exactly_these() -> None:
    from harness_maker.synthesize import _TYPED_ONLY_COMMANDS

    names = _HIDDEN_COMMANDS + _HIDDEN_LOOP_COMMANDS
    assert {f"commands/hm/{n}.md" for n in names} == _TYPED_ONLY_COMMANDS


def test_codex_renders_the_policy_for_exactly_the_hidden_skills() -> None:
    from harness_maker.interview import _build_answers

    answers = _build_answers(
        locale="en", targets=[Target.CLAUDE_CODE, Target.CODEX], preset=Preset.SIDE
    )
    paths = {str(f.path) for f in synthesize(ProjectProfile(), answers, preset=Preset.SIDE).files}
    policy = "/agents/openai.yaml"
    for name in _HIDDEN_SKILLS:
        assert f".agents/skills/{name}{policy}" in paths, name
    for name in _VISIBLE_SKILLS:
        assert f".agents/skills/{name}{policy}" not in paths, name
