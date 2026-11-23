"""SPEC-self-prune-loop: the hm-variant bench arm and scripts/self_prune.py."""

from __future__ import annotations

import functools
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.unit.test_bench_light_lane import _load

_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN = _ROOT / "specs" / "SPEC-self-prune-loop.golden.json"

bench = _load()


@functools.cache
def _load_prune() -> ModuleType:
    spec = importlib.util.spec_from_file_location("self_prune", _ROOT / "scripts" / "self_prune.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["self_prune"] = module
    spec.loader.exec_module(module)
    return module


class _Lazy:
    """Loads scripts/self_prune.py on first use, so a missing script fails tests, not collection."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_load_prune(), name)


prune = _Lazy()

EXECUTE = """# /hm:execute — title

Intro line.

## Step 0.3 — Verify the PLAN

Confirm each phase line. Review for at most (2) rounds.

## Step 3 — Tests first, then the phases

### Phase A — Write every AC test

Write tests.

```yaml
# not a heading
```

### Phase C — Implement

Implement.

## Step 6 — Review

Review it.
"""


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "render"
    target = root / ".claude" / "commands" / "hm" / "execute.md"
    target.parent.mkdir(parents=True)
    target.write_text(EXECUTE, encoding="utf-8")
    return root


def _edit(**kw: str) -> dict[str, Any]:
    return {"path": ".claude/commands/hm/execute.md", **kw}


def _variant(*edits: dict[str, Any], vid: str = "a", detectable: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {"id": vid, "edits": list(edits)}
    out["detectable_by"] = ["tier-2 trap: scope"] if detectable else []
    return out


def _text(root: Path) -> str:
    return (root / ".claude" / "commands" / "hm" / "execute.md").read_text(encoding="utf-8")


# --- AC-001 -----------------------------------------------------------------------------------


def test_ac_001_apply_variant(tmp_path: Path) -> None:
    assert callable(getattr(bench, "apply_variant", None)), "bench has no apply_variant"
    root = _tree(tmp_path)
    bench.apply_variant(root, _variant(_edit(drop_heading="## Step 3")))
    assert _text(root) == EXECUTE.replace(
        EXECUTE[EXECUTE.index("## Step 3") : EXECUTE.index("## Step 6")], ""
    )

    root2 = _tree(tmp_path / "two")
    bench.apply_variant(root2, _variant(_edit(drop_heading="### Phase A")))
    text = _text(root2)
    assert "Write tests." not in text
    assert "# not a heading" not in text
    assert "### Phase C — Implement" in text
    assert "## Step 6 — Review" in text

    root3 = _tree(tmp_path / "three")
    bench.apply_variant(root3, _variant(_edit(old="(2) rounds", new="(1) rounds")))
    assert _text(root3) == EXECUTE.replace("(2) rounds", "(1) rounds")

    bad = [
        _edit(drop_heading="## Step 9"),
        {"path": ".claude/commands/hm/nope.md", "old": "x", "new": "y"},
        _edit(old="Review", new="Look"),  # occurs more than once
        _edit(old="absent text", new="y"),
        _edit(old="Intro line.", new="Intro line."),  # changes nothing
    ]
    for edit in bad:
        fresh = _tree(tmp_path / f"bad{bad.index(edit)}")
        with pytest.raises(bench.VariantError):
            bench.apply_variant(fresh, _variant(edit))


# --- AC-002 -----------------------------------------------------------------------------------

#: runner_hash on main a0b28554, before this task, for these arguments.
HASH_BEFORE = "5aefb428d926"
HASH_ARGS = ("claude-opus-5-5", 40, 900, 5.0)


def test_ac_002_bench_wiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert "hm-variant" in bench.HM_ARMS
    assert "hm-variant" in bench.ALL_ARMS
    assert bench.runner_hash(*HASH_ARGS) == HASH_BEFORE
    assert bench.runner_hash(*HASH_ARGS, variant_sha="ab") != HASH_BEFORE
    assert bench.runner_hash(*HASH_ARGS, variant_sha="ab") != bench.runner_hash(
        *HASH_ARGS, variant_sha="cd"
    )
    monkeypatch.setenv("INTEGRATION", "1")
    variant = tmp_path / "v.json"
    variant.write_text(json.dumps(_variant(_edit(old="a", new="b"))), encoding="utf-8")
    out = tmp_path / "out"
    assert bench.main(["run", "--arms", "hm-variant", "--out", str(out)]) == 2
    assert "--variant" in capsys.readouterr().err
    assert bench.main(["run", "--arms", "hm", "--variant", str(variant), "--out", str(out)]) == 2
    assert "hm-variant" in capsys.readouterr().err
    assert not out.exists()


def test_ac_002_variant_row_field() -> None:
    opts = bench.Options(
        out=Path("/o"), claude_bin="c", model="m", max_turns=1, timeout_s=1,
        transcript_root=Path("/t"), bench_hash="b", harness_sha="h",
        variant={"id": "drop-x", "edits": [], "detectable_by": []},
    )  # fmt: skip
    assert bench.variant_fields(opts, "hm-variant") == {"variant": "drop-x"}
    assert bench.variant_fields(opts, "hm") == {}


# --- AC-003 -----------------------------------------------------------------------------------

SIX = {
    "per_task_worktree",
    "tdd_red_gate",
    "sdd",
    "human_approval",
    "irr_lock",
    "understanding_delta",
}


def test_ac_003_protected(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    assert prune.protected_hits(root, _variant(_edit(drop_heading="## Step 3")))
    assert prune.protected_hits(root, _variant(_edit(old="Write tests.", new="Tests.")))
    assert not prune.protected_hits(root, _variant(_edit(drop_heading="## Step 0.3")))
    assert not prune.protected_hits(root, _variant(_edit(old="Review it.", new="Go.")))
    assert {p.guard for p in prune.PROTECTED} == SIX


def test_ac_003_protection_bypasses(tmp_path: Path) -> None:
    """Review round 1: an aliased path, text spanning into a protected section, an inserted
    heading dropped by a later edit, and a subsection of a protected section."""
    root = _tree(tmp_path)
    alias = {"path": "./.claude/commands/hm/execute.md", "drop_heading": "### Phase A"}
    assert prune.protected_hits(root, _variant(alias))
    spanning = _edit(old="Confirm each phase line.", new="x")
    assert not prune.protected_hits(root, _variant(spanning))
    into = _edit(old="the phases\n\n### Phase A — Write every AC test\n\nWrite tests.", new="x")
    assert prune.protected_hits(root, _variant(into))
    planted = [
        _edit(old="Confirm each phase line.", new="Confirm.\n\n# Planted"),
        _edit(drop_heading="# Planted"),
    ]
    assert prune.protected_hits(root, _variant(*planted))
    fence = [
        _edit(old="Confirm each phase line.", new="Confirm.\n```"),
        _edit(old="Write tests.", new="x"),
    ]
    problems = prune.candidate_problems(root, [_variant(*fence)])
    assert any("code fence" in p for p in problems)
    assert any("heading" in p for p in prune.candidate_problems(root, [_variant(*planted)]))
    nested = root / ".claude" / "commands" / "hm" / "execute.md"
    nested.write_text(EXECUTE.replace("Write tests.", "Write tests.\n\n#### Deep\n\nDeep text."))
    assert prune.protected_hits(root, _variant(_edit(drop_heading="#### Deep")))
    assert prune.protected_hits(root, _variant(_edit(old="Deep text.", new="x")))


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """The bench's own render (Side) and a Production render with per-task worktrees on."""
    side = tmp_path_factory.mktemp("prune") / "side"
    bench.build_template(side, "hm")
    prod = tmp_path_factory.mktemp("prune") / "prod"
    bench.build_template(prod, "plain")
    argv = [
        sys.executable,
        "-m",
        "harness_maker",
        "make",
        str(prod),
        "--autoloop",
        "--preset",
        "Production",
        "--targets",
        "claude-code",
        "--autonomy-level",
        "auto_full",
        "--worktree",
    ]
    subprocess.run(argv, cwd=prod, stdin=subprocess.DEVNULL, capture_output=True, timeout=300,
                   check=True)  # fmt: skip
    return [side, prod]


def test_ac_003_protected_headings_render(renders: list[Path]) -> None:
    for section in prune.PROTECTED:
        found = False
        for root in renders:
            path = root / section.path
            lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
            marks = [lines[i] for i, _level in bench.headings(lines)]  # fence-aware
            found = found or any(bench.heading_matches(line, section.heading) for line in marks)
        assert found, section


# --- AC-004 -----------------------------------------------------------------------------------


def _plan(tmp_path: Path, candidates: list[dict[str, Any]], name: str) -> tuple[int, set[str]]:
    root = _tree(tmp_path / name)
    file = tmp_path / f"{name}.json"
    file.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")
    out = tmp_path / f"{name}-out"
    code = prune.main(["plan", "--candidates", str(file), "--render", str(root), "--out", str(out)])
    return code, {p.name for p in out.glob("*.json")} if out.exists() else set()


def test_ac_004_plan(tmp_path: Path) -> None:
    ok = _edit(drop_heading="## Step 0.3")
    good = [_variant(ok, vid="a"), _variant(_edit(old="Review it.", new="Go."), vid="b")]
    assert _plan(tmp_path, good, "good") == (0, {"a.json", "b.json"})
    no_detect = _variant(ok)
    del no_detect["detectable_by"]
    bad = {
        "four": [_variant(ok, vid=v) for v in "abcd"],
        "dup": [_variant(ok, vid="a"), _variant(ok, vid="a")],
        "nodetect": [no_detect],
        "nomatch": [_variant(_edit(drop_heading="## Step 9"))],
        "protected": [_variant(_edit(drop_heading="### Phase A"))],
    }
    for name, candidates in bad.items():
        assert _plan(tmp_path, candidates, name) == (2, set()), name


# --- AC-005 -----------------------------------------------------------------------------------


def _golden() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(_GOLDEN.read_text(encoding="utf-8"))["AC-005"]
    return rows


def _side(row: dict[str, Any], i: int) -> dict[str, Any]:
    keys = ("solved", "trap", "judge", "cost", "stalls")
    return {k: row[k][i] for k in keys}


@pytest.mark.parametrize(
    "case",
    [r for r in _golden() if "mismatch" not in r["input"]],
    ids=[f"AC-005-{i}" for i, r in enumerate(_golden()) if "mismatch" not in r["input"]],
)
def test_ac_005_rule(case: dict[str, Any]) -> None:
    row = case["input"]
    verdict, reasons = prune.verdict(_side(row, 0), _side(row, 1), detectable=row["detectable"])
    assert verdict == case["expected"]
    assert reasons or verdict == "adopt"


def _rows(
    arm: str, *, model: str = "m", n: int = 7, solved: int = 7, caught: int = 3,
    vid: str = "drop-a", **same: str,
) -> list[dict[str, Any]]:  # fmt: skip
    """Seven tier-2 rows, plus noise metrics() must ignore: a failed tier-1 row, an unusable
    tier-2 row and (in a baseline) plain rows."""
    ident = {"bench_hash": "b", "harness_sha": "h", "model": model, **same}
    rows = []
    for i in range(n):
        rows.append({
            **ident, "runner_hash": arm,
            "tier": 2, "task": f"t{6 + i}", "arm": arm, "rep": 1, "status": "ok",
            "outcome": "solved" if i < solved else "wrong", "cost_usd": 1.0 if arm == "hm" else 0.8,
            "trap": {"kind": "scope", "caught": i < caught} if i < 3 else None,
            "judge": {"status": "ok", "scores": {"overall": 4.0}},
        })  # fmt: skip
    noise = [
        {**rows[0], "tier": 1, "task": "t1", "outcome": "stalled", "cost_usd": 9.0},
        {**rows[0], "task": "t6", "rep": 2, "status": "runner_error", "outcome": "wrong"},
    ]
    if arm == "hm":
        noise.append({**rows[0], "arm": "plain", "outcome": "stalled", "cost_usd": 0.01})
    for row in rows + noise:
        if arm == "hm-variant":
            row["variant"] = vid
    return rows + noise


def _out(
    tmp_path: Path, name: str, rows: list[dict[str, Any]], variant: dict[str, Any] | None
) -> Path:
    out = tmp_path / name
    out.mkdir()
    (out / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    if variant is not None:
        (out / "variant.json").write_text(json.dumps(variant), encoding="utf-8")
    return out


@pytest.mark.parametrize(
    ("cand_rows", "vid"),
    [
        (_rows("hm-variant", model="other", vid="x"), "x"),
        (_rows("hm-variant", harness_sha="h2", vid="x"), "x"),
        (_rows("hm-variant", bench_hash="b2", vid="x"), "x"),
        (_rows("hm-variant", judge_model="j2", vid="x"), "x"),
        (_rows("hm-variant", vid="other-variant"), "x"),  # rows from another variant
        ([{**r, "tier": 1} for r in _rows("hm-variant", vid="x")], "x"),  # no tier-2 rows
    ],
    ids=["model", "harness", "bench", "judge-model", "variant-id", "no-guard-rows"],
)
def test_ac_005_mismatch_exits_2(tmp_path: Path, cand_rows: list[dict[str, Any]], vid: str) -> None:
    assert [r["expected"] for r in _golden() if "mismatch" in r["input"]] == ["exit 2"]
    base = _out(tmp_path, "base", _rows("hm"), None)
    cand = _out(tmp_path, "cand", cand_rows, _variant(vid=vid))
    ledger = tmp_path / "ledger.jsonl"
    args = ["decide", "--baseline", str(base), "--candidate", str(cand), "--ledger", str(ledger)]
    assert prune.main(args) == 2
    assert not ledger.exists()


def test_ac_005_unequal_runs_hold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A baseline cut short by its budget compares counts over fewer cells: never a verdict."""
    base = _out(tmp_path, "base", _rows("hm", n=5, solved=5), None)
    cand = _out(tmp_path, "cand", _rows("hm-variant"), _variant(vid="drop-a"))
    ledger = tmp_path / "ledger.jsonl"
    argv = ["decide", "--baseline", str(base), "--candidate", str(cand), "--ledger", str(ledger)]
    assert prune.main(argv) == 0
    capsys.readouterr()
    (row,) = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert row["verdict"] == "hold"
    assert any("runs differ" in r for r in row["reasons"])


# --- AC-006 -----------------------------------------------------------------------------------


def test_ac_006_ledger_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = _out(tmp_path, "base", _rows("hm"), None)
    good = _out(tmp_path, "good", _rows("hm-variant"), _variant(vid="drop-a"))
    worse = _out(
        tmp_path, "worse", _rows("hm-variant", solved=5, vid="drop-b"), _variant(vid="drop-b")
    )
    ledger = tmp_path / "ledger.jsonl"
    argv = ["decide", "--baseline", str(base), "--candidate", str(good), "--candidate", str(worse)]
    assert prune.main([*argv, "--ledger", str(ledger)]) == 0
    table = capsys.readouterr().out
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [(r["candidate"], r["verdict"]) for r in rows] == [
        ("drop-a", "adopt"),
        ("drop-b", "reject"),
    ]
    need = {"model", "harness_sha", "candidate", "verdict", "reasons", "metrics", "decided_at"}
    assert all(need <= set(r) for r in rows)
    adopted = [line for line in table.splitlines() if "drop-a" in line]
    assert any("고쳐줘" in line for line in adopted)
    assert not any("고쳐줘" in line for line in table.splitlines() if "drop-b" in line)
    assert prune.main(["status", "--model", "m", "--ledger", str(ledger)]) == 0
    assert capsys.readouterr().out.strip() == "measured"
    assert prune.main(["status", "--model", "m2", "--ledger", str(ledger)]) == 1
    assert capsys.readouterr().out.strip() == "unmeasured"
