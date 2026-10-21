"""Fixture builder for SPEC-hm-light-lane-s3c, shared by the a7403f2f capture and the new tests.

One builder for both sides is the precondition of every differential in that SPEC: the
a7403f2f output and the new output are produced by the same code from the same inputs, so
only the `harness_maker` tree under test differs. It therefore uses only APIs that exist at
a7403f2f, and `tests/fixtures/light_lane_s3c/capture_a7403f2f.py.txt` runs it against an export
of that tree.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any

import yaml

GOLDENS = Path(__file__).resolve().parents[1] / "fixtures" / "light_lane_s3c"
CHECK_FIXTURES_DIR = GOLDENS / "check"
SOURCE_SHA = "a7403f2f"

STAGES = ("research", "spec", "execute", "review", "verify", "wrapup")
CLAUDE_COMMANDS = tuple(f"commands/hm/{s}.md" for s in STAGES)
CODEX_SKILLS = tuple(f"skills/hm-{s}" for s in STAGES)
#: The `.claude/hm/` reference files that exist at a7403f2f (autopilot-advance only when armed).
A7403F2F_REFS = (
    "hm/autopilot-advance.md",
    "hm/execute-a5.md",
    "hm/execute-light-check.md",
    "hm/review-autofix.md",
    "hm/review-confirmation.md",
    "hm/verify-checks.md",
    "hm/wrapup-steps.md",
)
NEW_REFS = ("hm/stage-preamble.md", "hm/execute-plan.md", "hm/spec-machine-full.md")
VBC_SKILLS = ("skills/verify-before-completion", "agents-skills/verify-before-completion")
DOCS = ("CLAUDE.md", "AGENTS.md")
RENDERED_PATHS = (
    *CLAUDE_COMMANDS,
    "commands/hm/loop.md",
    *A7403F2F_REFS,
    *NEW_REFS,
    *CODEX_SKILLS,
    *VBC_SKILLS,
    *DOCS,
)

LEVELS = ("gated", "auto_safe", "auto_full", "ask")


def a_key(level: str, wt: bool, locale: str) -> str:
    return f"{level}/wt-{'on' if wt else 'off'}/{locale}"


def full_key(preset: str, wt: bool, strictness: str, loop: bool) -> str:
    return f"{preset}/wt-{'on' if wt else 'off'}/{strictness}/loop-{'on' if loop else 'off'}"


#: S1/S2/S3/S7/S8/S12's config arms: autonomy x worktree x locale.
A_CONFIGS: dict[str, tuple[str, bool, str]] = {
    a_key(*c): c for c in product(LEVELS, (True, False), ("en", "ko"))
}
#: S13's full-lane arms: preset x worktree x strictness x loop.
FULL_CONFIGS: dict[str, tuple[str, bool, str, bool]] = {
    full_key(*c): c
    for c in product(("Side", "Production"), (True, False), ("warn", "block"), (False, True))
}


def _answers(update: Callable[[Any], dict[str, Any]]) -> Any:
    from harness_maker.interview import answers_from_harness_yaml
    from tests.structural._surface_baseline import HARNESS_YAML

    base = answers_from_harness_yaml(HARNESS_YAML)
    assert base is not None
    return base.model_copy(update=update(base))


def a_answers(key: str) -> Any:
    level, wt, locale = A_CONFIGS[key]
    return _answers(
        lambda b: {
            "autonomy": b.autonomy.model_copy(update={"level": level}),
            "worktree": {**b.worktree, "enabled": wt},
            "locale": locale,
        }
    )


def full_answers(key: str) -> Any:
    from harness_maker.models import LoopConfig, Preset

    preset, wt, strictness, loop = FULL_CONFIGS[key]
    return _answers(
        lambda b: {
            "preset": Preset(preset),
            "worktree": {**b.worktree, "enabled": wt},
            "strictness": strictness,
            "loop": LoopConfig(enabled=loop),
        }
    )


def render_files(answers: Any) -> dict[str, str | None]:
    """Render `answers` in-process (install ref pinned, clock frozen); return RENDERED_PATHS."""
    from harness_maker.models import ProjectProfile
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize
    from tests.structural._surface_baseline import pinned_install_ref

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pinned_install_ref():
            render(
                synthesize(ProjectProfile(), answers),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        out: dict[str, str | None] = {}
        for rel in RENDERED_PATHS:
            if rel.startswith("skills/hm-") or rel.startswith("agents-skills/"):
                p = root / ".agents" / "skills" / rel.split("/", 1)[1] / "SKILL.md"
            elif rel.startswith("skills/"):
                p = root / ".claude" / rel / "SKILL.md"
            elif rel in DOCS:
                p = root / rel
            else:
                p = root / ".claude" / rel
            out[rel] = p.read_text(encoding="utf-8") if p.is_file() else None
        return out


# ── slicers (identical on both trees) ─────────────────────────────────────────

REF_START, REF_END = "<!-- @hm:ref:start -->\n", "<!-- @hm:ref:end -->"
STAGE_HEADING = re.compile(r"^# Stage:", re.M)
STEP0_HEADING = "### Step 0 — Author the PLAN\n\n"
STEP01_HEADING = "#### Step 0.1 — SPEC-need fields"
STEP03_HEADING = "#### Step 0.3 — Verify the PLAN write\n\n"
STEP1_HEADING = "### Step 1 — Load PLAN + flag parsing"
PART1_START = "**Required frontmatter**"
STEP35_HEADING = "### Step 3.5 — Write SPEC.machine.yaml (ADR-006 dual-file)"
STEP4_HEADING = "### Step 4 + 4.5 — Verify write, cross-validate, and score, in ONE call"
STEP45_HEADING = "### Step 4.5 — "
LANG_START = "> **Output language.**"
LANG_END = "<!-- @hm:output_language -->"


_CONTENT_HASH = re.compile(r"^content_hash: [0-9a-f]+$", re.M)


def mask_content_hash(text: str) -> str:
    """The frontmatter hash of a file's own body: it moves with any byte, so S13 masks it."""
    return _CONTENT_HASH.sub("content_hash: <MASKED>", text)


