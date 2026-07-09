"""Second-opinion ledger: model field + one-time legacy forward-copy idempotency (ADR-005)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.codex_ledger import (
    _LEGACY_LEDGER_FILENAME,
    LEDGER_FILENAME,
    SecondOpinionRecord,
    emit,
    record_from_dict,
)


def _obs_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude" / "observability"
    d.mkdir(parents=True)
    return d


def _record(**over: object) -> SecondOpinionRecord:
    base: dict[str, object] = {
        "ts": "2026-07-09T00:00:00Z",
        "slug": "demo",
        "stage": "plan",
        "model": "antigravity",
        "finding_ref": "f1",
        "disposition": "accepted",
        "status": "invoked",
    }
    base.update(over)
    return SecondOpinionRecord.model_validate(base)


def test_model_field_defaults_to_codex() -> None:
    rec = record_from_dict(
        {
            "slug": "s",
            "stage": "review",
            "finding_ref": "f",
            "disposition": "unresolved",
            "status": "skipped",
        }
    )
    assert rec.model == "codex"


def test_status_enum_accepts_failed() -> None:
    rec = _record(status="failed", disposition="unresolved")
    assert rec.status == "failed"


def test_emit_writes_new_filename(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    path = emit(_record(), project_root=tmp_path, observability_dir=obs)
    assert path.name == LEDGER_FILENAME
    rows = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["model"] == "antigravity"


def _legacy_row(**over: object) -> str:
    base: dict[str, object] = {
        "ts": "2026-05-01T00:00:00Z",
        "slug": "old",
        "stage": "plan",
        "finding_ref": "legacy-f",
        "disposition": "accepted",
        "codex_status": "invoked",
        "skip_reason": None,
        "oracle_result": None,
        "later_regression_link": None,
    }
    base.update(over)
    return json.dumps(base)


def test_forward_copy_tags_legacy_rows_codex(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    (obs / _LEGACY_LEDGER_FILENAME).write_text(_legacy_row() + "\n", encoding="utf-8")
    emit(_record(), project_root=tmp_path, observability_dir=obs)
    rows = (obs / LEDGER_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    # 1 forward-copied legacy row + 1 fresh emit
    assert len(rows) == 2
    migrated = json.loads(rows[0])
    assert migrated["model"] == "codex"
    assert migrated["status"] == "invoked"  # codex_status -> status
    assert migrated["slug"] == "old"


def test_forward_copy_is_one_time_not_repeated(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    (obs / _LEGACY_LEDGER_FILENAME).write_text(_legacy_row() + "\n", encoding="utf-8")
    emit(_record(), project_root=tmp_path, observability_dir=obs)
    emit(_record(finding_ref="f2"), project_root=tmp_path, observability_dir=obs)
    rows = (obs / LEDGER_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    # 1 legacy + 2 fresh — the legacy migration must NOT re-run on the second emit
    assert len(rows) == 3
    assert sum(1 for r in rows if json.loads(r)["slug"] == "old") == 1


def test_forward_copy_skips_when_new_file_exists(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    (obs / _LEGACY_LEDGER_FILENAME).write_text(_legacy_row() + "\n", encoding="utf-8")
    (obs / LEDGER_FILENAME).write_text(json.dumps(_record().model_dump()) + "\n", encoding="utf-8")
    emit(_record(finding_ref="f2"), project_root=tmp_path, observability_dir=obs)
    rows = (obs / LEDGER_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    # new file pre-existed -> legacy migration is a no-op; only the 2 new rows present
    assert all(json.loads(r)["slug"] != "old" for r in rows)


def test_forward_copy_skips_malformed_legacy_rows(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    content = "not json\n" + _legacy_row() + "\n" + '{"partial":\n'
    (obs / _LEGACY_LEDGER_FILENAME).write_text(content, encoding="utf-8")
    emit(_record(), project_root=tmp_path, observability_dir=obs)
    rows = (obs / LEDGER_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    # 1 valid legacy row survives + 1 fresh; the 2 malformed lines are dropped
    assert len(rows) == 2


def test_new_only_no_legacy(tmp_path: Path) -> None:
    obs = _obs_dir(tmp_path)
    emit(_record(), project_root=tmp_path, observability_dir=obs)
    rows = (obs / LEDGER_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValueError, match="codex_status|extra"):
        _record(codex_status="invoked")
