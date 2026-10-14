"""Bench runner for hm_cost_ratio_small: plain vs /hm: arms on small single-session tasks.

SPEC-hm-light-lane-bench. Each task under `scripts/bench/tasks/<id>/` has a `prompt.md`, hidden
tests in `hidden/` and a reference overlay in `reference/` for the `scripts/bench/timeparse/`
fixture. A run copies the fixture into a fresh git repo (the hm arm also renders this checkout's
harness into it), runs `claude -p` headlessly, then grades the work dir with the hidden tests from
outside it.

Usage:
    INTEGRATION=1 uv run python scripts/bench_light_lane.py run [--runs 3] [--out DIR]
    uv run python scripts/bench_light_lane.py report --out DIR [--json]
    uv run python scripts/bench_light_lane.py check

`run` calls a live model and refuses without INTEGRATION=1; `report` and `check` are offline.

Safety: the agent runs with --dangerously-skip-permissions as the invoking user, so it has that
user's full file access (its environment is an allowlist, not a sandbox). Run live benches in a
container or throwaway VM. A stop signal (Ctrl-C, SIGTERM) kills every live agent process group.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_maker import economics, economics_source

BENCH_ID = "hm-light-lane"
METRIC_ID = "hm_cost_ratio_small"
# Mirrors `.claude/intent.yaml` metric `hm_cost_ratio_small` (target, lower is better);
# test_target_matches_the_intent_metric keeps the two equal.
TARGET = 5.0
TARGET_EPS = 1e-9  # float noise in a mean of means must not flip an inclusive `<=`
SUSPECT_GAP = 0.2  # CLI and transcript ratios further apart than this are not trusted
ARMS = ("plain", "hm")
HM_PREFIX = "/hm:spec "
DEFAULT_MODEL = "claude-sonnet-5-5"  # the baseline's model (RESEARCH-hm-light-lane)
DEFAULT_MAX_TURNS = 400
DEFAULT_TIMEOUT_S = 1800
DEFAULT_MAX_BUDGET_USD = 5.0
DEFAULT_TOTAL_BUDGET_USD = 40.0
GRADE_TIMEOUT_S = 300
SETUP_TIMEOUT_S = 300
REAP_TIMEOUT_S = 10
SETTING_SOURCES = "project,local"  # never `user`: ~/.claude settings, plugins and CLAUDE.md

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = Path(__file__).resolve().parent / "bench"
FIXTURE_DIR = BENCH_DIR / "timeparse"
TASKS_DIR = BENCH_DIR / "tasks"
RESULTS = "results.jsonl"
LOCK_FILE = ".run.lock"
# Statuses that are the runner's fault: left out of the report and retried on resume.
UNUSABLE = ("setup_error", "runner_error")
MIXED_FIELDS = ("bench_hash", "harness_sha", "model", "runner_hash")

_IGNORED = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
# Variables of an enclosing Claude Code session that must not leak into the agent under test.
_SESSION_ENV = ("CLAUDECODE", "CLAUDE_ENV_FILE", "HM_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT")
# The agent sees only these (plus LC_*); anything else needs --pass-env.
_AGENT_ENV = (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "TERM", "TMPDIR",
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CONFIG_DIR", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy",
    "http_proxy", "no_proxy", "all_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
)  # fmt: skip
_GRADE_ENV = ("PATH", "LANG", "TERM", "TMPDIR", "SYSTEMROOT")
_GIT = ["git", "-c", "user.name=hm-bench", "-c", "user.email=bench@localhost"]
_GIT += ["-c", "commit.gpgsign=false"]

# Set on Ctrl-C / SIGTERM or a failed run: workers stop before spending or recording more.
STOP = threading.Event()
_LIVE: set[int] = set()
_LIVE_LOCK = threading.Lock()


class MixedResultsError(Exception):
    """A results file mixes bench versions, harness versions, runner settings or models."""


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    hidden_dir: Path
    reference_dir: Path
    guards: frozenset[str] = frozenset()  # hidden tests that pass on the pristine fixture


@dataclass(frozen=True)
class Grade:
    tests: int
    failures: int
    errors: int
    skipped: int
    cases: tuple[tuple[str, str], ...] = ()  # (test name, passed|failed|error|skipped)

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
    runner_hash: str = ""
    max_budget_usd: float = DEFAULT_MAX_BUDGET_USD
    total_budget_usd: float = DEFAULT_TOTAL_BUDGET_USD
    templates: dict[str, Path] = field(default_factory=dict)
    leak_markers: tuple[str, ...] = ()
    pass_env: tuple[str, ...] = ()


# --- fixture and tasks ------------------------------------------------------------------------


def _read_guards(task_dir: Path) -> frozenset[str]:
    path = task_dir / "guards.txt"
    if not path.exists():
        return frozenset()
    lines = (line.partition("#")[0].strip() for line in path.read_text("utf-8").splitlines())
    return frozenset(line for line in lines if line)


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[Task]:
    tasks = []
    for d in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        prompt = (d / "prompt.md").read_text(encoding="utf-8").strip()
        tasks.append(Task(d.name, prompt, d / "hidden", d / "reference", _read_guards(d)))
    return tasks


def bench_hash(root: Path = BENCH_DIR) -> str:
    """Content hash of the fixture and every task, so rows from different benches never mix."""
    digest = hashlib.sha256()
    for base in (root / "timeparse", root / "tasks"):
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(root)
            cache = {"__pycache__", ".pytest_cache"} & set(rel.parts)
            if path.is_file() and not cache and path.suffix != ".pyc":
                digest.update(rel.as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:12]


def harness_sha() -> str:
    """HEAD plus a hash of the uncommitted diff, so two different dirty trees never look alike."""

    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30, check=False
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    sha = git("rev-parse", "--short=12", "HEAD") or "unknown"
    if not git("status", "--porcelain", "--untracked-files=no"):
        return sha
    return f"{sha}-dirty-{hashlib.sha256(git('diff', 'HEAD').encode()).hexdigest()[:8]}"


def harness_argv(work: Path) -> list[str]:
    argv = [sys.executable, "-m", "harness_maker", "make", str(work), "--autoloop"]
    return argv + ["--preset", "Side", "--targets", "claude-code", "--autonomy-level", "auto_full"]


def runner_hash(model: str, max_turns: int, timeout_s: int, max_budget_usd: float) -> str:
    """Hash of every runner setting that changes what an arm does, so rows never mix them."""
    config = {
        "hm_prefix": HM_PREFIX,
        "agent": agent_argv("<claude>", "<prompt>", model, max_turns, max_budget_usd),
        "harness": harness_argv(Path("<work>"))[1:],
        "timeout_s": timeout_s,
    }
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]


def copy_fixture(dest: Path, fixture: Path = FIXTURE_DIR) -> None:
    shutil.copytree(fixture, dest, ignore=_IGNORED)


def apply_overlay(work: Path, overlay: Path) -> None:
    shutil.copytree(overlay, work, dirs_exist_ok=True, ignore=_IGNORED)


def snapshot_bench() -> tuple[Path, str]:
    """Private copy of the fixture and tasks, so hidden tests are graded from bytes the agent
    could not have edited in the checkout. Returns (root, bench_hash) after verifying the copy."""
    root = Path(tempfile.mkdtemp(prefix="hm-bench-snapshot-"))
    try:
        shutil.copytree(BENCH_DIR, root / "bench", ignore=_IGNORED)
        snap = root / "bench"
        if (digest := bench_hash(snap)) != bench_hash(BENCH_DIR):
            raise OSError("bench files changed while the snapshot was taken")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return snap, digest


# --- grading ----------------------------------------------------------------------------------


def _case_outcome(case: ET.Element) -> str:
    for tag, outcome in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        if case.find(tag) is not None:
            return outcome
    return "passed"


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
    cases = tuple((c.get("name", ""), _case_outcome(c)) for c in root.iter("testcase"))
    return Grade(total["tests"], total["failures"], total["errors"], total["skipped"], cases)


def grade(work: Path, tests_dir: Path, scratch: Path, timeout_s: int = GRADE_TIMEOUT_S) -> Grade:
    """Run `tests_dir` against `work/timeparse` from a clean directory.

    Only the package is copied out of `work`: a pytest.py, sitecustomize.py, conftest.py or
    pytest config the agent left next to it is never importable or readable by the grader, which
    also gets its own ini, rootdir, user-site-free interpreter and a minimal environment.
    """
    if scratch.exists():
        shutil.rmtree(scratch)
    tests, pkg = scratch / "tests", scratch / "pkg"
    try:
        shutil.copytree(tests_dir, tests, ignore=_IGNORED)
        pkg.mkdir()
        if (work / "timeparse").is_dir():
            shutil.copytree(work / "timeparse", pkg / "timeparse", ignore=_IGNORED)
    except (OSError, shutil.Error):
        return Grade(0, 0, 1, 0)
    ini = scratch / "pytest.ini"
    ini.write_text("[pytest]\n", encoding="utf-8")
    xml_path = scratch / "junit.xml"
    env = {k: v for k, v in os.environ.items() if k in _GRADE_ENV or k.startswith("LC_")}
    env.update(
        PYTHONPATH=str(pkg), PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONNOUSERSITE="1", HOME=str(scratch),
    )  # fmt: skip
    argv = [sys.executable, "-s", "-m", "pytest", str(tests), "-q", "-c", str(ini)]
    argv += ["--rootdir", str(tests), "-p", "no:cacheprovider", "--junitxml", str(xml_path)]
    try:
        subprocess.run(
            argv, cwd=tests, env=env, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        return Grade(0, 0, 1, 0)
    return _junit_counts(xml_path)


def _by_function(graded: Grade) -> dict[str, list[str]]:
    funcs: dict[str, list[str]] = {}
    for name, outcome in graded.cases:
        funcs.setdefault(name.partition("[")[0], []).append(outcome)
    return funcs


def check_task(task: Task, scratch: Path, log: Callable[[str], None] | None = None) -> list[str]:
    """Problems that make `task` unable to tell a fix from no fix (empty list = sound).

    Every hidden test must fail on the pristine fixture unless the task lists it in guards.txt
    as a regression guard, and a guard must pass there; a test that always passes proves nothing.
    """
    problems = []
    pristine, reference = scratch / "pristine", scratch / "reference"
    copy_fixture(pristine)
    copy_fixture(reference)
    apply_overlay(reference, task.reference_dir)
    before = grade(pristine, task.hidden_dir, scratch / "g-pristine")
    if before.passed:
        problems.append(f"{task.id}: hidden tests already pass on the pristine fixture")
    funcs = _by_function(before)
    for func, outcomes in funcs.items():
        guard = func in task.guards
        if log is not None:
            tag = " [guard]" if guard else ""
            log(f"  {task.id} pristine {func}: {dict(Counter(outcomes))}{tag}")
        if guard and set(outcomes) != {"passed"}:
            problems.append(f"{task.id}: guard {func} does not pass on the pristine fixture")
        if not guard and "passed" in outcomes:
            problems.append(f"{task.id}: {func} passes on the pristine fixture and is not a guard")
    for missing in sorted(task.guards - set(funcs)):
        problems.append(f"{task.id}: guards.txt names {missing}, which no hidden test defines")
    hidden_ref = grade(reference, task.hidden_dir, scratch / "g-reference")
    if not hidden_ref.passed:
        problems.append(f"{task.id}: hidden tests fail on the reference ({hidden_ref})")
    for name, work in (("pristine", pristine), ("reference", reference)):
        if not grade(work, work / "tests", scratch / f"v-{name}").passed:
            problems.append(f"{task.id}: visible tests fail on the {name} copy")
    return problems


# --- one run ----------------------------------------------------------------------------------


def failure_text(exc: BaseException) -> str:
    """The failing command's own stderr/stdout, which str(exc) leaves out."""
    parts = [str(exc)[-300:]]
    for label in ("stderr", "stdout"):
        data = getattr(exc, label, None)
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        if isinstance(data, str) and data.strip():
            parts.append(f"{label}: {data.strip()[-500:]}")
    return " | ".join(parts)


