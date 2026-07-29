"""Wrapup Steps 6 → 7.6 as one call: pre-scan, stage, commit, pop, clear, drain.

Orchestration only ([ADR-003](../../work-docs/PLAN-workflow-step-audit.md#adr-003)) —
every git effect below is produced by `worktree.py`'s existing entry points, so this
cannot drift from the steps it replaces. The one piece of genuinely new logic is the
typed staging manifest ([ADR-007](#adr-007)), because no library function owns it today
and the shell form it replaces treated an absent optional path, a permission error and a
real `git add` failure as the same silent success.

It deliberately STOPS before Step 7.7 `task-land` ([ADR-006](#adr-006)): that is the only
step that can lose work, and it keeps its own invocation, its own stderr, and its own
operator decision point.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_maker import command_registry
from harness_maker import worktree as wt

#: Exit codes are part of the contract the stage prose reads.
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


class LandAbortError(Exception):
    """Abort before any mutation. Carries the receipt fragment to print."""

    def __init__(self, reason: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _resolve_root(raw: str, label: str) -> Path:
    """Refuse anything that is not an absolute path to a real git working tree.

    There is no `Path.cwd()` default on purpose. A cwd default is wrong twice over here:
    it silently retargets the whole composite when the caller's shell is somewhere
    unexpected, and `Path.cwd()` itself raises when the process's cwd has been deleted —
    which is exactly the state `task-land` leaves behind for a subsequent run.
    """
    p = Path(raw)
    if not p.is_absolute():
        raise LandAbortError(f"{label} must be an absolute path, got {raw!r}")
    try:
        resolved = p.resolve(strict=True)
    except OSError as e:
        raise LandAbortError(f"{label} does not resolve: {raw!r} ({type(e).__name__}: {e})") from e
    if not wt._is_git_repo(resolved):
        raise LandAbortError(f"{label} is not a git working tree: {resolved}")
    return resolved


def _common_git_dir(root: Path) -> str | None:
    r = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    return str(Path(out).resolve()) if out else None


def assert_same_repo(worktree: Path, base: Path) -> None:
    """A worktree and its base share one common git dir. Symlinked roots resolve first.

    Without this a `--worktree` pointing at an unrelated checkout would be staged and
    committed happily, and the pop would then run against a base that never produced it.
    """
    wt_common, base_common = _common_git_dir(worktree), _common_git_dir(base)
    if wt_common is None or base_common is None:
        raise LandAbortError("could not resolve the common git dir for --worktree/--base")
    if wt_common != base_common:
        raise LandAbortError(
            "--worktree is not a worktree of --base "
            f"(common git dirs differ: {wt_common} vs {base_common})"
        )


# ── ADR-006: the legacy-ref pre-scan ──────────────────────────────────────────


def live_legacy_refs(base: Path) -> list[str]:
    """Live `.hm-finalize-stash-*` refs with an EMPTY `session_uuid`.

    `worktree.py:3330` skips a ref only when its `session_uuid` is truthy AND unowned; a
    legacy ref with an empty uuid falls through to the session-marker check and IS
    popped. That pop dirties the base, and `task-land` self-aborts on a dirty base — so
    the deadlock is reachable from a state the harness itself can be carrying.
    """
    claude = base / wt._LOOP_MARKER_DIR
    if not claude.is_dir():
        return []
    found: list[str] = []
    for ref_file in sorted(claude.glob(f"{wt._STASH_REF_PREFIX}*")):
        fields = wt._validate_stash_ref_fields(wt._read_stash_ref_file(ref_file))
        if fields is None:
            continue
        if fields.get("session_uuid", "").strip():
            continue
        if not wt._session_marker_present(fields["session_marker"]):
            continue
        found.append(ref_file.name)
    return found


def legacy_ref_remediation(base: Path, refs: list[str]) -> str:
    """CLAUDE.md's LLM behavior contract: never point at `git stash drop` without a diff.

    This is precisely the moment a reader reaches for `drop`, so the preview obligation
    is part of the message rather than a nearby paragraph someone may not read.
    """
    lines = [
        "[wrapup_land] ABORT — live legacy finalize-stash ref(s) with no session_uuid:",
        *(f"  - {base / wt._LOOP_MARKER_DIR / name}" for name in refs),
        "",
        "Nothing was staged and nothing was committed. These refs would be popped by",
        "post-commit-pop, dirtying the base, and `task-land` self-aborts on a dirty base.",
        "",
        "Resolve manually, in this order:",
        "  1. PREVIEW the content first — read it before deciding anything:",
        "       git stash show -p <ref>",
        "  2. Keep it (apply/cherry-pick into the task branch) or, only after reading that",
        "     diff and confirming with the user, drop it.",
        "  3. Re-run this command.",
        "",
        "To proceed anyway (you accept the pop + the possible land deadlock):",
        "  ... wrapup_land --allow-legacy-ref ...",
    ]
    return "\n".join(lines)


# ── ADR-007: the typed staging manifest ───────────────────────────────────────


def stage_manifest(
    worktree: Path, required: list[str], optional: list[str]
) -> list[dict[str, str]]:
    """Stage each path independently and record what happened to it.

    A single multi-pathspec `git add` is atomic: one non-matching argument aborts the
    whole call and stages nothing. The shell loop this replaces avoided that but paid for
    it with `2>/dev/null || true`, which also swallowed real failures — the observed
    2026-05-30 case where wiki + failures silently left a wrapup commit.
    """
    dispositions: list[dict[str, str]] = []
    for kind, paths in (("required", required), ("optional", optional)):
        for rel in paths:
            target = worktree / rel
            # A glob that matches nothing is an absent OPTIONAL path, not an error —
            # `REVIEW-<slug>-*.md` legitimately has zero hits when review did not run.
            is_glob = any(c in rel for c in "*?[")
            exists = bool(list(worktree.glob(rel))) if is_glob else target.exists()
            if not exists:
                if kind == "required":
                    raise LandAbortError(
                        f"required path is absent: {rel} (looked under {worktree})",
                        {"path": rel, "kind": kind},
                    )
                dispositions.append({"path": rel, "kind": kind, "disposition": "absent-optional"})
                continue
            r = _git(worktree, "add", "--", rel)
            if r.returncode != 0:
                raise LandAbortError(
                    f"git add failed for {rel}: {r.stderr.strip()}",
                    {"path": rel, "kind": kind, "git_stderr": r.stderr.strip()},
                )
            dispositions.append({"path": rel, "kind": kind, "disposition": "staged"})
    return dispositions


def _staged_paths(worktree: Path) -> list[str]:
    r = _git(worktree, "diff", "--cached", "--name-only")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def _head_subject(worktree: Path) -> str:
    r = _git(worktree, "log", "-1", "--pretty=%s")
    return r.stdout.strip() if r.returncode == 0 else ""


# ── the composite ─────────────────────────────────────────────────────────────


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    receipt: dict[str, Any] = {"steps": {}}

    worktree = _resolve_root(args.worktree, "--worktree")
    base = _resolve_root(args.base, "--base")
    assert_same_repo(worktree, base)
    receipt["worktree"], receipt["base"], receipt["slug"] = str(worktree), str(base), args.slug

    # ADR-006 — BEFORE staging, so an abort leaves no commit for a retry to accumulate on.
    if args.allow_legacy_ref:
        receipt["steps"]["legacy_ref_scan"] = {"status": "bypassed"}
    else:
        legacy = live_legacy_refs(base)
        if legacy:
            print(legacy_ref_remediation(base, legacy), file=sys.stderr)
            receipt["steps"]["legacy_ref_scan"] = {"status": "abort", "refs": legacy}
            return EXIT_FAILED, receipt
        receipt["steps"]["legacy_ref_scan"] = {"status": "clean"}

    message = Path(args.message_file).read_text(encoding="utf-8")
    subject = message.splitlines()[0].strip() if message.strip() else ""
    if not subject:
        raise LandAbortError(f"--message-file is empty: {args.message_file}")

    receipt["steps"]["index_before"] = _staged_paths(worktree)
    dispositions = stage_manifest(worktree, args.required, args.optional)
    receipt["steps"]["stage"] = dispositions

    staged = _staged_paths(worktree)
    receipt["steps"]["index_after"] = staged

    if staged:
        r = _git(worktree, "commit", "-m", message)
        if r.returncode != 0:
            raise LandAbortError(f"git commit failed: {r.stderr.strip()}")
        receipt["steps"]["commit"] = {"status": "created", "subject": subject}
    elif _head_subject(worktree) == subject:
        # Resume after a failed pop: the commit already happened, so re-committing would
        # add an empty duplicate. Skipping is what makes a retry safe to run.
        receipt["steps"]["commit"] = {"status": "already-present", "subject": subject}
    else:
        raise LandAbortError(
            "nothing is staged and HEAD is not this commit — refusing to commit an empty "
            f"index (HEAD subject: {_head_subject(worktree)!r})"
        )

    owned = wt._owned_crumb_read(base, args.slug)
    receipt["steps"]["owned_uuids"] = sorted(owned)
    env_before = os.environ.get("HM_OWNED_SESSION_UUIDS")
    os.environ["HM_OWNED_SESSION_UUIDS"] = ",".join(sorted(owned))
    try:
        pop_rc = wt._cli_post_commit_pop([str(base)])
    finally:
        if env_before is None:
            os.environ.pop("HM_OWNED_SESSION_UUIDS", None)
        else:
            os.environ["HM_OWNED_SESSION_UUIDS"] = env_before
    receipt["steps"]["post_commit_pop"] = {"rc": pop_rc}

    if pop_rc == 0:
        wt._owned_crumb_clear(base, args.slug)
        receipt["steps"]["owned_crumb_clear"] = {"status": "cleared"}
    else:
        # The crumb is the only record of which refs are ours. Clearing it after a failed
        # pop would strand the remaining refs as unownable on every later attempt.
        receipt["steps"]["owned_crumb_clear"] = {"status": "kept-pop-failed"}
        return EXIT_FAILED, receipt

    wt._cli_drain([str(base)])
    receipt["steps"]["drain"] = {"status": "ran"}
    return EXIT_OK, receipt


def main(argv: list[str] | None = None) -> int:
    guard = command_registry.guard_or_none("wrapup_land", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm wrapup_land")
    parser.add_argument("--worktree", required=True, help="absolute path to the task worktree")
    parser.add_argument("--base", required=True, help="absolute path to the base repo")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--message-file", dest="message_file", required=True)
    parser.add_argument("--required", action="append", default=[], help="repeatable")
    parser.add_argument("--optional", action="append", default=[], help="repeatable")
    parser.add_argument("--allow-legacy-ref", dest="allow_legacy_ref", action="store_true")
    args = parser.parse_args(argv)

    try:
        rc, receipt = run(args)
    except LandAbortError as e:
        print(f"[wrapup_land] {e.reason}", file=sys.stderr)
        print(json.dumps({"ok": False, "abort": e.reason, **e.detail}, indent=2))
        return EXIT_FAILED
    receipt["ok"] = rc == EXIT_OK
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return rc


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    raise SystemExit(main())
