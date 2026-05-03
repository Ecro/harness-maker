"""Relevance filter — adaptive threshold + simple keyword scorer + stale-asset scan.

For Phase 5 the scorer is intentionally lightweight: a keyword-overlap
heuristic over CrawlItem ``title`` + ``summary`` against a list of project
keywords (e.g. words extracted from CLAUDE.md / README.md). Phase 7+ will
plug in an LLM-driven scorer.

The adaptive-threshold algorithm follows ``phase_5_amendments.md §E``.

Stale-asset detection (``detect_stale_assets``) reads the ``last_reviewed_at``
HTML comment that domain packs and reviewer partials carry, and reports those
older than a configurable threshold. ``/hm:refresh`` consumes the result to
prompt the user (or write proposed-<date>.md under autoloop).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

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


# ──────────────────────────────────────────────────────────────────────────────
# Stale-asset detection (Phase 5 — /hm:refresh anti-rot)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_STALE_DAYS = 90

_LAST_REVIEWED_RE = re.compile(
    r"last_reviewed_at:\s*[\"']?(\d{4}-\d{2}-\d{2})[\"']?",
)


@dataclass(frozen=True)
class StaleAsset:
    """One asset whose ``last_reviewed_at`` is past the threshold (or missing)."""

    path: Path
    asset_kind: str  # "domain-pack" | "partial"
    last_reviewed_at: date | None
    days_since_review: int  # threshold_days + 1 when last_reviewed_at is None
    threshold_days: int


def parse_last_reviewed_at(text: str) -> date | None:
    """Extract the ``last_reviewed_at`` date from a partial / domain-pack body.

    Tolerant of either YAML frontmatter or HTML-comment annotations — both
    forms are used in the templates.
    """
    match = _LAST_REVIEWED_RE.search(text)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _scan_dir(
    root: Path,
    glob: str,
    asset_kind: str,
    *,
    now: date,
    threshold_days: int,
) -> list[StaleAsset]:
    out: list[StaleAsset] = []
    if not root.is_dir():
        return out
    for asset in sorted(root.glob(glob)):
        try:
            text = asset.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Skip the user-authored skeleton template itself (template, not content).
        if asset.name.startswith("_template"):
            continue
        last = parse_last_reviewed_at(text)
        if last is None:
            out.append(
                StaleAsset(
                    path=asset,
                    asset_kind=asset_kind,
                    last_reviewed_at=None,
                    days_since_review=threshold_days + 1,
                    threshold_days=threshold_days,
                ),
            )
            continue
        delta = (now - last).days
        if delta > threshold_days:
            out.append(
                StaleAsset(
                    path=asset,
                    asset_kind=asset_kind,
                    last_reviewed_at=last,
                    days_since_review=delta,
                    threshold_days=threshold_days,
                ),
            )
    return out


def detect_stale_assets(
    project_dir: Path,
    *,
    now: datetime | date | None = None,
    threshold_days: int = DEFAULT_STALE_DAYS,
    template_dir: Path | None = None,
) -> list[StaleAsset]:
    """Return stale partials + domain packs from project + harness-maker templates.

    ``project_dir`` is the user project root; user-authored domain packs at
    ``<project_dir>/.claude/agents/_standards/*.md`` are scanned. Shipped
    partials live under ``template_dir`` (defaults to harness-maker's own
    ``templates/`` directory) — these typically only go stale during package
    upgrade, but surfacing them lets ``/hm:refresh`` prompt for explicit
    review when 90+ days have passed.
    """
    if isinstance(now, datetime):
        today = now.date()
    elif isinstance(now, date):
        today = now
    else:
        today = datetime.now().date()  # noqa: DTZ005 — date-only comparisons

    if template_dir is None:
        # Resolve harness-maker's own templates/ relative to this module.
        template_dir = Path(__file__).resolve().parent.parent.parent / "templates"

    stale: list[StaleAsset] = []
    stale.extend(
        _scan_dir(
            project_dir / ".claude" / "agents" / "_standards",
            "*.md",
            "domain-pack",
            now=today,
            threshold_days=threshold_days,
        ),
    )
    stale.extend(
        _scan_dir(
            template_dir / "agents" / "_partials",
            "*.md.j2",
            "partial",
            now=today,
            threshold_days=threshold_days,
        ),
    )
    stale.extend(
        _scan_dir(
            template_dir / "agents" / "_standards",
            "*.md.j2",
            "domain-pack",
            now=today,
            threshold_days=threshold_days,
        ),
    )
    return stale
