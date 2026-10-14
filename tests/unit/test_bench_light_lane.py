"""SPEC-hm-light-lane-bench — the stage-4 bench runner, exercised offline.

No test here calls a model. A fake `claude` executable (written per test session) applies the
task's reference overlay, records what it saw, writes a transcript and prints a CLI-shaped result.
Expected numbers come from the fake and from the fixture on disk, never from the runner.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
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
_SESSION_KEYS = ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID", "INTEGRATION")


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


_FAKE_AGENT = r"""
import hashlib, json, os, re, shutil, subprocess, sys, uuid
from pathlib import Path

if os.environ.get("FAKE_MARKER"):
    Path(os.environ["FAKE_MARKER"]).write_text("called")
argv = sys.argv[1:]
prompt = argv[argv.index("-p") + 1]
arm = "hm" if prompt.startswith("/hm:spec ") else "plain"
text = prompt.removeprefix("/hm:spec ").strip()
tasks = Path(os.environ["FAKE_TASKS_DIR"])
task = next(d for d in sorted(tasks.iterdir()) if (d / "prompt.md").read_text().strip() == text)
cwd = Path.cwd()
files = {}
for p in sorted(cwd.rglob("*")):
    rel = p.relative_to(cwd)
    if p.is_file() and ".git" not in rel.parts:
        files[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
status = subprocess.run(
    ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, check=True
).stdout
log = Path(os.environ["FAKE_LOG_DIR"])
log.mkdir(parents=True, exist_ok=True)
(log / f"{arm}-{task.name}.json").write_text(
    json.dumps({"argv": argv, "files": files, "status": status})
)
shutil.copytree(task / "reference", cwd, dirs_exist_ok=True)
session = str(uuid.uuid4())
proj = Path(os.environ["FAKE_TRANSCRIPT_ROOT"]) / re.sub(r"[/._]", "-", str(cwd))
proj.mkdir(parents=True, exist_ok=True)
line = {
    "type": "assistant", "timestamp": "2026-10-14T00:00:00Z", "cwd": str(cwd),
    "sessionId": session,
    "message": {"id": "msg_" + session, "model": "claude-sonnet-5-5",
                "usage": {"input_tokens": 1000, "output_tokens": 100}},
}
(proj / f"{session}.jsonl").write_text(json.dumps(line) + "\n")
cost = 0.4 if arm == "hm" else 0.1
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "num_turns": 3, "session_id": session, "total_cost_usd": cost}))
"""


def _write_fake_agent(directory: Path) -> Path:
    path = directory / "fake-claude"
    path.write_text(f"#!{sys.executable}\n{_FAKE_AGENT}")
    path.chmod(0o755)
    return path


def _env(home: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_KEYS}
    env["HOME"] = str(home)
    env.update(extra)
    return env


@pytest.fixture(scope="module")
def bench_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One offline run of t1 in both arms through the real CLI, shared by several tests."""
    base = tmp_path_factory.mktemp("bench-run")
    home, out, logs, troot = (base / n for n in ("home", "out", "logs", "transcripts"))
    home.mkdir()
    fake = _write_fake_agent(base)
    env = _env(
        home,
        INTEGRATION="1",
        FAKE_TASKS_DIR=str(_TASKS),
        FAKE_LOG_DIR=str(logs),
        FAKE_TRANSCRIPT_ROOT=str(troot),
    )
    argv = [sys.executable, str(_SCRIPT), "run", "--tasks", "t1", "--runs", "1"]
    argv += ["--out", str(out), "--claude-bin", str(fake), "--transcript-root", str(troot)]
    argv += ["--guard-top", str(base)]  # the host's /tmp may hold a stray CLAUDE.md
    proc = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=600, check=False)
    assert (out / "results.jsonl").exists(), proc.stdout + proc.stderr
    rows = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
    return {"proc": proc, "rows": rows, "logs": logs, "out": out}


