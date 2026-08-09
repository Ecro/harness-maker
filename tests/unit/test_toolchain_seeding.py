"""Phase 3 of PLAN-second-opinion-oracle-polyglot — make-time seeding (ADR-007).

The two assertions that make the seeded value *useful* rather than merely present are the
`{path}` check and the runner-validity check. Without them, seeding the detector's own strings
would produce a harness whose oracle yields ZERO labelled evidence — for Python too — while
every other assertion here still passes and AC-011's warning never fires (the command set is
non-empty and the paths are covered). That is the exact residue validator pass 2 found.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.models import ToolchainConfig
from harness_maker.profile import detect_toolchains

_SENTINEL = "zz-user-authored-never-detected {path}"


def _pkg(tmp_path: Path, deps: dict[str, str], *, lockfile: str | None = None) -> Path:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "x", "devDependencies": deps, "scripts": {"test": "vitest"}}),
        encoding="utf-8",
    )
    if lockfile:
        (tmp_path / lockfile).write_text("", encoding="utf-8")
    return tmp_path


# --- detection produces USABLE commands, not just present ones ---------------------------


def test_python_group_is_path_scoped(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.uv]\n[tool.ruff]\n[tool.mypy]\n[tool.pytest.ini_options]\n", encoding="utf-8"
    )
    groups = detect_toolchains(tmp_path)
    assert [g.name for g in groups] == ["python"]
    assert set(groups[0].extensions) == {".py", ".pyi"}
    assert "{path}" in (groups[0].commands.test or "")
    assert "{path}" in (groups[0].commands.lint or "")


def test_python_roles_are_gated_on_evidence_not_on_pyproject_presence(tmp_path: Path) -> None:
    """`_detect_mechanical_checks`' own docstring records the measured harm of the ungated
    predicate: `uv run ruff check .` emitted on a repo that uses neither uv nor configures
    ruff. An ungated `uv run …` on a poetry/pip repo fails with FileNotFoundError or a sync
    error — which the verifier reads as an ABSENT oracle, so every finding degrades to
    `unresolved` while the coverage warning stays silent, because labelled blocks ARE being
    produced. They just contain no evidence.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert detect_toolchains(tmp_path) == [], "seeded a toolchain with zero supporting evidence"


