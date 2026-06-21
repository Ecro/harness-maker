"""PLAN-multisession-fleet-reverify Phase 3 — wrapup memory-write render gate.

H1 is closed only while the rendered wrapup routes its memory-tier writes through
the locked `memory_md` CLI. This gate fails if a re-render reverts Step 5.1/5.2/5.5
back to a direct `Edit`/`Write` on the tier files (which races concurrent fleet
sessions and can drop the close marker).
"""

from __future__ import annotations

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def wrapup_text(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("rendered-memory-gate")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(synthesize(p, interview(p, autoloop_mode=True)), out, freeze_time=DEFAULT_FREEZE_TIME)
    return (out / "commands" / "hm" / "wrapup.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "subcommand",
    ["memory_md upsert-wiki", "memory_md upsert-failure", "memory_md append-session"],
)
def test_memory_tiers_written_via_locked_cli(wrapup_text: str, subcommand: str) -> None:
    assert subcommand in wrapup_text, (
        f"wrapup must write the memory tier via `{subcommand}` (H1 lock); "
        "a direct Edit/Write reverts the fix"
    )


def test_no_edit_based_marker_insert_procedure(wrapup_text: str) -> None:
    # The old Edit-based instruction told Claude to hand-splice above the close
    # marker. Its disappearance proves Step 5.1/5.2 no longer race-prone.
    assert "insert the new entry on the lines directly above it" not in wrapup_text
    assert "locate the line `<!-- @hm:/user:entries -->`" not in wrapup_text
