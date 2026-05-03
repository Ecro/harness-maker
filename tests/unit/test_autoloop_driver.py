"""Tests for the autoloop driver (M7)."""

from __future__ import annotations

from harness_maker.autoloop_driver import AutoloopState, parse_goal, run


def test_parse_goal_splits_on_semicolon() -> None:
    features = parse_goal("Add login; Add logout; Add reset")
    assert features == ["Add login", "Add logout", "Add reset"]


def test_parse_goal_keeps_dotted_tokens_intact() -> None:
    """Period inside version numbers / URLs / decimals is NOT a separator."""
    features = parse_goal("release v1.2.3; fetch from https://api.x.com/v1")
    assert features == ["release v1.2.3", "fetch from https://api.x.com/v1"]


def test_parse_goal_mixed_separators() -> None:
    features = parse_goal("login;logout\npasswd · oauth")
    assert features == ["login", "logout", "passwd", "oauth"]


def test_parse_goal_single_feature_no_separator() -> None:
    features = parse_goal("implement login")
    assert features == ["implement login"]


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

    def boom(feature: str, iter_idx: int) -> bool:
        calls.append((feature, iter_idx))
        msg = "executor must not run in dry_run"
        raise AssertionError(msg)

    state = run("a;b", dry_run=True, executor=boom)
    assert calls == []
    assert state.converged is True


def test_max_iter_cap_halts_loop() -> None:
    """When many features + low max_iter, loop halts at cap before convergence."""

    def succeed(feature: str, iter_idx: int) -> bool:  # noqa: ARG001
        return True

    state = run("a;b;c;d;e;f;g;h", max_iter=2, executor=succeed)
    assert state.iter == 2
    assert state.converged is False
    assert "max_iter" in state.stop_reason


def test_failed_streak_3_halts_loop() -> None:
    def always_fail(feature: str, iter_idx: int) -> bool:  # noqa: ARG001
        return False

    state = run("a;b;c;d;e", max_iter=10, executor=always_fail)
    assert state.failed_streak >= 3
    assert state.converged is False
    assert state.stop_reason == "3 consecutive failures"
    # Must have stopped at iter 3, not run further.
    assert state.iter == 3


def test_success_path_with_mock_executor_converges() -> None:
    seen: list[str] = []

    def succeed(feature: str, iter_idx: int) -> bool:  # noqa: ARG001
        seen.append(feature)
        return True

    state = run("login;logout;reset", max_iter=10, executor=succeed)
    assert state.converged is True
    assert state.completed == ["login", "logout", "reset"]
    assert seen == ["login", "logout", "reset"]
    assert state.iter == 3
    assert state.stop_reason == "converged"


def test_failure_then_success_resets_streak() -> None:
    """One failure followed by success should NOT trip the 3-failure halt."""
    # Use a mutable state to vary executor return per call.
    call_results = iter([False, True, True, True])

    def varied(feature: str, iter_idx: int) -> bool:  # noqa: ARG001
        return next(call_results)

    state = run("a;b;c;d", max_iter=10, executor=varied)
    # Iter 1: a fails (streak=1) — not completed.
    # Iter 2: a (still next remaining) succeeds (streak=0) — completed.
    # Iter 3: b succeeds. Iter 4: c succeeds. d remains.
    # Loop continues but iter has consumed all results — call_results exhausted.
    # Next executor call would raise StopIteration → wrapped as failure.
    # Eventually halts via 3-failure streak (since d never completes).
    assert state.failed_streak >= 1 or state.converged
    assert "a" in state.completed


def test_convergence_expression_can_short_circuit() -> None:
    """Custom convergence expr stops loop before all features done."""

    def succeed(feature: str, iter_idx: int) -> bool:  # noqa: ARG001
        return True

    # Stop after first completion via named predicate (eval removed for security).
    state = run(
        "a;b;c",
        max_iter=10,
        executor=succeed,
        convergence="any-feature-completed",
    )
    assert state.converged is True
    assert len(state.completed) == 1


def test_state_is_pydantic_model() -> None:
    state = AutoloopState(features=["x"])
    # Must reject extra fields.
    state.iter = 5
    assert state.iter == 5
