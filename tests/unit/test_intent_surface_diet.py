"""SPEC-intent-surface-diet — AC-001…AC-009 over rendered stage prose, four arms.

Goldens (`tests/fixtures/intent_surface_diet/goldens.json`) are captured by `_write_goldens()`
from the UNMODIFIED templates before the first template edit and never regenerated (PLAN
ADR-003). Every predicate has a control: the same predicate on a mutated input must turn false.

Phase A.4 justification for tests that pass before the change: AC-003's verb/guard half and
AC-004 are preservation oracles against pre-change goldens — they go red the moment the
compression drops a guard phrase, a verb or a byte of the Understanding text. Their RED siblings
are AC-003's absent-table/evidence clauses (`test_ac003_*`, `test_ac008_*`), AC-001, AC-002,
AC-005, AC-006 and AC-009, which force the change into existence.
"""

from __future__ import annotations

import json
import re
import tempfile
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

ROOT = Path(__file__).parents[2]
GOLDENS = ROOT / "tests" / "fixtures" / "intent_surface_diet" / "goldens.json"
STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")
ARMS = [(p, h) for p in (Preset.PRODUCTION, Preset.SIDE) for h in ("claude", "codex")]
ARM_IDS = [f"{p.value}-{h}" for p, h in ARMS]

GUARD_PHRASES = (
    "each with its exact arguments",
    "`pending` rows",
    "previous attempt failed",
    "that bears on a metric",
    "`## Feedback`",
    "PLAN, SPEC and RESEARCH",
    "Read `hm intent status --json` once",
    "only the selected",
    "read status back",
    "`declined`",
    "`failed`",
    "do not retry",
    "ask nothing",
    "measure: false",
    "`how_measured`",
    "proposing a value from its `last`",
    "names this task's slug",
    "already has a `recorded` verdict row",
    "one single-choice question",
    "keep open",
    "withdrawal criterion met",
)
S33_CONTRACT = (
    "`[A-Z0-9-]+`",
    "do not run the command",
    "hm intent show <id> --json",
    "legacy `objective: <id>`",
    "reject conflicts",
    "**P2**",
    '`source: "main-loop"`',
    "`scope_drift`",
    "before Step 3.4 stamps ids",
    "`<id>: …`",
    "No halt",
    "`unverified_severe`",
    "outside `scope`",
    "inside `out_of_scope`",
    "`statement` unmet",
    "`file` = the PLAN",
    "never edit the record",
    "`intent: <id>`",
    "[intent] no intent link — skipping",
    "[intent] intent id malformed — skipping",
)
EVIDENCE_PHRASE = "from this task's PLAN, SPEC, REVIEW and diff"
ABSENT_TABLE_PHRASE = "creating the table when it is absent"
COLLECTION_PHRASES = ("stages only collect", "in every stage", "where it was observed")
CONSENT_TOKEN = {"claude": "`multiSelect: true`", "codex": "numbered list"}

_UNDERSTANDING_PATTERNS = (
    r"\*\*End the body with the `Understanding:` block\*\*.*?missing or malformed\.",
    r"\*\*Immediately before the stage summary banner, show the Understanding result\*\*"
    r".*?never present a block that did not land\.",
    r"Every ADR\s+carries a provenance line:.*?`\*\*Decided by:\*\* agent`\.",
)


# ── rendering helpers ───────────────────────────────────────────────────────────────────


@cache
def _root(preset: Preset) -> Path:
    root = Path(tempfile.mkdtemp(prefix=f"hm-surface-diet-{preset.value}-"))
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=preset,
                targets=[Target.CLAUDE_CODE, Target.CODEX],
                delegation=DelegationConfig(stages=["wrapup", "verify"]),
            ),
        ),
        root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return root


_SRC_RE = re.compile(r"uv run --with (\S+) hm")


def _normalized(text: str) -> str:
    """The install ref is the checkout's own path, so byte counts would vary by environment."""
    m = _SRC_RE.search(text)
    return text.replace(m.group(1), "<SRC>") if m else text