def frontmatter_end(text: str) -> int:
    assert text.startswith("---\n"), text[:40]
    return text.index("\n---\n", 4) + len("\n---\n")


def preamble_span(text: str) -> str:
    """Everything between the frontmatter and the `# Stage:` heading."""
    m = STAGE_HEADING.search(text)
    assert m is not None
    return text[frontmatter_end(text) : m.start()]


def ref_slice(text: str) -> str:
    i = text.index(REF_START) + len(REF_START)
    return text[i : text.index(REF_END, i)]


def restore_preamble(command: str, preamble_file: str) -> str:
    """A Claude stage command with its preamble pointer replaced by the text it points at.

    The inverse of ADR-001's move: the span between the frontmatter and `# Stage:` becomes the
    `stage-preamble.md` slice again, which is the whole a7403f2f span (AC-002). The frontmatter's
    `content_hash` is left as rendered; callers that compare bytes mask or strip it.
    """
    fm = frontmatter_end(command)
    return command[:fm] + ref_slice(preamble_file) + command[fm + len(preamble_span(command)) :]


# ── C: the execute delta, undone (AC-016, and the older byte-identity goldens) ──
#: Exact strings written in the SPEC's Outcomes C (as amended 2026-10-15, review round 1). The
#: routing sentence depends on whether the loop renders: with it, `loop-mode-active` decides.
ROUTING = (
    'If that prints `"trusted_lane": "light"`, write the light PLAN from the light block below. '
    "Otherwise (full lane or untrusted light) follow the full PLAN text instead."
)
ROUTING_LOOP = (
    'If approval-status prints `"trusted_lane": "light"` and loop-mode-active (`<PROJECT_ROOT>`: '
    "cwd without any `/.worktrees/<name>/` suffix) exits 1, write the light PLAN from the light "
    "block below. Otherwise (full lane, untrusted light, or loop mode) follow the full PLAN text "
    "instead."
)
STEP03_SENTENCE = (
    "Light PLAN: run the light read-back from Step 0's light block. Any other PLAN: apply the "
    "Step 0.3 part of `.claude/hm/execute-plan.md`, read from the project root, never a "
    "worktree; if it is missing, say to re-render with `/hm:make` and STOP."
)
#: The Codex render spells the re-render command `$hm-make` (AGENTS.md rewrite).
STEP03_SENTENCE_CODEX = STEP03_SENTENCE.replace("`/hm:make`", "`$hm-make`")
LOOP_MODE_CMD = "hm worktree loop-mode-active"
LIGHT_OPEN, LIGHT_CLOSE = "<!-- @hm:light-plan -->", "<!-- @hm:/light-plan -->"
#: The fixed separator line, as its own paragraph.
SEPARATOR = (
    "<!-- @hm:ref:step-0.3 --> Apply the rest of this file at the command's Step 0.3 heading, "
    "after Step 0.1 has run.\n\n"
)
POINTER_EXECUTE_PLAN = "Read `.claude/hm/execute-plan.md`"


