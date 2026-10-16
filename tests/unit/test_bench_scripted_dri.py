"""SPEC-hm-eval-scripted-dri — the bench plays the DRI for the hm arm, offline.

No test here calls a model. A fake `claude` (written per test) follows a per-call script: it logs
its argv, writes the files its step names (a SPEC on cue), writes a transcript and prints a
CLI-shaped result with the session id, running total and turn count its step gives. The prompts
expected here are typed from the SPEC, not read from the runner's constants.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bench_light_lane.py"
_TASKS = _ROOT / "scripts" / "bench" / "tasks"

HM = "/hm:spec "
APPROVE = (
    "I approve this SPEC as written. For each open question, take the option you recommend and"
    " record it in the SPEC. Stamp the approval, then stop."
)
REPLY = (
    "I have nothing to add. For each open question, take the option you recommend, then write"
    " the SPEC."
)
MARKER = "Please answer: shall I build the parser now, and with which tests?"
LEAK = "reading scripts/bench/tasks/t1/hidden"

# test_bench_tier3.py's pinned key set of a tier-1/2 row (SPEC-hm-eval-tier3 AC-007).
_TIER_TWO_ROW_KEYS = {
    "bench", "bench_hash", "harness_sha", "runner_hash", "model", "tier", "task", "arm", "rep",
    "max_budget_usd", "total_budget_usd", "started_at", "run_dir", "status", "exit_code",
    "cost_usd", "cost_source", "cli_cost_usd", "transcript_cost_usd", "transcript_turns",
    "subagent_turns", "num_turns", "subtype", "wall_s", "hidden", "passed", "leak_suspect",
    "tokens", "outcome", "quality", "trap", "quality_tools", "judge", "judge_model",
}  # fmt: skip


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
    """A `claude` on PATH that always fails: a test that forgets claude_bin stops here."""
    stub_dir = tmp_path_factory.getbasetemp() / "no-claude"
    stub = stub_dir / "claude"
    if not stub.exists():
        stub_dir.mkdir(exist_ok=True)
        stub.write_text(f"#!{sys.executable}\nraise SystemExit(99)\n")
        stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_dir}{os.pathsep}{os.environ['PATH']}")


# --- the fake agent ---------------------------------------------------------------------------

# One step per call, in call order: {"spec": slug, "overlay": dir, "total": usd | None,
# "turns": n | None, "session": "new" | "none", "exit": n, "error": bool, "sleep": s,
# "leak": bool}. A missing "total" is a running total of 0.1 per call; None omits the field. The
# session id is "sess-1" on the first call and the `--resume` value after it.
_FAKE = r"""
import json, re, shutil, sys, time, uuid
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
with log.open("a") as handle:
    handle.write(json.dumps({"argv": argv, "cwd": str(cwd)}) + "\n")
if step.get("sleep"):
    time.sleep(step["sleep"])
if step.get("overlay"):
    shutil.copytree(step["overlay"], cwd, dirs_exist_ok=True)
if step.get("spec"):
    path = cwd / "specs" / f"SPEC-{step['spec']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# SPEC\n")
resumed = argv[argv.index("--resume") + 1] if "--resume" in argv else None
session = resumed or "sess-1"
if step.get("session") == "new":
    session = "sess-" + uuid.uuid4().hex
proj = Path(cfg["transcript_root"]) / re.sub(r"[/._]", "-", str(cwd))
proj.mkdir(parents=True, exist_ok=True)
msg = uuid.uuid4().hex
line = {
    "type": "assistant", "timestamp": "2026-10-16T00:00:00Z", "cwd": str(cwd),
    "sessionId": session, "message": {"id": "msg_" + msg, "model": cfg["model"],
                                      "usage": {"input_tokens": 1000, "output_tokens": 100}},
}
(proj / f"{msg}.jsonl").write_text(json.dumps(line) + "\n")
if step.get("leak"):
    print(cfg["leak"])
result = {"type": "result", "subtype": step.get("subtype", "success"),
          "is_error": bool(step.get("error")), "result": cfg["marker"]}
