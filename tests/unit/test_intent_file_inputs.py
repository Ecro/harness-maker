"""SPEC-intent-file-inputs AC-001..005, AC-007 — `hm intent` free text read from files.

The CLI is driven in-process through `intent_cli.main`, the same entry point `hm intent`
dispatches to. Every stored value is compared with the original text the test wrote, never with
the other form's output, so a normaliser shared by both forms cannot satisfy the oracle.

Phase A.4: `test_refused_inputs[neither-form]` passes before the change by construction — a
required `--note` was already refused when absent. It is a preservation guard: it goes red if
the new exclusive group stops requiring one form. Its RED siblings are the other five rows,
which need the file twins to exist before they can be refused for the right reason.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker import intent, intent_cli
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.spec_machine import GoldenRow, load_golden_table
from harness_maker.synthesize import synthesize
from tests.unit import world_fixture as fx
from tests.unit.test_intent_vocabulary import LEGACY

SPEC_YAML = Path(__file__).parents[2] / "specs" / "SPEC-intent-file-inputs.machine.yaml"
AT = "2026-09-01T00:00:00Z"
_LOCKS = re.compile(r"\.lock$")


# ── harness ──────────────────────────────────────────────────────────────────


def _run(root: Path, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = intent_cli.main(["--root", str(root), *argv])
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _ok(root: Path, *argv: str) -> str:
    rc, out, err = _run(root, *argv)
    assert rc == 0, (argv, out, err)
    return out


def _new_root(dest: Path) -> Path:
    fx.build_root(dest, intent=copy.deepcopy(LEGACY))
    _ok(dest, "migrate", "--json")
    return dest


def _with_question(root: Path) -> Path:
    _ok(root, "question", "add", "runtime", "--claim", "CPython", "--status", "open", "--json")
    return root


def _with_active_intent(root: Path) -> Path:
    _ok(root, "new", "W", "--title", "t", "--statement", "s", "--scope", "p", "--metric", "latency")
    _ok(root, "approve", "W", "--json")
    _ok(root, "activate", "W", "--json")
    return root


@cache
def _template(kind: str) -> Path:
    base = Path(tempfile.mkdtemp(prefix=f"hm-intent-file-{kind}-"))
    root = _new_root(base / "root")
    if kind == "question":
        _with_question(root)
    elif kind == "active":
        _with_active_intent(root)
    return root


def _fresh(kind: str, where: Path) -> Path:
    dest = where / "root"
    shutil.copytree(_template(kind), dest)
    return dest


def _question(root: Path, qid: str = "runtime") -> dict[str, Any]:
    questions = fx.load(root / ".claude/intent.yaml")["open_questions"]
    return next(q for q in questions if q["id"] == qid)


def _intent(root: Path, iid: str) -> dict[str, Any]:
    import json

    return dict(json.loads(_ok(root, "show", iid, "--json")))


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts and not _LOCKS.search(p.name)
    }


@dataclass(frozen=True)
class Case:
    """One single-valued argument: how to call it and where its value is stored."""

    flag: str
    template: str
    argv: Callable[[str], list[str]]
    stored: Callable[[Path], Any]


_NEW_BASE = ["--metric", "latency", "--json"]

CASES = {
    "question-add-claim": Case(
        "claim",
        "fresh",
        lambda v: ["question", "add", "q1", "{claim}", "--status", "open", "--json"],
        lambda r: _question(r, "q1")["claim"],
    ),
    "question-add-text": Case(
        "text",
        "fresh",
        lambda v: [
            "question",
            "add",
            "q1",
            "--claim",
            "c",
            "--status",
            "open",
            "{text}",
            "--observed-at",
            AT,
            "--json",
        ],
        lambda r: _question(r, "q1")["evidence"][-1]["text"],
    ),
    "question-observe-text": Case(
        "text",
        "question",
        lambda v: [
            "question",
            "observe",
            "runtime",
            "--relation",
            "confirms",
            "{text}",
            "--observed-at",
            AT,
            "--json",
        ],
        lambda r: _question(r)["evidence"][-1]["text"],
    ),
    "question-observe-claim": Case(
        "claim",
        "question",
        lambda v: [
            "question",
            "observe",
            "runtime",
            "--relation",
            "supersedes",
            "--text",
            "t",
            "--observed-at",
            AT,
            "{claim}",
            "--json",
        ],
        lambda r: _question(r)["claim"],
    ),
    "question-resolve-claim": Case(
        "claim",
        "question",
        lambda v: ["question", "resolve", "runtime", "--status", "confirmed", "{claim}", "--json"],
        lambda r: _question(r)["claim"],
    ),
    "metric-record-evidence": Case(
        "evidence",
        "fresh",
        lambda v: [
            "metric",
            "record",
            "latency",
            "--value",
            "8",
            "--observed-at",
            AT,
            "{evidence}",
            "--json",
        ],
        lambda r: fx.load(r / ".claude/intent/metrics.yaml")["values"][-1]["evidence"],
    ),
    "close-note": Case(
        "note",
        "active",
        lambda v: ["close", "W", "--observed", "met", "{note}", "--json"],
        lambda r: _intent(r, "W")["note"],
    ),
    "new-title": Case(
        "title",
        "fresh",
        lambda v: ["new", "N", "{title}", "--statement", "s", "--scope", "p", *_NEW_BASE],
        lambda r: _intent(r, "N")["title"],
    ),
    "new-statement": Case(
        "statement",
        "fresh",
        lambda v: ["new", "N", "--title", "t", "{statement}", "--scope", "p", *_NEW_BASE],
        lambda r: _intent(r, "N")["statement"],
    ),
}


def _fill(case: Case, inline: str | None = None, path: Path | None = None) -> list[str]:
    slot = "{" + case.flag + "}"
    out: list[str] = []
    for token in case.argv(""):
        if token != slot:
            out.append(token)
        elif path is not None:
            out += [f"--{case.flag}-file", str(path)]
        else:
            assert inline is not None
            out += [f"--{case.flag}", inline]
    return out


# ── AC-001 ───────────────────────────────────────────────────────────────────

_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="  "),
    min_size=1,
    max_size=40,
).flatmap(
    lambda head: st.lists(st.sampled_from(["", "\n"]), max_size=2).map(
        lambda seps: head + "".join(s + "x" for s in seps if s)
    )
)


@pytest.mark.parametrize("name", sorted(CASES))
@settings(
    max_examples=6,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    x=_TEXT.filter(lambda s: s == s.strip() and not s.endswith("\n")),
    newlines=st.integers(0, 2),
)
def test_file_equals_inline(name: str, x: str, newlines: int, tmp_path_factory: Any) -> None:
    case = CASES[name]
    kind = "fresh" if case.template == "fresh" else case.template
    via_inline = _fresh(kind, tmp_path_factory.mktemp("inline"))
    _ok(via_inline, *_fill(case, inline=x))
    via_file = _fresh(kind, tmp_path_factory.mktemp("file"))
    value_file = tmp_path_factory.mktemp("value") / "value.txt"
    value_file.write_text(x + "\n" * newlines, encoding="utf-8")
    _ok(via_file, *_fill(case, path=value_file))
    assert case.stored(via_inline) == x
    assert case.stored(via_file) == x


# ── AC-002 ───────────────────────────────────────────────────────────────────

PAYLOAD = 'it\'s "quoted" `tick` $(touch PWNED) and\nsecond line'


def test_metacharacters_verbatim(tmp_path: Path) -> None:
    root = _fresh("fresh", tmp_path)
    value = tmp_path / "claim.txt"
    value.write_text(PAYLOAD + "\n", encoding="utf-8")
    _ok(root, "question", "add", "q1", "--claim-file", str(value), "--status", "open", "--json")
    stored_value = _question(root, "q1")["claim"]
    assert stored_value == PAYLOAD


# ── AC-003 ───────────────────────────────────────────────────────────────────

_ROWS = load_golden_table(SPEC_YAML, "AC-003")


def _refusal_argv(note: str, tmp: Path) -> tuple[str, list[str]]:
    good = tmp / "good.txt"
    good.write_text("value\n", encoding="utf-8")
    if note == "both-forms-single":
        return "fresh", [
            "question",
            "add",
            "q1",
            "--claim",
            "c",
            "--claim-file",
            str(good),
            "--status",
            "open",
        ]
    if note == "both-forms-list":
        return "fresh", [
            "new",
            "N",
            "--title",
            "t",
            "--statement",
            "s",
            "--scope",
            "a",
            "--scope-file",
            str(good),
            "--metric",
            "latency",
        ]
    if note == "neither-form":
        return "active", ["close", "W", "--observed", "met"]
    if note == "missing-file":
        return "question", [
            "question",
            "observe",
            "runtime",
            "--relation",
            "confirms",
            "--text-file",
            str(tmp / "absent.txt"),
            "--observed-at",
            AT,
        ]
    if note == "non-utf8":
        bad = tmp / "bad.txt"
        bad.write_bytes(b"\xff\xfe\xfa")
        return "fresh", [
            "metric",
            "record",
            "latency",
            "--value",
            "8",
            "--observed-at",
            AT,
            "--evidence-file",
            str(bad),
        ]
    if note == "empty-value":
        empty = tmp / "empty.txt"
        empty.write_text("\n\n", encoding="utf-8")
        return "fresh", [
            "new",
            "N",
            "--title-file",
            str(empty),
            "--statement",
            "s",
            "--scope",
            "p",
            "--metric",
            "latency",
        ]
    raise AssertionError(note)


@pytest.mark.parametrize("row", _ROWS, ids=[r.note for r in _ROWS])
def test_refused_inputs(row: GoldenRow, tmp_path: Path) -> None:
    kind, argv = _refusal_argv(row.note, tmp_path)
    root = _fresh(kind, tmp_path)
    before = _snapshot(root)
    rc, _out, err = _run(root, *argv)
    expected = row.expected
    assert (rc != 0) is expected["exit_nonzero"]
    assert expected["message_contains"] in err
    # Refused by the new rule, not by argparse failing to know the flag at all.
    assert "unrecognized arguments" not in err
    # The row names the flag the refusal is about (the file twin for file rows).
    assert row.input["flag"] in err
    assert (_snapshot(root) == before) is expected["artefacts_unchanged"]


# ── AC-004 ───────────────────────────────────────────────────────────────────

_LIST_FLAGS = {"scope": "scope", "out-of-scope": "out_of_scope", "declined": "rejected"}


def _new_with_list(root: Path, flag: str, path: Path) -> tuple[int, str, str]:
    argv = ["new", "N", "--title", "t", "--statement", "s", "--metric", "latency"]
    if flag != "scope":
        argv += ["--scope", "p"]
    if flag == "declined":
        argv += ["--from-proposal", "--candidates", "3"]
    return _run(root, *argv, f"--{flag}-file", str(path))


def test_scope_file_lines(tmp_path: Path) -> None:
    parsed: dict[str, Any] = {}
    zero_item_refused: dict[str, bool] = {}
    for flag, field in _LIST_FLAGS.items():
        root = _fresh("fresh", tmp_path / flag)
        items = tmp_path / flag / "items.txt"
        items.write_text("  alpha item \n\nbeta item\n", encoding="utf-8")
        rc, _out, err = _new_with_list(root, flag, items)
        assert rc == 0, err
        key = flag.replace("-", "_")
        parsed[key] = _intent(root, "N")[field]
        empty_root = _fresh("fresh", tmp_path / f"{flag}-empty")
        blank = tmp_path / f"{flag}-empty" / "blank.txt"
        blank.write_text("\n   \n", encoding="utf-8")
        before = _snapshot(empty_root)
        rc_empty, _o, err_empty = _new_with_list(empty_root, flag, blank)
        zero_item_refused[key] = (
            rc_empty != 0 and f"--{flag}" in err_empty and _snapshot(empty_root) == before
        )
    # AC-004 predicate, one conjunct per assert.
    lists = ("scope", "out_of_scope", "declined")
    assert all(parsed[flag] == ["alpha item", "beta item"] for flag in lists), parsed
    assert all(zero_item_refused[flag] for flag in lists), zero_item_refused


# ── AC-007 ───────────────────────────────────────────────────────────────────

TITLE = "Inline title"
STATEMENT = "Statement from a file, it's fine"


def test_mixed_forms(tmp_path: Path) -> None:
    root = _fresh("fresh", tmp_path)
    statement_file = tmp_path / "statement.txt"
    statement_file.write_text(STATEMENT + "\n", encoding="utf-8")
    _ok(
        root,
        "new",
        "N",
        "--title",
        TITLE,
        "--statement-file",
        str(statement_file),
        "--scope",
        "p",
        "--metric",
        "latency",
        "--json",
    )
    shown = _intent(root, "N")
    record_title, record_statement = shown["title"], shown["statement"]
    assert record_title == TITLE
    assert record_statement == STATEMENT


@pytest.mark.parametrize(
    ("dest", "flag"), [(d, f) for d, _, f, multi in intent.FILE_TWINS if not multi]
)
@pytest.mark.parametrize("edge", [" ", "\t", "  \t "])
def test_file_value_keeps_boundary_whitespace(
    dest: str, flag: str, edge: str, tmp_path: Path
) -> None:
    """IRR-001 drops only trailing newlines: a `strip()` reader would pass the property above,
    whose stored values cannot carry boundary whitespace, but fails here."""
    value = f"{edge}body{edge}"
    path = tmp_path / "value.txt"
    path.write_text(value + "\n\n", encoding="utf-8")
    parser = argparse.ArgumentParser()
    args = argparse.Namespace(**{d: None for d, fd, _, _ in intent.FILE_TWINS})
    args.__dict__.update({fd: None for _, fd, _, _ in intent.FILE_TWINS})
    setattr(args, f"{dest}_file", str(path))
    intent.resolve_file_args(parser, args)
    assert getattr(args, dest) == value


def test_pair_refuses_a_twin_missing_from_the_table() -> None:
    with pytest.raises(ValueError, match="FILE_TWINS"):
        intent._pair(argparse.ArgumentParser(), "--unlisted", dest="unlisted", required=False)


# ── AC-005 ───────────────────────────────────────────────────────────────────

_WRITE_VERB = re.compile(r"hm intent (question (?:add|observe|resolve)|metric record|close|new)\b")
_COVERED_INLINE = re.compile(
    r"--(claim|text|note|evidence|title|statement|scope|out-of-scope|declined)(?![-\w])"
)
#: `spec` left this table with Step 4.9 (SPEC-intent-surface-diet AC-002): it no longer runs
#: `hm intent new`, so it has no free-text write recipe to check.
SURFACES = {
    Target.CLAUDE_CODE: {
        "wrapup": ".claude/commands/hm/wrapup.md",
        "intent-layer": ".claude/skills/intent-layer/SKILL.md",
    },
    Target.CODEX: {
        "wrapup": ".agents/skills/hm-wrapup/SKILL.md",
        "intent-layer": ".agents/skills/intent-layer/SKILL.md",
    },
}
#: Each call site, the `-file` flags its line must carry, in matching order: a site claims the
#: first unclaimed line of its surface and verb that carries every flag, so the synopsis `new`
#: and the proposal-path `new` must be two lines, and the more specific site goes first.
CALL_SITES: tuple[tuple[tuple[str, str, str], tuple[str, ...]], ...] = (
    (("wrapup", "question observe", "observe"), ("--text-file", "--claim-file")),
    (("wrapup", "question add", "add"), ("--claim-file", "--text-file")),
    (("wrapup", "close", "close"), ("--note-file",)),
    (("intent-layer", "question add", "synopsis"), ("--claim-file", "--text-file")),
    (("intent-layer", "question observe", "synopsis"), ("--text-file", "--claim-file")),
    (("intent-layer", "question resolve", "synopsis"), ("--claim-file",)),
    (("intent-layer", "metric record", "synopsis"), ("--evidence-file",)),
    (
        ("intent-layer", "new", "synopsis"),
        ("--title-file", "--statement-file", "--scope-file", "--out-of-scope-file"),
    ),
    # `[`: the declined file is optional — every candidate accepted leaves nothing to write,
    # and an empty file is refused.
    (("intent-layer", "new", "proposal"), ("--from-proposal", "[--declined-file")),
    (("intent-layer", "close", "synopsis"), ("--note-file",)),
)
EXPECTED_CALL_SITES = {key for key, _ in CALL_SITES}
#: Where the inline scan looks: the whole section, not only the call lines, so prose that
#: describes arguments (a preview the operator confirms) cannot name an inline form either.
_SCAN = {
    "wrapup": re.compile(r"#### 5\.7.*?(?=\n#{2,4} )", re.S),
    "intent-layer": re.compile(r".*", re.S),
}
_SECTION = {
    **_SCAN,
    "intent-layer": re.compile(r"## The rule for every write.*?(?=\n## )", re.S),
}


@cache
def _renders(target: Target) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(), InterviewAnswers(preset=Preset.PRODUCTION, targets=[target])
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        return {
            surface: (root / rel).read_text(encoding="utf-8")
            for surface, rel in SURFACES[target].items()
        }


def _write_lines(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), line) for line in text.splitlines() if (m := _WRITE_VERB.search(line))]


def present_call_sites(renders: dict[str, str]) -> set[tuple[str, str, str]]:
    lines = {surface: _write_lines(text) for surface, text in renders.items()}
    claimed: set[tuple[str, int]] = set()
    present = set()
    for (surface, verb, role), flags in CALL_SITES:
        for i, (found, line) in enumerate(lines.get(surface, [])):
            if (surface, i) in claimed or found != verb:
                continue
            if all(re.search(re.escape(f) + r"(?![-\w])", line) for f in flags):
                claimed.add((surface, i))
                present.add((surface, verb, role))
                break
    return present


def covered_inline_flags(renders: dict[str, str]) -> list[str]:
    return [
        line
        for surface, text in renders.items()
        if (m := _SCAN[surface].search(text))
        for line in m.group(0).splitlines()
        if _COVERED_INLINE.search(line)
    ]


def write_tool_mktemp_instruction(section: str) -> bool:
    return "mktemp" in section and "write tool" in section.lower()


@pytest.mark.parametrize("target", list(SURFACES), ids=["claude", "codex"])
def test_recipes_carry_no_inline_text(target: Target) -> None:
    renders = _renders(target)
    sections = {
        surface: (m.group(0) if (m := _SECTION[surface].search(text)) else "")
        for surface, text in renders.items()
    }
    assert present_call_sites(renders) >= EXPECTED_CALL_SITES, (
        EXPECTED_CALL_SITES - present_call_sites(renders)
    )
    assert not covered_inline_flags(renders), covered_inline_flags(renders)
    assert all(write_tool_mktemp_instruction(sections[s]) for s in SURFACES[target]), {
        s: write_tool_mktemp_instruction(sections[s]) for s in SURFACES[target]
    }
