"""Phase 2 e2e: drive the CLI the rendered stage actually runs, not the Python API.

Every other span test calls `worktree.task_preflight(...)` directly. That is not what
ships — the rendered stage runs a `!uv run … python -m harness_maker.worktree …` line,
and ADR-008 declares THAT line load-bearing. The gap this file closes is concrete: a
parser that mistook `--stage`'s value for the base positional passed every unit test
and every render grep, because neither observes a parse.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

from harness_maker import worktree
from harness_maker.stage_spans import SpanEvent, ledger_path, read_events


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=60)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n", encoding="utf-8")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _events(repo: Path) -> list[SpanEvent]:
    evs, diag = read_events(ledger_path(repo))
    assert diag.malformed_lines == 0
    return evs


def test_cli_preflight_parses_the_stage_flag_without_eating_the_base_positional(
    tmp_path: Path,
) -> None:
    """The regression that motivated this file.

    The shipped parser took positionals as "every arg not starting with `--`", so
    `task-preflight <slug> "$(pwd)" --stage hm:plan` would have resolved
    `base_dir = Path("hm:plan")` had the flag come first, and even in this order a
    naive parser sees three positionals. Asserting the WORKTREE LOCATION is what
    proves the base survived: a mis-parsed base creates the worktree somewhere else
    entirely, which no text-grep render test can see.
    """
    repo = _repo(tmp_path)
    rc = worktree.main(["task-preflight", "feat-x", str(repo), "--stage", "hm:plan"])
    assert rc == 0

    assert (repo / ".worktrees" / "feat-x").is_dir()
    assert not (repo / "hm:plan").exists()

    events = _events(repo)
    assert [(e.event, e.stage) for e in events] == [("start", "hm:plan")]
    assert events[0].base_root == str(repo.resolve())
    assert events[0].task_slug == "feat-x"


def test_cli_preflight_accepts_the_equals_form_of_the_flag(tmp_path: Path) -> None:
    """`--stage=hm:plan` is one argv token; a parser splitting only on the two-token
    form would drop the stage and silently record the absent case."""
    repo = _repo(tmp_path)
    assert worktree.main(["task-preflight", "feat-y", str(repo), "--stage=hm:review"]) == 0
    assert [e.stage for e in _events(repo)] == ["hm:review"]


def test_cli_preflight_without_the_flag_records_the_absent_case(tmp_path: Path) -> None:
    """An un-re-rendered harness. Must still work, and must be countable."""
    repo = _repo(tmp_path)
    assert worktree.main(["task-preflight", "feat-z", str(repo)]) == 0
    assert [e.stage for e in _events(repo)] == [""]


def test_cli_create_with_a_session_id_emits_one_loop_level_span(tmp_path: Path) -> None:
    """`/hm:loop` orders its stages NOT to run task-preflight, so the loop's own
    `create` call carries the span. Only loop.md.j2 passes `--claude-session-id`,
    which is what distinguishes a loop from a standalone /hm:execute create.
    """
    repo = _repo(tmp_path)
    rc = worktree.main(
        [
            "create",
            "execute",
            str(repo),
            "--claude-session-id",
            "aaaabbbb-1111-2222-3333-444455556666",
        ]
    )
    assert rc == 0
    events = _events(repo)
    assert [e.stage for e in events] == ["hm:loop"]
    assert events[0].session_id == "aaaabbbb-1111-2222-3333-444455556666"


def test_cli_create_without_a_session_id_is_not_labelled_a_loop(tmp_path: Path) -> None:
    """Negative control — a standalone /hm:execute create must not masquerade as a
    loop, or loop-vs-stage spend becomes unreadable."""
    repo = _repo(tmp_path)
    assert worktree.main(["create", "execute", str(repo)]) == 0
    assert [e.stage for e in _events(repo)] == ["hm:execute"]


def test_the_ledger_accumulates_a_start_and_an_end_across_two_cli_calls(
    tmp_path: Path,
) -> None:
    """The exit criterion asks for BOTH records. `end` had no producer and no test
    at all before this: every span was closed by next-start, session-end, or a cap,
    so the `event: "end"` arm of the schema was dead weight.
    """
    repo = _repo(tmp_path)
    assert worktree.main(["task-preflight", "feat-x", str(repo), "--stage", "hm:plan"]) == 0
    assert worktree.main(["span-end", str(repo), "--stage", "hm:plan"]) == 0

    events = _events(repo)
    assert [e.event for e in events] == ["start", "end"]
    assert {e.stage for e in events} == {"hm:plan"}


def test_span_end_on_a_project_that_never_started_one_is_a_no_op_not_an_error(
    tmp_path: Path,
) -> None:
    """The Stop hook fires on every session, including ones that ran no /hm: stage.
    Recording a bare `end` would leave the reader pairing an end against whatever
    span preceded it in a LATER session.
    """
    repo = _repo(tmp_path)
    assert worktree.main(["span-end", str(repo), "--stage", "hm:plan"]) == 0
    assert _events(repo) == []


def test_create_with_an_empty_session_id_is_still_a_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The WSL2 case, and the author's own platform.

    `loop.md.j2` passes `--claude-session-id "$HM_SESSION_ID"` QUOTED, so an empty
    `$HM_SESSION_ID` still supplies the flag with an empty value. Selecting on the
    VALUE would label every loop `hm:execute` there. Neither the flag-absent test
    above nor the `sess-1` test covers this third argv — it is the absent case.
    """
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    repo = _repo(tmp_path)
    assert worktree.main(["create", "execute", str(repo), "--claude-session-id", ""]) == 0
    assert [e.stage for e in _events(repo)] == ["hm:loop"]


