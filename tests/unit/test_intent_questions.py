"""SPEC-intent-lean ADR-005: open questions in `.claude/intent.yaml` (add, observe, resolve).

Replaces the `hm world assume` tests: statuses are canonical (`open|confirmed|wrong`), every
assertion reads the file back or the shipped CLI's output, and a refusal writes nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.unit import intent_fixture as fx

TS = "2026-09-10T00:00:00Z"


def _root(tmp_path: Path) -> Path:
    q = fx.question("existing", claim="E", status="open")
    return fx.build_root(tmp_path, intent=fx.intent_doc(fx.outcome(), questions=[q]), git=False)


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return fx.run_cli(["--root", str(root), "question", *args, "--json"], cwd=root)


def _questions(root: Path) -> list[dict[str, Any]]:
    return list(fx.load(root / ".claude" / "intent.yaml")["open_questions"])


def test_add_appends_a_canonical_question(tmp_path: Path) -> None:
    root = _root(tmp_path)
    proc = _cli(root, "add", "x", "--claim", "C", "--status", "open", "--text", "seen",
                "--observed-at", "2026-09-10T09:00:00+09:00")  # fmt: skip
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert fx.stdout_json(proc)["changed"] == ".claude/intent.yaml"
    assert _questions(root)[-1] == {
        "id": "x",
        "claim": "C",
        "status": "open",
        "evidence": [{"text": "seen", "observed_at": TS, "relation": "confirms"}],
        "history": [],
    }
    assert _questions(root)[0]["id"] == "existing"


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (("existing", "--claim", "C", "--status", "open"), "id"),
        (("Bad-Id", "--claim", "C", "--status", "open"), "id"),
        (("x", "--claim", " ", "--status", "open"), "claim"),
        (("x", "--claim", "C", "--status", "open", "--observed-at", TS), "text"),
    ],
    ids=["duplicate", "bad-id", "empty-claim", "stamp-without-text"],
)
def test_add_refusals_write_nothing(tmp_path: Path, args: tuple[str, ...], field: str) -> None:
    root = _root(tmp_path)
    before = (root / ".claude" / "intent.yaml").read_bytes()
    proc = _cli(root, "add", *args)
    assert proc.returncode == 1
    assert fx.stdout_json(proc)["error"]["field"] == field
    assert (root / ".claude" / "intent.yaml").read_bytes() == before


def test_observe_contradicts_marks_wrong_and_supersedes_keeps_history(tmp_path: Path) -> None:
    root = _root(tmp_path)
    assert _cli(root, "observe", "existing", "--relation", "contradicts", "--text", "no",
                "--observed-at", TS).returncode == 0  # fmt: skip
    q = _questions(root)[0]
    assert q["status"] == "wrong"
    assert q["evidence"][-1] == {"text": "no", "observed_at": TS, "relation": "contradicts"}
    assert _cli(root, "observe", "existing", "--relation", "supersedes", "--text", "moved",
                "--claim", "E2").returncode == 0  # fmt: skip
    q = _questions(root)[0]
    assert (q["claim"], q["history"]) == ("E2", ["E"])
    refused = _cli(root, "observe", "existing", "--relation", "supersedes", "--text", "t")
    assert fx.stdout_json(refused)["error"]["field"] == "claim"


@pytest.mark.parametrize(
    ("start", "target", "ok"),
    [
        ("open", "confirmed", True),
        ("open", "wrong", True),
        ("wrong", "confirmed", True),
        ("wrong", "open", True),
        ("confirmed", "wrong", False),
        ("open", "open", False),
    ],
)
def test_resolve_moves(tmp_path: Path, start: str, target: str, ok: bool) -> None:
    q = fx.question("q", claim="old", status=start)
    root = fx.build_root(tmp_path, intent=fx.intent_doc(fx.outcome(), questions=[q]), git=False)
    before = (root / ".claude" / "intent.yaml").read_bytes()
    proc = _cli(root, "resolve", "q", "--status", target, "--claim", "new")
    assert (proc.returncode == 0) is ok, proc.stdout
    got = _questions(root)[0]
    if ok:
        assert (got["status"], got["claim"], got["history"]) == (target, "new", ["old"])
    else:
        assert (root / ".claude" / "intent.yaml").read_bytes() == before


def test_parallel_adds_never_lose_a_question(tmp_path: Path) -> None:
    """Writers share the checkout lock, so eight parallel adds leave eight new questions."""
    root = _root(tmp_path)
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "harness_maker.hm",
                "intent",
                "--root",
                str(root),
                "question",
                "add",
                f"q{i}",
                "--claim",
                f"c{i}",
                "--status",
                "open",
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )  # fmt: skip
        for i in range(8)
    ]
    outs = [p.communicate(timeout=120) for p in procs]
    assert all(p.returncode == 0 for p in procs), [o[1][-200:] for o in outs]
    assert sorted(q["id"] for q in _questions(root)) == sorted(
        ["existing", *(f"q{i}" for i in range(8))]
    )
