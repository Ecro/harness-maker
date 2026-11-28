"""Frozen v1 fixtures: do not rename the legacy keys in this module.

The oracle comes from HANDOFF H1-H4, not migrated production constants. SPEC-intent-lean
(AC-011): only `hm intent migrate` reads the legacy vocabulary now, so these tests build a
legacy layout by hand, show every other read reports it `invalid` naming migrate, and pin what
migrate keeps (values, record bodies and approval bytes, history, question statuses).
"""

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from harness_maker import intent
from harness_maker.models import Target
from harness_maker.wrapup_land import derive_deliverable_globs
from tests.unit import intent_fixture as fx
from tests.unit.test_render_intent_layer import _render_target

METRIC = {
    "id": "latency",
    "description": "latency",
    "target": 10,
    "higher_is_better": False,
    "how_measured": "stopwatch",
}
LEGACY = {
    "schema_version": 1,
    "mission": "빠르게 ship",
    "vision": "keep quality",
    "outcomes": [METRIC],
    "non_negotiables": ["preserve data"],
    "non_scope": ["auth"],
    "unknowns": ["Which runtime?"],
    "owners": [],
}
BODY = b"## Problem\r\n\r\nKeep these bytes.\r\n"
APPROVAL = {
    "content_hash": "c" * 64,
    "approved_by": "Fixture Approver",
    "approved_at": "2026-09-02T00:00:00Z",
    "approved_target": 10,
}
_EVIDENCE = [{"text": "E1", "observed_at": "2026-09-01T00:00:00Z", "relation": "confirms"}]


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "intent", "--root", str(root), *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=120,
    )


def _ok(root: Path, *args: str) -> dict[str, Any]:
    proc = _cli(root, *args)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    return cast(dict[str, Any], json.loads(proc.stdout))


def _legacy_record(rid: str = "OBJ-1") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": rid,
        "title": f"{rid} title",
        "hypothesis": "shorter onboarding keeps users",
        "scope": ["cut the interview to one round"],
        "non_scope": ["rewrite the renderer"],
        "rejected": [],
        "outcome_id": "latency",
        "depends_on": [],
        "state": "active",
        "approval": dict(APPROVAL),
        "revisit_when": None,
        "observed": None,
        "note": None,
        "created_at": "2026-09-01T00:00:00Z",
        "closed_at": None,
    }


def _root(root: Path, *, questions: list[dict[str, Any]] | None = None) -> Path:
    """The pre-0.58 layout, written by hand: `.claude/world/` plus a legacy `intent.yaml`."""
    fx.git_init(root)
    fx.dump(root / ".claude/intent.yaml", copy.deepcopy(LEGACY))
    fx.dump(
        root / ".claude/world/assumptions.yaml",
        {"schema_version": 1, "assumptions": questions or []},
    )
    fx.dump(root / ".claude/world/outcomes.yaml", {"schema_version": 1, "values": []})
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def _canonical() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "purpose": {"statement": "빠르게 ship", "vision": "keep quality"},
        "metrics": [copy.deepcopy(METRIC)],
        "rules": ["preserve data"],
        "out_of_scope": ["auth"],
        "open_questions": [
            {
                "id": "q_runtime",
                "claim": "Which runtime?",
                "status": "open",
                "evidence": [],
                "history": [],
            }
        ],
        "owners": {},
    }


def test_s1(tmp_path: Path) -> None:
    raw = _canonical()
    raw["metrics"][0]["measure"] = {"cmd": "python measure.py", "select": "last-number"}
    path = tmp_path / "intent.yaml"
    fx.dump(path, raw)
    before = path.read_bytes()
    assert intent.validate_intent(path) == []
    loaded = intent.load_intent(path)
    assert (loaded.purpose, loaded.rules, loaded.out_of_scope) == (
        {"statement": "빠르게 ship", "vision": "keep quality"},
        ("preserve data",),
        ("auth",),
    )
    assert [q["claim"] for q in loaded.open_questions] == ["Which runtime?"]
    assert asdict(loaded.metrics[0]) == {
        **METRIC,
        "measure": {
            "cmd": "python measure.py",
            "select": "last-number",
            "cwd": "base",
            "timeout_s": 300,
        },
    }
    assert path.read_bytes() == before


def test_s1_legacy_reads_invalid_naming_migrate(tmp_path: Path) -> None:
    root = _root(tmp_path)
    before = _snapshot(root)
    report = _ok(root, "status", "--json")
    assert report["state"] == "invalid"
    assert "hm intent migrate" in report["error"]["message"]
    refused = _cli(root, "question", "add", "new", "--claim", "why", "--status", "open")
    assert refused.returncode != 0
    assert "hm intent migrate" in refused.stdout + refused.stderr
    assert _snapshot(root) == before


