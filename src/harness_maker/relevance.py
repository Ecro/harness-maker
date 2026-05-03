"""Relevance filter — adaptive threshold + simple keyword scorer.

For Phase 5 the scorer is intentionally lightweight: a keyword-overlap
heuristic over CrawlItem ``title`` + ``summary`` against a list of project
keywords (e.g. words extracted from CLAUDE.md / README.md). Phase 7+ will
plug in an LLM-driven scorer.

The adaptive-threshold algorithm follows ``phase_5_amendments.md §E``.
"""

from __future__ import annotations

import re

from harness_maker.models import CrawlItem

DEFAULT_THRESHOLD = 0.7
THRESHOLD_MIN = 0.5
THRESHOLD_MAX = 0.9
WINDOW = 20  # last N decisions
MIN_SAMPLES = 5

# Tokenize on word boundaries (alnum + underscore).
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def adaptive_threshold(history: list[bool]) -> float:
    """Return the next-cycle threshold given an accept/reject decision history.

    ``history`` is ordered oldest → newest. Only the last ``WINDOW`` entries
    are used. Below ``MIN_SAMPLES`` the function returns ``DEFAULT_THRESHOLD``.

    Behaviour summary:
      * accept_rate > 0.8 → relax threshold downward (clamped at THRESHOLD_MIN)
      * accept_rate < 0.5 → tighten threshold upward (clamped at THRESHOLD_MAX)
      * otherwise → DEFAULT_THRESHOLD
    """
    recent = history[-WINDOW:]
    if len(recent) < MIN_SAMPLES:
        return DEFAULT_THRESHOLD
    accept_rate = sum(recent) / len(recent)
    if accept_rate > 0.8:
        relaxed = DEFAULT_THRESHOLD - 0.05 * (accept_rate - 0.8) / 0.2
        return max(THRESHOLD_MIN, relaxed)
    if accept_rate < 0.5:
        tightened = DEFAULT_THRESHOLD + 0.05 * (0.5 - accept_rate) / 0.5
        return min(THRESHOLD_MAX, tightened)
    return DEFAULT_THRESHOLD


def score_item(item: CrawlItem, project_keywords: list[str]) -> float:
    """Return a relevance score in ``[0, 1]`` from keyword overlap.

    Score = (unique project keywords matched) / (total unique project keywords).
    Returns 0.0 when ``project_keywords`` is empty.
    """
    if not project_keywords:
        return 0.0
    text = f"{item.title} {item.summary}".lower()
    haystack_tokens = set(_WORD_RE.findall(text))
    keyword_set = {k.lower().strip() for k in project_keywords if k.strip()}
    if not keyword_set:
        return 0.0
    # Token-set membership only — substring fallback caused false positives
    # (e.g. keyword "ai" matching "maintain"/"detail"). Word-boundary safe.
    matched = sum(1 for kw in keyword_set if kw in haystack_tokens)
    return matched / len(keyword_set)


def filter_items(items: list[CrawlItem], threshold: float) -> list[CrawlItem]:
    """Return items whose ``score`` is greater than or equal to ``threshold``."""
    return [item for item in items if item.score >= threshold]


# Backwards-compat alias used by .claude-verify.sh final_acceptance step.
def score(item: CrawlItem, project_keywords: list[str]) -> float:
    """Public alias for :func:`score_item` (used by external acceptance gate)."""
    return score_item(item, project_keywords)
