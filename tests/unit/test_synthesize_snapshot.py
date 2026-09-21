"""Snapshot tests for the Synthesizer + Renderer pipeline (Task 3.5).

One case per fixture project profile, each rendered at its recommended preset's default
strictness (SPEC-dev-mode-removal AC-005). The guard that strictness actually changes the
render — the job the old "two arms must differ" case did for the retired axis — lives in
`tests/unit/test_render_strictness_surface.py`, which asserts WHAT differs, not merely that
something does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.strictness import resolve_strictness
from harness_maker.synthesize import synthesize

sys.path.insert(0, str(Path(__file__).parent.parent / "snapshot"))
from regenerate import is_excluded, load_exclusions  # noqa: E402

_FIXTURES = ("side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware")


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


@pytest.mark.parametrize("fixture", _FIXTURES)
def test_snapshot_matches(fixture: str, tmp_path: Path) -> None:
    fix_dir = Path(__file__).parent.parent / "fixtures" / fixture
    snap_path = Path(__file__).parent.parent / "snapshot" / f"{fixture}.expected.yaml"
    expected = yaml.safe_load(snap_path.read_text())
    p = profile(fix_dir)
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    render(bp, tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    exclusions = load_exclusions()
    filtered = [f for f in bp.files if not is_excluded(str(f.path), exclusions)]
    assert bp.config.preset.value == expected["preset"]
    assert resolve_strictness(bp.config) == expected["strictness"]
    assert len(filtered) == expected["file_count"]
    actual = sorted(
        [
            {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
            for f in filtered
        ],
        key=lambda x: x["path"] or "",
    )
    assert actual == expected["files"]
