"""P7 exit 2 — every changed baseline key is attributed, or CI goes red.

R5 in the PLAN: `surface_baseline.json` is silently rebaselined by whichever phase trips it.
The mitigation is ADR-010 (P7 owns it) plus this file, and the split matters: ownership is a
convention and conventions are what `ratchet-rebaselined-by-its-own-subject` (count:2) got
past twice. This test is the part that does not depend on anyone remembering.

**What it compares.** The committed `surface_baseline.json` against the last committed
version in git, key by key. Any key whose value moved must appear in `BASELINE-DELTA-P7.md`.
A rebaseline with no attribution row fails here — the author has to write down what moved
and why, in the same commit, or the suite stays red.

It is deliberately NOT a check that the attribution is *correct*. Nothing mechanical can
know whether "P3 added the emit line" is true. What it can enforce is that a human-readable
claim exists for every moved number, which is the difference between a delta someone chose
and a delta that happened.
"""

from __future__ import annotations

import json
import subprocess
from functools import cache
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]
_BASELINE = _REPO / "tests" / "structural" / "surface_baseline.json"
_DELTA_DOC = _REPO / "work-docs" / "BASELINE-DELTA-P7.md"

#: Keys whose movement is mechanical (they change whenever anything else does) and whose
#: attribution row is therefore generic. Named explicitly rather than skipped by pattern, so
#: adding a real key to this set is a visible edit.
_MECHANICAL_KEYS = frozenset({"render_sha", "payload_digest"})


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    return {prefix: node}


def _git(args: list[str]) -> str | None:
    proc = subprocess.run(
        ["git", *args], cwd=_REPO, capture_output=True, text=True, timeout=30, check=False
    )
    return proc.stdout if proc.returncode == 0 else None


@cache
def _comparison_base() -> str:
    """The revision the baseline is compared against — NOT `HEAD`.

    `HEAD` was the first version and it made this gate **inert in CI**: a clean checkout has
    working tree == HEAD, so `changed_keys()` came back empty and every assertion below
    passed vacuously. The gate could only fail in the window between editing the baseline
    and committing it — and the module docstring *demands* the rebaseline be committed in
    the same commit, so the gate was green precisely in the state it exists to police.
    That is the same "guard that stops binding once the thing it guards happens" shape as
    `ratchet-rebaselined-by-its-own-subject` itself.

    The merge-base against the integration branch keeps the whole branch's delta in view,
    so a committed rebaseline still has to carry its attribution row.
    """
    for ref in ("origin/main", "main"):
        base = _git(["merge-base", "HEAD", ref])
        if base and base.strip():
            return base.strip()
    return "HEAD"


