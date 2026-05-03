"""Autoloop driver (M7) — orchestrate unattended `/hm:loop` iterations.

Per architecture M7: token-unlimited, time + iter capped. The driver consumes
either:

- A free-form `goal` string parsed into a feature list via `parse_goal`, or
- A structured `LoopSpec` (loaded from `.claude/loop-specs/<slug>.yaml`) with
  per-feature acceptance criteria, a one-line objective, and a convergence
  predicate.

Each iteration: pick next un-completed feature → invoke executor → update
state → check convergence. Safety rails: 3 consecutive failures stop the
loop; every 5 iterations emits a ping log; time/iter caps stop with
`converged=False`.

The `executor` argument is a callable injected by the caller. Its contract:
`executor(feature: Feature, iter_idx: int) -> bool` — True on success, False
on failure. The executor receives the feature's AC so the per-iteration
workflow can ground its work on testable criteria. `dry_run=True` skips the
executor entirely (single iteration that marks all features completed).
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class Feature(BaseModel):
    """One unit of work the autoloop iterates on."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    acceptance_criteria: list[str] = Field(default_factory=list)


class LoopSpec(BaseModel):
    """Structured input for `/hm:loop --spec`. Persisted as YAML."""

    model_config = ConfigDict(strict=True, extra="forbid")

    objective: str
    features: list[Feature]
    convergence: str = "all-features-completed"


# Type alias: executor takes a Feature (with AC) so per-iteration workflows can
# ground implementation against testable criteria.
ExecutorCallable = Callable[[Feature, int], bool]


class AutoloopState(BaseModel):
    """Mutable state passed across iterations + returned at end of run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    iter: int = 0
    time_started: float = 0.0
    objective: str = ""
    features: list[Feature] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)  # by feature name
    failed_streak: int = 0
    converged: bool = False
    stop_reason: str = ""


# Strict separators only: newline, semicolon, Korean enumeration marker ·.
# Period and comma are NOT separators because they routinely appear inside
# version numbers (v1.2.3), URLs (api.x.com/v1), and decimals (3.14) — naive
# split mangles legitimate goals into junk feature names.
_SPLIT_RE = re.compile(r"[;\n·]+")


def parse_goal(goal: str) -> list[Feature]:
    """Split a free-form goal string into Feature objects with empty AC.

    Strict separators (`;`, newline, `·`) only. Period/comma kept inside features
    to preserve version numbers, URLs, decimals. Returns single-element list
    when no separator present (whole goal becomes one Feature).
    """
    parts = [p.strip() for p in _SPLIT_RE.split(goal) if p.strip()]
    if parts:
        return [Feature(name=p) for p in parts]
    stripped = goal.strip()
    return [Feature(name=stripped)] if stripped else []


def parse_loop_spec(path: Path) -> LoopSpec:
    """Load + validate a YAML loop-spec from disk."""
    raw = path.read_text(encoding="utf-8")
    # Strip provenance frontmatter if present (renderer may have wrapped it).
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            raw = raw[end + 5 :]
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"loop-spec at {path} is not a YAML mapping"
        raise ValueError(msg)
    return LoopSpec.model_validate(data)


def is_loop_consumable(text: str) -> bool:
    """Cheap heuristic: does this text parse as a LoopSpec YAML?

    Returns True when the input is YAML with `objective`, `features`, and at
    least one feature having a `name`. Markdown / arbitrary prose returns False
    so the `/hm:loop` command knows to trigger the conditioning interview.
    """
    if not text.strip():
        return False
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    if "objective" not in data or "features" not in data:
        return False
    features = data.get("features")
    if not isinstance(features, list) or not features:
        return False
    return all(isinstance(f, dict) and f.get("name") for f in features)


def _default_executor(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
    """Dry-run no-op executor — always succeeds, never touches disk."""
    return True


_CONVERGENCE_PREDICATES: dict[str, Callable[[AutoloopState], bool]] = {
    "all-features-completed": lambda s: (
        bool(s.features) and all(f.name in s.completed for f in s.features)
    ),
    "any-feature-completed": lambda s: any(f.name in s.completed for f in s.features),
    "min-2-features": lambda s: len(s.completed) >= 2,
    "min-5-features": lambda s: len(s.completed) >= 5,
    "first-iter": lambda s: s.iter >= 1,
}


def _check_convergence(
    state: AutoloopState,
    convergence: str | None,
) -> bool:
    """Return True when the loop should terminate as converged.

    Default (convergence=None): every feature is in `state.completed`.
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
    return all(f.name in state.completed for f in state.features)


def run(  # noqa: PLR0913
    goal: str | None = None,
    *,
    spec: LoopSpec | None = None,
    time_h: float = 8.0,
    max_iter: int = 30,
    dry_run: bool = False,
    workflow: str = "exec-rev-wrap",  # noqa: ARG001 — opaque, passed by /hm:loop
    convergence: str | None = None,
    executor: ExecutorCallable | None = None,
) -> AutoloopState:
    """Run the autoloop until converged, capped by time_h or max_iter.

    Either `goal` (free-form string) or `spec` (structured LoopSpec) must be
    provided. When both are given, `spec` wins. The structured `spec` carries
    per-feature acceptance criteria, an objective, and a convergence predicate
    (which the `convergence=` argument can still override).
    """
    features: list[Feature]
    objective: str
    effective_convergence: str | None
    if spec is not None:
        features = list(spec.features)
        objective = spec.objective
        effective_convergence = convergence or spec.convergence
    elif goal is not None:
        features = parse_goal(goal)
        objective = ""
        effective_convergence = convergence
    else:
        msg = "run() requires either `goal` or `spec`"
        raise ValueError(msg)

    state = AutoloopState(
        time_started=time.time(),
        features=features,
        objective=objective,
    )
    time_cap_s = time_h * 3600.0

    if dry_run:
        state.iter = 1
        state.completed = [f.name for f in state.features]
        state.converged = _check_convergence(state, effective_convergence)
        state.stop_reason = "dry_run"
        return state

    active_executor: ExecutorCallable = executor or _default_executor

    while True:
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
        if _check_convergence(state, effective_convergence):
            state.converged = True
            state.stop_reason = "converged"
            break

        remaining = [f for f in state.features if f.name not in state.completed]
        if not remaining:
            state.converged = _check_convergence(state, effective_convergence)
            state.stop_reason = "no_remaining_features"
            break
        next_feature = remaining[0]

        state.iter += 1
        if state.iter % 5 == 0:
            logger.info(
                "autoloop ping: iter=%d feature=%s",
                state.iter,
                next_feature.name,
            )

        try:
            success = active_executor(next_feature, state.iter)
        except Exception:
            logger.exception("executor raised on feature=%s", next_feature.name)
            success = False

        if success:
            state.completed.append(next_feature.name)
            state.failed_streak = 0
        else:
            state.failed_streak += 1

    return state
