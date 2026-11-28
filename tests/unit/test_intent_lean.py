"""SPEC-intent-lean: the intent layer keeps goals, metrics and measurement history, and asks less."""

# ruff: noqa: E501 — the golden rows below are pasted verbatim from the machine SPEC.
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import typing
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

REPO = Path(__file__).resolve().parents[2]

# AC-002 golden rows from SPEC-intent-lean.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_002_ROWS = [
    (
        {"verb": "approve"},
        {
            "exit": 2,
            "message_contains": "no step needed",
            "message_excludes": "spec_machine",
            "unchanged": True,
        },
    ),
    (
        {"verb": "activate"},
        {
            "exit": 2,
            "message_contains": "no step needed",
            "message_excludes": "spec_machine",
            "unchanged": True,
        },
    ),
    (
        {"verb": "drop"},
        {
            "exit": 2,
            "message_contains": "close",
            "message_excludes": "spec_machine",
            "unchanged": True,
        },
    ),
    (
        {"verb": "reopen"},
        {
            "exit": 2,
            "message_contains": "no step needed",
            "message_excludes": "spec_machine",
            "unchanged": True,
        },
    ),
]

# AC-003 golden rows from SPEC-intent-lean.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_003_ROWS = [
    ({"state": "proposed"}, {"state": "open"}),
    ({"state": "active"}, {"state": "open"}),
    (
        {"state": "closed", "observed": "met"},
        {"state": "closed", "observed": "met", "bytes_unchanged": True},
    ),
    ({"state": "dropped"}, {"state": "closed", "observed": "no_data", "bytes_unchanged": True}),
    ({"other_question_has_locator": True}, {"other_entries_equal": True}),
]

# AC-006 golden rows from SPEC-intent-lean.machine.yaml: (input, expected).
# Do not edit; `hm check` compares them with the SPEC.
AC_006_ROWS = [
    ({"last": 6.984, "target": 8, "higher_is_better": False}, "at_or_better"),
    ({"last": 9, "target": 8, "higher_is_better": False}, "above_target"),
    ({"last": 80, "target": 80, "higher_is_better": True}, "at_or_better"),
    ({"last": 70, "target": 80, "higher_is_better": True}, "below_target"),
    ({"last": None, "target": 8, "higher_is_better": False}, "unevaluable"),
    (
        {"last": 6.984, "target": 8, "higher_is_better": False, "stale_definition": True},
        "unevaluable",
    ),
]

_LOCATOR = {
    "path": "src/x.py",
    "lines": [1, 2],
    "fingerprint": "0" * 64,
    "k": 1,
}


def _project_yaml(
    *, target: float = 8, higher_is_better: bool = False, measure: bool = False
) -> dict[str, Any]:
    metric: dict[str, Any] = {
        "id": "cost",
        "description": "cost ratio",
        "target": target,
        "higher_is_better": higher_is_better,
        "how_measured": "bench",
    }
    if measure:
        metric["measure"] = {
            "cmd": f"{sys.executable} -c print(5)",
            "select": "last-number",
            "cwd": "checkout",
        }
    return {
        "schema_version": 1,
        "purpose": {"statement": "ship small", "vision": "v"},
        "metrics": [metric],
        "rules": ["r1"],
        "out_of_scope": [],
        "open_questions": [
            {
                "id": "q_kept",
                "claim": "a claim with a locator",
                "status": "confirmed",
                "evidence": [
                    {
                        "text": "seen",
                        "observed_at": "2026-09-01T00:00:00Z",
                        "relation": "confirms",
                        "locator": _LOCATOR,
                    }
                ],
                "history": [],
            }
        ],
        "owners": {},
    }


def _record(rid: str, state: str, **extra: Any) -> str:
    fm: dict[str, Any] = {
        "id": rid,
        "title": f"title {rid}",
        "scope": ["s"],
        "state": state,
        "created_at": "2026-09-01T00:00:00Z",
        "schema_version": 1,
        "rejected": [],
        "depends_on": [],
        "approval": {
            "content_hash": "a" * 64,
            "approved_by": "x",
            "approved_at": "2026-09-01T00:00:00Z",
            "approved_target": 8,
        },
        "revisit_when": None,
        "observed": None,
        "note": None,
        "closed_at": None,
        "statement": "s",
        "metric_id": "cost",
        "out_of_scope": [],
    }
    fm.update(extra)
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n## Problem\n"


def _make_project(tmp_path: Path, **kw: Any) -> Path:
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "intent.yaml").write_text(
        yaml.safe_dump(_project_yaml(**kw), sort_keys=False, allow_unicode=True)
    )
    (root / "intent").mkdir()
    return root


