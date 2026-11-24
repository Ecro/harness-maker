"""Scrubbed environment for tests that run `uv run` inside this repository."""

from __future__ import annotations

import os

_FORWARDED = ("PATH", "HOME", "USER", "VIRTUAL_ENV")


def uv_subprocess_env() -> dict[str, str]:
    """Keep the test env hermetic but pass every UV_* setting through.

    Without UV_PYTHON uv falls back to `.python-version` (3.12) and rebuilds a `.venv` made for
    another interpreter (nightly's 3.13 job) under every other xdist worker.
    """
    env = {k: os.environ[k] for k in _FORWARDED if k in os.environ}
    env.update({k: v for k, v in os.environ.items() if k.startswith("UV_")})
    return env
