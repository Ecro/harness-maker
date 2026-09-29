"""SPEC-top-issues-2026-09 S1–S4: deterministic `caused_by` stamping and the fix-defect rate.

Every fixture here is a real git repository with pinned `refs/hm-churn/v1/*` endpoints, because
the defect this closes is exactly a value that was "determined" in prose and never reached data:
67 of 69 persisted payloads carried no `caused_by` key at all.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker import review_churn
from harness_maker.review_churn import (
    attribute_findings,
    changed_new_lines,
    fix_defect_rate,
    pin,
)
from harness_maker.spec_machine import GoldenRow, load_golden_table

SLUG = "demo"
RUN = "ea8087ff-20260817T0757Z"
_SPEC = Path(__file__).parents[2] / "specs/SPEC-top-issues-2026-09.machine.yaml"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=60
    ).stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "a.py").write_text("".join(f"line{i}\n" for i in range(1, 61)), encoding="utf-8")
    (root / "b.py").write_text("".join(f"b{i}\n" for i in range(1, 21)), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _round2_fix(root: Path, label: str = "r2") -> None:
    """Pin `<label>-pre`, apply iteration 2's fix, pin `<label>-post` (the loop labels it `r2`).

    The fix inserts ten lines after line 2 of a.py (new-side 3-12) and rewrites original lines
    30-32 (new-side 40-42). Old side and new side then sit more than the +/-3 tolerance apart, so
    an old-side implementation and a new-side one disagree on a.py:31 and a.py:41 — a fixture
    where they coincide cannot tell them apart. It also deletes b.py lines 5-7 outright, which
    git reports as the deletion-only hunk `+4,0`.
    """
    pin(root, SLUG, f"{label}-pre")
    lines = [f"line{i}\n" for i in range(1, 61)]
    lines[29:32] = ["fixed30\n", "fixed31\n", "fixed32\n"]
    lines[2:2] = [f"ins{i}\n" for i in range(10)]
    (root / "a.py").write_text("".join(lines), encoding="utf-8")
    b = [f"b{i}\n" for i in range(1, 21)]
    del b[4:7]
    (root / "b.py").write_text("".join(b), encoding="utf-8")
    pin(root, SLUG, f"{label}-post")


def _finding(fid: str, file: str, line: int | None, **extra: Any) -> dict[str, Any]:
    return {"id": fid, "file": file, "line": line, "severity": "P1", "summary": fid, **extra}


def _run(
    root: Path, findings: list[dict[str, Any]], *, round_n: int = 2, base: Path | None = None
) -> list[dict[str, Any]]:
    return attribute_findings(
        findings,
        root=root,
        base_root=base or root,
        slug=SLUG,
        run_id=RUN,
        round_n=round_n,
    )


# ── AC-001 ───────────────────────────────────────────────────────────────────


def test_finding_inside_fix_delta_is_fix_r1(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _round2_fix(root)
    findings_after = _run(root, [_finding("f41", "a.py", 41)])
    stamped = {f"{f['file']}:{f['line']}": f["caused_by"] for f in findings_after}
    assert stamped["a.py:41"] == "fix-r2"


def test_changed_new_lines_uses_new_side_coordinates(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _round2_fix(root)
    covered = changed_new_lines(
        root, review_churn.pin_ref(SLUG, "r2-pre"), review_churn.pin_ref(SLUG, "r2-post")
    )
    assert set(range(3, 13)) | {40, 41, 42} == covered["a.py"]
    assert {4, 5} == covered["b.py"]  # deletion-only hunk +4,0 → lines 4 and 5


# ── AC-002 (golden table is the SSOT) ────────────────────────────────────────

_ROWS = load_golden_table(_SPEC, "AC-002")


def _situation(root: Path, row: dict[str, Any]) -> tuple[dict[str, Any], int, str | None]:
    raw = str(row["finding"])
    file, _, rest = raw.partition(":")
    line_txt = rest.split(" ")[0]
    line = None if line_txt == "null" else int(line_txt)
    finding = _finding(f"{file}-{line_txt}", file, line)
    if "caused_by key absent" not in raw:
        finding["caused_by"] = None
    else:
        finding.pop("caused_by", None)
    refs = {"refs missing": None, "only r1 refs pinned": "r1"}.get(str(row["fix_new_side"]), "r2")
    return finding, int(row["round"]), refs


@pytest.mark.parametrize(
    "row", _ROWS, ids=[f"row{i}-{r.input['finding']}" for i, r in enumerate(_ROWS)]
)
def test_non_attributable_cases(tmp_path: Path, row: GoldenRow) -> None:
    root = _repo(tmp_path)
    finding, round_n, refs = _situation(root, row.input)
    if refs is not None and round_n >= 2:
        _round2_fix(root, label=refs)
    out = _run(root, [finding], round_n=round_n)
    assert out[0]["caused_by"] == row.expected


# ── AC-003 (frame property) ──────────────────────────────────────────────────

_CAUSE = st.one_of(st.none(), st.just("__absent__"), st.sampled_from(["none", "fix-r1", "#7"]))
_EXTRA = st.dictionaries(
    st.sampled_from(["lens", "voices", "resolution", "status"]),
    st.one_of(st.text(max_size=5), st.integers(), st.lists(st.text(max_size=3), max_size=2)),
    max_size=3,
)


def _strip(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in f.items() if k != "caused_by"} for f in findings]


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    specs=st.lists(
        st.tuples(
            _CAUSE,
            st.sampled_from(["a.py", "b.py", "c.py"]),
            st.one_of(st.none(), st.integers(1, 60)),
            _EXTRA,
        ),
        min_size=1,
        max_size=6,
    ),
    wrapped=st.booleans(),
)
def test_attribute_changes_only_unstamped_caused_by(
    tmp_path_factory: pytest.TempPathFactory,
    specs: list[tuple[Any, str, int | None, dict[str, Any]]],
    wrapped: bool,
) -> None:
    root = _repo(tmp_path_factory.mktemp("p"))
    _round2_fix(root)
    findings: list[dict[str, Any]] = []
    for i, (cause, file, line, extra) in enumerate(specs):
        f = _finding(f"id{i}", file, line, **extra)
        if cause != "__absent__":
            f["caused_by"] = cause
        findings.append(f)
    payload: Any = {"findings": findings, "meta": {"k": 1}} if wrapped else findings
    path = root / "payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    review_churn.attribute_file(path, root=root, base_root=root, slug=SLUG, run_id=RUN, round_n=2)
    out_payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(out_payload, dict) == wrapped
    if wrapped:
        assert out_payload["meta"] == {"k": 1}
    out = out_payload["findings"] if wrapped else out_payload
    assert _strip(out) == _strip(findings)
    for before, after in zip(findings, out, strict=True):
        if isinstance(before.get("caused_by"), str):
            assert after.get("caused_by") == before.get("caused_by")
    assert all(isinstance(after.get("caused_by"), str) for after in out)


def test_attribute_cli_rewrites_file_and_prints_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The public verb end to end: argv → --root/base-root wiring → rewrite → one JSON line.

    Hand-counted: a.py:41 is inside the fix (fix-r2), a.py:55 is not (none), a.py:null in a
    changed file is unknown. Rendered templates call this verb by name (IRR-002).
    """
    root = _repo(tmp_path)
    _round2_fix(root)
    path = root / "payload.json"
    path.write_text(
        json.dumps(
            [_finding("in", "a.py", 41), _finding("out", "a.py", 55), _finding("nl", "a.py", None)]
        ),
        encoding="utf-8",
    )
    rc = review_churn.main(
        [
            "attribute",
            "--slug", SLUG,
            "--run-id", RUN,
            "--round", "2",
            "--findings-file", str(path),
            "--root", str(root),
        ]
    )  # fmt: skip
    assert rc == 0
    stamped = {f["id"]: f["caused_by"] for f in json.loads(path.read_text(encoding="utf-8"))}
    assert stamped == {"in": "fix-r2", "out": "none", "nl": "unknown"}
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lines) == 1
    summary = json.loads(lines[0])
    assert summary["round"] == 2
    assert summary["counts"] == {"fix-r2": 1, "none": 1, "unknown": 1}


