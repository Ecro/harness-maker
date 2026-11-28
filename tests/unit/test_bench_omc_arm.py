"""SPEC-bench-omc-arm — the oh-my-claudecode arm in the tier 1/2 and saga benches, offline."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

# AC-002 golden rows from SPEC-bench-omc-arm.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_002_ROWS = [
    (
        {"runner": "bench_light_lane", "task": "t1", "arm": "plain"},
        "Add an optional `max_units` parameter to `format_duration` i",
    ),
    (
        {"runner": "bench_light_lane", "task": "t1", "arm": "hm"},
        "/hm:spec Add an optional `max_units` parameter to `format_du",
    ),
    (
        {"runner": "bench_light_lane", "task": "t1", "arm": "omc"},
        "/oh-my-claudecode:execute Add an optional `max_units` parame",
    ),
]

# AC-003 golden rows from SPEC-bench-omc-arm.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_003_ROWS = [
    (
        {"claude_bin": "c", "prompt": "p", "model": "m", "max_turns": 5, "max_budget_usd": 1.0},
        [
            "c",
            "-p",
            "p",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            "--max-turns",
            "5",
            "--model",
            "m",
            "--max-budget-usd",
            "1",
            "--setting-sources",
            "project,local",
            "--strict-mcp-config",
        ],
    ),
]

# AC-005 golden rows from SPEC-bench-omc-arm.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_005_ROWS = [
    (
        {
            "runner": "bench_light_lane",
            "model": "claude-sonnet-5-5",
            "max_turns": 200,
            "timeout_s": 1800,
            "max_budget_usd": 2.0,
            "pass_env": [],
            "claude_version": "v1",
        },
        "c2140abbf394",
    ),
    (
        {"runner": "saga_bench", "options": "default with out=/x", "claude_version": "v1"},
        "3ad4cf9e1937",
    ),
]  # noqa: E501


def _load(name: str) -> ModuleType:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bll() -> ModuleType:
    return _load("bench_light_lane")


@pytest.fixture(scope="module")
def saga() -> ModuleType:
    return _load("saga_bench")


def _plugin(root: Path, name: str = "oh-my-claudecode", version: str = "5.8.9") -> Path:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}), encoding="utf-8"
    )
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True, timeout=60)
    subprocess.run([*git, "add", "-A"], cwd=root, check=True, timeout=60)
    subprocess.run([*git, "commit", "-q", "-m", "x"], cwd=root, check=True, timeout=60)
    return root


def _sha(root: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                         check=True, timeout=60)  # fmt: skip
    return out.stdout.strip()


# --- AC-001 ------------------------------------------------------------------------------------


def test_ac_001_omc_setup(bll: ModuleType, tmp_path: Path) -> None:
    plugin_dir = _plugin(tmp_path / "omc")
    other = _plugin(tmp_path / "other", name="superpowers")
    assert bll.omc_setup(["plain", "hm"], None) is None
    assert bll.omc_setup(["plain", "omc"], plugin_dir) == (_sha(plugin_dir), "5.8.9")
    (plugin_dir / "stray.txt").write_text("x", encoding="utf-8")
    assert bll.omc_setup(["omc"], plugin_dir) == (_sha(plugin_dir) + "-dirty", "5.8.9")
    not_git = tmp_path / "not-git" / "omc"
    (not_git / ".claude-plugin").mkdir(parents=True)
    (not_git / ".claude-plugin" / "plugin.json").write_text('{"name": "oh-my-claudecode"}')
    refused = 0
    for arms, path in ((["omc"], None), (["plain"], plugin_dir), (["omc"], other),
                       (["omc"], tmp_path / "missing"), (["omc"], not_git)):  # fmt: skip
        with pytest.raises(bll.OmcError):
            bll.omc_setup(arms, path)
        refused += 1
    assert refused == 5


def test_ac_001_runners_refuse_before_spend(
    bll: ModuleType, saga: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    monkeypatch.setenv("INTEGRATION", "1")
    monkeypatch.setenv("IS_SANDBOX", "1")
    out = tmp_path / "out"
    wrong = _plugin(tmp_path / "wrong", name="superpowers")
    for extra in ([], ["--omc-dir", str(wrong)]):
        assert bll.main(["run", "--arms", "plain,omc", "--out", str(out), *extra]) == 2
        assert "refusing --omc-dir" in capsys.readouterr().err
        assert saga.main(["run", "--arms", "plain,omc", "--out", str(out), *extra]) == 2
        assert "refusing --omc-dir" in capsys.readouterr().err
    assert not out.exists()


# --- AC-002 ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "expected"), AC_002_ROWS, ids=[f"AC-002-{i}" for i in range(len(AC_002_ROWS))]
)
def test_ac_002_prompts(bll: ModuleType, args: dict[str, Any], expected: str) -> None:
    task = next(t for t in bll.load_tasks() if t.id == args["task"])
    assert bll.prompt_for(task, args["arm"])[:60] == expected


def test_ac_002_saga_prompts(saga: ModuleType) -> None:
    sessions = saga.load_saga().sessions
    first = sessions[0]
    resume = next(s for s in sessions if s.resume_of is not None)
    assert saga.prompt_for(first, "omc") == saga.bll.OMC_PREFIX + first.prompt
    assert saga.prompt_for(resume, "omc") == resume.prompt
    assert saga.prompt_for(first, "plain") == first.prompt


# --- AC-003 ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("args", "expected"), AC_003_ROWS, ids=["AC-003-0"])
def test_ac_003_argv(
    bll: ModuleType, args: dict[str, Any], expected: list[str], tmp_path: Path
) -> None:
    base = bll.agent_argv(args["claude_bin"], args["prompt"], args["model"], args["max_turns"],
                          args["max_budget_usd"])  # fmt: skip
    assert base == expected
    assert bll.omc_argv(base, tmp_path) == [*expected, "--plugin-dir", str(tmp_path)]


def test_ac_003_session_argv_per_arm(bll: ModuleType, tmp_path: Path) -> None:
    task = next(t for t in bll.load_tasks() if t.id == "t1")
    opts = bll.Options(
        out=tmp_path, claude_bin="c", model="m", max_turns=5, timeout_s=1, transcript_root=tmp_path,
        bench_hash="b", harness_sha="h", omc_dir=tmp_path / "omc",
    )  # fmt: skip
    omc = bll.session_argv(task, "omc", 0, opts)
    plain = bll.session_argv(task, "plain", 0, opts)
    assert omc[-2:] == ["--plugin-dir", str(tmp_path / "omc")]
    assert "--plugin-dir" not in plain
    assert omc[2] == bll.OMC_PREFIX + plain[2]


# --- AC-004 ------------------------------------------------------------------------------------


def test_ac_004_own_home(bll: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    operator = tmp_path / "operator"
    operator.mkdir()
    (operator / ".gitconfig").write_text("[user]\n\tname = op\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(operator))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    (operator / ".cache").mkdir()
    cell = tmp_path / "cell"
    plain_env = bll.agent_env()
    env = bll.agent_env(overrides=bll.omc_env(cell / "home"))
    config_dir = str(operator / ".claude")
    assert env["HOME"] == str(cell / "home")
    assert (cell / "home" / ".gitconfig").is_file()
    assert (cell / "home" / ".cache").resolve() == operator / ".cache"
    assert not (cell / "home" / ".config").exists()
    assert bll.omc_env(cell / "home") == bll.omc_env(cell / "home")  # a saga run's next turn
    assert env["CLAUDE_CONFIG_DIR"] == config_dir
    assert plain_env == bll.agent_env()
    assert plain_env["HOME"] == str(operator)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert bll.omc_env(cell / "home2")["CLAUDE_CONFIG_DIR"] == str(tmp_path / "cfg")


def test_ac_004_saga_turn_env(
    saga: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "operator"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    seen: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_invoke(argv: list[str], *_a: Any, **kw: Any) -> tuple[str, int, bool]:
        seen.append((argv, kw.get("env_overrides")))
        return "", 1, False

    monkeypatch.setattr(saga, "invoke", fake_invoke)
    opts = saga.Options(out=tmp_path, omc_dir=tmp_path / "omc")
    for arm in ("omc", "plain"):
        saga._agent_turn("p", "task", None, opts, tmp_path, tmp_path / "log", None, arm=arm,
                         home=tmp_path / "run" / "home" if arm == "omc" else None)  # fmt: skip
    (omc_argv, omc_env), (plain_argv, plain_env) = seen
    assert "--plugin-dir" in omc_argv
    assert "--plugin-dir" not in plain_argv
    assert omc_env is not None
    assert omc_env["HOME"] == str(tmp_path / "run" / "home")
    assert omc_env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "cfg")
    assert plain_env is None


def test_ac_004_run_cell_wiring(
    bll: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_cell hands the omc env and argv to the agent call and stamps the row; plain gets
    neither."""
    monkeypatch.setenv("HOME", str(tmp_path / "operator"))
    calls: list[tuple[list[str], dict[str, str] | None]] = []

    def fake_invoke(argv: list[str], *_a: Any, **kw: Any) -> tuple[str, str, int]:
        calls.append((argv, kw.get("env_overrides")))
        return "", "", 1

    monkeypatch.setattr(bll, "_invoke", fake_invoke)
    monkeypatch.setattr(bll, "_record", lambda row, *_a, **_k: row)
    template = tmp_path / "template"
    template.mkdir()
    (template / "README.md").write_text("x", encoding="utf-8")
    task = next(t for t in bll.load_tasks() if t.id == "t1")
    opts = bll.Options(
        out=tmp_path / "out", claude_bin="c", model="m", max_turns=5, timeout_s=1,
        transcript_root=tmp_path, bench_hash="b", harness_sha="h", templates={"plain": template},
        omc_dir=tmp_path / "omc", omc_sha="abc", omc_version="5.8.9",
    )  # fmt: skip
    omc_row = bll.run_cell(task, "omc", 1, opts)
    plain_row = bll.run_cell(task, "plain", 1, opts)
    (omc_argv, omc_env), (plain_argv, plain_env) = calls
    assert omc_row["omc_sha"] == "abc"
    assert omc_row["omc_version"] == "5.8.9"
    assert "omc_sha" not in plain_row
    assert omc_argv[-2:] == ["--plugin-dir", str(tmp_path / "omc")]
    assert "--plugin-dir" not in plain_argv
    assert omc_env is not None
    assert omc_env["HOME"] == str(Path(omc_row["run_dir"]) / "home")
    assert plain_env is None


