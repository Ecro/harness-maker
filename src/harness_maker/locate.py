"""Resolve which harness-maker plugin install is active for a given cwd."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

PLUGIN_NAME = "harness-maker"
_ASCII_DIGITS_RE = re.compile(r"[0-9]+")


def _default_plugins_json() -> Path:
    """Resolved per call so tests that monkeypatch HOME after import work correctly."""
    return Path.home() / ".claude" / "plugins" / "installed_plugins.json"


class LocateEntry(NamedTuple):
    marketplace: str
    version: str
    scope: str
    install_path: Path
    installed_at: str
    git_commit_sha: str
    project_path: Path | None


def _iter_harness_maker_entries(
    payload: dict[str, Any], plugin_name: str
) -> list[tuple[str, dict[str, Any]]]:
    """Walk ``plugins`` map and yield (marketplace, entry) for matching plugin keys.

    Key format: "<plugin>@<marketplace>". Skips keys whose left side != plugin_name.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    for key, entries in (payload.get("plugins") or {}).items():
        if "@" not in key:
            continue
        left, marketplace = key.split("@", 1)
        if left != plugin_name:
            continue
        for entry in entries or []:
            out.append((marketplace, entry))
    return out


def _to_entry(marketplace: str, raw: dict[str, Any]) -> LocateEntry | None:
    """Return None when required keys are missing (corrupt / partial entries)."""
    try:
        project_path_raw = raw.get("projectPath")
        return LocateEntry(
            marketplace=marketplace,
            version=str(raw["version"]),
            scope=str(raw["scope"]),
            install_path=Path(str(raw["installPath"])),
            installed_at=str(raw.get("installedAt", "")),
            git_commit_sha=str(raw.get("gitCommitSha", "")),
            project_path=Path(project_path_raw) if project_path_raw else None,
        )
    except (KeyError, TypeError):
        return None


def resolve(
    plugin_name: str = PLUGIN_NAME,
    cwd: Path | None = None,
    installed_plugins_json: Path | None = None,
) -> LocateEntry | None:
    """Pick the highest-priority entry for ``plugin_name``.

    Priority:
        1. ``projectPath == cwd``                  (tier 1)
        2. ``scope == "user"``                     (tier 2)
        3. ``installedAt`` desc (tiebreak only)    within same tier

    No tier-3 fallback to "most-recent project-scope of another cwd" — that
    would silently re-pick the kairos-style wrong entry (the original bug).
    Returns None when neither tier-1 nor tier-2 matches, when the source file
    is missing, or when it is unreadable / corrupt (a stderr warning is
    emitted in the latter case so torn-read races during concurrent
    `claude plugin install/update` are diagnosable).
    """
    src = installed_plugins_json or _default_plugins_json()
    if not src.exists():
        return None
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"harness-maker: warning — {src} unreadable ({exc.__class__.__name__}); "
            "treating as not installed",
            file=sys.stderr,
        )
        return None

    candidates = _iter_harness_maker_entries(payload, plugin_name)
    if not candidates:
        return None

    cwd_str = str(cwd) if cwd is not None else None

    tier_1: list[tuple[str, dict[str, Any]]] = []
    tier_2: list[tuple[str, dict[str, Any]]] = []
    for marketplace, raw in candidates:
        scope = raw.get("scope")
        project_path = raw.get("projectPath")
        if cwd_str is not None and project_path == cwd_str:
            tier_1.append((marketplace, raw))
        elif scope == "user":
            tier_2.append((marketplace, raw))

    # Drop malformed entries from each tier independently so a tier-1 made of
    # only malformed entries still falls through to tier-2 (avoids the bug
    # where the higher-priority tier "wins" but yields nothing).
    def _is_well_formed(raw: dict[str, Any]) -> bool:
        return "version" in raw and "scope" in raw and "installPath" in raw

    tier_1 = [(mk, raw) for (mk, raw) in tier_1 if _is_well_formed(raw)]
    tier_2 = [(mk, raw) for (mk, raw) in tier_2 if _is_well_formed(raw)]
    chosen_tier = tier_1 or tier_2
    if not chosen_tier:
        return None

    # installedAt desc tiebreak (lexicographic ISO-8601 sort works as time sort)
    marketplace, raw = max(chosen_tier, key=lambda mr: str(mr[1].get("installedAt", "")))
    return _to_entry(marketplace, raw)


def compare_version(actual: str, required: str) -> bool:
    """True iff ``actual >= required`` (semver-ish integer tuple compare).

    Accepts X / X.Y / X.Y.Z forms. Missing parts treated as 0. ASCII decimal
    digits only — Unicode numerics (Arabic-Indic, fullwidth, superscript)
    are rejected so an attacker cannot bypass a `--require-version` gate by
    writing `٢.٠.٠` in a user-writable installed_plugins.json.
    Raises ValueError on non-numeric input.
    """
    return _parse(actual) >= _parse(required)


def _parse(v: str) -> tuple[int, int, int]:
    if not v:
        raise ValueError("version string is empty")
    parts = v.split(".")
    if len(parts) > 3:
        raise ValueError(f"version {v!r} has more than 3 parts")
    nums: list[int] = []
    for p in parts:
        if not _ASCII_DIGITS_RE.fullmatch(p):
            raise ValueError(f"version {v!r} contains non-numeric (or non-ASCII) part {p!r}")
        nums.append(int(p))
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]
