"""Regenerate expected.yaml files for all preset×dev_mode fixture combinations.

Why 8 = 4 fixtures × 2 dev_modes: preset (Side/Production) and dev_mode
(spec-driven/task-driven) are orthogonal axes per the PLAN; each fixture
project profile recommends one default, but the cross combos are explicitly
allowed and worth pinning so a regression in either axis is caught.

Run from harness-maker repo root:
    uv run python tests/snapshot/regenerate.py
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from harness_maker.interview import interview
from harness_maker.models import DevMode
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

EXCLUSIONS_FILE = Path(__file__).parent / "EXCLUSIONS.md"


def load_exclusions(path: Path = EXCLUSIONS_FILE) -> list[str]:
    """Parse EXCLUSIONS.md into a list of fnmatch globs.

    PLAN-llm-code-review-2026 ADR-005 — paths inside the
    ``<!-- @hm:exclusion-list -->`` / ``<!-- @hm:/exclusion-list -->`` block
    are dropped from snapshot comparison so non-deterministic reviewer output
    paths do not flake.
    """
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8")
    match = re.search(
        r"<!--\s*@hm:exclusion-list\s*-->(.*?)<!--\s*@hm:/exclusion-list\s*-->",
        raw,
        flags=re.DOTALL,
    )
    if not match:
        return []
    globs: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "<!--")):
            continue
        globs.append(stripped)
    return globs


def is_excluded(path: str, exclusions: list[str]) -> bool:
    """True iff ``path`` matches any of the active fnmatch globs."""
    return any(fnmatch.fnmatch(path, g) for g in exclusions)

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
    exclusions = load_exclusions()
    filtered = [f for f in bp.files if not is_excluded(str(f.path), exclusions)]
    snap = {
        "preset": bp.config.preset.value,
        "dev_mode": bp.config.dev_mode.value,
        "file_count": len(filtered),
        "files": sorted(
            [
                {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
                for f in filtered
            ],
            key=lambda x: x["path"],
        ),
    }
    out = Path("tests/snapshot") / f"{fixture_name}-{mode_label}.expected.yaml"
    out.write_text(yaml.safe_dump(snap, sort_keys=False, default_flow_style=False))
    shutil.rmtree(target)


if __name__ == "__main__":
    # Pin HOME to an empty tmp dir so any environment-dependent helper
    # (e.g., user-global config probes) returns deterministic results,
    # keeping snapshots stable across developer machines.
    with tempfile.TemporaryDirectory() as fake_home:
        os.environ["HOME"] = fake_home
        with patch.object(Path, "home", lambda: Path(fake_home)):
            for fixture in FIXTURES:
                for label, mode in DEV_MODES:
                    regen_one(fixture, label, mode)
                    print(f"Regenerated {fixture}-{label}")
