"""Phase 2 — `.hm-autopilot` session marker (PLAN-human-bottleneck-auto-advance).

ADR-006: the session-start answer (level + pipeline) is persisted INTO the marker,
keyed by `session_uuid` (reuses worktree._current_session_uuid). A stale / foreign /
corrupt / schema-invalid marker fails safe to OFF (gated) and is never honored —
this test suite is the fail-safe matrix the plan-validator demanded (finding #9).
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker import autopilot
from harness_maker.models import AtomicStage
from harness_maker.worktree import _HARNESS_CHURN_FILES, _current_session_uuid

DEFAULT_PIPELINE = [
    AtomicStage.RESEARCH,
    AtomicStage.SPEC,
    AtomicStage.PLAN,
    AtomicStage.EXECUTE,
    AtomicStage.REVIEW,
    AtomicStage.VERIFY,
    AtomicStage.WRAPUP,
]


def _raw_write(root: Path, text: str) -> None:
    """Write arbitrary bytes to the marker path (for corrupt/foreign cases)."""
    p = autopilot.marker_path(root, session_id=None)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# --- write / load / clear roundtrip ---------------------------------------------


def test_write_then_load_roundtrips(tmp_path: Path) -> None:
    m = autopilot.write(
        tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE, now="2026-06-20T00:00:00+00:00"
    )
    assert m.level == "auto_safe"
    assert m.pipeline == DEFAULT_PIPELINE
    assert m.created_at == "2026-06-20T00:00:00+00:00"
    loaded = autopilot.load(tmp_path, session_id=None)
    assert loaded is not None
    assert loaded.level == "auto_safe"
    assert loaded.session_uuid == _current_session_uuid(tmp_path)


def test_clear_removes_marker_idempotently(tmp_path: Path) -> None:
    autopilot.write(tmp_path, level="full", pipeline=DEFAULT_PIPELINE)
    autopilot.clear(tmp_path, session_id=None)
    assert autopilot.load(tmp_path, session_id=None) is None
    autopilot.clear(tmp_path, session_id=None)  # second clear must not raise


# --- fail-safe matrix (all → inactive / None) -----------------------------------


def test_load_absent_returns_none(tmp_path: Path) -> None:
    assert autopilot.load(tmp_path, session_id=None) is None


def test_load_corrupt_json_returns_none(tmp_path: Path) -> None:
    _raw_write(tmp_path, "{ this is not json")
    assert autopilot.load(tmp_path, session_id=None) is None


def test_load_invalid_schema_returns_none(tmp_path: Path) -> None:
    _raw_write(
        tmp_path,
        json.dumps({"session_uuid": "abc", "level": "yolo", "pipeline": [], "created_at": "x"}),
    )
    assert autopilot.load(tmp_path, session_id=None) is None


def test_active_marker_matches_current_session(tmp_path: Path) -> None:
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    m = autopilot.active_marker(tmp_path)
    assert m is not None
    assert m.level == "auto_safe"


def test_active_marker_foreign_uuid_returns_none(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    # A marker stamped by a different session must be ignored (fail-safe → gated).
    # Pin the current-session uuid so the mismatch is deterministic, not probabilistic.
    monkeypatch.setattr(autopilot, "_current_session_uuid", lambda _root: "aaaaaaaaaaaa")
    _raw_write(
        tmp_path,
        json.dumps(
            {
                "session_uuid": "ffffffffffff",
                "level": "full",
                "pipeline": ["research"],
                "created_at": "2026-06-20T00:00:00+00:00",
            }
        ),
    )
    assert autopilot.active_marker(tmp_path) is None


# --- precedence resolver (ADR-006: active marker > harness.yaml) -----------------


def test_effective_level_active_marker_wins(tmp_path: Path) -> None:
    autopilot.write(tmp_path, level="auto_safe", pipeline=DEFAULT_PIPELINE)
    assert autopilot.effective_level(tmp_path, yaml_level="gated") == "auto_safe"


def test_effective_level_falls_back_to_yaml_when_no_marker(tmp_path: Path) -> None:
    # A harness.yaml that has not been re-rendered still says `full`; it must resolve to the
    # level it always behaved as, NOT fall into the unknown-level clamp (which would read as
    # autopilot-off for every un-updated project).
    assert autopilot.effective_level(tmp_path, yaml_level="full") == "auto_safe"


def test_effective_level_foreign_marker_falls_back_to_yaml(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(autopilot, "_current_session_uuid", lambda _root: "aaaaaaaaaaaa")
    _raw_write(
        tmp_path,
        json.dumps(
            {
                "session_uuid": "ffffffffffff",
                "level": "full",
                "pipeline": ["research"],
                "created_at": "2026-06-20T00:00:00+00:00",
            }
        ),
    )
    assert autopilot.effective_level(tmp_path, yaml_level="gated") == "gated"


# --- gitignore coverage ----------------------------------------------------------


def test_marker_is_in_churn_files() -> None:
    # ADR-006 + PLAN-worktree-base-artifact-pollution: the marker must be gitignored
    # and recognized by both dirt-filters, or a committed marker footguns collaborators.
    # PLAN-multisession-marker-scoping ADR-011: the marker is now one file per session,
    # so the exact-match churn-FILE literal matched none of them and moved to the
    # prefix-matched artifact tuple (the one the finalize dirt-filter actually reads),
    # with a `*` glob for .gitignore.
    from harness_maker.worktree import _HARNESS_ARTIFACT_PREFIXES, _HARNESS_GITIGNORE_PATTERNS

    assert ".claude/.hm-autopilot" not in _HARNESS_CHURN_FILES
    assert ".claude/.hm-autopilot" in _HARNESS_ARTIFACT_PREFIXES
    assert ".claude/.hm-autopilot*" in _HARNESS_GITIGNORE_PATTERNS


# --- CLI boundary (checkpoint 8: user-boundary code needs a real-invocation test) ---


def test_cli_on_then_off(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from harness_maker.cli import app

    runner = CliRunner()
    on = runner.invoke(app, ["autopilot", "on", "--level", "auto_safe", "--root", str(tmp_path)])
    assert on.exit_code == 0, on.output
    assert autopilot.active_marker(tmp_path) is not None
    off = runner.invoke(app, ["autopilot", "off", "--root", str(tmp_path)])
    assert off.exit_code == 0, off.output
    assert autopilot.load(tmp_path, session_id=None) is None


def test_cli_shim_accepts_every_registered_action(tmp_path: Path) -> None:
    """Parity gate. `harness-maker autopilot <a>` and `hm autopilot <a>` are one command
    with two spellings; `resolve_toggle_config` is shared precisely so they cannot drift,
    but the ACTION TABLE was not. `status` landed on the module entry and in the registry
    while this shim still answered "unknown action", and the same change added `--force`
    here — so the miss was not a whole-feature oversight, it was one of two edits. Nothing
    caught it because no test ever invoked the shim with anything but on/off/garbage.

    Derived from the registry rather than hard-coded, so a future action cannot land on one
    surface only.
    """
    import json as _json

    from typer.testing import CliRunner

    from harness_maker import command_registry
    from harness_maker.cli import app

    runner = CliRunner()
    actions = command_registry.MODULES["autopilot"].subcommands
    assert "status" in actions, "registry no longer declares the action this gate exists for"
    # `off` → `on` → `status`: alphabetical order happens to leave a live marker for the
    # read, so `status` is exercised against a real one rather than the absent case.
    for action in sorted(actions):
        res = runner.invoke(app, ["autopilot", action, "--root", str(tmp_path)])
        assert res.exit_code == 0, f"{action}: {res.output}"
        assert "unknown action" not in res.output, f"{action}: {res.output}"
    # And the payload is the module entry's, not a shim-local reimplementation.
    res = runner.invoke(app, ["autopilot", "status", "--root", str(tmp_path)])
    assert _json.loads(res.output) == autopilot.status(tmp_path)


def test_cli_invalid_action_exits_2(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from harness_maker.cli import app

    res = CliRunner().invoke(app, ["autopilot", "sideways", "--root", str(tmp_path)])
    assert res.exit_code == 2


def test_cli_invalid_level_exits_2(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from harness_maker.cli import app

    res = CliRunner().invoke(app, ["autopilot", "on", "--level", "yolo", "--root", str(tmp_path)])
    assert res.exit_code == 2
    assert autopilot.load(tmp_path, session_id=None) is None


# --- review-driven hardening (Phase 2 round 1 findings) --------------------------


def test_load_empty_file_returns_none(tmp_path: Path) -> None:
    # Partial-write survivor (WSL2/NTFS): zero-byte marker → JSONDecodeError → None.
    _raw_write(tmp_path, "")
    assert autopilot.load(tmp_path, session_id=None) is None


def test_load_extra_key_rejected(tmp_path: Path) -> None:
    # extra="forbid" must reject an injected key even under model_validate(strict=False).
    _raw_write(
        tmp_path,
        json.dumps(
            {
                "session_uuid": "aabbccddeeff",
                "level": "full",
                "pipeline": ["research"],
                "created_at": "2026-06-20T00:00:00+00:00",
                "injected": "x",
            }
        ),
    )
    assert autopilot.load(tmp_path, session_id=None) is None


def test_load_empty_pipeline_rejected(tmp_path: Path) -> None:
    # min_length=1: an empty pipeline is a silent Phase-3 no-op → reject as malformed.
    _raw_write(
        tmp_path,
        json.dumps(
            {
                "session_uuid": "aabbccddeeff",
                "level": "full",
                "pipeline": [],
                "created_at": "2026-06-20T00:00:00+00:00",
            }
        ),
    )
    assert autopilot.load(tmp_path, session_id=None) is None


def test_effective_level_garbage_yaml_clamps_to_gated(tmp_path: Path) -> None:
    # No active marker + an unknown/typo yaml level must clamp to gated, not propagate.
    assert autopilot.effective_level(tmp_path, yaml_level="auto-safe") == "gated"
    assert autopilot.effective_level(tmp_path, yaml_level="") == "gated"


def test_dirt_filters_recognize_marker() -> None:
    # End-to-end (not just tuple-membership): both filters must treat a porcelain line
    # for the marker as a harness artifact, or a committed marker footguns collaborators.
    from harness_maker.worktree import _is_create_guard_harness_artifact, _is_harness_artifact

    line = "?? .claude/.hm-autopilot"  # git status --porcelain v1: "XY " + path
    assert _is_harness_artifact(line)
    assert _is_create_guard_harness_artifact(line)


def test_cli_custom_pipeline_valid(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from harness_maker.cli import app

    res = CliRunner().invoke(
        app, ["autopilot", "on", "--pipeline", "research,plan", "--root", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    m = autopilot.active_marker(tmp_path)
    assert m is not None
    assert [s.value for s in m.pipeline] == ["research", "plan"]


def test_cli_invalid_pipeline_exits_2(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from harness_maker.cli import app

    res = CliRunner().invoke(
        app, ["autopilot", "on", "--pipeline", "research,bogus", "--root", str(tmp_path)]
    )
    assert res.exit_code == 2
    assert autopilot.load(tmp_path, session_id=None) is None


def test_cli_failed_on_preserves_prior_marker(tmp_path: Path) -> None:
    # Transactional contract: a failed `on` is validated BEFORE write, so a prior
    # valid marker is neither corrupted nor silently replaced (Codex P2).
    from typer.testing import CliRunner

    from harness_maker.cli import app

    runner = CliRunner()
    runner.invoke(app, ["autopilot", "on", "--level", "auto_safe", "--root", str(tmp_path)])
    bad = runner.invoke(app, ["autopilot", "on", "--level", "yolo", "--root", str(tmp_path)])
    assert bad.exit_code == 2
    m = autopilot.active_marker(tmp_path)
    assert m is not None  # prior state intact
    assert m.level == "auto_safe"
