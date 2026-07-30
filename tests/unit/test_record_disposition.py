"""Per-finding disposition rows + the oracle_result cap.

PLAN-second-opinion-acceptance-gate ADR-005 / ADR-006 / ADR-009.

Three defects this module exists to keep closed, each of which shipped or was designed once:

1. **cwd instead of base root.** `codex_ledger.main()` wrote to `Path.cwd()`, so rows emitted
   from inside `.worktrees/<slug>/` landed in a gitignored path that `task-land` destroyed.
   `test_row_lands_under_base_root_not_cwd` proves the new entrypoint delegates to
   `resolve_base_root` — it monkeypatches that resolver, so a regression to cwd fails even
   though no git worktree is involved.
2. **silent row loss to length.** `oracle_result` is `max_length=200` under
   `strict=True, extra="forbid"`, and the invoker's row emission swallows exceptions by
   contract — so an over-length verdict+evidence string loses the WHOLE row with no
   diagnostic. The cap is applied before validation and truncation is visible.
3. **silent no-op.** A failure to record must not fail the review (an unwritten calibration
   row is not worth a red review) but must not be invisible either, or a successful review
   is indistinguishable from one that recorded nothing.

`test_existing_invoke_argv_still_parses` is the byte-unchanged guard: `--record-disposition`
is a separate flag mode, NOT an argparse subcommand, precisely because subparsers would
break the four already-rendered call sites that pass no subcommand token.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker import codex_ledger, second_opinion_invoke
from harness_maker.codex_ledger import LEDGER_FILENAME, ORACLE_RESULT_MAX, cap_oracle_result

_DISPOSITIONS = [
    {
        "id": "abc123def4567890",
        "model": "codex",
        "disposition": "accepted",
        "oracle_result": "KEEP: pytest tests/x.py::test_y failed as predicted",
    },
    {
        "id": "fed321cba0987654",
        "model": "antigravity",
        "disposition": "rejected",
        "oracle_result": "REFUTE: the guard already runs before the write",
    },
]


def _payload(dispositions: list[dict[str, object]]) -> str:
    return json.dumps({"dispositions": dispositions})


def _rows(base: Path) -> list[dict[str, object]]:
    path = base / codex_ledger.DEFAULT_OBSERVABILITY_DIR / LEDGER_FILENAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# ── the deterministic cap (ADR-005) ────────────────────────────────────────────────────


def test_cap_leaves_a_short_value_untouched() -> None:
    out = cap_oracle_result("KEEP", "short evidence")
    assert out == "KEEP: short evidence"
    assert len(out) <= ORACLE_RESULT_MAX


def test_cap_truncates_visibly_and_fits_the_field() -> None:
    """The marker matters: a silently-clipped value reads as complete evidence."""
    out = cap_oracle_result("REFUTE", "x" * 500)
    assert len(out) <= ORACLE_RESULT_MAX
    assert out.startswith("REFUTE: ")
    assert out.endswith("…"), f"truncation is invisible: {out[-20:]!r}"


def test_cap_handles_absent_evidence() -> None:
    assert cap_oracle_result("unresolved", None) == "unresolved"


def test_cap_is_deterministic() -> None:
    assert cap_oracle_result("KEEP", "y" * 400) == cap_oracle_result("KEEP", "y" * 400)


# ── the entrypoint (ADR-009) ───────────────────────────────────────────────────────────


def test_row_lands_under_base_root_not_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact regression CLAUDE.md documents: writing relative to cwd loses every row at
    `task-land` when the stage runs inside a worktree."""
    base = tmp_path / "base"
    cwd = tmp_path / "base" / ".worktrees" / "slug"
    cwd.mkdir(parents=True)
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(cwd)

    payload = tmp_path / "d.json"
    payload.write_text(_payload(_DISPOSITIONS), encoding="utf-8")

    rc = second_opinion_invoke.main(
        [
            "--record-disposition",
            "--disposition-file",
            str(payload),
            "--slug",
            "s",
            "--stage",
            "review",
        ]
    )
    assert rc == 0
    assert len(_rows(base)) == 2, "rows did not land under the base root"
    assert not (cwd / ".claude").exists(), "rows leaked into the worktree"


def test_finding_ref_is_the_supplied_id() -> None:
    """`finding_ref` is the join key back to the REVIEW frozen set; a re-derived value
    joins to nothing."""
    row = codex_ledger.record_from_dict(
        {
            "slug": "s",
            "stage": "review",
            "model": "codex",
            "finding_ref": _DISPOSITIONS[0]["id"],
            "disposition": "accepted",
            "status": "invoked",
        }
    )
    assert row.finding_ref == _DISPOSITIONS[0]["id"]


