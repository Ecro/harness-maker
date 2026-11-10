"""SPEC-hm-cost-p4 AC-008: hm-novalidator is the hm arm minus spec-validator, nothing else."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.test_bench_light_lane import _load

bench = _load()

SPEC_COMMANDS = (".claude/commands/hm/spec.md", ".agents/skills/hm-spec/SKILL.md")
#: Render bookkeeping that carries the render's own timestamp, so two hm renders differ there too.
VOLATILE = (".claude/.hm-render-manifest.jsonl", ".claude/observability/")


def _files(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
        and ".git" not in p.relative_to(root).parts
        and not p.relative_to(root).as_posix().startswith(VOLATILE)
    }


@pytest.fixture(scope="module")
def templates(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    base = tmp_path_factory.mktemp("arms")
    bench.build_template(base / "hm", "hm")
    bench.build_template(base / "nv", "hm-novalidator")
    return _files(base / "hm"), _files(base / "nv")


def test_ac_008_novalidator_arm(templates: tuple[dict[str, bytes], dict[str, bytes]]) -> None:
    hm, nv = templates
    assert "hm-novalidator" in bench.ALL_ARMS
    assert set(hm) == set(nv)
    changed = sorted(f for f in hm if hm[f] != nv[f])
    assert changed
    assert set(changed) <= set(SPEC_COMMANDS), changed
    for f in changed:
        assert b"spec-validator" in hm[f]
        assert b"spec-validator" not in nv[f]
    task = next(t for t in bench.load_tasks() if t.tier == 1)
    for s in range(len(task.session_prompts)):
        assert bench.prompt_for(task, "hm-novalidator", s) == bench.prompt_for(task, "hm", s)
    assert bench.template_key(task, "hm-novalidator") != bench.template_key(task, "hm")
    assert bench.uses_dri(task, "hm-novalidator") == bench.uses_dri(task, "hm") is True
