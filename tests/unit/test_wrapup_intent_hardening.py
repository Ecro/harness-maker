"""SPEC-wrapup-intent-hardening — AC-001…AC-005 over the rendered wrapup 5.7, four arms.

Goldens (`tests/fixtures/wrapup_intent_hardening/goldens.json`) are captured by `_write_goldens()`
from the unmodified templates at f57cef3b before the first template edit and never regenerated
(PLAN ADR-001), under the unit conftest's install-ref pin (`$HOME/harness-maker`) — a capture
without that pin hashes a different install ref. Every predicate has a control: the same
predicate on a mutated input turns false.

Phase A.4 justification: AC-005 (`test_ac005_render_outside_57_unchanged`) and the inventory
half of AC-002 (`test_ac002_inventory_kept`) pass before the change. They are preservation
oracles against the pre-change goldens and go red the moment the edit touches text outside 5.7
or drops a placeholder. Their RED siblings are AC-001, AC-002's format half, AC-003 and AC-004,
which force the change into existence. `test_ac005_control` also passes before the change: it
checks the oracle (a one-heading edit outside 5.7 changes the hash), not the template.
"""

from __future__ import annotations

import hashlib
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
GOLDENS = ROOT / "tests" / "fixtures" / "wrapup_intent_hardening" / "goldens.json"
ARMS = [(p, h) for p in (Preset.PRODUCTION, Preset.SIDE) for h in ("claude", "codex")]
ARM_IDS = [f"{p.value}-{h}" for p, h in ARMS]

SOURCE_ROW_PHRASE = "in its own table as well as in the PLAN table"
OLD_PHRASE = "in that table too"
MALFORMED_LINE = "[intent] malformed <argument> — skipped <item>"
CLOSE_SKIP_LINE = "[intent] intent id malformed — skipping close"
WHOLE_VALUE = "whole value"
INTENT_ID = "`[A-Z0-9][A-Z0-9-]*`"
SNAKE_ID = "`[a-z0-9_]+`"
VALUE_PAT = r"`-?[0-9]+(\.[0-9]+)?`"
LOCATOR_PAT = "`[A-Za-z0-9._/][A-Za-z0-9._/-]*:[0-9]+-[0-9]+`"
FORMAT_PATTERNS = (INTENT_ID, SNAKE_ID, VALUE_PAT, LOCATOR_PAT)
MALFORMED_WORDS = ("run nothing", "continue", "never its value", "item's kind")
# S2's two state transitions, each tied to its own trigger (step 5 also marks rows elsewhere).
FAILED_REASON_RE = re.compile(r"`failed`[^.]{0,60}malformed <argument>")
# The malformed failure defers to the single re-offer rule rather than restating it.
REOFFER_POINTER_RE = re.compile(r"malformed <argument>`[^.]{0,40}re-offer rule")
REOFFER_RULE = "a re-offered row that fails again becomes `declined`"
MALFORMED_REASON = "malformed <argument>"
ENUM_RULE = "only the values listed"
EDIT_TOKEN = {"claude": "Other edits", "codex": "edits travel in the same reply"}
EDIT_CLAUSE = {
    "claude": "after any edit made through Other",
    "codex": "after any edit made in the reply",
}

# SPEC S3 argument boundary: every <placeholder> on an `hm intent` line except --*-file values.
# The rule each one must carry comes from the CLI's own regexes (intent.py:45, world.py:75) and
# the enum lists on the command line, never from the prose under test (PLAN ADR-002).
RULE_FOR = {
    ("question observe", "<id>"): SNAKE_ID,
    ("question add", "<id>"): SNAKE_ID,
    ("metric record", "<metric-id>"): SNAKE_ID,
    ("close", "<id>"): INTENT_ID,
    ("--value", "<value>"): VALUE_PAT,
    ("--locator", "<path:A-B>"): LOCATOR_PAT,
    ("--relation", "<confirms|supersedes|contradicts>"): ENUM_RULE,
    ("--status", "<open|confirmed|wrong>"): ENUM_RULE,
    ("--observed", "<met|missed|no_data>"): ENUM_RULE,
}
# The name each argument goes by in the rule prose (SPEC S3 wording).
NAME_FOR = {
    ("question observe", "<id>"): "question id",
    ("question add", "<id>"): "question id",
    ("metric record", "<metric-id>"): "metric id",
    ("close", "<id>"): "intent id",
    ("--value", "<value>"): "`--value`",
    ("--locator", "<path:A-B>"): "`--locator`",
    ("--relation", "<confirms|supersedes|contradicts>"): "`--relation`",
    ("--status", "<open|confirmed|wrong>"): "`--status`",
    ("--observed", "<met|missed|no_data>"): "`--observed`",
}


