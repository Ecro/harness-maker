"""SPEC-price-table-current-models: current-model rates, the fallback trace, the corrected record.

`claude-sonnet-5-5` had no row and was priced by `sonnet-5` with no signal, which doubled its
cache-read rate and inflated the recorded hm cost ratio. Expected dollars here are computed from the
published rates, never from PRICE_TABLE.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from harness_maker.economics import (
    PRICE_TABLE_EFFECTIVE_DATE,
    PRICE_TABLE_VERSION,
    TokenUsage,
    TurnRecord,
    aggregate,
    price_turn,
    resolve_model_family,
)
from tests.unit import test_bench_tier3 as tier3

_REPO = Path(__file__).resolve().parents[2]
_GOLDEN = json.loads(
    (_REPO / "specs/SPEC-price-table-current-models.golden.json").read_text(encoding="utf-8")
)
_RESULTS = _REPO / "docs" / "evals" / "results.jsonl"


def _ids(ac: str) -> list[str]:
    return [f"{ac}-{i}" for i in range(len(_GOLDEN[ac]))]


def _turn(model: str, usage: dict[str, int] | None = None) -> TurnRecord:
    u = usage or {"input": 1000, "output": 100}
    return TurnRecord(
        session_id="s1",
        ts=datetime(2026, 11, 16, 12, 0, tzinfo=UTC),
        model=model,
        usage=TokenUsage(
            input_tokens=u.get("input", 0),
            output_tokens=u.get("output", 0),
            cache_read_tokens=u.get("cache_read", 0),
            cache_write_5m_tokens=u.get("cache_write_5m", 0),
            cache_write_1h_tokens=u.get("cache_write_1h", 0),
        ),
    )


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    return tier3._load()


@pytest.mark.parametrize("row", _GOLDEN["AC-001"], ids=_ids("AC-001"))
def test_ac_001_current_models_published_rates(row: dict[str, Any]) -> None:
    cost = price_turn(_turn(row["input"]["model"], row["input"]["usage"]))
    assert cost.total_usd == pytest.approx(row["expected"]["total_usd"], rel=1e-9)
    assert cost.priced_with_family_row is row["expected"]["family_priced"]
    assert cost.priced_with_fallback is row["expected"]["fallback"]


@pytest.mark.parametrize("row", _GOLDEN["AC-002"], ids=_ids("AC-002"))
def test_ac_002_haiku_long_prompt_card(row: dict[str, Any]) -> None:
    cost = price_turn(_turn(row["input"]["model"], row["input"]["usage"]))
    assert cost.total_usd == pytest.approx(row["expected"]["total_usd"], rel=1e-9)


@pytest.mark.parametrize("row", _GOLDEN["AC-003"], ids=_ids("AC-003"))
def test_ac_003_existing_rows_unchanged(row: dict[str, Any]) -> None:
    cost = price_turn(_turn(row["input"]["model"], row["input"]["usage"]))
    assert cost.total_usd == pytest.approx(row["expected"]["total_usd"], rel=1e-9)


@pytest.mark.parametrize("row", _GOLDEN["AC-004"], ids=_ids("AC-004"))
def test_ac_004_point_release_trace(row: dict[str, Any]) -> None:
    model = row["input"]["model"]
    turn = _turn(model)
    cost = price_turn(turn)
    assert cost.priced_with_family_row is row["expected"]["family_priced"]
    assert cost.priced_with_fallback is row["expected"]["fallback"]
    # Through the report: a flag no report reads would pass the two lines above.
    report = aggregate([turn])
    expected = {model: 1} if row["expected"]["family_priced"] else {}
    assert report.family_priced_models == expected
    assert report.family_priced_turns == len(expected)


def test_long_prompt_card_applies_through_the_fallback_model() -> None:
    """`price_model` is free text: an unknown turn priced as Haiku 5.5 takes its cards too."""
    turn = _turn("some-unknown-model", {"input": 200_000, "output": 10_000})
    cost = price_turn(turn, fallback_model="claude-haiku-5-5")
    assert cost.priced_with_fallback is True
    assert cost.total_usd == pytest.approx(200_000 * 0.5 / 1e6 + 10_000 * 2.5 / 1e6, rel=1e-9)


@pytest.mark.parametrize(
    ("model", "family"),
    [
        ("sonnet4.5", "sonnet"),  # free-text price_model spelling: a bare key is not guarded
        ("claude-haiku35", "haiku"),
        ("claude-fable-5-20260401", "fable-5"),
        ("claude-fable-5-2", "fable-5-2"),
        ("claude-fable-5-2-20261001", "fable-5-2"),
        ("claude-opus-50", "opus"),  # `opus-5` is guarded, the bare family row still resolves
    ],
)
def test_a_key_ending_in_a_digit_does_not_match_before_a_digit(model: str, family: str) -> None:
    assert resolve_model_family(model) == family


def test_the_bench_row_counts_family_priced_turns(
    bench: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bench is where the wrong rate was recorded, so the trace has to reach its rows."""
    turns = [_turn("claude-sonnet-5-6"), _turn("claude-sonnet-5-5"), _turn("claude-fable-5-3")]

    class _Loaded:
        def __init__(self) -> None:
            self.turns = turns

    monkeypatch.setattr(bench.economics_source, "load_turns", lambda *a, **k: _Loaded())
    spend = bench.transcript_cost(tmp_path, tmp_path)
    assert spend.turns == 3
    assert spend.family_priced_turns == 2


