"""Regenerate expected.yaml files, one per fixture project profile.

Why 4, not 8: the second axis these snapshots used to cross (spec-driven / task-driven) was
folded into `spec.strictness`, which derives from the preset (SPEC-dev-mode-removal). Each
fixture now renders at its recommended preset's default strictness, so every rendered artifact
is a function of the profile alone. The strictness-specific render differences are pinned by
`tests/unit/test_render_strictness_surface.py` instead.

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
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.strictness import resolve_strictness
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


def regen_one(fixture_name: str) -> None:
    fix_dir = Path("tests/fixtures") / fixture_name
    p = profile(fix_dir)
    # model_copy keeps validators in play and matches the convention used in
    # cli.py / tests; direct attribute mutation works today but would skip any
    # future @model_validator on InterviewAnswers.
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    target = fix_dir / ".claude.regen-tmp"
    target.mkdir(exist_ok=True)
    render(bp, target, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    exclusions = load_exclusions()
    filtered = [f for f in bp.files if not is_excluded(str(f.path), exclusions)]
    snap = {
        "preset": bp.config.preset.value,
        "strictness": resolve_strictness(bp.config),
        "file_count": len(filtered),
        "files": sorted(
            [
                {"path": str(f.path), "template": f.template, "body_sha256": f.body_sha256}
                for f in filtered
            ],
            key=lambda x: x["path"] or "",
        ),
    }
    out = Path("tests/snapshot") / f"{fixture_name}.expected.yaml"
    out.write_text(yaml.safe_dump(snap, sort_keys=False, default_flow_style=False))
    shutil.rmtree(target)


if __name__ == "__main__":
    # Pin HOME to an empty tmp dir so any environment-dependent helper
    # (e.g., user-global config probes) returns deterministic results,
    # keeping snapshots stable across developer machines.
    #
    # ALSO pin synthesize._HARNESS_MAKER_PKG_ROOT to the canonical main
    # checkout so snapshots remain worktree-invariant. Matches the autouse
    # fixture in ``tests/unit/conftest.py`` (HM_MAIN_CHECKOUT_PATH override
    # available for non-default layouts).
    from harness_maker import synthesize as _synth

    _pinned = os.environ.get(
        "HM_MAIN_CHECKOUT_PATH",
        "/home/noel/harness-maker",
    )
    _synth._HARNESS_MAKER_PKG_ROOT = _pinned
    # 0.15.1: renderer reads direct_url.json instead of the constant; pin the
    # function too so snapshots stay byte-identical regardless of the dev's
    # actual install layout.
    # PLAN-portable-hook-paths: pin the PORTABLE ($HOME-substituted) form so
    # snapshots are home-free and match production render (where _portablize_ref
    # rewrites the home-prefixed cache path to $HOME/...), and so the render-time
    # leak-check assert passes. Mirrors tests/unit/conftest.py's pin.
    _synth._compute_install_ref = lambda: "$HOME/harness-maker"
    with tempfile.TemporaryDirectory() as fake_home:
        os.environ["HOME"] = fake_home
        with patch.object(Path, "home", lambda: Path(fake_home)):
            for fixture in FIXTURES:
                regen_one(fixture)
                print(f"Regenerated {fixture}")