def test_uv_prefix_only_when_the_project_is_uv_managed(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    poetry = detect_toolchains(tmp_path)
    assert poetry
    assert not (poetry[0].commands.lint or "").startswith("uv run")

    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    managed = detect_toolchains(tmp_path)
    assert managed
    assert (managed[0].commands.lint or "").startswith("uv run")


def test_runtime_dependency_does_not_seed_a_dev_check(tmp_path: Path) -> None:
    """devDependencies ONLY. A runtime package named `typescript` is not evidence that the
    project runs `tsc` as a check."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "x", "dependencies": {"typescript": "^5", "vitest": "^2"}}),
        encoding="utf-8",
    )
    assert detect_toolchains(tmp_path) == []


@pytest.mark.parametrize("lockfile", [None, "pnpm-lock.yaml", "yarn.lock"])
def test_node_commands_are_valid_for_every_runner(tmp_path: Path, lockfile: str | None) -> None:
    """`_detect_mechanical_checks` falls back to `npm` when no lockfile exists — the most
    common Node repo — and `npm vitest run x` is not a valid command: npm exposes no such
    subcommand. A wrong command exits non-zero WITHOUT parsing the subject and, because it
    carries `{path}`, is emitted id-LABELLED: fabricated evidence.
    """
    _pkg(tmp_path, {"vitest": "^2", "eslint": "^9", "typescript": "^5"}, lockfile=lockfile)
    groups = detect_toolchains(tmp_path)
    assert [g.name for g in groups] == ["node"]

    for role, template in groups[0].commands.declared():
        head = template.split()[0]
        assert head != "npm", f"{role}: bare `npm <bin>` is not a valid invocation"
        assert head in {"npx", "pnpm", "yarn"}, f"{role}: unexpected runner {head!r}"
        if head == "npx":
            assert template.split()[1] == "--no-install", (
                f"{role}: npx without --no-install may fetch a package mid-review"
            )


def test_absent_devdependency_yields_no_entry_for_that_role(tmp_path: Path) -> None:
    """A repo on `jest` must get NO `test` role rather than a wrong `vitest` command.
    An absent role routes to no_oracle with a visible reason — honest degradation."""
    _pkg(tmp_path, {"jest": "^29", "eslint": "^9"})
    groups = detect_toolchains(tmp_path)
    assert groups, "node stack should still be detected"
    assert groups[0].commands.test is None, "vitest was emitted for a jest project"
    assert groups[0].commands.lint is not None


def test_rust_is_repo_wide_and_declared(tmp_path: Path) -> None:
    """cargo takes a name filter, not a path — so Rust legitimately has no `{path}`.
    This is the ADR-007 declared limitation, pinned so it cannot drift into a fake path arg."""
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
    groups = detect_toolchains(tmp_path)
    assert [g.name for g in groups] == ["rust"]
    for _role, template in groups[0].commands.declared():
        assert "{path}" not in template


def test_mixed_stack_yields_disjoint_groups(tmp_path: Path) -> None:
    """One merged list is the P0 both second-opinion models found; groups must stay disjoint."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    _pkg(tmp_path, {"eslint": "^9"})
    groups = detect_toolchains(tmp_path)
    assert {g.name for g in groups} == {"python", "node"}
    seen: set[str] = set()
    for g in groups:
        assert not (seen & set(g.extensions)), "toolchain groups share an extension"
        seen |= set(g.extensions)


def test_unknown_stack_emits_nothing(tmp_path: Path) -> None:
    """Guessing is worse than silence: a wrong command is fabricated evidence."""
    (tmp_path / "CMakeLists.txt").write_text("project(x)\n", encoding="utf-8")
    assert detect_toolchains(tmp_path) == []


def test_every_path_scoped_role_carries_the_placeholder(tmp_path: Path) -> None:
    """The assertion that would have caught the pass-2 residue. A seeded value with no
    `{path}` produces only UNLABELLED blocks, i.e. zero per-finding evidence."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\n[tool.mypy]\n[tool.pytest.ini_options]\n", encoding="utf-8"
    )
    _pkg(tmp_path, {"vitest": "^2", "eslint": "^9"})
    for group in detect_toolchains(tmp_path):
        for role in ("test", "lint"):
            template = getattr(group.commands, role)
            if template is None:
                continue
            assert "{path}" in template, f"{group.name}.{role} is repo-wide: {template!r}"


# --- fill-if-empty ------------------------------------------------------------------------


def _seed(existing: list[ToolchainConfig], project: Path) -> list[ToolchainConfig]:
    from harness_maker.profile import seed_toolchains

    return seed_toolchains(existing, project)


def test_absent_key_is_filled(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    assert [g.name for g in _seed([], tmp_path)] == ["python"]


def test_user_authored_value_is_preserved_verbatim(tmp_path: Path) -> None:
    """The sentinel is a string no detector could ever emit, so preservation is
    distinguishable from coincidental regeneration."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    mine = [
        ToolchainConfig.model_validate(
            {"name": "mine", "extensions": [".py"], "commands": {"test": _SENTINEL}}
        )
    ]
    out = _seed(mine, tmp_path)
    assert [g.name for g in out] == ["mine"]
    assert out[0].commands.test == _SENTINEL


def test_detection_empty_leaves_the_key_absent(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(x)\n", encoding="utf-8")
    assert _seed([], tmp_path) == []


def test_a_malformed_user_block_is_not_overwritten_by_seeding(tmp_path: Path) -> None:
    """The reproduced defect: `answers_from_harness_yaml` drops an unusable value and returns
    the field default, so "wrote something unparseable" and "wrote nothing" arrive identically
    — and seeding then replaced the user's text with detected defaults, silently resuming
    checks they never configured AND defeating the oracle's fail-closed contract across one
    re-render.
    """
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n[tool.ruff]\n", encoding="utf-8")
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "---\ngenerated_by: harness-maker\n---\npreset: Side\ntoolchains: not-a-list\n",
        encoding="utf-8",
    )
    assert _seed([], tmp_path) == [], "seeding overwrote a malformed user block"


def test_seeding_still_fills_when_no_harness_yaml_exists(tmp_path: Path) -> None:
    """The key-presence guard must not turn fill-if-empty into never-fill on a fresh install."""
    (tmp_path / "pyproject.toml").write_text("[tool.uv]\n[tool.ruff]\n", encoding="utf-8")
    assert [g.name for g in _seed([], tmp_path)] == ["python"]


# --- end-to-end: a seeded fixture yields a LABELLED block ---------------------------------


def test_seeded_config_yields_a_labelled_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not only unlabelled repo-wide context. This is what `{path}` presence buys."""
    from harness_maker import second_opinion_oracle as soo

    _pkg(tmp_path, {"vitest": "^2", "eslint": "^9"})
    groups = detect_toolchains(tmp_path)

    monkeypatch.setattr(soo, "_changed_files", lambda _root: {"src/App.tsx"})
    monkeypatch.setattr(soo, "_load_toolchains", lambda _root: groups)
    monkeypatch.setattr(soo, "_run_argv", lambda argv, root: f"ran {argv[0]}")

    out = soo.gather([{"id": "f-1", "file": "src/App.tsx"}], tmp_path)
    assert "### oracle for id(s)=f-1" in out, f"seeded config produced no labelled block:\n{out}"