def _tree(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and "__pycache__" not in rel.parts and ".pytest_cache" not in rel.parts:
            files[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


# --- AC-001 -----------------------------------------------------------------------------------


def test_run_refuses_without_integration(tmp_path: Path) -> None:
    fake = _write_fake_agent(tmp_path)
    marker = tmp_path / "called"
    out = tmp_path / "out"
    out.mkdir()
    env = _env(tmp_path, FAKE_MARKER=str(marker), FAKE_TASKS_DIR=str(_TASKS))
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
    hidden_names = {p.name for p in (_TASKS / "t1" / "hidden").iterdir()}
    for files in (plain["files"], hm["files"]):
        assert not hidden_names & {Path(p).name for p in files}

    pa, ha = plain["argv"], hm["argv"]
    assert len(pa) == len(ha)
    diffs = [i for i, (a, b) in enumerate(zip(pa, ha, strict=True)) if a != b]
    assert diffs == [pa.index("-p") + 1]
    assert ha[diffs[0]] == "/hm:spec " + pa[diffs[0]]


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

    assert bench.pick_cost(0.25, spend.usd) == (0.25, "cli")
    assert bench.pick_cost(None, spend.usd) == (pytest.approx(expected), "transcript")


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
    [("reference", True), ("pristine", False), ("syntax_error", False), ("sabotage", False)],
)
def test_grading_is_strict_and_isolated(
    bench: ModuleType, tmp_path: Path, case: str, expected: bool
) -> None:
    task = next(t for t in bench.load_tasks() if t.id == "t1")
    work = tmp_path / "work"
    bench.copy_fixture(work)
    if case in ("reference", "syntax_error"):
        bench.apply_overlay(work, task.reference_dir)
    if case == "syntax_error":
        target = work / "timeparse" / "format.py"
        target.write_text(target.read_text() + "\ndef broken(:\n")
    if case == "sabotage":
        (work / "conftest.py").write_text(_SABOTAGE)
    grade = bench.grade(work, task.hidden_dir, tmp_path / "grade")
    assert grade.passed is expected
    if case == "syntax_error":
        assert grade.errors >= 1


# --- AC-006 -----------------------------------------------------------------------------------


def _rows(
    arm: str,
    cost: float,
    *,
    tasks: tuple[str, ...] = ("t1", "t2"),
    runs: int = 3,
    fail: int = 0,
    status: str = "ok",
) -> list[dict[str, Any]]:
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
                    "cost_usd": cost,
                    "transcript_cost_usd": cost,
                    "wall_s": 10.0,
                    "passed": True,
                }
            )
    for row in rows[:fail]:
        row["passed"] = False
    return rows


_VERDICT_CASES = [
    (_rows("plain", 0.10) + _rows("hm", 0.40), 4.0, "met"),
    (_rows("plain", 0.10) + _rows("hm", 2.20), 22.0, "missed"),
    (_rows("plain", 0.10) + _rows("hm", 0.30, fail=1), 3.0, "missed"),
    (_rows("plain", 0.10) + _rows("hm", 0.50), 5.0, "met"),
    (_rows("plain", 0.10), None, "no_data"),
    (_rows("plain", 0.10) + _rows("hm", 0.40)[:-1], 4.0, "no_data"),
    (
        _rows("plain", 0.10)
        + _rows("hm", 0.40)
        + _rows("hm", 9.0, tasks=("t1",), runs=1, status="setup_error"),
        4.0,
        "met",
    ),
]


@pytest.mark.parametrize(
    ("rows", "ratio", "verdict"),
    _VERDICT_CASES,
    ids=["met", "ratio-above", "pass-rate-drop", "inclusive", "no-hm", "unbalanced", "setup"],
)
def test_report_verdict(
    bench: ModuleType, rows: list[dict[str, Any]], ratio: float | None, verdict: str
) -> None:
    summary = bench.summarize(rows)
    assert summary["ratio"] == ratio
    assert summary["verdict"] == verdict


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
    assert lines[-1] == "hm_cost_ratio_small=4.0"


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
    ]
    pending = bench.pending_cells(done, ["t1", "t2"], ["plain", "hm"], 1)
    assert pending == [("t2", "plain", 1), ("t2", "hm", 1)]


@pytest.mark.parametrize("field", ["bench_hash", "harness_sha", "model"])
def test_report_refuses_mixed_results(bench: ModuleType, tmp_path: Path, field: str) -> None:
    rows = _rows("plain", 0.10) + _rows("hm", 0.40)
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
    assert lines[-1] == "hm_cost_ratio_small=4.0"
    assert "verdict: met" in proc.stdout
    rows = bench_run["rows"]
    assert sorted((r["task"], r["arm"], r["rep"]) for r in rows) == [
        ("t1", "hm", 1),
        ("t1", "plain", 1),
    ]
    assert all(r["passed"] and r["status"] == "ok" and r["cost_source"] == "cli" for r in rows)
    assert all(r["transcript_cost_usd"] > 0 for r in rows)


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
    ("layout", "refused"), [("git", True), ("claude_md", True), ("clean", False)]
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
    out = parent / "out"
    assert (bench.guard_out_dir(out, top=tmp_path) is not None) is refused
    if refused:
        monkeypatch.setenv("INTEGRATION", "1")
        assert bench.main(["run", "--out", str(out), "--claude-bin", "/nonexistent"]) == 2
        assert not out.exists()
