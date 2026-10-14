"""Bench runner for hm_cost_ratio_small: plain vs /hm: arms on small single-session tasks.

SPEC-hm-light-lane-bench. Each task under `scripts/bench/tasks/<id>/` has a `prompt.md`, hidden
tests in `hidden/` and a reference overlay in `reference/` for the `scripts/bench/timeparse/`
fixture. A run copies the fixture into a fresh git repo (the hm arm also renders this checkout's
harness into it), runs `claude -p` headlessly, then grades the work dir with the hidden tests from
outside it.

Usage:
    INTEGRATION=1 uv run python scripts/bench_light_lane.py run [--runs 3] [--jobs 3] [--out DIR]
    uv run python scripts/bench_light_lane.py report --out DIR [--json]
    uv run python scripts/bench_light_lane.py check

`run` calls a live model and refuses without INTEGRATION=1; `report` and `check` are offline.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker import economics, economics_source

BENCH_ID = "hm-light-lane"
METRIC_ID = "hm_cost_ratio_small"
# Mirrors `.claude/intent.yaml` metric `hm_cost_ratio_small` (target, lower is better);
# test_target_matches_the_intent_metric keeps the two equal.
TARGET = 5.0
ARMS = ("plain", "hm")
HM_PREFIX = "/hm:spec "
DEFAULT_MODEL = "claude-sonnet-5-5"  # the baseline's model (RESEARCH-hm-light-lane)
DEFAULT_MAX_TURNS = 400
DEFAULT_TIMEOUT_S = 1800
GRADE_TIMEOUT_S = 300
SETUP_TIMEOUT_S = 300

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = Path(__file__).resolve().parent / "bench"
FIXTURE_DIR = BENCH_DIR / "timeparse"
TASKS_DIR = BENCH_DIR / "tasks"
RESULTS = "results.jsonl"

_IGNORED = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
# Variables of an enclosing Claude Code session that must not leak into the agent under test.
_SESSION_ENV = ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT")
_GIT = ["git", "-c", "user.name=hm-bench", "-c", "user.email=bench@localhost"]
_GIT += ["-c", "commit.gpgsign=false"]


class MixedResultsError(Exception):
    """A results file mixes bench versions, harness versions or models."""


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    hidden_dir: Path
    reference_dir: Path


@dataclass(frozen=True)
class Grade:
    tests: int
    failures: int
    errors: int
    skipped: int

    @property
    def passed(self) -> bool:
        return self.tests > 0 and self.failures == self.errors == self.skipped == 0


@dataclass(frozen=True)
class Spend:
    usd: float
    turns: int
    subagent_turns: int


@dataclass(frozen=True)
class Options:
    out: Path
    claude_bin: str
    model: str
    max_turns: int
    timeout_s: int
    transcript_root: Path
    bench_hash: str
    harness_sha: str


# --- fixture and tasks ------------------------------------------------------------------------


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[Task]:
    tasks = []
    for d in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        prompt = (d / "prompt.md").read_text(encoding="utf-8").strip()
        tasks.append(Task(d.name, prompt, d / "hidden", d / "reference"))
    return tasks


def bench_hash() -> str:
    """Content hash of the fixture and every task, so rows from different benches never mix."""
    digest = hashlib.sha256()
    for base in (FIXTURE_DIR, TASKS_DIR):
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(BENCH_DIR)
            cache = {"__pycache__", ".pytest_cache"} & set(rel.parts)
            if path.is_file() and not cache and path.suffix != ".pyc":
                digest.update(rel.as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:12]


def harness_sha() -> str:
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30, check=False
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    sha = git("rev-parse", "--short=12", "HEAD") or "unknown"
    return f"{sha}-dirty" if git("status", "--porcelain", "--untracked-files=no") else sha


def copy_fixture(dest: Path) -> None:
    shutil.copytree(FIXTURE_DIR, dest, ignore=_IGNORED)


def apply_overlay(work: Path, overlay: Path) -> None:
    shutil.copytree(overlay, work, dirs_exist_ok=True, ignore=_IGNORED)


# --- grading ----------------------------------------------------------------------------------


def _junit_counts(xml_path: Path) -> Grade:
    try:
        root = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError):
        return Grade(0, 0, 1, 0)
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = Counter[str]()
    for suite in suites:
        for key in ("tests", "failures", "errors", "skipped"):
            total[key] += int(suite.get(key, "0"))
    return Grade(total["tests"], total["failures"], total["errors"], total["skipped"])


def grade(work: Path, tests_dir: Path, scratch: Path) -> Grade:
    """Run `tests_dir` against `work` from outside it.

    The tests are copied to `scratch` and pytest gets its own ini and rootdir, so a conftest.py
    or pytest config left in `work` is never loaded; `work` is reachable only via PYTHONPATH.
    """
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(tests_dir, scratch, ignore=_IGNORED)
    ini = scratch / "pytest.ini"
    ini.write_text("[pytest]\n", encoding="utf-8")
    xml_path = scratch.parent / f"{scratch.name}.junit.xml"
    xml_path.unlink(missing_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(
        PYTHONPATH=str(work), PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
    )
    argv = [sys.executable, "-m", "pytest", str(scratch), "-q", "-c", str(ini)]
    argv += ["--rootdir", str(scratch), "-p", "no:cacheprovider", "--junitxml", str(xml_path)]
    try:
        subprocess.run(
            argv,
            cwd=scratch,
            env=env,
            capture_output=True,
            text=True,
            timeout=GRADE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Grade(0, 0, 1, 0)
    return _junit_counts(xml_path)


def check_task(task: Task, scratch: Path) -> list[str]:
    """Problems that make `task` unable to tell a fix from no fix (empty list = sound)."""
    problems = []
    pristine, reference = scratch / "pristine", scratch / "reference"
    copy_fixture(pristine)
    copy_fixture(reference)
    apply_overlay(reference, task.reference_dir)
    if grade(pristine, task.hidden_dir, scratch / "g-pristine").passed:
        problems.append(f"{task.id}: hidden tests already pass on the pristine fixture")
    hidden_ref = grade(reference, task.hidden_dir, scratch / "g-reference")
    if not hidden_ref.passed:
        problems.append(f"{task.id}: hidden tests fail on the reference ({hidden_ref})")
    for name, work in (("pristine", pristine), ("reference", reference)):
        if not grade(work, work / "tests", scratch / f"v-{name}").passed:
            problems.append(f"{task.id}: visible tests fail on the {name} copy")
    return problems


# --- one run ----------------------------------------------------------------------------------


def _git(work: Path, *args: str) -> None:
    subprocess.run([*_GIT, *args], cwd=work, capture_output=True, timeout=60, check=True)


def prepare_work(work: Path, arm: str) -> None:
    """Fixture in a clean git repo; the hm arm adds this checkout's harness as a second commit."""
    copy_fixture(work)
    _git(work, "init", "-q")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "fixture")
    if arm == "hm":
        argv = [sys.executable, "-m", "harness_maker", "make", str(work), "--autoloop"]
        argv += ["--preset", "Side", "--targets", "claude-code", "--autonomy-level", "auto_full"]
        subprocess.run(
            argv,
            cwd=work,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=SETUP_TIMEOUT_S,
            check=True,
        )
        _git(work, "add", "-A")
        _git(work, "commit", "-q", "-m", "harness")


