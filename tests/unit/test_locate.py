"""Unit tests for harness_maker.locate — resolver priority + version comparator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.locate import (
    compare_version,
    resolve,
)

# ---------- helpers ----------


def _write_fixture(tmp_path: Path, payload: dict[str, object]) -> Path:
    p = tmp_path / "installed_plugins.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _entry(
    *,
    scope: str = "project",
    project_path: str | None = None,
    install_path: str,
    version: str,
    installed_at: str = "2026-05-01T00:00:00.000Z",
    git_sha: str = "abc1234",
) -> dict[str, str]:
    e: dict[str, str] = {
        "scope": scope,
        "installPath": install_path,
        "version": version,
        "installedAt": installed_at,
        "lastUpdated": installed_at,
        "gitCommitSha": git_sha,
    }
    if project_path is not None:
        e["projectPath"] = project_path
    return e


# ---------- resolve() priority matrix ----------


def test_cwd_match_wins_over_user_scope(tmp_path: Path) -> None:
    """projectPath == cwd outranks scope=user even when user-scope is newer."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    _entry(
                        scope="project",
                        project_path=str(tmp_path),
                        install_path="/cache/local/0.7.3",
                        version="0.7.3",
                        installed_at="2026-01-01T00:00:00.000Z",
                    ),
                ],
                "harness-maker@harness-maker": [
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.19.0",
                        version="0.19.0",
                        installed_at="2026-05-21T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.version == "0.7.3"
    assert entry.scope == "project"


def test_user_scope_wins_when_cwd_does_not_match_any_project(tmp_path: Path) -> None:
    """When cwd does not match any projectPath, scope=user beats project-scope-of-other-cwd."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    _entry(
                        scope="project",
                        project_path="/some/other/project",
                        install_path="/cache/local/0.7.3",
                        version="0.7.3",
                        installed_at="2026-01-01T00:00:00.000Z",
                    ),
                ],
                "harness-maker@harness-maker": [
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.19.0",
                        version="0.19.0",
                        installed_at="2026-05-21T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.version == "0.19.0"
    assert entry.scope == "user"


def test_installed_at_desc_tiebreak_across_user_scope(tmp_path: Path) -> None:
    """When multiple user-scope entries exist, most-recent installedAt wins."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker": [
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.18.0",
                        version="0.18.0",
                        installed_at="2026-04-01T00:00:00.000Z",
                    ),
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.19.0",
                        version="0.19.0",
                        installed_at="2026-05-21T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.version == "0.19.0"


def test_no_cwd_match_and_no_user_scope_returns_none(tmp_path: Path) -> None:
    """When neither tier-1 (cwd-match) nor tier-2 (scope=user) applies, return None.

    The PLAN's strict-priority reading does NOT fall back to "most-recent project-scope
    of some other cwd" — that fallback would silently pick the kairos-style wrong entry,
    which is the original footgun in a different form. Fail loud (None → CLI exit 3)
    so the caller knows to install user-scope rather than silently accepting another
    project's pinned version.
    """
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    _entry(
                        scope="project",
                        project_path="/home/noel/kairos",
                        install_path="/cache/local/0.7.3",
                        version="0.7.3",
                        installed_at="2026-01-01T00:00:00.000Z",
                    ),
                    _entry(
                        scope="project",
                        project_path="/home/noel/hiloop",
                        install_path="/cache/local/0.19.3",
                        version="0.19.3",
                        installed_at="2026-05-15T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    # cwd = tmp_path matches neither projectPath; no user-scope entries exist.
    assert resolve(cwd=tmp_path, installed_plugins_json=f) is None


def test_hwcc_forensic_replay_user_scope_wins_over_kairos(tmp_path: Path) -> None:
    """Replay of the 2026-05-21 hwcc bootstrap state.

    cwd = /home/noel/hwcc/ (not in any projectPath list)
    harness-maker-local has 6 project-scope entries (kairos@0.7.3, ..., hiloop@0.19.3)
    harness-maker has 2 entries (edgescan@0.17.0 project, user-scope@0.19.0)

    Correct resolution: user-scope 0.19.0 wins. NOT kairos@0.7.3 (the entries[0] bug).
    """
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    _entry(
                        scope="project",
                        project_path="/home/noel/kairos",
                        install_path="/cache/local/0.7.3",
                        version="0.7.3",
                        installed_at="2026-05-03T15:22:13.710Z",
                    ),
                    _entry(
                        scope="project",
                        project_path="/home/noel/hiloop",
                        install_path="/cache/local/0.19.3",
                        version="0.19.3",
                        installed_at="2026-05-09T11:59:24.480Z",
                    ),
                ],
                "harness-maker@harness-maker": [
                    _entry(
                        scope="project",
                        project_path="/home/noel/edgescan",
                        install_path="/cache/main/0.17.0",
                        version="0.17.0",
                        installed_at="2026-05-18T12:45:14.618Z",
                    ),
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.19.0",
                        version="0.19.0",
                        installed_at="2026-05-21T04:09:31.908Z",
                    ),
                ],
            }
        },
    )
    cwd = Path("/home/noel/hwcc")
    entry = resolve(cwd=cwd, installed_plugins_json=f)
    assert entry is not None, "forensic case must resolve, not return None"
    assert entry.version == "0.19.0", (
        f"forensic case must resolve user-scope 0.19.0, got {entry.version} "
        f"(scope={entry.scope}, projectPath={entry.project_path})"
    )
    assert entry.scope == "user"


