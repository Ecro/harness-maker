"""Phase 4 — ledger + JSONL adjudication store + CLI contract (SPEC AC-007, ADR-005/006/007)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from harness_maker.delivery_metrics import main
from tests.unit._dm_git import ANCHOR, DMRepo

_NOW = ANCHOR.isoformat()


def _ambiguous_repo(tmp_path: Path) -> Path:
    """v1.0.0 at day 6 + tail `fix:` 2.4h later → exactly one candidate."""
    r = DMRepo(tmp_path / "ambig")
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: alpha", days_ago=6)
    r.tag("v1.0.0", days_ago=6)
    r.commit("fix: subtle regression", days_ago=5.9)
    return r.root


def _ledger_rows(root: Path) -> list[dict[str, object]]:
    ledger = root / ".claude/observability/delivery-metrics.jsonl"
    if not ledger.is_file():
        return []
    rows = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_ledger_append_and_adjudication_reuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-007: adjudicate once → verdict row persisted; a second run on
    unchanged history re-uses it (zero new adjudication requests) and appends
    a NEW snapshot row. Machine predicate: adjudication_requests(second_run) == 0."""
    root = _ambiguous_repo(tmp_path)

    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    first = json.loads(capsys.readouterr().out)
    assert len(first["candidates"]) == 1
    cand = first["candidates"][0]

    assert (
        main(
            [
                "adjudicate",
                "--root",
                str(root),
                "--commit",
                cand["commit_sha"],
                "--release",
                cand["release_ref"],
                "--verdict",
                "routine",
                "--reason",
                "scheduled cleanup, unrelated to the release",
                "--now",
                _NOW,
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["compute", "--root", str(root), "--now", _NOW]) == 0
    snap1 = json.loads(capsys.readouterr().out)
    assert snap1["event"] == "snapshot"
    assert snap1["pending_adjudications"] == 0
    # ADR-005 nested snapshot schema: cfr {failed, total, unit, status, reason}.
    assert snap1["cfr"]["failed"] == 0
    assert snap1["cfr"]["total"] == 1
    assert snap1["cfr"]["unit"] == "tag"
    assert snap1["cfr"]["status"] == "ok"

    # Second run, unchanged history: candidates list is EMPTY (verdict reused).
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["candidates"] == []  # zero new adjudication requests

    assert main(["compute", "--root", str(root), "--now", _NOW]) == 0
    capsys.readouterr()

    rows = _ledger_rows(root)
    assert sum(1 for r in rows if r["event"] == "adjudication") == 1
    assert sum(1 for r in rows if r["event"] == "snapshot") == 2


def test_compute_fail_closed_on_pending_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-006: compute with unresolved candidates exits 3, lists them, and
    writes NO snapshot row (fail-closed)."""
    root = _ambiguous_repo(tmp_path)
    assert main(["compute", "--root", str(root), "--now", _NOW]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "pending_adjudications"
    assert len(out["candidates"]) == 1
    assert _ledger_rows(root) == []


def test_compute_assume_routine_is_explicit_and_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-006 headless path: --assume-routine computes with pending candidates
    treated as routine (no failure), records how many were assumed, and does
    NOT write verdict rows (a later interactive run can still adjudicate)."""
    root = _ambiguous_repo(tmp_path)
    assert main(["compute", "--root", str(root), "--now", _NOW, "--assume-routine"]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["cfr"]["failed"] == 0  # ADR-005 nested schema
    assert snap["pending_adjudications"] == 1  # assumed, surfaced — not hidden
    rows = _ledger_rows(root)
    assert sum(1 for r in rows if r["event"] == "adjudication") == 0
    assert sum(1 for r in rows if r["event"] == "snapshot") == 1


def test_adjudication_reason_truncated_row_under_pipe_buf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-005 byte-cap: an oversized reason is truncated deterministically and
    the serialized row stays <= 4096 bytes (single O_APPEND write)."""
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    cand = json.loads(capsys.readouterr().out)["candidates"][0]
    long_reason = "x" * 5000
    assert (
        main(
            [
                "adjudicate",
                "--root",
                str(root),
                "--commit",
                cand["commit_sha"],
                "--release",
                cand["release_ref"],
                "--verdict",
                "remediation",
                "--reason",
                long_reason,
                "--now",
                _NOW,
            ]
        )
        == 0
    )
    capsys.readouterr()
    ledger = root / ".claude/observability/delivery-metrics.jsonl"
    line = ledger.read_text(encoding="utf-8").splitlines()[0]
    assert len(line.encode("utf-8")) <= 4096
    row = json.loads(line)
    assert len(row["reason"]) <= 200


def test_cli_exit_4_outside_git_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert main(["compute", "--root", str(plain), "--now", _NOW]) == 4
    capsys.readouterr()


def test_git_subprocess_failure_maps_to_exit_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW re-review P2: a git subprocess OSError/TimeoutExpired (git binary
    missing, or a blame/log timeout on a huge repo) surfaces as the structured
    exit-4 error contract, never a raw traceback."""
    import subprocess as _sp

    root = _ambiguous_repo(tmp_path)

    def _boom(*_a: object, **_k: object) -> object:
        raise _sp.TimeoutExpired(cmd="git", timeout=60)

    monkeypatch.setattr("harness_maker.delivery_metrics.subprocess.run", _boom)
    assert main(["compute", "--root", str(root), "--now", _NOW]) == 4
    err = capsys.readouterr().err
    assert '"status": "error"' in err


def test_read_only_subcommands_never_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-009 (0.36.0 — no disabled state): the read-only subcommands
    `candidates` and `trend` never append a ledger row; only `compute`
    (and `adjudicate`) write. So the feature is inert until the user asks
    for a snapshot — there is nothing to gate on."""
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    capsys.readouterr()
    assert main(["trend", "--root", str(root)]) == 0
    capsys.readouterr()
    assert _ledger_rows(root) == []  # neither read-only command wrote anything


def test_legacy_enabled_key_still_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A 0.35.0-era harness.yaml carrying `delivery_metrics.enabled: false` no
    longer disables anything (the key was removed) — the command just runs,
    the stale key is dropped, tuning is honored."""
    root = _ambiguous_repo(tmp_path)
    cfg_dir = root / ".claude"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "harness.yaml").write_text(
        "preset: Side\nlocale: en\ntargets: [claude-code]\ndelivery_metrics:\n"
        "  enabled: false\n  tag_pattern: 'v*'\n",
        encoding="utf-8",
    )
    assert main(["compute", "--root", str(root), "--now", _NOW, "--assume-routine"]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["event"] == "snapshot"


def test_trend_lists_snapshots_newest_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two snapshots taken at different --now instants: trend must return the
    LATER one first — a raw-append (oldest-first) or shuffled ordering fails
    on the window_end comparison (test-reviewer R1: ordering must be asserted)."""
    root = _ambiguous_repo(tmp_path)
    earlier = (ANCHOR - timedelta(days=1)).isoformat()
    assert main(["compute", "--root", str(root), "--now", earlier, "--assume-routine"]) == 0
    capsys.readouterr()
    assert main(["compute", "--root", str(root), "--now", _NOW, "--assume-routine"]) == 0
    capsys.readouterr()
    assert main(["trend", "--root", str(root)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["snapshots"]) == 2
    assert all(s["event"] == "snapshot" for s in out["snapshots"])
    # Newest first: the ANCHOR-run row precedes the ANCHOR-1d row.
    assert out["snapshots"][0]["window_end"] > out["snapshots"][1]["window_end"]


def test_e2e_module_invocation_from_foreign_cwd(tmp_path: Path) -> None:
    """CLAUDE.md checkpoint 8: one real subprocess boundary case — the module
    entrypoint works from an unrelated cwd with --root."""
    root = _ambiguous_repo(tmp_path)
    foreign = tmp_path / "elsewhere"
    foreign.mkdir()
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "harness_maker.delivery_metrics",
            "candidates",
            "--root",
            str(root),
            "--now",
            _NOW,
        ],
        cwd=foreign,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert len(payload["candidates"]) == 1


def _adjudicate(root: Path, commit: str, release: str, *extra: str) -> int:
    return main(
        [
            "adjudicate",
            "--root",
            str(root),
            "--commit",
            commit,
            "--release",
            release,
            "--verdict",
            "remediation",
            "--reason",
            "repairs a regression the release shipped",
            "--now",
            _NOW,
            *extra,
        ]
    )


def test_abbreviated_commit_is_normalised_to_the_full_sha(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The verdict lookup is keyed by the FULL sha `git log` reports.

    `adjudicate` used to store the caller's string verbatim, so the abbreviated
    sha that `git log --oneline` hands you produced a row no candidate would ever
    look up: the verdict was written, `compute` kept exiting 3 on the candidate it
    had supposedly resolved, and nothing surfaced the mismatch. Asserting only
    that the row exists passes in that broken world — the assertion has to be that
    the SAME run then reaches `compute`.
    """
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    cand = json.loads(capsys.readouterr().out)["candidates"][0]
    full = str(cand["commit_sha"])

    assert _adjudicate(root, full[:8], str(cand["release_ref"])) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["commit_sha"] == full, "abbreviated sha stored verbatim"

    rows = [r for r in _ledger_rows(root) if r["event"] == "adjudication"]
    assert [r["commit_sha"] for r in rows] == [full]

    # The behavioural half: the verdict is now actually READ.
    assert main(["compute", "--root", str(root), "--now", _NOW]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["pending_adjudications"] == 0
    assert snap["cfr"]["failed"] == 1


def test_unresolvable_commit_is_rejected_not_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sha that is not a commit in this repo can never be looked up.

    Name the guard in the assertion: exit 4 alone is also what the candidate-pair gate
    returns, so `rc == 4` passes with `_resolve_commit_sha` deleted.
    """
    root = _ambiguous_repo(tmp_path)
    assert _adjudicate(root, "a" * 40, "v1.0.0") == 4
    err = json.loads(capsys.readouterr().err)
    assert err["status"] == "error"
    assert "does not resolve to a commit" in err["error"], err
    assert not [r for r in _ledger_rows(root) if r["event"] == "adjudication"]


def test_an_overlong_release_ref_is_rejected_not_silently_truncated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ledger truncates `release_ref` to fit PIPE_BUF; the gate compares it whole.

    A ref past that cap would clear the gate and then be STORED under a different key —
    the same write-under-one-key/read-under-another failure this gate exists to close,
    reintroduced one layer down.
    """
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    cand = json.loads(capsys.readouterr().out)["candidates"][0]

    assert _adjudicate(root, str(cand["commit_sha"]), "v" + "9" * 300) == 4
    err = json.loads(capsys.readouterr().err)
    assert "never read" in err["error"], err
    assert not [r for r in _ledger_rows(root) if r["event"] == "adjudication"]


def test_pair_that_is_not_a_pending_candidate_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real sha with the wrong `--release` lands in the same dead end.

    Normalising only the sha would close the instance and leave the class open.
    """
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    cand = json.loads(capsys.readouterr().out)["candidates"][0]

    assert _adjudicate(root, str(cand["commit_sha"]), "v9.9.9") == 4
    err = json.loads(capsys.readouterr().err)
    assert "never read" in err["error"]
    assert not [r for r in _ledger_rows(root) if r["event"] == "adjudication"]

    # ...and --force is the documented escape hatch, so the gate is not a wall.
    assert _adjudicate(root, str(cand["commit_sha"]), "v9.9.9", "--force") == 0


def test_re_adjudicating_an_already_recorded_pair_is_allowed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Changing a verdict must not need --force: once recorded, the pair leaves
    the pending list, so a naive membership check would lock the verdict in.

    Discriminating detail: the FIRST adjudication is made with an abbreviated sha. That
    forces the second call's `store.get` short-circuit to be reached via the normalised
    key — with normalisation removed, the first row lands under the abbreviation, the
    pair is neither recorded nor pending, and the second call is rejected. Passing a
    full sha both times (as this test first did) succeeds against the pre-fix code too.
    """
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    cand = json.loads(capsys.readouterr().out)["candidates"][0]
    sha, ref = str(cand["commit_sha"]), str(cand["release_ref"])

    assert _adjudicate(root, sha[:9], ref) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "adjudicate",
                "--root",
                str(root),
                "--commit",
                sha,
                "--release",
                ref,
                "--verdict",
                "routine",
                "--reason",
                "on reflection this was scheduled work",
                "--now",
                _NOW,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["compute", "--root", str(root), "--now", _NOW]) == 0
    assert json.loads(capsys.readouterr().out)["cfr"]["failed"] == 0
