"""SPEC-hm-light-lane-s3c AC-005..007 — `hm spec_machine check --all` is quiet unless a gate failed.

AC-005's rows are the SPEC's B contract (key set, line count, exit code), written before the code;
the score is set by `light_lane_s3c_fixture.scorer`, a stub of `evaluate_spec`, as
`test_spec_machine_check_all.py` already does. AC-006 and AC-007 are differentials: OLD is the
a7403f2f module's stdout and exit code on the same fixtures (`check_a7403f2f.json`, captured by
`tests/fixtures/light_lane_s3c/capture_a7403f2f.py.txt` before the edit).
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from tests.unit import light_lane_s3c_fixture as fx

OLD: dict[str, dict[str, Any]] = json.loads(
    (fx.GOLDENS / "check_a7403f2f.json").read_text(encoding="utf-8")
)["cases"]
FAIL_KEYS = {"ok", "strictness", "validate", "cross_validate", "quality"}
QUALITY_KEYS = {"overall", "weak_dimensions", "low_dimensions", "blocked", "strictness"}
YAML_SYNTAX_ERR = re.compile(r"yaml load failed: YAMLError: [^\n]+ \(line \d+, column \d+\)")
MISSING_FILE_ERR = re.compile(r"yaml load failed: (FileNotFoundError|OSError): [^\n]+")
#: A pydantic error in the quiet form, `<loc>: <msg>`; a loc is dotted field names and indices.
_PYDANTIC_LINE = re.compile(r"^([A-Za-z_]\w*(?:\.\w+)*): ")

#: AC-005's golden table: (fixture, scorer kind) -> expected.
ROWS: dict[str, tuple[str, str, dict[str, Any]]] = {
    "clean": ("valid", "clean", {"lines": 1, "keys": {"ok", "overall", "strictness"}, "exit": 0}),
    "weak": (
        "valid",
        "weak",
        {
            "lines": 1,
            "keys": {"ok", "overall", "strictness", "weak_dimensions", "low_dimensions"},
            "exit": 0,
        },
    ),
    "low": (
        "valid",
        "low",
        {
            "lines": 1,
            "keys": {"ok", "overall", "strictness", "weak_dimensions", "low_dimensions"},
            "low_dimensions_nonempty": True,
            "exit": 0,
        },
    ),
    "raise": (
        "valid",
        "raise",
        {"keys": FAIL_KEYS, "quality_keys": {"error", "strictness"}, "ok": True, "exit": 0},
    ),
    "raise_and_validate_fails": (
        "valid_fails_validate",
        "raise",
        {"keys": FAIL_KEYS, "quality_keys": {"error", "strictness"}, "ok": False, "exit": 1},
    ),
}


@pytest.mark.parametrize("row", list(ROWS))
def test_no_failed_gate_prints_one_line(row: str) -> None:
    fixture, kind, expected = ROWS[row]
    rc, out = fx.run_check(fixture, "warn", kind)
    payload = json.loads(out)
    assert rc == expected["exit"], (row, out)
    assert set(payload) == expected["keys"], (row, out)
    if "lines" in expected:
        assert out.count("\n") == expected["lines"], (row, out)
        assert payload["ok"] is True
        assert payload["strictness"] == "warn"
        scores = fx.SCORER_SCORES[kind]
        assert payload["overall"] == sum(scores.values()) // len(scores)
        if "weak_dimensions" in expected["keys"]:
            assert payload["weak_dimensions"] == [d for d, s in scores.items() if s < 40]
            assert payload["low_dimensions"] == {d: s for d, s in scores.items() if s < 60}
    if expected.get("low_dimensions_nonempty"):
        assert payload["low_dimensions"], row
    if "quality_keys" in expected:
        assert payload["ok"] is expected["ok"], (row, out)
        assert set(payload["quality"]) == expected["quality_keys"], (row, out)
        assert payload["quality"]["error"] == "RuntimeError: scorer exploded"
        assert payload["quality"]["strictness"] == "warn"


def _payload(out: str) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(out)
    return doc


def _verdict(case: dict[str, Any]) -> tuple[Any, ...]:
    p = _payload(case["stdout"])
    return (
        p["ok"],
        case["exit"],
        p["validate"]["ok"],
        p["cross_validate"]["ok"],
        p["quality"].get("blocked"),
    )


def _locations(error: str) -> set[tuple[str, str]]:
    """What an error points at, readable from both the a7403f2f and the quiet form."""
    if error == "yaml load failed (see validate.errors)":
        return set()
    first = error.splitlines()[0]
    if first.startswith("yaml load failed"):
        if "validation error" in first:
            # a7403f2f's pydantic dump: the loc lines are the unindented lines after the first.
            return {("pydantic", ln) for ln in error.splitlines()[1:] if ln and ln[0] != " "}
        return {("yaml", "load")}
    rule = re.match(r"(rule-\d): ", error)
    if rule:
        ac = re.search(r"AC-\d+", error)
        return {(rule.group(1), ac.group(0) if ac else "")}
    m = _PYDANTIC_LINE.match(error)
    if m:
        return {("pydantic", m.group(1))}
    ac = re.match(r"(AC-\d+): ", error)
    return {("validate", ac.group(1) if ac else error)}


def _error_locations(out: str) -> set[tuple[str, str]]:
    p = _payload(out)
    errors = [*p["validate"]["errors"], *p["cross_validate"]["errors"]]
    return set().union(*(_locations(e) for e in errors)) if errors else set()


def _all_errors(p: dict[str, Any]) -> list[str]:
    errors = [*p["validate"]["errors"], *p["cross_validate"]["errors"]]
    if "error" in p["quality"]:
        errors.append(p["quality"]["error"])
    return errors


@pytest.fixture(scope="module")
def new() -> dict[str, dict[str, Any]]:
    return fx.run_all_checks()


@pytest.mark.parametrize("name", list(fx.FAILURE_FIXTURES))
def test_failure_prints_each_error_once(new: dict[str, dict[str, Any]], name: str) -> None:
    case, old = new[name], OLD[name]
    out = case["stdout"]
    p = _payload(out)
    assert _verdict(case) == _verdict(old), name
    assert _error_locations(out) == _error_locations(old["stdout"]), name
    errors = _all_errors(p)
    assert len(errors) == len(set(errors)), (name, errors)
    assert "errors.pydantic.dev" not in out, name
    assert "input_value" not in out, name
    assert set(p) == FAIL_KEYS, (name, sorted(p))
    assert set(p["validate"]) == {"ok", "errors"}, name
    assert set(p["cross_validate"]) == {"ok", "errors", "by_rule"}, name
    by_rule = p["cross_validate"]["by_rule"]
    assert all(isinstance(n, int) and n > 0 for n in by_rule.values()), (name, by_rule)
    assert sum(by_rule.values()) == len(p["cross_validate"]["errors"]), name
    if name == "raise_and_validate_fails":
        assert set(p["quality"]) == {"error", "strictness"}, name
    else:
        assert set(p["quality"]) == QUALITY_KEYS, name
    if name == "block_overall_55":
        low = p["quality"]["low_dimensions"]
        assert low, name
        assert all(isinstance(s, int) and s < 60 for s in low.values()), low
        assert low == {
            d: s for d, s in _payload(old["stdout"])["quality"]["scores"].items() if s < 60
        }
        assert p["quality"]["weak_dimensions"] == []
    if name == "unparseable_yaml":
        assert YAML_SYNTAX_ERR.fullmatch(p["validate"]["errors"][0]), p["validate"]["errors"]
    if name == "missing_yaml_file":
        assert MISSING_FILE_ERR.fullmatch(p["validate"]["errors"][0]), p["validate"]["errors"]
    if not p["validate"]["ok"] and p["validate"]["errors"][0].startswith("yaml load failed"):
        assert p["cross_validate"]["errors"] == ["yaml load failed (see validate.errors)"]


def test_failure_output_is_at_most_half(new: dict[str, dict[str, Any]]) -> None:
    sizes = {n: (len(new[n]["stdout"]), len(OLD[n]["stdout"])) for n in fx.FAILURE_FIXTURES}
    assert sum(a for a, _ in sizes.values()) * 2 <= sum(b for _, b in sizes.values()), sizes
    assert all(a <= b for a, b in sizes.values()), sizes
