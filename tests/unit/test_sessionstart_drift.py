"""Tests for harness_maker.hooks.sessionstart_drift."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from harness_maker.hooks.sessionstart_drift import _format_context, run

# Pin both the imported __version__ AND latest_installed_version to a stable
# value so this test suite is deterministic regardless of what's actually in
# ~/.claude/plugins/cache/ (0.6.2 P6 alignment surfaced this).
_TEST_CURRENT = "0.5.5"


def _write_harness_yaml(project_dir: Path, stamped_version: str) -> None:
    """Write a minimal harness.yaml with telemetry opted out.

    Why ``disable_telemetry: true`` (Phase 11): the SessionStart hook now
    also fires a personalization-audit hint when override count or
    days-since-last-audit thresholds trip. Existing drift tests assert
    silence / no systemMessage and predate that branch; opting telemetry
    out keeps the drift-only invariants under test isolated from the
    Phase 11 hint. Phase 11's own tests construct their own harness.yaml.
    """
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    fm = (
        f"---\nharness_maker_version: {stamped_version}\npreset: Side\n---\n"
        "preset: Side\nadaptive:\n  disable_telemetry: true\n"
    )
    (claude / "harness.yaml").write_text(fm, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# run() — silent paths
# ──────────────────────────────────────────────────────────────────────────────


def test_run_silent_when_no_harness_yaml(tmp_path: Path, capsys) -> None:
    rc = run(cwd=tmp_path)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_run_silent_when_versions_match(tmp_path: Path, capsys) -> None:
    _write_harness_yaml(tmp_path, _TEST_CURRENT)
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_run_silent_when_harness_yaml_has_no_frontmatter(tmp_path: Path, capsys) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    # disable_telemetry isolates this drift-silence assertion from the Phase 11
    # personalization-audit hint (which would otherwise fire on missing
    # last-audit.txt).
    (claude / "harness.yaml").write_text(
        "preset: Side\nadaptive:\n  disable_telemetry: true\n",
        encoding="utf-8",
    )
    rc = run(cwd=tmp_path)
    assert rc == 0
    assert capsys.readouterr().out == ""


# ──────────────────────────────────────────────────────────────────────────────
# run() — drift surfaced
# ──────────────────────────────────────────────────────────────────────────────


def test_run_emits_additional_context_on_upgrade(tmp_path: Path, capsys) -> None:
    _write_harness_yaml(tmp_path, "0.0.1")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "harness-maker drift" in ctx
    assert "0.0.1" in ctx
    assert _TEST_CURRENT in ctx
    assert "/harness-maker:make" in ctx


def test_run_emits_downgrade_warning(tmp_path: Path, capsys) -> None:
    _write_harness_yaml(tmp_path, "999.0.0")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "downgrade" in ctx.lower()


def test_run_does_not_emit_system_message(tmp_path: Path, capsys) -> None:
    """systemMessage is NOT emitted (0.11.5).

    Per official Claude Code docs (2026-05-13), SessionStart hooks have no
    user-visible output field — both ``additionalContext`` and
    ``systemMessage`` feed Claude's context only. The 0.11.3 attempt to
    split into a "user-facing systemMessage" was based on a misreading of
    the spec. The replacement strategy: an imperative phrasing in
    ``additionalContext`` that tells Claude to surface the drift in its
    first response. Test guards against the dead field returning silently.
    """
    _write_harness_yaml(tmp_path, "0.0.1")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "systemMessage" not in payload["hookSpecificOutput"]


def test_additional_context_is_imperative(tmp_path: Path, capsys) -> None:
    """additionalContext must instruct Claude to surface drift to the user.

    Descriptive phrasing ("drift detected: ...") is too easy to ignore.
    The text must contain explicit instruction to mention the drift in
    Claude's next response so the user actually finds out.
    """
    _write_harness_yaml(tmp_path, "0.0.1")
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        run(cwd=tmp_path)
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    # Imperative markers that prompt Claude to surface the drift.
    assert "TELL THE USER" in ctx
    assert "Tell the user" in ctx


# ──────────────────────────────────────────────────────────────────────────────
# _format_context
# ──────────────────────────────────────────────────────────────────────────────


def test_format_context_upgrade_mentions_make_command() -> None:
    msg = _format_context("0.4.0", "0.5.5", "upgrade")
    assert "/harness-maker:make" in msg
    assert "0.4.0" in msg
    assert "0.5.5" in msg


def test_format_context_downgrade_warns_intent() -> None:
    msg = _format_context("0.5.5", "0.4.0", "downgrade")
    assert "downgrade" in msg.lower()


def test_message_contains_update_flag() -> None:
    """Upgrade message mentions `make --update` so users know the fast re-render command."""
    msg = _format_context("0.4.0", "0.5.5", "upgrade")
    assert "make --update" in msg, (
        f"Expected 'make --update' as actionable command in message:\n{msg}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point — proves module is invokable as `python -m`
# ──────────────────────────────────────────────────────────────────────────────


def test_main_as_subprocess_silent_when_no_harness(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.sessionstart_drift"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_main_as_subprocess_emits_on_drift(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.0.1")
    result = subprocess.run(
        [sys.executable, "-m", "harness_maker.hooks.sessionstart_drift"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


# ──────────────────────────────────────────────────────────────────────────────
# Phase 11 — personalization-audit hint
# ──────────────────────────────────────────────────────────────────────────────


def _write_phase11_harness_yaml(
    project_dir: Path,
    *,
    disable_telemetry: bool = False,
    audit_session_threshold: int = 30,
    audit_days_threshold: int = 14,
) -> None:
    """Write a harness.yaml where the stamped version matches the running
    plugin so the drift branch stays silent; the test isolates the
    personalization-hint behavior."""
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    fm = (
        f"---\nharness_maker_version: {_TEST_CURRENT}\npreset: Side\n---\n"
        "preset: Side\nadaptive:\n"
        f"  disable_telemetry: {str(disable_telemetry).lower()}\n"
        f"  audit_session_threshold: {audit_session_threshold}\n"
        f"  audit_days_threshold: {audit_days_threshold}\n"
    )
    (claude / "harness.yaml").write_text(fm, encoding="utf-8")


def _write_overrides(project_dir: Path, n: int) -> None:
    """Materialise ``n`` schema_version=1 override records on disk so
    load_overrides() returns exactly n entries."""
    path = project_dir / ".claude" / "observability" / "adaptive" / "overrides.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for i in range(n):
        record = {
            "schema_version": 1,
            "ts": f"2026-05-01T00:00:{i:02d}+00:00",
            "axis_path": f"axis.{i}",
            "before": None,
            "after": f"v{i}",
            "source": "configure-exit",
            "reason": "",
        }
        lines.append(json.dumps(record))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_last_audit(project_dir: Path, days_ago: float) -> None:
    """Stamp last-audit.txt as ``days_ago`` days before now."""
    from datetime import UTC, datetime, timedelta

    path = project_dir / ".claude" / "observability" / "adaptive" / "last-audit.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    path.write_text(ts, encoding="utf-8")


def test_no_hint_when_under_thresholds(tmp_path: Path, capsys) -> None:
    """5 overrides + 7 days since audit → neither threshold tripped → silent."""
    _write_phase11_harness_yaml(tmp_path)
    _write_overrides(tmp_path, 5)
    _write_last_audit(tmp_path, 7.0)
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_hint_when_override_count_exceeds_threshold(tmp_path: Path, capsys) -> None:
    """35 overrides ≥ default 30 → hint includes the count."""
    _write_phase11_harness_yaml(tmp_path)
    _write_overrides(tmp_path, 35)
    _write_last_audit(tmp_path, 1.0)  # well under the days threshold
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    hook_out = payload["hookSpecificOutput"]
    assert hook_out["hookEventName"] == "SessionStart"
    assert "35 axis overrides" in hook_out["additionalContext"]
    assert "/hm:personalization-audit" in hook_out["additionalContext"]
    assert "35 personalization axis overrides" in hook_out["systemMessage"]


def test_hint_when_days_since_audit_exceeds_threshold(tmp_path: Path, capsys) -> None:
    """15 days since audit ≥ default 14 → hint fires even with no overrides."""
    _write_phase11_harness_yaml(tmp_path)
    _write_overrides(tmp_path, 3)
    _write_last_audit(tmp_path, 15.0)
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    hook_out = payload["hookSpecificOutput"]
    assert "/hm:personalization-audit" in hook_out["additionalContext"]
    assert "/hm:personalization-audit" in hook_out["systemMessage"]


def test_no_hint_when_telemetry_disabled(tmp_path: Path, capsys) -> None:
    """ADR-005 opt-out: telemetry off suppresses the hint even with 100
    overrides + never-audited."""
    _write_phase11_harness_yaml(tmp_path, disable_telemetry=True)
    _write_overrides(tmp_path, 100)
    # Deliberately no last-audit.txt — would otherwise trip the days branch.
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_systemMessage_and_additionalContext_both_present(tmp_path: Path, capsys) -> None:  # noqa: N802
    """Wiki [[sessionstart-systemmessage-required]] — banner needs both
    fields populated. Guard against one being dropped in a future refactor."""
    _write_phase11_harness_yaml(tmp_path)
    _write_overrides(tmp_path, 40)
    _write_last_audit(tmp_path, 0.5)
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    hook_out = payload["hookSpecificOutput"]
    assert "additionalContext" in hook_out
    assert "systemMessage" in hook_out
    assert hook_out["additionalContext"]
    assert hook_out["systemMessage"]


def test_missing_last_audit_treated_as_infinity(tmp_path: Path, capsys) -> None:
    """last-audit.txt absent → days_since = +inf → hint fires by the days branch."""
    _write_phase11_harness_yaml(tmp_path)
    _write_overrides(tmp_path, 2)
    # Deliberately no last-audit.txt.
    with patch("harness_maker.relevance.latest_installed_version", return_value=_TEST_CURRENT):
        rc = run(cwd=tmp_path)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    hook_out = payload["hookSpecificOutput"]
    assert "/hm:personalization-audit" in hook_out["additionalContext"]
    assert "/hm:personalization-audit" in hook_out["systemMessage"]
