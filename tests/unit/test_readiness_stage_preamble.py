"""SPEC-hm-light-lane-s3c AC-004 — `/hm:health` checks the preamble file when a command names it.

The expected values per row are AC-004's golden table, written from the SPEC's A outcome before
the code. The old-render row compares against a7403f2f's own `_dim_workflow_clarity` output on its
default render, captured by `tests/fixtures/light_lane_s3c/capture_a7403f2f.py.txt`
(`readiness_a7403f2f.json`).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.unit import light_lane_s3c_fixture as fx

PREAMBLE_FILE = ".claude/hm/stage-preamble.md"
OLD: dict[str, Any] = json.loads(
    (fx.GOLDENS / "readiness_a7403f2f.json").read_text(encoding="utf-8")
)["workflow_clarity"]
SIGNALS = ("output_language_present", "start_end_summary_present")

ROWS: dict[str, dict[str, Any]] = {
    "full render": {"output_language_present": True, "start_end_summary_present": True},
    "stage-preamble.md deleted": {
        "output_language_present": False,
        "start_end_summary_present": False,
        "detail_names": PREAMBLE_FILE,
    },
    "@hm:output_language removed from stage-preamble.md": {
        "output_language_present": False,
        "start_end_summary_present": True,
    },
    "@hm:banner:start removed from stage-preamble.md": {
        "output_language_present": True,
        "start_end_summary_present": False,
    },
}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("render")
    fx.render_project(fx._answers(lambda _b: {}), root)
    return root


def _copy(rendered: Path, tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(rendered, root, symlinks=True)
    return root


def _apply(root: Path, row: str) -> None:
    preamble = root / PREAMBLE_FILE
    if row == "stage-preamble.md deleted":
        preamble.unlink()
    elif row.startswith("@hm:output_language removed"):
        preamble.write_text(
            preamble.read_text(encoding="utf-8").replace("<!-- @hm:output_language -->", ""),
            encoding="utf-8",
        )
    elif row.startswith("@hm:banner:start removed"):
        preamble.write_text(
            preamble.read_text(encoding="utf-8").replace("<!-- @hm:banner:start -->", ""),
            encoding="utf-8",
        )


def _signals(root: Path) -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in fx.workflow_clarity(root)["signals"]}


@pytest.mark.parametrize("row", list(ROWS))
def test_health_checks_the_preamble_file(rendered: Path, tmp_path: Path, row: str) -> None:
    root = _copy(rendered, tmp_path)
    assert (root / PREAMBLE_FILE).is_file(), "the render ships the preamble file"
    _apply(root, row)
    signals = _signals(root)
    expected = ROWS[row]
    for sig in SIGNALS:
        assert signals[sig]["passed"] is expected[sig], (row, sig, signals[sig])
        if not expected[sig]:
            detail = f"{signals[sig]['evidence']} {signals[sig]['action']}"
            assert PREAMBLE_FILE in detail, (row, sig, detail)
    if "detail_names" in expected:
        for sig in SIGNALS:
            assert expected["detail_names"] in signals[sig]["evidence"], (row, sig)


def test_health_scores_an_old_render_as_today(rendered: Path, tmp_path: Path) -> None:
    """A render whose commands inline the preamble and name no file scores as at a7403f2f."""
    root = _copy(rendered, tmp_path)
    preamble = fx.ref_slice((root / PREAMBLE_FILE).read_text(encoding="utf-8"))
    (root / PREAMBLE_FILE).unlink()
    for stage in fx.STAGES:
        cmd = root / ".claude" / "commands" / "hm" / f"{stage}.md"
        text = cmd.read_text(encoding="utf-8")
        head = text[: fx.frontmatter_end(text)]
        rest = text[len(head) + len(fx.preamble_span(text)) :]
        cmd.write_text(head + preamble + rest, encoding="utf-8")
        assert "stage-preamble.md" not in cmd.read_text(encoding="utf-8")
    signals = _signals(root)
    for sig in SIGNALS:
        assert signals[sig]["passed"] is True, sig
    assert fx.workflow_clarity(root) == OLD
