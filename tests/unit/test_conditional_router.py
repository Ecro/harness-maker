"""Tests for the Conditional Router (M6) — rule-based + LLM-driven variants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_maker.conditional_router import (
    _parse_router_response,
    _strip_markdown_fence,
    route_reviewers,
    route_with_llm,
)

ALL_REVIEWERS = [
    "code-reviewer",
    "security-reviewer",
    "performance-reviewer",
    "ux-reviewer",
    "concurrency-reviewer",
]


class _FakeJudge:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def judge(self, system: str, user: str, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


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


# ── route_with_llm ─────────────────────────────────────────────────────────


def _llm_response(reviewers: list[str]) -> str:
    return json.dumps({"reviewers": reviewers})


def test_strip_fence() -> None:
    assert _strip_markdown_fence("```json\n{}\n```") == "{}"


def test_parse_router_response_valid() -> None:
    out = _parse_router_response(
        _llm_response(["code-reviewer", "concurrency-reviewer"]),
        set(ALL_REVIEWERS),
    )
    assert out == ["code-reviewer", "concurrency-reviewer"]


def test_parse_router_response_filters_unknown_reviewers() -> None:
    out = _parse_router_response(
        _llm_response(["code-reviewer", "made-up-reviewer"]),
        set(ALL_REVIEWERS),
    )
    assert out == ["code-reviewer"]


def test_parse_router_response_invalid_json_returns_none() -> None:
    assert _parse_router_response("not json", set(ALL_REVIEWERS)) is None


def test_parse_router_response_missing_key_returns_none() -> None:
    assert _parse_router_response(json.dumps({"foo": []}), set(ALL_REVIEWERS)) is None


def test_parse_router_response_inserts_code_reviewer_floor() -> None:
    out = _parse_router_response(
        _llm_response(["security-reviewer"]),
        set(ALL_REVIEWERS),
    )
    assert out is not None
    assert out[0] == "code-reviewer"
    assert "security-reviewer" in out


def test_route_with_llm_happy_path() -> None:
    fake = _FakeJudge(_llm_response(["code-reviewer", "concurrency-reviewer"]))
    files = [Path("src/parser.py")]  # rule-based wouldn't pick concurrency
    diff = "diff --git a/src/parser.py b/src/parser.py\n+threading.Lock()"
    result = route_with_llm(files, ALL_REVIEWERS, diff, client=fake)
    assert "concurrency-reviewer" in result
    assert "code-reviewer" in result
    assert len(fake.calls) == 1


def test_route_with_llm_falls_back_on_error() -> None:
    fake = _FakeJudge(RuntimeError("rate limited"))
    files = [Path("src/auth/login.py")]
    result = route_with_llm(files, ALL_REVIEWERS, "diff", client=fake)
    # rule-based fallback picks security from /auth/ path
    assert "security-reviewer" in result
    assert "code-reviewer" in result


def test_route_with_llm_falls_back_on_invalid_json() -> None:
    fake = _FakeJudge("garbage response")
    files = [Path("src/auth/login.py")]
    result = route_with_llm(files, ALL_REVIEWERS, "diff", client=fake)
    # Same fallback path
    assert "security-reviewer" in result


def test_route_with_llm_preserves_preset_ordering() -> None:
    """LLM may return reviewers in any order; output must match preset order."""
    fake = _FakeJudge(_llm_response(["concurrency-reviewer", "code-reviewer", "security-reviewer"]))
    result = route_with_llm([Path("x")], ALL_REVIEWERS, "diff", client=fake)
    # ALL_REVIEWERS order: code, security, perf, ux, concurrency
    assert result.index("code-reviewer") < result.index("security-reviewer")
    assert result.index("security-reviewer") < result.index("concurrency-reviewer")


def test_route_with_llm_caps_diff_input() -> None:
    fake = _FakeJudge(_llm_response(["code-reviewer"]))
    huge = "x" * 50_000
    route_with_llm([Path("x")], ALL_REVIEWERS, huge, client=fake)
    user = fake.calls[0]["user"]
    diff_section = user.split("BEGIN DIFF ---\n")[1].split("\n--- END DIFF")[0]
    assert len(diff_section) <= 16_000
