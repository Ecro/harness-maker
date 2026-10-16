"""SPEC-autopilot-stop-gate: the Stop hook refuses once when a turn authorized a stage it never ran.

AC-001 is the golden state table, AC-002 the differential against the df070f6c loop gate, AC-003
the replay of the 35 eval-2 hm runs (fixtures in `tests/fixtures/autopilot_stop_gate/`, reduced as
`manifest.json` describes), AC-004 the reason text.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import harness_maker
from harness_maker import autopilot, autopilot_ledger
from harness_maker.hooks import loop_gate
from harness_maker.loop_marker import format_marker_content
from harness_maker.models import AtomicStage, OperationalLevel

_REPO = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO / "tests" / "fixtures" / "autopilot_stop_gate"
_REFERENCE_REV = "df070f6c"

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
SID = "5dc15c88-0324-452e-8cf5-45963e7c6062"
PEER = "0a1b2c3d-0000-4000-8000-00000000beef"
PIPELINE = ["research", "spec", "execute", "review", "verify", "wrapup"]
LOOP_REASON = (
    "/hm:loop is active for this session. To exit the loop early, "
    "remove this session's .claude/.hm-loop-* marker."
)


def _at(minutes_before_now: float) -> str:
    return (NOW - timedelta(minutes=minutes_before_now)).isoformat()


def _z(minutes_before_now: float) -> str:
    """A transcript timestamp: millisecond precision with a `Z`, as Claude Code writes it."""
    moment = NOW - timedelta(minutes=minutes_before_now)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


# ── transcript records (the shapes observed in the eval-2 transcripts) ───────


def user_prompt(m: float) -> dict[str, Any]:
    return {"type": "user", "timestamp": _z(m), "message": {"role": "user", "content": "go on"}}


def meta_text(m: float) -> dict[str, Any]:
    return {
        "type": "user",
        "timestamp": _z(m),
        "isMeta": True,
        "message": {"role": "user", "content": [{"type": "text", "text": "skill body"}]},
    }


def tool_result(m: float) -> dict[str, Any]:
    return {
        "type": "user",
        "timestamp": _z(m),
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}],
        },
        "toolUseResult": {"stdout": "ok"},
    }


def task_notification(m: float) -> dict[str, Any]:
    return {
        "type": "user",
        "timestamp": _z(m),
        "origin": {"kind": "task-notification", "producer": "session-task"},
        "message": {"role": "user", "content": "<task-notification>done</task-notification>"},
    }


def assistant_text(m: float) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": _z(m),
        "message": {"role": "assistant", "content": [{"type": "text", "text": "SPEC written."}]},
    }


def skill_call(m: float, stage: str) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": _z(m),
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "Skill",
                    "input": {"skill": f"hm:{stage}"},
                }
            ],
        },
    }


def skill_at(timestamp: str, skill: str = "hm:execute") -> dict[str, Any]:
    """A `Skill` call with a literal timestamp and skill string."""
    record = skill_call(0, "execute")
    record["timestamp"] = timestamp
    record["message"]["content"][0]["input"] = {"skill": skill}
    return record


def queued_command(m: float | None) -> dict[str, Any]:
    record: dict[str, Any] = {"type": "attachment", "attachment": {"type": "queued_command"}}
    if m is not None:
        record["timestamp"] = _z(m)
    return record


def authorized(stage: str, m: float = 5) -> dict[str, Any]:
    return {"to": stage, "ts": _at(m), "event": "advance_authorized"}


def entered(stage: str, m: float = 4) -> dict[str, Any]:
    return {"to": stage, "elapsed_s": 60.0, "ts": _at(m), "event": "advance_entered"}


# ── one project on disk ──────────────────────────────────────────────────────


@dataclass
class World:
    """Marker, ledger, transcript and payload for one Stop-hook call; mutated per case."""

    root: Path
    marker: str | None = "own"  # own | gated | foreign | expired | None
    marker_created_m: float = 30
    pipeline: list[str] = field(default_factory=lambda: list(PIPELINE))
    task_slug: str | None = None
    peer: str | None = None  # live | fresh-unseen | idle | gated | idless | old
    ledger: list[dict[str, Any]] | None = field(default_factory=lambda: [authorized("execute")])
    ledger_prefix_lines: list[str] = field(default_factory=list)
    # The row-1 end state: a prompt before the authorization; after it only the boundary's own
    # tool result and the model's closing text.
    transcript: list[dict[str, Any]] | None = field(
        default_factory=lambda: [user_prompt(20), tool_result(4.9), assistant_text(4.8)]
    )
    transcript_raw: str | None = None
    transcript_key: bool = True
    loop: str | None = None  # own | foreign | global
    session_id: str | None = SID
    stop_hook_active: bool = False

    def build(self) -> str:
        claude = self.root / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (self.root / ".git").mkdir(exist_ok=True)
        if self.marker is not None:
            self._write_marker()
        if self.peer is not None:
            self._write_peer()
        if self.ledger is not None:
            path = autopilot_ledger.ledger_path(self.root)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = [*self.ledger_prefix_lines, *(json.dumps(r) for r in self.ledger)]
            path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        tpath = self.root / "transcript.jsonl"
        if self.transcript_raw is not None:
            tpath.write_text(self.transcript_raw, encoding="utf-8")
        elif self.transcript is not None:
            tpath.write_text(
                "".join(json.dumps(r) + "\n" for r in self.transcript), encoding="utf-8"
            )
        self._write_loop()
        payload: dict[str, Any] = {
            "hook_event_name": "Stop",
            "cwd": str(self.root),
            "stop_hook_active": self.stop_hook_active,
        }
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.transcript_key:
            payload["transcript_path"] = str(tpath)
        return json.dumps(payload)

    def _write_marker(self) -> None:
        level: OperationalLevel = "gated" if self.marker == "gated" else "auto_full"
        created = _at(19 * 60) if self.marker == "expired" else _at(self.marker_created_m)
        owner = PEER if self.marker == "foreign" else SID
        _write_marker_file(
            self.root,
            key=SID,
            claude_session_id=owner,
            created=created,
            level=level,
            pipeline=self.pipeline,
            task_slug=self.task_slug,
        )

    def _write_peer(self) -> None:
        kind = self.peer
        _write_marker_file(
            self.root,
            key=PEER,
            claude_session_id=None if kind == "idless" else PEER,
            created=_at(19 * 60) if kind == "old" else _at(60),
            level="gated" if kind == "gated" else "auto_full",
            last_seen={
                "live": _at(5),
                "idle": _at(45),
                "gated": _at(5),
                "idless": _at(5),
                "future-seen": _at(-60),
            }.get(str(kind)),
        )

    def _write_loop(self) -> None:
        if self.loop is None:
            return
        if self.loop == "global":
            (self.root / ".hm-loop-active").write_text("", encoding="utf-8")
            return
        wt = self.root / ".worktrees" / "execute-1"
        wt.mkdir(parents=True, exist_ok=True)
        owner = SID if self.loop == "own" else PEER
        (self.root / ".claude" / ".hm-loop-execute-1").write_text(
            format_marker_content(owner, [wt]), encoding="utf-8"
        )


def _write_marker_file(
    root: Path,
    *,
    key: str,
    claude_session_id: str | None,
    created: str,
    level: OperationalLevel = "auto_full",
    pipeline: list[str] = PIPELINE,
    task_slug: str | None = None,
    last_seen: str | None = None,
) -> None:
    """Write a marker at `key`'s path holding `claude_session_id`; they differ for a foreign one."""
    marker = autopilot.AutopilotMarker(
        session_uuid="0123456789ab",
        level=level,
        pipeline=[AtomicStage(s) for s in pipeline],
        created_at=created,
        claude_session_id=claude_session_id,
        task_slug=task_slug,
        last_seen=last_seen,
    )
    path = autopilot.marker_path(root, session_id=key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(marker.model_dump_json(), encoding="utf-8")


@dataclass
class Outcome:
    code: int
    out: str
    err: str


def _capture(call: Callable[[], int]) -> Outcome:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = call()
    return Outcome(code, out.getvalue(), err.getvalue())


def _run(payload: str, *, now: datetime = NOW) -> Outcome:
    """The module under test, always on a fixed clock."""
    return _capture(lambda: loop_gate._stop_hook(payload, now=now))


def _run_reference(reference: ModuleType, payload: str) -> Outcome:
    """The df070f6c module, whose `_stop_hook` takes no clock."""
    hook: Callable[[str], int] = reference._stop_hook
    return _capture(lambda: hook(payload))


def _reason(outcome: Outcome) -> str:
    response = json.loads(outcome.out)
    assert response["decision"] == "block", response
    reason = response["reason"]
    assert isinstance(reason, str)
    return reason


def _assert_blocks(outcome: Outcome, stage: str) -> None:
    assert outcome.code == 2, outcome
    reason = _reason(outcome)
    assert f"/hm:{stage}" in reason, reason
    for other in PIPELINE:
        if other != stage:
            assert f"/hm:{other}" not in reason, reason


def _assert_allows(outcome: Outcome) -> None:
    assert (outcome.code, outcome.out) == (0, ""), outcome


def _warn_lines(outcome: Outcome) -> list[str]:
    return [line for line in outcome.err.splitlines() if line.startswith("[loop-gate] warn")]


# ── AC-001: the golden state table ───────────────────────────────────────────

Setup = Callable[[World], None]


def _set(**fields: Any) -> Setup:
    def apply(w: World) -> None:
        for name, value in fields.items():
            setattr(w, name, value)

    return apply


def _append_after(*records: dict[str, Any]) -> Setup:
    def apply(w: World) -> None:
        assert w.transcript is not None
        w.transcript = [*w.transcript, *records]

    return apply


_BLOCK_EXECUTE = ("block", "execute")
_BLOCK_REVIEW = ("block", "review")
_ALLOW = ("allow", None)
_ALLOW_WARN = ("allow_warn", None)
_LOOP = ("loop", None)

GOLDEN: list[tuple[str, Setup, tuple[str, str | None]]] = [
    ("r01-authorized-never-invoked", _set(), _BLOCK_EXECUTE),
    (
        "r02-later-stage-named",
        _set(ledger=[authorized("execute", 8), entered("execute", 7), authorized("review", 5)]),
        _BLOCK_REVIEW,
    ),
    ("r03-skill-called-after", _append_after(skill_call(4.5, "execute")), _ALLOW),
    ("r04-user-entry-after", _append_after(user_prompt(4.5)), _ALLOW),
    ("r05-task-notification-after", _append_after(task_notification(4.5)), _ALLOW),
    (
        "r06-only-meta-and-tool-results-after",
        _append_after(meta_text(4.6), tool_result(4.5), meta_text(4.4)),
        _BLOCK_EXECUTE,
    ),
    ("r07-stop-hook-active", _set(stop_hook_active=True), _ALLOW),
    ("r08-confirmed", _set(ledger=[authorized("execute", 5), entered("execute", 4)]), _ALLOW),
    (
        "r09-rerun-boundary-collapses",
        _set(ledger=[authorized("execute", 6), authorized("execute", 5), entered("execute", 4)]),
        _ALLOW,
    ),
    ("r10a-ledger-absent", _set(ledger=None), _ALLOW),
    ("r10b-ledger-empty", _set(ledger=[]), _ALLOW),
    ("r11-no-marker", _set(marker=None), _ALLOW),
    ("r12-gated-marker", _set(marker="gated"), _ALLOW),
    ("r13-foreign-marker", _set(marker="foreign"), _ALLOW),
    ("r14-expired-marker", _set(marker="expired"), _ALLOW),
    ("r15-peer-armed", _set(peer="live"), _ALLOW),
    ("r15b-peer-without-last-seen-but-fresh", _set(peer="fresh-unseen"), _ALLOW),
    ("r15c-idle-peer", _set(peer="idle"), _BLOCK_EXECUTE),
    ("r15d-gated-peer", _set(peer="gated"), _BLOCK_EXECUTE),
    ("r15e-idless-peer", _set(peer="idless"), _BLOCK_EXECUTE),
    ("r15f-19h-old-peer", _set(peer="old"), _BLOCK_EXECUTE),
    ("r15g-peer-last-seen-in-the-future-falls-back-to-ttl", _set(peer="future-seen"), _ALLOW),
    ("r16-marker-after-authorization", _set(marker_created_m=2), _ALLOW),
    ("r17-stage-outside-pipeline", _set(pipeline=["research", "spec"]), _ALLOW),
    ("r18-loop-precedence", _set(loop="own"), _LOOP),
    ("r19a-no-transcript-path", _set(transcript_key=False), _ALLOW),
    ("r19b-transcript-unreadable", _set(transcript=None), _ALLOW),
    (
        "r20-no-claude-code-record",
        _set(
            transcript=None,
            transcript_raw=(
                '{"type": "session_meta", "timestamp": "2026-10-15T11:50:00Z"}\n'
                '{"type": "event_msg", "timestamp": "2026-10-15T11:56:00Z", "payload": {}}\n'
                '{"type": "user", "timestamp": "2026-10-15T11:57:00Z"}\n'
            ),
        ),
        _ALLOW_WARN,
    ),
    ("r21-garbage-ledger-line", _set(ledger_prefix_lines=["{not json"]), _BLOCK_EXECUTE),
    # ── review round 1 ──
    (
        "b1-skill-before-authorization",
        _set(transcript=[user_prompt(20), skill_call(6, "execute"), tool_result(4.9)]),
        _BLOCK_EXECUTE,
    ),
    (
        "b2-skill-at-the-authorization-instant",
        _append_after(skill_call(5, "execute")),
        _BLOCK_EXECUTE,
    ),
    ("c1-other-hm-skill-after", _append_after(skill_call(4.5, "review")), _BLOCK_EXECUTE),
    ("c2-non-hm-skill-after", _append_after(skill_at(_z(4.5), "simplify")), _BLOCK_EXECUTE),
    ("s1-skill-with-args", _append_after(skill_at(_z(4.5), "hm:execute ratelimit")), _ALLOW),
    ("s2-skill-with-slash", _append_after(skill_at(_z(4.5), "/hm:execute")), _ALLOW),
    ("s3-plugin-namespaced", _append_after(skill_at(_z(4.5), "harness-maker:execute")), _ALLOW),
    ("s4-hyphen-form", _append_after(skill_at(_z(4.5), "hm-execute")), _ALLOW),
    ("s5-longer-name", _append_after(skill_at(_z(4.5), "hm:executor")), _BLOCK_EXECUTE),
    ("s6-stage-only-as-arg", _append_after(skill_at(_z(4.5), "hm:review execute")), _BLOCK_EXECUTE),
    ("s7-bare-stage-name", _append_after(skill_at(_z(4.5), "execute")), _BLOCK_EXECUTE),
    ("s8-other-plugin-stage", _append_after(skill_at(_z(4.5), "other:execute")), _BLOCK_EXECUTE),
    ("s9-longer-hyphen-name", _append_after(skill_at(_z(4.5), "hm:execute-plan")), _BLOCK_EXECUTE),
    (
        "d1-same-second-skill-500us-before",
        _set(
            ledger=[
                {
                    "to": "execute",
                    "ts": "2026-10-15T11:55:00.000500+00:00",
                    "event": "advance_authorized",
                }
            ],
            transcript=[user_prompt(20), skill_at("2026-10-15T11:55:00.000Z")],
        ),
        _BLOCK_EXECUTE,
    ),
    (
        "d2-same-second-skill-500us-after",
        _set(
            ledger=[
                {
                    "to": "execute",
                    "ts": "2026-10-15T11:55:00.000500+00:00",
                    "event": "advance_authorized",
                }
            ],
            transcript=[user_prompt(20), skill_at("2026-10-15T11:55:00.001Z")],
        ),
        _ALLOW,
    ),
    (
        "d3-offset-transcript-after",
        _append_after(skill_at("2026-10-15T13:55:30.000+02:00")),
        _ALLOW,
    ),
    (
        "d4-offset-transcript-before",
        _append_after(skill_at("2026-10-15T12:54:30.000+01:00")),
        _BLOCK_EXECUTE,
    ),
    (
        "d5-naive-ledger-ts-is-utc-skill-after",
        _set(
            ledger=[{"to": "execute", "ts": "2026-10-15T11:55:00", "event": "advance_authorized"}],
            transcript=[user_prompt(20), skill_at("2026-10-15T11:55:30.000Z")],
        ),
        _ALLOW,
    ),
    (
        "d6-naive-ledger-ts-is-utc-skill-before",
        _set(
            ledger=[{"to": "execute", "ts": "2026-10-15T11:55:00", "event": "advance_authorized"}],
            transcript=[user_prompt(20), skill_at("2026-10-15T11:54:30.000Z")],
        ),
        _BLOCK_EXECUTE,
    ),
    ("f1-authorization-10min-in-the-future", _set(ledger=[authorized("execute", -10)]), _ALLOW),
    (
        "f2-authorization-3min-in-the-future",
        _set(ledger=[authorized("execute", -3)]),
        _BLOCK_EXECUTE,
    ),
    ("q1-queued-command-after", _append_after(queued_command(4.5)), _ALLOW),
    (
        "q2-queued-command-before",
        _set(transcript=[user_prompt(20), queued_command(6), tool_result(4.9)]),
        _BLOCK_EXECUTE,
    ),
    ("q3-queued-command-without-timestamp", _append_after(queued_command(None)), _ALLOW),
    (
        "q4-user-record-without-timestamp",
        _append_after({k: v for k, v in user_prompt(0).items() if k != "timestamp"}),
        _ALLOW,
    ),
    (
        "g1-sidechain-user-entry-after",
        _append_after(user_prompt(4.5) | {"isSidechain": True}),
        _BLOCK_EXECUTE,
    ),
    (
        "g2-unparseable-authorization-ts",
        _set(ledger=[{"to": "execute", "ts": "yesterday", "event": "advance_authorized"}]),
        _ALLOW_WARN,
    ),
    (
        "g3-two-pending-latest-named",
        _set(ledger=[authorized("execute", 8), authorized("review", 5)]),
        _BLOCK_REVIEW,
    ),
    (
        "g4-two-pending-latest-named-reversed",
        _set(ledger=[authorized("review", 8), authorized("execute", 5)]),
        _BLOCK_EXECUTE,
    ),
    ("g5-idless-payload-own-key-marker", _set(session_id=None), _ALLOW),
]


@pytest.mark.parametrize(("case_id", "setup", "expected"), GOLDEN, ids=[g[0] for g in GOLDEN])
def test_ac001_golden_state_table(
    tmp_path: Path, case_id: str, setup: Setup, expected: tuple[str, str | None]
) -> None:
    world = World(tmp_path)
    setup(world)
    outcome = _run(world.build())
    kind, stage = expected
    if kind == "block":
        assert stage is not None
        _assert_blocks(outcome, stage)
    elif kind == "loop":
        assert outcome.code == 2, outcome
        assert outcome.out == json.dumps({"decision": "block", "reason": LOOP_REASON}) + "\n"
        assert "Autopilot" not in outcome.err, outcome.err
    else:
        _assert_allows(outcome)
        if kind == "allow_warn":
            assert len(_warn_lines(outcome)) == 1, outcome.err
            assert len(outcome.err.splitlines()) == 1, outcome.err


@pytest.mark.parametrize("target", ["active_marker", "find_unconfirmed_authorization"])
def test_ac001_r22_read_oserror_fails_open_with_one_warn_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """Row 22: the marker or the ledger read raises."""

    def boom(*_a: object, **_kw: object) -> object:
        raise OSError(5, "Input/output error")

    module = autopilot if target == "active_marker" else autopilot_ledger
    monkeypatch.setattr(module, target, boom)
    outcome = _run(World(tmp_path).build())
    _assert_allows(outcome)
    assert len(_warn_lines(outcome)) == 1, outcome.err
    assert len(outcome.err.splitlines()) == 1, outcome.err


def test_block_reason_also_reaches_stderr(tmp_path: Path) -> None:
    """With exit 2 Claude Code hands the model stderr, not stdout (PLAN ADR-008)."""
    outcome = _run(World(tmp_path).build())
    _assert_blocks(outcome, "execute")
    assert _reason(outcome) in outcome.err


def test_task_slug_rides_in_the_reason(tmp_path: Path) -> None:
    world = World(tmp_path, task_slug="ratelimit")
    reason = _reason(_run(world.build()))
    assert 'call the Skill tool with skill "hm:execute" and args "ratelimit".' in reason


def test_no_slug_means_no_args_clause(tmp_path: Path) -> None:
    reason = _reason(_run(World(tmp_path).build()))
    assert 'call the Skill tool with skill "hm:execute".' in reason
    assert "args" not in reason


def test_an_import_failure_fails_open_with_one_warn_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The autopilot modules load inside the guarded path, so a broken import cannot crash it."""
    monkeypatch.delattr(harness_maker, "autopilot")
    monkeypatch.setitem(sys.modules, "harness_maker.autopilot", None)
    outcome = _run(World(tmp_path).build())
    _assert_allows(outcome)
    assert len(_warn_lines(outcome)) == 1, outcome.err
    assert len(outcome.err.splitlines()) == 1, outcome.err


def test_importing_the_hook_does_not_load_the_autopilot_stack() -> None:
    """The loop path and `--mode pretooluse` stay as light as at df070f6c."""
    code = (
        "import sys, harness_maker.hooks.loop_gate\n"
        "heavy = ('harness_maker.autopilot', 'harness_maker.autopilot_ledger',"
        " 'harness_maker.models', 'pydantic')\n"
        "print(sorted(m for m in heavy if m in sys.modules))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


def test_a_transcript_over_the_size_cap_fails_open_with_one_warn_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(loop_gate, "_TRANSCRIPT_CAP_BYTES", 64)
    outcome = _run(World(tmp_path).build())
    _assert_allows(outcome)
    assert len(_warn_lines(outcome)) == 1, outcome.err
    assert len(outcome.err.splitlines()) == 1, outcome.err


def test_undecodable_bytes_do_not_stop_the_read(tmp_path: Path) -> None:
    world = World(tmp_path)
    payload = world.build()
    tpath = tmp_path / "transcript.jsonl"
    tpath.write_bytes(b"\xff\xfe not json\n" + tpath.read_bytes())
    _assert_blocks(_run(payload), "execute")


def _run_cli(root: Path, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR", "HM_HOOK_HOST"}
    }
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.loop_gate", "--mode", "stop-hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=root,
        env=env,
    )


@pytest.mark.parametrize(("owner", "age_minutes"), [(PEER, 30), (SID, 19 * 60)])
def test_a_foreign_or_stale_marker_adds_no_stderr_line(
    tmp_path: Path, owner: str, age_minutes: int
) -> None:
    """`harness_maker.autopilot` logs a warning for both; in the hook process that is stderr."""
    real_now = datetime.now(UTC)
    payload = json.loads(World(tmp_path, marker=None).build())
    _write_marker_file(
        tmp_path,
        key=SID,
        claude_session_id=owner,
        created=(real_now - timedelta(minutes=age_minutes)).isoformat(),
    )
    proc = _run_cli(tmp_path, payload)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")


def test_sidechain_skill_call_does_not_count_as_started(tmp_path: Path) -> None:
    """A subagent's `Skill` call is not this session invoking the stage."""
    call = skill_call(4.5, "execute") | {"isSidechain": True}
    world = World(tmp_path)
    _append_after(call)(world)
    _assert_blocks(_run(world.build()), "execute")


def test_the_cli_entry_point_blocks_on_the_real_clock(tmp_path: Path) -> None:
    """Checklist item 8: the hook as Claude Code runs it, a subprocess reading stdin."""
    real_now = datetime.now(UTC)
    world = World(tmp_path)
    _write_marker_file(
        tmp_path,
        key=SID,
        claude_session_id=SID,
        created=(real_now - timedelta(minutes=30)).isoformat(),
    )
    world.marker = None
    payload = json.loads(world.build())
    row = {
        "to": "execute",
        "ts": (real_now - timedelta(minutes=5)).isoformat(),
        "event": "advance_authorized",
    }
    autopilot_ledger.ledger_path(tmp_path).write_text(json.dumps(row) + "\n", encoding="utf-8")
    after = (real_now - timedelta(minutes=4)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    Path(payload["transcript_path"]).write_text(
        json.dumps(user_prompt(20) | {"timestamp": "2026-01-01T00:00:00.000Z"})
        + "\n"
        + json.dumps(tool_result(0) | {"timestamp": after})
        + "\n",
        encoding="utf-8",
    )
    env = {
        k: v for k, v in os.environ.items() if k not in {"CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR"}
    }
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.loop_gate", "--mode", "stop-hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=tmp_path,
        env=env,
    )
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "/hm:execute" in json.loads(proc.stdout)["reason"]


def test_the_cli_entry_point_stands_down_in_cursor(tmp_path: Path) -> None:
    """The Claude-settings copy exits before any check when Cursor runs it (row 1's state)."""
    real_now = datetime.now(UTC)
    world = World(tmp_path, marker=None, ledger=None)
    payload = json.loads(world.build())
    _write_marker_file(
        tmp_path,
        key=SID,
        claude_session_id=SID,
        created=(real_now - timedelta(minutes=30)).isoformat(),
    )
    row = {
        "to": "execute",
        "ts": (real_now - timedelta(minutes=5)).isoformat(),
        "event": "advance_authorized",
    }
    ledger = autopilot_ledger.ledger_path(tmp_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    (tmp_path / ".cursor").mkdir()
    # A kept 0.62 file stands the Claude copy down only for a marked, runnable entry of the
    # same module (SPEC-hm-overhaul-p1 PR-C review round 1).
    command = (
        f'HM_HOOK_HOST=cursor uv run --with "{tmp_path}" python -m harness_maker.hooks.loop_gate'
    )
    (tmp_path / ".cursor" / "hooks.json").write_text(
        json.dumps({"version": 1, "hooks": {"preToolUse": [{"command": command}]}}),
        encoding="utf-8",
    )
    payload |= {"cursor_version": "2.4.0", "workspace_roots": [str(tmp_path)]}
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"CLAUDE_PROJECT_DIR", "CURSOR_PROJECT_DIR", "HM_HOOK_HOST"}
    }
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.loop_gate", "--mode", "stop-hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=tmp_path,
        env=env,
    )
    assert (proc.returncode, proc.stdout) == (0, ""), (proc.stdout, proc.stderr)


