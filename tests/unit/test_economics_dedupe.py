"""AC-001/002/003/008 — one API call is one turn, not one transcript record per block.

Claude Code writes one assistant JSONL record per content block (thinking / text /
tool_use) and stamps the **same** `usage` on each, so a loader that emits one turn per
record bills a single call two or three times. Measured on the frozen corpus: 24,082
assistant records, 10,945 calls.

The fixtures are hand-counted, and each one exists to kill a *specific* wrong collapse:

* `dedupe_split` — one 3-record group plus one singleton. Expected turn count 2 is
  distinguishable from the pre-fix answer (4) AND from a collapse that merged everything
  (1). The `tool_use` block sits in the group's MIDDLE record while the max-`output_tokens`
  record is the LAST, so keep-last loses `written_paths` and keep-first loses the final
  usage. Only union-metadata + max-usage survives.
* `dedupe_no_split` — the zero case for `duplicate_records_collapsed`. A field that only
  appears when non-zero lets a post-fix report over a split-free corpus read exactly like a
  pre-fix one, which defeats the point of labelling the change of unit.
* `dedupe_window` — a group whose records straddle the `--days` cutoff. Collapse precedes
  the window filter, so the group is atomic; this is the only shape where a denominator
  that mixes record-counted and group-counted terms is observable.
* `dedupe_attribution` — a group whose records disagree on `attributionSkill`. Measured at
  **0 of 5,757** multi-record groups in the frozen corpus, so this pins the behaviour on an
  unmodelled input rather than claiming to falsify anything. Its companion assertion is the
  one that matters: because real groups never disagree, `find_boundaries` cannot lose a
  boundary, and ADR-003's "the verdict cache needs no migration" holds as an invariant.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker.economics import PRICE_TABLE, main, resolve_model_family
from harness_maker.economics_source import encode_project_dir, load_turns

# Hypothesis profile contract (spec-tetrad ADR-002): `ci` = reproducible gate,
# `dev` = broader local bug-finding. Select via HYPOTHESIS_PROFILE (default ci).
settings.register_profile("ci", derandomize=True, max_examples=60, deadline=None)
settings.register_profile("dev", max_examples=300, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Hand-counted from dedupe_split.jsonl. Named rather than inlined so that changing either
# the fixture or the expectation is a visible edit to a stated pair.
_SPLIT_RECORDS = 4
_SPLIT_CALLS = 2
_SPLIT_COLLAPSED = _SPLIT_RECORDS - _SPLIT_CALLS  # 2
_SPLIT_CACHE_READ_TOKENS = 1000 + 500  # msg_A counted ONCE, plus msg_B
_SPLIT_FINAL_OUTPUT = 1663  # the LAST record of msg_A; keep-first would give 10

_MODEL = "claude-opus-4-7"


def _materialise(tmp_path: Path, fixture: str) -> tuple[Path, Path]:
    """Lay a fixture out the way `discover_transcript_dirs` requires.

    `load_turns` never reads a flat file: discovery only accepts child directories named
    `encode_project_dir(root)` or prefixed `<name>--worktrees-`. The per-turn `cwd` must
    also be rewritten to the tmp project, or `is_own_cwd` drops every turn as
    `foreign_cwd` — both traps cost an iteration to rediscover.
    """
    project = tmp_path / "proj"
    project.mkdir(exist_ok=True)
    store = tmp_path / "transcripts"
    session_dir = store / encode_project_dir(project)
    session_dir.mkdir(parents=True, exist_ok=True)
    body = (_FIXTURES / fixture).read_text(encoding="utf-8").replace("/proj", str(project))
    (session_dir / "session.jsonl").write_text(body, encoding="utf-8")
    return project, store


def _price():
    # Stated, not defaulted: an `or "opus"` fallback would keep pricing this test at opus
    # rates while `price_turn` took its own fallback path, and the two would agree by
    # coincidence rather than because the model resolved.
    family = resolve_model_family(_MODEL)
    assert family is not None, f"fixture model {_MODEL!r} no longer resolves to a price row"
    return PRICE_TABLE[family]


@pytest.fixture
def split(tmp_path: Path) -> tuple[Path, Path]:
    return _materialise(tmp_path, "dedupe_split.jsonl")


def test_the_split_fixture_is_shaped_as_these_tests_assume(split: tuple[Path, Path]) -> None:
    """Positive control — every assertion below is vacuous against a mis-built fixture."""
    _, store = split
    lines = [
        json.loads(x)
        for x in next(store.glob("*/session.jsonl")).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    assert len(lines) == _SPLIT_RECORDS
    ids = [rec["message"]["id"] for rec in lines]
    assert ids.count("msg_A") == 3, "the split group must have three records"
    # The two arms that make keep-first and keep-last both wrong.
    grp = [rec for rec in lines if rec["message"]["id"] == "msg_A"]
    assert grp[1]["message"]["content"][0]["type"] == "tool_use", "tool_use must be MIDDLE"
    assert grp[-1]["message"]["usage"]["output_tokens"] == _SPLIT_FINAL_OUTPUT


def test_ac_001_one_api_call_contributes_exactly_one_turn(split: tuple[Path, Path]) -> None:
    """AC-001 — turn count is calls, not records, and cache_read is priced once."""
    project, store = split
    result = load_turns(project, transcript_root=store, days=3650)
    assert len(result.turns) == _SPLIT_CALLS


def test_ac_001_cache_read_is_priced_once_per_call(
    split: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The load-bearing arm: a collapse that keeps one row but SUMS the group's usage
    satisfies the turn count and still bills cache_read three times."""
    project, store = split
    rc = main(["report", "--root", str(project), "--transcript-root", str(store), "--days", "3650"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    expected = _SPLIT_CACHE_READ_TOKENS * _price().cache_read / 1e6
    assert payload["report"]["cache_read_usd"] == pytest.approx(expected)


def test_adr_003_collapse_takes_the_final_usage_not_the_first(split: tuple[Path, Path]) -> None:
    """ADR-003's max-`output_tokens` rule. Only 1 of 5,757 real groups disagrees on
    output_tokens, so without a synthesised fixture this branch ships unexercised."""
    project, store = split
    turns = load_turns(project, transcript_root=store, days=3650).turns
    grouped = next(t for t in turns if t.message_id == "msg_A")
    assert grouped.usage.output_tokens == _SPLIT_FINAL_OUTPUT


def test_adr_003_collapse_unions_written_paths(split: tuple[Path, Path]) -> None:
    """`written_paths` is the one field that genuinely differs per record — the tool_use
    block lives in exactly one of them. Losing it silently re-labels PRODUCE/REWORK turns
    as OTHER, corrupting the classifier the whole economics model rests on."""
    project, store = split
    turns = load_turns(project, transcript_root=store, days=3650).turns
    grouped = next(t for t in turns if t.message_id == "msg_A")
    assert any(p.endswith("only_here.md") for p in grouped.written_paths)


def test_adr_003_collapse_keeps_the_first_records_uuid(split: tuple[Path, Path]) -> None:
    """`uuid` is the retroactive-classification verdict cache key. A non-deterministic
    winner invalidates the cache on every run."""
    project, store = split
    turns = load_turns(project, transcript_root=store, days=3650).turns
    grouped = next(t for t in turns if t.message_id == "msg_A")
    assert grouped.uuid == "a1"


def test_ac_002_the_report_states_how_many_records_it_collapsed(
    split: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-002 first conjunct."""
    project, store = split
    rc = main(["report", "--root", str(project), "--transcript-root", str(store), "--days", "3650"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ingestion"]["duplicate_records_collapsed"] == _SPLIT_COLLAPSED


def test_ac_002_the_collapse_count_is_present_and_zero_without_splits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-002 second conjunct — the absent case. A field that appears only when non-zero
    lets a post-fix report over a split-free corpus read exactly like a pre-fix one."""
    project, store = _materialise(tmp_path, "dedupe_no_split.jsonl")
    rc = main(["report", "--root", str(project), "--transcript-root", str(store), "--days", "3650"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ingestion"]["duplicate_records_collapsed"] == 0


def test_ac_008_coverage_survives_the_change_of_unit(split: tuple[Path, Path]) -> None:
    """AC-008 first conjunct. Collapsing divides the numerator by ~2.2; leaving the
    denominator record-counted drops coverage to ~0.45 permanently, retiring the one
    diagnostic that detects a real transcript-format change by making it always red."""
    project, store = split
    diag = load_turns(project, transcript_root=store, days=3650).diagnostics
    assert diag.coverage == pytest.approx(1.0)


def test_ac_008_coverage_holds_when_a_group_straddles_the_window(tmp_path: Path) -> None:
    """AC-008 second conjunct — the load-bearing one.

    Collapse precedes the window filter, so a group is atomic: it is wholly in or wholly
    out. If `assistant_calls` is group-counted while `outside_window` stays record-counted,
    the denominator goes negative and coverage reads 0.0; if the denominator stays
    record-counted it reads 0.33. Only both-group-counted gives 1.0.
    """
    from datetime import UTC, datetime

    project, store = _materialise(tmp_path, "dedupe_window.jsonl")
    now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
    result = load_turns(project, transcript_root=store, days=1, now=now)
    assert len(result.turns) == 1, "the straddling group is atomic and falls outside"
    assert result.diagnostics.coverage == pytest.approx(1.0)


def test_boundaries_are_preserved_because_groups_never_disagree_on_attribution(
    tmp_path: Path,
) -> None:
    """ADR-003's cache/classifier claim, tested rather than asserted.

    `find_boundaries` opens a run only where `attribution_skill` is None, and the boundary
    uuid is the stretch's first turn's. It can therefore only lose a boundary when a
    group's records DISAGREE on `attributionSkill` — measured at 0 of 5,757 groups in the
    frozen corpus, which is why the claim holds as an invariant rather than by luck.

    This fixture synthesises the disagreement anyway, so the behaviour on an unmodelled
    input is *defined* instead of being whatever the loop happens to do: the collapsed turn
    takes the first non-null skill and the first record's uuid, and the group is therefore
    attributed — no boundary, no cache key that moves between runs.
    """
    from harness_maker.run_classify import find_boundaries

    project, store = _materialise(tmp_path, "dedupe_attribution.jsonl")
    turns = load_turns(project, transcript_root=store, days=3650).turns
    assert len(turns) == 2, "msg_P singleton + the msg_G group"
    grouped = next(t for t in turns if t.uuid == "g1")
    assert grouped.attribution_skill == "hm:review"
    assert [b.uuid for b in find_boundaries(turns)] == []


def _write_group(session_dir: Path, name: str, project: Path, n: int, usage: dict) -> None:
    """N assistant records sharing one `message.id`, with byte-identical usage.

    Identical usage is the shape 5,756 of 5,757 real groups have; varying `output_tokens`
    is ADR-003's domain and is example-tested above, so it is deliberately NOT varied here.
    """
    lines = []
    for i in range(n):
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "uuid": f"{name}-{i}",
                    "timestamp": f"2026-07-20T10:{i:02d}:00.000Z",
                    "cwd": str(project),
                    "gitBranch": "main",
                    "message": {
                        "id": f"msg_{name}",
                        "model": _MODEL,
                        "usage": usage,
                        "content": [{"type": "text", "text": f"block {i}"}],
                    },
                }
            )
        )
    (session_dir / f"{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


@given(
    n=st.integers(min_value=1, max_value=8),
    inp=st.integers(min_value=0, max_value=10**6),
    cr=st.integers(min_value=0, max_value=10**6),
    cw=st.integers(min_value=0, max_value=10**6),
    out=st.integers(min_value=0, max_value=10**6),
)
def test_ac_003_collapse_preserves_context_and_divides_carry(
    tmp_path_factory: pytest.TempPathFactory, n: int, inp: int, cr: int, cw: int, out: int
) -> None:
    """AC-003 — the metamorphic relation, over every group size including the identity.

    Two conjuncts, and the FIRST is the one nothing else in this file covers:
    `context_tokens` is `input + cache_read + cache_write` (both TTLs), so a collapse that
    takes one record's `cache_read` but SUMS `input_tokens` and `cache_creation_input_tokens`
    passes every example-based assertion here — on the split fixture those are 2 and 0, too
    small to notice — while `total_usd` and `carry_ratio` silently move. This property is
    what kills that mutant, and it is why the AC is `type: property` rather than an example.

    N=1 is in the domain because collapse must be the identity there; an implementation
    that only fires for N>=2 is a different bug from one that never fires.
    """
    tmp_path = tmp_path_factory.mktemp("prop")
    project = tmp_path / "proj"
    project.mkdir()
    store = tmp_path / "transcripts"
    session_dir = store / encode_project_dir(project)
    session_dir.mkdir(parents=True)
    usage = {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_read_input_tokens": cr,
        "cache_creation_input_tokens": cw,
    }
    _write_group(session_dir, "G", project, n, usage)

    turns = load_turns(project, transcript_root=store, days=3650).turns
    assert len(turns) == 1, "a group of any size is exactly one call"
    collapsed = turns[0]

    # Conjunct 1 — context per turn is invariant under collapse. Mean over a one-element
    # set IS that element, so this is the per-record value, unsummed.
    assert collapsed.usage.context_tokens == inp + cr + cw

    # Conjunct 2 — the group's carry is exactly 1/N of the uncollapsed sum.
    price = _price().cache_read / 1e6
    assert collapsed.usage.cache_read_tokens * price * n == pytest.approx(cr * price * n)
    assert collapsed.usage.cache_read_tokens == cr


def test_assistant_calls_equals_groups_plus_unpriceable(tmp_path: Path) -> None:
    """Pins the identity the old expression relied on without stating it.

    `assistant_calls` used to be `assistant_lines - duplicate_records_collapsed`, which is
    arithmetically the same value only because `assistant_lines` is incremented AFTER the
    oversize / json-error / not-assistant skips, so the two record-counted terms cancel. It
    is now computed from the groups directly. This test fails if either form drifts from
    the other — including if a future edit moves the `assistant_lines` increment above one
    of those skips, which would silently break the cancellation the old form depended on.
    """
    project, store = _materialise(tmp_path, "dedupe_split.jsonl")
    result = load_turns(project, transcript_root=store, days=3650)
    diag = result.diagnostics
    assert diag.assistant_calls == diag.assistant_lines - diag.duplicate_records_collapsed
    assert diag.assistant_calls == len(result.turns) + diag.skipped_by_reason.get("no_usage", 0)


def test_grouping_is_within_file_not_global(tmp_path: Path) -> None:
    """ADR-002's within-file key. Every other fixture is a single session file, so a
    global-`message.id` implementation passes all of them — yet main-loop and subagent
    records live in separate files (`*/subagents/agent-*.jsonl`) and must never merge.
    """
    project = tmp_path / "proj"
    project.mkdir()
    store = tmp_path / "transcripts"
    session_dir = store / encode_project_dir(project)
    session_dir.mkdir(parents=True)
    usage = {
        "input_tokens": 1,
        "output_tokens": 2,
        "cache_read_input_tokens": 300,
        "cache_creation_input_tokens": 0,
    }
    # Same `message.id` in two files. A global key merges them into one turn;
    # a within-file key keeps two.
    _write_group(session_dir, "SHARED", project, 2, usage)
    (session_dir / "second.jsonl").write_text(
        (session_dir / "SHARED.jsonl").read_text(encoding="utf-8"), encoding="utf-8"
    )

    turns = load_turns(project, transcript_root=store, days=3650).turns
    assert len(turns) == 2, "one call per file — a global message.id key would give 1"


def test_records_without_a_message_id_are_never_grouped(tmp_path: Path) -> None:
    """The absent case, which is this repo's #1 recorded failure mode (count 8).

    ADR-002 promises each id-less record gets a unique sentinel. An implementation that
    groups them under a shared falsy key collapses an entire legacy-format transcript into
    ONE turn — and no other fixture here contains an id-less record, so that bug would
    ship with the suite fully green.
    """
    project = tmp_path / "proj"
    project.mkdir()
    store = tmp_path / "transcripts"
    session_dir = store / encode_project_dir(project)
    session_dir.mkdir(parents=True)
    lines = []
    for i in range(3):
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "uuid": f"noid-{i}",
                    "timestamp": f"2026-07-20T10:0{i}:00.000Z",
                    "cwd": str(project),
                    "message": {
                        "model": _MODEL,
                        "usage": {
                            "input_tokens": 1,
                            "output_tokens": 2,
                            "cache_read_input_tokens": 100,
                            "cache_creation_input_tokens": 0,
                        },
                        "content": [{"type": "text", "text": f"n{i}"}],
                    },
                }
            )
        )
    (session_dir / "legacy.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = load_turns(project, transcript_root=store, days=3650)
    assert len(result.turns) == 3, "three id-less records are three turns, not one"
    assert result.diagnostics.duplicate_records_collapsed == 0
