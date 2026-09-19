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


def test_execute_names_where_its_topic_comes_from(tmp_path: Path) -> None:
    """Phase 3 exit criterion: copying the bare `<topic>` placeholder must not satisfy it.

    Nothing asserts the substitution at runtime (R11), so the rendered instruction has to
    say what to substitute. A placeholder topic returns a non-empty fence — more so with the
    count floor on, since floor entries are topic-independent — which is why a miss is silent.
    """
    body = _render_execute(tmp_path)
    idx = body.find("hm memory_retrieve")
    assert idx >= 0
    window = body[max(0, idx - 900) : idx + 400]
    assert "Substitute the topic before running" in window
    assert "PLAN slug" in window
    assert "never the literal `<topic>` placeholder" in window


def test_execute_explains_the_high_recurrence_section(tmp_path: Path) -> None:
    """A labelled section the reader cannot interpret is noise (AC-005's consumer half)."""
    body = _render_execute(tmp_path)
    assert "high-recurrence" in body
    assert "count floor" in body


def test_execute_invocation_is_is_codex_branched() -> None:
    """Same convention the other four stages use — Codex gets Bash(...), Claude gets `!`."""
    src = EXECUTE_SRC.read_text(encoding="utf-8")
    idx = src.find("hm memory_retrieve")
    assert idx >= 0
    assert "is_codex" in src[max(0, idx - 400) : idx]


def test_execute_keeps_the_compaction_checkpoint_read(tmp_path: Path) -> None:
    """Regression guard: the hot-tier checkpoint read must survive this edit."""
    body = _render_execute(tmp_path)
    assert "checkpoint:compaction" in body