def light_span(text: str) -> str:
    assert text.count(LIGHT_OPEN) == 1, "one light span"
    assert text.count(LIGHT_CLOSE) == 1, "one light span"
    i = text.index(LIGHT_OPEN)
    return text[i : text.index(LIGHT_CLOSE, i) + len(LIGHT_CLOSE)]


def delete_once(text: str, literal: str) -> str:
    assert text.count(literal) == 1, literal[:80]
    return text.replace(literal, "", 1)


def approval_block(step0: str) -> str:
    blocks: list[str] = re.findall(
        r"```[a-z]*\n[^\n]*hm spec_machine approval-status --root \. --slug <slug>[^\n]*\n"
        r"(?:[^\n]*hm worktree loop-mode-active [^\n]*\n)?```\n\n",
        step0,
    )
    assert len(blocks) == 1, blocks
    return blocks[0]


def loop_routing_as_off(text: str) -> str:
    """The one loop-dependent edit 3c makes outside a loop-only span, mapped to its loop-off form.

    Review round 1 (2026-10-15) made the light route read `loop-mode-active` when the loop renders:
    the Step 0 block gains that call and the routing sentence becomes `ROUTING_LOOP`. A body
    without the call is returned unchanged.
    """
    if ROUTING_LOOP not in text:
        return text
    i = text.index(STEP0_HEADING) + len(STEP0_HEADING)
    j = text.index(STEP01_HEADING, i)
    step0 = text[i:j]
    block = approval_block(step0)
    off_block = "\n".join(ln for ln in block.split("\n") if LOOP_MODE_CMD not in ln)
    assert len(off_block) < len(block), "one loop-mode-active line in the block"
    assert step0.count(ROUTING_LOOP) == 1, "one loop routing sentence"
    step0 = step0.replace(block, off_block, 1).replace(ROUTING_LOOP, ROUTING, 1)
    return text[:i] + step0 + text[j:]


