"""`hm check`: a task's deterministic gates as one JSON line and one exit code."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_DEGRADED = 3
EXIT_TREE_CHANGED = 4
EXIT_APPROVAL = 5

#: Precedence of the non-zero exits when several apply (usage never reaches here: argparse).
_PRECEDENCE = (EXIT_FAILED, EXIT_TREE_CHANGED, EXIT_DEGRADED, EXIT_APPROVAL)

#: A code file for the skip-path rule (SPEC AC-005 `ac`); a test file is any path under a
#: `tests/` or `test/` directory.
CODE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".java",
        ".kt",
        ".rb",
        ".sh",
    }
)
HOOK_FILES: tuple[str, ...] = (".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json")
GATE_TIMEOUT_S = 3600
#: The exit a gate row records when it outlived `GATE_TIMEOUT_S` (as coreutils `timeout`).
EXIT_TIMEOUT = 124
_GATE_TAIL = 30
_GIT_ENV = {"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}

#: Writes the one outcome junit cannot express: a non-strict XPASS is recorded as a plain pass.
_OUTCOME_PLUGIN = """\
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.passed and hasattr(rep, "wasxfail"):
        item.user_properties.append(("hm_check_outcome", "xpassed"))
"""
_PLUGIN_NAME = "hm_check_outcomes"

#: Records the in-repo paths every pytest process opens in-process (PEP 578 `open` events), one
#: JSON file per process, so `--reuse` can void a declared-inert path a test actually read
#: (SPEC-hm-check-docs-only-reuse ADR-004). The controller lists the xdist workers it saw go
#: down; the parent refuses the set when any of them left no file.
_READSET_PLUGIN = """\
import json
import os
import sys
import threading

import pytest

_DIR = os.environ.get("HM_CHECK_READSET_DIR")
_ROOT = os.path.realpath(os.environ.get("HM_CHECK_READSET_ROOT") or os.getcwd())
_SEEN = set()
_LOCAL = threading.local()
_WORKERS = set()


def _hook(event, args):
    if event != "open" or getattr(_LOCAL, "busy", False) or not args:
        return
    if isinstance(args[0], int):
        return
    _LOCAL.busy = True
    try:
        rel = os.path.relpath(os.path.realpath(os.fsdecode(args[0])), _ROOT)
        outside = rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel)
        if not outside:
            _SEEN.add(rel.replace(os.sep, "/"))
    except Exception:
        pass
    finally:
        _LOCAL.busy = False


if _DIR:
    sys.addaudithook(_hook)


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    _WORKERS.add(str(node.gateway.id))


def _write(config):
    if not _DIR:
        return
    _LOCAL.busy = True
    try:
        worker = getattr(config, "workerinput", {}).get("workerid")
        data = {"role": "worker" if worker else "main", "id": worker,
                "workers": sorted(_WORKERS), "paths": sorted(_SEEN)}
        with open(os.path.join(_DIR, f"{os.getpid()}.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    finally:
        _LOCAL.busy = False


def pytest_sessionfinish(session, exitstatus):
    _write(session.config)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_unconfigure(config):
    # Outermost wrapper: rewrites the file after every plugin's unconfigure (and the terminal
    # summary before it) has run, so their reads are in the set too.
    yield
    _write(config)
"""
_READSET_NAME = "hm_check_readset"


# ── process plumbing ──────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> str | None:
    """stdout of a bounded git call, or None. `GIT_OPTIONAL_LOCKS=0`: no index refresh write."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            timeout=60,
            check=False,
            env={**os.environ, **_GIT_ENV},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="surrogateescape")


def _git_bytes(root: Path, *args: str) -> bytes | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            timeout=60,
            check=False,
            env={**os.environ, **_GIT_ENV},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def gate_env(extra: dict[str, str] | None = None, *, root: Path | None = None) -> dict[str, str]:
    """The environment every gate subprocess runs in: no bytecode, and the project's own
    `.venv/bin` first on PATH.

    hm runs under `uv run --no-project`, which no longer puts the project environment on PATH,
    so a bare `pytest -q` or `ruff check .` gate would otherwise find hm's tools, or none.
    """
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(extra or {})}
    bin_dir = root / ".venv" / "bin" if root is not None else None
    if bin_dir is not None and bin_dir.is_dir():
        env["PATH"] = os.pathsep.join(p for p in (str(bin_dir), env.get("PATH", "")) if p)
    return env


