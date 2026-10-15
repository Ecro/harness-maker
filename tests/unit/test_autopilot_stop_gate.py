"""SPEC-autopilot-stop-gate: the Stop hook refuses once when a turn authorized a stage it never ran.

AC-001 is the golden state table, AC-002 the differential against the df070f6c loop gate, AC-003
the replay of the 35 eval-2 hm runs (fixtures in `tests/fixtures/autopilot_stop_gate/`, reduced as
`manifest.json` describes), AC-004 the reason text.
"""

from __future__ import annotations

import contextlib
import importlib.util
import inspect
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
    peer: bool = False
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
        if self.peer:
            _write_marker_file(self.root, key=PEER, claude_session_id=PEER, created=_at(10))
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
    claude_session_id: str,
    created: str,
    level: OperationalLevel = "auto_full",
    pipeline: list[str] = PIPELINE,
    task_slug: str | None = None,
) -> None:
    """Write a marker at `key`'s path holding `claude_session_id`; they differ for a foreign one."""
    marker = autopilot.AutopilotMarker(
        session_uuid="0123456789ab",
        level=level,
        pipeline=[AtomicStage(s) for s in pipeline],
        created_at=created,
        claude_session_id=claude_session_id,
        task_slug=task_slug,
    )
    path = autopilot.marker_path(root, session_id=key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(marker.model_dump_json(), encoding="utf-8")


@dataclass
class Outcome:
    code: int
    out: str
    err: str


def _run(hook: Callable[..., int], payload: str, *, now: datetime = NOW) -> Outcome:
    """Call a `_stop_hook`, passing `now` only to a hook that takes it (the reference does not)."""
    kwargs = {"now": now} if "now" in inspect.signature(hook).parameters else {}
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hook(payload, **kwargs)
    return Outcome(code, out.getvalue(), err.getvalue())


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
    ("r15-peer-armed", _set(peer=True), _ALLOW),
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
]


@pytest.mark.parametrize(("case_id", "setup", "expected"), GOLDEN, ids=[g[0] for g in GOLDEN])
def test_ac001_golden_state_table(
    tmp_path: Path, case_id: str, setup: Setup, expected: tuple[str, str | None]
) -> None:
    world = World(tmp_path)
    setup(world)
    outcome = _run(loop_gate._stop_hook, world.build())
    kind, stage = expected
    if kind == "block":
        assert stage is not None
        _assert_blocks(outcome, stage)
    elif kind == "loop":
        assert outcome.code == 2, outcome
        assert outcome.out == json.dumps({"decision": "block", "reason": LOOP_REASON}) + "\n"
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
    outcome = _run(loop_gate._stop_hook, World(tmp_path).build())
    _assert_allows(outcome)
    assert len(_warn_lines(outcome)) == 1, outcome.err
    assert len(outcome.err.splitlines()) == 1, outcome.err


def test_block_reason_also_reaches_stderr(tmp_path: Path) -> None:
    """With exit 2 Claude Code hands the model stderr, not stdout (PLAN ADR-008)."""
    outcome = _run(loop_gate._stop_hook, World(tmp_path).build())
    _assert_blocks(outcome, "execute")
    assert _reason(outcome) in outcome.err


def test_task_slug_rides_in_the_reason(tmp_path: Path) -> None:
    world = World(tmp_path, task_slug="ratelimit")
    reason = _reason(_run(loop_gate._stop_hook, world.build()))
    assert "ratelimit" in reason


def test_sidechain_skill_call_does_not_count_as_started(tmp_path: Path) -> None:
    """A subagent's `Skill` call is not this session invoking the stage."""
    call = skill_call(4.5, "execute") | {"isSidechain": True}
    world = World(tmp_path)
    _append_after(call)(world)
    _assert_blocks(_run(loop_gate._stop_hook, world.build()), "execute")


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
        new = _run(loop_gate._stop_hook, payload)
        ref = _run(reference_loop_gate._stop_hook, payload)
        if (new.out, new.code) != (ref.out, ref.code):
            differing.append((cell, ref.code, new.code))
        cells += 1
    assert cells == 160
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
        codes.add(_run(reference_loop_gate._stop_hook, payload).code)
    assert codes == {0, 2}


# ── AC-003: replaying the eval-2 hm runs ─────────────────────────────────────

STALLED = {"t5-hm-1", "t5-hm-3", "t7-hm-3", "t10-hm-3", "t11-hm-1"}


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

    def skill_cuts(self) -> Iterator[tuple[datetime, str]]:
        for line in self.transcript:
            record = json.loads(line)
            for block in record["message"]["content"] or []:
                if block.get("name") == "Skill":
                    yield _parse(record["timestamp"]), block["input"]["skill"]

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
        return _run(loop_gate._stop_hook, payload, now=created + timedelta(hours=2))


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
        if (outcome.code, outcome.out) != (0, ""):
            blocked.append((skill, cut.isoformat(), outcome.out))
    assert blocked == []


def test_ac003_cuts_exist() -> None:
    """The cut half is vacuous if the reduction lost the Skill calls."""
    total = sum(len(list(Replay.load(cell).skill_cuts())) for cell in _cells())
    assert total == 89


# ── AC-004: the reason ───────────────────────────────────────────────────────


def test_ac004_reason_names_stage_skill_and_the_second_stop(tmp_path: Path) -> None:
    reason = _reason(_run(loop_gate._stop_hook, World(tmp_path).build()))
    assert "/hm:execute" in reason
    assert "Skill" in reason
    sentences = re.split(r"(?<=[.!?])\s+", reason)
    assert any(
        re.search(r"\bend(ing)? the turn again\b", s, re.IGNORECASE) and "stop" in s.lower()
        for s in sentences
    ), reason