@cache
def _committed_baseline() -> dict[str, Any] | None:
    """The baseline at the comparison base. `None` when unreadable (shallow clone/new file)."""
    proc = subprocess.run(
        ["git", "show", f"{_comparison_base()}:{_BASELINE.relative_to(_REPO).as_posix()}"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        loaded = json.loads(proc.stdout)
    except ValueError:
        return None
    return loaded if isinstance(loaded, dict) else None


def changed_keys() -> list[str]:
    """Flattened keys whose value differs from the committed baseline."""
    old = _committed_baseline()
    if old is None:
        return []
    new = json.loads(_BASELINE.read_text(encoding="utf-8"))
    flat_old, flat_new = _flatten(old), _flatten(new)
    return sorted(k for k in flat_new if flat_old.get(k) != flat_new[k])


def test_the_delta_document_exists() -> None:
    assert _DELTA_DOC.is_file(), "P7 moved baselines with no attribution document"


def test_the_comparison_is_actually_running() -> None:
    """Positive control.

    Every assertion below is vacuous when the git read fails — a shallow clone, a rename, a
    detached state — and it would fail SILENTLY, in the permissive direction. This test is
    what turns "nothing to check" into a visible skip instead of a false green.
    """
    if _committed_baseline() is None:
        pytest.skip("baseline not readable at the comparison base (new file or shallow clone)")
    assert _flatten(_committed_baseline() or {}), "the committed baseline flattened to nothing"


def test_the_comparison_base_is_resolved_against_an_integration_branch() -> None:
    """The regression that made this whole file inert, asserted at the MECHANISM.

    A value assertion (`base != HEAD`) is wrong: a task branch with no commits yet has
    `merge-base(HEAD, main) == HEAD` legitimately, and the working-tree diff is still
    visible, so the gate works. It only breaks when the base is *pinned* to `HEAD` by
    construction — which is what the first version did, and what a one-word edit would
    restore. So assert the resolution path, not the value it happens to produce today.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    whole = source[source.index("def _comparison_base(") : source.index("def _committed_baseline(")]
    # Read the CODE, not the docstring. The docstring below explains the merge-base fix in
    # prose containing every literal asserted here, so slicing it in would let a revert to
    # `return "HEAD"` pass on its own explanation of why that is wrong.
    body = whole[whole.index('"""', whole.index('"""') + 3) + 3 :]
    assert "merge-base" in body, "the comparison base no longer resolves via merge-base"
    assert "origin/main" in body or "main" in body, "no integration branch is consulted"
    # `HEAD` may appear only as the last-resort fallback, never as the first choice.
    assert body.index("merge-base") < body.rindex('return "HEAD"'), (
        "the HEAD fallback precedes the merge-base resolution — the gate is pinned again"
    )


def test_every_changed_key_has_an_attribution_row() -> None:
    """P7 exit criterion 2, and the whole point of this file."""
    if _committed_baseline() is None:
        pytest.skip("baseline not readable from HEAD")
    doc = _DELTA_DOC.read_text(encoding="utf-8")
    unattributed = []
    for key in changed_keys():
        leaf = key.rsplit(".", 1)[-1]
        parent = key.rsplit(".", 2)[-2] if key.count(".") >= 2 else ""
        if leaf in _MECHANICAL_KEYS:
            assert f"`{leaf}`" in doc, f"{leaf} moved and is not even mentioned"
            continue
        # A row must name the subject (the command / variant), not merely the metric —
        # "chars changed" attributed to nothing is not an attribution.
        if parent and f"`{parent}`" not in doc:
            unattributed.append(key)
    assert not unattributed, (
        "baseline keys moved with no row in BASELINE-DELTA-P7.md: "
        + ", ".join(unattributed)
        + " — add the row in the same commit that moved them (ADR-010)"
    )


def test_the_document_names_the_owning_phase_and_the_reason_for_ownership() -> None:
    """A future reader must learn WHY only P7 may touch these, or they will touch them."""
    doc = _DELTA_DOC.read_text(encoding="utf-8")
    assert "ADR-010" in doc
    assert "ratchet-rebaselined-by-its-own-subject" in doc


def test_the_document_states_the_direction_of_the_aggregate() -> None:
    """The finding a reader is most likely to skip past.

    This PLAN raised the shipped surface while being a cost-reduction PLAN. A delta document
    that lists the numbers without saying that is technically complete and practically
    misleading.
    """
    doc = _DELTA_DOC.read_text(encoding="utf-8")
    assert "larger" in doc.lower() or "wrong way" in doc.lower()


def test_the_documented_aggregate_matches_the_actual_baseline() -> None:
    """The number itself, not merely that A number is present.

    The first version asserted the literal `"+5 525" in doc`. Two later fixes grew the review
    template by ~1 590 chars, the real aggregate moved to 361 396, and this assertion stayed
    green on a figure that was now wrong — a gate checking that text EXISTS rather than that
    it is TRUE. That is the same shape as every other defect this change had to fix today, so
    it is closed here rather than noted.
    """
    actual = json.loads(_BASELINE.read_text(encoding="utf-8"))["aggregate_chars"]
    doc = _DELTA_DOC.read_text(encoding="utf-8")
    for variant, value in actual.items():
        # The doc writes numbers with thin spaces for readability (361 396).
        grouped = f"{value:,}".replace(",", " ")
        assert grouped in doc or str(value) in doc, (
            f"aggregate_chars.{variant} is {value} in the baseline but that figure appears "
            f"nowhere in BASELINE-DELTA-P7.md — the attribution went stale"
        )
