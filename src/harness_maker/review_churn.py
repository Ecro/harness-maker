"""Per-round fix churn: config resolution today, measurement in a later phase."""

from __future__ import annotations

from typing import Any

DEFAULT_CHURN_RATIO = 0.20
"""Fraction of a touched file's LOC above which a repair round re-reviews.

0.20 comes from the source experiment, whose subject was a 156-line Python
module in another codebase — hence the config key. It is a starting point to be
recalibrated from the ratios the loop records, not a measured property of this
project (PLAN risk R3).
"""

_RATIO_KEY = "rereview_churn_ratio"
_GATE_KEY = "rereview_churn_gate"


class ChurnConfigError(ValueError):
    """A present-but-malformed churn setting.

    Fail loudly rather than falling back to the default: a silent fallback makes
    a typo indistinguishable from a deliberate value, and the gate it feeds
    decides whether a review happens at all.
    """


def resolve_churn_threshold(reviewers: dict[str, Any]) -> float:
    """Absent key -> the documented default; present key -> validated.

    The absent case is the one that actually ships: harnesses rendered before
    this key existed have no `reviewers.rereview_churn_ratio`, and a feature that
    no-ops for them would never fire for the data that motivated it
    (CLAUDE.md learned correction 2026-06-08).
    """
    if _RATIO_KEY not in reviewers:
        return DEFAULT_CHURN_RATIO

    raw = reviewers[_RATIO_KEY]
    if isinstance(raw, bool):  # bool is an int subclass — reject before the numeric path
        raise ChurnConfigError(f"{_RATIO_KEY} must be a number in [0, 1], got a bool: {raw!r}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as e:
        raise ChurnConfigError(f"{_RATIO_KEY} must be a number in [0, 1], got {raw!r}") from e

    if not (0.0 <= value <= 1.0):
        raise ChurnConfigError(f"{_RATIO_KEY} must be within [0, 1], got {value!r}")
    return value


def churn_gate_enabled(reviewers: dict[str, Any]) -> bool:
    """Absent key -> on.

    The gate defaults on so the ratios accrue; a harness that regresses turns it
    off in one line rather than pinning an old plugin version (ADR-004).
    """
    if _GATE_KEY not in reviewers:
        return True

    raw = reviewers[_GATE_KEY]
    if not isinstance(raw, bool):
        raise ChurnConfigError(f"{_GATE_KEY} must be a bool, got {raw!r}")
    return raw
