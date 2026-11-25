"""SPEC-saga-bench — the consecutive-session bench with a simulated owner, offline.

No test here calls a model. A fake `claude` (written per test, config beside it) answers agent
calls by the first rule whose `match` text is in the prompt (writing files, sleeping, printing a
CLI-shaped result) and answers schema calls (simulator, quiz, grader) from per-role lists. It
logs every call's argv, prompt and start/end time. Expected prompts and verdicts are typed from
the SPEC.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
_SAGA = _SCRIPTS / "bench" / "saga"

DISCIPLINE = (
    "If anything is ambiguous, ask before implementing. Show your plan and get approval before"
    " implementing. Write decisions and lessons to NOTES.md, and read it when you start. Write"
    " tests, have one subagent review your diff, and fix what it finds. Commit when you are done."
)
RESUME_PROMPT = (
    "My last session was cut off before it finished. Finish the work that was in progress."
)


def _load(name: str) -> ModuleType:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def saga() -> ModuleType:
    return _load("saga_bench")


_FAKE = r"""
import json, os, sys, time
from pathlib import Path
home = Path(sys.argv[0]).resolve().parent
cfg = json.loads((home / "config.json").read_text())
argv = sys.argv[1:]
start = time.time()
def out(payload):
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, **payload}))
def log(prompt, role):
    with (home / "log.jsonl").open("a") as f:
        f.write(json.dumps({"argv": argv, "prompt": prompt, "role": role, "start": start,
                            "end": time.time(), "cwd": os.getcwd()}) + "\n")
if "--json-schema" in argv:
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    role = next(r for r in ("reply", "answers", "correct", "detected")
                if r in schema["properties"])
    counter = home / f"count-{role}"
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    answers = cfg[role]
    data = answers[min(n, len(answers) - 1)]
    sys.stdin.read()
    log("", role)
    out({"structured_output": data, "total_cost_usd": 0.01, "session_id": "s-" + role})
    raise SystemExit(0)
prompt = argv[argv.index("-p") + 1]
rule = next(r for r in cfg["agent"] if r["match"] in prompt)
for rel, text in rule.get("write", {}).items():
    path = Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
time.sleep(rule.get("sleep", 0))
session = argv[argv.index("--resume") + 1] if "--resume" in argv else rule.get("session", "sess-1")
log(prompt, "agent")
out({"result": rule.get("result", "Done."), "session_id": session, "total_cost_usd": 0.1,
     "num_turns": 2})
