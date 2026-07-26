"""The delegated wrapup's OUTPUT contract: a machine receipt, checked against reality.

ADR-006 validates INPUTS; complete inputs do not imply a complete wrapup. CLAUDE.md's
only visibility mechanism for under-promotion is a prose line the agent prints
(`promotion evaluated: N candidates, M promoted`), and delegation puts that line behind
a summarising main loop that would relay it whether the agent printed it, printed
`N=0`, or printed nothing.

So every claim here is reconciled against observable state before the commit. What that
proves is that entries EXIST — never that they are good (ADR-012's stated limit).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

SCHEMA_VERSION = 1

# `## [wiki:architecture] some-slug | 2026-07-26` / `## [fail:test] s | d | count:1`
_HEADING = re.compile(r"^##\s*\[(?P<kind>wiki|fail):[^\]]*\]\s*(?P<slug>[^|]+?)\s*\|", re.M)


class PromotionSkip(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    slug: str
    reason: str

    @field_validator("reason", "slug", mode="after")
    @classmethod
    def _non_vacuous(cls, v: str) -> str:
        """A skip with no reason is unauditable — it is the field that makes
        under-promotion diagnosable rather than merely visible."""
        if not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v


class CheckResult(BaseModel):
    """One verify check. `verdict` is a closed enum so `"probably fine"` cannot become
    a third value the reconciler silently ignores."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    verdict: Literal["PASS", "FAIL", "SKIP"]


