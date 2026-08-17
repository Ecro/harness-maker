"""One open `/hm:review` run per slug — the identity the round caps were missing (ADR-003)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker import command_registry
from harness_maker.freeze import validate_slug
from harness_maker.second_opinion_invoke import resolve_base_root

#: Where a slug's open run is recorded, relative to the BASE repo root.
#:
#: Registered in TWO places in `worktree.py` and both are load-bearing: the gitignore globs keep
#: it out of commits, and `_HARNESS_ARTIFACT_PREFIXES` is the tuple the FINALIZE dirt-filter
#: reads. A gitignore-only registration leaves every live run-state file as user dirt that
#: `worktree finalize` sweeps into the finalize stash — how `.hm-autopilot` was silently
#: disarmed once already (ADR-011 of PLAN-multisession-marker-scoping).
STATE_PREFIX = ".claude/.hm-review-run-"


def run_state_path(base: Path, slug: str) -> Path:
    """Base-root-relative, and slug-validated at the one place it becomes a filename.

    Base root, never the worktree: a worktree-relative path is gitignored inside the worktree
    and vanishes at `task-land` — the `codex_ledger` `Path.cwd()` precedent.
    """
    return base / f"{STATE_PREFIX}{validate_slug(slug)}.json"


def load_run(base: Path, slug: str) -> dict[str, Any] | None:
    path = run_state_path(base, slug)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # A truncated write is not an open run. Refusing here would block the slug forever on a
        # file nothing can interpret; treating it as absent lets `open` mint a fresh record.
        return None
    return payload if isinstance(payload, dict) else None


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _create_exclusive(path: Path, content: str) -> bool:
    """Create the record or lose the race — never overwrite. Returns False if it already exists.

    `open`'s read-then-write was a TOCTOU: two `/hm:review` invocations on one slug could both
    see no record and both write one, and the loser's id wins the file. That is load-bearing
    rather than cosmetic because `freeze.freeze_ref` keys on **slug + pass_id with no run id**,
    so the two runs share freeze refs — the run that loses the race can clobber the tree the
    other one froze.

    The record is written to a temp file FIRST and published with `os.link`, so the path never
    exists in an empty state. `os.open(O_CREAT|O_EXCL)` alone is NOT enough here: it creates the
    directory entry and writes a moment later, and in that window a peer sees a zero-byte file.
    The peer's recovery path cannot tell "empty because a peer is mid-write" from "corrupt", so
    it would overwrite a live record and both runs would proceed as owner — reopening the race
    this function exists to close. `link` publishes an already-complete file, which is what makes
    the caller's "unreadable ⇒ corrupt" inference sound.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(tmp, 0o600)
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        Path(tmp).unlink(missing_ok=True)


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _cmd_open(base: Path, slug: str, force: bool) -> int:
    existing = load_run(base, slug)
    if existing is not None and not force:
        # Non-zero so the stage branches on the exit code, and the SAME id on stdout so it
        # resumes that run rather than minting one. Both halves matter: an exit code with no id
        # tells the caller to stop without telling it what to stop into.
        _emit(existing)
        sys.stderr.write(
            f"[review-run] slug {slug!r} already has an open run "
            f"{existing.get('id')!r} (opened {existing.get('opened_at')}). Resume it. "
            "Recovery from an abandoned run is `open --force`, which names what it displaces — "
            "there is no expiry, because a long review and an abandoned one look identical "
            "from elapsed time alone.\n"
        )
        return 1

    record: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "slug": slug,
        "opened_at": datetime.now(UTC).isoformat(),
        "state": "open",
        # Always present, `None` when nothing was displaced. A key that exists only on the
        # takeover path makes every reader carry a `.get`, and the one that forgets raises
        # `KeyError` on the ordinary path rather than the rare one.
        "displaced": existing.get("id") if existing is not None else None,
    }
    payload = json.dumps(record, sort_keys=True) + "\n"
    path = run_state_path(base, slug)
    if force:
        _atomic_write(path, payload)
    elif not _create_exclusive(path, payload):
        winner = load_run(base, slug)
        if winner is None:
            # The file exists but is not a readable record — the corrupt-state case `load_run`
            # promises to recover from. `O_EXCL` cannot tell a live peer from a half-written
            # file, so the recovery has to happen here or the slug is blocked forever on bytes
            # nothing can interpret.
            _atomic_write(path, payload)
        else:
            # Lost the create race to a real peer. Report it the way the read-side refusal above
            # does, so both paths tell the caller what to resume into.
            _emit(winner)
            sys.stderr.write(
                f"[review-run] slug {slug!r} was opened concurrently by another run "
                f"{winner.get('id')!r}. Resume it.\n"
            )
            return 1
    _emit(record)
    return 0


