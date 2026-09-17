"""AC-002 / AC-003 / AC-004 / AC-006 (SPEC-outcome-measure) — `hm world outcome measure`.

Oracles: AC-002/003/006 are golden — every probe is a hand-written script with a known
output, the expected evidence string and hash are computed here from the fixture's own facts
(argv, `git rev-parse`, the intent fields via the test-side `fx.definition_hash`), never from
the verb's return value; refusals compare `outcomes.yaml` byte for byte. AC-004 is a property:
for any world the fixture builder produces, `--all --dry-run` leaves the sha256 of every file
under the checkout unchanged (the probes are the test's own and never write). Profiles: `ci`
(derandomized, the gate) and `dev` (broader), selected by HYPOTHESIS_PROFILE (default ci).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import world
from tests.unit import world_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=8, deadline=None)
settings.register_profile("dev", max_examples=40, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

KINDS = ("measurable-ok", "measurable-failing", "manual")


@pytest.fixture(autouse=True)
def _python_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """`cmd: python probe.py` must resolve to the interpreter running the tests."""
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


def _probe(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def _rows(root: Path) -> list[dict[str, Any]]:
    return list(fx.load(fx.outcomes_path(root))["values"])


def _tree_hash(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _measure(
    cmd: str = "python probe.py", select: str = "json:report.carry_ratio", **over: Any
) -> dict[str, Any]:
    return {"cmd": cmd, "select": select, **over}


def _committed_root(tmp_path: Path, *outcomes: dict[str, Any]) -> tuple[Path, str]:
    root = fx.build_root(tmp_path, intent=fx.intent_doc(*outcomes))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root, _git(root, "rev-parse", "--short", "HEAD")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return fx.run_cli(["--root", str(root), "outcome", "measure", *args, "--json"], cwd=root)


# ── AC-002 ───────────────────────────────────────────────────────────────────


def test_ac_002_measure_records_the_extracted_number_with_auto_evidence(tmp_path: Path) -> None:
    carry = fx.outcome("carry", measure=_measure())
    rx = fx.outcome("rx", measure=_measure("python text.py", "regex:carry=([0-9.]+)"))
    ln = fx.outcome("ln", measure=_measure("python text.py", "last-number"))
    root, sha = _committed_root(tmp_path, carry, rx, ln)
    _probe(root, "probe.py", 'import json; print(json.dumps({"report": {"carry_ratio": 0.672}}))')
    _probe(root, "text.py", 'print("stage carry=0.672")')

    proc = _run(root, "carry")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = _rows(root)
    assert rows[-1]["value"] == 0.672
    assert rows[-1]["evidence"] == f"auto: python probe.py @ {sha} exit=0 cwd=base"
    assert rows[-1]["observed_at"].endswith("Z")
    assert rows[-1]["definition_hash"] == fx.definition_hash(carry)
    assert "carry_ratio" not in rows[-1]["evidence"]

    assert _run(root, "rx").returncode == 0
    assert _run(root, "ln").returncode == 0
    regex_row, last_number_row = _rows(root)[-2:]
    assert (regex_row["outcome_id"], regex_row["value"]) == ("rx", 0.672)
    assert (last_number_row["outcome_id"], last_number_row["value"]) == ("ln", 0.672)


def test_ac_002_the_recorded_row_is_what_record_value_would_write(tmp_path: Path) -> None:
    """Differential against the shipped writer: same outcome, same value, same evidence."""
    carry = fx.outcome("carry", measure=_measure())
    root, sha = _committed_root(tmp_path, carry)
    _probe(root, "probe.py", 'import json; print(json.dumps({"report": {"carry_ratio": 0.672}}))')
    assert _run(root, "carry").returncode == 0
    measured = _rows(root)[-1]
    manual = world.record_value(
        root,
        outcome_id="carry",
        value=0.672,
        observed_at=measured["observed_at"],
        evidence=f"auto: python probe.py @ {sha} exit=0 cwd=base",
    )
    assert manual == measured


def test_ac_002_stdout_never_reaches_the_row_and_diagnostics_are_bounded(tmp_path: Path) -> None:
    carry = fx.outcome("carry", measure=_measure("python noisy.py", "json:report.carry_ratio"))
    root, _ = _committed_root(tmp_path, carry)
    _probe(
        root,
        "noisy.py",
        "import sys, json\n"
        "sys.stderr.write('x' * 5000)\n"
        "print(json.dumps({'report': {'carry_ratio': 0.5}, 'blob': 'SECRETBLOB' * 400}))\n"
        "sys.exit(3)\n",
    )
    proc = _run(root, "carry")
    assert proc.returncode != 0
    assert "SECRETBLOB" * 5 not in proc.stdout + proc.stderr
    assert "truncated" in proc.stdout + proc.stderr
    assert len(proc.stdout + proc.stderr) < 4000
    assert _rows(root) == []


@pytest.mark.parametrize(
    ("text", "select", "expected"),
    [
        ("done 1e-3", "last-number", 0.001),
        ("ratio .672", "last-number", 0.672),
        ("a 3 b 17.0", "last-number", 17),
        ("v=+2.5e2", "last-number", 250),
        ('{"a": [{"b": 4}]}', "json:a.0.b", 4),
        ("carry=0.672", "regex:carry=([0-9.]+)", 0.672),
    ],
)
def test_ac_002_selectors_parse_every_valid_number_form(
    text: str, select: str, expected: float
) -> None:
    got = world.select_number(text, select)
    assert got == expected
    assert isinstance(got, int) == float(expected).is_integer()


@pytest.mark.parametrize(
    ("text", "select"),
    [
        ('{"a": true}', "json:a"),
        ('{"a": NaN}', "json:a"),
        ('{"a": "0.5"}', "json:a"),
        ('{"a": 1}', "json:b"),
        ("not json", "json:a"),
        ("no digits here", "last-number"),
        ("carry=none", "regex:carry=([0-9.]+)"),
        ("Infinity", "regex:(Infinity)"),
        ("abc", "regex:(\\d+)?abc"),  # review 58012515: optional group did not participate
        ('{"a": ' + "9" * 400 + "}", "json:a"),  # review 3836a55b: int too large for float
        ("token=super-secret", "regex:token=(.+)"),  # review c55b8855: message carries no stdout
    ],
)
def test_ac_002_selectors_refuse_non_numbers_as_select(text: str, select: str) -> None:
    with pytest.raises(world.WorldError) as exc:
        world.select_number(text, select)
    assert exc.value.field == "select"
    assert "super-secret" not in str(exc.value)
    assert "9" * 20 not in str(exc.value)


def test_ac_002_select_failure_message_is_redacted_and_bounded(tmp_path: Path) -> None:
    """Review c55b8855: exit 0 + secret-shaped stdout + a failing selector — the CLI's error
    must not carry the stdout fragment (ADR-004: stdout never reaches a row or a message)."""
    carry = fx.outcome("carry", measure=_measure("python leak.py", "json:report.token"))
    root, _ = _committed_root(tmp_path, carry)
    _probe(
        root,
        "leak.py",
        "import json; print(json.dumps({'report': {'token': 'SECRETVALUE' * 50}}))",
    )
    proc = _run(root, "carry")
    assert proc.returncode != 0
    assert "SECRETVALUE" not in proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["error"]["field"] == "select"
    assert _rows(root) == []


def test_ac_003_timeout_kills_the_whole_process_group(tmp_path: Path) -> None:
    """Review 1b9bdc41: a grandchild of measure.cmd must not outlive timeout_s."""
    slow = fx.outcome("slow", measure=_measure("python parent.py", "last-number", timeout_s=3))
    root, _ = _committed_root(tmp_path, slow)
    marker = root / "grandchild.pid"
    _probe(
        root,
        "parent.py",
        "import subprocess, sys, time\n"
        f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open({str(marker)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(30)\n",
    )
    proc = _run(root, "slow")
    assert proc.returncode != 0
    assert json.loads(proc.stdout)["error"]["field"] == "timeout"
    pid = int(marker.read_text())
    import time as _time

    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        # a zombie still answers kill(0); reap-check via /proc state on Linux
        state = Path(f"/proc/{pid}/stat")
        if not state.exists() or " Z " in state.read_text():
            break
        _time.sleep(0.1)
    else:
        os.kill(pid, 9)
        pytest.fail("the grandchild survived the timeout")


# ── AC-003 ───────────────────────────────────────────────────────────────────


def test_ac_003_failures_write_nothing_and_name_the_cause(tmp_path: Path) -> None:
    outcomes = [
        fx.outcome("bad_exit", measure=_measure("python exit3.py", "last-number")),
        fx.outcome("no_number", measure=_measure("python words.py", "last-number")),
        fx.outcome("slow", measure=_measure("python slow.py", "last-number", timeout_s=1)),
        fx.outcome("manual"),
    ]
    root, _ = _committed_root(tmp_path, *outcomes)
    _probe(root, "exit3.py", "print(7); raise SystemExit(3)")
    _probe(root, "words.py", "print('no digits')")
    _probe(root, "slow.py", "import time; time.sleep(5); print(1)")
    before = fx.outcomes_path(root).read_bytes()
    failures = [
        (_run(root, "bad_exit"), "exit"),
        (_run(root, "no_number"), "select"),
        (_run(root, "slow"), "timeout"),
        (_run(root, "manual"), "measure"),
    ]
    assert all(
        proc.returncode != 0 and cause in proc.stdout + proc.stderr for proc, cause in failures
    ), [(p.returncode, p.stdout[-200:], c) for p, c in failures]
    for proc, cause in failures:
        assert json.loads(proc.stdout)["error"]["field"] == cause
    assert fx.outcomes_path(root).read_bytes() == before


def test_ac_003_an_unknown_outcome_id_is_refused(tmp_path: Path) -> None:
    root, _ = _committed_root(tmp_path, fx.outcome("carry", measure=_measure()))
    proc = _run(root, "nope")
    assert proc.returncode != 0
    assert json.loads(proc.stdout)["error"]["field"] == "outcome_id"


# ── AC-004 ───────────────────────────────────────────────────────────────────


def _world_of(root: Path, kinds: list[str]) -> Path:
    outcomes = []
    for i, kind in enumerate(kinds):
        oid = f"o{i}"
        if kind == "measurable-ok":
            outcomes.append(fx.outcome(oid, measure=_measure("python ok.py", "json:v")))
        elif kind == "measurable-failing":
            outcomes.append(fx.outcome(oid, measure=_measure("python bad.py", "json:v")))
        else:
            outcomes.append(fx.outcome(oid))
    fx.build_root(root, intent=fx.intent_doc(*outcomes))
    _probe(root, "ok.py", "print('{\"v\": 1}')")
    _probe(root, "bad.py", "raise SystemExit(3)")
    return root


@given(kinds=st.lists(st.sampled_from(KINDS), min_size=0, max_size=3))
def test_ac_004_dry_run_writes_nothing(
    tmp_path_factory: pytest.TempPathFactory, kinds: list[str]
) -> None:
    root = _world_of(tmp_path_factory.mktemp("w"), kinds)
    before = _tree_hash(root)
    proc = _run(root, "--all", "--dry-run")
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    assert _tree_hash(root) == before
    payload = json.loads(proc.stdout)
    assert [r["outcome"] for r in payload["results"]] == [f"o{i}" for i in range(len(kinds))]


def test_ac_004_all_reports_every_outcome_and_records_only_successes(tmp_path: Path) -> None:
    root = _world_of(tmp_path, ["measurable-ok", "measurable-failing", "manual"])
    dry = _run(root, "--all", "--dry-run")
    assert dry.returncode == 1
    dry_results = json.loads(dry.stdout)["results"]
    assert [r["status"] for r in dry_results] == ["would_record", "failed", "manual"]
    assert dry_results[0]["value"] == 1  # dry-run RUNS the command; the harness writes nothing
    assert dry_results[1]["cause"] == "exit"
    assert _rows(root) == []

    wet = _run(root, "--all")
    assert wet.returncode == 1
    results = json.loads(wet.stdout)["results"]
    assert [r["status"] for r in results] == ["recorded", "failed", "manual"]
    assert results[0]["value"] == 1
    rows = _rows(root)
    assert [r["outcome_id"] for r in rows] == ["o0"]

    ok_only = _world_of(tmp_path / "ok", ["measurable-ok"])
    assert _run(ok_only, "--all").returncode == 0


# ── AC-006 ───────────────────────────────────────────────────────────────────


def test_ac_006_default_cwd_is_the_base_root(tmp_path: Path) -> None:
    """The probe prints the marker file at ITS cwd; base and the linked worktree hold different
    markers, so the recorded value identifies the directory independently of the verb."""
    base_o = fx.outcome("base_o", measure=_measure("python marker.py", "last-number"))
    wt_o = fx.outcome("wt_o", measure=_measure("python marker.py", "last-number", cwd="checkout"))
    base, _ = _committed_root(tmp_path / "base", base_o, wt_o)
    _probe(base, "marker.py", "print(open('marker.txt').read())")
    (base / "marker.txt").write_text("111\n", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-q", "-m", "marker")
    wt = base / ".worktrees" / "t"
    _git(base, "worktree", "add", "-q", "-b", "hm/t", str(wt))
    (wt / "marker.txt").write_text("222\n", encoding="utf-8")
    base_marker, worktree_marker = 111, 222

    assert _run(wt, "base_o").returncode == 0
    assert _run(wt, "wt_o").returncode == 0
    base_row, checkout_row = _rows(wt)[-2:]
    assert (base_row["value"], checkout_row["value"]) == (base_marker, worktree_marker)
    assert "cwd=base" in base_row["evidence"]
    assert "cwd=checkout" in checkout_row["evidence"]


# ── gap_report carries the listing the wrapup question reads (ADR-006) ────────


def test_gap_report_marks_measurable_outcomes(tmp_path: Path) -> None:
    root = fx.build_root(
        tmp_path, intent=fx.intent_doc(fx.outcome("m", measure=_measure()), fx.outcome("h"))
    )
    outcomes = world.gap_report(root)["outcomes"]
    assert outcomes["m"]["measure"] is True
    assert outcomes["h"]["measure"] is False
    assert outcomes["m"]["observed_at"] is None


def test_concurrent_writers_never_lose_a_row(tmp_path: Path) -> None:
    """Confirm-1 finding: `_rmw_lock` serializes the read-modify-write of outcomes.yaml across
    processes — eight parallel `outcome record` CLIs must leave eight rows, and the lock lives
    under the gitignored observability dir, never as dirt in `.claude/world/`."""
    outcomes = [fx.outcome(f"o{i}") for i in range(8)]
    root, _ = _committed_root(tmp_path, *outcomes)
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "harness_maker.hm",
                "world",
                "--root",
                str(root),
                "outcome",
                "record",
                f"o{i}",
                "--value",
                str(i),
                "--observed-at",
                "2026-09-17T00:00:00Z",
                "--evidence",
                "race",
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(8)
    ]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1][-200:] for o in outs]
    assert sorted(r["outcome_id"] for r in _rows(root)) == [f"o{i}" for i in range(8)]
    assert not list((root / ".claude" / "world").glob("*.lock"))
    assert (root / ".claude" / "observability" / ".hm-world-outcomes.lock").exists()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", ".claude/world"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    assert "lock" not in status
