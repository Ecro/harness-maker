"""HM-LIGHT-LANE stage 3c: one stage preamble, a quiet check, a short light PLAN (SPEC s3c).

The oracle is the a7403f2f render, captured BEFORE any template changed by
`tests/fixtures/light_lane_s3c/capture_a7403f2f.py.txt` from an export of a7403f2f: the preamble
spans, the CLAUDE.md / AGENTS.md language sections, execute Step 0's head and part 1 and Step 0.3's
body, spec Step 3.5 and Step 4 + 4.5's length on the A arms (`arms_a7403f2f.json`), every compared
path's SHA-256 on the full-lane arms (`full_a7403f2f.json`), the boundary observations
(`boundary_a7403f2f.json`) and `measure_surface()` (`surface_a7403f2f.json`). The phrases and exact
strings below are copied from the SPEC's Outcomes, written before the templates. None of it is
derived from the new templates.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from tests.unit import light_lane_s3c_fixture as fx
from tests.unit import light_lane_s3d_fixture as s3d

ARMS: dict[str, Any] = json.loads((fx.GOLDENS / "arms_a7403f2f.json").read_text(encoding="utf-8"))
TEXTS: dict[str, str] = ARMS["texts"]
A_KEYS = list(fx.A_CONFIGS)
FULL_KEYS = list(fx.FULL_CONFIGS)
assert set(ARMS["configs"]) == set(A_KEYS)

FRONTMATTER_KEYS = ("generated_by", "content_hash", "source_template", "harness_maker_version")
BANNER_MARKER = "<!-- @hm:banner:start -->"
LANG_MARKER = "<!-- @hm:output_language -->"

# ── A: the preamble pointer (SPEC Outcomes A) ─────────────────────────────────
POINTER_PHRASES = (
    "`.claude/hm/stage-preamble.md`",
    "project root",
    "unless this session's context already holds it from an earlier `/hm:` stage",
    "either way",
    "apply it to this stage",
    "loop-mode check",
    "start banner",
    "autopilot picker",
    "only if it has not been answered this session",
    # The missing-file rule: name the file, re-render, no banner and no picker, stay armed.
    "If it is missing or unreadable, name `stage-preamble.md`",
    "re-render with `/hm:make`",
    "no banner and no picker",
    "stays armed",
    BANNER_MARKER,
    LANG_MARKER,
)


@cache
def _a_render(key: str) -> dict[str, str | None]:
    return fx.render_files(fx.a_answers(key))


def _text(key: str, rel: str) -> str:
    text = _a_render(key)[rel]
    assert text is not None, f"{rel} did not render for {key}"
    return text


def _golden(key: str, field: str, rel: str) -> str:
    return TEXTS[ARMS["configs"][key][field][rel]]


def _preamble_sentences(preamble: str) -> list[str]:
    """The a7403f2f preamble's sentences, as its quoted lines (markers and short lines aside)."""
    out = []
    for line in preamble.splitlines():
        body = line.lstrip("> ").strip()
        if len(body) >= 30 and not body.startswith("<!--"):
            out.append(body)
    return out


@pytest.mark.parametrize("key", A_KEYS)
def test_stage_commands_point_at_the_preamble(key: str) -> None:
    """AC-001: every Claude stage command carries the read-once, apply-every-stage pointer."""
    for rel in fx.CLAUDE_COMMANDS:
        text = _text(key, rel)
        pointer = fx.preamble_span(text)
        assert len(pointer) <= 650, (rel, len(pointer))
        for phrase in POINTER_PHRASES:
            assert phrase in pointer, (rel, phrase)
        # "Either way" applies the file; the banner comes after it, and the picker last.
        assert pointer.index("either way") < pointer.index("banner"), rel
        assert (
            pointer.index("loop-mode check")
            < pointer.index("start banner")
            < pointer.index("autopilot picker")
        ), rel
        wt_on = fx.A_CONFIGS[key][1]
        assert ("never from `<WT>`" if wt_on else "never from a worktree") in pointer, rel
        assert "STOP" not in pointer, rel
        for sentence in _preamble_sentences(_golden(key, "preamble", rel)):
            assert sentence not in text, (rel, sentence)


