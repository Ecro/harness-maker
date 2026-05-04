"""Snapshot tests for the Synthesizer + Renderer pipeline (Task 3.5).

Parametrized over preset × dev_mode (4 fixtures × 2 modes = 8 cases) so that a
regression in either axis fails its own test rather than being swallowed by a
single combined snapshot. A 9th sanity case asserts the two dev_modes for the
same fixture actually produce different output — guarding against a bug where
synthesize ignores ``answers.dev_mode`` and both regenerate.py + the snapshot
test silently agree on identical files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness_maker.interview import interview
from harness_maker.models import DevMode
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_FIXTURES = ("side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware")
_MODES: tuple[tuple[str, DevMode], ...] = (
    ("task", DevMode.TASK_DRIVEN),
    ("spec", DevMode.SPEC_DRIVEN),
)


@pytest.fixture(autouse=True)
def _isolate_home(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin Path.home() to an empty tmp dir so snapshot output stays stable
    regardless of the developer's personal ~/.claude/settings.json.
    """
    fake_home = tmp_path_factory.mktemp("hm-home")
    monkeypatch.setattr(Path, "home", lambda: fake_home)


@pytest.mark.parametrize(
    ("fixture", "mode_label", "mode"),
    [(f, label, mode) for f in _FIXTURES for label, mode in _MODES],
)
def test_snapshot_matches(
    fixture: str,
    mode_label: str,
    mode: DevMode,
    tmp_path: Path,
) -> None:
    fix_dir = Path(__file__).parent.parent / "fixtures" / fixture
    snap_path = Path(__file__).parent.parent / "snapshot" / f"{fixture}-{mode_label}.expected.yaml"
    expected = yaml.safe_load(snap_path.read_text())
    p = profile(fix_dir)
    a = interview(p, autoloop_mode=True).model_copy(update={"dev_mode": mode})
    bp = synthesize(p, a)
    render(bp, tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    assert bp.config.preset.value == expected["preset"]
    assert bp.config.dev_mode.value == expected["dev_mode"]
    assert len(bp.files) == expected["file_count"]
    actual = sorted(
        [
            {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
            for f in bp.files
        ],
        key=lambda x: x["path"],
    )
    assert actual == expected["files"]


@pytest.mark.parametrize("fixture", _FIXTURES)
def test_dev_mode_axis_actually_differentiates(fixture: str) -> None:
    """task-driven and spec-driven for the same fixture must produce different files.

    Catches the regression class where ``answers.dev_mode`` is plumbed through
    types but ignored at synthesis — both snapshots would be identical and all
    parametrized tests above would still pass.
    """
    snap_dir = Path(__file__).parent.parent / "snapshot"
    task = yaml.safe_load((snap_dir / f"{fixture}-task.expected.yaml").read_text())
    spec = yaml.safe_load((snap_dir / f"{fixture}-spec.expected.yaml").read_text())
    assert task["files"] != spec["files"], (
        f"{fixture}: task-driven and spec-driven produced identical outputs"
    )
