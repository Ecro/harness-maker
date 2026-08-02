"""Repo-wide test fixtures — the session-env pin, owned in ONE place.

`tests/unit/conftest.py` has pinned `CLAUDECODE` / `CLAUDE_ENV_FILE` / `HM_SESSION_ID`
since the 2026-06-21 fix for `[fail:design] runtime-env-gate-dead-on-arrival`. Every other
test directory inherited nothing, so `tests/integration/test_fresh_install_readiness.py`
read the developer's live Claude session and failed (Side 53 < 66, Production 46 < 72) when
run from inside one — while passing under `env -u CLAUDECODE`. A release procedure that
tells the operator to run a suite locally cannot have a suite whose colour depends on which
shell they used.

Lifting the pin here rather than copying it into four more conftests: unlike the
install-ref pin next door (four deliberate copies, because a shared helper's import is
rootdir-sensitive and a silently-unloaded pin is the failure IT prevents), this one needs
no import — pytest applies the rootdir conftest to every directory beneath it, and its
absence is loud rather than silent (`tests/integration/test_env_isolation.py` runs an inner
pytest with all three variables set and asserts the inner run is green).

Opt-out: mark a test `@pytest.mark.live_env` when it must observe the real environment.
Declaring the escape hatch here, once, is deliberate — an autouse fixture cannot be
overridden by a sibling fixture without one, so leaving it undefined means the first test
that needs the live env improvises a `setenv`-after-autouse that works only because of
fixture ordering nothing pins, and every later test copies that.
"""

from __future__ import annotations

import pytest

_SESSION_ENV_KEYS = ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID")


@pytest.fixture(autouse=True)
def _isolate_session_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the Claude-session variables unless the test asks for them.

    `CLAUDECODE` is the one that bites: `readiness._dim_guardrails` treats it as "we are
    inside a Claude Code session" and then emits a hard-gating signal, so an unpinned run
    under Claude Code floors the `guardrails` dimension to 0 and drags every composite
    assertion down with it.
    """
    if request.node.get_closest_marker("live_env") is not None:
        return
    for key in _SESSION_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
