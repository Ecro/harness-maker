"""AC-007 — `delegation_fires`, the signal that would have surfaced four dead months.

Seven arms, because two of them decide by reflex if left unstated: the absent-ledger case
(every harness on day one) and the no-dispatch-tool case (every Cursor / Codex harness).
Getting either wrong reproduces a documented failure mode — a signal that is permanently
red on an action nobody can satisfy is the same "signal nobody reads" outcome as no signal
at all.

Each arm builds a real project tree, because the signal reads `harness.yaml` and the
ledger file from disk; a stubbed reader would certify the wiring rather than the behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import delegation_ledger
from harness_maker.readiness import Signal, _dim_guardrails

SIGNAL_ID = "delegation_fires"


@pytest.fixture(autouse=True)
def _unpin_session_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without this, the score comparison below degenerates to `0 == 0`.

    `sessionid_envfile_live` is emitted only when `CLAUDECODE` is set and is
    `hard_gate=True`, which floors the WHOLE dimension to 0 whenever `HM_SESSION_ID` is
    unset. Every pytest run launched from a Claude Code session is in exactly that state,
    so the assertion stopped discriminating on the developer's machine while still
    discriminating in CI — a weighted `delegation_fires` would have passed here.
    CLAUDE.md checkpoint 7: env isolation is part of the change, not an afterthought.
    """
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


def _project(tmp_path: Path, *, stages: list[str]) -> Path:
    root = tmp_path / "proj"
    (root / ".claude" / "observability").mkdir(parents=True)
    stage_lines = "\n".join(f"    - {s}" for s in stages) or "    []"
    # `worktree.enabled: true` is written EXPLICITLY. It used to be omitted, relying on
    # readiness defaulting an absent key to True — but the single reader
    # (`worktree.worktree_enabled`) defaults an absent key to False, and readiness now
    # agrees with it (PLAN-worktree-side-defaults). A fixture that depends on the two
    # disagreeing is exactly the drift that made `/hm:health` able to report a mode the
    # execution path does not take.
    (root / ".claude" / "harness.yaml").write_text(
        "delegation:\n  stages:\n"
        + (stage_lines if stages else "    []")
        + "\nworktree:\n  enabled: true\n",
        encoding="utf-8",
    )
    return root


def _rows(root: Path, rows: list[dict[str, object]]) -> None:
    path = delegation_ledger.ledger_path(root)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _brief_ok(n: int, start: int = 0) -> list[dict[str, object]]:
    return [
        {
            "ts": f"2026-07-20T10:{start + i:02d}:00Z",
            "stage": "wrapup",
            "slug": "s",
            "kind": "brief",
            "status": "ok",
            "reason": None,
        }
        for i in range(n)
    ]


def _dispatch(status: str, minute: int) -> dict[str, object]:
    return {
        "ts": f"2026-07-20T10:{minute:02d}:00Z",
        "stage": "wrapup",
        "slug": "s",
        "kind": "dispatch",
        "status": status,
        "reason": None,
    }


def _signal(root: Path) -> Signal:
    hits = [s for s in _dim_guardrails(root).signals if s.id == SIGNAL_ID]
    assert len(hits) == 1, f"{SIGNAL_ID} must be emitted exactly once, got {len(hits)}"
    return hits[0]


# ------------------------------------------------------------------------- arms


def test_arm_absent_ledger_fails_with_an_action(tmp_path: Path) -> None:
    """The state every harness ships in. Passing here means the signal can never fire on a
    harness that renders the block and then never runs it — the exact four-month case."""
    sig = _signal(_project(tmp_path, stages=["wrapup"]))
    assert sig.passed is False
    assert sig.action


def test_arm_briefs_but_no_dispatch_fails_with_an_action(tmp_path: Path) -> None:
    root = _project(tmp_path, stages=["wrapup"])
    _rows(root, _brief_ok(3))
    sig = _signal(root)
    assert sig.passed is False
    assert sig.action