@pytest.mark.parametrize("key", A_KEYS)
def test_preamble_moved_byte_for_byte(key: str) -> None:
    """AC-002: the reference file's ref slice is each command's a7403f2f preamble span."""
    ref = _text(key, "hm/stage-preamble.md")
    for rel in fx.CLAUDE_COMMANDS:
        assert fx.ref_slice(ref) == _golden(key, "preamble", rel), rel
    frontmatter = ref.split("---\n", 2)[1]
    for k in FRONTMATTER_KEYS:
        assert re.search(rf"^{k}:", frontmatter, re.M), k


@pytest.mark.parametrize("key", A_KEYS)
def test_codex_and_claude_md_keep_the_preamble(key: str) -> None:
    """AC-003: the Codex skills, CLAUDE.md and AGENTS.md keep their a7403f2f inline text."""
    for rel in fx.CODEX_SKILLS:
        assert fx.preamble_span(_text(key, rel)) == _golden(key, "preamble", rel), rel
    for doc in fx.DOCS:
        assert fx.output_language_section(_text(key, doc)) == _golden(key, "lang", doc), doc
    assert "stage-preamble" not in "".join(_text(key, rel) for rel in fx.CODEX_SKILLS)


def _sha(text: str | None) -> str | None:
    return None if text is None else hashlib.sha256(text.encode()).hexdigest()


# ── B: the spec stage describes the quiet check (AC-009) ──────────────────────
#: The B contract's names (SPEC Outcomes B): the one-line success form, the two dimension lists,
#: blocked, by_rule counts and the scoring-exception form.
QUIET_PHRASES = (
    "one line, `{ok: true, overall, strictness}`",
    "`weak_dimensions`",
    "`low_dimensions`",
    "`{dim: score}`",
    "`quality.blocked`",
    "`by_rule` counts",
    "each error once",
    "`quality` is `{error, strictness}`",
)


@pytest.mark.parametrize("key", A_KEYS)
def test_spec_describes_quiet_check(key: str) -> None:
    for rel in ("commands/hm/spec.md", "skills/hm-spec"):
        step4 = fx.step4(_text(key, rel))
        for phrase in QUIET_PHRASES:
            assert phrase in step4, (rel, phrase)
        assert "scores" not in step4, rel
        assert len(step4) <= ARMS["configs"][key]["step4_len"][rel] + 300, (rel, len(step4))


# ── C: the light PLAN (AC-010, AC-011) ────────────────────────────────────────
#: Exact strings written in the SPEC's Outcomes C.
ROUTING, STEP03_SENTENCE = fx.ROUTING, fx.STEP03_SENTENCE
LIGHT_OPEN, LIGHT_CLOSE = fx.LIGHT_OPEN, fx.LIGHT_CLOSE
SEPARATOR, POINTER_EXECUTE_PLAN = fx.SEPARATOR, fx.POINTER_EXECUTE_PLAN
#: The four read-back assertions, the Step 1.5 note and the oversize rule (SPEC Outcomes C).
LIGHT_BRANCH_PHRASES = (
    "every key of the template",
    "`scope:`, `exit:`, `risk:` and `rollback:`",
    "`### Do not change` is present and non-empty",
    "three admitted forms",
    "only as the sole bullet",
    "`spec_need_verdict`",
    "after Step 0.1",
    "self-repaired inline",
    "Step 1.5",
    "phases run in order",
    "well over five files",
    "follow the full PLAN text instead",
    "reads as `full`",
    # The full Step 0 / 0.3 guards, kept on the light arm (SPEC amendment 2026-10-15).
    "no absolute, `..` or globs",
    "only when the user explicitly made that call",
    "never invented for an empty list; beside others, delete the `none`",
    "if a re-read still fails, surface the path and error and stop before Step 1",
)
PHASE_LINE = (
    "- [ ] {N}. **Phase {N} — {name}** — scope: {files} · exit: `{command}` · risk: {risk} · "
    "rollback: {rollback}"
)
LIGHT_TEMPLATE_KEYS = (
    "type: plan",
    "task_slug: {slug}",
    "status: planning",
    "created: {YYYY-MM-DD}",
    "spec:",
    "research_doc:",
    "intent: <id>",
    "adrs: {M}",
    "summary:",
    "## 📝 Implementation Plan",
    "## 🚧 Contract Boundaries",
    "### Do not change",
    "## 📐 Architecture Decision Records",
    PHASE_LINE,
    "- ADR-{NNN}: {decision}. **Decided by:** {provenance}",
)
EXECUTES = ("commands/hm/execute.md", "skills/hm-execute")