def _stage(preset: Preset, host: str, stage: str) -> str:
    rel = (
        f".claude/commands/hm/{stage}.md"
        if host == "claude"
        else f".agents/skills/hm-{stage}/SKILL.md"
    )
    return _normalized((_root(preset) / rel).read_text(encoding="utf-8"))


def _skill_files(preset: Preset, host: str) -> list[Path]:
    base = _root(preset) / (".claude" if host == "claude" else ".agents") / "skills/intent-layer"
    return [base / "SKILL.md", base / "references" / "workflow-feedback.md"]


def _block(text: str, name: str) -> str:
    m = re.search(rf"<!-- @hm:{re.escape(name)} -->.*?<!-- @hm:/{re.escape(name)} -->", text, re.S)
    return m.group(0) if m else ""


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^#+ {re.escape(heading)}.*?(?=^#{{2,4}} )", text, re.S | re.M)
    return m.group(0) if m else ""


def _execute_feedback_lines(text: str) -> str:
    m = re.search(r"Add a Feedback section.*?without rewriting prior dispositions\.", text, re.S)
    return m.group(0) if m else ""


def intent_verbs(text: str) -> set[str]:
    return set(re.findall(r"hm intent (question \w+|metric \w+|\w+)", text))


def understanding_extracts(texts: list[str]) -> list[str]:
    out: list[str] = []
    for text in texts:
        for pat in _UNDERSTANDING_PATTERNS:
            out += re.findall(pat, text, re.S)
    return out


def _arm_key(preset: Preset, host: str) -> str:
    return f"{preset.value}-{host}"


def _total_bytes(preset: Preset, host: str) -> int:
    total = sum(len(_stage(preset, host, s).encode()) for s in STAGES)
    reference = _skill_files(preset, host)[1].read_text(encoding="utf-8")
    return total + len(_normalized(reference).encode())


def _intent_block_bytes(preset: Preset, host: str) -> int:
    n = 0
    for s in STAGES:
        text = _stage(preset, host, s)
        for name in ("feedback-entry", "feedback-close"):
            n += len(_block(text, name).encode())
    spec = _stage(preset, host, "spec")
    n += len(_section(spec, "Step 0.5").encode()) + len(_section(spec, "Step 4.9").encode())
    n += len(_section(_stage(preset, host, "review"), "Step 3.3").encode())
    n += len(_section(_stage(preset, host, "wrapup"), "5.7").encode())
    n += len(_execute_feedback_lines(_stage(preset, host, "execute")).encode())
    return n


def _write_goldens() -> None:  # pragma: no cover — run once, before the first template edit
    data: dict[str, Any] = {}
    for preset, host in ARMS:
        s57 = _section(_stage(preset, host, "wrapup"), "5.7")
        s33 = _section(_stage(preset, host, "review"), "Step 3.3")
        missing = [g for g in GUARD_PHRASES if g not in s57]
        assert not missing, (preset, host, missing)
        extracts = understanding_extracts(
            [_stage(preset, host, "wrapup"), _stage(preset, host, "execute")]
        )
        assert len(extracts) == 3, (preset, host, len(extracts))
        assert all(extracts), (preset, host)
        data[_arm_key(preset, host)] = {
            "verbs_57": sorted(intent_verbs(s57)),
            "guards_57": list(GUARD_PHRASES),
            "s33_bytes": len(s33.encode()),
            "understanding": extracts,
            "total_bytes": _total_bytes(preset, host),
            "intent_block_bytes": _intent_block_bytes(preset, host),
        }
        assert data[_arm_key(preset, host)]["verbs_57"]
        assert data[_arm_key(preset, host)]["intent_block_bytes"] > 0
    GOLDENS.parent.mkdir(parents=True, exist_ok=True)
    GOLDENS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")


@cache
def _golden(preset: Preset, host: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLDENS.read_text("utf-8"))
    arm: dict[str, Any] = data[_arm_key(preset, host)]
    return arm


# ── predicates (each has a control below) ─────────────────────────────────────────────


def no_feedback_blocks(text: str) -> bool:
    return "@hm:feedback-entry" not in text and "@hm:feedback-close" not in text


COLLECTION_PROSE = re.compile(r"`pending` rows?\b|most downstream artifact|`## Feedback`")