def _cli(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.intent", "--root", str(root), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _status(root: Path) -> dict[str, Any]:
    rc, out = _cli(root, "status", "--json")
    assert rc == 0, out
    return json.loads(out)  # type: ignore[no-any-return]


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and "observability" not in p.parts
    }


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


# ── AC-002 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("row", "expected"), AC_002_ROWS, ids=[f"AC-002-{i}" for i in range(len(AC_002_ROWS))]
)
def test_ac_002_removed_verbs(
    tmp_path: Path, row: dict[str, Any], expected: dict[str, Any]
) -> None:
    root = _make_project(tmp_path)
    (root / "intent" / "G-1.md").write_text(_record("G-1", "proposed"))
    before = _tree(root)
    rc, out = _cli(root, row["verb"], "G-1")
    assert rc == expected["exit"], out
    assert expected["message_contains"] in out
    assert expected["message_excludes"] not in out
    assert (_tree(root) == before) is expected["unchanged"]


def test_ac_002_removed_verb_through_hm_without_root(tmp_path: Path) -> None:
    """The `hm` front door (no leading `--root`) and a trailing flag still name the replacement."""
    root = _make_project(tmp_path)
    (root / "intent" / "G-1.md").write_text(_record("G-1", "proposed"))
    before = _tree(root)
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "intent", "approve", "--json", "G-1"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "a new goal is open from the start" in proc.stderr
    assert _tree(root) == before


# ── AC-003 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("row", "expected"), AC_003_ROWS, ids=[f"AC-003-{i}" for i in range(len(AC_003_ROWS))]
)
def test_ac_003_state_mapping_and_preservation(
    tmp_path: Path, row: dict[str, Any], expected: dict[str, Any]
) -> None:
    root = _make_project(tmp_path)
    if "state" in row:
        extra: dict[str, Any] = {}
        if row["state"] == "closed":
            extra = {"observed": row["observed"], "note": "n", "closed_at": "2026-09-02T00:00:00Z"}
        path = root / "intent" / "G-1.md"
        path.write_text(_record("G-1", row["state"], **extra))
        before = path.read_bytes()
        status = _status(root)
        assert status["intents"]["G-1"]["state"] == expected["state"]
        if "observed" in expected:
            assert status["intents"]["G-1"]["observed"] == expected["observed"]
        rc, out = _cli(root, "show", "G-1", "--json")
        assert rc == 0, out
        shown = json.loads(out)
        assert shown["state"] == expected["state"]
        if "observed" in expected:
            assert shown["observed"] == expected["observed"]
        if expected.get("bytes_unchanged"):
            note = _write(tmp_path, "note.txt", "n")
            ev = _write(tmp_path, "ev.txt", "e")
            title = _write(tmp_path, "t.txt", "t")
            stmt = _write(tmp_path, "st.txt", "s")
            assert _cli(root, "new", "G-2", "--title-file", str(title), "--statement-file",
                        str(stmt), "--metric", "cost")[0] == 0  # fmt: skip
            assert _cli(root, "metric", "record", "cost", "--value", "5", "--evidence-file",
                        str(ev))[0] == 0  # fmt: skip
            assert _cli(root, "close", "G-2", "--observed", "met", "--note-file", str(note))[0] == 0
            assert _cli(root, "question", "add", "q_b", "--status", "open", "--claim-file",
                        str(note))[0] == 0  # fmt: skip
            assert _cli(root, "question", "observe", "q_b", "--relation", "confirms",
                        "--text-file", str(ev))[0] == 0  # fmt: skip
            assert path.read_bytes() == before
    else:
        before_q = yaml.safe_load((root / ".claude/intent.yaml").read_text())["open_questions"]
        claim = _write(tmp_path, "c.txt", "new claim")
        text = _write(tmp_path, "x.txt", "evidence")
        assert _cli(root, "question", "add", "q_new", "--status", "open", "--claim-file",
                    str(claim))[0] == 0  # fmt: skip
        assert _cli(root, "question", "observe", "q_new", "--relation", "confirms",
                    "--text-file", str(text))[0] == 0  # fmt: skip
        after_q = yaml.safe_load((root / ".claude/intent.yaml").read_text())["open_questions"]
        kept = [q for q in after_q if q["id"] != "q_new"]
        assert (kept == before_q) is expected["other_entries_equal"]


# ── AC-004 ────────────────────────────────────────────────────────────────────