light_span = fx.light_span


def light_template(text: str) -> str:
    span = light_span(text)
    i = span.index("```markdown\n") + len("```markdown\n")
    return span[i : span.index("\n```", i) + 1]


def step03_paragraph(text: str) -> str:
    """The paragraph the Step 0.3 heading carries, directly under it."""
    i = text.index(fx.STEP03_HEADING) + len(fx.STEP03_HEADING)
    return text[i : text.index("\n\n", i)]


def approval_status_line(key: str, rel: str) -> str:
    """APPROVAL_STATUS_CMD: the light check's own command, from its unchanged a7403f2f text."""
    source = _text(key, "hm/execute-light-check.md" if rel.startswith("commands") else rel)
    if not rel.startswith("commands"):
        source = source[source.index("### Step 4.2 — Light check") :]
    return next(ln for ln in source.splitlines() if "hm spec_machine approval-status" in ln)


def pointer_at(rel: str, body: str) -> str:
    """The full-lane text at the pointer's place: the pointer line, or Codex's inline part 1."""
    return POINTER_EXECUTE_PLAN if rel.startswith("commands") else fx.PART1_START


@pytest.mark.parametrize("key", A_KEYS)
def test_light_execute_writes_the_short_plan(key: str) -> None:
    """AC-010: Step 0 opens with its a7403f2f head, then routes; the light block follows."""
    wt_on = fx.A_CONFIGS[key][1]
    shared_rules = (
        f"Write to `{'<WT>' if wt_on else '.'}/work-docs/PLAN-{{slug}}.md`",
        "**If that file already exists, do not rewrite it**",
    )
    for rel in EXECUTES:
        r = _text(key, rel)
        b = fx.step0_body(r)
        head = _golden(key, "step0_head", rel)
        assert b.startswith(head), rel
        for rule in shared_rules:
            assert rule in head, (rel, rule)
        cmd = approval_status_line(key, rel)
        assert (
            len(head)
            <= b.index(cmd)
            < b.index(ROUTING)
            < b.index(pointer_at(rel, b))
            < b.index(LIGHT_OPEN)
        ), rel
        assert b.count(LIGHT_OPEN) == 1, rel
        assert b.count(LIGHT_CLOSE) == 1, rel
        span = light_span(r)
        assert len(span) <= 2400, (rel, len(span))
        flat = " ".join(span.split())  # the prose is wrapped; a phrase may span a line break
        for phrase in LIGHT_BRANCH_PHRASES:
            assert phrase in flat, (rel, phrase)
        template = light_template(r)
        for k in LIGHT_TEMPLATE_KEYS:
            assert k in template, (rel, k)
        claude = rel.startswith("commands")
        assert step03_paragraph(r) == (STEP03_SENTENCE if claude else fx.STEP03_SENTENCE_CODEX), rel
        # Loop off: `/hm:loop` does not render, so no loop check and no loop clause.
        assert fx.LOOP_MODE_CMD not in b, rel


LOOP_ON_KEYS = [k for k in FULL_KEYS if fx.FULL_CONFIGS[k][3]]