class WrapupReceipt(BaseModel):
    """Named for wrapup, which came first; `stage` also carries `verify` (Phase 6).

    The verify fields below default empty, so a wrapup receipt neither carries them
    nor acquires a verify mismatch for their absence.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int
    stage: str
    # ── verify (Phase 6) ──
    result: str = ""
    checks: tuple[CheckResult, ...] = ()
    record_path: str | None = None
    wiki_slugs: tuple[str, ...] = ()
    failure_slugs: tuple[str, ...] = ()
    promotion_candidates: int = 0
    promoted_slugs: tuple[str, ...] = ()
    promotion_skips: tuple[PromotionSkip, ...] = ()
    documents_updated: tuple[str, ...] = ()


class Mismatch(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: str
    detail: str


class ReconcileResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    ok: bool
    mismatches: tuple[Mismatch, ...] = ()
    checked: int = 0
    unverified: int = 0


# ------------------------------------------------------------------ parsing


def _extract_payload(raw: str) -> tuple[str | None, str]:
    """Exactly one JSON object in the WHOLE reply, or nothing. Fail-closed on ambiguity.

    Two defects the first version had (review M-06 / M-08 / M-12):
    - it looked at fenced blocks and, only if there were none, at unfenced text — so a
      reply with one fenced payload plus a second unfenced one short-circuited on the
      fence and the "refuse if more than one" promise silently did not hold;
    - it counted `{`/`}` characters without tracking string literals, so a brace inside
      a string (`{"a": "}"}`) split the object at the wrong place.

    `raw_decode` fixes both: it parses a real JSON value from each candidate start and
    reports where it ended, so string contents are respected and every object in the
    reply is counted. Mirrors `codex_adapter.extract_antigravity_payload`.
    """
    decoder = json.JSONDecoder()
    found: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        try:
            _value, end = decoder.raw_decode(raw, i)
        except ValueError:
            i += 1
            continue
        found.append(raw[i:end])
        i = end
    if not found:
        return None, "no JSON object found in the delegated body's output"
    if len(found) > 1:
        return (
            None,
            f"{len(found)} JSON objects found — refusing to guess which is the receipt",
        )
    return found[0], ""


def parse_receipt(raw: str) -> tuple[WrapupReceipt | None, str]:
    """(receipt, error). A prose-only reply is the ADR-012 failure — it must be loud."""
    payload, error = _extract_payload(raw)
    if payload is None:
        return None, error
    try:
        data = json.loads(payload)
    except ValueError as exc:
        return None, f"receipt is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, "receipt payload is not a JSON object"
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        # Reconciling a shape we do not understand would check the fields we recognise
        # and silently ignore any new claim.
        return None, f"receipt schema_version {version!r} != {SCHEMA_VERSION}"
    try:
        # JSON validation mode, NOT model_validate(dict): under strict=True the
        # Python-mode validator rejects a `list` for a `tuple` field, so EVERY
        # well-formed agent receipt would be reported as schema-violating. Same defect
        # class as the span ledger's ISO-string datetime — only a round trip finds it.
        return WrapupReceipt.model_validate_json(payload), ""
    except Exception as exc:  # noqa: BLE001 - any shape error is a fail-closed reject
        return None, f"receipt does not match the schema: {exc}"


# ------------------------------------------------------------------ reconciliation


def _tier_slugs(base: Path, filename: str, kind: str) -> set[str]:
    """Headings only. A body-text grep would let a slug MENTIONED satisfy a claim."""
    path = base / ".claude" / "memory" / filename
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    return {m.group("slug") for m in _HEADING.finditer(text) if m.group("kind") == kind}


# `promote_note` writes `<type>-<slug>.md`. Anchoring on the KNOWN type prefixes is
# what makes a vault note attributable to this harness (review M-02 / M-10): the first
# version took `stem.split("-", 1)[1]` for every `*.md` under the vault, so a user's own
# `my-notes.md` registered slug `notes` and could satisfy a promotion claim by accident.
def _vault_note_types() -> frozenset[str]:
    """DERIVED from the enum, never hand-copied (review R2-02).

    The first version listed five of the six types by hand and omitted `journal` —
    which `wrapup.md.j2` Step 5.6 explicitly offers as a promotion type — so a truthful
    journal promotion reconciled as `promotion-missing` and the template then told the
    main loop to treat an honest claim as fabricated.
    """
    from .models import SecondBrainNoteType

    return frozenset(t.value for t in SecondBrainNoteType)


def _vault_slugs(vault_root: Path, folders: Sequence[str] | None = None) -> set[str]:
    """Slugs this harness could have promoted — nothing else in the vault counts.

    `folders` narrows the walk to `second_brain.folders`, the allowlist a prior
    security review introduced precisely to keep the harness out of the rest of a
    personal Obsidian vault. Absent config falls back to the vault root, which is the
    documented shape for a single-folder vault.
    """
    # No folders configured → NO slugs, not "walk the whole vault" (review R2-04).
    # `promote_note` already refuses to write in that config, so nothing this harness
    # produced can be there; falling back to the vault root re-opened the unbounded
    # walk M-02 was raised about, and would let an unrelated personal note satisfy a
    # promotion claim.
    if not folders:
        return set()
    types = _vault_note_types()
    roots = [vault_root / f for f in folders]
    out: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            prefix, _, slug = path.stem.partition("-")
            if slug and prefix in types:
                out.add(slug)
    return out


def _confined(base: Path, rel: str) -> Path | None:
    """Resolve `rel` under `base`, or None when it escapes (review F-04).

    `record_path` and `documents_updated` are free strings from an LLM reply, and
    `Path("/base") / "/etc/hostname"` is `/etc/hostname` — so an unvalidated join let a
    delegate satisfy reconciliation with any existing file on the machine, after which
    the verify template adopts the receipt's verdict. Mirrors
    `SecondBrainFolder._reject_absolute_or_empty_path`.
    """
    candidate = Path(rel)
    if not rel.strip() or candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        resolved = (base / candidate).resolve()
        # `resolve()` before `is_relative_to` is the load-bearing half: it is the only
        # thing that catches a SYMLINK escape, which is neither absolute nor `..`-bearing
        # and so passes every string check above.
        return resolved if resolved.is_relative_to(base.resolve()) else None
    except (OSError, ValueError):
        # An embedded NUL reaches `os.lstat` as ValueError, which would escape
        # `reconcile`'s "never raises" contract and `main`'s JSON output (review R2-05).
        return None


def reconcile(
    receipt: WrapupReceipt,
    *,
    base_root: Path,
    vault_root: Path | None = None,
    vault_folders: Sequence[str] | None = None,
    worktree_root: Path | None = None,
    expected_stage: str | None = None,
) -> ReconcileResult:
    """Check every claim against observable state. Never raises.

    Tier files resolve from the BASE repo: memory is shared project state committed by
    wrapup, and a worktree copy is ephemeral — reconciling against it would check a
    file `task-land` is about to delete.
    """
    from .memory_md import _base_root

    base = _base_root(base_root)
    # Documents and the verify record are written by the delegate, which is told to
    # write only inside the worktree — and `.claude/observability/` is gitignored churn
    # that exists ONLY there. Resolving them at base false-failed every delegated run
    # (review M-05). Memory tiers stay on `base`: they are shared project state.
    doc_root = Path(worktree_root).resolve() if worktree_root else base
    mismatches: list[Mismatch] = []
    checked = 0

    if expected_stage is not None and receipt.stage != expected_stage:
        # `stage` was a free string nothing compared against, so a wrapup receipt could
        # be reconciled as a verify one and vice versa (review F-05).
        checked += 1
        mismatches.append(
            Mismatch(
                kind="stage-mismatch",
                detail=f"receipt is for {receipt.stage!r}, expected {expected_stage!r}",
            )
        )

    wiki = _tier_slugs(base, "wiki.md", "wiki")
    for slug in receipt.wiki_slugs:
        checked += 1
        if slug not in wiki:
            mismatches.append(
                Mismatch(kind="wiki-missing", detail=f"{slug!r} claimed but not a wiki.md heading")
            )

    failures = _tier_slugs(base, "failures.md", "fail")
    for slug in receipt.failure_slugs:
        checked += 1
        if slug not in failures:
            mismatches.append(
                Mismatch(
                    kind="failure-missing",
                    detail=f"{slug!r} claimed but not a failures.md heading",
                )
            )

    for rel in receipt.documents_updated:
        checked += 1
        target = _confined(doc_root, rel)
        if target is None:
            mismatches.append(
                Mismatch(
                    kind="document-escapes-root",
                    detail=f"{rel!r} is absolute or escapes the repository root",
                )
            )
        elif not target.is_file():
            mismatches.append(
                Mismatch(kind="document-missing", detail=f"{rel!r} claimed but does not exist")
            )

    # The anti-fabrication check: a summarising main loop inventing a plausible
    # `N candidates, M promoted` line produces counts that do not add up, and an agent
    # that actually evaluated N can always account for all N.
    promoted = list(receipt.promoted_slugs)
    skipped = [s.slug for s in receipt.promotion_skips]
    if (
        len(set(promoted)) != len(promoted)
        or len(set(skipped)) != len(skipped)
        or (set(promoted) & set(skipped))
    ):
        # Duplicates and overlap both inflate the count without evaluating anything,
        # which defeats the arithmetic check they pass through (review M-11).
        checked += 1
        mismatches.append(
            Mismatch(
                kind="promotion-duplicate",
                detail="promoted/skipped slugs contain duplicates or overlap",
            )
        )
    accounted = len(receipt.promoted_slugs) + len(receipt.promotion_skips)
    if accounted != receipt.promotion_candidates:
        checked += 1
        mismatches.append(
            Mismatch(
                kind="promotion-arithmetic",
                detail=(
                    f"{receipt.promotion_candidates} candidates but "
                    f"{len(receipt.promoted_slugs)} promoted + "
                    f"{len(receipt.promotion_skips)} skipped = {accounted}"
                ),
            )
        )

    # ── verify (Phase 6): its observable output is the JSONL record it appends and
    # the per-check verdicts. Without these the reconciliation would have nothing in
    # it — every memory field is legitimately empty for verify, so any claim would
    # reconcile clean.
    if receipt.stage == "verify":
        # Every one of these was CONDITIONAL, so `{"schema_version": 1, "stage":
        # "verify"}` produced zero mismatches, reconciled `ok`, and the template then
        # adopted an empty-string verdict as the gate result (review F-05).
        if not receipt.result.strip():
            checked += 1
            mismatches.append(
                Mismatch(kind="verify-result-missing", detail="receipt carries no `result`")
            )
        if not receipt.checks:
            checked += 1
            mismatches.append(
                Mismatch(kind="verify-checks-missing", detail="receipt claims no checks ran")
            )
        if not receipt.record_path:
            checked += 1
            mismatches.append(
                Mismatch(
                    kind="verify-record-missing",
                    detail="receipt names no record_path, so the run left no verifiable trace",
                )
            )
    if receipt.record_path:
        checked += 1
        target = _confined(doc_root, receipt.record_path)
        if target is None:
            mismatches.append(
                Mismatch(
                    kind="document-escapes-root",
                    detail=f"record_path {receipt.record_path!r} escapes the repository root",
                )
            )
        elif not target.is_file():
            mismatches.append(
                Mismatch(
                    kind="verify-record-missing",
                    detail=f"{receipt.record_path!r} claimed but the record does not exist",
                )
            )
    failed = [c.name for c in receipt.checks if c.verdict == "FAIL"]
    if failed and receipt.result.strip().upper() == "PASS":
        # The mirror of the promotion arithmetic, and the one mismatch that must never
        # be smoothed over: verify is a GATE, so a relayed "all green" over a failing
        # check lets the pipeline proceed past the thing that was supposed to stop it.
        checked += 1
        mismatches.append(
            Mismatch(
                kind="verify-result-inconsistent",
                detail=f"result is PASS but these checks FAILed: {', '.join(failed)}",
            )
        )

    unverified = 0
    if vault_root is None:
        # Second Brain is optional and lives outside the repo. Counting an uncheckable
        # claim as verified would let the one number CLAUDE.md relies on go unchecked
        # while the result says ok.
        unverified = len(receipt.promoted_slugs)
    else:
        in_vault = _vault_slugs(vault_root, vault_folders)
        for slug in receipt.promoted_slugs:
            checked += 1
            if slug not in in_vault:
                mismatches.append(
                    Mismatch(
                        kind="promotion-missing",
                        detail=f"{slug!r} claimed promoted but absent from {vault_root}",
                    )
                )

    return ReconcileResult(
        ok=not mismatches,
        mismatches=tuple(mismatches),
        checked=checked,
        unverified=unverified,
    )


# ------------------------------------------------------------------ CLI


def _configured_vault(base: Path) -> Path | None:
    """The Second Brain namespace, when the project has one.

    Absent config means promotions are UNVERIFIABLE, not verified — the caller
    reports `unverified` rather than passing them silently.
    """
    path = base / ".claude" / "harness.yaml"
    if not path.is_file():
        return None
    try:
        from .io_utils import load_harness_yaml

        data = load_harness_yaml(path)
    except Exception:  # noqa: BLE001 - a broken harness.yaml must not block the wrapup
        return None
    raw = data.get("second_brain") if isinstance(data, dict) else None
    if not isinstance(raw, dict) or not raw.get("enabled"):
        return None
    vault = raw.get("vault_path")
    return Path(str(vault)).expanduser() if isinstance(vault, str) and vault.strip() else None


def _configured_vault_folders(base: Path) -> list[str] | None:
    """`second_brain.folders` — the allowlist that keeps this walk out of the rest of a
    personal Obsidian vault (review M-02)."""
    path = base / ".claude" / "harness.yaml"
    if not path.is_file():
        return None
    try:
        from .io_utils import load_harness_yaml

        data = load_harness_yaml(path)
    except Exception:  # noqa: BLE001
        return None
    raw = data.get("second_brain") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    folders = raw.get("folders")
    if not isinstance(folders, list):
        return None
    out = [f.get("path") for f in folders if isinstance(f, dict) and isinstance(f.get("path"), str)]
    return [p for p in out if p] or None


def main(argv: list[str] | None = None) -> int:
    """Exit 0 on a clean reconciliation, 1 on a mismatch, 2 on an unparseable receipt.

    A non-zero exit here is a real signal — unlike the brief's degraded path, which
    must never halt: a receipt that does not reconcile means the main loop is about
    to commit work whose claims do not hold.
    """
    from .memory_md import _base_root

    parser = argparse.ArgumentParser(prog="python -m harness_maker.wrapup_receipt")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--receipt-file", required=True, help="file holding the delegated body's reply"
    )
    parser.add_argument("--vault", default=None, help="override the configured vault path")
    parser.add_argument("--stage", default=None, help="stage the receipt must be for")
    parser.add_argument(
        "--worktree", default=None, help="worktree root that documents/record resolve against"
    )
    ns = parser.parse_args(argv if argv is not None else sys.argv[1:])

    base = _base_root(Path(ns.root))
    try:
        raw = Path(ns.receipt_file).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(json.dumps({"status": "unparseable", "error": str(exc)}, indent=2))
        return 2

    receipt, error = parse_receipt(raw)
    if receipt is None:
        print(json.dumps({"status": "unparseable", "error": error}, indent=2))
        return 2

    vault = Path(ns.vault).expanduser() if ns.vault else _configured_vault(base)
    result = reconcile(
        receipt,
        base_root=base,
        vault_root=vault,
        vault_folders=_configured_vault_folders(base),
        # Default the document root to the invocation cwd: a delegated stage runs
        # inside the task worktree, which is where it writes (review M-05).
        worktree_root=Path(ns.worktree).resolve() if ns.worktree else Path(ns.root).resolve(),
        expected_stage=ns.stage,
    )
    print(
        json.dumps(
            {
                "status": "ok" if result.ok else "mismatch",
                "result": result.model_dump(mode="json"),
                "receipt": receipt.model_dump(mode="json"),
                "vault_checked": str(vault) if vault else None,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
