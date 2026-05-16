"""Shared unit-test fixtures — environment isolation for HOME-reading modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import detection_cache, foreign_config


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
