"""Build the commit a confirmation pass reviews, and resolve what it is diffed against."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from harness_maker import command_registry

_TIMEOUT = 30

#: The empty tree, git's universal fixed object. The last-resort `review_base` for a
#: repository whose HEAD is its only commit.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _git(base: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(base), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        env=env,
    )
    return result.stdout.strip()


def _try_git(base: Path, *args: str) -> str | None:
    try:
        return _git(base, *args)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None


def _default_base_branch(base: Path) -> str:
    """The branch a review is measured against when harness.yaml does not name one."""
    head = _try_git(base, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.rsplit("/", 1)[-1]
    return "main"


def resolve_review_base(base: Path, base_branch: str | None = None) -> str:
    """Resolve the commit the whole review is measured against — never HEAD.

    The naive definition (merge-base with the base branch) silently degenerates to HEAD in two
    ordinary configurations: a review running directly on the base branch (worktree OFF / Side
    preset, a supported mode) and a branch with no commits of its own. In both, the confirmation
    pass would then diff only the uncommitted working state — i.e. only the last round's fixes —
    which is precisely the scope-selective re-review the pass exists to replace. So each rule
    that returns HEAD is skipped rather than accepted.
    """
    head = _git(base, "rev-parse", "HEAD")
    branch = base_branch or _default_base_branch(base)

    # Try the remote-tracking ref FIRST. `_default_base_branch` reads
    # `refs/remotes/origin/HEAD` and returns its short name, but using that as a LOCAL branch
    # fails in a fresh clone that has no local `main`, and silently picks a stale commit when
    # the local branch lags the remote. Either way the chain fell through to `HEAD~1`, which
    # spans one commit instead of the branch divergence — the pass then reviews almost nothing.
    # Prefer whichever of the local and remote branch is FURTHER ALONG. Round 2 caught the
    # naive "remote first" ordering: this repo pushes manually and infrequently (CLAUDE.md), so
    # `origin/main` routinely lags local `main` by many commits, and merge-base against the
    # stale remote made the confirmation pass diff every unpushed commit. That is over-scope
    # rather than fail-open, but it costs a full-history lens dispatch per pass.
    remote = f"refs/remotes/origin/{branch}"
    preferred = branch
    if _try_git(base, "rev-parse", "--verify", "--quiet", remote):
        if _try_git(base, "merge-base", "--is-ancestor", branch, remote) is not None:
            preferred = remote
    elif not _try_git(base, "rev-parse", "--verify", "--quiet", branch):
        preferred = remote

    for args in (
        ("merge-base", "HEAD", preferred),
        ("merge-base", "HEAD", branch),
        ("merge-base", "--fork-point", branch),
        ("rev-parse", "HEAD~1"),
    ):
        candidate = _try_git(base, *args)
        if candidate and candidate != head:
            return candidate
    return EMPTY_TREE


def snapshot_working_tree(base: Path) -> str:
    """Write the current working state — tracked and untracked — to a tree, index untouched.

    Sole owner of this technique; `review_churn` pins its per-round endpoints the same way,
    and a second hand-rolled copy would be the place the ignored-file subtlety below is lost.

    Seed from HEAD before adding. An EMPTY index makes `add -A` treat a file that is
    tracked-but-`.gitignore`-matched as ignored, so it is silently omitted and the reader
    sees it as DELETED — the snapshot is then not the working tree, which is the one
    property that makes it usable. Reproduced against a probe repo with a tracked, ignored
    file. Seeding first also means `add -A` records genuine deletions rather than starting
    from nothing.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(base, "read-tree", "HEAD", env=env)
        _git(base, "add", "-A", env=env)
        return _git(base, "write-tree", env=env)