# ── AC-004 ───────────────────────────────────────────────────────────────────


def test_malformed_file_untouched(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _round2_fix(root)
    path = root / "bad.json"
    original_bytes = b'{"findings": [ not json'
    path.write_bytes(original_bytes)
    rc = review_churn.main(
        [
            "attribute",
            "--slug", SLUG,
            "--run-id", RUN,
            "--round", "2",
            "--findings-file", str(path),
            "--root", str(root),
        ]
    )  # fmt: skip
    assert rc == 1
    assert path.read_bytes() == original_bytes


# ── AC-014 (carried ids, same run only) ──────────────────────────────────────


def _persist(
    base: Path, slug: str, run_id: str, round_n: int, findings: list[dict[str, Any]]
) -> None:
    store = base / ".claude" / "observability" / "review-payloads" / slug
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{run_id}-round{round_n}-merged.json").write_text(
        json.dumps(findings), encoding="utf-8"
    )


def test_carried_ids_same_run_only(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _round2_fix(root)
    carried_in_delta = "X"
    other_run_id = "Y"
    _persist(root, SLUG, "other-run", 1, [_finding(other_run_id, "a.py", 41, caused_by="none")])
    # "L" is a legacy carried id whose earlier value was never stamped.
    _persist(root, SLUG, RUN, 1, [
        _finding(carried_in_delta, "a.py", 41, caused_by="none"),
        _finding("L", "a.py", 40),
    ])  # fmt: skip
    out = _run(
        root,
        [
            _finding(carried_in_delta, "a.py", 41),
            _finding(other_run_id, "a.py", 41),
            _finding("L", "a.py", 40),
        ],
    )
    stamped = {f["id"]: f["caused_by"] for f in out}
    assert stamped[carried_in_delta] == "none"
    assert stamped[other_run_id] == "fix-r2"
    assert stamped["L"] == "unknown"


# ── AC-005 ───────────────────────────────────────────────────────────────────


def test_fix_defect_rate_report(tmp_path: Path) -> None:
    base = tmp_path
    run1 = "ea8087ff-20260817T0757Z"
    r1 = [_finding("carried", "a.py", 1, caused_by="none")]
    r2 = [
        _finding("f1", "a.py", 2, caused_by="fix-r1"),
        _finding("f2", "a.py", 3, caused_by="none"),
        _finding("carried", "a.py", 1, caused_by="fix-r1"),  # carried → excluded
        {**_finding("p2", "a.py", 4, caused_by="fix-r1"), "severity": "P2"},  # excluded
    ]
    _persist(base, "s-one", run1, 1, r1 + [_finding("r1only", "a.py", 9, caused_by="fix-r1")])
    _persist(base, "s-one", run1, 2, r2)
    _persist(base, "s-two", "20260807T0210Z-posthoc", 2, [
        {**_finding("g1", "b.py", 2, caused_by="fix-r1"), "severity": "P0"},
        _finding("g2", "b.py", 3, caused_by="none"),
        _finding("g3", "b.py", 4, caused_by="unknown"),
        _finding("g4", "b.py", 5),
    ])  # fmt: skip
    report = fix_defect_rate(base)
    expected_counts = {"fix": 2, "none": 2, "unknown": 1, "unstamped": 1}
    assert report["total"]["counts"] == expected_counts
    assert report["total"]["rate"] == 0.5
    assert report["slugs"].keys() == {"s-one", "s-two"}
    assert report["slugs"]["s-one"]["counts"] == {"fix": 1, "none": 1, "unknown": 0, "unstamped": 0}
    assert report["slugs"]["s-two"]["rate"] == 0.5


def test_fix_defect_rate_cli_prints_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _persist(tmp_path, "s", "r-1", 2, [
        _finding("a", "a.py", 1, caused_by="fix-r1"),
        _finding("b", "a.py", 2, caused_by="none"),
    ])  # fmt: skip
    rc = review_churn.main(["fix-defect-rate", "--root", str(tmp_path)])
    assert rc == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0]) == fix_defect_rate(tmp_path)
    assert json.loads(lines[0])["total"]["rate"] == 0.5


def test_fix_defect_rate_null_when_no_denominator(tmp_path: Path) -> None:
    _persist(tmp_path, "s", "r", 2, [_finding("u", "a.py", 1, caused_by="unknown")])
    assert fix_defect_rate(tmp_path)["total"]["rate"] is None
