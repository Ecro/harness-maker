"""Filesystem cache for ProjectProfile keyed by repo path sha256."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from pydantic import ValidationError

from harness_maker.io_utils import atomic_write
from harness_maker.models import ProjectProfile
from harness_maker.profile import STACK_MANIFESTS

logger = logging.getLogger(__name__)

# Hard ceiling: even if no manifest changed, refresh the cache after this many
# seconds. 24h matches the validator C2 spec.
_MAX_AGE_SECONDS = 24 * 60 * 60

# Foreign-AI config files that future Phase 5 detection consumes. Listing them
# here so a touched `.cursor/rules/` or `AGENTS.md` invalidates Phase 2's cache
# even before Phase 5 wires the actual detection. (Per CACHED_MANIFESTS mandate
# in the PLAN.)
_FOREIGN_AI_CONFIGS: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    ".cursor/rules",
    ".continue/config.json",
    ".aider.conf.yml",
    ".github/copilot-instructions.md",
)


def _flatten_stack_manifests() -> tuple[str, ...]:
    """Flatten STACK_MANIFESTS dict-of-lists into a unique tuple of filenames."""
    seen: list[str] = []
    for manifests in STACK_MANIFESTS.values():
        for m in manifests:
            if m not in seen:
                seen.append(m)
    return tuple(seen)


def _flatten_stack_glob_concrete() -> tuple[str, ...]:
    """Literal filenames from STACK_GLOB_MANIFESTS (no ``*``-glob patterns).

    Glob patterns like ``*.csproj`` cannot be stat'd; they remain out of
    ``CACHED_MANIFESTS`` and rely on the 24h ceiling for invalidation.
    Function-scope import mirrors the module-level pattern that keeps
    ``profile`` ↔ ``detection_cache`` free of circular import deadlock.
    """
    from harness_maker.profile import STACK_GLOB_MANIFESTS

    out: list[str] = []
    for patterns in STACK_GLOB_MANIFESTS.values():
        for pat in patterns:
            if "*" not in pat:
                out.append(pat)
    return tuple(sorted(set(out)))


# All filenames whose mtime invalidates the cache. Stack manifests +
# STACK_GLOB literal filenames + foreign-AI config locations. Phase 5
# extends this with any new foreign-AI types. STACK_GLOB ``*``-pattern
# globs (e.g. ``*.csproj``) cannot be stat'd cheaply and rely on the
# 24h ceiling for invalidation — partial closure of the Phase 3 gap.
CACHED_MANIFESTS: tuple[str, ...] = (
    _flatten_stack_manifests() + _flatten_stack_glob_concrete() + _FOREIGN_AI_CONFIGS
)


def _default_cache_dir() -> Path:
    """Resolve to ~/.cache/harness-maker (CLAUDE.md §테스트 정책 shared cache root)."""
    return Path.home() / ".cache" / "harness-maker"


def _repo_hash(repo_path: Path) -> str:
    """Stable filename-safe key — sha256 of the absolute repo path, truncated."""
    abs_str = str(repo_path.resolve())
    return hashlib.sha256(abs_str.encode("utf-8")).hexdigest()[:16]


def _cache_file(repo_path: Path, cache_dir: Path) -> Path:
    return cache_dir / f"profile-{_repo_hash(repo_path)}.json"


def _max_manifest_mtime(repo_path: Path) -> float:
    """Newest mtime across all watched manifest files; 0.0 if none exist."""
    newest = 0.0
    for name in CACHED_MANIFESTS:
        candidate = repo_path / name
        try:
            mtime = candidate.stat().st_mtime
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            continue
        if mtime > newest:
            newest = mtime
    return newest


def load_or_run(repo_path: Path, cache_dir: Path | None = None) -> ProjectProfile | None:
    """Return cached profile if fresh; None tells caller to re-run live detection."""
    cdir = cache_dir if cache_dir is not None else _default_cache_dir()
    cache_file = _cache_file(repo_path, cdir)

    try:
        cache_stat = cache_file.stat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("detection_cache: cannot stat %s: %s", cache_file, exc)
        return None

    cache_mtime = cache_stat.st_mtime
    now = time.time()

    # 24h hard ceiling overrides everything else.
    if now - cache_mtime > _MAX_AGE_SECONDS:
        return None

    # Manifest-mtime invalidation: any tracked manifest newer than the cache
    # means the project changed and we must re-detect.
    if _max_manifest_mtime(repo_path) > cache_mtime:
        return None

    try:
        raw = cache_file.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("detection_cache: cannot read %s: %s", cache_file, exc)
        return None

    try:
        return ProjectProfile.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "detection_cache: corrupt cache at %s (%s); deleting and re-running detection",
            cache_file,
            exc,
        )
        try:
            cache_file.unlink()
        except OSError as unlink_exc:
            logger.warning(
                "detection_cache: failed to delete corrupt cache %s: %s",
                cache_file,
                unlink_exc,
            )
        return None


def write(
    profile: ProjectProfile,
    repo_path: Path,
    cache_dir: Path | None = None,
) -> None:
    """Persist profile JSON atomically; last-writer-wins on concurrent runs (ADR-008)."""
    cdir = cache_dir if cache_dir is not None else _default_cache_dir()
    cache_file = _cache_file(repo_path, cdir)
    atomic_write(cache_file, profile.model_dump_json())