# ── rendering helpers ───────────────────────────────────────────────────────────────────


@cache
def _root(preset: Preset) -> Path:
    root = Path(tempfile.mkdtemp(prefix=f"hm-wrapup-hardening-{preset.value}-"))
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
    """The install ref is the checkout's own path, so goldens would vary by environment."""
    m = _SRC_RE.search(text)
    return text.replace(m.group(1), "<SRC>") if m else text


def _wrapup(preset: Preset, host: str) -> str:
    rel = (
        ".claude/commands/hm/wrapup.md" if host == "claude" else ".agents/skills/hm-wrapup/SKILL.md"
    )
    return _normalized((_root(preset) / rel).read_text(encoding="utf-8"))


_S57_RE = re.compile(r"^#### 5\.7 .*?(?=^### Steps 6)", re.S | re.M)


def section_57(text: str) -> str:
    """5.7 through the Withdrawal line — the record batch and the close block both live here."""
    m = _S57_RE.search(text)
    return m.group(0) if m else ""


_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)


def strip_57(text: str) -> str:
    """Frontmatter goes too: its `content_hash` covers the whole body, 5.7 included."""
    return _S57_RE.sub("", _FRONTMATTER_RE.sub("", text, count=1), count=1)


def step(s57: str, n: int) -> str:
    m = re.search(rf"^{n}\. .*?(?=^\d\. |^<!-- /@hm|\Z)", s57, re.S | re.M)
    return m.group(0) if m else ""


def close_block(s57: str) -> str:
    m = re.search(r"<!-- @hm:answer-gated:intent-close -->.*?<!-- /@hm:answer-gated -->", s57, re.S)
    return m.group(0) if m else ""


