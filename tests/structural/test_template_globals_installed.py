"""Every Jinja environment in `src/` installs the shared template globals.

This is an AST **discovery** test, not a checklist. Three modules build their own
`Environment(...)` — `render`, `personalization_audit`, `foreign_config` — and they render the
SAME template files, so a global installed on one of them is not installed at all: the template
renders in one code path and raises `UndefinedError` in another.

That is exactly how the review lens axis shipped: `render._make_env` got
`mandatory_lenses`/`routable_lenses`/`lens_dispatch`, the other two did not, and
`personalization_audit` blew up on the harness.yaml template it renders for its convergence
audit. A list of call sites written into a docstring would have been wrong the same way — so
this test *finds* the constructions instead of naming them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from harness_maker.template_globals import TEMPLATE_GLOBALS

_SRC = Path(__file__).resolve().parents[2] / "src" / "harness_maker"


def _modules_constructing_an_environment() -> list[Path]:
    """Every module with a literal `Environment(...)` call, found by AST."""
    found: list[Path] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Environment"
            ):
                found.append(path)
                break
    return found


def test_the_discovery_is_not_vacuous() -> None:
    """A broken scan would silently pass every arm below."""
    modules = _modules_constructing_an_environment()
    assert len(modules) >= 3, f"expected several Environment call sites, found {modules}"


@pytest.mark.parametrize("path", _modules_constructing_an_environment(), ids=lambda p: p.stem)
def test_every_environment_goes_through_the_installer(path: Path) -> None:
    """`template_globals.install(...)` must appear in the same module.

    Textual rather than behavioural because the environments are built inside functions with
    real arguments; what this pins is that no module grows an environment without routing it
    through the one place the globals live.
    """
    src = path.read_text(encoding="utf-8")
    assert "template_globals.install(" in src, (
        f"{path.name} builds a Jinja Environment but never calls template_globals.install(); "
        "templates rendered through it will raise UndefinedError on shared globals"
    )


def test_the_installer_actually_binds_every_declared_global() -> None:
    from jinja2 import Environment

    from harness_maker.template_globals import install

    env = install(Environment(autoescape=False))
    assert set(TEMPLATE_GLOBALS) <= set(env.globals)
    for name in TEMPLATE_GLOBALS:
        assert callable(env.globals[name]), f"{name} must be callable from a template"