def undo_execute(text: str, parts: list[str], claude: bool) -> str:
    """S13's fixed rules for execute: drop the light span and the three literals, restore parts.

    `parts` is `execute-plan.md`'s slice split at `SEPARATOR`. Shared with the older byte-identity
    tests, which undo 3c's execute delta this way before comparing with their goldens.
    """
    i = text.index(STEP0_HEADING) + len(STEP0_HEADING)
    j = text.index(STEP01_HEADING, i)
    step0 = text[i:j]
    step0 = delete_once(step0, approval_block(step0))
    routing = ROUTING_LOOP if LOOP_MODE_CMD in approval_block(text[i:j]) else ROUTING
    step0 = delete_once(step0, routing + "\n\n")
    span = light_span(step0)
    assert len(span) <= 2400
    anchor_end = step0.index(span)
    if claude:
        pointer = next(ln for ln in step0.splitlines() if ln.startswith(POINTER_EXECUTE_PLAN))
        anchor = pointer + "\n\n"
        assert step0[anchor_end - len(anchor) : anchor_end] == anchor, "span follows the pointer"
    else:
        assert step0[:anchor_end].endswith(parts[0]), "span follows the inline part 1"
    step0 = delete_once(step0, span + "\n\n")
    if claude:
        step0 = step0.replace(anchor, parts[0], 1)
    text = text[:i] + step0 + text[j:]
    k = text.index(STEP03_HEADING) + len(STEP03_HEADING)
    sentence = STEP03_SENTENCE if claude else STEP03_SENTENCE_CODEX
    assert text[k:].startswith(sentence + "\n\n")
    rest = text[k + len(sentence) + 2 :]
    return text[:k] + (parts[1] if claude else "") + rest


def with_content_hash(text: str) -> str:
    """`text` with its frontmatter `content_hash` recomputed over its body.

    The hash is the body's sha256, so after an undo it equals the old line exactly when the body
    equals the old body; a byte golden that includes the frontmatter can then be compared as is.
    """
    fm = frontmatter_end(text)
    digest = hashlib.sha256(text[fm:].encode()).hexdigest()
    return (
        re.sub(r"^content_hash: .*$", f"content_hash: {digest}", text[:fm], flags=re.M) + text[fm:]
    )


def step0_body(text: str) -> str:
    i = text.index(STEP0_HEADING) + len(STEP0_HEADING)
    return text[i : text.index(STEP01_HEADING, i)]


def step0_head(text: str) -> str:
    """At a7403f2f: the two intro paragraphs and the two shared rules (a prefix of the body)."""
    body = step0_body(text)
    return body[: body.index(PART1_START)]


def step0_part1(text: str) -> str:
    body = step0_body(text)
    return body[body.index(PART1_START) :]


def step03_body(text: str) -> str:
    i = text.index(STEP03_HEADING) + len(STEP03_HEADING)
    return text[i : text.index(STEP1_HEADING, i)]


def step35(text: str) -> str:
    i = text.index(STEP35_HEADING)
    return text[i : text.index(STEP4_HEADING, i)]


def step4(text: str) -> str:
    i = text.index(STEP4_HEADING)
    return text[i : text.index(STEP45_HEADING, i + len(STEP4_HEADING))]


def output_language_section(text: str) -> str:
    i = text.index(LANG_START)
    return text[i : text.index(LANG_END, i) + len(LANG_END)]


def without_spec_steps_35_4(text: str) -> str:
    """Spec with Step 3.5 and Step 4 + 4.5 left out (S13: AC-015 and AC-009 compare them)."""
    i = text.index(STEP35_HEADING)
    j = text.index(STEP45_HEADING, text.index(STEP4_HEADING) + len(STEP4_HEADING))
    return text[:i] + text[j:]


def render_project(answers: Any, root: Path) -> None:
    """Render `answers` into the project at `root` (install ref pinned, clock frozen)."""
    from harness_maker.models import ProjectProfile
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize
    from tests.structural._surface_baseline import pinned_install_ref

    with pinned_install_ref():
        render(
            synthesize(ProjectProfile(), answers), root / ".claude", freeze_time=DEFAULT_FREEZE_TIME
        )


def workflow_clarity(root: Path) -> dict[str, Any]:
    from harness_maker import readiness

    dim = readiness._dim_workflow_clarity(root)
    return {"score": dim.score, "signals": [s.model_dump() for s in dim.signals]}