@pytest.mark.parametrize("key", LOOP_ON_KEYS)
def test_loop_on_routing_runs_the_loop_check(key: str) -> None:
    """AC-010 with the loop renderable: the routing reads `loop-mode-active`, not the preamble."""
    files = _full_render(key)
    for rel in EXECUTES:
        b = fx.step0_body(files[rel] or "")
        block = fx.approval_block(b)
        assert fx.LOOP_MODE_CMD in block, rel
        assert b.index(block) < b.index(fx.ROUTING_LOOP) < b.index(LIGHT_OPEN), rel
        assert fx.ROUTING not in b, rel


@pytest.mark.parametrize("key", A_KEYS)
def test_full_execute_reads_the_moved_plan_text(key: str) -> None:
    """AC-011: execute-plan.md is part 1, the separator, part 2 — each a7403f2f's own text."""
    part1 = _golden(key, "step0_part1", "commands/hm/execute.md")
    part2 = _golden(key, "step03", "commands/hm/execute.md")
    ref = _text(key, "hm/execute-plan.md")
    sliced = fx.ref_slice(ref)
    assert sliced.count(SEPARATOR) == 1
    assert sliced.split(SEPARATOR) == [part1, part2]
    frontmatter = ref.split("---\n", 2)[1]
    for k in FRONTMATTER_KEYS:
        assert re.search(rf"^{k}:", frontmatter, re.M), k
    step0 = fx.step0_body(_text(key, "commands/hm/execute.md"))
    pointer = next(ln for ln in step0.splitlines() if ln.startswith(POINTER_EXECUTE_PLAN))
    assert "project root" in pointer
    assert "STOP" in pointer
    assert "Step 0.3" in pointer
    # Off the light path (SPEC amendment 2026-10-15): a light run never Reads the file.
    assert "only when not writing the light PLAN" in pointer
    codex = _text(key, "skills/hm-execute")
    assert _golden(key, "step0_part1", "skills/hm-execute") in codex
    assert _golden(key, "step03", "skills/hm-execute") in codex
    assert "execute-plan" in fx_synth_reference_files()


def fx_synth_reference_files() -> tuple[str, ...]:
    from harness_maker import synthesize

    return synthesize._STAGE_REFERENCE_FILES


# ── C: spec Step 3.5 (AC-015) ─────────────────────────────────────────────────
#: The SPEC's minimal key list (Outcomes C, "Minimal machine.yaml"), plus the row shape and
#: the T1 mutation keys.
MINIMAL_KEYS = (
    "schema_version: 3",
    "spec_slug",
    "verification_tier",
    "irreversible_decisions",
    "ac:",
    "id:",
    "title:",
    "type:",
    "test_ids",
    "pending_test",
    "oracle_source",
    "oracle_evidence",
    "executable_predicate",
    "golden_table",
    "rubric_id",
    "judgment_subject_paths",
    "input_domain",
    "transformation",
    "expected_relation",
    "observable_output",
    "mutation_threshold",
    "paths_to_mutate",
    "input:",
    "expected:",
    "lane: light",
    "lane: full",
)
POINTER_SPEC_FULL = "Read `.claude/hm/spec-machine-full.md`"
#: The moved part of a7403f2f's Step 3.5, sliced at two of a7403f2f's own strings.
MOVED_FROM, MOVED_TO = (
    "**Required machine.yaml schema (schema_version=3):**",
    "**`executable_predicate` must be",
)


def _moved_step35(key: str, rel: str) -> str:
    old = _golden(key, "step35", rel)
    return old[old.index(MOVED_FROM) : old.index(MOVED_TO)]