"""


def _fake(tmp_path: Path, config: dict[str, Any]) -> tuple[str, Path]:
    home = tmp_path / "fake"
    home.mkdir()
    (home / "config.json").write_text(json.dumps(config))
    binary = home / "claude"
    binary.write_text(f"#!{sys.executable}\n{_FAKE}")
    binary.chmod(0o755)
    return str(binary), home


def _log(home: Path, role: str = "agent") -> list[dict[str, Any]]:
    lines = (home / "log.jsonl").read_text().splitlines() if (home / "log.jsonl").exists() else []
    return [e for e in map(json.loads, lines) if e["role"] == role]


def _opts(saga: ModuleType, tmp_path: Path, claude: str, home: Path, **extra: Any) -> Any:
    return saga.Options(
        out=tmp_path / "out",
        claude_bin=claude,
        model="m",
        sim_model="s",
        transcript_root=tmp_path / "transcripts",
        grade=False,
        quiz=False,
        **extra,
    )


def _session(saga: ModuleType, **fields: Any) -> Any:
    base: dict[str, Any] = {"id": "S1", "prompt": "Add alarms.", "hidden": "S1"}
    return saga.Session(**{**base, **fields})


def _work(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    (work / "remind").mkdir(parents=True)
    (work / "tests").mkdir()
    return work


# --- AC-001 -------------------------------------------------------------------------------------


def test_ac_001_fixture_checks_and_hashes_unchanged(saga: ModuleType, tmp_path: Path) -> None:
    assert saga.check_fixture(_SAGA) == []
    copy = tmp_path / "saga"
    shutil.copytree(_SAGA, copy)
    (copy / "hidden" / "S5" / "test_extra.py").write_text("def test_always():\n    pass\n")
    problems = saga.check_fixture(copy)
    assert any("test_always" in p for p in problems)
    bench = _load("bench_light_lane")
    assert (bench.bench_hash(), bench.tier2_hash(), bench.tier3_hash()) == (
        "92672094f80e",
        "1cf707c57e12",
        "1f8767cb8b8c",
    )


# --- AC-002 -------------------------------------------------------------------------------------


def test_ac_002_prompts_per_arm(saga: ModuleType) -> None:
    task = _session(saga, prompt="Add alarms.")
    resume = _session(saga, id="S4r", prompt=RESUME_PROMPT, resume_of="S4")
    assert saga.prompt_for(task, "plain") == "Add alarms."
    assert saga.prompt_for(task, "plain-discipline") == f"Add alarms.\n\n{DISCIPLINE}"
    assert saga.prompt_for(task, "hm") == "/hm:spec Add alarms."
    for arm in ("plain", "plain-discipline", "hm"):
        assert saga.prompt_for(resume, arm) == RESUME_PROMPT
    shipped = saga.load_saga(_SAGA)
    assert next(s for s in shipped.sessions if s.id == "S4r").prompt == RESUME_PROMPT


# --- AC-003 -------------------------------------------------------------------------------------


def test_ac_003_owner_loop_resumes_and_caps(saga: ModuleType, tmp_path: Path) -> None:
    config = {
        "agent": [{"match": "", "result": "Which colour should alarms use?", "session": "abc"}],
        "reply": [
            {"reply": "Use your judgment.", "delivered": [], "approved": False, "observed": []}
        ],
    }
    claude, home = _fake(tmp_path, config)
    record = saga.run_session(
        _session(saga),
        "plain",
        _work(tmp_path),
        _opts(saga, tmp_path, claude, home),
        tmp_path / "run",
    )
    calls = _log(home)
    assert len(calls) == 4
    assert all("--resume" not in c["argv"] for c in calls[:1])
    for call in calls[1:]:
        assert call["argv"][call["argv"].index("--resume") + 1] == "abc"
        assert call["prompt"] == "Use your judgment."
    assert len([t for t in record["turns"] if t.get("sim")]) == 3


# --- AC-004 -------------------------------------------------------------------------------------


def _c1_session(saga: ModuleType) -> Any:
    fact = saga.Fact(
        id="C1",
        when="approval",
        text="Cap at 52.",
        must_deliver=True,
        posthoc="One more thing: cap at 52.",
    )
    return _session(saga, facts=(fact,))


def test_ac_004_correction_sent_once_when_undelivered(saga: ModuleType, tmp_path: Path) -> None:
    silent: dict[str, Any] = {"reply": None, "delivered": [], "approved": False, "observed": []}
    config = {"agent": [{"match": "", "result": "Done."}], "reply": [silent]}
    claude, home = _fake(tmp_path, config)
    record = saga.run_session(
        _c1_session(saga),
        "plain",
        _work(tmp_path),
        _opts(saga, tmp_path, claude, home),
        tmp_path / "run",
    )
    prompts = [c["prompt"] for c in _log(home)]
    assert prompts == ["Add alarms.", "One more thing: cap at 52."]
    assert record["c1"]["delivered_by"] == "posthoc"

    tmp2 = tmp_path / "second"
    tmp2.mkdir()
    told = {"reply": "Cap it at 52 please.", "delivered": ["C1"], "approved": False, "observed": []}
    claude2, home2 = _fake(tmp2, {"agent": config["agent"], "reply": [told, silent]})
    record2 = saga.run_session(
        _c1_session(saga),
        "plain",
        _work(tmp2),
        _opts(saga, tmp2, claude2, home2),
        tmp2 / "run",
    )
    prompts2 = [c["prompt"] for c in _log(home2)]
    assert prompts2 == ["Add alarms.", "Cap it at 52 please."]
    assert record2["c1"]["delivered_by"] == "simulator"
    assert record2["c1"]["before_code"] is True


# --- AC-005 -------------------------------------------------------------------------------------

_APPROVED_YAML = "spec_slug: alarm\napproval:\n  approved_at: '2026-11-25T00:00:00Z'\n"


def test_ac_005_hm_walks_execute_and_wrapup(saga: ModuleType, tmp_path: Path) -> None:
    silent: dict[str, Any] = {"reply": None, "delivered": [], "approved": False, "observed": []}
    write = {
        ".worktrees/x/specs/SPEC-alarm.md": "# SPEC\n",
        ".worktrees/x/specs/SPEC-alarm.machine.yaml": _APPROVED_YAML,
    }
    config = {
        "agent": [
            {"match": "/hm:spec", "write": write, "result": "SPEC approved."},
            {"match": "", "result": "Done."},
        ],
        "reply": [silent],
    }
    claude, home = _fake(tmp_path, config)
    saga.run_session(
        _session(saga),
        "hm",
        _work(tmp_path),
        _opts(saga, tmp_path, claude, home),
        tmp_path / "run",
    )
    assert [c["prompt"] for c in _log(home)] == [
        "/hm:spec Add alarms.",
        "/hm:execute alarm",
        "/hm:wrapup alarm",
    ]

    tmp2 = tmp_path / "nospec"
    tmp2.mkdir()
    claude2, home2 = _fake(tmp2, {"agent": [{"match": "", "result": "Hm."}], "reply": [silent]})
    saga.run_session(
        _session(saga), "hm", _work(tmp2), _opts(saga, tmp2, claude2, home2), tmp2 / "run"
    )
    assert [c["prompt"] for c in _log(home2)] == ["/hm:spec Add alarms."]

    tmp3 = tmp_path / "unapproved"
    tmp3.mkdir()
    draft = {".worktrees/x/specs/SPEC-alarm.md": "# SPEC\n"}
    claude3, home3 = _fake(
        tmp3, {"agent": [{"match": "", "write": draft, "result": "Approve?"}], "reply": [silent]}
    )
    saga.run_session(
        _session(saga), "hm", _work(tmp3), _opts(saga, tmp3, claude3, home3), tmp3 / "run"
    )
    assert [c["prompt"] for c in _log(home3)] == ["/hm:spec Add alarms."]


# --- AC-006 -------------------------------------------------------------------------------------


def test_ac_006_parallel_overlap_and_interrupt_resume(saga: ModuleType, tmp_path: Path) -> None:
    silent: dict[str, Any] = {"reply": None, "delivered": [], "approved": False, "observed": []}
    config = {
        "agent": [
            {"match": "colour", "sleep": 2, "session": "a"},
            {"match": "rename", "sleep": 2, "session": "b"},
            {
                "match": "time zone",
                "write": {"remind/x.py": "x = 1\n"},
                "sleep": 60,
                "session": "c",
            },
            {"match": "", "session": "d"},
        ],
        "reply": [silent],
    }
    claude, home = _fake(tmp_path, config)
    sessions = (
        _session(saga, id="S3a", prompt="Add colour.", hidden="S3a", parallel="S3"),
        _session(saga, id="S3b", prompt="Do the rename.", hidden="S3b", parallel="S3"),
        _session(saga, id="S4", prompt="Add a time zone.", hidden="S4", interrupt=True),
        _session(saga, id="S4r", prompt=RESUME_PROMPT, hidden="S4", resume_of="S4"),
    )
    plan = saga.Saga(sessions=sessions, quiz=())
    opts = _opts(saga, tmp_path, claude, home, interrupt_delay_s=1.0)
    started = time.monotonic()
    records = saga.run_sessions(plan, "plain", _work(tmp_path), opts, tmp_path / "run")
    assert time.monotonic() - started < 40
    calls = {c["prompt"]: c for c in _log(home)}
    a, b = calls["Add colour."], calls["Do the rename."]
    assert a["start"] < b["end"]
    assert b["start"] < a["end"]
    assert records["S4"]["interrupted"] is True
    assert records["S4"]["wall_s"] < 20
    resumed = calls[RESUME_PROMPT]
    assert "--resume" not in resumed["argv"]
    assert "--continue" not in resumed["argv"]


# --- AC-007 -------------------------------------------------------------------------------------


def _passed(*names: str) -> dict[str, str]:
    return dict.fromkeys(names, "passed")


def test_ac_007_trap_verdicts_golden(saga: ModuleType) -> None:
    run = {
        "sessions": {
            "S1": {
                "status": "ok",
                "hidden": {
                    "test_weekly_occurrences": "passed",
                    "test_h1_one_entry_per_repeating_reminder": "failed",
                    "test_c1_count_capped_at_52": "passed",
                },
                "c1": {"delivered_by": "simulator", "before_code": True},
                "frozen_changed": False,
                "e1_seen": True,
            },
            "S2": {
                "status": "ok",
                "hidden": {
                    "test_irr_top_level_unchanged": "passed",
                    "test_h1_kept_on_import": "failed",
                },
                "frozen_changed": True,
                "e1_seen": False,
            },
            "S3a": {
                "status": "ok",
                "hidden": _passed("test_a1", "test_a2"),
                "visible_ok": True,
                "frozen_changed": False,
                "e1_seen": False,
            },
            "S3b": {
                "status": "ok",
                "hidden": {"test_b1": "passed", "test_b2": "failed"},
                "visible_ok": True,
                "frozen_changed": False,
                "e1_seen": True,
            },
            "S4": {
                "status": "ok",
                "hidden": {"test_t1": "failed"},
                "interrupted": True,
                "frozen_changed": False,
                "e1_seen": False,
                "duplicates_before": 1,
            },
            "S4r": {
                "status": "ok",
                "hidden": _passed("test_t1"),
                "duplicates": 1,
                "frozen_changed": False,
                "e1_seen": False,
            },
        }
    }
    assert saga.score_traps(run) == {
        "H1": False,
        "C1": True,
        "C1_before_code": True,
        "IRR": True,
        "H1_kept": None,
        "frozen": False,
        "parallel": False,
        "resume": True,
        "no_dependency": None,
        "E1_no_recurrence": False,
    }


# --- AC-008 -------------------------------------------------------------------------------------


def _row(arm: str, true: range) -> dict[str, Any]:
    return {"arm": arm, "status": "ok", "traps": {f"T{i}": i in true for i in range(10)}}


def test_ac_008_verdict_and_validator(saga: ModuleType, tmp_path: Path) -> None:
    # hm 0.75 vs discipline 0.50 over 10 traps: lead 0.25, hm ahead on T0-T4 (5 traps).
    lead_rows = [
        _row("hm", range(8)),
        _row("hm", range(7)),
        _row("plain-discipline", range(5, 10)),
        _row("plain-discipline", range(5, 10)),
    ]
    assert saga.verdict(lead_rows, margin=0.2, min_traps=4) == "hm_unique"
    assert saga.verdict(lead_rows, margin=0.2, min_traps=6) == "reproduced"
    # hm 0.6 vs discipline 0.5: lead 0.1.
    close_rows = [_row("hm", range(6)), _row("plain-discipline", range(5))]
    assert saga.verdict(close_rows, margin=0.2, min_traps=1) == "reproduced"

    root = tmp_path / "saga"
    (root / "validator").mkdir(parents=True)
    shutil.copytree(_SAGA / "repo", root / "repo")
    for name in ("SPEC-cap.md", "SPEC-done-all.md"):
        shutil.copy(_SAGA / "validator" / name, root / "validator" / name)
    key = json.loads((_SAGA / "validator" / "key.json").read_text())
    (root / "validator" / "key.json").write_text(
        json.dumps({k: key[k] for k in ("cap", "done-all")})
    )
    grade = {"detected": True, "serious_defect_claimed": False}
    claude, home = _fake(
        tmp_path, {"agent": [{"match": "", "result": "AC-001 vs AC-002."}], "detected": [grade]}
    )
    opts = _opts(saga, tmp_path, claude, home)
    rows = saga.run_validator(opts, arms=("plain-review",), reps=2, root=root)
    assert len(rows) == 4
    summary = saga.validator_summary(rows)
    assert summary["plain-review"]["detected"] == (2, 2)
    assert summary["plain-review"]["false_alarms"] == (0, 2)
