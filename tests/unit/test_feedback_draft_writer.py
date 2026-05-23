"""Phase 3 — FeedbackDraft + TriggerSignal Pydantic models + write() with dedup + redaction.

PLAN-auto-feedback-2026-05 Phase 3 exit criterion (a)-(f).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness_maker.feedback.draft_writer import (
    FeedbackDraft,
    TriggerSignal,
    _dedup_hash,
    write,
)


def _make_draft(**overrides) -> FeedbackDraft:
    base = {
        "harness_maker_version": "0.23.7",
        "ide": "claude-code",
        "os": "Linux 6.6.0",
        "stage": "research",
        "task_slug": "auto-feedback-2026-05",
        "trigger_signal": TriggerSignal(id="hook-error", count=1, duration_ms=18000),
    }
    base.update(overrides)
    return FeedbackDraft(**base)


# ── (a) whitelist enforcement: extra=forbid + strict types ───────────────────


def test_draft_extra_fields_rejected() -> None:
    """extra='forbid' must surface unknown keys (whitelist guarantee)."""
    with pytest.raises(ValidationError):
        FeedbackDraft(
            harness_maker_version="0.23.7",
            ide="claude-code",
            os="Linux",
            stage="research",
            task_slug="x",
            trigger_signal=TriggerSignal(id="x", count=0),
            unknown_field="leak",  # type: ignore[call-arg]
        )


def test_trigger_signal_extra_fields_rejected() -> None:
    """TriggerSignal must also reject extras (nested-model leak guard)."""
    with pytest.raises(ValidationError):
        TriggerSignal(id="x", count=0, raw_payload="leak")  # type: ignore[call-arg]


def test_trigger_signal_strict_count_type() -> None:
    """count must be int (not coerced from string)."""
    with pytest.raises(ValidationError):
        TriggerSignal(id="x", count="3")  # type: ignore[arg-type]


def test_trigger_signal_negative_count_rejected() -> None:
    """ge=0 constraint."""
    with pytest.raises(ValidationError):
        TriggerSignal(id="x", count=-1)


# ── (b) error_message redaction via telemetry._SECRET_PATTERNS ──────────────


@pytest.mark.parametrize(
    "leak",
    [
        # All four match telemetry._SECRET_PATTERNS length thresholds
        # (sk-≥8, ghp_≥20, AKIA≥16, Bearer≥16).
        "sk-ant-api03-AABBCCDDEEFF",
        "ghp_ABCDEF1234567890XYZA",
        "AKIA1234567890ABCDEF",
        "Bearer eyJabc.def.ghi.AAA",
    ],
)
def test_error_message_redacts_known_secret_patterns(leak: str) -> None:
    d = _make_draft(error_message=f"failure: {leak} encountered while reading config")
    assert d.error_message is not None
    assert leak not in d.error_message
    assert "[REDACTED]" in d.error_message


def test_error_message_long_truncated() -> None:
    d = _make_draft(error_message="x" * 500)
    assert d.error_message is not None
    assert len(d.error_message) <= 256
    assert d.error_message.endswith("...<truncated>")


def test_error_message_short_passes_through() -> None:
    d = _make_draft(error_message="simple failure")
    assert d.error_message == "simple failure"


# ── REVIEW round 1 P1-1 — task_slug path-traversal guard ────────────────────


def test_task_slug_path_traversal_rejected() -> None:
    """REVIEW round 1 P1-1: a prompt-injected ../../etc/foo task_slug must raise.

    Without sanitization, write() would resolve f'{date}-{task_slug}-{hash}.md'
    via os.replace through the path, escaping .claude/observability/feedback/.
    """
    for bad in ("../etc/foo", "../../evil", "x/y", "a\\b", "name with space"):
        with pytest.raises(ValidationError, match="task_slug"):
            _make_draft(task_slug=bad)


def test_task_slug_too_long_rejected() -> None:
    with pytest.raises(ValidationError, match="task_slug"):
        _make_draft(task_slug="x" * 201)


def test_task_slug_kebab_case_accepted() -> None:
    """Real harness-maker slugs (kebab + digits + underscore) must still pass."""
    for good in ("auto-feedback-2026-05", "x", "feature_under_score", "ALL-CAPS-OK"):
        d = _make_draft(task_slug=good)
        assert d.task_slug == good


# ── (c) file_paths hard-reject non-.claude/ paths ────────────────────────────


def test_file_paths_outside_claude_rejected() -> None:
    """User-repo paths MUST raise — prevents content leak."""
    with pytest.raises(ValidationError, match=".claude/"):
        _make_draft(file_paths=["/home/user/src/main.py"])


def test_file_paths_relative_outside_claude_rejected() -> None:
    with pytest.raises(ValidationError, match=".claude/"):
        _make_draft(file_paths=["src/main.py"])


def test_file_paths_claude_subpath_accepted() -> None:
    d = _make_draft(file_paths=[".claude/hooks/hooks.json", ".claude/agents/foo.md"])
    assert d.file_paths == [".claude/hooks/hooks.json", ".claude/agents/foo.md"]


def test_file_paths_empty_list_default() -> None:
    d = _make_draft()
    assert d.file_paths == []


# ── (e) dedup: same (trigger_id, slug, date) → one file ──────────────────────


def test_write_dedup_returns_existing_path_silent(tmp_path) -> None:
    d = _make_draft()
    p1 = write(d, base_dir=tmp_path, date="2026-05-23")
    # Modify a different field to prove dedup is by (trigger_id, slug, date), not body hash.
    d2 = _make_draft(error_message="different error this time")
    p2 = write(d2, base_dir=tmp_path, date="2026-05-23")
    assert p1 == p2
    # Original content preserved (no rewrite).
    assert "different error this time" not in p1.read_text()


def test_write_different_date_produces_separate_file(tmp_path) -> None:
    d = _make_draft()
    p1 = write(d, base_dir=tmp_path, date="2026-05-23")
    p2 = write(d, base_dir=tmp_path, date="2026-05-24")
    assert p1 != p2
    assert p1.is_file()
    assert p2.is_file()


def test_write_different_trigger_id_produces_separate_file(tmp_path) -> None:
    d_a = _make_draft(trigger_signal=TriggerSignal(id="hook-error", count=1))
    d_b = _make_draft(trigger_signal=TriggerSignal(id="silent-intent-miss", count=1))
    p_a = write(d_a, base_dir=tmp_path, date="2026-05-23")
    p_b = write(d_b, base_dir=tmp_path, date="2026-05-23")
    assert p_a != p_b


def test_dedup_hash_deterministic() -> None:
    """Same inputs → same hash, always (CLAUDE.md checkpoint 7 determinism)."""
    h1 = _dedup_hash("hook-error", "x", "2026-05-23")
    h2 = _dedup_hash("hook-error", "x", "2026-05-23")
    assert h1 == h2
    assert len(h1) == 16


def test_dedup_hash_varies_with_inputs() -> None:
    assert _dedup_hash("a", "x", "d") != _dedup_hash("b", "x", "d")
    assert _dedup_hash("a", "x", "d") != _dedup_hash("a", "y", "d")
    assert _dedup_hash("a", "x", "d") != _dedup_hash("a", "x", "e")


# ── (f) body structure ─────────────────────────────────────────────────────


def test_write_body_contains_all_5_whitelisted_fields(tmp_path) -> None:
    d = _make_draft(error_message="boom", file_paths=[".claude/foo.md"])
    p = write(d, base_dir=tmp_path, date="2026-05-23")
    body = p.read_text()
    assert "harness-maker: `0.23.7`" in body
    assert "IDE: `claude-code`" in body
    assert "OS: `Linux 6.6.0`" in body
    assert "Stage: `/hm:research`" in body
    assert "Task slug: `auto-feedback-2026-05`" in body
    assert "Type: `hook-error`" in body
    assert "Count: `1`" in body
    assert "boom" in body
    assert ".claude/foo.md" in body


def test_write_body_excludes_user_repo_strings(tmp_path) -> None:
    """The PLAN's privacy invariant — body must not contain any path not declared in whitelist."""
    d = _make_draft()
    p = write(d, base_dir=tmp_path, date="2026-05-23")
    body = p.read_text()
    # Trivial sanity — no /home/, /etc/, /Users/ leaks from the writer itself.
    assert "/home/" not in body
    assert "/etc/" not in body
    assert "/Users/" not in body
