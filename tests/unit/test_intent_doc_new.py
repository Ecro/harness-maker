"""AC-006 — `hm world objective new <ID>` writes a loadable INTENT skeleton (ADR-004).

The verb is exercised through the shipped CLI entrypoint (seam rule) and judged against the
loader's acceptance plus the Playbook's five section names, never against the verb's own output.

AC-003 (SPEC-objective-gap-proposal) — Phase A.4 note: four AC-003 tests pass before the
`--from-proposal` implementation exists, deliberately. `..._a_call_without_proposal_flags_...`
is the negative invariant of ADR-003 (no flag → record, no event; goes red if the event is ever
emitted unconditionally), and the three refusal parametrizations (`candidates-without-flag`,
`too-few-candidates`, `flag-without-candidates`) assert the observable — non-zero exit, no
file, no row — that argparse's unknown-flag rejection satisfies today and the flag-combination
rule must keep satisfying once the flags exist. Their RED positive siblings are
`..._prefills_rejected_and_emits_one_event`, `..._two_accepted_candidates_...`,
`..._a_failed_ledger_append_...` and `declined-without-flag` (whose message assertion names the
rule, not argparse).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import world
from tests.unit import world_fixture as fx

_PLAYBOOK_HEADINGS = (
    "## Problem",
    "## Proposed outcome",
    "## Affected users and systems",
    "## Constraints",
    "## Open questions",
)


def _new(root: Path, oid: str, *extra: str) -> tuple[int, str, str]:
    proc = fx.run_cli(
        [
            "--root",
            str(root),
            "objective",
            "new",
            oid,
            "--title",
            "One-round onboarding",
            "--hypothesis",
            "shorter onboarding keeps users",
            "--scope",
            "cut the interview to one round",
            "--scope",
            "keep the locale question",
            "--outcome",
            "onboarding_minutes",
            *extra,
        ],
        cwd=root,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_ac_006_objective_new_writes_a_loadable_skeleton(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rc, out, err = _new(root, "OBJ-9", "--non-scope", "rewrite the renderer", "--json")
    assert rc == 0, err
    path = root / "work-docs" / "INTENT-OBJ-9.md"
    assert path.exists()
    w = world.load_world(root)
    assert "OBJ-9" not in w.broken
    rec = w.objectives["OBJ-9"]
    assert rec["state"] == "proposed"
    assert rec["approval"] is None
    assert rec["schema_version"] == 1
    assert rec["scope"] == ["cut the interview to one round", "keep the locale question"]
    assert rec["non_scope"] == ["rewrite the renderer"]
    assert rec["outcome_id"] == "onboarding_minutes"
    assert rec["created_at"].endswith("Z")
    body = w.bodies["OBJ-9"].decode("utf-8")
    assert all(h in body for h in _PLAYBOOK_HEADINGS)
    assert (
        fx.stdout_json(
            fx.run_cli(["--root", str(root), "objective", "show", "OBJ-9", "--json"], cwd=root)
        )["id"]
        == "OBJ-9"
    )
    assert "INTENT-OBJ-9.md" in out


def test_ac_006_a_second_new_is_refused_and_the_file_is_untouched(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    assert _new(root, "OBJ-9")[0] == 0
    path = root / "work-docs" / "INTENT-OBJ-9.md"
    path.write_bytes(path.read_bytes() + b"\nhand-written prose\n")
    before = path.read_bytes()
    rc, out, err = _new(root, "OBJ-9")
    assert rc != 0
    assert "OBJ-9" in out + err  # `main()` emits WorldError via _emit (stdout), rc 1
    assert path.read_bytes() == before


def test_ac_006_a_bad_id_is_refused_naming_the_rule_before_any_write(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rc, out, err = _new(root, "obj-9")
    assert rc != 0
    assert "[A-Z0-9-]+" in out + err
    assert (
        not list((root / "work-docs").glob("INTENT-*")) if (root / "work-docs").exists() else True
    )


def test_ac_006_an_unknown_outcome_is_refused(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    proc = fx.run_cli(
        [
            "--root",
            str(root),
            "objective",
            "new",
            "OBJ-9",
            "--title",
            "t",
            "--hypothesis",
            "h",
            "--scope",
            "s",
            "--outcome",
            "ghost",
        ],
        cwd=root,
    )
    assert proc.returncode != 0
    assert "ghost" in proc.stdout + proc.stderr
    assert not (root / "work-docs" / "INTENT-OBJ-9.md").exists()


def test_ac_006_the_python_api_matches_the_cli(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rec = world.new_objective(
        root,
        "OBJ-8",
        title="t",
        hypothesis="h",
        scope=["s"],
        outcome_id="onboarding_minutes",
    )
    assert rec["id"] == "OBJ-8"
    assert world.load_world(root).objectives["OBJ-8"] == rec


# ── AC-003 (SPEC-objective-gap-proposal) — `--from-proposal` ──────────────────
#
# The expected ledger line is written by hand from SPEC S3 (objective / candidates / accepted);
# the record is re-read through `load_world`, never from the verb's return value. The base/worktree
# split is exercised with a LINKED worktree of a throwaway base (never a before/after count on this
# checkout's live ledger — the shape `test_ledger_isolation.py` rejects for a shared append-only
# file): the row must land under that base and the record in the worktree.


def _ledger_rows(root: Path) -> list[dict[str, Any]]:
    p = root / ".claude" / "observability" / "auto-advance.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _proposal_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {k: v for k, v in r.items() if k != "ts"}
        for r in _ledger_rows(root)
        if r.get("event") == "objective_proposed"
    ]


def test_ac_003_from_proposal_prefills_rejected_and_emits_one_event(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path)
    rc, out, err = _new(
        root,
        "OBJ-9",
        "--from-proposal",
        "--candidates",
        "3",
        "--declined",
        "P1 title",
        "--declined",
        "P3 title",
        "--json",
    )
    assert rc == 0, out + err
    rec = world.load_world(root).objectives["OBJ-9"]
    assert rec["state"] == "proposed"
    assert rec["rejected"] == ["P1 title", "P3 title"]
    assert _proposal_rows(root) == [
        {"event": "objective_proposed", "objective": "OBJ-9", "candidates": 3, "accepted": 1}
    ]


def test_ac_003_a_call_without_proposal_flags_writes_the_record_and_no_event(
    tmp_path: Path,
) -> None:
    root = fx.build_root(tmp_path)
    assert _new(root, "OBJ-9")[0] == 0
    assert world.load_world(root).objectives["OBJ-9"]["rejected"] == []
    assert _ledger_rows(root) == []


@pytest.mark.parametrize(
    "extra",
    [
        ["--candidates", "2"],
        ["--declined", "P1 title"],
        [
            "--from-proposal",
            "--candidates",
            "1",
            "--declined",
            "P1 title",
        ],  # candidates < declined+1
        ["--from-proposal"],  # candidates required with the flag
    ],
    ids=[
        "candidates-without-flag",
        "declined-without-flag",
        "too-few-candidates",
        "flag-without-candidates",
    ],
)
def test_ac_003_bad_proposal_flag_combinations_are_refused_before_any_write(
    tmp_path: Path, extra: list[str]
) -> None:
    root = fx.build_root(tmp_path)
    rc, out, err = _new(root, "OBJ-9", *extra)
    assert rc != 0
    assert "from-proposal" in out + err or "candidates" in out + err
    assert not (root / "work-docs" / "INTENT-OBJ-9.md").exists()
    assert _ledger_rows(root) == []


def test_ac_003_two_accepted_candidates_share_the_declined_list_and_emit_two_events(
    tmp_path: Path,
) -> None:
    root = fx.build_root(tmp_path)
    declined = ["--declined", "P3 title"]
    assert _new(root, "OBJ-1", "--from-proposal", "--candidates", "3", *declined)[0] == 0
    assert _new(root, "OBJ-2", "--from-proposal", "--candidates", "3", *declined)[0] == 0
    w = world.load_world(root)
    assert w.objectives["OBJ-1"]["rejected"] == ["P3 title"]
    assert w.objectives["OBJ-2"]["rejected"] == ["P3 title"]
    rows = _proposal_rows(root)
    assert [r["objective"] for r in rows] == ["OBJ-1", "OBJ-2"]
    assert all(r["candidates"] == 3 and r["accepted"] == 1 for r in rows)


def test_ac_003_a_failed_ledger_append_keeps_the_record_and_warns(tmp_path: Path) -> None:
    """Fault injection at the filesystem, through the shipped CLI: the ledger path is a
    directory, so the append raises after the record write. The verb must exit 0, keep the
    record, and say on stderr that the row was NOT recorded (never retry — the id now exists)."""
    root = fx.build_root(tmp_path)
    ledger = root / ".claude" / "observability" / "auto-advance.jsonl"
    ledger.mkdir(parents=True)
    rc, out, err = _new(
        root, "OBJ-7", "--from-proposal", "--candidates", "2", "--declined", "P2", "--json"
    )
    assert rc == 0, out + err
    rec = world.load_world(root).objectives["OBJ-7"]
    assert rec["rejected"] == ["P2"]
    assert (root / "work-docs" / "INTENT-OBJ-7.md").exists()
    assert "objective_proposed NOT recorded" in err
    assert ledger.is_dir()  # nothing was written around the fault


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def test_ac_003_a_linked_worktree_writes_the_row_at_base_and_the_record_in_the_worktree(
    tmp_path: Path,
) -> None:
    """`resolve_base_root` only diverges from `root` inside a linked worktree, so this is the one
    fixture that exercises the base/worktree split AC-003 names (ADR-003/004)."""
    base = fx.build_root(tmp_path / "base")
    _git(base, "add", "-A")
    _git(base, "commit", "-q", "-m", "fixture")
    wt = base / ".worktrees" / "t"
    _git(base, "worktree", "add", "-q", "-b", "hm/t", str(wt))
    rc, out, err = _new(wt, "OBJ-5", "--from-proposal", "--candidates", "1", "--json")
    assert rc == 0, out + err
    assert (wt / "work-docs" / "INTENT-OBJ-5.md").exists()
    assert not (base / "work-docs" / "INTENT-OBJ-5.md").exists()
    assert _proposal_rows(base) == [
        {"event": "objective_proposed", "objective": "OBJ-5", "candidates": 1, "accepted": 1}
    ]
    assert _ledger_rows(wt) == []
