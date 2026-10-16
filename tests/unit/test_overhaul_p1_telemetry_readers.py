"""SPEC-hm-overhaul-p1 AC-011: every metrics-*.jsonl reader says it has no telemetry source.

The `telemetry` PostToolUse hook is retired (IRR-005), so no new `metrics-*.jsonl` is written.
A reader that read the absent file as evidence would report "clean" (security) or score a
missing hook as a defect (readiness). The reader list is pinned to a grep of `src/`.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness_maker import readiness, security_scanner
from harness_maker.feedback import telemetry_grep
from harness_maker.models import Finding
from tests._overhaul_p1_ref import REPO_ROOT, clean_env, ref_root

NO_SOURCE = "no telemetry source"
SRC = REPO_ROOT / "src" / "harness_maker"


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security_scanner, "_build_pi_client", lambda: None)


def _project(tmp_path: Path, *, metrics: bool, name: str | None = None) -> Path:
    root = tmp_path / "proj"
    obs = root / ".claude" / "observability"
    obs.mkdir(parents=True)
    if metrics:
        rows = [
            {"event": "post_tool_use", "tool_name": name, "tool_input": json.dumps(args)}
            for name, args in (
                ("Read", {"path": "/srv/prod/db.sqlite"}),
                ("Edit", {"path": "/srv/prod/db.sqlite"}),
                ("Read", {"path": "notes.txt"}),
                ("Delete", {"path": "notes.txt"}),
            )
        ]
        # Dated today by default: a stale file is no telemetry source (ADR-013, P1-d).
        (obs / (name or f"metrics-{date.today().isoformat()}.jsonl")).write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
        )
    return root


def _gate7(findings: list[Finding]) -> list[dict[str, object]]:
    rows = [f.model_dump() for f in findings]
    return [r for r in rows if str(r["category"]).startswith("prod_name_guard")]


def _reference_gate7(root: Path, tmp_path: Path) -> list[dict[str, object]]:
    """Gate 7 as db19f023 computes it on the same file (`git archive` reference)."""
    src = ref_root(tmp_path / "ref") / "src"
    code = (
        "import json, sys; from pathlib import Path\n"
        "from harness_maker.security_scanner import _load_recent_tool_calls\n"
        "from harness_maker.secscan.prod_name_guard import scan_sequence\n"
        "out = scan_sequence(_load_recent_tool_calls(Path(sys.argv[1])))\n"
        "print(json.dumps([f.model_dump() for f in out]))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        env=clean_env(home=tmp_path / "home", src=src),
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    rows: list[dict[str, object]] = json.loads(proc.stdout)
    return rows


def test_ac011_reader_table(tmp_path: Path) -> None:
    # Row 1: security, no metrics file -> a status line, never zero-findings-as-passed.
    empty = _project(tmp_path / "a", metrics=False)
    findings, status = security_scanner.scan_all_with_status(empty, force=True)
    assert status["prod_name_guard"] == NO_SOURCE
    assert not _gate7(findings)
    from harness_maker.cli import app

    out = CliRunner().invoke(app, ["security-scan", str(empty), "--force"]).output
    assert f"prod_name_guard: {NO_SOURCE}" in out, out
    assert not re.search(r"prod_name_guard: (passed|clean|ok)", out)

    # Row 2: with a db19f023-shaped file the findings equal db19f023's on the same file.
    full = _project(tmp_path / "b", metrics=True)
    findings, status = security_scanner.scan_all_with_status(full, force=True)
    assert status["prod_name_guard"] != NO_SOURCE
    got = _gate7(findings)
    assert got, "the fixture is meant to trip Gate 7"
    assert got == _reference_gate7(full, tmp_path)

    # Row 3: readiness — both telemetry signals n/a, labelled, out of the denominator.
    dim = readiness._dim_observability_setup(empty)
    by_id = {s.id: s for s in dim.signals}
    for sid in ("metrics_jsonl_present", "metrics_has_samples"):
        sig = by_id[sid]
        assert sig.not_applicable, sig
        assert sig.weight == 0, sig
        assert "telemetry hook retired" in sig.evidence, sig
        assert sig.action is None
    applicable = [s for s in dim.signals if not s.not_applicable and s.weight]
    earned = sum(s.weight for s in applicable if s.passed)
    assert dim.score == round(100 * earned / sum(s.weight for s in applicable))

    # Row 4: feedback.telemetry_grep.
    assert telemetry_grep.last_stop_with_trace(empty / ".claude" / "observability") == NO_SOURCE
    assert telemetry_grep.last_stop_with_trace(tmp_path / "nowhere") == NO_SOURCE
    bundle = json.loads(telemetry_grep.gather_recent_signals(empty / ".claude" / "observability"))
    assert bundle["metrics"] == NO_SOURCE

    # Row 5: cache_diagnostics is not a reader, and stays one.
    source = (SRC / "cache_diagnostics.py").read_text(encoding="utf-8")
    imported = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    assert not any("_metrics_io" in name for name in imported)
    assert "metrics-" not in source

    # Row 6: the writer's `python -m` entry point is an exit-0 stub that writes nothing.
    proj = _project(tmp_path / "c", metrics=False)
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.telemetry"],
        input=json.dumps({"tool_name": "Read", "workspace": {"current_dir": str(proj)}}),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=proj,
        env={
            **clean_env(home=tmp_path / "home", src=REPO_ROOT / "src"),
            "CLAUDE_PROJECT_DIR": str(proj),
        },
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert not list((proj / ".claude" / "observability").glob("metrics*"))


_READER = re.compile(r"_metrics_io|metrics-")


def test_ac011_reader_list_matches_grep() -> None:
    """A new reader of the retired files must join the AC-011 table (and this set)."""
    readers: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "_metrics_io.py" or "__pycache__" in path.parts:
            continue
        code_lines = [
            ln
            for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.lstrip().startswith("#")
        ]
        if any(_READER.search(ln) for ln in code_lines):
            readers.add(path.relative_to(SRC).with_suffix("").as_posix())
    assert readers == {"security_scanner", "readiness", "feedback/telemetry_grep", "telemetry"}


@pytest.mark.parametrize("kind", ["stale-dated", "stale-legacy"])
def test_ac011_a_stale_file_is_no_telemetry_source(kind: str, tmp_path: Path) -> None:
    """ADR-013's case: a `metrics-*.jsonl` left from before 0.64.0 is history, not a source.

    On an upgraded install the writer is gone but its last files remain, so presence alone would
    keep every reader on "scanned" forever and AC-011's "no telemetry source" would never fire.
    """
    stale = date.today() - timedelta(days=30)
    name = f"metrics-{stale.isoformat()}.jsonl" if kind == "stale-dated" else "metrics.jsonl"
    root = _project(tmp_path, metrics=True, name=name)
    obs = root / ".claude" / "observability"
    if kind == "stale-legacy":
        old = time.time() - 30 * 86400
        os.utime(obs / name, (old, old))
    assert security_scanner.gate_status(root)["prod_name_guard"] == NO_SOURCE
    assert telemetry_grep.last_stop_with_trace(obs) == NO_SOURCE

    # The same file, fresh, is a source again.
    if kind == "stale-dated":
        (obs / name).rename(obs / f"metrics-{date.today().isoformat()}.jsonl")
    else:
        os.utime(obs / name, None)
    assert security_scanner.gate_status(root)["prod_name_guard"] == "scanned"
    assert telemetry_grep.last_stop_with_trace(obs) != NO_SOURCE
