"""SPEC-hm-light-lane-bench — the stage-4 bench runner, exercised offline.

No test here calls a model. A fake `claude` executable (written per test session) applies the
task's reference overlay, records what it saw, writes a transcript and prints a CLI-shaped result.
Expected numbers come from the fake and from the fixture on disk, never from the runner.
"""

from __future__ import annotations

import atexit
import contextlib
import fcntl
import functools
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from harness_maker import economics, intent
from harness_maker.economics import TokenUsage, TurnRecord

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bench_light_lane.py"
_TASKS = _ROOT / "scripts" / "bench" / "tasks"
_FIXTURE = _ROOT / "scripts" / "bench" / "timeparse"
_SESSION_KEYS = ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID", "INTEGRATION", "HM_BENCH_TEST")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None, f"missing {_SCRIPT}"
    assert spec.loader is not None, f"missing {_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    return _load()


@functools.cache
def _stub_dir() -> Path:
    """A `claude` that always fails, for PATH: a regression that forgets --claude-bin must stop
    here instead of launching (and paying for) the real CLI."""
    directory = Path(tempfile.mkdtemp(prefix="hm-no-claude-"))
    atexit.register(shutil.rmtree, directory, ignore_errors=True)
    stub = directory / "claude"
    stub.write_text(f"#!{sys.executable}\nraise SystemExit(99)\n")
    stub.chmod(0o755)
    return directory


@pytest.fixture(autouse=True)
def _no_real_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", f"{_stub_dir()}{os.pathsep}{os.environ['PATH']}")


# The fake reads its settings from a JSON file beside it, not from the environment: the runner
# hands the agent an allowlisted environment, so FAKE_* variables would never arrive.
_FAKE_AGENT = r"""
import hashlib, json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path

cfg = json.loads(Path(__file__).with_suffix(".json").read_text())
if "--version" in sys.argv[1:]:
    print(cfg.get("version", "fake 1.0"))
    sys.exit(0)
mode = cfg.get("mode", "normal")
if cfg.get("marker"):
    Path(cfg["marker"]).write_text("called")
argv = sys.argv[1:]
prompt = argv[argv.index("-p") + 1]
arm = "hm" if prompt.startswith("/hm:spec ") else "plain"
text = prompt.removeprefix("/hm:spec ").strip()
tasks = Path(cfg["tasks_dir"])
task = next(d for d in sorted(tasks.iterdir()) if (d / "prompt.md").read_text().strip() == text)
cwd = Path.cwd()
if mode == "sleep":
    pids = Path(cfg["pid_dir"])
    pids.mkdir(parents=True, exist_ok=True)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    (pids / f"child-{child.pid}").write_text("")
    (pids / f"agent-{os.getpid()}").write_text("")
    time.sleep(300)
files = {}
for p in sorted(cwd.rglob("*")):
    rel = p.relative_to(cwd)
    if p.is_file() and ".git" not in rel.parts:
        files[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
status = subprocess.run(
    ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, check=True
).stdout
log = Path(cfg["log_dir"])
log.mkdir(parents=True, exist_ok=True)
(log / f"{arm}-{task.name}.json").write_text(
    json.dumps({"argv": argv, "files": files, "status": status, "env": dict(os.environ)})
)
shutil.copytree(task / "reference", cwd, dirs_exist_ok=True)
session = str(uuid.uuid4())
scale = 4 if arm == "hm" else 1
if mode != "lose_cost":
    proj = Path(cfg["transcript_root"]) / re.sub(r"[/._]", "-", str(cwd))
    proj.mkdir(parents=True, exist_ok=True)
    line = {
        "type": "assistant", "timestamp": "2026-10-14T00:00:00Z", "cwd": str(cwd),
        "sessionId": session, "note": cfg.get("transcript_text", ""),
        "message": {"id": "msg_" + session, "model": "claude-sonnet-5-5",
                    "usage": {"input_tokens": 1000 * scale, "output_tokens": 100 * scale}},
    }
    (proj / f"{session}.jsonl").write_text(json.dumps(line) + "\n")
if mode == "leak":
    print("reading " + str(tasks / task.name / "hidden"))
result = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
          "session_id": session}
if mode != "lose_cost":
    result["total_cost_usd"] = 0.4 if arm == "hm" else 0.1
print(json.dumps(result))
"""


def _write_fake_agent(directory: Path, **cfg: Any) -> Path:
    path = directory / "fake-claude"
    path.write_text(f"#!{sys.executable}\n{_FAKE_AGENT}")
    path.chmod(0o755)
    path.with_suffix(".json").write_text(json.dumps({"tasks_dir": str(_TASKS), **cfg}))
    return path


def _env(home: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_KEYS}
    env["HOME"] = str(home)
    env["PATH"] = f"{_stub_dir()}{os.pathsep}{env['PATH']}"
    env.update(extra)
    return env


def _run_bench(
    base: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    command: str = "run",
    **cfg: Any,
) -> dict[str, Any]:
    """One offline `run` through the real CLI with the fake agent; paths live under `base`."""
    home, out, logs, troot = (base / n for n in ("home", "out", "logs", "transcripts"))
    home.mkdir(exist_ok=True)
    fake = _write_fake_agent(
        base, log_dir=str(logs), transcript_root=str(troot), pid_dir=str(base / "pids"), **cfg
    )
    full_env = _env(home, INTEGRATION="1", HM_BENCH_TEST="1", **(env or {}))
    argv = [sys.executable, str(_SCRIPT), command, "--out", str(out), "--claude-bin", str(fake)]
    argv += ["--transcript-root", str(troot), "--guard-top", str(base), *args]
    proc = subprocess.run(
        argv, env=full_env, capture_output=True, text=True, timeout=600, check=False
    )
    path = out / "results.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return {"proc": proc, "rows": rows, "logs": logs, "out": out}


@pytest.fixture(scope="module")
def bench_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One offline run of t1 in both arms, with decoy secrets in the runner's environment."""
    base = tmp_path_factory.mktemp("bench-run")
    env = {
        "GITHUB_TOKEN": "ghp_decoy", "AWS_SECRET_ACCESS_KEY": "aws_decoy", "CLAUDECODE": "1",
        "ANTHROPIC_API_KEY": "sk-decoy", "HTTPS_PROXY": "http://proxy.invalid:1",
        "LC_ALL": "C.UTF-8", "HM_BENCH_PASS": "passed-through",
    }  # fmt: skip
    got = _run_bench(base, ["--tasks", "t1", "--runs", "1", "--pass-env", "HM_BENCH_PASS"], env=env)
    assert got["rows"], got["proc"].stdout + got["proc"].stderr
    return got


