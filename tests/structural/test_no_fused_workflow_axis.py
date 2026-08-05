"""Phase 1 gate — the fused-workflow axis is gone, root and branch (ADR-001/002/012).

These assertions are deliberately *absence* checks. The axis was 58.6% of the shipped
Claude command surface and had zero recorded invocations, so the only durable proof it
stayed deleted is a test that fails the moment any part of it grows back.

Three things this file must NOT assert, because they are unrelated surfaces that merely
share the word "workflow":
  * `.github/workflows/` — read by `profile.py`, `test_dep_map.py`, `readiness.py`.
  * `worktree.py`'s `<workflow>-<uuid>-<ts>` directory naming.
  * `AtomicStage` itself — all seven stages survive; only their *fusion* is removed.
"""

from __future__ import annotations

import importlib
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import render
from harness_maker.synthesize import synthesize
from tests.structural.conftest import pin_install_ref

_FROZEN = datetime(2026, 1, 1, tzinfo=UTC)
_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src" / "harness_maker"
_TEMPLATES = _SRC / "templates"

# The schema defined SEVEN fused names (interview.py starter tables); this repo only ever
# rendered five of them. Both sets must be gone.
FUSED_NAMES = (
    "exec-rev",
    "exec-rev-wrap",
    "exec-rev-ver-wrap",
    "exec-rev-wrap-ver",
    "plan-exec-rev",
    "plan-exec-rev-wrap",
    "res-spec-plan",
)

DELETED_TEMPLATES = (
    "commands/hm/workflow_command.md.j2",
    "codex/workflow_skill.md.j2",
    "rubrics/workflow.yaml.j2",
    "agents/_partials/fused_preamble.md.j2",
)


def test_workflow_fuse_module_is_gone() -> None:
    assert not (_SRC / "workflow_fuse.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("harness_maker.workflow_fuse")


def test_harness_config_has_no_workflow_axis() -> None:
    from harness_maker.models import HarnessConfig

    for field in ("workflows", "default_workflow"):
        assert field not in HarnessConfig.model_fields, f"HarnessConfig.{field} survived"


def test_interview_answers_has_no_workflow_axis() -> None:
    from harness_maker.models import InterviewAnswers

    for field in ("fused_workflows", "default_workflow"):
        assert field not in InterviewAnswers.model_fields, f"InterviewAnswers.{field} survived"


@pytest.mark.parametrize(
    ("module", "symbol"),
    [
        ("harness_maker.models", "STAGE_ABBREV"),
        ("harness_maker.models", "auto_workflow_name"),
        ("harness_maker.models", "WorkflowDef"),
        ("harness_maker.validators", "RESERVED_WORKFLOW_NAMES"),
        ("harness_maker.validators", "validate_workflow_name"),
    ],
)
def test_axis_symbol_is_gone(module: str, symbol: str) -> None:
    """A deleted module satisfies this as fully as a deleted symbol.

    `validators.py` existed only to police workflow names, so the whole module went;
    importing it raises rather than returning a namespace without the symbol.
    """
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError:
        return
    assert not hasattr(mod, symbol), f"{module}.{symbol} survived"


@pytest.mark.parametrize("rel", DELETED_TEMPLATES)
def test_fused_template_is_deleted(rel: str) -> None:
    assert not (_TEMPLATES / rel).exists(), f"{rel} survived"


def test_no_template_references_workflow_context() -> None:
    """`workflow_context` only ever existed to let a stage know it was fused."""
    hits = [
        p.relative_to(_SRC).as_posix()
        for p in _TEMPLATES.rglob("*.j2")
        if "workflow_context" in p.read_text(encoding="utf-8")
    ]
    assert hits == [], f"workflow_context survived in: {hits}"


def test_no_template_references_the_deleted_config_fields() -> None:
    pattern = re.compile(r"config\.(default_workflow|workflows|fused_workflows)\b")
    hits = [
        p.relative_to(_SRC).as_posix()
        for p in _TEMPLATES.rglob("*.j2")
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert hits == [], f"deleted config field referenced in: {hits}"


def _fresh_render(preset: Preset, targets: list[Target], tmp: Path) -> dict[str, str]:
    """Render into a tmp dir and return every emitted path → text.

    Asserting against the repo's own `.claude/` would be VACUOUS: `.gitignore:26`
    (`.claude/*`) means the dogfooded render is absent from every checkout, so such a
    test passes whether or not the axis was removed. That is the absent-case no-op this
    project keeps re-learning; the positive control below is what keeps it honest.
    """
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(ProjectProfile(), InterviewAnswers(preset=preset, targets=targets)),
            tmp,
            freeze_time=_FROZEN,
        )
    return {
        p.relative_to(tmp).as_posix(): p.read_text(encoding="utf-8", errors="replace")
        for p in tmp.rglob("*")
        if p.is_file()
    }


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, str]]:
    """Both presets × the target combinations that carry commands (PLAN Phase 1 exit)."""
    combos = {
        "prod-all": (Preset.PRODUCTION, [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]),
        "prod-claude": (Preset.PRODUCTION, [Target.CLAUDE_CODE]),
        "side-all": (Preset.SIDE, [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]),
        "side-claude": (Preset.SIDE, [Target.CLAUDE_CODE]),
    }
    return {
        label: _fresh_render(preset, targets, tmp_path_factory.mktemp(label))
        for label, (preset, targets) in combos.items()
    }