def no_collection_prose(text: str, stage: str) -> bool:
    """Wrapup 5.7 legitimately carries these tokens; no other stage may collect rows."""
    return stage == "wrapup" or not COLLECTION_PROSE.search(text)


def execute_adds_no_feedback(execute: str) -> bool:
    return not re.search(r"Feedback (section|table)|## Feedback", execute, re.I)


SPEC_LINK_GATE = "no `active`/`proposed` intent"
SPEC_LINK_SKIP = "`[intent] no intent to link — skipping`"
STATUS = "hm intent status --json"
STATUS_CALL = {"claude": "!uv run", "codex": 'Bash("uv run'}


def spec_link_only(spec: str, host: str = "claude") -> bool:
    s05 = _section(spec, "Step 0.5")
    ask = s05.find("Which intent does this task serve?")
    gate = s05.find(SPEC_LINK_GATE)
    status_lines = [
        ln for ln in s05.splitlines() if STATUS in ln and ln.lstrip().startswith(STATUS_CALL[host])
    ]
    return (
        bool(status_lines)
        and 0 <= s05.find(STATUS) < gate
        and "Step 4.9" not in spec
        and "Draft an intent for this task?" not in spec
        and "rejected[]" not in spec
        and "revisits[" not in spec
        and 0 <= gate < ask
        and SPEC_LINK_SKIP in s05
        and '**"none"**' in s05
        and "`intent: <id>`" in s05
    )


# S3's conditions, checked by position (gate before the action it guards) — the pre-change
# guard golden only pins rule text, so an item offered unconditionally would still pass it.
S57_GATES = (
    ("`measure: true`", '"measure all"'),
    ("`measure: false`", "one verdict item"),
    ("`intent: <id>`", "Close intent"),
)


def gates_precede(s57: str) -> bool:
    return all(0 <= s57.find(gate) < s57.find(action) for gate, action in S57_GATES)


S57_RULES = (
    r"skip `recorded`/`declined`",
    r"re-offer a `failed` one once",
    r"fails again[^.;]{0,30}`declined`",
    r"the Step 1 read is the readback",
    r"a row taken from a SPEC or RESEARCH table in that table too",
)


def rules_hold(s57: str) -> bool:
    return all(re.search(r, s57) for r in S57_RULES)


def consent_ok(s57: str, host: str) -> bool:
    """One batch, in the target's own mechanism — and never the other target's."""
    if host == "claude":
        return CONSENT_TOKEN["claude"] in s57 and "AskUserQuestion" in s57
    return (
        CONSENT_TOKEN["codex"] in s57
        and "one reply" in s57
        and "multiSelect" not in s57
        and "AskUserQuestion" not in s57
    )


def s57_ok(s57: str, host: str, golden: dict[str, Any]) -> bool:
    return (
        intent_verbs(s57) >= set(golden["verbs_57"])
        and all(g in s57 for g in golden["guards_57"])
        and gates_precede(s57)
        and rules_hold(s57)
        and consent_ok(s57, host)
        and ABSENT_TABLE_PHRASE in s57
    )


def s33_ok(s33: str, golden_bytes: int) -> bool:
    return all(t in s33 for t in S33_CONTRACT) and len(s33.encode()) <= 0.6 * golden_bytes


PRESERVATION_PHRASE = "preserve existing IDs, paths, history and approvals"


def skill_no_collection(texts: list[str]) -> bool:
    return all(p not in t.lower() for t in texts for p in COLLECTION_PHRASES)


def skill_names_57_and_preserves(skill: str, reference: str) -> bool:
    return "Step 5.7" in skill and "Step 5.7" in reference and PRESERVATION_PHRASE in reference


# ── AC-001 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac001_no_feedback_blocks(preset: Preset, host: str, stage: str) -> None:
    text = _stage(preset, host, stage)
    assert no_feedback_blocks(text)
    assert no_collection_prose(text, stage)
    if stage == "execute":
        assert execute_adds_no_feedback(text)


