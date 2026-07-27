"""AC-001/002/003/005/006 — the two context-carry rules reach every harness, and bite.

The rules exist because the main loop is 87.9% of spend at 70.0% carry, and two habits —
unbounded search/inspection output (16.0% of carried context) and re-sending a file body the
context already holds (3.8%) — are avoidable. Measured in
`work-docs/RESEARCH-context-carry-economics-2026-07-28.md`.

**AC-002 is the load-bearing criterion here, not AC-001.** A section that exists and says
"be mindful of context" satisfies "the rules render" and changes nothing. The required
tokens are fixed in PLAN ADR-006, chosen BEFORE the rule text was written, so the text was
made to satisfy the gate rather than the gate fitted to the text. Every assertion below is
scoped to the individual BULLET, not the section: the section contains both rules, so a
section-wide check for `Edit` would pass on the rewrite rule while the search rule was
gutted — the scoping defect recorded as `PLAN-token-economy-step-pruning` ADR-021.
"""

from __future__ import annotations

import re
import tempfile
from functools import cache
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref

# Stops at the next `##` heading OR the first user marker, whichever comes first. The
# rendered variants are followed by `<!-- @hm:user`; this repo's hand-maintained CLAUDE.md
# is followed by another `##`. A slice that only knew the first shape silently failed to
# match on AC-003's subject and asserted nothing about it.
_SECTION = re.compile(r"^## Context discipline\n.*?(?=^## |^<!-- @hm:user)", re.M | re.S)
_BULLET = re.compile(r"^- \*\*.*?(?=^- \*\*|\Z)", re.M | re.S)

_CAP_CHARS = 2000  # SPEC AC-005 / PLAN ADR-006 — instruction bytes are carried bytes.
_INSPECTION_TOOLS = ("cat", "head", "ls", "find")
# `Read` alone was an alternative here and the mutation receipt killed it: the rewrite
# bullet says "requires a prior `Read`" in its EXPLANATION, so the conditional clause
# could be deleted — turning the rule into the false bare "prefer Edit" (PLAN ADR-004) —
# while the token survived elsewhere in the same bullet. These two phrases are the
# clause itself, one per locale.
_PRECONDITION = ("already read", "이미 읽은")

# `ja` is not a third translation: it is the documented unknown-locale fallback. It selects
# the `.en` FILE while `config.locale` stays `ja`, so it proves the two locale mechanisms
# (file selection and the in-partial branch) agree. PLAN ADR-002 reasoned this out; this
# renders it.
_LOCALES = ("en", "ko", "ja")


