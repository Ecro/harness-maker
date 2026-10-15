"""The light lane's one reader: is a task on a trusted light lane, and did its light check pass."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Lane = Literal["light", "full"]

#: The `review_kind` a light-check record carries (SPEC-hm-light-lane-s3a IRR-002). A REVIEW
#: without it is a real review, and any real review for the slug disables the skip.
LIGHT_CHECK_KIND = "light-check"
_REVIEW_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _mapping(path: Path) -> dict[str, Any] | None:
    from harness_maker.frontmatter import split_frontmatter

    try:
        return split_frontmatter(path.read_bytes()).mapping
    except OSError:
        return None


def review_records(docs: Path, slug: str) -> list[Path]:
    """Every `REVIEW-<slug>-<YYYY-MM-DD>.md` in `docs`, oldest first.

    Exact names only: a hyphen-prefix slug (`world-model` vs `world-model-name`) must not pick up
    a sibling task's committed REVIEW (REVIEW a003ff68).
    """
    prefix = f"REVIEW-{slug}-"
    return sorted(
        p
        for p in (docs.glob(f"{prefix}*.md") if docs.is_dir() else [])
        if _REVIEW_DATE.fullmatch(p.name[len(prefix) : -len(".md")])
    )


def _checkout(base: Path, slug: str, checkout: Path | None) -> Path:
    from harness_maker.spec_machine import _resolve_checkout

    return _resolve_checkout(base, slug, checkout)


def lane_of(base: Path, slug: str | None, checkout: Path | None = None) -> Lane:
    """`light` only on exactly `lane: light`, an approved or exempt SPEC, no irreversible ids.

    Every other answer, including any read error, is `full`: the light lane removes two stages,
    so a SPEC nobody accepted, or one carrying a decision that cannot be cheaply undone, never
    earns it.
    """
    from harness_maker.spec_machine import _is_plain_slug, _named_spec_dir, approval_state

    try:
        if not slug or not _is_plain_slug(slug):
            return "full"
        root = _checkout(base, slug, checkout)
        fm = _mapping(_named_spec_dir(base, slug, root) / f"SPEC-{slug}.md")
        if fm is None or fm.get("lane") != "light":
            return "full"
        state = approval_state(base, slug, checkout)
        if state.state not in ("approved", "exempt") or state.irreversible:
            return "full"
        return "light"
    except Exception:  # noqa: BLE001 — an unreadable lane is the full lane, never a crash
        return "full"


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _record_passed(fm: dict[str, Any], slug: str, since: str | None) -> bool:
    verdict = fm.get("drift_verdict")
    if not (
        fm.get("review_kind") == LIGHT_CHECK_KIND
        and fm.get("status") == "PASSED"
        and fm.get("task_slug") == slug
        and isinstance(verdict, dict)
        and verdict.get("task_slug") == slug
        and verdict.get("result") == "clean"
    ):
        return False
    if since is None:
        return True
    computed, floor = _as_utc(verdict.get("computed_at")), _as_utc(since)
    return computed is not None and floor is not None and computed >= floor


def light_check_passed(
    base: Path, slug: str | None, checkout: Path | None = None, *, since: str | None = None
) -> bool:
    """True when the task's light check passed on the tree as it stands now.

    The record alone is not enough: it must be the newest REVIEW for the slug in the checkout,
    no real review may sit beside it, its drift verdict must postdate `since` (the autopilot
    marker's `created_at`), and verify Check 2's marker must be fresh for the current tree, so a
    record outlived by a later change never removes review and verify. The record lives under
    `work-docs/`, which the verification key ignores, so writing it does not stale the cache.
    """
    if not slug or lane_of(base, slug, checkout) != "light":
        return False
    try:
        root = _checkout(base, slug, checkout)
        records = review_records(root / "work-docs", slug)
        if not records:
            return False
        mappings = [_mapping(p) for p in records]
        if any(m is None or m.get("review_kind") != LIGHT_CHECK_KIND for m in mappings):
            return False
        newest = mappings[-1]
        if newest is None or not _record_passed(newest, slug, since):
            return False
        from harness_maker.observability import verification_cache

        key = verification_cache.compute_relevant_skip_key(root)
        return verification_cache.is_fresh(key) is not None
    except Exception:  # noqa: BLE001 — any read error means no skip
        return False
