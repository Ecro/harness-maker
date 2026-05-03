"""Agent quality scoring (Platinum/Gold/Silver/Bronze) per amendment §G."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class LLMJudge(Protocol):
    """Optional LLM-based agent prompt evaluator (0-100)."""

    def judge(self, prompt: str) -> int: ...


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
        # Look for closing frontmatter delimiter
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


def score_agent(agent_md: Path, judge: LLMJudge | None = None) -> dict[str, Any]:
    """Score an agent .md file across (a) static structure, (b) LLM judge, (c) Monte Carlo.

    Returns dict with composite + tier (Platinum >=90 / Gold >=80 / Silver >=70 / Bronze else).
    """
    static = _static_score(agent_md)
    llm: int | None = None
    if judge is not None:
        try:
            llm = int(judge.judge(agent_md.read_text(encoding="utf-8")))
        except OSError:
            llm = 0
    monte_carlo = 100  # placeholder (Phase 4)
    if llm is None:
        weights = {"static": 1.0, "llm": 0.0, "consistency": 0.0}
    else:
        weights = {"static": 0.4, "llm": 0.3, "consistency": 0.3}
    composite_f = (
        static * weights["static"]
        + (llm or 0) * weights["llm"]
        + monte_carlo * weights["consistency"]
    )
    composite = int(composite_f)
    return {
        "static": static,
        "llm": llm,
        "monte_carlo": monte_carlo,
        "composite": composite,
        "tier": _tier(composite),
    }