@pytest.mark.parametrize("key", A_KEYS)
def test_spec_step_3_5_minimal_inline(key: str) -> None:
    claude = fx.step35(_text(key, "commands/hm/spec.md"))
    codex = fx.step35(_text(key, "skills/hm-spec"))
    for step in (claude, codex):
        for k in MINIMAL_KEYS:
            assert k in step, k
    ref = _text(key, "hm/spec-machine-full.md")
    assert fx.ref_slice(ref) == _moved_step35(key, "commands/hm/spec.md")
    frontmatter = ref.split("---\n", 2)[1]
    for k in FRONTMATTER_KEYS:
        assert re.search(rf"^{k}:", frontmatter, re.M), k
    pointer = next(ln for ln in claude.splitlines() if ln.startswith(POINTER_SPEC_FULL))
    assert "lane: full" in pointer
    assert "STOP" in pointer
    assert MOVED_FROM not in claude
    assert _moved_step35(key, "skills/hm-spec") in codex
    assert POINTER_SPEC_FULL not in codex


# ── S13: the full lane changes only by the named deltas (AC-016) ──────────────
FULL: dict[str, Any] = json.loads((fx.GOLDENS / "full_a7403f2f.json").read_text(encoding="utf-8"))
BOUNDARY: dict[str, str] = json.loads(
    (fx.GOLDENS / "boundary_a7403f2f.json").read_text(encoding="utf-8")
)["cases"]
assert set(FULL["configs"]) == set(FULL_KEYS)


# 2026-10-16, SPEC-hm-overhaul-p1 PR-C: the Cursor target is gone, so the `"cursor" not in
# config.targets` half of research Phase 1's fan-out condition went with it. The full-lane arms
# render this repo's `.claude/harness.yaml`, whose `targets` still lists cursor (dropped at parse),
# so the Claude research command now takes the Explore fan-out branch where a7403f2f took the
# plain "Run these in parallel" branch. Swapping exactly that branch back gives a7403f2f's bytes.
_RESEARCH_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "src/harness_maker/templates/stages/research.md.j2"
).read_text(encoding="utf-8")
_FANOUT_OPEN, _FANOUT_ELSE, _FANOUT_END = "{% if not is_codex %}", "{% else %}", "{% endif %}"
_FANOUT_START = _RESEARCH_TEMPLATE.index(_FANOUT_OPEN) + len(_FANOUT_OPEN)
_FANOUT_MID = _RESEARCH_TEMPLATE.index(_FANOUT_ELSE, _FANOUT_START)
FANOUT_BRANCH = _RESEARCH_TEMPLATE[_FANOUT_START:_FANOUT_MID]
PLAIN_BRANCH = _RESEARCH_TEMPLATE[
    _FANOUT_MID + len(_FANOUT_ELSE) : _RESEARCH_TEMPLATE.index(_FANOUT_END, _FANOUT_MID)
]
#: PR-C's research growth, measured 2026-10-16 (surface baseline 16 677 -> 17 292 chars). Fixed
#: here, not derived, so a later edit to either branch moves the bound only by a deliberate edit.
FANOUT_DELTA = 615
assert len(FANOUT_BRANCH) - len(PLAIN_BRANCH) == FANOUT_DELTA, "the fan-out branch changed size"


def without_cursor_fanout(text: str) -> str:
    """`text` with PR-C's research fan-out branch swapped back for the plain one, exactly once."""
    assert text.count(FANOUT_BRANCH) == 1
    return text.replace(FANOUT_BRANCH, PLAIN_BRANCH)


@cache
def _full_render(key: str) -> dict[str, str | None]:
    return fx.render_files(fx.full_answers(key))


def _normalise(key: str, rel: str) -> str | None:
    files = _full_render(key)
    text = files[rel]
    if text is None:
        return None
    if rel in fx.CLAUDE_COMMANDS:
        preamble = fx.ref_slice(files["hm/stage-preamble.md"] or "")
        fm = fx.frontmatter_end(text)
        text = text[:fm] + preamble + text[fm + len(fx.preamble_span(text)) :]
    if rel in EXECUTES:
        parts = fx.ref_slice(files["hm/execute-plan.md"] or "").split(SEPARATOR)
        assert len(parts) == 2
        text = fx.undo_execute(text, parts, claude=rel.startswith("commands"))
    if rel in ("commands/hm/spec.md", "skills/hm-spec"):
        text = fx.without_spec_steps_35_4(text)
    if rel in ("hm/execute-light-check.md", "skills/hm-execute"):
        # 2026-10-15, SPEC-hm-light-lane-s3d: the light check's Check 2 passes `--spec-slug` and
        # its record line names the gate source. Undoing exactly those bytes gives a7403f2f's.
        text = s3d.without_s3d(text, record=True)
    if rel == "commands/hm/research.md":
        text = without_cursor_fanout(text)
    return fx.mask_content_hash(text)


