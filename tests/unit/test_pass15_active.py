"""Pass 1.5 is REMOVED (ADR-001) — this file used to assert the opposite.

**Read this before editing.** Until 2026-08-05 every test here asserted the Pass 1.5
verifier was *active*, and after the dispatch was deleted they all still passed — on the
prose of the removal notice. `assert "Pass 1.5" in review` matched the sentence explaining
that Pass 1.5 is gone; `assert "code-verifier" in review` matched the same sentence saying
the agent survives for mode B; `"verified findings" in pass2 or "Pass 1.5" in pass2` passed
through its second arm because the notice sits immediately before the Pass 2 heading.

Three green tests asserting a shipped behaviour that no longer existed. That is
`[fail:test] test-pins-retired-implementation-name` compounded by a substring predicate
loose enough to match documentation *about* the removal — the file had stopped gating
anything while still reading as the authority on this behaviour.

Kept and inverted rather than deleted, because the risk it now guards is real: someone
re-introducing a Pass 1.5 dispatch would otherwise face no test here at all. The assertions
are dispatch-shaped, never word-shaped. `tests/structural/test_review_pass15_removed.py`
carries AC-001's binding and the same discovery over all three render targets.
"""

from __future__ import annotations

import re
from pathlib import Path

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_H4_BLOCK = re.compile(r"^####\s.*?(?=^####\s|^###\s|\Z)", re.MULTILINE | re.DOTALL)
_PASS15_HEADING = re.compile(r"^####\s*Pass\s*1\.5\b", re.MULTILINE)
_DISPATCHES_VERIFIER = re.compile(
    r'subagent_type="code-verifier"|Task\([^)]*code-verifier', re.IGNORECASE
)


def _render_preset(tmp_path: Path, preset: Preset) -> Path:
    profile = (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )
    a = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, a, preset=preset)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _review(tmp_path: Path, preset: Preset = Preset.PRODUCTION) -> str:
    out = _render_preset(tmp_path, preset)
    return (out / "stages" / "review.md").read_text(encoding="utf-8")


def test_no_pass_15_verifier_dispatch_remains(tmp_path: Path) -> None:
    """Dispatch-shaped, not word-shaped.

    A bare `"Pass 1.5" not in review` would fail on the removal notice — the very text that
    documents the removal — so the naive inverse is wrong in both directions.
    """
    review = _review(tmp_path)
    blocks = _H4_BLOCK.findall(review)
    # Positive control. This is a NEGATIVE assertion, so it also passes when the matchers
    # match nothing at all — a heading-level change or a new dispatch syntax would make it
    # green while gating nothing, which is how the previous version of this file died.
    assert blocks, "the h4 block matcher found nothing — the negative assertion is vacuous"
    assert _DISPATCHES_VERIFIER.search('subagent_type="code-verifier"'), (
        "the dispatch matcher no longer recognises this repo's dispatch syntax"
    )
    sites = [b for b in blocks if _PASS15_HEADING.search(b) and _DISPATCHES_VERIFIER.search(b)]
    assert sites == [], (
        f"a Pass 1.5 verifier dispatch is back: {[s.splitlines()[0] for s in sites]}"
    )


def test_pass_2_consumes_the_raw_pass_1_findings(tmp_path: Path) -> None:
    """The data-flow half.

    Deleting the dispatch while leaving Pass 2 reading the verifier's `kept` output would
    render a stage instructing the model to consume a list nothing produces — silently
    empty input to the contextual pass, worse than the round-trip it replaced.
    """
    review = _review(tmp_path)
    assert "raw Pass 1 findings" in review
    assert not re.search(r"`kept`\s+as the input to Pass 2", review)


def test_the_code_verifier_agent_still_ships_for_mode_b(tmp_path: Path) -> None:
    """Scope guard — ADR-001 removed a dispatch, not the agent.

    Mode B (cross-model PIDA) is still live at review Step 3.6, so deleting the agent would
    break a path this change never touched.
    """
    out = _render_preset(tmp_path, Preset.PRODUCTION)
    agent = out / "agents" / "code-verifier.md"
    assert agent.is_file()
    body = agent.read_text(encoding="utf-8")
    assert "Mode B" in body
    assert "assume mode B" in body, "an unlabelled invocation no longer defaults to mode B"
