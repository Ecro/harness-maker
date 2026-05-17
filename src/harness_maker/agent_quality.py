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

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from harness_maker.cache import HttpCache
from harness_maker.llm_judge import JudgeClient, judge_file
from harness_maker.rubric_loader import load_rubric_file

_LOG = logging.getLogger(__name__)
_SKIP_TIERS = {"Platinum", "Gold"}


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


def _content_hash(agent_md: Path) -> str:
    try:
        content = agent_md.read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(content).hexdigest()[:16]


def _get_cached_score(agent_md: Path) -> dict[str, Any] | None:
    """Return previous score if tier was Platinum/Gold and content unchanged."""
    cache = HttpCache("agent-quality")
    key = hashlib.sha256(str(agent_md.resolve()).encode()).hexdigest()[:16]
    cached = cache.get(key, ttl=float("inf"))  # no TTL — content-based
    if not isinstance(cached, dict):
        return None
    if cached.get("tier") not in _SKIP_TIERS:
        return None
    if cached.get("content_hash") != _content_hash(agent_md):
        return None
    _LOG.info("agent_quality: skip (cached tier=%s) for %s", cached["tier"], agent_md.name)
    return cached


def _cache_score(agent_md: Path, result: dict[str, Any]) -> None:
    cache = HttpCache("agent-quality")
    key = hashlib.sha256(str(agent_md.resolve()).encode()).hexdigest()[:16]
    entry = {**result, "content_hash": _content_hash(agent_md)}
    cache.put(key, entry)


def score_agent(
    agent_md: Path,
    *,
    rubric_dir: Path | None = None,
    client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
    force: bool = False,
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
    if not force:
        cached = _get_cached_score(agent_md)
        if cached is not None:
            return {k: cached[k] for k in ("static", "llm", "composite", "tier") if k in cached}

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
    result = {
        "static": static,
        "llm": llm,
        "composite": composite,
        "tier": _tier(composite),
    }
    _cache_score(agent_md, result)
    return result
