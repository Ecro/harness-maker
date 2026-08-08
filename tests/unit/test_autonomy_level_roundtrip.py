"""Phase B4 — the interview's four values, and that each one survives a re-render.

The round-trip is the load-bearing half. A level that the interview can produce but
`answers_from_harness_yaml` cannot read back is silently reset on the next
`/harness-maker:make --update` — the user picks `auto_full`, gets it once, and is quietly
returned to the default the next time the harness is regenerated, with nothing to see.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_maker import interview as iv
from harness_maker.interview import _ask_autonomy, answers_from_harness_yaml
from harness_maker.models import AutonomyConfig, InterviewAnswers, Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ALL_FOUR = ("gated", "auto_safe", "auto_full", "ask")


def _feed(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    it: Iterator[str] = iter(answers)
    monkeypatch.setattr(iv, "_input_or_empty", lambda _prompt: next(it, ""))


def test_the_offered_default_is_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed(monkeypatch, ["", "", "", "", ""])
    assert _ask_autonomy().level == "ask"


@pytest.mark.parametrize("level", ["auto_safe", "auto_full", "ask"])
def test_each_offered_level_is_taken(monkeypatch: pytest.MonkeyPatch, level: str) -> None:
    _feed(monkeypatch, ["y", level, "", "", ""])
    assert _ask_autonomy().level == level


def test_an_explicit_decline_still_pins_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-013 — the class default now ASKS, so inheriting it here would re-ask a user who
    has already said no."""
    _feed(monkeypatch, ["n"])
    cfg = _ask_autonomy()
    assert cfg.level == "gated"
    assert cfg.autopilot_persistent is False


def test_a_typo_takes_the_default_rather_than_arming_something_wider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _feed(monkeypatch, ["y", "auto_ful", "", "", ""])
    assert _ask_autonomy().level == "ask"


@pytest.mark.parametrize("level", list(_ALL_FOUR))
def test_every_level_survives_a_re_render(tmp_path: Path, level: str) -> None:
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, autonomy=AutonomyConfig(level=level)),  # type: ignore[arg-type]
    )
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    restored = answers_from_harness_yaml(tmp_path / ".claude" / "harness.yaml")
    assert restored is not None
    assert restored.autonomy.level == level
