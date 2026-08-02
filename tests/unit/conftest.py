"""Shared unit-test fixtures — environment isolation for HOME-reading modules."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_maker import detection_cache, foreign_config, synthesize


@pytest.fixture(autouse=True)
def _bypass_worktree_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-013 cwd guard fires when pytest itself runs inside the harness-maker
    `.worktrees/<branch>/` checkout (which is the normal development case).
    Set the documented bypass env var so unit tests can exercise --update."""
    monkeypatch.setenv("HARNESS_MAKER_BYPASS_WORKTREE_GUARD", "1")


# The CLAUDECODE / CLAUDE_ENV_FILE / HM_SESSION_ID pin that used to live here moved to
# `tests/conftest.py` (PLAN-sessionid-env-propagation ADR-002) so integration, e2e, render
# and structural inherit it too — this directory was the only one protected, which is how
# `test_fresh_install_readiness` came to depend on which shell the operator ran it from.


@pytest.fixture(autouse=True)
def _pin_harness_maker_pkg_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the renderer's install-ref output for worktree-invariant snapshots.

    From within a ``.worktrees/<x>/`` checkout the constant resolves via
    ``__file__`` to the worktree path and leaks into rendered templates
    (``harness_maker_src_path``), breaking byte-identical snapshot comparisons.
    Pin to the canonical main checkout so unit tests are invariant to where
    they are invoked from.

    Since 0.15.1 the renderer reads ``direct_url.json`` directly instead of
    using ``_HARNESS_MAKER_PKG_ROOT``; pin both so snapshot determinism
    survives the dev's actual install state.

    PLAN-portable-hook-paths: ``_compute_install_ref`` now returns a
    ``$HOME``-substituted ref (``_portablize_ref``), so the pinned install ref is
    the portable ``$HOME/harness-maker`` form — home-free and deterministic on any
    runner, and it satisfies the render-time leak-check assert
    (``render._assert_portable_install_ref``). ``_HARNESS_MAKER_PKG_ROOT`` stays
    the absolute checkout path (only consumed by tests that ``monkeypatch.undo()``
    and re-derive the portable form themselves).
    """
    main_path = os.environ.get(
        "HM_MAIN_CHECKOUT_PATH",
        "/home/noel/harness-maker",
    )
    portable_ref = "$HOME/harness-maker"
    monkeypatch.setattr(synthesize, "_HARNESS_MAKER_PKG_ROOT", main_path)
    monkeypatch.setattr(synthesize, "_compute_install_ref", lambda: portable_ref)


@pytest.fixture(autouse=True)
def _isolate_detection_cache(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect detection_cache._default_cache_dir() into per-test tmp_path.

    CLAUDE.md §테스트 정책: HOME-reading code must be isolated. The Phase 3
    profile() now writes through detection_cache on every call — without this
    fixture the developer's ~/.cache/harness-maker/ accumulates fixture state
    across runs and tests assume each other's cache files.
    """
    tmp_cache: Path = tmp_path_factory.mktemp("hm_cache")
    monkeypatch.setattr(detection_cache, "_default_cache_dir", lambda: tmp_cache)


@pytest.fixture(autouse=True)
def _isolate_foreign_config_cache(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect foreign_config._default_cache_dir() into per-test tmp_path.

    Phase 6 ``llm_map`` writes cache files to ``~/.cache/harness-maker/`` —
    must be isolated per test for the same reason as detection_cache (HOME
    pollution + cross-test state leak).
    """
    tmp_cache: Path = tmp_path_factory.mktemp("hm_foreign_cache")
    monkeypatch.setattr(foreign_config, "_default_cache_dir", lambda: tmp_cache)


@pytest.fixture(autouse=True)
def _isolate_transcript_root(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect economics_source.default_transcript_root() into per-test tmp_path.

    CLAUDE.md checkpoint 7: HOME-reading code must be isolated. Layer 3
    (cache_efficiency) now reads Claude Code session transcripts, so without this any
    ai_readiness/improvement test would score against the developer's real
    ``~/.claude/projects`` — non-deterministic, and different on CI. Tests that
    exercise the reader pass ``transcript_root=`` explicitly.
    """
    from harness_maker import economics_source

    tmp_root: Path = tmp_path_factory.mktemp("hm_transcripts")
    monkeypatch.setattr(economics_source, "default_transcript_root", lambda: tmp_root)
