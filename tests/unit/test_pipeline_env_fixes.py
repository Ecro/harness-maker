"""SPEC-pipeline-env-fixes: hm leaves the project alone and picks a runner that can run."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from harness_maker import check, intent, loop_marker, synthesize, worktree
from harness_maker.gates import worktree_gate
from harness_maker.interview import _build_answers
from harness_maker.models import HarnessConfig, Preset, ProjectProfile, Target
from harness_maker.observability import verification_cache
from harness_maker.render import DEFAULT_FREEZE_TIME, _make_env, _no_project_entry, render

REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "pipeline_env_fixes"
_GOLDEN: dict[str, list[dict[str, Any]]] = json.loads(
    (REPO_ROOT / "specs" / "SPEC-pipeline-env-fixes.golden.json").read_text(encoding="utf-8")
)
OLD = "uv run --with"
NEW = "uv run --no-project --with"
_HM_COMMAND = re.compile(r"python -m (harness_maker\.\S.*)$")


def _render_project(root: Path, preset: Preset = Preset.SIDE, *, upgrade: bool = False) -> Path:
    """`upgrade` merges the hook file already on disk, as `make --update` does."""
    answers = _build_answers(locale="en", targets=[Target.CLAUDE_CODE, Target.CODEX], preset=preset)
    render(
        synthesize.synthesize(ProjectProfile(), answers, preset=preset),
        root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
        merge_json_paths={Path(".codex/hooks.json")} if upgrade else None,
    )
    return root


def _stage(path: str, *, is_codex: bool = False) -> str:
    return (
        _make_env()
        .get_template(path)
        .render(
            stage=path.rsplit("/", 1)[-1].split(".")[0], workflow_context="", project_name="",
            feature="", config=HarnessConfig().model_dump(mode="json"),
            harness_maker_src_path=synthesize._HARNESS_MAKER_PKG_ROOT,
            is_codex=is_codex, communication_variant="reframe",
        )
    )  # fmt: skip


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=cwd, check=True, capture_output=True, text=True, timeout=60,
    ).stdout  # fmt: skip


def _porcelain(cwd: Path) -> list[str]:
    return [ln for ln in _git(cwd, "status", "--porcelain").splitlines() if ln]


def _fake_venv(root: Path, *, pytest_ok: bool) -> Path:
    """A `.venv/bin/python` that really runs Python: with this suite's packages, or without any."""
    py = root / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    bare = "" if pytest_ok else '"-I", "-S", '
    py.write_text(
        f"#!{sys.executable}\nimport subprocess, sys\n"
        f"sys.exit(subprocess.call([{sys.executable!r}, {bare}*sys.argv[1:]]))\n",
        encoding="utf-8",
    )
    py.chmod(0o755)
    (root / ".venv" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
    return py


def _sub(value: Any, root: Path) -> Any:  # noqa: ANN401 — golden JSON is heterogeneous
    if isinstance(value, str):
        return value.replace("<root>", str(root))
    if isinstance(value, list):
        return [_sub(v, root) for v in value]
    return value


def _rows(ac: str) -> list[Any]:
    return [pytest.param(row, id=f"{ac}-{i}") for i, row in enumerate(_GOLDEN[ac])]


# --- AC-001 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("preset", list(Preset), ids=lambda p: p.value)
def test_ac_001_rendered_invocations_carry_no_project(tmp_path: Path, preset: Preset) -> None:
    root = _render_project(tmp_path / "proj", preset)
    ref = re.escape(synthesize._compute_install_ref())
    seen = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert OLD not in text, path
        for m in re.finditer(r"--with[ =]\"?" + ref, text):
            assert text[: m.start()].endswith("uv run --no-project "), (
                path,
                text[m.start() - 40 : m.end()],
            )
            seen += 1
    assert seen >= 10


def test_ac_001_plugin_root_and_gate_remedy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    surfaces = [
        *sorted((REPO_ROOT / "commands").rglob("*.md")),
        *sorted((REPO_ROOT / "skills").rglob("*.md")),
        REPO_ROOT / "hooks" / "hooks.json",
    ]
    hits = 0
    for path in surfaces:
        text = path.read_text(encoding="utf-8")
        assert OLD not in text, path
        hits += text.count(NEW)
    assert hits >= 2

    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    peer = repo / ".worktrees" / "theirs"
    peer.mkdir(parents=True)
    (repo / ".claude" / ".hm-task-theirs").write_text(
        loop_marker.format_marker_content("bbbb2222cafe", [peer]), encoding="utf-8"
    )
    payload = {
        "tool_name": "Write", "cwd": str(repo), "session_id": "aaaa1111cafe",
        "tool_input": {"file_path": str(peer / "f.py")},
    }  # fmt: skip
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert worktree_gate.main() == 2
    err = capsys.readouterr().err
    assert f"{NEW} <plugin_path>" in err
    assert OLD not in err


# --- AC-003 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("row", _rows("AC-003"))
def test_ac_003_runner_rows(tmp_path: Path, row: dict[str, Any]) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    venv = row["input"]["venv"]
    if venv != "none":
        _fake_venv(root, pytest_ok=venv == "with_pytest")
    runner = check.pytest_runner(root, row["input"]["commands"])
    assert runner == _sub(row["expected"]["runner"], root)
    reason = None if runner is not None else check.no_runner_reason(root)
    assert reason == _sub(row["expected"]["reason"], root)


# --- AC-004 -----------------------------------------------------------------------------------

_UV_RECORDER = """#!{py}
import json, os, pathlib, sys

here = pathlib.Path(__file__).parent
with open(here / "uv.log", "a") as f:
    f.write(json.dumps({{"argv": ["uv", *sys.argv[1:]], "cwd": os.getcwd()}}) + "\\n")
code = int((here / "exit").read_text()) if (here / "exit").exists() else 0
if code:
    print("resolving")
    print("error: boom")
    sys.exit(code)
if sys.argv[1:2] == ["sync"]:
    py = pathlib.Path(".venv/bin/python")
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    py.chmod(0o755)
"""


@pytest.mark.parametrize("row", _rows("AC-004"))
def test_ac_004_interpreter_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict[str, Any]
) -> None:
    given, want = row["input"], row["expected"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    if given["uv_on_path"]:
        (bin_dir / "uv").write_text(_UV_RECORDER.format(py=sys.executable), encoding="utf-8")
        (bin_dir / "uv").chmod(0o755)
    if "uv_exit" in given:
        (bin_dir / "exit").write_text(str(given["uv_exit"]), encoding="utf-8")
    monkeypatch.setenv("PATH", str(bin_dir))

    root = tmp_path / "proj"
    root.mkdir()
    (root / "README.md").write_text("x\n", encoding="utf-8")
    if given["lock"] != "absent":
        (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    if given["lock"] != "present_outside_git":
        _git(root, "init", "-q", "-b", "main")
        (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        _git(
            root,
            "add",
            "README.md",
            ".gitignore",
            *(["uv.lock"] if given["lock"] == "tracked" else []),
        )
        _git(root, "commit", "-q", "-m", "init")
    if given["venv"]:
        py = root / ".venv" / "bin" / "python"
        py.parent.mkdir(parents=True)
        py.write_text("", encoding="utf-8")
        py.chmod(0o755)

    python, reason = check.project_python(root)

    log = bin_dir / "uv.log"
    calls = [json.loads(ln) for ln in log.read_text().splitlines()] if log.exists() else []
    assert [c["argv"] for c in calls] == want["uv_calls"]
    assert all(Path(c["cwd"]).resolve() == root.resolve() for c in calls)
    assert (str(python) if python is not None else None) == _sub(want["python"], root)
    want_reason = _sub(want["reason"], root)
    if want_reason is not None:
        want_reason = want_reason.replace("<last output line>", "error: boom")
    assert reason == want_reason
    if given["lock"] == "tracked":
        assert _porcelain(root) == []

    # The other readers go through the same owner.
    monkeypatch.setattr("harness_maker.light_lane.lane_of", lambda *_a, **_k: "light")
    monkeypatch.setattr(verification_cache, "_spec_test_framework", lambda *_a, **_k: "pytest")
    commands, why, _source = check.gate_commands(root, {})
    if reason is None:
        if given["lock"] != "present_outside_git":
            assert why is None
            assert commands[-1] == f"{shlex.quote(str(python))} -m pytest"
    else:
        assert reason in (why or "")
        assert check.pytest_runner(root, []) is None
        assert verification_cache._spec_commands(root, "x") == reason


# --- AC-005 -----------------------------------------------------------------------------------


def test_ac_005_runner_without_junit_is_error(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_x.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    tid = "tests/test_x.py::test_a"

    dead = check.run_tests(root, [sys.executable, "-I", "-S", "-m", "pytest"], [tid])[tid]
    assert dead.outcome == "error"
    assert "No module named pytest" in dead.detail

    live = [sys.executable, "-m", "pytest", "--deselect", tid]
    assert check.run_tests(root, live, [tid])[tid].outcome == "deselected"


# --- AC-006 -----------------------------------------------------------------------------------


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    (repo / ".claude").mkdir()
    return repo


def _listed_worktree(repo: Path, branch: str) -> Path:
    blocks = _git(repo, "worktree", "list", "--porcelain").split("\n\n")
    block = next(b for b in blocks if f"branch refs/heads/{branch}" in b)
    return Path(block.splitlines()[0].removeprefix("worktree "))


def _worktree_cli(*args: str) -> Path:
    """One CLI call per process, as a stage makes it: a second preflight in THIS process would
    meet its own still-live registry row and be refused as a concurrent session."""
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", *args],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    return Path(proc.stdout.strip().splitlines()[-1])


def test_ac_006_preflight_and_refresh_from_inside_the_worktree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    wt = _worktree_cli("task-preflight", "alpha", str(repo))

    assert _worktree_cli("task-preflight", "alpha", str(wt)) == _listed_worktree(repo, "hm/alpha")
    assert _listed_worktree(repo, "hm/alpha") == wt
    assert _porcelain(wt) == []
    assert not (wt / ".worktrees").exists()
    assert not (wt / ".claude").exists()
    assert any(row.branch == "hm/alpha" for row in worktree._read_sessions(repo))

    beta = _worktree_cli("task-preflight", "beta", str(wt))
    assert beta == _listed_worktree(repo, "hm/beta") == repo / ".worktrees" / "beta"

    assert worktree.main(["task-refresh", "alpha", str(wt)]) == 0


# --- AC-007 -----------------------------------------------------------------------------------


def _fill(token: str, file: Path) -> str:
    if token == "<f>":
        return str(file)
    m = re.fullmatch(r"<([^>]+)>", token)
    return m.group(1).split("|")[0] if m else token


@pytest.mark.parametrize("is_codex", [False, True])
def test_ac_007_wrapup_exit_2_and_observe_example(tmp_path: Path, is_codex: bool) -> None:
    execute = _stage("stages/execute.md.j2", is_codex=is_codex)
    wrapup = _stage("stages/wrapup.md.j2", is_codex=is_codex)
    clause = re.search(r"^- 2: (.+?)\.?$", execute, re.M)
    assert clause is not None
    gate = wrapup.split("## Step 1 ", 1)[1].split("\n## ", 1)[0]
    assert f"2: {clause.group(1)}" in gate

    file = tmp_path / "f.txt"
    file.write_text("x", encoding="utf-8")
    stages = [execute, wrapup, _stage("stages/spec.md.j2", is_codex=is_codex)]
    examples = [e for s in stages for e in re.findall(r"`(hm intent question observe [^`]+)`", s)]
    assert examples
    for example in examples:
        tokens = [_fill(t, file) for t in shlex.split(re.sub(r"\[[^\]]*\]", "", example))]
        try:
            intent._parser().parse_args(tokens[2:])
        except SystemExit as exc:
            pytest.fail(f"{example!r} does not parse (exit {exc.code})")


# --- AC-008 -----------------------------------------------------------------------------------


def _harness_hooks(doc: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(event, matcher, invocation) of every harness-maker hook command in a hooks document."""
    found = []
    for event, groups in doc.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                m = _HM_COMMAND.search(hook.get("command", ""))
                if m:
                    found.append((event, str(group.get("matcher")), m.group(1)))
    return sorted(found)


def _per_event(hooks: list[tuple[str, str, str]]) -> Counter[tuple[str, str]]:
    return Counter((event, invocation) for event, _matcher, invocation in hooks)


def _commands(doc: dict[str, Any]) -> list[str]:
    return [
        hook.get("command", "")
        for groups in doc.get("hooks", {}).values()
        for group in groups
        for hook in group.get("hooks", [])
    ]


def _user_group(command: str) -> dict[str, Any]:
    return {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}


def test_ac_008_upgrade_from_0653(tmp_path: Path) -> None:
    fresh = _render_project(tmp_path / "fresh")
    old = tmp_path / "old"
    (old / ".claude").mkdir(parents=True)
    (old / ".codex").mkdir()
    settings = json.loads((_FIXTURES / "settings_0653.json").read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"].append(_user_group("echo user-own"))
    mixed = next(
        g for g in settings["hooks"]["PreToolUse"]
        if any("worktree_gate" in h["command"] for h in g["hooks"])
    )  # fmt: skip
    mixed["hooks"].append({"type": "command", "command": "echo user-mixed"})
    user_grant = "Bash(uv run --with requests pytest:*)"
    settings["permissions"]["allow"].append(user_grant)
    (old / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    codex = json.loads((_FIXTURES / "codex_hooks_0653.json").read_text(encoding="utf-8"))
    codex["hooks"]["PreToolUse"].append(_user_group("echo user-codex"))
    (old / ".codex" / "hooks.json").write_text(json.dumps(codex), encoding="utf-8")

    _render_project(old, upgrade=True)

    for rel, before, kept in (
        (".claude/settings.json", settings, {"echo user-own", "echo user-mixed"}),
        (".codex/hooks.json", codex, {"echo user-codex"}),
    ):
        after = json.loads((old / rel).read_text(encoding="utf-8"))
        hooks = _harness_hooks(after)
        shipped = _per_event(_harness_hooks(json.loads((fresh / rel).read_text("utf-8"))))
        was = _per_event(_harness_hooks(before))
        assert len(hooks) == len(set(hooks)), rel  # none twice under one matcher
        now = _per_event(hooks)
        assert all(now[key] >= count for key, count in shipped.items()), rel  # none lost
        assert all(count <= max(was[key], shipped[key]) for key, count in now.items()), rel
        commands = _commands(after)
        assert all(NEW in c for c in commands if _HM_COMMAND.search(c)), rel
        assert kept <= set(commands), rel
    allow = json.loads((old / ".claude" / "settings.json").read_text())["permissions"]["allow"]
    assert [a for a in allow if a.startswith(f"Bash({OLD} ") and "harness" in a] == []
    assert user_grant in allow


def test_ac_008_prunes_the_current_refs_old_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(synthesize, "_compute_install_ref", lambda: "/opt/hm-dev")
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    ours, theirs = "Bash(uv run --with /opt/hm-dev hm *)", "Bash(uv run --with /opt/other hm *)"
    (proj / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [ours, theirs]}}), encoding="utf-8"
    )
    _render_project(proj)
    allow = json.loads((proj / ".claude" / "settings.json").read_text())["permissions"]["allow"]
    assert ours not in allow
    assert "Bash(uv run --no-project --with /opt/hm-dev hm *)" in allow
    assert theirs in allow


# --- AC-009 -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "bench_light_lane", REPO_ROOT / "scripts" / "bench_light_lane.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module
    spec.loader.exec_module(module)
    return module


def test_ac_009_bench_guard_and_fixture(tmp_path: Path, bench: ModuleType) -> None:
    rendered = _render_project(tmp_path / "rendered")
    assert NEW in (rendered / ".claude" / "commands" / "hm" / "spec.md").read_text()
    # The guard read the reference out of the new prefix: it got as far as hashing that path.
    with pytest.raises(bench.CliProvenanceError, match="is not a package directory"):
        bench.check_cli_fresh(rendered)

    stale = tmp_path / "stale"
    command = stale / ".claude" / "commands" / "hm" / "spec.md"
    command.parent.mkdir(parents=True)
    command.write_text("!uv run --with /abs/checkout hm spec_machine approve --yaml x\n")
    with pytest.raises(bench.CliProvenanceError, match="carries no"):
        bench.check_cli_fresh(stale)

    template = tmp_path / "template"
    bench.build_template(template, "plain")
    assert "uv.lock" in _git(template, "ls-files").split()


# --- AC-010 -----------------------------------------------------------------------------------

_PATH_DUMP_TEST = """import os


def test_dump():
    with open(os.environ["HM_PATH_DUMP"], "a") as f:
        f.write(os.environ["PATH"] + "\\n")
"""


def test_ac_010_gate_subprocess_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_path.py").write_text(_PATH_DUMP_TEST, encoding="utf-8")
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    _fake_venv(root, pytest_ok=True)
    dump = tmp_path / "path.txt"
    monkeypatch.setenv("HM_PATH_DUMP", str(dump))
    first = str(root / ".venv" / "bin")

    tid = "tests/test_path.py::test_dump"
    assert check.run_tests(root, [sys.executable, "-m", "pytest"], [tid])[tid].outcome == "passed"
    check.gates_section(root, {})

    seen = [ln.split(os.pathsep)[0] for ln in dump.read_text().splitlines()]
    assert seen == [first, first]

    bare = tmp_path / "bare"
    bare.mkdir()
    assert check.gate_env(root=bare)["PATH"] == os.environ["PATH"]


def test_ac_010_mutation_gate_gets_the_project_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proj"
    _fake_venv(root, pytest_ok=True)
    seen: list[str] = []

    def record(argv: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
        seen.append(env["PATH"].split(os.pathsep)[0])
        return 0, ""

    monkeypatch.setattr(check, "_run", record)
    spec = SimpleNamespace(model=SimpleNamespace(verification_tier=2), yaml_path=root / "s.yaml")
    check.mutation_section(root, spec)  # type: ignore[arg-type]
    assert seen == [str(root / ".venv" / "bin")]


def test_ac_004_failed_sync_is_the_reason_on_the_ac_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lock uv cannot sync is what the DRI must hear, also where only the runner is asked,
    and also when a stale `.venv` without pytest sits next to it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    (bin_dir / "uv").write_text(_UV_RECORDER.format(py=sys.executable), encoding="utf-8")
    (bin_dir / "uv").chmod(0o755)
    (bin_dir / "exit").write_text("2", encoding="utf-8")
    monkeypatch.setenv("PATH", str(bin_dir))
    root = tmp_path / "proj"
    root.mkdir()
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    want = f"uv sync --frozen failed in {root}: error: boom"

    assert check.pytest_runner(root, []) is None
    assert check.no_runner_reason(root) == want
    _fake_venv(root, pytest_ok=False)
    assert check.no_runner_reason(root) == want
    # One reader after another does not run the failing sync again for the same state.
    calls = (bin_dir / "uv.log").read_text().splitlines()
    assert len(calls) == 2


def test_ac_008_rewrites_only_harness_calls_in_a_chained_command() -> None:
    cmd = (
        "uv run --with mine lint && uv run --with /a python -m harness_maker.x "
        '&& uv run --with "/b c" python -m harness_maker.y '
        "&& uv run --with requests --with /p python -m harness_maker.z"
    )
    entry = {"hooks": [{"type": "command", "command": cmd}, {"type": "command", "command": "ls"}]}
    out = _no_project_entry(entry)
    assert [h["command"] for h in out["hooks"]] == [
        "uv run --with mine lint && uv run --no-project --with /a python -m harness_maker.x "
        '&& uv run --no-project --with "/b c" python -m harness_maker.y '
        "&& uv run --no-project --with requests --with /p python -m harness_maker.z",
        "ls",
    ]
    assert _no_project_entry(out) == out
