"""Phase 3 remainder — `refs/hm-freeze/v1/*` is reaped when its task is finished.

Nothing else deletes these. `/hm:review` writes `<slug>-base` once and a freeze commit per
confirmation pass, so without a sweep every review leaves refs behind permanently and each one
keeps a whole frozen working tree reachable in the object store.

The interesting assertions are the ones that DON'T reap: a live task's base must survive,
because a confirmation pass reads it rounds after it was written (SPEC AC-004). Reaping it
mid-review would make the pass silently re-resolve against a drifting HEAD — a wrong review,
which is far worse than a stale ref.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

import harness_maker.worktree as wt_mod
from harness_maker.freeze import store_review_base
from harness_maker.worktree import prune_stale


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()


@pytest.fixture(autouse=True)
def _no_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Age out the grace window.

    `FREEZE_REF_GRACE_S` presumes a young ref is live, because a review between round 1 and
    its confirmation pass owns no branch to prove liveness with. Every ref these tests create
    is seconds old, so without this the reaper correctly refuses to touch any of them and the
    tests would assert the guard rather than the sweep. `test_a_young_ref_is_never_reaped`
    below covers the guard itself, with the real value.
    """
    monkeypatch.setattr(wt_mod, "FREEZE_REF_GRACE_S", 0.0)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, timeout=30)
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "first")
    return tmp_path


def _make_base_ref(repo: Path, slug: str, *, age_s: float) -> None:
    """A `<slug>-base` ref WITH a stamp, aged as if written `age_s` ago.

    The stamp is what dates a base ref — its commit is a merge-base and says nothing about when
    the review claimed it. A stamp-less base ref is deliberately presumed live, so a test that
    wants one reaped has to supply the evidence of death rather than rely on its absence.
    """
    import os

    store_review_base(repo, slug, _git(repo, "rev-parse", "HEAD"))
    stamp = repo / ".claude" / "observability" / ".hm-freeze" / f"{slug}.stamp"
    old = time.time() - age_s
    os.utime(stamp, (old, old))


def _refs(repo: Path) -> set[str]:
    out = _git(repo, "for-each-ref", "--format=%(refname)", "refs/hm-freeze/v1/")
    return {line.strip() for line in out.splitlines() if line.strip()}


def _make_freeze_ref(repo: Path, name: str) -> None:
    """Point a freeze ref at HEAD.

    **This helper is why round 2 caught a defect round 1 shipped.** HEAD here is a commit the
    fixture made seconds ago, so every ref it creates looks young — and the first grace-window
    implementation read the COMMIT's date. `<slug>-base` in production points at a merge-base
    that is days or months old, so it was born past the window while this helper made the guard
    look correct. A test can only see what its fixture can be.
    """
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", f"refs/hm-freeze/v1/{name}", head)


def test_a_finished_task_s_refs_are_reaped(repo: Path) -> None:
    """No `hm/<slug>` branch and no worktree → the task is landed and its refs are dead.

    An unrelated `hm/other` exists so the live set is non-empty: an EMPTY set now returns
    early (it proves nothing is dead, not that everything is), which is a separate guard
    covered by `test_an_empty_live_set_reaps_nothing`.
    """
    _git(repo, "branch", "hm/other")
    _make_base_ref(repo, "gone", age_s=48 * 60 * 60)
    _make_freeze_ref(repo, "gone-confirm-1")
    assert len(_refs(repo)) == 2

    report = prune_stale(repo)
    assert sorted(report.removed_freeze_refs) == [
        "refs/hm-freeze/v1/gone-base",
        "refs/hm-freeze/v1/gone-confirm-1",
    ]
    assert _refs(repo) == set()


def test_a_live_task_s_base_survives(repo: Path) -> None:
    """The assertion that matters. AC-004's store is read rounds after it is written.

    Reaping it while `hm/<slug>` still exists makes the confirmation pass re-resolve
    `review_base` against a HEAD that has moved — the exact drift the store exists to prevent,
    and it would be silent.
    """
    _git(repo, "branch", "hm/alive")
    _make_freeze_ref(repo, "alive-base")
    _make_freeze_ref(repo, "alive-confirm-1")

    report = prune_stale(repo)
    assert report.removed_freeze_refs == []
    assert len(_refs(repo)) == 2


def test_a_slug_with_hyphens_is_not_mis_attributed(repo: Path) -> None:
    """`a-b-base` must not be read as slug `a`.

    Splitting on the last hyphen group would attribute it to a different, possibly finished
    slug and reap a live task's base. Matching against the live set instead makes the
    hyphenated case fall out for free.
    """
    _git(repo, "branch", "hm/multi-word-slug")
    _make_base_ref(repo, "multi-word-slug", age_s=48 * 60 * 60)
    _make_base_ref(repo, "multi", age_s=48 * 60 * 60)  # a DIFFERENT, finished slug

    report = prune_stale(repo)
    assert report.removed_freeze_refs == ["refs/hm-freeze/v1/multi-base"]
    assert "refs/hm-freeze/v1/multi-word-slug-base" in _refs(repo)


