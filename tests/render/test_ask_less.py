"""SPEC-ask-less: hm asks the DRI only what the DRI owns, and decides and reports the rest."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from harness_maker import synthesize
from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from tests._overhaul_p1_ref import HEAD_SRC, init_project, ref_root, run_make

#: SPEC Constraints "Order": main's tip once SPEC-hm-cost-p5 and the pipeline-env-fixes fold
#: landed (PR #49 merge commit), the base of AC-007 and AC-008.
BASE_SHA = "9a0788a1"
PRESETS = ("Side", "Production")
RUNTIMES = ("claude", "codex")
STAGES = ("research", "spec", "execute", "wrapup")
TOOL = {"claude": "`AskUserQuestion`", "codex": "`request_user_input`"}
_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")

#: SPEC "Rule text R", verbatim.
_R_HEAD = (
    "**Choices.** The DRI decides the goal, scope, overall design, a main feature, a "
    "costly-to-undo decision and every approval, plus any question this command names: ask with "
)
_R_TAIL = (
    ", recommendation first, except approvals and equal options; without the tool, a numbered "
    "list, then wait. Decide the rest yourself and report it."
)
RULE = {
    "claude": _R_HEAD + "`AskUserQuestion`" + _R_TAIL,
    "codex": _R_HEAD + "`request_user_input` where available" + _R_TAIL,
}
_OLD_TAIL = (
    "; recommendation first, except approvals and equal options. Without the tool: a numbered "
    "list, then wait; never choose for the user."
)
OLD_RULE = {
    "claude": "**Choices.** Ask each choice with `AskUserQuestion`" + _OLD_TAIL,
    "codex": "**Choices.** Ask each choice with `request_user_input` where available" + _OLD_TAIL,
}

_PATHS = {
    "claude": {
        **{s: f".claude/commands/hm/{s}.md" for s in STAGES},
        "maker": ".claude/skills/maker/SKILL.md",
        "intent": ".claude/skills/intent-layer/SKILL.md",
        "feedback": ".claude/skills/intent-layer/references/workflow-feedback.md",
    },
    "codex": {
        **{s: f".agents/skills/hm-{s}/SKILL.md" for s in STAGES},
        "maker": ".agents/skills/maker/SKILL.md",
        "intent": ".agents/skills/intent-layer/SKILL.md",
        "feedback": ".agents/skills/intent-layer/references/workflow-feedback.md",
    },
}

Renders = Callable[[str, str], Path]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Renders:
    """(preset, which) -> project root, where `which` is "head" or "base"."""
    cache: dict[tuple[str, str], Path] = {}

    def get(preset: str, which: str = "head") -> Path:
        if (preset, which) not in cache:
            base = tmp_path_factory.mktemp(f"ask-less-{preset}-{which}")
            src = HEAD_SRC if which == "head" else ref_root(base / "ref", BASE_SHA) / "src"
            project = init_project(base / "proj")
            proc = run_make(project, (*_ARGS, "--preset", preset), src=src, home=base / "home")
            assert proc.returncode == 0, proc.stderr[-2000:]
            cache[(preset, which)] = project
        return cache[(preset, which)]

    return get


def _read(root: Path, runtime: str, name: str) -> str:
    return (root / _PATHS[runtime][name]).read_text(encoding="utf-8")


def _step(text: str, heading: str) -> str:
    start = text.index(f"## {heading}")
    nxt = text.find("\n## ", start + 1)
    return text[start : nxt if nxt != -1 else len(text)]


def _intent_block(wrapup: str) -> str:
    start = wrapup.index("An intent in use")
    nxt = wrapup.find("\n## ", start)
    return wrapup[start : nxt if nxt != -1 else len(wrapup)]


@pytest.mark.parametrize("preset", PRESETS)
def test_ac_001_one_rule_everywhere(preset: str, rendered: Renders) -> None:
    root = rendered(preset, "head")
    for runtime in RUNTIMES:
        for name in (*STAGES, "maker"):
            assert _read(root, runtime, name).count(RULE[runtime]) == 1, (runtime, name)
    for tree in (".claude", ".agents"):
        for path in (root / tree).rglob("*"):
            if path.is_file():
                assert "never choose for the user" not in path.read_text(errors="replace"), path


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_002_intent_link_is_picked(runtime: str, rendered: Renders) -> None:
    step = _step(_read(rendered("Side", "head"), runtime, "spec"), "Step 0.5")
    assert TOOL[runtime] not in step
    assert "pick the one this task plainly serves, else none, without asking" in step
    assert "Step 3 writes `intent: <id>` and lists the pick under Refinement Decisions" in step


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_003_interview_asks_dri_slots_only(runtime: str, rendered: Renders) -> None:
    spec = _read(rendered("Side", "head"), runtime, "spec")
    step = _step(spec, "Step 2")
    for literal in (
        "Ask only what the DRI owns: categories 1–4 and each irreversible decision",
        "at most 3 questions per round",
        "Settle categories 5–6 and every oracle yourself",
        "Once nothing the DRI owns is open (round 1 included), one question per round offers",
        "Approve this SPEC and end interview",
        "Approve after spec-validator",
    ):
        assert literal in step, literal
    for gone in ("Ask for `oracle_source`", "closed ones are unlimited", "From round 2"):
        assert gone not in step, gone
    assert spec.count("Approve this SPEC and end interview") >= 2


def _spec_at_depth(depth: str, runtime: str) -> str:
    config = HarnessConfig().model_dump(mode="json")
    config["interview"].setdefault("comprehension", {})["depth"] = depth
    return (
        _make_env()
        .get_template("stages/spec.md.j2")
        .render(
            stage="spec", workflow_context="", project_name="", feature="", config=config,
            harness_maker_src_path=synthesize._HARNESS_MAKER_PKG_ROOT,
            is_codex=runtime == "codex", communication_variant="reframe",
        )
    )  # fmt: skip


@pytest.mark.parametrize("depth", ["minimal", "standard", "deep"])
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_004_decisions_listed_and_shown(runtime: str, depth: str) -> None:
    spec = _spec_at_depth(depth, runtime)
    assert (
        "Refinement Decisions lists each choice you made for the DRI: what, why and the cost "
        "to undo" in _step(spec, "Step 3 ")
    )
    assert "Show your Refinement Decisions with the approval question" in _step(spec, "Step 2")


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_005_wrapup_records_plain_writes(runtime: str, rendered: Renders) -> None:
    wrapup = _read(rendered("Side", "head"), runtime, "wrapup")
    block = _intent_block(wrapup)
    asked = "Anything else, and every write under an exempt SPEC: ask once with " + TOOL[runtime]
    asked_at = block.index(asked)
    for literal in (
        "Under an approved SPEC (not `--exempt`), write without asking",
        "`hm intent question add <id> … --status open` with `--claim-file <f>`",
        "`hm intent question observe <id> --relation <confirms|contradicts>",
        "`hm intent metric measure`",
        "`metric record` with an `--evidence-file` from this task",
    ):
        assert -1 < block.find(literal) < asked_at, literal
    assert block.count(TOOL[runtime]) == 1
    assert "then each intent write of Step 5" in _step(wrapup, "Step 8")
    assert "ask the DRI once (" not in wrapup


_ASKED = (
    "`question add --status confirmed|wrong`",
    "`question observe --relation supersedes`",
    "`question resolve`",
    "`new`",
    "`approve`",
    "`activate`",
    "`drop`",
    "`reopen`",
    "`close`",
)
_RECORDS = (
    "`question add --status open`",
    "`question observe --relation confirms|contradicts`",
    "`metric measure`",
    "`metric record` with an `--evidence-file` from this task",
)


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_006_intent_skill_splits_records_from_decisions(runtime: str, rendered: Renders) -> None:
    root = rendered("Side", "head")
    skill = _read(root, runtime, "intent")
    rule = _step(skill, "The rule for every write")
    for literal in (*_RECORDS, *_ASKED, "showing the exact arguments"):
        assert literal in rule, literal
    assert "written without asking under an approved SPEC" in rule
    asked_at = rule.index("showing the exact arguments")
    assert rule.index("on any other answer or no answer — write nothing") > asked_at
    for literal in (
        "ask about all candidates in one multi-select question",
        "an unticked candidate is declined; no answer writes nothing and records no decline",
        "answer every candidate before the first write",
    ):
        assert literal in skill, literal
    feedback = _read(root, runtime, "feedback")
    for gone in (
        "Ask before writes",
        "Mutation verbs write only after consent",
        "Workflow writes are consented once",
        "ask about each candidate in turn",
    ):
        assert gone not in skill, gone
        assert gone not in feedback, gone


_MEASURED = (*STAGES, "maker", "intent", "feedback")


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_007_nothing_else_grows(preset: str, runtime: str, rendered: Renders) -> None:
    head, base = rendered(preset, "head"), rendered(preset, "base")
    grew = sum(len(_read(head, runtime, n)) - len(_read(base, runtime, n)) for n in _MEASURED)
    allowance = 5 * (len(RULE[runtime]) - len(OLD_RULE[runtime]))
    assert grew <= allowance, (grew, allowance)


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_ac_008_fewer_tool_mentions(runtime: str, rendered: Renders) -> None:
    head, base = rendered("Side", "head"), rendered("Side", "base")

    def count(root: Path, name: str) -> int:
        return _read(root, runtime, name).count(TOOL[runtime])

    assert count(head, "spec") == count(base, "spec") - 1
    for name in ("wrapup", "research", "execute", "maker"):
        assert count(head, name) == count(base, name), name
    assert count(head, "intent") <= count(base, "intent")
