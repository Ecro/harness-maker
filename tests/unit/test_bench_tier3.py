"""SPEC-hm-eval-tier3 — tier 3 of the hm eval and its multi-session runner, offline.

No test here calls a model. A fake `claude` (written per test) follows a per-call script: it
records what it saw, copies the overlay the test chose into its work dir, writes a transcript
and prints a CLI-shaped result. Expected values come from the fake, from the task files on disk
and from hash values recorded before tier 3 existed, never from the runner.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bench_light_lane.py"
_BENCH = _ROOT / "scripts" / "bench"
_TIER3 = _BENCH / "tier3"
_TASK_IDS = ["t13", "t14", "t15", "t16", "t17", "t18", "t19", "t20", "t21"]
_COPY_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
CAREFUL = (
    "Before changing code, read the documentation and every caller that the change could affect."
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    return _load()


@pytest.fixture(autouse=True)
def _no_real_claude(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A `claude` on PATH that always fails: a test that forgets --claude-bin stops here."""
    stub_dir = tmp_path_factory.getbasetemp() / "no-claude"
    stub = stub_dir / "claude"
    if not stub.exists():
        stub_dir.mkdir(exist_ok=True)
        stub.write_text(f"#!{sys.executable}\nraise SystemExit(99)\n")
        stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_dir}{os.pathsep}{os.environ['PATH']}")


def _task(bench: ModuleType, task_id: str) -> Any:
    return next(t for t in bench.load_tier3_tasks() if t.id == task_id)


def _norm(text: str) -> str:
    return " ".join(text.split())


# --- the fake agent ---------------------------------------------------------------------------

# One step per call, in call order: {"overlay": dir, "write": {rel: text}, "stage": [rel],
# "exit": n, "error": bool, "cost": usd}. The fake also logs, per call, its argv, cwd, prompt,
# the HEAD commit's files and message and `git status --porcelain`.
_FAKE = r"""
import json, os, re, shutil, subprocess, sys, uuid
from pathlib import Path

cfg = json.loads(Path(__file__).with_suffix(".json").read_text())
if "--version" in sys.argv[1:]:
    print("fake 1.0")
    sys.exit(0)
argv = sys.argv[1:]
log = Path(cfg["log"])
calls = log.read_text().splitlines() if log.exists() else []
step = cfg["steps"][len(calls)] if len(calls) < len(cfg["steps"]) else {}
cwd = Path.cwd()

def git(*args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout

seen = {
    "argv": argv, "cwd": str(cwd), "prompt": argv[argv.index("-p") + 1],
    "head_files": git("show", "--name-only", "--format=", "HEAD").split(),
    "head_message": git("log", "-1", "--format=%s").strip(),
    "status": git("status", "--porcelain"),
    "locale": (cwd / "timeparse" / "locale.py").read_text()
    if (cwd / "timeparse" / "locale.py").exists() else None,
}
with log.open("a") as handle:
    handle.write(json.dumps(seen) + "\n")
if step.get("overlay"):
    shutil.copytree(step["overlay"], cwd, dirs_exist_ok=True)
for rel, text in step.get("write", {}).items():
    (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
    (cwd / rel).write_text(text)
if step.get("stage"):
    subprocess.run(["git", "add", "--", *step["stage"]], cwd=cwd, check=True)
session = str(uuid.uuid4())
proj = Path(cfg["transcript_root"]) / re.sub(r"[/._]", "-", str(cwd))
proj.mkdir(parents=True, exist_ok=True)
line = {
    "type": "assistant", "timestamp": "2026-10-15T00:00:00Z", "cwd": str(cwd),
    "sessionId": session,
    "message": {"id": "msg_" + session, "model": "claude-sonnet-5-5",
                "usage": {"input_tokens": 1000, "output_tokens": 100}},
}
(proj / f"{session}.jsonl").write_text(json.dumps(line) + "\n")
result = {"type": "result", "subtype": "success", "is_error": bool(step.get("error")),
          "num_turns": 2, "session_id": session, "total_cost_usd": step.get("cost", 0.1)}
print(json.dumps(result))
sys.exit(step.get("exit", 0))
"""


def _fake(directory: Path, steps: list[dict[str, Any]]) -> tuple[Path, Path]:
    path = directory / "fake-claude"
    path.write_text(f"#!{sys.executable}\n{_FAKE}")
    path.chmod(0o755)
    log = directory / "calls.jsonl"
    cfg = {"log": str(log), "steps": steps, "transcript_root": str(directory / "transcripts")}
    path.with_suffix(".json").write_text(json.dumps(cfg))
    return path, log


