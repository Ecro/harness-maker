"""Phase 3 — the freeze is faithful, and review_base never degenerates to HEAD."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness_maker.freeze import (
    EMPTY_TREE,
    create_freeze_commit,
    freeze_ref,
    load_review_base,
    resolve_review_base,
    review_base_ref,
    store_review_base,
)
from harness_maker.freeze import (
    main as freeze_main,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "a.txt").write_text("one\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "first")
    return r


def test_review_base_never_resolves_to_head_on_the_base_branch(repo: Path) -> None:
    """The Side / worktree-OFF configuration: the review runs on the base branch itself.

    `merge-base(HEAD, main)` is HEAD here. Accepting it would make the confirmation pass diff
    only the uncommitted working state — exactly the scope-selective re-review it replaces.
    """
    (repo / "b.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "second")

    head = _git(repo, "rev-parse", "HEAD")
    base = resolve_review_base(repo, base_branch="main")
    assert base != head
    assert base == _git(repo, "rev-parse", "HEAD~1")


def test_review_base_never_resolves_to_head_on_a_branch_with_no_own_commits(repo: Path) -> None:
    _git(repo, "checkout", "-b", "hm/task")
    head = _git(repo, "rev-parse", "HEAD")
    assert resolve_review_base(repo, base_branch="main") != head


def test_review_base_falls_back_to_the_empty_tree_on_a_single_commit_repo(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    base = resolve_review_base(repo, base_branch="main")
    assert base != head
    assert base == EMPTY_TREE


def test_review_base_is_the_fork_point_on_a_task_branch(repo: Path) -> None:
    fork = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "hm/task")
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "task work")
    assert resolve_review_base(repo, base_branch="main") == fork


def test_freeze_commit_tree_equals_the_working_tree(repo: Path) -> None:
    """Tracked modifications and untracked additions must both survive the freeze.

    The fixes a confirmation pass exists to examine are uncommitted; a freeze that omitted
    them would review the artifact without the content under review.
    """
    (repo / "a.txt").write_text("modified\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("new\n", encoding="utf-8")

    base = resolve_review_base(repo, base_branch="main")
    commit = create_freeze_commit(repo, "slug", "confirm-1", base)

    frozen = _git(repo, "ls-tree", "-r", commit)
    assert "untracked.txt" in frozen
    blob = _git(repo, "rev-parse", f"{commit}:a.txt")
    assert _git(repo, "cat-file", "blob", blob) == "modified"


def test_freeze_commit_leaves_the_index_untouched(repo: Path) -> None:
    (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "staged.txt")
    before = _git(repo, "diff", "--cached", "--name-only")

    base = resolve_review_base(repo, base_branch="main")
    create_freeze_commit(repo, "slug", "confirm-1", base)

    assert _git(repo, "diff", "--cached", "--name-only") == before


def test_freeze_commit_is_parented_on_review_base_not_head(repo: Path) -> None:
    """With `-p HEAD`, `review_base..freeze` would show only the last round's fixes."""
    _git(repo, "checkout", "-b", "hm/task")
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "earlier phase")
    head = _git(repo, "rev-parse", "HEAD")

    (repo / "d.txt").write_text("uncommitted fix\n", encoding="utf-8")
    base = resolve_review_base(repo, base_branch="main")
    commit = create_freeze_commit(repo, "slug", "confirm-1", base)

    assert _git(repo, "rev-parse", f"{commit}^") == base
    assert base != head

    spanned = _git(repo, "diff", "--name-only", f"{base}..{commit}").split()
    assert "c.txt" in spanned, "the committed earlier phase must be in the reviewed diff"
    assert "d.txt" in spanned


def test_review_base_round_trips_through_its_ref(repo: Path) -> None:
    """A value that must survive N rounds and a repair round needs a named store."""
    assert load_review_base(repo, "slug") is None
    base = resolve_review_base(repo, base_branch="main")
    _git(repo, "checkout", "-b", "hm/task")
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "later")
    store_review_base(repo, "slug", base) if base != EMPTY_TREE else None
    if base != EMPTY_TREE:
        assert load_review_base(repo, "slug") == base