def create_freeze_commit(base: Path, slug: str, pass_id: str, review_base: str) -> str:
    """Commit the current working state — tracked and untracked — without touching the index.

    The fixes a confirmation pass must examine are uncommitted at the moment the gate would
    approve (commits happen at wrapup), so a ref naming HEAD would freeze the artifact WITHOUT
    the content the pass exists to look at.

    Parented on `review_base` so the pass's diff spans the whole review rather than the last
    round's fixes.
    """
    tree = snapshot_working_tree(base)

    parents = [] if review_base == EMPTY_TREE else ["-p", review_base]
    commit = _git(base, "commit-tree", tree, *parents, "-m", f"hm freeze: {slug} {pass_id}")
    _git(base, "update-ref", freeze_ref(slug, pass_id), commit)
    return commit


#: The only pass ids a freeze commit may use. `base` is EXCLUDED and that is the point:
#: `freeze_ref(slug, "base")` is byte-identical to `review_base_ref(slug)`, so
#: `hm freeze commit --pass base` overwrote the stored review base with the freeze commit —
#: after which the confirmation diff spans nothing and approves. Found by the cross-model
#: reviewer; reproduced by comparing the two functions' output.
VALID_PASS_IDS: frozenset[str] = frozenset({"confirm-1", "confirm-2"})


def freeze_ref(slug: str, pass_id: str) -> str:
    if pass_id not in VALID_PASS_IDS:
        raise ValueError(
            f"pass_id must be one of {sorted(VALID_PASS_IDS)}, got {pass_id!r}. "
            "`base` in particular would collide with the review_base store."
        )
    return f"refs/hm-freeze/v1/{validate_slug(slug)}-{pass_id}"


def review_base_ref(slug: str) -> str:
    """Where `review_base` is stored between round 1 and a pass that runs N rounds later.

    A value that must survive across rounds and a repair round, with no named store, is a free
    variable each pass would re-resolve — drifting as new commits land.
    """
    return f"refs/hm-freeze/v1/{validate_slug(slug)}-base"


#: Where the review_base WRITE time is recorded. The ref itself cannot carry it: it points at
#: a merge-base — a commit days or months old — so `git log --format=%ct` on the ref reads the
#: age of the branch point, not of the review. Both round-2 reviewers found the same
#: consequence independently: a grace window keyed on the commit date is inert for `-base`,
#: which is the ref the confirmation pass actually needs.
FREEZE_STAMP_DIR = Path(".claude/observability/.hm-freeze")


#: A slug reaches here from the stage prompt, where it is a task name the user typed. It is
#: interpolated into BOTH a git ref and a filesystem path, and the two fail differently: git
#: rejects `..` in a refname on its own, but `review_base_stamp` would happily write
#: `<base>/.claude/observability/.hm-freeze/../../../x.stamp`. A leading `-` is the other half —
#: it turns the ref argument into an option for whichever git plumbing command receives it.
_SAFE_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_slug(slug: str) -> str:
    """The one place a slug becomes a path or a ref. Rejects rather than sanitises.

    Sanitising (stripping `../`) would silently map two different slugs onto one namespace,
    which is worse here than refusing: these refs and stamps are how a confirmation pass finds
    the artifact it froze, and a collision hands it someone else's.
    """
    if not _SAFE_SLUG.match(slug):
        raise ValueError(
            f"slug must match {_SAFE_SLUG.pattern} (no path separators, no leading '-'), "
            f"got {slug!r}"
        )
    return slug


def review_base_stamp(base: Path, slug: str) -> Path:
    return base / FREEZE_STAMP_DIR / f"{validate_slug(slug)}.stamp"


def store_review_base(base: Path, slug: str, commit: str) -> None:
    _git(base, "update-ref", review_base_ref(slug), commit)
    stamp = review_base_stamp(base, slug)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(commit + "\n", encoding="utf-8")