def test_ac001_control() -> None:
    assert not no_feedback_blocks("x <!-- @hm:feedback-entry --> y")
    assert not no_feedback_blocks("x <!-- @hm:feedback-close --> y")
    assert not execute_adds_no_feedback("Append a Feedback section to the PLAN.")
    assert not execute_adds_no_feedback("Add a `## Feedback` table when the task serves an intent.")
    assert execute_adds_no_feedback("Write the PLAN with its nine sections.")
    # Unmarked collection prose must fail too — the marker is a rendering artifact.
    assert not no_collection_prose("append a `pending` row to the table", "review")
    assert not no_collection_prose("the most downstream artifact — PLAN, else SPEC", "spec")
    assert not no_collection_prose("add the `## Feedback` table", "research")
    assert no_collection_prose("offer any `pending` rows already present", "wrapup")


# ── AC-002 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac002_spec_link_only(preset: Preset, host: str) -> None:
    assert spec_link_only(_stage(preset, host, "spec"), host)


def test_ac002_control() -> None:
    good = (
        f"### Step 0.5 — Intent\n!uv run --with <SRC> {STATUS}\n"
        f"{SPEC_LINK_GATE} → print {SPEC_LINK_SKIP}.\n"
        'Otherwise ask **"Which intent does this task serve?"** plus '
        '**"none"** writes `intent: <id>`.\n### Step 1 — next\n'
    )
    assert spec_link_only(good)
    assert not spec_link_only(good + "### Step 4.9 — Intent draft\n")
    assert not spec_link_only(good + "compare each intent's `rejected[]` list\n")
    assert not spec_link_only(good.replace('**"none"**', "nothing"))
    assert not spec_link_only(good.replace(SPEC_LINK_GATE, "always"))
    assert not spec_link_only(good.replace(SPEC_LINK_SKIP, "nothing"))
    # The gate must precede the question: an unconditional ask with a trailing note fails.
    unconditional = good.replace(f"{SPEC_LINK_GATE} → print {SPEC_LINK_SKIP}.\n", "")
    assert not spec_link_only(
        unconditional.replace("### Step 1", f"{SPEC_LINK_GATE} {SPEC_LINK_SKIP}\n### Step 1")
    )
    # The status read is the data source of the pick: removed, moved after the gate, or in
    # the other target's call form, it fails.
    assert not spec_link_only(good.replace(f"!uv run --with <SRC> {STATUS}\n", ""))
    late = good.replace(f"!uv run --with <SRC> {STATUS}\n", "").replace(
        "### Step 1", f"!uv run --with <SRC> {STATUS}\n### Step 1"
    )
    assert not spec_link_only(late)
    assert not spec_link_only(good, "codex")


# ── AC-003 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac003_wrapup_57_guards_and_consent(preset: Preset, host: str) -> None:
    s57 = _section(_stage(preset, host, "wrapup"), "5.7")
    assert s57
    assert s57_ok(s57, host, _golden(preset, host))


def test_ac003_control() -> None:
    golden = _golden(Preset.PRODUCTION, "claude")
    s57 = _section(_stage(Preset.PRODUCTION, "claude", "wrapup"), "5.7")
    for g in golden["guards_57"]:
        if g in s57:
            assert not s57_ok(s57.replace(g, ""), "claude", golden), g
    assert not s57_ok(s57.replace("hm intent metric record", "hm x"), "claude", golden)
    assert not s57_ok(s57.replace(CONSENT_TOKEN["claude"], ""), "claude", golden)
    for rule in S57_RULES:
        assert rules_hold(s57), rule
        assert not s57_ok(re.sub(rule, "", s57), "claude", golden), rule


def test_ac003_consent_controls() -> None:
    for preset in (Preset.PRODUCTION, Preset.SIDE):
        codex = _section(_stage(preset, "codex", "wrapup"), "5.7")
        claude = _section(_stage(preset, "claude", "wrapup"), "5.7")
        assert consent_ok(codex, "codex")
        assert consent_ok(claude, "claude")
        # A unified prose that also carries the Claude mechanism must fail on Codex.
        assert not consent_ok(codex + " `multiSelect: true`", "codex")
        assert not consent_ok(codex + " AskUserQuestion", "codex")
        assert not consent_ok(codex.replace("one reply", "a reply"), "codex")
        assert not consent_ok(claude.replace(CONSENT_TOKEN["claude"], ""), "claude")