def test_per_finding_and_per_call_rows_are_distinguishable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both kinds carry `status: invoked`; only `finding_ref == "n/a"` separates them, and
    every future aggregation depends on that discriminator."""
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(base)
    codex_ledger.emit(
        codex_ledger.record_from_dict(
            {
                "slug": "s",
                "stage": "review",
                "model": "codex",
                "finding_ref": "n/a",
                "disposition": "unresolved",
                "status": "invoked",
            }
        ),
        project_root=base,
    )
    payload = tmp_path / "d.json"
    payload.write_text(_payload(_DISPOSITIONS), encoding="utf-8")
    second_opinion_invoke.main(
        [
            "--record-disposition",
            "--disposition-file",
            str(payload),
            "--slug",
            "s",
            "--stage",
            "review",
        ]
    )
    rows = _rows(base)
    per_call = [r for r in rows if r["finding_ref"] == "n/a"]
    per_finding = [r for r in rows if r["finding_ref"] != "n/a"]
    assert len(per_call) == 1
    assert len(per_finding) == 2


def test_absent_evidence_still_records_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence-less findings keep their verdict in `oracle_result`.

    The caller used to short-circuit to `None` whenever evidence was falsy, which skipped
    `cap_oracle_result` — a function whose no-evidence branch returns the bare verdict and was
    therefore unreachable from its only caller. The row then said nothing at all about an
    `unresolved` finding. Storing the verdict makes the row self-describing without a
    cross-reference to `disposition`.

    `oracle_result is None` remains correct — and asserted — for per-call, skip and failure
    rows (`test_per_finding_and_per_call_rows_are_distinguishable` covers the per-call kind);
    this test pins only the per-finding path."""
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(base)
    payload = tmp_path / "d.json"
    payload.write_text(
        _payload(
            [{"id": "aaa", "model": "codex", "disposition": "unresolved", "oracle_result": None}]
        ),
        encoding="utf-8",
    )
    assert (
        second_opinion_invoke.main(
            [
                "--record-disposition",
                "--disposition-file",
                str(payload),
                "--slug",
                "s",
                "--stage",
                "review",
            ]
        )
        == 0
    )
    assert _rows(base)[0]["oracle_result"] == "unresolved"


def test_over_length_oracle_result_is_capped_not_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defect 2: without the cap the ValidationError is swallowed and the row vanishes."""
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(base)
    payload = tmp_path / "d.json"
    payload.write_text(
        _payload(
            [{"id": "bbb", "model": "codex", "disposition": "rejected", "oracle_result": "z" * 900}]
        ),
        encoding="utf-8",
    )
    assert (
        second_opinion_invoke.main(
            [
                "--record-disposition",
                "--disposition-file",
                str(payload),
                "--slug",
                "s",
                "--stage",
                "review",
            ]
        )
        == 0
    )
    rows = _rows(base)
    assert len(rows) == 1, "the row was dropped instead of capped"
    assert len(str(rows[0]["oracle_result"])) <= ORACLE_RESULT_MAX


def test_unreadable_payload_exits_zero_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Defect 3: warn-and-proceed for the verdict, but never a silent no-op."""
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(base)
    rc = second_opinion_invoke.main(
        [
            "--record-disposition",
            "--disposition-file",
            str(tmp_path / "missing.json"),
            "--slug",
            "s",
            "--stage",
            "review",
        ]
    )
    assert rc == 0, "a failed calibration write must not fail the review"
    assert "disposition rows NOT recorded" in capsys.readouterr().err
    assert _rows(base) == []


def test_malformed_json_exits_zero_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(base)
    payload = tmp_path / "d.json"
    payload.write_text("{not json", encoding="utf-8")
    assert (
        second_opinion_invoke.main(
            [
                "--record-disposition",
                "--disposition-file",
                str(payload),
                "--slug",
                "s",
                "--stage",
                "review",
            ]
        )
        == 0
    )
    assert "disposition rows NOT recorded" in capsys.readouterr().err


def test_argparse_error_still_exits_non_zero(tmp_path: Path) -> None:
    """Only argparse owns the non-zero exit — everything else degrades gracefully."""
    with pytest.raises(SystemExit) as exc:
        second_opinion_invoke.main(["--record-disposition", "--slug", "s", "--stage", "review"])
    assert exc.value.code != 0


def test_one_bad_entry_does_not_discard_the_valid_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """REVIEW C3/M5. An earlier revision returned on the first bad entry, so rows already
    appended stayed committed while every LATER valid row was dropped — a prefix that reads as
    a complete batch and skews the acceptance-rate denominator the ledger exists to produce.

    Three entries, the middle one missing `disposition`: the two good ones must land, and the
    failure must be named on stderr with a count rather than swallowed."""
    base = tmp_path / "base"
    base.mkdir()
    monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)
    monkeypatch.chdir(base)
    payload = tmp_path / "d.json"
    payload.write_text(
        _payload(
            [
                {"id": "good1", "model": "codex", "disposition": "accepted"},
                {"id": "bad", "model": "codex"},
                {"id": "good2", "model": "antigravity", "disposition": "rejected"},
            ]
        ),
        encoding="utf-8",
    )
    rc = second_opinion_invoke.main(
        [
            "--record-disposition",
            "--disposition-file",
            str(payload),
            "--slug",
            "s",
            "--stage",
            "review",
        ]
    )
    assert rc == 0
    refs = {r["finding_ref"] for r in _rows(base)}
    assert refs == {"good1", "good2"}, f"a valid row was discarded by a sibling's failure: {refs}"
    err = capsys.readouterr().err
    assert "2/3 rows recorded" in err
    assert "bad" in err


def test_existing_invoke_argv_still_parses() -> None:
    """The four already-rendered call sites pass no subcommand token. If
    `--record-disposition` had been an argparse subcommand, all four would break with
    'invalid choice' — this is the guard that keeps the flag-mode decision honest."""
    args = second_opinion_invoke._build_parser().parse_args(
        ["--model", "codex", "--prompt-file", "/tmp/p.txt", "--slug", "s", "--stage", "review"]
    )
    assert args.model == "codex"
    smoke = second_opinion_invoke._build_parser().parse_args(
        ["--model", "antigravity", "--smoke", "--slug", "s", "--stage", "health"]
    )
    assert smoke.smoke is True
