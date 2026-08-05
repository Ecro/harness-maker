"""Atomic file I/O helpers."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Top-level `harness.yaml` keys this project used to emit and has since RETIRED.
#
# This is the single source of truth for retired-key migration — `render` imports it rather
# than keeping a parallel copy, so removing a future key edits exactly one constant
# (PLAN-harness-diet ADR-012).
#
# Two layers consume it, and both are load-bearing:
#   1. `load_harness_yaml` (below) strips them from every read. This is the layer that
#      reaches an ALREADY-INSTALLED project: a package upgrade alone never runs the
#      renderer, so a render-time-only drop leaves the keys in place indefinitely.
#   2. `render._preserve_yaml_user_keys` filters them again, because it classifies
#      "present in the existing file, absent from the new render" as a user addition and
#      would otherwise re-append the key under a banner claiming it is the user's.
RETIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"workflows", "default_workflow"})

# Projects already advised about their retired keys, keyed by resolved path.
# The advisory is per-project rather than per-load because a single CLI invocation reads
# harness.yaml many times (verify, worktree, second_brain, render, ...) and one migration
# notice repeated a dozen times reads as an error.
_ADVISED_RETIRED_KEY_PATHS: set[str] = set()


def denormalize_home_to_tilde(path_str: str) -> str:
    """Convert a literal $HOME-prefixed absolute path back to ``~/...``.

    Bash expands unquoted ``~/foo`` at variable assignment time
    (``VAR=~/foo`` → ``VAR=/home/alice/foo``), so the CLI receives the
    machine-specific absolute path even though the user typed ``~/foo``.
    Storing that in ``harness.yaml`` breaks team sharing — teammate Bob has
    ``/home/bob``, not ``/home/alice``. Re-prefixing with ``~`` makes the path
    portable while still resolving correctly on every machine via
    ``Path(...).expanduser()`` downstream.
    """
    home = str(Path.home())
    if path_str == home:
        return "~"
    if path_str.startswith(home + "/"):
        return "~/" + path_str[len(home) + 1 :]
    return path_str


def atomic_write(path: Path, content: str | bytes, *, encoding: str = "utf-8") -> None:
    """Write content to path atomically: tempfile + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            delete=False,
        ) as tmp_b:
            tmp_b.write(content)
            tmp_b.flush()
            os.fsync(tmp_b.fileno())
            tmp_path = Path(tmp_b.name)
    else:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            delete=False,
            encoding=encoding,
            newline="",
        ) as tmp_t:
            tmp_t.write(content)
            tmp_t.flush()
            os.fsync(tmp_t.fileno())
            tmp_path = Path(tmp_t.name)
    try:
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def atomic_append(path: Path, line: str) -> None:
    """Append one short text line atomically (single os.write on O_APPEND fd).

    POSIX guarantees a single ``write()`` syscall ≤ PIPE_BUF (4096 bytes) on
    an ``O_APPEND`` descriptor is atomic — two concurrent writers cannot
    interleave their bytes. The buffered ``TextIOWrapper`` returned by
    ``Path.open("a")`` may split a write across multiple syscalls and is
    therefore unsafe for concurrent appenders (render manifest, orphan log).

    The caller MUST include any trailing newline in ``line`` — this helper
    does not append one. The caller MUST also ensure ``len(line.encode()) <
    4096``; longer lines lose the POSIX guarantee.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = line.encode("utf-8")
    fd = os.open(
        str(path),
        os.O_WRONLY | os.O_APPEND | os.O_CREAT,
        0o644,
    )
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def load_harness_yaml(path: Path) -> dict[str, Any]:
    """Load `harness.yaml` while tolerating the renderer's provenance frontmatter.

    Why: `render.py:_format_frontmatter` prepends a YAML provenance block
    (``generated_by``, ``content_hash``, …) to every rendered ``harness.yaml``.
    The resulting file is a *multi-document* YAML stream and ``yaml.safe_load``
    rejects it. Consumers (second_brain, verify, worktree, …) historically each
    invented their own parse strategy; this helper centralises it so the
    contract stops drifting. The user-data body is the LAST non-provenance
    mapping document — provenance always comes first and is filtered out so a
    truncated file (provenance written, body not yet flushed — possible on
    WSL2/NTFS partial writes) does not return provenance keys as user data.

    Returns ``{}`` for empty files, files with no top-level mapping, and any
    YAML that yields only non-mapping documents. Raises ``FileNotFoundError``
    when the file is absent and ``yaml.YAMLError`` when the content is
    structurally invalid.

    Retired top-level keys (``RETIRED_TOP_LEVEL_KEYS``) are stripped here so that
    every config entry point inherits the migration — including the ones an
    already-installed project hits after a package upgrade, which never re-render.
    """
    text = path.read_text(encoding="utf-8")
    last_mapping: dict[str, Any] = {}
    for doc in yaml.safe_load_all(text):
        if not isinstance(doc, dict):
            continue
        # Skip the renderer-injected provenance doc — see ADR-005 (frontmatter
        # invariant). Identifying it by `generated_by: harness-maker` is
        # tighter than positional ("first doc"); also avoids accidentally
        # treating a provenance-only truncated write as valid user data.
        if doc.get("generated_by") == "harness-maker":
            continue
        last_mapping = doc
    return strip_retired_keys(last_mapping, source=path)


def strip_retired_keys(data: dict[str, Any], *, source: Path | None = None) -> dict[str, Any]:
    """Drop retired top-level keys, advising once per project.

    Exposed separately from ``load_harness_yaml`` because not every config entry point
    goes through the multi-doc loader — ``cli._load_harness_yaml_body`` parses the body
    itself for the make-time telemetry diff and must see the same post-migration shape,
    or it reports a phantom "user key removed" on every upgrade.

    Returns the input unchanged (same object) when no retired key is present, so the
    common path allocates nothing.
    """
    present = sorted(k for k in data if k in RETIRED_TOP_LEVEL_KEYS)
    if not present:
        return data
    key = str(source.resolve()) if source is not None else ""
    if key not in _ADVISED_RETIRED_KEY_PATHS:
        _ADVISED_RETIRED_KEY_PATHS.add(key)
        # WARNING, not INFO: nothing in this package configures logging, so the root logger
        # sits at WARNING and `logging.lastResort` also fires only at WARNING+. An INFO
        # record is discarded outright — the advisory would never reach a single real user,
        # and the once-per-project memo below would be guarding a message nobody sees.
        # `hooks/autopilot_autoarm.py` records the same reasoning at its own log site.
        logger.warning(
            "harness.yaml carries retired key(s) %s — the fused-workflow axis was removed in "
            "0.47.0; they are ignored. Re-render via /harness-maker:make to drop them from "
            "disk. Chain stages with `/hm:loop --per-iter-stages` or autopilot instead.",
            ", ".join(present),
        )
    return {k: v for k, v in data.items() if k not in RETIRED_TOP_LEVEL_KEYS}


def append_atomic_line(path: Path, line: str) -> None:
    """Append one line via O_APPEND — kernel-atomic for writes <= PIPE_BUF (4096 bytes).

    The public home for a helper that four modules had each copied privately
    (`codex_ledger`, `review_telemetry`, `autopilot_ledger`, `delivery_metrics`). Those
    copies are left in place — rewiring them is a separate change — but a NEW caller
    reaching across a module boundary for a `_`-prefixed name is how a fifth copy starts,
    so new ledgers import this one.

    Raises `ValueError` above PIPE_BUF rather than writing: past that size the kernel may
    split the write, and a torn line interleaved with a concurrent writer's is dropped
    silently by every JSONL reader in this repo. Callers that must not fail bound their
    own fields first.

    **The guarantee is narrower than "atomic".** PIPE_BUF is specified for pipes; for a
    regular file, `O_APPEND` makes each individual `write()` land at an atomically-chosen
    offset, but nothing makes a MULTI-write row contiguous. The four private copies this
    replaces looped on a short write, which is precisely the case where a peer can append
    between iterations and interleave. A short write is therefore treated as a failure
    rather than retried: the row is lost (one observability line) instead of corrupting
    its neighbour, which is the direction every reader here degrades safely in.
    """
    payload = line if line.endswith("\n") else line + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > 4096:
        raise ValueError(
            f"ledger line {len(encoded)} bytes exceeds PIPE_BUF (4096); "
            "trim field content to preserve append atomicity"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_NOFOLLOW: a symlink committed at the ledger path would otherwise turn every
    # append into a write to its target. Callers already treat a failed append as a
    # dropped row, so the OSError degrades exactly like a full disk.
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    try:
        written = os.write(fd, encoded)
        if written != len(encoded):
            # Do NOT loop: a second write() can land after a peer's append, splicing this
            # row into theirs. Both lines then fail to parse and are silently dropped.
            raise OSError(
                f"short append: wrote {written} of {len(encoded)} bytes; "
                "retrying would risk interleaving with a concurrent writer"
            )
        os.fsync(fd)
    finally:
        os.close(fd)
