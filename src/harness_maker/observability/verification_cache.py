"""Check-suite verification cache — skip lint/mypy/test when input is unchanged.

Implements ADR-007: skip-key = sha256(project_root + HEAD sha + diff hash +
uv.lock hash + pyproject.toml hash + tool versions + env hash). Uses inverted
env policy: hash ALL env vars except a known-safe ignore set.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ENV_IGNORE: frozenset[str] = frozenset(
    {
        "PWD",
        "OLDPWD",
        "_",
        "SHLVL",
        "TERM",
        "TERM_PROGRAM",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "EDITOR",
        "VISUAL",
        "PAGER",
        "COLORFGBG",
        "COLORTERM",
    }
)

_ENV_IGNORE_PATTERNS: tuple[str, ...] = (
    "SSH_*",
    "WSL_*",
    "WT_*",
    "CLAUDE_CODE_*",
)


def _should_ignore_env(key: str) -> bool:
    if key in _ENV_IGNORE:
        return True
    return any(fnmatch.fnmatch(key, pat) for pat in _ENV_IGNORE_PATTERNS)


def _env_hash() -> str:
    """Hash all env vars except the known-safe ignore set (inverted policy)."""
    items = sorted(
        (k, v) for k, v in os.environ.items() if not _should_ignore_env(k)
    )
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


def _file_hash(path: Path) -> str:
    """SHA-256 of file contents, or empty string if file doesn't exist."""
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_quiet(cmd: list[str], *, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=cwd,
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _tool_versions(project_root: Path) -> dict[str, str]:
    """Collect semver strings for key tools."""
    versions: dict[str, str] = {}
    for name, cmd in [
        ("python", ["python3", "--version"]),
        ("ruff", ["ruff", "--version"]),
        ("mypy", ["mypy", "--version"]),
        ("pytest", ["python3", "-m", "pytest", "--version"]),
    ]:
        versions[name] = _run_quiet(cmd, cwd=project_root)
    return versions


def compute_skip_key(project_root: Path) -> str:
    """Compute the skip-key for a project's check suite.

    ADR-007: project_root_hash + HEAD sha + diff hash + uv.lock hash +
    pyproject.toml hash + tool versions + env hash (inverted allowlist).
    """
    parts: list[str] = []

    parts.append(hashlib.sha256(str(project_root.resolve()).encode()).hexdigest())

    parts.append(_run_quiet(["git", "rev-parse", "HEAD"], cwd=project_root))

    diff_out = _run_quiet(["git", "diff", "HEAD"], cwd=project_root)
    staged_out = _run_quiet(["git", "diff", "--cached"], cwd=project_root)
    combined = diff_out + staged_out
    parts.append(hashlib.sha256(combined.encode()).hexdigest() if combined else "")

    parts.append(_file_hash(project_root / "uv.lock"))
    parts.append(_file_hash(project_root / "pyproject.toml"))

    tv = _tool_versions(project_root)
    parts.append(json.dumps(tv, sort_keys=True))

    parts.append(_env_hash())

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_dir() -> Path:
    env_override = os.environ.get("HARNESS_MAKER_CACHE_DIR")
    if env_override:
        return Path(env_override) / "verify"
    return Path.home() / ".cache" / "harness-maker" / "verify"


def _marker_path(key: str) -> Path:
    return _cache_dir() / f"{key}.json"


def is_fresh(key: str) -> dict[str, Any] | None:
    """Check if a passing marker exists for this key.

    Returns the marker dict if fresh, None otherwise.
    """
    path = _marker_path(key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("passed"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def mark_passed(
    key: str,
    *,
    checks: list[str] | None = None,
    project_root: str = "",
) -> Path:
    """Write a passing marker for the given key. Returns the marker path."""
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    marker = {
        "passed": True,
        "passed_at": datetime.now(tz=timezone.utc).isoformat(),
        "checks": checks or ["lint", "mypy", "pytest"],
        "project_root": project_root,
        "key": key,
    }

    path = _marker_path(key)
    fd, tmp = tempfile.mkstemp(
        dir=str(cache),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(marker, f)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def invalidate(key: str) -> bool:
    """Remove the marker for a key. Returns True if it existed."""
    path = _marker_path(key)
    if path.is_file():
        path.unlink()
        return True
    return False