def _run(argv: list[str], root: Path, env: dict[str, str]) -> tuple[int, str]:
    """Run in its own process group; any abnormal exit kills the whole group."""
    try:
        proc = subprocess.Popen(
            argv,
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    try:
        out, _ = proc.communicate(timeout=GATE_TIMEOUT_S)
    except BaseException as exc:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        partial = ""
        with contextlib.suppress(Exception):
            partial, _ = proc.communicate(timeout=5)
        if isinstance(exc, subprocess.TimeoutExpired):
            # A failed row, not a traceback: the caller still prints its one JSON line.
            return EXIT_TIMEOUT, f"{partial or ''}\ntimed out after {GATE_TIMEOUT_S}s"
        raise
    return proc.returncode, out or ""


def _tail(text: str) -> str:
    return "\n".join(text.splitlines()[-_GATE_TAIL:])


def _is_pytest(argv: list[str]) -> bool:
    return any(Path(tok).name in ("pytest", "py.test") for tok in argv)


# ── the tree snapshot (ADR-002) ───────────────────────────────────────────────


def _listed_files(root: Path) -> list[str]:
    out = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if out is not None:
        return sorted({p for p in out.split("\0") if p})
    found: list[str] = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if rel.parts[0] == ".git" or not p.is_file():
            continue
        found.append(rel.as_posix())
    return sorted(found)


def snapshot(root: Path) -> dict[str, str]:
    """sha256 of every tracked or unignored path; a listed path missing on disk is `absent`."""
    digests: dict[str, str] = {}
    for rel in _listed_files(root):
        path = root / rel
        try:
            digests[rel] = (
                "link:" + os.readlink(path)
                if path.is_symlink()
                else hashlib.sha256(path.read_bytes()).hexdigest()
            )
        except FileNotFoundError:
            digests[rel] = "absent"
        except OSError as exc:
            digests[rel] = f"unreadable:{type(exc).__name__}"
    return digests


def tree_delta(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


# ── the change set ─────────────────────────────────────────────────────────────


def has_head(root: Path) -> bool:
    return _git(root, "rev-parse", "--verify", "-q", "HEAD^{commit}") is not None


def changed_paths(root: Path) -> list[str]:
    """`git diff HEAD`, staged, and untracked-unignored paths (SPEC AC-005 `security`)."""
    if not has_head(root):
        return _listed_files(root)
    found: set[str] = set()
    for args in (
        ("diff", "--name-only", "-z", "HEAD"),
        ("diff", "--name-only", "-z", "--cached"),
        ("ls-files", "-z", "--others", "--exclude-standard"),
    ):
        out = _git(root, *args)
        if out:
            found.update(p for p in out.split("\0") if p)
    return sorted(found)


def is_code_or_test(path: str) -> bool:
    parts = Path(path).parts
    return Path(path).suffix.lower() in CODE_SUFFIXES or any(p in ("tests", "test") for p in parts)


def head_text(root: Path, rel: str) -> str | None:
    if not has_head(root):
        return None
    data = _git_bytes(root, "show", f"HEAD:{rel}")
    return None if data is None else data.decode("utf-8", errors="replace")


def head_has(root: Path, rel: str) -> bool:
    return has_head(root) and _git(root, "cat-file", "-e", f"HEAD:{rel}") is not None


# ── config and SPEC ────────────────────────────────────────────────────────────


def _harness_config(root: Path) -> dict[str, Any]:
    from harness_maker.io_utils import load_harness_yaml

    path = root / ".claude" / "harness.yaml"
    if not path.is_file():
        return {}
    try:
        data = load_harness_yaml(path)
    except Exception:  # noqa: BLE001 — an unreadable config reads as defaults, never a crash
        return {}
    return data if isinstance(data, dict) else {}


def _dig(config: dict[str, Any], *keys: str) -> Any:
    node: Any = config
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _spec_dir(root: Path, slug: str) -> Path:
    from harness_maker import spec_machine

    return spec_machine._named_spec_dir(root, slug, root)


# ── sections ───────────────────────────────────────────────────────────────────


@dataclass
class Section:
    body: dict[str, Any]
    code: int = EXIT_OK


@dataclass
class Outcome:
    outcome: str
    detail: str = ""


# The one level at which a SPEC with no approval stamp may proceed (AC-005 approval row).
_SELF_APPROVING = "auto_full"


def approval_section(root: Path, slug: str, config: dict[str, Any]) -> Section:
    """approved/exempt pass; missing (and legacy, ADR-006) pass only at `_SELF_APPROVING`."""
    from harness_maker import spec_machine

    state = spec_machine.approval_state(root, slug)
    level = _dig(config, "autonomy", "level")
    body: dict[str, Any] = {"state": state.state, "level": level}
    if state.detail:
        body["detail"] = state.detail
    if state.notice:
        body["notice"] = state.notice
    if state.state in ("approved", "exempt"):
        return Section({"ok": True, **body})
    if state.state in ("missing", "legacy"):
        if level == _SELF_APPROVING:
            return Section({"ok": True, "pending": True, **body})
        return Section({"ok": False, **body}, EXIT_APPROVAL)
    return Section({"ok": False, **body}, EXIT_APPROVAL)


def gate_commands(root: Path, config: dict[str, Any]) -> tuple[list[str], str | None, str]:
    """The gate commands, why there are none, and where they came from."""
    from harness_maker.observability.verification_cache import spec_plan
    from harness_maker.verification_plan import read_plan

    plan = read_plan(root)
    commands: list[str]
    source: str
    if plan.degraded and plan.ci_absent:
        py, why = project_python(root)
        if py is None:
            return [], f"{plan.reason}; and {why}", "none"
        derived = spec_plan(root, shlex.quote(str(py)))
        if isinstance(derived, str):
            return [], derived, "none"
        commands, source = derived, "pyproject"
    elif plan.degraded:
        return [], plan.reason or "the CI plan is degraded", "none"
    else:
        commands, source = plan.primary_commands(), "ci"
        if not commands:
            return [], "CI declares no blocking gate", "none"
    extra = _dig(config, "reviewers", "mechanical_checks")
    if isinstance(extra, list):
        commands += [c for c in extra if isinstance(c, str) and c.strip()]
    return commands, None, source


def gates_section(root: Path, config: dict[str, Any]) -> Section:
    return gates_with_read_set(root, config)[0]


def _merge_read_set(run_dir: Path) -> set[str] | None:
    """One pytest command's read-set, or None when any process it started left no record."""
    mains: list[dict[str, Any]] = []
    workers: dict[str, set[str]] = {}
    for f in sorted(run_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("paths"), list):
            return None
        if data.get("role") == "worker":
            workers[str(data.get("id"))] = set(map(str, data["paths"]))
        else:
            mains.append(data)
    if len(mains) != 1:
        return None
    expected = set(map(str, mains[0].get("workers") or []))
    if not expected <= set(workers):
        return None
    paths = set(map(str, mains[0]["paths"]))
    for w in expected:
        paths |= workers[w]
    return paths


def gates_with_read_set(root: Path, config: dict[str, Any]) -> tuple[Section, list[str] | None]:
    """The gate section, plus the union of in-repo paths its pytest gates opened in-process
    (None when no pytest gate ran or any read-set is incomplete)."""
    commands, reason, source = gate_commands(root, config)
    if reason is not None:
        return Section({"ok": False, "degraded": True, "reason": reason}, EXIT_DEGRADED), None
    results: list[dict[str, Any]] = []
    union: set[str] | None = None
    complete = True
    with tempfile.TemporaryDirectory(prefix="hm-check-readset-") as tmp:
        (Path(tmp) / f"{_READSET_NAME}.py").write_text(_READSET_PLUGIN, encoding="utf-8")
        for i, cmd in enumerate(commands):
            argv = shlex.split(cmd)
            env = gate_env(root=root)
            run_dir: Path | None = None
            if _is_pytest(argv):
                run_dir = Path(tmp) / f"run-{i}"
                run_dir.mkdir()
                argv += ["-p", "no:cacheprovider", "-p", _READSET_NAME]
                pythonpath = os.pathsep.join(
                    p for p in (tmp, os.environ.get("PYTHONPATH", "")) if p
                )
                env = gate_env(
                    {
                        "PYTHONPATH": pythonpath,
                        "HM_CHECK_READSET_DIR": str(run_dir),
                        "HM_CHECK_READSET_ROOT": str(root),
                    },
                    root=root,
                )
            code, out = _run(argv, root, env)
            row: dict[str, Any] = {"cmd": cmd, "exit": code}
            if code != 0:
                row["tail"] = _tail(out)
            results.append(row)
            if run_dir is not None:
                paths = _merge_read_set(run_dir)
                if paths is None:
                    complete = False
                else:
                    union = (union or set()) | paths
    ok = all(r["exit"] == 0 for r in results)
    section = Section(
        {"ok": ok, "source": source, "results": results}, EXIT_OK if ok else EXIT_FAILED
    )
    return section, (sorted(union) if complete and union is not None else None)


# ── pytest outcomes from junit (ADR-004) ──────────────────────────────────────


def _dotted(file: str) -> str:
    return file.removesuffix(".py").replace("/", ".")


def _id_parts(test_id: str) -> tuple[str, str, str]:
    """(file, junit classname, junit name) for a pytest node id."""
    file, _, rest = test_id.partition("::")
    parts = rest.split("::") if rest else []
    if len(parts) >= 2:
        return file, f"{_dotted(file)}.{'.'.join(parts[:-1])}", parts[-1]
    return file, _dotted(file), parts[0] if parts else ""


def _static_test_names(source: str) -> list[str]:
    """Only function definitions: a `test_cases = [...]` assignment is not a test to run."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    fn = (ast.FunctionDef, ast.AsyncFunctionDef)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, fn) and node.name.startswith("test"):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.update(
                f"{node.name}::{i.name}"
                for i in node.body
                if isinstance(i, fn) and i.name.startswith("test")
            )
    return sorted(names)


def _top_level_names(source: str) -> set[str] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if isinstance(node, ast.ClassDef):
                names.update(
                    f"{node.name}::{i.name}"
                    for i in node.body
                    if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def _statically_present(root: Path, test_id: str) -> bool | None:
    """Does the node id name a test in its file? None: the file does not parse (pytest says why)."""
    file, _, rest = test_id.partition("::")
    path = root / file
    if not path.is_file():
        return False
    if not rest:
        return True
    try:
        names = _top_level_names(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    if names is None:
        return None
    return re.sub(r"\[.*\]$", "", rest) in names


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


_PROJECT_PYTHON: dict[tuple[str, int, bool, str | None], tuple[Path | None, str | None]] = {}


def _lock_tracked(root: Path) -> bool:
    return (root / "uv.lock").is_file() and (
        _git_bytes(root, "ls-files", "--error-unmatch", "uv.lock") is not None
    )


def project_python(root: Path) -> tuple[Path | None, str | None]:
    """The project's interpreter, or why there is none: the one place that decides it.

    hm's own calls run with `--no-project`, so `.venv` is no longer a side effect of running
    hm. uv is asked for one only when the project says it is uv-managed by tracking `uv.lock`;
    `--frozen` never rewrites that lock and `--inexact` keeps what the user installed by hand.
    The main checkout's `.venv` is never borrowed from a worktree: an editable install there
    imports the main checkout's code, and the gate would judge the wrong tree.
    """
    py = root / ".venv" / "bin" / "python"
    tracked = _lock_tracked(root)
    uv = shutil.which("uv") if tracked else None
    # One answer per state of the project: a failed sync is not retried by the next reader.
    key = (str(root), (root / "uv.lock").stat().st_mtime_ns if tracked else 0, py.is_file(), uv)
    if key not in _PROJECT_PYTHON:
        found = _resolve_project_python(root, py, tracked=tracked, uv=uv)
        # Also under the state the sync left behind, so the `.venv` it created is not synced again.
        _PROJECT_PYTHON[key] = _PROJECT_PYTHON[(*key[:2], py.is_file(), uv)] = found
    return _PROJECT_PYTHON[key]


def _resolve_project_python(
    root: Path, py: Path, *, tracked: bool, uv: str | None
) -> tuple[Path | None, str | None]:
    if tracked:
        if uv is not None:
            code, out = _run([uv, "sync", "--frozen", "--inexact"], root, gate_env())
            if code != 0:
                return None, f"uv sync --frozen failed in {root}: {_last_line(out)}"
        elif not py.is_file():
            return None, f"no .venv/bin/python in {root}; uv.lock is tracked but uv is not on PATH"
    if py.is_file():
        return py, None
    return None, (
        f"no .venv/bin/python in {root} (a worktree does not share the main checkout's .venv); "
        "hm creates one only for a tracked uv.lock"
    )


def _imports_pytest(py: Path) -> bool:
    try:
        proc = subprocess.run(
            [str(py), "-c", "import pytest"], capture_output=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


# uv options that take the next token as their value; `uv run --with pytest pytest` names
# pytest twice and only the second one runs it.
_VALUE_OPTIONS = frozenset(
    {
        "--with", "--with-editable", "--with-requirements", "--group", "--only-group",
        "--no-group", "--extra", "--python", "-p", "--project", "--directory", "--env-file",
        "--package", "--index", "--upgrade-package", "-P", "--reinstall-package",
        "--no-install-package", "--refresh-package",
    }
)  # fmt: skip


def _pytest_prefix(argv: list[str]) -> list[str] | None:
    skip = False
    for i, tok in enumerate(argv):
        if skip:
            skip = False
        elif tok in _VALUE_OPTIONS:
            skip = True
        elif Path(tok).name in ("pytest", "py.test"):
            return argv[: i + 1]
    return None


def pytest_runner(root: Path, commands: Iterable[str]) -> list[str] | None:
    """The project interpreter when it can import pytest, else the first gate command that
    runs pytest. A `.venv` without pytest reported every test as `deselected`."""
    py, _why = project_python(root)
    if py is not None and _imports_pytest(py):
        return [str(py), "-m", "pytest"]
    for cmd in commands:
        prefix = _pytest_prefix(shlex.split(cmd))
        if prefix is not None:
            return prefix
    return None


#: Files that mark a Python test setup, at the root or one directory down (a monorepo's
#: `backend/`). Without any of them, installing pytest is not the fix: the RED and AC gates
#: cannot run this project's tests at all (SPEC-pytest-only).
_PY_MARKERS = (
    "pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "pytest.ini", "conftest.py",
    "Pipfile", "poetry.lock", "uv.lock", "requirements*.txt",
)  # fmt: skip


def _python_project(root: Path) -> bool:
    return any(next(root.glob(p), None) or next(root.glob(f"*/{p}"), None) for p in _PY_MARKERS)


def no_runner_reason(root: Path) -> str:
    """Why `pytest_runner` found nothing, in words the DRI can act on."""
    py, why = project_python(root)
    if py is not None:
        return (
            f"{py} has no pytest and no gate command runs pytest; install pytest there "
            "(uv: add it to a dependency group; if uv.lock is not yours, `git rm uv.lock`)"
        )
    if why is not None and _lock_tracked(root):
        return why
    if not _python_project(root):
        return (
            "the RED and AC gates run pytest only, and no Python test setup was found at the "
            "project root or one level down; a testable AC cannot pass here, so make it a "
            "judgment AC"
        )
    return "no pytest runner"


def _exception_line(text: str) -> str:
    lines = [ln[1:].strip() for ln in text.splitlines() if ln.startswith("E ")]
    for ln in reversed(lines):
        if re.match(r"^[\w.]+(Error|Exception|Exit)\b", ln):
            return ln
    return lines[-1] if lines else ""


def _inside(root: Path, rel: str) -> bool:
    """A listed test file must be a relative path that resolves under the project root."""
    if not rel or Path(rel).is_absolute():
        return False
    return (root / rel).resolve().is_relative_to(root.resolve())


def run_tests(root: Path, runner: list[str], test_ids: list[str]) -> dict[str, Outcome]:
    """One pytest run over the files of `test_ids`; outcomes read from its junit XML."""
    outcomes: dict[str, Outcome] = {}
    runnable: list[str] = []
    for tid in test_ids:
        if not _inside(root, tid.partition("::")[0]):
            outcomes[tid] = Outcome(
                "not collected", "the node id resolves outside the project root"
            )
            continue
        present = _statically_present(root, tid)
        if present is False:
            outcomes[tid] = Outcome("not collected", "the node id names no test")
        else:
            runnable.append(tid)
    if not runnable:
        return outcomes
    files = sorted({tid.partition("::")[0] for tid in runnable})
    with tempfile.TemporaryDirectory(prefix="hm-check-") as tmp:
        (Path(tmp) / f"{_PLUGIN_NAME}.py").write_text(_OUTCOME_PLUGIN, encoding="utf-8")
        junit = Path(tmp) / "junit.xml"
        argv = [
            *runner,
            "-p",
            "no:cacheprovider",
            "-p",
            _PLUGIN_NAME,
            "-q",
            "--tb=short",
            "--continue-on-collection-errors",
            f"--junitxml={junit}",
            "--",
            *files,
        ]
        pythonpath = os.pathsep.join(p for p in (tmp, os.environ.get("PYTHONPATH", "")) if p)
        code, out = _run(argv, root, gate_env({"PYTHONPATH": pythonpath}, root=root))
        wrote_junit = junit.is_file()
        cases = _junit_cases(junit)
    if not wrote_junit:
        # The runner never got as far as pytest's report (no pytest in that interpreter, a
        # command that does not exist): that is an error with a cause, never `deselected`.
        for tid in runnable:
            outcomes[tid] = Outcome("error", _tail(out))
        return outcomes
    module_errors = {name: oc for (cls, name), oc in cases.items() if cls == ""}
    for tid in runnable:
        file, cls, name = _id_parts(tid)
        if _dotted(file) in module_errors:
            outcomes[tid] = module_errors[_dotted(file)]
            continue
        if not cases and code not in (0, 1, 5):
            outcomes[tid] = Outcome("error", _tail(out))
            continue
        matched = [
            oc
            for (c, n), oc in cases.items()
            if c == cls and (n == name or ("[" not in name and n.startswith(name + "[")))
        ]
        outcomes[tid] = _merge(matched) if matched else Outcome("deselected")
    return outcomes


_RANK = ("error", "failed", "xpassed", "skipped", "xfailed", "passed")


def _merge(found: list[Outcome]) -> Outcome:
    return min(found, key=lambda o: _RANK.index(o.outcome))


def _junit_cases(path: Path) -> dict[tuple[str, str], Outcome]:
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError):
        return {}
    cases: dict[tuple[str, str], Outcome] = {}
    for tc in tree.iter("testcase"):
        key = (tc.get("classname") or "", tc.get("name") or "")
        props = {p.get("name"): p.get("value") for p in tc.iter("property")}
        outcome = Outcome("passed")
        for child in tc:
            text = f"{child.get('message') or ''}\n{child.text or ''}"
            if child.tag == "failure":
                outcome = Outcome("failed", text)
            elif child.tag == "error":
                outcome = Outcome("error", text)
            elif child.tag == "skipped":
                msg = child.get("message") or ""
                if "passes unexpectedly" in msg:
                    outcome = Outcome("xpassed", msg)
                elif child.get("type") == "pytest.xfail":
                    outcome = Outcome("xfailed", msg)
                else:
                    outcome = Outcome("skipped", msg)
        if props.get("hm_check_outcome") == "xpassed":
            outcome = Outcome("xpassed")
        cases[key] = _merge([cases[key], outcome]) if key in cases else outcome
    return cases


# ── red_by_import (SPEC AC-005 `--red`) ───────────────────────────────────────


@dataclass(frozen=True)
class ImportName:
    module: str
    symbol: str | None


def _module_files(module: str) -> list[str]:
    rel = module.replace(".", "/")
    return [f"{base}{rel}{tail}" for base in ("", "src/") for tail in (".py", "/__init__.py")]


def _first_party_top(root: Path, module: str) -> bool:
    top = module.split(".")[0]
    return any(
        (root / base / top).is_dir() or (root / base / f"{top}.py").is_file()
        for base in ("", "src")
    )


def _module_file_now(root: Path, module: str) -> str | None:
    return next((f for f in _module_files(module) if (root / f).is_file()), None)


def _module_at_head(root: Path, module: str) -> str | None:
    return next((f for f in _module_files(module) if head_has(root, f)), None)


def _defines(source: str | None, symbol: str) -> bool:
    if source is None:
        return False
    names = _top_level_names(source)
    return names is not None and symbol in names


def absent_at_head(root: Path, name: ImportName) -> bool:
    if name.symbol is None:
        return _module_at_head(root, name.module) is None
    if _module_at_head(root, f"{name.module}.{name.symbol}") is not None:
        return False
    file = _module_at_head(root, name.module)
    return file is None or not _defines(head_text(root, file), name.symbol)


def red_import_name(root: Path, text: str) -> ImportName | None:
    """The first-party name an import failure is about, when it is absent at HEAD."""
    line = _exception_line(text)
    name: ImportName | None = None
    if m := re.match(r"ModuleNotFoundError: No module named '([\w.]+)'", line):
        name = ImportName(m.group(1), None)
    elif m := re.match(r"ImportError: cannot import name '(\w+)' from '([\w.]+)'", line):
        name = ImportName(m.group(2), m.group(1))
    elif m := re.match(r"AttributeError: module '([\w.]+)' has no attribute '(\w+)'", line):
        name = ImportName(m.group(1), m.group(2))
    if name is None or not _first_party_top(root, name.module):
        return None
    return name if absent_at_head(root, name) else None


def _real_reason(outcome: Outcome) -> bool:
    """A failure that is not about the test's own syntax, a missing fixture or an import."""
    line = _exception_line(outcome.detail)
    if re.match(r"(SyntaxError|IndentationError|TabError)\b", line):
        return False
    if "fixture '" in outcome.detail and "' not found" in outcome.detail:
        return False
    if outcome.outcome == "error" and "collection failure" in outcome.detail:
        return False
    return not re.match(r"(ImportError|ModuleNotFoundError)\b", line) and not re.match(
        r"AttributeError: module '", line
    )


def test_file_imports(root: Path, test_ids: Iterable[str]) -> list[tuple[str, ImportName]]:
    """Every absolute import in the files of `test_ids`, statically, with its test id."""
    found: list[tuple[str, ImportName]] = []
    seen: set[tuple[str, ImportName]] = set()
    for tid in test_ids:
        path = root / tid.partition("::")[0]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            names: list[ImportName] = []
            if isinstance(node, ast.Import):
                names = [ImportName(a.name, None) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [ImportName(node.module, a.name) for a in node.names if a.name != "*"]
            for n in names:
                key = (tid.partition("::")[0], n)
                if key not in seen:
                    seen.add(key)
                    found.append((tid, n))
    return found


def implemented(root: Path, name: ImportName, changed: set[str]) -> bool:
    """Defined as a module file, or a top-level def/class/assignment, in a changed file."""
    if name.symbol is not None:
        sub = _module_file_now(root, f"{name.module}.{name.symbol}")
        if sub is not None and sub in changed:
            return True
        file = _module_file_now(root, name.module)
        if file is None or file not in changed:
            return False
        try:
            return _defines((root / file).read_text(encoding="utf-8"), name.symbol)
        except OSError:
            return False
    file = _module_file_now(root, name.module)
    return file is not None and file in changed


# ── ac ─────────────────────────────────────────────────────────────────────────


@dataclass
class SpecView:
    model: Any
    yaml_path: Path

    def live(self) -> list[Any]:
        return [ac for ac in self.model.ac if not ac.superseded_by]

    def testable(self) -> list[Any]:
        return [ac for ac in self.live() if ac.type != "judgment"]

    def judgment(self) -> list[Any]:
        return [ac for ac in self.live() if ac.type == "judgment"]


def load_spec(root: Path, slug: str) -> SpecView | None:
    from harness_maker import spec_machine

    yaml_path = _spec_dir(root, slug) / f"SPEC-{slug}.machine.yaml"
    try:
        return SpecView(spec_machine.load(yaml_path), yaml_path)
    except Exception:  # noqa: BLE001 — approval reports why it is unreadable
        return None


def _no_spec(approval_state: str) -> Section:
    """No readable SPEC is approval's `no_spec`/`malformed` (exit 5), not a failed test."""
    body = {"ok": False, "reason": "no readable machine SPEC"}
    if approval_state in ("no_spec", "malformed"):
        return Section({**body, "see": "approval"}, EXIT_APPROVAL)
    return Section(body, EXIT_FAILED)


def ac_section(
    root: Path,
    spec: SpecView | None,
    approval_state: str,
    changed: list[str],
    runner: list[str] | None,
) -> Section:
    from harness_maker.spec_machine import find_unjudged

    if spec is None:
        return _no_spec(approval_state)
    if not spec.model.ac:
        code_change = sorted(p for p in changed if is_code_or_test(p))
        if approval_state == "exempt" and not code_change:
            return Section({"ok": True, "reason": "skip-path"})
        if approval_state == "exempt":
            return Section(
                {"ok": False, "reason": "skip-path SPEC with a code change", "paths": code_change},
                EXIT_FAILED,
            )
        return Section({"ok": False, "reason": "ac is [] and the SPEC is not exempt"}, EXIT_FAILED)

    failed: dict[str, Any] = {}
    to_run: dict[str, list[str]] = {}
    for ac in spec.testable():
        if ac.pending_test:
            failed[ac.id] = "pending_test is true"
        elif not ac.test_ids:
            failed[ac.id] = "no test_ids"
        else:
            to_run[ac.id] = list(ac.test_ids)
    if spec.judgment():
        try:
            unjudged = set(find_unjudged(spec.yaml_path, root))
        except Exception as exc:  # noqa: BLE001 — fail closed with the reason
            unjudged = {ac.id for ac in spec.judgment()}
            failed["judgment"] = f"cannot read verdicts: {type(exc).__name__}"
        for ac in spec.judgment():
            if ac.id in unjudged:
                failed[ac.id] = "no current pass verdict"

    if to_run and runner is None:
        return Section(
            {"ok": False, "degraded": True, "reason": no_runner_reason(root), "failed": failed},
            EXIT_DEGRADED,
        )
    ids = sorted({t for ts in to_run.values() for t in ts})
    outcomes = run_tests(root, runner, ids) if to_run and runner else {}
    for ac_id, ts in to_run.items():
        bad = {t: outcomes[t].outcome for t in ts if outcomes[t].outcome != "passed"}
        if bad:
            failed[ac_id] = {"outcomes": bad}

    changed_set = set(changed)
    red_by_import: list[dict[str, Any]] = []
    for ac in spec.testable():
        for tid, name in test_file_imports(root, ac.test_ids):
            if not _first_party_top(root, name.module) or not absent_at_head(root, name):
                continue
            done = implemented(root, name, changed_set)
            red_by_import.append(
                {
                    "ac": ac.id,
                    "test_id": tid,
                    "module": name.module,
                    "symbol": name.symbol,
                    "implemented": done,
                }
            )
            if not done:
                failed.setdefault(ac.id, "red_by_import not implemented")
    reason = (
        "red_by_import not implemented"
        if any(not e["implemented"] for e in red_by_import)
        else None
    )
    body: dict[str, Any] = {
        "ok": not failed,
        "testable": len(spec.testable()),
        "judgment": len(spec.judgment()),
        "failed": failed,
        "red_by_import": red_by_import,
    }
    if reason:
        body["reason"] = reason
    return Section(body, EXIT_OK if not failed else EXIT_FAILED)


def _is_test_file(rel: str) -> bool:
    name = Path(rel).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def red_discovery(root: Path, spec: SpecView, runner: list[str]) -> dict[str, list[str]]:
    """Tests the name convention gives each AC with empty `test_ids` (SPEC-hm-cost-p4 IRR-001).

    Read-only, and scoped to changed test files: Phase A's tests are new, and collecting a
    whole suite would cost the minutes the RED run is meant to save. A file that fails to
    collect is Phase A's usual RED (a module-level import of a name that does not exist yet),
    so it binds by its static function names instead of binding nothing.
    """
    from harness_maker import spec_machine

    testable = spec.testable()
    empty = [ac for ac in testable if not ac.test_ids]
    if not empty:
        return {}
    files = sorted(p for p in changed_paths(root) if _is_test_file(p) and (root / p).is_file())
    if not files:
        return {}
    argv = [*runner, "-p", "no:cacheprovider", "-o", "addopts=", "--collect-only", "-q",
            "--no-header", "--continue-on-collection-errors", "--", *files]  # fmt: skip
    _code, out = _run(argv, root, gate_env(root=root))
    # `-q --collect-only` prints one node id per line; a case id may hold spaces.
    nodeids = [
        ln.strip()
        for ln in out.splitlines()
        if ".py::" in ln and not ln.startswith(("ERROR ", "FAILED "))
    ]
    collected = {n.partition("::")[0] for n in nodeids}
    golden = spec.yaml_path.name.removesuffix(".machine.yaml") + ".golden.json"
    golden_tests: list[str] = []
    for rel in files:
        if rel in collected:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError:
            continue
        names = _static_test_names(text)
        nodeids += [f"{rel}::{n}" for n in names]
        if golden in text:  # the recipe's literal file name; a computed path is not detected
            golden_tests += [f"{rel}::{n}" for n in names]
    found: dict[str, list[str]] = {}
    for ac in empty:
        ids = spec_machine.ac_tests_for(ac.id, nodeids)
        if not ids and ac.type == "parametric":
            ids = golden_tests
        if ids:
            found[ac.id] = ids
    return found


def red_section(
    root: Path,
    spec: SpecView | None,
    runner: list[str] | None,
    green_ok: set[str],
    approval_state: str = "",
) -> Section:
    if spec is None:
        return _no_spec(approval_state)
    testable = spec.testable()
    if not testable:
        return Section({"ok": False, "degraded": True, "reason": "no testable AC"}, EXIT_DEGRADED)
    if runner is None:
        return Section(
            {"ok": False, "degraded": True, "reason": no_runner_reason(root)}, EXIT_DEGRADED
        )
    discovered = red_discovery(root, spec, runner)
    bound = {ac.id: list(ac.test_ids) or discovered.get(ac.id, []) for ac in testable}
    ids = sorted({t for ts in bound.values() for t in ts})
    outcomes = run_tests(root, runner, ids) if ids else {}
    not_red: dict[str, Any] = {}
    green_before: list[str] = []
    waived: list[str] = []
    red_by_import: list[dict[str, Any]] = []
    for ac in testable:
        if not bound[ac.id]:
            not_red[ac.id] = "no test_ids"
            continue
        is_red = False
        for tid in bound[ac.id]:
            oc = outcomes[tid]
            if oc.outcome not in ("failed", "error"):
                continue
            if _real_reason(oc):
                is_red = True
                continue
            name = red_import_name(root, oc.detail)
            if name is not None:
                is_red = True
                red_by_import.append(
                    {"ac": ac.id, "test_id": tid, "module": name.module, "symbol": name.symbol}
                )
        if is_red:
            continue
        seen = {tid: outcomes[tid].outcome for tid in bound[ac.id]}
        if all(o == "passed" for o in seen.values()):
            green_before.append(ac.id)
            if ac.id in green_ok:
                waived.append(ac.id)
                continue
        not_red[ac.id] = {"outcomes": seen}
    ok = not not_red
    return Section(
        {
            "ok": ok,
            "mode": "red",
            "not_red": not_red,
            "green_before": green_before,
            "waived": waived,
            "red_by_import": red_by_import,
        },
        EXIT_OK if ok else EXIT_FAILED,
    )


# ── review (ADR-007) ───────────────────────────────────────────────────────────

_DISPOSITIONS = frozenset({"accepted", "rejected", "duplicate", "unresolved"})


def _cells(line: str) -> list[str]:
    return [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]


_DOC_SUFFIXES = frozenset({".md", ".rst", ".txt"})
#: Markdown that steers an agent is behaviour, not documentation.
_PROMPT_DIRS = frozenset({"agents", "commands", "skills"})
_PROMPT_FILES = frozenset({"CLAUDE.md", "AGENTS.md", "SKILL.md"})


def _work_docs(config: dict[str, Any]) -> str:
    return str(_dig(config, "work_docs", "dir") or "work-docs/").strip("/") + "/"


def needs_review(path: str, slug: str, config: dict[str, Any]) -> bool:
    """A changed path the reviewer must have seen: anything but docs and the task's own records.
    Wider than `is_code_or_test` on purpose: templates, configs and locks deserve review too."""
    if path.startswith((_work_docs(config), ".claude/memory/", ".claude/observability/")):
        return False
    if path.startswith(f"specs/SPEC-{slug}."):
        return False
    pure = Path(path)
    if pure.name in _PROMPT_FILES or _PROMPT_DIRS & set(pure.parts[:-1]):
        return True
    return pure.suffix.lower() not in _DOC_SUFFIXES


def review_section(
    root: Path,
    slug: str,
    config: dict[str, Any],
    *,
    changed: list[str] | None = None,
    state: str = "",
    require: bool = False,
) -> Section:
    work_docs = _work_docs(config)
    # Anchored: `REVIEW-auth-*.md` would also match another task's `REVIEW-auth-refresh-…`.
    name = re.compile(rf"REVIEW-{re.escape(slug)}-\d{{4}}-\d{{2}}-\d{{2}}\.md")
    docs = sorted(
        p for p in (root / work_docs).glob(f"REVIEW-{slug}-*.md") if name.fullmatch(p.name)
    )
    if not docs:
        unreviewed = [p for p in changed or [] if needs_review(p, slug, config)]
        if require and state != "exempt" and unreviewed:
            return Section(
                {
                    "ok": False,
                    "reason": "no REVIEW record for a non-doc change",
                    "paths": unreviewed[:10],
                },
                EXIT_FAILED,
            )
        return Section({"ok": True, "gating": False, "reason": "no REVIEW record"})
    doc = docs[-1]
    rel = doc.relative_to(root).as_posix()
    text = doc.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^## Findings[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if m is None:
        return Section({"ok": False, "doc": rel, "reason": "no ## Findings section"}, EXIT_FAILED)
    rows = [ln for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    if not rows:
        if re.search(r"^\s*none\b", m.group(1), re.M | re.I):
            return Section({"ok": True, "doc": rel, "findings": 0})
        return Section(
            {"ok": False, "doc": rel, "reason": "findings without a disposition table"},
            EXIT_FAILED,
        )
    header = [c.lower() for c in _cells(rows[0])]
    if "disposition" not in header:
        return Section(
            {"ok": False, "doc": rel, "reason": "findings table has no disposition column"},
            EXIT_FAILED,
        )
    d_col = header.index("disposition")
    a_col = header.index("authority") if "authority" in header else None
    missing: list[str] = []
    open_: list[str] = []
    count = 0
    for row in rows[1:]:
        cells = _cells(row)
        if all(set(c) <= set("-: ") for c in cells):
            continue
        count += 1
        disposition = cells[d_col].lower() if d_col < len(cells) else ""
        label = cells[0] or f"row {count}"
        if disposition not in _DISPOSITIONS:
            missing.append(label)
        elif disposition == "unresolved":
            open_.append(label)
        elif disposition == "rejected" and (
            a_col is None or a_col >= len(cells) or not cells[a_col] or cells[a_col] == "-"
        ):
            missing.append(f"{label} (rejected without an authority)")
    ok = not missing and not open_
    return Section(
        {"ok": ok, "doc": rel, "findings": count, "without_disposition": missing, "open": open_},
        EXIT_OK if ok else EXIT_FAILED,
    )


# ── contract boundaries (SPEC-wrapup-gate AC-003) ──────────────────────────────

_DNC_HEADING = re.compile(r"^###\s+Do not change\s*$", re.M)
_ADR_LINE = re.compile(r"^[\s#*|>-]*ADR-\d+")
_USER_DECIDED = re.compile(r"Decided by:\**\s*(?:user|DRI)\b", re.I)
_ALLOWS = re.compile(r"\ballows:\s*(?:`([^`]+)`|([^\s,;`]+))")


def _dnc_entry(bullet: str) -> tuple[list[str], bool] | None:
    """(patterns, qualified). A qualified bullet (text after the path) protects a behaviour, not
    the whole file, so it is advisory: only a model can judge it. A bare name with no glob
    character also covers the directory of that name, so `src/api` cannot fail open."""
    text = bullet.strip()[1:].strip()
    if not text or re.match(r"none\b", text, re.I):
        return None
    tick = re.match(r"\**`([^`]+)`\**", text)
    if tick:
        entry, rest = tick.group(1), text[tick.end() :]
    else:
        entry, _, rest = text.partition(" ")
        entry = entry.rstrip(".,;:").strip("*").rstrip(".,;:")
    entry = entry.strip().removeprefix("./")
    if not entry:
        return None
    if entry.endswith("/"):
        patterns = [f"{entry}**"]
    elif any(c in entry for c in "*?["):
        patterns = [entry]
    else:
        patterns = [entry, f"{entry}/**"]
    return patterns, bool(rest.strip(" .;,:"))


def _plan_boundaries(text: str) -> tuple[list[tuple[list[str], bool]], list[str]] | None:
    """(Do-not-change entries, user-decided ADR `allows:` patterns), or None when the PLAN has
    no list. An agent-decided `allows:` does not count: the model that crosses a boundary must
    not authorise the crossing itself."""
    m = _DNC_HEADING.search(text)
    if m is None:
        return None
    entries: list[tuple[list[str], bool]] = []
    for line in text[m.end() :].splitlines():
        if line.startswith("#"):
            break
        if line.strip().startswith(("- ", "* ")):
            entry = _dnc_entry(line)
            if entry:
                entries.append(entry)
    allows = [
        (ticked or bare.rstrip(".")).removeprefix("./")
        for line in text.splitlines()
        if _ADR_LINE.match(line) and _USER_DECIDED.search(line)
        for ticked, bare in _ALLOWS.findall(line)
    ]
    return entries, allows


def contract_section(root: Path, slug: str, config: dict[str, Any], changed: list[str]) -> Section:
    """The PLAN's `Do not change` list against the task diff, so the model that did the work does
    not judge its own scope (HR-020)."""
    from harness_maker.check_reuse import glob_match

    plan = root / _work_docs(config) / f"PLAN-{slug}.md"
    if not plan.is_file():
        return Section({"ok": True, "gating": False, "reason": "no PLAN"})
    parsed = _plan_boundaries(plan.read_text(encoding="utf-8", errors="replace"))
    if parsed is None:
        return Section({"ok": True, "gating": False, "reason": "no Do not change list"})
    entries, allows = parsed
    strict = [g for globs, qualified in entries if not qualified for g in globs]
    loose = [g for globs, qualified in entries if qualified for g in globs]
    hits = [p for p in changed if any(glob_match(e, p) for e in strict)]
    allowed = [p for p in hits if any(glob_match(a, p) for a in allows)]
    crossed = [p for p in hits if p not in allowed]
    advisory = [p for p in changed if p not in hits and any(glob_match(e, p) for e in loose)]
    return Section(
        {"ok": not crossed, "crossed": crossed, "allowed": allowed, "advisory": advisory},
        EXIT_FAILED if crossed else EXIT_OK,
    )


# ── security (IRR-004) ─────────────────────────────────────────────────────────


def _finding_row(f: Any) -> dict[str, Any]:
    return {"category": f.category, "file": f.file, "line": f.line, "evidence": f.evidence[:120]}


def security_section(root: Path, changed: list[str]) -> Section:
    from harness_maker.secscan import hook_injection, secrets

    touched = set(changed)
    findings = secrets.scan_files(root, _listed_files(root))
    for rel in HOOK_FILES:
        for f in hook_injection.scan(root / rel):
            findings.append(f.model_copy(update={"file": rel}))
    gating = [f for f in findings if f.file in touched]
    out_of_scope = len(findings) - len(gating)
    ok = not gating
    return Section(
        {
            "ok": ok,
            "findings": [_finding_row(f) for f in gating[:20]],
            "out_of_scope": out_of_scope,
        },
        EXIT_OK if ok else EXIT_FAILED,
    )


# ── cve (ADR-008) ──────────────────────────────────────────────────────────────

QueryFn = Callable[[list[dict[str, Any]]], list[Any]]


def _cve_query(specs: list[dict[str, Any]]) -> list[Any]:
    """OSV lookups that RAISE on failure: the crawler swallows errors, which would read clean."""
    import httpx

    from harness_maker.crawler import osv_dev

    items: list[Any] = []
    with httpx.Client(timeout=osv_dev.DEFAULT_TIMEOUT, follow_redirects=True) as client:
        for spec in specs:
            response = client.post(osv_dev.OSV_QUERY_URL, json=spec)
            response.raise_for_status()
            payload = response.json()
            vulns = payload.get("vulns", []) if isinstance(payload, dict) else []
            pkg = spec["package"]
            for vuln in vulns or []:
                item = osv_dev._to_item(vuln, pkg["name"], pkg["ecosystem"], spec["version"])
                if item is not None:
                    items.append(item)
    return items


def _lock_specs(text: str) -> list[dict[str, Any]]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    out: list[dict[str, Any]] = []
    for pkg in data.get("package", []) if isinstance(data.get("package"), list) else []:
        if isinstance(pkg, dict) and pkg.get("name") and pkg.get("version"):
            out.append(
                {
                    "package": {"name": str(pkg["name"]), "ecosystem": "PyPI"},
                    "version": str(pkg["version"]),
                }
            )
    return out


def _pyproject_names(text: str | None) -> set[str]:
    if text is None:
        return set()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return set()
    deps = _dig(data, "project", "dependencies")
    names: set[str] = set()
    for dep in deps if isinstance(deps, list) else []:
        if isinstance(dep, str):
            m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", dep)
            if m:
                names.add(m.group(1).lower())
    return names


def dependency_specs(root: Path) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    """Every dependency to look up, and the (name, version) pairs the change added/re-pinned."""
    lock = root / "uv.lock"
    if lock.is_file():
        now = _lock_specs(lock.read_text(encoding="utf-8", errors="replace"))
        head = head_text(root, "uv.lock")
        before = {(s["package"]["name"], s["version"]) for s in _lock_specs(head or "")}
        touched = {(s["package"]["name"], s["version"]) for s in now} - before
        return now, touched
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return [], set()
    names = _pyproject_names(pyproject.read_text(encoding="utf-8", errors="replace"))
    before_names = _pyproject_names(head_text(root, "pyproject.toml"))
    specs = [{"package": {"name": n, "ecosystem": "PyPI"}, "version": "*"} for n in sorted(names)]
    return specs, {(n, "*") for n in names - before_names}


def cve_section(root: Path, *, offline: bool, query: QueryFn | None = None) -> Section:
    if offline:
        return Section({"ok": True, "status": "skipped", "reason": "--offline: no lookup made"})
    specs, touched = dependency_specs(root)
    if not specs:
        return Section({"ok": True, "status": "no dependencies"})
    if not (root / "uv.lock").is_file():
        # Unpinned names have no version to look up, so an empty answer would read clean.
        return Section(
            {
                "ok": True,
                "status": "unavailable",
                "warning": "no uv.lock, so dependency versions are unknown and no CVE lookup "
                "was made; this is not a clean result",
                "added": sorted(n for n, _ in touched),
            }
        )
    try:
        items = (query or _cve_query)(specs)
    except Exception as exc:  # noqa: BLE001 — any lookup failure is `unavailable`, never clean
        return Section(
            {
                "ok": True,
                "status": "unavailable",
                "warning": f"CVE lookup failed ({type(exc).__name__}); this is not a clean result",
            }
        )
    gating: list[str] = []
    existing: list[str] = []
    for item in items:
        meta = getattr(item, "metadata", {}) or {}
        key = (str(meta.get("package")), str(meta.get("version")))
        label = f"{item.item_id}: {key[0]} {key[1]}"
        (gating if key in touched else existing).append(label)
    ok = not gating
    return Section(
        {"ok": ok, "status": "checked", "gating": gating, "existing": existing},
        EXIT_OK if ok else EXIT_FAILED,
    )


# ── opt-ins ────────────────────────────────────────────────────────────────────


def mutation_section(root: Path, spec: SpecView | None, approval_state: str = "") -> Section:
    if spec is None:
        return _no_spec(approval_state)
    tier = str(getattr(spec.model, "verification_tier", 2))
    argv = [
        sys.executable,
        "-m",
        "harness_maker.spec_mutation",
        "gate",
        "--yaml",
        str(spec.yaml_path),
        "--tier",
        tier,
    ]
    code, out = _run(argv, root, gate_env(root=root))
    ok = code == 0
    return Section({"ok": ok, "exit": code, "tail": _tail(out)}, EXIT_OK if ok else EXIT_FAILED)


def harness_section(root: Path) -> Section:
    """Reported, never gating (ADR-009)."""
    try:
        from harness_maker.ai_readiness import run_structural
        from harness_maker.cli import _read_preset
        from harness_maker.models import Preset

        preset = _read_preset(root / ".claude" / "harness.yaml") or Preset.SIDE
        structural = run_structural(root, preset=preset)
    except Exception as exc:  # noqa: BLE001 — reported, not a crash
        return Section({"ok": False, "gating": False, "reason": f"{type(exc).__name__}: {exc}"})
    return Section(
        {
            "ok": True,
            "gating": False,
            "score": structural.get("score"),
            "signals_failed": structural.get("signals_failed", []),
        }
    )


# ── golden JSON (SPEC-hm-cost-p2 AC-002) ───────────────────────────────────────


def with_golden(section: Section, spec: SpecView) -> Section:
    """Add the golden-JSON verdict to an `ac` section, in either mode.

    A SPEC with no live parametric AC gets nothing, so its output is unchanged. An absent JSON
    is not a failure: SPECs and tests from before the file read `load_golden_table`. Drift fails
    the section even when it already passed, because a parametric test reading a stale JSON
    passes against rows the SPEC no longer holds.
    """
    from harness_maker import spec_machine

    try:
        want = spec_machine.golden_export(spec.model)
    except spec_machine.GoldenTableError as e:
        want, unexportable = {}, f"{e.ac_id}: {e.cause}"
    else:
        unexportable = ""
    if not want and not unexportable:
        return section
    path = spec_machine.golden_json_path(spec.yaml_path)
    fix = f"hm spec_machine export-golden --yaml {spec.yaml_path}"
    body = dict(section.body)
    if not path.is_file():
        body["golden"] = "absent"
        body["hint"] = (
            f"{unexportable}; export-golden refuses it, so its test cannot read {path.name}"
            if unexportable
            else f"parametric tests read {path.name}; write it with `{fix}`"
        )
        return Section(body, section.code)
    body["golden"] = "present"
    try:
        have = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        have = {}
    if not isinstance(have, dict):
        have = {}
    if unexportable:
        drift = [unexportable]  # `want` is empty here, so a comparison would name every AC
    else:
        drift = sorted(a for a in set(want) | set(have) if want.get(a) != have.get(a))
    if not drift:
        return Section(body, section.code)
    body["ok"] = False
    body["golden_drift"] = {"acs": drift, "fix": fix}
    return Section(body, EXIT_FAILED if section.code == EXIT_OK else section.code)


# ── compact output (SPEC-hm-cost-p2 AC-006) ────────────────────────────────────

#: What a passing section keeps when the output is compacted: the keys that carry a warning or a
#: value a stage reads (a self-approved SPEC, a skipped lookup, waived RED ACs, golden state, an
#: unclean CVE scan's new dependencies, the reported-only harness score).
COMPACT_KEEP: tuple[str, ...] = (
    "pending", "notice", "skipped", "status", "reason", "waived", "green_before", "golden",
    "hint", "gating", "degraded", "warning", "added", "out_of_scope", "score", "signals_failed",
)  # fmt: skip


def compact(section: Section) -> dict[str, Any]:
    """A passing section (exit 0 and `ok` true) reduced to `ok` plus its non-empty keep-set
    keys. The caller re-reads every byte on each later turn; `--full` restores the rest."""
    body = section.body
    if section.code != EXIT_OK or body.get("ok") is not True:
        return body
    kept = {k: v for k, v in body.items() if k in COMPACT_KEEP and v not in ("", [], {}, None)}
    return {"ok": True, **kept}


# ── orchestration ──────────────────────────────────────────────────────────────


@dataclass
class Options:
    slug: str
    root: Path
    red: bool = False
    green_ok: set[str] = field(default_factory=set)
    mutation: bool = False
    offline: bool = False
    harness: bool = False
    full: bool = True
    #: Wrapup's call (SPEC-wrapup-gate AC-001): a non-doc change needs a REVIEW record.
    require_review: bool = False


# ── verdict reuse (SPEC-hm-cost-p3 AC-002) ─────────────────────────────────────

#: The last passing verdict, kept in the git dir so that recording it never changes the tree.
VERDICT_RECORD = "hm/check-verdict.json"


def verdict_path(root: Path) -> Path | None:
    out = _git(root, "rev-parse", "--git-path", VERDICT_RECORD)
    if out is None:
        return None
    path = Path(out.strip())
    return path if path.is_absolute() else root / path


#: Options that cannot change a gate result. `require_review` is only read by the review section,
#: which an identical reprint recomputes (SPEC-wrapup-gate AC-002); keying on it would cost
#: wrapup the reuse of execute's pass.
_UNKEYED_OPTIONS = frozenset({"root", "require_review"})


def _verdict_key(
    opts: Options,
    root: Path,
    gates: list[str],
    reason: str | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """What a reused gate result must match: every `Options` field but `_UNKEYED_OPTIONS` (a
    narrower set let a `--mutation` run reuse a pass that never ran the mutation gate), the gate
    list and the harness config (it may be ignored by git). HEAD and the per-path tree are
    compared by `check_reuse.decide`, which may accept a declared-inert difference in either."""
    from harness_maker import __version__

    options = {
        k: sorted(v) if isinstance(v, set) else v
        for k, v in asdict(opts).items()
        if k not in _UNKEYED_OPTIONS
    }
    gate_inputs = {"gates": gates, "reason": reason, "config": config}
    return {
        "slug": opts.slug,
        "options": options,
        "head": (_git(root, "rev-parse", "HEAD") or "").strip(),
        "fingerprint": hashlib.sha256(
            json.dumps(gate_inputs, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "harness_maker_version": __version__,
    }


def _load_record(path: Path | None) -> object:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _record(path: Path | None, record: dict[str, Any]) -> None:
    """Keep a passing gate result for `--reuse`. Losing it costs one rerun, so a failed write
    warns and never changes the verdict."""
    from harness_maker.io_utils import atomic_write

    if path is None:
        return
    try:
        atomic_write(path, json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        sys.stderr.write(f"hm check: verdict not recorded ({type(exc).__name__}: {exc})\n")


def _reuse_line(record: dict[str, Any], decision: Any, commands: list[str]) -> dict[str, Any]:
    unobserved = [c for c in commands if not _is_pytest(shlex.split(c))]
    read_set = record.get("read_set")
    state = "absent" if not isinstance(read_set, list) else "partial" if unobserved else "checked"
    return {
        "rule": decision.rule,
        "delta": decision.delta,
        "inert": decision.inert,
        "read_set": state,
        "unobserved": unobserved,
    }


def _reprint(
    line: dict[str, Any], opts: Options, root: Path, config: dict[str, Any]
) -> dict[str, Any]:
    """An identical exit-0 line, with review and contract recomputed: execute's pass predates
    its REVIEW and must not carry wrapup past it (SPEC-wrapup-gate AC-002), and a gitignored
    PLAN edit is invisible to the tree snapshot."""
    changed = changed_paths(root)
    state = str(approval_section(root, opts.slug, config).body["state"])
    fresh = {
        "review": review_section(
            root, opts.slug, config, changed=changed, state=state, require=opts.require_review
        ),
        "contract": contract_section(root, opts.slug, config, changed),
    }
    failed = {name: s for name, s in fresh.items() if s.code != EXIT_OK}
    if not failed:
        return dict(line)
    sections = dict(line.get("sections") or {})
    sections.update({name: s.body for name, s in failed.items()})
    return {**line, "exit": EXIT_FAILED, "sections": sections}


def run(opts: Options, *, reuse: bool = False, cve_query: QueryFn | None = None) -> dict[str, Any]:
    from harness_maker import check_reuse

    root = opts.root.resolve()
    before = snapshot(root)
    config = _harness_config(root)
    commands, reason, _source = gate_commands(root, config)
    path = verdict_path(root)
    key = _verdict_key(opts, root, commands, reason, config)
    reused_gates: Section | None = None
    reuse_info: dict[str, Any] | None = None
    reuse_miss: dict[str, Any] | None = None
    if reuse and not opts.red:
        record = _load_record(path)
        decision = check_reuse.decide(
            record,
            key=key,
            files=before,
            declaration=check_reuse.parse_declaration(config),
            head=key["head"],
            has_pytest_gate=any(_is_pytest(shlex.split(c)) for c in commands),
        )
        if decision.reuse and isinstance(record, dict):
            reuse_info = _reuse_line(record, decision, commands)
            line = record.get("line")
            if decision.rule == "identical" and isinstance(line, dict) and line.get("exit") == 0:
                return _reprint(line, opts, root, config) | {"reused": True, "reuse": reuse_info}
            reused_gates = Section(dict(record["gates"]))
        else:
            reuse_miss = {"reason": decision.reason, "paths": decision.paths}
    sections: dict[str, Section] = {}
    approval = approval_section(root, opts.slug, config)
    sections["approval"] = approval
    spec = load_spec(root, opts.slug)
    changed = changed_paths(root)
    runner = pytest_runner(root, commands)
    skipped = Section({"ok": True, "skipped": "--red"})
    state = str(approval.body["state"])
    read_set: list[str] | None = None
    if opts.red:
        sections["gates"] = skipped
        sections["ac"] = red_section(root, spec, runner, opts.green_ok, state)
        for name in ("review", "contract", "security", "cve"):
            sections[name] = skipped
    else:
        if reused_gates is not None:
            sections["gates"] = reused_gates
        else:
            sections["gates"], read_set = gates_with_read_set(root, config)
        sections["ac"] = ac_section(root, spec, state, changed, runner)
        sections["review"] = review_section(
            root, opts.slug, config, changed=changed, state=state, require=opts.require_review
        )
        sections["contract"] = contract_section(root, opts.slug, config, changed)
        sections["security"] = security_section(root, changed)
        sections["cve"] = cve_section(root, offline=opts.offline, query=cve_query)
        if opts.mutation:
            sections["mutation"] = mutation_section(root, spec, state)
        if opts.harness:
            sections["harness"] = harness_section(root)
    if spec is not None:
        sections["ac"] = with_golden(sections["ac"], spec)
    tree_changed = tree_delta(before, snapshot(root))
    codes = {s.code for s in sections.values()}
    if tree_changed:
        codes.add(EXIT_TREE_CHANGED)
    exit_code = next((c for c in _PRECEDENCE if c in codes), EXIT_OK)
    result: dict[str, Any] = {
        "exit": exit_code,
        "tree_changed": tree_changed,
        "sections": {name: s.body if opts.full else compact(s) for name, s in sections.items()},
    }
    if reuse_info is not None:
        result.update(reused=True, reuse=reuse_info)
    elif reuse_miss is not None:
        result["reuse_miss"] = reuse_miss
    if opts.red or reused_gates is not None:
        if tree_changed and path is not None:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        return result
    gates = sections["gates"]
    unhashable = any(d.startswith("unreadable:") for d in before.values())
    head_now = (_git(root, "rev-parse", "HEAD") or "").strip()
    if gates.code == EXIT_OK and not tree_changed and not unhashable and head_now == key["head"]:
        kept = sorted(set(read_set) & set(before)) if read_set is not None else None
        line = {k: v for k, v in result.items() if k not in ("reused", "reuse", "reuse_miss")}
        _record(
            path,
            {
                **key,
                "files": before,
                "read_set": kept,
                "gates": gates.body,
                "line": line if exit_code == EXIT_OK else None,
                "at": datetime.now(UTC).isoformat(),
            },
        )
    elif path is not None and (gates.code != EXIT_OK or tree_changed):
        # A pass recorded earlier must not outlive a fresh gate failure: a gate can fail on what
        # the record cannot see (a service, an ignored file).
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
    return result


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hm check",
        description="Run every deterministic gate of a task; print one JSON line; exit per "
        "the contract (0 ok, 1 failed, 2 usage, 3 degraded, 4 tree changed, 5 approval).",
    )
    p.add_argument("--slug", required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--red", action="store_true", help="RED gate: every testable AC must fail")
    p.add_argument(
        "--green-ok",
        action="append",
        default=[],
        metavar="AC-NNN",
        help="with --red: this AC's tests may already pass (echoed as waived)",
    )
    p.add_argument("--mutation", action="store_true", help="opt-in mutation gate")
    p.add_argument("--offline", action="store_true", help="skip the CVE lookup and say so")
    p.add_argument("--harness", action="store_true", help="report the harness structure layer")
    p.add_argument(
        "--require-review",
        action="store_true",
        help="wrapup's call: fail a non-doc change that has no REVIEW record, unless the SPEC is "
        "exempt",
    )
    p.add_argument(
        "--full", action="store_true", help="print passing sections in full, not just ok + notes"
    )
    p.add_argument(
        "--reuse",
        action="store_true",
        help="print the last passing verdict for this exact tree, HEAD, config and options instead "
        "of rerunning the gates (marked reused: true); a reused line repeats its CVE lookup result",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.green_ok and not args.red:
        _parser().error("--green-ok needs --red")
    result = run(
        Options(
            slug=args.slug,
            root=args.root,
            red=args.red,
            green_ok=set(args.green_ok),
            mutation=args.mutation,
            offline=args.offline,
            harness=args.harness,
            full=args.full,
            require_review=args.require_review,
        ),
        reuse=args.reuse,
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return int(result["exit"])


if __name__ == "__main__":
    raise SystemExit(main())
