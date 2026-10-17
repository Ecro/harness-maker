"""SPEC-review-effect-measurement — parser, interval, escape row, report and score (no git)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import review_effect as re_mod
from harness_maker.spec_machine import load_golden_table

_YAML = (
    Path(__file__).resolve().parents[2] / "specs" / "SPEC-review-effect-measurement.machine.yaml"
)


# ── AC-001 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", load_golden_table(_YAML, "AC-001"))
def test_ac_001_parse_review_golden(row: Any, capsys: pytest.CaptureFixture[str]) -> None:
    parsed = re_mod.parse_review(row.input["file"])
    exp = row.expected
    assert parsed.status == exp["status"]
    assert parsed.counts == exp["counts"]
    assert parsed.severe_accepted == exp["severe_accepted"]
    assert parsed.unrecognized_n == exp["unrecognized_n"]
    if exp.get("stderr_warning"):
        assert "review_effect" in capsys.readouterr().err


# ── AC-005 ──────────────────────────────────────────────────────────────────


def _ledger(root: Path) -> Path:
    return root / ".claude" / "observability" / "review-effect.jsonl"


def _rows(root: Path) -> list[dict[str, Any]]:
    p = _ledger(root)
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _escape_argv(root: Path, **kw: str) -> list[str]:
    vals = {
        "commit": "a" * 40,
        "verdict": "escape",
        "introduced_by": "bar",
        "flagged": "no",
        "reviewable": "yes",
        "reason": "off-by-one",
    }
    vals.update(kw)
    return [
        "escape",
        "--root",
        str(root),
        "--commit",
        vals["commit"],
        "--verdict",
        vals["verdict"],
        "--introduced-by",
        vals["introduced_by"],
        "--flagged",
        vals["flagged"],
        "--reviewable",
        vals["reviewable"],
        "--reason",
        vals["reason"],
    ]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()  # resolve_base_root stops at the first repo marker
    return tmp_path


@pytest.mark.parametrize("row", load_golden_table(_YAML, "AC-005"))
def test_ac_005_escape_row(row: Any, project: Path) -> None:
    inp, exp = row.input, row.expected
    if inp.get("same_commit_twice"):
        assert re_mod.main(_escape_argv(project)) == 0
        rc = re_mod.main(_escape_argv(project))
    elif "flagged" in inp and inp["flagged"] not in ("yes", "no", "not-reviewed", "unknown"):
        with pytest.raises(SystemExit) as exc:
            re_mod.main(_escape_argv(project, flagged=inp["flagged"]))
        rc = int(exc.value.code or 0)
    else:
        rc = re_mod.main(
            _escape_argv(
                project,
                verdict=inp.get("verdict", "escape"),
                flagged=inp.get("flagged", "no"),
                reviewable=inp.get("reviewable", "yes"),
            )
        )
    assert rc == exp["exit"]
    rows = [r for r in _rows(project) if r["event"] == "escape"]
    assert len(rows) == exp["rows"]
    for r in rows:
        for key in ("schema_version", "event", "ts", "slug", "harness_version", "commit"):
            assert key in r
    if "listed_by_escape_candidates" in exp:
        assert re_mod.recorded_escape_commits(rows) == {"a" * 40}


# ── AC-006 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("row", load_golden_table(_YAML, "AC-006"))
def test_ac_006_clopper_pearson_golden(row: Any) -> None:
    lo, hi = re_mod.clopper_pearson(row.input["k"], row.input["n"])
    assert lo == pytest.approx(row.expected["lo"], abs=1e-4)
    assert hi == pytest.approx(row.expected["hi"], abs=1e-4)


_KN = st.integers(min_value=1, max_value=200).flatmap(
    lambda n: st.tuples(st.integers(0, n), st.just(n))
)


@settings(deadline=None)
@given(_KN)
def test_ac_006_clopper_pearson_brackets_the_point_estimate(kn: tuple[int, int]) -> None:
    k, n = kn
    lo, hi = re_mod.clopper_pearson(k, n)
    assert 0.0 <= lo <= k / n <= hi <= 1.0


# ── AC-007 ──────────────────────────────────────────────────────────────────


def _row(event: str, slug: str, **kw: Any) -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "event": event,
        "ts": "2026-10-17T00:00:00Z",
        "slug": slug,
        "harness_version": "0.0.0",
    }
    base.update(kw)
    return base


def _review(slug: str, status: str, severe: int = 0, commit: str = "c") -> dict[str, Any]:
    return _row(
        "review",
        slug,
        commit=commit,
        review_file=None,
        status=status,
        counts={},
        severe_accepted=severe,
        unrecognized_n=0,
    )


def _escape(slug: str, verdict: str, flagged: str, reviewable: str, commit: str) -> dict[str, Any]:
    return _row(
        "escape",
        slug,
        commit=commit,
        verdict=verdict,
        flagged=flagged,
        reviewable=reviewable,
        reason="r",
    )


_AC007_LEDGERS: list[tuple[list[dict[str, Any]], list[dict[str, str]]] | None] = [
    None,
    (
        [
            _review("foo", "parsed", 1, "c1"),
            _review("baz", "none", 0, "c2"),
            _review("qux", "absent", 0, "c3"),
            _review("zed", "unparseable", 0, "c4"),
            _review("foo", "parsed", 0, "c5"),
            _escape("baz", "escape", "no", "yes", "e1"),
            _escape("baz", "not-escape", "unknown", "unknown", "e2"),
        ],
        [{"key": "slug", "value": "zed", "reason": "test"}],
    ),
    (
        [_review("x", "parsed", 1, "c1"), _escape("x", "escape", "no", "yes", "e1")],
        [{"key": "slug", "value": "x", "reason": "test"}],
    ),
]


@pytest.mark.parametrize(
    ("row", "fixture"), list(zip(load_golden_table(_YAML, "AC-007"), _AC007_LEDGERS, strict=True))
)
def test_ac_007_report(
    row: Any, fixture: Any, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if fixture is not None:
        rows, exclusions = fixture
        obs = project / ".claude" / "observability"
        obs.mkdir(parents=True)
        _ledger(project).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (obs / ".ledger-exclusions.json").write_text(json.dumps(exclusions), encoding="utf-8")
    assert re_mod.main(["report", "--root", str(project), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    exp = row.expected
    my = out["marginal_yield"]
    assert f"{my['k']}/{my['n']}" == exp["marginal_yield"]
    if "escape_miss" in exp:
        em = out["escape_miss"]
        assert f"{em['k']}/{em['n']}" == exp["escape_miss"]
    # text form never prints a bare percentage
    assert re_mod.main(["report", "--root", str(project)]) == 0
    text = capsys.readouterr().out
    assert "%" not in text
    assert "/" in text


# ── AC-009 ──────────────────────────────────────────────────────────────────


def _loc(s: str) -> tuple[str, int | None]:
    f, _, ln = s.rpartition(":")
    return f, (None if ln == "null" else int(ln))


@pytest.mark.parametrize("row", load_golden_table(_YAML, "AC-009"))
def test_ac_009_score_golden(row: Any) -> None:
    seeds = [{"file": f, "line": ln} for f, ln in map(_loc, row.input["seeds"])]
    findings = [{"file": f, "line": ln} for f, ln in map(_loc, row.input["findings"])]
    assert re_mod.score(seeds, findings) == row.expected["hits"]
    assert len(seeds) == row.expected["seeded"]


def test_ac_009_score_record_appends_recall_row(project: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    findings = tmp_path / "f.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "file": "a.py",
                    "line": 10,
                    "operator": "cmp-flip",
                    "original": "a < b",
                    "mutated": "a <= b",
                }
            ]
        ),
        encoding="utf-8",
    )
    findings.write_text(json.dumps([{"file": "a.py", "line": 11}]), encoding="utf-8")
    rc = re_mod.main(
        [
            "score",
            "--root",
            str(project),
            "--manifest",
            str(manifest),
            "--findings",
            str(findings),
            "--record",
            "--slug",
            "s",
            "--model",
            "m",
        ]
    )
    assert rc == 0
    rows = [r for r in _rows(project) if r["event"] == "recall"]
    assert len(rows) == 1
    assert rows[0]["hits"] == 1
    assert rows[0]["seeded"] == 1
    assert rows[0]["model"] == "m"


# ── review round 1 regressions ─────────────────────────────────────────────


def _real_repo(root: Path) -> str:
    import subprocess

    def g(*a: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *a], capture_output=True, text=True, check=True
        ).stdout.strip()

    g("init", "-b", "main")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "T")
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-m", "fix: a")
    return g("rev-parse", "HEAD")


def test_ac_005_short_sha_resolves_and_dedupes(tmp_path: Path) -> None:
    full = _real_repo(tmp_path)
    assert re_mod.main(_escape_argv(tmp_path, commit=full[:8])) == 0
    rows = [r for r in _rows(tmp_path) if r["event"] == "escape"]
    assert [r["commit"] for r in rows] == [full]
    assert re_mod.main(_escape_argv(tmp_path, commit=full)) == 1


def test_ac_005_unresolvable_short_commit_exits_2(tmp_path: Path) -> None:
    _real_repo(tmp_path)
    assert re_mod.main(_escape_argv(tmp_path, commit="deadbee")) == 2
    assert _rows(tmp_path) == []


def test_ac_006_clopper_pearson_large_n_does_not_overflow() -> None:
    lo, hi = re_mod.clopper_pearson(550, 1100)
    assert lo == pytest.approx(0.4700, abs=2e-3)
    assert hi == pytest.approx(0.5300, abs=2e-3)


def test_ac_007_report_recall_status_and_format(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [
        {**_review("a", "parsed", 1, "c1"), "unrecognized_n": 2},
        _review("b", "absent", 0, "c2"),
        _row("recall", "a", hits=2, seeded=3, model="m", manifest_sha256="x"),
        _row("recall", "b", hits=1, seeded=2, model="m", manifest_sha256="y"),
    ]
    obs = project / ".claude" / "observability"
    obs.mkdir(parents=True)
    _ledger(project).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert re_mod.main(["report", "--root", str(project), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["reviews"]["by_status"] == {"parsed": 1, "absent": 1}
    assert out["unrecognized_n"] == 2
    assert (out["seeded_recall"]["k"], out["seeded_recall"]["n"]) == (3, 5)
    assert re_mod.main(["report", "--root", str(project)]) == 0
    import re

    text = capsys.readouterr().out
    assert re.search(r"seeded recall \(hits / seeded\): 3/5 \[\d\.\d{3}, \d\.\d{3}\]", text)
    assert re.search(r": 1/1 \[\d\.\d{3}, \d\.\d{3}\]", text)


def test_ac_009_score_rejects_malformed_manifest(project: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    findings = tmp_path / "f.json"
    manifest.write_text(json.dumps([{"file": "a.py"}]), encoding="utf-8")
    findings.write_text(json.dumps([{"file": "a.py", "line": 1}]), encoding="utf-8")
    argv = ["score", "--root", str(project), "--manifest", str(manifest)]
    assert re_mod.main([*argv, "--findings", str(findings)]) == 2
