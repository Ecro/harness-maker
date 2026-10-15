"""HM-LIGHT-LANE stage 3d — only the light check opts in to the SPEC plan (SPEC-hm-light-lane-s3d).

AC-006's oracle is the df070f6c render, captured BEFORE any template changed by
`tests/fixtures/light_lane_s3d/capture.py.txt` from a `git archive` of df070f6c. The SPEC names
4bd3d3d8; stage 3c (merged after the SPEC was written) changed these renders, so the reference
is the main tip 3d builds on, and the AC's intent holds: 3d adds no render bytes outside the
light check. The answer sets are stage 3a's (`CONFIGS`), both targets, worktree on and off.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import LoopConfig, Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from tests.render.test_render_light_lane_s3a import CONFIGS, MECH
from tests.structural._surface_baseline import HARNESS_YAML, pinned_install_ref

GOLDEN_PATH = Path(__file__).parents[1] / "fixtures/light_lane_s3d/renders_df070f6c.json"
UNCHANGED_PATHS = (
    "commands/hm/review.md",
    "commands/hm/verify.md",
    "commands/hm/wrapup.md",
    "commands/hm/loop.md",
    "commands/hm/execute.md",
    "hm/verify-checks.md",
    "hm/wrapup-steps.md",
    "hm/review-autofix.md",
    "hm/review-confirmation.md",
    "skills/hm-review",
    "skills/hm-verify",
    "skills/hm-wrapup",
)
LIGHT_CHECK_PATHS = ("hm/execute-light-check.md", "skills/hm-execute")
VERIFY_PATHS = ("commands/hm/verify.md", "hm/verify-checks.md", "skills/hm-verify")
KEYS = [k for k, _ in CONFIGS]
_HEADING = re.compile(r"^#{1,6} .*$", re.M)


@cache
def golden() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return data


@contextmanager
def _empty_home(home: Path) -> Iterator[None]:
    home.mkdir()
    old = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old


@cache
def render_paths(key: str) -> dict[str, str | None]:
    """Stage 3a's answer builder, rendered once per config (shared with the capture script).

    HOME is pinned to an empty dir for the render, as the capture pinned it. The clock needs no
    `HARNESS_MAKER_FREEZE`: the capture did not set it, and `render` gets `DEFAULT_FREEZE_TIME`.
    """
    loop, wt, strictness, mech, preset = dict(CONFIGS)[key]
    base = answers_from_harness_yaml(HARNESS_YAML)
    assert base is not None
    answers = base.model_copy(
        update={
            "loop": LoopConfig(enabled=loop),
            "worktree": {**base.worktree, "enabled": wt},
            "strictness": strictness,
            "mechanical_checks": list(MECH) if mech else [],
            "preset": Preset(preset),
        }
    )
    with tempfile.TemporaryDirectory() as td, _empty_home(Path(td) / "home"):
        root = Path(td) / "out"
        with pinned_install_ref():
            render(
                synthesize(ProjectProfile(), answers),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        out: dict[str, str | None] = {}
        for rel in (*UNCHANGED_PATHS, *LIGHT_CHECK_PATHS):
            if rel.startswith("skills/"):
                p = root / ".agents" / "skills" / rel.split("/", 1)[1] / "SKILL.md"
            else:
                p = root / ".claude" / rel
            out[rel] = p.read_text(encoding="utf-8") if p.is_file() else None
        return out


def sha256(text: str | None) -> str | None:
    return None if text is None else hashlib.sha256(text.encode()).hexdigest()


def headings(text: str | None) -> list[str]:
    return [] if text is None else _HEADING.findall(text)


def _text(key: str, rel: str) -> str:
    text = render_paths(key)[rel]
    assert text is not None, f"{rel} did not render for {key}"
    return text


def _codex_light_check(key: str) -> str:
    """The light check inlined in the Codex execute skill, from its heading to the next step."""
    text = _text(key, "skills/hm-execute")
    i = text.index("### Step 4.2 — Light check")
    ends = ("\n### Step 4.5", "\n<!-- @hm:loop-only -->\n### Step 5", "\n## Outputs")
    return text[i : min(text.index(e, i) for e in ends if e in text[i:])]


@pytest.mark.parametrize("key", KEYS)
def test_only_the_light_check_passes_the_slug(key: str) -> None:
    """AC-005: the light check's Check 2 passes the slug and names the source; verify does not."""
    light = {"claude": _text(key, "hm/execute-light-check.md"), "codex": _codex_light_check(key)}
    for arm, text in light.items():
        assert "--spec-slug <slug>" in text, arm
        assert "from SPEC (no CI file)" in text, arm
        assert "With no CI file, `--spec-slug` takes the gates from this trusted SPEC" in text, arm
        (run,) = [ln for ln in text.splitlines() if "verification_cache run" in ln]
        assert "--spec-slug <slug>" in run, arm
        bullet = next(ln for ln in text.splitlines() if ln.startswith("- `3`"))
        assert "neither" in bullet, arm
        assert "SPEC plan" in bullet, arm
        assert "not a pass" in bullet, arm
        assert '"gate_source": "spec"' in text, arm
    for rel in VERIFY_PATHS:
        verify = _text(key, rel)
        assert "--spec-slug" not in verify, rel
        assert "gate_source" not in verify, rel


@pytest.mark.parametrize("key", KEYS)
def test_typed_stages_match_4bd3d3d8(key: str) -> None:
    """AC-006 (reference: df070f6c, see the module docstring): typed stages are byte-identical,
    and neither light-check surface gains or loses a heading."""
    cfg = golden()["configs"][key]
    texts = render_paths(key)
    differ = [rel for rel in UNCHANGED_PATHS if sha256(texts[rel]) != cfg["sha256"][rel]]
    assert differ == []
    for rel in LIGHT_CHECK_PATHS:
        assert headings(texts[rel]) == cfg["headings"][rel], rel


def test_golden_covers_every_config() -> None:
    assert golden()["source_sha"] == "df070f6c"
    assert set(golden()["configs"]) == set(KEYS)
    assert tuple(golden()["unchanged_paths"]) == UNCHANGED_PATHS
