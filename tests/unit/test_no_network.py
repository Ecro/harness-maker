"""ADR-005 positive obligation: telemetry + audit + SessionStart hook must
not make network calls.

Why this exists: ADR-005 declares the personalization-depth telemetry
pipeline "100% local". A regression that quietly opens a socket (e.g. a
dependency upgrade pulling in a telemetry-phone-home library) would
break that contract silently. Per validator W4 amendment, every code
path that runs in the user's session-start window (the SessionStart
hook) or in their /hm:configure flow (override emit + load) must be
covered by a positive monkeypatch on ``socket.socket`` so a regression
trips the test instead of leaking data.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest


def _make_socket_explode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch socket.socket so any attempt to open one is fatal.

    We patch BOTH the class and the constructor: some libraries cache a
    reference to ``socket.socket`` at import time, but the harness-maker
    code we cover here imports socket lazily (if at all). Patching the
    top-level attribute is enough.
    """

    def _no_socket(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "ADR-005 violation: telemetry/audit/SessionStart attempted network call"
        )

    monkeypatch.setattr(socket, "socket", _no_socket)


def test_emit_override_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 9 primary capture path: emit_override performs zero socket calls."""
    _make_socket_explode(monkeypatch)
    from harness_maker.telemetry import OverrideRecord, emit_override

    record = OverrideRecord(
        ts="2026-05-16T12:00:00+00:00",
        axis_path="preset",
        before="Side",
        after="Production",
        source="configure-exit",
    )
    emit_override(record, tmp_path)
    out = tmp_path / ".claude" / "observability" / "adaptive" / "overrides.jsonl"
    assert out.is_file()


def test_load_overrides_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reader path must be socket-free — it runs from /hm:personalization-audit
    (Phase 10) which has the same 100%-local contract."""
    _make_socket_explode(monkeypatch)
    from harness_maker.telemetry import load_overrides

    overrides = load_overrides(tmp_path)
    assert overrides == []


def test_compute_yaml_diff_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pure-function helper — extra defensive: still proves it via the
    monkeypatch in case a future caching layer is added."""
    _make_socket_explode(monkeypatch)
    from harness_maker.telemetry import compute_yaml_diff

    records = compute_yaml_diff(
        {"preset": "Side"},
        {"preset": "Production"},
        ts="2026-05-16T12:00:00+00:00",
    )
    assert len(records) == 1


def test_personalization_audit_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 10 audit reader: run_audit performs zero socket calls.

    100% local contract (ADR-005): the audit pipeline reads overrides.jsonl,
    harness.yaml, the detection cache, and writes last-audit.txt — none of
    those steps should touch a socket. A regression (e.g. a future cache
    upgrade pulling in a telemetry-phone-home library) would trip this
    monkeypatch."""
    _make_socket_explode(monkeypatch)
    from harness_maker import personalization_audit as pa

    # Avoid the detection-cache codepath looking at a real user repo.
    monkeypatch.setattr(pa, "load_or_run", lambda _: None)

    plan = pa.run_audit(tmp_path)
    # Must complete without raising the socket-trap RuntimeError.
    assert 0 <= plan.composite_score <= 100
    assert plan.tier in {"bronze", "silver", "gold", "platinum"}


def test_session_start_hook_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hook runs in the user's terminal session-start window — a
    network call here would be the worst-case ADR-005 violation
    (synchronous, blocking, visible). Cover the secondary capture path
    end-to-end with a socket trap.
    """
    _make_socket_explode(monkeypatch)
    # Avoid spurious git subprocess calls polluting the trace: point cwd at
    # an empty directory so _capture_yaml_overrides exits before git is
    # consulted. (The contract under test is "no socket", not "yes git".)
    from harness_maker.hooks import sessionstart_drift

    monkeypatch.setattr(
        sessionstart_drift,
        "detect_version_drift",
        lambda _cwd: None,
    )
    rc = sessionstart_drift.run(tmp_path)
    assert rc == 0
