"""SPEC-top-issues-2026-09 S5: `verification_cache run` owns both the gate run and the marker.

The marker used to be written by the LLM calling `mark-pass` after it *said* the suite passed —
on 2026-09-20 that landed an uncollectable test on main. These tests drive `run` against a
real git repo whose CI workflow names fake `ruff` / `pytest` executables on PATH, so what
"ran" and what it "returned" are observed facts, not claims.

Phase A.4 justified pass: `test_check_still_accepts_legacy_markers` pins that `check` is NOT changed
(a SPEC non-goal). It goes red if `run`'s stricter freshness leaks into `is_fresh`. Its RED positive
sibling is `test_cached_only_for_own_marker`.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker.observability import verification_cache as vc

_FAKE_TOOL = """#!/usr/bin/env python3
import os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
if "--version" in sys.argv[1:]:
    # The skip key fingerprints tool versions; that probe is not a gate run.
    print(f"{name} 0.0.0")
    sys.exit(0)
out = pathlib.Path(os.environ["FAKE_SENTINEL_DIR"])
out.mkdir(parents=True, exist_ok=True)
(out / f"ran-{name}").write_text(" ".join(sys.argv[1:]))
spawn = os.environ.get(f"FAKE_SPAWN_{name}")
if spawn:
    import subprocess as sp
    code = f"import time,pathlib; time.sleep(2); pathlib.Path({spawn!r}).write_text('orphan')"
    sp.Popen([sys.executable, "-c", code])
detach = os.environ.get(f"FAKE_DETACH_{name}")
if detach:
    import subprocess as sp
    # Leaves the gate's group AND keeps the stdout pipe open: killpg cannot reach it.
    d = sp.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    pathlib.Path(detach).write_text(str(d.pid))
if os.environ.get(f"FAKE_TERM_PARENT_{name}"):
    import signal
    time.sleep(0.3)  # let the spawned grandchild start first
    os.kill(os.getppid(), signal.SIGTERM)
sleep = os.environ.get(f"FAKE_SLEEP_{name}")
if sleep:
    time.sleep(float(sleep))
mutate = os.environ.get(f"FAKE_MUTATE_{name}")
if mutate:
    pathlib.Path(mutate).write_text("changed during the run\\n")
if os.environ.get(f"FAKE_RC_{name}", "0") != "0":
    print(f"{name}: simulated failure line", file=sys.stderr)
sys.exit(int(os.environ.get(f"FAKE_RC_{name}", "0")))
"""

_CI = """name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruff check .
      - run: pytest -q
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def _project(
    base: Path, monkeypatch: pytest.MonkeyPatch, *, with_ci: bool = True, ci: str = _CI
) -> Path:
    root = base / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (root / "uv.lock").write_text("# lock\n", encoding="utf-8")
    (root / "src.py").write_text("x = 1\n", encoding="utf-8")
    if with_ci:
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text(ci, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")

    fake_bin = base / "bin"
    fake_bin.mkdir()
    for name in ("ruff", "pytest"):
        tool = fake_bin / name
        tool.write_text(_FAKE_TOOL, encoding="utf-8")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_SENTINEL_DIR", str(base / "sentinels"))
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(base / "cache"))
    for name in ("ruff", "pytest"):
        for knob in ("RC", "SLEEP", "MUTATE", "SPAWN", "DETACH", "TERM_PARENT"):
            monkeypatch.delenv(f"FAKE_{knob}_{name}", raising=False)
    return root


def _markers(base: Path) -> list[Path]:
    return sorted((base / "cache" / "verify").glob("*.json"))


def _run(
    root: Path, capsys: pytest.CaptureFixture[str], *extra: str
) -> tuple[int, dict[str, Any], str]:
    rc = vc.main(["run", "--root", str(root), *extra])
    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    return rc, json.loads(lines[-1]), captured.err


# ── AC-007 (property over exit codes and mid-run mutation) ───────────────────


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(rcs=st.tuples(st.sampled_from([0, 1]), st.sampled_from([0, 1])), mutate=st.booleans())
def test_marks_only_when_all_pass_and_key_stable(
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
    rcs: tuple[int, int],
    mutate: bool,
) -> None:
    base = tmp_path_factory.mktemp("run")
    with pytest.MonkeyPatch.context() as mp:
        root = _project(base, mp)
        mp.setenv("FAKE_RC_ruff", str(rcs[0]))
        mp.setenv("FAKE_RC_pytest", str(rcs[1]))
        if mutate:
            mp.setenv("FAKE_MUTATE_pytest", str(root / "src.py"))
        rc, out, err = _run(root, capsys)

    marker_exists_after = bool(_markers(base))
    all_pass = all(r == 0 for r in rcs)
    ran_pytest = (base / "sentinels" / "ran-pytest").exists()
    key_changed = mutate and ran_pytest
    assert marker_exists_after == (all_pass and not key_changed)
    if marker_exists_after:
        assert rc == 0
    elif not all_pass:
        assert rc == 1
        assert "simulated failure line" in err
    else:
        assert rc == 4
        assert "src.py" in err
    # Stop at the first failure: a failing lint means pytest never ran.
    if rcs[0] != 0:
        assert not ran_pytest
    assert out["cached"] is False


