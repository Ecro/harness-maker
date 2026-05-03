"""Snapshot tests for the Synthesizer + Renderer pipeline (Task 3.5).

Parametrized over preset × dev_mode (4 fixtures × 2 modes = 8 cases) so that a
regression in either axis fails its own test rather than being swallowed by a
single combined snapshot.
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
    snap_path = (
        Path(__file__).parent.parent / "snapshot" / f"{fixture}-{mode_label}.expected.yaml"
    )
    expected = yaml.safe_load(snap_path.read_text())
    p = profile(fix_dir)
    a = interview(p, autoloop_mode=True)
    a.dev_mode = mode
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
