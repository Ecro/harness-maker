"""Install-ref pin for `tests/structural/` — the third directory to need it.

`synthesize._compute_install_ref()` resolves through `__file__`, so a render produced
from a `.worktrees/<x>/` checkout bakes that checkout's absolute path into
`harness_maker_src_path`. `test_command_size_budget.py` measures `len(read_text())`
against committed constants, so an unpinned render makes the ratchet a function of
WHERE the suite ran — the numbers frozen in a worktree would be wrong in CI and in base.

That is `[fail:test] snapshot-regen-inside-worktree`, whose instance 13 was exactly this:
a new test directory inheriting the pin from neither owner. The owners are
`tests/snapshot/regenerate.py` and `tests/unit/conftest.py`, plus `tests/render/conftest.py`
since Phase 3. This is a fourth copy of five lines, deliberately: a shared helper imported
across test directories depends on pytest's rootdir-sensitive import machinery, and a pin
that silently fails to load is the failure this file exists to prevent. If a fifth copy is
ever needed, extract then.
"""

from __future__ import annotations

import os

import pytest

from harness_maker import synthesize

_MAIN_CHECKOUT_DEFAULT = "/home/noel/harness-maker"
_PORTABLE_REF = "$HOME/harness-maker"


def pin_install_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exposed as a plain function, not only as a fixture.

    A module- or session-scoped render fixture is set up BEFORE any function-scoped
    autouse fixture, so the autouse pin below is not in effect while such a fixture
    renders. Callers that render at module scope must apply this themselves through
    `pytest.MonkeyPatch.context()`.
    """
    main_path = os.environ.get("HM_MAIN_CHECKOUT_PATH", _MAIN_CHECKOUT_DEFAULT)
    monkeypatch.setattr(synthesize, "_HARNESS_MAKER_PKG_ROOT", main_path)
    monkeypatch.setattr(synthesize, "_compute_install_ref", lambda: _PORTABLE_REF)


@pytest.fixture(autouse=True)
def _pin_harness_maker_pkg_root(monkeypatch: pytest.MonkeyPatch) -> None:
    pin_install_ref(monkeypatch)