def test_span_end_works_in_its_shipped_zero_argument_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook command is `… worktree span-end` with NO arguments — it relies on
    cwd and on inheriting the open span's stage. Every other span-end test passes
    an explicit base and `--stage`, i.e. an argv that never ships.
    """
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    repo = _repo(tmp_path)
    assert worktree.main(["task-preflight", "feat-x", str(repo), "--stage", "hm:plan"]) == 0
    monkeypatch.chdir(repo)
    assert worktree.main(["span-end"]) == 0

    events = _events(repo)
    assert [(e.event, e.stage) for e in events] == [("start", "hm:plan"), ("end", "hm:plan")]


def test_a_peer_sessions_span_end_does_not_truncate_a_live_span(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ledger is SHARED across concurrent sessions and the reader closes the
    globally-current span on any `end`. An idle peer's Stop hook firing would
    otherwise cut a live session's span short — silently, and only under
    concurrency, which is where this project has already shipped three incidents.
    """
    repo = _repo(tmp_path)
    monkeypatch.setenv("HM_SESSION_ID", "11111111-2222-3333-4444-555555555555")
    assert worktree.main(["task-preflight", "feat-x", str(repo), "--stage", "hm:plan"]) == 0

    monkeypatch.setenv("HM_SESSION_ID", "99999999-8888-7777-6666-555555555555")
    assert worktree.main(["span-end", str(repo)]) == 0

    assert [e.event for e in _events(repo)] == ["start"]  # B did not close A's span


def test_span_end_is_wired_into_settings_json_not_the_dead_hooks_json(
    tmp_path: Path,
) -> None:
    """Session-end closure only exists if the hook actually fires.

    Claude Code reads project hooks ONLY from `.claude/settings.json`; the rendered
    `.claude/hooks/hooks.json` is dead weight (confirmed by controlled experiment
    2026-07-17). A render test asserting the hook in hooks.json would be green and
    dead — which is exactly how every hook this project shipped before 0.40.0 was
    silently not running.
    """
    import json

    from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
    )
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    # `render()`'s target dir IS the `.claude/` dir, so settings.json sits at its root.
    settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))

    def _cmds(event: str) -> list[str]:
        return [h["command"] for entry in settings["hooks"][event] for h in entry.get("hooks", [])]

    stop_cmds = _cmds("Stop")
    assert any("worktree span-end" in c for c in stop_cmds), stop_cmds
    # the pre-existing loop gate must survive alongside it
    assert any("loop_gate" in c for c in stop_cmds), stop_cmds

    # PreCompact is the OTHER half of ADR-003's session-end closure, and the one that
    # matters most: compaction is listed as a boundary class that produces
    # unattributed runs. Wiring only Stop would leave a compaction boundary riding to
    # the 400-turn cap, which is sized for whole runs — absorbed by `capped_turns`,
    # invisible, and green.
    precompact = settings["hooks"]["PreCompact"]
    assert len(precompact) == 2, "both auto and manual matchers must close the span"
    for entry in precompact:
        cmds = [h["command"] for h in entry["hooks"]]
        assert any("worktree span-end" in c for c in cmds), (entry.get("matcher"), cmds)
        assert any("flush_session" in c for c in cmds), (entry.get("matcher"), cmds)


def test_span_end_closes_the_span_when_only_stdin_carries_the_session_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The asymmetry every existing span-end test is blind to.

    `span-end` ships ONLY as a Stop/PreCompact hook, and a hook's session id arrives on
    **stdin** — `sessionid_envfile` says so verbatim, and the sibling Stop hook
    `loop_gate` reads it from there. `HM_SESSION_ID` is the slash-command bridge and is
    documented-empty on WSL2.

    So the realistic shape is: the `start` (a slash-command Bash line) has the env var,
    the `end` (a hook) has only stdin. Every other test in this file sets or clears the
    env var identically for both, which is precisely why none of them could see that
    reading env-only left the span open until a cap fired.
    """
    repo = _repo(tmp_path)
    monkeypatch.setenv("HM_SESSION_ID", "11111111-2222-3333-4444-555555555555")
    assert worktree.main(["task-preflight", "feat-x", str(repo), "--stage", "hm:plan"]) == 0

    # The hook process: no env var, session id only on stdin.
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"session_id": "11111111-2222-3333-4444-555555555555"}))
    )
    assert worktree.main(["span-end", str(repo)]) == 0

    events = _events(repo)
    assert [(e.event, e.session_id) for e in events] == [
        ("start", "11111111-2222-3333-4444-555555555555"),
        ("end", "11111111-2222-3333-4444-555555555555"),
    ]


def test_a_hook_whose_stdin_names_a_peer_still_does_not_close_your_span(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control for the stdin channel: reading stdin must not weaken the
    session scoping that R2-03's first attempt was written to provide."""
    repo = _repo(tmp_path)
    monkeypatch.setenv("HM_SESSION_ID", "11111111-2222-3333-4444-555555555555")
    assert worktree.main(["task-preflight", "feat-x", str(repo), "--stage", "hm:plan"]) == 0

    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"session_id": "99999999-8888-7777-6666-555555555555"}))
    )
    assert worktree.main(["span-end", str(repo)]) == 0

    assert [e.event for e in _events(repo)] == ["start"]
