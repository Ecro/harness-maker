"""Check-suite verification cache — skip lint/mypy/test when input is unchanged.

Implements ADR-007: skip-key = sha256(project_root + HEAD sha + diff hash +
uv.lock hash + pyproject.toml hash + tool versions + env hash). Uses inverted
env policy: hash ALL env vars except a known-safe ignore set — over-invalidate
rather than risk a false PASS.

Env VALUES are scrubbed of per-invocation launcher paths before hashing (see
`_VOLATILE_VALUE_RE`). Without that the key changed on every call and no marker
could ever be fresh, so the cache was permanently cold while looking healthy.
Any change here must keep the key stable across two invocations of the same
command — `test_key_is_stable_across_ephemeral_launcher_envs` is that fence.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker import command_registry

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


# Path prefixes a launcher recreates on EVERY invocation. `uv run --with <pkg>` builds a
# throwaway environment per call under `~/.cache/uv/builds-v*/.tmpXXXXXX` and exports it
# through both PATH and VIRTUAL_ENV — and every rendered harness command is invoked that
# way, so hashing those values verbatim made the key change on every single call. The
# cache could never be fresh and `/hm:verify` + `/hm:wrapup` each re-ran the full suite
# forever, which is indistinguishable from correct invalidation (see
# `[fail:design] verification-cache-key-nondeterministic`).
#
# Scrubbed at the VALUE level rather than by ignoring the variable, for two reasons: a
# genuine PATH / VIRTUAL_ENV change still invalidates (the inverted-policy safety
# property is preserved — over-invalidate rather than risk a false PASS), and a future
# launcher's throwaway directory is covered without having to name its variable.
#
# `archive-v*` is deliberately NOT scrubbed: that path encodes the identity of the
# installed package, which is real signal.
_VOLATILE_VALUE_RE = re.compile(
    r"(?:[^\s:]*/\.cache/uv/(?:builds|environments)-v\d+"
    rf"|{re.escape(tempfile.gettempdir())})"
    r"/[^\s:]*"
)


def _scrub_volatile(value: str) -> str:
    return _VOLATILE_VALUE_RE.sub("<volatile>", value)


def _env_hash() -> str:
    """Hash all env vars except the known-safe ignore set (inverted policy).

    Values are scrubbed of per-invocation launcher paths first — see
    `_VOLATILE_VALUE_RE`. Without that, the key is not stable across two invocations
    of the same command and no marker can ever match.
    """
    items = sorted(
        (k, _scrub_volatile(v)) for k, v in os.environ.items() if not _should_ignore_env(k)
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


_DEFAULT_RELEVANT_PATTERNS: tuple[str, ...] = (
    "src/**",
    "tests/**",
    ".github/workflows/**",
    ".claude-verify.sh",
    "pyproject.toml",
    "uv.lock",
    "requirements*.txt",
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Makefile",
    "noxfile.py",
    "tox.ini",
)

_DEFAULT_IRRELEVANT_PATTERNS: tuple[str, ...] = (
    ".claude/memory/**",
    ".claude/observability/review-*.jsonl",
    "work-docs/**",
    "CHANGELOG.md",
)


def _match_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def is_relevant_path(path: str, *, docs_are_behavior: bool = False) -> bool:
    """Return True when a changed path can affect verification outcomes.

    The default policy intentionally treats wrapup-managed memory/work-docs
    edits as irrelevant so a post-verify PLAN status or memory append does not
    force another full regression suite. Unknown paths stay conservative.
    """
    normalized = path.replace("\\", "/")
    if docs_are_behavior and normalized.endswith((".md", ".rst", ".txt")):
        return True
    if _match_any(normalized, _DEFAULT_IRRELEVANT_PATTERNS):
        return False
    if _match_any(normalized, _DEFAULT_RELEVANT_PATTERNS):
        return True
    # Conservative fallback: unknown source-control changes might matter.
    return True


def _changed_paths(project_root: Path) -> list[str]:
    names = set[str]()
    for cmd in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        out = _run_quiet(cmd, cwd=project_root)
        if out:
            names.update(line.strip() for line in out.splitlines() if line.strip())
    return sorted(names)


def compute_relevant_skip_key(project_root: Path, *, docs_are_behavior: bool = False) -> str:
    """Compute a verification key that ignores wrapup-only document churn."""
    parts: list[str] = []
    root = project_root.resolve()
    parts.append(hashlib.sha256(str(root).encode()).hexdigest())
    parts.append(_run_quiet(["git", "rev-parse", "HEAD"], cwd=root))

    relevant_paths = [
        path
        for path in _changed_paths(root)
        if is_relevant_path(path, docs_are_behavior=docs_are_behavior)
    ]
    if relevant_paths:
        diff_parts: list[str] = []
        for path in relevant_paths:
            file_path = root / path
            diff_parts.append(path)
            diff_parts.append(_run_quiet(["git", "diff", "HEAD", "--", path], cwd=root))
            diff_parts.append(_run_quiet(["git", "diff", "--cached", "--", path], cwd=root))
            if file_path.is_file():
                diff_parts.append(_file_hash(file_path))
        parts.append(hashlib.sha256("\n".join(diff_parts).encode()).hexdigest())
    else:
        parts.append("")

    parts.append(_file_hash(root / "uv.lock"))
    parts.append(_file_hash(root / "pyproject.toml"))
    parts.append(json.dumps(_tool_versions(root), sort_keys=True))
    parts.append(_env_hash())
    parts.append("docs_are_behavior=1" if docs_are_behavior else "docs_are_behavior=0")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


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
        "passed_at": datetime.now(tz=UTC).isoformat(),
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


def _compute_key_for_args(args: argparse.Namespace) -> str:
    root = Path(args.root)
    if args.mode == "relevant":
        return compute_relevant_skip_key(root, docs_are_behavior=args.docs_are_behavior)
    return compute_skip_key(root)


def main(argv: list[str] | None = None) -> int:
    _guard = command_registry.guard_or_none("observability.verification_cache", argv)
    if _guard is not None:
        return _guard
    parser = argparse.ArgumentParser(prog="verification-cache")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", default=".")
        p.add_argument("--mode", choices=("full", "relevant"), default="relevant")
        p.add_argument("--docs-are-behavior", action="store_true")

    key_p = sub.add_parser("key")
    add_common(key_p)

    check_p = sub.add_parser("check")
    add_common(check_p)

    mark_p = sub.add_parser("mark-pass")
    add_common(mark_p)
    mark_p.add_argument("--checks", default="lint,mypy,pytest")

    explain_p = sub.add_parser("explain")
    add_common(explain_p)

    args = parser.parse_args(argv)
    key = _compute_key_for_args(args)

    if args.command == "key":
        print(key)
        return 0
    if args.command == "check":
        marker = is_fresh(key)
        if marker is None:
            print(json.dumps({"fresh": False, "key": key}))
            return 1
        print(json.dumps({"fresh": True, "key": key, "marker": marker}, sort_keys=True))
        return 0
    if args.command == "mark-pass":
        checks = [c.strip() for c in args.checks.split(",") if c.strip()]
        path = mark_passed(key, checks=checks, project_root=str(Path(args.root).resolve()))
        print(json.dumps({"marked": True, "key": key, "path": str(path)}, sort_keys=True))
        return 0
    if args.command == "explain":
        root = Path(args.root)
        changed = _changed_paths(root)
        relevant = [
            path
            for path in changed
            if is_relevant_path(path, docs_are_behavior=args.docs_are_behavior)
        ]
        print(
            json.dumps(
                {
                    "key": key,
                    "mode": args.mode,
                    "changed_paths": changed,
                    "relevant_paths": relevant,
                    "ignored_paths": [path for path in changed if path not in relevant],
                },
                sort_keys=True,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
