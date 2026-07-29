"""Phases 2–5 — the collapses reach the rendered surface, on the right targets only.

Every assertion here is scoped to the ONE rendered artifact a given consumer reads.
That scoping is the point, twice over:

* `.cursor/commands/` is dead code (`render.py:585-597` — no template feeds it), so
  **Cursor reads the Claude render**. A fan-out gated on `"claude-code" in targets`
  would therefore ship Cursor a `Task(subagent_type="Explore")` it cannot resolve — the
  CLAUDE.md checklist-#2 failure class where the file on disk is right and only the
  executed content differs. The gate is `cursor not in targets`, and the test that
  matters is the one that renders WITH cursor and asserts the dispatch is absent.
* Phase D and Phase C sit outside every `dev_mode` gate, so both arms are rendered and
  compared: a collapse that reached one arm only is the defect the per-arm instruction
  baseline exists to catch.
"""

from __future__ import annotations

import re
import tempfile
from functools import cache
from pathlib import Path

import pytest

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref

_BANG = re.compile(r"^!", re.M)


@cache
def _commands(
    targets: tuple[Target, ...], dev_mode: DevMode = DevMode.TASK_DRIVEN
) -> dict[str, str]:
    """The `.claude/commands/hm/*.md` bodies — what Claude Code AND Cursor both read."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / ".claude"
        out.mkdir()
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(
                        preset=Preset.PRODUCTION,
                        targets=list(targets),
                        dev_mode=dev_mode,
                        worktree={"feature_branch_workflow": True},
                    ),
                ),
                out,
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        return {p.stem: p.read_text(encoding="utf-8") for p in sorted(out.glob("commands/hm/*.md"))}


@cache
def _codex_skills(targets: tuple[Target, ...]) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(preset=Preset.PRODUCTION, targets=list(targets)),
                ),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        return {
            p.parent.name: p.read_text(encoding="utf-8")
            for p in sorted((root / ".agents" / "skills").glob("hm-*/SKILL.md"))
        }


_CLAUDE_ONLY = (Target.CLAUDE_CODE,)
_WITH_CURSOR = (Target.CLAUDE_CODE, Target.CURSOR)
_WITH_CODEX = (Target.CLAUDE_CODE, Target.CODEX)


# ── positive control ───────────────────────────────────────────────────────────


def test_the_render_helper_produces_the_seven_atomic_commands() -> None:
    """Without this, every `not in` assertion below would pass on an empty render."""
    cmds = _commands(_CLAUDE_ONLY)
    for stage in ("research", "spec", "plan", "execute", "review", "verify", "wrapup"):
        assert stage in cmds, f"{stage} did not render"
        assert len(cmds[stage]) > 2000


# ── Phase 4 — execute Phase C per-file + Phase D select-then-one-call ───────────


@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_phase_c_checks_per_file_not_per_edit(dev_mode: DevMode) -> None:
    body = _commands(_CLAUDE_ONLY, dev_mode)["execute"]
    assert "Type-check once per FILE" in body
    assert "Compile / type-check after each edit" not in body, (
        "the per-edit rule survived — that is the cost being cut"
    )


@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_phase_d_issues_one_combined_check_call(dev_mode: DevMode) -> None:
    body = _commands(_CLAUDE_ONLY, dev_mode)["execute"]
    assert "hm test_dep_map --root ." in body
    assert "<lint> && <type> && <test>" in body
    for gone in ("!cd <WT> && <lint command>", "!cd <WT> && <type command>"):
        assert gone not in body, f"the three-call form survived: {gone}"


def test_phase_d_collapse_also_reaches_the_codex_render() -> None:
    """Codex gets the same collapse in its own `Bash(...)` form, not the Claude one."""
    body = _codex_skills(_WITH_CODEX)["hm-execute"]
    assert 'Bash("cd <WT> && uv run' in body
    assert "hm test_dep_map --root ." in body
    assert "!cd <WT> && <lint command>" not in body


# ── Phase 5 — research fan-out, Claude-only ────────────────────────────────────


def test_the_fan_out_renders_when_claude_is_the_only_reader() -> None:
    body = _commands(_CLAUDE_ONLY)["research"]
    assert body.count('Task(subagent_type="Explore"') == 3
    assert "SINGLE message" in body
    assert "verbatim snippet" in body, "the citation contract is what makes a digest usable"


def test_the_fan_out_is_absent_when_cursor_shares_the_claude_render() -> None:
    """The load-bearing case: Cursor reads THIS file and cannot resolve `Explore`."""
    body = _commands(_WITH_CURSOR)["research"]
    assert "Explore" not in body
    assert "Run these in parallel where the answers are independent" in body


def test_the_fan_out_is_absent_from_the_codex_render() -> None:
    body = _codex_skills(_WITH_CODEX)["hm-research"]
    assert "Explore" not in body


@pytest.mark.parametrize("targets", [_CLAUDE_ONLY, _WITH_CURSOR])
def test_every_source_class_survives_in_both_renders(targets: tuple[Target, ...]) -> None:
    """Redistributed, not deleted — a fan-out that loses source classes is a regression."""
    body = _commands(targets)["research"]
    for marker in (
        "Codebase patterns",
        "Prior-art search in memory",
        "Prior PLANs / REVIEWs",
        "User-workflow / product discovery",
        "Library / framework docs",
        "Web search",
        "Refdocs folders",
    ):
        assert marker in body, f"source class lost: {marker}"


def test_every_dispatched_agent_resolves_on_the_target_that_gets_it() -> None:
    """The general form of the bug: a render-grep for presence would pass on an unresolvable name.

    `Explore` is a Claude Code built-in; every OTHER dispatched type must be an agent this
    harness actually renders.
    """
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / ".claude"
        out.mkdir()
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
                ),
                out,
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        rendered_agents = {p.stem for p in (out / "agents").glob("*.md")}
        builtins = {"Explore"}
        dispatched = set()
        for cmd in (out / "commands" / "hm").glob("*.md"):
            dispatched |= set(
                re.findall(r'subagent_type="([\w-]+)"', cmd.read_text(encoding="utf-8"))
            )
    assert dispatched, "no dispatches found — the regex is stale and this asserts nothing"
    unresolvable = dispatched - rendered_agents - builtins
    assert not unresolvable, f"dispatched to agent(s) that do not resolve: {sorted(unresolvable)}"


# ── Phase 3 — spec Steps 4/4.5 collapse ────────────────────────────────────────


def test_spec_issues_one_check_call_instead_of_three() -> None:
    body = _commands(_CLAUDE_ONLY)["spec"]
    assert "hm spec_machine check --all" in body
    assert "hm spec_machine validate" not in body
    assert "from harness_maker.spec_machine import cross_validate" not in body
    assert "hm spec_quality eval" not in body


def test_spec_still_documents_all_six_cross_validate_rules() -> None:
    body = _commands(_CLAUDE_ONLY)["spec"]
    for n in range(1, 7):
        assert f"\n{n}. " in body or f"rule-{n}" in body


# ── Phase 2 — wrapup Steps 6 → 7.6 collapse ────────────────────────────────────


def test_wrapup_issues_one_land_call_for_steps_6_through_7_6() -> None:
    body = _commands(_CLAUDE_ONLY)["wrapup"]
    assert "hm wrapup_land" in body
    for gone in (
        "hm worktree post-commit-pop",
        "hm worktree drain",
        "hm worktree owned-crumb-read",
    ):
        assert gone not in body, f"a swallowed step is still its own call: {gone}"


def test_wrapup_keeps_task_land_as_its_own_visible_call() -> None:
    """ADR-006 — the only step that can lose work keeps its own operator decision point."""
    body = _commands(_CLAUDE_ONLY)["wrapup"]
    assert "hm worktree task-land" in body
    assert "hm worktree commit-base-memory" in body


def test_the_wrapup_git_tail_is_three_calls() -> None:
    """`wrapup_land` + `task-land` + `commit-base-memory`, and nothing else in between.

    Sliced to Steps 6 → 7.7 exactly. Slicing "to the end of the file" would sweep in Step
    8's push, the Gate-0 receipt guard and the two autopilot calls — shared blocks present
    in every stage command, outside this PLAN's scope and not part of the git tail.
    """
    body = _commands(_CLAUDE_ONLY)["wrapup"]
    tail = body[body.index("### Steps 6 → 7.6") : body.index("### Step 8")]
    assert len(_BANG.findall(tail)) == 3, _BANG.findall(tail)


def test_wrapup_carries_the_stash_preview_obligation_into_the_prose() -> None:
    """The abort text is where a reader reaches for `drop`; the contract has to be there."""
    body = _commands(_CLAUDE_ONLY)["wrapup"]
    assert "git stash show -p" in body


def test_the_manifest_marks_plan_required_and_review_optional() -> None:
    body = _commands(_CLAUDE_ONLY)["wrapup"]
    assert re.search(r"--required \S*PLAN-\{slug\}\.md", body)
    assert re.search(r"--optional \S*REVIEW-\{slug\}-\*\.md", body)