def test_tier_1_tiebreak_most_recent_installed_at_wins(tmp_path: Path) -> None:
    """Two project-scope entries match cwd (different marketplaces); most-recent installedAt wins.

    REVIEW-2026-05-21 F9: tier-1 tiebreak was previously untested.
    """
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    _entry(
                        scope="project",
                        project_path=str(tmp_path),
                        install_path="/cache/local/0.7.3",
                        version="0.7.3",
                        installed_at="2026-01-01T00:00:00.000Z",
                    ),
                ],
                "harness-maker@harness-maker": [
                    _entry(
                        scope="project",
                        project_path=str(tmp_path),
                        install_path="/cache/main/0.20.0",
                        version="0.20.0",
                        installed_at="2026-05-21T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.version == "0.20.0"  # most recent installedAt wins the tier-1 tiebreak
    assert entry.scope == "project"


def test_malformed_entry_missing_required_field_does_not_crash(
    tmp_path: Path,
) -> None:
    """An entry without 'installPath' must be skipped, not crash with KeyError.

    REVIEW-2026-05-21 F1: _to_entry was previously vulnerable to KeyError on
    corrupt/partial entries. The resolver now drops malformed entries before
    the tiebreak and returns the next-best valid entry (or None).
    """
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker": [
                    {
                        "scope": "user",
                        # NO installPath — corrupt entry
                        "version": "0.20.0",
                        "installedAt": "2026-05-21T00:00:00.000Z",
                    },
                ],
            }
        },
    )
    # Must NOT raise KeyError; must return None since the only entry is malformed.
    assert resolve(cwd=tmp_path, installed_plugins_json=f) is None


def test_tier_1_all_malformed_falls_through_to_tier_2(tmp_path: Path) -> None:
    """When every tier-1 (cwd-match) entry is malformed, tier-2 (user-scope) wins.

    Edge case discovered in REVIEW-2026-05-21: a naive "tier_1 or tier_2"
    BEFORE the malformed filter would have selected tier_1, then filtered it
    to empty, then returned None — silently losing a perfectly valid tier-2.
    """
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    {
                        "scope": "project",
                        "projectPath": str(tmp_path),
                        # malformed: no version, no installPath
                        "installedAt": "2026-05-01T00:00:00.000Z",
                    },
                ],
                "harness-maker@harness-maker": [
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.20.0",
                        version="0.20.0",
                        installed_at="2026-05-21T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.version == "0.20.0"
    assert entry.scope == "user"


def test_malformed_entry_alongside_valid_entry_picks_valid_one(
    tmp_path: Path,
) -> None:
    """When tier-2 has one malformed + one valid user-scope entry, valid one wins."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker": [
                    {
                        "scope": "user",
                        # malformed — no version, no installPath
                        "installedAt": "2026-06-01T00:00:00.000Z",
                    },
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.20.0",
                        version="0.20.0",
                        installed_at="2026-05-21T00:00:00.000Z",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.version == "0.20.0"


def test_missing_file_returns_none(tmp_path: Path) -> None:
    """When installed_plugins.json does not exist, resolve returns None."""
    nonexistent = tmp_path / "does_not_exist.json"
    assert resolve(cwd=tmp_path, installed_plugins_json=nonexistent) is None


def test_empty_plugins_returns_none(tmp_path: Path) -> None:
    """When plugins map is empty, resolve returns None."""
    f = _write_fixture(tmp_path, {"plugins": {}})
    assert resolve(cwd=tmp_path, installed_plugins_json=f) is None


def test_no_harness_maker_plugin_returns_none(tmp_path: Path) -> None:
    """When map has entries but none are harness-maker, resolve returns None."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "some-other-plugin@some-marketplace": [
                    _entry(
                        scope="user",
                        install_path="/cache/other/1.0.0",
                        version="1.0.0",
                    ),
                ],
            }
        },
    )
    assert resolve(cwd=tmp_path, installed_plugins_json=f) is None


