"""HM-LIGHT-LANE stage 2a — stage text that cannot run in the harness that renders it goes.

The 2026-10-14 phase-pruning research found that most removable text is not a weak check but a
path the rendering harness cannot take: loop-only branches in a loop-off harness, an auto-advance
procedure repeated in six commands, telemetry with no input. The DRI approved these cuts on
decision cards the same day (SPEC-hm-light-lane-s2).

What must hold: a loop-on harness keeps every loop branch word for word, and autopilot runs the
same executed lines with the same instructions, now read from one shared file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

from harness_maker import models
from harness_maker.interview import _build_answers, answers_from_harness_yaml
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import _TYPED_ONLY_SKILLS, synthesize

REPO = Path(__file__).parents[2]
TEMPLATES = REPO / "src" / "harness_maker" / "templates"
FIXTURES = REPO / "tests" / "fixtures" / "light_lane_s2"
STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")
SHARED = "hm/autopilot-advance.md"
OPEN, CLOSE = "<!-- @hm:autopilot-advance -->", "<!-- @hm:/autopilot-advance -->"
LOOP_OPEN, LOOP_CLOSE = "<!-- @hm:loop-only -->", "<!-- @hm:/loop-only -->"

# The loop-only inventory the research measured in the e9b6198 render, before any edit.
LOOP_ONLY_MARKERS = (
    "Gate 0",
    "iter_receipts write",
    "Step 0.2 — Loop mode",
    "loop-mode-active",
    "Step 5 — Worktree finalize",
    "Check 5 — Worktree merge cleanliness",
)

# Seven skills carried the per-template flag at e9b6198.
TYPED_ONLY_AT_E9B6198 = {
    "intent-layer",
    "project-knowledge",
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "autoloop-driver",
    "context-linter",
    "worktree-isolator",
}


def _render(
    root: Path,
    *,
    loop: bool,
    level: str = "auto_safe",
    preset: Preset = Preset.PRODUCTION,
) -> Path:
    answers = _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE, Target.CODEX],
        preset=preset,
        loop=models.LoopConfig(enabled=loop),
        autonomy=models.AutonomyConfig(level=level),  # type: ignore[arg-type]
        worktree_enabled=True,
    )
    render(
        synthesize(ProjectProfile(), answers, preset=preset),
        root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return root


def _norm(text: str) -> str:
    # The install ref is a checkout path that differs per machine; fixtures carry `{src}`.
    return re.sub(r"--with \S+ hm ", "--with {src} hm ", text)


def _bodies(root: Path) -> dict[str, str]:
    out = {
        f"claude:{s}": (root / ".claude" / "commands" / "hm" / f"{s}.md").read_text()
        for s in STAGES
    }
    for s in STAGES:
        out[f"stages:{s}"] = (root / ".claude" / "stages" / f"{s}.md").read_text()
    for s in STAGES:
        p = root / ".agents" / "skills" / f"hm-{s}" / "SKILL.md"
        if p.exists():
            out[f"codex:{s}"] = p.read_text()
    return out


@pytest.fixture(scope="module")
def loop_off(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _render(tmp_path_factory.mktemp("s2-loop-off"), loop=False)


@pytest.fixture(scope="module")
def loop_on(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _render(tmp_path_factory.mktemp("s2-loop-on"), loop=True)


def _between(body: str, start: str, stop: str) -> str:
    i = body.find(start)
    assert i != -1, f"missing anchor {start!r}"
    j = body.find(stop, i + len(start))
    assert j != -1, f"missing end anchor {stop!r}"
    return body[i + len(start) : j]


# AC-001
def test_loop_off_renders_no_loop_branch(loop_off: Path) -> None:
    bodies = _bodies(loop_off)
    assert any(k.startswith("codex:") for k in bodies), "Codex stage skills must be covered too"
    for name, body in bodies.items():
        hits = [m for m in LOOP_ONLY_MARKERS if m in body]
        assert not hits, f"{name} carries loop-only text with loop off: {hits}"


# AC-002
def _no_frontmatter(body: str) -> str:
    # The provenance hash covers the body, so it moves with every loop section by construction.
    return re.sub(r"^content_hash: .*$", "", body, count=1, flags=re.M)


def _strip_loop(body: str) -> str:
    body = _no_frontmatter(body)
    out = re.sub(
        re.escape(LOOP_OPEN) + r".*?" + re.escape(LOOP_CLOSE) + r"\n?", "", body, flags=re.S
    )
    return re.sub(r"\n{3,}", "\n\n", out)


# SPEC S2's inventory: the lead line of every loop-only section, fixed before the edit. A section
# gated beyond these changes the lead set, so over-gating cannot pass by construction.
_GATE0_LEAD = {"execute": "### Step 4.5 — Emit Gate 0 receipt (ADR-001, ADR-005)"}
S2_INVENTORY: dict[str, list[str]] = {
    "research": [],
    "spec": [],
    "execute": [
        "#### Step 0.2 — Loop mode: the per-iter PLAN",
        "### Step 5 — Worktree finalize (ephemeral `/hm:loop` worktrees ONLY)",
        "- An `execute-<uuid>` worktree finalized exactly once: success or fail.",
    ],
    "review": ["• Loop mode: proceed", "→ Loop mode: emit the Gate 0 receipt"],
    "verify": ["### Check 5 — Worktree merge cleanliness"],
    "wrapup": [],
}


def _leads(body: str) -> list[str]:
    spans = re.findall(re.escape(LOOP_OPEN) + r"\s*(.*?)\n", body)
    return sorted(spans)


def _expected_leads(stage: str) -> list[str]:
    gate0 = _GATE0_LEAD.get(stage, "## Emit Gate 0 receipt (ADR-001, ADR-005)")
    return sorted([gate0, *S2_INVENTORY[stage]])


def test_loop_on_adds_exactly_the_loop_branches(loop_off: Path, loop_on: Path) -> None:
    off, on = _bodies(loop_off), _bodies(loop_on)
    assert off.keys() == on.keys()
    for name, body in on.items():
        stage = name.split(":")[1]
        # Codex spells the loop command `$hm-loop` (template_globals.stage_invocation).
        leads = sorted(ld.replace("`$hm-loop`", "`/hm:loop`") for ld in _leads(body))
        expected = _expected_leads(stage)
        assert len(leads) == len(expected), f"{name}: loop sections {leads}"
        for got, want in zip(leads, expected, strict=True):
            assert got.strip().startswith(want), f"{name}: {got!r} is not {want!r}"
    for name in on:
        assert LOOP_OPEN not in off[name], f"{name}: a loop marker rendered with loop off"
        assert _strip_loop(on[name]) == re.sub(r"\n{3,}", "\n\n", _no_frontmatter(off[name])), (
            f"{name}: the loop flag changed text outside the loop-only sections"
        )
    claude_on = {k.split(":")[1]: v for k, v in on.items() if k.startswith("claude:")}
    for stage in STAGES:
        assert "Gate 0 receipt" in claude_on[stage], f"{stage}: loop-on lost its Gate 0 receipt"
    assert "Step 0.2 — Loop mode" in claude_on["execute"]
    assert "Step 5 — Worktree finalize" in claude_on["execute"]
    assert "Check 5 — Worktree merge cleanliness" in claude_on["verify"]


# AC-003
def _gate_predicate(stage: str) -> str:
    src = (TEMPLATES / "stages" / f"{stage}.md.j2").read_text()
    m = re.search(r'set summary_autopilot_gate = "((?:[^"\\]|\\.)*)"', src)
    assert m, f"{stage}: no summary_autopilot_gate"
    return m.group(1)


def _executed(stub: str) -> list[str]:
    return [ln for ln in stub.splitlines() if ln.startswith("!uv run")]


@pytest.mark.parametrize("stage", STAGES)
def test_stub_points_at_the_shared_procedure(loop_off: Path, stage: str) -> None:
    body = (loop_off / ".claude" / "commands" / "hm" / f"{stage}.md").read_text()
    stub = _between(body, OPEN, CLOSE)
    assert f".claude/{SHARED}" in stub
    for phrase in (
        "project root",
        "never from `<WT>`",
        "missing or unreadable",
        "no `Skill` tool",
        "loop-mode is on for THIS session",
    ):
        assert phrase in " ".join(stub.split()), f"{stage}: stub lacks {phrase!r}"
    predicate = _gate_predicate(stage)
    assert predicate in stub, f"{stage}: the stub lost its own gate predicate"
    prose = stub.replace(predicate, "")
    for line in _executed(stub):
        prose = prose.replace(line, "")
    assert len(prose) <= 700, f"{stage}: stub prose is {len(prose)} chars"
    assert (loop_off / ".claude" / SHARED).is_file()


# AC-004
def _golden_rows() -> list[tuple[str, list[str]]]:
    doc = yaml.safe_load((REPO / "specs" / "SPEC-hm-light-lane-s2.machine.yaml").read_text())
    ac = next(a for a in doc["ac"] if a["id"] == "AC-004")
    return [(r["input"]["stage"], r["expected"]["lines"]) for r in ac["golden_table"]]


@pytest.fixture(scope="module")
def repo_render(tmp_path_factory: pytest.TempPathFactory) -> Path:
    sys.path.insert(0, str(REPO / "tests" / "structural"))
    from _surface_baseline import HARNESS_YAML, pinned_install_ref

    root = tmp_path_factory.mktemp("s2-repo")
    answers = answers_from_harness_yaml(HARNESS_YAML)
    assert answers is not None
    with pinned_install_ref():
        render(
            synthesize(ProjectProfile(), answers), root / ".claude", freeze_time=DEFAULT_FREEZE_TIME
        )
    return root


@pytest.mark.parametrize(("stage", "expected"), _golden_rows())
def test_executed_autopilot_lines_are_unchanged(
    loop_off: Path, stage: str, expected: list[str]
) -> None:
    body = _norm((loop_off / ".claude" / "commands" / "hm" / f"{stage}.md").read_text())
    assert _executed(_between(body, OPEN, CLOSE)) == expected


# AC-005
# Lines the stub rewrites rather than carries: the NO-OP lead (now one paragraph that also points
# at the file) and the Step 1 lead that holds the predicate (the stub names it on its own line).
ALLOWLIST = {
    "Before the STOP banner below, check whether this session runs under **autopilot** (live",
    "auto-advance, ADR-005) — **Claude-Code-only**: it needs the `.hm-autopilot` marker (armed",
    "by the picker) and the `Skill` tool. **This section is a NO-OP** — fall straight through",
    "to the STOP banner, running nothing below — **if any of: no `Skill` tool (Cursor/Codex),",
    "no active marker, or loop-mode is on for THIS session (a `.claude/.hm-loop-*` marker",
    "matches `$HM_SESSION_ID`, or a legacy `.hm-loop-active` exists).**",
    "*before* anything else: If any verification check FAILED, STOP.",
}


@pytest.mark.parametrize("stage", ["spec", "verify"])
def test_shared_procedure_keeps_every_instruction(loop_off: Path, stage: str) -> None:
    old = (FIXTURES / f"advance-e9b6198-{stage}.md").read_text()
    body = _norm((loop_off / ".claude" / "commands" / "hm" / f"{stage}.md").read_text())
    new_lines = {ln.strip() for ln in _between(body, OPEN, CLOSE).splitlines()}
    new_lines |= {ln.strip() for ln in (loop_off / ".claude" / SHARED).read_text().splitlines()}
    old_lines = {ln.strip() for ln in old.splitlines() if ln.strip()}
    old_lines -= {OPEN, CLOSE}
    if stage == "spec":
        old_lines = {ln for ln in old_lines if not ln.startswith("*before* anything else: Read")}
    missing = sorted(old_lines - {a.strip() for a in ALLOWLIST} - new_lines)
    assert not missing, f"{stage}: instructions lost from the auto-advance block: {missing}"


# AC-006
def test_gated_renders_no_autopilot_text(tmp_path: Path) -> None:
    root = _render(tmp_path, loop=False, level="gated")
    for stage in STAGES:
        body = (root / ".claude" / "commands" / "hm" / f"{stage}.md").read_text()
        for marker in (f".claude/{SHARED}", "autopilot_caps boundary", "@hm:autopilot-advance"):
            assert marker not in body, f"{stage}: {marker}"
    assert not (root / ".claude" / SHARED).exists()


# AC-007
@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
def test_dead_review_telemetry_is_gone(tmp_path: Path, preset: Preset) -> None:
    root = _render(tmp_path, loop=True, preset=preset)
    for name in ("review", "health"):
        body = (root / ".claude" / "commands" / "hm" / f"{name}.md").read_text()
        for marker in (
            "record_intent_miss",
            "silent_intent_miss_rate",
            "review_churn complexity",
            "Size & Complexity",
            "Step 2.5",
        ):
            assert marker not in body, f"{preset.value} {name}: {marker}"


# AC-008
def _phase_body(body: str, heading: str) -> list[str]:
    start = body.index(heading)
    rest = body[start + len(heading) :].split("\n", 1)[1]
    end = re.search(r"^#{2,4} ", rest, flags=re.M)
    chunk = rest[: end.start()] if end else rest
    return [ln for ln in chunk.splitlines() if ln.strip()]


def test_repair_phases_are_three_lines_or_fewer(loop_off: Path) -> None:
    body = (loop_off / ".claude" / "commands" / "hm" / "execute.md").read_text()
    for heading in ("#### Phase C.0", "#### Phase D.5"):
        lines = _phase_body(body, heading)
        assert 1 <= len(lines) <= 3, f"{heading}: {len(lines)} lines"
        assert "repair" in " ".join(lines).lower(), f"{heading} lost its repair trigger"


# AC-009
def _flagged(skills_dir: Path) -> set[str]:
    out = set()
    for p in skills_dir.glob("*/SKILL.md"):
        fm = yaml.safe_load(p.read_text().split("---", 2)[1])
        if fm.get("disable-model-invocation") is True:
            out.add(p.parent.name)
    return out


def test_typed_only_skill_flag_comes_from_the_list(loop_off: Path) -> None:
    assert _flagged(loop_off / ".claude" / "skills") == set(_TYPED_ONLY_SKILLS)
    assert set(_TYPED_ONLY_SKILLS) == TYPED_ONLY_AT_E9B6198
    assert _flagged(loop_off / ".agents" / "skills") == set()
    carriers = [
        p.relative_to(TEMPLATES).as_posix()
        for p in (TEMPLATES / "skills").rglob("*.j2")
        if "disable-model-invocation" in p.read_text()
    ]
    assert carriers == [], f"templates still carry the flag by hand: {carriers}"


# AC-010
# This repo's config rendered at e9b6198 under the pinned install ref, measured before the edit.
BASELINE_E9B6198 = 46_985 + 62_901 + 86_011 + 26_710


def test_the_four_stage_bodies_shrink(repo_render: Path) -> None:
    total = sum(
        len((repo_render / ".claude" / "commands" / "hm" / f"{s}.md").read_text())
        for s in ("spec", "execute", "review", "verify")
    )
    assert BASELINE_E9B6198 - total >= 20_000, f"shrank by {BASELINE_E9B6198 - total}"


# AC-011
def test_no_answers_path_keeps_gate0_beside_the_driver() -> None:
    from harness_maker.render import _make_env
    from harness_maker.synthesize import _atomic_command_files, _loop_enabled

    assert _loop_enabled(None), "the no-answers path renders the loop commands"
    bodies = {out: str(ctx.get("stage_body", "")) for _tpl, out, ctx in _atomic_command_files(None)}
    rendered = [b for b in bodies.values() if b]
    assert len(rendered) == len(STAGES)
    for body in rendered:
        assert "Gate 0 receipt" in body
    from harness_maker.synthesize import _codex_stage_skills

    codex = [str(ctx["stage_body"]) for _t, _o, ctx in _codex_stage_skills(config_dump=None)]
    assert codex
    assert all("Gate 0 receipt" in b for b in codex)
    env = _make_env()
    for flag in (True, False):
        dump = {"loop": {"enabled": flag}}
        assert _loop_enabled(dump) is flag
        tpl = env.from_string("{{ loop_enabled(config) }}")
        assert tpl.render(config=dump) == str(flag)