def prompt_for(task: Task, arm: str) -> str:
    return HM_PREFIX + task.prompt if arm == "hm" else task.prompt


def agent_argv(claude_bin: str, prompt: str, model: str, max_turns: int) -> list[str]:
    return [
        claude_bin, "-p", prompt, "--output-format", "json", "--dangerously-skip-permissions",
        "--max-turns", str(max_turns), "--model", model,
    ]  # fmt: skip


def parse_cli_result(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("type") == "result":
            return data
    return None


def _invoke(argv: list[str], work: Path, timeout_s: int) -> tuple[str, str, int | None]:
    """Run the agent in its own process group so a timeout also stops its children."""
    env = {k: v for k, v in os.environ.items() if k not in _SESSION_ENV}
    proc = subprocess.Popen(
        argv, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )  # fmt: skip
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return out, err, None
    return out, err, proc.returncode


def transcript_cost(work: Path, transcript_root: Path) -> Spend:
    """Price every main and subagent transcript turn launched from `work`."""
    turns = economics_source.load_turns(work, transcript_root=transcript_root).turns
    usd = sum(economics.price_turn(t).total_usd for t in turns)
    return Spend(usd, len(turns), sum(1 for t in turns if t.is_sidechain))


def pick_cost(cli_cost: float | None, transcript_usd: float) -> tuple[float, str]:
    """The CLI's own total is the baseline's source; the transcript price covers a lost result."""
    if cli_cost is None:
        return transcript_usd, "transcript"
    return cli_cost, "cli"


def run_cell(task: Task, arm: str, rep: int, opts: Options) -> dict[str, Any]:
    run_dir = opts.out / "runs" / f"{task.id}-{arm}-{rep}-{uuid.uuid4().hex[:6]}"
    work = (run_dir / "work").resolve()
    row: dict[str, Any] = {
        "bench": BENCH_ID, "bench_hash": opts.bench_hash, "harness_sha": opts.harness_sha,
        "model": opts.model, "task": task.id, "arm": arm, "rep": rep,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"), "run_dir": str(run_dir),
    }  # fmt: skip
    try:
        run_dir.mkdir(parents=True)
        prepare_work(work, arm)
    except (OSError, subprocess.SubprocessError) as exc:
        return {**row, "status": "setup_error", "error": str(exc)[-500:]}
    argv = agent_argv(opts.claude_bin, prompt_for(task, arm), opts.model, opts.max_turns)
    start = time.monotonic()
    try:
        stdout, stderr, code = _invoke(argv, work, opts.timeout_s)
    except OSError as exc:
        return {**row, "status": "setup_error", "error": str(exc)[-500:]}
    wall = time.monotonic() - start
    (run_dir / "agent.stdout").write_text(stdout, encoding="utf-8")
    (run_dir / "agent.stderr").write_text(stderr, encoding="utf-8")
    result = parse_cli_result(stdout)
    if code is None:
        status = "timeout"
    elif code != 0 or result is None or result.get("is_error"):
        status = "agent_error"
    else:
        status = "ok"
    raw_cost = result.get("total_cost_usd") if result else None
    cli_cost = float(raw_cost) if isinstance(raw_cost, int | float) else None
    spend = transcript_cost(work, opts.transcript_root)
    cost, source = pick_cost(cli_cost, spend.usd)
    graded = grade(work, task.hidden_dir, run_dir / "hidden")
    return {
        **row, "status": status, "exit_code": code, "cost_usd": round(cost, 6),
        "cost_source": source, "cli_cost_usd": cli_cost,
        "transcript_cost_usd": round(spend.usd, 6), "transcript_turns": spend.turns,
        "subagent_turns": spend.subagent_turns,
        "num_turns": result.get("num_turns") if result else None,
        "subtype": result.get("subtype") if result else None, "wall_s": round(wall, 1),
        "hidden": {"tests": graded.tests, "failures": graded.failures,
                   "errors": graded.errors, "skipped": graded.skipped},
        "passed": graded.passed,
    }  # fmt: skip


# --- results ----------------------------------------------------------------------------------


def read_rows(out: Path) -> list[dict[str, Any]]:
    path = out / RESULTS
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def pending_cells(
    rows: list[dict[str, Any]], tasks: list[str], arms: list[str], runs: int
) -> list[tuple[str, str, int]]:
    """Cells still to run; a setup failure was the runner's fault and is retried."""
    done = {(r["task"], r["arm"], r["rep"]) for r in rows if r.get("status") != "setup_error"}
    cells = [(t, a, rep) for t in tasks for rep in range(1, runs + 1) for a in arms]
    return [c for c in cells if c not in done]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(hm: float | None, plain: float | None) -> float | None:
    if hm is None or plain is None or plain <= 0:
        return None
    return round(hm / plain, 2)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the intent's pre-registered rule (intent/HM-LIGHT-LANE.md, 판정 규칙)."""
    usable = [r for r in rows if r.get("status") != "setup_error"]
    for field in ("bench_hash", "harness_sha", "model"):
        seen = sorted({str(r.get(field)) for r in usable})
        if len(seen) > 1:
            raise MixedResultsError(f"results mix {field} values {seen}; use a fresh --out")
    tasks = sorted({r["task"] for r in usable})
    per_task: dict[str, dict[str, dict[str, Any]]] = {}
    arms: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        mine = [r for r in usable if r["arm"] == arm]
        arms[arm] = _cell(mine)
        for task in tasks:
            per_task.setdefault(task, {})[arm] = _cell([r for r in mine if r["task"] == task])
    counts = {per_task[t][a]["runs"] for t in tasks for a in ARMS}
    balanced = bool(tasks) and len(counts) == 1 and 0 not in counts
    ratio = _ratio(arms["hm"]["mean_cost"], arms["plain"]["mean_cost"])
    transcript_ratio = _ratio(arms["hm"]["mean_transcript"], arms["plain"]["mean_transcript"])
    if ratio is None or not balanced:
        verdict, why = "no_data", "an arm has no runs or the task x arm grid is unbalanced"
    elif ratio > TARGET:
        verdict, why = "missed", f"ratio {ratio} > target {TARGET:g}"
    elif arms["hm"]["pass_rate"] < arms["plain"]["pass_rate"]:
        verdict, why = "missed", "hm hidden-test pass rate is below plain"
    else:
        verdict, why = "met", f"ratio {ratio} <= target {TARGET:g} and hm pass rate >= plain"
    first = usable[0] if usable else {}
    return {
        "bench": BENCH_ID, "bench_hash": first.get("bench_hash"),
        "harness_sha": first.get("harness_sha"), "model": first.get("model"),
        "tasks": tasks, "runs_per_cell": counts.pop() if balanced else None,
        "arms": arms, "per_task": per_task, "ratio": ratio,
        "transcript_ratio": transcript_ratio, "verdict": verdict, "why": why,
        "setup_errors": len(rows) - len(usable), "target": TARGET,
    }  # fmt: skip


def _cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for r in rows if r.get("passed"))
    return {
        "runs": len(rows),
        "passed": passed,
        "pass_rate": passed / len(rows) if rows else 0.0,
        "mean_cost": _mean([float(r["cost_usd"]) for r in rows]),
        "mean_transcript": _mean([float(r.get("transcript_cost_usd") or 0.0) for r in rows]),
        "mean_wall_s": _mean([float(r.get("wall_s") or 0.0) for r in rows]),
    }


