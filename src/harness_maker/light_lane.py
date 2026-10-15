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
#: What each `checks` entry of a passing record may say (SPEC-hm-light-lane-s3a AC-016).
_PASSING_CHECKS: dict[str, frozenset[str]] = {
    "regression": frozenset({"pass"}),
    "security": frozenset({"pass"}),
    "mechanical": frozenset({"pass", "n-a"}),
    "spec_requirement": frozenset({"pass", "warn", "n-a"}),
}
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
    """`light` only on exactly `lane: light`, an approved or exempt SPEC, no irreversible ids,
    and a stamp that recorded `lane: light` itself (IRR-005).

    Every other answer, including any read error, is `full`: the light lane removes two stages,
    so a SPEC nobody accepted, or one carrying a decision that cannot be cheaply undone, never
    earns it. The approval hash covers only the machine yaml, so the `.md` lane counts only when
    the stamp agrees: a `full` -> `light` edit after approval, or a stamp older than the field,
    stays `full`.
    """
    from harness_maker.spec_machine import _is_plain_slug, _named_spec_dir, approval_state, load

    try:
        if not slug or not _is_plain_slug(slug):
            return "full"
        root = _checkout(base, slug, checkout)
        spec_dir = _named_spec_dir(base, slug, root)
        fm = _mapping(spec_dir / f"SPEC-{slug}.md")
        if fm is None or fm.get("lane") != "light":
            return "full"
        state = approval_state(base, slug, checkout)
        if state.state not in ("approved", "exempt") or state.irreversible:
            return "full"
        stamp = load(spec_dir / f"SPEC-{slug}.machine.yaml").approval
        if stamp is None or stamp.lane != "light":
            return "full"
        return "light"
    except Exception:  # noqa: BLE001 — an unreadable lane is the full lane, never a crash
        return "full"


def _as_utc(value: Any) -> datetime | None:
    """A zoned moment, or None: a date alone or a time without its zone says nothing exact."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return moment.astimezone(UTC) if moment.tzinfo is not None else None


def _record_passed(fm: dict[str, Any], slug: str, since: str | None, key: str) -> bool:
    """The record's own fields: a clean drift verdict for this slug, every check passing, the
    tree it checked (`verification_key`), and — given `since` — a zoned `computed_at` >= it."""
    verdict, checks = fm.get("drift_verdict"), fm.get("checks")
    if not (
        fm.get("review_kind") == LIGHT_CHECK_KIND
        and fm.get("status") == "PASSED"
        and fm.get("task_slug") == slug
        and fm.get("verification_key") == key
        and isinstance(verdict, dict)
        and verdict.get("task_slug") == slug
        and verdict.get("result") == "clean"
        and isinstance(checks, dict)
        and all(checks.get(name) in allowed for name, allowed in _PASSING_CHECKS.items())
    ):
        return False
    computed = _as_utc(verdict.get("computed_at"))
    if computed is None:
        return False
    if since is None:
        return True
    floor = _as_utc(since)
    return floor is not None and computed >= floor


def light_check_passed(
    base: Path, slug: str | None, checkout: Path | None = None, *, since: str | None = None
) -> bool:
    """True when the task's light check passed on the tree as it stands now.

    The record alone is not enough: it must be the newest REVIEW for the slug in the checkout,
    no real review may sit beside it, its drift verdict must postdate `since` (the autopilot
    marker's `created_at`), its `verification_key` must be the current tree's relevant key, and
    a marker `verification_cache run` wrote must be fresh for that key. So a record outlived by
    a later change never removes review and verify, even when a later Check 2 marked the new
    tree, and a `mark-pass` claim never stands in for the gates. The record lives under
    `work-docs/`, which the verification key ignores, so writing it does not move the key.
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
        from harness_maker.observability import verification_cache

        key = verification_cache.compute_relevant_skip_key(root)
        newest = mappings[-1]
        if newest is None or not _record_passed(newest, slug, since, key):
            return False
        marker = verification_cache.is_fresh(key)
        return marker is not None and marker.get("writer") == verification_cache.RUN_WRITER
    except Exception:  # noqa: BLE001 — any read error means no skip
        return False
