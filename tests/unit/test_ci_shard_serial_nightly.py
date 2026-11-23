"""SPEC-ci-shard-serial-nightly: CI runs pytest in file shards; nightly owns the serial run."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
GOLDEN = ROOT / "specs" / "SPEC-ci-shard-serial-nightly.golden.json"

PARALLEL_PYTEST = "uv run pytest -x --tb=short -n auto --dist loadfile"
SERIAL_PYTEST = "uv run pytest -x --tb=short"
SHARD_ENV = "${{ matrix.shard }}/3"

#: Small, fast test files: enough of them that three shards are not all trivially empty.
_PROBE_FILES = [
    "tests/unit/test_pr_boundary_gate.py",
    "tests/unit/test_release_ui_tolerant.py",
    "tests/unit/test_verification_plan.py",
    "tests/structural/test_autotag_workflow.py",
    "tests/unit/test_release_identity.py",
    "tests/unit/test_io_utils.py",
]


def _workflow(name: str) -> dict[Any, Any]:
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


def _runs(job: dict[str, Any]) -> list[str]:
    return [
        s["run"].strip()
        for s in job.get("steps", [])
        if isinstance(s, dict) and isinstance(s.get("run"), str)
    ]


def _inner_env(shard: str | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "HM_TEST_SHARD"))}
    if shard is not None:
        env["HM_TEST_SHARD"] = shard
    return env


def _collect(shard: str | None) -> tuple[int, set[str]]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
        ]
        + _PROBE_FILES,
        cwd=ROOT,
        env=_inner_env(shard),
        capture_output=True,
        text=True,
        timeout=300,
    )
    ids = {line.strip() for line in proc.stdout.splitlines() if "::" in line}
    return proc.returncode, ids


# ---------------------------------------------------------------------------
# AC-001 — the shard filter partitions the suite by file
# ---------------------------------------------------------------------------


def test_ac_001_shard_filter_partitions_by_file() -> None:
    from tests.conftest import parse_shard, shard_of

    files = sorted(
        str(p.relative_to(ROOT)) for p in (ROOT / "tests").rglob("test_*.py") if p.is_file()
    )
    assert len(files) > 100
    for total in range(1, 6):
        buckets = [shard_of(f, total) for f in files]
        assert all(0 <= b < total for b in buckets)
        # Stable: the same file always lands in the same shard (xdist workers recollect).
        assert buckets == [shard_of(f, total) for f in files]

    assert parse_shard("2/3") == (2, 3)
    assert parse_shard("1/1") == (1, 1)
    for bad in ("0/3", "4/3", "x", "1/0", "", "1/2/3", "a/b"):
        with pytest.raises(ValueError, match="HM_TEST_SHARD"):
            parse_shard(bad)

    # The real session: pytest's own collection, sharded three ways, against the unsharded set.
    code, everything = _collect(None)
    assert code == 0
    assert everything
    shards = []
    for i in (1, 2, 3):
        code, ids = _collect(f"{i}/3")
        assert code in (0, 5), code  # 5 = this shard drew none of the probe files
        shards.append(ids)
    assert set().union(*shards) == everything
    for a in range(3):
        for b in range(a + 1, 3):
            assert not shards[a] & shards[b]
    for ids in shards:
        files_here = {i.split("::", 1)[0] for i in ids}
        for other in shards:
            if other is not ids:
                assert not files_here & {i.split("::", 1)[0] for i in other}

    code, ids = _collect("1/1")
    assert code == 0
    assert ids == everything
    code, _ = _collect("4/3")
    assert code == 4  # pytest's usage-error exit, not a silent empty or full run

    # Under xdist (how CI runs it) the error must still be a readable usage error.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n",
            "2",
            "-p",
            "no:cacheprovider",
            _PROBE_FILES[0],
        ],
        cwd=ROOT,
        env=_inner_env("4/3"),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 4, proc.stdout[-1500:] + proc.stderr[-1500:]
    assert "must be 'i/n'" in proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# AC-002 — ci.yml shards quality-gate and keeps a summary check
# ---------------------------------------------------------------------------


def test_ac_002_ci_quality_gate_sharded() -> None:
    jobs = _workflow("ci.yml")["jobs"]
    gate = jobs["quality-gate"]
    assert gate["strategy"]["matrix"]["shard"] == [1, 2, 3]
    assert gate["env"]["HM_TEST_SHARD"] == SHARD_ENV
    runs = _runs(gate)
    for cmd in (
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy --strict src tests",
        PARALLEL_PYTEST,
    ):
        assert cmd in runs, (cmd, runs)
    assert gate.get("continue-on-error") is not True
    assert all(s.get("continue-on-error") is not True for s in gate["steps"])

    summaries = [
        (key, job)
        for key, job in jobs.items()
        if key != "quality-gate" and job.get("name") == "quality-gate"
    ]
    assert len(summaries) == 1, summaries
    _, summary = summaries[0]
    needs = summary["needs"]
    assert needs == "quality-gate" or needs == ["quality-gate"]
    assert summary["if"].strip() in ("always()", "${{ !cancelled() }}", "!cancelled()")
    assert "needs.quality-gate.result" in json.dumps(summary)
    assert any('= "success"' in cmd for cmd in _runs(summary))

    assert "needs" not in jobs["install-cmd-regression"]


# ---------------------------------------------------------------------------
# AC-003 — release.yml tests with the same shards, not serially
# ---------------------------------------------------------------------------


def test_ac_003_release_quality_gate_sharded() -> None:
    jobs = _workflow("release.yml")["jobs"]
    gate = jobs["quality-gate"]
    assert gate["strategy"]["matrix"]["shard"] == [1, 2, 3]
    assert gate["env"]["HM_TEST_SHARD"] == SHARD_ENV
    assert PARALLEL_PYTEST in _runs(gate)
    assert jobs["build"]["needs"] == ["quality-gate"]
    for job in jobs.values():
        for cmd in _runs(job):
            for line in cmd.splitlines():
                if "uv run pytest" in line and "tests/integration/" not in line:
                    assert " -n " in f" {line} ", f"serial pytest in release.yml: {line!r}"


# ---------------------------------------------------------------------------
# AC-004 — nightly owns the serial run, adds 3.13 and skips an unchanged SHA
# ---------------------------------------------------------------------------


def test_ac_004_nightly_serial_py313_skip() -> None:
    doc = _workflow("nightly.yml")
    triggers: dict[str, Any] = doc.get("on") or doc[True]
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    jobs = doc["jobs"]

    serial = [k for k, j in jobs.items() if SERIAL_PYTEST in _runs(j)]
    assert len(serial) == 1, serial
    py313 = [k for k, j in jobs.items() if j.get("env", {}).get("UV_PYTHON") == "3.13"]
    assert len(py313) == 1, py313
    assert any("pytest" in c for c in _runs(jobs[py313[0]]))

    gates = [
        k for k, j in jobs.items() if "outputs" in j and any("gh run list" in c for c in _runs(j))
    ]
    assert len(gates) == 1, gates
    gate_key = gates[0]
    gate_text = "\n".join(_runs(jobs[gate_key]))
    assert "--status success" in gate_text
    assert "nightly.yml" in gate_text
    assert "github.event_name" in json.dumps(jobs[gate_key]) or "GITHUB_EVENT_NAME" in gate_text
    for key in (serial[0], py313[0]):
        job = jobs[key]
        needs = job["needs"] if isinstance(job["needs"], list) else [job["needs"]]
        assert gate_key in needs
        assert f"needs.{gate_key}.outputs." in job["if"]


# ---------------------------------------------------------------------------
# AC-005 — the local gate still runs the full, unsharded suite (golden)
# ---------------------------------------------------------------------------


def _golden_rows() -> list[dict[str, Any]]:
    rows = json.loads(GOLDEN.read_text(encoding="utf-8"))["AC-005"]
    assert isinstance(rows, list)
    assert rows
    return rows


_ROWS = _golden_rows()


@pytest.mark.parametrize("row", _ROWS, ids=[f"AC-005-{i}" for i in range(len(_ROWS))])
def test_ac_005_local_gate_unsharded(row: dict[str, Any]) -> None:
    from harness_maker.verification_plan import read_plan

    assert read_plan(ROOT).primary_commands() == row["expected"]


# ---------------------------------------------------------------------------
# AC-006 — the shard variable does not leak into tests
# ---------------------------------------------------------------------------


def test_shard_env_absent_inside_a_test() -> None:
    """In a CI shard this checks the real thing; AC-006 also runs it with the variable set."""
    assert "HM_TEST_SHARD" not in os.environ


def test_ac_006_shard_env_does_not_leak() -> None:
    probe = "tests/unit/test_ci_shard_serial_nightly.py::test_shard_env_absent_inside_a_test"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", probe],
        cwd=ROOT,
        env=_inner_env("1/1"),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