@pytest.mark.parametrize("defect", ["mixed", "foreign", "missing", "unknown", "purpose"])
def test_s1_invalid(tmp_path: Path, defect: str) -> None:
    raw = _canonical()
    if defect == "mixed":
        raw["mission"] = "contradictory"
    elif defect == "foreign":
        raw["schema_version"] = 99
    elif defect == "missing":
        del raw["metrics"]
    elif defect == "unknown":
        raw["typo"] = True
    else:
        raw["purpose"] = {"statement": 123, "vision": "v"}
    path = tmp_path / "intent.yaml"
    fx.dump(path, raw)
    good = tmp_path / "good.yaml"
    fx.dump(good, _canonical())
    assert intent.validate_intent(good) == []
    assert intent.validate_intent(path)
    with pytest.raises(intent.IntentInvalidError):
        intent.load_intent(path)


def test_s2(tmp_path: Path) -> None:
    root = _root(tmp_path)
    record = _legacy_record()
    fx.dump_intent(root / "work-docs/INTENT-OBJ-1.md", record, BODY)
    definition = _hash({"higher_is_better": False, "how_measured": "stopwatch", "target": 10})
    fx.dump(
        root / ".claude/world/outcomes.yaml",
        {
            "schema_version": 1,
            "values": [
                {
                    "outcome_id": "latency",
                    "value": 8,
                    "observed_at": "2026-09-01T00:00:00Z",
                    "evidence": "timed",
                    "definition_hash": definition,
                }
            ],
        },
    )
    _ok(root, "migrate", "--json")
    path = root / "intent/OBJ-1.md"
    persisted = fx.load(path)
    assert (
        persisted["statement"],
        persisted["metric_id"],
        persisted["out_of_scope"],
        persisted["approval"],
        persisted["created_at"],
    ) == (record["hypothesis"], "latency", record["non_scope"], APPROVAL, record["created_at"])
    assert path.read_bytes().endswith(BODY)
    report = _ok(root, "status", "--json")
    assert report["intents"]["OBJ-1"]["state"] == "open"
    assert report["metrics"]["latency"]["last"] == 8
    assert report["metrics"]["latency"]["reason"] == "measured"
    rows = fx.load(root / ".claude/intent/metrics.yaml")["values"]
    assert rows[0]["definition_hash"] == definition
    assert rows[0]["metric_id"] == "latency"


