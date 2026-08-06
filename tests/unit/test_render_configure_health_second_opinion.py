"""Render contract for the `/hm:configure` recovery entries and the `/hm:health` advisory.

PLAN-onboarding-interview-ux P1-5 / P1-6. Two separate failure modes are pinned:

* An axis silently defaulted at install had no guided way to be turned on afterwards —
  `/hm:configure` named neither `second_opinion`, `autonomy`, nor `locale`.
* `/hm:health`'s second-opinion smoke was gated on the axis already being ON, so the common
  state "the CLI is installed but nothing ever asks it" was silent for its whole lifetime.

The advisory's byte cost is invisible to `test_aggregate_shipped_surface_does_not_grow`,
because the surface baseline renders THIS repo's harness, whose `second_opinion.models` is
non-empty — so the block is absent from what the ratchet measures (ADR-005). These render
fixtures are the only thing that proves it works at all.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import (
    AutonomyConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(
    tmp_path: Path,
    *,
    models: list[str],
    level: str = "gated",
) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            second_opinion=SecondOpinionConfig(models=models),  # type: ignore[arg-type]
            autonomy=AutonomyConfig(level=level),  # type: ignore[arg-type]
        ),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        str(f.relative_to(tmp_path)): f.read_text(encoding="utf-8") for f in tmp_path.rglob("*.md")
    }


def _cmd(files: dict[str, str], name: str) -> str:
    key = f"commands/hm/{name}.md"
    assert key in files, sorted(files)
    return files[key]


# ── /hm:configure — the recovery path (P1-5) ───────────────────────────────────


def test_configure_offers_the_three_axes_the_install_never_asked(tmp_path: Path) -> None:
    body = _cmd(_render(tmp_path, models=[]), "configure")
    assert "second_opinion.models" in body
    assert "autonomy.level" in body
    assert "**Locale**" in body


def test_configure_dispatches_each_new_axis_to_its_existing_flag(tmp_path: Path) -> None:
    """ADR-004: no new CLI surface — every flag already exists."""
    body = _cmd(_render(tmp_path, models=[]), "configure")
    for flag in ("--second-opinion-models", "--autonomy-level", "--locale"):
        assert flag in body, flag
    # The persistence pair is explicit-choice-only, so both spellings must be named.
    assert "--autonomy-persistent" in body
    assert "--no-autonomy-persistent" in body


def test_configure_states_the_clear_versus_preserve_semantics(tmp_path: Path) -> None:
    """A partial update must not clobber a neighbouring setting (codex `4ee3418e`).

    Omitting a flag preserves; an explicit empty string clears. Without this stated, an
    executor picks one and the other behaviour becomes a silent data-loss bug.
    """
    body = _cmd(_render(tmp_path, models=[]), "configure")
    lowered = body.lower()
    assert "preserv" in lowered
    assert 'empty string `""`' in body
    # `gated` must be described as preserving persistence/caps, not resetting them.
    assert "gated" in lowered


def test_configure_tells_the_user_detection_is_not_authentication(tmp_path: Path) -> None:
    body = _cmd(_render(tmp_path, models=[]), "configure")
    assert "detect-tools" in body
    assert "not authentication" in body.lower()
    # The call must be an executable block, not prose: a bare inline `!uv run …` inside a
    # sentence is not autorun, and `bash` would read `!uv` as a command word.
    assert "```bash\n!uv run" in body


# ── /hm:health — the installed-but-disabled advisory (P1-6) ────────────────────


def test_health_carries_the_advisory_when_the_axis_is_off(tmp_path: Path) -> None:
    body = _cmd(_render(tmp_path, models=[]), "health")
    assert "detect-tools" in body
    assert "second opinion is off" in body.lower()
    # It must route the user somewhere actionable.
    assert "configure" in body.lower()


def test_health_omits_the_advisory_once_a_model_is_enabled(tmp_path: Path) -> None:
    """The advisory and the smoke are mutually exclusive — both would contradict."""
    body = _cmd(_render(tmp_path, models=["codex"]), "health")
    assert "second opinion is off" not in body.lower()
    assert "second_opinion_invoke" in body  # the positive smoke took its place


def test_the_advisory_is_non_blocking_and_silent_when_nothing_is_installed(
    tmp_path: Path,
) -> None:
    """`/hm:health` must not fail on a missing/among-broken detect-tools, and must not
    nag a user who does not have these CLIs at all."""
    body = _cmd(_render(tmp_path, models=[]), "health")
    lowered = body.lower()
    assert "never fail" in lowered or "must never fail" in lowered
    assert "print nothing" in lowered


def test_the_advisory_probes_at_run_time_not_render_time(tmp_path: Path) -> None:
    """ADR-001: a render-time detection answer freezes at install and goes stale.

    The detection half must be a shell-out inside the rendered command; only the
    `models`-is-empty half is decided at render.
    """
    body = _cmd(_render(tmp_path, models=[]), "health")
    assert "hm cli detect-tools --json" in body
    assert "run time" in body.lower() or "run-time" in body.lower()
