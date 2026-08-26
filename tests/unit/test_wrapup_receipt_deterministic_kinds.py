"""AC-004 — the delegate stops producing deterministically-invalid receipts.

The subject is the PRODUCER; this file covers the CONSUMER half that ADR-002 assigns to
`wrapup_receipt` — `_confined` (ADR-003) and the `WrapupReceipt` field shapes. The
`promotion-arithmetic` check is deliberately NOT under test for change: ADR-002 makes that
defect producer-only because deriving the count would make the anti-fabrication check
(`wrapup_receipt.py:351-353`) structurally unraisable.
`test_promotion_arithmetic_check_is_unchanged`
is the regression guard for that decision, not a formality — it must go red if a later edit
derives the number.

The golden rows are the SSOT (PLAN-nonmechanical-ac-binding ADR-003): loaded from the machine
SPEC, never inlined. Their provenance is the 15 mismatch rows recorded in
`.claude/observability/delegation.jsonl` between 2026-08-01 and 2026-08-23, before any fix
existed.

Wrong implementations these assertions reject:
  1. `_confined` unchanged — a contained worktree-absolute path still raises
     `document-escapes-root` (the structural false positive on the truthful path);
  2. `_confined` widened to accept ANY absolute path — `/etc/hostname` would then satisfy
     reconciliation, which is exactly review F-04. Asserted as a NEGATIVE with a reachable
     fixture, per `[fail:test] assertion-invariant-over-named-dimension` instance 14;
  3. a fix applied to `documents_updated` only — `record_path` is `_confined`'s other caller
     and carries its own positive and negative case;
  4. the mismatch rate reduced by weakening detection — the three claim-based kinds each
     assert they still fire.

Phase A.4 — justified passes (3 of 13 in this file). All three are negatives that are
vacuously true while the wrong construct does not yet exist, each with a RED positive sibling
that forces it into existence:
  * `test_confined_still_rejects_an_escaping_absolute_path` and
    `test_confined_still_rejects_dotdot_and_symlink_escapes` — true today because `_confined`
    rejects EVERY absolute path. They go red the moment the widening is done carelessly
    (accept any absolute). Sibling: `test_confined_accepts_a_contained_absolute_path`.
  * `test_schema_still_forbids_an_unobserved_extra_field` — true today via `extra="forbid"`.
    It goes red if the widening is done with `extra="allow"` instead of named fields.
    Sibling: `test_schema_accepts_the_shapes_the_delegate_actually_emits`.

Phase A.4 (round 2) — five MORE justified passes appeared after the round-1 repair (two in
the first bullet, three in the second — 3 + 5 = 8 of this file's 13, leaving 5 that were
genuinely red before the fix), and they
are justified by ADR-002 rather than by a pending fix:
  * `[promotion-arithmetic]` (expected `[]`) and `test_promotion_arithmetic_check_is_unchanged`
    both pass today and must KEEP passing. ADR-002 makes that defect producer-only precisely
    so this consumer check survives; the pair is the regression guard for that decision. The
    mutation they reject is not the pending fix but a FORBIDDEN one — deriving
    `promotion_candidates` from `promoted + skipped`, which makes the check unraisable.
  * `[wiki-missing]`, `[failure-missing]`, `[promotion-missing]` (each expecting its own kind)
    pass because detection works today. They are the "do not weaken detection" guard that
    SPEC AC-004 and the PLAN's Contract Boundaries both state explicitly: a fix that lowered
    the mismatch RATE by silencing these kinds would turn them red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_maker.spec_machine import load_golden_table
from harness_maker.wrapup_receipt import WrapupReceipt, _confined, parse_receipt, reconcile

_REPO = Path(__file__).resolve().parents[2]
_SPEC = _REPO / "specs" / "SPEC-render-observability-audit.machine.yaml"
_ROWS = load_golden_table(_SPEC, "AC-004")
_DETERMINISTIC = {"receipt-unparseable", "document-escapes-root", "promotion-arithmetic"}

# The raw delegate reply whose shapes tripped `extra_forbidden` on run hm-receipt.vvv0sGJy:
# `steps_skipped` as a list and `drift_verdict` as an object. Kept as TEXT because
# `parse_receipt` is the subject and it takes a string — building a model here would bypass it.
_DELEGATE_RAW_JSON = json.dumps(
    {
        "schema_version": 1,
        "stage": "wrapup",
        "record_path": "CHANGELOG.md",
        "wiki_slugs": [],
        "failure_slugs": [],
        "promotion_candidates": 0,
        "promoted_slugs": [],
        "promotion_skips": [],
        "documents_updated": ["CHANGELOG.md"],
        "steps_skipped": ["Step 2 (verification pass)"],
        "drift_verdict": {"result": "scope_violation"},
    }
)


def _kinds(result) -> list[str]:
    return [m.kind for m in result.mismatches]


def _row_id(row) -> str:
    return str(row.input.get("kind", "row"))


# ── the golden table: three deterministic kinds absent, three claim kinds still reported ──


@pytest.mark.parametrize("row", _ROWS, ids=[_row_id(r) for r in _ROWS])
def test_deterministic_receipt_mismatch_kinds_absent(row, tmp_path: Path) -> None:
    """Each row's `expected` is the kind list a CORRECT delegate run must produce.

    Two oracle bodies, because the two kinds live on different code paths — `load_golden_table`
    is data-loading only and `f(**input) == expected` is explicitly NOT the contract
    (PLAN-nonmechanical-ac-binding ADR-003):

    * `receipt-unparseable` is produced by `main()`'s raw-JSON branch via `parse_receipt`
      (`wrapup_receipt.py:589`), never by `reconcile`. Routing it through `reconcile` on a
      pre-built `WrapupReceipt` made it a tautology — the assertion held identically whether
      or not the schema was ever widened, because the object under test could not carry the
      offending fields in the first place.
    * every other kind is a `reconcile` mismatch.
    """
    kind = str(row.input["kind"])
    expected = list(row.expected)

    if kind == "receipt-unparseable":
        receipt, error = parse_receipt(_DELEGATE_RAW_JSON)
        # `expected: []` means "no unparseable outcome" — i.e. the raw reply parses.
        assert expected == []
        assert error == "", error
        assert receipt is not None
        assert receipt.steps_skipped == ("Step 2 (verification pass)",)
        assert receipt.drift_verdict == {"result": "scope_violation"}
        return

    built = _build_case(kind, tmp_path)
    result = reconcile(
        built.receipt,
        base_root=built.root,
        worktree_root=built.root,
        vault_root=built.vault,
    )
    assert _kinds(result) == expected


class _Case:
    def __init__(self, receipt: WrapupReceipt, root: Path, vault: Path | None = None) -> None:
        self.receipt = receipt
        self.root = root
        # `promotion-missing` is unreachable with `vault_root=None`: that branch marks the
        # claim `unverified` instead of raising. A fixture that omits the vault therefore
        # cannot express the defect it names — the shape
        # `[fail:test] assertion-invariant-over-named-dimension` calls an unreachable fixture.
        self.vault = vault


def _base_receipt(root: Path, **over: object) -> WrapupReceipt:
    (root / "CHANGELOG.md").write_text("x", encoding="utf-8")
    fields: dict[str, object] = {
        "schema_version": 1,
        "stage": "wrapup",
        "record_path": "CHANGELOG.md",
        "wiki_slugs": (),
        "failure_slugs": (),
        "promotion_candidates": 0,
        "promoted_slugs": (),
        "promotion_skips": (),
        "documents_updated": ("CHANGELOG.md",),
    }
    fields.update(over)
    return WrapupReceipt(**fields)  # type: ignore[arg-type]


def _build_case(kind: str, tmp_path: Path) -> _Case:
    """One fixture per golden row. A correct delegate emits the deterministic three cleanly."""
    root = tmp_path / "repo"
    root.mkdir()
    if kind == "document-escapes-root":
        # The delegate reports a path inside its own worktree, in ABSOLUTE form. Contained,
        # therefore truthful, therefore must not raise.
        return _Case(_base_receipt(root, documents_updated=(str(root / "CHANGELOG.md"),)), root)
    if kind == "promotion-arithmetic":
        return _Case(
            _base_receipt(
                root,
                promotion_candidates=1,
                promoted_slugs=("a",),
                promotion_skips=(),
            ),
            root,
        )
    if kind == "receipt-unparseable":
        return _Case(_base_receipt(root), root)
    if kind == "wiki-missing":
        return _Case(_base_receipt(root, wiki_slugs=("never-written",)), root)
    if kind == "failure-missing":
        return _Case(_base_receipt(root, failure_slugs=("never-written",)), root)
    if kind == "promotion-missing":
        vault = tmp_path / "vault"
        (vault / "99_HM").mkdir(parents=True)
        # NO note is written, deliberately. An earlier version wrote an unrelated one and
        # claimed it made the fixture discriminate; review round 2 showed it is inert TWICE
        # over — `_vault_slugs` short-circuits to an empty set while `vault_folders` is unset,
        # and even without that short-circuit the regression it named (an unrelated note
        # satisfying an unrelated claim) needs the CLAIMED slug to coincide with a real note's,
        # which this fixture never arranged. Dressing that suggests evidence it does not carry
        # is worse than none: the next reader skims the code, not the comment.
        # What the row does earn: `promotion-missing` is unreachable at `vault_root=None`
        # (that branch marks the claim `unverified`), so supplying a vault is what makes the
        # kind reachable at all, and the row goes red if detection is weakened.
        return _Case(
            _base_receipt(root, promotion_candidates=1, promoted_slugs=("never-promoted",)),
            root,
            vault=vault,
        )
    raise AssertionError(f"golden row names an unhandled kind: {kind}")


# ── `_confined`: both callers, both directions ────────────────────────────────────────────


def test_confined_accepts_a_contained_absolute_path(tmp_path: Path) -> None:
    """Rejects implementation 1. The predicate must ask 'escapes the root', not 'is absolute'."""
    base = tmp_path / "repo"
    (base / "work-docs").mkdir(parents=True)
    target = base / "work-docs" / "PLAN-x.md"
    target.write_text("x", encoding="utf-8")
    assert _confined(base, str(target)) == target.resolve()


def test_confined_still_rejects_an_escaping_absolute_path(tmp_path: Path) -> None:
    """Rejects implementation 2 — the F-04 property. Reachable fixture, not a prose negative."""
    base = tmp_path / "repo"
    base.mkdir()
    assert _confined(base, "/etc/hostname") is None


def test_confined_still_rejects_dotdot_and_symlink_escapes(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("s", encoding="utf-8")
    base = tmp_path / "repo"
    base.mkdir()
    (base / "link").symlink_to(outside)
    assert _confined(base, "../outside/secret") is None
    assert _confined(base, "link/secret") is None


def test_record_path_accepts_contained_absolute_and_rejects_escaping(tmp_path: Path) -> None:
    """Rejects implementation 3 — `_confined`'s second caller changes with it."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "CHANGELOG.md").write_text("x", encoding="utf-8")

    contained = _base_receipt(root, record_path=str(root / "CHANGELOG.md"))
    assert "document-escapes-root" not in _kinds(
        reconcile(contained, base_root=root, worktree_root=root)
    )

    escaping = _base_receipt(root, record_path="/etc/hostname")
    assert "document-escapes-root" in _kinds(
        reconcile(escaping, base_root=root, worktree_root=root)
    )


