"""AC-005 (property) — an explicit depth survives the yaml → answers → yaml round-trip.

`answers_from_harness_yaml` does NOT round-trip the `interview` block. It rebuilds the
whole block from `_preset_extras` and applies exactly one read-side overlay, for
`common_ground.llm_inference_enabled` — because 0.16.0's ADR-012 froze ε/τ/cap as code
constants. A key added to `_preset_extras` alone is therefore **silently reset to the
preset default on every `/harness-maker:make --update`**, which is the failure mode that
silently reverted hand-edited `scope`/`branch_prefix` before 0.48.0.

The oracle is an **inverse-pair invariant** — `read(write(read(write(d)))).depth == d` —
which holds for any correct reader/writer pair regardless of how either is implemented,
so it cannot be satisfied by reading the implementation. The input domain is the three
literals; enumeration is exhaustive, so no generator is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

DEPTHS = ("minimal", "standard", "deep")


def _write_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "harness.yaml"
    p.write_text("---\ngenerated_by: harness-maker\n---\n" + body)
    return p


def _emit(tmp_path: Path, depth: str, preset: str = "Production") -> Path:
    """write(d) — render a harness.yaml carrying an explicit depth."""
    source = _write_yaml(
        tmp_path / "src",
        f"preset: {preset}\nlocale: en\ntargets: [claude-code]\n"
        f"interview:\n  comprehension:\n    depth: {depth}\n",
    )
    answers = answers_from_harness_yaml(source)
    assert answers is not None
    out = tmp_path / f"out-{depth}-{preset}"
    render(synthesize(ProjectProfile(), answers), out / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    emitted = out / ".claude" / "harness.yaml"
    assert emitted.is_file(), f"renderer produced no harness.yaml at {emitted}"
    return emitted


@pytest.fixture(autouse=True)
def _mk_src(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(exist_ok=True)


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("preset", ["Production", "Side"])
def test_explicit_depth_survives_yaml_answers_yaml_roundtrip(
    tmp_path: Path, depth: str, preset: str
) -> None:
    """read(write(read(write(d)))).interview.comprehension.depth == d, for every d.

    Both presets, because `_preset_extras` has two branches and a key wired into only one
    of them regresses for the other with no diagnostic.
    """
    emitted = _emit(tmp_path, depth, preset)

    body = load_harness_yaml(emitted)
    assert body["interview"]["comprehension"]["depth"] == depth, (
        f"the emitted harness.yaml lost the depth: {body['interview'].get('comprehension')!r}"
    )

    reread = answers_from_harness_yaml(emitted)
    assert reread is not None
    assert reread.interview["comprehension"]["depth"] == depth, (
        "re-reading the emitted file did not recover the depth — `_preset_extras` "
        "rebuilds `interview` wholesale, so an explicit read-side overlay is required"
    )
    assert reread.preset == Preset(preset), "the round-trip must not move the preset either"


@pytest.mark.parametrize("depth", DEPTHS)
def test_the_roundtrip_is_idempotent_not_merely_survivable(tmp_path: Path, depth: str) -> None:
    """A second lap must not drift — one surviving lap can hide an off-by-one normalization."""
    first = _emit(tmp_path, depth)
    answers = answers_from_harness_yaml(first)
    assert answers is not None
    second_root = tmp_path / f"second-{depth}"
    render(
        synthesize(ProjectProfile(), answers),
        second_root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    second = second_root / ".claude" / "harness.yaml"
    assert load_harness_yaml(second)["interview"]["comprehension"]["depth"] == depth
    assert second.read_text(encoding="utf-8") == first.read_text(encoding="utf-8"), (
        "the emitted harness.yaml is not a fixed point — a re-render moves the file"
    )


def test_the_three_depths_do_not_all_emit_the_same_file(tmp_path: Path) -> None:
    """Guards the tautology: a writer that ignores `depth` would pass every arm above."""
    emitted = {d: _emit(tmp_path, d).read_text(encoding="utf-8") for d in DEPTHS}
    assert len(set(emitted.values())) == len(DEPTHS), (
        "the three depths produced identical harness.yaml files — the value is not being written"
    )
