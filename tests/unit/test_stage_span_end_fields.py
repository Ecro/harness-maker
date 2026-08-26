"""AC-003 — a closed span's `end` row carries the `task_slug` and `git_branch` its `start` did.

Metamorphic, not a fixture comparison (spec-tetrad ADR-001): whatever pair the `start`
carried, the `end` must carry. The relation holds for every `(slug, branch)` regardless of
how `span-end` resolves them internally, so it cannot be satisfied by echoing a constant the
test also knows — which is what a single hardcoded fixture pair would permit.

The measured violation this exists to reject: every one of the 109 `end` rows in this repo's
live `stage-spans.jsonl` carries `task_slug: null, git_branch: null` while its `start` carries
both, because `worktree._cli_span_end` calls `emit_event("end", stage=…, cwd=…, session_id=…)`
and passes neither field. A slug-keyed join over that ledger silently yields zero spans.

Wrong implementations these assertions reject, named per
`[fail:test] assertion-invariant-over-named-dimension`:
  1. the shipped one — both fields omitted, so `end` nulls them;
  2. a half-fix that carries `task_slug` and forgets `git_branch` (or the reverse) — the two
     are asserted separately, never as one tuple-equality that a shared null would satisfy;
  3. a constant echo — Hypothesis varies both values, so a hardcoded pair fails immediately;
  4. reading the pair off the globally-last event rather than the caller's own — a peer `start`
     is interleaved in `test_end_ignores_a_peers_start_when_copying_the_pair`.

Phase A.4 — justified pass (1 of 3 in this file):
  `test_legacy_null_bearing_rows_still_parse` passes before the implementation. It is a
  backward-compat negative: `SpanEvent` already declares both fields `str | None = None`, so a
  null-bearing legacy row loads today. It exists to go RED if the fix is implemented by making
  the fields REQUIRED, which would make every one of the 109 existing `end` rows unloadable.
  RED positive sibling that forces that construct into existence:
  `test_span_end_preserves_start_task_and_branch`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker.stage_spans import emit_event, ledger_path, read_events

# Hypothesis profile contract (spec-tetrad ADR-002): `ci` = reproducible gate,
# `dev` = broader local bug-finding. Select via HYPOTHESIS_PROFILE (default ci).
settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_SESSION = "11111111-2222-3333-4444-555555555555"
_PEER = "99999999-8888-7777-6666-555555555555"

# `input_domain` from the machine SPEC: any (task_slug, git_branch) task-preflight can emit,
# including non-ASCII and hyphenated forms. Excludes the empty string, which `emit_event`
# stores as-is but no preflight produces.
_SLUGS = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E, exclude_characters='"\\'),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() == s and s.strip() != "")
_BRANCHES = _SLUGS.map(lambda s: f"hm/{s}")


def _git_repo(tmp: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "-q", "--allow-empty", "-m", "root"],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )
    return tmp


def _close_span(base: Path, session_id: str | None) -> None:
    """Drive the real CLI entry point, not a helper — the defect is in `_cli_span_end`.

    The hook payload must be delivered on `sys.stdin`, the Python object, NOT on file
    descriptor 0: `_span_end_session_id` calls `sys.stdin.isatty()`/`.read()`, and under
    pytest `sys.stdin` is already a replacement object, so a `dup2` onto fd 0 is invisible to
    it. The first version of this helper did exactly that — the id never arrived, `mine` fell
    to `None`, the session-less bucket held nothing, and `_cli_span_end` returned 0 without
    writing any `end` at all. The tests then failed for a plumbing reason instead of the
    defect they name, which is the failure this repo files as
    `[fail:test] assertion-invariant-over-named-dimension`'s mirror: red for the wrong cause.
    """
    import io

    from harness_maker.worktree import _cli_span_end

    payload = json.dumps({"session_id": session_id}) if session_id else ""
    saved = sys.stdin
    try:
        sys.stdin = io.StringIO(payload)
        _cli_span_end([str(base)])
    finally:
        sys.stdin = saved


def _rows(base: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in ledger_path(base).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@given(slug=_SLUGS, branch=_BRANCHES)
def test_span_end_preserves_start_task_and_branch(tmp_path_factory, slug, branch) -> None:
    """expected_relation: end.task_slug == start.task_slug
    and end.git_branch == start.git_branch.
    """
    base = _git_repo(tmp_path_factory.mktemp("span"))
    emit_event(
        "start",
        stage="hm:execute",
        cwd=base,
        session_id=_SESSION,
        git_branch=branch,
        task_slug=slug,
    )
    _close_span(base, _SESSION)

    rows = _rows(base)
    assert [r["event"] for r in rows] == ["start", "end"], rows
    start, end = rows
    # Asserted SEPARATELY: a single tuple equality is satisfied by a half-fix that nulls
    # both, because (None, None) == (None, None).
    assert end["task_slug"] == start["task_slug"] == slug
    assert end["git_branch"] == start["git_branch"] == branch


def test_end_ignores_a_peers_start_when_copying_the_pair(tmp_path: Path) -> None:
    """Rejects implementation 4: reading the pair off the globally-last event.

    A peer's `start` is appended between ours and our close. `_cli_span_end` already picks
    `ours[-1]` for `stage`; the pair must come from the same record.
    """
    base = _git_repo(tmp_path)
    emit_event(
        "start",
        stage="hm:plan",
        cwd=base,
        session_id=_SESSION,
        git_branch="hm/mine",
        task_slug="mine",
    )
    emit_event(
        "start",
        stage="hm:review",
        cwd=base,
        session_id=_PEER,
        git_branch="hm/theirs",
        task_slug="theirs",
    )
    _close_span(base, _SESSION)

    end = _rows(base)[-1]
    assert end["event"] == "end"
    assert end["session_id"] == _SESSION
    assert end["task_slug"] == "mine"
    assert end["git_branch"] == "hm/mine"


def test_id_less_end_does_not_copy_a_peers_pair(tmp_path: Path) -> None:
    """Review round 2 (concurrency P1): the degraded bucket must NOT carry a pair.

    When the caller has no session id, `ours` is the SHARED session-less bucket — the
    `KNOWN LIMIT` `_cli_span_end` documents — so `ours[-1]` can be a concurrent peer's
    still-open `start`. Copying its pair would stamp this row with ANOTHER task's slug.

    The distinction that makes this a defect rather than a wash: a null is excluded by the
    slug-keyed join AC-003 exists to enable, while a well-formed WRONG slug is silently
    accepted by that same join and attributed to the wrong task. Null is inert; wrong is not.

    Wrong implementations rejected: (1) copying unconditionally from `ours[-1]` — the shipped
    round-1 code, which yields peer-y here; (2) copying only when `ours[-1]` is a start —
    still yields the peer's, since a peer's open span IS a start.
    """
    base = _git_repo(tmp_path)
    emit_event(
        "start",
        stage="hm:plan",
        cwd=base,
        session_id=None,
        git_branch="hm/peer",
        task_slug="peer",
    )
    _close_span(base, None)

    end = _rows(base)[-1]
    assert end["event"] == "end"
    assert end["session_id"] is None
    assert end["task_slug"] is None
    assert end["git_branch"] is None


def test_legacy_null_bearing_rows_still_parse(tmp_path: Path) -> None:
    """Backward compat (SPEC Constraints): pre-fix rows must keep loading.

    `SpanEvent` declares both fields `str | None = None`, so this is additive. The assertion
    pins that the reader accepts a null-bearing `end` — not merely that the file exists.
    """
    base = _git_repo(tmp_path)
    path = ledger_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event": "start",
                "stage": "hm:execute",
                "cwd": str(base),
                "base_root": str(base),
                "git_branch": "hm/old",
                "task_slug": "old",
                "ts": "2026-07-01T00:00:00Z",
                "session_id": None,
            }
        )
        + "\n"
        + json.dumps(
            {
                "schema_version": 1,
                "event": "end",
                "stage": "hm:execute",
                "cwd": str(base),
                "base_root": str(base),
                "git_branch": None,
                "task_slug": None,
                "ts": "2026-07-01T00:05:00Z",
                "session_id": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events, diag = read_events(path)
    assert diag.malformed_lines == 0
    assert [e.event for e in events] == ["start", "end"]
    assert events[1].task_slug is None