def record_argv(summary: dict[str, Any]) -> list[str] | None:
    if summary["ratio"] is None:
        return None
    a, p = summary["arms"]["hm"], summary["arms"]["plain"]
    evidence = (
        f"bench {BENCH_ID}@{summary['bench_hash']} harness {summary['harness_sha']} "
        f"model {summary['model']}: hm ${a['mean_cost']:.3f}/run vs plain "
        f"${p['mean_cost']:.3f}/run over {len(summary['tasks'])} tasks x "
        f"{summary['runs_per_cell']} runs (transcript-priced ratio {summary['transcript_ratio']}); "
        f"hidden-test pass plain {p['passed']}/{p['runs']}, hm {a['passed']}/{a['runs']}; "
        f"verdict {summary['verdict']}"
    )
    value = str(summary["ratio"])
    return ["hm", "intent", "metric", "record", METRIC_ID, "--value", value, "--evidence", evidence]


def _money(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _secs(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"bench {BENCH_ID}@{summary['bench_hash']}  harness {summary['harness_sha']}  "
        f"model {summary['model']}",
        f"{'task':<6}{'plain pass':>11}{'hm pass':>9}{'plain $/run':>13}{'hm $/run':>10}"
        f"{'plain s':>9}{'hm s':>7}",
    ]
    rows = [(t, summary["per_task"][t]) for t in summary["tasks"]] + [("all", summary["arms"])]
    for name, cell in rows:
        p, h = cell["plain"], cell["hm"]
        lines.append(
            f"{name:<6}{p['passed']:>6}/{p['runs']:<4}{h['passed']:>4}/{h['runs']:<4}"
            f"{_money(p['mean_cost']):>13}{_money(h['mean_cost']):>10}"
            f"{_secs(p['mean_wall_s']):>9}{_secs(h['mean_wall_s']):>7}"
        )
    p, h = summary["arms"]["plain"], summary["arms"]["hm"]
    lines.append(
        f"ratio (CLI cost): {summary['ratio']}    ratio (transcript price): "
        f"{summary['transcript_ratio']}"
    )
    lines.append(
        f"pass rate: plain {p['passed']}/{p['runs']} ({p['pass_rate']:.0%}), "
        f"hm {h['passed']}/{h['runs']} ({h['pass_rate']:.0%})"
    )
    if summary["setup_errors"]:
        lines.append(f"setup errors left out: {summary['setup_errors']} (re-run to retry them)")
    lines.append(f"verdict: {summary['verdict']} — {summary['why']}")
    argv = record_argv(summary)
    if argv is not None:
        lines += ["record with:", "  uv run " + shlex.join(argv)]
    value = "n/a" if summary["ratio"] is None else str(summary["ratio"])
    lines.append(f"{METRIC_ID}={value}")
    return "\n".join(lines)


# --- CLI --------------------------------------------------------------------------------------


def guard_out_dir(out: Path, top: Path | None = None) -> str | None:
    """Why `out` would leak project context into both arms, or None when it is safe.

    Claude Code reads CLAUDE.md from every ancestor of the launch dir. `top` bounds the walk
    for tests; the runner always walks to the filesystem root.
    """
    resolved = out.resolve()
    ancestors = [resolved, *resolved.parents]
    if top is not None:
        bound = top.resolve()
        ancestors = [p for p in ancestors if p == bound or bound in p.parents]
    for parent in ancestors:
        if (parent / ".git").exists():
            return f"{parent} is a git work tree"
        if (parent / "CLAUDE.md").exists():
            return f"{parent}/CLAUDE.md would load into both arms"
    return None


def _cmd_run(args: argparse.Namespace) -> int:
    if os.environ.get("INTEGRATION") != "1":
        print("run calls a live model; set INTEGRATION=1 to opt in", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="hm-bench-"))
    reason = guard_out_dir(out, Path(args.guard_top) if args.guard_top else None)
    if reason is not None:
        if not args.out:
            out.rmdir()
        print(f"refusing --out {out}: {reason}; pick a dir outside any project", file=sys.stderr)
        return 2
    all_tasks = load_tasks()
    wanted = args.tasks.split(",") if args.tasks else [t.id for t in all_tasks]
    tasks = {t.id: t for t in all_tasks if t.id in wanted}
    unknown = sorted(set(wanted) - set(tasks))
    arms = args.arms.split(",")
    if unknown or not set(arms) <= set(ARMS):
        print(f"unknown task or arm: {unknown or arms}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    opts = Options(
        out=out, claude_bin=args.claude_bin, model=args.model, max_turns=args.max_turns,
        timeout_s=args.timeout_s, bench_hash=bench_hash(), harness_sha=harness_sha(),
        transcript_root=Path(args.transcript_root or economics_source.default_transcript_root()),
    )  # fmt: skip
    cells = pending_cells(read_rows(out), list(tasks), arms, args.runs)
    print(f"bench {BENCH_ID}: {len(cells)} run(s) to go, results in {out / RESULTS}", flush=True)
    lock = threading.Lock()

    def one(cell: tuple[str, str, int]) -> None:
        row = run_cell(tasks[cell[0]], cell[1], cell[2], opts)
        with lock, (out / RESULTS).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        print(f"  {cell[0]} {cell[1]} #{cell[2]}: {row['status']} "
              f"passed={row.get('passed')} cost={row.get('cost_usd')}", flush=True)  # fmt: skip

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        list(pool.map(one, cells))
    return _cmd_report(argparse.Namespace(out=str(out), json=False))


