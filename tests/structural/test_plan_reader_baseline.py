"""AC-003 — no PLAN frontmatter key may have a reader and no writer.

SPEC-plan-stage-absorption moves the PLAN document's authorship from `/hm:plan` to
`/hm:execute` Step 0. The failure this file exists to catch is the one the SPEC's IRR-003
names: `verify.md.j2` Check 6 reads `spec_need_verdict` and treats an ABSENT key as
`PASS (N-A)`, so deleting the only writer does not make anything red — it makes the gate
permanently green. That is `absent-case = feature black hole` (count:8).

**Nothing here is a hand-written list.** Both the author set and the key set are DISCOVERED:
an author is any template carrying a `type: plan` frontmatter block, and the keys are the ones
that block declares. This repo hand-listed a reader set three times and was wrong all three
(`new-marker-content-field-must-update-every-reader`, count:3), so the discovery is the point
— a list here would inherit exactly that defect.

The corpus is the template tree, not the Python import graph: no module under
`src/harness_maker/` reads PLAN frontmatter (every `task_slug` hit there belongs to the
autopilot marker). The SPEC records that correction under AC-003.

**Phase A.4 note — one test here passes before the implementation exists, deliberately.**
`test_no_plan_frontmatter_key_is_orphaned` is a NEGATIVE invariant: while `plan.md.j2` still
writes every key, nothing is orphaned, so it is vacuously true today. It goes red the moment
Phase 4 deletes that template without Phase 1 having made `execute.md.j2` a writer — which is
the wrong implementation it forbids. Its RED positive sibling is
`test_execute_is_a_plan_author` in this same file, which fails now and forces the construct
(an `execute.md.j2` that authors PLAN frontmatter) into existence.
"""

from __future__ import annotations

import re
from pathlib import Path

import harness_maker
from harness_maker import spec_need

_TEMPLATES = Path(harness_maker.__file__).parent / "templates"

# A frontmatter key line: `key:` or `key: value`, optionally indented, and optionally behind an
# inline Jinja tag. The tag matters: both `plan.md.j2` and `execute.md.j2` write
# `{% if config.dev_mode == 'spec-driven' %}spec_need_verdict: …` on one line, and a regex that
# stops at `{%` ends the block there. That is not cosmetic — it drops `spec_need_verdict` from
# the authored set, which drops it from the universe, which makes the orphan check below pass
# VACUOUSLY for the exact pair whose absent case defeats verify Check 6.
_KEY_LINE = re.compile(r"^(?P<indent>\s*)(?:\{%.*?%\})?(?P<key>[a-z_][a-z0-9_]*):(?:\s|$)")
_TYPE_PLAN = re.compile(r"^\s*type:\s*plan\s*$")

# Used ONLY when the author set is empty, to keep the orphan check from passing vacuously.
_ORPHAN_PROBE = re.compile(
    r"^\s*(spec_need_\w+|validator_outcome|interview_rounds|derived_from|loop_mode"
    r"|halt_reason|halt_note|task_slug):",
    re.MULTILINE,
)


def _template_files() -> list[Path]:
    """Every shipped template, found by walking the tree — never a listed set."""
    return sorted(p for p in _TEMPLATES.rglob("*") if p.is_file() and p.suffix in {".j2", ".md"})


def _plan_frontmatter_blocks(text: str) -> list[list[str]]:
    """The contiguous key-line runs that contain `type: plan`.

    A PLAN author declares the document's frontmatter contract somewhere in its prose; the
    block is bounded by the first line on either side that is not a key line at the same
    indentation. That is deliberately syntactic: it must keep working when the block moves
    from `plan.md.j2` to `execute.md.j2`.
    """
    lines = text.splitlines()
    blocks: list[list[str]] = []
    for i, line in enumerate(lines):
        if not _TYPE_PLAN.match(line):
            continue
        m = _KEY_LINE.match(line)
        if m is None:  # pragma: no cover - `type: plan` is itself a key line
            continue
        indent = m.group("indent")
        lo = i
        while lo > 0:
            prev = _KEY_LINE.match(lines[lo - 1])
            if prev is None or prev.group("indent") != indent:
                break
            lo -= 1
        hi = i + 1
        while hi < len(lines):
            nxt = _KEY_LINE.match(lines[hi])
            if nxt is None or nxt.group("indent") != indent:
                break
            hi += 1
        blocks.append(lines[lo:hi])
    return blocks


#: A template also authors a key by CALLING the verb that writes it — the keys are not in any
#: declared block. `spec_need frontmatter-upsert` is that case: SPEC-plan-stage-absorption's
#: review found that DECLARING `spec_need_verdict` in Step 0's block forced an unjudged guess
#: which the preserving writer then kept forever, so the declaration was removed and Step 0.1's
#: verb call is now the only author. A detector that only reads declared blocks would have
#: called `verify.md.j2` orphaned at that moment — a reader with no writer — when the writer had
#: simply changed shape. The key set comes from the owning module, never a second list here.
_VERB_AUTHORED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("spec_need frontmatter-upsert", tuple(spec_need._SPEC_NEED_KEYS)),
)


