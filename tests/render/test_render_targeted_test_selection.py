"""PLAN-dep-map-alias-imports Phase 3 — the `targeted-test-selection` skill.

The skill exists because `review.md.j2` cannot grow: `test_aggregate_shipped_surface_does_not_grow`
is a STRICT non-increase over the summed command surface, frozen at HEAD, so the headroom
is zero and the recipe is ~700 characters. Skills are outside that sum (the codex arm
globs `hm-*/SKILL.md`, which this name does not match), so the recipe can be explicit
there — which is the point: every part a character budget would have cut is a part whose
absence ships as a silent skip.

These are render-greps and are honest about it (CLAUDE.md checkpoint 2): they prove the
instruction is PRESENT, never that an LLM follows it. What keeps them from being
decorative is `test_the_operative_predicates_discriminate`, which asserts the same
predicates are FALSE against a sibling skill — without it, a predicate true of every
document would pass.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_SKILL = "targeted-test-selection"


def _profile(preset: Preset) -> ProjectProfile:
    return (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )


@cache
def _render_root(preset: Preset) -> Path:
    """Render once per preset for the whole module — a full render is not cheap.

    Populated lazily from inside a test, so `tests/render/conftest.py`'s autouse
    install-ref pin is already in effect (`[fail:test] snapshot-regen-inside-worktree`
    instance 13 — a render captured outside the pin bakes the checkout's absolute path).
    """
    profile = _profile(preset)
    answers = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, answers, preset=preset)
    out = Path(mkdtemp(prefix="hm-targeted-selection-"))
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _skill_body(preset: Preset) -> str:
    return (_render_root(preset) / "skills" / _SKILL / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
def test_the_skill_renders_for_both_presets(preset: Preset) -> None:
    """Rejects registering the skill in `synthesize` but not rendering it."""
    assert (_render_root(preset) / "skills" / _SKILL / "SKILL.md").is_file()


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
def test_the_skill_is_enabled_in_both_presets(preset: Preset) -> None:
    """Side must ENABLE it, not merely install it.

    `review.md.j2`'s verify step points at this skill from an UNGUARDED line — there is
    no `{% if %}` around it — so a Side harness that installs the skill without enabling
    it leaves that pointer dangling. This is the same trap `second-opinion-gate` documents
    in `interview._ALL_SKILLS`, and the failure is silent: the render succeeds and the
    reference resolves to nothing at use time.

    Rejects adding the name to `_ALL_SKILLS` only.
    """
    answers = interview(_profile(preset), autoloop_mode=True)
    assert _SKILL in answers.skills["installed"]
    assert _SKILL in answers.skills["enabled"]


def test_the_recipe_carries_every_part_a_character_budget_would_have_cut() -> None:
    """The four operative parts of ADR-004, each a silent-skip bug when absent.

    Rejects a compressed inline-shaped recipe: dropping the untracked union makes a
    fix that ADDS a file invisible; dropping `-z` mangles this repo's Korean-named
    paths into non-existent ones; dropping the empty-set instruction means the
    `select_tests` guard never runs because the CLI is never called; dropping the
    worktree scoping selects from the base tree while the fixes sit in the worktree.
    """
    body = _skill_body(Preset.PRODUCTION)
    assert "hm test_dep_map --root . --changed-file" in body
    assert "uv run --with" in body
    assert "git diff -z --name-only HEAD" in body
    assert "git ls-files -z --others --exclude-standard" in body
    assert "the task worktree" in body
    # The empty-set branch. `"zero" in body` was the earlier form and it held against a
    # §3 rewritten to say the OPPOSITE ("skip when zero files changed") — invariant over
    # the dimension it names. These pin the operative instruction instead.
    assert "run the command from §2 anyway" in body
    assert "honour the `mode: full`" in body
    # The argv form: `=`-attached and quoted. A `-`-leading path makes the separate-token
    # form exit 2 with no JSON; an unquoted path with a space splits into two argv entries.
    assert "--changed-file='<f1>'" in body
    # The failure arm — without it, exit 2 lands in a branch the recipe does not define.
    # Matched on a phrase that sits within ONE source line: the sentence that follows it
    # wraps in the template, so a longer literal would fail on the newline + indent.
    assert "non-zero exit, no output, or output that is not JSON" in body


def test_command_lines_carry_no_slash_command_bang_prefix() -> None:
    """A leading `!` is inert inside a SKILL body.

    `!` marks an executable line in a slash COMMAND; a skill is loaded as reference
    prose, so the marker buys nothing and misreports the line's status to any gate keyed
    on `^!`. `second-opinion-gate/SKILL.md.j2` sets the precedent (plain `cd … && uv run
    …`, no bang). Rejects copying execute Phase D's command shape verbatim.
    """
    body = _skill_body(Preset.PRODUCTION)
    offenders = [ln for ln in body.splitlines() if ln.startswith("!")]
    assert offenders == [], f"bang-prefixed lines in a skill body: {offenders}"


def test_the_operative_predicates_discriminate() -> None:
    """The predicates above are false of a sibling skill.

    Without this, a predicate satisfied by every rendered document — or by an empty
    string — would pass `test_the_recipe_carries_every_part…` while proving nothing.
    """
    other = (
        _render_root(Preset.PRODUCTION) / "skills" / "verify-before-completion" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "hm test_dep_map --root . --changed-file" not in other
    assert "git ls-files -z --others --exclude-standard" not in other


def test_the_rendered_skill_is_within_the_context_lint_cap() -> None:
    """Production caps SKILL.md at 150 lines; the renderer only warns, so assert it."""
    lines = _skill_body(Preset.PRODUCTION).splitlines()
    assert len(lines) <= 150, f"{_SKILL} SKILL.md is {len(lines)} lines (cap 150)"
