"""SPEC-wrapup-gate: the review requirement at wrapup and the deterministic Do-not-change check."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import check
from harness_maker.spec_machine import load_golden_table
from tests.hm_cost_p2_fixture import init_project
from tests.unit.test_hm_cost_p3_reuse import _opts, _project

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_YAML = REPO_ROOT / "specs" / "SPEC-wrapup-gate.machine.yaml"
REVIEW = "work-docs/REVIEW-s-2026-11-10.md"
REVIEW_BODY = (
    "# REVIEW\n\n## Findings\n\n| id | severity | finding | disposition | authority |\n"
    "|---|---|---|---|---|\n| F1 | nit | x | accepted | SPEC |\n"
)


def _rows(ac: str) -> list[Any]:
    return [pytest.param(r, id=f"{ac}-{i}") for i, r in enumerate(load_golden_table(SPEC_YAML, ac))]


@pytest.mark.parametrize("row", _rows("AC-001"))
def test_ac_001_require_review(tmp_path: Path, row: Any) -> None:
    given, want = row.input, row.expected
    if given["review_doc"]:
        (tmp_path / "work-docs").mkdir()
        (tmp_path / REVIEW).write_text(REVIEW_BODY, encoding="utf-8")
    state = "missing" if given["approval"] == "missing_auto_full" else given["approval"]

    def review(require: bool) -> check.Section:
        return check.review_section(
            tmp_path,
            "s",
            {"autonomy": {"level": "auto_full"}},
            changed=list(given["changed"]),
            state=state,
            require=require,
        )

    section = review(given["require_review"])
    assert section.body["ok"] is want["review_ok"]
    assert section.code == want["exit"]
    assert section.body.get("reason") == want["reason"]
    # Without the flag (execute's pre-review gate) every row is today's behaviour.
    off = review(False)
    assert off.body["ok"] is True
    assert off.code == check.EXIT_OK
    assert off.body.get("reason") == (None if given["review_doc"] else "no REVIEW record")


def test_ac_002_identical_reprint_still_requires_review(tmp_path: Path) -> None:
    p = _project(tmp_path)
    first = check.run(_opts(p.root))
    assert first["exit"] == 0, first
    runs = p.gate_runs()
    again = check.run(_opts(p.root, require_review=True), reuse=True)
    assert again["exit"] == check.EXIT_FAILED, again
    assert again["sections"]["review"]["reason"] == "no REVIEW record for a non-doc change"
    assert p.gate_runs() == runs, "the gate ran again instead of being reused"


def test_ac_002_cli_flag_reaches_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _project(tmp_path)
    argv = ["--slug", "demo", "--root", str(p.root), "--offline"]
    assert check.main(argv) == 0
    capsys.readouterr()
    assert check.main([*argv, "--reuse", "--require-review"]) == check.EXIT_FAILED
    assert "no REVIEW record for a non-doc change" in capsys.readouterr().out


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        timeout=30,
    )


def _plan(row_input: dict[str, Any]) -> str:
    dnc = "\n".join(row_input.get("dnc", []))
    adrs = "\n\n".join(row_input.get("adr", []))
    return (
        "---\ntype: plan\ntask_slug: s\n---\n\n# PLAN\n\n- Phase 1 — scope: x\n\n"
        f"## 🚧 Contract Boundaries\n\n### Do not change\n\n{dnc}\n\n{adrs}\n"
    )


@pytest.mark.parametrize("row", _rows("AC-003"))
def test_ac_003_contract_section(tmp_path: Path, row: Any) -> None:
    given, want = row.input, row.expected
    root = init_project(tmp_path / "p")
    if given.get("plan", True):
        (root / "work-docs").mkdir()
        (root / "work-docs" / "PLAN-s.md").write_text(_plan(given), encoding="utf-8")
    for rel in given["changed"]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("v1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    for rel in given["changed"]:
        (root / rel).write_text("v2\n", encoding="utf-8")
    for rel in given.get("untracked", []):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("new\n", encoding="utf-8")
    section = check.contract_section(root, "s", {}, check.changed_paths(root))
    assert section.body["ok"] is want["ok"]
    assert section.code == (check.EXIT_OK if want["ok"] else check.EXIT_FAILED)
    if "reason" in want:
        assert section.body["reason"] == want["reason"]
    else:
        assert section.body["crossed"] == want["crossed"]
        assert section.body["allowed"] == want["allowed"]
        assert section.body["advisory"] == want.get("advisory", [])


def test_ac_003_identical_reprint_recomputes_contract(tmp_path: Path) -> None:
    """A PLAN in an ignored directory is invisible to the tree snapshot, so an identical
    reprint must still read it."""
    p = _project(tmp_path)
    (p.root / ".gitignore").write_text("work-docs/\n", encoding="utf-8")
    assert check.run(_opts(p.root))["exit"] == 0
    runs = p.gate_runs()
    (p.root / "work-docs").mkdir()
    (p.root / "work-docs" / "PLAN-demo.md").write_text(
        "### Do not change\n\n- `tests/test_ok.py`\n", encoding="utf-8"
    )
    again = check.run(_opts(p.root), reuse=True)
    assert again.get("reused") is True, again
    assert again["exit"] == check.EXIT_FAILED
    assert again["sections"]["contract"]["crossed"] == ["tests/test_ok.py"]
    assert p.gate_runs() == runs


def test_ac_003_red_skips_contract(tmp_path: Path) -> None:
    p = _project(tmp_path)
    (p.root / "work-docs").mkdir()
    (p.root / "work-docs" / "PLAN-demo.md").write_text(
        "### Do not change\n\n- `tests/test_ok.py`\n", encoding="utf-8"
    )
    assert check.run(_opts(p.root))["sections"]["contract"]["crossed"] == ["tests/test_ok.py"]
    red = check.run(_opts(p.root, red=True))
    assert red["sections"]["contract"] == {"ok": True, "skipped": "--red"}


def _stage_text(runtime: str, stage: str) -> str:
    from tests.unit.test_pipeline_env_fixes import _stage

    return _stage(f"stages/{stage}.md.j2", is_codex=runtime == "codex")


def _step(text: str, heading: str) -> str:
    start = text.index(f"## {heading}")
    nxt = text.find("\n## ", start + 1)
    return text[start : nxt if nxt != -1 else len(text)]


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_ac_004_stage_text(runtime: str) -> None:
    wrapup = _stage_text(runtime, "wrapup")
    execute = _stage_text(runtime, "execute")
    assert "hm check --slug <slug> --reuse --require-review" in wrapup
    assert "Compare `git diff --name-only HEAD`" not in execute
    assert "`contract.crossed`" in _step(execute, "Step 4")
    assert "allows: <path>" in _step(execute, "Step 0")
