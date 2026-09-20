"""AC-001/002/003: observable native lifecycle, pinned engine and honest completion."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from harness_maker.codex_setup import setup

ROOT = Path(__file__).resolve().parents[2]


def plugin(root: Path, version: str = "0.58.0") -> Path:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "harness-maker", "version": version})
    )
    return root


class Commands:
    def __init__(self, installed: Path, *, fail: str = "", engine: str = "0.58.0"):
        self.installed = installed
        self.fail = fail
        self.engine = engine
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        assert kwargs.get("shell", False) is False
        if self.fail and self.fail in argv:
            return subprocess.CompletedProcess(argv, 1, "", "credential-SENTINEL")
        result: dict[str, Any]
        if argv[:3] == ["codex", "plugin", "add"]:
            result = {
                "name": "harness-maker",
                "version": "0.58.0",
                "installedPath": str(self.installed),
            }
        elif argv[:4] == ["codex", "plugin", "marketplace", "upgrade"]:
            result = {}
        else:
            result = {"engine": self.engine, "project": "0.58.0", "codex_assets": True}
        return subprocess.CompletedProcess(argv, 0, json.dumps(result), "")


def test_ac_001_distributed_skills_resolve_the_bundled_script() -> None:
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert manifest["skills"] == "./skills/"
    for name in ("hm-make", "hm-update"):
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert "scripts/codex_setup.py" in text
        assert "CLAUDE_PLUGIN_ROOT" not in text
    assert (ROOT / "scripts/codex_setup.py").is_file()
    assert (ROOT / "scripts/codex_engine.py").is_file()


def test_ac_002_make_pins_engine_and_uses_installed_script(tmp_path: Path) -> None:
    pkg = plugin(tmp_path / "plugin with spaces", "0.58.0+codex.dev")
    commands = Commands(pkg)
    result = setup("make", tmp_path / "project with spaces", plugin_root=pkg, runner=commands)
    assert result["state"] == "complete"
    assert result["plugin"] == "0.58.0+codex.dev"
    argv = commands.calls[0]
    assert argv[:6] == [
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        "harness-maker==0.58.0",
    ]
    assert argv[6:8] == ["python", "-I"]
    assert str(pkg / "scripts/codex_engine.py") in argv
    assert str(tmp_path / "project with spaces") in argv


def test_ac_003_update_uses_reinstalled_root(tmp_path: Path) -> None:
    old = plugin(tmp_path / "old", "0.57.0")
    new = plugin(tmp_path / "new")
    commands = Commands(new)
    result = setup(
        "update", tmp_path, plugin_root=old, marketplace="harness-maker", runner=commands
    )
    assert result["state"] == "complete"
    assert commands.calls[0] == [
        "codex",
        "plugin",
        "marketplace",
        "upgrade",
        "harness-maker",
        "--json",
    ]
    assert commands.calls[1] == ["codex", "plugin", "add", "harness-maker@harness-maker", "--json"]
    assert str(new / "scripts/codex_engine.py") in commands.calls[2]
    assert "harness-maker==0.58.0" in commands.calls[2]


@pytest.mark.parametrize("failure", ["upgrade", "add", "uv"])
def test_ac_003_partial_failures_never_report_complete(tmp_path: Path, failure: str) -> None:
    pkg = plugin(tmp_path / "package")
    commands = Commands(pkg, fail=failure)
    result = setup("update", tmp_path, plugin_root=pkg, runner=commands)
    assert result["state"] == ("partial" if failure == "uv" else "pending")
    assert result["plugin"] == ("0.58.0" if failure == "uv" else None)
    assert result["engine"] is None
    assert result["project"] is None
    assert result["pending"] == (
        ["engine", "project"] if failure == "uv" else ["plugin", "engine", "project"]
    )
    assert result["error"]
    assert "credential-SENTINEL" not in json.dumps(result)
    assert len(commands.calls) == {"upgrade": 1, "add": 2, "uv": 3}[failure]


def test_ac_003_observed_engine_mismatch_is_not_success(tmp_path: Path) -> None:
    pkg = plugin(tmp_path / "package")
    result = setup("make", tmp_path, plugin_root=pkg, runner=Commands(pkg, engine="0.57.0"))
    assert result["state"] == "partial"
    assert "engine" in result["pending"]


@pytest.mark.parametrize("raw", ["{}", "null", "[]", "not json"])
def test_ac_003_invalid_engine_receipt_is_not_success(tmp_path: Path, raw: str) -> None:
    pkg = plugin(tmp_path / "package")

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, raw, "")

    result = setup("make", tmp_path, plugin_root=pkg, runner=runner)
    assert result["state"] != "complete"


def test_ac_003_native_version_must_match_installed_manifest(tmp_path: Path) -> None:
    old = plugin(tmp_path / "old")
    wrong = plugin(tmp_path / "wrong", "0.57.0")
    commands = Commands(wrong)
    result = setup("update", tmp_path, plugin_root=old, runner=commands)
    assert result["state"] != "complete"
    assert len(commands.calls) == 2


def test_ac_002_engine_reuses_generator_and_preserves_user_blocks(tmp_path: Path) -> None:
    project = tmp_path / "project with spaces"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname="demo"\nversion="0.1.0"\n')
    env = dict(os.environ, HOME=str(tmp_path / "isolated-home"))
    Path(env["HOME"]).mkdir()
    cmd = [
        sys.executable,
        "-I",
        str(ROOT / "scripts/codex_engine.py"),
        str(project),
        "--expected",
        "0.58.0",
        "--preset",
        "Side",
        "--locale",
        "en",
        "--dev-mode",
        "task-driven",
    ]
    first = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120, check=True)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout) == {
        "engine": "0.58.0",
        "project": "0.58.0",
        "codex_assets": True,
    }
    assert (project / ".codex/config.toml").is_file()
    assert (project / ".agents/skills/hm-execute/SKILL.md").is_file()
    assert "name: hm-execute" in (project / ".agents/skills/hm-execute/SKILL.md").read_text()
    assert list((project / ".codex/agents").glob("*.toml"))
    agents = project / "AGENTS.md"
    text = agents.read_text()
    marker = "<!-- @hm:user:extensions -->"
    assert marker in text
    agents.write_text(text.replace(marker, marker + "\nSentinel: retain this custom convention.\n"))
    update = subprocess.run(
        cmd + ["--update"], env=env, capture_output=True, text=True, timeout=120, check=True
    )
    assert update.returncode == 0, update.stderr
    assert "Sentinel: retain this custom convention." in agents.read_text()
    before = agents.read_text()
    again = subprocess.run(
        cmd + ["--update"], env=env, capture_output=True, text=True, timeout=120, check=True
    )
    assert again.returncode == 0, again.stderr
    assert "Sentinel: retain this custom convention." in agents.read_text()
    # Generated time/hash may move, but the owned user block must remain byte-identical.
    assert before.split(marker)[1] == agents.read_text().split(marker)[1]


def test_ac_001_entrypoint_resolves_copied_install_without_claude_cache(tmp_path: Path) -> None:
    installed = tmp_path / "installed package with spaces"
    for rel in (".codex-plugin", "scripts", "src/harness_maker"):
        (installed / rel).mkdir(parents=True, exist_ok=True)
    for rel in (
        ".codex-plugin/plugin.json",
        "scripts/codex_setup.py",
        "scripts/codex_engine.py",
        "src/harness_maker/__init__.py",
        "src/harness_maker/codex_setup.py",
        "src/harness_maker/codex_bootstrap.py",
    ):
        shutil.copy2(ROOT / rel, installed / rel)
    capture = tmp_path / "args.json"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        f"#!{sys.executable}\nimport sys,json\n"
        f"json.dump(sys.argv[1:],open({str(capture)!r},'w'))\n"
        "print(json.dumps({'engine':'0.58.0','project':'0.58.0','codex_assets':True}))\n"
    )
    uv.chmod(0o700)
    home = tmp_path / "clean-home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])
    proc = subprocess.run(
        [sys.executable, str(installed / "scripts/codex_setup.py"), "make", str(tmp_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["state"] == "complete"
    args = json.loads(capture.read_text())
    assert str(installed / "scripts/codex_engine.py") in args
    assert not (home / ".claude/plugins/cache").exists()


def test_ac_003_project_mismatch_independent_of_engine(tmp_path: Path) -> None:
    pkg = plugin(tmp_path / "package")

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            argv, 0, json.dumps({"engine": "0.58.0", "project": "0.57.0", "codex_assets": True}), ""
        )

    result = setup("make", tmp_path, plugin_root=pkg, runner=runner)
    assert result["state"] == "partial"
    assert result["engine"] == "0.58.0"
    assert result["project"] == "0.57.0"
    assert result["pending"] == ["project"]


def test_ac_003_failed_engine_preserves_existing_custom_files(tmp_path: Path) -> None:
    pkg = plugin(tmp_path / "package")
    project = tmp_path / "project"
    project.mkdir()
    sentinel = b"<!-- @hm:user:extensions -->\nkeep exactly\n<!-- @hm:/user:extensions -->\n"
    (project / "AGENTS.md").write_bytes(sentinel)
    result = setup("update", project, plugin_root=pkg, runner=Commands(pkg, fail="uv"))
    assert result["state"] == "partial"
    assert (project / "AGENTS.md").read_bytes() == sentinel
    assert result["pending"] == ["engine", "project"]


@pytest.mark.parametrize("checked", [False, True])
def test_ac_003_nonzero_engine_preserves_observed_layers(tmp_path: Path, checked: bool) -> None:
    pkg = plugin(tmp_path / "package")

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raw = json.dumps({"engine": "0.58.0", "project": "0.57.0", "codex_assets": True})
        if checked:
            raise subprocess.CalledProcessError(1, argv, output=raw)
        return subprocess.CompletedProcess(argv, 1, raw, "")

    result = setup("make", tmp_path, plugin_root=pkg, runner=runner)
    assert result["state"] == "partial"
    assert result["engine"] == "0.58.0"
    assert result["project"] == "0.57.0"
    assert result["pending"] == ["project"]
    assert result["error"] == "engine_generation_failed"


@pytest.mark.parametrize("raw", ["[]", "null", "42"])
def test_ac_003_malformed_manifest_reports_pending(tmp_path: Path, raw: str) -> None:
    pkg = plugin(tmp_path / "package")
    (pkg / ".codex-plugin/plugin.json").write_text(raw)
    result = setup("make", tmp_path, plugin_root=pkg, runner=Commands(pkg))
    assert result["state"] == "pending"
    assert result["error"] == "package_failed"


def test_ac_003_timeout_kills_owned_generation_tree(tmp_path: Path) -> None:
    from harness_maker.codex_setup import _run_command

    pidfile = tmp_path / "child.pid"
    code = (
        "import subprocess,sys,time\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\n"
        f"open({str(pidfile)!r},'w').write(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    pid = None
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            _run_command([sys.executable, "-c", code], timeout=1)
        pid = int(pidfile.read_text())
        status = Path(f"/proc/{pid}/stat")
        deadline = time.monotonic() + 2
        while (
            status.exists() and status.read_text().split()[2] != "Z" and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert not status.exists() or status.read_text().split()[2] == "Z"
    finally:
        if pid is not None:
            import contextlib
            import signal

            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


def test_ac_003_upgrade_error_receipt_stops_before_reinstall(tmp_path: Path) -> None:
    pkg = plugin(tmp_path / "package")
    calls = []

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '{"errors":["secret-SENTINEL"]}', "")

    result = setup("update", tmp_path, plugin_root=pkg, runner=runner)
    assert result["state"] == "pending"
    assert result["error"] == "marketplace_upgrade_failed"
    assert len(calls) == 1
    assert "secret-SENTINEL" not in json.dumps(result)


def test_ac_003_failed_receipt_cannot_claim_complete(tmp_path: Path) -> None:
    pkg = plugin(tmp_path / "package")

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            argv, 1, json.dumps({"engine": "0.58.0", "project": "0.58.0", "codex_assets": True}), ""
        )

    result = setup("make", tmp_path, plugin_root=pkg, runner=runner)
    assert result["state"] == "partial"
    assert result["engine"] == "0.58.0"
    assert result["pending"] == ["project"]
