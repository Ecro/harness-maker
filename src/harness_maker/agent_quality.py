"""Agent prompt quality scoring → Platinum/Gold/Silver/Bronze tier.

Hybrid score: static structural checks (line count, frontmatter, bullets)
combined with an optional Layer-2 LLM judgment against the shipped
``agent_prompt.yaml`` rubric. When a ``JudgeClient`` and ``rubric_dir`` are
provided, the LLM half lifts the score above the structural floor; on any
LLM failure we degrade to the static score with a logged warning.

Tier thresholds are preserved: composite ≥90 Platinum, ≥80 Gold, ≥70 Silver,
else Bronze (which auto-flags an agent for /hm:refresh anti-rot review).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from harness_maker.llm_judge import JudgeClient, judge_file
from harness_maker.rubric_loader import load_rubric_file

_LOG = logging.getLogger(__name__)


def _static_score(agent_md: Path) -> int:
    try:
        text = agent_md.read_text(encoding="utf-8")
    except OSError:
        return 0
    if not text.strip():
        return 0
    score = 0
    lines = text.splitlines()
    line_count = len(lines)
    if 100 <= line_count <= 500:
        score += 40
    elif 50 <= line_count < 100 or 500 < line_count <= 700:
        score += 20
    if text.startswith("---"):
        rest = text[4:]
        if "\n---" in rest:
            score += 30
    if any(line.lstrip().startswith(("-", "*", "+")) for line in lines) or "```" in text:
        score += 30
    return min(100, score)


def _tier(composite: int) -> str:
    if composite >= 90:
        return "Platinum"
    if composite >= 80:
        return "Gold"
    if composite >= 70:
        return "Silver"
    return "Bronze"


def score_agent(
    agent_md: Path,
    *,
    rubric_dir: Path | None = None,
    client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict[str, Any]:
    """Score one agent prompt and emit a tier.

    Args:
        agent_md: Path to ``.claude/agents/<name>.md``.
        rubric_dir: When provided alongside ``client``, points at the
            ``.claude/rubrics/`` directory; the ``agent_prompt.yaml`` rubric
            inside drives the LLM judgment.
        client: Optional LLM client (``JudgeClient`` Protocol). When omitted,
            the LLM half is skipped and the score reflects structural signals
            only.
        model: Anthropic model id passed through to the judge.

    Returns:
        ``{"static": int, "llm": int|None, "composite": int, "tier": str}``.
    """
    static = _static_score(agent_md)
    llm: int | None = None

    if client is not None and rubric_dir is not None:
        rubric_path = rubric_dir / "agent_prompt.yaml"
        rubric = load_rubric_file(rubric_path)
        if rubric is None:
            _LOG.warning("agent_quality: rubric not found at %s; static-only score", rubric_path)
        else:
            try:
                result = judge_file(agent_md, rubric, client=client, model=model)
            except Exception as e:  # noqa: BLE001 — LLM transport degrades gracefully
                _LOG.warning("agent_quality: LLM judge failed (%s); static-only score", e)
                result = None
            if result is not None and result.error is None:
                llm = result.score
            elif result is not None and result.error:
                _LOG.warning("agent_quality: LLM judge reported %s", result.error)

    composite = static if llm is None else (static + llm) // 2
    return {
        "static": static,
        "llm": llm,
        "composite": composite,
        "tier": _tier(composite),
    }