def test_ac_005_saga_options(saga: ModuleType, tmp_path: Path) -> None:
    opts = saga.Options(out=tmp_path)
    assert saga._with_omc(opts, None, None) is opts
    found = saga._with_omc(opts, ("abc", "5.8.9"), str(tmp_path))
    assert (found.omc_dir, found.omc_sha, found.omc_version) == (tmp_path, "abc", "5.8.9")


# --- AC-005 ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("args", "expected"), AC_005_ROWS, ids=["AC-005-0", "AC-005-1"])
def test_ac_005_hashes(
    bll: ModuleType, saga: ModuleType, args: dict[str, Any], expected: str
) -> None:
    if args["runner"] == "bench_light_lane":
        call = (args["model"], args["max_turns"], args["timeout_s"], args["max_budget_usd"],
                tuple(args["pass_env"]), args["claude_version"])  # fmt: skip
        assert bll.runner_hash(*call) == expected
        assert bll.runner_hash(*call, omc_sha="abc") != expected
    else:
        opts = saga.Options(out=Path("/x"))
        assert saga.runner_hash(opts, args["claude_version"]) == expected
        with_omc = saga.Options(out=Path("/x"), omc_dir=Path("/o"), omc_sha="abc")
        assert saga.runner_hash(with_omc, args["claude_version"]) != expected


