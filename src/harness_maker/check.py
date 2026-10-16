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
import signal
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
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


def gate_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every gate subprocess runs in: no bytecode, nothing else changed."""
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(extra or {})}


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
        py = root / ".venv" / "bin" / "python"
        if not py.is_file():
            return [], f"{plan.reason}; and no .venv/bin/python in the project", "none"
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
    commands, reason, source = gate_commands(root, config)
    if reason is not None:
        return Section({"ok": False, "degraded": True, "reason": reason}, EXIT_DEGRADED)
    results: list[dict[str, Any]] = []
    for cmd in commands:
        argv = shlex.split(cmd)
        if _is_pytest(argv):
            argv += ["-p", "no:cacheprovider"]
        code, out = _run(argv, root, gate_env())
        row: dict[str, Any] = {"cmd": cmd, "exit": code}
        if code != 0:
            row["tail"] = _tail(out)
        results.append(row)
    ok = all(r["exit"] == 0 for r in results)
    return Section({"ok": ok, "source": source, "results": results}, EXIT_OK if ok else EXIT_FAILED)


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


def pytest_runner(root: Path, commands: Iterable[str]) -> list[str] | None:
    py = root / ".venv" / "bin" / "python"
    if py.is_file():
        return [str(py), "-m", "pytest"]
    for cmd in commands:
        argv = shlex.split(cmd)
        for i, tok in enumerate(argv):
            if Path(tok).name in ("pytest", "py.test"):
                return argv[: i + 1]
    return None


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
        code, out = _run(argv, root, gate_env({"PYTHONPATH": pythonpath}))
        cases = _junit_cases(junit)
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
            {"ok": False, "degraded": True, "reason": "no pytest runner", "failed": failed},
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
        return Section({"ok": False, "degraded": True, "reason": "no pytest runner"}, EXIT_DEGRADED)
    ids = sorted({t for ac in testable for t in ac.test_ids})
    outcomes = run_tests(root, runner, ids) if ids else {}
    not_red: dict[str, Any] = {}
    green_before: list[str] = []
    waived: list[str] = []
    red_by_import: list[dict[str, Any]] = []
    for ac in testable:
        if not ac.test_ids:
            not_red[ac.id] = "no test_ids"
            continue
        is_red = False
        for tid in ac.test_ids:
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
        seen = {tid: outcomes[tid].outcome for tid in ac.test_ids}
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


def review_section(root: Path, slug: str, config: dict[str, Any]) -> Section:
    work_docs = _dig(config, "work_docs", "dir") or "work-docs/"
    # Anchored: `REVIEW-auth-*.md` would also match another task's `REVIEW-auth-refresh-…`.
    name = re.compile(rf"REVIEW-{re.escape(slug)}-\d{{4}}-\d{{2}}-\d{{2}}\.md")
    docs = sorted(
        p for p in (root / str(work_docs)).glob(f"REVIEW-{slug}-*.md") if name.fullmatch(p.name)
    )
    if not docs:
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
    code, out = _run(argv, root, gate_env())
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


def run(opts: Options, *, cve_query: QueryFn | None = None) -> dict[str, Any]:
    root = opts.root.resolve()
    before = snapshot(root)
    config = _harness_config(root)
    sections: dict[str, Section] = {}
    approval = approval_section(root, opts.slug, config)
    sections["approval"] = approval
    spec = load_spec(root, opts.slug)
    changed = changed_paths(root)
    commands, _reason, _source = gate_commands(root, config)
    runner = pytest_runner(root, commands)
    skipped = Section({"ok": True, "skipped": "--red"})
    state = str(approval.body["state"])
    if opts.red:
        sections["gates"] = skipped
        sections["ac"] = red_section(root, spec, runner, opts.green_ok, state)
        for name in ("review", "security", "cve"):
            sections[name] = skipped
    else:
        sections["gates"] = gates_section(root, config)
        sections["ac"] = ac_section(root, spec, state, changed, runner)
        sections["review"] = review_section(root, opts.slug, config)
        sections["security"] = security_section(root, changed)
        sections["cve"] = cve_section(root, offline=opts.offline, query=cve_query)
        if opts.mutation:
            sections["mutation"] = mutation_section(root, spec, state)
        if opts.harness:
            sections["harness"] = harness_section(root)
    tree_changed = tree_delta(before, snapshot(root))
    codes = {s.code for s in sections.values()}
    if tree_changed:
        codes.add(EXIT_TREE_CHANGED)
    exit_code = next((c for c in _PRECEDENCE if c in codes), EXIT_OK)
    return {
        "exit": exit_code,
        "tree_changed": tree_changed,
        "sections": {name: s.body for name, s in sections.items()},
    }


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
        )
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return int(result["exit"])


if __name__ == "__main__":
    raise SystemExit(main())
