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
    role = next(r for r in ("reply", "answers", "correct", "detected", "maintainability")
                if r in schema["properties"])
    counter = home / f"count-{role}"
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    answers = cfg[role]
    data = answers[min(n, len(answers) - 1)]
    log(sys.stdin.read(), role)
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
        # 1 FAILED mark in 5 later sessions (SPEC-saga-pilot-fixes: fewer than half passes).
        "E1_no_recurrence": True,
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


# --- SPEC-saga-pilot-fixes ----------------------------------------------------------------------


def test_pilot_ac_001_interrupt_delay_default(saga: ModuleType, tmp_path: Path) -> None:
    assert saga.Options(out=tmp_path).interrupt_delay_s == 5.0
    assert saga.build_parser().parse_args(["run", "--out", "x"]).interrupt_delay_s == 5.0


def test_pilot_ac_002_owner_keeps_earlier_facts(saga: ModuleType, tmp_path: Path) -> None:
    shipped = saga.load_saga(_SAGA)
    order = [s.id for s in shipped.sessions]
    before_s2 = shipped.sessions[: order.index("S2")]
    carried = saga.carried_facts(before_s2)
    assert [f.id for f in carried] == ["H1", "C1", "F1"]
    assert all(f.when == "asked" and not f.must_deliver for f in carried)
    groups = {tuple(s.id for s in g): g for g in saga._groups(shipped.sessions)}
    # The parallel group carries S1 and S2 only, never one member's facts into the other.
    assert [f.id for f in saga.group_carried(shipped, groups[("S3a", "S3b")])] == [
        "H1", "C1", "F1", "F3", "F4",
    ]  # fmt: skip
    assert [f.id for f in saga.group_carried(shipped, groups[("S4r",)])] == [
        "H1", "C1", "F1", "F3", "F4", "F5", "F6",
    ]  # fmt: skip

    told = {"reply": "One entry, please.", "delivered": ["H1"], "approved": False, "observed": []}
    silent: dict[str, Any] = {"reply": None, "delivered": [], "approved": False, "observed": []}
    claude, home = _fake(
        tmp_path,
        {"agent": [{"match": "", "result": "Copies or one entry?"}], "reply": [told, silent]},
    )
    record = saga.run_session(
        _session(saga, id="S2"),
        "plain",
        _work(tmp_path),
        _opts(saga, tmp_path, claude, home),
        tmp_path / "run",
        carried=tuple(carried),
    )
    stdin = sorted((tmp_path / "run" / "calls").glob("S2-01-task-owner*.stdin"))
    assert stdin
    assert "Our phone app syncs" in stdin[0].read_text()
    assert record["delivered"]["H1"]["carried"] is True
    prompts = [c["prompt"] for c in _log(home)]
    assert prompts == ["Add alarms.", "One entry, please."]


def _resume_run(s4r_delivered: dict[str, Any], e1_later: list[bool]) -> dict[str, Any]:
    """S1 plus later sessions S2, S3a, S3b, S4r with the given E1 marks; S4 was cut off and
    shows a mark that must not count."""
    sessions: dict[str, Any] = {
        "S1": {"status": "ok", "hidden": {}, "e1_seen": True},
        "S2": {"status": "ok", "hidden": {}},
        "S3a": {"status": "ok", "hidden": {}},
        "S3b": {"status": "ok", "hidden": {}},
        "S4": {"status": "interrupted", "hidden": {}, "interrupted": True,
               "duplicates_before": 0, "e1_seen": True},
        "S4r": {"status": "ok", "hidden": {"t": "passed"}, "duplicates": 0,
                "delivered": s4r_delivered},
    }  # fmt: skip
    for sid, seen in zip(["S2", "S3a", "S3b", "S4r"], e1_later, strict=True):
        sessions[sid]["e1_seen"] = seen
    return {"sessions": sessions}


def test_pilot_ac_003_resume_and_e1(saga: ModuleType) -> None:
    own = {"F7": {"delivered_by": "simulator", "before_code": True}}
    carried = {"F6": {"delivered_by": "simulator", "before_code": True, "carried": True}}
    one_of_four = [True, False, False, False]
    two_of_four = [True, True, False, False]
    assert saga.score_traps(_resume_run(own, one_of_four))["resume"] is False
    assert saga.score_traps(_resume_run(carried, one_of_four))["resume"] is True
    assert saga.score_traps(_resume_run({}, one_of_four))["E1_no_recurrence"] is True
    assert saga.score_traps(_resume_run({}, two_of_four))["E1_no_recurrence"] is False