def test_resolve_returns_entry_with_marketplace_name(tmp_path: Path) -> None:
    """Returned entry surfaces the marketplace part of the key (right of @)."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker-local": [
                    _entry(
                        scope="user",
                        install_path="/cache/local/0.19.3",
                        version="0.19.3",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert entry.marketplace == "harness-maker-local"


def test_resolve_install_path_is_path_object(tmp_path: Path) -> None:
    """install_path is typed as Path, not str."""
    f = _write_fixture(
        tmp_path,
        {
            "plugins": {
                "harness-maker@harness-maker": [
                    _entry(
                        scope="user",
                        install_path="/cache/main/0.19.0",
                        version="0.19.0",
                    ),
                ],
            }
        },
    )
    entry = resolve(cwd=tmp_path, installed_plugins_json=f)
    assert entry is not None
    assert isinstance(entry.install_path, Path)


# ---------- compare_version() ----------


class TestCompareVersion:
    """compare_version(actual, required) — True iff actual >= required."""

    def test_full_three_part_lt_returns_false(self) -> None:
        assert compare_version("0.7.3", "0.16") is False

    def test_full_three_part_gt_returns_true(self) -> None:
        assert compare_version("0.19.3", "0.19") is True

    def test_equal_returns_true(self) -> None:
        assert compare_version("0.20.0", "0.20.0") is True

    def test_two_part_vs_three_part_missing_parts_are_zero(self) -> None:
        """0.20 == 0.20.0; 0.19 < 0.19.3."""
        assert compare_version("0.20", "0.20.0") is True
        assert compare_version("0.19", "0.19.3") is False

    def test_one_part_vs_two_part(self) -> None:
        """0 < 0.1; 1 >= 0.99."""
        assert compare_version("0", "0.1") is False
        assert compare_version("1", "0.99") is True

    def test_required_one_part_works(self) -> None:
        assert compare_version("0.20.0", "0") is True

    def test_non_numeric_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="non-numeric"):
            compare_version("abc", "0.1")
        with pytest.raises(ValueError, match="non-numeric"):
            compare_version("0.1", "abc")
        with pytest.raises(ValueError, match="non-numeric"):
            compare_version("0.7.3-beta", "0.16")

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compare_version("", "0.1")

    def test_arabic_indic_digits_rejected(self) -> None:
        """REVIEW-2026-05-21 F12: Unicode digits must be rejected, not accepted.

        Python's str.isdigit() returns True for Arabic-Indic digits (٠–٩),
        and int() converts them silently — a malicious installed_plugins.json
        could use '٢.٠.٠' to bypass --require-version 2.0.0. The ASCII-only
        regex check in _parse() must reject these.
        """
        with pytest.raises(ValueError, match="non-numeric"):
            compare_version("٢.٠.٠", "1.0.0")

    def test_fullwidth_digits_rejected(self) -> None:
        """Fullwidth digits ０–９ (U+FF10–U+FF19) also bypass isdigit()."""
        with pytest.raises(ValueError, match="non-numeric"):
            compare_version("２.０.０", "1.0.0")


# ---------- corrupt JSON file handling (F10) ----------


def test_corrupt_json_emits_warning_and_returns_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW-2026-05-21 F10: torn read / corrupt JSON must surface a warning.

    Previously OSError and JSONDecodeError were silently swallowed, making a
    transient torn-read race indistinguishable from "no install found". The
    fix emits a stderr warning before returning None so operators can diagnose.
    """
    corrupt = tmp_path / "installed_plugins.json"
    corrupt.write_text("{this is not valid json", encoding="utf-8")
    result = resolve(cwd=tmp_path, installed_plugins_json=corrupt)
    captured = capsys.readouterr()
    assert result is None
    assert "warning" in captured.err.lower()
    assert "unreadable" in captured.err.lower() or "JSONDecodeError" in captured.err
