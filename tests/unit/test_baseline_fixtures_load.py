"""PLAN P0 exit: the two differential fixtures exist, parse, and are non-empty.

They are the oracles for AC-012 (boundary matrix) and AC-019 (command names). A fixture
that fails to load would make those tests error rather than fail, which reads as "the
harness is broken" instead of "the change moved a row" — so loadability is pinned here.
"""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_boundary_matrix_covers_every_stage_and_input() -> None:
    data = json.loads((_FIXTURES / "autopilot_caps_baseline.json").read_text(encoding="utf-8"))
    stages, inputs, matrix = data["stages"], data["inputs"], data["matrix"]
    # 7 -> 6: `plan` was removed (SPEC-plan-stage-absorption IRR-001).
    assert len(stages) == 6, data.keys()
    assert inputs, data.keys()
    assert set(matrix) == {f"{s}|{i}" for s in stages for i in inputs}
    for key, cell in matrix.items():
        assert cell["rc"] == 0, key
        assert isinstance(cell["proceed"], bool), key
        assert cell["halt_kind"] is None or isinstance(cell["halt_kind"], str), key


def test_boundary_matrix_carries_the_expected_halts() -> None:
    """The matrix must record real behaviour, not an all-advance placeholder."""
    matrix = json.loads((_FIXTURES / "autopilot_caps_baseline.json").read_text(encoding="utf-8"))[
        "matrix"
    ]
    assert matrix["spec|no_marker"]["halt_kind"] == "kill_switch"
    assert matrix["spec|step_cap"]["halt_kind"] == "step_cap"
    assert matrix["spec|jg_pending_safe"]["halt_kind"] == "judgment_gate"
    assert matrix["verify|armed"]["halt_kind"] == "merge_gate"
    assert matrix["wrapup|armed"]["pipeline_complete"] is True
    assert matrix["review|jg_clear_safe"]["next_stage"] == "verify"
    assert matrix["execute|armed"]["proceed"] is True


def test_rendered_command_names_freeze_both_variants() -> None:
    names = json.loads((_FIXTURES / "rendered_command_names.json").read_text(encoding="utf-8"))
    assert set(names) == {"claude", "codex"}
    # `plan` / `hm-plan` were removed (SPEC-plan-stage-absorption IRR-001); `spec` is the
    # stage that now carries the DRI interview, so it is the meaningful presence check.
    assert "spec" in names["claude"]
    assert "hm-spec" in names["codex"]
    assert names["claude"] == sorted(names["claude"])
