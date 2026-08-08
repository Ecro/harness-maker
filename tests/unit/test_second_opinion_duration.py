"""`duration_s` on per-invocation rows, across BOTH validators and BOTH eras.

A slow model was invisible until it crossed the timeout, at which point the row said
`skipped` and the elapsed time was gone — the regression could only be diagnosed by
re-probing the CLI by hand months later. This field is the trend that makes budget creep
visible before it becomes a cliff.

The dual-surface obligation is the load-bearing part. `SecondOpinionRecord` is
`ConfigDict(strict=True, extra="forbid")` and the shipped
`templates/schemas/second-opinion-ledger.schema.json` is `additionalProperties: false`.
Adding a field to one half only is the `stage`-gains-`"health"` incident, where a parity
test compared property NAMES and was invariant over the enum VALUES.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from harness_maker import codex_ledger
from harness_maker import second_opinion_invoke as soi

_SCHEMA = (
    Path(codex_ledger.__file__).parent
    / "templates"
    / "schemas"
    / "second-opinion-ledger.schema.json"
)


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


# ── the dual surface ─────────────────────────────────────────────────────────


def test_duration_is_a_property_on_both_surfaces() -> None:
    assert "duration_s" in codex_ledger.SecondOpinionRecord.model_fields
    assert "duration_s" in _schema()["properties"]


def test_duration_is_not_required_so_legacy_rows_stay_valid() -> None:
    """The 112 rows written before this field existed must not become invalid.

    `required` means the key must be PRESENT, even when nullable — so listing
    `duration_s` there would declare the harness's own history malformed. The shipped
    schema is the contract the harness publishes about its own JSONL; it must not
    contradict the rows the harness actually wrote.
    """
    assert "duration_s" not in _schema()["required"]


def test_legacy_row_without_the_field_still_parses() -> None:
    legacy = {
        "ts": "2026-07-15T12:46:44Z",
        "slug": "spec-optional-task-driven",
        "stage": "plan",
        "model": "antigravity",
        "finding_ref": "n/a",
        "disposition": "unresolved",
        "status": "skipped",
        "skip_reason": "subscription quota reached (resets ~18h)",
        "oracle_result": None,
        "later_regression_link": None,
    }
    record = codex_ledger.SecondOpinionRecord(**legacy)
    assert record.duration_s is None


def test_duration_type_contract_under_strict_mode() -> None:
    """What `strict=True` actually rejects here — measured, not assumed.

    The PLAN claimed an int would raise and that the producer's `float()` cast was what
    prevented a row from vanishing inside `_emit_row`'s exception-swallowing block. That
    is wrong: pydantic strict mode accepts `int` for a `float` field (lossless widening).
    The real hazard is a NON-numeric value — a string duration, or a `timedelta` someone
    passes later — and that does raise. The cast stays because it normalises the stored
    type, but the row-deleting risk it was credited with belongs to this other input
    class, so that is what gets asserted.
    """
    base = {
        "ts": "2026-08-08T00:00:00Z",
        "slug": "s",
        "stage": "review",
        "model": "antigravity",
        "finding_ref": "n/a",
        "disposition": "unresolved",
        "status": "invoked",
        "skip_reason": None,
        "oracle_result": None,
        "later_regression_link": None,
    }
    assert codex_ledger.SecondOpinionRecord(**base, duration_s=27.4).duration_s == 27.4
    # int is accepted by strict mode and widened — documented so the next reader does
    # not re-derive it from the same wrong premise.
    assert codex_ledger.SecondOpinionRecord(**base, duration_s=27).duration_s == 27.0
    with pytest.raises(ValidationError):
        codex_ledger.SecondOpinionRecord(**base, duration_s="27.4")


# ── the producer ─────────────────────────────────────────────────────────────


@pytest.fixture
def agy_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "second_opinion:\n  models: ['antigravity']\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _rows(base: Path) -> list[dict[str, Any]]:
    path = base / ".claude" / "observability" / "second-opinion.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize(
    ("stdout", "returncode", "exc", "expected_status"),
    [
        (json.dumps({"findings": [], "summary": "s", "confidence": 1.0}), 0, None, "invoked"),
        ("", 1, None, "skipped"),
        ("not json", 0, None, "failed"),
        ("", 0, FileNotFoundError(), "skipped"),
        ("", 0, subprocess.TimeoutExpired("agy", 300), "skipped"),
        ("", 0, PermissionError(), "skipped"),
    ],
    ids=["invoked", "nonzero-exit", "unreadable", "not-installed", "timeout", "no-exec-bit"],
)
def test_every_status_branch_writes_a_row_carrying_duration(
    agy_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    returncode: int,
    exc: BaseException | None,
    expected_status: str,
) -> None:
    """A row must exist on EVERY branch, with the field populated.

    Parametrised over the branch matrix rather than asserting one happy path: the field
    is useless if it is only present when the call already succeeded, since the branches
    that matter for latency are precisely the failing ones.
    """

    def _fake(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if exc is not None:
            raise exc
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="err")

    monkeypatch.setattr(soi.subprocess, "run", _fake)
    result = soi.invoke(
        model="antigravity", prompt="p", slug="s", stage="review", base_root=agy_repo
    )
    assert result["status"] == expected_status, result["reason"]

    rows = _rows(agy_repo)
    assert len(rows) == 1, f"expected exactly one invocation row, got {len(rows)}"
    assert isinstance(rows[0]["duration_s"], float), (
        f"row on the {expected_status!r} branch has no float duration: {rows[0]}"
    )
    assert rows[0]["duration_s"] >= 0.0