def test_ac_004_status_shape(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    (root / "intent" / "G-1.md").write_text(_record("G-1", "active"))
    (root / "intent" / "G-2.md").write_text(
        _record("G-2", "closed", observed="missed", note="n", closed_at="2026-09-02T00:00:00Z")
    )
    s = _status(root)
    assert set(s) == {"state", "purpose", "metrics", "intents", "open_questions", "open"}
    assert all(set(v) == {"state", "title", "metric_id", "observed"} for v in s["intents"].values())
    assert all(
        set(v)
        == {
            "last",
            "target",
            "gap",
            "observed_at",
            "reason",
            "how_measured",
            "higher_is_better",
            "measure",
        }
        for v in s["metrics"].values()
    )
    assert s["open"] == [k for k, v in s["intents"].items() if v["state"] == "open"]
    assert s["open"] == ["G-1"]


# ── AC-005 ────────────────────────────────────────────────────────────────────


def test_ac_005_new_then_close(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    title = _write(tmp_path, "t.txt", "a goal")
    stmt = _write(tmp_path, "s.txt", "why")
    note = _write(tmp_path, "n.txt", "measured 6.9")
    rc, out = _cli(root, "new", "G-9", "--title-file", str(title), "--statement-file", str(stmt),
                   "--metric", "cost")  # fmt: skip
    assert rc == 0, out
    rec = yaml.safe_load((root / "intent/G-9.md").read_text().split("---\n")[1])
    assert rec["state"] == "open"
    assert "approval" not in rec
    rc, out = _cli(root, "close", "G-9", "--observed", "met", "--note-file", str(note))
    assert rc == 0, out
    text = (root / "intent/G-9.md").read_text()
    rec = yaml.safe_load(text.split("---\n")[1])
    assert (rec["state"], rec["observed"]) == ("closed", "met")
    assert rec["note"] == "measured 6.9"
    assert _cli(root, "close", "G-9", "--observed", "met", "--note-file", str(note))[0] != 0


# ── AC-006 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("row", "expected"), AC_006_ROWS, ids=[f"AC-006-{i}" for i in range(len(AC_006_ROWS))]
)
def test_ac_006_gap_rule(tmp_path: Path, row: dict[str, Any], expected: str) -> None:
    root = _make_project(tmp_path, target=row["target"], higher_is_better=row["higher_is_better"])
    if row["last"] is not None:
        ev = _write(tmp_path, "ev.txt", "bench run")
        rc, out = _cli(root, "metric", "record", "cost", "--value", str(row["last"]),
                       "--evidence-file", str(ev))  # fmt: skip
        assert rc == 0, out
    if row.get("stale_definition"):
        path = root / ".claude/intent/metrics.yaml"
        doc = yaml.safe_load(path.read_text())
        doc["values"][-1]["definition_hash"] = "f" * 64
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert _status(root)["metrics"]["cost"]["gap"] == expected


# ── AC-007 ────────────────────────────────────────────────────────────────────


def _digest(root: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.world_model", "digest", "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.strip().encode("utf-8")) <= 1500, len(proc.stdout)
    return json.loads(proc.stdout)  # type: ignore[no-any-return]


def _git_project(tmp_path: Path, goals: int, tasks: int) -> Path:
    root = _make_project(tmp_path)
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30)
    for i in range(goals):
        rid = f"GOAL-NUMBER-{i:02d}-WITH-A-LONG-NAME"
        (root / "intent" / f"{rid}.md").write_text(_record(rid, "proposed"))
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}  # fmt: skip
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, timeout=30)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "x"], check=True, timeout=30, env=env)
    for t in range(tasks):
        slug = f"task-{t}-with-a-fairly-long-slug-name"
        subprocess.run(
            ["git", "-C", str(root), "worktree", "add", "-q", "-b", f"hm/{slug}",
             str(root / ".worktrees" / slug)],
            check=True, timeout=30,
        )  # fmt: skip
    return root


def test_ac_007_digest_intents_lean_and_capped(tmp_path: Path) -> None:
    one = _git_project(tmp_path / "one", goals=1, tasks=0)
    d = _digest(one)
    assert set(d["intents"]) == {"open"}
    assert set(d["intents"]["open"][0]) == {"id", "metric_id", "last", "target", "gap"}
    many = _git_project(tmp_path / "many", goals=12, tasks=5)
    d = _digest(many)
    assert "unavailable" not in d
    assert len(d["tasks"]) >= 1
    assert all("other_session" in t for t in d["tasks"])


# ── AC-001 / AC-008: the rendered surface ─────────────────────────────────────

_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
_PATHS = {
    "claude": {
        "spec": ".claude/commands/hm/spec.md",
        "wrapup": ".claude/commands/hm/wrapup.md",
        "maker": ".claude/skills/maker/SKILL.md",
        "intent": ".claude/skills/intent-layer/SKILL.md",
        "feedback": ".claude/skills/intent-layer/references/workflow-feedback.md",
    },
    "codex": {
        "spec": ".agents/skills/hm-spec/SKILL.md",
        "wrapup": ".agents/skills/hm-wrapup/SKILL.md",
        "maker": ".agents/skills/maker/SKILL.md",
        "intent": ".agents/skills/intent-layer/SKILL.md",
        "feedback": ".agents/skills/intent-layer/references/workflow-feedback.md",
    },
}
_TOOL = {"claude": "AskUserQuestion", "codex": "request_user_input"}
_REMOVED = (
    "approve",
    "activate",
    "drop",
    "reopen",
    "revisit",
    "--from-proposal",
    "workflow-feedback",
)


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def get(preset: str) -> Path:
        if preset not in cache:
            base = tmp_path_factory.mktemp(f"intent-lean-{preset}")
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=base / "h")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[preset] = project
        return cache[preset]

    return get


