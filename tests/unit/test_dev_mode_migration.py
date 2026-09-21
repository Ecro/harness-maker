"""AC-002 (SPEC-dev-mode-removal): the migration maps every cross and never moves the preset.

The six rows live in the machine SPEC's `golden_table` and are loaded, not inlined — the
table is the DRI's Round-1/Round-2 answers and inlining it would recreate the drift the SSOT
exists to remove. Every row goes through the real loader (`io_utils.load_harness_yaml`) on a
real file, because the loader is the migration site: a migration living only in the renderer
reaches users who re-render, not users who merely upgrade (PLAN-harness-diet ADR-012).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.spec_machine import GoldenRow, load_golden_table

_SPEC = Path(__file__).resolve().parents[2] / "specs" / "SPEC-dev-mode-removal.machine.yaml"
_ROWS = load_golden_table(_SPEC, "AC-002")


def _write(tmp_path: Path, body: dict[str, Any]) -> Path:
    path = tmp_path / ".claude" / "harness.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return path


def _body(row_input: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {"schema_version": 4, "preset": row_input["preset"]}
    if row_input.get("dev_mode") is not None:
        body["dev_mode"] = row_input["dev_mode"]
    return body


def _migration_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING and "dev_mode" in r.getMessage()
    ]


@pytest.mark.parametrize(
    "row",
    _ROWS,
    ids=[f"{i}-{r.input['preset']}-{r.input.get('dev_mode')}" for i, r in enumerate(_ROWS)],
)
def test_ac_002_migration_maps_every_cross(
    row: GoldenRow, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.strictness import resolve_strictness

    path = _write(tmp_path, _body(row.input))
    caplog.set_level(logging.WARNING)
    loaded = load_harness_yaml(path)

    assert "dev_mode" not in loaded
    assert loaded["preset"] == row.expected["preset"]
    assert resolve_strictness(loaded) == row.expected["strictness"]

    had_key = row.input.get("dev_mode") is not None
    if had_key:
        # S2: a translated value is WRITTEN, never left to preset derivation — otherwise the
        # Side + spec-driven row would silently resolve to the Side default, `warn`.
        assert loaded["spec"]["strictness"] == row.expected["strictness"]
        assert len(_migration_warnings(caplog)) == 1
    else:
        assert "strictness" not in (loaded.get("spec") or {})
        assert _migration_warnings(caplog) == []

    # Fixed point: a second load of the same file changes nothing and does not re-advise.
    caplog.clear()
    again = load_harness_yaml(path)
    assert again == loaded
    assert _migration_warnings(caplog) == []


def test_ac_002_migrated_mapping_is_idempotent() -> None:
    from harness_maker.io_utils import migrate_dev_mode

    once = migrate_dev_mode({"preset": "Side", "dev_mode": "spec-driven"})
    assert migrate_dev_mode(once) == once


def test_ac_002_migration_preserves_existing_spec_keys(tmp_path: Path) -> None:
    from harness_maker.io_utils import load_harness_yaml

    path = _write(
        tmp_path,
        {"preset": "Production", "dev_mode": "task-driven", "spec": {"dir": "docs/specs/"}},
    )
    loaded = load_harness_yaml(path)
    assert loaded["spec"] == {"dir": "docs/specs/", "strictness": "warn"}


def test_ac_002_an_explicit_strictness_wins_over_a_stale_dev_mode(tmp_path: Path) -> None:
    """A file carrying both keys was hand-edited to the new key; the old one is stale."""
    from harness_maker.io_utils import load_harness_yaml

    path = _write(
        tmp_path,
        {"preset": "Production", "dev_mode": "task-driven", "spec": {"strictness": "block"}},
    )
    loaded = load_harness_yaml(path)
    assert loaded["spec"]["strictness"] == "block"
    assert "dev_mode" not in loaded


def test_ac_002_make_time_body_loader_sees_the_migrated_shape(tmp_path: Path) -> None:
    """`cli._load_harness_yaml_body` parses the body itself for the make-time telemetry diff;
    if it skipped the migration it would report a phantom "user key removed" on every upgrade.
    """
    from harness_maker.cli import _load_harness_yaml_body

    path = _write(tmp_path, {"preset": "Side", "dev_mode": "spec-driven"})
    body = _load_harness_yaml_body(path)
    assert "dev_mode" not in body
    assert body["spec"]["strictness"] == "block"


def test_ac_002_a_re_render_does_not_re_append_the_retired_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`render._preserve_yaml_user_keys` treats "on disk, absent from the new render" as a user
    addition and re-appends it. Without `dev_mode` in the retired set, every re-render would
    resurrect the old key under a banner claiming it is the user's. Reached with the loader
    returning UNSTRIPPED data — the state a refactor away from the shared loader would produce.
    """
    from harness_maker import render

    out = tmp_path / "harness.yaml"
    out.write_text("preset: Side\ndev_mode: task-driven\n", encoding="utf-8")
    monkeypatch.setattr(
        "harness_maker.io_utils.load_harness_yaml",
        lambda _p: {"preset": "Side", "dev_mode": "task-driven", "custom_block": {"a": 1}},
    )
    result = render._preserve_yaml_user_keys(out, "preset: Side\nlocale: en\n")
    assert "dev_mode" not in result
    assert "custom_block" in result  # positive control: a real user key IS preserved