def _cmd_status(base: Path, slug: str) -> int:
    existing = load_run(base, slug)
    _emit(existing if existing is not None else {"slug": slug, "state": "none"})
    return 0


def _cmd_close(base: Path, slug: str, run_id: str, outcome: str) -> int:
    existing = load_run(base, slug)
    if existing is None:
        # Idempotent on purpose. `review.md.j2` wires `close` onto several terminal branches and
        # a review can reach two of them in one pass, so a second close must be a no-op rather
        # than a failure the stage reports as a blocker.
        _emit({"closed": False, "slug": slug, "reason": "no open run"})
        return 0
    if existing.get("id") != run_id:
        sys.stderr.write(
            f"[review-run] refusing to close {slug!r}: the open run is "
            f"{existing.get('id')!r}, not {run_id!r}. Releasing it would hand the slug to a "
            "peer that is still using it.\n"
        )
        return 1
    run_state_path(base, slug).unlink(missing_ok=True)
    _emit({"closed": True, "slug": slug, "id": run_id, "outcome": outcome})
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``hm review_run open|status|close --slug <slug>``."""
    guard = command_registry.guard_or_none("review_run", argv)
    if guard is not None:
        return guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args or args[0] not in ("open", "status", "close"):
        sys.stderr.write(
            "usage: hm review_run open   --slug <slug> [--root <path>] [--force]\n"
            "       hm review_run status --slug <slug> [--root <path>]\n"
            "       hm review_run close  --slug <slug> --run-id <id> "
            "--outcome <APPROVED|CHANGES_REQUESTED> [--root <path>]\n"
        )
        return 2

    parser = argparse.ArgumentParser(prog=f"hm review_run {args[0]}", add_help=False)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--run-id", dest="run_id", default=None)
    parser.add_argument("--outcome", default=None)
    try:
        opts = parser.parse_args(args[1:])
    except SystemExit:
        return 2

    try:
        slug = validate_slug(opts.slug)
    except ValueError as exc:
        sys.stderr.write(f"[review-run] {exc}\n")
        return 2

    base = resolve_base_root(Path(opts.root))

    if args[0] == "open":
        return _cmd_open(base, slug, force=opts.force)
    if args[0] == "status":
        return _cmd_status(base, slug)
    # Explicit rather than a fall-through: the T-C2 registry↔source parity gate reads the
    # `args[0] == "<verb>"` comparisons to discover a module's real subcommands, so a verb that
    # is only reachable as the else-branch reads as registry-only drift.
    if args[0] == "close":
        if not opts.run_id or not opts.outcome:
            sys.stderr.write("[review-run] close requires --run-id and --outcome\n")
            return 2
        if opts.outcome not in ("APPROVED", "CHANGES_REQUESTED"):
            sys.stderr.write(
                "[review-run] --outcome must be APPROVED or CHANGES_REQUESTED, "
                f"got {opts.outcome!r}\n"
            )
            return 2
        return _cmd_close(base, slug, opts.run_id, opts.outcome)

    return 2


if __name__ == "__main__":
    sys.exit(main())
