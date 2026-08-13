"""AC-004 + ADR-004/006 — the absent-case and malformed-value branches.

`[fail:design] absent-case = feature black hole` is this repo's most-recurring class
(count:8): a feature that activates on an optional field silently never fires for input
that predates the field. `interview.comprehension` is exactly such a field, so the branch
under test here is the one NOBODY exercises by using the product — every fresh install
takes the other one.

ADR-006 makes absent → `standard` for existing files too, i.e. an explicit, accepted
retrofit rather than a preservation bug. AC-004's oracle is **differential**: the
legacy-file render is compared against an explicitly-`standard` render produced by a
separate code path, so neither side can define correctness for the other.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

PRESETS = ("Production", "Side")


def _base(preset: str = "Production") -> str:
    """`_preset_extras` has two branches; a key wired into one regresses silently in the other."""
    return f"preset: {preset}\nlocale: en\ntargets: [claude-code]\n"


_BASE = _base()
_LEGACY_INTERVIEW = (
    "interview:\n"
    "  deep_gate:\n"
    "    eig_epsilon: 0.5\n"
    "    confidence_tau: 0.7\n"
    "    open_ended_cap_by_locale:\n"
    "      en: 2\n"
    "      ko: 1\n"
    "      ja: 1\n"
    "      default: 1\n"
    "    common_ground:\n"
    "      llm_inference_threshold: 0.95\n"
    "      llm_inference_enabled: true\n"
    "  main_loop:\n"
    "    max_rounds: null\n"
)


def _write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "harness.yaml"
    p.write_text("---\ngenerated_by: harness-maker\n---\n" + body)
    return p


def _depth(path: Path) -> str:
    answers = answers_from_harness_yaml(path)
    assert answers is not None
    value = answers.interview["comprehension"]["depth"]
    assert isinstance(value, str)
    return value


def _render_artifacts(path: Path, out: Path) -> dict[str, str]:
    """Every artifact the differential compares — commands **and** the emitted harness.yaml.

    Commands alone are depth-invariant until Phase 2 lands the partial, so a
    commands-only comparison cannot fail for ANY implementation at Phase 1. The emitted
    `harness.yaml` is the artifact that carries the value at this phase, so leaving it out
    made the oracle inert exactly where it was supposed to bite.
    """
    answers = answers_from_harness_yaml(path)
    assert answers is not None
    render(synthesize(ProjectProfile(), answers), out / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    artifacts = {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted((out / ".claude" / "commands" / "hm").glob("*.md"))
    }
    emitted = out / ".claude" / "harness.yaml"
    assert emitted.is_file(), f"renderer produced no harness.yaml at {emitted}"
    artifacts["harness.yaml"] = emitted.read_text(encoding="utf-8")
    return artifacts


@pytest.mark.parametrize("preset", PRESETS)
def test_legacy_harness_yaml_without_comprehension_defaults_to_standard(
    tmp_path: Path, preset: str
) -> None:
    """The count:8 branch: an `interview:` block written before the key existed."""
    p = _write_yaml(tmp_path, _base(preset) + _LEGACY_INTERVIEW)
    assert _depth(p) == "standard"


@pytest.mark.parametrize("preset", PRESETS)
def test_harness_yaml_with_no_interview_block_at_all_defaults_to_standard(
    tmp_path: Path, preset: str
) -> None:
    """Older still: the whole `interview:` key is absent, not just its new child."""
    p = _write_yaml(tmp_path, _base(preset))
    assert _depth(p) == "standard"


@pytest.mark.parametrize("preset", PRESETS)
def test_legacy_render_is_identical_to_an_explicit_standard_render(
    tmp_path: Path, preset: str
) -> None:
    """AC-004's differential oracle — two code paths, one expected artifact.

    The legacy file reaches `standard` through the absent branch; the explicit file
    reaches it through the round-trip overlay. Comparing them means neither side is
    asserting its own implementation back at itself.

    The depth agreement is asserted FIRST and on both paths. Without it this test is green
    today for every implementation — including the ADR-006 inversion (absent → `minimal`)
    it exists to forbid — because no rendered command reads the value until Phase 2. Going
    through `_depth` routes it into the same `KeyError` as its siblings, so it is a real
    RED now rather than a fixture that already passes.
    """
    legacy = _write_yaml(tmp_path / "a", _base(preset) + _LEGACY_INTERVIEW)
    explicit = _write_yaml(
        tmp_path / "b",
        _base(preset) + _LEGACY_INTERVIEW + "  comprehension:\n    depth: standard\n",
    )
    assert _depth(legacy) == "standard", "the absent branch did not resolve to standard"
    assert _depth(explicit) == "standard", "the explicit branch did not survive the round-trip"

    legacy_artifacts = _render_artifacts(legacy, tmp_path / "out-legacy")
    explicit_artifacts = _render_artifacts(explicit, tmp_path / "out-explicit")
    assert legacy_artifacts.keys() == explicit_artifacts.keys()
    for name in ("plan", "spec", "harness.yaml"):
        assert legacy_artifacts[name] == explicit_artifacts[name], (
            f"{name} diverged between the absent path and the explicit-standard path"
        )


@pytest.mark.parametrize("preset", PRESETS)
def test_the_emitted_harness_yaml_actually_carries_the_retrofitted_value(
    tmp_path: Path, preset: str
) -> None:
    """ADR-006's retrofit has to reach DISK, not just the in-memory answers.

    An emitter that resolves `standard` in memory but writes its own default would pass
    every in-memory assertion above while the user's file never gains the key.
    """
    p = _write_yaml(tmp_path, _base(preset) + _LEGACY_INTERVIEW)
    emitted = _render_artifacts(p, tmp_path / "out")["harness.yaml"]
    assert "comprehension:" in emitted, "the emitter did not write the block at all"
    assert "depth: standard" in emitted, f"the emitted file lost the retrofit:\n{emitted[:400]}"


@pytest.fixture(autouse=True)
def _mk_subdirs(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir(exist_ok=True)
    (tmp_path / "b").mkdir(exist_ok=True)


@pytest.mark.parametrize("bad", ["verbose", "full", "MINIMAL", "", "deeep"])
def test_unknown_depth_normalizes_to_standard(tmp_path: Path, bad: str) -> None:
    """ADR-004: fail-open. A typo must not disable the feature and must not brick the load."""
    p = _write_yaml(tmp_path, _BASE + _LEGACY_INTERVIEW + f"  comprehension:\n    depth: {bad!r}\n")
    assert _depth(p) == "standard"


@pytest.mark.parametrize(
    "malformed",
    [
        "  comprehension: not-a-mapping\n",
        "  comprehension: []\n",
        "  comprehension:\n    depth: 3\n",
        "  comprehension:\n    depth: null\n",
        "  comprehension: {}\n",
    ],
)
def test_wrong_container_types_fall_back_without_raising(tmp_path: Path, malformed: str) -> None:
    """A hand-edited file can put anything here; none of it may raise on load."""
    p = _write_yaml(tmp_path, _BASE + _LEGACY_INTERVIEW + malformed)
    assert _depth(p) == "standard"


def test_unknown_depth_warns_and_says_the_value_will_be_rewritten(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """ADR-004's corrected consequence.

    Normalization happens on read and the harness-yaml emitters re-emit from the
    normalized config, so `depth: verbose` becomes `depth: standard` on disk at the next
    `--update` and this warning can never fire again. It is therefore the ONLY notice the
    user ever gets, and it has to say so — an earlier draft promised "until they read the
    warning", which assumed a persistence that does not exist.
    """
    p = _write_yaml(tmp_path, _BASE + _LEGACY_INTERVIEW + "  comprehension:\n    depth: verbose\n")
    with caplog.at_level(logging.WARNING):
        answers_from_harness_yaml(p)
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    hit = [m for m in warnings if "comprehension" in m]
    assert hit, f"no comprehension warning emitted; got {warnings!r}"
    message = hit[0]
    assert "verbose" in message, "the warning must name the offending value"
    assert str(p) in message or p.name in message, "the warning must name the file"
    assert "standard" in message, "the warning must name the value it fell back to"
    assert "rewrit" in message.lower() or "overwrit" in message.lower(), (
        "the warning must state that the typo does not survive the next re-render — "
        f"got: {message!r}"
    )


def test_a_valid_value_is_not_warned_about(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A warning on the happy path trains the user to ignore the warning."""
    p = _write_yaml(tmp_path, _BASE + _LEGACY_INTERVIEW + "  comprehension:\n    depth: deep\n")
    with caplog.at_level(logging.WARNING):
        assert _depth(p) == "deep"
    assert not [
        r.getMessage()
        for r in caplog.records
        if r.levelno >= logging.WARNING and "comprehension" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# The two `models.py` default factories — the suppliers no yaml path reaches.
#
# `_preset_extras` is only one of four suppliers the PLAN enumerates. A bare
# `HarnessConfig()` / `InterviewAnswers()` is an implicit call site at every construction
# and every fall-through, and `[fail:design] promoted-default-reaches-bare-callers` is the
# class where those fall-throughs are invisible to grep because they name nothing.
# ---------------------------------------------------------------------------


def test_bare_harness_config_carries_the_default_depth() -> None:
    from harness_maker.models import HarnessConfig

    assert HarnessConfig().interview["comprehension"]["depth"] == "standard"


def test_bare_interview_answers_carries_the_default_depth() -> None:
    from harness_maker.models import InterviewAnswers

    assert InterviewAnswers().interview["comprehension"]["depth"] == "standard"


def test_the_two_factories_do_not_share_a_mutable_default() -> None:
    """A shared dict would let one construction's edit leak into every later one."""
    from harness_maker.models import HarnessConfig

    first, second = HarnessConfig(), HarnessConfig()
    first.interview["comprehension"]["depth"] = "deep"
    assert second.interview["comprehension"]["depth"] == "standard"


def test_the_emitters_survive_a_config_whose_interview_dict_lacks_the_key(
    tmp_path: Path,
) -> None:
    """PLAN Phase 1 exit criterion — the `.get()`/`| default()` rule covers the EMITTERS too.

    `harness-yaml/{Production,Side}.yaml.j2` use bare attribute access throughout
    (`config.interview.deep_gate.eig_epsilon`), and several tests construct a
    `HarnessConfig` with a hand-built `interview` dict. A `comprehension:` emit line
    written in the house style raises `UndefinedError` for every one of them — a failure
    no yaml-driven test can reach, because `answers_from_harness_yaml` always supplies the
    key.
    """
    for preset in PRESETS:
        preset_dir = tmp_path / preset
        preset_dir.mkdir(exist_ok=True)
        source = _write_yaml(preset_dir, _base(preset) + _LEGACY_INTERVIEW)
        answers = answers_from_harness_yaml(source)
        assert answers is not None
        blueprint = synthesize(ProjectProfile(), answers)
        # Strip the key back out of the SYNTHESIZED config — this is the hand-built-dict
        # shape, reached through the real blueprint so the emitter actually runs.
        blueprint.config.interview.pop("comprehension", None)
        assert "comprehension" not in blueprint.config.interview
        out = source.parent / "rendered"
        render(blueprint, out / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        emitted = (out / ".claude" / "harness.yaml").read_text(encoding="utf-8")
        assert "depth: standard" in emitted, (
            f"{preset}: the emitter did not fall back to the default for an absent key:\n"
            f"{emitted[:400]}"
        )


@pytest.mark.parametrize("bad", [None, [], "", 0])
def test_the_depth_guard_survives_a_present_but_malformed_comprehension(bad: object) -> None:
    """`.get(k, {})` guards the ABSENT key only — a present-but-`None` value defeats it.

    `dict.get('comprehension', {})` returns the stored `None` when the key EXISTS, and
    `None.get('depth', …)` then raises under `StrictUndefined`. Both cross-model reviewers
    found this independently and the expression oracle confirms it. The absent-key siblings
    above cannot catch it: `.pop()` produces the one shape the original guard did handle —
    the same absent-case class, one level in, written for the branch its author had in mind.

    **Asserted at the expression, deliberately.** A first attempt mutated
    `blueprint.config.interview` after `synthesize` and rendered; it passed against the OLD
    expression too, i.e. it discriminated nothing. The reason is the finding's own limit:
    templates read the per-file `fe.context` built at synthesize time, not `bp.config`, so a
    post-synthesize mutation never reaches Jinja. **No code path can deliver a malformed
    value here** — `_parse_comprehension` normalizes on read. The guard is therefore
    defense-in-depth, and this test pins the guard rather than pretending to a reachability
    that does not exist.

    **Stated residual:** `or {}` catches FALSY non-mappings only. A truthy non-mapping — a
    non-empty string, a non-zero int — still raises, and is deliberately left unguarded:
    it is equally unreachable, and an `is mapping` ternary across five template sites buys
    nothing but length. The parametrize below is scoped to what the guard actually promises
    rather than to what the finding claimed, so it cannot drift into a false green.
    """
    import jinja2

    env = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False)  # noqa: S701
    expression = env.from_string(
        "{{ (config.interview.get('comprehension') or {}).get('depth', 'standard') }}"
    )
    config = type("C", (), {"interview": {"comprehension": bad}})()
    assert expression.render(config=config) == "standard"
