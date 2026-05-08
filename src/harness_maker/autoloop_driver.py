"""Autoloop driver (M7) — orchestrate unattended `/hm:loop` iterations.

Per architecture M7: token-unlimited, time + iter capped. The driver consumes
either:

- A free-form `goal` string parsed into a feature list via `parse_goal`, or
- A structured `LoopSpec` (loaded from `.claude/loop-specs/<slug>.yaml`).

Two modes (LoopMode):
- `feature` (default): pick next un-completed Feature → invoke executor →
  update state → check convergence. The executor is the configured fused
  workflow. Convergence is predicate-based.
- `improve`: continuous improvement cycle (review → fix → test → review) until
  LLM judges stopping criteria met. No feature list; context captured via a
  coverage-driven adaptive interview persisted to
  `work-docs/loop-context/<slug>.yaml` as a LoopContext.

Key types:
- `LoopMode` — FEATURE | IMPROVE
- `ImprovementContext` — five required interview dimensions (purpose,
  invariants, priority, test_reliability, stopping_criteria) plus notes
- `LoopContext` — persisted context wrapper with slug, source, timestamps
- `Feature` — one unit of work with name + acceptance_criteria
- `LoopSpec` — structured loop input: mode, objective, features, convergence,
  target, context_ref, and optional inline ImprovementContext
- `AutoloopState` — mutable run state returned by `run()`

Safety rails: 3 consecutive failures stop the loop; every 5 iterations emits
a ping log; time/iter caps stop with `converged=False`.

The `executor` argument is a callable injected by the caller. Its contract:
`executor(feature: Feature, iter_idx: int) -> bool` — True on success, False
on failure. `dry_run=True` skips the executor (single iteration, all features
marked completed).

**`run()` is feature-mode only.** Improve mode orchestration is entirely
prompt-driven inside `/hm:loop` and does not go through `run()`.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class LoopMode(StrEnum):
    """Execution mode that determines loop body behaviour."""

    FEATURE = "feature"
    IMPROVE = "improve"


class ImprovementContext(BaseModel):
    """Five required dimensions captured by the adaptive interview.

    Persisted inside LoopContext. Also embedded inline in LoopSpec when
    context_ref is not used.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    purpose: str
    invariants: list[str] = Field(default_factory=list)
    priority: str
    test_reliability: str
    stopping_criteria: str
    notes: list[str] = Field(default_factory=list)


class LoopContext(BaseModel):
    """Persisted to work-docs/loop-context/<slug>.yaml.

    Survives across multiple loop runs on the same project/target so the
    adaptive interview doesn't repeat already-answered questions.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    slug: str
    source: str = ""
    created_at: str
    updated_at: str
    context: ImprovementContext


class Feature(BaseModel):
    """One unit of work the autoloop iterates on."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    acceptance_criteria: list[str] = Field(default_factory=list)


class LoopSpec(BaseModel):
    """Structured input for `/hm:loop --spec`. Persisted as YAML."""

    model_config = ConfigDict(strict=True, extra="forbid")

    objective: str
    features: list[Feature] = Field(default_factory=list)
    convergence: str = "all-features-completed"
    mode: LoopMode = LoopMode.FEATURE
    target: str = ""
    context_ref: str = ""
    context: ImprovementContext | None = None

    @field_validator("mode", mode="before")
    @classmethod
    def _coerce_mode(cls, v: object) -> LoopMode:
        if isinstance(v, LoopMode):
            return v
        if isinstance(v, str):
            return LoopMode(v)
        msg = f"mode must be a string, got {type(v).__name__}"
        raise ValueError(msg)

    @model_validator(mode="after")
    def _default_convergence_by_mode(self) -> LoopSpec:
        """Set convergence to stopping-criteria when mode=improve and convergence
        is still the class-level default (all-features-completed never converges
        with an empty features list, so the default is wrong for improve mode).
        """
        if self.mode == LoopMode.IMPROVE and self.convergence == "all-features-completed":
            self.convergence = "stopping-criteria"
        return self


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

# Keywords that signal the user wants a continuous-improvement loop rather than
# a feature-implementation loop. Matched case-insensitively against the goal.
_IMPROVE_KEYWORDS: frozenset[str] = frozenset(
    {
        "improve",
        "refactor",
        "quality",
        "clean",
        "optimize",
        "review loop",
        "코드 품질",
        "리팩토링",
        "개선",
        "cleanup",
        "code review",
    }
)


