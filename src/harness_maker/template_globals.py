"""The names every Jinja environment in this package must expose to templates.

There is more than one `Environment(...)` in `src/` — `render`, `personalization_audit` and
`foreign_config` each build their own — and they render the SAME template files. A global
installed on one of them is therefore not installed at all: the template renders in one code
path and raises `UndefinedError` in another, which is how the review lens axis shipped broken
into `personalization_audit` the first time.

Two rules keep that from recurring. Every environment calls `install(env)`, and
`tests/structural/test_template_globals_installed.py` finds each `Environment(` construction by
AST rather than from a list in this docstring — a hand-maintained list of call sites is the
thing that was wrong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness_maker import conditional_router, review_churn

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters at type-check time
    from jinja2 import Environment

#: Exported as a callable rather than baked into each template as a literal list. The rendered
#: dispatch list and `hm lens_coverage check` must agree on the mandatory lens set; a literal
#: would let them disagree, and the symptom of that is not a visible drift but a review that can
#: never be approved, because the CLI names a lens the command never told anyone to run.
TEMPLATE_GLOBALS: dict[str, object] = {
    "lens_dispatch": conditional_router.lens_dispatch,
    "mandatory_lenses": conditional_router.mandatory_lenses,
    "routable_lenses": conditional_router.routable_lenses,
    # Same reason, different axis: the rendered gate branch and `resolve_churn_threshold`
    # must agree on what "absent key" means. A literal `0.20` in the template would let the
    # prose promise one threshold while the CLI applied another.
    "default_churn_ratio": review_churn.default_churn_ratio,
}


def install(env: Environment) -> Environment:
    """Add every shared global to `env`, in place. Returns it for call-site convenience."""
    env.globals.update(TEMPLATE_GLOBALS)
    return env