def load_review_base(base: Path, slug: str) -> str | None:
    return _try_git(base, "rev-parse", "--verify", "--quiet", review_base_ref(slug))


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``hm freeze resolve-base --slug <slug>``.

    Round 1 of `/hm:review` calls this once and every later pass reads the ref, so the
    resolution happens in exactly one place rather than drifting per pass.
    """
    guard = command_registry.guard_or_none("freeze", argv)
    if guard is not None:
        return guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args or (
        args[0] != "resolve-base"
        and args[0] != "commit"
        and args[0] != "read-base"
        and args[0] != "reap"
    ):
        sys.stderr.write(
            "usage: hm freeze resolve-base --slug <slug> [--root <path>]\n"
            "       hm freeze read-base --slug <slug> [--root <path>]\n"
            "       hm freeze commit --slug <slug> --pass <confirm-1|confirm-2>\n"
            "       hm freeze reap --slug <slug>\n"
        )
        return 2

    parser = argparse.ArgumentParser(prog=f"hm freeze {args[0]}", add_help=False)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base-branch", default=None)
    parser.add_argument("--pass", dest="pass_id", default=None)
    try:
        opts = parser.parse_args(args[1:])
    except SystemExit:
        return 2

    base = Path(opts.root).resolve()

    try:
        validate_slug(opts.slug)
    except ValueError as exc:
        # Surface it as a diagnosed exit, not a traceback: every caller is a rendered stage
        # step whose next instruction reads this command's stdout, and a traceback there
        # produces no JSON at all.
        sys.stderr.write(f"freeze: {exc}\n")
        return 2

    if args[0] == "read-base":
        stored = load_review_base(base, opts.slug)
        if stored is None:
            # Fail loudly rather than silently re-resolving: a pass that recomputes the base
            # gets one that has drifted with the commits landed during the review, and the
            # drift is invisible in the diff it then reviews.
            sys.stderr.write(
                f"freeze: no stored review_base at {review_base_ref(opts.slug)}. Round 1 did "
                "not record it; do NOT re-resolve here — re-run the review from round 1.\n"
            )
            return 1
        sys.stdout.write(
            json.dumps({"review_base": stored, "ref": review_base_ref(opts.slug)}) + "\n"
        )
        return 0

    if args[0] == "reap":
        # An owner that does not depend on `live_slugs`. `prune_stale`'s sweep returns early
        # when nothing looks live, which under `worktree.enabled: false` (the Side default) is
        # ALWAYS — so with that guard alone every review permanently pinned a commit whose tree
        # holds every untracked non-ignored file present at pass time, reachable from a local
        # ref and therefore immune to gc. Found in round 2, created by the round-1 repair.
        removed: list[str] = []
        for ref in (
            review_base_ref(opts.slug),
            *(freeze_ref(opts.slug, p) for p in sorted(VALID_PASS_IDS)),
        ):
            if _try_git(base, "rev-parse", "--verify", "--quiet", ref) is None:
                continue
            _git(base, "update-ref", "-d", ref)
            removed.append(ref)
        review_base_stamp(base, opts.slug).unlink(missing_ok=True)
        sys.stdout.write(json.dumps({"removed": removed}) + "\n")
        return 0

    if args[0] == "commit":
        if opts.pass_id not in VALID_PASS_IDS:
            sys.stderr.write(
                f"freeze commit: --pass must be one of {sorted(VALID_PASS_IDS)}, got "
                f"{opts.pass_id!r}. `base` would collide with the review_base store ref.\n"
            )
            return 2
        stored = load_review_base(base, opts.slug)
        if stored is None:
            sys.stderr.write(
                f"freeze: no stored review_base at {review_base_ref(opts.slug)}; the freeze "
                "commit would have no parent to diff from.\n"
            )
            return 1
        sha = create_freeze_commit(base, opts.slug, opts.pass_id, stored)
        sys.stdout.write(
            json.dumps(
                {
                    "freeze_commit": sha,
                    "ref": freeze_ref(opts.slug, opts.pass_id),
                    "review_base": stored,
                    "diff_span": f"{stored}..{sha}",
                }
            )
            + "\n"
        )
        return 0

    commit = resolve_review_base(base, opts.base_branch)
    store_review_base(base, opts.slug, commit)
    sys.stdout.write(json.dumps({"review_base": commit, "ref": review_base_ref(opts.slug)}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
