"""AC-002/003/004 (SPEC-intent-layer-ops) — `hm world gap` measures the withdrawal criterion.

Oracles are golden. Every expected value is fixed by the fixture, never read back from the
reader: commits carry a pinned `GIT_COMMITTER_DATE` (with a non-UTC offset, so a reader that
forgets to normalise fails), the stage-spans ledger is hand-written with a known number of
`hm:wrapup` `start` events either side of the fill commit plus lines that must NOT count (`end`
events, a non-wrapup stage, a malformed line, a timezone-less `ts`). AC-003 and AC-004 load their
rows from `specs/SPEC-intent-layer-ops.machine.yaml` — the table is the single source.

Git is isolated from the host (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`) so a
signing or hook config on the machine cannot change the fixture.

Phase A.4 — two tests pass before the change, by design: `test_ac_004_every_table_row_has_a_fixture`
is a positive control on the test itself (a table row without a builder would go untested), and
the AC-004 `intent.yaml invalid` row is the negative invariant that the invalid payload carries
no `withdrawal` key (it goes red if the block leaks into `_invalid_payload`); its RED positive
siblings are every other AC-004 row and AC-002, which force the block into existence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import world
from harness_maker.spec_machine import GoldenRow, load_golden_table
from tests.unit import world_fixture as fx

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-intent-layer-ops.machine.yaml"
_KEYS = {
    "filled_at",
    "wrapups_since_fill",
    "objectives_observed",
    "revisit_candidates_now",
    "due",
    "reason",
}

SKELETON_DATE = "2026-09-01T10:00:00+09:00"
FILL_DATE = "2026-09-10T12:00:00+09:00"
FILL_ISO = "2026-09-10T03:00:00Z"


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(root: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    if date is not None:
        env["GIT_COMMITTER_DATE"] = date
        env["GIT_AUTHOR_DATE"] = date
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    ).stdout.strip()


def _skeleton() -> dict[str, Any]:
    return fx.intent_doc(mission="")


def _commit(root: Path, date: str, msg: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", msg, date=date)


def _filled_repo(
    root: Path,
    *,
    objectives: list[dict[str, Any]] | None = None,
    values: list[dict[str, Any]] | None = None,
) -> Path:
    """Skeleton committed at SKELETON_DATE, then filled and committed at FILL_DATE."""
    fx.build_root(root, intent=_skeleton())
    _commit(root, SKELETON_DATE, "skeleton")
    fx.build_root(
        root, intent=fx.intent_doc(fx.outcome()), objectives=objectives, values=values, git=False
    )
    _commit(root, FILL_DATE, "fill")
    return root


def _span(stage: str, event: str, ts: str) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "event": event,
            "stage": stage,
            "cwd": "/x",
            "base_root": "/x",
            "git_branch": None,
            "task_slug": None,
            "ts": ts,
            "session_id": None,
        }
    )


def _spans(root: Path, lines: list[str]) -> None:
    path = root / ".claude" / "observability" / "stage-spans.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gap(root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "world", "gap", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return fx.stdout_json(proc)


# ── AC-002 ───────────────────────────────────────────────────────────────────


def test_ac_002_gap_reports_the_withdrawal_block(tmp_path: Path) -> None:
    o = fx.outcome()
    closed = fx.objective(
        "OBJ-DONE", state="closed", observed="met", note="done", closed_at="2026-09-11T00:00:00Z"
    )
    fired = fx.objective("OBJ-FIRE", revisit_when={"outcome": o["id"], "op": "<", "value": 10})
    value = {
        "outcome_id": o["id"],
        "value": 5,
        "observed_at": "2026-09-11T00:00:00Z",
        "evidence": "fixture",
        "definition_hash": fx.definition_hash(o),
    }
    root = _filled_repo(tmp_path, objectives=[closed, fired], values=[value])
    _spans(
        root,
        [
            _span("hm:wrapup", "start", "2026-09-09T00:00:00Z"),  # before fill
            _span("hm:wrapup", "start", "2026-09-10T02:59:59Z"),  # before fill (UTC)
            _span("hm:wrapup", "start", "2026-09-10T03:00:01Z"),
            _span("hm:wrapup", "end", "2026-09-10T03:30:00Z"),  # end events never count
            _span("hm:wrapup", "start", "2026-09-12T00:00:00+09:00"),
            _span("hm:plan", "start", "2026-09-13T00:00:00Z"),  # another stage
            _span("hm:wrapup", "start", "2026-09-15T00:00:00Z"),
            _span("hm:wrapup", "start", "2026-09-16T00:00:00"),  # naive ts: skipped
            "{not json",
        ],
    )

    out = _gap(root)
    w = out["withdrawal"]
    assert set(w) == _KEYS
    assert w["filled_at"] == FILL_ISO
    assert w["wrapups_since_fill"] == 3
    assert w["objectives_observed"] == 1
    assert w["revisit_candidates_now"] == 1
    assert w["due"] is False
    assert w["reason"] == "ok"

    status = fx.stdout_json(fx.run_cli(["status", "--json"], cwd=root))
    assert "withdrawal" not in status


def test_ac_002_due_fires_on_a_real_count(tmp_path: Path) -> None:
    """Positive control for AC-002: the same reader reports `due` when the criterion holds."""
    root = _filled_repo(tmp_path)
    _spans(root, [_span("hm:wrapup", "start", f"2026-09-{d:02d}T00:00:00Z") for d in range(11, 21)])
    w = _gap(root)["withdrawal"]
    assert (w["wrapups_since_fill"], w["due"], w["reason"]) == (10, True, "ok")


# ── AC-003 ───────────────────────────────────────────────────────────────────

_DUE_ROWS = load_golden_table(_SPEC, "AC-003")


@pytest.mark.parametrize(
    "row", _DUE_ROWS, ids=[f"{i}-{r.note or 'row'}" for i, r in enumerate(_DUE_ROWS)]
)
def test_ac_003_due_is_the_criterion_exactly(row: GoldenRow) -> None:
    i = row.input
    expected = row.expected == "due=true"
    got = world.withdrawal_due(
        i["wrapups_since_fill"], i["objectives_observed"], i["revisit_candidates_now"]
    )
    assert got is expected


# ── AC-004 ───────────────────────────────────────────────────────────────────


def _no_path_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent / "no-such-dir")
    return env


def _b_not_filled(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp, intent=_skeleton())
    _commit(tmp, SKELETON_DATE, "skeleton")
    return tmp, None


def _b_git_missing(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    root = _filled_repo(tmp)
    _spans(root, [_span("hm:wrapup", "start", "2026-09-11T00:00:00Z")])
    return root, _no_path_env()


def _b_not_a_repo(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp, intent=fx.intent_doc(fx.outcome()), git=False)
    _spans(tmp, [_span("hm:wrapup", "start", "2026-09-11T00:00:00Z")])
    return tmp, None


def _b_shallow(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    src = _filled_repo(tmp / "src")
    _git(src, "commit", "-q", "--allow-empty", "-m", "later", date="2026-09-12T00:00:00Z")
    dst = tmp / "dst"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{src}", str(dst)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    _spans(dst, [_span("hm:wrapup", "start", "2026-09-13T00:00:00Z")])
    return dst, None


def _b_deleted_then_filled(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp, intent=_skeleton())
    _commit(tmp, SKELETON_DATE, "skeleton")
    (tmp / ".claude" / "intent.yaml").unlink()
    _commit(tmp, "2026-09-05T00:00:00Z", "delete")
    fx.build_root(tmp, intent=fx.intent_doc(fx.outcome()), git=False)
    _commit(tmp, FILL_DATE, "fill")
    _spans(tmp, [_span("hm:wrapup", "start", "2026-09-09T00:00:00Z")])
    return tmp, None


def _b_fill_uncommitted(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp, intent=_skeleton())
    _commit(tmp, SKELETON_DATE, "skeleton")
    fx.dump(tmp / ".claude" / "intent.yaml", fx.intent_doc(fx.outcome()))
    _spans(tmp, [_span("hm:wrapup", "start", "2026-09-11T00:00:00Z")])
    return tmp, None


def _b_no_spans(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    return _filled_repo(tmp), None


def _b_spans_dir(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    root = _filled_repo(tmp)
    (root / ".claude" / "observability" / "stage-spans.jsonl").mkdir(parents=True)
    return root, None


def _b_no_wrapup(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    root = _filled_repo(tmp)
    _spans(
        root,
        [
            _span("hm:plan", "start", "2026-09-11T00:00:00Z"),
            _span("hm:plan", "end", "2026-09-11T01:00:00Z"),
        ],
    )
    return root, None


def _b_invalid(tmp: Path) -> tuple[Path, dict[str, str] | None]:
    fx.build_root(tmp)
    (tmp / ".claude" / "intent.yaml").write_text(
        "schema_version: 1\nmission: x\noutcomes: 5\n", encoding="utf-8"
    )
    return tmp, None


_BUILDERS: dict[str, Callable[[Path], tuple[Path, dict[str, str] | None]]] = {
    "not_filled_in skeleton, committed": _b_not_filled,
    "filled, git binary missing (FileNotFoundError)": _b_git_missing,
    "filled, checkout is not a git repository": _b_not_a_repo,
    "filled and committed in a shallow clone": _b_shallow,
    (
        "history contains a commit that deleted intent.yaml before it was re-added filled"
    ): _b_deleted_then_filled,
    "skeleton committed, filled only in the working tree": _b_fill_uncommitted,
    "filled and committed, no stage-spans.jsonl at the base root": _b_no_spans,
    "filled and committed, a directory at the stage-spans path": _b_spans_dir,
    "filled and committed, stage-spans has only non-wrapup events": _b_no_wrapup,
    "intent.yaml invalid": _b_invalid,
}
_ABSENT_ROWS = load_golden_table(_SPEC, "AC-004")


def _parse_expected(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for token in text.split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k] = v
    return out


def test_ac_004_every_table_row_has_a_fixture() -> None:
    """Positive control: a table row with no builder would be silently untested."""
    assert {r.input["world"] for r in _ABSENT_ROWS} == set(_BUILDERS)


@pytest.mark.parametrize("row", _ABSENT_ROWS, ids=[r.input["world"] for r in _ABSENT_ROWS])
def test_ac_004_unmeasurable_counts_are_null_with_reason(tmp_path: Path, row: GoldenRow) -> None:
    root, env = _BUILDERS[row.input["world"]](tmp_path)
    exp = _parse_expected(str(row.expected))
    out = _gap(root, env)
    if exp.get("state") == "invalid":
        assert out["state"] == "invalid"
        assert "withdrawal" not in out
        return
    w = out["withdrawal"]
    assert set(w) == _KEYS
    assert w["reason"] == exp["reason"]
    for key in ("filled_at", "wrapups_since_fill"):
        if key not in exp:
            continue
        want = exp[key]
        if want == "None":
            assert w[key] is None, (key, w)
        elif want.startswith("<"):
            assert w[key] == FILL_ISO, (key, w)
        else:
            assert w[key] == yaml.safe_load(want), (key, w)
    if "due" in exp:
        assert w["due"] is (exp["due"] == "true")
