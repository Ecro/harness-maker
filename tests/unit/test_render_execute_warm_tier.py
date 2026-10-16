"""AC-007 / P-11 — `/hm:execute`'s warm tier loads bodies, not slugs.

`execute.md.j2` was the only stage template still instructing a `failures.md` head-skim plus
`rg -F "[fail:"`. That returns a slug list: it says a failure class exists and not how to
recognise an instance — at the one stage where instances are created.

The negative half is what makes this non-vacuous. A template that adds the `memory_retrieve`
call while keeping the skim would pass a presence-only check and ship the same problem.

A.4 (justified pass): `test_execute_keeps_the_compaction_checkpoint_read` passes on the
unmodified template by design — a preservation guard that goes red if the edit removes the
hot-tier read. Its RED positive sibling is `test_execute_warm_tier_uses_memory_retrieve`.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates" / "stages"
EXECUTE_SRC = TEMPLATES / "execute.md.j2"


def _render_execute(tmp_path: Path) -> str:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "execute.md").read_text(encoding="utf-8")


def test_execute_warm_tier_uses_memory_retrieve(tmp_path: Path) -> None:
    body = _render_execute(tmp_path)
    assert "hm memory_retrieve" in body, "execute must invoke the retrieval helper"
    # Negative half — the slug scan must be gone, not merely accompanied.
    assert "first 60 lines" not in body
    assert 'rg -F "[fail:"' not in body


def test_execute_keeps_the_compaction_checkpoint_read(tmp_path: Path) -> None:
    """Regression guard: the hot-tier checkpoint read must survive this edit."""
    body = _render_execute(tmp_path)
    assert "checkpoint:compaction" in body
