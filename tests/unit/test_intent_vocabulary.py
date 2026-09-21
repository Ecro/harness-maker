"""Frozen v1 fixtures: do not rename the legacy keys in this module.

The oracle comes from HANDOFF H1-H4, not migrated production constants. Canonical
CLI assertions are followed by independent value/body/history checks so merely
registering an alias cannot make these tests pass.
"""

import copy
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from harness_maker import intent, world
from harness_maker.models import Target
from harness_maker.wrapup_land import derive_deliverable_globs
from tests.unit import world_fixture as fx
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


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _cli(root: Path, *args: str, module: str = "intent") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", module, "--root", str(root), *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=120,
    )


def _ok(root: Path, *args: str) -> dict[str, Any]:
    proc = _cli(root, *args)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    return cast(dict[str, Any], json.loads(proc.stdout))


def _root(root: Path) -> Path:
    fx.build_root(root, intent=copy.deepcopy(LEGACY))
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


@pytest.mark.parametrize("canonical", [False, True])
def test_s1(tmp_path: Path, canonical: bool) -> None:
    raw: dict[str, Any] = _canonical() if canonical else copy.deepcopy(LEGACY)
    raw["metrics" if canonical else "outcomes"][0]["measure"] = {
        "cmd": "python measure.py",
        "select": "last-number",
    }
    path = tmp_path / "intent.yaml"
    fx.dump(path, raw)
    before = path.read_bytes()
    assert intent.validate_intent(path) == []
    loaded = intent.load_intent(path)
    result = (loaded.purpose, [m.id for m in loaded.metrics], loaded.rules, loaded.out_of_scope)
    expected = (
        {"statement": "빠르게 ship", "vision": "keep quality"},
        ["latency"],
        ("preserve data",),
        ("auth",),
    )
    assert result == expected
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
    expected = True
    # A valid canonical sibling must load, preventing a reject-everything false RED.
    good = tmp_path / "good.yaml"
    fx.dump(good, _canonical())
    assert intent.validate_intent(good) == []
    result = bool(intent.validate_intent(path))
    assert result == expected
    with pytest.raises(intent.IntentInvalidError):
        intent.load_intent(path)


def test_s2(tmp_path: Path) -> None:
    root = _root(tmp_path)
    record = fx.objective(outcome_id="latency")
    record = fx.approved(record, 10)
    before_hash = record["approval"]["content_hash"]
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
    result = (
        persisted["statement"],
        persisted["metric_id"],
        persisted["out_of_scope"],
        persisted["approval"]["content_hash"],
        persisted["created_at"],
    )
    expected = (
        record["hypothesis"],
        "latency",
        record["non_scope"],
        before_hash,
        record["created_at"],
    )
    assert result == expected
    assert path.read_bytes().endswith(BODY)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True
    report = _ok(root, "status", "--json")
    assert report["metrics"]["latency"]["last"] == 8
    assert report["metrics"]["latency"]["stale_definition"] is False
    rows = fx.load(root / ".claude/intent/metrics.yaml")["values"]
    assert rows[0]["definition_hash"] == definition
    assert rows[0]["metric_id"] == "latency"


def test_s3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.test_world_withdrawal import _commit, _span

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = _root(tmp_path)
    _commit(root, "2026-09-01T10:00:00+09:00", "legacy filled")
    ledger = root / ".claude/observability/stage-spans.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "\n".join(_span("hm:wrapup", "start", f"2026-09-{i:02}T00:00:00Z") for i in range(2, 12))
        + "\n"
    )
    _ok(root, "migrate", "--json")
    _commit(root, "2026-09-15T00:00:00Z", "canonical")
    report = _ok(root, "status", "--json")
    result = (
        report["withdrawal"]["filled_at"],
        report["withdrawal"]["quiet_wrapups"],
        report["withdrawal"]["due"],
    )
    expected = ("2026-09-01T01:00:00Z", 10, True)
    assert result == expected


