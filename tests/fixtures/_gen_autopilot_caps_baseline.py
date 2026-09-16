"""Freeze the pre-change autopilot boundary matrix + rendered command names (PLAN P0).

Run from the repo root BEFORE Phase 3 touches ``autopilot_caps`` and BEFORE Phase 4
touches any template:

    uv run python tests/fixtures/_gen_autopilot_caps_baseline.py

Two fixtures, two differential oracles:

- ``autopilot_caps_baseline.json`` freezes ``hm autopilot_caps boundary``'s JSON for every
  pipeline stage × every input class the existing tests enumerate (armed, no marker, step cap,
  time cap, judgment-gate pending/clear/blocked/absent at auto_safe and auto_full). AC-012
  compares the post-change module against THIS file, so the expectation cannot be re-derived
  from the changed code. ``reason`` is dropped: it carries floats and paths.
- ``rendered_command_names.json`` freezes the command names of both rendered variants so
  AC-019's "no new slash command" clause compares against a frozen list.

It also prints the per-command ``chars`` / ``round_trips`` for the eight variant keys the
BASELINE-DELTA document and the PLAN's ``surface_allowance`` need.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

from harness_maker import autopilot, autopilot_caps
from harness_maker.io_utils import atomic_write
from harness_maker.models import AtomicStage

_FIXTURES = Path(__file__).parent
_REPO = _FIXTURES.parent.parent
sys.path.insert(0, str(_REPO / "tests" / "structural"))
from _surface_baseline import measure_surface  # noqa: E402

#: The shipped pipeline order (harness.yaml), not the enum order — the fixture must describe
#: the surface a real session runs.
_PIPELINE = [
    AtomicStage(s) for s in ("research", "spec", "plan", "execute", "review", "verify", "wrapup")
]
_STAGES = [s.value for s in _PIPELINE]
_KEEP = ("proceed", "halt_kind", "next_stage", "pipeline_complete", "judgment_auto_answered")

#: Input classes. Each is (armed?, level, extra argv). Judgment-gate inputs matter only on
#: the two judgment-gated stages, but the matrix runs them everywhere on purpose — a change
#: that made a non-gated stage honour the flag would move a row here.
INPUTS: dict[str, tuple[bool, str, list[str]]] = {
    "armed": (True, "auto_safe", ["--step-cap", "20", "--time-cap-min", "300"]),
    "no_marker": (False, "auto_safe", ["--step-cap", "20", "--time-cap-min", "300"]),
    "step_cap": (True, "auto_safe", ["--step-cap", "0", "--time-cap-min", "300"]),
    "time_cap": (True, "auto_safe", ["--step-cap", "20", "--time-cap-min", "0"]),
    "jg_absent_safe": (True, "auto_safe", []),
    "jg_pending_safe": (True, "auto_safe", ["--judgment-gate", "pending"]),
    "jg_clear_safe": (True, "auto_safe", ["--judgment-gate", "clear"]),
    "jg_blocked_safe": (True, "auto_safe", ["--judgment-gate", "blocked"]),
    "jg_pending_full": (True, "auto_full", ["--judgment-gate", "pending"]),
    "jg_clear_full": (True, "auto_full", ["--judgment-gate", "clear"]),
    "jg_blocked_full": (True, "auto_full", ["--judgment-gate", "blocked"]),
}


def boundary_cell(stage: str, armed: bool, level: str, extra: list[str]) -> dict[str, object]:
    """One boundary call on a fresh root, reduced to its stable keys."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        if armed:
            now = datetime.now(UTC).isoformat()
            autopilot.write(root, level=level, pipeline=_PIPELINE, now=now)  # type: ignore[arg-type]
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = autopilot_caps.main(["boundary", "--root", str(root), "--current", stage, *extra])
        out = json.loads(buf.getvalue().strip().splitlines()[-1])
        return {"rc": rc, **{k: out.get(k) for k in _KEEP}}


def build_matrix() -> dict[str, dict[str, object]]:
    return {
        f"{stage}|{name}": boundary_cell(stage, armed, level, extra)
        for stage in _STAGES
        for name, (armed, level, extra) in INPUTS.items()
    }


def main() -> int:
    matrix = build_matrix()
    atomic_write(
        _FIXTURES / "autopilot_caps_baseline.json",
        json.dumps({"inputs": list(INPUTS), "stages": _STAGES, "matrix": matrix}, indent=1) + "\n",
    )
    surface = measure_surface()
    names = {variant: sorted(cmds) for variant, cmds in surface.items()}
    atomic_write(_FIXTURES / "rendered_command_names.json", json.dumps(names, indent=1) + "\n")
    print(f"matrix cells: {len(matrix)}")
    for variant, cmds in surface.items():
        for name in ("plan", "wrapup", "review", "help"):
            key = name if variant == "claude" else f"hm-{name}"
            row = cmds.get(key)
            if row is not None:
                print(
                    f"{variant:6s} {key:10s} chars={row['chars']} round_trips={row['round_trips']}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