def test_arm_degrading_briefs_fail_with_an_action(tmp_path: Path) -> None:
    """The regression the whole work unit exists to detect, if it ever returns.

    A brief that cannot be derived makes Step 0.5 skip the dispatch entirely, so an
    ok-brief-anchored window would sit green through it forever.
    """
    root = _project(tmp_path, stages=["wrapup"])
    _rows(
        root,
        _brief_ok(1)
        + [_dispatch("dispatched", 1)]
        + [
            {
                "ts": f"2026-07-20T10:{20 + i:02d}:00Z",
                "stage": "wrapup",
                "slug": "s",
                "kind": "brief",
                "status": "degraded",
                "reason": "HEAD is 'main', not a hm/<slug> task branch",
            }
            for i in range(delegation_ledger.WINDOW_BRIEFS + 2)
        ],
    )
    sig = _signal(root)
    assert sig.passed is False
    assert sig.action


def test_flag_off_gets_an_action_it_can_actually_perform(tmp_path: Path) -> None:
    """`derive_brief` resolves an `hm/<slug>` task branch; with the per-task workflow off
    there is never one, so every brief degrades STRUCTURALLY. Still failing — a silent pass
    would hide that delegation is dead — but the action must name a remedy the user can
    carry out, not restate a condition their config guarantees."""
    root = tmp_path / "off" / "proj"
    (root / ".claude" / "observability").mkdir(parents=True)
    (root / ".claude" / "harness.yaml").write_text(
        "delegation:\n  stages:\n    - wrapup\nworktree:\n  enabled: false\n",
        encoding="utf-8",
    )
    _rows(
        root,
        [
            {
                "ts": f"2026-07-20T10:{i:02d}:00Z",
                "stage": "wrapup",
                "slug": "s",
                "kind": "brief",
                "status": "degraded",
            }
            for i in range(3)
        ],
    )
    sig = _signal(root)
    assert sig.passed is False
    assert "worktree.enabled" in (sig.action or "")

    # And the same ledger under the default (flag-on) config gets the OTHER action.
    on = _project(tmp_path / "on", stages=["wrapup"])
    _rows(on, _rows_of(root))
    assert _signal(on).action != sig.action


def _rows_of(base: Path) -> list[dict[str, object]]:
    return delegation_ledger.read_rows(base)


def test_all_three_failing_arms_carry_different_actions(tmp_path: Path) -> None:
    """Identical text makes remedies indistinguishable, and the action string is the ONLY
    surface a user sees. The three failures point at three different places: nothing has
    run yet, the brief is not derivable, or the brief is fine and the dispatch is not
    issued. Sending someone to the wrong half of the seam is how a signal stops being read.
    """
    empty = _project(tmp_path / "a", stages=["wrapup"])
    briefed = _project(tmp_path / "b", stages=["wrapup"])
    _rows(briefed, _brief_ok(3))
    degrading = _project(tmp_path / "c", stages=["wrapup"])
    _rows(
        degrading,
        [
            {
                "ts": f"2026-07-20T10:{i:02d}:00Z",
                "stage": "wrapup",
                "slug": "s",
                "kind": "brief",
                "status": "degraded",
            }
            for i in range(3)
        ],
    )
    actions = [_signal(p).action for p in (empty, briefed, degrading)]
    assert all(a for a in actions), actions
    assert len(set(actions)) == 3, actions


def test_arm_all_unavailable_dispatch_passes(tmp_path: Path) -> None:
    """Cursor and Codex have no dispatch tool. A permanently-red action their user cannot
    satisfy is the failure mode, not the detection."""
    root = _project(tmp_path, stages=["wrapup"])
    _rows(root, _brief_ok(3) + [_dispatch("unavailable", 5)])
    sig = _signal(root)
    assert sig.passed is True


def test_arm_dispatch_that_stopped_goes_red_again(tmp_path: Path) -> None:
    """A lifetime-existence rule reports green here forever. This is the regression the
    signal exists to catch, and it is the arm three in-house review rounds missed."""
    root = _project(tmp_path, stages=["wrapup"])
    _rows(
        root,
        _brief_ok(1)
        + [_dispatch("dispatched", 1)]
        + _brief_ok(delegation_ledger.WINDOW_BRIEFS + 2, start=20),
    )
    sig = _signal(root)
    assert sig.passed is False
    assert sig.action


