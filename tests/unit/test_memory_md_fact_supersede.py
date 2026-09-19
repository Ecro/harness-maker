"""AC-003 (SPEC-mission-context-loop) — a correction replaces the fact in place.

The capture contract (S2) relies on `upsert-wiki`'s replace-by-slug: a correction reuses the
subject slug and the entry becomes the current truth plus one `Supersedes:` line. Replace-by-key
is an invariant of any upsert, and the expected body is the test's own second input, so the
oracle never reads `memory_md`. The domain is the writer's canonical bodies: it strips surrounding
newlines and refuses heading-shaped lines and marker strings, so those are excluded, not asserted.

This whole module passes before any change in this task, by design: `memory_md` is a
`Do not change` boundary, and these are REGRESSION pins on the semantics the capture contract
depends on (AC-003 is a regression guard, per the SPEC's machine note). The RED positive
siblings that force this task's behaviour into existence are the AC-001/002 tests
(`test_memory_retrieve_root.py`) and the render tests of AC-004..007.

The second test pins the hazard ADR-007 exists for: a same-slug upsert under ANOTHER category
rewrites the heading and discards the fact. It documents why wrapup 5.1.0 must never reuse a
`[wiki:fact]` slug and the skill must reuse only fact slugs; if the writer ever grows a category
guard, this test tells the reader the prose rule became redundant.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import memory_md

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_SLUG = st.from_regex(r"[a-z][a-z0-9]{2,10}(-[a-z0-9]{2,8}){0,2}", fullmatch=True)
_LINE = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,:;()/-_'",
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() == s and not s.startswith("#"))
_BODY = st.lists(_LINE, min_size=1, max_size=4).map("\n".join)


def _fresh_root() -> Path:
    root = Path(tempfile.mkdtemp())
    mem = root / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "wiki.md").write_text(
        f"# Wiki Index\n\n{memory_md.OPEN_MARKER}\n{memory_md.CLOSE_MARKER}\n", encoding="utf-8"
    )
    return root


def _entry(root: Path, slug: str) -> tuple[list[str], list[str]]:
    """(matching headings, body lines of the first match) — parsed from the file, not the API."""
    lines = (root / ".claude" / "memory" / "wiki.md").read_text(encoding="utf-8").split("\n")
    headings = [i for i, ln in enumerate(lines) if ln.startswith("## [") and f"] {slug} |" in ln]
    if not headings:
        return [], []
    body: list[str] = []
    for ln in lines[headings[0] + 1 :]:
        if ln.startswith("## [") or ln == memory_md.CLOSE_MARKER:
            break
        body.append(ln)
    while body and body[-1] == "":
        body.pop()
    return [lines[i] for i in headings], body


@given(slug=_SLUG, body1=_BODY, body2=_BODY, old_claim=_LINE)
def test_ac_003_same_slug_upsert_replaces_and_keeps_supersedes(
    slug: str, body1: str, body2: str, old_claim: str
) -> None:
    root = _fresh_root()
    corrected = f"{body2}\nSupersedes: {old_claim} (2026-09-19)"
    memory_md.upsert_wiki(root, slug, "fact", body1, today="2026-09-18")
    memory_md.upsert_wiki(root, slug, "fact", corrected, today="2026-09-19")
    headings, body = _entry(root, slug)
    assert len(headings) == 1
    assert headings[0] == f"## [wiki:fact] {slug} | 2026-09-19"
    assert "\n".join(body) == corrected.strip("\n")


def test_cross_category_upsert_on_fact_slug_rewrites_heading() -> None:
    root = _fresh_root()
    memory_md.upsert_wiki(
        root, "staging-api-rate-limit", "fact", "Staging throttles at 10 req/s.", today="2026-09-18"
    )
    memory_md.upsert_wiki(
        root,
        "staging-api-rate-limit",
        "architecture",
        "Task summary: added a retry wrapper.",
        today="2026-09-19",
    )
    headings, body = _entry(root, "staging-api-rate-limit")
    assert headings == ["## [wiki:architecture] staging-api-rate-limit | 2026-09-19"]
    assert body == ["Task summary: added a retry wrapper."]