def sentence_with(phrase: str, text: str) -> str:
    """Sentences end at `. ` + uppercase or end of text; `\\.[` inside a pattern never splits."""
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z`*\[])", text):
        if phrase in sentence:
            return sentence
    return ""


_FLAG_RE = re.compile(r"(--[a-z-]+) (<[^<>]+>)")
_POS_RE = re.compile(r"hm intent (question observe|question add|metric record|close) (<[^<>]+>)")


def placeholders(s57: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for line in s57.splitlines():
        if "hm intent" not in line:
            continue
        out |= set(_POS_RE.findall(line))
        flags = _FLAG_RE.findall(line)
        out |= {(f, p) for f, p in flags if not f.endswith("-file") and f != "--with"}
    return out


def _arm_key(preset: Preset, host: str) -> str:
    return f"{preset.value}-{host}"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _write_goldens() -> None:  # pragma: no cover — run once, before the first template edit
    data: dict[str, Any] = {}
    for preset, host in ARMS:
        text = _wrapup(preset, host)
        s57 = section_57(text)
        assert s57, (preset, host)
        assert close_block(s57), (preset, host)
        inv = sorted(placeholders(s57))
        assert len(inv) >= 8, (preset, host, inv)
        data[_arm_key(preset, host)] = {
            "outside_57_sha256": _sha(strip_57(text)),
            "placeholders": inv,
        }
    GOLDENS.parent.mkdir(parents=True, exist_ok=True)
    GOLDENS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")


@cache
def _golden(preset: Preset, host: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLDENS.read_text("utf-8"))
    arm: dict[str, Any] = data[_arm_key(preset, host)]
    return arm


def _golden_placeholders(preset: Preset, host: str) -> set[tuple[str, str]]:
    return {(a, b) for a, b in _golden(preset, host)["placeholders"]}


# ── predicates (each has a control below) ─────────────────────────────────────────────


def source_rows_ok(s57: str) -> bool:
    """The three outcomes sit in the clause right after the phrase, not elsewhere in step 5."""
    five = step(s57, 5)
    at = five.find(SOURCE_ROW_PHRASE)
    window = (
        five[at + len(SOURCE_ROW_PHRASE) : at + len(SOURCE_ROW_PHRASE) + 60] if at != -1 else ""
    )
    return (
        bool(window)
        and all(w in window for w in ("`recorded`", "`failed`", "`declined`"))
        and OLD_PHRASE not in s57
    )


_RULE_TOKENS = (*FORMAT_PATTERNS, ENUM_RULE)


def bound(s57: str, name: str, rule: str) -> bool:
    """Some mention of `name` is followed by `rule` before any other rule token — the binding."""
    for m in re.finditer(re.escape(name), s57):
        rest = s57[m.end() :]
        hits = [(rest.find(t), t) for t in _RULE_TOKENS if rest.find(t) != -1]
        if hits and min(hits)[1] == rule:
            return True
    return False


def formats_ok(s57: str) -> bool:
    """Whole-value check stated, and every placeholder's name is bound to its own rule."""
    if WHOLE_VALUE not in s57:
        return False
    keys = placeholders(s57)
    return all(k in RULE_FOR and bound(s57, NAME_FOR[k], RULE_FOR[k]) for k in keys)


def malformed_ok(s57: str, host: str) -> bool:
    five = step(s57, 5)
    if MALFORMED_LINE not in five or not all(w in five for w in MALFORMED_WORDS):
        return False
    if not FAILED_REASON_RE.search(five) or not REOFFER_POINTER_RE.search(five):
        return False
    if REOFFER_RULE not in five or EDIT_CLAUSE[host] not in five:
        return False
    base = s57.find(five)
    edit_at = base + five.find(EDIT_CLAUSE[host])
    if s57.find(EDIT_TOKEN[host]) == -1 or s57.find(EDIT_TOKEN[host]) > base:
        return False
    check_at = base + five.find(WHOLE_VALUE) if WHOLE_VALUE in five else -1
    run_at = base + five.lower().find("run only the selected")
    return -1 < edit_at < check_at < run_at and "run only the selected" in five.lower()


def close_ok(s57: str) -> bool:
    block = close_block(s57)
    return (
        CLOSE_SKIP_LINE in block
        and INTENT_ID in block
        and WHOLE_VALUE in block
        and "ask nothing" in block[block.find(CLOSE_SKIP_LINE) : block.find("Close intent")]
        and "otherwise" in block[block.find(CLOSE_SKIP_LINE) : block.find("Close intent")].lower()
        and block.find(CLOSE_SKIP_LINE) < block.find("Close intent")
    )


# ── tests ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac001_source_rows_marked_in_own_table(preset: Preset, host: str) -> None:
    assert source_rows_ok(section_57(_wrapup(preset, host)))


def test_ac001_control() -> None:
    s57 = section_57(_wrapup(Preset.PRODUCTION, "claude"))
    assert source_rows_ok(s57)
    assert not source_rows_ok(s57.replace(SOURCE_ROW_PHRASE, "in the PLAN table"))
    five = step(s57, 5)
    at = five.find(SOURCE_ROW_PHRASE) + len(SOURCE_ROW_PHRASE)
    # Delete only the clause after the phrase; the generic tail of the sentence stays.
    clause_gone = five[:at] + five[at + 60 :]
    assert "`declined`" in clause_gone
    assert not source_rows_ok(s57.replace(five, clause_gone))
    assert not source_rows_ok(s57 + "\n" + OLD_PHRASE)


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac002_every_arg_has_a_format(preset: Preset, host: str) -> None:
    assert formats_ok(section_57(_wrapup(preset, host)))


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac002_inventory_kept(preset: Preset, host: str) -> None:
    assert _golden_placeholders(preset, host) <= placeholders(section_57(_wrapup(preset, host)))


def test_ac002_control() -> None:
    s57 = section_57(_wrapup(Preset.PRODUCTION, "claude"))
    assert formats_ok(s57)
    for pat in (*_RULE_TOKENS, WHOLE_VALUE):
        assert not formats_ok(s57.replace(pat, "")), pat
    # Mis-binding: swap the two id patterns → each name now meets the other's rule first.
    swapped = s57.replace(INTENT_ID, "@@").replace(SNAKE_ID, INTENT_ID).replace("@@", SNAKE_ID)
    assert not formats_ok(swapped)
    unruled = s57.replace(
        "hm intent metric measure --all", "hm intent metric measure --all --tag <tag>"
    )
    assert not formats_ok(unruled)
    golden = _golden_placeholders(Preset.PRODUCTION, "claude")
    assert not golden <= placeholders(s57.replace(" [--locator <path:A-B>]", ""))


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac003_malformed_skips_item(preset: Preset, host: str) -> None:
    assert malformed_ok(section_57(_wrapup(preset, host)), host)


@pytest.mark.parametrize("word", [*MALFORMED_WORDS, MALFORMED_LINE])
def test_ac003_control(word: str) -> None:
    s57 = section_57(_wrapup(Preset.PRODUCTION, "claude"))
    assert malformed_ok(s57, "claude")
    five = step(s57, 5)
    assert not malformed_ok(s57.replace(five, five.replace(word, "")), "claude")


def test_ac003_reason_control() -> None:
    s57 = section_57(_wrapup(Preset.PRODUCTION, "claude"))
    assert malformed_ok(s57, "claude")
    five = step(s57, 5)
    without_reason = five.replace(MALFORMED_LINE, "@@").replace(MALFORMED_REASON, "an error")
    restored = without_reason.replace("@@", MALFORMED_LINE)
    assert not malformed_ok(s57.replace(five, restored), "claude")
    assert not malformed_ok(s57.replace(five, five.replace(REOFFER_RULE, "")), "claude")
    assert not malformed_ok(s57.replace(five, five.replace("re-offer rule", "rule")), "claude")


def test_ac003_order_control() -> None:
    s57 = section_57(_wrapup(Preset.PRODUCTION, "codex"))
    assert malformed_ok(s57, "codex")
    assert not malformed_ok(s57.replace(MALFORMED_LINE, "[intent] skipped"), "codex")
    # The run instruction moved ahead of the whole-value check inside step 5 → order broken.
    five = step(s57, 5)
    early = s57.replace(five, five.replace("5. ", "5. Run only the selected writes. ", 1))
    assert not malformed_ok(early, "codex")
    # The post-edit timing dropped from the check → fails.
    assert not malformed_ok(s57.replace(five, five.replace(EDIT_CLAUSE["codex"], "")), "codex")
    # The check stated before the edit clause → order broken.
    swapped = five.replace(EDIT_CLAUSE["codex"], "@@").replace(WHOLE_VALUE, EDIT_CLAUSE["codex"], 1)
    assert not malformed_ok(s57.replace(five, swapped.replace("@@", WHOLE_VALUE)), "codex")


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac004_close_rejects_malformed_id(preset: Preset, host: str) -> None:
    assert close_ok(section_57(_wrapup(preset, host)))


def test_ac004_control() -> None:
    s57 = section_57(_wrapup(Preset.SIDE, "claude"))
    assert close_ok(s57)
    assert not close_ok(s57.replace(CLOSE_SKIP_LINE, ""))
    block0 = close_block(s57)
    assert not close_ok(s57.replace(block0, block0.replace(WHOLE_VALUE, "value")))
    assert not close_ok(s57.replace(block0, block0.replace("ask nothing", "continue")))
    asks_anyway = block0.replace("ask nothing; otherwise ask", "then ask")
    assert asks_anyway != block0
    assert not close_ok(s57.replace(block0, asks_anyway))
    block = close_block(s57)
    late = block.replace(CLOSE_SKIP_LINE, "").replace(
        "<!-- /@hm:answer-gated -->", CLOSE_SKIP_LINE + "\n<!-- /@hm:answer-gated -->"
    )
    assert not close_ok(s57.replace(block, late))


@pytest.mark.parametrize(("preset", "host"), ARMS, ids=ARM_IDS)
def test_ac005_render_outside_57_unchanged(preset: Preset, host: str) -> None:
    assert _sha(strip_57(_wrapup(preset, host))) == _golden(preset, host)["outside_57_sha256"]


def test_ac005_control() -> None:
    text = _wrapup(Preset.PRODUCTION, "claude")
    golden = _golden(Preset.PRODUCTION, "claude")["outside_57_sha256"]
    edited = text.replace("### Step 4 — PLAN status update", "### Step 4 — PLAN")
    assert edited != text
    assert _sha(strip_57(edited)) != golden
    # A 5.7-only edit, with the frontmatter hash it would move, leaves the oracle unchanged.
    s57 = section_57(text)
    inside = text.replace(s57, s57 + "extra\n").replace("content_hash:", "content_hash: x", 1)
    assert _sha(strip_57(inside)) == _sha(strip_57(text))
