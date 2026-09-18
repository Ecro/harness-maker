"""AC-008 (SPEC-assumption-entry-and-evidence-locator) — assumption writers do not lose rows.

Two layers, because either alone can pass without a lock (validator critique on the PLAN):

(a) **Deterministic.** The test holds the RMW lock itself and starts the writer on a thread.
    `flock` conflicts between separate open file descriptions even inside one process, so a
    locked writer retries — and its first retry sets an Event through the patched `sleep`. The
    test waits on that Event (a positive "blocked" signal, never a timer), checks the file is
    untouched, releases, and checks the write landed. An unlocked writer never retries, never
    sets the Event, and writes while the lock is held — so it fails here by construction.

(b) **Stress.** Two subprocesses released by one barrier file, each doing 20 writes; every id
    and every evidence row either process was told to write must be present afterwards.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness_maker import world
from tests.unit import world_fixture as fx

TS = "2026-09-18T00:00:00Z"
N = 20


def _root(tmp_path: Path) -> Path:
    return fx.build_root(
        tmp_path,
        assumptions=[
            fx.assumption("known_one", claim="K"),
            fx.assumption("split", claim="S", status="conflict"),
        ],
    )


def _ops(root: Path) -> dict[str, Callable[[], Any]]:
    return {
        "add": lambda: world.add_assumption(root, "new_one", claim="N", status="assumed"),
        "observe": lambda: world.observe(
            root, "known_one", text="t", observed_at=TS, relation="confirms"
        ),
        "resolve": lambda: world.resolve(root, "split", status="known", claim="settled"),
    }


def _landed(doc: dict[str, Any], op: str) -> bool:
    recs: dict[str, dict[str, Any]] = {r["id"]: r for r in doc["assumptions"]}
    if op == "add":
        return "new_one" in recs
    if op == "observe":
        return len(recs["known_one"]["evidence"]) == 2
    return bool(recs["split"]["status"] == "known" and recs["split"]["claim"] == "settled")


@pytest.mark.parametrize("op", ["add", "observe", "resolve"])
def test_ac_008_a_writer_meeting_a_held_lock_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    root = _root(tmp_path)
    path = fx.assumptions_path(root)
    blocked = threading.Event()
    real_sleep = time.sleep

    def spy(seconds: float) -> None:
        blocked.set()
        real_sleep(seconds)

    monkeypatch.setattr(time, "sleep", spy)  # the module world.py sleeps through
    errors: list[BaseException] = []

    def run() -> None:
        try:
            _ops(root)[op]()
        except BaseException as exc:  # noqa: BLE001 — surfaced by the assertion below
            errors.append(exc)

    writer = threading.Thread(target=run)
    with world._rmw_lock(path):
        before = path.read_bytes()
        writer.start()
        assert blocked.wait(10), "the writer never contended for the lock"
        assert path.read_bytes() == before, "the writer wrote while the lock was held"
    writer.join(30)
    assert not errors, errors
    assert _landed(fx.load(path), op)


def test_ac_008_lock_timeout_names_the_file_it_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(world, "_APPEND_LOCK_TIMEOUT_S", 0.2)
    with world._rmw_lock(fx.assumptions_path(root)), pytest.raises(world.WorldError) as info:
        world.add_assumption(root, "new_one", claim="N", status="assumed")
    assert info.value.message.startswith("assumptions.yaml is locked by another writer")


_WORKER = """
import pathlib, sys, time
from harness_maker.world import main
barrier = pathlib.Path(sys.argv[1])
root, kind, n = sys.argv[2], sys.argv[3], int(sys.argv[4])
while not barrier.exists():
    time.sleep(0.002)
for i in range(n):
    if kind.startswith("add:"):
        argv = ["--root", root, "assume", "add", f"{kind[4:]}{i}", "--claim", "c", "--status",
                "known"]
    else:
        argv = ["--root", root, "assume", "observe", "known_one", "--relation", "confirms",
                "--text", f"t{i}", "--observed-at", "2026-09-18T00:00:00Z"]
    if main(argv) != 0:
        sys.exit(1)
"""


def _race(root: Path, kinds: tuple[str, str], tmp_path: Path) -> list[int]:
    barrier = tmp_path / "go"
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _WORKER, str(barrier), str(root), kind, str(N)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for kind in kinds
    ]
    time.sleep(1.0)  # let both interpreters finish importing before release
    barrier.touch()
    return [p.wait(timeout=120) for p in procs]


def test_ac_008_concurrent_writers_keep_both_rows(tmp_path: Path) -> None:
    root_aa = _root(tmp_path / "aa")
    assert _race(root_aa, ("add:a", "add:b"), tmp_path / "aa") == [0, 0]
    ids = {r["id"] for r in fx.load(fx.assumptions_path(root_aa))["assumptions"]}
    assert {f"a{i}" for i in range(N)} | {f"b{i}" for i in range(N)} <= ids

    root_ao = _root(tmp_path / "ao")
    assert _race(root_ao, ("add:c", "observe"), tmp_path / "ao") == [0, 0]
    recs = {r["id"]: r for r in fx.load(fx.assumptions_path(root_ao))["assumptions"]}
    assert {f"c{i}" for i in range(N)} <= set(recs)
    assert len(recs["known_one"]["evidence"]) == 1 + N