def _cmd_report(args: argparse.Namespace) -> int:
    rows = read_rows(Path(args.out))
    if not rows:
        print(f"no results in {Path(args.out) / RESULTS}", file=sys.stderr)
        return 2
    try:
        summary = summarize(rows)
    except MixedResultsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({**summary, "record_argv": record_argv(summary)}, indent=2))
    else:
        print(render_report(summary))
    return 0


def _cmd_check(_args: argparse.Namespace) -> int:
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hm-bench-check-") as scratch:
        for task in load_tasks():
            problems += check_task(task, Path(scratch) / task.id)
    for problem in problems:
        print(problem, file=sys.stderr)
    print("check: ok" if not problems else f"check: {len(problems)} problem(s)")
    return 1 if problems else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bench_light_lane", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run both arms (live model; needs INTEGRATION=1)")
    run.add_argument("--out", default=None, help="results dir (default: fresh temp dir)")
    run.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    run.add_argument("--arms", default=",".join(ARMS))
    run.add_argument("--runs", type=int, default=3, help="runs per task and arm")
    run.add_argument("--jobs", type=int, default=1, help="runs in parallel")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, dest="max_turns")
    run.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S, dest="timeout_s")
    run.add_argument("--claude-bin", default="claude", dest="claude_bin")
    run.add_argument("--transcript-root", default=None, dest="transcript_root")
    run.add_argument(
        "--guard-top", default=None, dest="guard_top",
        help="tests only: stop the CLAUDE.md/.git ancestor check at this dir",
    )  # fmt: skip
    rep = sub.add_parser("report", help="summarize a results dir (offline)")
    rep.add_argument("--out", required=True)
    rep.add_argument("--json", action="store_true")
    sub.add_parser("check", help="prove each task's hidden tests discriminate (offline)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handlers = {"run": _cmd_run, "report": _cmd_report, "check": _cmd_check}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