@cache
def _claude_md(preset: Preset, locale: str) -> str:
    """CLAUDE.md renders to `../CLAUDE.md`, i.e. the PARENT of the output dir."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / ".claude"
        out.mkdir()
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(
                synthesize(
                    ProjectProfile(),
                    InterviewAnswers(preset=preset, targets=[Target.CLAUDE_CODE], locale=locale),
                ),
                out,
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        return (Path(td) / "CLAUDE.md").read_text(encoding="utf-8")


def _section(text: str) -> str:
    match = _SECTION.search(text)
    assert match is not None, "no `## Context discipline` section — the slice regex is stale"
    return match.group(0)


def _rules(text: str) -> tuple[str, str]:
    """(search rule, rewrite rule), identified by content rather than by position."""
    bullets = _BULLET.findall(_section(text))
    assert len(bullets) == 2, f"expected 2 bullets, got {len(bullets)}"
    search = next(b for b in bullets if "`rg`" in b)
    rewrite = next(b for b in bullets if "`Write`" in b)
    assert search is not rewrite
    return search, rewrite


def _repo_claude_md() -> str:
    return (Path(__file__).resolve().parents[2] / "CLAUDE.md").read_text(encoding="utf-8")


# ── positive controls ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
@pytest.mark.parametrize("locale", _LOCALES)
def test_the_slice_is_not_vacuous(preset: Preset, locale: str) -> None:
    """An empty or runaway section would make every assertion below pass."""
    body = _section(_claude_md(preset, locale))
    assert 300 < len(body) < _CAP_CHARS
    assert body.count("- **") == 2, "the section is not two bullets"


# ── AC-001 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
@pytest.mark.parametrize("locale", _LOCALES)
def test_both_rules_render_in_every_preset_and_locale(preset: Preset, locale: str) -> None:
    """AC-001 — six renders, not one. A ko-only or Side-only omission must fail."""
    search, rewrite = _rules(_claude_md(preset, locale))
    assert search
    assert rewrite


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
def test_the_korean_render_is_actually_korean(preset: Preset) -> None:
    """Every other assertion here passes on an English body in a ko file.

    The required tokens (`rg`, `grep`, `Edit`, `Write`, `| head`) are identifiers and are
    identical in both branches by design, so nothing else distinguishes them. The mutation
    receipt confirmed it: forcing the locale branch to `False` made ko render English and
    the whole file stayed green.
    """
    ko = _section(_claude_md(preset, "ko"))
    en = _section(_claude_md(preset, "en"))
    assert "검색·조회 출력에 상한을 걸 것" in ko
    assert "Bound what search" not in ko
    assert "Bound what search and inspection return" in en
    assert "검색" not in en


def test_the_unknown_locale_fallback_renders_the_english_rules() -> None:
    """`ja` selects the `.en` file while `config.locale` stays `ja` (PLAN ADR-002).

    If the in-partial branch keyed off the filename instead of `config.locale`, or if the
    two disagreed, this would render Korean text into an English file or nothing at all.
    """
    body = _section(_claude_md(Preset.PRODUCTION, "ja"))
    assert "Bound what search and inspection return" in body
    assert "검색" not in body


# ── AC-002 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
@pytest.mark.parametrize("locale", _LOCALES)
def test_the_search_rule_names_its_tools_and_a_concrete_bound(preset: Preset, locale: str) -> None:
    """AC-002 — an exhortation with no tool and no bound must not pass (PLAN ADR-006)."""
    search, _ = _rules(_claude_md(preset, locale))
    assert "`rg`" in search
    assert "`grep`" in search
    named = sum(1 for tool in _INSPECTION_TOOLS if f"`{tool}`" in search)
    assert named >= 2, f"only {named} inspection tools named"
    assert "| head" in search or "head_limit" in search, "no concrete output bound"
    assert re.search(r"\d", search), "no numeral — 'pipe through head' is not a bound"


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
@pytest.mark.parametrize("locale", _LOCALES)
def test_the_rewrite_rule_states_its_precondition(preset: Preset, locale: str) -> None:
    """AC-002 / PLAN ADR-004 — a bare "prefer Edit" is FALSE and must fail.

    69% of `Write` bytes create new files. The rule is only true under the condition that
    the file is already in the context from a `Read`, so the condition is not decoration.
    """
    _, rewrite = _rules(_claude_md(preset, locale))
    assert "`Edit`" in rewrite
    assert "`Write`" in rewrite
    assert any(p in rewrite for p in _PRECONDITION), "no prior-read precondition"


# ── AC-005 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
@pytest.mark.parametrize("locale", _LOCALES)
def test_the_instruction_stays_inside_its_own_budget(preset: Preset, locale: str) -> None:
    """AC-005 — Phase 3 of the prior plan spent 3,765 chars against an unmeasured saving."""
    assert len(_section(_claude_md(preset, locale))) <= _CAP_CHARS


# ── AC-003 ─────────────────────────────────────────────────────────────────────


def test_this_repo_carries_its_own_rule() -> None:
    """AC-003 — the repo whose transcripts produced the measurement is not exempt.

    `CLAUDE.md` here is hand-maintained and is NOT rendered from `templates/claude-md/`, so
    AC-001 says nothing about it. Held to the same predicates rather than to its own.
    """
    search, rewrite = _rules(_repo_claude_md())
    assert "`rg`" in search
    assert "`grep`" in search
    assert "| head" in search or "head_limit" in search
    assert "`Edit`" in rewrite
    assert "`Write`" in rewrite
    assert any(p in rewrite for p in _PRECONDITION)


# ── AC-006 ─────────────────────────────────────────────────────────────────────


def test_user_marker_content_survives_the_new_section() -> None:
    """AC-006 — adding a `##` section must not disturb the marker merge.

    Exercised through `block_merge.merge`, which is where the preservation contract lives.
    `render()` writes a fresh tree and never merges — an earlier version of this test called
    it and "failed" on user content that the render path was never responsible for. Testing
    the wrong entry point produces a red that says nothing about the product.

    Both markers carry non-empty content: with empty bodies the assertions would hold on two
    empty strings and gate nothing.
    """
    from harness_maker.block_merge import merge

    mine = "MY PROJECT RULE: never use tabs."
    extra = "MY EXTENSION: deploy runs on Fridays."
    existing = (
        "# CLAUDE.md — existing\n\n"
        f"<!-- @hm:user:project-rules -->\n{mine}\n<!-- @hm:/user:project-rules -->\n\n"
        f"<!-- @hm:user:extensions -->\n{extra}\n<!-- @hm:/user:extensions -->\n"
    )
    merged, _report = merge(existing, _claude_md(Preset.PRODUCTION, "en"))
    assert mine in merged, "user project-rules content was dropped"
    assert extra in merged, "user extensions content was dropped"
    assert "## Context discipline" in merged, "the new section did not survive the merge"
