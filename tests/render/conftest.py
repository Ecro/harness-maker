"""Render-test fixtures — the install-ref pin `tests/render/` was missing.

Without this, a render produced from a `.worktrees/<x>/` checkout bakes the worktree
absolute path into `harness_maker_src_path` (39-45 occurrences per fused command), so a
golden captured here is only valid here: it breaks in CI and in the base repo the moment
the worktree is landed and deleted.

That is instance 13 of `[fail:test] snapshot-regen-inside-worktree` — the highest-count
entry in this repo's ledger. Its 2026-07-26 SUPERSEDED note says renders are
worktree-invariant "by construction", and that is true *of the two places that pin it*:
`tests/snapshot/regenerate.py` and `tests/unit/conftest.py`. A NEW test directory
inherits neither. The generalisation from "the snapshot fixtures are clean" to "my
goldens are clean" is exactly the step that has to stop being made.
"""

from __future__ import annotations

import os

import pytest

from harness_maker import synthesize

_MAIN_CHECKOUT_DEFAULT = "/home/noel/harness-maker"
_PORTABLE_REF = "$HOME/harness-maker"


def pin_install_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror of `tests/unit/conftest.py::_pin_harness_maker_pkg_root`.

    Exposed as a plain function, not only as a fixture, because the goldens in
    `tests/fixtures/*_pre_change.md` are captured by a script that never enters pytest —
    and a pin the capture path cannot reach is how the leak got in.
    """
    main_path = os.environ.get("HM_MAIN_CHECKOUT_PATH", _MAIN_CHECKOUT_DEFAULT)
    monkeypatch.setattr(synthesize, "_HARNESS_MAKER_PKG_ROOT", main_path)
    monkeypatch.setattr(synthesize, "_compute_install_ref", lambda: _PORTABLE_REF)


@pytest.fixture(autouse=True)
def _pin_harness_maker_pkg_root(monkeypatch: pytest.MonkeyPatch) -> None:
    pin_install_ref(monkeypatch)
