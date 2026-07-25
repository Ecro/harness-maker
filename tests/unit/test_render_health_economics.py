"""Phase 6 contract: the economics liveness smoke lives in the health TEMPLATE.

ADR-009 deliberately puts it here rather than in `readiness.py`: `compute_readiness`
takes no transcript root, so a readiness signal would force `Path.home()` into a scored
path and make the whole health suite HOME-dependent (CLAUDE.md checkpoint 7).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import readiness as readiness_mod
from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def health_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    fake_home = tmp_path_factory.mktemp("hm-home")
    out = tmp_path_factory.mktemp("hm-out")
    monkey = pytest.MonkeyPatch()
    monkey.setattr(Path, "home", lambda: fake_home)
    try:
        fix_dir = Path(__file__).parent.parent / "fixtures" / "prod-tauri-app"
        p = profile(fix_dir)
        a = interview(p, autoloop_mode=True)
        bp = synthesize(p, a)
        render(bp, out, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    finally:
        monkey.undo()
    rendered = out / "commands" / "hm" / "health.md"
    if not rendered.is_file():
        pytest.fail(f"health.md was not rendered at {rendered}")
    return rendered.read_text(encoding="utf-8")


def test_the_doctor_step_is_present(health_body: str) -> None:
    assert "@hm:economics-doctor" in health_body
    assert "@hm:/economics-doctor" in health_body
    assert "harness_maker.economics doctor" in health_body


@pytest.mark.parametrize("state", ["ok", "n/a", "fail"])
def test_all_three_exit_states_are_documented(health_body: str, state: str) -> None:
    assert f"status: {state}" in health_body


def test_the_na_state_is_declared_not_a_finding(health_body: str) -> None:
    """Fresh clone / CI / Cursor / Codex must degrade to N-A, never to a failure."""
    assert "pass, not a finding" in health_body
    assert "Cursor or" in health_body


def test_the_smoke_declares_it_measures_the_instrument_not_the_spend(
    health_body: str,
) -> None:
    """Non-Goal 7 — it must never become a spend gate under another name."""
    assert "Measures the INSTRUMENT, never the spend" in health_body
    assert "no score impact" in health_body


def test_readiness_gained_no_economics_signal(tmp_path: Path) -> None:
    """The Non-Goal 7 guard: economics must NOT become a scored readiness dimension."""
    source = Path(readiness_mod.__file__).read_text(encoding="utf-8")
    assert "economics" not in source.lower()

    result = readiness_mod.compute_readiness(
        tmp_path, __import__("harness_maker.models", fromlist=["Preset"]).Preset.SIDE
    )
    signal_ids = {s.id for dim in result.dimensions.values() for s in dim.signals}
    assert signal_ids, "readiness produced no signals — the guard would be vacuous"
    assert not {sid for sid in signal_ids if "economic" in sid or "transcript" in sid}
