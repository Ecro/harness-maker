"""Tests for the Conditional Router (M6)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.conditional_router import route_reviewers

ALL_REVIEWERS = [
    "code-reviewer",
    "security-reviewer",
    "performance-reviewer",
    "ux-reviewer",
    "concurrency-reviewer",
]


def test_always_all_returns_preset_unchanged() -> None:
    files = [Path("src/auth/login.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="always-all")
    assert result == ALL_REVIEWERS


def test_unknown_routing_returns_preset_unchanged() -> None:
    files = [Path("src/auth/login.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="invented")
    assert result == ALL_REVIEWERS


def test_conditional_secrets_env_triggers_security() -> None:
    files = [Path(".env"), Path("src/main.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "security-reviewer" in result
    assert "code-reviewer" in result


def test_conditional_auth_path_triggers_security() -> None:
    files = [Path("src/auth/login.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "security-reviewer" in result


def test_conditional_secret_path_triggers_security() -> None:
    files = [Path("config/secret-keys.yaml")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "security-reviewer" in result


def test_conditional_perf_path_triggers_performance() -> None:
    files = [Path("src/perf/inner_loop.c")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "performance-reviewer" in result


def test_conditional_benchmark_triggers_performance() -> None:
    files = [Path("tests/benchmark_throughput.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "performance-reviewer" in result


def test_conditional_hot_triggers_performance() -> None:
    files = [Path("src/hot_path.rs")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "performance-reviewer" in result


def test_conditional_tsx_triggers_ux() -> None:
    files = [Path("src/components/Button.tsx")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "ux-reviewer" in result


def test_conditional_jsx_triggers_ux() -> None:
    files = [Path("src/Button.jsx")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "ux-reviewer" in result


def test_conditional_ui_path_triggers_ux() -> None:
    files = [Path("src/ui/dashboard.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "ux-reviewer" in result


def test_conditional_thread_triggers_concurrency() -> None:
    files = [Path("src/thread_pool.cpp")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "concurrency-reviewer" in result


def test_conditional_isr_triggers_concurrency() -> None:
    files = [Path("firmware/isr_uart.c")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "concurrency-reviewer" in result


def test_conditional_worker_triggers_concurrency() -> None:
    files = [Path("src/background_worker.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "concurrency-reviewer" in result


def test_conditional_async_triggers_concurrency() -> None:
    files = [Path("src/async_handler.py")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "concurrency-reviewer" in result


def test_conditional_no_match_still_includes_code_reviewer() -> None:
    files = [Path("docs/README.md")]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert result == ["code-reviewer"]


def test_conditional_multi_match_combines() -> None:
    files = [
        Path("src/auth/secret.py"),
        Path("src/perf/inner.c"),
        Path("src/ui/Button.tsx"),
    ]
    result = route_reviewers(files, ALL_REVIEWERS, routing="conditional")
    assert "security-reviewer" in result
    assert "performance-reviewer" in result
    assert "ux-reviewer" in result
    assert "code-reviewer" in result


def test_conditional_respects_preset_omission() -> None:
    """If the preset omits a reviewer, conditional routing must not invent it."""
    minimal_preset = ["code-reviewer"]  # Side preset
    files = [Path("src/auth/login.py")]
    result = route_reviewers(files, minimal_preset, routing="conditional")
    # security-reviewer was matched but not in preset → must NOT appear
    assert result == ["code-reviewer"]


def test_conditional_preserves_preset_ordering() -> None:
    files = [
        Path(".env"),
        Path("src/perf/x.c"),
    ]
    preset = [
        "code-reviewer",
        "security-reviewer",
        "performance-reviewer",
        "ux-reviewer",
        "concurrency-reviewer",
    ]
    result = route_reviewers(files, preset, routing="conditional")
    assert result == ["code-reviewer", "security-reviewer", "performance-reviewer"]


def test_conditional_empty_files_falls_back_to_code_reviewer() -> None:
    result = route_reviewers([], ALL_REVIEWERS, routing="conditional")
    assert result == ["code-reviewer"]