def detect_mode(goal: str) -> LoopMode:
    """Infer loop mode from free-form goal text.

    Keyword match → IMPROVE; everything else → FEATURE. Explicit --mode flag
    is resolved upstream before this is called.
    """
    lowered = goal.lower()
    if any(kw in lowered for kw in _IMPROVE_KEYWORDS):
        return LoopMode.IMPROVE
    return LoopMode.FEATURE


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


def _strip_frontmatter(raw: str) -> str:
    """Remove provenance frontmatter (--- ... ---) if present."""
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            return raw[end + 5 :]
    return raw


def parse_loop_spec(path: Path) -> LoopSpec:
    """Load + validate a YAML loop-spec from disk."""
    raw = _strip_frontmatter(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"loop-spec at {path} is not a YAML mapping"
        raise ValueError(msg)
    return LoopSpec.model_validate(data)


def parse_loop_context(path: Path) -> LoopContext:
    """Load + validate a LoopContext from work-docs/loop-context/<slug>.yaml."""
    raw = _strip_frontmatter(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"loop-context at {path} is not a YAML mapping"
        raise ValueError(msg)
    return LoopContext.model_validate(data)


def is_loop_consumable(text: str) -> bool:
    """Cheap heuristic: does this text parse as a LoopSpec YAML?

    Returns True when the input is YAML with `objective` and either:
    - `features` non-empty (feature mode), or
    - `mode: improve` (improve mode allows empty features list).

    Markdown / arbitrary prose returns False so the `/hm:loop` command knows
    to trigger the adaptive interview. Provenance frontmatter is stripped
    before parsing so renderer-wrapped specs are handled correctly.
    """
    if not text.strip():
        return False
    try:
        data = yaml.safe_load(_strip_frontmatter(text))
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    if "objective" not in data:
        return False
    mode = data.get("mode", LoopMode.FEATURE.value)
    if mode == LoopMode.IMPROVE.value:
        return True
    features = data.get("features")
    if not isinstance(features, list) or not features:
        return False
    return all(isinstance(f, dict) and f.get("name") for f in features)


class ErrorClass(StrEnum):
    """LLM error classification for per-class cap enforcement (ADR-009)."""

    SYNTAX = "syntax"
    LOGICAL = "logical"
    UNKNOWN = "unknown"


ERROR_CLASS_CAPS: dict[ErrorClass, int] = {
    ErrorClass.SYNTAX: 5,
    ErrorClass.LOGICAL: 2,
    ErrorClass.UNKNOWN: 3,
}


def classify_error(error_msg: str) -> ErrorClass:
    """Classify an LLM error message into an ErrorClass.

    Uses keyword heuristics. Callers may override with LLM-based
    classification by passing pre-classified ErrorClass directly.
    """
    lowered = error_msg.lower()
    syntax_signals = [
        "syntax",
        "indent",
        "parse",
        "unexpected token",
        "unterminated",
        "invalid syntax",
        "syntaxerror",
    ]
    if any(sig in lowered for sig in syntax_signals):
        return ErrorClass.SYNTAX
    logical_signals = [
        "logic",
        "semantic",
        "wrong result",
        "incorrect",
        "assertion",
        "type error",
        "typeerror",
        "attributeerror",
        "nameerror",
        "keyerror",
        "valueerror",
    ]
    if any(sig in lowered for sig in logical_signals):
        return ErrorClass.LOGICAL
    return ErrorClass.UNKNOWN


def check_error_cap(
    error_counts: dict[ErrorClass, int],
    error_class: ErrorClass,
) -> bool:
    """Return True if the error class has NOT exceeded its cap (safe to retry).

    Returns False when the cap is reached — caller should halt.
    """
    cap = ERROR_CLASS_CAPS.get(error_class, 3)
    current = error_counts.get(error_class, 0)
    return current < cap


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
    # stopping-criteria: LLM evaluates the qualitative bar each iteration.
    # In Python tests, the executor signals convergence by returning True,
    # which marks the synthetic feature completed → all-features-completed fires.
    # This predicate is registered so the name is accepted without warning.
    "stopping-criteria": lambda s: (
        bool(s.features) and all(f.name in s.completed for f in s.features)
    ),
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

    **Feature mode only.** This function implements the feature-implementation
    loop body: pick next feature → executor → update state. Improve mode
    orchestration (review → fix → test → review cycle) is entirely
    prompt-driven inside `/hm:loop` and does not go through this function.
    Passing an improve-mode spec with `features=[]` will exit immediately with
    `stop_reason="no_remaining_features"`.
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
