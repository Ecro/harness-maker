"""Regenerate expected.yaml files for all 4 fixtures.

Run from harness-maker repo root:
    uv run python tests/snapshot/regenerate.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

FIXTURES = ["side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware"]


def regen_one(fixture_name: str) -> None:
    fix_dir = Path("tests/fixtures") / fixture_name
    p = profile(fix_dir)
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    target = fix_dir / ".claude.regen-tmp"
    target.mkdir(exist_ok=True)
    render(bp, target, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    snap = {
        "preset": bp.config.preset.value,
        "file_count": len(bp.files),
        "files": sorted(
            [
                {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
                for f in bp.files
            ],
            key=lambda x: x["path"],
        ),
    }
    out = Path("tests/snapshot") / f"{fixture_name}.expected.yaml"
    out.write_text(yaml.safe_dump(snap, sort_keys=False, default_flow_style=False))
    shutil.rmtree(target)


if __name__ == "__main__":
    for f in FIXTURES:
        regen_one(f)
        print(f"Regenerated {f}")
