"""PLAN-bench-study-adoption Phase 3 exit criterion (b) — the CLI actually appends.

A unit test over `record_row` proves the writer works; it does not prove the **command** calls
it. Terminal plan-validation named that gap: a phase can go green with the calculator correct
and the sink never written. This runs the real entry point in a real temp repo and reads the
file back off disk.

**This is the heavier second sample, NOT the primary verifier.** An earlier draft made it the
only test satisfying exit criterion (a) while gating it behind `INTEGRATION=1`, which means it
did not run in a default `pytest` — the same as not existing, for every gate that decides
whether the phase is done. Phase A.5 round 1 blocked on exactly that. The primary verifier is
now `tests/unit/test_review_complexity.py::test_the_cli_verb_measures_and_writes_the_sink`,
ungated and in-process, following `test_review_churn_measure.py:250`'s precedent for the
sibling verbs.

The gate was also mis-scoped: CLAUDE.md:136 reserves `INTEGRATION=1` for EXTERNAL APIs (arxiv,
GitHub, OSV.dev). Local `git` is not one. What this test still adds over the in-process one is
a **real subprocess** — it proves the module is reachable as `python -m harness_maker.review_churn`
from a foreign cwd, which an in-process `main()` call cannot show. That is worth keeping, and it
is why the gate is kept rather than simply removed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"), reason="INTEGRATION=1 required (shells out to git)"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=60)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src" / "m.py").write_text("def f(a):\n    return a\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "pre")
    return root


def test_the_cli_appends_exactly_one_row_carrying_slug_and_round(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    pre = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=60
    ).stdout.strip()
    (root / "src" / "m.py").write_text(
        "def f(a, b):\n    if a:\n        for x in b:\n            return x\n    return a\n",
        encoding="utf-8",
    )
    _git(root, "commit", "-qam", "post")

    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.review_churn",
            "complexity",
            "--root",
            str(root),
            "--pre",
            pre,
            "--post",
            "HEAD",
            "--slug",
            "demo",
            "--round",
            "2",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert out.returncode == 0, out.stderr

    ledger = root / ".claude" / "observability" / "review-complexity.jsonl"
    assert ledger.is_file(), f"the command ran but wrote no sink; stdout={out.stdout!r}"
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
    assert rows[0]["slug"] == "demo"
    assert rows[0]["round"] == 2

    touched = {f["path"]: f for f in rows[0]["files"]}
    assert "src/m.py" in touched
    entry = touched["src/m.py"]
    assert entry["complexity_status"] == "measured"
    assert entry["pre_complexity"]["cyclomatic"] == 1
    assert entry["post_complexity"]["cyclomatic"] > 1
    assert entry["pre_loc"] == 2
    assert entry["post_loc"] == 5
