"""Tests for the autoloop driver (M7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.autoloop_driver import (
    AutoloopState,
    Feature,
    LoopSpec,
    is_loop_consumable,
    parse_goal,
    parse_loop_spec,
    run,
)


def _names(features: list[Feature]) -> list[str]:
    return [f.name for f in features]


def test_parse_goal_splits_on_semicolon() -> None:
    features = parse_goal("Add login; Add logout; Add reset")
    assert _names(features) == ["Add login", "Add logout", "Add reset"]
    assert all(f.acceptance_criteria == [] for f in features)


def test_parse_goal_keeps_dotted_tokens_intact() -> None:
    """Period inside version numbers / URLs / decimals is NOT a separator."""
    features = parse_goal("release v1.2.3; fetch from https://api.x.com/v1")
    assert _names(features) == ["release v1.2.3", "fetch from https://api.x.com/v1"]


def test_parse_goal_mixed_separators() -> None:
    features = parse_goal("login;logout\npasswd · oauth")
    assert _names(features) == ["login", "logout", "passwd", "oauth"]


def test_parse_goal_single_feature_no_separator() -> None:
    features = parse_goal("implement login")
    assert _names(features) == ["implement login"]


def test_parse_goal_empty_returns_empty_list() -> None:
    assert parse_goal("") == []
    assert parse_goal("   \n  ") == []


def test_dry_run_terminates_in_single_iteration() -> None:
    state = run("a;b;c", dry_run=True)
    assert state.iter == 1
    assert state.completed == ["a", "b", "c"]
    assert state.converged is True
    assert state.stop_reason == "dry_run"


def test_dry_run_does_not_invoke_executor() -> None:
    calls: list[tuple[str, int]] = []

    def boom(feature: Feature, iter_idx: int) -> bool:
        calls.append((feature.name, iter_idx))
        msg = "executor must not run in dry_run"
        raise AssertionError(msg)

    state = run("a;b", dry_run=True, executor=boom)
    assert calls == []
    assert state.converged is True


def test_max_iter_cap_halts_loop() -> None:
    """When many features + low max_iter, loop halts at cap before convergence."""

    def succeed(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return True

    state = run("a;b;c;d;e;f;g;h", max_iter=2, executor=succeed)
    assert state.iter == 2
    assert state.converged is False
    assert "max_iter" in state.stop_reason


def test_failed_streak_3_halts_loop() -> None:
    def always_fail(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return False

    state = run("a;b;c;d;e", max_iter=10, executor=always_fail)
    assert state.failed_streak >= 3
    assert state.converged is False
    assert state.stop_reason == "3 consecutive failures"
    assert state.iter == 3


def test_success_path_with_mock_executor_converges() -> None:
    seen: list[str] = []

    def succeed(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        seen.append(feature.name)
        return True

    state = run("login;logout;reset", max_iter=10, executor=succeed)
    assert state.converged is True
    assert state.completed == ["login", "logout", "reset"]
    assert seen == ["login", "logout", "reset"]
    assert state.iter == 3
    assert state.stop_reason == "converged"


def test_failure_then_success_resets_streak() -> None:
    """One failure followed by success should NOT trip the 3-failure halt."""
    call_results = iter([False, True, True, True])

    def varied(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return next(call_results)

    state = run("a;b;c;d", max_iter=10, executor=varied)
    assert state.failed_streak >= 1 or state.converged
    assert "a" in state.completed


def test_convergence_expression_can_short_circuit() -> None:
    """Custom convergence expr stops loop before all features done."""

    def succeed(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return True

    state = run(
        "a;b;c",
        max_iter=10,
        executor=succeed,
        convergence="any-feature-completed",
    )
    assert state.converged is True
    assert len(state.completed) == 1


def test_state_is_pydantic_model() -> None:
    state = AutoloopState(features=[Feature(name="x")])
    state.iter = 5
    assert state.iter == 5


# ──────────────────────────────────────────────────────────────────────────────
# Structured LoopSpec input
# ──────────────────────────────────────────────────────────────────────────────


def test_run_with_loopspec_uses_features_and_acceptance(tmp_path: Path) -> None:
    """`run(spec=...)` consumes structured features with AC."""
    spec = LoopSpec(
        objective="ship auth flow",
        convergence="all-features-completed",
        features=[
            Feature(
                name="JWT login",
                acceptance_criteria=["200 with token", "401 on invalid"],
            ),
            Feature(name="logout", acceptance_criteria=["204 + token revoked"]),
        ],
    )
    seen_ac: list[list[str]] = []

    def executor(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        seen_ac.append(list(feature.acceptance_criteria))
        return True

    state = run(spec=spec, max_iter=10, executor=executor)
    assert state.objective == "ship auth flow"
    assert state.converged is True
    assert state.completed == ["JWT login", "logout"]
    # Executor saw per-feature AC
    assert seen_ac == [
        ["200 with token", "401 on invalid"],
        ["204 + token revoked"],
    ]


def test_parse_loop_spec_round_trip(tmp_path: Path) -> None:
    spec_path = tmp_path / "loop-spec.yaml"
    spec_path.write_text(
        "objective: build foo\n"
        "convergence: min-2-features\n"
        "features:\n"
        "  - name: foo\n"
        "    acceptance_criteria:\n"
        "      - returns 200\n"
        "  - name: bar\n"
        "    acceptance_criteria: []\n",
        encoding="utf-8",
    )
    spec = parse_loop_spec(spec_path)
    assert spec.objective == "build foo"
    assert spec.convergence == "min-2-features"
    assert len(spec.features) == 2
    assert spec.features[0].acceptance_criteria == ["returns 200"]


def test_parse_loop_spec_strips_provenance_frontmatter(tmp_path: Path) -> None:
    """Renderer-wrapped loop-spec.yaml (with `---` provenance) parses cleanly."""
    spec_path = tmp_path / "wrapped.yaml"
    spec_path.write_text(
        "---\ngenerated_by: test\n---\nobjective: x\nfeatures:\n  - name: a\n",
        encoding="utf-8",
    )
    spec = parse_loop_spec(spec_path)
    assert spec.objective == "x"


def test_run_requires_goal_or_spec() -> None:
    with pytest.raises(ValueError, match="goal.*spec"):
        run()


def test_is_loop_consumable_rejects_markdown() -> None:
    md = "# Tech Spec\n\nSome description.\n\n## Features\n- foo\n- bar\n"
    assert is_loop_consumable(md) is False


def test_is_loop_consumable_accepts_well_formed_yaml() -> None:
    yaml_text = "objective: x\nfeatures:\n  - name: foo\n"
    assert is_loop_consumable(yaml_text) is True


def test_is_loop_consumable_rejects_missing_features() -> None:
    yaml_text = "objective: x\nfeatures: []\n"
    assert is_loop_consumable(yaml_text) is False


def test_is_loop_consumable_rejects_feature_without_name() -> None:
    yaml_text = "objective: x\nfeatures:\n  - acceptance_criteria: [a]\n"
    assert is_loop_consumable(yaml_text) is False


def test_spec_convergence_overridden_by_argument() -> None:
    """Explicit convergence= argument wins over spec.convergence."""
    spec = LoopSpec(
        objective="o",
        convergence="all-features-completed",
        features=[Feature(name="a"), Feature(name="b"), Feature(name="c")],
    )

    def succeed(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return True

    state = run(
        spec=spec,
        max_iter=10,
        executor=succeed,
        convergence="any-feature-completed",
    )
    assert state.converged is True
    assert len(state.completed) == 1
