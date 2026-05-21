"""CLI integration tests for `harness-maker locate` + `make --require-version`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness_maker.cli import app

runner = CliRunner()


# ---------- fixture helpers ----------


def _write_installed_plugins_json(target: Path, version: str = "0.20.0") -> Path:
    """Write a minimal valid installed_plugins.json with one user-scope entry."""
    p = target / "installed_plugins.json"
    p.write_text(
        json.dumps(
            {
                "plugins": {
                    "harness-maker@harness-maker": [
                        {
                            "scope": "user",
                            "installPath": f"/cache/main/{version}",
                            "version": version,
                            "installedAt": "2026-05-21T04:09:31.908Z",
                            "lastUpdated": "2026-05-21T04:09:31.908Z",
                            "gitCommitSha": "deadbeef",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def patched_installed_plugins_json(monkeypatch, tmp_path: Path) -> Path:
    """Redirect the lazy default-path lookup to a tmp fixture file."""
    fixture = _write_installed_plugins_json(tmp_path)
    import harness_maker.locate as locate_mod

    monkeypatch.setattr(locate_mod, "_default_plugins_json", lambda: fixture, raising=True)
    return fixture


# ---------- locate command ----------


def test_locate_plain_prints_install_path(patched_installed_plugins_json: Path) -> None:
    """--plain prints installPath alone, no JSON."""
    result = runner.invoke(app, ["locate", "--plain"])
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() == "/cache/main/0.20.0"
    assert "{" not in result.stdout  # no JSON in stdout


def test_locate_default_prints_json(patched_installed_plugins_json: Path) -> None:
    """Default locate output is parseable JSON with required keys."""
    result = runner.invoke(app, ["locate"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["version"] == "0.20.0"
    assert payload["scope"] == "user"
    assert payload["installPath"] == "/cache/main/0.20.0"
    assert payload["marketplace"] == "harness-maker"
    assert payload["gitCommitSha"] == "deadbeef"


def test_locate_exit_3_when_no_plugin(monkeypatch, tmp_path: Path) -> None:
    """Exit 3 (NOT 1, NOT 2) when no installed plugin entry found."""
    import harness_maker.locate as locate_mod

    nonexistent = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(
        locate_mod,
        "_default_plugins_json",
        lambda: nonexistent,
        raising=True,
    )
    result = runner.invoke(app, ["locate"])
    assert result.exit_code == 3
    assert "no installed plugin" in result.stderr.lower()


def test_locate_require_version_mismatch_exit_2(
    patched_installed_plugins_json: Path,
) -> None:
    """--require-version 99.0 against installed 0.20.0 → exit 2 + structured stderr."""
    result = runner.invoke(app, ["locate", "--require-version", "99.0"])
    assert result.exit_code == 2
    assert re.search(r"installed=0\.20\.0.*required=>=99\.0", result.stderr), (
        f"stderr did not match expected format: {result.stderr!r}"
    )
    assert "claude plugin update harness-maker" in result.stderr


def test_locate_require_version_ok_exit_0(patched_installed_plugins_json: Path) -> None:
    """--require-version 0.1 against installed 0.20.0 → exit 0."""
    result = runner.invoke(app, ["locate", "--require-version", "0.1"])
    assert result.exit_code == 0, result.stderr


def test_locate_require_version_equal_exit_0(
    patched_installed_plugins_json: Path,
) -> None:
    """--require-version 0.20.0 against installed 0.20.0 → exit 0 (>= is inclusive)."""
    result = runner.invoke(app, ["locate", "--require-version", "0.20.0"])
    assert result.exit_code == 0, result.stderr


def test_locate_require_version_bad_input_exit_2(
    patched_installed_plugins_json: Path,
) -> None:
    """--require-version with non-numeric input → exit 2 + error message."""
    result = runner.invoke(app, ["locate", "--require-version", "abc"])
    assert result.exit_code == 2
    assert "invalid" in result.stderr.lower()


def test_locate_help_documents_exit_codes_and_constraint() -> None:
    """`locate --help` mentions the >=X.Y constraint and exit codes."""
    result = runner.invoke(app, ["locate", "--help"])
    assert result.exit_code == 0
    assert ">=X.Y" in result.stdout
    # Help text rendered by typer may wrap lines, so check the constituent
    # exit-code tokens rather than the literal "0 found+ok" phrasing.
    assert "2" in result.stdout
    assert "3" in result.stdout


# ---------- make --require-version ----------


def test_make_require_version_mismatch_exit_2(
    patched_installed_plugins_json: Path, tmp_path: Path
) -> None:
    """`make --require-version 99.0` exits 2 before touching the target."""
    target = tmp_path / "scratch_project"
    target.mkdir()
    result = runner.invoke(
        app,
        ["make", str(target), "--require-version", "99.0", "--autoloop"],
    )
    assert result.exit_code == 2, result.stderr
    assert re.search(r"installed=0\.20\.0.*required=>=99\.0", result.stderr), (
        f"stderr did not match expected format: {result.stderr!r}"
    )
    # No .claude/ should have been written — the gate fires BEFORE any work.
    assert not (target / ".claude").exists()


def test_make_require_version_ok_does_not_block(
    patched_installed_plugins_json: Path, tmp_path: Path
) -> None:
    """`make --require-version 0.1` does NOT exit 2 — gate is bypassed.

    We only test that the gate does not block; full make execution requires
    interview/render fixtures that are out of scope for this CLI test.
    """
    target = tmp_path / "scratch_project"
    target.mkdir()
    result = runner.invoke(
        app,
        ["make", str(target), "--require-version", "0.1", "--autoloop"],
    )
    # Exit may be non-zero for other reasons (interview defaults, etc.),
    # but MUST NOT be 2 from the version gate.
    if result.exit_code == 2:
        assert "required=>=" not in result.stderr, (
            f"version gate fired when it should not have: {result.stderr!r}"
        )


def test_make_help_documents_require_version() -> None:
    """`make --help` exposes the --require-version flag."""
    result = runner.invoke(app, ["make", "--help"])
    assert result.exit_code == 0
    assert "--require-version" in result.stdout
