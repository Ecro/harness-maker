"""Phase 3: the two transcript fields run-boundary classification needs.

`uuid` is the verdict cache key — without it a judgment cannot be reused, and a
key derived from anything else (index, timestamp) shifts when the window moves.
`preceded_by_user` is how ADR-005's "boundary with no user message" case becomes
observable at all; the loader drops every non-assistant line, so the information
is destroyed unless it is captured during the scan.

Shapes here were taken from a real store, not invented: a user line is either a
`str` content, a list of `tool_result` blocks, or a list of `text` blocks with
`isMeta: true` (slash-command injection).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_maker.economics_source import load_turns

_PROJECT = Path("/repo/proj")


def _assistant(uuid: str | None, ts: str) -> dict[str, Any]:
    line: dict[str, Any] = {
        "type": "assistant",
        "sessionId": "s1",
        "timestamp": ts,
        "cwd": str(_PROJECT),
        "message": {
            "model": "claude-opus-4-7",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "content": [{"type": "text", "text": "hi"}],
        },
    }
    if uuid is not None:
        line["uuid"] = uuid
    return line


def _user(content: Any, *, is_meta: bool = False) -> dict[str, Any]:
    line: dict[str, Any] = {
        "type": "user",
        "sessionId": "s1",
        "timestamp": "2026-07-26T09:00:00Z",
        "cwd": str(_PROJECT),
        "message": {"role": "user", "content": content},
    }
    if is_meta:
        line["isMeta"] = True
    return line


def _store(tmp_path: Path, lines: list[dict[str, Any]], *, name: str = "a.jsonl") -> Path:
    root = tmp_path / "projects"
    directory = root / "-repo-proj"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        "".join(json.dumps(entry) + "\n" for entry in lines), encoding="utf-8"
    )
    return root


def _flags(tmp_path: Path, lines: list[dict[str, Any]]) -> list[bool]:
    result = load_turns(_PROJECT, transcript_root=_store(tmp_path, lines))
    return [t.preceded_by_user for t in result.turns]


def test_the_turn_uuid_is_carried_through_for_the_verdict_cache_key(tmp_path: Path) -> None:
    root = _store(tmp_path, [_assistant("abc123", "2026-07-26T09:01:00Z")])
    (turn,) = load_turns(_PROJECT, transcript_root=root).turns
    assert turn.uuid == "abc123"


def test_a_line_without_a_uuid_loads_with_none_rather_than_failing(tmp_path: Path) -> None:
    """Older transcripts predate the field; refusing them would silently shrink the
    corpus the retroactive path exists to recover."""
    root = _store(tmp_path, [_assistant(None, "2026-07-26T09:01:00Z")])
    (turn,) = load_turns(_PROJECT, transcript_root=root).turns
    assert turn.uuid is None


def test_a_typed_user_message_marks_the_next_turn(tmp_path: Path) -> None:
    assert _flags(
        tmp_path, [_user("please fix the parser"), _assistant("a", "2026-07-26T09:01:00Z")]
    ) == [True]


def test_a_tool_result_line_is_not_a_user_message(tmp_path: Path) -> None:
    """The commonest user-typed line in a transcript by far, and not a boundary: it
    is the harness feeding a tool's output back into the same turn sequence."""
    content = [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}]
    assert _flags(tmp_path, [_user(content), _assistant("a", "2026-07-26T09:01:00Z")]) == [False]


def test_a_slash_command_injection_is_not_a_user_message(tmp_path: Path) -> None:
    """`isMeta: true` carries the expanded command template, not something the user
    said. Treating it as a boundary would mark every stage invocation a new run."""
    content = [{"type": "text", "text": "# /hm:metrics\n\n> Delivery metrics..."}]
    assert _flags(
        tmp_path, [_user(content, is_meta=True), _assistant("a", "2026-07-26T09:01:00Z")]
    ) == [False]


def test_a_synthetic_command_envelope_is_not_a_user_message(tmp_path: Path) -> None:
    envelope = "<command-message>hm:metrics</command-message>"
    assert _flags(tmp_path, [_user(envelope), _assistant("a", "2026-07-26T09:01:00Z")]) == [False]


def test_a_task_notification_is_not_a_user_message(tmp_path: Path) -> None:
    """ADR-005 names this one explicitly — a background task completing looks like a
    user turn but nobody spoke."""
    note = "<task-notification>agent finished</task-notification>"
    assert _flags(tmp_path, [_user(note), _assistant("a", "2026-07-26T09:01:00Z")]) == [False]


def test_a_turn_that_follows_another_assistant_turn_is_not_user_preceded(tmp_path: Path) -> None:
    lines = [
        _user("go"),
        _assistant("a", "2026-07-26T09:01:00Z"),
        _assistant("b", "2026-07-26T09:02:00Z"),
    ]
    assert _flags(tmp_path, lines) == [True, False]


def test_the_first_turn_in_a_file_is_not_user_preceded(tmp_path: Path) -> None:
    assert _flags(tmp_path, [_assistant("a", "2026-07-26T09:01:00Z")]) == [False]


def test_the_flag_is_consumed_so_it_marks_only_the_immediately_following_turn(
    tmp_path: Path,
) -> None:
    """A sticky flag would mark an entire post-user stretch as user-opened, which is
    the same over-attribution the run model exists to avoid."""
    lines = [
        _user("go"),
        _assistant("a", "2026-07-26T09:01:00Z"),
        _user([{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]),
        _assistant("b", "2026-07-26T09:02:00Z"),
    ]
    assert _flags(tmp_path, lines) == [True, False]


def test_the_flag_does_not_leak_across_transcript_files(tmp_path: Path) -> None:
    """Files are scanned in sequence; a trailing user message in one session must not
    mark the first turn of the next."""
    root = tmp_path / "projects"
    directory = root / "-repo-proj"
    directory.mkdir(parents=True)
    (directory / "a.jsonl").write_text(json.dumps(_user("go")) + "\n", encoding="utf-8")
    (directory / "b.jsonl").write_text(
        json.dumps(_assistant("x", "2026-07-26T09:05:00Z")) + "\n", encoding="utf-8"
    )

    result = load_turns(_PROJECT, transcript_root=root)
    assert [t.preceded_by_user for t in result.turns] == [False]


def test_a_malformed_line_between_the_user_and_the_turn_does_not_mark_it(
    tmp_path: Path,
) -> None:
    """Fail-closed: if the scan lost its place, the safe answer is "no user message",
    which routes the boundary to `unknown` instead of a guessed continuation."""
    root = tmp_path / "projects"
    directory = root / "-repo-proj"
    directory.mkdir(parents=True)
    (directory / "a.jsonl").write_text(
        json.dumps(_user("go"))
        + "\n{ broken\n"
        + json.dumps(_assistant("x", "2026-07-26T09:05:00Z"))
        + "\n",
        encoding="utf-8",
    )

    result = load_turns(_PROJECT, transcript_root=root)
    assert [t.preceded_by_user for t in result.turns] == [False]
