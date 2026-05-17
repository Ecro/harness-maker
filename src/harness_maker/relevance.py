"""Relevance filter — adaptive threshold + simple keyword scorer + stale-asset scan.

For Phase 5 the scorer is intentionally lightweight: a keyword-overlap
heuristic over CrawlItem ``title`` + ``summary`` against a list of project
keywords (e.g. words extracted from CLAUDE.md / README.md). Phase 7+ will
plug in an LLM-driven scorer.

The adaptive-threshold algorithm follows ``phase_5_amendments.md §E``.

Stale-asset detection (``detect_stale_assets``) reads the ``last_reviewed_at``
annotation that domain packs and reviewer partials carry, and reports those
older than a configurable threshold. ``/hm:health`` consumes the result via
``build_proposal_lines`` to prompt the user (or write proposed-<date>.md under
autoloop). Accepted proposals are applied through ``update_last_reviewed_at``.

Version-drift detection moved out of this module as of 0.13.0 (PLAN
health-consolidation Phase 1). The single remaining caller — the SessionStart
drift hook — owns the implementation now (``harness_maker.hooks.sessionstart_drift``).
Removing it from ``relevance`` shrinks the public surface that ``/hm:health``
imports and eliminates the duplicate code path that previously needed to agree
with the hook on cache scanning.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import resources
from pathlib import Path

from harness_maker.io_utils import atomic_write
from harness_maker.llm_judge import JudgeClient
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


def _keyword_score(item: CrawlItem, project_keywords: list[str]) -> float:
    """Fallback: keyword-overlap heuristic when the LLM scorer is unreachable.

    Score = (unique project keywords matched in title+summary) / (total keywords).
    """
    if not project_keywords:
        return 0.0
    text = f"{item.title} {item.summary}".lower()
    haystack_tokens = set(_WORD_RE.findall(text))
    keyword_set = {k.lower().strip() for k in project_keywords if k.strip()}
    if not keyword_set:
        return 0.0
    matched = sum(1 for kw in keyword_set if kw in haystack_tokens)
    return matched / len(keyword_set)


_PROJECT_CTX_CHAR_CAP = 2000  # per file


def extract_project_context(project_dir: Path) -> str:
    """Build the relevance scorer's system-prompt context from project docs.

    Reads CLAUDE.md and README.md, capped at ``_PROJECT_CTX_CHAR_CAP`` chars
    each. Returns an empty string when neither exists; the LLM scorer treats
    that as "no signal" and defers to the keyword fallback.
    """
    parts: list[str] = []
    for name in ("CLAUDE.md", "README.md"):
        p = project_dir / name
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        snippet = text[:_PROJECT_CTX_CHAR_CAP]
        parts.append(f"--- {name} ---\n{snippet}")
    return "\n\n".join(parts)


def _build_relevance_system_prompt(project_context: str) -> str:
    return (
        "You score the relevance of a crawled research item to a specific "
        "project. Return JSON ONLY in the exact shape:\n"
        '  {"score": <float 0..1>, "rationale": "<one sentence>"}\n\n'
        "Higher score = more directly applicable to this project's tech "
        "stack, current work, or stated principles. Lower score = generic "
        "or unrelated.\n\n"
        f"Project context:\n{project_context}\n"
    )


def _parse_relevance_response(raw: str) -> tuple[float | None, str]:
    body = raw.strip()
    if body.startswith("```"):
        nl = body.find("\n")
        if nl != -1:
            body = body[nl + 1 :]
        if body.endswith("```"):
            body = body[:-3]
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None, "non-JSON LLM response"
    if not isinstance(data, dict):
        return None, "LLM response not an object"
    raw_score = data.get("score")
    rationale = data.get("rationale", "") if isinstance(data.get("rationale"), str) else ""
    if not isinstance(raw_score, int | float):
        return None, "missing score"
    return max(0.0, min(1.0, float(raw_score))), rationale


def score_item(
    item: CrawlItem,
    project_keywords: list[str] | None = None,
    *,
    project_context: str | None = None,
    client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
) -> float:
    """LLM-judged relevance with keyword-overlap fallback.

    When ``client`` and ``project_context`` are provided, the LLM scores the
    item against the project's CLAUDE.md / README.md. Any LLM failure
    (non-JSON, network, missing API key) falls back to the keyword scorer
    using ``project_keywords`` — the call site never crashes.
    """
    if client is not None and project_context:
        try:
            system = _build_relevance_system_prompt(project_context)
            user = f"Title: {item.title}\nSummary: {item.summary}\nSource: {item.source}"
            raw = client.judge(system, user, model)
        except Exception:  # noqa: BLE001 — LLM transport failures degrade gracefully
            raw = None
        if raw is not None:
            score, _rationale = _parse_relevance_response(raw)
            if score is not None:
                return score
    return _keyword_score(item, project_keywords or [])


def filter_items(items: list[CrawlItem], threshold: float) -> list[CrawlItem]:
    """Return items whose ``score`` is greater than or equal to ``threshold``."""
    return [item for item in items if item.score >= threshold]


def score(
    item: CrawlItem,
    project_keywords: list[str] | None = None,
    *,
    project_context: str | None = None,
    client: JudgeClient | None = None,
    model: str = "claude-sonnet-4-6",
) -> float:
    """Public alias for :func:`score_item` — kept for the verify-script entrypoint."""
    return score_item(
        item,
        project_keywords,
        project_context=project_context,
        client=client,
        model=model,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Stale-asset detection (Phase 5 → /hm:health Step 2)
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
    source: str  # "user" | "shipped" — distinguishes mutator target
    last_reviewed_at: date | None
    days_since_review: int  # threshold_days + 1 when last_reviewed_at is None
    threshold_days: int


def parse_last_reviewed_at(text: str) -> date | None:
    """Extract the ``last_reviewed_at`` date.

    Tolerant of YAML frontmatter, HTML comments, or Jinja comments — the regex
    matches the bare ``last_reviewed_at: YYYY-MM-DD`` substring regardless of
    enclosing syntax.
    """
    match = _LAST_REVIEWED_RE.search(text)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def resolve_template_dir() -> Path:
    """Locate harness-maker's templates/ directory at runtime.

    Templates ship inside the harness_maker package (``src/harness_maker/
    templates/``), so a single resolver handles both editable installs and
    wheel installs. ``importlib.resources`` returns a Traversable that
    ``as_file`` materialises to a real path — necessary for Jinja's
    ``FileSystemLoader`` and for ``Path.glob``.
    """
    try:
        traversable = resources.files("harness_maker").joinpath("templates")
        with resources.as_file(traversable) as tdir:
            if tdir.is_dir():
                return Path(tdir)
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    # Editable-install fallback — same directory ``Path(__file__).parent`` would
    # find, kept here as a defensive secondary in case the package metadata
    # lookup fails for an unusual install layout.
    return Path(__file__).resolve().parent / "templates"


def _scan_dir(
    root: Path,
    glob: str,
    asset_kind: str,
    source: str,
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
                    source=source,
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
                    source=source,
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
    ``<project_dir>/.claude/agents/_standards/*.md`` are scanned and tagged
    ``source="user"``. Shipped partials and samples live under
    ``template_dir`` (resolved via :func:`resolve_template_dir` when omitted)
    and are tagged ``source="shipped"`` so an accept handler can route the
    update to the correct location.
    """
    if isinstance(now, datetime):
        today = now.date()
    elif isinstance(now, date):
        today = now
    else:
        today = datetime.now(tz=UTC).date()

    if template_dir is None:
        template_dir = resolve_template_dir()

    stale: list[StaleAsset] = []
    stale.extend(
        _scan_dir(
            project_dir / ".claude" / "agents" / "_standards",
            "*.md",
            "domain-pack",
            "user",
            now=today,
            threshold_days=threshold_days,
        ),
    )
    stale.extend(
        _scan_dir(
            template_dir / "agents" / "_partials",
            "*.md.j2",
            "partial",
            "shipped",
            now=today,
            threshold_days=threshold_days,
        ),
    )
    stale.extend(
        _scan_dir(
            template_dir / "agents" / "_standards",
            "*.md.j2",
            "domain-pack",
            "shipped",
            now=today,
            threshold_days=threshold_days,
        ),
    )
    return stale