def test_pilot_ac_004_verdict_skips_saturated(saga: ModuleType) -> None:
    assert saga.SATURATED == ("IRR", "frozen", "no_dependency", "parallel", "H1_kept")
    active = {"hm": range(5), "plain-discipline": range(2)}  # hm leads on T2-T4: 0.6 over 5

    def rows(with_saturated: bool) -> list[dict[str, Any]]:
        out = []
        for arm, true in active.items():
            traps = {f"T{i}": i in true for i in range(5)}
            if with_saturated:
                # hm "loses" every saturated trap; the verdict must not see it.
                traps |= dict.fromkeys(saga.SATURATED, arm != "hm")
            out.append({"arm": arm, "status": "ok", "traps": traps})
        return out

    assert saga.verdict(rows(False)) == "hm_unique"
    assert saga.verdict(rows(True)) == "hm_unique"
    text = saga.report(rows(True))
    for trap in saga.SATURATED:
        line = next(ln for ln in text.splitlines() if ln.startswith(trap))
        assert "saturated" in line
    assert "saturated" not in next(ln for ln in text.splitlines() if ln.startswith("T0"))
    assert "min traps 3" in text


# --- SPEC-owner-attention-metrics ---------------------------------------------------------------


def test_owner_ac_001_attention_from_turns(saga: ModuleType) -> None:
    record = {
        "turns": [
            {"kind": "task", "message": "a" * 10,
             "sim": {"reply": "Approved, go ahead.", "approved": True}},
            {"kind": "reply", "message": "b" * 10, "sim": {"reply": None, "approved": False}},
            {"kind": "execute", "message": "", "sim": {"reply": "  ", "approved": False}},
            {"kind": "posthoc", "message": "c" * 10},
        ]
    }  # fmt: skip
    assert saga.attention(record) == {"read_chars": 30, "replies": 2, "approvals": 1}
    assert saga.attention({**record, "doc_chars": 5})["read_chars"] == 35


def test_owner_ac_002_doc_chars(saga: ModuleType, tmp_path: Path) -> None:
    work = _work(tmp_path)
    specs = work / "specs"
    specs.mkdir()
    spec_md = "# SPEC\n\nAC-001: x\n"
    (specs / "SPEC-x.md").write_text(spec_md)
    (specs / "SPEC-x.machine.yaml").write_text("spec_slug: x\n")
    unapproved_chars = saga.doc_chars(work, "hm", "x")
    (specs / "SPEC-x.machine.yaml").write_text("approval:\n  approved_at: '2026-11-28'\n")
    approved_chars = saga.doc_chars(work, "hm", "x")
    assert (approved_chars, unapproved_chars) == (len(spec_md), 0)
    assert saga.doc_chars(work, "plain", "x") == 0
    assert saga.doc_chars(work, "hm", None) == 0


