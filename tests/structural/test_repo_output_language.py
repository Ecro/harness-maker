"""This repo's hand-written CLAUDE.md must keep the locale directive readiness checks for."""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Preset
from harness_maker.readiness import compute_readiness

_REPO = Path(__file__).resolve().parents[2]
_MARKER = "<!-- @hm:output_language -->"


def test_ac_004_repo_root_files_carry_the_output_language_directive() -> None:
    """SPEC-retire-autopilot-remnants AC-004.

    No render writes CLAUDE.md here, so nothing restores the marker if an edit drops it.
    AGENTS.md is gitignored, so readiness checks it only where it exists; the direct
    CLAUDE.md assertion is what a fresh clone enforces.
    """
    result = compute_readiness(_REPO, Preset.PRODUCTION)
    signal = next(
        s
        for d in result.dimensions.values()
        for s in d.signals
        if s.id == "output_language_present"
    )
    assert signal.passed is True, signal.evidence
    assert _MARKER in (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