def test_s4(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fx.dump_intent(root / "work-docs/INTENT-OBJ-1.md", _legacy_record(), BODY)
    _ok(root, "migrate", "--json")
    before = _snapshot(root)
    _ok(root, "migrate", "--json")
    result = _snapshot(root)
    assert result == before
    assert "intent/OBJ-1.md" in result
    assert "work-docs/INTENT-OBJ-1.md" not in result
    assert ".claude/world/assumptions.yaml" not in result
    assert ".claude/world/outcomes.yaml" not in result
    assert set(fx.load(root / ".claude/intent.yaml")) == {
        "schema_version",
        "purpose",
        "metrics",
        "rules",
        "out_of_scope",
        "open_questions",
        "owners",
    }


def test_s4_conflict(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fx.dump_intent(root / "work-docs/INTENT-OBJ-1.md", _legacy_record(), BODY)
    fx.dump_intent(root / "intent/OBJ-1.md", {"id": "OBJ-1", "statement": "other"}, b"other\n")
    before = _snapshot(root)
    proc = _cli(root, "migrate", "--json")
    assert "conflict" in (proc.stdout + proc.stderr).lower()
    assert proc.returncode != 0
    assert _snapshot(root) == before


def test_s5(tmp_path: Path) -> None:
    questions = [
        {
            "id": f"q_{i}",
            "claim": f"claim {i}",
            "status": s,
            "evidence": copy.deepcopy(_EVIDENCE),
            "history": [f"earlier {i}", f"old {i}"],
            "revisit_when": None,
        }
        for i, s in enumerate(["known", "assumed", "unknown", "conflict"])
    ]
    root = _root(tmp_path, questions=questions)
    _ok(root, "migrate", "--json")
    stored = fx.load(root / ".claude/intent.yaml")["open_questions"]
    by_id = {q["id"]: q for q in stored}
    assert [by_id[f"q_{i}"]["status"] for i in range(4)] == ["confirmed", "open", "open", "wrong"]
    for q in questions:
        assert by_id[q["id"]]["claim"] == q["claim"]
        assert by_id[q["id"]]["evidence"] == q["evidence"]
        assert by_id[q["id"]]["history"] == q["history"]
    unknown = next(q for q in stored if q["claim"] == "Which runtime?")
    _ok(root, "question", "resolve", unknown["id"], "--status", "confirmed", "--claim", "CPython",
        "--json")  # fmt: skip
    _ok(root, "migrate", "--json")
    after = fx.load(root / ".claude/intent.yaml")["open_questions"]
    assert len(after) == 5
    assert next(q for q in after if q["id"] == unknown["id"])["claim"] == "CPython"
    assert not (root / ".claude/world/assumptions.yaml").exists()


def test_s6_open_record_survives_migrate(tmp_path: Path) -> None:
    """S6: migrate accepts an existing canonical `state: open` record and leaves it as it is."""
    root = _root(tmp_path)
    _ok(root, "migrate", "--json")
    _ok(root, "new", "WORK", "--title", "faster", "--statement", "speed helps", "--metric",
        "latency", "--json")  # fmt: skip
    before = (root / "intent/WORK.md").read_bytes()
    assert _ok(root, "migrate", "--json") == {"changed": [], "retired": []}
    assert (root / "intent/WORK.md").read_bytes() == before
    assert _ok(root, "show", "WORK", "--json")["state"] == "open"


def test_s7(tmp_path: Path) -> None:
    files = _render_target([Target.CLAUDE_CODE, Target.CODEX])
    for path in (".claude/skills/intent-layer/SKILL.md", ".agents/skills/intent-layer/SKILL.md"):
        text = files[path]
        assert "hm intent status" in text
        assert "hm world" not in text
        assert "intent/<ID>.md" in text
        assert "hm intent migrate" in text
    (tmp_path / "intent").mkdir()
    (tmp_path / "intent/WORK.md").write_text("record")
    globs = derive_deliverable_globs("unrelated-task", tmp_path)
    assert any((tmp_path / "intent/WORK.md") in tmp_path.glob(g) for g in globs)


@pytest.mark.parametrize(
    ("field", "value"),
    [("id", ""), ("claim", ""), ("evidence", [{}]), ("history", [42])],
)
def test_nested_question_validation(tmp_path: Path, field: str, value: Any) -> None:
    raw = _canonical()
    raw["open_questions"][0][field] = value
    path = tmp_path / "intent.yaml"
    fx.dump(path, raw)
    with pytest.raises(intent.IntentInvalidError):
        intent.load_intent(path)


def test_unknown_ids_survive_reordering_and_preserve_duplicates(tmp_path: Path) -> None:
    def migrated(unknowns: list[str], where: Path) -> dict[str, Any]:
        root = _root(where)
        raw = copy.deepcopy(LEGACY)
        raw["unknowns"] = unknowns
        fx.dump(root / ".claude/intent.yaml", raw)
        _ok(root, "migrate", "--json")
        return {q["id"]: q for q in fx.load(root / ".claude/intent.yaml")["open_questions"]}

    before = migrated(["a", "b", "a"], tmp_path / "one")
    after = migrated(["b", "a", "a"], tmp_path / "two")
    assert len(before) == len(after) == 3
    assert before == after


def test_registered_intent_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "intent", "--help"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    assert all(verb in result.stdout for verb in ("status", "migrate", "question", "metric"))


def test_migration_write_failure_preserves_sources_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import intent_migrate

    root = _root(tmp_path)
    fx.dump_intent(root / "work-docs/INTENT-RETRY.md", _legacy_record("RETRY"), BODY)
    before = _snapshot(root)
    from harness_maker.io_utils import atomic_write as original_write

    def fail_project(path: Path, content: bytes) -> None:
        if path == root / ".claude/intent.yaml":
            raise OSError("injected project write failure")
        original_write(path, content)

    with monkeypatch.context() as patch:
        patch.setattr(intent_migrate, "atomic_write", fail_project)
        with pytest.raises(OSError, match="injected project write failure"):
            intent_migrate.migrate(root)
    # A completed destination may exist, but no original has been removed or rewritten.
    for path, content in before.items():
        assert (root / path).read_bytes() == content
    result = intent_migrate.migrate(root)
    assert "work-docs/INTENT-RETRY.md" in result["retired"]
    assert _ok(root, "show", "RETRY", "--json")["statement"] == "shorter onboarding keeps users"
    assert intent_migrate.migrate(root) == {"changed": [], "retired": []}