def test_owner_ac_003_escaped_regressions(
    saga: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hidden = tmp_path / "hidden"
    (hidden / "S1").mkdir(parents=True)
    (hidden / "S4").mkdir()
    (hidden / "conftest.py").write_text("")
    (hidden / "S1" / "test_s1.py").write_text(
        "import remind\n\ndef test_a():\n    assert remind.X == 1\n\n"
        "def test_b():\n    assert remind.X == 3\n\n"
        "def test_d():\n    assert remind.X in (1, 2)\n"
    )
    (hidden / "S4" / "test_s4.py").write_text(
        "import remind\n\ndef test_c():\n    assert remind.X == 1\n"
    )
    work = _work(tmp_path)
    (work / "remind" / "__init__.py").write_text("X = 1\n")
    at_s1 = saga.grade_hidden(work, hidden, "S1")
    at_s4 = saga.grade_hidden(work, hidden, "S4")
    assert sorted(at_s1.values()) == ["failed", "passed", "passed"]
    (work / "remind" / "__init__.py").write_text("X = 2\n")
    records = {
        "S1": {"hidden": at_s1},
        "S4": {"hidden": at_s4, "interrupted": True},
        "S5": {"status": "ok"},
    }
    name_a = next(k for k in at_s1 if k.endswith("test_a"))
    name_c = next(k for k in at_s4 if k.endswith("test_c"))
    assert saga.escaped_regressions(records, work, hidden) == [f"S1::{name_a}"]
    # S4r grades S4's dir; a final run that itself failed (timeout) is unknown, not a regression.
    records["S4r"] = {"hidden": at_s4, "hidden_dir": "S4"}
    assert saga.escaped_regressions(records, work, hidden) == [f"S1::{name_a}", f"S4::{name_c}"]
    real = saga.grade_hidden
    monkeypatch.setattr(saga, "grade_hidden", lambda w, h, n: (
        {"<run>": "error"} if n == "S4" else real(w, h, n)))  # fmt: skip
    assert saga.escaped_regressions(records, work, hidden) == [f"S1::{name_a}"]


def _owner_row(arm: str, escaped: list[str] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "arm": arm, "status": "ok", "quiz_mean": 0.8,
        "sessions": {
            "S1": {"hidden": {"t": "passed"}, "turns": [
                {"kind": "task", "message": "m" * 100, "sim": {"reply": "ok", "approved": True}}]},
            "S2": {"hidden": {"t": "failed"}, "turns": [
                {"kind": "task", "message": "m" * 50, "sim": {"reply": None, "approved": False}}]},
            "S4": {"hidden": {"t": "passed"}, "interrupted": True, "turns": [
                {"kind": "task", "message": "m" * 10}]},
        },
    }  # fmt: skip
    if escaped is not None:
        row["escaped"] = escaped
    return row


def test_owner_ac_004_owner_summary(saga: ModuleType) -> None:
    rows = [_owner_row("hm"), _owner_row("hm"), _owner_row("plain", ["S1::t"]),
            {"arm": "plain", "status": "runner_error"}]  # fmt: skip
    old = saga.owner_summary(rows)
    assert old["hm"] == {
        "runs": 2, "shipped": 1.0, "read_per_ship": 160.0, "replies_per_ship": 1.0,
        "approvals_per_ship": 1.0, "quiz": 0.8, "escaped": None, "docs_counted": False,
    }  # fmt: skip
    assert old["plain"]["docs_counted"] is True
    assert old["hm"]["escaped"] is None
    assert old["plain"]["runs"] == 1
    assert old["plain"]["escaped"] == 1.0
    text = saga.report(rows)
    assert "owner" in text
    assert "read/ship" in text
    assert "SPEC documents not counted: hm" in text


def test_owner_ac_005_judge(saga: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "saga"
    shutil.copytree(_SAGA / "repo", root / "repo")
    shutil.copy(_SAGA / "saga.json", root / "saga.json")
    first = dict.fromkeys(saga.JUDGE_AXES, "first")
    second = dict.fromkeys(first, "second")
    claude, home = _fake(tmp_path, {
        "agent": [{"match": ""}],
        "maintainability": [{**first, "reason": "r"}, {**second, "reason": "r"},
                            {**first, "reason": "r"}, {**first, "reason": "r"}],
    })  # fmt: skip
    opts = _opts(saga, tmp_path, claude, home, root=root)
    opts.out.mkdir(parents=True)
    rows = []
    for arm in ("hm", "plain"):
        for rep in (1, 2):
            run_dir = opts.out / "runs" / f"{arm}-{rep}"
            shutil.copytree(root / "repo", run_dir / "work")
            (run_dir / "work" / "remind" / "extra.py").write_text(f"CELL = '{arm}-{rep}'\n")
            rows.append({"arm": arm, "rep": rep, "status": "ok", "run_dir": str(run_dir)})
    (opts.out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    judged = saga.run_judge(opts, "opus")
    assert [(r["other"], r["rep"]) for r in judged] == [("plain", 1), ("plain", 2)]
    row = judged[0]
    assert row["axes"]["maintainability"] == "A"
    assert judged[1]["axes"]["maintainability"] == "split"
    calls = [c["prompt"] for c in _log(home, "maintainability")]
    assert len(calls) == 4
    for n, rep in ((0, 1), (2, 2)):  # hm first, then hm second, on the same rep
        hm_at, other_at = calls[n].index(f"'hm-{rep}'"), calls[n].index(f"'plain-{rep}'")
        assert hm_at < other_at
        assert calls[n + 1].index(f"'plain-{rep}'") < calls[n + 1].index(f"'hm-{rep}'")
    assert saga.read_rows(opts.out / "judge.jsonl") == judged
    summary = saga.judge_summary(judged)
    assert summary["plain"]["maintainability"] == (1, 0)
    assert summary["plain"]["overall"] == (1, 0)
    assert (summary["plain"]["n"], summary["plain"]["failed"]) == (2, 0)
    # A second run judges nothing new.
    assert saga.run_judge(opts, "opus") == []
    assert len(_log(home, "maintainability")) == 4