def test_the_render_fixture_is_not_empty(renders: dict[str, dict[str, str]]) -> None:
    """Positive control — every absence assertion below is vacuous against an empty render."""
    for label, files in renders.items():
        stages = [p for p in files if re.search(r"commands/hm/(execute|review|plan)\.md$", p)]
        assert len(stages) == 3, f"{label}: expected 3 atomic stage commands, got {stages}"
        assert any(len(t) > 10_000 for t in files.values()), f"{label}: render looks truncated"


@pytest.mark.parametrize("name", FUSED_NAMES)
def test_no_fresh_render_emits_a_fused_command(
    renders: dict[str, dict[str, str]], name: str
) -> None:
    for label, files in renders.items():
        offenders = [
            p for p in files if p.endswith(f"commands/hm/{name}.md") or f"hm-{name}/SKILL.md" in p
        ]
        assert offenders == [], f"{label}: {offenders}"


def test_retired_top_level_keys_are_declared() -> None:  # ADR-012
    """The drop-list is a named constant, not an implicit absence."""
    from harness_maker.render import _RETIRED_TOP_LEVEL_KEYS

    assert {"workflows", "default_workflow"} <= set(_RETIRED_TOP_LEVEL_KEYS)


def test_a_retired_key_is_not_re_injected_on_re_render(tmp_path: Path) -> None:
    """The BEHAVIOUR, not the constant.

    Asserting only that the constant contains the two names leaves the wiring untested.

    **Superseded mechanism (2026-08-05, PLAN-harness-diet Phase 2).** This docstring used
    to say "delete the ``and k not in _RETIRED_TOP_LEVEL_KEYS`` clause and this still
    passes" — which was the reason this test existed. It is no longer true of that clause:
    ``load_harness_yaml`` now strips retired keys on every read, so ``_preserve_yaml_user_keys``
    never sees one and the clause is unreachable. Deleting it leaves this test GREEN
    (verified). What this test now guards is the LOADER-level strip, which is the layer that
    actually enforces the behaviour. The unreachable render-side clause is reached
    deliberately by ``tests/unit/test_retired_key_migration.py``.

    Scope correction (review, 2026-08-05): the original rationale claimed the regrown key
    would then fail ``HarnessConfig``'s ``extra="forbid"`` on the next load. **No such path
    exists** — nothing validates a user's harness.yaml into `HarnessConfig`;
    `answers_from_harness_yaml` reads selected keys and ignores the rest. The real cost is
    narrower and still worth a gate: a retired key silently persisting in every user's
    config forever, re-appended under an "@hm:user:extensions" banner that says it is
    theirs.
    """
    out = tmp_path / "harness.yaml"
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
            ),
            tmp_path,
            freeze_time=_FROZEN,
        )
    assert out.is_file(), "fixture did not render harness.yaml — assertion would be vacuous"

    # Simulate a pre-diet install: append the retired keys as a user would have had them.
    out.write_text(
        out.read_text(encoding="utf-8")
        + "\nworkflows:\n  exec-rev:\n    - execute\n    - review\ndefault_workflow: exec-rev\n",
        encoding="utf-8",
    )
    assert "workflows:" in out.read_text(encoding="utf-8"), "seed did not take"

    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
            ),
            tmp_path,
            freeze_time=_FROZEN,
        )
    after = out.read_text(encoding="utf-8")
    assert "\nworkflows:" not in after, "retired `workflows:` was re-injected on re-render"
    assert "default_workflow:" not in after, "retired `default_workflow:` was re-injected"