def _tree(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and "__pycache__" not in rel.parts and ".pytest_cache" not in rel.parts:
            files[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


# --- AC-001 -----------------------------------------------------------------------------------


def test_run_refuses_without_integration(tmp_path: Path) -> None:
    marker = tmp_path / "called"
    fake = _write_fake_agent(tmp_path, marker=str(marker))
    out = tmp_path / "out"
    out.mkdir()
    env = _env(tmp_path)
    argv = [sys.executable, str(_SCRIPT), "run", "--out", str(out), "--claude-bin", str(fake)]
    proc = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 2
    assert "INTEGRATION=1" in proc.stderr
    assert not marker.exists()
    assert not any(out.iterdir())


# --- AC-002 -----------------------------------------------------------------------------------


def test_five_tasks_ship(bench: ModuleType) -> None:
    assert [t.id for t in bench.load_tasks()] == ["t1", "t2", "t3", "t4", "t5"]


@pytest.mark.parametrize("task_id", ["t1", "t2", "t3", "t4", "t5"])
def test_hidden_tests_discriminate(bench: ModuleType, task_id: str, tmp_path: Path) -> None:
    task = next(t for t in bench.load_tasks() if t.id == task_id)
    assert bench.check_task(task, tmp_path) == []


# --- AC-003 -----------------------------------------------------------------------------------


def test_arms_differ_only_by_harness_and_prefix(bench_run: dict[str, Any]) -> None:
    logs: Path = bench_run["logs"]
    plain = json.loads((logs / "plain-t1.json").read_text())
    hm = json.loads((logs / "hm-t1.json").read_text())

    assert plain["files"] == _tree(_FIXTURE)
    extra = set(hm["files"]) - set(plain["files"])
    assert extra, "the hm arm carries no harness"
    assert all(p.startswith(".claude/") or p in {"CLAUDE.md", ".gitignore"} for p in extra)
    assert {p: hm["files"][p] for p in plain["files"]} == plain["files"]
    assert ".claude/commands/hm/spec.md" in extra

    assert plain["status"] == hm["status"] == ""
    hidden = _tree(_TASKS / "t1" / "hidden")
    reference = _tree(_TASKS / "t1" / "reference")
    for files in (plain["files"], hm["files"]):
        assert not any("hidden" in Path(p).parts for p in files)
        assert not set(hidden.values()) & set(files.values())
        assert all(files.get(rel) != digest for rel, digest in reference.items())

    pa, ha = plain["argv"], hm["argv"]
    assert len(pa) == len(ha)
    diffs = [i for i, (a, b) in enumerate(zip(pa, ha, strict=True)) if a != b]
    assert diffs == [pa.index("-p") + 1]
    assert ha[diffs[0]] == "/hm:spec " + pa[diffs[0]]


def test_agent_runs_with_project_only_settings_and_a_spend_cap(bench_run: dict[str, Any]) -> None:
    for arm in ("plain", "hm"):
        argv = json.loads((bench_run["logs"] / f"{arm}-t1.json").read_text())["argv"]
        assert argv[argv.index("--setting-sources") + 1] == "project,local"
        assert "--strict-mcp-config" in argv
        assert argv[argv.index("--max-budget-usd") + 1] == "5"
    assert {r["max_budget_usd"] for r in bench_run["rows"]} == {5.0}


def test_agent_gets_an_allowlisted_environment(bench_run: dict[str, Any]) -> None:
    for arm in ("plain", "hm"):
        env = json.loads((bench_run["logs"] / f"{arm}-t1.json").read_text())["env"]
        assert not {"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "CLAUDECODE"} & set(env)
        assert env["ANTHROPIC_API_KEY"] == "sk-decoy"
        assert env["HTTPS_PROXY"] == "http://proxy.invalid:1"
        assert env["LC_ALL"] == "C.UTF-8"
        assert env["HM_BENCH_PASS"] == "passed-through"  # named by --pass-env
        assert "PATH" in env


def test_agent_env_unit(bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "SECRET_X": "1",
        "CLAUDECODE": "1",
        "HM_SESSION_ID": "s",
        "LC_CTYPE": "C",
    }.items():
        monkeypatch.setenv(key, value)
    env = bench.agent_env()
    assert "SECRET_X" not in env
    assert env["LC_CTYPE"] == "C"
    passed = bench.agent_env(("SECRET_X", "CLAUDECODE", "HM_SESSION_ID"))
    assert passed["SECRET_X"] == "1"
    assert not {"CLAUDECODE", "HM_SESSION_ID"} & set(
        passed
    )  # session vars are stripped even if named


# --- AC-004 -----------------------------------------------------------------------------------


def _line(cwd: Path, msg_id: str, usage: dict[str, int], *, sidechain: bool = False) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": "2026-10-14T00:00:00Z",
            "cwd": str(cwd),
            "sessionId": "s1",
            "isSidechain": sidechain,
            "message": {"id": msg_id, "model": "claude-sonnet-5-5", "usage": usage},
        }
    )


def _priced(usage: TokenUsage) -> float:
    turn = TurnRecord(
        session_id="s1",
        ts=datetime(2026, 10, 14, tzinfo=UTC),
        model="claude-sonnet-5-5",
        usage=usage,
    )
    return economics.price_turn(turn).total_usd


def test_cost_comes_from_cli_and_transcripts(bench: ModuleType, tmp_path: Path) -> None:
    work = tmp_path / "runs" / "t1-hm-1-abc" / "work"
    work.mkdir(parents=True)
    root = tmp_path / "transcripts"
    proj = root / str(work).replace("/", "-").replace(".", "-").replace("_", "-")
    (proj / "s1" / "subagents").mkdir(parents=True)
    main_usage = {"input_tokens": 2000, "output_tokens": 300, "cache_read_input_tokens": 50000}
    sub_usage = {"input_tokens": 700, "output_tokens": 90, "cache_creation_input_tokens": 4000}
    (proj / "s1.jsonl").write_text(_line(work, "m1", main_usage) + "\n")
    (proj / "s1" / "subagents" / "agent-a.jsonl").write_text(
        _line(work, "m2", sub_usage, sidechain=True) + "\n"
    )
    foreign = tmp_path / "runs" / "t1-plain-1-def" / "work"
    fproj = root / str(foreign).replace("/", "-").replace(".", "-").replace("_", "-")
    fproj.mkdir(parents=True)
    (fproj / "f.jsonl").write_text(_line(foreign, "m3", {"output_tokens": 10**6}) + "\n")

    expected = _priced(
        TokenUsage(input_tokens=2000, output_tokens=300, cache_read_tokens=50000)
    ) + _priced(TokenUsage(input_tokens=700, output_tokens=90, cache_write_5m_tokens=4000))
    spend = bench.transcript_cost(work, root)
    assert spend.usd == pytest.approx(expected)
    assert (spend.turns, spend.subagent_turns) == (2, 1)

    assert bench.pick_cost(0.25, spend) == (0.25, "cli")
    assert bench.pick_cost(None, spend) == (pytest.approx(expected), "transcript")


def test_a_lost_cost_with_an_empty_transcript_is_unknown_not_free(bench: ModuleType) -> None:
    assert bench.pick_cost(None, bench.Spend(0.0, 0, 0)) == (None, "unknown")
    assert bench.pick_cost(0.0, bench.Spend(0.0, 0, 0)) == (0.0, "cli")


def test_unknown_cost_run_is_recorded_unpriced_and_left_out_of_the_mean(tmp_path: Path) -> None:
    got = _run_bench(
        tmp_path, ["--tasks", "t1", "--runs", "1", "--arms", "plain"], mode="lose_cost"
    )
    (row,) = got["rows"]
    assert (row["cost_usd"], row["cost_source"], row["transcript_turns"]) == (None, "unknown", 0)
    assert "runs with no cost" in got["proc"].stdout


def test_cli_result_is_parsed_from_the_last_result_line(bench: ModuleType) -> None:
    stdout = (
        'noise\n{"type": "system"}\n{"type": "result", "total_cost_usd": 1.5, "num_turns": 7}\n'
    )
    assert bench.parse_cli_result(stdout)["total_cost_usd"] == 1.5
    assert bench.parse_cli_result("not json") is None


# --- AC-005 -----------------------------------------------------------------------------------

_SABOTAGE = (
    "def pytest_collection_modifyitems(config, items):\n"
    "    for item in items:\n"
    "        item.runtest = lambda: None\n"
)


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("reference", True),
        ("pristine", False),
        ("syntax_error", False),
        ("sabotage", False),
        ("ini_addopts", True),
        ("shadow_pytest", True),
        ("sitecustomize", True),
        ("skip_via_package", False),
        ("hung_import", False),
    ],
)
def test_grading_is_strict_and_isolated(
    bench: ModuleType, tmp_path: Path, case: str, expected: bool
) -> None:
    task = next(t for t in bench.load_tasks() if t.id == "t1")
    work = tmp_path / "work"
    bench.copy_fixture(work)
    if case not in ("pristine", "sabotage"):
        bench.apply_overlay(work, task.reference_dir)
    if case == "syntax_error":
        target = work / "timeparse" / "format.py"
        target.write_text(target.read_text() + "\ndef broken(:\n")
    if case == "sabotage":
        (work / "conftest.py").write_text(_SABOTAGE)
    if case == "ini_addopts":
        for where in (work, work / "timeparse"):
            (where / "pytest.ini").write_text("[pytest]\naddopts = -k nothing_matches\n")
    if case == "shadow_pytest":
        (work / "pytest.py").write_text("raise SystemExit('shadowed pytest')\n")
    if case == "sitecustomize":
        marker = tmp_path / "sitecustomize-ran"
        (work / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').close()\n")
    package = work / "timeparse" / "__init__.py"
    if case == "skip_via_package":
        package.write_text(
            package.read_text() + "\nimport pytest\npytest.skip('x', allow_module_level=True)\n"
        )
    if case == "hung_import":
        package.write_text(package.read_text() + "\nimport time\ntime.sleep(300)\n")
    timeout = 5 if case == "hung_import" else bench.GRADE_TIMEOUT_S
    grade = bench.grade(work, task.hidden_dir, tmp_path / "grade", timeout_s=timeout)
    assert grade.passed is expected
    if case == "syntax_error":
        assert grade.errors >= 1
    if case == "sitecustomize":
        assert not marker.exists()


# --- AC-006 -----------------------------------------------------------------------------------


def _rows(
    arm: str,
    cost: float | dict[str, float],
    *,
    tasks: tuple[str, ...] = ("t1", "t2"),
    runs: int = 3,
    fail: int = 0,
    status: str = "ok",
    transcript: float | dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Rows for `arm`; `cost` (and `transcript`, default equal) may differ per task."""

    def at(value: float | dict[str, float], task: str) -> float:
        return value[task] if isinstance(value, dict) else value

    rows = []
    for task in tasks:
        for rep in range(1, runs + 1):
            rows.append(
                {
                    "bench_hash": "b1",
                    "harness_sha": "h1",
                    "model": "claude-sonnet-5-5",
                    "task": task,
                    "arm": arm,
                    "rep": rep,
                    "status": status,
                    "cost_usd": at(cost, task),
                    "transcript_cost_usd": at(cost if transcript is None else transcript, task),
                    "wall_s": 10.0,
                    "passed": True,
                }
            )
    for row in rows[:fail]:
        row["passed"] = False
    return rows


def _with(rows: list[dict[str, Any]], **fields: Any) -> list[dict[str, Any]]:
    for row in rows[:1]:
        row.update(fields)
    return rows


_VERDICT_CASES = [
    (_rows("plain", 0.10) + _rows("hm", 0.40), 4.0, "met"),
    (_rows("plain", 0.10) + _rows("hm", 2.20), 22.0, "missed"),
    (_rows("plain", 0.10) + _rows("hm", 0.30, fail=1), 3.0, "missed"),
    (_rows("plain", 0.10) + _rows("hm", 0.50), 5.0, "met"),
    (_rows("plain", 0.10), None, "no_data"),
    (_rows("plain", 0.10) + _rows("hm", 0.40)[:-1], None, "no_data"),
    (
        _rows("plain", 0.10)
        + _rows("hm", 0.40)
        + _rows("hm", 9.0, tasks=("t1",), runs=1, status="setup_error"),
        4.0,
        "met",
    ),
    (
        _rows("plain", 0.10)
        + _rows("hm", 0.40)
        + _rows("hm", 9.0, tasks=("t1",), runs=1, status="runner_error"),
        4.0,
        "met",
    ),
    # Unequal costs, by hand: plain mean (0.1 + 0.3) / 2 = 0.2, hm mean (0.2 + 1.0) / 2 = 0.6.
    (_rows("plain", {"t1": 0.1, "t2": 0.3}) + _rows("hm", {"t1": 0.2, "t2": 1.0}), 3.0, "met"),
    # Mean of per-task ratios would be (10 + 1.11) / 2 = 5.56 and miss; ratio of means is 2.0.
    (_rows("plain", {"t1": 0.1, "t2": 0.9}) + _rows("hm", {"t1": 1.0, "t2": 1.0}), 2.0, "met"),
    # 5.004 is above the target and is what gets recorded (3 places), not a rounded 5.0.
    (_rows("plain", 1.0) + _rows("hm", 5.004), 5.004, "missed"),
    # The CLI ratio is 4.0 and the larger transcript ratio 4.8 is within 20%: the judged (and
    # recorded) number is 4.8; at 5.4 it is over the target.
    (_rows("plain", 0.10) + _rows("hm", 0.40, transcript=0.48), 4.8, "met"),
    (_rows("plain", 0.10) + _rows("hm", 0.46, transcript=0.54), 5.4, "missed"),
    # CLI and transcript disagree by more than 20%: the number is not trusted, nothing to record.
    (_rows("plain", 0.10) + _rows("hm", 0.40, transcript=1.20), None, "suspect"),
    # A met that rests on a budget-capped or possibly leaking run is not trusted either.
    (
        _rows("plain", 0.10) + _with(_rows("hm", 0.40), subtype="error_max_budget_usd"),
        None,
        "suspect",
    ),
    (_rows("plain", 0.10) + _with(_rows("hm", 0.40), leak_suspect=True), None, "suspect"),
]


@pytest.mark.parametrize(
    ("rows", "ratio", "verdict"),
    _VERDICT_CASES,
    ids=[
        "met", "ratio-above", "pass-rate-drop", "inclusive", "no-hm", "unbalanced", "setup",
        "runner-error", "unequal-costs", "mean-of-ratios", "unrounded", "transcript-within",
        "transcript-decides", "suspect", "budget-capped", "leak",
    ],
)  # fmt: skip
def test_report_verdict(
    bench: ModuleType, rows: list[dict[str, Any]], ratio: float | None, verdict: str
) -> None:
    summary = bench.summarize(rows)
    assert summary["ratio"] == ratio
    assert summary["verdict"] == verdict


def test_unpriced_runs_stay_out_of_the_cost_mean_and_never_make_a_free_arm(
    bench: ModuleType,
) -> None:
    hm = _rows("hm", 0.40)
    for row in hm[:2]:
        row["cost_usd"] = None
    summary = bench.summarize(_rows("plain", 0.10) + hm)
    assert (summary["ratio"], summary["verdict"], summary["cost_unknown"]) == (4.0, "met", 2)
    assert "no cost" in bench.render_report(summary)

    for row in hm:
        row["cost_usd"] = None
    assert bench.summarize(_rows("plain", 0.10) + hm)["verdict"] == "no_data"


# --- AC-007 -----------------------------------------------------------------------------------


def test_record_command_parses(bench: ModuleType) -> None:
    summary = bench.summarize(_rows("plain", 0.10) + _rows("hm", 0.40))
    lines = bench.render_report(summary).splitlines()
    record = next(line for line in lines if "intent metric record" in line)
    tokens = shlex.split(record)
    ns = intent._parser().parse_args(tokens[tokens.index("intent") + 1 :])
    assert (ns.cmd, ns.verb, ns.id) == ("metric", "record", "hm_cost_ratio_small")
    assert ns.value == summary["ratio"] == 4.0
    for part in ("b1", "h1", "claude-sonnet-5-5", "plain 6/6", "hm 6/6", "met"):
        assert part in ns.evidence
    assert lines[-1] == "hm_cost_ratio_small=4.000"
    assert tokens[tokens.index("--value") + 1] == "4.000"


def test_the_recorded_value_is_the_number_the_verdict_used(bench: ModuleType) -> None:
    rows = _rows("plain", 0.10) + _rows("hm", 0.46, transcript=0.54)
    summary = bench.summarize(rows)
    assert summary["verdict"] == "missed"
    lines = bench.render_report(summary).splitlines()
    tokens = shlex.split(next(line for line in lines if "intent metric record" in line))
    assert tokens[tokens.index("--value") + 1] == "5.400"
    assert lines[-1] == "hm_cost_ratio_small=5.400"


@pytest.mark.parametrize(
    "extra", [{"transcript": 1.20}, {"transcript": None}], ids=["suspect", "no-hm"]
)
def test_suspect_and_no_data_record_nothing(bench: ModuleType, extra: dict[str, Any]) -> None:
    rows = _rows("plain", 0.10)
    if extra["transcript"]:
        rows += _rows("hm", 0.40, transcript=extra["transcript"])
    summary = bench.summarize(rows)
    assert summary["verdict"] in ("suspect", "no_data")
    lines = bench.render_report(summary).splitlines()
    assert not any("intent metric record" in line for line in lines)
    assert lines[-1] == "hm_cost_ratio_small=n/a"
    assert bench.record_argv(summary) is None


def test_no_ratio_prints_no_record_command(bench: ModuleType) -> None:
    lines = bench.render_report(bench.summarize(_rows("plain", 0.10))).splitlines()
    assert not any("intent metric record" in line for line in lines)
    assert lines[-1] == "hm_cost_ratio_small=n/a"


# --- AC-008 -----------------------------------------------------------------------------------


def test_target_matches_the_intent_metric(bench: ModuleType) -> None:
    data = yaml.safe_load((_ROOT / ".claude" / "intent.yaml").read_text(encoding="utf-8"))
    metric = next(m for m in data["metrics"] if m["id"] == "hm_cost_ratio_small")
    assert metric["target"] == bench.TARGET
    assert metric["higher_is_better"] is False


# --- AC-009 -----------------------------------------------------------------------------------


def test_resume_skips_completed_cells(bench: ModuleType) -> None:
    done = [
        {"task": "t1", "arm": "plain", "rep": 1, "status": "ok"},
        {"task": "t1", "arm": "hm", "rep": 1, "status": "agent_error"},
        {"task": "t2", "arm": "plain", "rep": 1, "status": "setup_error"},
        {"task": "t2", "arm": "hm", "rep": 1, "status": "runner_error"},
    ]
    pending = bench.pending_cells(done, ["t1", "t2"], ["plain", "hm"], 1)
    assert pending == [("t2", "plain", 1), ("t2", "hm", 1)]


@pytest.mark.parametrize("field", ["bench_hash", "harness_sha", "model", "runner_hash"])
def test_report_refuses_mixed_results(bench: ModuleType, tmp_path: Path, field: str) -> None:
    rows = _rows("plain", 0.10) + _rows("hm", 0.40)
    for row in rows:
        row["runner_hash"] = "r1"
    rows[0][field] = "other"
    with pytest.raises(bench.MixedResultsError):
        bench.summarize(rows)
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert bench.main(["report", "--out", str(tmp_path)]) == 2


# --- AC-010 -----------------------------------------------------------------------------------


def test_offline_end_to_end_run(bench_run: dict[str, Any]) -> None:
    proc = bench_run["proc"]
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert lines[-1] == "hm_cost_ratio_small=4.000"
    assert "verdict: met" in proc.stdout
    rows = bench_run["rows"]
    assert sorted((r["task"], r["arm"], r["rep"]) for r in rows) == [
        ("t1", "hm", 1),
        ("t1", "plain", 1),
    ]
    assert all(r["passed"] and r["status"] == "ok" and r["cost_source"] == "cli" for r in rows)
    assert all(r["transcript_cost_usd"] > 0 for r in rows)
    assert not any(r["leak_suspect"] for r in rows)
    assert len({r["runner_hash"] for r in rows}) == 1
    assert "leak suspects" not in proc.stdout


def test_hidden_tests_are_graded_outside_the_results_dir(bench_run: dict[str, Any]) -> None:
    out: Path = bench_run["out"]
    hidden_names = {p.name for p in (_TASKS / "t1" / "hidden").iterdir()}
    assert not any(p.name in hidden_names or p.name == "hidden" for p in out.rglob("*"))
    assert all(
        (out / "runs").stat().st_mode & 0o077 == 0
        and Path(r["run_dir"]).stat().st_mode & 0o077 == 0
        for r in bench_run["rows"]
    )


def test_agent_output_naming_the_hidden_path_is_flagged(tmp_path: Path) -> None:
    got = _run_bench(tmp_path, ["--tasks", "t1", "--runs", "1", "--arms", "plain"], mode="leak")
    (row,) = got["rows"]
    assert row["leak_suspect"] is True
    assert "leak suspects: 1" in got["proc"].stdout


def test_report_reprints_without_a_model(bench_run: dict[str, Any], tmp_path: Path) -> None:
    out = tmp_path / "copy"
    shutil.copytree(bench_run["out"], out)
    argv = [sys.executable, str(_SCRIPT), "report", "--out", str(out), "--json"]
    proc = subprocess.run(
        argv, env=_env(tmp_path), capture_output=True, text=True, timeout=120, check=False
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert (summary["ratio"], summary["verdict"]) == (4.0, "met")
    assert summary["record_argv"][:4] == ["hm", "intent", "metric", "record"]


# --- AC-011 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("layout", "refused"),
    [
        ("git", True),
        ("claude_md", True),
        ("claude_local", True),
        ("claude_dir", True),
        ("clean", False),
    ],
)
def test_out_dir_with_project_context_is_refused(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str, refused: bool
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    if layout == "git":
        (parent / ".git").mkdir()
    elif layout == "claude_md":
        (parent / "CLAUDE.md").write_text("# project\n")
    elif layout == "claude_local":
        (parent / "CLAUDE.local.md").write_text("# mine\n")
    elif layout == "claude_dir":
        (parent / ".claude").mkdir()
    out = parent / "out"
    assert (bench.guard_out_dir(out, top=tmp_path) is not None) is refused
    if refused:
        monkeypatch.setenv("INTEGRATION", "1")
        assert bench.main(["run", "--out", str(out), "--claude-bin", "/nonexistent"]) == 2
        assert not out.exists()


def test_guard_top_is_hidden_and_only_honoured_under_the_test_flag(
    bench: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    helped = subprocess.run(
        [sys.executable, str(_SCRIPT), "run", "--help"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert "--max-budget-usd" in helped.stdout
    assert "guard-top" not in helped.stdout
    (tmp_path / "CLAUDE.md").write_text("# project\n")
    out = tmp_path / "out"
    argv = ["run", "--out", str(out), "--guard-top", str(out), "--runs", "0", "--arms", "plain"]
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.delenv("HM_BENCH_TEST", raising=False)
    assert bench.main(argv) == 2
    assert "refusing --out" in capsys.readouterr().err
    monkeypatch.setenv("HM_BENCH_TEST", "1")
    bench.main(argv)
    assert "refusing --out" not in capsys.readouterr().err


# --- review hardening -------------------------------------------------------------------------


def _alive(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return state != "Z"


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM], ids=["sigint", "sigterm"])
def test_stop_signal_kills_live_agents_and_skips_queued_cells(tmp_path: Path, sig: int) -> None:
    pids = tmp_path / "pids"
    fake = _write_fake_agent(
        tmp_path, mode="sleep", pid_dir=str(pids), log_dir=str(tmp_path / "l"),
        transcript_root=str(tmp_path / "t"),
    )  # fmt: skip
    out = tmp_path / "out"
    argv = [sys.executable, str(_SCRIPT), "run", "--out", str(out), "--claude-bin", str(fake)]
    argv += ["--guard-top", str(tmp_path), "--tasks", "t1,t2,t3", "--arms", "plain"]
    argv += ["--runs", "1", "--jobs", "2", "--transcript-root", str(tmp_path / "t")]
    env = _env(tmp_path, INTEGRATION="1", HM_BENCH_TEST="1")
    proc = subprocess.Popen(
        argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        deadline = time.monotonic() + 90
        while len(list(pids.glob("agent-*"))) < 2 and time.monotonic() < deadline:
            time.sleep(0.2)
        assert len(list(pids.glob("agent-*"))) == 2, "two agents never started"
        proc.send_signal(sig)
        code = proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
        for path in pids.glob("*"):
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(path.name.split("-")[1]), signal.SIGKILL)
    assert code == 130
    time.sleep(0.5)
    started = [int(p.name.split("-")[1]) for p in pids.glob("*")]
    assert len(started) == 4, "the queued third cell must not start (2 agents + 2 children)"
    assert not any(_alive(pid) for pid in started)
    results = out / "results.jsonl"
    assert not results.exists() or results.read_text() == ""


def test_a_second_runner_on_the_same_out_is_refused(
    bench: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.setenv("HM_BENCH_TEST", "1")
    with (out / ".run.lock").open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        code = bench.main(["run", "--out", str(out), "--guard-top", str(tmp_path), "--runs", "1"])
    assert code == 2
    assert "another runner" in capsys.readouterr().err
    assert not (out / "results.jsonl").exists()


def _inprocess_args(out: Path, tmp_path: Path, *extra: str) -> list[str]:
    argv = ["run", "--out", str(out), "--guard-top", str(tmp_path), "--claude-bin", "unused"]
    return [*argv, "--arms", "plain", "--tasks", "t1,t2,t3", "--runs", "1", *extra]


def _canned_row(task: Any, arm: str, rep: int, opts: Any, **over: Any) -> dict[str, Any]:
    row = {
        "bench_hash": opts.bench_hash, "harness_sha": opts.harness_sha, "model": opts.model,
        "runner_hash": opts.runner_hash, "task": task.id, "arm": arm, "rep": rep,
        "status": "ok", "passed": True, "cost_usd": 0.1, "transcript_cost_usd": 0.1,
    }  # fmt: skip
    return {**row, **over}


@pytest.fixture
def inprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.setenv("HM_BENCH_TEST", "1")


def test_one_crashing_cell_is_recorded_and_the_grid_continues(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inprocess: None
) -> None:
    calls: list[tuple[str, str, int]] = []

    def crashing(task: Any, arm: str, rep: int, opts: Any) -> dict[str, Any]:
        calls.append((task.id, arm, rep))
        if task.id == "t1":
            raise RuntimeError("unexpected")
        return _canned_row(task, arm, rep, opts)

    monkeypatch.setattr(bench, "run_cell", crashing)
    out = tmp_path / "out"
    bench.main(_inprocess_args(out, tmp_path))
    status = {r["task"]: r["status"] for r in bench.read_rows(out)}
    assert status == {"t1": "runner_error", "t2": "ok", "t3": "ok"}
    errors = [r for r in bench.read_rows(out) if r["status"] == "runner_error"]
    assert "RuntimeError: unexpected" in errors[0]["error"]

    calls.clear()

    def recording_cell(t: Any, a: str, r: int, o: Path) -> dict[str, Any]:
        calls.append((t.id, a, r))
        return _canned_row(t, a, r, o)

    monkeypatch.setattr(bench, "run_cell", recording_cell)
    bench.main(_inprocess_args(out, tmp_path))
    assert calls == [("t1", "plain", 1)]


def test_total_budget_stops_scheduling_new_cells(
    bench: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    inprocess: None,
) -> None:
    monkeypatch.setattr(bench, "run_cell", lambda t, a, r, o: _canned_row(t, a, r, o))
    out = tmp_path / "out"
    bench.main(_inprocess_args(out, tmp_path, "--total-budget-usd", "0.15"))
    assert len(bench.read_rows(out)) == 2
    assert (
        "stopped: spend passed --total-budget-usd 0.15; 1 cell(s) not run"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize(
    ("change", "extra"),
    [
        ({"harness_sha": "old"}, []),
        ({"model": "claude-other"}, []),
        ({"bench_hash": "old"}, []),
        ({}, ["--max-turns", "7"]),
        ({}, ["--max-budget-usd", "1"]),
        ({}, ["--timeout-s", "9"]),
        ({}, ["--pass-env", "SOME_NAME"]),
    ],
    ids=["harness", "model", "bench", "max-turns", "max-budget", "timeout", "pass-env"],
)
def test_resume_refuses_rows_from_another_setup_before_spending(
    bench: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    inprocess: None,
    change: dict[str, str],
    extra: list[str],
) -> None:
    out = tmp_path / "out"
    seen: list[Any] = []

    def record(task: Any, arm: str, rep: int, opts: Any) -> dict[str, Any]:
        seen.append(opts)
        return _canned_row(task, arm, rep, opts, **change)

    monkeypatch.setattr(bench, "run_cell", record)
    bench.main([*_inprocess_args(out, tmp_path), "--tasks", "t1"])
    assert len(seen) == 1
    capsys.readouterr()

    calls: list[str] = []

    def recording_cell(t: Any, a: str, r: int, o: Path) -> dict[str, Any]:
        calls.append(t.id)
        return {}

    monkeypatch.setattr(bench, "run_cell", recording_cell)
    code = bench.main([*_inprocess_args(out, tmp_path), *extra])
    assert code == 2
    assert not calls
    assert "refusing to resume" in capsys.readouterr().err


def test_resume_with_the_same_setup_continues(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inprocess: None
) -> None:
    out = tmp_path / "out"
    monkeypatch.setattr(bench, "run_cell", lambda t, a, r, o: _canned_row(t, a, r, o))
    bench.main([*_inprocess_args(out, tmp_path), "--tasks", "t1"])
    assert bench.main(_inprocess_args(out, tmp_path)) == 0
    assert sorted(r["task"] for r in bench.read_rows(out)) == ["t1", "t2", "t3"]


def test_runner_hash_covers_every_setting_that_changes_an_arm(bench: ModuleType) -> None:
    base = bench.runner_hash("m", 400, 1800, 5.0)
    assert base == bench.runner_hash("m", 400, 1800, 5.0)
    variants = [
        ("m2", 400, 1800, 5.0),
        ("m", 7, 1800, 5.0),
        ("m", 400, 9, 5.0),
        ("m", 400, 1800, 1.0),
        ("m", 400, 1800, 5.0, ("SOME_NAME",)),
        ("m", 400, 1800, 5.0, (), "claude 9.9"),
    ]
    assert all(bench.runner_hash(*v) != base for v in variants)


def test_setup_failure_keeps_the_failing_commands_stderr(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(_work: Path, _template: Path) -> None:
        raise subprocess.CalledProcessError(1, ["git", "commit"], stderr=b"fatal: no identity set")

    monkeypatch.setattr(bench, "prepare_work", failing)
    task = bench.load_tasks()[0]
    opts = bench.Options(
        out=tmp_path, claude_bin="unused", model="m", max_turns=1, timeout_s=1,
        transcript_root=tmp_path, bench_hash="b", harness_sha="h", templates={"plain": tmp_path},
    )  # fmt: skip
    row = bench.run_cell(task, "plain", 1, opts)
    assert row["status"] == "setup_error"
    assert "fatal: no identity set" in row["error"]


def test_torn_results_line_is_skipped_and_the_next_row_survives(
    bench: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bench.append_row(tmp_path, {"task": "t1", "arm": "plain", "rep": 1, "status": "ok"})
    with (tmp_path / "results.jsonl").open("a") as handle:
        handle.write('{"task": "t1", "ar')  # a crash mid-write: no closing brace, no newline
    bench.append_row(tmp_path, {"task": "t2", "arm": "plain", "rep": 1, "status": "ok"})
    rows = bench.read_rows(tmp_path)
    assert [r["task"] for r in rows] == ["t1", "t2"]
    assert "unparsable" in capsys.readouterr().err
    capsys.readouterr()
    assert bench.main(["report", "--out", str(tmp_path)]) == 0
    assert "verdict: no_data" in capsys.readouterr().out


def test_append_row_is_one_write_on_an_append_fd(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[int] = []
    flags: list[int] = []
    real_write, real_open = os.write, os.open

    def spy_write(fd: int, data: bytes) -> int:
        writes.append(len(data))
        return real_write(fd, data)

    def spy_open(path: Any, flag: int, *rest: Any) -> int:
        flags.append(flag)
        return real_open(path, flag, *rest)

    monkeypatch.setattr(bench.os, "write", spy_write)
    monkeypatch.setattr(bench.os, "open", spy_open)
    bench.append_row(tmp_path, {"task": "t1", "payload": "x" * 5000})
    assert len(writes) == 1
    assert flags
    assert flags[0] & os.O_APPEND


def test_snapshot_is_private_and_matches_the_checkout(bench: ModuleType) -> None:
    snap, digest = bench.snapshot_bench()
    try:
        assert digest == bench.bench_hash()
        assert snap.parent.stat().st_mode & 0o077 == 0
        assert (snap / "tasks" / "t1" / "hidden").is_dir()
    finally:
        shutil.rmtree(snap.parent)


def test_harness_sha_changes_with_the_uncommitted_diff(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def git(*args: str) -> None:
        subprocess.run([*bench._GIT, *args], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    (tmp_path / "f.txt").write_text("one\n")
    git("add", "-A")
    git("commit", "-q", "-m", "x")
    monkeypatch.setattr(bench, "REPO_ROOT", tmp_path)
    clean = bench.harness_sha()
    assert "dirty" not in clean
    (tmp_path / "f.txt").write_text("two\n")
    first = bench.harness_sha()
    (tmp_path / "f.txt").write_text("three\n")
    second = bench.harness_sha()
    assert first.startswith(f"{clean}-dirty-")
    assert second.startswith(f"{clean}-dirty-")
    assert first != second


# --- check_task: every hidden test must fail on pristine unless it is a marked guard -------------


def _guard_task(tmp_path: Path, guards: frozenset[str], bench: ModuleType) -> Any:
    hidden, reference = tmp_path / "hidden", tmp_path / "reference"
    (reference / "timeparse").mkdir(parents=True)
    hidden.mkdir()
    (reference / "timeparse" / "extra.py").write_text("VALUE = 1\n")
    (hidden / "test_x.py").write_text(
        "from timeparse import parse_duration\n\n\n"
        "def test_old():\n    assert parse_duration('1h') == 3600\n\n\n"
        "def test_new():\n    from timeparse.extra import VALUE\n    assert VALUE == 1\n"
    )
    return bench.Task("tx", "prompt", hidden, reference, guards)


@pytest.mark.parametrize(
    ("guards", "expect"),
    [
        (frozenset({"test_old"}), []),
        (frozenset(), ["test_old passes on the pristine fixture and is not a guard"]),
        (frozenset({"test_old", "test_new"}), ["guard test_new does not pass on the pristine"]),
        (frozenset({"test_old", "test_ghost"}), ["names test_ghost, which no hidden test defines"]),
    ],
    ids=["marked", "unmarked", "guard-fails", "ghost-guard"],
)
def test_check_task_requires_every_unmarked_test_to_fail_on_pristine(
    bench: ModuleType, tmp_path: Path, guards: frozenset[str], expect: list[str]
) -> None:
    task = _guard_task(tmp_path, guards, bench)
    lines: list[str] = []
    problems = bench.check_task(task, tmp_path / "scratch", log=lines.append)
    assert len(problems) == len(expect)
    assert all(any(e in p for p in problems) for e in expect)
    assert any("test_old" in line and "passed" in line for line in lines)
    assert any("test_new" in line for line in lines)


# --- confirmation pass ------------------------------------------------------------------------


def _wait_dead(pid: int, seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + seconds
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not _alive(pid)


def test_a_stop_flag_set_before_the_agent_is_registered_still_kills_it(
    bench: ModuleType, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    bench.STOP.set()
    try:
        start = time.monotonic()
        argv = [sys.executable, "-c", "import time; time.sleep(300)"]
        _out, _err, code = bench._invoke(argv, work, 30)
    finally:
        bench.STOP.clear()
    assert code == -signal.SIGKILL
    assert time.monotonic() - start < 15


def test_a_straggler_holding_the_output_does_not_stall_or_outlive_the_cell(
    bench: ModuleType, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    pidfile = tmp_path / "straggler.pid"
    script = (
        "import subprocess, sys\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(p.pid))\n"
        "print('done')\n"
    )
    start = time.monotonic()
    out, _err, code = bench._invoke([sys.executable, "-c", script], work, 20)
    assert (code, out.strip()) == (0, "done")
    assert time.monotonic() - start < 15
    assert _wait_dead(int(pidfile.read_text()))


def test_a_hung_agent_times_out_and_its_group_is_killed(tmp_path: Path) -> None:
    got = _run_bench(
        tmp_path,
        ["--tasks", "t1", "--runs", "1", "--arms", "plain", "--timeout-s", "3"],
        mode="sleep",
    )
    (row,) = got["rows"]
    assert (row["status"], row["exit_code"]) == ("timeout", None)
    pids = [int(p.name.split("-")[1]) for p in (tmp_path / "pids").glob("*")]
    assert len(pids) == 2
    assert all(_wait_dead(pid) for pid in pids)


def _cell_options(bench: ModuleType, tmp_path: Path, **cfg: Any) -> tuple[Any, Any]:
    troot = tmp_path / "transcripts"
    fake = _write_fake_agent(
        tmp_path, log_dir=str(tmp_path / "logs"), transcript_root=str(troot), **cfg
    )
    template = tmp_path / "tpl"
    bench.build_template(template, "plain")
    (tmp_path / "out").mkdir()
    opts = bench.Options(
        out=tmp_path / "out", claude_bin=str(fake), model="claude-sonnet-5-5", max_turns=5,
        timeout_s=120, transcript_root=troot, bench_hash="b", harness_sha="h",
        templates={"plain": template},
    )  # fmt: skip
    return next(t for t in bench.load_tasks() if t.id == "t1"), opts


def test_a_crash_after_the_agent_ran_still_records_what_it_cost(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task, opts = _cell_options(bench, tmp_path)

    def boom(*_args: Any, **_kw: Any) -> Any:
        raise RuntimeError("grader crashed")

    monkeypatch.setattr(bench, "grade", boom)
    row = bench.run_cell(task, "plain", 1, opts)
    assert row["status"] == "runner_error"
    assert "grader crashed" in row["error"]
    assert row["cli_cost_usd"] == 0.1
    assert row["transcript_cost_usd"] > 0
    assert Path(row["run_dir"]).is_dir()
    assert bench._spent(row) == 0.1


def test_spent_falls_back_from_cost_to_cli_to_transcript(bench: ModuleType) -> None:
    assert bench._spent({"cost_usd": 0.5, "cli_cost_usd": 0.4, "transcript_cost_usd": 0.3}) == 0.5
    assert bench._spent({"cost_usd": None, "cli_cost_usd": 0.4, "transcript_cost_usd": 0.3}) == 0.4
    assert bench._spent({"cost_usd": None, "cli_cost_usd": None, "transcript_cost_usd": 0.3}) == 0.3
    assert bench._spent({"status": "runner_error"}) == 0.0


def test_transcript_root_follows_claude_config_dir(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert bench.default_transcript_root() == bench.economics_source.default_transcript_root()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert bench.default_transcript_root() == tmp_path / "projects"


def test_canary_passes_when_the_marker_is_absent(tmp_path: Path) -> None:
    got = _run_bench(tmp_path, ["--marker", "CANARY-7f3a"], command="canary")
    assert got["proc"].returncode == 0, got["proc"].stderr
    assert "canary ok" in got["proc"].stdout


def test_canary_fails_when_the_marker_reaches_the_transcript(tmp_path: Path) -> None:
    got = _run_bench(
        tmp_path,
        ["--marker", "CANARY-7f3a"],
        command="canary",
        transcript_text="memory says CANARY-7f3a",
    )
    assert got["proc"].returncode == 1
    assert "canary FAIL" in got["proc"].stdout


def test_canary_without_a_transcript_is_inconclusive_not_ok(tmp_path: Path) -> None:
    got = _run_bench(tmp_path, ["--marker", "CANARY-7f3a"], command="canary", mode="lose_cost")
    assert got["proc"].returncode == 2
    assert "inconclusive" in got["proc"].stderr


def test_canary_needs_integration(bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTEGRATION", raising=False)
    assert bench.main(["canary", "--marker", "x", "--claude-bin", "/nonexistent"]) == 2


def test_runner_hash_follows_the_claude_version(tmp_path: Path) -> None:
    args = ["--tasks", "t1", "--runs", "1", "--arms", "plain"]
    hashes = {}
    for name, version in (("a", "claude 1.0"), ("b", "claude 2.0"), ("c", "claude 1.0")):
        (tmp_path / name).mkdir()
        got = _run_bench(tmp_path / name, args, version=version)
        hashes[name] = got["rows"][0]["runner_hash"]
    assert hashes["a"] != hashes["b"]
    assert hashes["a"] == hashes["c"]


def test_harness_sha_covers_untracked_files_but_not_ignored_ones(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def git(*args: str) -> None:
        subprocess.run([*bench._GIT, *args], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "f.txt").write_text("one\n")
    git("add", "-A")
    git("commit", "-q", "-m", "x")
    monkeypatch.setattr(bench, "REPO_ROOT", tmp_path)
    clean = bench.harness_sha()
    (tmp_path / "ignored.txt").write_text("noise\n")
    assert bench.harness_sha() == clean
    (tmp_path / "new.py").write_text("a = 1\n")
    first = bench.harness_sha()
    (tmp_path / "new.py").write_text("a = 2\n")
    second = bench.harness_sha()
    assert first.startswith(f"{clean}-dirty-")
    assert second.startswith(f"{clean}-dirty-")
    assert first != second


def test_budget_capped_runs_are_counted_and_reported(bench: ModuleType) -> None:
    rows = _rows("plain", 0.10) + _with(_rows("hm", 0.40), subtype="error_max_budget_usd")
    summary = bench.summarize(rows)
    assert summary["budget_capped"] == 1
    assert "budget-capped runs: 1" in bench.render_report(summary)
    assert summary["verdict"] == "suspect"