def test_timeout_is_a_failure_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_SLEEP_pytest", "5")
    rc, out, err = _run(root, capsys, "--timeout-s", "1")
    assert rc == 1
    assert not _markers(tmp_path)
    assert "timed out" in err


def test_marker_records_the_commands_it_ran(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, monkeypatch)
    rc, out, _ = _run(root, capsys)
    assert rc == 0
    marker = json.loads(_markers(tmp_path)[0].read_text(encoding="utf-8"))
    assert marker["writer"] == "run"
    assert marker["checks"] == ["ruff check .", "pytest -q"]
    assert out["commands"] == ["ruff check .", "pytest -q"]


# ── AC-008 ───────────────────────────────────────────────────────────────────


def test_cached_only_for_own_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, monkeypatch)
    sentinel = tmp_path / "sentinels" / "ran-pytest"

    # A writer-less marker for EXACTLY run's command list: only the writer rule can reject it.
    # This is the 2026-09-20 route — a self-attested marker naming the right commands.
    assert vc.main(["mark-pass", "--root", str(root), "--checks", "ruff check .,pytest -q"]) == 0
    capsys.readouterr()
    rc, out, _ = _run(root, capsys)
    assert out["cached"] is False
    assert sentinel.exists()
    sentinel.unlink()
    for marker in _markers(tmp_path):
        marker.unlink()

    # A marker written by `mark-pass` — the self-attested path — must not satisfy `run`.
    assert vc.main(["mark-pass", "--root", str(root)]) == 0
    capsys.readouterr()
    rc, out, _ = _run(root, capsys)
    assert out["cached"] is False
    assert sentinel.exists()
    assert rc == 0

    # A second `run` on the same tree reuses its own marker and runs nothing.
    sentinel.unlink()
    rc, out, _ = _run(root, capsys)
    assert out["cached"] is True
    assert rc == 0
    assert not sentinel.exists()

    # Writer provenance alone (stuck Path B): take `run`'s own marker and change ONLY `writer`.
    # Every other byte — commands, hash — stays identical, so a hash-only check cannot reject it.
    own = _markers(tmp_path)[0]
    pristine = own.read_text(encoding="utf-8")
    for tamper in ("mark-pass", None):
        data = json.loads(pristine)
        if tamper is None:
            data.pop("writer")
        else:
            data["writer"] = tamper
        own.write_text(json.dumps(data), encoding="utf-8")
        rc, out, _ = _run(root, capsys)
        assert out["cached"] is False, tamper
        assert sentinel.exists(), tamper
        sentinel.unlink()
        own.write_text(pristine, encoding="utf-8")

    # A `run` marker for a DIFFERENT command list does not count either.
    key = vc.compute_relevant_skip_key(root)
    vc.mark_passed(key, checks=["pytest -x"], writer="run")
    rc, out, _ = _run(root, capsys)
    assert out["cached"] is False
    assert sentinel.exists()


def test_check_still_accepts_legacy_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`check` keeps its semantics — un-re-rendered harnesses still call it (SPEC non-goal)."""
    root = _project(tmp_path, monkeypatch)
    assert vc.main(["mark-pass", "--root", str(root)]) == 0
    assert vc.main(["check", "--root", str(root)]) == 0


# ── AC-009 ───────────────────────────────────────────────────────────────────


def test_degraded_plan_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, monkeypatch, with_ci=False)
    rc, out, err = _run(root, capsys)
    marker_exists = bool(_markers(tmp_path))
    sentinel = tmp_path / "sentinels" / "ran-pytest"
    assert rc == 3
    assert not marker_exists
    assert not sentinel.exists()
    assert "degraded" in err


# ── review round 1 repairs: the windows the fixes newly reach ─────────────────


def test_no_blocking_gate_is_degraded_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every CI gate continue-on-error → nothing would run; a marker would record a pass nobody
    observed (review finding 081ddfc3)."""
    ci = _CI.replace(
        "      - run: ruff check .\n      - run: pytest -q\n",
        ("      - run: pytest -q\n        continue-on-error: true\n"),
    )
    root = _project(tmp_path, monkeypatch, ci=ci)
    rc, out, err = _run(root, capsys)
    assert rc == 3
    assert not _markers(tmp_path)
    assert not (tmp_path / "sentinels" / "ran-pytest").exists()
    assert "no blocking gate" in err