def workflow_clarity_of_default() -> dict[str, Any]:
    """workflow_clarity on the repo's own config, rendered fresh."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        render_project(_answers(lambda _b: {}), root)
        return workflow_clarity(root)


def boundary_case(case: Any) -> bool:
    """S13's boundary inputs: every execute case and every verify case of s3a's AC-004 domain."""
    return bool(case.current in ("execute", "verify") and case.gate in (None, "clear"))


# ── spec_machine check fixtures (S4 / S5) ─────────────────────────────────────

#: S5's failure fixtures, each a directory under CHECK_FIXTURES_DIR holding SPEC-x.md and,
#: unless the fixture is the missing file, SPEC-x.machine.yaml. Value: (strictness, scorer).
FAILURE_FIXTURES: dict[str, tuple[str, str | None]] = {
    "string_golden_input": ("warn", None),
    "row_without_expected": ("warn", None),
    "missing_ac_heading": ("warn", None),
    "title_mismatch": ("warn", None),
    "v2_ac_without_oracle_evidence": ("warn", None),
    "unparseable_yaml": ("warn", None),
    "missing_yaml_file": ("warn", None),
    "block_overall_55": ("block", "overall_55"),
    "raise_and_validate_fails": ("warn", "raise"),
}
#: S4's passing fixtures: all on the `valid` pair, the score set by the scorer stub.
PASSING_CASES: dict[str, tuple[str, str]] = {
    "clean": ("warn", "clean"),
    "weak": ("warn", "weak"),
    "low": ("warn", "low"),
    "raise": ("warn", "raise"),
}
#: The fixed scores each stub returns; the dimension names are evaluate_spec's own.
SCORER_SCORES: dict[str, dict[str, int]] = {
    "clean": {
        "completeness": 80,
        "testability": 80,
        "unambiguity": 80,
        "consistency": 80,
        "scope_boundary": 80,
        "machine_verifiability": 80,
        "mutation_coverage_set": 80,
        "oracle_independence": 80,
    },
    # One dimension under 40, overall 70.
    "weak": {
        "completeness": 30,
        "testability": 80,
        "unambiguity": 80,
        "consistency": 80,
        "scope_boundary": 80,
        "machine_verifiability": 80,
        "mutation_coverage_set": 80,
        "oracle_independence": 70,
    },
    # Overall 55, no dimension under 40.
    "low": {
        "completeness": 50,
        "testability": 45,
        "unambiguity": 60,
        "consistency": 70,
        "scope_boundary": 55,
        "machine_verifiability": 50,
        "mutation_coverage_set": 50,
        "oracle_independence": 60,
    },
}
SCORER_SCORES["overall_55"] = SCORER_SCORES["low"]
CHECK_YAML = "SPEC-x.machine.yaml"
CHECK_MD = "SPEC-x.md"


@contextlib.contextmanager
def scorer(kind: str | None) -> Iterator[None]:
    """Replace `spec_quality.evaluate_spec` with a fixed stub (the a7403f2f test's technique)."""
    import importlib

    if kind is None:
        yield
        return
    sq: Any = importlib.import_module("harness_maker.spec_quality")
    original = sq.evaluate_spec

    def stub(_text: str, strictness: str = "warn", **_kw: Any) -> Any:
        if kind == "raise":
            raise RuntimeError("scorer exploded")
        scores = dict(SCORER_SCORES[kind])
        weak = [d for d, s in scores.items() if s < 40]
        overall = sum(scores.values()) // len(scores)
        mode = "block" if strictness == "block" else "warn"
        return sq.SpecQualityResult(
            scores=scores,
            overall=overall,
            weak_dimensions=weak,
            blocked=mode == "block" and (overall < 60 or bool(weak)),
            strictness=mode,
        )

    sq.evaluate_spec = stub
    try:
        yield
    finally:
        sq.evaluate_spec = original


@contextlib.contextmanager
def _cwd(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def run_check(fixture: str, strictness: str, kind: str | None) -> tuple[int, str]:
    """`hm spec_machine check --all` on a copy of `fixture`, with relative paths (stable bytes)."""
    from harness_maker import spec_machine

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "specs"
        shutil.copytree(CHECK_FIXTURES_DIR / fixture, work)
        buf = io.StringIO()
        with _cwd(work), scorer(kind), contextlib.redirect_stdout(buf):
            rc = spec_machine.main(
                [
                    "check",
                    "--all",
                    "--yaml",
                    CHECK_YAML,
                    "--md",
                    CHECK_MD,
                    "--strictness",
                    strictness,
                ]
            )
        return rc, _without_approval(buf.getvalue())


def _without_approval(out: str) -> str:
    """Drop SPEC-hm-cost-p2's additive `approval` key (IRR-003): these goldens pin the quiet
    contract of a7403f2f, which the new key does not change."""
    try:
        payload = json.loads(out)
    except ValueError:
        return out
    if not isinstance(payload, dict) or "approval" not in payload:
        return out
    payload.pop("approval")
    return json.dumps(payload, ensure_ascii=False) + "\n"


def run_all_checks() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, (strictness, kind) in FAILURE_FIXTURES.items():
        fixture = "valid_fails_validate" if name == "raise_and_validate_fails" else name
        if name == "block_overall_55":
            fixture = "valid"
        rc, stdout = run_check(fixture, strictness, kind)
        out[name] = {"exit": rc, "stdout": stdout}
    for name, (strictness, kind) in PASSING_CASES.items():
        rc, stdout = run_check("valid", strictness, kind)
        out[f"pass:{name}"] = {"exit": rc, "stdout": stdout}
    return out


# ── the light-path CLIs (S6) ──────────────────────────────────────────────────

SLUG = "demo"
SESSION_ID = "s3c-fixture-session"
#: Volatile values masked before the byte comparison: the temp root, and wall-clock numbers.
_VOLATILE = (
    (re.compile(r'"(idle_minutes|age_minutes|elapsed_s|duration_s|seconds)": [0-9.]+'), r'"\1": 0'),
    # The verification key folds in the local tool versions, so it is per-machine.
    (re.compile(r'"key": "[0-9a-f]{64}"'), '"key": "<KEY>"'),
    (
        re.compile(r'"(created_at|last_seen|expires_at|ts|now|at|computed_at)": "[^"]*"'),
        r'"\1": "<T>"',
    ),
)


def _mask(text: str, root: Path) -> str:
    text = text.replace(str(root.resolve()), "<ROOT>").replace(str(root), "<ROOT>")
    for pattern, repl in _VOLATILE:
        text = pattern.sub(repl, text)
    return text


def _capture(fn: Callable[[], int]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


_FAKE_TOOL = """#!/usr/bin/env python3
import sys
sys.exit(0)
"""
_CI = """name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruff check .
      - run: pytest -q
"""


def run_light_path_clis(base: Path) -> dict[str, dict[str, Any]]:
    """Run every S6 CLI once on its own succeeding fixture; return masked stdout and exit code."""
    from harness_maker import autopilot, autopilot_caps, spec_machine, spec_need
    from harness_maker.models import AtomicStage
    from harness_maker.observability import verification_cache
    from tests.unit import light_lane_s3a_fixture as s3a

    s3a.isolate_env(base / "home")
    out: dict[str, dict[str, Any]] = {}

    def keep(name: str, root: Path, fn: Callable[[], int]) -> None:
        rc, stdout = _capture(fn)
        out[name] = {"exit": rc, "stdout": _mask(stdout, root)}

    # autopilot status — an armed marker for this session.
    root = base / "status"
    s3a.init_repo(root)
    created = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    autopilot.write(
        root,
        level="auto_safe",
        pipeline=[AtomicStage(s) for s in s3a.DEFAULT_PIPELINE],
        now=created,
        claude_session_id=SESSION_ID,
    )
    keep(
        "autopilot status",
        root,
        lambda: autopilot.main(["status", "--root", str(root), "--session-id", SESSION_ID]),
    )

    # autopilot_caps boundary — proceed (light, passing check, execute) and the merge gate
    # (verify, auto_full, the AC-003 oracle case of s3a).
    for name, case in (
        ("autopilot_caps boundary proceed", s3a.Case("full", "none", "research", gate="clear")),
        (
            "autopilot_caps boundary merge-gate",
            s3a.Case("light", "passed", "verify", "auto_full"),
        ),
    ):
        root = base / name.replace(" ", "_")
        argv = s3a.build(root, case)
        keep(name, root, functools.partial(autopilot_caps.main, argv))

    # spec_machine approval-status on an approved light SPEC.
    root = base / "approval"
    s3a.init_repo(root)
    s3a.write_spec(root, "light")
    keep(
        "spec_machine approval-status",
        root,
        lambda: spec_machine.main(["approval-status", "--root", str(root), "--slug", SLUG]),
    )

    # spec_need record / frontmatter-upsert / op-check / waiver-check.
    root = base / "spec_need"
    s3a.init_repo(root)
    s3a.write_spec(root, "light")
    (root / "work-docs").mkdir()
    plan = root / "work-docs" / f"PLAN-{SLUG}.md"
    plan.write_text(f"---\ntype: plan\ntask_slug: {SLUG}\n---\n\n# PLAN\n", encoding="utf-8")
    keep(
        "spec_need record",
        root,
        lambda: spec_need.main(
            [
                "record",
                "--verdict",
                "none",
                "--target",
                "none",
                "--root",
                str(root),
                "--rationale",
                "fixture",
            ]
        ),
    )
    keep(
        "spec_need frontmatter-upsert",
        root,
        lambda: spec_need.main(
            [
                "frontmatter-upsert",
                "--plan",
                str(plan),
                "--root",
                str(root),
                "--verdict",
                "none",
                "--target",
                "none",
            ]
        ),
    )
    keep(
        "spec_need op-check",
        root,
        lambda: spec_need.main(
            ["op-check", "--verdict", "add", "--target", SLUG, "--root", str(root)]
        ),
    )
    with contextlib.redirect_stdout(io.StringIO()):
        spec_need.main(
            [
                "waiver-set",
                "--root",
                str(root),
                "--slug",
                SLUG,
                "--verdict",
                "none",
                "--target",
                "none",
                "--rationale",
                "fixture",
                "--changed-file",
                "src/app.py",
            ]
        )
    keep(
        "spec_need waiver-check",
        root,
        lambda: spec_need.main(
            ["waiver-check", "--root", str(root), "--slug", SLUG, "--changed-file", "src/app.py"]
        ),
    )

    # observability.verification_cache run — a CI with two blocking gates that pass.
    root = base / "vc"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (root / "uv.lock").write_text("# lock\n", encoding="utf-8")
    (root / "src.py").write_text("x = 1\n", encoding="utf-8")
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(_CI, encoding="utf-8")
    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@t"),
        ("config", "user.name", "t"),
        ("add", "-A"),
        ("commit", "-q", "-m", "base"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)
    fake_bin = base / "bin"
    fake_bin.mkdir()
    for name in ("ruff", "pytest"):
        tool = fake_bin / name
        tool.write_text(_FAKE_TOOL, encoding="utf-8")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    old_path = os.environ["PATH"]
    os.environ["PATH"] = f"{fake_bin}{os.pathsep}{old_path}"
    try:
        keep(
            "observability.verification_cache run",
            root,
            lambda: verification_cache.main(["run", "--root", str(root)]),
        )
    finally:
        os.environ["PATH"] = old_path
    return out


def light_path_outputs() -> dict[str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as td:
        env = {
            k: os.environ.get(k)
            for k in (
                "HOME",
                "GIT_CONFIG_GLOBAL",
                "GIT_CONFIG_NOSYSTEM",
                "HARNESS_MAKER_CACHE_DIR",
                "HM_SESSION_ID",
            )
        }
        try:
            return run_light_path_clis(Path(td))
        finally:
            for k, v in env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def dump(doc: Any) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