if step.get("session") != "none":
    result["session_id"] = session
total = step["total"] if "total" in step else round(0.1 * (len(calls) + 1), 6)
if total is not None:
    result["total_cost_usd"] = total
turns = step["turns"] if "turns" in step else 1
if turns is not None:
    result["num_turns"] = turns
print(json.dumps(result))
sys.exit(step.get("exit", 0))
"""


def _fake(directory: Path, steps: list[dict[str, Any]], model: str) -> tuple[Path, Path]:
    path = directory / "fake-claude"
    path.write_text(f"#!{sys.executable}\n{_FAKE}")
    path.chmod(0o755)
    log = directory / "calls.jsonl"
    cfg = {"log": str(log), "steps": steps, "transcript_root": str(directory / "transcripts"),
           "model": model, "marker": MARKER, "leak": LEAK}  # fmt: skip
    path.with_suffix(".json").write_text(json.dumps(cfg))
    return path, log


def _task(bench: ModuleType, task_id: str) -> Any:
    return next(t for t in [*bench.load_tasks(), *bench.load_tier3_tasks()] if t.id == task_id)


def _options(
    bench: ModuleType, tmp_path: Path, task: Any, steps: list[dict[str, Any]], **over: Any
) -> Any:
    """One in-process run_cell of `task` with every arm mapped to the plain template, so a test
    of the turn loop never renders the harness: the fake does what the step says."""
    fake, _log = _fake(tmp_path, steps, bench.DEFAULT_MODEL)
    template = tmp_path / "tpl"
    bench.build_template(template, "plain", seed=task.seed_dir, base=task.base_dir)
    (tmp_path / "out").mkdir()
    keys = {bench.template_key(task, arm) for arm in bench.ALL_ARMS}
    settings: dict[str, Any] = {
        "out": tmp_path / "out", "claude_bin": str(fake), "model": "m", "max_turns": 5,
        "timeout_s": 120, "transcript_root": tmp_path / "transcripts", "bench_hash": "b",
        "harness_sha": "h", "templates": dict.fromkeys(keys, template), "judge": False,
        "tier3_hash": bench.tier3_hash(), "leak_markers": ("scripts/bench/tasks",),
    }  # fmt: skip
    return bench.Options(**{**settings, **over})


def _calls(tmp_path: Path) -> list[dict[str, Any]]:
    log = tmp_path / "calls.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def _prompt(argv: list[str]) -> str:
    return str(argv[argv.index("-p") + 1])


def _run(
    bench: ModuleType, tmp_path: Path, steps: list[dict[str, Any]], *, task_id: str = "t1",
    arm: str = "hm", **over: Any,
) -> tuple[dict[str, Any], list[list[str]]]:  # fmt: skip
    task = _task(bench, task_id)
    opts = _options(bench, tmp_path, task, steps, **over)
    row = bench.run_cell(task, arm, 1, opts)
    assert row["status"] not in ("setup_error", "runner_error", "interrupted"), row
    return row, [[opts.claude_bin, *c["argv"]] for c in _calls(tmp_path)]


def _kinds(row: dict[str, Any]) -> list[str]:
    return [t["kind"] for t in row["dri_turns"]]


def _reference(task_id: str) -> str:
    return str(_TASKS / task_id / "reference")


def _with_prompt(argv: list[str], prompt: str) -> list[str]:
    out = list(argv)
    out[out.index("-p") + 1] = prompt
    return out


# --- AC-001: spec, approval, execute and wrapup in one resumed session ------------------------


def test_hm_cell_sends_spec_approve_execute_wrapup_in_one_resumed_session(
    bench: ModuleType, tmp_path: Path
) -> None:
    row, argvs = _run(bench, tmp_path, [{"spec": "x"}, {}, {}, {}])
    task = _task(bench, "t1")
    assert [_prompt(a) for a in argvs] == [
        HM + task.prompt, APPROVE, "/hm:execute x", "/hm:wrapup x",
    ]  # fmt: skip
    assert bench.APPROVE_TURN == APPROVE
    assert _kinds(row) == ["spec", "approve", "execute", "wrapup"]
    assert row["dri_slug"] == "x"
    assert row["dri_stop"] is None
    assert row["stopped_at"] is None
    assert row["status"] == "ok"


def test_later_turns_differ_from_turn_one_only_by_prompt_and_resume(
    bench: ModuleType, tmp_path: Path
) -> None:
    _row, argvs = _run(bench, tmp_path, [{"spec": "x"}, {}, {}, {}])
    task = _task(bench, "t1")
    claude = argvs[0][0]
    today = bench.agent_argv(claude, HM + task.prompt, "m", 5, bench.DEFAULT_MAX_BUDGET_USD)
    assert argvs[0] == today
    assert "--resume" not in argvs[0]
    for argv in argvs[1:]:
        assert argv[-2:] == ["--resume", "sess-1"]
        assert argv[:-2] == _with_prompt(argvs[0], _prompt(argv))
        for flag in ("--max-turns", "--model", "--max-budget-usd", "--setting-sources"):
            assert argv[argv.index(flag) + 1] == argvs[0][argvs[0].index(flag) + 1]


# --- AC-002: one fixed reply, then no_spec ----------------------------------------------------


def test_no_spec_after_turn_one_gets_one_fixed_reply(bench: ModuleType, tmp_path: Path) -> None:
    row, argvs = _run(bench, tmp_path, [{}, {"spec": "late"}, {}, {}, {}])
    assert bench.REPLY_TURN == REPLY
    assert _kinds(row) == ["spec", "reply", "approve", "execute", "wrapup"]
    assert [_prompt(a) for a in argvs][1:] == [REPLY, APPROVE, "/hm:execute late",
                                               "/hm:wrapup late"]  # fmt: skip
    assert row["dri_slug"] == "late"
    assert row["dri_stop"] is None
    assert row["stopped_at"] is None


def test_no_spec_after_the_reply_stops_as_no_spec(bench: ModuleType, tmp_path: Path) -> None:
    row, argvs = _run(bench, tmp_path, [{}, {}, {}, {}])
    assert len(argvs) == 2
    assert _kinds(row) == ["spec", "reply"]
    assert _prompt(argvs[1]) == REPLY
    assert row["dri_stop"] == "no_spec"
    assert row["stopped_at"] == 2
    assert row["dri_slug"] is None
    assert row["outcome"] == "stalled"


# --- AC-003: the slug is the newest SPEC the run created --------------------------------------


def _golden_slug(
    bench: ModuleType, tmp_path: Path, work_specs: dict[str, int], template_specs: list[str]
) -> str | None:
    work, template = tmp_path / "work", tmp_path / "template"
    work.mkdir()
    template.mkdir()
    for rel, mtime in work_specs.items():
        path = work / "specs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# SPEC\n")
        os.utime(path, ns=(mtime, mtime))
    for name in template_specs:
        (template / "specs").mkdir(exist_ok=True)
        (template / "specs" / name).write_text("# template SPEC\n")
    slug: str | None = bench.spec_slug(work, template)
    return slug


@pytest.mark.parametrize(
    ("work_specs", "template_specs", "expected"),
    [
        ({"SPEC-a.md": 1, "SPEC-b.md": 2}, [], "b"),
        ({"SPEC-a.md": 5, "SPEC-b.md": 5}, [], "b"),
        ({"SPEC-old.md": 9, "SPEC-new.md": 1}, ["SPEC-old.md"], "new"),
    ],
)
def test_slug_is_the_newest_spec_the_run_created(
    bench: ModuleType, tmp_path: Path, work_specs: dict[str, int], template_specs: list[str],
    expected: str,
) -> None:  # fmt: skip
    assert _golden_slug(bench, tmp_path, work_specs, template_specs) == expected


@pytest.mark.parametrize(
    "work_specs",
    [
        {"SPEC-x.machine.yaml": 3, "notes.md": 4, "SPEC-Bad_Name.md": 5, "sub/SPEC-y.md": 6},
        {},
    ],
)
def test_template_specs_and_other_names_give_no_slug(
    bench: ModuleType, tmp_path: Path, work_specs: dict[str, int]
) -> None:
    assert _golden_slug(bench, tmp_path, work_specs, []) is None
    assert bench.spec_slug(tmp_path / "missing", None) is None
    only_template = tmp_path / "only"
    (only_template / "work" / "specs").mkdir(parents=True)
    (only_template / "tpl" / "specs").mkdir(parents=True)
    for root in ("work", "tpl"):
        (only_template / root / "specs" / "SPEC-kept.md").write_text("# SPEC\n")
    assert bench.spec_slug(only_template / "work", only_template / "tpl") is None


# --- AC-004: turn costs, turns and wall time summed into one row ------------------------------


def _ran(totals: list[float | None], turns: list[int | None], walls: list[float]) -> list[Any]:
    ran = []
    for total, num, wall in zip(totals, turns, walls, strict=True):
        result: dict[str, Any] = {"type": "result", "subtype": "success", "is_error": False,
                                  "session_id": "s"}  # fmt: skip
        if total is not None:
            result["total_cost_usd"] = total
        if num is not None:
            result["num_turns"] = num
        ran.append((json.dumps(result) + "\n", "", 0, wall))
    return ran


_KINDS4 = ["spec", "approve", "execute", "wrapup"]


def test_turn_costs_are_differences_of_the_running_cli_total(bench: ModuleType) -> None:
    got = bench.dri_fields(
        _KINDS4, _ran([0.25, 0.3, 0.9, 1.0], [2, 1, 30, 5], [80.0, 10.0, 400.0, 60.0])
    )
    own = [t["cost_usd"] for t in got["dri_turns"]]
    assert all(math.isclose(a, b) for a, b in zip(own, [0.25, 0.05, 0.6, 0.1], strict=True))
    assert [t["cli_total_usd"] for t in got["dri_turns"]] == [0.25, 0.3, 0.9, 1.0]
    assert got["cli_cost_usd"] == 1.0
    assert got["cli_cost_shape"] is None
    assert [t["kind"] for t in got["dri_turns"]] == _KINDS4
    assert set(got["dri_turns"][0]) == {
        "kind", "status", "cost_usd", "cli_total_usd", "turns", "subtype", "wall_s",
    }  # fmt: skip
    assert bench.pick_cost(got["cli_cost_usd"], bench.Spend(0.7, 4, 0)) == (1.0, "cli")


def test_a_falling_or_missing_total_falls_back_to_the_transcript_price(
    bench: ModuleType, tmp_path: Path
) -> None:
    spend = bench.Spend(0.7, 4, 0)
    falling = bench.dri_fields(
        _KINDS4, _ran([0.25, 0.2, 0.9, 1.0], [2, 1, 30, 5], [80.0, 10.0, 400.0, 60.0])
    )
    assert falling["cli_cost_usd"] is None
    assert falling["cli_cost_shape"] == "not_cumulative"
    assert bench.pick_cost(falling["cli_cost_usd"], spend) == (0.7, "transcript")
    missing = bench.dri_fields(_KINDS4[:2], _ran([0.25, None], [2, None], [80.0, 10.0]))
    assert missing["cli_cost_usd"] is None
    assert missing["num_turns"] is None
    assert missing["wall_s"] == 90.0
    assert bench.pick_cost(missing["cli_cost_usd"], spend) == (0.7, "transcript")

    row, _argvs = _run(bench, tmp_path, [{"spec": "x", "total": 0.3}, {"total": 0.2}, {}, {}])
    assert row["cli_cost_usd"] is None
    assert row["cli_cost_shape"] == "not_cumulative"
    assert row["cost_source"] == "transcript"
    assert row["cost_usd"] == row["transcript_cost_usd"] > 0


def test_turns_and_wall_time_are_summed(bench: ModuleType, tmp_path: Path) -> None:
    got = bench.dri_fields(
        _KINDS4, _ran([0.25, 0.3, 0.9, 1.0], [2, 1, 30, 5], [80.0, 10.0, 400.0, 60.0])
    )
    assert got["num_turns"] == 38
    assert got["wall_s"] == 550.0
    assert [t["wall_s"] for t in got["dri_turns"]] == [80.0, 10.0, 400.0, 60.0]

    steps: list[dict[str, Any]] = [
        {"spec": "x", "turns": 2},
        {"turns": 1},
        {"turns": 30},
        {"turns": 5},
    ]
    row, _argvs = _run(bench, tmp_path, steps)
    assert row["num_turns"] == 38
    assert row["cli_cost_usd"] == pytest.approx(0.4)
    assert row["cost_source"] == "cli"
    assert row["wall_s"] == pytest.approx(sum(t["wall_s"] for t in row["dri_turns"]), abs=0.2)
    assert row["transcript_turns"] == 4, "the transcript price covers every turn of the session"


# --- AC-005: a failed turn, the run budget or a lost session stops the run --------------------


def test_a_failed_turn_stops_the_run_with_its_status(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeouts: list[int] = []
    original = bench._invoke

    def recording(argv: list[str], work: Path, timeout_s: int, *rest: Any) -> Any:
        timeouts.append(timeout_s)
        return original(argv, work, timeout_s, *rest)

    monkeypatch.setattr(bench, "_invoke", recording)
    steps: list[dict[str, Any]] = [{"spec": "x"}, {}, {"sleep": 60}, {}]
    timed_out, argvs = _run(bench, tmp_path, steps, timeout_s=3)
    assert (timed_out["status"], _kinds(timed_out)) == ("timeout", ["spec", "approve", "execute"])
    assert (timed_out["stopped_at"], timed_out["dri_stop"]) == (3, None)
    assert len(argvs) == 3
    assert timeouts == [3, 3, 3]

    (tmp_path / "err").mkdir()
    failed, _ = _run(bench, tmp_path / "err", [{"spec": "x"}, {"error": True, "exit": 1}, {}])
    assert (failed["status"], _kinds(failed), failed["stopped_at"]) == (
        "agent_error", ["spec", "approve"], 2,
    )  # fmt: skip


def test_the_run_budget_stops_the_next_turn(bench: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "capped").mkdir()
    capped, argvs = _run(
        bench, tmp_path / "capped", [{"spec": "x", "total": 2.0}, {"total": 5.0}, {}, {}]
    )
    assert (capped["dri_stop"], capped["subtype"], _kinds(capped)) == (
        "budget", "error_max_budget_usd", ["spec", "approve"],
    )  # fmt: skip
    assert capped["stopped_at"] == 2
    assert len(argvs) == 2

    (tmp_path / "under").mkdir()
    steps: list[dict[str, Any]] = [
        {"spec": "x", "total": 2.0},
        {"total": 4.0},
        {"total": 4.5},
        {"total": 4.6},
    ]
    under_cap, _ = _run(bench, tmp_path / "under", steps)
    assert _kinds(under_cap)[:3] == ["spec", "approve", "execute"]
    assert under_cap["dri_stop"] is None

    (tmp_path / "unknown").mkdir()
    unknown, argvs = _run(bench, tmp_path / "unknown", [{"spec": "x", "total": None}, {}, {}])
    assert (unknown["dri_stop"], _kinds(unknown), len(argvs)) == ("budget", ["spec"], 1)
    assert unknown["subtype"] == "success", "an unknown spend is not a capped run"

    (tmp_path / "fell").mkdir()
    steps = [{"spec": "x", "total": 3.0}, {"total": 2.5}, {}, {}]
    fell, _ = _run(bench, tmp_path / "fell", steps)
    assert (fell["dri_stop"], _kinds(fell)) == ("budget", ["spec", "approve"]), (
        "a falling total is read as a sum (5.5), so the cap is never under-counted"
    )


def test_a_lost_session_id_stops_the_run(bench: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "lost").mkdir()
    lost, argvs = _run(bench, tmp_path / "lost", [{"spec": "x"}, {"session": "new"}, {}, {}])
    assert (lost["dri_stop"], _kinds(lost)) == ("session_lost", ["spec", "approve"])
    assert lost["stopped_at"] == 2
    assert len(argvs) == 2

    (tmp_path / "none").mkdir()
    none, argvs = _run(bench, tmp_path / "none", [{"spec": "x", "session": "none"}, {}])
    assert (none["dri_stop"], _kinds(none), none["stopped_at"]) == ("session_lost", ["spec"], 1)
    assert len(argvs) == 1


# --- AC-006: graded once on the final tree, every turn's output kept and leak-checked ---------


def test_the_run_is_graded_once_after_its_last_turn(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graded: list[Path] = []
    original = bench.grade

    def counting(work: Path, tests_dir: Path, *args: Any, **kwargs: Any) -> Any:
        if tests_dir.name == "hidden":
            graded.append(work)
        return original(work, tests_dir, *args, **kwargs)

    monkeypatch.setattr(bench, "grade", counting)
    (tmp_path / "row").mkdir()
    steps: list[dict[str, Any]] = [{"spec": "x"}, {}, {"overlay": _reference("t1")}, {}]
    row, _ = _run(bench, tmp_path / "row", steps)
    assert len(graded) == 1
    assert graded[0] == Path(row["run_dir"]) / "work"
    assert row["outcome"] == "solved"
    assert row["passed"] is True

    (tmp_path / "late").mkdir()
    steps = [{"spec": "x"}, {}, {}, {"overlay": _reference("t1")}]
    late_fix, _ = _run(bench, tmp_path / "late", steps)
    assert late_fix["outcome"] == "solved"


def test_every_turn_output_is_kept_and_leak_checked(bench: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "clean").mkdir()
    clean, _ = _run(bench, tmp_path / "clean", [{"spec": "x"}, {}, {}, {}])
    run_dir = Path(clean["run_dir"])
    assert sorted(p.name for p in run_dir.glob("agent-*.stdout")) == [
        "agent-1.stdout", "agent-2.stdout", "agent-3.stdout", "agent-4.stdout",
    ]  # fmt: skip
    assert sorted(p.name for p in run_dir.glob("agent-*.stderr")) == [
        "agent-1.stderr", "agent-2.stderr", "agent-3.stderr", "agent-4.stderr",
    ]  # fmt: skip
    assert (run_dir / "agent.stdout").read_text() == (run_dir / "agent-4.stdout").read_text()
    assert clean["leak_suspect"] is False

    (tmp_path / "leaky").mkdir()
    leaky, _ = _run(bench, tmp_path / "leaky", [{"spec": "x"}, {}, {}, {"leak": True}])
    assert leaky["leak_suspect"] is True
    assert LEAK in (Path(leaky["run_dir"]) / "agent-4.stdout").read_text()


# --- AC-007: plain and tier 3 unchanged -------------------------------------------------------


def test_the_plain_arm_runs_one_unchanged_call(bench: ModuleType, tmp_path: Path) -> None:
    row, argvs = _run(bench, tmp_path, [{"overlay": _reference("t1")}, {}], arm="plain")
    task = _task(bench, "t1")
    assert len(argvs) == 1
    expected = bench.agent_argv(argvs[0][0], task.prompt, "m", 5, bench.DEFAULT_MAX_BUDGET_USD)
    assert argvs[0] == expected
    assert set(row) == _TIER_TWO_ROW_KEYS
    assert row["outcome"] == "solved"


def test_tier3_cells_keep_one_call_per_session(bench: ModuleType, tmp_path: Path) -> None:
    row, argvs = _run(bench, tmp_path, [{}, {}], task_id="t19")
    task = _task(bench, "t19")
    assert [_prompt(a) for a in argvs] == [HM + p for p in task.session_prompts]
    assert all("--resume" not in a for a in argvs)
    assert not any(k.startswith("dri_") for k in row)
    assert "cli_cost_shape" not in row
    assert "sessions" in row


# --- AC-008: runner_hash covers the turn script -----------------------------------------------


def _base_hash(bench: ModuleType) -> str:
    tools = {"ruff": "r", "mypy": "m"}
    value: str = bench.runner_hash("model-x", 400, 1800, 5.0, (), "fake 1.0", quality_tools=tools)
    return value


def test_runner_hash_covers_the_turn_script(
    bench: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _base_hash(bench)
    assert base not in ("17f703bf0fcc", "10856c4eb248"), "the turn script is a new setting"
    variants: list[tuple[str, Any]] = [
        ("APPROVE_TURN", APPROVE + " Thanks."),
        ("REPLY_TURN", REPLY + " Thanks."),
        ("EXECUTE_PREFIX", "/hm:exec "),
        ("WRAPUP_PREFIX", "/hm:wrap "),
        ("DRI_ORDER", ("spec", "execute", "approve", "wrapup")),
        ("DRI_MAX_REPLIES", 2),
        ("RESUME_FLAG", "--continue"),
        ("SPEC_PATTERN", r"SPEC-(\w+)\.md"),
        ("DRI_TIERS", (1,)),
    ]
    for name, changed in variants:
        assert hasattr(bench, name), name
        with monkeypatch.context() as patch:
            patch.setattr(bench, name, changed)
            assert _base_hash(bench) != base, name
    assert _base_hash(bench) == base
    assert bench.bench_hash() == "569e17ef29ab"
    assert bench.tier2_hash() == "1cf707c57e12"


def test_rows_from_before_the_turn_script_are_refused(bench: ModuleType) -> None:
    old = bench.read_rows(_ROOT / "docs" / "evals")
    assert old
    old_row = next(r for r in old if r.get("status") not in bench.UNUSABLE)
    new_row = {**old_row, "runner_hash": _base_hash(bench)}
    assert old_row["runner_hash"] != new_row["runner_hash"]
    with pytest.raises(bench.MixedResultsError, match="runner_hash"):
        bench.ensure_consistent([old_row, new_row])
    bench.ensure_consistent([new_row, {**new_row, "rep": 99}])


# --- AC-009: nothing but fixed strings, the task prompt or the slug reaches the agent ---------

_SCENARIOS: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]] = {
    "full": ([{"spec": "x"}, {}, {}, {}], {}),
    "reply_then_spec": ([{}, {"spec": "late-one"}, {}, {}, {}], {}),
    "reply_then_none": ([{}, {}, {}, {}], {}),
    "timeout": ([{"spec": "x"}, {"sleep": 60}, {}, {}], {"timeout_s": 3}),
    "budget": ([{"spec": "x", "total": 1.0}, {"total": 5.0}, {}, {}], {}),
    "lost": ([{"spec": "x"}, {"session": "new"}, {}, {}], {}),
    "renamed": ([{"spec": "first"}, {"spec": "second"}, {}, {}], {}),
}


@pytest.mark.parametrize("task_id", ["t1", "t6"])
@pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
def test_every_sent_prompt_is_fixed_or_the_task_or_the_slug(
    bench: ModuleType, tmp_path: Path, task_id: str, scenario: str
) -> None:
    steps, over = _SCENARIOS[scenario]
    row, argvs = _run(bench, tmp_path, steps, task_id=task_id, **over)
    task = _task(bench, task_id)
    work_specs = Path(row["run_dir"]) / "work" / "specs"
    written = {p.name[5:-3] for p in work_specs.glob("SPEC-*.md")} if work_specs.is_dir() else set()
    sent = [_prompt(a) for a in argvs]
    assert sent
    for prompt in sent:
        head, _sep, rest = prompt.partition(" ")
        fixed = prompt in (HM + task.prompt, REPLY, APPROVE)
        slugged = head in ("/hm:execute", "/hm:wrapup") and rest in written
        assert fixed or slugged, prompt
        assert MARKER not in prompt
    if scenario == "renamed":
        assert sent[2:] == ["/hm:execute second", "/hm:wrapup second"]
