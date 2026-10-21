"""SPEC-hm-cost-p3 AC-002: `hm check --reuse` reuses only an identical passing verdict."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import check
from harness_maker.spec_machine import load_golden_table
from tests.hm_cost_p2_fixture import init_project, mech_ac, write_spec

SPEC_YAML = Path(__file__).parents[2] / "specs" / "SPEC-hm-cost-p3.machine.yaml"
NODE = "tests/test_ok.py::test_ok"


@dataclass
class Project:
    root: Path
    marker: Path
    fail_flag: Path

    def gate_runs(self) -> int:
        return len(self.marker.read_text().splitlines()) if self.marker.exists() else 0


def _project(tmp: Path) -> Project:
    """A task whose extra gate and AC test both append to a marker outside the tree, so a fresh
    run (normal or RED) is observed without reading hm check's own output; the gate fails while
    `fail_flag` exists."""
    root = init_project(tmp / "p")
    marker, fail_flag = tmp / "gate-runs.log", tmp / "gate-fails"
    gate = (
        f"python3 -c \"import os, sys; open('{marker}', 'a').write('x\\n'); "
        f"sys.exit(1 if os.path.exists('{fail_flag}') else 0)\""
    )
    cfg = {"autonomy": {"level": "auto_full"}, "reviewers": {"mechanical_checks": [gate]}}
    (root / ".claude" / "harness.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    write_spec(root, [mech_ac("AC-001", pending_test=False, test_ids=[NODE])])
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text(
        f"def test_ok():\n    open({str(marker)!r}, 'a').write('t\\n')\n    assert 1 + 1 == 2\n"
    )
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)
    return Project(root, marker, fail_flag)


def _opts(root: Path, **kw: Any) -> check.Options:
    return check.Options(**{"slug": "demo", "root": root, "offline": True, **kw})


def _edit_record(root: Path, **fields: Any) -> None:
    path = check.verdict_path(root)
    assert path is not None
    assert path.is_file(), "a passing run wrote no verdict record"
    record = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**record, **fields}), encoding="utf-8")


def _seed(p: Project, record: str) -> None:
    if record == "none":
        return
    if record == "written_by_failed_run":
        p.fail_flag.touch()
        assert check.run(_opts(p.root))["exit"] == 1
        path = check.verdict_path(p.root)
        assert path is not None
        assert not path.exists(), "a failed run wrote a verdict record"
        return
    assert check.run(_opts(p.root))["exit"] == 0
    if record == "pass_other_slug":
        _edit_record(p.root, slug="other")
    elif record == "pass_other_version":
        _edit_record(p.root, harness_maker_version="0.0.0")
    elif record == "fail":
        _edit_record(p.root, exit=1)


def _change(p: Project, change: str) -> None:
    if change == "edit_listed_file":
        with (p.root / "tests" / "test_ok.py").open("a") as f:
            f.write("# edited\n")
    elif change == "add_untracked_file":
        (p.root / "notes.txt").write_text("new\n")
    elif change == "head_moved_same_tree":
        subprocess.run(
            ["git", "-C", str(p.root), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "move"],
            check=True, timeout=30,
        )  # fmt: skip
    elif change == "git_dir_unwritable":
        path = check.verdict_path(p.root)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o500)


VARIANTS: dict[str, dict[str, Any]] = {
    "reuse_red": {"red": True, "green_ok": {"AC-001"}},
    "reuse_mutation": {"mutation": True},
    "reuse_offline_differs": {"offline": False},
    "reuse_harness": {"harness": True},
    "reuse_full_differs": {"full": False},
    "reuse_green_ok_differs": {"green_ok": {"AC-001"}},
}


def _act(p: Project, args: str, capsys: pytest.CaptureFixture[str]) -> tuple[dict[str, Any], str]:
    capsys.readouterr()
    if args in ("reuse", "plain"):
        argv = ["--slug", "demo", "--root", str(p.root), "--offline", "--full"]
        code = check.main([*argv, "--reuse"] if args == "reuse" else argv)
        captured = capsys.readouterr()
        line = json.loads(captured.out.strip().splitlines()[-1])
        assert line["exit"] == code
        return line, captured.err
    opts = _opts(p.root, **VARIANTS[args])
    result = check.run(opts, reuse=True, cve_query=lambda *a, **k: [])
    return result, capsys.readouterr().err


def _row_id(row: Any) -> str:
    return "-".join(map(str, row.input.values()))


@pytest.mark.parametrize("row", load_golden_table(SPEC_YAML, "AC-002"), ids=_row_id)
def test_ac_002_reuse(tmp_path: Path, row: Any, capsys: pytest.CaptureFixture[str]) -> None:
    if row.input["change"] == "git_dir_unwritable" and os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    p = _project(tmp_path)
    _seed(p, row.input["record"])
    _change(p, row.input["change"])
    before = p.gate_runs()
    snap = check.snapshot(p.root)
    try:
        result, err = _act(p, row.input["args"], capsys)
    finally:
        path = check.verdict_path(p.root)
        if path is not None and path.parent.exists():
            path.parent.chmod(0o755)
    observed = {
        "gates_ran": p.gate_runs() > before,
        "reused": result.get("reused") is True,
        "exit": result["exit"],
    }
    assert observed == row.expected
    # The record lives outside the work tree: writing it never moves the fingerprint.
    assert check.snapshot(p.root) == snap
    if row.input["change"] == "git_dir_unwritable":
        assert "verdict not recorded" in err
        path = check.verdict_path(p.root)
        assert path is not None
        assert not path.exists()


def test_a_fresh_failure_drops_an_earlier_pass(tmp_path: Path) -> None:
    """Pass, then the same tree fails (the gate reads state outside the tree), then --reuse:
    the gate must run again rather than reprint the pass (second-opinion finding, review 1)."""
    p = _project(tmp_path)
    assert check.run(_opts(p.root))["exit"] == 0
    p.fail_flag.touch()
    assert check.run(_opts(p.root))["exit"] == 1
    before = p.gate_runs()
    result = check.run(_opts(p.root), reuse=True)
    assert p.gate_runs() > before
    assert result["exit"] == 1
    assert result.get("reused") is not True


def test_an_ignored_config_change_runs_fresh(tmp_path: Path) -> None:
    """The harness config feeds approval and review; git may ignore it, so the key hashes it."""
    p = _project(tmp_path)
    (p.root / ".gitignore").write_text(".claude/harness.yaml\n")
    assert check.run(_opts(p.root))["exit"] == 0
    cfg_path = p.root / ".claude" / "harness.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg_path.write_text(yaml.safe_dump({**cfg, "reviewers": {**cfg["reviewers"], "fanout": True}}))
    before = p.gate_runs()
    assert check.run(_opts(p.root), reuse=True).get("reused") is not True
    assert p.gate_runs() > before


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_an_unreadable_file_is_never_recorded(tmp_path: Path) -> None:
    """Its digest is a constant, so a change inside it would be invisible to the key."""
    p = _project(tmp_path)
    secret = p.root / "locked.txt"
    secret.write_text("x\n")
    secret.chmod(0)
    try:
        assert check.run(_opts(p.root))["exit"] in (0, 1)
        path = check.verdict_path(p.root)
        assert path is not None
        assert not path.exists()
    finally:
        secret.chmod(0o644)
