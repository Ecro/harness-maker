#!/usr/bin/env python3
"""Pre-release smoke test — build wheel, install into an isolated venv, exercise the CLI.

Runs end-to-end without touching PyPI or TestPyPI. Intended as the human-runnable
gate before a maintainer pushes a ``v*`` tag (see ``docs/release-checklist.md``).

Why Python and not bash: CLAUDE.md §Runtime mandates Python-only scripts so
``security_scanner`` does not flag its own toolchain.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUILD_TIMEOUT = 180
_INSTALL_TIMEOUT = 120
_CLI_TIMEOUT = 60


def _log(msg: str) -> None:
    """Single banner format so the script's output is grep-able from CI logs."""
    print(f"[release_smoke] {msg}", flush=True)


def _run(
    cmd: list[str],
    *,
    timeout: float,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Forward to ``subprocess.run`` with CLAUDE.md-mandated defaults.

    ``timeout`` is keyword-only and required — mypy enforces every call site
    supplies one (CLAUDE.md §외부 명령 호출). Adding new kwargs here is fine,
    but never widen ``cmd`` to ``str`` or pass ``shell=True`` — both bypass
    the security_scanner hook injection guard.
    """
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


def _venv_bin(venv: Path) -> Path:
    """Return the platform-specific scripts directory of a virtualenv."""
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _harness_maker_exe(venv: Path) -> Path:
    """Resolve the installed ``harness-maker`` console script."""
    name = "harness-maker.exe" if os.name == "nt" else "harness-maker"
    return _venv_bin(venv) / name


def _build_wheel(out_dir: Path) -> Path:
    """Build sdist + wheel into ``out_dir`` and return the wheel path."""
    _log(f"building dist into {out_dir}")
    _run(
        ["uv", "build", "--out-dir", str(out_dir)],
        cwd=str(_REPO_ROOT),
        timeout=_BUILD_TIMEOUT,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"uv build produced no wheel in {out_dir}")
    wheel = wheels[-1]
    _log(f"built {wheel.name}")
    return wheel


def _install_into_venv(wheel: Path, venv: Path) -> None:
    """Create an isolated venv and install the wheel into it."""
    _log(f"creating venv at {venv}")
    _run(["uv", "venv", str(venv)], timeout=_INSTALL_TIMEOUT)
    _log(f"installing {wheel.name} into venv")
    _run(
        ["uv", "pip", "install", "--python", str(_venv_bin(venv) / "python"), str(wheel)],
        timeout=_INSTALL_TIMEOUT,
    )


def _exercise_cli(venv: Path, proj_dir: Path) -> None:
    """Smoke the installed CLI: ``--help``, ``profile``, ``make``."""
    exe = _harness_maker_exe(venv)
    if not exe.exists():
        raise RuntimeError(f"installed harness-maker binary missing at {exe}")

    _log("harness-maker --help")
    help_out = _run([str(exe), "--help"], timeout=_CLI_TIMEOUT)
    if "harness-maker" not in help_out.stdout.lower():
        raise RuntimeError(f"--help did not mention harness-maker: {help_out.stdout!r}")

    _log("harness-maker profile <tmp> --json")
    prof = _run([str(exe), "profile", str(proj_dir), "--json"], timeout=_CLI_TIMEOUT)
    try:
        json.loads(prof.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"profile --json output is not valid JSON: {exc}") from exc

    _log("harness-maker make <tmp> --preset Side --locale en --targets claude-code --autoloop")
    _run(
        [
            str(exe),
            "make",
            str(proj_dir),
            "--preset",
            "Side",
            "--locale",
            "en",
            "--targets",
            "claude-code",
            "--autoloop",
        ],
        timeout=_CLI_TIMEOUT,
    )

    harness_yaml = proj_dir / ".claude" / "harness.yaml"
    if not harness_yaml.exists():
        raise RuntimeError(f"make did not produce {harness_yaml}")
    _log(f"harness.yaml rendered at {harness_yaml}")


def main() -> int:
    """Run the full smoke. Returns 0 on success, non-zero on failure."""
    tmp_root = Path(tempfile.mkdtemp(prefix="harness-smoke-"))
    dist_dir = tmp_root / "dist"
    venv_dir = tmp_root / "venv"
    proj_dir = tmp_root / "project"
    dist_dir.mkdir()
    proj_dir.mkdir()
    try:
        wheel = _build_wheel(dist_dir)
        _install_into_venv(wheel, venv_dir)
        _exercise_cli(venv_dir, proj_dir)
        _log("ALL SMOKE CHECKS PASSED")
        return 0
    except subprocess.CalledProcessError as exc:
        _log(f"FAILED: {' '.join(exc.cmd)} exited {exc.returncode}")
        if exc.stdout:
            _log(f"stdout: {exc.stdout[-2000:]}")
        if exc.stderr:
            _log(f"stderr: {exc.stderr[-2000:]}")
        return exc.returncode or 1
    except subprocess.TimeoutExpired as exc:
        _log(f"FAILED: timeout after {exc.timeout}s on {' '.join(map(str, exc.cmd))}")
        return 1
    except (RuntimeError, OSError) as exc:
        _log(f"FAILED: {exc}")
        return 1
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