def _git(work: Path, *args: str) -> None:
    subprocess.run([*_GIT, *args], cwd=work, capture_output=True, timeout=60, check=True)


def build_template(dest: Path, arm: str, fixture: Path = FIXTURE_DIR) -> None:
    """Fixture in a clean git repo; the hm arm adds this checkout's harness as a second commit.

    Built once per run and copied per cell, so every cell of an arm starts from the same bytes
    and a render failure surfaces before any model spend.
    """
    copy_fixture(dest, fixture)
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "fixture")
    if arm == "hm":
        subprocess.run(
            harness_argv(dest),
            cwd=dest,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=SETUP_TIMEOUT_S,
            check=True,
        )
        _git(dest, "add", "-A")
        _git(dest, "commit", "-q", "-m", "harness")


def prepare_work(work: Path, template: Path) -> None:
    shutil.copytree(template, work, symlinks=True)


def prompt_for(task: Task, arm: str) -> str:
    return HM_PREFIX + task.prompt if arm == "hm" else task.prompt


def agent_argv(
    claude_bin: str, prompt: str, model: str, max_turns: int, max_budget_usd: float
) -> list[str]:
    return [
        claude_bin, "-p", prompt, "--output-format", "json", "--dangerously-skip-permissions",
        "--max-turns", str(max_turns), "--model", model, "--max-budget-usd", f"{max_budget_usd:g}",
        "--setting-sources", SETTING_SOURCES, "--strict-mcp-config",
    ]  # fmt: skip


