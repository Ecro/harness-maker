"""Presence detection for the external CLIs the onboarding flow can offer.

The defining property is what this module does NOT do: it never consults
``detection_cache``. `profile()` is served from a 24h cache invalidated only by project
manifest mtime, and installing a CLI touches no project manifest — so a cached answer here
would report a CLI installed five minutes ago as absent, silently, for up to a day
(PLAN-onboarding-interview-ux ADR-001). Half these tests exist to pin that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import tool_detect


def _fake_which(present: set[str]) -> object:
    def _which(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}" if cmd in present else None

    return _which


def test_every_tool_reports_installed_when_its_binary_is_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"codex", "agy", "cursor"}))
    result = tool_detect.detect_tools()
    assert result == {
        "codex": {"installed": True},
        "antigravity": {"installed": True},
        "cursor": {"installed": True},
    }


def test_every_tool_reports_absent_when_nothing_is_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which(set()))
    result = tool_detect.detect_tools()
    assert result == {
        "codex": {"installed": False},
        "antigravity": {"installed": False},
        "cursor": {"installed": False},
    }


def test_the_antigravity_key_is_driven_by_the_agy_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The binary is `agy`; the config key and `SECOND_OPINION_MODELS` name is `antigravity`.

    A test asserting only "some tool was detected" would pass with the mapping inverted,
    and the inversion is invisible until a user with `agy` installed is never offered it.
    """
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"agy"}))
    result = tool_detect.detect_tools()
    assert result["antigravity"] == {"installed": True}
    assert result["codex"] == {"installed": False}
    assert result["cursor"] == {"installed": False}

    # And the reverse: a binary literally named `antigravity` is NOT what we look for.
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"antigravity"}))
    assert tool_detect.detect_tools()["antigravity"] == {"installed": False}


def test_the_key_set_matches_the_second_opinion_model_names() -> None:
    """Drift guard: a model added to `SECOND_OPINION_MODELS` with no detector here would
    make the onboarding offer structurally unable to mention it."""
    from harness_maker.models import SECOND_OPINION_MODELS

    detected = set(tool_detect.detect_tools())
    assert set(SECOND_OPINION_MODELS) <= detected, (
        sorted(SECOND_OPINION_MODELS),
        sorted(detected),
    )


def test_detection_never_touches_the_detection_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR-001's whole point, asserted two ways.

    (a) The cache module's entry points are booby-trapped — calling either fails the test
        rather than quietly returning a stale answer.
    (b) An isolated cache dir stays empty, so nothing is written either.
    """
    from harness_maker import detection_cache

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("detect_tools must not consult detection_cache")

    monkeypatch.setattr(detection_cache, "load_or_run", _boom)
    monkeypatch.setattr(detection_cache, "write", _boom)
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"codex"}))

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(detection_cache, "_default_cache_dir", lambda: cache_dir)

    assert tool_detect.detect_tools()["codex"] == {"installed": True}
    assert list(cache_dir.iterdir()) == []


def test_repeated_calls_reflect_a_binary_that_appears_between_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The staleness this module exists to avoid, as a behavioural assertion.

    A memoised implementation passes every test above and fails this one — which is the
    exact failure mode ADR-001 rejects (a CLI installed mid-session reading as absent).
    """
    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which(set()))
    assert tool_detect.detect_tools()["codex"] == {"installed": False}

    monkeypatch.setattr(tool_detect.shutil, "which", _fake_which({"codex"}))
    assert tool_detect.detect_tools()["codex"] == {"installed": True}