@pytest.mark.parametrize("key", FULL_KEYS)
def test_full_lane_changes_only_by_named_deltas(key: str) -> None:
    golden = FULL["configs"][key]
    differ = [rel for rel in FULL["paths"] if _sha(_normalise(key, rel)) != golden[rel]]
    assert differ == [], (key, differ)


@pytest.mark.parametrize("case_key", sorted(BOUNDARY))
def test_boundary_json_is_unchanged(case_key: str, tmp_path: Any) -> None:
    """S13's last clause: the boundary JSON for the same inputs equals a7403f2f's."""
    from tests.unit import light_lane_s3a_fixture as s3a

    case = next(c for c in s3a.ac004_cases() if c.key == case_key)
    old = s3a.isolate_env(tmp_path / "home")
    try:
        argv = s3a.build(tmp_path / "c", case)
        assert s3a.observation_sha(s3a.observe(tmp_path / "c", argv)) == BOUNDARY[case_key]
    finally:
        import os

        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── S14: the surface meets the bounds (AC-017) ────────────────────────────────
SURFACE: dict[str, Any] = json.loads(
    (fx.GOLDENS / "surface_a7403f2f.json").read_text(encoding="utf-8")
)
#: The SPEC's per-cut bounds (Surface table), applied to a7403f2f's own numbers.
CUTS: dict[tuple[str, str], int] = {
    # + FANOUT_DELTA: PR-C's fan-out branch (see `without_cursor_fanout`), not a stage-3c cut.
    ("claude", "research"): -3712 + FANOUT_DELTA,
    ("claude", "spec"): -3712 + 300 - 1000,
    # C amended to -2150 (SPEC amendment 2026-10-15, review round 1): the light read-back
    # keeps the full Step 0 / 0.3 guards, and Step 0.3 carries the read rule.
    ("claude", "execute"): -3712 - 2150,
    ("claude", "review"): -3712,
    ("claude", "verify"): -3712,
    ("claude", "wrapup"): -3712,
    ("codex", "hm-execute"): 2500,
    # B's Step 4 text (at most +300, AC-009) and C's minimal schema (at most +800).
    ("codex", "hm-spec"): 300 + 800,
    ("codex", "hm-research"): 0,
    ("codex", "hm-review"): 0,
    ("codex", "hm-verify"): 0,
    ("codex", "hm-wrapup"): 0,
}
REF_BOUND = {"stage-preamble": 4900, "execute-plan": 6300, "spec-machine-full": 3500}


def test_surface_meets_bounds() -> None:
    from tests.structural import _surface_baseline as sb

    now = sb.measure_surface()
    old = SURFACE["surface"]
    for (variant, name), delta in CUTS.items():
        bound = old[variant][name]["chars"] + delta
        assert now[variant][name]["chars"] <= bound, (variant, name, now[variant][name], bound)
    refs = sb.render_surface(with_refs=True)[sb.REFS_VARIANT]
    for name, bound in REF_BOUND.items():
        assert len(refs[name]) <= bound, (name, len(refs[name]))
    for name, size in SURFACE["refs"].items():
        ref = refs[name]
        if name == "execute-light-check":
            # 2026-10-15, SPEC-hm-light-lane-s3d adds `--spec-slug` and the gate-source record
            # line to this file; the bound applies to it with exactly those bytes undone.
            ref = s3d.without_s3d(ref, record=True)
        assert len(ref) <= size, name