# Prose, not just expressions. The Jinja-expression checks above miss a template that
# merely *talks* about the deleted feature — which is how four stage templates, four
# shipped skills, `AGENTS.md`, the Cursor rule and `/hm:configure` all kept advertising
# fused workflows after the axis was gone (review round 1, 2026-08-05).
#
# Round-2 hardening (re-review): the ban was English-only and the allow-list was ONE
# exact English phrase, so a Korean rendering slipped past the ban while a reworded
# English sentence could accidentally satisfy the allow. The allow is now an explicit
# marker a human must type — an escape hatch cannot be entered by accident.
# TWO vocabularies, not one. The feature is "fused workflow" in the config and the code, but
# the prose docs call the same thing a "fusion command" / "퓨전 명령" — and the first version
# of this pattern banned only the former. Result: `docs/HOW-IT-WORKS{,.ko}.md` kept asserting
# "coupling between stages is handled by fusion commands" through the entire removal, and the
# Korean file kept a whole section 4 documenting the four deleted commands, while this gate
# stayed green. Ban both spellings in both languages.
_PROSE_BAN = re.compile(
    r"fused workflow|fused-workflow|융합 워크플로|fusion command|퓨전 명령"
    r"|@hm-exec-rev|/hm:exec-rev|`exec-rev|`plan-exec-rev|`res-spec-plan"
)
_AXIS_REMOVED_MARKER = "<!-- @hm:axis-removed -->"


def _prose_offenders(paths: list[Path], root: Path) -> list[str]:
    """A line may name the axis ONLY to say it is gone, and must carry the marker."""
    return [
        f"{p.relative_to(root).as_posix()}:{n}"
        for p in paths
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if _PROSE_BAN.search(line) and _AXIS_REMOVED_MARKER not in line
    ]


def test_no_repo_doc_advertises_a_fused_workflow() -> None:
    """The gate's scope was the SHIPPED render surface; the repo's own docs were outside it.

    That omission is the same shape as the two the reviews already caught this task — a gate
    aimed at the artifact being fixed, letting the identical defect survive next to it. The
    templates were swept clean while `docs/HOW-IT-WORKS.ko.md` still carried section 4.1-4.4
    describing `/hm:res-spec-plan`, `/hm:exec-rev`, `/hm:exec-rev-wrap` and
    `/hm:exec-rev-wrap-ver` as live commands, and both language versions still told the reader
    that stages are coupled by fusion commands.

    CHANGELOG and `work-docs/` are excluded on purpose: a changelog and a landed PLAN/REVIEW
    are HISTORICAL records, and an entry that describes what a past release removed has to be
    allowed to name it. `TECH_SPEC.md` keeps its build-phase history for the same reason and
    annotates the live claims in place, so it is excluded too. Everything a reader treats as
    a description of the CURRENT system is in scope.

    A line that announces the removal is exempted by the explicit `<!-- @hm:axis-removed -->`
    marker — a human has to type it, so a future rewording cannot satisfy the exemption by
    accident.
    """
    docs = [_REPO / "README.md", _REPO / "README.ko.md"]
    docs += sorted(
        d for d in (_REPO / "docs").rglob("*.md") if "adr" not in d.relative_to(_REPO).parts
    )
    paths = [d for d in docs if d.is_file()]
    # Non-vacuity: a mistyped root would make this pass over an empty list forever.
    assert len(paths) >= 5, [str(p) for p in paths]
    assert _prose_offenders(paths, _REPO) == []


def test_no_shipped_template_advertises_a_fused_workflow() -> None:
    paths = sorted(_TEMPLATES.rglob("*.j2"))
    assert len(paths) > 50, f"sweep saw only {len(paths)} templates — the fixture is broken"
    assert _prose_offenders(paths, _SRC) == []


def test_the_plugins_own_shipped_surface_is_clean() -> None:
    """Everything the plugin ships that is NOT a template, so no template sweep sees it.

    `commands/make.md` is the entry point for a NEW install and carried `default_workflow`
    until review round 1; `skills/` and `agents/` ship verbatim to three IDEs.
    """
    # The plugin's skills/ and agents/ live UNDER templates/ and are covered by the .j2
    # sweep above; `commands/` is the one shipped surface outside it. README is
    # deliberately not swept here — its fused references are PLAN Phase 6 (serial-close)
    # scope, and a gate that fails on scheduled work teaches people to disable gates.
    paths = sorted((_REPO / "commands").glob("*.md"))
    assert paths, "sweep saw no plugin commands — the fixture is broken"
    offenders = _prose_offenders(paths, _REPO) + [
        f"{p.relative_to(_REPO).as_posix()}:{n}"
        for p in paths
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "default_workflow" in line
    ]
    assert offenders == [], f"plugin surface still names the deleted axis: {offenders}"