def test_ac_005_row_fields(bll: ModuleType, tmp_path: Path) -> None:
    opts = bll.Options(
        out=tmp_path, claude_bin="c", model="m", max_turns=5, timeout_s=1, transcript_root=tmp_path,
        bench_hash="b", harness_sha="h", omc_dir=tmp_path, omc_sha="abc", omc_version="5.8.9",
    )  # fmt: skip
    assert bll.omc_fields(opts, "omc") == {"omc_sha": "abc", "omc_version": "5.8.9"}
    assert bll.omc_fields(opts, "plain") == {}


# --- AC-006 ------------------------------------------------------------------------------------


def _row(task: str, arm: str, rep: int, cost: float) -> dict[str, Any]:
    return {
        "bench": "hm-light-lane", "bench_hash": "b", "harness_sha": "h", "model": "m",
        "runner_hash": "r", "tier": 1, "task": task, "arm": arm, "rep": rep, "status": "ok",
        "passed": True, "outcome": "solved", "cost_usd": cost, "cli_cost_usd": cost,
        "transcript_cost_usd": cost, "transcript_turns": 2, "num_turns": 2, "wall_s": 10.0,
        "hidden": {"tests": 4, "failures": 0, "errors": 0, "skipped": 0},
        "judge": {"status": "off"},
    }  # fmt: skip


def test_ac_006_report_and_publish(bll: ModuleType, tmp_path: Path) -> None:
    base_rows = [_row(t, a, r, 0.1 if a == "plain" else 0.5) for t in ("t1", "t2")
                 for a in ("plain", "hm") for r in (1, 2)]  # fmt: skip
    rows = base_rows + [_row(t, "omc", r, 0.3) for t in ("t1", "t2") for r in (1, 2)]
    text = bll.report_text(rows)
    unchanged_text = bll.report_text(list(base_rows))
    assert bll.EXTERNAL_TITLE in text
    assert bll.EXTERNAL_TITLE not in unchanged_text
    assert "3.00x" in text  # omc $0.300 over plain $0.100
    assert text.startswith(unchanged_text)
    out = tmp_path / "out"
    out.mkdir()
    (out / bll.RESULTS).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert not [r for r in bll.publish_rows(out) if r["arm"] == "omc"]


def test_ac_006_saga_report(saga: ModuleType) -> None:
    def row(arm: str, true: range) -> dict[str, Any]:
        return {"arm": arm, "status": "ok", "traps": {f"T{i}": i in true for i in range(5)}}

    base_rows = [row("hm", range(4)), row("plain-discipline", range(2))]
    rows = [*base_rows, row("omc", range(1))]
    text = saga.report(rows)
    assert any(line.startswith("omc ") for line in text.splitlines())
    assert "hm vs omc" in text
    assert "hm vs omc" not in saga.report(base_rows)
    assert saga.verdict(rows) == saga.verdict(base_rows)