def test_a_live_worktree_without_a_branch_still_protects_its_refs(repo: Path) -> None:
    """A task worktree directory is enough evidence that the task is in flight."""
    (repo / ".worktrees" / "wt-only").mkdir(parents=True)
    _make_freeze_ref(repo, "wt-only-base")

    report = prune_stale(repo)
    assert report.removed_freeze_refs == []


def test_dry_run_reports_without_deleting(repo: Path) -> None:
    _git(repo, "branch", "hm/other")  # non-empty live set — see the empty-set guard test
    _make_base_ref(repo, "gone", age_s=48 * 60 * 60)
    report = prune_stale(repo, dry_run=True)
    assert report.removed_freeze_refs == ["refs/hm-freeze/v1/gone-base"]
    assert len(_refs(repo)) == 1, "dry_run deleted a ref"


def test_a_young_ref_is_never_reaped(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard two reviewers found independently, with the shipped grace value.

    `live_slugs` is empty under `worktree.enabled: false` (the Side default) and under
    `/hm:loop` (worktrees are `execute-<uuid>`, never a task slug), so every freeze ref looked
    dead — including the `<slug>-base` of a review still on its way to the confirmation pass.
    `prune_stale` runs from `worktree create`, `task-land` AND `drain`, and `/hm:health` calls
    `drain` unconditionally, so a peer session could delete a live review's base.
    """
    monkeypatch.setattr(wt_mod, "FREEZE_REF_GRACE_S", 6 * 60 * 60)
    _git(
        repo, "branch", "hm/other"
    )  # a non-empty live set, so the empty-set guard is not what runs
    _make_freeze_ref(repo, "inflight-base")

    report = prune_stale(repo)
    assert report.removed_freeze_refs == [], "a ref minutes old was reaped as finished"


def test_an_empty_live_set_reaps_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No `hm/*` branch and no `.worktrees/` proves nothing is dead — it proves nothing at all.

    Even with the grace window disabled, an empty live set must not authorise a sweep.
    """
    monkeypatch.setattr(wt_mod, "FREEZE_REF_GRACE_S", 0.0)
    _make_freeze_ref(repo, "whatever-base")
    assert prune_stale(repo).removed_freeze_refs == []


def test_the_base_ref_is_protected_even_though_its_commit_is_old(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round-2 P1, found by BOTH reviewers independently.

    `store_review_base` points `<slug>-base` at a merge-base — a pre-existing commit, typically
    days or months old. A grace window keyed on `git log --format=%ct <ref>` therefore reads the
    age of the branch point, not of the review, and the ref the confirmation pass depends on is
    unprotected from the moment it is written. The `-confirm-*` refs point at freshly built
    freeze commits, so they WERE protected — which is exactly why a fixture built on fresh refs
    showed the guard working.

    Liveness now comes from a written stamp instead.
    """
    monkeypatch.setattr(wt_mod, "FREEZE_REF_GRACE_S", 6 * 60 * 60)
    _git(repo, "branch", "hm/other")  # non-empty live set, so the empty-set guard is not what runs

    # An OLD commit, as a merge-base is. Backdated well past the grace window.
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e.com",
        "commit",
        "--allow-empty",
        "--date=2020-01-01T00:00:00",
        "-m",
        "ancient",
    )
    old = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/hm-freeze/v1/live-base", old)
    store_review_base(repo, "live", old)  # writes the stamp, which is what dates the ref

    assert prune_stale(repo).removed_freeze_refs == [], (
        "the review_base ref was reaped mid-review because its COMMIT is old; the stamp, not "
        "the commit date, is what records when the review claimed it"
    )


def test_a_base_ref_with_no_stamp_is_presumed_live(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ref written by an older version has no stamp. Unknown age is not evidence of death."""
    monkeypatch.setattr(wt_mod, "FREEZE_REF_GRACE_S", 6 * 60 * 60)
    _git(repo, "branch", "hm/other")
    _make_freeze_ref(repo, "legacy-base")
    assert prune_stale(repo).removed_freeze_refs == []


def test_freeze_reap_releases_refs_without_needing_a_live_slug(repo: Path) -> None:
    """The hole the round-1 repair created, closed by an owner that does not consult liveness.

    `prune_stale`'s sweep returns early when nothing looks live — which under
    `worktree.enabled: false` is ALWAYS — so every review permanently pinned a commit whose
    tree holds every untracked non-ignored file present at pass time.
    """
    from harness_maker.freeze import main as freeze_main
    from harness_maker.freeze import store_review_base as _store

    _store(repo, "done", _git(repo, "rev-parse", "HEAD"))
    assert "refs/hm-freeze/v1/done-base" in _refs(repo)

    assert freeze_main(["reap", "--slug", "done", "--root", str(repo)]) == 0
    assert _refs(repo) == set()
