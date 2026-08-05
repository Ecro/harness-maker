"""AC-001 of SPEC-workflow-loop-efficiency — the Pass 1.5 verifier dispatch is gone.

ADR-001 removed it because it was a full serialized agent round-trip on the critical
path of every review round while nothing else ran, and it dropped 5 of 261 findings
(1.9%) across 41 archived reviews. This file is the standing proof it stays removed.

Three things this file must NOT assert, because removing them would be a different and
wrong change:
  * the `code-verifier` **agent** — still rendered, still live for cross-model PIDA
    mode B at Step 3.7. Only the mode A *dispatch* from the review stage is gone.
  * `#### Pass 1` / `#### Pass 2` — the two-pass redaction structure is untouched.
  * the string "Pass 1.5" in prose — the removal notices deliberately name it, so a
    bare substring check would fail on the very text that documents the removal. The
    discovery below is dispatch-shaped, not word-shaped.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, SecondOpinionConfig, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

_LOOP_HEADING = "## Auto-Fix Loop"
_H4_BLOCK = re.compile(r"^####\s.*?(?=^####\s|^###\s|\Z)", re.MULTILINE | re.DOTALL)
#: A Pass 1.5 site is an h4 dispatch block that both announces the pass AND orders the
#: verifier to run. Requiring both is what keeps a removal notice from counting as one.
_PASS15_HEADING = re.compile(r"^####\s*Pass\s*1\.5\b", re.MULTILINE)
_DISPATCHES_VERIFIER = re.compile(
    r'subagent_type="code-verifier"|Task\([^)]*code-verifier|invoke the `?code-verifier`? agent',
    re.IGNORECASE,
)


def count_pass15_verifier_dispatches(rendered_commands: dict[str, str]) -> int:
    """AC-001's free symbol. Counts Pass 1.5 verifier dispatch SITES, not mentions."""
    total = 0
    for text in rendered_commands.values():
        for block in _H4_BLOCK.findall(text):
            if _PASS15_HEADING.search(block) and _DISPATCHES_VERIFIER.search(block):
                total += 1
    return total


@cache
def _render_root() -> Path:
    """Production across all three targets — the cursor/codex surfaces render too."""
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]
    answers.second_opinion = SecondOpinionConfig(models=["codex", "antigravity"])
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-pass15-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root


@cache
def rendered_commands() -> dict[str, str]:
    """Every rendered document that inlines the review stage, discovered by content."""
    root = _render_root()
    return {
        str(path.relative_to(root)): text
        for path in sorted(root.rglob("*.md"))
        if _LOOP_HEADING in (text := path.read_text(encoding="utf-8"))
    }


def test_the_discovery_is_not_empty() -> None:
    """Positive control — `== 0` over an empty corpus holds in every possible world.

    All three artifact families must be present; the codex one is what a claude-only
    fixture cannot see, and it is a separate synthesis path (`synthesize._COMMUNICATION_
    VARIANT` and friends), so a removal that missed it would be invisible without this.
    """
    found = rendered_commands()
    assert ".claude/commands/hm/review.md" in found
    assert ".claude/stages/review.md" in found
    assert ".agents/skills/hm-review/SKILL.md" in found


def test_the_counter_discriminates_against_the_pre_change_render() -> None:
    """The anti-tautology arm: the counter must find the site on the frozen golden.

    Without this, `count_pass15_verifier_dispatches` could be a function that returns 0
    for every input — it would pass AC-001 while gating nothing at all.
    """
    golden = (_FIXTURES / "review_command_pre_change.md").read_text(encoding="utf-8")
    assert count_pass15_verifier_dispatches({"golden": golden}) >= 1


def test_ac_001_no_pass15_verifier_in_rendered_review() -> None:
    """AC-001's executable predicate, verbatim."""
    assert count_pass15_verifier_dispatches(rendered_commands()) == 0


def test_pass2_consumes_the_raw_pass1_findings() -> None:
    """The data-flow half. Absence of the dispatch does not prove the input was rewired.

    A removal that deleted the Task call but left Pass 2 reading `kept` would render a
    stage instructing the model to consume a list nothing produces — silently empty
    input to the contextual pass, which is worse than the round-trip it replaced.
    """
    for name, text in rendered_commands().items():
        assert "raw Pass 1 findings" in text, f"{name}: Pass 2's input is not named as raw"
        assert not re.search(r"`kept`\s+as the input to Pass 2", text), (
            f"{name}: Pass 2 still consumes the removed verifier's `kept` output"
        )


def test_the_code_verifier_agent_survives_for_mode_b() -> None:
    """Scope guard — ADR-001 removed a dispatch, not the agent."""
    body = (_render_root() / ".claude" / "agents" / "code-verifier.md").read_text(encoding="utf-8")
    assert "Mode B" in body
    assert "assume mode B" in body, "the unlabelled-invocation default is not mode B"
