"""Tests for the autoloop driver (M7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.autoloop_driver import (
    AutoloopState,
    ErrorClass,
    Feature,
    ImprovementContext,
    LoopMode,
    LoopSpec,
    check_error_cap,
    classify_error,
    detect_mode,
    is_loop_consumable,
    parse_goal,
    parse_loop_context,
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

    state = run("a;b;c;d;e", max_iter=10, executor=always_fail, failed_streak_cap=3)
    assert state.failed_streak >= 3
    assert state.converged is False
    assert state.stop_reason == "3 consecutive failures"
    assert state.iter == 3


def test_failed_streak_cap_default_5() -> None:
    """Default failed_streak_cap is 5; loop continues past 3 failures."""

    def always_fail(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return False

    state = run("a;b;c;d;e;f;g", max_iter=20, executor=always_fail)
    assert state.failed_streak >= 5
    assert "5 consecutive failures" in state.stop_reason


def test_max_iter_default_50() -> None:
    """Default max_iter is 50."""
    import inspect

    sig = inspect.signature(run)
    assert sig.parameters["max_iter"].default == 50


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
    """One failure followed by success should NOT trip the 3-failure halt.

    Feature 'a' fails once (iter 1) then succeeds (iter 2); b and c succeed
    on first try (iters 3–4). Exactly 4 executor calls → iterator safe with
    max_iter=10 (cap check fires before convergence check at loop top, so
    max_iter must be > number of executor calls, not equal).
    """
    call_results = iter([False, True, True, True])

    def varied(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return next(call_results)

    state = run("a;b;c", max_iter=10, executor=varied)
    assert state.converged is True
    assert state.completed == ["a", "b", "c"]
    assert state.failed_streak == 0
    assert state.iter == 4


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


def test_run_with_loopspec_uses_features_and_acceptance() -> None:
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


def test_is_loop_consumable_strips_provenance_frontmatter() -> None:
    """Renderer-wrapped specs (with --- frontmatter) are still consumable."""
    wrapped = "---\ngenerated_by: harness-maker\n---\nobjective: x\nfeatures:\n  - name: foo\n"
    assert is_loop_consumable(wrapped) is True


def test_is_loop_consumable_frontmatter_improve_mode() -> None:
    """Frontmatter-wrapped improve-mode spec is consumable."""
    wrapped = "---\ngenerated_by: harness-maker\n---\nmode: improve\nobjective: improve auth\n"
    assert is_loop_consumable(wrapped) is True


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


# ──────────────────────────────────────────────────────────────────────────────
# LoopMode + detect_mode
# ──────────────────────────────────────────────────────────────────────────────


def test_detect_mode_returns_feature_by_default() -> None:
    assert detect_mode("implement login flow") == LoopMode.FEATURE
    assert detect_mode("add logout endpoint") == LoopMode.FEATURE
    assert detect_mode("build user profile page") == LoopMode.FEATURE


def test_detect_mode_returns_improve_on_keywords() -> None:
    assert detect_mode("improve code quality") == LoopMode.IMPROVE
    assert detect_mode("refactor auth module") == LoopMode.IMPROVE
    assert detect_mode("clean up this service") == LoopMode.IMPROVE
    assert detect_mode("optimize database queries") == LoopMode.IMPROVE
    assert detect_mode("코드 품질 개선") == LoopMode.IMPROVE
    assert detect_mode("리팩토링 필요") == LoopMode.IMPROVE


def test_detect_mode_case_insensitive() -> None:
    assert detect_mode("IMPROVE the API") == LoopMode.IMPROVE
    assert detect_mode("Refactor this module") == LoopMode.IMPROVE


def test_detect_mode_empty_goal_returns_feature() -> None:
    assert detect_mode("") == LoopMode.FEATURE


# ──────────────────────────────────────────────────────────────────────────────
# ImprovementContext + LoopContext
# ──────────────────────────────────────────────────────────────────────────────


def _make_context() -> ImprovementContext:
    return ImprovementContext(
        purpose="JWT auth handler. Called by API gateway on every request.",
        invariants=["RS256 algorithm only", "/auth/token signature stable"],
        priority="safety > performance > readability",
        test_reliability="e2e: 12 scenarios, unit: 78% coverage. Missing token-expiry cases.",
        stopping_criteria="0 critical/high issues, ≤2 medium, all e2e passing",
    )


def test_improvement_context_fields() -> None:
    ctx = _make_context()
    assert ctx.purpose.startswith("JWT")
    assert len(ctx.invariants) == 2
    assert ctx.notes == []


def test_improvement_context_notes_field() -> None:
    ctx = ImprovementContext(
        purpose="x",
        invariants=[],
        priority="readability > safety > performance",
        test_reliability="low",
        stopping_criteria="no critical issues",
        notes=["Redis out of scope", "rate limiting is gateway's job"],
    )
    assert len(ctx.notes) == 2


def test_loop_context_round_trip(tmp_path: Path) -> None:
    ctx_path = tmp_path / "auth-service.yaml"
    ctx_path.write_text(
        "slug: auth-service\n"
        "source: TECH_SPEC.md\n"
        "created_at: '2026-05-04'\n"
        "updated_at: '2026-05-04'\n"
        "context:\n"
        "  purpose: JWT auth handler\n"
        "  invariants:\n"
        "    - RS256 only\n"
        "  priority: safety > performance > readability\n"
        "  test_reliability: medium\n"
        "  stopping_criteria: no critical issues\n"
        "  notes: []\n",
        encoding="utf-8",
    )
    lc = parse_loop_context(ctx_path)
    assert lc.slug == "auth-service"
    assert lc.source == "TECH_SPEC.md"
    assert lc.context.purpose == "JWT auth handler"
    assert lc.context.invariants == ["RS256 only"]


def test_parse_loop_context_strips_frontmatter(tmp_path: Path) -> None:
    ctx_path = tmp_path / "ctx.yaml"
    ctx_path.write_text(
        "---\ngenerated_by: harness-maker\n---\n"
        "slug: foo\n"
        "source: ''\n"
        "created_at: '2026-05-04'\n"
        "updated_at: '2026-05-04'\n"
        "context:\n"
        "  purpose: does stuff\n"
        "  invariants: []\n"
        "  priority: readability\n"
        "  test_reliability: low\n"
        "  stopping_criteria: none\n"
        "  notes: []\n",
        encoding="utf-8",
    )
    lc = parse_loop_context(ctx_path)
    assert lc.slug == "foo"


# ──────────────────────────────────────────────────────────────────────────────
# LoopSpec with mode / context / context_ref
# ──────────────────────────────────────────────────────────────────────────────


def test_loopspec_features_optional() -> None:
    """LoopSpec without features field is valid (improve mode)."""
    spec = LoopSpec(objective="improve auth module", mode=LoopMode.IMPROVE)
    assert spec.features == []
    assert spec.mode == LoopMode.IMPROVE
    # improve mode overrides the class-level default convergence
    assert spec.convergence == "stopping-criteria"


def test_loopspec_improve_explicit_convergence_not_overridden() -> None:
    """Explicitly set convergence on improve mode is preserved."""
    spec = LoopSpec(
        objective="improve auth",
        mode=LoopMode.IMPROVE,
        convergence="first-iter",
    )
    assert spec.convergence == "first-iter"


def test_loopspec_feature_mode_convergence_default_unchanged() -> None:
    """feature mode still defaults to all-features-completed."""
    spec = LoopSpec(objective="build foo", features=[Feature(name="a")])
    assert spec.convergence == "all-features-completed"


def test_loopspec_with_inline_context() -> None:
    ctx = _make_context()
    spec = LoopSpec(
        objective="improve auth",
        mode=LoopMode.IMPROVE,
        target="src/auth/",
        context=ctx,
    )
    assert spec.context is not None
    assert spec.context.purpose.startswith("JWT")
    assert spec.target == "src/auth/"


def test_loopspec_with_context_ref() -> None:
    spec = LoopSpec(
        objective="improve auth",
        mode=LoopMode.IMPROVE,
        context_ref="work-docs/loop-context/auth-service.yaml",
    )
    assert spec.context_ref == "work-docs/loop-context/auth-service.yaml"
    assert spec.context is None


def test_parse_loop_spec_improve_mode(tmp_path: Path) -> None:
    """Improve-mode loop-spec parses correctly with context block."""
    spec_path = tmp_path / "improve-auth.yaml"
    spec_path.write_text(
        "mode: improve\n"
        "objective: improve auth module quality\n"
        "target: src/auth/\n"
        "convergence: stopping-criteria\n"
        "features: []\n"
        "context_ref: work-docs/loop-context/auth-service.yaml\n",
        encoding="utf-8",
    )
    spec = parse_loop_spec(spec_path)
    assert spec.mode == LoopMode.IMPROVE
    assert spec.target == "src/auth/"
    assert spec.convergence == "stopping-criteria"
    assert spec.context_ref == "work-docs/loop-context/auth-service.yaml"


def test_is_loop_consumable_improve_mode_empty_features() -> None:
    """improve mode with no features list is still consumable."""
    yaml_text = "mode: improve\nobjective: improve auth\ntarget: src/auth/\n"
    assert is_loop_consumable(yaml_text) is True


def test_is_loop_consumable_feature_mode_still_requires_features() -> None:
    """feature mode (default) without features is not consumable."""
    yaml_text = "objective: build foo\n"
    assert is_loop_consumable(yaml_text) is False


def test_parse_loop_spec_rejects_invalid_mode(tmp_path: Path) -> None:
    """Invalid mode value raises ValidationError, not a silent default."""
    spec_path = tmp_path / "bad-mode.yaml"
    spec_path.write_text(
        "objective: x\nmode: invalid_value\nfeatures:\n  - name: a\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        parse_loop_spec(spec_path)


def test_run_improve_spec_empty_features_exits_immediately() -> None:
    """Improve-mode spec with no features exits with no_remaining_features, not converged."""
    spec = LoopSpec(objective="improve auth module", mode=LoopMode.IMPROVE)
    assert spec.features == []
    state = run(spec=spec, max_iter=5)
    assert state.converged is False
    assert state.stop_reason == "no_remaining_features"
    assert state.iter == 0


def test_stopping_criteria_predicate_registered() -> None:
    """stopping-criteria is a valid predicate name — no unknown-predicate warning."""
    spec = LoopSpec(
        objective="improve auth",
        mode=LoopMode.IMPROVE,
        convergence="stopping-criteria",
        features=[Feature(name="cycle-1")],
    )

    def succeed(feature: Feature, iter_idx: int) -> bool:  # noqa: ARG001
        return True

    state = run(spec=spec, max_iter=5, executor=succeed)
    assert state.converged is True
    assert "cycle-1" in state.completed


# --- Phase 10: Error-Class LLM Cap tests ---


class TestClassifyError:
    def test_syntax_error_detected(self) -> None:
        assert classify_error("SyntaxError: unexpected token") == ErrorClass.SYNTAX

    def test_indent_error_detected(self) -> None:
        assert classify_error("IndentationError at line 5") == ErrorClass.SYNTAX

    def test_parse_error_detected(self) -> None:
        assert classify_error("Failed to parse JSON") == ErrorClass.SYNTAX

    def test_type_error_detected(self) -> None:
        assert classify_error("TypeError: int is not callable") == ErrorClass.LOGICAL

    def test_assertion_error_detected(self) -> None:
        assert classify_error("AssertionError: expected 5 got 3") == ErrorClass.LOGICAL

    def test_name_error_detected(self) -> None:
        assert classify_error("NameError: name 'foo' is not defined") == ErrorClass.LOGICAL

    def test_unknown_error_fallback(self) -> None:
        assert classify_error("Something went wrong") == ErrorClass.UNKNOWN

    def test_case_insensitive(self) -> None:
        assert classify_error("SYNTAXERROR: bad token") == ErrorClass.SYNTAX


class TestCheckErrorCap:
    def test_syntax_under_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.SYNTAX: 3}
        assert check_error_cap(counts, ErrorClass.SYNTAX) is True

    def test_syntax_at_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.SYNTAX: 5}
        assert check_error_cap(counts, ErrorClass.SYNTAX) is False

    def test_syntax_over_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.SYNTAX: 7}
        assert check_error_cap(counts, ErrorClass.SYNTAX) is False

    def test_logical_under_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.LOGICAL: 1}
        assert check_error_cap(counts, ErrorClass.LOGICAL) is True

    def test_logical_at_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.LOGICAL: 2}
        assert check_error_cap(counts, ErrorClass.LOGICAL) is False

    def test_unknown_under_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.UNKNOWN: 2}
        assert check_error_cap(counts, ErrorClass.UNKNOWN) is True

    def test_unknown_at_cap(self) -> None:
        counts: dict[ErrorClass, int] = {ErrorClass.UNKNOWN: 3}
        assert check_error_cap(counts, ErrorClass.UNKNOWN) is False

    def test_empty_counts_safe(self) -> None:
        counts: dict[ErrorClass, int] = {}
        assert check_error_cap(counts, ErrorClass.SYNTAX) is True