def test_the_shipped_cli_resolves_and_stores_in_one_call(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercise the entry point in its shipped spelling, not just the functions under it.

    `[fail:test] shipped-entry-point-not-exercised` (count:4): a unit test on
    `resolve_review_base` + `store_review_base` passes while `hm freeze resolve-base` is broken
    — an unparsed flag, a guard that swallows argv, a main that never writes the ref. The
    rendered `/hm:review` calls the CLI, so the CLI is what has to work.
    """
    _git(repo, "checkout", "-b", "hm/task")
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "later")

    rc = freeze_main(["resolve-base", "--slug", "cli-slug", "--root", str(repo)])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ref"] == "refs/hm-freeze/v1/cli-slug-base"
    assert payload["review_base"] == load_review_base(repo, "cli-slug"), (
        "the CLI printed a base it did not store; a later pass would re-resolve and drift"
    )
    assert payload["review_base"] != _git(repo, "rev-parse", "HEAD")


def test_the_cli_rejects_an_unknown_verb_without_writing_a_ref(repo: Path) -> None:
    assert freeze_main(["freeze-it"]) == 2
    assert load_review_base(repo, "cli-slug") is None


def test_the_cli_freezes_a_pass_and_reports_its_diff_span(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hm freeze commit --pass confirm-1`, the call the rendered confirmation pass makes."""
    _git(repo, "checkout", "-b", "hm/task")
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "later")
    assert freeze_main(["resolve-base", "--slug", "s", "--root", str(repo)]) == 0
    capsys.readouterr()

    # An UNCOMMITTED fix — the state the gate is about to approve, since wrapup owns commits.
    (repo / "fix.txt").write_text("the fix\n", encoding="utf-8")

    assert freeze_main(["commit", "--slug", "s", "--pass", "confirm-1", "--root", str(repo)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ref"] == "refs/hm-freeze/v1/s-confirm-1"
    assert payload["diff_span"] == f"{payload['review_base']}..{payload['freeze_commit']}"

    spanned = _git(repo, "diff", "--name-only", payload["diff_span"]).split()
    assert "fix.txt" in spanned, (
        "the frozen commit omits the uncommitted fix, so the pass would review an artifact "
        "without the content it exists to look at"
    )
    assert "c.txt" in spanned, "the span covers only the last change, not the whole review"


def test_read_base_fails_loudly_rather_than_re_resolving(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The absent case, fail-closed.

    Silently re-resolving here would hand the pass a base recomputed against a HEAD that moved
    during the review. The drift is invisible in the diff the pass then reviews, which is the
    whole reason the value has a named store.
    """
    assert freeze_main(["read-base", "--slug", "never-stored", "--root", str(repo)]) == 1
    assert "do NOT re-resolve" in capsys.readouterr().err


def test_read_base_returns_exactly_what_round_one_stored(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(repo, "checkout", "-b", "hm/task")
    (repo / "c.txt").write_text("three\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "later")
    assert freeze_main(["resolve-base", "--slug", "s", "--root", str(repo)]) == 0
    stored = json.loads(capsys.readouterr().out)["review_base"]

    # Commits land during the review — the drift a re-resolve would pick up.
    (repo / "d.txt").write_text("four\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "during the review")

    assert freeze_main(["read-base", "--slug", "s", "--root", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["review_base"] == stored


def test_freeze_commit_requires_a_pass_id(repo: Path) -> None:
    assert freeze_main(["commit", "--slug", "s", "--root", str(repo)]) == 2


# ── Round-1 review findings, all reproduced before repair ────────────────────


def test_a_freeze_pass_id_can_never_collide_with_the_base_store(repo: Path) -> None:
    """`freeze_ref(slug, "base")` was byte-identical to `review_base_ref(slug)`.

    So `hm freeze commit --slug s --pass base` overwrote the stored review base with the
    freeze commit. The next confirmation diff then spans `<freeze>..<freeze>` — nothing — and
    the pass approves without reviewing the artifact. Found by the cross-model reviewer;
    confirmed by comparing the two functions' output directly.
    """
    with pytest.raises(ValueError, match="collide"):
        freeze_ref("s", "base")
    assert freeze_ref("s", "confirm-1") != review_base_ref("s")
    assert freeze_ref("s", "confirm-2") != review_base_ref("s")


def test_the_cli_rejects_a_pass_id_that_would_overwrite_the_base(repo: Path) -> None:
    assert freeze_main(["commit", "--slug", "s", "--pass", "base", "--root", str(repo)]) == 2


def test_a_tracked_but_gitignored_file_is_still_frozen(repo: Path) -> None:
    """AC-004's whole claim is that the frozen tree IS the working tree.

    With an EMPTY temporary index, `git add -A` treats a tracked file that matches
    `.gitignore` as ignored and omits it — so the confirmation pass sees that file as DELETED
    relative to review_base and reviews an artifact that does not exist. Reproduced on a probe
    repo before the fix; the repair seeds the index from HEAD first.
    """
    (repo / ".mycache").write_text("original\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".mycache\n", encoding="utf-8")
    _git(repo, "add", "-f", ".mycache")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "tracked-and-ignored")
    _git(repo, "checkout", "-b", "hm/task")
    (repo / ".mycache").write_text("MODIFIED\n", encoding="utf-8")

    base = resolve_review_base(repo, base_branch="main")
    sha = create_freeze_commit(repo, "s", "confirm-1", base)
    listed = _git(repo, "ls-tree", "--name-only", sha).split()
    assert ".mycache" in listed, (
        "a tracked file matching .gitignore is absent from the frozen tree, so the pass would "
        f"read it as deleted: {listed}"
    )
    blob = _git(repo, "show", f"{sha}:.mycache")
    assert blob == "MODIFIED", "the frozen content is not the working-tree content"


def test_base_resolution_prefers_the_remote_tracking_ref(repo: Path) -> None:
    """A fresh clone has no local `main`; the chain fell through to `HEAD~1`.

    `HEAD~1` spans ONE commit instead of the branch divergence, so the confirmation pass
    reviews almost none of the work. Simulated by renaming the local branch away, which is
    what a clone that only has `origin/main` looks like to `merge-base`.
    """
    (repo / "b.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c2")
    first = _git(repo, "rev-parse", "HEAD~1")
    _git(repo, "update-ref", "refs/remotes/origin/main", first)
    _git(repo, "branch", "-m", "main", "feature")

    assert resolve_review_base(repo, base_branch="main") == first, (
        "base resolution ignored refs/remotes/origin/main and fell back to HEAD~1"
    )