# ── the anti-fabrication check must survive ───────────────────────────────────────────────


def test_promotion_arithmetic_check_is_unchanged(tmp_path: Path) -> None:
    """ADR-002's regression guard: a receipt whose counts DISAGREE must still be caught.

    Goes red the moment `promotion_candidates` is derived from `promoted + skipped`, because
    the two sides would then be equal by construction and no receipt could fail this.
    """
    root = tmp_path / "repo"
    root.mkdir()
    fabricated = _base_receipt(
        root, promotion_candidates=4, promoted_slugs=("a", "b", "c"), promotion_skips=()
    )
    assert "promotion-arithmetic" in _kinds(
        reconcile(fabricated, base_root=root, worktree_root=root)
    )


# ── schema: widened to observed shapes, never `extra="allow"` ─────────────────────────────


def test_schema_accepts_the_shapes_the_delegate_actually_emits() -> None:
    """Both fields were observed on run hm-receipt.vvv0sGJy: a list and an object."""
    receipt, error = parse_receipt(_DELEGATE_RAW_JSON)
    assert error == "", error
    assert receipt is not None
    assert receipt.steps_skipped == ("Step 2 (verification pass)",)
    assert receipt.drift_verdict == {"result": "scope_violation"}


def test_schema_still_forbids_an_unobserved_extra_field() -> None:
    """Widening must be enumerated, never `extra="allow"` (PLAN R4)."""
    _, error = parse_receipt(
        json.dumps(
            {
                "schema_version": 1,
                "stage": "wrapup",
                "not_a_real_field": 1,
            }
        )
    )
    assert "does not match the schema" in error, error
