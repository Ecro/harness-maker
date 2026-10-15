"""HM-LIGHT-LANE stage 3a — execute's light check, and what must not move (SPEC-hm-light-lane-s3a).

The oracle is the e7dd6648 render, captured BEFORE any template changed by
`tests/fixtures/light_lane_s3a/capture_e7dd6648.py.txt` in a `git worktree` of e7dd6648: SHAs of
the review/verify/wrapup/loop surface (AC-011), the execute command's length (AC-007), verify
Checks 2, 4 and 6 sliced by heading and review Step 2's drift rule (AC-008), and spec Step 0's
exempt command (AC-014). None of it is derived from the new templates.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from functools import cache
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from harness_maker import synthesize as synthesize_mod
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import LoopConfig, Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from tests.structural._surface_baseline import HARNESS_YAML, pinned_install_ref
from tests.unit import light_lane_s3c_fixture as s3c

GOLDEN: dict[str, Any] = json.loads(
    (Path(__file__).parents[1] / "fixtures/light_lane_s3a/renders_e7dd6648.json").read_text(
        encoding="utf-8"
    )
)
MECH = ["uv run ruff check .", "uv run pytest -q"]
FRONTMATTER_KEYS = ("generated_by", "content_hash", "source_template", "harness_maker_version")
LIGHT_CHECK_MARKERS = frozenset(
    {"security-scan", "review_kind: light-check", "drift_verdict", "### Check 2 — Regression smoke"}
)
SCAN_CMD = {True: "hm cli security-scan <WT> --force", False: "hm cli security-scan . --force"}
REVIEWERS_STILL_RUN = (
    "Drift findings get severity `P1` and surface in the REVIEW report; reviewers still run on "
    "the actual diff."
)
#: The dispatch macro's rendered forms (agents/_partials/dispatch.md.j2 at e7dd6648).
DISPATCH_RE = re.compile(r"Agent\(|subagent_type|spawn_agent")
#: AC-009's rows, as the phrases the light check must carry for each non-pass condition.
NO_RECORD_PHRASES = (
    "not `approved` or `exempt`",
    "irreversible",
    "loop mode",
    "well over five files",
    "any check fails",
    "not `clean`",
    "already holds a real review",
    "writes no record",
    "review runs next",
    # Review item D: the forced scan's own failure clause.
    "no `Security scan:` line",
    # Confirmation pass item 1: Step 4.2 runs only on the boundary's own predicate.
    '`"trusted_lane": "light"`',
    # Confirmation pass item 2: the security gate reads the scan's own summary.
    "a missing or unparseable `Severity:` line",
)
#: The summary's next step after a passing light check (review item P).
WRAPUP_NEXT = {
    "claude": "`/hm:wrapup` when Step 4.2 wrote",
    "codex": "`$hm-wrapup` when Step 4.2 wrote",
}
#: Review item E: the conditions Step 5's exempt branch must name.
EXEMPT_CONDITIONS = (
    "Step 4 passed",
    "no open questions",
    "the DRI was not asked",
    "`auto_full`",
    "no question tool",
    "Never stamp `exempt` over a DRI who was asked",
)
POINTER_START = "Read `.claude/hm/execute-light-check.md`"


def _key(loop: bool, wt: bool, strictness: str, mech: bool, preset: str) -> str:
    return (
        f"loop-{'on' if loop else 'off'}/wt-{'on' if wt else 'off'}/{strictness}/"
        f"mech-{'set' if mech else 'unset'}/{preset}"
    )


CONFIGS = [
    (_key(*c), c)
    for c in product(
        (False, True), (False, True), ("warn", "block"), (False, True), ("Side", "Production")
    )
]
assert {k for k, _ in CONFIGS} == set(GOLDEN["configs"])


@cache
def _render(key: str) -> dict[str, str | None]:
    loop, wt, strictness, mech, preset = dict(CONFIGS)[key]
    base = answers_from_harness_yaml(HARNESS_YAML)
    assert base is not None
    answers = base.model_copy(
        update={
            "loop": LoopConfig(enabled=loop),
            "worktree": {**base.worktree, "enabled": wt},
            "strictness": strictness,
            "mechanical_checks": list(MECH) if mech else [],
            "preset": Preset(preset),
        }
    )
    paths = (
        *GOLDEN["unchanged_paths"],
        "commands/hm/execute.md",
        "commands/hm/spec.md",
        "hm/execute-light-check.md",
        "skills/hm-execute",
        "skills/hm-spec",
        "hm/stage-preamble.md",
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pinned_install_ref():
            render(
                synthesize(ProjectProfile(), answers),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        out: dict[str, str | None] = {}
        for rel in paths:
            if rel.startswith("skills/"):
                p = root / ".agents" / "skills" / rel.split("/", 1)[1] / "SKILL.md"
            else:
                p = root / ".claude" / rel
            out[rel] = p.read_text(encoding="utf-8") if p.is_file() else None
        return out


def _text(key: str, rel: str) -> str:
    text = _render(key)[rel]
    assert text is not None, f"{rel} did not render for {key}"
    return text


def _codex_light_check(key: str) -> str:
    """The light check inlined in the Codex execute skill, from its heading to the next step."""
    text = _text(key, "skills/hm-execute")
    i = text.index("### Step 4.2 — Light check")
    ends = ("\n### Step 4.5", "\n<!-- @hm:loop-only -->\n### Step 5", "\n## Outputs")
    return text[i : min(text.index(e, i) for e in ends if e in text[i:])]


def _light_checks(key: str) -> dict[str, str]:
    return {"claude": _text(key, "hm/execute-light-check.md"), "codex": _codex_light_check(key)}


def _commands(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.startswith(("!uv run", 'Bash("uv run'))]


def _without_pointer(execute: str) -> str:
    return "\n".join(ln for ln in execute.splitlines() if not ln.startswith(POINTER_START))


KEYS = [k for k, _ in CONFIGS]


@pytest.mark.parametrize("key", KEYS)
def test_execute_points_at_the_light_check(key: str) -> None:
    claude_execute = _text(key, "commands/hm/execute.md")
    assert "### Step 4.2 — Light check" in claude_execute
    pointer = next(ln for ln in claude_execute.splitlines() if ln.startswith(POINTER_START))
    assert "execute-light-check.md" in pointer
    assert "project root" in pointer
    wt_on = dict(CONFIGS)[key][1]
    assert ("never from `<WT>`" if wt_on else "never from a worktree") in pointer
    # Review item G: a missing reference file skips the light check; it does not end execute.
    assert "STOP" not in pointer
    assert "skip the light check" in pointer
    assert "review runs next" in pointer
    stub = claude_execute[claude_execute.index("### Step 4.2 — Light check") :]
    assert "loop mode is not active for this session" in stub[: stub.index(POINTER_START)]
    for arm, rel in (("claude", "commands/hm/execute.md"), ("codex", "skills/hm-execute")):
        assert WRAPUP_NEXT[arm] in _text(key, rel), arm
    rest = _without_pointer(claude_execute)
    assert not {m for m in LIGHT_CHECK_MARKERS if m in rest}
    ref = _text(key, "hm/execute-light-check.md")
    frontmatter = ref.split("---\n", 2)[1]
    for k in FRONTMATTER_KEYS:
        assert re.search(rf"^{k}:", frontmatter, re.M), k
    codex = _text(key, "skills/hm-execute")
    assert {m for m in LIGHT_CHECK_MARKERS if m in codex} == LIGHT_CHECK_MARKERS
    assert "execute-light-check" in synthesize_mod._STAGE_REFERENCE_FILES
    assert len(claude_execute) - GOLDEN["configs"][key]["execute_chars"] <= 1000


@pytest.mark.parametrize("key", KEYS)
def test_light_check_runs_the_kept_gates(key: str) -> None:
    _loop, wt, _strictness, mech, _preset = dict(CONFIGS)[key]
    golden = GOLDEN["configs"][key]
    wtr = "<WT>" if wt else "."
    for arm, text in _light_checks(key).items():
        assert SCAN_CMD[wt] in text, arm
        assert "hm spec_machine approval-status" in text, arm
        checks = {n: GOLDEN["texts"][sha] for n, sha in golden["checks"][arm].items()}
        # Check 2 keeps verify's `run` and its stop line; the guessed-gates mark-pass is gone
        # (review item F): exit 3 is not a pass here.
        (run,) = [c for c in _commands(checks["2"]) if "verification_cache run" in c]
        assert run in text, arm
        assert "FAIL when: any subprocess returns non-zero." in text, arm
        assert "mark-pass" not in text, arm
        assert "not a pass" in next(ln for ln in text.splitlines() if ln.startswith("- `3`")), arm
        # Check 4 keeps verify's rule, on this scan's own rows (review item K).
        rule = next(ln for ln in checks["4"].splitlines() if ln.startswith("FAIL when:"))
        assert rule in text, arm
        assert f"`{wtr}/.claude/observability/security/findings-<today>.jsonl`" in text, arm
        assert "Security scan: N finding(s)" in text, arm
        # Confirmation pass item 2: the gate counts `high` and `P0` on the scan's `Severity:`
        # line; the findings file is read for detail only.
        assert "`Severity: high=K, …`" in text, arm
        assert "`high` or `P0`" in text, arm
        assert "for detail only" in text, arm
        assert "last N lines" in text, arm
        # Check 6 keeps verify's two commands, without the BLOCKED box or the 6a/6b prose.
        assert _commands(checks["6"]), arm
        for c in _commands(checks["6"]):
            assert c in text, (arm, c)
        assert "BLOCKED: check 6" not in text, arm
        assert "Step 6a" not in text, arm
        # The record's tree binding and timestamp (review items B and H).
        assert "hm observability.verification_cache key --root . --mode relevant" in text, arm
        assert "verification_key: <" in text, arm
        assert "date -u +%Y-%m-%dT%H:%M:%SZ" in text, arm
        if arm == "claude":
            gate3 = text[text.index("**3. Security**") : text.index("**4. SPEC requirement**")]
            assert "run_in_background" in gate3
        assert GOLDEN["texts"][golden["drift_rule"][arm]] in text, arm
        assert REVIEWERS_STILL_RUN not in text, arm
        assert not DISPATCH_RE.search(text), arm
        if mech:
            assert all(c in text for c in MECH), arm
        else:
            assert "## MECHANICAL_BLOCK" not in text, arm
            assert not any(c in text for c in MECH), arm


@pytest.mark.parametrize("key", KEYS)
def test_light_check_fails_closed(key: str) -> None:
    for arm, text in _light_checks(key).items():
        for phrase in NO_RECORD_PHRASES:
            assert phrase in text, (arm, phrase)
        assert text.index("status: PASSED") > text.index("result: clean"), arm
        assert "repair" not in text, arm


@pytest.mark.parametrize("key", KEYS)
def test_typed_stages_and_loop_unchanged(key: str) -> None:
    golden = GOLDEN["configs"][key]["sha256"]
    for rel in GOLDEN["unchanged_paths"]:
        text = _render(key)[rel]
        if text is not None and rel in s3c.CLAUDE_COMMANDS:
            # 2026-10-15, SPEC-hm-light-lane-s3c: the Claude stage commands point at
            # `.claude/hm/stage-preamble.md` for the preamble they used to carry. Putting that
            # text back (and recomputing the body hash) must give the e7dd6648 bytes exactly.
            text = s3c.with_content_hash(
                s3c.restore_preamble(text, _text(key, "hm/stage-preamble.md"))
            )
        got = None if text is None else hashlib.sha256(text.encode()).hexdigest()
        assert got == golden[rel], (key, rel)


def _step5(text: str) -> str:
    i = text.index("### Step 5 — Status update")
    return text[i : text.index("**Stage terminal**", i)]


@pytest.mark.parametrize("key", KEYS)
def test_spec_stamps_light_exempt(key: str) -> None:
    for arm, rel in (("claude", "commands/hm/spec.md"), ("codex", "skills/hm-spec")):
        step5 = _step5(_text(key, rel))
        assert GOLDEN["configs"][key]["exempt_cmd"][arm] in step5, arm
        assert "lane: light" in step5, arm
        assert "irreversible_decisions: []" in step5, arm
        exempt = step5[step5.index("**exempt**") :]
        for condition in EXEMPT_CONDITIONS:
            assert condition in exempt, (arm, condition)