def test_timeout_kills_the_whole_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A grandchild the gate spawned must not outlive the timeout (review finding db1aa405)."""
    import time

    root = _project(tmp_path, monkeypatch)
    orphan = tmp_path / "orphan-wrote-this"
    monkeypatch.setenv("FAKE_SPAWN_ruff", str(orphan))
    monkeypatch.setenv("FAKE_SLEEP_ruff", "5")
    rc, _, err = _run(root, capsys, "--timeout-s", "1")
    assert rc == 1
    assert "timed out" in err
    time.sleep(3)
    assert not orphan.exists()


def test_run_deadline_caps_the_sum_of_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each gate is under its own cap, but their sum is not under the run's (finding 22071e4e)."""
    root = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(vc, "RUN_DEADLINE_S", 2)
    monkeypatch.setenv("FAKE_SLEEP_ruff", "1.5")
    monkeypatch.setenv("FAKE_SLEEP_pytest", "1.5")
    rc, _, err = _run(root, capsys, "--timeout-s", "10")
    assert rc == 1
    assert "timed out" in err
    assert not _markers(tmp_path)


def test_unbalanced_quote_is_a_failure_inside_the_exit_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ci = _CI.replace("      - run: pytest -q\n", '      - run: pytest "unterminated\n')
    root = _project(tmp_path, monkeypatch, ci=ci)
    rc, _, err = _run(root, capsys)
    assert rc == 1
    assert "could not start" in err


# ── confirm-1 repair: the abnormal-exit and bounded-reap windows ─────────────


def test_termination_kills_the_gate_group_and_stays_in_the_exit_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """SIGTERM to `run` (the host tearing it down) must not orphan the gate's group — the gate
    runs in its own session, so the signal never reaches it on its own (confirm-1 P1)."""
    import time

    root = _project(tmp_path, monkeypatch)
    orphan = tmp_path / "orphan-wrote-this"
    monkeypatch.setenv("FAKE_SPAWN_ruff", str(orphan))
    monkeypatch.setenv("FAKE_TERM_PARENT_ruff", "1")
    monkeypatch.setenv("FAKE_SLEEP_ruff", "5")
    rc = vc.main(["run", "--root", str(root)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "terminated" in err
    assert not _markers(tmp_path)
    time.sleep(3)
    assert not orphan.exists()


def test_reap_is_bounded_when_a_descendant_holds_the_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A descendant that left the group keeps stdout open; the reap must not wait for it
    forever, or the run deadline is not a bound (confirm-1 P1)."""
    import signal
    import time

    root = _project(tmp_path, monkeypatch)
    pidfile = tmp_path / "detached.pid"
    monkeypatch.setenv("FAKE_DETACH_ruff", str(pidfile))
    monkeypatch.setenv("FAKE_SLEEP_ruff", "30")
    monkeypatch.setattr(vc, "REAP_TIMEOUT_S", 1)
    started = time.monotonic()
    try:
        rc, _, err = _run(root, capsys, "--timeout-s", "1")
        elapsed = time.monotonic() - started
    finally:
        if pidfile.exists():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
    assert rc == 1
    assert "timed out" in err
    assert elapsed < 15


# ── verify-stage dogfood: the default budget cannot hold this repo's own suite ──


def test_deadline_flag_lifts_and_tightens_the_run_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--deadline-s` is the whole-run budget: 2 s fails two 1.5 s gates, 30 s passes them.

    Found by dogfooding `run` at /hm:verify: this repo's pytest gate alone took 425-702 s, over
    the 570 s default, so the rendered recipe must be able to lift the budget.
    """
    root = _project(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_SLEEP_ruff", "1.5")
    monkeypatch.setenv("FAKE_SLEEP_pytest", "1.5")
    rc, _, err = _run(root, capsys, "--deadline-s", "2", "--timeout-s", "10")
    assert rc == 1
    assert "2s run deadline" in err or "timed out after" in err
    assert not _markers(tmp_path)
    rc, out, _ = _run(root, capsys, "--deadline-s", "30", "--timeout-s", "10")
    assert rc == 0
    assert out["cached"] is False
    assert _markers(tmp_path)
