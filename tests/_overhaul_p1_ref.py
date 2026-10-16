"""The db19f023 reference harness for the overhaul-p1 differentials, extracted read-only."""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import tarfile
import threading
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAD_SRC = REPO_ROOT / "src"
REF_SHA = "db19f023"
#: The PR-C merge commit (0.63.0). AC-001 is PR-C's relation, so it is pinned to the render PR-C
#: shipped; PR-S changes the render on purpose and would otherwise break it (PLAN-hm-overhaul-p1-s).
PRC_MERGE_SHA = (
    (REPO_ROOT / "tests" / "fixtures" / "overhaul_p1" / "prc_merge_sha").read_text().strip()
)

_LOCK = threading.Lock()
_EXTRACTED: dict[tuple[Path, str], Path] = {}

# Ambient session state a hook or `make` would otherwise read from the developer's shell.
_SCRUBBED_ENV = (
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_ENV_FILE",
    "CLAUDECODE",
    "CURSOR_PROJECT_DIR",
    "HM_HOOK_HOST",
    "HM_SESSION_ID",
    "PYTHONPATH",
)


def ref_root(cache_dir: Path, sha: str = REF_SHA) -> Path:
    """A copy of `src/` at `sha` (db19f023 by default) under `cache_dir`, once per process.

    `git archive` reads the commit's tree straight from the object store, so nothing is
    written into `.git/` (PLAN-hm-overhaul-p1-c ADR-001).
    """
    with _LOCK:
        if (cache_dir, sha) in _EXTRACTED:
            return _EXTRACTED[(cache_dir, sha)]
        out = cache_dir / f"ref-{sha}"
        if not (out / "src" / "harness_maker" / "__init__.py").is_file():
            blob = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "archive", "--format=tar", sha, "src"],
                check=True,
                capture_output=True,
                timeout=120,
            ).stdout
            out.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
                tar.extractall(out, filter="data")
        _EXTRACTED[(cache_dir, sha)] = out
        return out


def clean_env(*, home: Path, src: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED_ENV}
    env.update(
        HOME=str(home),
        HARNESS_MAKER_FREEZE="1",
        PYTHONPATH=str(src),
        PYTHONDONTWRITEBYTECODE="1",
    )
    env.update(extra)
    return env


def init_project(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True, timeout=30)
    return path


def run_make(
    project: Path,
    args: Sequence[str],
    *,
    src: Path,
    home: Path,
) -> subprocess.CompletedProcess[str]:
    """`harness-maker make <project> <args>` under the given source tree."""
    home.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.cli", "make", str(project), *args],
        cwd=project,
        env=clean_env(home=home, src=src),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


_MASKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"^(\s*)(generated_at|harness_maker_version|content_hash): .*$", re.M),
        r"\1\2: <N>",
    ),
    (re.compile(r'"(timestamp|content_hash|version|recorded_hash)": "[^"]*"'), r'"\1": "<N>"'),
    (re.compile(r"content_hash=\S+ version=\S+ generated_at=\S+"), "content_hash=<N>"),
)


def normalise(text: str) -> str:
    """Mask provenance fields and timestamps, which differ by version and clock alone."""
    for pattern, repl in _MASKS:
        text = pattern.sub(repl, text)
    return text


def tree_files(root: Path) -> dict[str, str]:
    """Every rendered file under a project, normalised, keyed by its relative path."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or rel.parts[0] == ".git" or rel.parts[0].startswith(".backup-"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_bytes().hex()
        out[rel.as_posix()] = normalise(text)
    return out
