"""Tests for spec_inventory.reverse_map (P0, ADR-010)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.spec_inventory import (
    AC_TYPES,
    GATE_A_MIN_CONFIDENCE,
    GATE_A_MIN_ENTRIES,
    JudgeProtocol,
    TestInventoryEntry,
    classify_test,
    collect_tests,
    extract_test_context,
    reverse_map,
    sample_for_review,
    to_json,
    verify_inventory,
)
from harness_maker.spec_inventory.__main__ import main as _cli_main
from harness_maker.spec_inventory.reverse_map import (
    _clip_confidence,
    _heuristic_feature,
    _normalize_ac_type,
)


class _StubJudge:
    """Deterministic stub conforming to JudgeProtocol."""

    def __init__(self, response: dict[str, Any] | str) -> None:
        self._response = response

    def judge(self, system: str, user: str, model: str) -> str:
        if isinstance(self._response, str):
            return self._response
        return json.dumps(self._response)


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------


def test_heuristic_feature_strips_test_prefix() -> None:
    assert _heuristic_feature("tests/unit/test_render.py", "test_render_emits") == "render"


def test_heuristic_feature_handles_missing_prefix() -> None:
    assert _heuristic_feature("tests/unit/render.py", "test_x") == "render"


def test_heuristic_feature_fallback_unknown() -> None:
    # An empty stem after stripping should fall through to "unknown".
    assert _heuristic_feature("tests/unit/test_.py", "test_x") == "unknown"


def test_normalize_ac_type_known_values() -> None:
    for t in AC_TYPES:
        assert _normalize_ac_type(t) == t


def test_normalize_ac_type_unknown_defaults_mechanical() -> None:
    assert _normalize_ac_type("structural") == "mechanical"
    assert _normalize_ac_type(None) == "mechanical"


def test_clip_confidence_bounds() -> None:
    assert _clip_confidence(-0.5) == 0.0
    assert _clip_confidence(1.5) == 1.0
    assert _clip_confidence(0.75) == pytest.approx(0.75)
    assert _clip_confidence("not-a-number") == 0.5


# ---------------------------------------------------------------------------
# AST walkers
# ---------------------------------------------------------------------------


def _make_tests_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tests" / "unit"
    d.mkdir(parents=True)
    return d


def test_collect_tests_finds_test_functions(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_foo.py").write_text(
        "def test_a():\n    assert 1\ndef test_b():\n    pass\ndef helper():\n    pass\n"
    )
    out = collect_tests(tmp_path)
    names = sorted(fn for _, fn in out)
    assert names == ["test_a", "test_b"]


def test_collect_tests_skips_fixtures_and_conftest(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_x.py").write_text("def test_keep(): assert 1\n")
    fix = td / "fixtures"
    fix.mkdir()
    (fix / "test_fixture.py").write_text("def test_should_skip(): assert 1\n")
    (td / "conftest.py").write_text("def test_should_also_skip(): assert 1\n")
    out = collect_tests(tmp_path)
    assert sorted(fn for _, fn in out) == ["test_keep"]


def test_collect_tests_deterministic_ordering(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_b.py").write_text("def test_two(): assert 1\n")
    (td / "test_a.py").write_text("def test_one(): assert 1\n")
    out = collect_tests(tmp_path)
    files = [str(p) for p, _ in out]
    assert files == sorted(files)


def test_collect_tests_handles_syntax_errors(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_good.py").write_text("def test_one(): assert 1\n")
    (td / "test_broken.py").write_text("def test_x(:\n    syntax error\n")
    out = collect_tests(tmp_path)
    assert any(fn == "test_one" for _, fn in out)
    # broken file is silently skipped
    assert all("test_broken.py" not in str(p) for p, _ in out)


def test_extract_test_context_returns_docstring_and_snippet(tmp_path: Path) -> None:
    f = tmp_path / "test_x.py"
    f.write_text(
        "def test_alpha():\n"
        "    '''A first test.'''\n"
        "    x = 1\n"
        "    assert x == 1\n"
        "    assert x > 0\n"
        "    assert x != 5\n"
        "    assert x is not None\n"
    )
    ctx = extract_test_context(f, "test_alpha")
    assert ctx["docstring"] == "A first test."
    snippet_lines = ctx["snippet"].split("\n")
    # cap is 3 assertions
    assert len(snippet_lines) == 3


def test_extract_test_context_missing_fn_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "test_x.py"
    f.write_text("def test_a(): assert 1\n")
    ctx = extract_test_context(f, "test_does_not_exist")
    assert ctx == {"docstring": "", "snippet": ""}


def test_extract_test_context_first_3_asserts_in_source_order(tmp_path: Path) -> None:
    """Asserts inside nested ``if`` must not jump ahead of top-level asserts."""
    f = tmp_path / "test_y.py"
    f.write_text(
        "def test_z():\n"
        "    assert 'top1' == 'top1'\n"
        "    if True:\n"
        "        assert 'nested' == 'nested'\n"
        "    assert 'top2' == 'top2'\n"
        "    assert 'top3' == 'top3'\n"
        "    assert 'top4_should_not_appear' == 'top4_should_not_appear'\n"
    )
    ctx = extract_test_context(f, "test_z")
    lines = ctx["snippet"].split("\n")
    assert len(lines) == 3
    # source-order should put top1 first, then nested (line 4), then top2 (line 5)
    assert "top1" in lines[0]
    assert "nested" in lines[1]
    assert "top2" in lines[2]
    # top3 / top4 must NOT appear (cap=3)
    assert "top3" not in ctx["snippet"]
    assert "top4_should_not_appear" not in ctx["snippet"]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classify_test_with_stub_judge() -> None:
    judge = _StubJudge(
        {
            "feature": "render",
            "ac_summary": "renders content_hash in frontmatter",
            "ac_type": "mechanical",
            "confidence": 0.9,
        }
    )
    entry = classify_test(
        test_id="tests/unit/test_render.py::test_x",
        docstring="renders frontmatter",
        snippet="assert content_hash in out",
        judge=judge,
    )
    assert entry.inferred_feature == "render"
    assert entry.inferred_ac_summary == "renders content_hash in frontmatter"
    assert entry.ac_type == "mechanical"
    assert entry.confidence == pytest.approx(0.9)


def test_classify_test_without_judge_uses_heuristic() -> None:
    entry = classify_test(
        test_id="tests/unit/test_render.py::test_x",
        docstring="renders frontmatter",
        snippet="",
        judge=None,
    )
    assert entry.inferred_feature == "render"
    # heuristic confidence is intentionally < 1.0 to surface unverified state
    assert entry.confidence < 1.0


def test_classify_test_judge_error_falls_back_gracefully() -> None:
    judge = _StubJudge("not valid json")
    entry = classify_test(
        test_id="tests/unit/test_render.py::test_x",
        docstring="d",
        snippet="s",
        judge=judge,
    )
    assert entry.inferred_feature == "render"
    # error path uses lower confidence than no-judge path
    assert entry.confidence == pytest.approx(0.3)


def test_classify_test_normalizes_bad_ac_type() -> None:
    judge = _StubJudge(
        {
            "feature": "render",
            "ac_summary": "x",
            "ac_type": "structural",  # not in AC_TYPES → mechanical
            "confidence": 0.8,
        }
    )
    entry = classify_test(
        test_id="t::f",
        docstring="",
        snippet="",
        judge=judge,
    )
    assert entry.ac_type == "mechanical"


def test_classify_test_clips_out_of_range_confidence() -> None:
    judge = _StubJudge(
        {"feature": "x", "ac_summary": "y", "ac_type": "mechanical", "confidence": 2.0}
    )
    entry = classify_test(test_id="t::f", docstring="", snippet="", judge=judge)
    assert entry.confidence == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def test_reverse_map_walks_all_tests(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_a.py").write_text("def test_one(): assert 1\n")
    (td / "test_b.py").write_text("def test_two(): assert 2\n")
    judge = _StubJudge(
        {"feature": "x", "ac_summary": "y", "ac_type": "mechanical", "confidence": 0.7}
    )
    entries = reverse_map(tmp_path, judge=judge)
    assert len(entries) == 2
    assert all(e.confidence == pytest.approx(0.7) for e in entries)


def test_reverse_map_progress_callback_invoked(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_a.py").write_text("def test_one(): assert 1\n")
    (td / "test_b.py").write_text("def test_two(): assert 2\n")
    calls: list[tuple[int, int]] = []

    def cb(i: int, total: int, entry: TestInventoryEntry) -> None:
        calls.append((i, total))

    reverse_map(tmp_path, judge=None, progress_callback=cb)
    assert len(calls) == 2
    assert calls[-1] == (2, 2)


def test_reverse_map_callback_exceptions_dont_break(tmp_path: Path) -> None:
    td = _make_tests_dir(tmp_path)
    (td / "test_a.py").write_text("def test_one(): assert 1\n")

    def bad_cb(*_a: Any, **_kw: Any) -> None:
        raise RuntimeError("callback explodes")

    entries = reverse_map(tmp_path, judge=None, progress_callback=bad_cb)
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# Serialization + verification
# ---------------------------------------------------------------------------


def test_to_json_round_trip() -> None:
    entry = TestInventoryEntry(
        test_id="t::f",
        file="t",
        inferred_ac_summary="summary",
        inferred_feature="feat",
        ac_type="mechanical",
        confidence=0.5,
    )
    blob = to_json([entry])
    out = json.loads(blob)
    assert out[0]["confidence"] == 0.5
    assert out[0]["ac_type"] == "mechanical"
    # ensure trailing newline (POSIX file convention)
    assert blob.endswith("\n")


def _write_inventory(path: Path, n: int, conf: float) -> None:
    data = [
        {
            "test_id": f"tests/unit/test_x.py::test_n{i}",
            "file": "tests/unit/test_x.py",
            "inferred_ac_summary": "stub",
            "inferred_feature": "x",
            "ac_type": "mechanical",
            "confidence": conf,
        }
        for i in range(n)
    ]
    path.write_text(json.dumps(data))


def test_verify_inventory_gate_a_pass(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=GATE_A_MIN_ENTRIES + 5, conf=0.9)
    report = verify_inventory(p)
    assert report["count"] == GATE_A_MIN_ENTRIES + 5
    assert report["avg_confidence"] == pytest.approx(0.9)
    assert report["passes_gate_a"] is True


def test_verify_inventory_gate_a_fail_low_count(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=10, conf=0.99)
    report = verify_inventory(p)
    assert report["passes_gate_a"] is False


def test_verify_inventory_gate_a_fail_low_confidence(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=GATE_A_MIN_ENTRIES + 5, conf=GATE_A_MIN_CONFIDENCE - 0.1)
    report = verify_inventory(p)
    assert report["passes_gate_a"] is False


def test_verify_inventory_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    p.write_text("[]")
    report = verify_inventory(p)
    assert report == {"count": 0, "avg_confidence": 0.0, "passes_gate_a": False}


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def test_sample_for_review_returns_n_entries(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=50, conf=0.9)
    sample = sample_for_review(p, n=10)
    assert len(sample) == 10


def test_sample_for_review_deterministic_seed(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=50, conf=0.9)
    a = sample_for_review(p, n=10, seed=42)
    b = sample_for_review(p, n=10, seed=42)
    c = sample_for_review(p, n=10, seed=7)
    assert a == b
    assert a != c  # different seed → different sample


def test_sample_for_review_caps_at_available(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=5, conf=0.9)
    sample = sample_for_review(p, n=100)
    assert len(sample) == 5


def test_sample_for_review_empty(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    p.write_text("[]")
    assert sample_for_review(p) == []


def test_verify_inventory_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    p.write_text("{not valid json}")
    rep = verify_inventory(p)
    assert rep["passes_gate_a"] is False
    assert rep["count"] == 0


def test_sample_for_review_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "inv.json"
    p.write_text("not [ valid")
    assert sample_for_review(p) == []


def test_verify_inventory_missing_file(tmp_path: Path) -> None:
    rep = verify_inventory(tmp_path / "nope.json")
    assert rep["passes_gate_a"] is False


def test_sample_for_review_missing_file(tmp_path: Path) -> None:
    assert sample_for_review(tmp_path / "nope.json") == []


# ---------------------------------------------------------------------------
# Package surface — public exports remain stable
# ---------------------------------------------------------------------------


def test_public_surface_includes_judge_protocol_and_gate_constants() -> None:
    """JudgeProtocol is runtime-conformance-checkable; constants are pinned.

    REVIEW T-P1-A: prior `assert JudgeProtocol is not None` was tautological
    (a Protocol class can never be None after a successful import). Real
    contract: the protocol enforces the `judge(system, user, model)` shape
    at isinstance() time (runtime_checkable).
    """

    class _Conformant:
        def judge(self, system: str, user: str, model: str) -> str:
            return "{}"

    class _NonConformant:
        pass

    assert isinstance(_Conformant(), JudgeProtocol)
    assert not isinstance(_NonConformant(), JudgeProtocol)
    assert frozenset({"mechanical", "parametric", "judgment"}) == AC_TYPES
    assert GATE_A_MIN_ENTRIES == 145
    assert pytest.approx(0.85) == GATE_A_MIN_CONFIDENCE


# ---------------------------------------------------------------------------
# CLI entry point — exit-code contract
# ---------------------------------------------------------------------------


def test_cli_no_subcommand_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli_main([]) == 2


def test_cli_verify_inventory_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=GATE_A_MIN_ENTRIES + 5, conf=0.9)
    rc = _cli_main(["verify-inventory", str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "passes_gate_a" in out


def test_cli_verify_inventory_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=10, conf=0.99)
    rc = _cli_main(["verify-inventory", str(p)])
    assert rc == 1


def test_cli_sample_for_review_returns_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "inv.json"
    _write_inventory(p, n=50, conf=0.9)
    rc = _cli_main(["sample-for-review", str(p), "-n", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert len(parsed) == 5