def _body(text: str) -> str:
    """The skill body after its frontmatter (generated metadata names no verbs)."""
    return text.split("\n---\n", 1)[1] if text.startswith("---\n") else text


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + 1)
    return text[start : nxt if nxt != -1 else len(text)]


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_ac_001_intent_skill_asks_three_moments(
    preset: str, renders: Callable[[str], Path]
) -> None:
    root = renders(preset)
    for runtime, paths in _PATHS.items():
        whole = (root / paths["intent"]).read_text(encoding="utf-8")
        assert len(whole) <= 4000, (runtime, len(whole))  # the rendered file, frontmatter included
        s = _body(whole)
        assert s.count(_TOOL[runtime]) == 1, runtime
        rule = _section(s, "## Ask only")
        assert _TOOL[runtime] in rule
        for moment in ("create a goal", "change a target", "close a goal"):
            assert moment in rule, (runtime, moment)
        assert "one round" in s
        assert "at most 3 questions" in s
        assert not any(v in s for v in _REMOVED), [v for v in _REMOVED if v in s]
        assert len(s) <= 4000, len(s)


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_ac_008_lean_surface_rendered(preset: str, renders: Callable[[str], Path]) -> None:
    root = renders(preset)
    for runtime, paths in _PATHS.items():
        spec = (root / paths["spec"]).read_text(encoding="utf-8")
        assert "Step 0.5 — Intent" not in spec
        assert "`intent` (if picked)" not in spec
        wrapup = (root / paths["wrapup"]).read_text(encoding="utf-8")
        step5 = _section(wrapup, "## Step 5")
        for verb in ("metric measure", "metric record", "question add", "question observe"):
            assert verb in step5, (runtime, verb)
        assert "`intent: <verb> <id>" in step5
        assert step5.count(_TOOL[runtime]) == 1
        ask_line = next(line for line in step5.splitlines() if _TOOL[runtime] in line)
        assert "close" in ask_line
        assert not (root / paths["feedback"]).exists()
        maker = (root / paths["maker"]).read_text(encoding="utf-8")
        assert "intents.open" in maker
        assert "intents.active" not in maker
        assert len(_body(maker)) <= 4689


# ── AC-009 ────────────────────────────────────────────────────────────────────


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        return False
    return True


def test_ac_009_engine_modules_gone() -> None:
    from harness_maker import autopilot_caps, command_registry

    assert not _importable("harness_maker.world")
    assert not _importable("harness_maker.intent_vocabulary")
    assert "world" not in command_registry.MODULES
    assert not hasattr(autopilot_caps, "_objective_check")
    assert "objective_gate" not in typing.get_args(autopilot_caps.HaltKind)


# ── AC-010 ────────────────────────────────────────────────────────────────────


def test_ac_010_project_data_fixed() -> None:
    rules = yaml.safe_load((REPO / ".claude/intent.yaml").read_text())["rules"]
    assert not any("Cursor" in r for r in rules)
    rec = yaml.safe_load((REPO / "intent/HM-LIGHT-LANE.md").read_text().split("---\n")[1])
    assert (rec["state"], rec["observed"]) == ("closed", "met")


# ── AC-011 ────────────────────────────────────────────────────────────────────


def test_ac_011_legacy_layout(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    (root / ".claude" / "world").mkdir(parents=True)
    (root / ".claude" / "intent.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "mission": "m",
                "outcomes": [
                    {
                        "id": "cost",
                        "description": "d",
                        "target": 8,
                        "higher_is_better": False,
                        "how_measured": "h",
                    }  # fmt: skip
                ],
            }
        )
    )
    rc, out = _cli(root, "status", "--json")
    s = json.loads(out)
    assert s["state"] == "invalid"
    assert "hm intent migrate" in json.dumps(s)
    rc, out = _cli(root, "migrate", "--json")
    assert rc == 0, out
    (root / "intent").mkdir(exist_ok=True)
    (root / "intent" / "G-1.md").write_text(_record("G-1", "open"))
    rc, out = _cli(root, "migrate", "--json")
    assert rc == 0, out
    assert _status(root)["intents"]["G-1"]["state"] == "open"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/unit/test_intent_vocabulary.py"],
        cwd=REPO, capture_output=True, text=True, timeout=300,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-2000:]