def test_ac003_gates_hold_on_the_pre_change_render() -> None:
    """The gates are today's text: the preservation half must hold before any edit."""
    for preset, host in ARMS:
        assert gates_precede(_section(_stage(preset, host, "wrapup"), "5.7")), (preset, host)


@pytest.mark.parametrize(("gate", "action"), S57_GATES, ids=["measure-all", "verdict", "close"])
def test_ac003_gate_controls(gate: str, action: str) -> None:
    s57 = _section(_stage(Preset.PRODUCTION, "claude", "wrapup"), "5.7")
    assert gates_precede(s57)
    # Gate deleted → the item is offered unconditionally.
    assert not gates_precede(s57.replace(gate, ""))
    # Gate moved after its action → still unconditional at the point of offer.
    moved = s57.replace(gate, "", 1)
    i = moved.find(action) + len(action)
    assert not gates_precede(moved[:i] + " " + gate + moved[i:])


# ── AC-004 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac004_understanding_byte_identical(preset: Preset, host: str) -> None:
    golden = _golden(preset, host)["understanding"]
    assert len(golden) == 3
    assert all(golden)
    got = understanding_extracts([_stage(preset, host, "wrapup"), _stage(preset, host, "execute")])
    assert got == golden


def test_ac004_control() -> None:
    golden = _golden(Preset.PRODUCTION, "claude")["understanding"]
    mutated = [golden[0].replace("Understanding", "Understandin", 1), *golden[1:]]
    assert understanding_extracts(mutated) != golden


# ── AC-005 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac005_review_33_contract_and_size(preset: Preset, host: str) -> None:
    s33 = _section(_stage(preset, host, "review"), "Step 3.3")
    assert s33
    assert s33_ok(s33, _golden(preset, host)["s33_bytes"])


def test_ac005_control() -> None:
    small = " ".join(S33_CONTRACT)
    assert not s33_ok(small, len(small.encode()))  # over 60% of its own size
    # Every contract token is load-bearing on the real render, for both hosts.
    for host in ("claude", "codex"):
        s33 = _section(_stage(Preset.PRODUCTION, host, "review"), "Step 3.3")
        for tok in S33_CONTRACT:
            assert tok in s33, (host, tok)
            assert not s33_ok(s33.replace(tok, ""), 10**9), (host, tok)


# ── AC-006 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac006_whole_render_shrink_per_target(preset: Preset, host: str) -> None:
    golden = _golden(preset, host)
    saved = golden["total_bytes"] - _total_bytes(preset, host)
    assert saved >= 0.5 * golden["intent_block_bytes"], (saved, golden["intent_block_bytes"])


# ── AC-008 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac008_57_derives_from_evidence(preset: Preset, host: str) -> None:
    assert EVIDENCE_PHRASE in _section(_stage(preset, host, "wrapup"), "5.7")


# ── AC-009 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac009_skill_no_stage_collection(preset: Preset, host: str) -> None:
    files = _skill_files(preset, host)
    assert all(f.is_file() for f in files)
    skill, reference = (f.read_text(encoding="utf-8") for f in files)
    assert skill_no_collection([skill, reference])
    assert skill_names_57_and_preserves(skill, reference)


def test_ac009_control() -> None:
    assert not skill_no_collection(["Workflow stages only collect `pending` rows"])
    assert not skill_no_collection(["Stages Only Collect pending rows"])
    assert not skill_no_collection(["in every stage, an observation becomes a row"])
    assert skill_no_collection(["wrapup Step 5.7 proposes observations once"])
    ref = f"wrapup Step 5.7 is the one moment; {PRESERVATION_PHRASE}."
    assert skill_names_57_and_preserves("see Step 5.7", ref)
    assert not skill_names_57_and_preserves("see wrapup", ref)
    assert not skill_names_57_and_preserves("see Step 5.7", ref.replace(PRESERVATION_PHRASE, ""))
    assert not skill_names_57_and_preserves("see Step 5.7", ref.replace("Step 5.7", "wrapup"))
