"""Snapshot tests for the Synthesizer + Renderer pipeline (Task 3.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.mark.parametrize(
    "fixture",
    ["side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware"],
)
def test_snapshot_matches(fixture: str, tmp_path: Path) -> None:
    fix_dir = Path(__file__).parent.parent / "fixtures" / fixture
    snap_path = Path(__file__).parent.parent / "snapshot" / f"{fixture}.expected.yaml"
    expected = yaml.safe_load(snap_path.read_text())
    p = profile(fix_dir)
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    assert bp.config.preset.value == expected["preset"]
    assert len(bp.files) == expected["file_count"]
    actual = sorted(
        [
            {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
            for f in bp.files
        ],
        key=lambda x: x["path"],
    )
    assert actual == expected["files"]
