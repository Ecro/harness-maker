"""Phase 2 — CFR golden tests (SPEC AC-001/002/003, PLAN ADR-001)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.delivery_metrics import (
    CfrResult,
    InMemoryAdjudicationStore,
    compute_cfr,
)
from tests.unit._dm_git import ANCHOR, golden_empty_repo, golden_tagged_repo, golden_untagged_repo


@pytest.fixture
def tagged_repo(tmp_path: Path) -> Path:
    return golden_tagged_repo(tmp_path / "tagged").root


@pytest.fixture
def untagged_repo(tmp_path: Path) -> Path:
    return golden_untagged_repo(tmp_path / "untagged").root


@pytest.fixture
def empty_repo(tmp_path: Path) -> Path:
    return golden_empty_repo(tmp_path / "empty").root


def test_cfr_tagged_golden(tagged_repo: Path) -> None:
    """AC-001: 3 tagged releases in window, one failed via revert linkage.

    Machine predicate: compute_cfr(golden_tagged_repo, window_days=28)
    == CfrResult(failed=1, total=3, unit='tag'). failed==1 here is a SINGLE
    vote (the revert) — v0.2.1 is fix-only and excluded from the denominator,
    but lands 5d after v0.2.0, outside the 72h respin heuristic, so it casts
    no second vote. The ≤1-failure cap itself is exercised by
    test_cfr_failure_cap_on_double_signal_collision.
    """
    result = compute_cfr(tagged_repo, window_days=28, now=ANCHOR)
    assert result == CfrResult(failed=1, total=3, unit="tag")
    # Raw counts carried, not only a ratio (SPEC Outcomes).
    assert result.failed == 1
    assert result.total == 3


def test_cfr_task_land_fallback(untagged_repo: Path) -> None:
    """AC-002: no tags → first-parent lands are the denominator, unit='task-land'."""
    result = compute_cfr(untagged_repo, window_days=28, now=ANCHOR)
    assert result.release_unit == "task-land"
    assert result.total == 3  # the day-40 initial commit is outside the window
    assert result.failed == 0
    assert result.status == "ok"


def test_cfr_absent_case_not_applicable(empty_repo: Path) -> None:
    """AC-003: neither tags nor in-window lands → explicit not_applicable + reason."""
    result = compute_cfr(empty_repo, window_days=28, now=ANCHOR)
    assert result.status == "not_applicable"
    assert result.reason  # human-readable, non-empty
    assert result.total == 0
    assert result.failed == 0


def test_cfr_old_tags_do_not_fall_back_to_lands(tmp_path: Path) -> None:
    """A tag-disciplined repo whose tags are all older than the window stays
    unit='tag' with not_applicable — it must NOT flap to task-land counting
    (ADR-001: unit stability; absent-case is explicit)."""
    from tests.unit._dm_git import DMRepo

    r = DMRepo(tmp_path / "oldtags")
    r.commit("feat: ancient", days_ago=60)
    r.tag("v0.0.1", days_ago=60)
    r.commit("feat: recent-but-untagged", days_ago=5)
    result = compute_cfr(r.root, window_days=28, now=ANCHOR)
    assert result.status == "not_applicable"
    assert result.unit == "tag"


def test_cfr_ambiguous_fix_pending_then_adjudicated(tmp_path: Path) -> None:
    """A tail `fix:` commit landing shortly after the newest release is
    ambiguous: pending without a verdict; remediation verdict fails the
    release; routine verdict does not (ADR-006 candidate semantics)."""
    from tests.unit._dm_git import DMRepo

    r = DMRepo(tmp_path / "ambig")
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: alpha", days_ago=6)
    r.tag("v1.0.0", days_ago=6)
    fix_sha = r.commit("fix: subtle regression", days_ago=5.9)  # ~2.4h after release

    pending = compute_cfr(r.root, window_days=28, now=ANCHOR)
    assert pending.pending_adjudications == 1
    assert pending.failed == 0  # unadjudicated candidates never count as failures

    store = InMemoryAdjudicationStore()
    store.put(commit_sha=fix_sha, release_ref="v1.0.0", verdict="remediation", reason="test")
    failed = compute_cfr(r.root, window_days=28, now=ANCHOR, store=store)
    assert failed.pending_adjudications == 0
    assert failed.failed == 1

    store2 = InMemoryAdjudicationStore()
    store2.put(commit_sha=fix_sha, release_ref="v1.0.0", verdict="routine", reason="test")
    routine = compute_cfr(r.root, window_days=28, now=ANCHOR, store=store2)
    assert routine.pending_adjudications == 0
    assert routine.failed == 0


def test_cfr_quick_fix_only_respin_fails_predecessor(tmp_path: Path) -> None:
    """A fix-only release within the 72h respin window retro-fails its nearest
    non-fix-only predecessor deterministically (Swarmia rule; no adjudication)."""
    from tests.unit._dm_git import DMRepo

    r = DMRepo(tmp_path / "respin")
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: big", days_ago=6)
    r.tag("v1.0.0", days_ago=6)
    r.commit("fix: emergency", days_ago=5.9)
    r.tag("v1.0.1", days_ago=5.9)

    result = compute_cfr(r.root, window_days=28, now=ANCHOR)
    assert result.total == 1  # v1.0.1 is fix-only → excluded from denominator
    assert result.failed == 1  # …and retro-fails v1.0.0 (within 72h)
    assert result.pending_adjudications == 0


def test_cfr_failure_cap_on_double_signal_collision(tmp_path: Path) -> None:
    """AC-006 '≤1 failure per release': the SAME release accrues TWO independent
    deterministic signals — a direct revert of its commit AND a fix-only respin
    within 72h — yet failed stays 1, not 2. A cap-less implementation that
    appends per signal returns 2 and fails here (test-reviewer round 1)."""
    from tests.unit._dm_git import DMRepo

    r = DMRepo(tmp_path / "collision")
    r.commit("chore: initial", days_ago=40)
    bad = r.commit("feat: bad change", days_ago=6)
    r.tag("v1.0.0", days_ago=6)
    r.revert_commit(bad, "feat: bad change", days_ago=5.95)  # vote 1: revert
    r.commit("fix: emergency", days_ago=5.9)
    r.tag("v1.0.1", days_ago=5.9)  # vote 2: fix-only respin within 72h

    result = compute_cfr(r.root, window_days=28, now=ANCHOR)
    assert result.total == 1  # v1.0.1 fix-only → excluded
    assert result.failed == 1  # capped: two votes, one failure
    assert result.pending_adjudications == 0


def test_cfr_not_a_git_repo_raises(tmp_path: Path) -> None:
    """Outside a git repo the adapter raises the module error (CLI maps → exit 4)."""
    from harness_maker.delivery_metrics import DeliveryMetricsError

    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(DeliveryMetricsError):
        compute_cfr(plain, window_days=28, now=ANCHOR)


def test_candidate_subject_is_bounded() -> None:
    """REVIEW security P1: a candidate subject (git %s, attacker-influenced) is
    length-capped before it reaches the LLM adjudication transcript."""
    from harness_maker.delivery_metrics import _CANDIDATE_SUBJECT_MAX, AdjudicationCandidate

    huge = "fix: " + "A" * 10_000
    cand = AdjudicationCandidate(commit_sha="a" * 40, subject=huge, release_ref="v1", ts=0)
    assert len(cand.subject) <= _CANDIDATE_SUBJECT_MAX + 1  # +1 for the ellipsis
    short = AdjudicationCandidate(commit_sha="b" * 40, subject="fix: tidy", release_ref="v1", ts=0)
    assert short.subject == "fix: tidy"  # unbounded content passes through unchanged
