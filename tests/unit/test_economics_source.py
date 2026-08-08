"""Phase 2 adapter contract: directory discovery, defensive parsing, ingestion diagnostics.

No test here reads the developer's real ``~/.claude`` — the transcript root is always a
parameter pointing at the checked-in fixture store (CLAUDE.md checkpoint 7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.economics import classify_turns
from harness_maker.economics_source import (
    IngestionResult,
    default_transcript_root,
    derive_task_slug,
    discover_transcript_dirs,
    encode_project_dir,
    load_turns,
    normalise_written_path,
)

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "transcripts"
_PROJECT = Path("/repo/proj")


@pytest.fixture
def loaded() -> IngestionResult:
    return load_turns(_PROJECT, transcript_root=_FIXTURES)


# ---------------------------------------------------------------- encoding / discovery


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (Path("/repo/proj"), "-repo-proj"),
        (Path("/home/noel/harness-maker"), "-home-noel-harness-maker"),
        (Path("/repo/proj/.worktrees/demo"), "-repo-proj--worktrees-demo"),
        # PLAN-workflow-time-token-savings A1: Claude Code maps `_` to `-` as well.
        # Verified against five underscore-path projects, all hyphen-encoded on disk.
        (Path("/a/b/c_d"), "-a-b-c-d"),
        (Path("/home/noel/strange_chess"), "-home-noel-strange-chess"),
    ],
)
def test_encode_project_dir_maps_slash_dot_and_underscore_to_dash(
    path: Path, expected: str
) -> None:
    assert encode_project_dir(path) == expected


def _write_turn(directory: Path, name: str, cwd: str) -> None:
    """One priced assistant turn whose `cwd` decides which project owns it."""
    directory.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "type": "assistant",
            "sessionId": name,
            "timestamp": "2026-08-08T12:00:00.000Z",
            "cwd": cwd,
            "isSidechain": False,
            "message": {
                "id": f"msg_{name}",
                "model": "claude-opus-5",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "content": [{"type": "text", "text": "hi"}],
            },
        }
    )
    (directory / f"{name}.jsonl").write_text(line + "\n", encoding="utf-8")


def test_discovery_finds_an_underscore_bearing_project_path(tmp_path: Path) -> None:
    """The existing cases all used `_`-free absolute paths — which is why this shipped broken.

    `economics stages --root /home/noel/strange_chess` reported `$0 / 0 turns` for $1,637 of
    real spend, because the encoder left the underscore alone and matched no directory.
    """
    root = tmp_path / "projects"
    _write_turn(root / "-x-my-proj", "sess", "/x/my_proj")

    found = discover_transcript_dirs(Path("/x/my_proj"), transcript_root=root)

    assert [p.name for p in found] == ["-x-my-proj"]


def test_cwd_filter_is_the_real_boundary_when_two_paths_encode_alike(tmp_path: Path) -> None:
    """`/x/a_b` and `/x/a-b` collide after encoding; `is_own_cwd` is what separates them.

    Widening the encoder admits a foreign DIRECTORY, and `load_turns` re-checks every turn's
    `cwd` — so no foreign turn **that carries a `cwd`** survives. That qualifier is load-bearing:
    `test_a_cwd_less_foreign_turn_survives_the_collision_boundary` below shows a `cwd`-less line
    IS admitted. An earlier version of this docstring made the claim unconditional and three
    reviewers refuted it. This test pins the carrying-cwd branch; that one pins the other.
    """
    root = tmp_path / "projects"
    _write_turn(root / "-x-a-b", "sess", "/x/a-b")

    assert encode_project_dir(Path("/x/a_b")) == encode_project_dir(Path("/x/a-b"))

    foreign = load_turns(Path("/x/a_b"), transcript_root=root)
    # Name the mechanism rather than deducing it from an empty list: the colliding directory
    # WAS discovered, and the turn was dropped by the per-turn cwd check. Asserting only
    # `turns == []` would stay green if a later change made discovery stop returning the
    # directory at all — retiring the guard this test exists to pin.
    assert foreign.diagnostics.dirs_scanned == 1
    assert foreign.diagnostics.skipped_by_reason.get("foreign_cwd") == 1
    assert foreign.turns == []

    assert len(load_turns(Path("/x/a-b"), transcript_root=root).turns) == 1


def test_a_cwd_less_foreign_turn_survives_the_collision_boundary(tmp_path: Path) -> None:
    """The boundary is fail-OPEN on absent `cwd`, so the collision CAN admit a foreign turn.

    `is_own_cwd` returns True when `cwd is None` — deliberately, for older transcript lines
    that predate the field. Widening the encoder enlarged the collision set, so this branch
    became reachable where it previously never fired. Pinned as an accepted limit rather than
    left to a docstring: an earlier version of `encode_project_dir`'s docstring claimed the
    widening "cannot admit foreign turns", and three reviewers refuted it against this branch.
    Change this test's expectation only alongside a deliberate decision to make `is_own_cwd`
    fail-closed — which would drop legacy no-cwd turns everywhere, not just here.
    """
    root = tmp_path / "projects"
    directory = root / "-x-a-b"
    directory.mkdir(parents=True)
    line = json.dumps(
        {
            "type": "assistant",
            "sessionId": "legacy",
            "timestamp": "2026-08-08T12:00:00.000Z",
            "message": {
                "id": "msg_legacy",
                "model": "claude-opus-5",
                "usage": {"input_tokens": 2, "output_tokens": 3},
                "content": [{"type": "text", "text": "hi"}],
            },
        }
    )
    (directory / "legacy.jsonl").write_text(line + "\n", encoding="utf-8")

    admitted = load_turns(Path("/x/a_b"), transcript_root=root)

    assert admitted.diagnostics.dirs_scanned == 1
    assert admitted.diagnostics.skipped_by_reason.get("foreign_cwd") is None
    assert len(admitted.turns) == 1


def test_discovery_finds_the_base_dir_and_its_worktree_encoded_siblings() -> None:
    """ADR-007 — a session launched inside a worktree lands in its own project dir."""
    dirs = {p.name for p in discover_transcript_dirs(_PROJECT, transcript_root=_FIXTURES)}
    assert dirs == {"-repo-proj", "-repo-proj--worktrees-demo"}


def test_discovery_returns_empty_when_no_store_exists(tmp_path: Path) -> None:
    assert discover_transcript_dirs(_PROJECT, transcript_root=tmp_path / "nope") == []


def test_default_transcript_root_is_under_home() -> None:
    assert default_transcript_root() == Path.home() / ".claude" / "projects"


# ---------------------------------------------------------------- path normalisation


@pytest.mark.parametrize(
    "raw",
    [
        "/repo/proj/src/a.py",
        "/repo/proj/.worktrees/demo/src/a.py",
        "/repo/proj/.worktrees/other-slug/src/a.py",
        "src/a.py",
    ],
)
def test_worktree_and_base_paths_normalise_to_the_same_repo_relative_path(raw: str) -> None:
    assert normalise_written_path(raw, _PROJECT) == "src/a.py"


def test_foreign_absolute_path_is_kept_verbatim() -> None:
    assert normalise_written_path("/etc/hosts", _PROJECT) == "/etc/hosts"


# ---------------------------------------------------------------- task slug


@pytest.mark.parametrize(
    ("branch", "cwd", "expected"),
    [
        ("hm/demo", "/repo/proj", "demo"),
        ("main", "/repo/proj/.worktrees/demo", "demo"),
        ("main", "/repo/proj", None),
        (None, None, None),
    ],
)
def test_derive_task_slug(branch: str | None, cwd: str | None, expected: str | None) -> None:
    assert derive_task_slug(branch, cwd) == expected


# ---------------------------------------------------------------- loading


def test_loads_turns_from_base_subagent_and_sibling_dirs(loaded: IngestionResult) -> None:
    assert len(loaded.turns) == 7
    assert {t.session_id for t in loaded.turns} == {"sess1", "sess2"}
    assert any(t.is_sidechain for t in loaded.turns)
    assert any(t.attribution_skill == "hm:plan" for t in loaded.turns)  # sibling dir
    # git_branch feeds estimate_attribution's adjacency bound — an unmapped field
    # would silently weaken the estimator against real data.
    assert loaded.turns[0].git_branch == "hm/demo"


def test_turns_are_returned_in_timestamp_order(loaded: IngestionResult) -> None:
    stamps = [t.ts for t in loaded.turns]
    assert stamps == sorted(stamps)


def test_subagent_turn_carries_its_agent_and_scope(loaded: IngestionResult) -> None:
    sub = [t for t in loaded.turns if t.is_sidechain]
    assert len(sub) == 1
    assert sub[0].attribution_agent == "security-reviewer"
    assert sub[0].attribution_skill == "hm:review"
    assert sub[0].scope == "subagent"


def test_multi_tool_turn_collects_every_written_path(loaded: IngestionResult) -> None:
    multi = [t for t in loaded.turns if len(t.written_paths) == 2]
    assert len(multi) == 1
    assert multi[0].written_paths == ("src/a.py", "src/b.py")


def test_worktree_write_is_normalised_so_it_matches_the_base_write(loaded: IngestionResult) -> None:
    wt = [t for t in loaded.turns if t.cwd == "/repo/proj/.worktrees/demo" and t.written_paths]
    assert len(wt) == 1
    assert wt[0].written_paths == ("src/a.py",)


def test_every_usage_field_is_mapped_and_cache_creation_is_not_double_counted(
    loaded: IngestionResult,
) -> None:
    first = loaded.turns[0]
    assert first.usage.input_tokens == 2
    assert first.usage.output_tokens == 100
    assert first.usage.cache_read_tokens == 1000
    assert first.usage.cache_write_5m_tokens == 200
    assert first.usage.cache_write_1h_tokens == 300
    # The line also carries a redundant cache_creation_input_tokens: 500 — the tier
    # breakdown wins, and 500 must NOT be added on top of 200+300.
    assert first.usage.context_tokens == 1502


def test_end_to_end_ladder_over_the_fixture_store(loaded: IngestionResult) -> None:
    """The subagent VERIFY at 12:01:20 clears the rewrite window for the 12:02 write."""
    assert classify_turns(loaded.turns) == [
        "PRODUCE",
        "PRODUCE",
        "VERIFY",
        "PRODUCE",
        "OTHER",
        "OTHER",
        "OTHER",
    ]


def test_removing_the_subagent_verify_turn_makes_the_rewrite_rework(
    loaded: IngestionResult,
) -> None:
    """Isolates the cause: without the VERIFY, the 12:02 rewrite IS unprompted rework.

    Without this, the previous test would report PRODUCE for the same index even if
    path normalisation had silently failed — same expected value, different reason.
    """
    without_verify = [t for t in loaded.turns if not t.is_sidechain]
    labels = classify_turns(without_verify)
    assert labels[:3] == ["PRODUCE", "PRODUCE", "REWORK"]


# ---------------------------------------------------------------- defensive parsing


def test_malformed_and_usageless_lines_do_not_raise_and_are_not_priced(
    loaded: IngestionResult,
) -> None:
    assert len(loaded.turns) == 7  # the malformed + usageless lines produced no turn
    assert loaded.diagnostics.skipped_by_reason["json_error"] == 1
    assert loaded.diagnostics.skipped_by_reason["no_usage"] == 1


def test_non_assistant_lines_are_skipped_with_their_own_reason(loaded: IngestionResult) -> None:
    assert loaded.diagnostics.skipped_by_reason["not_assistant"] == 2


def test_unknown_extra_keys_do_not_prevent_parsing(loaded: IngestionResult) -> None:
    assert any(t.usage.output_tokens == 50 for t in loaded.turns)


def test_unknown_model_string_is_loaded_verbatim_for_the_pricer_to_flag(
    loaded: IngestionResult,
) -> None:
    assert any(t.model == "some-future-model-9" for t in loaded.turns)


def test_undecodable_bytes_are_read_with_replacement_and_counted_as_json_errors(
    tmp_path: Path,
) -> None:
    """Contract: bad BYTES are a line-level problem, not a file-level one."""
    root = tmp_path / "projects"
    (root / "-repo-proj").mkdir(parents=True)
    (root / "-repo-proj" / "broken.jsonl").write_bytes(b"\xff\xfe not utf8 \x00")
    result = load_turns(_PROJECT, transcript_root=root)
    assert result.turns == []
    assert result.diagnostics.files_read == 1
    assert result.diagnostics.files_failed == 0
    assert result.diagnostics.skipped_by_reason["json_error"] >= 1


def test_an_unopenable_file_is_counted_as_failed_not_raised(tmp_path: Path) -> None:
    """`files_failed` must be pinned NON-ZERO somewhere or it is a phantom counter.

    A directory named `*.jsonl` is discovered by the glob and raises IsADirectoryError
    on open — a deterministic, portable OSError.
    """
    root = tmp_path / "projects"
    (root / "-repo-proj" / "bad.jsonl").mkdir(parents=True)
    result = load_turns(_PROJECT, transcript_root=root)
    assert result.turns == []
    assert result.diagnostics.files_discovered == 1
    assert result.diagnostics.files_failed == 1
    assert result.diagnostics.files_read == 0


# ---------------------------------------------------------------- ingestion diagnostics


def test_diagnostics_count_directories_and_files(loaded: IngestionResult) -> None:
    d = loaded.diagnostics
    assert d.dirs_scanned == 2
    assert d.files_discovered == 3
    assert d.files_read == 3
    assert d.files_failed == 0


def test_diagnostics_count_lines(loaded: IngestionResult) -> None:
    d = loaded.diagnostics
    assert d.lines_total == 11
    assert d.assistant_lines == 8
    assert d.turns_with_usage == 7


def test_coverage_is_priced_turns_over_assistant_lines(loaded: IngestionResult) -> None:
    """A partial-drift format change shows up here; a binary zero-check would miss it."""
    assert loaded.diagnostics.coverage == pytest.approx(7 / 8)


def test_coverage_is_zero_for_an_empty_store(tmp_path: Path) -> None:
    result = load_turns(_PROJECT, transcript_root=tmp_path)
    assert result.turns == []
    assert result.diagnostics.coverage == 0.0
    assert result.diagnostics.dirs_scanned == 0
