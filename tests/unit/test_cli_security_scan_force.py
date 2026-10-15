"""SPEC-hm-light-lane-s3a AC-008 (CLI half) — `hm cli security-scan --force` skips the scan cache.

The light check runs the scan uncached on the change's checkout before reading Check 4's
findings (IRR-004). `scan_all` is mocked: the real one walks the tree and queries OSV.dev.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

from typer.testing import CliRunner

from harness_maker import security_scanner
from harness_maker.cli import app


def _invoke(tmp_path: Path, *flags: str) -> Any:
    with mock.patch.object(security_scanner, "scan_all", return_value=[]) as scan:
        result = CliRunner().invoke(app, ["security-scan", str(tmp_path), *flags])
    assert result.exit_code == 0, result.output
    return scan


def test_force_bypasses_the_fresh_scan_cache(tmp_path: Path) -> None:
    scan = _invoke(tmp_path, "--force")
    assert scan.call_args.kwargs["force"] is True
    assert scan.call_args.args[0] == tmp_path.resolve()


def test_without_force_the_cache_is_used(tmp_path: Path) -> None:
    scan = _invoke(tmp_path)
    assert scan.call_args.kwargs.get("force", False) is False
