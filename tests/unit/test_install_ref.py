"""Tests for _compute_install_ref() — ADR-002 install reference auto-detection."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_returns_package_name_for_wheel_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-editable wheel install (no direct_url.json) → return 'harness-maker'."""
    monkeypatch.undo()
    dist = SimpleNamespace(read_text=lambda name: None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_returns_url_path_for_editable_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Editable install with file:// direct_url → return the URL path verbatim.

    Before 0.15.1 this returned ``_HARNESS_MAKER_PKG_ROOT`` (the renderer's
    ``__file__``-derived guess), which is wrong when the renderer runs from
    a uv archive cache. The URL path is the original source uv was given
    and is the only value that can be re-used in a downstream
    ``uv run --with <ref>`` call.
    """
    monkeypatch.undo()
    # The URL must point at a RESOLVABLE project (ADR-001) — a bare `/tmp/hm` that does
    # not exist now falls back, which is a different test. The claim here is unchanged:
    # an editable install's URL path is what gets returned.
    project = tmp_path / "hm"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    direct_url = json.dumps({"dir_info": {"editable": True}, "url": f"file://{project}"})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == str(project)


def test_returns_local_path_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package not installed at all → fall back to local abs path."""
    # conftest autouse fixture pins _compute_install_ref, undo it for this test.
    monkeypatch.undo()
    with patch(
        "importlib.metadata.distribution",
        side_effect=Exception("not found"),
    ):
        from harness_maker.synthesize import (
            _HARNESS_MAKER_PKG_ROOT,
            _compute_install_ref,
            _portablize_ref,
        )

        # The fallback is home-prefixed too, so it is portablized (ADR-002 wraps
        # every branch); compare against the portablized form so the assertion is
        # correct whether or not the checkout lives under the runner's home.
        assert _compute_install_ref() == _portablize_ref(_HARNESS_MAKER_PKG_ROOT)


def test_returns_package_name_for_non_file_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-editable install with non-file:// direct_url (e.g. git+https) → 'harness-maker'."""
    monkeypatch.undo()
    direct_url = json.dumps({"url": "https://github.com/Ecro/harness-maker.git", "vcs_info": {}})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_returns_local_path_when_direct_url_json_corrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dist found but direct_url.json has invalid JSON → fall back to local path.

    0.11.3: previously returned 'harness-maker' on parse failure. That assumed
    the package is on PyPI, which is unsafe for harness-maker (not published).
    Local path works for both PyPI installs (uv accepts the directory) and
    local installs; PyPI name only works if published. Falling back to local
    on ambiguity removes the SessionStart-drift footgun.
    """
    monkeypatch.undo()

    def _read(name: str) -> str | None:
        return "{bad json" if name == "direct_url.json" else None

    dist = SimpleNamespace(read_text=_read)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import (
            _HARNESS_MAKER_PKG_ROOT,
            _compute_install_ref,
            _portablize_ref,
        )

        assert _compute_install_ref() == _portablize_ref(_HARNESS_MAKER_PKG_ROOT)


def test_returns_url_path_for_non_editable_file_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-editable file:// install (Claude Code plugin cache) → return URL path.

    Regression guard for the 0.15.1 fix: when ``uv run --with /path/to/plugin``
    archives the package into ``~/.cache/uv/archive-v0/<hash>/lib/python3.12/
    site-packages/harness_maker/``, ``_HARNESS_MAKER_PKG_ROOT`` (computed from
    ``__file__.parent.parent.parent``) resolves to the archive's
    ``lib/python3.12`` directory — NOT a Python project. The pre-0.15.1 code
    returned that constant anyway, and every rendered hook then fired
    ``uv run --with <archive>/lib/python3.12 ...`` and failed at uv resolution.

    The fix: read the URL from ``direct_url.json`` directly. uv writes the
    original source path there as a ``file://`` URL, which is exactly the arg
    the downstream rendered ``uv run --with ...`` line needs.
    """
    monkeypatch.undo()
    # ADR-001: the URL must resolve, so the cache dir is materialized. The claim under
    # test is unchanged — the URL path, not PKG_ROOT, is what comes back.
    cache = tmp_path / ".claude/plugins/cache/harness-maker-local/harness-maker/0.15.1"
    cache.mkdir(parents=True)
    (cache / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    direct_url = json.dumps({"dir_info": {"editable": False}, "url": f"file://{cache}"})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == str(cache)


def test_url_path_wins_over_uv_archive_pkg_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Even when _HARNESS_MAKER_PKG_ROOT points at a uv archive, the URL wins.

    Exact reproduction of the 0.15.0 bug: in production, when the renderer is
    imported from ``~/.cache/uv/archive-v0/<hash>/lib/python3.12/site-packages/
    harness_maker/synthesize.py``, ``_HARNESS_MAKER_PKG_ROOT`` resolves to
    ``<hash>/lib/python3.12`` — not a Python project. The renderer must
    *ignore* this useless value and use the URL from direct_url.json instead.
    """
    monkeypatch.undo()
    # Simulate the broken archive PKG_ROOT.
    from harness_maker import synthesize

    monkeypatch.setattr(
        synthesize,
        "_HARNESS_MAKER_PKG_ROOT",
        "/home/dev/.cache/uv/archive-v0/8LyafCD5C6AzA5QzTykGR/lib/python3.12",
    )
    cache = tmp_path / ".claude/plugins/cache/harness-maker-local/harness-maker/0.15.1"
    cache.mkdir(parents=True)
    (cache / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    direct_url = json.dumps({"dir_info": {"editable": False}, "url": f"file://{cache}"})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        result = synthesize._compute_install_ref()

    assert result == str(cache), (
        f"renderer fell back to broken archive PKG_ROOT instead of URL path: {result}"
    )


def test_console_scripts_entry_point_callable() -> None:
    """Verify the console_scripts entry point resolves to a callable."""
    from harness_maker.cli import main

    assert callable(main)


# ── $HOME portability (PLAN-portable-hook-paths, ADR-001/002, R4/R5) ──────────
# The raw install_ref (plugin-cache file:// path) is home-prefixed and machine-
# specific; baked into committed hooks it flip-flops across a team repo. These
# guard `_portablize_ref` (the substitution) + its wiring into every
# `_compute_install_ref` return branch. Path.home() is always mocked so the
# result never depends on the runner's real home.


def test_portablize_home_subpath_substituted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ref UNDER the render-machine home → its home prefix becomes `$HOME`."""
    monkeypatch.undo()
    from harness_maker import synthesize

    with patch.object(Path, "home", lambda: Path("/home/noel")):
        got = synthesize._portablize_ref(
            "/home/noel/.claude/plugins/cache/harness-maker/harness-maker/0.42.0"
        )
    assert got == "$HOME/.claude/plugins/cache/harness-maker/harness-maker/0.42.0"


def test_portablize_home_exact_substituted(monkeypatch: pytest.MonkeyPatch) -> None:
    """raw == home exactly → `$HOME` (no trailing separator corruption)."""
    monkeypatch.undo()
    from harness_maker import synthesize

    with patch.object(Path, "home", lambda: Path("/home/noel")):
        assert synthesize._portablize_ref("/home/noel") == "$HOME"


def test_portablize_sibling_prefix_not_substituted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Boundary safety (R4): `/home/noel-other` must NOT match home `/home/noel`.

    A bare str.startswith(home) would corrupt it to `$HOME-other`, which a shell
    reads as the variable `HOME` followed by `-other`.
    """
    monkeypatch.undo()
    from harness_maker import synthesize

    with patch.object(Path, "home", lambda: Path("/home/noel")):
        raw = "/home/noel-other/.claude/plugins/cache/hm/0.42.0"
        assert synthesize._portablize_ref(raw) == raw


def test_portablize_non_home_abs_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """A system-wide install NOT under home (`/opt/...`) stays absolute."""
    monkeypatch.undo()
    from harness_maker import synthesize

    with patch.object(Path, "home", lambda: Path("/home/noel")):
        assert synthesize._portablize_ref("/opt/hm/0.42.0") == "/opt/hm/0.42.0"


def test_portablize_pypi_name_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """The PyPI distribution name is not a path → passes through untouched."""
    monkeypatch.undo()
    from harness_maker import synthesize

    with patch.object(Path, "home", lambda: Path("/home/noel")):
        assert synthesize._portablize_ref("harness-maker") == "harness-maker"


def test_compute_install_ref_portablizes_file_url_under_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Integration: a file:// plugin-cache URL under home → `$HOME/...` (all branches wired)."""
    monkeypatch.undo()
    # ADR-001: materialize the cache dir under a fake home so the ref resolves; the
    # claim under test is the `$HOME` substitution, not existence.
    cache = tmp_path / ".claude/plugins/cache/harness-maker/harness-maker/0.42.0"
    cache.mkdir(parents=True)
    (cache / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    direct_url = json.dumps({"dir_info": {"editable": False}, "url": f"file://{cache}"})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with (
        patch("importlib.metadata.distribution", return_value=dist),
        patch.object(Path, "home", lambda: tmp_path),
    ):
        from harness_maker.synthesize import _compute_install_ref

        assert (
            _compute_install_ref()
            == "$HOME/.claude/plugins/cache/harness-maker/harness-maker/0.42.0"
        )


# ---------------------------------------------------------------------------
# PLAN-render-degrades-live-harness ADR-001 — the ref must be RESOLVABLE, not
# merely portable.
#
# `_assert_portable_install_ref` checks only that `$HOME` substitution happened;
# nothing ever checked that the path exists. A plugin update prunes the old
# version's cache dir, the next render bakes a ref pointing at it, and every
# rendered hook is a PreToolUse BLOCKING gate — so `uv run --with <gone>` fails
# and the project loses `Edit`, including the edits that would fix it.
#
# The check lives INSIDE the file:// branch, on the decoded path, BEFORE
# `_portablize_ref` wraps it. After wrapping the value is the literal
# `$HOME/...`, which Python does not expand, so `exists()` would be False for
# EVERY valid home-cache install — the dominant install path. That would force
# the whole fleet to the fallback: worse than the defect being fixed.
# ---------------------------------------------------------------------------


def _dist_for(url: str) -> SimpleNamespace:
    payload = json.dumps({"url": url})
    return SimpleNamespace(read_text=lambda name: payload if name == "direct_url.json" else None)


def _make_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    return root


def test_a_resolvable_cache_path_is_returned_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dominant path: a real cache dir with a pyproject.toml survives untouched."""
    monkeypatch.undo()
    project = _make_project(tmp_path / "cache" / "harness-maker" / "0.51.1")
    with patch("importlib.metadata.distribution", return_value=_dist_for(f"file://{project}")):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == str(project)


def test_a_home_prefixed_resolvable_path_still_portablizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression the insertion point exists to prevent.

    If the existence check ran AFTER `_portablize_ref`, it would test the literal
    `$HOME/...` string, find nothing, and send every home-cache install to the
    fallback. This pins that a home-prefixed path that DOES resolve still comes
    back in the `$HOME` form.
    """
    monkeypatch.undo()
    fake_home = tmp_path / "home"
    project = _make_project(fake_home / ".claude/plugins/cache/harness-maker/harness-maker/0.51.1")
    with (
        patch("importlib.metadata.distribution", return_value=_dist_for(f"file://{project}")),
        patch.object(Path, "home", lambda: fake_home),
    ):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == (
            "$HOME/.claude/plugins/cache/harness-maker/harness-maker/0.51.1"
        )


def test_a_missing_cache_path_falls_back_to_the_pinned_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-001: the fallback is version-PINNED, not the bare name.

    An unpinned `harness-maker` lets hooks rendered by this release execute a
    future release's gate implementation. `dist.version` is free at the call site.
    """
    monkeypatch.undo()
    gone = tmp_path / "cache" / "harness-maker" / "0.43.3"
    dist = _dist_for(f"file://{gone}")
    dist.version = "0.51.2"
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker==0.51.2"


def test_an_existing_dir_without_pyproject_also_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existence is not usability — the 0.15.0 shape.

    `_compute_install_ref`'s own docstring records an EXISTING uv-archive
    `lib/python3.12` directory being baked, after which every hook failed with
    "does not appear to be a Python project". An `exists()`-only guard would not
    have caught this repo's one documented instance of the class.
    """
    monkeypatch.undo()
    archive = tmp_path / "archive-v0" / "deadbeef" / "lib" / "python3.12"
    archive.mkdir(parents=True)
    dist = _dist_for(f"file://{archive}")
    dist.version = "0.51.2"
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker==0.51.2"


def test_the_rejection_warns_once_on_stderr_naming_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_compute_install_ref` is called from four sites; an undeduplicated warning
    fires four times per make. The message must name the rejected path — a warning
    that does not say WHICH path is unactionable."""
    monkeypatch.undo()
    gone = tmp_path / "cache" / "harness-maker" / "0.43.3"
    dist = _dist_for(f"file://{gone}")
    dist.version = "0.51.2"
    from harness_maker import synthesize as _syn

    _syn._reset_install_ref_warning()
    with patch("importlib.metadata.distribution", return_value=dist):
        _syn._compute_install_ref()
        _syn._compute_install_ref()
    err = capsys.readouterr().err
    assert str(gone) in err, f"the warning must name the rejected path; got: {err!r}"
    assert err.count(str(gone)) == 1, f"warned more than once: {err!r}"


def test_a_non_file_url_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """A PyPI / git+https install has no path to check — the branch must not fire."""
    monkeypatch.undo()
    with patch(
        "importlib.metadata.distribution",
        return_value=_dist_for("https://pypi.org/simple/harness-maker"),
    ):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


# ---------------------------------------------------------------------------
# Phase 4 — ADR-010, amending ADR-001 after REVIEW round 1.
#
# (a) The `pyproject.toml` predicate rejected a wheel/sdist install — whose PEP 610
#     `direct_url.json` names the ARCHIVE, not a project dir — even though
#     `uv run --with <whl>` resolves it. That broke a working install class.
# (b) `_pinned_distribution_ref` pinned ANY non-empty version, so a dev/local build
#     rendered a pin no index serves: the same dead-gate outcome Phase 1 exists to stop.
# ---------------------------------------------------------------------------


def test_a_wheel_install_ref_is_returned_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-010a. `uv run --with <whl>` resolves a wheel — the render must not 'fix' it."""
    monkeypatch.undo()
    whl = tmp_path / "harness_maker-0.51.3-py3-none-any.whl"
    whl.write_bytes(b"PK\x03\x04")
    dist = _dist_for(f"file://{whl}")
    dist.version = "0.51.3"
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == str(whl)


def test_an_sdist_install_ref_is_returned_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-010a covers sdists too — the suffix list is the contract, not just `.whl`."""
    monkeypatch.undo()
    sdist = tmp_path / "harness_maker-0.51.3.tar.gz"
    sdist.write_bytes(b"\x1f\x8b")
    dist = _dist_for(f"file://{sdist}")
    dist.version = "0.51.3"
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == str(sdist)


@pytest.mark.parametrize("version", ["0.52.0.dev0", "1.2.3+local", "0.52.0rc1", "2.0.0a1"])
def test_a_non_release_version_falls_back_to_the_bare_name(
    version: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-010b. Pinning a version no index serves renders a gate that resolves to
    nothing — strictly worse than the version skew the bare name accepts."""
    monkeypatch.undo()
    gone = tmp_path / "cache" / "harness-maker" / "0.43.3"
    dist = _dist_for(f"file://{gone}")
    dist.version = version
    from harness_maker import synthesize as _syn

    _syn._reset_install_ref_warning()
    with patch("importlib.metadata.distribution", return_value=dist):
        assert _syn._compute_install_ref() == "harness-maker", (
            f"{version!r} is not a plain release and must not be pinned"
        )


@pytest.mark.parametrize("version", ["1", "1.2", "0.51.3", "1.2.3.post1"])
def test_a_plain_release_version_is_still_pinned(
    version: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of ADR-010b — the pin must survive for the versions that CAN
    resolve, or the fallback silently loses the ADR-001 guarantee it exists for."""
    monkeypatch.undo()
    gone = tmp_path / "cache" / "harness-maker" / "0.43.3"
    dist = _dist_for(f"file://{gone}")
    dist.version = version
    from harness_maker import synthesize as _syn

    _syn._reset_install_ref_warning()
    with patch("importlib.metadata.distribution", return_value=dist):
        assert _syn._compute_install_ref() == f"harness-maker=={version}"


def test_the_non_release_fallback_says_why_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A silent downgrade from a pin to the bare name is indistinguishable from a
    harness that predates the PyPI publication — the message must name the version."""
    monkeypatch.undo()
    gone = tmp_path / "cache" / "harness-maker" / "0.43.3"
    dist = _dist_for(f"file://{gone}")
    dist.version = "0.52.0.dev0"
    from harness_maker import synthesize as _syn

    _syn._reset_install_ref_warning()
    with patch("importlib.metadata.distribution", return_value=dist):
        _syn._compute_install_ref()
        _syn._compute_install_ref()
    err = capsys.readouterr().err
    assert "0.52.0.dev0" in err, f"the warning must name the unpinnable version; got {err!r}"
    # `_compute_install_ref` runs at four call sites per make. The path warning was routed
    # through `_INSTALL_REF_WARNED` for exactly that reason and this one was not, so it
    # fired 4x beside a 1x sibling — the readability failure the dedup set exists to stop,
    # reintroduced next to the comment stating the rationale.
    assert err.count("0.52.0.dev0") == 1, f"the version warning is not deduped; got {err!r}"


def test_an_unusable_pkg_root_is_not_handed_back_as_the_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-007's premise, made true rather than assumed.

    The refresh overwrites a user's preserved hook with the TEMPLATE's command text on the
    grounds that the template's ref is validated. It was validated on the `file://` branch
    only — the two `_HARNESS_MAKER_PKG_ROOT` returns handed it back unchecked, and that is
    precisely the 0.15.0 archive shape (`…/lib/python3.12`, no `pyproject.toml`). In that
    state the refresh would replace a still-working invocation with a dead one.
    """
    monkeypatch.undo()
    archive = tmp_path / "archive-v0" / "deadbeef" / "lib" / "python3.12"
    archive.mkdir(parents=True)
    from harness_maker import synthesize as _syn

    monkeypatch.setattr(_syn, "_HARNESS_MAKER_PKG_ROOT", str(archive))
    dist = SimpleNamespace(
        read_text=lambda name: "{not json" if name == "direct_url.json" else None
    )
    dist.version = "0.51.3"
    _syn._reset_install_ref_warning()
    with patch("importlib.metadata.distribution", return_value=dist):
        result = _syn._compute_install_ref()
    assert result == "harness-maker==0.51.3", (
        f"an unusable PKG_ROOT was baked into every rendered hook; got {result!r}"
    )
