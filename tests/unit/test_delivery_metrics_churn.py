"""Phase 3 — churn cohort-blame survival (SPEC AC-004 + AC-005 churn half, ADR-004)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from harness_maker.delivery_metrics import compute_cfr, compute_churn
from harness_maker.models import DeliveryMetricsConfig
from tests.unit._dm_git import ANCHOR, DMRepo, golden_churn_repo, perf_repo


def test_churn_blame_survival_excludes_whitespace(tmp_path: Path) -> None:
    """AC-004: rewrites within maturation churn; whitespace-only and
    post-boundary rewrites do not. Machine predicate:
    compute_churn(golden_churn_repo, window_days=14).churned_loc == 4."""
    repo = golden_churn_repo(tmp_path / "churn").root
    result = compute_churn(repo, window_days=14, now=ANCHOR)
    assert result.status == "ok"
    assert result.churned_loc == 4
    assert result.added_loc == 10
    assert result.partial is False
    assert result.files_skipped == 0


def test_churn_absent_case_immature_cohort(tmp_path: Path) -> None:
    """ADR-004 absent-case: a repo whose commits are all younger than the
    maturation window yields explicit not_applicable — NEVER a 0% snapshot
    (CLAUDE.md 2026-06-08 absent-case guard; validator warning 2)."""
    r = DMRepo(tmp_path / "young")
    r.commit("chore: initial", days_ago=5)
    r.commit("feat: fresh", days_ago=2)
    result = compute_churn(r.root, window_days=14, now=ANCHOR)
    assert result.status == "not_applicable"
    assert result.reason
    assert result.churned_loc == 0
    assert result.added_loc == 0


def test_churn_window_outside_invariance_two_repo(tmp_path: Path) -> None:
    """AC-005 (churn half), metamorphic via two-repo equivalence: the same
    cohort script preceded by extra out-of-window commits yields an identical
    ChurnResult. SHAs differ between the repos, so equality can only come
    from the window math being genuinely prefix-independent."""

    def cohort_script(r: DMRepo) -> None:
        r.commit(
            "feat: cohort",
            days_ago=20,
            files={"core.py": "\n".join(f"c-{i}" for i in range(8)) + "\n"},
        )
        r.commit(
            "refactor: rewrite half",
            days_ago=9,
            files={
                "core.py": "\n".join([f"x-{i}" for i in range(4)] + [f"c-{i}" for i in range(4, 8)])
                + "\n"
            },
        )

    base = DMRepo(tmp_path / "base")
    base.commit("chore: init", days_ago=40, files={"init.txt": "seed\n"})
    cohort_script(base)

    extended = DMRepo(tmp_path / "extended")
    extended.commit("chore: init", days_ago=40, files={"init.txt": "seed\n"})
    extended.commit("feat: ancient one", days_ago=38, files={"old.py": "o1\no2\n"})
    extended.commit("fix: ancient two", days_ago=33, files={"old.py": "o1x\no2\n"})
    cohort_script(extended)

    assert compute_churn(base.root, window_days=14, now=ANCHOR) == compute_churn(
        extended.root, window_days=14, now=ANCHOR
    )


def test_churn_rename_is_not_churn(tmp_path: Path) -> None:
    """A pure rename inside the maturation window must not count the cohort
    commit's lines as churned (rename map + blame content detection)."""
    r = DMRepo(tmp_path / "rename")
    r.commit("chore: init", days_ago=40, files={"a.py": "seed\n"})
    r.commit(
        "feat: module",
        days_ago=20,
        files={"mod.py": "\n".join(f"m-{i}" for i in range(6)) + "\n"},
    )
    r.git("mv", "mod.py", "renamed.py")
    r.git("commit", "-m", "refactor: rename module", days_ago=9)
    result = compute_churn(r.root, window_days=14, now=ANCHOR)
    assert result.status == "ok"
    assert result.churned_loc == 0
    assert result.added_loc == 6


def test_churn_deleted_file_counts_fully(tmp_path: Path) -> None:
    """Deleting the cohort commit's file within maturation churns all its lines."""
    r = DMRepo(tmp_path / "delete")
    r.commit("chore: init", days_ago=40, files={"keep.py": "k\n"})
    r.commit(
        "feat: doomed",
        days_ago=20,
        files={"doomed.py": "\n".join(f"d-{i}" for i in range(6)) + "\n"},
    )
    r.git("rm", "-q", "doomed.py")
    r.git("commit", "-m", "chore: drop doomed", days_ago=9)
    result = compute_churn(r.root, window_days=14, now=ANCHOR)
    assert result.churned_loc == 6
    assert result.added_loc == 6


