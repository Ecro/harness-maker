"""Phase 1 — second-opinion calibration ledger (PLAN-crossmodel-codex-gaps ADR-005,
generalized to multi-vendor by PLAN-second-opinion-multi-model ADR-005).

Model-field default + legacy-forward-copy behavior are covered by the sibling
``test_second_opinion_ledger.py`` — this file keeps the remaining record-shape,
enum, CLI, and schema-parity assertions that file doesn't duplicate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from harness_maker import codex_ledger


def _valid_invoked() -> dict[str, object]:
    return {
        "ts": "2026-06-07T07:45:00Z",
        "slug": "crossmodel-codex-gaps",
        "stage": "review",
        "finding_ref": "src/foo.py:42",
        "disposition": "accepted",
        "status": "invoked",
        "skip_reason": None,
        "oracle_result": None,
        "later_regression_link": None,
    }


def _valid_skipped() -> dict[str, object]:
    return {
        "ts": "2026-06-07T07:45:00Z",
        "slug": "crossmodel-codex-gaps",
        "stage": "plan",
        "finding_ref": "n/a",
        "disposition": "unresolved",
        "status": "skipped",
        "skip_reason": "codex exec Bash denied by sandbox",
        "oracle_result": None,
        "later_regression_link": None,
    }


def test_emit_appends_valid_row(tmp_path: Path) -> None:
    rec = codex_ledger.record_from_dict(_valid_invoked(), auto_timestamp=False)
    path = codex_ledger.emit(rec, project_root=tmp_path)
    assert path.name == "second-opinion.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["disposition"] == "accepted"
    assert row["status"] == "invoked"
    assert row["stage"] == "review"


def test_emit_is_append_only(tmp_path: Path) -> None:
    rec = codex_ledger.record_from_dict(_valid_invoked(), auto_timestamp=False)
    codex_ledger.emit(rec, project_root=tmp_path)
    codex_ledger.emit(rec, project_root=tmp_path)
    path = tmp_path / ".claude" / "observability" / "second-opinion.jsonl"
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_status_enum_rejects_unknown() -> None:
    bad = _valid_invoked()
    bad["status"] = "maybe"
    with pytest.raises(ValidationError):
        codex_ledger.record_from_dict(bad, auto_timestamp=False)


def test_disposition_enum_rejects_unknown() -> None:
    bad = _valid_invoked()
    bad["disposition"] = "ignored"
    with pytest.raises(ValidationError):
        codex_ledger.record_from_dict(bad, auto_timestamp=False)


def test_disposition_unresolved_is_valid() -> None:
    rec = codex_ledger.record_from_dict(_valid_skipped(), auto_timestamp=False)
    assert rec.disposition == "unresolved"


def test_stage_enum_rejects_unknown() -> None:
    bad = _valid_invoked()
    bad["stage"] = "wrapup"
    with pytest.raises(ValidationError):
        codex_ledger.record_from_dict(bad, auto_timestamp=False)


def test_nullable_optionals_default_none() -> None:
    minimal = {
        "ts": "2026-06-07T07:45:00Z",
        "slug": "x",
        "stage": "review",
        "finding_ref": "a.py:1",
        "disposition": "rejected",
        "status": "invoked",
    }
    rec = codex_ledger.record_from_dict(minimal, auto_timestamp=False)
    assert rec.skip_reason is None
    assert rec.oracle_result is None
    assert rec.later_regression_link is None


def test_record_from_dict_auto_timestamp() -> None:
    data = _valid_invoked()
    del data["ts"]
    rec = codex_ledger.record_from_dict(data, auto_timestamp=True)
    assert rec.ts.endswith("Z")


def test_emit_rejects_observability_dir_escaping_root(tmp_path: Path) -> None:
    rec = codex_ledger.record_from_dict(_valid_invoked(), auto_timestamp=False)
    outside = tmp_path.parent / "escape"
    with pytest.raises(ValueError, match="escapes project_root"):
        codex_ledger.emit(rec, project_root=tmp_path, observability_dir=outside)


def _literal_values(annotation: object) -> set[str]:
    """The `Literal[...]` members of a field annotation, ignoring any `| None` union."""
    out: set[str] = set()
    for arg in (annotation, *get_args(annotation)):
        if get_origin(arg) is Literal:
            out.update(str(v) for v in get_args(arg))
    return out


def test_json_schema_matches_model_fields() -> None:
    """The rendered ledger schema property set must equal the pydantic model fields."""
    schema_path = (
        Path(__file__).resolve().parents[1].parent
        / "src"
        / "harness_maker"
        / "templates"
        / "schemas"
        / "second-opinion-ledger.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_props = set(schema["properties"])
    model_fields = set(codex_ledger.SecondOpinionRecord.model_fields)
    assert schema_props == model_fields

    # Names alone are invariant over the enum VALUES — a widened `Literal` against a
    # stale enum passed this test while the shipped schema declared the rows the code
    # writes invalid. That is exactly what happened when `stage` gained "health".
    for name, field in codex_ledger.SecondOpinionRecord.model_fields.items():
        literals = _literal_values(field.annotation)
        if not literals:
            continue
        assert set(schema["properties"][name].get("enum", [])) == literals, (
            f"{name}: schema enum drifted from the model Literal"
        )


def test_cli_emit_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _StdinStub(json.dumps(_valid_invoked())))
    rc = codex_ledger.main(["emit"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("second-opinion.jsonl")


def test_cli_emit_from_args_is_injection_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REVIEW P1: arg-based emit builds JSON in Python — a quote in skip_reason is data."""
    monkeypatch.chdir(tmp_path)
    rc = codex_ledger.main(
        [
            "emit",
            "--slug",
            "crossmodel-codex-gaps",
            "--stage",
            "review",
            "--finding-ref",
            "n/a",
            "--disposition",
            "unresolved",
            "--status",
            "skipped",
            "--skip-reason",
            "codex exited; reason had a ' quote and ; semicolon",
        ]
    )
    assert rc == 0
    path = tmp_path / ".claude" / "observability" / "second-opinion.jsonl"
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["skip_reason"] == "codex exited; reason had a ' quote and ; semicolon"
    assert row["status"] == "skipped"


def test_cli_emit_args_reject_bad_enum(monkeypatch: pytest.MonkeyPatch) -> None:
    rc = codex_ledger.main(
        [
            "emit",
            "--slug",
            "x",
            "--stage",
            "wrapup",
            "--finding-ref",
            "a",
            "--disposition",
            "accepted",
            "--status",
            "invoked",
        ]
    )
    assert rc == 1  # stage 'wrapup' not in the enum


class _StdinStub:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> str:
        return self._payload
