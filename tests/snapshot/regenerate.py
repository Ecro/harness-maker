"""Regenerate expected.yaml files for all preset×dev_mode fixture combinations.

Why 8 = 4 fixtures × 2 dev_modes: preset (Side/Production) and dev_mode
(spec-driven/task-driven) are orthogonal axes per the PLAN; each fixture
project profile recommends one default, but the cross combos are explicitly
allowed and worth pinning so a regression in either axis is caught.

Run from harness-maker repo root:
    uv run python tests/snapshot/regenerate.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from harness_maker.interview import interview
from harness_maker.models import DevMode
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

FIXTURES = ["side-python-cli", "side-tauri-app", "prod-tauri-app", "prod-firmware"]
DEV_MODES: tuple[tuple[str, DevMode], ...] = (
    ("task", DevMode.TASK_DRIVEN),
    ("spec", DevMode.SPEC_DRIVEN),
)


def regen_one(fixture_name: str, mode_label: str, mode: DevMode) -> None:
    fix_dir = Path("tests/fixtures") / fixture_name
    p = profile(fix_dir)
    # model_copy keeps validators in play and matches the convention used in
    # cli.py / tests; direct attribute mutation works today but would skip any
    # future @model_validator on InterviewAnswers.
    a = interview(p, autoloop_mode=True).model_copy(update={"dev_mode": mode})
    bp = synthesize(p, a)
    target = fix_dir / f".claude.regen-tmp-{mode_label}"
    target.mkdir(exist_ok=True)
    render(bp, target, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    snap = {
        "preset": bp.config.preset.value,
        "dev_mode": bp.config.dev_mode.value,
        "file_count": len(bp.files),
        "files": sorted(
            [
                {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
                for f in bp.files
            ],
            key=lambda x: x["path"],
        ),
    }
    out = Path("tests/snapshot") / f"{fixture_name}-{mode_label}.expected.yaml"
    out.write_text(yaml.safe_dump(snap, sort_keys=False, default_flow_style=False))
    shutil.rmtree(target)


if __name__ == "__main__":
    for fixture in FIXTURES:
        for label, mode in DEV_MODES:
            regen_one(fixture, label, mode)
            print(f"Regenerated {fixture}-{label}")