def test_churn_file_cap_is_deterministic_and_marks_partial(tmp_path: Path) -> None:
    """ADR-004 cap: files ordered by descending added-LOC; beyond-cap entries
    are counted in files_skipped and the snapshot is marked partial. The
    bigger file must be the one processed (deterministic ordering)."""
    r = DMRepo(tmp_path / "cap")
    r.commit("chore: init", days_ago=40, files={"seed.txt": "s\n"})
    r.commit(
        "feat: two files",
        days_ago=20,
        files={
            "big.py": "\n".join(f"b-{i}" for i in range(9)) + "\n",
            "small.py": "s-0\ns-1\n",
        },
    )
    # Rewrite ALL of big.py within maturation; small.py untouched.
    r.commit(
        "refactor: rewrite big",
        days_ago=9,
        files={"big.py": "\n".join(f"B-{i}" for i in range(9)) + "\n"},
    )
    cfg = DeliveryMetricsConfig(blame_file_cap=1)
    result = compute_churn(r.root, window_days=14, config=cfg, now=ANCHOR)
    assert result.partial is True
    assert result.files_skipped == 1
    # big.py (9 added) outranks small.py (2 added) → its churn is measured.
    assert result.churned_loc == 9
    assert result.added_loc == 9  # skipped entries stay out of the denominator


def test_churn_moved_block_across_files_not_churn(tmp_path: Path) -> None:
    """AC-004 `-C` semantics: a block moved from the cohort commit's file into
    ANOTHER file (modified in the same later commit) is still attributed to
    the cohort commit — moves are refactoring, not churn (test-reviewer R1)."""
    block = [f"moved-block-content-line-{i}-abcdefghijklmnopqrstuvwxyz" for i in range(4)]
    keep = ["keeper-line-0-zyxwvutsrqponmlkjihgfedcba", "keeper-line-1-zyxwvutsrqponmlkjihgfedcba"]
    r = DMRepo(tmp_path / "movedblock")
    r.commit("chore: init", days_ago=40, files={"util.py": "u-seed\n"})
    r.commit(
        "feat: lib block",
        days_ago=20,
        files={"lib.py": "\n".join(block + keep) + "\n"},
    )
    # One commit moves the 4-line block into util.py and removes it from lib.py.
    r.commit(
        "refactor: relocate block",
        days_ago=9,
        files={
            "lib.py": "\n".join(keep) + "\n",
            "util.py": "u-seed\n" + "\n".join(block) + "\n",
        },
    )
    result = compute_churn(r.root, window_days=14, now=ANCHOR)
    assert result.status == "ok"
    assert result.added_loc == 6
    assert result.churned_loc == 0


def test_churn_duplicate_line_counts_only_rewritten_instance(tmp_path: Path) -> None:
    """AC-004 duplicate-content lines: the cohort commit introduces two
    identical lines; only ONE is rewritten within maturation → churned_loc
    reflects exactly that occurrence — not both, not neither (test-reviewer R1)."""
    dup = "duplicated-boilerplate-line-abcdefghijklmnopqrstuvwxyz-0123456789"
    lines = ["uniq-0", dup, "uniq-1", dup, "uniq-2"]
    r = DMRepo(tmp_path / "dupline")
    r.commit("chore: init", days_ago=40, files={"seed.txt": "s\n"})
    r.commit("feat: dup lines", days_ago=20, files={"dup.py": "\n".join(lines) + "\n"})
    rewritten = list(lines)
    rewritten[1] = "rewritten-first-instance"
    r.commit("refactor: rework one dup", days_ago=9, files={"dup.py": "\n".join(rewritten) + "\n"})
    result = compute_churn(r.root, window_days=14, now=ANCHOR)
    assert result.added_loc == 5
    assert result.churned_loc == 1


@pytest.mark.slow
def test_perf_2000_commit_repo_under_30s(tmp_path: Path) -> None:
    """SPEC constraint (blocking, PLAN P3 exit): one full metrics run —
    compute_cfr + compute_churn — completes within 30s on a 2000-commit repo."""
    repo = perf_repo(tmp_path / "perf").root
    started = time.monotonic()
    cfr = compute_cfr(repo, window_days=28, now=ANCHOR)
    churn = compute_churn(repo, window_days=14, now=ANCHOR)
    elapsed = time.monotonic() - started
    assert cfr.status == "ok"
    assert churn.status == "ok"
    assert elapsed <= 30, f"metrics run took {elapsed:.1f}s (budget 30s)"
