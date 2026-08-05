"""Phase 2 — retired top-level keys are dropped at LOAD time, not only at render time.

PLAN-harness-diet ADR-012 shipped the drop-list inside `render._preserve_yaml_user_keys`,
which only runs on `/harness-maker:make`. An already-installed project that upgrades the
package **without re-rendering** never touches that path, so its `harness.yaml` keeps
`workflows:` / `default_workflow:` and every reader sees them (codex P1).

The fix routes the strip through the one loader every config entry point already shares,
`io_utils.load_harness_yaml`, so the migration cannot be bypassed by not re-rendering.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_maker import io_utils
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.io_utils import RETIRED_TOP_LEVEL_KEYS, load_harness_yaml

_RETIRED_BODY = (
    "---\n"
    "generated_by: harness-maker\n"
    "content_hash: deadbeef\n"
    "---\n"
    "preset: Side\n"
    "locale: en\n"
    "targets: [claude-code]\n"
    "dev_mode: task-driven\n"
    "schema_version: 3\n"
    "workflows:\n"
    "  exec-rev:\n"
    "    stages: [execute, review]\n"
    "default_workflow: exec-rev\n"
    "custom_user_block:\n"
    "  keep: me\n"
)


@pytest.fixture(autouse=True)
def _reset_advisory_memo() -> None:
    """The advisory is once-per-project, so the memo must not leak between tests."""
    io_utils._ADVISED_RETIRED_KEY_PATHS.clear()


def _write(tmp_path: Path, body: str = _RETIRED_BODY) -> Path:
    path = tmp_path / "harness.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_retired_keys_are_absent_from_the_loaded_body(tmp_path: Path) -> None:
    data = load_harness_yaml(_write(tmp_path))
    assert "workflows" not in data
    assert "default_workflow" not in data


def test_the_rest_of_the_file_survives_the_strip(tmp_path: Path) -> None:
    """Non-vacuity: proves the loader returned real content, not an empty dict."""
    data = load_harness_yaml(_write(tmp_path))
    assert data["preset"] == "Side"
    assert data["custom_user_block"] == {"keep": "me"}
    assert data["schema_version"] == 3


def test_exactly_one_advisory_per_project_across_repeated_loads(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`--single advisory line per project, not per load`: a CLI run loads config many times."""
    path = _write(tmp_path)
    # Capture at WARNING, deliberately NOT at INFO. Forcing INFO here is what made the
    # first version of this test vacuous: the advisory was emitted at INFO, which nothing
    # in this package's runtime ever displays (no logging config anywhere in `src/`, so the
    # root logger stays at WARNING), and the test passed while no user could see it.
    # Capturing at the level a real run would show is the assertion.
    with caplog.at_level(logging.WARNING, logger="harness_maker.io_utils"):
        for _ in range(3):
            load_harness_yaml(path)
    advisories = [r for r in caplog.records if "workflows" in r.getMessage()]
    assert len(advisories) == 1, [r.getMessage() for r in advisories]
    assert advisories[0].levelno >= logging.WARNING
    assert "default_workflow" in advisories[0].getMessage()


def test_two_projects_each_get_their_own_advisory(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Per-project, not per-process — a sibling-repo run must not silence the second one."""
    paths = []
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        paths.append(_write(tmp_path / name))
    with caplog.at_level(logging.WARNING, logger="harness_maker.io_utils"):
        for path in paths:
            load_harness_yaml(path)
    assert len([r for r in caplog.records if "workflows" in r.getMessage()]) == 2


def test_a_clean_file_emits_no_advisory(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    clean = "---\ngenerated_by: harness-maker\n---\npreset: Side\nlocale: en\n"
    with caplog.at_level(logging.WARNING, logger="harness_maker.io_utils"):
        data = load_harness_yaml(_write(tmp_path, clean))
    assert data == {"preset": "Side", "locale": "en"}
    assert [r for r in caplog.records if "workflows" in r.getMessage()] == []


def test_an_upgraded_project_loads_its_answers_without_re_rendering(tmp_path: Path) -> None:
    """The phase's exit criterion: package upgrade, no re-render, config still loads."""
    answers = answers_from_harness_yaml(_write(tmp_path))
    assert answers is not None
    assert answers.preset.value == "Side"


def test_the_shipped_retired_key_fixtures_still_carry_the_old_shape() -> None:
    """Guard the inputs this phase exists for.

    `tests/fixtures/harness_yaml_v1_with_provenance.yaml` and the cursor-compat fixture are
    deliberately preserved in the retired format — Phase 1's sweep excludes them. If a future
    cleanup "fixes" them, every test above would still pass while testing nothing real.
    """
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "tests/fixtures/harness_yaml_v1_with_provenance.yaml",
        "tests/cursor-compat/fixture/.claude/harness.yaml",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "workflows:" in text, rel
        assert "default_workflow:" in text, rel


def test_the_render_side_filter_still_works_when_it_is_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restores a gate this phase silently made vacuous.

    Phase 1's `test_a_retired_key_is_not_re_injected_on_re_render` existed to fail when the
    `and k not in _RETIRED_TOP_LEVEL_KEYS` clause is deleted from `_preserve_yaml_user_keys`.
    Once the loader began stripping, that test passed with the clause removed — verified by
    deleting it — so the render-side filter became unguarded dead code.

    This reaches it directly by making the loader return UNSTRIPPED data, the state a future
    refactor away from `load_harness_yaml` would produce.
    """
    from harness_maker import render

    out = tmp_path / "harness.yaml"
    out.write_text("preset: Side\nworkflows:\n  x: {stages: [execute]}\n", encoding="utf-8")
    # `_preserve_yaml_user_keys` imports the loader inside the function body (cycle
    # avoidance), so the module-under-test has no attribute to patch — the source module is
    # the only hook.
    monkeypatch.setattr(
        "harness_maker.io_utils.load_harness_yaml",
        lambda _p: {"preset": "Side", "workflows": {"x": {}}},
    )
    result = render._preserve_yaml_user_keys(out, "preset: Side\nlocale: en\n")
    assert "workflows" not in result
    # Positive control: a genuine user key on the same unstripped input IS preserved, so a
    # filter that dropped everything would not pass this.
    monkeypatch.setattr(
        "harness_maker.io_utils.load_harness_yaml",
        lambda _p: {"preset": "Side", "workflows": {"x": {}}, "custom_block": {"a": 1}},
    )
    result = render._preserve_yaml_user_keys(out, "preset: Side\nlocale: en\n")
    assert "custom_block" in result
    assert "workflows" not in result


def test_the_render_drop_list_is_the_same_object_as_the_loader_one() -> None:
    """One source of truth (ADR-012): a future key removal edits exactly one constant."""
    from harness_maker import render

    assert render._RETIRED_TOP_LEVEL_KEYS is RETIRED_TOP_LEVEL_KEYS
    assert set(RETIRED_TOP_LEVEL_KEYS) == {"workflows", "default_workflow"}
