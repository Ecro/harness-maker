"""Phase 6 of PLAN-token-efficiency-autopilot-ux-speed — AC-010.

Every name a rendered `harness.yaml` enables must resolve to something that exists: a skill name to
a `templates/skills/<name>/` directory, a reviewer name to a rendered `.claude/agents/<name>.md`.

**Resolution, not containment.** `synthesize.py:3-5` installs the full inventory unconditionally, so
the sibling `installed` list is *descriptive*: a containment check `enabled ⊆ installed` is
satisfiable by adding a phantom to `installed`, where it still resolves to no template. Resolution
is against the actual inventory, so it cannot be satisfied that way.

**This AC is a regression guard, not a repair, and it passes on arrival.** The SPEC claimed two live
phantoms (`relevance-filter`, `research-crawler`); measured, both were removed in 0.22.3 and survive
only in comments, so no producer-emitted config contains them. That premise is corrected in the
SPEC. The killer is demonstrated explicitly by `test_ac_010_a_phantom_name_is_caught`, which injects
a name that resolves to nothing and asserts the predicate rejects it — without that arm, a green
resolution test proves only that the loop ran.

**The fixtures are producer-emitted lists, not a bare `InterviewAnswers`.** A bare one yields
`skills.enabled` of length 1 and `reviewers.enabled` empty — values `interview()` never writes.
Phase 5's A.5 round 1 killed a test built on exactly that mistake.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import interview as iv
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ROOT = Path(__file__).parents[2]
_SKILL_TEMPLATES = _ROOT / "src" / "harness_maker" / "templates" / "skills"

#: The producer's own per-preset lists — `interview()` writes exactly these.
_PRESET_LISTS: dict[Preset, tuple[list[str], list[str]]] = {
    Preset.PRODUCTION: (iv._PROD_ENABLED_SKILLS, iv._PROD_ENABLED_REVIEWERS),
    Preset.SIDE: (iv._SIDE_ENABLED_SKILLS, iv._SIDE_ENABLED_REVIEWERS),
}


def _render_for(
    preset: Preset,
    tmp: Path,
    *,
    extra_skill: str | None = None,
    extra_reviewer: str | None = None,
) -> Path:
    """Both phantom hooks exist because both halves need a negative control.

    A.5 round 1: the first version had `extra_skill` only, so the reviewer half — the one the SPEC
    says "a containment check would report green with zero work" — had no control at all.
    """
    skills, reviewers = _PRESET_LISTS[preset]
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=preset,
                targets=[Target.CLAUDE_CODE],
                skills={
                    "installed": (
                        [*iv._ALL_SKILLS, extra_skill] if extra_skill else list(iv._ALL_SKILLS)
                    ),
                    "enabled": [*skills, extra_skill] if extra_skill else list(skills),
                },
                reviewers={
                    "installed": (
                        [*iv._ALL_REVIEWERS, extra_reviewer]
                        if extra_reviewer
                        else list(iv._ALL_REVIEWERS)
                    ),
                    "enabled": [*reviewers, extra_reviewer] if extra_reviewer else list(reviewers),
                },
            ),
        ),
        tmp,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return tmp


def _enabled(out: Path) -> dict[str, set[str]]:
    """Read both `enabled` lists from the rendered artifact, and REFUSE an empty one.

    `.get(...) or []` silently converts a renamed key, an emptied preset list, or a synthesize that
    stops threading reviewers into "nothing unresolved" — the subtraction below then compares
    `set() - anything` and reports green while checking nothing. A.5 round 1 named this the vacuity
    hole, and the yaml template emits `enabled:` followed by a loop, so an empty list renders a key
    whose value is `None`: exactly the shape that would be swallowed.
    """
    cfg = load_harness_yaml(out / "harness.yaml")
    out_map: dict[str, set[str]] = {}
    for kind in ("skills", "reviewers"):
        names = cfg.get(kind, {}).get("enabled")
        assert names, (
            f"the rendered harness.yaml has no {kind}.enabled entries, so the resolution check "
            "below would pass vacuously — the key was renamed, or the preset list is empty"
        )
        out_map[kind] = set(names)
    return out_map


def _unresolved(out: Path) -> dict[str, list[str]]:
    """The predicate under test: names in `enabled` that resolve to no asset."""
    enabled = _enabled(out)
    skill_dirs = {p.name for p in _SKILL_TEMPLATES.iterdir() if p.is_dir()}
    rendered_agents = {p.stem for p in (out / "agents").glob("*.md")}
    return {
        "skills": sorted(enabled["skills"] - skill_dirs),
        "reviewers": sorted(enabled["reviewers"] - rendered_agents),
    }


@pytest.mark.parametrize("preset", sorted(_PRESET_LISTS, key=lambda p: p.value))
def test_ac_010_every_enabled_name_resolves_to_a_real_asset(preset: Preset, tmp_path: Path) -> None:
    """Both presets, because `_SIDE_ENABLED_SKILLS` is a different list and could drift alone."""
    out = _render_for(preset, tmp_path)

    unresolved = _unresolved(out)

    assert unresolved["skills"] == [], (
        f"{preset.value}: skills.enabled names resolve to no templates/skills/<name>/ directory: "
        f"{unresolved['skills']}"
    )
    assert unresolved["reviewers"] == [], (
        f"{preset.value}: reviewers.enabled names resolve to no rendered agent: "
        f"{unresolved['reviewers']}"
    )


def test_ac_010_a_phantom_name_is_caught(tmp_path: Path) -> None:
    """The killer, demonstrated rather than asserted.

    Without this arm the test above proves only that the sets were compared, not that a mismatch
    would be seen — and the AC ships already-green, so there is no natural RED to lean on. The
    phantom goes into **both** `installed` and `enabled`, which is precisely the shape a containment
    check would call fine: `enabled ⊆ installed` holds, and the name still resolves to nothing.
    """
    phantom = "relevance-filter"  # the name the SPEC believed was live; removed in 0.22.3
    assert not (_SKILL_TEMPLATES / phantom).exists(), (
        f"{phantom} now exists as a template, so it is no longer a phantom — pick another name"
    )

    out = _render_for(Preset.PRODUCTION, tmp_path, extra_skill=phantom)

    assert _unresolved(out)["skills"] == [phantom], (
        "the predicate did not reject a name that resolves to no template, so its green verdict on "
        "the real config means nothing"
    )


def test_ac_010_a_phantom_reviewer_is_caught(tmp_path: Path) -> None:
    """The reviewer half's negative control — the half a containment check calls green for free.

    `phantom-reviewer` goes into both `installed` and `enabled`, so `enabled ⊆ installed` holds and
    only resolution against the rendered agents rejects it. There is no `agents/phantom-reviewer.md`
    template, so `synthesize` cannot render one: the name reaches `harness.yaml` and resolves to
    nothing, which is the shape AC-010 exists to catch.
    """
    phantom = "phantom-reviewer"
    out = _render_for(Preset.PRODUCTION, tmp_path, extra_reviewer=phantom)

    assert _unresolved(out)["reviewers"] == [phantom], (
        "the predicate did not reject a reviewer that resolves to no rendered agent"
    )


def test_ac_010_enabled_is_contained_in_installed(tmp_path: Path) -> None:
    """Not the AC's invariant — an adjacent truth defect the AC's measurement surfaced.

    `installed` is rendered into `harness.yaml` as a claim about what the harness ships. It has no
    validating consumer (`cli.py` mutates only `enabled`), so an omission breaks nothing — which is
    exactly why nothing caught `test-reviewer` being enabled on Production while absent from
    `_ALL_REVIEWERS`. A config surface that under-reports what is installed is this unit's own
    defect class, so it is asserted here rather than left as a comment.
    """
    for name, enabled, installed in (
        ("skills", iv._PROD_ENABLED_SKILLS, iv._ALL_SKILLS),
        ("skills-side", iv._SIDE_ENABLED_SKILLS, iv._ALL_SKILLS),
        ("reviewers", iv._PROD_ENABLED_REVIEWERS, iv._ALL_REVIEWERS),
        ("reviewers-side", iv._SIDE_ENABLED_REVIEWERS, iv._ALL_REVIEWERS),
    ):
        missing = sorted(set(enabled) - set(installed))
        assert missing == [], f"{name}: enabled but not listed as installed: {missing}"

    # …and over the ARTIFACT, because the constants are the producer and the claim is what ships.
    # A template-side omission of `installed` is invisible to the loop above (A.5 round 1,
    # ADVISORY-6): the docstring says "rendered into harness.yaml as a claim", so read it there.
    out = _render_for(Preset.PRODUCTION, tmp_path)
    cfg = load_harness_yaml(out / "harness.yaml")
    for kind in ("skills", "reviewers"):
        shipped_installed = set(cfg.get(kind, {}).get("installed") or [])
        assert shipped_installed, f"the rendered harness.yaml has no {kind}.installed to check"
        orphans = sorted(set(cfg[kind]["enabled"]) - shipped_installed)
        assert orphans == [], (
            f"{kind}: the rendered harness.yaml enables names it does not list as installed: "
            f"{orphans}"
        )
