"""ADR-002 interface stability guard for eig.score_eig (PLAN F3 sub-exit).

The PLAN's EIG mechanism rollback path (ADR-002: self-report proxy → answer-
disagreement or BED-LLM MC) is only feasible if the public signature stays
mechanism-agnostic. This test pins the signature so any caller-breaking
change to score_eig surfaces at test-time, not at downstream-stage runtime.
"""

from __future__ import annotations

import inspect
import typing

from harness_maker import eig
from harness_maker.eig import ScoringContext, score_eig


def test_score_eig_positional_signature_is_q_ctx() -> None:
    """The first two parameters MUST be `q: str, ctx: ScoringContext`.

    These are the mechanism-agnostic positional contract. Any additional
    parameters must be keyword-only (separated by `*`) so that callers
    relying on positional args continue to work after a mechanism swap.
    """
    sig = inspect.signature(score_eig)
    params = list(sig.parameters.values())
    positional = [p for p in params if p.kind != inspect.Parameter.KEYWORD_ONLY]
    assert [p.name for p in positional] == ["q", "ctx"], (
        f"score_eig positional args drifted from (q, ctx); got "
        f"{[p.name for p in positional]} — ADR-002 rollback path broken"
    )


def test_score_eig_q_annotated_as_str() -> None:
    """First positional `q` must be annotated `str` (resolved via get_type_hints)."""
    hints = typing.get_type_hints(score_eig)
    assert hints["q"] is str


def test_score_eig_ctx_annotated_as_scoring_context() -> None:
    """Second positional `ctx` must be annotated `ScoringContext`."""
    hints = typing.get_type_hints(score_eig)
    assert hints["ctx"] is ScoringContext


def test_score_eig_returns_float() -> None:
    """Return annotation MUST resolve to `float`."""
    hints = typing.get_type_hints(score_eig)
    assert hints["return"] is float


def test_score_eig_only_q_and_ctx_are_positional() -> None:
    """Anything beyond (q, ctx) MUST be keyword-only.

    A future mechanism that needs extra setup (e.g. an `anthropic_client=`
    arg for answer-disagreement) must come as keyword-only so positional
    callers never break.
    """
    sig = inspect.signature(score_eig)
    params = list(sig.parameters.values())
    positional = [p for p in params if p.kind != inspect.Parameter.KEYWORD_ONLY]
    assert len(positional) == 2


def test_only_public_symbol_for_mechanism_path_is_score_eig() -> None:
    """`score_eig` is the only public entry for the mechanism path.

    Callers (inequality_gate.py, F4) MUST NOT import internal helpers
    like `_default_self_report_proxy` or `_cache_key` — that would couple
    them to the current mechanism. This sentinel asserts the module's
    HARNESS_MAKER-DEFINED public surface stays minimal.
    """
    # Exclude module-level imports (Any, dataclass, Callable, etc.) by checking
    # __module__ — only count callables defined IN harness_maker.eig itself.
    public_defined_here = [
        name
        for name in dir(eig)
        if not name.startswith("_")
        and callable(getattr(eig, name))
        and getattr(getattr(eig, name), "__module__", "") == "harness_maker.eig"
    ]
    # Whitelist: score_eig (main), clear_eig_cache (test helper),
    # cache_size (telemetry), ScoringContext (dataclass), EIGMechanism (type alias).
    allowed = {"score_eig", "clear_eig_cache", "cache_size", "ScoringContext"}
    unexpected = [name for name in public_defined_here if name not in allowed]
    assert not unexpected, (
        f"unexpected public symbols defined in harness_maker.eig: {unexpected} — "
        f"keep the public surface minimal to preserve ADR-002 rollback freedom"
    )


def test_eig_mechanism_type_alias_exported() -> None:
    """Module exposes EIGMechanism type alias for type-hint use by callers."""
    assert hasattr(eig, "EIGMechanism")


def test_scoring_context_is_frozen() -> None:
    """ScoringContext must be a frozen dataclass — accidental mutation under
    cache lookup would break key stability."""
    ctx = ScoringContext(context_summary="x")
    # dataclasses.FrozenInstanceError inherits from AttributeError in Python 3.11+
    import pytest

    with pytest.raises(AttributeError):
        ctx.context_summary = "y"  # type: ignore[misc]
