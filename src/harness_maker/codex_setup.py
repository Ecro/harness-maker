"""Bundled, standard-library-only Codex plugin lifecycle entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from harness_maker.codex_bootstrap import engine_requirement, update_status


def _run_command(
    argv: list[str],
    *,
    timeout: float = 300,
    capture_output: bool = True,
    text: bool = True,
    shell: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Own the whole uv/engine/generator process tree, including failed launches."""
    if not capture_output or not text or shell:
        raise ValueError("unsupported command mode")
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        process.wait()


def setup(
    action: str,
    project: Path,
    *,
    plugin_root: Path,
    marketplace: str = "harness-maker",
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run_command,
    preset: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """Install the pinned engine and report each independently observed layer."""
    observed: dict[str, Any] = {"plugin": None, "engine": None, "project": None}
    target: str | None = None

    def receipt(error: str | None = None) -> dict[str, Any]:
        status = update_status(target, **observed) if target else None
        return {
            **observed,
            "state": status.state if status else "pending",
            "pending": list(status.pending) if status else ["plugin", "engine", "project"],
            "error": error,
        }

    def run(argv: list[str], *, engine_receipt: bool = False) -> dict[str, Any]:
        try:
            result = runner(
                argv, capture_output=True, text=True, shell=False, timeout=300, check=True
            )
        except subprocess.CalledProcessError as exc:
            if not engine_receipt:
                raise
            result = subprocess.CompletedProcess(argv, exc.returncode, exc.stdout, exc.stderr)
        if result.returncode and not engine_receipt:
            raise ValueError("command_failed")
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError("invalid_receipt")
        if engine_receipt and result.returncode:
            data["error"] = "engine_generation_failed"
        return data

    step = "package"
    try:
        if action not in {"make", "update"} or not re.fullmatch(r"[A-Za-z0-9_-]+", marketplace):
            raise ValueError("invalid_request")
        native = None
        if action == "update":
            step = "marketplace_upgrade"
            upgrade = run(["codex", "plugin", "marketplace", "upgrade", marketplace, "--json"])
            if upgrade.get("errors"):
                raise ValueError("upgrade_failed")
            step = "plugin_install"
            native = run(["codex", "plugin", "add", f"harness-maker@{marketplace}", "--json"])
            plugin_root = Path(native["installedPath"])
            if not plugin_root.is_absolute():
                raise ValueError("invalid_root")
        manifest = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text())
        if not isinstance(manifest, dict):
            raise ValueError("invalid_manifest")
        requirement = engine_requirement(manifest)
        target = manifest["version"]
        if native is not None and (
            native.get("name") != "harness-maker" or native.get("version") != target
        ):
            raise ValueError("identity_mismatch")
        observed["plugin"] = target
        step = "engine_generation"
        argv = [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--with",
            requirement,
            "python",
            "-I",
            str(plugin_root / "scripts/codex_engine.py"),
            str(project.resolve()),
            "--expected",
            requirement.split("==")[1],
        ]
        if action == "update":
            argv.append("--update")
        for flag, value in (("--preset", preset), ("--locale", locale)):
            if value is not None:
                argv.extend([flag, value])
        engine = run(argv, engine_receipt=True)
        if not isinstance(engine.get("engine"), str):
            raise ValueError("invalid_receipt")
        observed["engine"] = engine["engine"]
        if isinstance(engine.get("project"), str) and engine.get("codex_assets") is True:
            observed["project"] = engine["project"]
        if engine.get("error"):
            outcome = receipt("engine_generation_failed")
            # A failed command cannot become complete even if its receipt claims
            # matching versions. Its project generation has not been verified.
            if outcome["state"] == "complete":
                observed["project"] = None
                outcome = receipt("engine_generation_failed")
            return outcome
        return receipt()
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return receipt(f"{step}_failed")


def main(plugin_root: Path) -> int:
    """CLI shared by the installed script and source checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["make", "update"])
    parser.add_argument("project", type=Path)
    parser.add_argument("--marketplace", default="harness-maker")
    parser.add_argument("--preset", choices=["Side", "Production"])
    parser.add_argument("--locale")
    args = vars(parser.parse_args())
    result = setup(plugin_root=plugin_root, **args)
    print(json.dumps(result))
    return 0 if result["state"] == "complete" else 1
