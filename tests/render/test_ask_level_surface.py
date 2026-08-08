"""Phase B4 (ADR-007) — no rendered command may carry `ask` as a `--level` argument.

`ask` is a meta-level: it says "resolve this per session". Every `--level` in a rendered
command is a concrete argument to a CLI that accepts only the three operational values, so an
interpolated `ask` does not degrade — it makes the command exit on an argument error. In
`/hm:health` that error is then *reported as a degraded harness*, which is worse than a
missing check: the probe would accuse a correctly-configured project of being broken.

`ask` is now the default level, so the ordinary render IS the fixture. That is deliberate —
the earlier form of this test rendered the `auto_safe` default and passed vacuously, proving
only that a level nobody had rendered was absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import AutonomyConfig, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("ask-level")
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE, Target.CODEX],
            autonomy=AutonomyConfig(level="ask"),
        ),
    )
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


def test_the_fixture_really_is_ask(rendered: Path) -> None:
    """Guards the guard: if the default moved, every assertion below would pass vacuously."""
    assert 'level: "ask"' in (rendered / ".claude" / "harness.yaml").read_text(encoding="utf-8")


def test_no_rendered_command_passes_level_ask(rendered: Path) -> None:
    offenders: list[str] = []
    for f in sorted(rendered.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "--level ask" in text:
            offenders.append(str(f.relative_to(rendered)))
    assert not offenders, offenders


def test_the_picker_offers_the_three_operational_levels(rendered: Path) -> None:
    text = (rendered / ".claude" / "commands" / "hm" / "plan.md").read_text(encoding="utf-8")
    assert "ask-pending" in text, "the picker must branch on ask-pending explicitly"
    assert "auto_safe" in text
    assert "auto_full" in text
    assert "<the level the user picked>" in text, (
        "the arm command must carry the PICKED level; a hard-coded one would make the "
        "picker's answer decorative"
    )


def test_health_skips_its_smoke_under_ask(rendered: Path) -> None:
    text = (rendered / ".claude" / "commands" / "hm" / "health.md").read_text(encoding="utf-8")
    assert "autopilot_ledger smoke" not in text, (
        "the smoke probe takes a concrete --level; under `ask` there is none to give"
    )
    assert "resolved per session" in text, "the skip must be stated, not silent"
