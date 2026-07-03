"""Phase 2/3 — property ACs over the pure classification layer (SPEC AC-005/006).

Metamorphic oracles (spec-tetrad ADR-001): the relations hold for any correct
implementation regardless of algorithm, so they cannot be satisfied by reading
the implementation. Pure layer only — git subprocess fixtures live in the
golden tests; properties exercise window math and classification.

Generator invariants that make the expectations exact:
- releases are spaced ≥4 days apart, so nothing falls inside the 72h quick-
  respin heuristic (candidate/fix-only-retrofail semantics are golden-tested);
- "reverted" releases carry feat commits only, so reverted ∩ fix-only = ∅.
Under those constraints: total == |non-fixonly in-window| and failed == |reverted|.
"""

from __future__ import annotations

import os

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker.delivery_metrics import (
    ChurnEntry,
    CommitInfo,
    ReleaseInfo,
    classify_cfr,
    classify_churn,
)

# Hypothesis profile contract (spec-tetrad ADR-002): `ci` = reproducible gate,
# `dev` = broader local bug-finding. Select via HYPOTHESIS_PROFILE (default ci).
settings.register_profile("ci", derandomize=True, max_examples=60, deadline=None)
settings.register_profile("dev", max_examples=300, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_DAY = 86_400
_WINDOW_END = 2_000_000_000
# Window wide enough for 6 releases at 4-day spacing (24d) + margin.
_WINDOW_START = _WINDOW_END - 30 * _DAY

_Plan = tuple[list[ReleaseInfo], list[ReleaseInfo], list[CommitInfo], int, int]


def _mk_commit(idx: int, ts: int, *, fix: bool, body: str = "") -> CommitInfo:
    subject = f"fix: f{idx}" if fix else f"feat: n{idx}"
    return CommitInfo(sha=f"c{idx:08d}", subject=subject, ts=ts, parents=("p",), body=body)


@st.composite
def _release_plan(draw: st.DrawFn) -> _Plan:
    """(in_window, older, tail_reverts, expected_total, expected_failed)."""
    n_in = draw(st.integers(min_value=1, max_value=6))
    n_old = draw(st.integers(min_value=0, max_value=4))
    kinds = draw(
        st.lists(
            st.sampled_from(["normal", "fixonly", "reverted"]),
            min_size=n_in,
            max_size=n_in,
        )
    )
    idx = 0
    releases: list[ReleaseInfo] = []
    tail: list[CommitInfo] = []
    for pos, kind in enumerate(kinds):
        ts = _WINDOW_START + (pos + 1) * 4 * _DAY
        commits: list[CommitInfo] = []
        n_commits = draw(st.integers(min_value=1, max_value=3))
        for _ in range(n_commits):
            commits.append(_mk_commit(idx, ts - 3600, fix=(kind == "fixonly")))
            idx += 1
        releases.append(
            ReleaseInfo(
                ref=f"v0.{pos}.0", sha=commits[-1].sha, ts=ts, unit="tag", commits=tuple(commits)
            )
        )
        if kind == "reverted":
            target = commits[0]
            tail.append(
                CommitInfo(
                    sha=f"r{idx:08d}",
                    subject=f'Revert "{target.subject}"',
                    ts=_WINDOW_END - 3600,
                    parents=("p",),
                    body=f"This reverts commit {target.sha}.",
                )
            )
            idx += 1
    older: list[ReleaseInfo] = []
    for opos in range(n_old):
        ts = _WINDOW_START - (opos + 1) * 5 * _DAY
        c = _mk_commit(idx, ts - 3600, fix=draw(st.booleans()))
        idx += 1
        older.append(ReleaseInfo(ref=f"old{opos}", sha=c.sha, ts=ts, unit="tag", commits=(c,)))
    expected_total = sum(1 for k in kinds if k != "fixonly")
    expected_failed = sum(1 for k in kinds if k == "reverted")
    return releases, older, tail, expected_total, expected_failed


@given(_release_plan())
def test_property_window_outside_invariance(plan: _Plan) -> None:
    """AC-005: appending releases strictly older than the window start leaves
    the classified result unchanged (metamorphic relation over fixed window W)."""
    releases, older, tail, _, _ = plan
    base = classify_cfr(
        releases, tail, window_start=_WINDOW_START, window_end=_WINDOW_END, unit="tag"
    )
    with_older = classify_cfr(
        [*older, *releases], tail, window_start=_WINDOW_START, window_end=_WINDOW_END, unit="tag"
    )
    assert base == with_older


@given(_release_plan())
def test_property_cfr_bounds_and_fix_only_exclusion(plan: _Plan) -> None:
    """AC-006: 0 ≤ failed ≤ total; fix-only releases never in the denominator;
    each revert-failed release counts exactly once (≤1 failure per release)."""
    releases, _, tail, expected_total, expected_failed = plan
    result = classify_cfr(
        releases, tail, window_start=_WINDOW_START, window_end=_WINDOW_END, unit="tag"
    )
    assert 0 <= result.failed <= result.total
    assert result.total == expected_total
    assert result.failed == expected_failed


# ── churn half of AC-005 (pure layer, same shape as the CFR half) ────────────

_COHORT_END = _WINDOW_END - 14 * _DAY
_COHORT_START = _COHORT_END - 14 * _DAY

_paths = st.sampled_from(["src/a.py", "src/b.py", "lib/c.py"])  # deliberate overlap


@st.composite
def _churn_entries(draw: st.DrawFn, *, region: str) -> list[ChurnEntry]:
    """region: 'in' → ts inside the mature cohort; 'out' → strictly outside
    (older than cohort OR immature/newer than cohort end)."""
    n = draw(st.integers(min_value=0, max_value=6))
    entries: list[ChurnEntry] = []
    for i in range(n):
        if region == "in":
            ts = draw(st.integers(min_value=_COHORT_START, max_value=_COHORT_END))
        else:
            older = draw(st.booleans())
            ts = (
                draw(st.integers(min_value=_COHORT_START - 20 * _DAY, max_value=_COHORT_START - 1))
                if older
                else draw(st.integers(min_value=_COHORT_END + 1, max_value=_WINDOW_END))
            )
        added = draw(st.integers(min_value=0, max_value=50))
        surviving = draw(st.integers(min_value=0, max_value=60))  # may exceed added (-C copies)
        entries.append(
            ChurnEntry(
                sha=f"{region}{i:04d}",
                ts=ts,
                path=draw(_paths),
                added_w=added,
                surviving=surviving,
            )
        )
    return entries


@given(
    _churn_entries(region="in"), _churn_entries(region="out"), st.integers(min_value=1, max_value=4)
)
def test_property_churn_window_outside_invariance(
    inside: list[ChurnEntry], outside: list[ChurnEntry], cap: int
) -> None:
    """AC-005 (churn half): entries strictly outside the mature cohort —
    whether older than the cohort start or still immature — never change the
    result, for any count/age/file-overlap mix and any cap."""
    base = classify_churn(inside, cohort_start=_COHORT_START, cohort_end=_COHORT_END, file_cap=cap)
    mixed = classify_churn(
        [*outside, *inside], cohort_start=_COHORT_START, cohort_end=_COHORT_END, file_cap=cap
    )
    assert base == mixed


@given(
    _churn_entries(region="in"),
    st.randoms(use_true_random=False),
    st.integers(min_value=1, max_value=4),
)
def test_property_churn_input_order_invariance(
    inside: list[ChurnEntry], rng: object, cap: int
) -> None:
    """ADR-004 cap determinism: the deterministic ordering inside the pure
    layer makes the result independent of input order even when the cap
    truncates — two runs over the same repo can never disagree."""
    shuffled = list(inside)
    rng.shuffle(shuffled)  # type: ignore[attr-defined]
    a = classify_churn(inside, cohort_start=_COHORT_START, cohort_end=_COHORT_END, file_cap=cap)
    b = classify_churn(shuffled, cohort_start=_COHORT_START, cohort_end=_COHORT_END, file_cap=cap)
    assert a == b
