"""SPEC-withdrawal-criterion-window — `hm world gap`'s withdrawal block is window-scoped.

The criterion this module now guards replaces a cumulative one: `due` used to require
`objectives_observed == 0`, so a single objective closed with `observed:` anywhere in history
pinned it to false forever. It now asks how many `hm:wrapup` start events have landed since the
layer last did anything.

**Oracles are golden, and the expected values are fixed by the fixture before the reader runs.**
Commits carry a pinned `GIT_COMMITTER_DATE` with a non-UTC offset (a reader that forgets to
normalise fails); the stage-spans ledger is hand-written with a known number of `start` events
either side of the cutoff plus lines that must NOT count. AC-006's rows load from
`specs/SPEC-withdrawal-criterion-window.machine.yaml` — that table is the single source.

**Discrimination: the control is a rename, not HEAD.** IRR-001 renames the payload keys, so
every test here raises `KeyError` against the shipped implementation whether or not it binds
the window dimension — a red sweep against HEAD carries no information. `_renamed_only_control`
below is the retired cumulative logic emitting the six new key names, and
`test_the_control_is_the_retired_rule` proves it really is the old behaviour.

**Only some of these tests can discriminate, and that is by design, not by omission.** The SPEC
deliberately preserves several behaviours — AC-004 and AC-006 say so in their own
`oracle_evidence`, and S3 says the never-signalled case behaves "as it did under the retired
rule" — so requiring those tests to fail against the control would be requiring the SPEC to be
violated. The tests carrying `@pytest.mark.discriminates` — eight functions, eleven items once
`test_ac_003` is parametrised — are the ones that read a value the window change actually
moves; every other test names its reason in `_NOT_IN_THE_SCREEN`, and
`test_every_subject_touching_test_declares_whether_it_discriminates` makes the two sets
exhaustive. The screen is a command, not a test:

    HM_WITHDRAWAL_CONTROL=1 uv run pytest tests/unit/test_world_withdrawal.py -m discriminates

Every selected test must FAIL.

Git is isolated from the host (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`) so a
signing or hook config on the machine cannot change the fixture.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import intent as intent_mod
from harness_maker import world
from harness_maker.second_opinion_invoke import resolve_base_root
from harness_maker.spec_machine import GoldenRow, load_golden_table
from tests.unit import world_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=8, deadline=None)
settings.register_profile("dev", max_examples=40, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-withdrawal-criterion-window.machine.yaml"
_KEYS = {
    "filled_at",
    "last_signal_at",
    "quiet_wrapups",
    "revisit_candidates_now",
    "due",
    "reason",
}

SKELETON_DATE = "2026-09-01T10:00:00+09:00"
FILL_DATE = "2026-09-10T12:00:00+09:00"
FILL_ISO = "2026-09-10T03:00:00Z"
#: Far enough past every fixture instant that no test's `now` accidentally clamps.
LATE_NOW = datetime(2027, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(root: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    if date is not None:
        env["GIT_COMMITTER_DATE"] = date
        env["GIT_AUTHOR_DATE"] = date
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    ).stdout.strip()


def _skeleton() -> dict[str, Any]:
    return fx.intent_doc(mission="")


def _commit(root: Path, date: str, msg: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", msg, date=date)


def _filled_repo(
    root: Path,
    *,
    objectives: list[dict[str, Any]] | None = None,
    values: list[dict[str, Any]] | None = None,
) -> Path:
    """Skeleton committed at SKELETON_DATE, then filled and committed at FILL_DATE."""
    fx.build_root(root, intent=_skeleton())
    _commit(root, SKELETON_DATE, "skeleton")
    fx.build_root(
        root, intent=fx.intent_doc(fx.outcome()), objectives=objectives, values=values, git=False
    )
    _commit(root, FILL_DATE, "fill")
    return root


def _span(stage: str, event: str, ts: str) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "event": event,
            "stage": stage,
            "cwd": "/x",
            "base_root": "/x",
            "git_branch": None,
            "task_slug": None,
            "ts": ts,
            "session_id": None,
        }
    )


def _spans(root: Path, lines: list[str]) -> None:
    path = root / ".claude" / "observability" / "stage-spans.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _wrapups(root: Path, instants: list[datetime]) -> None:
    _spans(root, [_span("hm:wrapup", "start", i.strftime("%Y-%m-%dT%H:%M:%SZ")) for i in instants])


def _gap(root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "world", "gap", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return fx.stdout_json(proc)


def _measurement(observed_at: str) -> dict[str, Any]:
    o = fx.outcome()
    return {
        "outcome_id": o["id"],
        "value": 5,
        "observed_at": observed_at,
        "evidence": "fixture",
        "definition_hash": fx.definition_hash(o),
    }


#: Set by the Phase 1 discrimination screen, never by CI. See `_renamed_only_control`.
CONTROL_ENV = "HM_WITHDRAWAL_CONTROL"


def _report(root: Path, *, now: datetime = LATE_NOW) -> dict[str, Any]:
    """The subject, read straight off disk — no boundary is mocked.

    Under `HM_WITHDRAWAL_CONTROL=1` this returns the renamed-only control instead, so the
    screen is one pytest invocation rather than a hand-maintained claim in a PLAN.
    """
    loaded = world.load_world(root)
    status = world.status_report(root)
    if os.environ.get(CONTROL_ENV) == "1":
        return _renamed_only_control(loaded, root, status["fired_revisits"], now=now)
    return world.withdrawal_report(loaded, root, status["fired_revisits"], now=now)


def _rewrite_values(root: Path, instants: list[datetime]) -> None:
    fx.dump(
        root / ".claude" / "world" / "outcomes.yaml",
        {
            "schema_version": fx.KNOWN_MAJOR,
            "values": [_measurement(i.strftime("%Y-%m-%dT%H:%M:%SZ")) for i in instants],
        },
    )


# ── the renamed-only control ─────────────────────────────────────────────────


def _renamed_only_control(
    loaded: world.World, root: Path, fired: list[str], *, now: datetime = LATE_NOW
) -> dict[str, Any]:
    """The RETIRED cumulative rule, emitting the six NEW key names.

    This is the screen the Phase A.4 false-RED check runs against. Screening against HEAD is
    informationless here: IRR-001 renames the keys, so a test that merely reads `quiet_wrapups`
    raises `KeyError` against HEAD whether or not it binds the window dimension.
    """
    observed = sum(1 for rec in loaded.objectives.values() if rec.get("observed") is not None)
    candidates = len(fired)
    filled: str | None = None
    wrapups: int | None = None
    if intent_mod.is_not_filled_in(loaded.intent):
        reason: str | None = "not_filled_in"
    else:
        filled, reason = world._filled_at(root)
        if reason is None and filled is not None:
            wrapups, reason = world._count_wrapups(resolve_base_root(root), filled)
    due = (
        wrapups is not None
        and wrapups >= world.WITHDRAWAL_WRAPUPS
        and observed == 0
        and candidates == 0
    )
    return {
        "filled_at": filled,
        "last_signal_at": None,
        "quiet_wrapups": wrapups,
        "revisit_candidates_now": candidates,
        "due": due,
        "reason": reason or "ok",
    }


def _control_report(root: Path, *, now: datetime = LATE_NOW) -> dict[str, Any]:
    loaded = world.load_world(root)
    status = world.status_report(root)
    return _renamed_only_control(loaded, root, status["fired_revisits"], now=now)


def test_the_control_is_the_retired_rule(tmp_path: Path) -> None:
    """Positive control on the control: one `observed` objective pins its `due` to false.

    Without this, a control that silently drifted toward the new behaviour would make the
    discrimination screen below vacuous in the other direction.
    """
    closed = fx.objective(
        "OBJ-DONE", state="closed", observed="missed", note="n", closed_at="2026-09-11T00:00:00Z"
    )
    root = _filled_repo(tmp_path, objectives=[closed])
    _wrapups(root, [datetime(2026, 9, 11 + d, tzinfo=UTC) for d in range(10)])
    control = _control_report(root)
    assert control["quiet_wrapups"] == 10
    assert control["due"] is False, "the retired rule must stay vetoed by an observed objective"


# ── AC-008: the key set ──────────────────────────────────────────────────────


def test_ac_008_the_withdrawal_block_key_set_is_exactly_six(tmp_path: Path) -> None:
    root = _filled_repo(tmp_path, values=[_measurement("2026-09-11T00:00:00Z")])
    _wrapups(root, [datetime(2026, 9, 12, tzinfo=UTC)])
    assert set(_report(root)) == _KEYS
    out = _gap(root)
    assert set(out["withdrawal"]) == _KEYS, "the CLI payload must carry the same key set"
    status = fx.stdout_json(fx.run_cli(["status", "--json"], cwd=root))
    assert "withdrawal" not in status, "status --json stays frozen"


# ── AC-003: last_signal_at is the max over the four sources ──────────────────


#: The four things that count as the layer having done something. Each must be able to WIN:
#: a fixture with one fixed winner leaves the other three unbound, and a reader that dropped
#: them entirely would still pass. Measured, not hypothesised — the 2026-09-20 targeted
#: mutation run of this change had `created_at source dropped` and `closed_at source dropped`
#: SURVIVE against the single-winner fixture this replaced.
_SIGNAL_SOURCES = ("observed_at", "created_at", "approved_at", "closed_at")
_LATEST = "2026-09-19T08:00:00Z"


@pytest.mark.discriminates
@pytest.mark.parametrize("winner", _SIGNAL_SOURCES, ids=_SIGNAL_SOURCES)
def test_ac_003_last_signal_at_is_the_max_over_the_four_sources(
    tmp_path: Path, winner: str
) -> None:
    """Every source, in turn, carries the maximum; the other three stay behind it.

    The expected value is fixed by the fixture before the reader runs. Two unparseable values
    ride along in every case — a `created_at` and an `observed_at` — and must be skipped rather
    than crash the report or win by being un-comparable.
    """
    at = {
        "observed_at": "2026-09-11T00:00:00Z",
        "created_at": "2026-09-12T00:00:00Z",
        "approved_at": "2026-09-13T00:00:00Z",
        "closed_at": "2026-09-14T00:00:00Z",
    }
    at[winner] = _LATEST

    approved = fx.objective("OBJ-APPROVED")
    approved["created_at"] = at["created_at"]
    approved["approval"] = {
        "content_hash": "0" * 64,
        "approved_by": "Ecro",
        "approved_at": at["approved_at"],
        "approved_target": 10,
    }
    closed = fx.objective(
        "OBJ-CLOSED", state="closed", observed="met", note="n", closed_at=at["closed_at"]
    )
    closed["created_at"] = "2026-09-10T00:00:00Z"  # never the winner
    junk = fx.objective("OBJ-JUNK")
    junk["created_at"] = "not-a-timestamp"
    root = _filled_repo(
        tmp_path,
        objectives=[approved, closed, junk],
        values=[_measurement(at["observed_at"]), _measurement("nonsense")],
    )
    _wrapups(root, [datetime(2026, 9, 20, tzinfo=UTC)])

    assert _report(root)["last_signal_at"] == _LATEST


# ── AC-001: window locality, and the sensitivity that makes it mean something ─

_INSTANTS = st.datetimes(min_value=datetime(2026, 9, 11), max_value=datetime(2026, 10, 31)).map(
    lambda d: d.replace(tzinfo=UTC, microsecond=0)
)


@given(
    signals=st.lists(_INSTANTS, min_size=1, max_size=4, unique=True), older_by=st.integers(1, 120)
)
def test_ac_001_a_signal_older_than_the_cutoff_changes_nothing(
    tmp_path_factory: pytest.TempPathFactory, signals: list[datetime], older_by: int
) -> None:
    root = _filled_repo(tmp_path_factory.mktemp("loc"))
    _wrapups(root, [datetime(2026, 11, d, tzinfo=UTC) for d in range(1, 8)])

    _rewrite_values(root, signals)
    before = _report(root)
    _rewrite_values(root, [*signals, min(signals) - timedelta(hours=older_by)])
    after = _report(root)

    assert (after["last_signal_at"], after["quiet_wrapups"], after["due"]) == (
        before["last_signal_at"],
        before["quiet_wrapups"],
        before["due"],
    )


@pytest.mark.discriminates
def test_ac_001_moving_the_newest_signal_across_the_wrapups_changes_the_count(
    tmp_path: Path,
) -> None:
    """The sensitivity half. Locality alone is satisfied by a constant, and by the retired rule.

    Ten wrapups sit on 2026-09-21..30. A signal before them leaves all ten counted and `due`
    true; moving that same signal past them counts none and `due` goes false.
    """
    root = _filled_repo(tmp_path)
    _wrapups(root, [datetime(2026, 9, 21 + d, tzinfo=UTC) for d in range(10)])

    _rewrite_values(root, [datetime(2026, 9, 20, tzinfo=UTC)])
    early = _report(root)
    _rewrite_values(root, [datetime(2026, 10, 5, tzinfo=UTC)])
    late = _report(root)

    assert (early["quiet_wrapups"], early["due"]) == (10, True)
    assert (late["quiet_wrapups"], late["due"]) == (0, False)


# ── AC-002: due is reachable from every filled, revisit-free state ───────────


@pytest.mark.discriminates
@given(signals=st.lists(_INSTANTS, min_size=1, max_size=3, unique=True))
@settings(max_examples=6)
def test_ac_002_due_is_reachable_from_every_filled_revisit_free_state(
    tmp_path_factory: pytest.TempPathFactory, signals: list[datetime]
) -> None:
    """Pinned to include an `observed: missed` objective — the state that killed the old rule.

    The retired criterion is absorbing: once any objective carries `observed`, no extension of
    the history can make `due` true again. This generator always puts the repository in exactly
    that state, so a regression to the cumulative rule cannot pass.
    """
    missed = fx.objective(
        "OBJ-MISS", state="closed", observed="missed", note="n", closed_at="2026-09-11T00:00:00Z"
    )
    root = _filled_repo(tmp_path_factory.mktemp("reach"), objectives=[missed])
    _rewrite_values(root, signals)
    _wrapups(root, [datetime(2026, 9, 12, tzinfo=UTC)])

    cutoff = datetime.fromisoformat(_report(root)["last_signal_at"].replace("Z", "+00:00"))
    _wrapups(root, [cutoff + timedelta(days=d + 1) for d in range(world.WITHDRAWAL_WRAPUPS)])

    after = _report(root, now=cutoff + timedelta(days=400))
    assert after["revisit_candidates_now"] == 0
    assert after["quiet_wrapups"] == world.WITHDRAWAL_WRAPUPS
    assert after["due"] is True


# ── The never-signalled fallback (ADR-001's stated reason for this design) ───


def test_a_layer_that_never_signalled_counts_from_filled_at(tmp_path: Path) -> None:
    """No signal at all: the cutoff is `filled_at`, and `due` still arrives after ten wrapups.

    ADR-001 rejects the trailing-set alternative *because* this case needs no special rule. An
    implementation that returned `None`/`no_git` whenever `last_signal_at` is None would pass
    AC-003, AC-004, AC-006 and AC-008 and break only here.
    """
    root = _filled_repo(tmp_path)
    _wrapups(root, [datetime(2026, 9, 11 + d, tzinfo=UTC) for d in range(10)])

    got = _report(root)
    assert got["last_signal_at"] is None
    assert got["filled_at"] == FILL_ISO
    assert (got["quiet_wrapups"], got["reason"], got["due"]) == (10, "ok", True)


# ── ADR-006 (corrected): a future-dated signal is not a signal ───────────────


@pytest.mark.discriminates
def test_a_future_dated_signal_never_becomes_the_cutoff(tmp_path: Path) -> None:
    """A real signal and a mistyped one coexist; the mistyped one must lose.

    This fixture is the whole point. A repository whose ONLY signal is future-dated cannot
    discriminate anything — dropping it falls back to `filled_at`, which is exactly what the
    retired rule counted from, so every implementation agrees. Pairing a valid 2026 signal with
    a bogus 2030 one separates them: the correct reader picks 2026-09-15 and counts the ten
    wrapups after it; a reader that lets the future value win counts from 2030 (or, under the
    clamp this replaced, from `now`) and reports zero.

    The chronology is REACHABLE. An earlier version of this test froze `now` and placed the
    wrapups AFTER it — a ledger state that cannot occur, since events are recorded as they
    happen. It passed against the broken clamp for that reason.
    """
    root = _filled_repo(tmp_path)
    now = datetime(2026, 9, 26, tzinfo=UTC)
    _rewrite_values(root, [datetime(2026, 9, 15, tzinfo=UTC), datetime(2030, 1, 1, tzinfo=UTC)])
    _wrapups(root, [datetime(2026, 9, 16 + d, tzinfo=UTC) for d in range(10)])

    got = _report(root, now=now)
    assert got["last_signal_at"] == "2026-09-15T00:00:00Z", "the future value must not win"
    assert got["quiet_wrapups"] == world.WITHDRAWAL_WRAPUPS
    assert got["due"] is True, (
        "a mistyped future date must not suppress the criterion; the clamp this replaced left "
        "it suppressed until that date arrived, because the cutoff advanced with `now`"
    )


@pytest.mark.discriminates
def test_a_past_dated_signal_is_the_cutoff(tmp_path: Path) -> None:
    """Control on the one above: an ordinary signal is used, and it excludes what precedes it."""
    root = _filled_repo(tmp_path)
    now = datetime(2026, 10, 1, tzinfo=UTC)
    _rewrite_values(root, [datetime(2026, 9, 25, tzinfo=UTC)])
    _wrapups(root, [datetime(2026, 9, 20, tzinfo=UTC), datetime(2026, 9, 28, tzinfo=UTC)])

    assert _report(root, now=now)["quiet_wrapups"] == 1


@pytest.mark.discriminates
def test_a_whitespace_padded_signal_does_not_crash_the_report(tmp_path: Path) -> None:
    """`_aware_instant` strips before parsing; `_count_wrapups`'s parse does not, and does not
    catch `ValueError`. Returning the padded original therefore turned a YAML whitespace typo —
    a trailing newline from a block scalar, say — into an uncaught crash of every
    `hm world gap`, in the module whose own contract says a history typo must not break it.

    The padding is invisible in a failure message, so the assertion names the stripped value.
    """
    o = fx.outcome()
    padded = {
        "outcome_id": o["id"],
        "value": 5,
        "observed_at": " 2026-09-15T00:00:00Z\n",
        "evidence": "fixture",
        "definition_hash": fx.definition_hash(o),
    }
    root = _filled_repo(tmp_path, values=[padded])
    _wrapups(root, [datetime(2026, 9, 16 + d, tzinfo=UTC) for d in range(3)])

    got = _report(root)
    assert got["last_signal_at"] == "2026-09-15T00:00:00Z"
    assert got["quiet_wrapups"] == 3
    assert got["reason"] == "ok"


# ── Reason precedence: not_filled_in outranks a recorded signal ──────────────


def test_not_filled_in_outranks_a_recorded_signal(tmp_path: Path) -> None:
    """A never-installed layer carrying a stray objective must not be told to retire itself.

    `world.objectives` loads independently of `intent.outcomes`, so this state is reachable;
    hoisting the signal computation above the guard would report `ok` and, after ten wrapups,
    `due: true` for a layer that was never filled in.
    """
    stray = fx.objective("OBJ-STRAY")
    stray["created_at"] = "2026-09-15T00:00:00Z"
    fx.build_root(tmp_path, intent=_skeleton(), objectives=[stray])
    _commit(tmp_path, SKELETON_DATE, "skeleton")
    _wrapups(tmp_path, [datetime(2026, 9, 16 + d, tzinfo=UTC) for d in range(10)])

    got = _report(tmp_path)
    assert got["reason"] == "not_filled_in"
    assert got["quiet_wrapups"] is None
    assert got["last_signal_at"] is None
    assert got["due"] is False


@pytest.mark.discriminates
def test_filled_at_is_not_resolved_when_a_signal_exists(tmp_path: Path) -> None:
    """The git work behind `filled_at` is paid only on the branch that consumes it.

    The repository here is ORDINARY — not shallow, fully committed — so `_filled_at` would
    succeed and return `FILL_ISO` if it were called. It is not, because a signal supplied the
    cutoff, and the reported `filled_at` is therefore null.

    That null is distinguishable from the failure null: `last_signal_at` is non-null here, which
    is the payload's own statement that the date was never asked for. The reason-table tests
    cover the other direction, where no signal exists and the git answer is what `reason` names.
    """
    root = _filled_repo(tmp_path, values=[_measurement("2026-09-15T00:00:00Z")])
    _wrapups(root, [datetime(2026, 9, 16 + d, tzinfo=UTC) for d in range(2)])

    got = _report(root)
    assert got["last_signal_at"] == "2026-09-15T00:00:00Z"
    assert got["filled_at"] is None, (
        "an ordinary repository can date its own fill; a non-null value here means the git "
        "chain ran anyway, which is the cost ADR-004 was reopened to stop paying"
    )
    assert (got["quiet_wrapups"], got["reason"]) == (2, "ok")


# ── AC-006: the reason table, and AC-004's absent-case invariant ─────────────


def _b_not_filled(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp, intent=_skeleton())
    _commit(tmp, SKELETON_DATE, "skeleton")
    return tmp, None


def _b_shallow_no_signal(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    src = _filled_repo(tmp / "src")
    _git(src, "commit", "-q", "--allow-empty", "-m", "later", date="2026-09-12T00:00:00Z")
    dst = tmp / "dst"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{src}", str(dst)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    _wrapups(dst, [datetime(2026, 9, 13, tzinfo=UTC)])
    return dst, None


def _b_fill_uncommitted(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp, intent=_skeleton())
    _commit(tmp, SKELETON_DATE, "skeleton")
    fx.dump(tmp / ".claude" / "intent.yaml", fx.intent_doc(fx.outcome()))
    _wrapups(tmp, [datetime(2026, 9, 11, tzinfo=UTC)])
    return tmp, None


def _b_signal_no_spans(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    return _filled_repo(tmp, values=[_measurement("2026-09-11T00:00:00Z")]), None


def _b_signal_no_wrapup(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    root = _filled_repo(tmp, values=[_measurement("2026-09-11T00:00:00Z")])
    _spans(
        root,
        [
            _span("hm:plan", "start", "2026-09-12T00:00:00Z"),
            _span("hm:plan", "end", "2026-09-12T01:00:00Z"),
        ],
    )
    return root, None


def _b_signal_ok(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    root = _filled_repo(tmp, values=[_measurement("2026-09-11T00:00:00Z")])
    _spans(
        root,
        [
            _span("hm:wrapup", "start", "2026-09-10T00:00:00Z"),  # before the cutoff
            _span("hm:wrapup", "start", "2026-09-12T00:00:00Z"),
            _span("hm:wrapup", "end", "2026-09-12T01:00:00Z"),  # end events never count
            _span("hm:plan", "start", "2026-09-13T00:00:00Z"),  # another stage
            _span("hm:wrapup", "start", "2026-09-14T00:00:00+09:00"),
            _span("hm:wrapup", "start", "2026-09-15T00:00:00"),  # naive ts: skipped
            "{not json",
        ],
    )
    return root, None


_BUILDERS: dict[
    tuple[bool, bool, str, str], Callable[[Path], tuple[Path, dict[str, str] | None]]
] = {
    (False, False, "ok", "ok"): _b_not_filled,
    (True, False, "shallow", "ok"): _b_shallow_no_signal,
    (True, False, "no_filled_commit", "ok"): _b_fill_uncommitted,
    (True, True, "ok", "missing"): _b_signal_no_spans,
    (True, True, "ok", "no_wrapup"): _b_signal_no_wrapup,
    (True, True, "ok", "ok"): _b_signal_ok,
}
_REASON_ROWS = load_golden_table(_SPEC, "AC-006")


def _key(row: GoldenRow) -> tuple[bool, bool, str, str]:
    i = row.input
    return (bool(i["filled"]), bool(i["signal"]), str(i["git"]), str(i["spans"]))


def test_ac_006_every_table_row_has_a_fixture() -> None:
    """Positive control: a table row with no builder would be silently untested."""
    assert {_key(r) for r in _REASON_ROWS} == set(_BUILDERS)


@pytest.mark.parametrize(
    "row", _REASON_ROWS, ids=[r.note or f"row{i}" for i, r in enumerate(_REASON_ROWS)]
)
def test_ac_006_each_reason_has_exactly_one_producing_condition(
    tmp_path: Path, row: GoldenRow
) -> None:
    root, _env = _BUILDERS[_key(row)](tmp_path)
    assert _report(root)["reason"] == row.expected


@pytest.mark.parametrize(
    "row", _REASON_ROWS, ids=[r.note or f"row{i}" for i, r in enumerate(_REASON_ROWS)]
)
def test_ac_004_an_uncountable_count_is_absent_with_a_reason_never_zero(
    tmp_path: Path, row: GoldenRow
) -> None:
    """The inherited invariant: `None` plus a reason, never a disguised `0`."""
    root, _env = _BUILDERS[_key(row)](tmp_path)
    got = _report(root)
    assert set(got) == _KEYS
    if got["quiet_wrapups"] is None:
        assert got["reason"] != "ok", got
        assert got["due"] is False, got
    else:
        assert got["reason"] == "ok", got


# ── AC-005: a recorded signal makes the verdict independent of git ───────────


@pytest.mark.discriminates
def test_ac_005_a_shallow_clone_with_a_signal_still_counts(tmp_path: Path) -> None:
    """Preconditions, all four: filled intent, a wrapup-bearing ledger, a shallow clone, a signal.

    `_filled_at` refuses a shallow clone by contract, so the retired implementation reports
    `no_git` here and takes no count at all. This asserts the COUNT, not `filled_at`: since the
    ADR-004 reversal the git call is skipped entirely when a signal exists, so `filled_at is
    None` would hold here whether or not git could have answered — a vacuous assertion for the
    thing this AC is about. `test_filled_at_is_not_resolved_when_a_signal_exists` binds that.
    """
    src = _filled_repo(tmp_path / "src", values=[_measurement("2026-09-11T00:00:00Z")])
    _git(src, "commit", "-q", "--allow-empty", "-m", "later", date="2026-09-12T00:00:00Z")
    dst = tmp_path / "dst"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{src}", str(dst)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    _wrapups(dst, [datetime(2026, 9, 12 + d, tzinfo=UTC) for d in range(3)])

    got = _report(dst)
    assert got["last_signal_at"] == "2026-09-11T00:00:00Z"
    assert got["quiet_wrapups"] == 3
    assert got["reason"] == "ok"


# ── The discrimination screen ────────────────────────────────────────────────


#: Every test NOT in the screen, and the reason it cannot fail against the control.
#:
#: Two reasons appear, and they are different facts. **preserved** — the SPEC deliberately keeps
#: this behaviour identical to the retired rule, so no correct implementation can diverge from
#: the control here, and requiring a failure would be requiring the SPEC to be violated.
#: **control-blind** — the control ignores the dimension the test varies, so the test cannot
#: fail against *this* control although it would fail against other wrong implementations.
#: Neither is "untested": each of these is live regression coverage. What they are not is
#: evidence about the window change.
_NOT_IN_THE_SCREEN: dict[str, str] = {
    "test_the_control_is_the_retired_rule": (
        "control-on-control — it asserts the RETIRED behaviour, so under the screen it is the "
        "one test that must stay green; marking it would make the screen self-contradictory"
    ),
    "test_ac_006_every_table_row_has_a_fixture": (
        "touches no subject — it compares the golden table's row keys to the builder map"
    ),
    "test_every_subject_touching_test_declares_whether_it_discriminates": "this test",
    "test_ac_001_a_signal_older_than_the_cutoff_changes_nothing": (
        "control-blind — the control reads no signal timestamp at all, so rewriting the signal "
        "history changes nothing it computes and the invariance holds trivially. The relation "
        "still binds against other wrong implementations (min instead of max, or a cutoff that "
        "drifts with the oldest signal); its partner "
        "`test_ac_001_moving_the_newest_signal_across_the_wrapups_changes_the_count` is the half "
        "that discriminates, and AC-001 is only meaningful as the pair"
    ),
    "test_a_layer_that_never_signalled_counts_from_filled_at": (
        "preserved — SPEC S3 says this case behaves 'as it did under the retired rule'. With no "
        "signal the cutoff IS `filled_at`, which is what the retired rule counted from, so the "
        "two are provably equal on this fixture and no rewrite can make it discriminate"
    ),
    "test_not_filled_in_outranks_a_recorded_signal": (
        "preserved — both rule versions honour the same `is_not_filled_in` short-circuit and "
        "neither reaches the window-versus-cumulative branch, so no fixture separates them"
    ),
    "test_ac_006_each_reason_has_exactly_one_producing_condition": (
        "preserved — AC-006's own oracle_evidence says the replacement 'introduces no new "
        "failure mode and retires none'. Only the cutoff fed to `_count_wrapups` changes, and "
        "that never changes which reason string comes back, only the count"
    ),
    "test_ac_004_an_uncountable_count_is_absent_with_a_reason_never_zero": (
        "preserved — AC-004's own oracle_evidence says 'the new key inherits the assertion its "
        "predecessor already had to pass'; the SPEC declares it a continuity check, not a "
        "discriminator"
    ),
    "test_ac_008_the_withdrawal_block_key_set_is_exactly_six": (
        "preserved — the control emits the six new names by construction, so its key-set "
        "assertion is true for the control by definition. AC-008 pins the rename, which is a "
        "different contract from the rule; AC-001 and AC-002 pin the rule"
    ),
}


def test_every_subject_touching_test_declares_whether_it_discriminates() -> None:
    """A new window test must not silently escape the Phase 1 screen.

    The population is DERIVED from the module — every `test_*` in it — and checked against the
    marker, never against a hand-kept list of test names. A list of names is the thing that goes
    stale; `_NOT_IN_THE_SCREEN` is the other kind of list, finite and each entry carrying the
    reason that entry is there.

    The screen itself is one command, not a test:

        HM_WITHDRAWAL_CONTROL=1 uv run pytest tests/unit/test_world_withdrawal.py -m discriminates

    Every selected test must FAIL. Running it here would mean a pytest inside a pytest whose own
    failure is the success condition — inverted, fragile, and it would have to re-enter this
    module. It is Phase 1's exit criterion instead.
    """
    tests = {name for name in globals() if name.startswith("test_")}
    marked = {
        name
        for name in tests
        if any(m.name == "discriminates" for m in getattr(globals()[name], "pytestmark", []))
    }
    exempt = set(_NOT_IN_THE_SCREEN)
    assert exempt <= tests, f"an exemption names a test that no longer exists: {exempt - tests}"
    assert all(_NOT_IN_THE_SCREEN.values()), "every exemption must carry a reason"
    assert tests - marked == exempt, (
        "every test that reads the subject must be marked `discriminates` or carry a reason in "
        f"_NOT_IN_THE_SCREEN; unaccounted: {sorted(tests - marked - exempt)}"
    )