def agent_env(extra: tuple[str, ...] = ()) -> dict[str, str]:
    """Allowlisted environment: auth, proxy and locale only, never the operator's other secrets."""
    keep = {*_AGENT_ENV, *extra}
    env = {k: v for k, v in os.environ.items() if k in keep or k.startswith("LC_")}
    return {k: v for k, v in env.items() if k not in _SESSION_ENV}


def parse_cli_result(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("type") == "result":
            return data
    return None


def _killpg(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def kill_live() -> None:
    """Kill every running agent's process group; they sit in their own session, so a signal
    sent to the runner never reaches them."""
    with _LIVE_LOCK:
        pids = list(_LIVE)
    for pid in pids:
        _killpg(pid)


def _reap(proc: subprocess.Popen[str]) -> tuple[str, str]:
    """Collect output after a kill, bounded: a grandchild outside the group may hold the pipes."""
    try:
        return proc.communicate(timeout=REAP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        return "", ""


def _invoke(
    argv: list[str], work: Path, timeout_s: int, extra_env: tuple[str, ...] = ()
) -> tuple[str, str, int | None]:
    """Run the agent in its own process group so a timeout or interrupt also stops its children."""
    proc = subprocess.Popen(
        argv, cwd=work, env=agent_env(extra_env), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )  # fmt: skip
    with _LIVE_LOCK:
        _LIVE.add(proc.pid)
    try:
        try:
            out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _killpg(proc.pid)
            out, err = _reap(proc)
            return out, err, None
        return out, err, proc.returncode
    except BaseException:
        _killpg(proc.pid)
        raise
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(proc.pid)


def transcript_cost(work: Path, transcript_root: Path) -> Spend:
    """Price every main and subagent transcript turn launched from `work`."""
    turns = economics_source.load_turns(work, transcript_root=transcript_root).turns
    usd = sum(economics.price_turn(t).total_usd for t in turns)
    return Spend(usd, len(turns), sum(1 for t in turns if t.is_sidechain))


def pick_cost(cli_cost: float | None, spend: Spend) -> tuple[float | None, str]:
    """The CLI's own total is the baseline's source; the transcript price covers a lost result.

    A lost result with an empty transcript is unknown, not free: recording $0 would deflate the
    arm's mean and could turn a miss into a pass.
    """
    if cli_cost is not None:
        return cli_cost, "cli"
    if spend.turns == 0:
        return None, "unknown"
    return spend.usd, "transcript"


def leaked(work: Path, texts: list[str], opts: Options) -> bool:
    """Whether the agent's output or transcripts mention where the hidden tests live."""
    with contextlib.suppress(OSError):
        for directory in economics_source.discover_transcript_dirs(
            work, transcript_root=opts.transcript_root
        ):
            texts += [p.read_text("utf-8", "replace") for p in directory.rglob("*.jsonl")]
    return any(marker in text for text in texts for marker in opts.leak_markers)


def run_cell(task: Task, arm: str, rep: int, opts: Options) -> dict[str, Any]:
    run_dir = opts.out / "runs" / f"{task.id}-{arm}-{rep}-{uuid.uuid4().hex[:6]}"
    work = (run_dir / "work").resolve()
    row: dict[str, Any] = {
        "bench": BENCH_ID, "bench_hash": opts.bench_hash, "harness_sha": opts.harness_sha,
        "runner_hash": opts.runner_hash, "model": opts.model, "task": task.id, "arm": arm,
        "rep": rep, "max_budget_usd": opts.max_budget_usd,
        "total_budget_usd": opts.total_budget_usd,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"), "run_dir": str(run_dir),
    }  # fmt: skip
    try:
        run_dir.mkdir(parents=True)
        run_dir.chmod(0o700)
        prepare_work(work, opts.templates[arm])
    except (OSError, shutil.Error, subprocess.SubprocessError) as exc:
        return {**row, "status": "setup_error", "error": failure_text(exc)}
    if STOP.is_set():
        return {**row, "status": "interrupted"}
    argv = agent_argv(
        opts.claude_bin, prompt_for(task, arm), opts.model, opts.max_turns, opts.max_budget_usd
    )
    start = time.monotonic()
    try:
        stdout, stderr, code = _invoke(argv, work, opts.timeout_s, opts.pass_env)
    except OSError as exc:
        return {**row, "status": "setup_error", "error": failure_text(exc)}
    wall = time.monotonic() - start
    if STOP.is_set():
        return {**row, "status": "interrupted"}
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
    cost, source = pick_cost(cli_cost, spend)
    scratch = Path(tempfile.mkdtemp(prefix="hm-bench-grade-"))
    try:
        graded = grade(work, task.hidden_dir, scratch / "g")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {
        **row, "status": status, "exit_code": code,
        "cost_usd": None if cost is None else round(cost, 6),
        "cost_source": source, "cli_cost_usd": cli_cost,
        "transcript_cost_usd": round(spend.usd, 6), "transcript_turns": spend.turns,
        "subagent_turns": spend.subagent_turns,
        "num_turns": result.get("num_turns") if result else None,
        "subtype": result.get("subtype") if result else None, "wall_s": round(wall, 1),
        "hidden": {"tests": graded.tests, "failures": graded.failures,
                   "errors": graded.errors, "skipped": graded.skipped},
        "passed": graded.passed, "leak_suspect": leaked(work, [stdout, stderr], opts),
    }  # fmt: skip


# --- results ----------------------------------------------------------------------------------


def read_rows(out: Path) -> list[dict[str, Any]]:
    """Rows of the results file; a torn line (crash mid-write) is skipped with a warning."""
    path = out / RESULTS
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except ValueError:
            data = None
        if isinstance(data, dict):
            rows.append(data)
        else:
            print(f"warning: {path}:{number}: skipped an unparsable line", file=sys.stderr)
    return rows


def append_row(out: Path, row: dict[str, Any]) -> None:
    """One os.write on an O_APPEND fd, so a row is never interleaved or half-written by us."""
    data = (json.dumps(row) + "\n").encode()
    fd = os.open(out / RESULTS, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            data = b"\n" + data  # a torn last line must not swallow this row
        os.write(fd, data)
    finally:
        os.close(fd)


def pending_cells(
    rows: list[dict[str, Any]], tasks: list[str], arms: list[str], runs: int
) -> list[tuple[str, str, int]]:
    """Cells still to run; a setup or runner failure was ours, not the model's, and is retried."""
    done = {(r["task"], r["arm"], r["rep"]) for r in rows if r.get("status") not in UNUSABLE}
    cells = [(t, a, rep) for t in tasks for rep in range(1, runs + 1) for a in arms]
    return [c for c in cells if c not in done]


def ensure_consistent(rows: list[dict[str, Any]], expected: dict[str, str] | None = None) -> None:
    """Refuse rows that differ in bench, harness, runner settings or model (and `expected`)."""
    usable = [r for r in rows if r.get("status") not in UNUSABLE]
    for name in MIXED_FIELDS:
        seen = {str(r.get(name)) for r in usable}
        if expected is not None and usable:
            seen.add(expected[name])
        if len(seen) > 1:
            raise MixedResultsError(f"results mix {name} values {sorted(seen)}; use a fresh --out")


def _mean(values: list[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def _ratio(hm: float | None, plain: float | None) -> float | None:
    if hm is None or plain is None or plain <= 0:
        return None
    return hm / plain


def _show(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the intent's pre-registered rule (intent/HM-LIGHT-LANE.md, 판정 규칙).

    The verdict compares unrounded ratios, and takes the larger of the CLI and transcript ratios
    because it is open whether the CLI total includes subagents; when the two disagree by more
    than SUSPECT_GAP the number is not trusted at all.
    """
    ensure_consistent(rows)
    usable = [r for r in rows if r.get("status") not in UNUSABLE]
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
    t_ratio = _ratio(arms["hm"]["mean_transcript"], arms["plain"]["mean_transcript"])
    judged = ratio if ratio is None or t_ratio is None else max(ratio, t_ratio)
    gap = 0.0
    if ratio is not None and t_ratio is not None and judged:
        gap = abs(ratio - t_ratio) / judged
    if ratio is None or judged is None or not balanced:
        verdict, why = "no_data", "an arm has no priced runs or the task x arm grid is unbalanced"
    elif gap > SUSPECT_GAP:
        verdict = "suspect"
        why = (f"CLI ratio {_show(ratio)} and transcript ratio {_show(t_ratio)} differ by "
               f"{gap:.0%}; total_cost_usd may leave out subagent spend")  # fmt: skip
    elif judged > TARGET + TARGET_EPS:
        verdict, why = "missed", f"ratio {judged:.3f} > target {TARGET:g}"
    elif arms["hm"]["pass_rate"] < arms["plain"]["pass_rate"]:
        verdict, why = "missed", "hm hidden-test pass rate is below plain"
    else:
        verdict, why = "met", f"ratio {judged:.3f} <= target {TARGET:g} and hm pass rate >= plain"
    first = usable[0] if usable else {}
    return {
        "bench": BENCH_ID, "bench_hash": first.get("bench_hash"),
        "harness_sha": first.get("harness_sha"), "model": first.get("model"),
        "runner_hash": first.get("runner_hash"),
        "tasks": tasks, "runs_per_cell": counts.pop() if balanced else None,
        "arms": arms, "per_task": per_task, "ratio": _show(ratio), "judged_ratio": judged,
        "transcript_ratio": _show(t_ratio), "verdict": verdict, "why": why,
        "setup_errors": len(rows) - len(usable), "target": TARGET,
        "cost_unknown": sum(a["cost_unknown"] for a in arms.values()),
        "leak_suspects": sum(1 for r in usable if r.get("leak_suspect")),
    }  # fmt: skip


def _cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for r in rows if r.get("passed"))
    priced = [r for r in rows if r.get("cost_usd") is not None]
    traced = [r for r in rows if r.get("transcript_turns", 1)]
    return {
        "runs": len(rows),
        "passed": passed,
        "pass_rate": passed / len(rows) if rows else 0.0,
        "cost_unknown": len(rows) - len(priced),
        "mean_cost": _mean([float(r["cost_usd"]) for r in priced]),
        "mean_transcript": _mean([float(r.get("transcript_cost_usd") or 0.0) for r in traced]),
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
    if summary["cost_unknown"]:
        lines.append(
            f"runs with no cost (no CLI result, empty transcript): {summary['cost_unknown']}, "
            "left out of the cost means"
        )
    if summary["leak_suspects"]:
        lines.append(
            f"leak suspects: {summary['leak_suspects']} run(s) whose output names the hidden-test "
            "path; inspect their agent.stdout and transcripts before trusting the pass rate"
        )
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

    Claude Code reads CLAUDE.md, CLAUDE.local.md and .claude/ from the ancestors of the launch
    dir. `top` bounds the walk for tests; the runner always walks to the filesystem root.
    """
    resolved = out.resolve()
    ancestors = [resolved, *resolved.parents]
    if top is not None:
        bound = top.resolve()
        ancestors = [p for p in ancestors if p == bound or bound in p.parents]
    for parent in ancestors:
        if (parent / ".git").exists():
            return f"{parent} is a git work tree"
        for name in ("CLAUDE.md", "CLAUDE.local.md", ".claude"):
            if (parent / name).exists():
                return f"{parent}/{name} would load into both arms"
    return None


def _acquire_lock(out: Path) -> int | None:
    fd = os.open(out / LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def _on_term(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def _spent(row: dict[str, Any]) -> float:
    for key in ("cost_usd", "transcript_cost_usd"):
        if isinstance(row.get(key), int | float):
            return float(row[key])
    return 0.0


def _run_grid(
    cells: list[tuple[str, str, int]], tasks: dict[str, Task], opts: Options, jobs: int,
    spent: float,
) -> int:  # fmt: skip
    """Run `cells`; stop scheduling once total spend passes the cap. Returns cells skipped."""
    lock = threading.Lock()
    total, skipped = spent, 0

    def one(cell: tuple[str, str, int]) -> None:
        nonlocal total, skipped
        if STOP.is_set():
            return
        with lock:
            if total > opts.total_budget_usd:
                skipped += 1
                return
        try:
            row = run_cell(tasks[cell[0]], cell[1], cell[2], opts)
        except Exception as exc:  # noqa: BLE001 - one bad cell must not abort the grid
            row = {
                "bench": BENCH_ID, "bench_hash": opts.bench_hash, "task": cell[0],
                "harness_sha": opts.harness_sha, "runner_hash": opts.runner_hash,
                "model": opts.model, "arm": cell[1], "rep": cell[2], "status": "runner_error",
                "error": f"{type(exc).__name__}: {failure_text(exc)}",
            }  # fmt: skip
        if STOP.is_set():
            return
        with lock:
            append_row(opts.out, row)
            total += _spent(row)
        print(f"  {cell[0]} {cell[1]} #{cell[2]}: {row['status']} "
              f"passed={row.get('passed')} cost={row.get('cost_usd')}", flush=True)  # fmt: skip

    pool = ThreadPoolExecutor(max_workers=max(1, jobs))
    try:
        for future in as_completed([pool.submit(one, c) for c in cells]):
            future.result()
    except BaseException:
        STOP.set()
        pool.shutdown(wait=False, cancel_futures=True)
        kill_live()
        raise
    pool.shutdown()
    return skipped


def _make_options(args: argparse.Namespace, out: Path, digest: str, snap_root: Path) -> Options:
    transcripts = args.transcript_root or economics_source.default_transcript_root()
    return Options(
        out=out, claude_bin=args.claude_bin, model=args.model, max_turns=args.max_turns,
        timeout_s=args.timeout_s, bench_hash=digest, harness_sha=harness_sha(),
        transcript_root=Path(transcripts),
        runner_hash=runner_hash(args.model, args.max_turns, args.timeout_s, args.max_budget_usd),
        max_budget_usd=args.max_budget_usd, total_budget_usd=args.total_budget_usd,
        leak_markers=(str(TASKS_DIR), str(snap_root), "scripts/bench/tasks", "/hidden/"),
        pass_env=tuple(n for n in args.pass_env.split(",") if n),
    )  # fmt: skip


def _cmd_run(args: argparse.Namespace) -> int:
    if os.environ.get("INTEGRATION") != "1":
        print("run calls a live model; set INTEGRATION=1 to opt in", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="hm-bench-"))
    top = (
        Path(args.guard_top) if args.guard_top and os.environ.get("HM_BENCH_TEST") == "1" else None
    )
    reason = guard_out_dir(out, top)
    if reason is not None:
        if not args.out:
            out.rmdir()
        print(f"refusing --out {out}: {reason}; pick a dir outside any project", file=sys.stderr)
        return 2
    all_tasks = load_tasks()
    wanted = args.tasks.split(",") if args.tasks else [t.id for t in all_tasks]
    arms = args.arms.split(",")
    unknown = sorted(set(wanted) - {t.id for t in all_tasks})
    if unknown or not set(arms) <= set(ARMS):
        print(f"unknown task or arm: {unknown or arms}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    lock_fd = _acquire_lock(out)
    if lock_fd is None:
        print(f"refusing --out {out}: another runner holds {LOCK_FILE}", file=sys.stderr)
        return 2
    STOP.clear()
    snap_root: Path | None = None
    previous = signal.getsignal(signal.SIGTERM)
    in_main = threading.current_thread() is threading.main_thread()
    if in_main:
        signal.signal(signal.SIGTERM, _on_term)
    try:
        snap, digest = snapshot_bench()
        snap_root = snap.parent
        tasks = {t.id: t for t in load_tasks(snap / "tasks") if t.id in wanted}
        opts = _make_options(args, out, digest, snap_root)
        rows = read_rows(out)
        try:
            ensure_consistent(rows, {
                "bench_hash": digest, "harness_sha": opts.harness_sha, "model": opts.model,
                "runner_hash": opts.runner_hash,
            })  # fmt: skip
        except MixedResultsError as exc:
            print(f"refusing to resume: {exc}", file=sys.stderr)
            return 2
        cells = pending_cells(rows, list(tasks), arms, args.runs)
        (out / "runs").mkdir(exist_ok=True, mode=0o700)
        templates: dict[str, Path] = {}
        for arm in sorted({a for _, a, _ in cells}):
            templates[arm] = out / ".templates" / arm
            shutil.rmtree(templates[arm], ignore_errors=True)
            templates[arm].parent.mkdir(exist_ok=True, mode=0o700)
            try:
                build_template(templates[arm], arm, snap / "timeparse")
            except (OSError, shutil.Error, subprocess.SubprocessError) as exc:
                print(f"cannot build the {arm} template: {failure_text(exc)}", file=sys.stderr)
                return 2
        opts = replace(opts, templates=templates)
        print(f"bench {BENCH_ID}: {len(cells)} run(s) to go, results in {out / RESULTS}",
              flush=True)  # fmt: skip
        try:
            skipped = _run_grid(cells, tasks, opts, args.jobs, sum(map(_spent, rows)))
        except KeyboardInterrupt:
            print("interrupted: live agents killed; re-run with the same --out to resume",
                  file=sys.stderr)  # fmt: skip
            return 130
        if skipped:
            print(f"stopped: spend passed --total-budget-usd {args.total_budget_usd:g}; "
                  f"{skipped} cell(s) not run", flush=True)  # fmt: skip
    finally:
        if in_main:
            signal.signal(signal.SIGTERM, previous)
        if snap_root is not None:
            shutil.rmtree(snap_root, ignore_errors=True)
        os.close(lock_fd)
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
            problems += check_task(task, Path(scratch) / task.id, log=print)
    for problem in problems:
        print(problem, file=sys.stderr)
    print("check: ok" if not problems else f"check: {len(problems)} problem(s)")
    return 1 if problems else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bench_light_lane",
        description=__doc__.splitlines()[0],
        epilog="WARNING: the agent runs with --dangerously-skip-permissions as you (full user-level"
        " file access); run live benches in a container or throwaway VM.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run both arms (live model; needs INTEGRATION=1)")
    run.add_argument("--out", default=None, help="results dir (default: fresh temp dir)")
    run.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    run.add_argument("--arms", default=",".join(ARMS))
    run.add_argument("--runs", type=int, default=3, help="runs per task and arm")
    run.add_argument(
        "--jobs", type=int, default=1,
        help="runs in parallel; runs share the user's Claude state, so smoke-test live first",
    )  # fmt: skip
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, dest="max_turns")
    run.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S, dest="timeout_s")
    run.add_argument(
        "--max-budget-usd", type=float, default=DEFAULT_MAX_BUDGET_USD, dest="max_budget_usd",
        help="per-run spend cap passed to claude",
    )  # fmt: skip
    run.add_argument(
        "--total-budget-usd", type=float, default=DEFAULT_TOTAL_BUDGET_USD,
        dest="total_budget_usd", help="stop scheduling new runs once recorded spend passes this",
    )  # fmt: skip
    run.add_argument(
        "--pass-env", default="", dest="pass_env",
        help="comma-separated extra env var names for the agent (it gets an allowlist only)",
    )  # fmt: skip
    run.add_argument("--claude-bin", default="claude", dest="claude_bin")
    run.add_argument("--transcript-root", default=None, dest="transcript_root")
    run.add_argument("--guard-top", default=None, dest="guard_top", help=argparse.SUPPRESS)
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