def test_s4(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fx.dump_intent(root / "work-docs/INTENT-OBJ-1.md", fx.objective(outcome_id="latency"), BODY)
    _ok(root, "migrate", "--json")
    before = _snapshot(root)
    _ok(root, "migrate", "--json")
    result = _snapshot(root)
    expected = before
    assert result == expected
    assert "intent/OBJ-1.md" in result
    assert "work-docs/INTENT-OBJ-1.md" not in result
    assert ".claude/world/assumptions.yaml" not in result
    assert ".claude/world/outcomes.yaml" not in result
    raw = fx.load(root / ".claude/intent.yaml")
    assert set(raw) == {
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
    fx.dump_intent(root / "work-docs/INTENT-OBJ-1.md", fx.objective(outcome_id="latency"), BODY)
    fx.dump_intent(root / "intent/OBJ-1.md", {"id": "OBJ-1", "statement": "other"}, b"other\n")
    before = _snapshot(root)
    proc = _cli(root, "migrate", "--json")
    # Registered canonical entrypoint and migration-specific error distinguish refusal from
    # the old dispatcher rejecting an unknown command.
    assert "conflict" in (proc.stdout + proc.stderr).lower()
    assert proc.returncode != 0
    result = _snapshot(root)
    expected = before
    assert result == expected


def test_s5(tmp_path: Path) -> None:
    root = _root(tmp_path)
    questions = [
        fx.assumption(f"q_{i}", claim=f"claim {i}", status=s, history=[f"earlier {i}", f"old {i}"])
        for i, s in enumerate(["known", "assumed", "unknown", "conflict"])
    ]
    fx.dump(
        root / ".claude/world/assumptions.yaml", {"schema_version": 1, "assumptions": questions}
    )
    _ok(root, "migrate", "--json")
    stored = fx.load(root / ".claude/intent.yaml")["open_questions"]
    by_id = {q["id"]: q for q in stored}
    result = [by_id[f"q_{i}"]["status"] for i in range(4)]
    expected = ["confirmed", "open", "open", "wrong"]
    assert result == expected
    for q in questions:
        assert by_id[q["id"]]["claim"] == q["claim"]
        assert by_id[q["id"]]["evidence"] == q["evidence"]
        assert by_id[q["id"]]["history"] == q["history"]
    unknown = next(q for q in stored if q["claim"] == "Which runtime?")
    _ok(
        root,
        "question",
        "resolve",
        unknown["id"],
        "--status",
        "confirmed",
        "--claim",
        "CPython",
        "--json",
    )
    _ok(root, "migrate", "--json")
    after = fx.load(root / ".claude/intent.yaml")["open_questions"]
    assert len(after) == 5
    assert next(q for q in after if q["id"] == unknown["id"])["claim"] == "CPython"
    assert not (root / ".claude/world/assumptions.yaml").exists()


def test_s6(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _ok(root, "migrate", "--json")
    _ok(
        root,
        "new",
        "WORK",
        "--title",
        "faster",
        "--statement",
        "speed helps",
        "--scope",
        "parser",
        "--metric",
        "latency",
        "--out-of-scope",
        "auth",
        "--json",
    )
    _ok(root, "approve", "WORK", "--json")
    _ok(root, "activate", "WORK", "--json")
    _ok(
        root,
        "metric",
        "record",
        "latency",
        "--value",
        "8",
        "--observed-at",
        "2026-09-01T00:00:00Z",
        "--evidence",
        "timed",
        "--json",
    )
    _ok(root, "question", "add", "runtime", "--claim", "CPython", "--status", "open", "--json")
    created = {q["id"]: q for q in fx.load(root / ".claude/intent.yaml")["open_questions"]}[
        "runtime"
    ]
    assert (created["claim"], created["status"]) == ("CPython", "open")
    _ok(
        root,
        "question",
        "observe",
        "runtime",
        "--relation",
        "contradicts",
        "--text",
        "PyPy",
        "--observed-at",
        "2026-09-02T00:00:00Z",
        "--json",
    )
    observed = {q["id"]: q for q in fx.load(root / ".claude/intent.yaml")["open_questions"]}[
        "runtime"
    ]
    assert observed["status"] == "wrong"
    assert observed["evidence"][-1] == {
        "text": "PyPy",
        "observed_at": "2026-09-02T00:00:00Z",
        "relation": "contradicts",
    }
    _ok(
        root, "question", "resolve", "runtime", "--status", "confirmed", "--claim", "PyPy", "--json"
    )
    resolved = {q["id"]: q for q in fx.load(root / ".claude/intent.yaml")["open_questions"]}[
        "runtime"
    ]
    assert (resolved["claim"], resolved["status"], resolved["history"][-1]) == (
        "PyPy",
        "confirmed",
        "CPython",
    )
    _ok(root, "close", "WORK", "--observed", "met", "--note", "measured", "--json")
    report = _ok(root, "status", "--json")
    result = (
        report["state"],
        report["metrics"]["latency"]["gap"],
        report["intents"]["WORK"]["state"],
    )
    expected = ("ok", "at_or_better", "closed")
    assert result == expected
    assert "withdrawal" in report
    assert "revisits" in report
    assert "open_questions" in report
    shown = _ok(root, "show", "WORK", "--json")
    assert (shown["id"], shown["statement"], shown["metric_id"], shown["state"]) == (
        "WORK",
        "speed helps",
        "latency",
        "closed",
    )
    _ok(
        root,
        "new",
        "SECOND",
        "--title",
        "next",
        "--statement",
        "try",
        "--scope",
        "parser",
        "--metric",
        "latency",
        "--json",
    )
    _ok(root, "drop", "SECOND", "--json")
    assert _ok(root, "status", "--json")["intents"]["SECOND"]["state"] == "dropped"
    _ok(root, "reopen", "SECOND", "--json")
    assert _ok(root, "status", "--json")["intents"]["SECOND"]["state"] == "proposed"
    project = fx.load(root / ".claude/intent.yaml")
    project["metrics"][0]["measure"] = {
        "cmd": shlex.join([sys.executable, "-c", "print(4)"]),
        "select": "last-number",
    }
    fx.dump(root / ".claude/intent.yaml", project)
    _ok(root, "metric", "measure", "latency", "--json")
    assert _ok(root, "status", "--json")["metrics"]["latency"]["last"] == 4
    old = _cli(root, "status", "--json", module="world")
    assert old.returncode == 0
    assert "deprecated" in old.stderr
    assert json.loads(old.stdout)["state"] == "ok"


def test_s7(tmp_path: Path) -> None:
    files = _render_target([Target.CLAUDE_CODE, Target.CODEX])
    for path in (".claude/skills/intent-layer/SKILL.md", ".agents/skills/intent-layer/SKILL.md"):
        text = files[path]
        assert "hm intent status" in text
        assert "hm world" not in text
        assert "intent/<ID>.md" in text
        assert "hm intent migrate" in text
        assert "preserves record body bytes" in text
    (tmp_path / "intent").mkdir()
    (tmp_path / "intent/WORK.md").write_text("record")
    globs = derive_deliverable_globs("unrelated-task", tmp_path)
    result = any((tmp_path / "intent/WORK.md") in tmp_path.glob(g) for g in globs)
    expected = True
    assert result == expected


def test_s3_shallow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.test_world_withdrawal import _commit

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    source = tmp_path / "source"
    source.mkdir()
    _root(source)
    _commit(source, "2026-09-01T00:00:00Z", "legacy")
    _ok(source, "migrate", "--json")
    _commit(source, "2026-09-02T00:00:00Z", "canonical")
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", source.as_uri(), str(shallow)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    report = _ok(shallow, "status", "--json")["withdrawal"]
    result = (report["filled_at"], report["quiet_wrapups"], report["due"])
    expected = (None, None, False)
    assert result == expected
    assert report["reason"] == "no_git"  # historical shallow-clone contract


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("claim", ""),
        ("evidence", [{}]),
        ("history", [42]),
        ("revisit_when", {"question": "q_runtime", "status": []}),
    ],
)
def test_nested_question_validation(tmp_path: Path, field: str, value: Any) -> None:
    raw = _canonical()
    raw["open_questions"][0][field] = value
    path = tmp_path / "intent.yaml"
    fx.dump(path, raw)
    with pytest.raises(intent.IntentInvalidError):
        intent.load_intent(path)


def test_legacy_read_then_explicit_migration_before_write(tmp_path: Path) -> None:
    root = _root(tmp_path)
    before = _snapshot(root)
    report = _ok(root, "status", "--json")
    assert [q["claim"] for q in report["open_questions"]] == ["Which runtime?"]
    refused = _cli(root, "question", "add", "new", "--claim", "why", "--status", "open")
    assert refused.returncode != 0
    assert "hm intent migrate" in refused.stdout + refused.stderr
    assert _snapshot(root) == before
    _ok(root, "migrate", "--json")
    alias = _cli(
        root,
        "objective",
        "new",
        "ALIAS",
        "--title",
        "legacy caller",
        "--hypothesis",
        "same meaning",
        "--scope",
        "parser",
        "--outcome",
        "latency",
        module="world",
    )
    assert alias.returncode == 0, alias.stderr
    assert "deprecated" in alias.stderr
    assert (root / "intent/ALIAS.md").exists()
    assert not (root / "work-docs/INTENT-ALIAS.md").exists()
    assert _ok(root, "show", "ALIAS", "--json")["statement"] == "same meaning"


def test_unknown_ids_survive_reordering_and_preserve_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "intent.yaml"
    raw = copy.deepcopy(LEGACY)
    raw["unknowns"] = ["a", "b", "a"]
    fx.dump(path, raw)
    before = intent.load_intent(path).open_questions
    raw["unknowns"] = ["b", "a", "a"]
    fx.dump(path, raw)
    after = intent.load_intent(path).open_questions
    assert len(before) == len(after) == 3
    assert {q["id"]: q for q in before} == {q["id"]: q for q in after}


@pytest.mark.parametrize(
    ("link", "proceed"),
    [
        ("intent: OBJ-1", True),
        ("intent: MISSING", False),
        ("intent: OBJ-1\nobjective: OTHER", False),
        ("", True),
    ],
)
def test_canonical_plan_link_at_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link: str, proceed: bool
) -> None:
    from tests.unit.test_autopilot_caps_objective_gate import PlanCase, _arm, _boundary, _project

    root = _project(tmp_path, PlanCase("canonical", f"---\ntype: plan\n{link}\n---\n"))
    _ok(root, "migrate", "--json")
    _arm(root, "auto_safe")
    got = _boundary(
        root, "execute", ["--step-cap", "20", "--time-cap-min", "300"], monkeypatch=monkeypatch
    )
    assert got["proceed"] is proceed
    if not proceed:
        assert got["halt_kind"] == "objective_gate"


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
    world.new_objective(
        root, "RETRY", title="retry", hypothesis="safe", scope=["parser"], outcome_id="latency"
    )
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
    assert (root / "intent/RETRY.md").exists()
    for path, content in before.items():
        assert (root / path).read_bytes() == content
    result = intent_migrate.migrate(root)
    assert "work-docs/INTENT-RETRY.md" in result["retired"]
    assert _ok(root, "show", "RETRY", "--json")["statement"] == "safe"
    assert intent_migrate.migrate(root) == {"changed": [], "retired": []}