# ──────────────────────────────────────────────────────────────────────────────
# Mutator + proposal formatting (Phase 5 → /hm:health accept handler)
# ──────────────────────────────────────────────────────────────────────────────


class StaleAssetUpdateError(RuntimeError):
    """Raised when ``update_last_reviewed_at`` cannot rewrite the asset."""


def update_last_reviewed_at(path: Path, new_date: date | None = None) -> date:
    """Rewrite the asset's ``last_reviewed_at`` to ``new_date`` atomically.

    Accept handler for stale-asset proposals — only the date is touched; body
    is the user's responsibility. Raises if no annotation exists (the asset
    needs a one-time hand-edit before it can be tracked).
    """
    if new_date is None:
        new_date = datetime.now(tz=UTC).date()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        msg = f"cannot read {path}: {e}"
        raise StaleAssetUpdateError(msg) from e
    if _LAST_REVIEWED_RE.search(text) is None:
        msg = (
            f"{path} has no last_reviewed_at annotation; add one "
            "(YAML frontmatter or HTML comment) before /hm:health can track it"
        )
        raise StaleAssetUpdateError(msg)
    new_text = _LAST_REVIEWED_RE.sub(
        f"last_reviewed_at: {new_date.isoformat()}",
        text,
        count=1,
    )
    atomic_write(path, new_text)
    return new_date


# Version-drift detection moved to harness_maker.hooks.sessionstart_drift
# (PLAN health-consolidation Phase 1, ADR-006 / Interview #9). The hook is
# the sole consumer; ``/hm:health`` no longer surfaces version drift.


def build_proposal_lines(
    stale: list[StaleAsset],
    project_dir: Path,
) -> list[str]:
    """Format each StaleAsset for inclusion in proposed-<date>.md.

    Paths are reported relative to ``project_dir`` when possible so the
    output is portable across machines.
    """
    lines: list[str] = []
    for asset in stale:
        try:
            rel = asset.path.relative_to(project_dir)
            shown = str(rel)
        except ValueError:
            shown = str(asset.path)
        when = asset.last_reviewed_at.isoformat() if asset.last_reviewed_at else "(never)"
        lines.append(
            f"- [{asset.source}/{asset.asset_kind}] {shown} — "
            f"last_reviewed_at: {when}, "
            f"{asset.days_since_review} days since review "
            f"(threshold {asset.threshold_days})",
        )
    return lines