def _calls(log: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def _options(bench: ModuleType, tmp_path: Path, task: Any, steps: list[dict[str, Any]]) -> Any:
    """Options for one in-process run_cell of `task` in the plain template, every arm mapped to
    it, so a test of the session loop never renders the harness."""
    fake, _log = _fake(tmp_path, steps)
    template = tmp_path / "tpl"
    bench.build_template(template, "plain", seed=task.seed_dir, base=task.base_dir)
    (tmp_path / "out").mkdir()
    keys = {bench.template_key(task, arm) for arm in bench.ALL_ARMS}
    return bench.Options(
        out=tmp_path / "out", claude_bin=str(fake), model="m", max_turns=5, timeout_s=120,
        transcript_root=tmp_path / "transcripts", bench_hash="b", harness_sha="h",
        templates=dict.fromkeys(keys, template), judge=False,
        tier3_hash=bench.tier3_hash(),
    )  # fmt: skip


def _run(bench: ModuleType, tmp_path: Path, task_id: str, steps: list[dict[str, Any]],
         arm: str = "plain") -> tuple[dict[str, Any], list[dict[str, Any]]]:  # fmt: skip
    task = _task(bench, task_id)
    opts = _options(bench, tmp_path, task, steps)
    row = bench.run_cell(task, arm, 1, opts)
    assert row["status"] not in ("setup_error", "runner_error", "interrupted"), row
    return row, _calls(tmp_path / "calls.jsonl")


def _reference(task_id: str) -> str:
    return str(_TIER3 / "tasks" / task_id / "reference")


# --- AC-001: every tier-3 task discriminates --------------------------------------------------


def test_tier3_ships_nine_tasks_in_four_families(bench: ModuleType) -> None:
    tasks = bench.load_tier3_tasks()
    assert [t.id for t in tasks] == _TASK_IDS
    assert {t.tier for t in tasks} == {3}
    assert all(t.base_dir == _TIER3 / "base" for t in tasks)
    assert all(t.careless_dir is not None and t.careless_dir.is_dir() for t in tasks)
    assert [t.id for t in tasks if len(t.sessions) == 2] == ["t19", "t20", "t21"]
    assert [t.id for t in tasks if any(s.overlay for s in t.sessions)] == ["t20"]
    assert [t.id for t in tasks if t.guard] == ["t21"]
    assert all(t.trap is None for t in tasks)
    assert sorted(t.id for t in bench.load_tasks()) == sorted(f"t{n}" for n in range(1, 13))


@pytest.mark.parametrize("task_id", _TASK_IDS)
def test_tier3_tasks_discriminate(bench: ModuleType, task_id: str, tmp_path: Path) -> None:
    assert bench.check_task(_task(bench, task_id), tmp_path) == []


def _task_copy(tmp_path: Path, task_id: str) -> Path:
    """A private tier-3 tree holding the base and one task, for tests that break a task."""
    root = tmp_path / "tier3"
    shutil.copytree(_TIER3 / "base", root / "base", ignore=_COPY_IGNORE)
    shutil.copytree(_TIER3 / "tasks" / task_id, root / "tasks" / task_id, ignore=_COPY_IGNORE)
    return root / "tasks"


def test_a_careless_overlay_that_passes_is_a_problem(bench: ModuleType, tmp_path: Path) -> None:
    tasks = _task_copy(tmp_path, "t16")
    careless = tasks / "t16" / "careless"
    shutil.rmtree(careless)
    shutil.copytree(tasks / "t16" / "reference", careless)
    task = bench.load_tasks(tasks)[0]
    problems = bench.check_task(task, tmp_path / "scratch")
    assert any("careless" in p and "passes the hidden tests" in p for p in problems), problems

    (careless / "timeparse" / "parse.py").write_text("raise ImportError('broken')\n")
    problems = bench.check_task(task, tmp_path / "scratch2")
    assert any("careless" in p and "visible" in p for p in problems), problems


# --- AC-002: every hidden test cites a findable sentence --------------------------------------


def _hidden_docstrings(task_dir: Path) -> dict[str, str]:
    found = {}
    for path in sorted((task_dir / "hidden").glob("test_*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                found[node.name] = ast.get_docstring(node) or ""
    return found


@pytest.mark.parametrize("task_id", _TASK_IDS)
def test_every_tier3_hidden_test_cites_a_findable_sentence(
    bench: ModuleType, task_id: str, tmp_path: Path
) -> None:
    task = _task(bench, task_id)
    tree = tmp_path / "tree"
    bench.start_tree(tree, task)
    docstrings = _hidden_docstrings(_TIER3 / "tasks" / task_id)
    assert docstrings
    for name, doc in docstrings.items():
        quote, sep, home = doc.rpartition("Source:")
        assert sep, f"{name} names no source"
        home = home.strip()
        if home == "prompt":
            text = (_TIER3 / "tasks" / task_id / "prompt.md").read_text(encoding="utf-8")
        elif home.startswith("session "):
            path = _TIER3 / "tasks" / task_id / "sessions" / home.split()[1] / "prompt.md"
            text = path.read_text(encoding="utf-8")
        else:
            assert not home.startswith(("/", "..")), home
            text = (tree / home).read_text(encoding="utf-8")
        assert _norm(quote), f"{name}: empty quote"
        assert _norm(quote) in _norm(text), f"{name}: quote not in {home}"
    assert bench.citation_problems(task, tree) == []


def test_a_quote_missing_from_its_home_is_a_problem(bench: ModuleType, tmp_path: Path) -> None:
    tasks = _task_copy(tmp_path, "t14")
    hidden = tasks / "t14" / "hidden" / "test_t14_decimals.py"
    text = hidden.read_text(encoding="utf-8")
    assert "never rounded or truncated." in text
    hidden.write_text(text.replace("never rounded or truncated.", "always rounded."))
    task = bench.load_tasks(tasks)[0]
    tree = tmp_path / "tree"
    bench.start_tree(tree, task)
    problems = bench.citation_problems(task, tree)
    assert problems
    assert all("docs/DECISIONS.md" in p for p in problems), problems

    hidden.write_text(text.replace("    Source: prompt\n", ""))
    problems = bench.citation_problems(bench.load_tasks(tasks)[0], tree)
    assert any("test_decimal_amounts_are_accepted" in p and "Source" in p for p in problems)

    hidden.write_text(text.replace("Source: prompt", "Source: docs/NOWHERE.md"))
    problems = bench.citation_problems(bench.load_tasks(tasks)[0], tree)
    assert any("docs/NOWHERE.md" in p for p in problems), problems


# --- AC-003: the prompt lint ------------------------------------------------------------------


@pytest.mark.parametrize("task_id", _TASK_IDS)
def test_tier3_prompts_carry_no_harness_word(bench: ModuleType, task_id: str) -> None:
    task = _task(bench, task_id)
    assert task.session_prompts
    for prompt in task.session_prompts:
        assert bench.prompt_lint(prompt) == [], prompt


@pytest.mark.parametrize(
    ("prompt", "count"),
    [
        ("Fix issue #21 in the format module.", 0),
        ("Write a spec first, then fix it.", 1),
        ("Make a Plan and remember the cap.", 2),
        ("See docs/DECISIONS.md.", 1),
        ("Cover AC-1 and note this.", 2),
        ("The planner keeps its specification.", 0),
        ("Keep it in memory; acceptance first; no non-goal.", 3),
    ],
)
def test_the_prompt_lint_rejects_each_listed_word(
    bench: ModuleType, prompt: str, count: int
) -> None:
    assert len(bench.prompt_lint(prompt)) == count, bench.prompt_lint(prompt)


# --- AC-004: the differential oracles equal the unchanged start tree --------------------------

_ORACLE_CHECK = textwrap.dedent(
    """
    import importlib.util, sys
    from pathlib import Path

    def hidden(path):
        spec = importlib.util.spec_from_file_location("hidden_" + Path(path).stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    from timeparse import format_duration, parse_duration
    from timeparse.pack import pack

    t16, t18, t13 = (hidden(p) for p in sys.argv[1:4])
    bad = [v for v, packed in t16._PACKED.items() if pack(v) != packed]
    corpus = t18._corpus()
    bad += [t for t in corpus if t18._outcome(parse_duration, t) != t18._outcome(t18._original, t)]
    bad += [s for s in t13._SWEEP if format_duration(s) != t13._compact(s)]
    print(len(t16._PACKED), len(corpus), len(t13._SWEEP), len(bad))
    """
)


def test_goldens_match_the_unchanged_start_tree(bench: ModuleType, tmp_path: Path) -> None:
    tree = tmp_path / "start"
    bench.start_tree(tree, _task(bench, "t16"))
    hidden = [
        _TIER3 / "tasks" / "t16" / "hidden" / "test_t16_weeks.py",
        _TIER3 / "tasks" / "t18" / "hidden" / "test_t18_one_regex.py",
        _TIER3 / "tasks" / "t13" / "hidden" / "test_t13_issue_21.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-c", _ORACLE_CHECK, *map(str, hidden)], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tree)}, capture_output=True, text=True,
        timeout=300, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    packed, corpus, sweep, bad = map(int, proc.stdout.split())
    assert packed >= 25
    assert corpus >= 5000
    assert sweep >= 1000
    assert bad == 0


# --- AC-005: the multi-session runner ---------------------------------------------------------


def test_sessions_run_in_order_as_fresh_processes_in_one_work_dir(
    bench: ModuleType, tmp_path: Path
) -> None:
    steps = [{"write": {"NOTES.md": "cap: 30 days\n"}, "cost": 0.1},
             {"overlay": _reference("t19"), "cost": 0.2}]  # fmt: skip
    row, calls = _run(bench, tmp_path, "t19", steps)
    task = _task(bench, "t19")
    assert [c["prompt"] for c in calls] == list(task.session_prompts)
    assert calls[0]["cwd"] == calls[1]["cwd"] == str(Path(row["run_dir"]) / "work")
    for call in calls:
        assert "--continue" not in call["argv"]
        assert "--resume" not in call["argv"]
    first, second = (list(c["argv"]) for c in calls)
    index = first.index("-p") + 1
    first[index] = second[index] = "<prompt>"
    assert first == second
    assert row["status"] == "ok"
    assert row["outcome"] == "solved"
    assert row["passed"] is True
    assert row["tier3_hash"] == bench.tier3_hash()
    assert [s["cost_usd"] for s in row["sessions"]] == [0.1, 0.2]
    assert [s["status"] for s in row["sessions"]] == ["ok", "ok"]
    assert row["cost_usd"] == pytest.approx(0.3)
    assert row["num_turns"] == 4
    assert row["stopped_at"] is None
    assert row["overlay_clobbered"] == []
    assert row["wall_s"] == pytest.approx(sum(s["wall_s"] for s in row["sessions"]), abs=0.2)
    hm = [bench.prompt_for(task, "hm", i) for i in range(2)]
    assert hm == ["/hm:spec " + p for p in task.session_prompts]


def test_the_teammate_commit_holds_only_the_overlay_paths(
    bench: ModuleType, tmp_path: Path
) -> None:
    edited = "# the arm's own uncommitted work\n"
    steps: list[dict[str, Any]] = [
        {"write": {"timeparse/format.py": edited, "scratch.txt": "wip\n"},
         "stage": ["timeparse/format.py"]},
        {"overlay": _reference("t20")},
    ]  # fmt: skip
    row, calls = _run(bench, tmp_path, "t20", steps)
    second = calls[1]
    assert second["head_message"] == "teammate"
    assert second["head_files"] == ["timeparse/locale.py"]
    overlay = _TIER3 / "tasks" / "t20" / "sessions" / "2" / "overlay" / "timeparse" / "locale.py"
    assert second["locale"] == overlay.read_text(encoding="utf-8")
    status = second["status"].splitlines()
    assert "M  timeparse/format.py" in status, status  # still staged, never committed
    assert "?? scratch.txt" in status, status
    assert row["overlay_clobbered"] == []
    assert row["outcome"] == "solved"


def test_an_overlay_the_arm_already_wrote_is_recorded_as_clobbered(
    bench: ModuleType, tmp_path: Path
) -> None:
    steps: list[dict[str, Any]] = [
        {"write": {"timeparse/locale.py": "NAMES = {}\n"}},
        {"overlay": _reference("t20")},
    ]
    row, calls = _run(bench, tmp_path, "t20", steps)
    assert row["overlay_clobbered"] == ["timeparse/locale.py"]
    assert calls[1]["locale"] != "NAMES = {}\n"
    assert calls[1]["head_files"] == ["timeparse/locale.py"]


def test_a_failed_session_stops_the_run_and_grades_once(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graded: list[Path] = []
    original = bench.grade

    def counting(work: Path, tests_dir: Path, *args: Any, **kwargs: Any) -> Any:
        if tests_dir.name == "hidden":
            graded.append(work)
        return original(work, tests_dir, *args, **kwargs)

    monkeypatch.setattr(bench, "grade", counting)
    row, calls = _run(bench, tmp_path, "t20", [{"error": True, "exit": 1}, {}])
    assert len(calls) == 1
    assert row["status"] == "agent_error"
    assert row["stopped_at"] == 1
    assert [s["status"] for s in row["sessions"]] == ["agent_error"]
    assert row["outcome"] == "stalled", "the overlay was never applied, so it is no change"
    assert graded.count(Path(row["run_dir"]) / "work") == 1


# --- AC-006: tier-3 hash, gate and rows -------------------------------------------------------


def test_tier3_hash_covers_tier3_files_only(bench: ModuleType, tmp_path: Path) -> None:
    copy = tmp_path / "bench"
    shutil.copytree(_BENCH, copy, ignore=_COPY_IGNORE)
    digest, bench_digest = bench.tier3_hash(copy), bench.bench_hash(copy)
    assert digest == bench.tier3_hash()
    assert len(digest) == 12
    (copy / "tasks" / "t6" / "prompt.md").write_text("changed\n")
    assert bench.tier3_hash(copy) == digest
    (copy / "tier3" / "tasks" / "t13" / "prompt.md").write_text("changed\n")
    assert bench.tier3_hash(copy) != digest
    edited = bench.tier3_hash(copy)
    (copy / "tier3" / "base" / "docs" / "DECISIONS.md").write_text("changed\n")
    assert bench.tier3_hash(copy) != edited
    shutil.rmtree(copy / "tasks" / "t6")
    shutil.copytree(_BENCH / "tasks" / "t6", copy / "tasks" / "t6", ignore=_COPY_IGNORE)
    assert bench.bench_hash(copy) == bench_digest, "a tier-3 edit leaves bench_hash alone"


@pytest.fixture
def inprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.setenv("IS_SANDBOX", "1")
    monkeypatch.setenv("HM_BENCH_TEST", "1")


def _canned(task: Any, arm: str, rep: int, opts: Any) -> dict[str, Any]:
    return {
        "bench_hash": opts.bench_hash, "harness_sha": opts.harness_sha, "model": opts.model,
        "runner_hash": opts.runner_hash, "tier": task.tier, "task": task.id, "arm": arm,
        "rep": rep, "status": "ok", "passed": True, "outcome": "solved", "cost_usd": 0.1,
        "transcript_cost_usd": 0.1, "tier3_hash": opts.tier3_hash,
    }  # fmt: skip


def test_a_tier3_run_with_the_hm_arm_needs_the_signoff(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inprocess: None
) -> None:
    calls: list[tuple[str, str]] = []

    def cell(task: Any, arm: str, rep: int, opts: Any) -> dict[str, Any]:
        calls.append((task.id, arm))
        return _canned(task, arm, rep, opts)

    monkeypatch.setattr(bench, "run_cell", cell)
    monkeypatch.setattr(bench, "build_template", lambda *a, **k: None)
    monkeypatch.setattr(bench, "check_cli_fresh", lambda *a, **k: None)
    signoff = tmp_path / "tier3-signoff.json"
    monkeypatch.setattr(bench, "TIER3_SIGNOFF_FILE", signoff)
    current = {"tier3_hash": bench.tier3_hash(), "signed_by": "dri", "signed_at": "2026-10-16"}

    def run(name: str, arms: str) -> int:
        out = tmp_path / name
        argv = ["run", "--out", str(out), "--guard-top", str(tmp_path), "--claude-bin", "unused"]
        code = int(bench.main([*argv, "--tier", "3", "--runs", "1", "--arms", arms]))
        if code == 2:
            assert not out.exists(), "a refused run copies nothing"
        return code

    assert run("no-signoff", "plain,hm") == 2
    signoff.write_text(json.dumps({**current, "tier3_hash": "000000000000"}))
    assert run("stale", "plain,hm") == 2
    signoff.write_text(json.dumps({**current, "signed_by": " "}))
    assert run("unsigned", "plain,hm") == 2
    assert calls == []
    signoff.unlink()
    assert run("pilot", "plain") == 0
    assert sorted(calls) == [(t, "plain") for t in _TASK_IDS]
    calls.clear()
    signoff.write_text(json.dumps(current))
    assert run("signed", "plain,hm") == 0
    assert len(calls) == 18
    argv = ["run", "--out", str(tmp_path / "all"), "--guard-top", str(tmp_path)]
    argv += ["--claude-bin", "unused", "--tier", "all", "--tasks", "t13", "--arms", "plain"]
    assert int(bench.main(argv)) == 2, "--tier all keeps meaning tiers 1 and 2"


def test_tier3_rows_record_their_hash_and_never_mix(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], inprocess: None,
) -> None:  # fmt: skip
    (tmp_path / "cell").mkdir()
    row, _calls_seen = _run(bench, tmp_path / "cell", "t13", [{"overlay": _reference("t13")}])
    assert row["tier3_hash"] == bench.tier3_hash()
    assert row["tier"] == 3
    other = {**row, "tier3_hash": "000000000000", "rep": 2}
    with pytest.raises(bench.MixedResultsError):
        bench.ensure_consistent([row, other])
    bench.ensure_consistent([row, {**row, "rep": 2}])
    tier1 = {**row, "tier": 1, "task": "t1"}
    tier1.pop("tier3_hash")
    bench.ensure_consistent([row, tier1])

    out = tmp_path / "out"
    monkeypatch.setattr(bench, "run_cell", lambda t, a, r, o: _canned(t, a, r, o))
    monkeypatch.setattr(bench, "build_template", lambda *a, **k: None)
    argv = ["run", "--out", str(out), "--guard-top", str(tmp_path), "--claude-bin", "unused"]
    argv += ["--tier", "3", "--runs", "1", "--arms", "plain", "--tasks", "t13"]
    assert bench.main(argv) == 0
    rows = bench.read_rows(out)
    assert [r["tier3_hash"] for r in rows] == [bench.tier3_hash()]
    (out / "results.jsonl").write_text(json.dumps({**rows[0], "tier3_hash": "000000000000"}))
    capsys.readouterr()
    assert bench.main([*argv[:-2], "--tasks", "t13,t14"]) == 2
    assert "tier3_hash" in capsys.readouterr().err


# --- AC-007: tiers 1-2 are unchanged ----------------------------------------------------------


def test_tier_one_and_two_hashes_are_unchanged(bench: ModuleType, tmp_path: Path) -> None:
    """bench_hash, tier2_hash and the report and scorecard pins are the values recorded by the
    runner at origin/main 687a46c3, before tier 3 existed (the report and scorecard pins moved
    there when #30 added wall time to the headline). The runner_hash pins moved on purpose with
    SPEC-hm-eval-scripted-dri: the hm arm's turn script is a new runner setting (S8). The report
    and scorecard pins read the eval-3 rows as committed in db19f023, so publishing a new run
    does not move them; only a change to the report code does."""
    assert bench.bench_hash() == "569e17ef29ab"
    assert bench.tier2_hash() == "1cf707c57e12"
    tools = {"ruff": "r", "mypy": "m"}
    assert bench.runner_hash("model-x", 400, 1800, 5.0, (), "fake 1.0", quality_tools=tools) == (
        "76dcd05532e7"
    )
    assert (
        bench.runner_hash(
            "model-x", 400, 1800, 5.0, ("IS_SANDBOX",), "fake 1.0", quality_tools=tools, judge=False
        )
        == "234f0721c2ae"
    )
    eval3 = subprocess.run(
        ["git", "-C", str(_ROOT), "show", "db19f023:docs/evals/results.jsonl"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    (tmp_path / "results.jsonl").write_text(eval3, encoding="utf-8")
    rows = bench.read_rows(tmp_path)
    report = hashlib.sha256(bench.report_text(rows).encode()).hexdigest()[:16]
    assert report == "a082ce5d4abd734b"
    card = json.dumps(bench.scorecard(rows), sort_keys=True)
    assert hashlib.sha256(card.encode()).hexdigest()[:16] == "4a9d0dc59df6770c"


_TIER_TWO_ROW_KEYS = {
    "bench", "bench_hash", "harness_sha", "runner_hash", "model", "tier", "task", "arm", "rep",
    "max_budget_usd", "total_budget_usd", "started_at", "run_dir", "status", "exit_code",
    "cost_usd", "cost_source", "cli_cost_usd", "transcript_cost_usd", "transcript_turns",
    "subagent_turns", "num_turns", "subtype", "wall_s", "hidden", "passed", "leak_suspect",
    "tokens", "outcome", "quality", "trap", "quality_tools", "judge", "judge_model",
}  # fmt: skip


def test_a_tier_two_row_has_no_tier3_fields(bench: ModuleType, tmp_path: Path) -> None:
    task = next(t for t in bench.load_tasks() if t.id == "t12")
    opts = _options(bench, tmp_path, task, [{"overlay": str(task.reference_dir)}])
    row = bench.run_cell(task, "plain", 1, opts)
    assert row["status"] == "ok"
    assert row["outcome"] == "solved"
    assert set(row) == _TIER_TWO_ROW_KEYS
    assert bench.template_key(task, "plain") == "plain-t12"
    assert bench.template_key(next(t for t in bench.load_tasks() if t.id == "t1"), "plain") == (
        "plain"
    )
    assert bench.prompt_for(task, "plain") == task.prompt
    assert bench.prompt_for(task, "hm") == "/hm:spec " + task.prompt


# --- AC-008: the plain controls ---------------------------------------------------------------


def test_the_careful_variant_appends_one_sentence(bench: ModuleType, tmp_path: Path) -> None:
    assert bench.CAREFUL_SENTENCE == CAREFUL
    task = _task(bench, "t19")
    _row, calls = _run(bench, tmp_path, "t19", [{}, {}], arm="plain-careful")
    assert [c["prompt"] for c in calls] == [f"{p}\n\n{CAREFUL}" for p in task.session_prompts]
    assert all("--continue" not in c["argv"] for c in calls)
    assert bench.template_key(task, "plain-careful") == bench.template_key(task, "plain")


def test_the_continue_variant_continues_after_the_first_session(
    bench: ModuleType, tmp_path: Path
) -> None:
    task = _task(bench, "t19")
    row, calls = _run(bench, tmp_path, "t19", [{}, {}], arm="plain-continue")
    assert [c["argv"].count("--continue") for c in calls] == [0, 1]
    assert [c["prompt"] for c in calls] == list(task.session_prompts)
    assert row["arm"] == "plain-continue"


def test_a_continued_session_costs_the_difference_of_running_totals(
    bench: ModuleType, tmp_path: Path
) -> None:
    """A resumed session's total_cost_usd is the conversation's running total, so adding the
    sessions' totals would count session 1 twice."""
    row, _calls = _run(bench, tmp_path, "t19", [{"cost": 0.1}, {"cost": 0.25}],
                       arm="plain-continue")  # fmt: skip
    assert row["cost_usd"] == pytest.approx(0.25)
    assert row["cli_cost_usd"] == pytest.approx(0.25)
    assert row["cost_source"] == "cli"
    assert [s["cost_usd"] for s in row["sessions"]] == pytest.approx([0.1, 0.15])
    assert [s["cli_total_usd"] for s in row["sessions"]] == pytest.approx([0.1, 0.25])


def test_a_continued_total_that_falls_is_not_read_as_a_running_total(
    bench: ModuleType, tmp_path: Path
) -> None:
    row, _calls = _run(bench, tmp_path, "t19", [{"cost": 0.3}, {"cost": 0.2}],
                       arm="plain-continue")  # fmt: skip
    assert row["cli_cost_usd"] is None
    assert row["cli_cost_shape"] == "not_cumulative"
    assert row["cost_source"] != "cli"


def test_fresh_control_sessions_still_sum_their_cli_totals(
    bench: ModuleType, tmp_path: Path
) -> None:
    row, _calls = _run(bench, tmp_path, "t19", [{"cost": 0.1}, {"cost": 0.25}],
                       arm="plain-careful")  # fmt: skip
    assert row["cost_usd"] == pytest.approx(0.35)
    assert [s["cost_usd"] for s in row["sessions"]] == pytest.approx([0.1, 0.25])
    assert "cli_cost_shape" not in row


def _row(task: str, arm: str, rep: int, *, solved: bool, cost: float = 0.1,
         judge: float | None = None, tier: int = 3) -> dict[str, Any]:  # fmt: skip
    scores = (
        None
        if judge is None
        else {"scope": judge, "clarity": judge, "maintainability": judge, "overall": judge}
    )
    return {
        "bench_hash": "b", "harness_sha": "h", "model": "m", "runner_hash": "r", "tier": tier,
        "task": task, "arm": arm, "rep": rep, "status": "ok", "passed": solved,
        "outcome": "solved" if solved else "wrong", "cost_usd": cost, "cli_cost_usd": cost,
        "transcript_cost_usd": cost, "transcript_turns": 2, "num_turns": 2, "wall_s": 30.0,
        "hidden": {"tests": 4, "failures": 0 if solved else 2, "errors": 0, "skipped": 0},
        "judge": {"status": "ok", "scores": scores} if scores else {"status": "off"},
        "tier3_hash": "t3" if tier == 3 else None,
    }  # fmt: skip


def _main_rows() -> list[dict[str, Any]]:
    return [_row(t, a, r, solved=(a == "hm"), judge=4.0) for t in ("t13", "t16")
            for a in ("plain", "hm") for r in (1, 2, 3)]  # fmt: skip


def test_control_rows_stay_out_of_the_main_scorecard(bench: ModuleType) -> None:
    rows = _main_rows()
    controls = [_row(t, a, r, solved=True) for t in ("t13", "t16")
                for a in ("plain-careful", "plain-continue") for r in (1, 2, 3, 4)]  # fmt: skip
    assert bench.scorecard(rows + controls) == bench.scorecard(rows)
    assert bench.summarize(rows + controls)["arms"] == bench.summarize(rows)["arms"]
    cells = bench.pending_cells([], ["t19"], ["plain-careful", "plain"], 1)
    assert cells == [("t19", "plain-careful", 1), ("t19", "plain", 1)]
    assert set(bench.ALL_ARMS) == {"plain", "hm", "plain-careful", "plain-continue"}


# --- AC-009: the tier-3 report ----------------------------------------------------------------


def test_the_tier3_report_lists_each_task_and_the_pilot_drop(bench: ModuleType) -> None:
    solved = {"t13": 0, "t14": 2, "t15": 3, "t21": 1}
    rows = [_row(t, "plain", r, solved=r <= n, cost=0.05 * r) for t, n in solved.items()
            for r in (1, 2, 3)]  # fmt: skip
    rows += [_row("t16", "plain", r, solved=r == 1) for r in (1, 2)]
    lines = bench.tier3_block(rows)
    text = "\n".join(lines)
    assert lines[0].startswith("Per task (tier 3)")
    by_task = {line.split()[0]: line for line in lines[2:]}
    assert set(by_task) == {"t13", "t14", "t15", "t16", "t21"}
    assert by_task["t13"].split()[1:3] == ["plain", "0/3"]
    assert by_task["t13"].rstrip().endswith("keep")
    assert by_task["t14"].rstrip().endswith("drop")
    assert by_task["t15"].rstrip().endswith("drop")
    assert by_task["t21"].rstrip().endswith("guard")
    assert by_task["t16"].rstrip().endswith("n/a (n=2)")
    assert "$0.100" in by_task["t13"]  # mean of 0.05, 0.10, 0.15
    assert "Per task (tier 3)" in bench.report_text(rows)
    assert text in bench.report_text(rows)
    tier12 = bench.read_rows(_ROOT / "docs" / "evals")
    assert bench.tier3_block(tier12) == []
    assert "Per task (tier 3)" not in bench.report_text(tier12)


def test_tier3_judge_lines_are_labelled_uncalibrated(bench: ModuleType) -> None:
    rows = _main_rows()
    tier2 = [{**r, "tier": 2, "tier3_hash": None} for r in rows]
    card = bench.scorecard(rows + tier2)
    by_tier = {t["tier"]: t for t in card["tiers"]}
    judge3 = [line["label"] for line in by_tier[3]["lines"] if line["metric"].startswith("judge_")]
    judge2 = [line["label"] for line in by_tier[2]["lines"] if line["metric"].startswith("judge_")]
    assert judge3
    assert all(label.endswith(" (uncalibrated)") for label in judge3)
    assert not any("uncalibrated" in label for label in judge2)
    value3 = next(x for x in by_tier[3]["value"]["lines"] if x["metric"] == "judge_overall")
    assert value3["label"].endswith(" (uncalibrated)")
    assert dataclasses.is_dataclass(bench.Session)


# --- tier-3 publish (DRI, 2026-10-16): the pilot outcome and the hm diagnostic ----------------
# The SPEC's non-goal "publish refuses an incomplete tier" stays true for the scorecard: tier 3
# is published beside it from its own rows dir, and tiers 1-2 keep every byte they had.

_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "hm_eval"
_WITHDRAWN = "The per-task code-quality claim is withdrawn"
_PILOT_SOLVED = {"t13": 3, "t14": 3, "t15": 3, "t16": 3, "t17": 3, "t18": 2, "t19": 3,
                 "t20": 0, "t21": 3}  # fmt: skip


def _pilot(solved: dict[str, int]) -> list[dict[str, Any]]:
    return [{**_row(t, "plain", r, solved=r <= n, cost=0.1), "harness_sha": "pilot"}
            for t, n in solved.items() for r in (1, 2, 3)]  # fmt: skip


def _diagnostic() -> list[dict[str, Any]]:
    rows = [{**_row("t20", "hm", r, solved=r == 2, cost=2.0), "harness_sha": "diag"}
            for r in (1, 2, 3)]  # fmt: skip
    rows += [
        {**_row("t21", "hm", r, solved=True, cost=1.0), "harness_sha": "diag"} for r in (1, 2, 3)
    ]
    rows += [
        {**_row("t20", "plain-careful", r, solved=False), "harness_sha": "diag"} for r in (1, 2, 3)
    ]
    sessions = [{"status": "ok", "cost_usd": 1.0, "turns": 2, "wall_s": 15.0}] * 2
    return [{**r, "sessions": sessions, "stopped_at": None} for r in rows]


def _write_rows(directory: Path, rows: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _tier3_repo(tmp_path: Path, pilot: list[dict[str, Any]],
                diagnostic: list[dict[str, Any]] | None) -> tuple[Path, Path]:  # fmt: skip
    out = tmp_path / "out"
    _write_rows(out, [json.loads(x) for x in (_GOLDEN / "rows.jsonl").read_text().splitlines()])
    repo = tmp_path / "repo"
    (repo / "docs" / "evals").mkdir(parents=True)
    (repo / "README.md").write_text((_GOLDEN / "README.before.md").read_text())
    tier3 = repo / "docs" / "evals" / "tier3"
    _write_rows(tier3 / "pilot", pilot)
    if diagnostic is not None:
        _write_rows(tier3 / "diagnostic", diagnostic)
    (tier3 / "notes.md").write_text("- A fairness note written by hand.\n")
    return out, repo


def _publish3(bench: ModuleType, out: Path, repo: Path) -> int:
    argv = ["publish", "--out", str(out), "--docs", str(repo / "docs" / "evals")]
    return int(bench.main([*argv, "--readme", str(repo / "README.md")]))


def test_tier3_publishes_the_pilot_rule_and_withdraws_the_claim(
    bench: ModuleType, tmp_path: Path
) -> None:
    out, repo = _tier3_repo(tmp_path, _pilot(_PILOT_SOLVED), _diagnostic())
    assert _publish3(bench, out, repo) == 0
    rows = bench.publish_rows(out)
    results = (repo / "docs" / "evals" / "RESULTS.md").read_text()
    readme = (repo / "README.md").read_text()
    # tiers 1-2 keep every byte: the old file is a prefix, the old block sits unchanged inside
    assert results.startswith(bench.render_results_md(rows))
    section = results[len(bench.render_results_md(rows)) :]
    old_block = bench.render_readme_block(rows)
    start, end = readme.index("<!-- hm:eval:start -->"), readme.index("<!-- hm:eval:end -->")
    assert readme[start:end].startswith(f"<!-- hm:eval:start -->\n{old_block}")
    before = (_GOLDEN / "README.before.md").read_text()
    assert readme[:start] == before[: before.index("<!-- hm:eval:start -->")]
    assert readme[end:] == before[before.index("<!-- hm:eval:end -->") :]

    pilot_lines = [x for x in section.splitlines() if re.match(r"\| t\d+ \| \d/\d \|", x)]
    pilot = {cells[0]: cells for cells in ([c.strip() for c in x.strip("|").split("|")]
                                           for x in pilot_lines)}  # fmt: skip
    assert list(pilot) == _TASK_IDS
    assert pilot["t20"][-1] == "keep"
    assert pilot["t21"][-1] == "guard"
    assert pilot["t18"][1] == "2/3"
    assert all(pilot[t][-1] == "drop" for t in _TASK_IDS[:7])
    assert "T = 1 (t20)" in section
    assert "inconclusive" in section
    assert "Plain solved 23 of 27 pilot runs" in section
    assert f"{_WITHDRAWN} under the pre-registered rule" in section
    assert "diagnostic, not a verdict" in section
    assert "| t20 | hm | 1/3 |" in section
    assert "| t21 | hm | 3/3 |" in section
    assert "| t20 | plain-careful | 0/3 |" in section
    assert "- A fairness note written by hand." in section
    assert "`1f8767cb8b8c`" not in section  # the rows' own hash is shown, not the checkout's
    assert "`t3`" in section
    assert "`m`" not in section  # no model name in the tier-3 section
    tier3_md = readme[readme.index(old_block) + len(old_block) : end]
    assert _WITHDRAWN.lower() in tier3_md.lower()
    assert "not a verdict" in tier3_md
    assert "t20 1/3" in tier3_md
    assert 1 <= tier3_md.count(". ") + tier3_md.count(".\n") <= 3  # one or two sentences

    first = _tree_bytes(repo)
    assert _publish3(bench, out, repo) == 0
    assert _tree_bytes(repo) == first


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}  # fmt: skip


def test_four_kept_tasks_make_tier3_measurable_and_keep_the_claim_open(
    bench: ModuleType, tmp_path: Path
) -> None:
    solved = {**_PILOT_SOLVED, "t13": 0, "t14": 1, "t15": 1}
    out, repo = _tier3_repo(tmp_path, _pilot(solved), None)
    assert _publish3(bench, out, repo) == 0
    results = (repo / "docs" / "evals" / "RESULTS.md").read_text()
    assert "T = 4 (t13, t14, t15, t20)" in results
    assert _WITHDRAWN not in results
    assert "inconclusive" not in results
    assert "the pre-registered full run decides" in results
    assert "### hm diagnostic" not in results


def _without(rows: list[dict[str, Any]], task: str, rep: int) -> list[dict[str, Any]]:
    return [r for r in rows if (r["task"], r["rep"]) != (task, rep)]


def _extra(task: str, arm: str, tier: int = 3) -> list[dict[str, Any]]:
    return [{**_row(task, arm, 1, solved=True, tier=tier), "harness_sha": "pilot"}]


_Rows = list[dict[str, Any]]
_TIER3_REFUSALS: dict[str, Callable[[], tuple[_Rows, _Rows | None]]] = {
    "mixed_tier3_hash": lambda: (
        _pilot(_PILOT_SOLVED),
        [{**r, "tier3_hash": "other"} for r in _diagnostic()],
    ),
    "hm_in_the_pilot": lambda: (_pilot(_PILOT_SOLVED) + _extra("t20", "hm"), None),
    "short_pilot": lambda: (_without(_pilot(_PILOT_SOLVED), "t13", 3), None),
    "tier_two_row": lambda: (_pilot(_PILOT_SOLVED) + _extra("t6", "plain", tier=2), None),
    "mixed_harness_in_one_dir": lambda: (
        _pilot(_PILOT_SOLVED),
        [{**r, "harness_sha": f"d{i}"} for i, r in enumerate(_diagnostic())],
    ),
    # a task whose every row is dropped as unusable must not vanish from T's denominator
    "task_whose_rows_were_all_dropped": lambda: (
        [
            {**r, "status": "runner_error"} if r["task"] == "t16" else r
            for r in _pilot(_PILOT_SOLVED)
        ],
        None,
    ),  # fmt: skip
    "missing_guard": lambda: ([r for r in _pilot(_PILOT_SOLVED) if r["task"] != "t21"], None),
    "unknown_arm": lambda: (
        _pilot(_PILOT_SOLVED),
        [*_diagnostic(), {**_diagnostic()[0], "arm": "bogus"}],
    ),
    "missing_rep": lambda: (
        _pilot(_PILOT_SOLVED),
        [{k: v for k, v in r.items() if k != "rep"} for r in _diagnostic()],
    ),
}


@pytest.mark.parametrize("case", list(_TIER3_REFUSALS))
def test_tier3_publish_refuses_rows_it_cannot_report_honestly(
    bench: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    pilot, diagnostic = _TIER3_REFUSALS[case]()
    out, repo = _tier3_repo(tmp_path, pilot, diagnostic)
    before = _tree_bytes(repo)
    assert _publish3(bench, out, repo) == 2
    assert "refusing to publish" in capsys.readouterr().err
    assert _tree_bytes(repo) == before


def test_without_tier3_rows_publish_writes_what_it_wrote_before(
    bench: ModuleType, tmp_path: Path
) -> None:
    out, repo = _tier3_repo(tmp_path, [], None)
    shutil.rmtree(repo / "docs" / "evals" / "tier3")
    assert _publish3(bench, out, repo) == 0
    rows = bench.publish_rows(out)
    assert (repo / "docs" / "evals" / "RESULTS.md").read_text() == bench.render_results_md(rows)
    assert (repo / "README.md").read_text() == (_GOLDEN / "README.after.md").read_text()


def test_the_committed_tier3_rows_carry_the_signed_tier3_hash(bench: ModuleType) -> None:
    """The DRI's sign-off, the checkout's tier-3 fixtures and the published rows name one hash."""
    signoff = json.loads((_ROOT / "scripts" / "bench" / "tier3-signoff.json").read_text())
    tier3 = bench.tier3_inputs(_ROOT / "docs" / "evals" / "tier3")
    assert tier3 is not None
    assert signoff["tier3_hash"] == bench.tier3_hash() == tier3["tier3_hash"]


def test_tier3_costs_say_they_are_cli_totals_without_subagent_spend(
    bench: ModuleType, tmp_path: Path
) -> None:
    diagnostic = _diagnostic()
    diagnostic[0] = {**diagnostic[0], "cost_usd": None}
    out, repo = _tier3_repo(tmp_path, _pilot(_PILOT_SOLVED), diagnostic)
    assert _publish3(bench, out, repo) == 0
    rows = bench.publish_rows(out)
    section = (repo / "docs" / "evals" / "RESULTS.md").read_text()[
        len(bench.render_results_md(rows)) :
    ]
    readme = (repo / "README.md").read_text()
    tier3_md = readme[readme.index("**Tier 3**") : readme.index("<!-- hm:eval:end -->")]
    for text in (section, tier3_md):
        assert "CLI" in text
        assert "excludes subagent spend" in text
        assert "1 of 36 runs has no price" in text  # counted, not averaged away
    assert 1 <= tier3_md.count(". ") + tier3_md.count(".\n") <= 3


def test_tier3_costs_omit_the_unpriced_note_when_every_row_is_priced(
    bench: ModuleType, tmp_path: Path
) -> None:
    out, repo = _tier3_repo(tmp_path, _pilot(_PILOT_SOLVED), _diagnostic())
    assert _publish3(bench, out, repo) == 0
    results = (repo / "docs" / "evals" / "RESULTS.md").read_text()
    assert "excludes subagent spend" in results
    assert "no price" not in results


def test_the_committed_tier3_rows_publish_the_committed_section(bench: ModuleType) -> None:
    """The committed RESULTS.md is the tier 1-2 render plus the section from docs/evals/tier3."""
    docs = _ROOT / "docs" / "evals"
    rows = bench.publish_rows(docs)
    tier3 = bench.tier3_inputs(docs / "tier3")
    assert tier3 is not None
    committed = (docs / "RESULTS.md").read_text()
    assert committed == bench.render_results_md(rows, tier3)
    assert committed.startswith(bench.render_results_md(rows))
    readme = (_ROOT / "README.md").read_text()
    assert bench.splice_readme(readme, bench.render_readme_block(rows, tier3)) == readme
    assert _WITHDRAWN in committed