def test_ac_005_table_is_version_4() -> None:
    assert PRICE_TABLE_VERSION == "4"
    assert PRICE_TABLE_EFFECTIVE_DATE == "2026-11-16"
    report = aggregate([_turn("claude-sonnet-5-5")])
    assert report.price_table_version == "4"
    assert report.price_table_effective_date == "2026-11-16"


def test_ac_006_recorded_rows_agree_with_cli(bench: ModuleType) -> None:
    rows = [json.loads(line) for line in _RESULTS.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 30
    for r in rows:
        where = (r["task"], r["arm"], r["rep"])
        assert r.get("price_table_version") == "4", where
        repriced = r["transcript_cost_usd_table_v3"] - r["tokens"]["cache_read"] * 0.10 / 1e6
        assert abs(r["transcript_cost_usd"] - repriced) <= 1e-6, where
        assert abs(r["transcript_cost_usd"] - r["cli_cost_usd"]) / r["cli_cost_usd"] <= 0.005, where
    summary = bench.summarize(rows)
    assert summary["verdict"] == "met"
    assert summary["ratio"] == 6.984


def test_ac_007_text_says_cli_includes_subagent_spend(bench: ModuleType, tmp_path: Path) -> None:
    out, repo = tier3._tier3_repo(tmp_path, tier3._pilot(tier3._PILOT_SOLVED), tier3._diagnostic())
    assert tier3._publish3(bench, out, repo) == 0
    rows = bench.publish_rows(out)
    results = (repo / "docs" / "evals" / "RESULTS.md").read_text(encoding="utf-8")
    section = results[len(bench.render_results_md(rows)) :]
    readme = (repo / "README.md").read_text(encoding="utf-8")
    block = readme[readme.index("**Tier 3**") : readme.index("<!-- hm:eval:end -->")]
    for text in (section, block):
        assert "includes subagent spend" in text
        assert "excludes subagent spend" not in text
        assert "understates" not in text

    gap_rows = [tier3._row("t1", arm, rep, solved=True, cost=cost, tier=1)
                for arm, cost in (("plain", 0.10), ("hm", 0.40)) for rep in (1, 2, 3)]  # fmt: skip
    for r in gap_rows:
        if r["arm"] == "hm":
            r["transcript_cost_usd"] = 1.20
    summary = bench.summarize(gap_rows)
    assert summary["verdict"] == "suspect"
    assert "price table" in summary["why"]
    assert "subagent" not in summary["why"]

    docs = _REPO / "docs" / "evals"
    committed_rows = bench.publish_rows(docs)
    t3 = bench.tier3_inputs(docs / "tier3")
    committed = (docs / "RESULTS.md").read_text(encoding="utf-8")
    assert committed == bench.render_results_md(committed_rows, t3)
    assert "leaves out subagent spend" not in committed
    root_readme = (_REPO / "README.md").read_text(encoding="utf-8")
    assert bench.splice_readme(root_readme, bench.render_readme_block(committed_rows, t3)) == (
        root_readme
    )
