"""ADR-003 — `/hm:configure` dispatches to a CLI flag, so the flag has to exist.

`/hm:configure` is prose that ends in `hm cli make "$(pwd)" --<flag> "$VALUE"`, with
"omit every flag whose dimension wasn't selected — the CLI preserves unspecified fields".
A configure dimension with no flag behind it renders instructions to pass a flag that does
not exist, while a render-grep success check passes — which is the exact defect ADR-003
exists to prevent, reintroduced one layer down. These tests are the part a grep cannot do.

The `--preset` arm is not incidental. `_apply_dimension_overrides` rebuilds the answers
through `_build_answers`, which takes a **field allowlist**: any root field it does not
name is reset to its default. That is `[fail:design] promoted-default-reaches-bare-callers`
— the class where three of seven sites were missed last time, and the missed ones were the
dangerous ones.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from harness_maker.cli import app
from harness_maker.interview import answers_from_harness_yaml

runner = CliRunner()

_YAML = (
    "---\ngenerated_by: harness-maker\n---\n"
    "preset: Production\nlocale: en\ntargets: [claude-code]\n"
    "interview:\n  comprehension:\n    depth: deep\n"
)


def _write_harness_yaml(tmp_path: Path, body: str = _YAML) -> Path:
    d = tmp_path / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "harness.yaml"
    p.write_text(body)
    return p


def _run(tmp_path: Path, *args: str) -> tuple[int, str, dict[str, object]]:
    """Invoke `make` with the render side effects stubbed, capturing the synthesized answers."""
    captured: dict[str, object] = {}
    real_answers = answers_from_harness_yaml(tmp_path / ".claude" / "harness.yaml")

    def _capture_synthesize(p: object, a: object, **kw: object) -> object:
        from harness_maker.models import Blueprint, HarnessConfig

        captured["interview"] = a.interview  # type: ignore[attr-defined]
        captured["preset"] = a.preset  # type: ignore[attr-defined]
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=real_answers),
        patch("harness_maker.cli.interview", return_value=real_answers),
    ):
        result = runner.invoke(app, ["make", str(tmp_path), *args])
    return result.exit_code, result.output, captured


def _depth(captured: dict[str, object]) -> str:
    interview = captured["interview"]
    assert isinstance(interview, dict)
    value = interview["comprehension"]["depth"]
    assert isinstance(value, str)
    return value


@pytest.mark.parametrize("value", ["minimal", "standard", "deep"])
def test_a_valid_value_reaches_synthesize(tmp_path: Path, value: str) -> None:
    _write_harness_yaml(tmp_path)
    code, output, captured = _run(tmp_path, "--comprehension-depth", value)
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == value


def test_an_invalid_value_exits_non_zero_and_names_the_valid_set(tmp_path: Path) -> None:
    """Unlike the read path (ADR-004 fail-open), an explicit CLI typo must be refused.

    A flag is a deliberate act with a human present, so silently substituting a different
    value is worse than failing: the user would believe they had set what they typed.
    """
    _write_harness_yaml(tmp_path)
    code, output, _ = _run(tmp_path, "--comprehension-depth", "verbose")
    assert code != 0, f"an invalid depth was accepted:\n{output}"
    assert "verbose" in output
    for valid in ("minimal", "standard", "deep"):
        assert valid in output, f"the error must name the valid set; {valid!r} missing:\n{output}"


def test_omitting_the_flag_preserves_the_existing_value(tmp_path: Path) -> None:
    """The configure contract: an unselected dimension is not touched."""
    _write_harness_yaml(tmp_path)
    code, output, captured = _run(tmp_path, "--update")
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == "deep"


def test_a_preset_switch_preserves_an_explicit_depth(tmp_path: Path) -> None:
    """`_build_answers`'s field allowlist resets any root field it does not name.

    A user with `depth: deep` who runs an unrelated `--preset Side` must not be silently
    rewritten to the preset default.
    """
    _write_harness_yaml(tmp_path)
    code, output, captured = _run(tmp_path, "--preset", "Side")
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == "deep", (
        "the preset switch reset the explicit depth — carry `interview` through the "
        "`_build_answers` rebuild"
    )


def test_the_flag_wins_when_preset_names_the_current_preset(tmp_path: Path) -> None:
    """`--preset` that does NOT switch must not swallow the depth flag.

    The seed is suppressed on the preset-switch path because `_build_answers` carries the
    depth there instead. Gating that on the flag's mere PRESENCE left a hole: with
    `--preset Production` on an already-Production harness, `_build_answers` never runs
    (`new_preset != answers.preset` is false) and the seed is suppressed too, so nothing
    carries the value — exit 0, no diagnostic, old depth persisted.

    Not a corner case: `commands/make.md`'s reconfigure path dispatches `--preset "$PRESET"`
    unconditionally with the collected value, which is usually unchanged. Every other
    `--preset` test here throws `Side` at a `Production` fixture, so the equal-preset branch
    was untested by construction.
    """
    _write_harness_yaml(tmp_path)  # on-disk depth: deep
    code, output, captured = _run(
        tmp_path, "--preset", "Production", "--comprehension-depth", "minimal"
    )
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == "minimal", (
        "a non-switching --preset swallowed the depth flag — the value the user typed was "
        "silently discarded"
    )


def test_reinterview_does_not_clobber_an_explicit_depth_flag(tmp_path: Path) -> None:
    """The `--reinterview` re-apply must yield to the flag.

    `_apply_dimension_overrides` runs at the TOP of `make`, before the re-apply block, so an
    ungated re-apply overwrites `--comprehension-depth` with the disk value — and with
    `standard` when the file carries no key at all. The flag is not merely ignored; its
    opposite reaches disk via the emitter.

    The sibling below covers the no-flag direction; this one covers the flag direction, and
    the pair is the whole contract: CLI flag > disk > preset default, on the `--reinterview`
    path too.
    """
    _write_harness_yaml(tmp_path)  # on-disk depth: deep
    from harness_maker.interview import _build_answers
    from harness_maker.models import DevMode, Preset, Target

    fresh = _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=Preset.PRODUCTION,
        dev_mode=DevMode.TASK_DRIVEN,
    )
    captured: dict[str, object] = {}

    def _capture_synthesize(p: object, a: object, **kw: object) -> object:
        from harness_maker.models import Blueprint, HarnessConfig

        captured["interview"] = a.interview  # type: ignore[attr-defined]
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.interview", return_value=fresh),
    ):
        result = runner.invoke(
            app,
            [
                "make",
                str(tmp_path),
                "--update",
                "--reinterview",
                "--comprehension-depth",
                "minimal",
            ],
        )

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert _depth(captured) == "minimal", (
        "the --reinterview re-apply overwrote the explicit flag with the disk value"
    )


def test_reinterview_preserves_an_explicit_on_disk_depth(tmp_path: Path) -> None:
    """`--reinterview` sets `reused = None`, so the ADR-002 read-side overlay never runs.

    `interview()` cannot re-ask either — ADR-003 deliberately adds no install-time question
    — so without an explicit re-apply the block is `_preset_extras`'s `standard` and the
    emitter writes it back over the user's file. A `depth: minimal` opt-out (the zero-cost
    escape ADR-005 leans on to justify the surface growth) is destroyed silently.

    **The stub matters.** Every other test here patches `cli.answers_from_harness_yaml` and
    `cli.interview` to the SAME disk-derived object, which makes the two branches
    indistinguishable by construction. Here `cli.interview` returns preset-default answers —
    what the real `--reinterview` path actually produces — so the assertion can fail.
    """
    _write_harness_yaml(
        tmp_path,
        "---\ngenerated_by: harness-maker\n---\n"
        "preset: Production\nlocale: en\ntargets: [claude-code]\n"
        "interview:\n  comprehension:\n    depth: minimal\n",
    )
    from harness_maker.interview import _build_answers
    from harness_maker.models import DevMode, Preset, Target

    fresh = _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=Preset.PRODUCTION,
        dev_mode=DevMode.TASK_DRIVEN,
    )
    assert fresh.interview["comprehension"]["depth"] == "standard", (
        "fixture precondition: a fresh interview must NOT already carry the disk value, "
        "or this test cannot distinguish the branches"
    )

    captured: dict[str, object] = {}

    def _capture_synthesize(p: object, a: object, **kw: object) -> object:
        from harness_maker.models import Blueprint, HarnessConfig

        captured["interview"] = a.interview  # type: ignore[attr-defined]
        return Blueprint(config=HarnessConfig(), files=[])

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.interview", return_value=fresh),
    ):
        result = runner.invoke(app, ["make", str(tmp_path), "--update", "--reinterview"])

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert _depth(captured) == "minimal", (
        "--reinterview reset the explicit on-disk depth to the preset default"
    )


@pytest.mark.parametrize(
    ("flag", "expected"),
    [(None, "deep"), ("minimal", "minimal")],
)
def test_reinterview_and_a_preset_switch_together(
    tmp_path: Path, flag: str | None, expected: str
) -> None:
    """The only input where BOTH cli.py guards are live in one invocation.

    Guard A (the seed, gated on an actual preset switch) and guard B (the `--reinterview`
    re-apply, gated on the flag being absent) are disjoint by construction — but "by
    construction" is what the first two versions of these guards also claimed, and each
    time the untested combination was where the hole was. No test covered this pair.

    No flag → the disk value survives the rebuild (guard B). Flag → the flag wins over both
    the disk value and the preset default (guard A's path is suppressed, and guard B stands
    down). And the preset's OWN `main_loop` must survive either way — that is the leak
    guard A exists to prevent.
    """
    _write_harness_yaml(tmp_path)  # on-disk depth: deep, preset Production
    from harness_maker.interview import _build_answers, _preset_extras
    from harness_maker.models import DevMode, Preset, Target

    fresh = _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=Preset.PRODUCTION,
        dev_mode=DevMode.TASK_DRIVEN,
    )
    captured: dict[str, object] = {}

    def _capture_synthesize(p: object, a: object, **kw: object) -> object:
        from harness_maker.models import Blueprint, HarnessConfig

        captured["interview"] = a.interview  # type: ignore[attr-defined]
        return Blueprint(config=HarnessConfig(), files=[])

    args = ["make", str(tmp_path), "--update", "--reinterview", "--preset", "Side"]
    if flag is not None:
        args += ["--comprehension-depth", flag]

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_capture_synthesize),
        patch("harness_maker.cli.render", return_value=[]),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli._write_harness_manifest"),
        patch("harness_maker.cli.interview", return_value=fresh),
    ):
        result = runner.invoke(app, args)

    assert result.exit_code == 0, f"exit {result.exit_code}:\n{result.output}"
    assert _depth(captured) == expected
    interview = captured["interview"]
    assert isinstance(interview, dict)
    assert interview["main_loop"] == _preset_extras(Preset.SIDE)["interview"]["main_loop"], (
        "the NEW preset's main_loop did not survive — a guard leaked the old preset's block"
    )


def test_the_flag_wins_over_the_on_disk_value(tmp_path: Path) -> None:
    """Documented precedence: CLI flag > harness.yaml > preset default."""
    _write_harness_yaml(tmp_path)
    code, output, captured = _run(tmp_path, "--comprehension-depth", "minimal")
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == "minimal"


def test_the_flag_wins_even_alongside_a_preset_switch(tmp_path: Path) -> None:
    """Both rewrite paths at once — the flag must still be the outermost authority."""
    _write_harness_yaml(tmp_path)
    code, output, captured = _run(tmp_path, "--preset", "Side", "--comprehension-depth", "minimal")
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == "minimal"


def test_a_preset_switch_with_the_flag_does_not_leak_the_old_presets_interview_block(
    tmp_path: Path,
) -> None:
    """The depth flag must carry ONLY the depth across a preset switch.

    `update` is applied with `model_copy` AFTER the `_build_answers` rebuild, so seeding the
    whole OLD `interview` dict wins over the rebuilt one and re-imports the previous
    preset's `main_loop.max_rounds` (Side ⇒ 5, Production ⇒ None). That value is emitted
    into `harness.yaml` and branched on by `plan.md.j2` ("up to 5 rounds" vs "unlimited
    rounds"), so the leak is user-visible.

    **The sibling above walks this exact invocation and cannot see it** — it asserts only
    the depth, which is the one field the bug does not touch. Asserting the field a bug
    changes is not optional just because a neighbouring assertion passes.
    """
    _write_harness_yaml(tmp_path)
    code, output, captured = _run(tmp_path, "--preset", "Side", "--comprehension-depth", "deep")
    assert code == 0, f"exit {code}:\n{output}"
    assert _depth(captured) == "deep"

    interview = captured["interview"]
    assert isinstance(interview, dict)
    from harness_maker.interview import _preset_extras
    from harness_maker.models import Preset

    expected = _preset_extras(Preset.SIDE)["interview"]["main_loop"]
    assert interview["main_loop"] == expected, (
        "the preset switch kept the OLD preset's main_loop — the depth flag overwrote the "
        f"rebuilt interview block: got {interview['main_loop']!r}, want {expected!r}"
    )