# ── AC-002: the df070f6c loop gate, everywhere nothing refuses ───────────────


@pytest.fixture(scope="module")
def reference_loop_gate() -> ModuleType:
    proc = subprocess.run(
        ["git", "show", f"{_REFERENCE_REV}:src/harness_maker/hooks/loop_gate.py"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    # Fails loudly rather than skipping: a shallow clone would otherwise turn the differential
    # into a vacuous pass (the CI checkout uses full history for the same reason).
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), proc.stderr
    spec = importlib.util.spec_from_loader(f"loop_gate_{_REFERENCE_REV}", loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    exec(compile(proc.stdout, f"loop_gate@{_REFERENCE_REV}", "exec"), module.__dict__)  # noqa: S102
    # The reference must be the code from before this change, not a copy of it.
    assert not hasattr(module, "_autopilot_stop")
    return module


_LOOP_DOMAIN = ["own", "foreign", "global-idless", "global-id", None]
_ACTIVE_DOMAIN = [True, False]
_MARKER_DOMAIN = [None, "gated", "foreign", "expired"]
_LEDGER_DOMAIN = ["absent", "authorized"]
_TRANSCRIPT_DOMAIN = ["absent", "nothing-after"]


def _differential_world(root: Path, cell: tuple[Any, ...]) -> World:
    loop, active, marker, ledger, transcript = cell
    world = World(root, marker=marker, stop_hook_active=active)
    world.loop = {"global-idless": "global", "global-id": "global"}.get(loop, loop)
    if loop == "global-idless":
        world.session_id = None
    if ledger == "absent":
        world.ledger = None
    if transcript == "absent":
        world.transcript = None
        world.transcript_key = False
    return world


_OWN_LEDGER_DOMAIN = ["confirmed", "authorized"]
_OWN_TRANSCRIPT_DOMAIN = ["skill-after", "user-after", "absent"]
_PEER_DOMAIN = [None, "live"]


def _own_marker_world(root: Path, cell: tuple[Any, ...]) -> World:
    """An own active marker in a state that must not refuse; the reference ignores the marker."""
    loop, active, ledger, transcript, peer = cell
    world = _differential_world(root, (loop, active, "own", "authorized", "nothing-after"))
    world.peer = peer
    if ledger == "confirmed":
        world.ledger = [authorized("execute"), entered("execute")]
    if transcript == "skill-after":
        _append_after(skill_call(4.5, "execute"))(world)
    elif transcript == "user-after":
        _append_after(user_prompt(4.5))(world)
    else:
        world.transcript = None
        world.transcript_key = False
    return world


def test_ac002_equals_the_reference_loop_gate_without_a_refusing_state(
    tmp_path: Path, reference_loop_gate: ModuleType
) -> None:
    domain = itertools.product(
        _LOOP_DOMAIN, _ACTIVE_DOMAIN, _MARKER_DOMAIN, _LEDGER_DOMAIN, _TRANSCRIPT_DOMAIN
    )
    differing: list[tuple[Any, ...]] = []
    cells = 0
    for index, cell in enumerate(domain):
        root = tmp_path / f"cell{index:03d}"
        payload = _differential_world(root, cell).build()
        new = _run(payload)
        ref = _run_reference(reference_loop_gate, payload)
        if (new.out, new.code) != (ref.out, ref.code):
            differing.append((cell, ref.code, new.code))
        cells += 1
    own = itertools.product(
        _LOOP_DOMAIN, _ACTIVE_DOMAIN, _OWN_LEDGER_DOMAIN, _OWN_TRANSCRIPT_DOMAIN, _PEER_DOMAIN
    )
    for index, own_cell in enumerate(own):
        root = tmp_path / f"own{index:03d}"
        payload = _own_marker_world(root, own_cell).build()
        new = _run(payload)
        ref = _run_reference(reference_loop_gate, payload)
        if (new.out, new.code) != (ref.out, ref.code):
            differing.append((("own", *own_cell), ref.code, new.code))
        cells += 1
    assert cells == 160 + 120
    assert differing == []


def test_ac002_domain_reaches_both_reference_outcomes(
    tmp_path: Path, reference_loop_gate: ModuleType
) -> None:
    """Guards the differential against a domain where the reference never blocks."""
    codes = set()
    for index, cell in enumerate(
        [("own", False, None, "absent", "absent"), (None, False, None, "absent", "absent")]
    ):
        payload = _differential_world(tmp_path / f"c{index}", cell).build()
        codes.add(_run_reference(reference_loop_gate, payload).code)
    assert codes == {0, 2}


# ── AC-003: replaying the eval-2 hm runs ─────────────────────────────────────

STALLED = {"t5-hm-1", "t5-hm-3", "t7-hm-3", "t10-hm-3", "t11-hm-1"}
#: Observed on the eval-2 fixtures (see `Replay.controls`); a change means the fixtures or the
#: reading of them changed, which is worth a look either way.
CONTROLS = 89


def _cells() -> list[str]:
    manifest = json.loads((_FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    return sorted(manifest["cells"])


def _parse(ts: str) -> datetime:
    moment = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


@dataclass
class Replay:
    cell: str
    ledger: list[str]
    transcript: list[str]

    @classmethod
    def load(cls, cell: str) -> Replay:
        base = _FIXTURES / cell
        return cls(
            cell,
            (base / "auto-advance.jsonl").read_text(encoding="utf-8").splitlines(),
            (base / "transcript.jsonl").read_text(encoding="utf-8").splitlines(),
        )

    def first_row(self) -> datetime:
        return min(_parse(json.loads(line)["ts"]) for line in self.ledger)

    def records(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.transcript]

    def rows(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.ledger]

    def skill_cuts(self) -> Iterator[tuple[datetime, str]]:
        for record in self.records():
            if record["type"] != "assistant":
                continue
            for block in record["message"]["content"] or []:
                if block.get("name") == "Skill":
                    yield _parse(record["timestamp"]), block["input"]["skill"]

    def controls(self) -> Iterator[tuple[datetime, str]]:
        """Cuts 1 ms before each `Skill(hm:<stage>)` that must block, by this test's own reading.

        Eligible when, up to the cut, the stage's last ledger row is an authorization (no entry
        after it) and nothing between that authorization and the cut gave the person the floor:
        no non-meta, non-tool-result user record and no queued command.
        """
        rows, records = self.rows(), self.records()
        for skill_ts, skill in self.skill_cuts():
            stage = skill.removeprefix("hm:")
            cut = skill_ts - timedelta(milliseconds=1)
            mine = [r for r in rows if r.get("to") == stage and _parse(r["ts"]) <= cut]
            if not mine or mine[-1]["event"] != "advance_authorized":
                continue
            entered_at = [i for i, r in enumerate(mine) if r["event"] == "advance_entered"]
            first_open = mine[entered_at[-1] + 1 if entered_at else 0]
            since = _parse(first_open["ts"])
            if any(self._gives_floor(r) and since < _parse(r["timestamp"]) <= cut for r in records):
                continue
            yield cut, stage

    @staticmethod
    def _gives_floor(record: dict[str, Any]) -> bool:
        if record["type"] == "attachment":
            return True
        if record["type"] != "user" or record.get("isMeta"):
            return False
        content = record["message"]["content"]
        return not (
            isinstance(content, list)
            and content
            and all(b["type"] == "tool_result" for b in content)
        )

    def run(self, root: Path, cut: datetime | None = None) -> Outcome:
        """An own active marker created before the first row; `cut` drops everything after it."""
        created = self.first_row() - timedelta(minutes=1)
        _write_marker_file(root, key=SID, claude_session_id=SID, created=created.isoformat())
        (root / ".git").mkdir(exist_ok=True)
        ledger = [
            line for line in self.ledger if cut is None or _parse(json.loads(line)["ts"]) <= cut
        ]
        transcript = [
            line
            for line in self.transcript
            if cut is None or _parse(json.loads(line)["timestamp"]) <= cut
        ]
        path = autopilot_ledger.ledger_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{line}\n" for line in ledger), encoding="utf-8")
        tpath = root / "transcript.jsonl"
        tpath.write_text("".join(f"{line}\n" for line in transcript), encoding="utf-8")
        payload = json.dumps(
            {
                "session_id": SID,
                "transcript_path": str(tpath),
                "cwd": str(root),
                "stop_hook_active": False,
                "hook_event_name": "Stop",
            }
        )
        return _run(payload, now=created + timedelta(hours=2))


def test_ac003_fixture_set_is_the_35_runs_with_a_ledger() -> None:
    cells = _cells()
    assert len(cells) == 35
    assert set(cells) >= STALLED
    assert "t4-hm-1" in cells
    assert "t12-hm-2" not in cells
    for cell in cells:
        assert (_FIXTURES / cell / "auto-advance.jsonl").is_file()
        assert (_FIXTURES / cell / "transcript.jsonl").is_file()


@pytest.mark.parametrize("cell", _cells())
def test_ac003_replay_at_run_end(tmp_path: Path, cell: str) -> None:
    outcome = Replay.load(cell).run(tmp_path)
    assert _warn_lines(outcome) == [], outcome.err
    if cell in STALLED:
        _assert_blocks(outcome, "execute")
    else:
        _assert_allows(outcome)


@pytest.mark.parametrize("cell", _cells())
def test_ac003_no_skill_call_cut_blocks(tmp_path: Path, cell: str) -> None:
    replay = Replay.load(cell)
    cuts = list(replay.skill_cuts())
    blocked = []
    for index, (cut, skill) in enumerate(cuts):
        outcome = replay.run(tmp_path / f"cut{index}", cut)
        if (outcome.code, outcome.out, _warn_lines(outcome)) != (0, "", []):
            blocked.append((skill, cut.isoformat(), outcome.out, outcome.err))
    assert blocked == []


def test_ac003_one_ms_before_each_skill_call_the_gate_blocks(tmp_path: Path) -> None:
    """Positive control for the cuts: just before an unrefused stage starts, the gate refuses.

    Without it the cut half could pass on a gate that never blocks anything.
    """
    misses: list[tuple[str, str, str, str]] = []
    controls = 0
    for cell in _cells():
        replay = Replay.load(cell)
        for index, (cut, stage) in enumerate(replay.controls()):
            controls += 1
            outcome = replay.run(tmp_path / f"{cell}-{index}", cut)
            ok = outcome.code == 2 and f"/hm:{stage}" in outcome.out
            if not ok or _warn_lines(outcome):
                misses.append((cell, stage, cut.isoformat(), outcome.out + outcome.err))
    assert misses == []
    assert controls == CONTROLS


def test_ac003_fixtures_match_the_manifest() -> None:
    """The fixtures are what the manifest says they are: hashes and kept-record counts."""
    manifest = json.loads((_FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    mismatched = []
    for cell, entry in manifest["cells"].items():
        ledger = (_FIXTURES / cell / "auto-advance.jsonl").read_bytes()
        transcript = (_FIXTURES / cell / "transcript.jsonl").read_bytes()
        actual = (
            hashlib.sha256(ledger).hexdigest(),
            hashlib.sha256(transcript).hexdigest(),
            len([line for line in transcript.split(b"\n") if line.strip()]),
        )
        expected = (
            entry["ledger_sha256"],
            entry["transcript_sha256"],
            entry["transcript_records_kept"],
        )
        if actual != expected:
            mismatched.append(cell)
    assert mismatched == []
    assert len(manifest["cells"]) == 35


def test_ac003_cuts_exist() -> None:
    """The cut half is vacuous if the reduction lost the Skill calls."""
    total = sum(len(list(Replay.load(cell).skill_cuts())) for cell in _cells())
    assert total == 89


# ── AC-004: the reason ───────────────────────────────────────────────────────


def test_ac004_reason_names_stage_skill_and_the_second_stop(tmp_path: Path) -> None:
    reason = _reason(_run(World(tmp_path).build()))
    assert "/hm:execute" in reason
    assert "Skill" in reason
    sentences = re.split(r"(?<=[.!?])\s+", reason)
    assert any(
        re.search(r"\bend(ing)? the turn again\b", s, re.IGNORECASE) and "stop" in s.lower()
        for s in sentences
    ), reason
