"""AC-012 — the re-review churn threshold resolves from config with a documented default."""

from pathlib import Path

import pytest

from harness_maker.review_churn import ChurnConfigError, resolve_churn_threshold
from harness_maker.spec_machine import load_golden_table

_SPEC = Path(__file__).parents[2] / "specs" / "SPEC-review-loop-empirics.machine.yaml"
_ROWS = load_golden_table(_SPEC, "AC-012")


def _as_yaml_value(config_value: str) -> object:
    """Turn a golden-table cell into the object PyYAML would have produced.

    Review found the earlier version passed `str(...)` straight through, so the
    resolver only ever saw strings and the `isinstance(raw, bool)` guard was never
    reached by any row. A real `harness.yaml` yields native types, so the fixture
    has to as well or the table tests a shape that cannot occur.
    """
    try:
        return float(config_value)
    except ValueError:
        return config_value


def _reviewers_block(config_value: str) -> dict[str, object]:
    """Build the `reviewers` mapping the golden row describes.

    `absent` means the key is missing entirely — the CLAUDE.md 2026-06-08
    absent-case rule is the reason this row exists at all.
    """
    if config_value == "absent":
        return {"enabled": ["code-reviewer"]}
    return {"enabled": ["code-reviewer"], "rereview_churn_ratio": _as_yaml_value(config_value)}


@pytest.mark.parametrize(
    "row",
    _ROWS,
    ids=[str(r.input["config"]) for r in _ROWS],
)
def test_churn_threshold_absent_and_explicit_and_invalid(row: object) -> None:
    reviewers = _reviewers_block(str(row.input["config"]))  # type: ignore[attr-defined]
    expected = row.expected  # type: ignore[attr-defined]

    if expected == "load-time error":
        with pytest.raises(ChurnConfigError):
            resolve_churn_threshold(reviewers)
    else:
        assert resolve_churn_threshold(reviewers) == pytest.approx(float(expected))


def test_ratio_rejects_bool_which_python_would_otherwise_accept_as_a_number() -> None:
    """`True` is an `int` subclass, so a bare numeric check would read it as 1.0."""
    with pytest.raises(ChurnConfigError):
        resolve_churn_threshold({"rereview_churn_ratio": True})


def test_gate_enabled_defaults_true_when_key_absent() -> None:
    """AC-019's precondition: an absent gate key is ON, not silently off."""
    from harness_maker.review_churn import churn_gate_enabled

    assert churn_gate_enabled({"enabled": ["code-reviewer"]}) is True
    assert churn_gate_enabled({"rereview_churn_gate": False}) is False
    assert churn_gate_enabled({"rereview_churn_gate": True}) is True


def test_gate_flag_rejects_non_bool() -> None:
    """A malformed flag is a load-time error, never a silent fallback."""
    from harness_maker.review_churn import churn_gate_enabled

    with pytest.raises(ChurnConfigError):
        churn_gate_enabled({"rereview_churn_gate": "yes"})
