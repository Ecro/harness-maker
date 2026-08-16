"""Regenerate the pre-migration dispatch baselines (ADR-006, T7/T9 of PLAN-codex-lens-dispatch).

Run from the repo root BEFORE Phase 2 migrates any call site:

    uv run python tests/fixtures/_gen_dispatch_baselines.py

Two fixtures, two different jobs:

- ``lens_briefs_baseline.json`` freezes ALL SEVEN ``conditional_router.LENS_DISPATCH`` briefs
  (T9 — the three domain briefs traverse the same macro quoting seam as the four core ones, so
  scoping the fixture to the core four would let a quoting defect on ``security`` pass Phase 2).
  The briefs live ONLY in ``conditional_router.py``; ``review.md.j2`` interpolates ``{{ d.brief }}``
  and contains none of the text (this is T2 — the first draft named the template as the source).
- ``claude_arm_baseline.json`` freezes the rendered Claude-arm dispatch lines so Phases 2 and 3
  diff against a frozen artifact rather than against a regenerated snapshot, which records
  whatever the macro produced and is therefore self-approving.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from harness_maker.conditional_router import LENS_DISPATCH
from harness_maker.io_utils import atomic_write
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_FIXTURES = Path(__file__).parent
_CLAUDE_MARKERS = ("Task(subagent_type=", "AskUserQuestion", "Skill(")


def _rendered(preset: Preset, targets: list[Target]) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=preset, targets=targets),
    )
    with tempfile.TemporaryDirectory() as td:
        # `target_dir` is the `.claude` DIRECTORY, not the project root: Claude paths are
        # relative to it, and Codex outputs (`.codex/`, `.agents/`, `AGENTS.md`) are written
        # to its PARENT. Passing a bare tmpdir therefore writes the Codex half into the
        # tmpdir's parent — i.e. straight into the real `/tmp` — and the scan then sees zero
        # Codex files and reads as "no leak found". Root the render one level down.
        root = Path(td)
        out = root / ".claude"
        render(blueprint, out, freeze_time=DEFAULT_FREEZE_TIME)
        # os.walk, rooted one level ABOVE the render target. `Path.rglob` does match dotted
        # paths (verified) — the "59 of 98 entries, zero Codex files" this scan first reported
        # came from the `target_dir.parent` fact above, not from rglob. That wrong explanation
        # was written into three files before review caught it; the walk root is the real fix.
        files: dict[str, str] = {}
        for walk_root, _dirs, names in os.walk(root):
            for name in names:
                f = Path(walk_root) / name
                files[str(f.relative_to(root))] = f.read_text(encoding="utf-8", errors="replace")
        return files


def gen_lens_briefs() -> dict[str, str]:
    return {lens: brief for lens, (_agent, brief) in LENS_DISPATCH.items()}


def gen_claude_arm() -> dict[str, list[str]]:
    """Every rendered line carrying a Claude-only call, keyed by output path.

    Rendered, not template source: a template may legitimately hold ``Task(`` inside a
    ``{% if not is_codex %}`` arm, and what Phases 2-3 must not change is the OUTPUT.
    """
    out: dict[str, list[str]] = {}
    for preset in (Preset.SIDE, Preset.PRODUCTION):
        rendered = _rendered(preset, [Target.CLAUDE_CODE, Target.CODEX])
        for path, body in sorted(rendered.items()):
            lines = [
                line.strip()
                for line in body.splitlines()
                if any(marker in line for marker in _CLAUDE_MARKERS)
            ]
            if lines:
                out[f"{preset.value}::{path}"] = lines
    return out


def main() -> None:
    # atomic_write, per the project's write standard: an interrupt mid-write leaves a
    # truncated baseline, and Phase 2 then diffs the render against that truncation as if it
    # were the contract.
    atomic_write(
        _FIXTURES / "lens_briefs_baseline.json",
        json.dumps(gen_lens_briefs(), indent=2, ensure_ascii=False) + "\n",
    )
    atomic_write(
        _FIXTURES / "claude_arm_baseline.json",
        json.dumps(gen_claude_arm(), indent=2, ensure_ascii=False) + "\n",
    )
    print("wrote lens_briefs_baseline.json + claude_arm_baseline.json")


if __name__ == "__main__":
    main()
