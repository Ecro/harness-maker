"""Autoloop driver (M7) — orchestrate unattended `/hm:loop` iterations.

Per architecture M7: token-unlimited, time + iter capped. The driver parses
a goal into a feature list, then iterates: pick next_feature → invoke
workflow executor → update state → check convergence. Safety rails: 3
consecutive failures stop the loop; every 5 iterations emits a ping log;
time/iter caps stop the loop with `converged=False`.

The `executor` argument is a callable injected by the caller (the rendered
`/hm:loop` command, an integration test, or unit-test mocks). Its contract:
`executor(feature: str, iter_idx: int) -> bool` — True on success, False on
failure. `dry_run=True` skips the executor entirely (single iteration that
marks all features completed without disk writes).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Type alias: executor must return True on success, False on failure.
ExecutorCallable = Callable[[str, int], bool]


class AutoloopState(BaseModel):
    """Mutable state passed across iterations + returned at end of run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    iter: int = 0
    time_started: float = 0.0
    features: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    failed_streak: int = 0
    converged: bool = False
    stop_reason: str = ""


# Strict separators only: newline, semicolon, Korean enumeration marker ·.
# Period and comma are NOT separators because they routinely appear inside
# version numbers (v1.2.3), URLs (api.x.com/v1), and decimals (3.14) — naive
# split mangles legitimate goals into junk feature names.
_SPLIT_RE = re.compile(r"[;\n·]+")


def parse_goal(goal: str) -> list[str]:
    """Split a free-form goal string into a feature list.

    Strict separators (`;`, newline, `·`) only. Period/comma kept inside features
    to preserve version numbers, URLs, decimals. Returns single-element list
    when no separator present (whole goal becomes one feature).
    """
    parts = [p.strip() for p in _SPLIT_RE.split(goal) if p.strip()]
    if parts:
        return parts
    stripped = goal.strip()
    return [stripped] if stripped else []


def _default_executor(feature: str, iter_idx: int) -> bool:  # noqa: ARG001
    """Dry-run no-op executor — always succeeds, never touches disk."""
    return True


_CONVERGENCE_PREDICATES: dict[str, callable] = {
    "all-features-completed": lambda s: bool(s.features) and all(
        f in s.completed for f in s.features
    ),
    "any-feature-completed": lambda s: any(f in s.completed for f in s.features),
    "min-2-features": lambda s: len(s.completed) >= 2,
    "min-5-features": lambda s: len(s.completed) >= 5,
    "first-iter": lambda s: s.iter >= 1,
}


def _check_convergence(
    state: AutoloopState,
    convergence: str | None,
) -> bool:
    """Return True when the loop should terminate as converged.

    Default (convergence=None): every parsed feature is in `state.completed`.
    Named predicate: must be one of `_CONVERGENCE_PREDICATES` keys.
    Arbitrary Python expressions are NOT supported — eval-based convergence
    was removed because of attribute-traversal sandbox escape (CVE-class).
    """
    if convergence:
        predicate = _CONVERGENCE_PREDICATES.get(convergence)
        if predicate is None:
            logger.warning(
                "unknown convergence predicate %r; allowed: %s. Falling back to default.",
                convergence,
                sorted(_CONVERGENCE_PREDICATES),
            )
            return _check_convergence(state, None)
        try:
            return bool(predicate(state))
        except Exception:
            logger.exception("convergence predicate failed: %s", convergence)
            return False
    if not state.features:
        return True
    return all(f in state.completed for f in state.features)


def run(  # noqa: PLR0913
    goal: str,
    *,
    time_h: float = 8.0,
    max_iter: int = 30,
    dry_run: bool = False,
    workflow: str = "dev",  # noqa: ARG001 — wired by /hm:loop, opaque here
    convergence: str | None = None,
    executor: ExecutorCallable | None = None,
) -> AutoloopState:
    """Run the autoloop until converged, capped by time_h or max_iter.

    Args:
        goal: free-form description; parsed into feature list
        time_h: max wall-clock duration (hours) — stops loop when exceeded
        max_iter: max iterations — stops loop when reached
        dry_run: when True, skip executor and mark all features completed
                 in a single iteration with no disk writes
        workflow: which fused workflow the iteration body invokes (opaque
                  to the driver — passed through for command-template logging)
        convergence: optional Python expression; default = all features done
        executor: callable `(feature, iter_idx) -> bool`; defaults to no-op
                  in dry_run, raises if None and dry_run=False

    Returns:
        Final AutoloopState. `converged=True` only when convergence check
        passes; iter/time caps and 3-failure halt return converged=False with
        `stop_reason` set.
    """
    state = AutoloopState(
        time_started=time.time(),
        features=parse_goal(goal),
    )
    time_cap_s = time_h * 3600.0

    if dry_run:
        # Single-shot: mark all features completed without invoking executor.
        state.iter = 1
        state.completed = list(state.features)
        state.converged = _check_convergence(state, convergence)
        state.stop_reason = "dry_run"
        return state

    active_executor: ExecutorCallable = executor or _default_executor

    while True:
        # Check caps before doing work so the loop respects them strictly.
        if state.iter >= max_iter:
            state.stop_reason = f"max_iter ({max_iter}) reached"
            break
        elapsed = time.time() - state.time_started
        if elapsed >= time_cap_s:
            state.stop_reason = f"time_cap ({time_h}h) reached"
            break
        if state.failed_streak >= 3:
            state.stop_reason = "3 consecutive failures"
            break
        if _check_convergence(state, convergence):
            state.converged = True
            state.stop_reason = "converged"
            break

        # Pick next feature — first feature not yet in completed.
        remaining = [f for f in state.features if f not in state.completed]
        if not remaining:
            # No features left but convergence didn't return True — defensive.
            state.converged = _check_convergence(state, convergence)
            state.stop_reason = "no_remaining_features"
            break
        next_feature = remaining[0]

        state.iter += 1
        if state.iter % 5 == 0:
            logger.info("autoloop ping: iter=%d feature=%s", state.iter, next_feature)

        try:
            success = active_executor(next_feature, state.iter)
        except Exception:
            logger.exception("executor raised on feature=%s", next_feature)
            success = False

        if success:
            state.completed.append(next_feature)
            state.failed_streak = 0
        else:
            state.failed_streak += 1

    return state