def _authored_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for block in _plan_frontmatter_blocks(text):
        for line in block:
            m = _KEY_LINE.match(line)
            if m is not None:
                keys.add(m.group("key"))
    for verb, written in _VERB_AUTHORED:
        if verb in text:
            keys.update(written)
    return keys


def plan_authors() -> dict[str, set[str]]:
    """{template path relative to templates/: the PLAN frontmatter keys it declares}."""
    out: dict[str, set[str]] = {}
    for path in _template_files():
        keys = _authored_keys(path.read_text(encoding="utf-8"))
        if keys:
            out[path.relative_to(_TEMPLATES).as_posix()] = keys
    return out


def plan_key_readers(universe: set[str]) -> dict[str, set[str]]:
    """{template: which of `universe` it mentions}, for templates that are not authors."""
    authors = set(plan_authors())
    out: dict[str, set[str]] = {}
    for path in _template_files():
        rel = path.relative_to(_TEMPLATES).as_posix()
        if rel in authors:
            continue
        text = path.read_text(encoding="utf-8")
        mentioned = {k for k in universe if re.search(rf"\b{re.escape(k)}\b", text)}
        if mentioned:
            out[rel] = mentioned
    return out


#: The key space the readers are scanned against when it cannot be derived from an author.
_ORPHAN_KEYS: set[str] = {
    "spec_need_verdict",
    "spec_need_target",
    "validator_outcome",
    "interview_rounds",
    "derived_from",
    "loop_mode",
    "halt_reason",
    "halt_note",
    "task_slug",
    "objective",
    "status",
}


def _orphan_probe_universe() -> set[str]:
    """Re-derive the key space from the readers when no author declares one.

    Without this the orphan check would compare every reader against an empty universe,
    find nothing "mentioned", and report zero orphans — passing precisely when the document
    has lost its author, which is the state it exists to catch.
    """
    found: set[str] = set()
    for path in _template_files():
        for m in _ORPHAN_PROBE.finditer(path.read_text(encoding="utf-8")):
            found.add(m.group(1))
    return found


def test_at_least_one_template_authors_the_plan_frontmatter() -> None:
    """The document outlives the stage. If nothing declares its shape, nothing writes it."""
    assert plan_authors(), (
        "no template carries a `type: plan` frontmatter block — the PLAN document has no "
        "author, so every reader is orphaned"
    )


def test_execute_is_a_plan_author() -> None:
    """`/hm:execute` Step 0 becomes the PLAN's author (SPEC AC-003/AC-010, ADR-002).

    RED until Phase 1 lands. This is the positive sibling that forces the construct the
    orphan invariant below is written against.
    """
    authors = plan_authors()
    assert "stages/execute.md.j2" in authors, (
        "stages/execute.md.j2 does not declare a `type: plan` frontmatter block; "
        f"current authors: {sorted(authors)}"
    )
    # Being *an* author is not enough. `execute.md.j2` declares two blocks — the PLAN's own
    # frontmatter and the loop per-iter one — and only the first carries the keys other
    # templates read. Asserting mere membership would stay green if that block were deleted
    # and the per-iter one left behind, which is the wrong implementation this guards.
    declared = authors["stages/execute.md.j2"]
    read_by_others = plan_key_readers(_ORPHAN_KEYS)
    needed: set[str] = set().union(*read_by_others.values()) if read_by_others else set()
    missing = sorted(needed - declared)
    assert not missing, (
        "stages/execute.md.j2 is an author but does not declare the keys other templates "
        f"read from the PLAN: {missing}"
    )


def test_no_plan_frontmatter_key_is_orphaned() -> None:
    """Every PLAN key some template reads must be declared by some template that writes it.

    Negative invariant — see the module docstring for why it is green today and what makes
    it go red.
    """
    authors = plan_authors()
    written: set[str] = set().union(*authors.values()) if authors else set()
    # The universe is NEVER derived from the authors alone. If it were, a key no author
    # declares would also be a key no reader is scanned for, and the check would report zero
    # orphans precisely when one exists — which is how this test passed vacuously for
    # `spec_need_verdict` until the mutation-receipt probe forced a single red line.
    universe = written | _ORPHAN_KEYS | _orphan_probe_universe()
    readers = plan_key_readers(universe)
    orphans = {
        template: sorted(keys - written) for template, keys in readers.items() if keys - written
    }
    assert not orphans, (
        "PLAN frontmatter keys are read by a template but written by none — the reader "
        f"cannot fail loudly, it just never fires: {orphans}"
    )
