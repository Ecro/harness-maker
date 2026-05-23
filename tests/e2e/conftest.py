"""E2E sandbox seed fixture — session-scoped autouse.

PLAN-worktree-cross-session-data-loss-defense ADR-007 untracked the
`tests/e2e/sandbox/` and `tests/e2e/sandbox-plugin-test/` directories from
git so concurrent version bumps don't trigger 2400+-file stash conflicts at
finalize. The trade-off: fresh checkouts (CI, new clones) lack the minimal
project seed (pyproject.toml + hello_world.py) that `harness-maker make`
needs to operate on.

This conftest re-creates those seed files on first import — idempotent
(skips when files already exist) — so the test suite is self-bootstrapping
regardless of git state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

E2E_DIR = Path(__file__).resolve().parent

_PYPROJECT = """\
[project]
name = "sandbox"
version = "0.1.0"
description = "Dogfood sandbox for harness-maker e2e tests (Phase 11)"
requires-python = ">=3.12"
"""

_HELLO_WORLD = '''\
"""Minimal hello-world for the dogfood sandbox (Phase 11)."""


def main() -> None:
    """Print the canonical greeting."""
    print("hello, sandbox")


if __name__ == "__main__":
    main()
'''


def _seed_one(sandbox: Path) -> None:
    sandbox.mkdir(parents=True, exist_ok=True)
    pyproj = sandbox / "pyproject.toml"
    if not pyproj.exists():
        pyproj.write_text(_PYPROJECT, encoding="utf-8")
    hello = sandbox / "hello_world.py"
    if not hello.exists():
        hello.write_text(_HELLO_WORLD, encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def _seed_e2e_sandboxes() -> None:
    """Bootstrap minimal project source into the gitignored sandbox dirs."""
    _seed_one(E2E_DIR / "sandbox")
    _seed_one(E2E_DIR / "sandbox-plugin-test")