def test_arm_unconfigured_delegation_passes_with_no_action(tmp_path: Path) -> None:
    """The absent case, decided rather than fallen through. A harness that never opted in
    must not accrue an action item for a feature it does not use."""
    sig = _signal(_project(tmp_path, stages=[]))
    assert sig.passed is True
    assert sig.action is None


# --------------------------------------------------------- invariants of the dimension


def test_the_signal_is_weight_zero_and_non_gating(tmp_path: Path) -> None:
    """`_dim_guardrails`' weights sum to 100. A weighted addition re-scores every existing
    harness, so a user who changed nothing sees their score move — indistinguishable from
    a real regression."""
    root = _project(tmp_path, stages=["wrapup"])
    sig = _signal(root)
    assert sig.weight == 0
    assert sig.hard_gate is False


def test_the_signal_reads_the_base_ledger_when_handed_a_worktree(tmp_path: Path) -> None:
    """Reader and writer must agree on which root owns the ledger.

    `.claude/observability/` is gitignored churn that exists only at the base, while
    `harness.yaml` is tracked and therefore present in every worktree checkout. A reader
    keyed on the raw path would pair "wrapup is delegated" with an absent ledger and report
    `no-rows` on a harness that is dispatching correctly — the same base-vs-worktree
    asymmetry `delegation_ledger` exists to remove, re-introduced on the read side.
    """
    base = _project(tmp_path, stages=["wrapup"])
    _rows(base, _brief_ok(3) + [_dispatch("dispatched", 5)])

    worktree = base / ".worktrees" / "some-task"
    (worktree / ".claude").mkdir(parents=True)
    (worktree / ".claude" / "harness.yaml").write_text(
        (base / ".claude" / "harness.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert not (worktree / ".claude" / "observability").exists()

    assert _signal(worktree).passed is True


def test_a_very_long_reason_still_lands_as_one_readable_row(tmp_path: Path) -> None:
    """The atomic append helper RAISES above PIPE_BUF, and `append` must never raise.

    `reason` carries `verdict.reason`, the one caller-supplied field with no natural
    bound. Unbounded, a long reason would either tear the row or lose it — and a lost row
    moves the verdict toward the failing arm through unevaluability rather than evidence.
    """
    base = _project(tmp_path, stages=["wrapup"])
    delegation_ledger.append(
        base, stage="wrapup", slug="s", kind="brief", status="degraded", reason="x" * 20_000
    )
    rows = delegation_ledger.read_rows(base)
    assert len(rows) == 1
    assert rows[0]["status"] == "degraded"
    assert rows[0]["reason"].startswith("xxx")


def test_the_emitted_weight_total_is_unchanged_by_this_signal(tmp_path: Path) -> None:
    """Scoped to THIS signal's contribution, not to the dimension's budget.

    An earlier version of this test asserted the emitted weights sum to 100. They do not
    — they sum to 115 on this tree, and did before this change: 100 is ADR-006's nominal
    budget, not an invariant of whichever conditional signals a given project emits. That
    assertion was scoped wider than its subject (`[fail:test]
    assertion-scoped-wider-than-subject`), so it would have failed on a correct
    implementation and been "fixed" by loosening it.
    """
    root = _project(tmp_path, stages=["wrapup"])
    sigs = _dim_guardrails(root).signals
    # Without this line the filtered comprehension excludes nothing when the signal is
    # deleted outright, and both sides agree on a tree where the feature is absent.
    assert SIGNAL_ID in {s.id for s in sigs}
    assert sum(s.weight for s in sigs) == sum(s.weight for s in sigs if s.id != SIGNAL_ID)


def test_a_failing_signal_does_not_dock_the_dimension_score(tmp_path: Path) -> None:
    """The whole point of weight 0: visible without being punitive. Asserted against the
    dimension score, not against the weight, because that is what a user actually reads."""
    on = _project(tmp_path / "on", stages=["wrapup"])
    off = _project(tmp_path / "off", stages=[])
    assert _signal(on).passed is False
    scored = _dim_guardrails(on).score
    # A floored dimension makes both sides 0 and the equality vacuous — the exact state
    # the autouse fixture above exists to prevent, asserted rather than assumed.
    assert scored > 0
    assert scored == _dim_guardrails(off).score
