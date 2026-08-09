"""Phase 4 of PLAN-second-opinion-oracle-polyglot — the oracle command-set parity gate.

**Why the discovery predicate is an anchor and not the string being removed.** Keying discovery
on the hardcoded `pytest`/`ruff`/`mypy` triple is self-defeating: the moment the fix lands, the
population is empty and a non-vacuity guard fails the suite. So each oracle-describing surface
carries an explicit anchor, discovery collects by that anchor, and the property asserted is
independent of it.

**Why there is also a complement scan.** An anchor set is self-declared by the artifacts being
fixed — the `[fail:test] gate-scoped-to-the-artifact-being-fixed` shape (count:3) this PLAN cites
in its own Prior Work. A dropped anchor fails on the size assertion, but a NEWLY ADDED surface
that asserts a fixed command set and carries no anchor would be invisible by construction.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "harness_maker"

ANCHOR = "@hm:oracle-command-surface"

# The surfaces that describe the ORACLE's command set and were corrected in Phase 4.
EXPECTED_ANCHORED = {
    "src/harness_maker/second_opinion_oracle.py",
    "src/harness_maker/templates/agents/code-verifier_body.md.j2",
    "src/harness_maker/templates/skills/second-opinion-gate/SKILL.md.j2",
}

# ADR-009's explicit deferral list — the eight surfaces that still hardcode the Python triple
# for their OWN purposes (verify/wrapup/loop gates, permission prefixes, a rubric example).
# They are out of scope this round and migrate onto `toolchains` later, with no key move
# because ADR-002 placed the key at the root. This constant is that deferral's single
# machine-readable home: adding a surface here is a deliberate, reviewable act.
DEFERRED_SURFACES = {
    "src/harness_maker/templates/stages/verify.md.j2",
    "src/harness_maker/templates/stages/wrapup.md.j2",
    "src/harness_maker/templates/commands/hm/loop.md.j2",
    "src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2",
    "src/harness_maker/templates/skills/targeted-test-selection/SKILL.md.j2",
    "src/harness_maker/templates/rubrics/claude_md.yaml.j2",
    "src/harness_maker/templates/settings/Production.json.j2",
    "src/harness_maker/templates/settings/Side.json.j2",
}

# The claim under removal: "oracle blocks are pytest / ruff / mypy output". Matched MULTILINE
# — one historical instance of a claim in this repo spanned a line break, which a line-oriented
# matcher cannot catch by construction ([fail:design] prose-refactor-removal-sweep-gaps).
_TRIPLE_CLAIM = re.compile(
    r"oracle[^.]{0,120}?`?pytest`?\s*/\s*`?ruff`?\s*/\s*`?mypy`?",
    re.IGNORECASE | re.DOTALL,
)

# ADR-009's general principle, which must be PRESENT — asserting only the triple's absence
# would pass on a rule generalised into a sentence that adjudicates nothing.
_PRINCIPLE = re.compile(
    r"non-zero.{0,200}?evidence only when.{0,200}?parsed",
    re.IGNORECASE | re.DOTALL,
)


def _anchored_surfaces() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in SRC.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".j2", ".md", ".json", ".yaml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if ANCHOR in text:
            out[str(path.relative_to(ROOT))] = text
    return out


def test_anchored_population_is_exactly_the_expected_set() -> None:
    """Non-emptiness is not enough — a dropped anchor must fail loudly rather than shrink the
    population silently, which would make every assertion below vacuous."""
    found = set(_anchored_surfaces())
    assert found, "discovery found zero anchored surfaces — the anchor or the scan is broken"
    assert found == EXPECTED_ANCHORED, (
        f"anchored surface set drifted.\n  missing: {sorted(EXPECTED_ANCHORED - found)}\n"
        f"  unexpected: {sorted(found - EXPECTED_ANCHORED)}"
    )


@pytest.mark.parametrize("rel", sorted(EXPECTED_ANCHORED))
def test_no_anchored_surface_asserts_a_fixed_command_set(rel: str) -> None:
    text = _anchored_surfaces()[rel]
    hit = _TRIPLE_CLAIM.search(text)
    assert hit is None, (
        f"{rel} still asserts the oracle runs a fixed pytest/ruff/mypy set: {hit.group(0)!r}"
    )


def test_the_general_exit_code_principle_is_present() -> None:
    """ADR-009. The pytest-specific `exit=5` rule was generalised, not deleted; if the
    replacement said nothing adjudicable, a triple-absence assertion alone would pass."""
    body = (SRC / "templates" / "agents" / "code-verifier_body.md.j2").read_text(encoding="utf-8")
    assert _PRINCIPLE.search(body), (
        "code-verifier_body.md.j2 lost the general 'a tool that did not parse the subject is an "
        "absent oracle, not a failing one' principle"
    )


def test_new_oracle_surfaces_must_be_anchored_or_explicitly_deferred() -> None:
    """The complement scan. Without it the anchor set is self-declared by the very artifacts
    being fixed, so a newly added surface asserting a fixed command set is invisible.
    """
    orphans: list[str] = []
    for path in SRC.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".j2", ".md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(ROOT))
        # DESCRIBES the command set, not merely NAMES the module. `command_registry.py` and
        # `hm.py` carry the module name as a dispatch-table string and say nothing about what
        # the oracle runs; requiring an anchor from them would be noise that trains the next
        # reader to add anchors reflexively, which is how an anchor set stops meaning anything.
        describes_oracle = "oracle_blocks" in text or (
            "second_opinion_oracle" in text
            and any(k in text.lower() for k in ("oracle block", "oracle for", "gathered"))
        )
        if not describes_oracle:
            continue
        if ANCHOR in text or rel in DEFERRED_SURFACES:
            continue
        orphans.append(rel)
    assert not orphans, (
        "these surfaces describe the oracle but carry neither the anchor nor an entry in "
        f"DEFERRED_SURFACES: {sorted(orphans)}"
    )


def test_deferred_surfaces_all_exist() -> None:
    """A deferral list that names a moved or deleted file silently shrinks the complement
    scan's exemptions into meaninglessness."""
    missing = [rel for rel in DEFERRED_SURFACES if not (ROOT / rel).exists()]
    assert not missing, f"DEFERRED_SURFACES names non-existent paths: {sorted(missing)}"
