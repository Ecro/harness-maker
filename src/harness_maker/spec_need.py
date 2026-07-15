"""SPEC requirement detection, verdict recording, waiver, and marker state machine.

ADR-001/002/008/009 from PLAN-spec-requirement-gate.

Task-driven runtime guard (PLAN-spec-optional-task-driven ADR-001): the CLI is
invoked ONLY from spec-driven-rendered plan Step 1.7 / verify Check 6. If a
harness flips ``dev_mode`` to task-driven WITHOUT re-rendering, those stale prose
blocks still call this CLI. To keep task-driven from forcing SPEC, the
verify-ORACLE commands (``op-check``, ``waiver-check``) short-circuit to
satisfied/valid on a CONFIDENT ``dev_mode == "task-driven"`` read — verify Check 6
reads the exit code, so this fully backstops verify. The relax is fail-CLOSED
(only a confident task-driven read; missing/unreadable/malformed → enforce), the
INVERSE of ``spec_gate.py``'s advisory fail-open, because this module IS the
verify oracle. All marker/record commands stay pass-through so the ADR-009
anti-loop machinery is untouched. plan Step 1.7's §1.7.2 enforcement is LLM-prose,
unreachable at runtime — surfaced instead by the ``plan_verify_dev_mode_match``
/hm:health signal (ADR-003); re-render is the real fix for stale plan prose.
"""

from __future__ import annotations

import argparse
import json
import logging
import re as _re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from harness_maker import command_registry
from harness_maker.io_utils import atomic_append, atomic_write, load_harness_yaml

logger = logging.getLogger(__name__)

Verdict = Literal["add", "change", "delete", "none", "not-evaluated"]
_VALID_VERDICTS: tuple[str, ...] = ("add", "change", "delete", "none", "not-evaluated")

# Only allow safe slug characters — no path traversal (FIX 3 / Codex-2).
_SLUG_RE = _re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_slug(s: str) -> None:
    """Reject slugs that could traverse paths outside the observability dir.

    Empty strings, path separators, '..' components, and any character outside
    [A-Za-z0-9._-] are all rejected with ValueError.
    """
    if not s:
        raise ValueError(f"slug/target must be non-empty, got {s!r}")
    if "/" in s or "\\" in s:
        raise ValueError(f"slug/target must not contain path separators, got {s!r}")
    if ".." in s.split("/"):
        raise ValueError(f"slug/target must not contain '..', got {s!r}")
    if not _SLUG_RE.match(s):
        raise ValueError(f"slug/target must match [A-Za-z0-9._-]+, got {s!r}")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpecNeedEvent:
    """A single spec-need verdict event for the observability ledger."""

    verdict: str
    target: str
    rationale: str
    detected_at: str
    changed_files_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. prefilter
# ---------------------------------------------------------------------------


def prefilter(specs_dir: Path, changed_files: list[str]) -> list[dict[str, Any]]:
    """Identify SPECs whose paths overlap with changed_files (HINT only, not a gate).

    Overlap = changed_files ∩ (paths_to_mutate ∪ all judgment_subject_paths).
    Malformed/unreadable machine.yaml files are silently skipped (degrade,
    never raise). Returns [] when specs_dir is absent or no overlap found.
    """
    if not specs_dir.is_dir():
        return []

    import harness_maker.spec_machine as spec_machine

    results: list[dict[str, Any]] = []
    changed_set = set(changed_files)

    for yaml_path in sorted(specs_dir.glob("SPEC-*.machine.yaml")):
        try:
            model = spec_machine.load(yaml_path)
        except Exception:
            # Malformed YAML or schema error — skip without raising (degrade).
            logger.debug("prefilter: skipping malformed %s", yaml_path)
            continue

        # Build the union of all path-bearing fields.
        candidate_paths: set[str] = set(model.paths_to_mutate)
        for ac in model.ac:
            candidate_paths.update(ac.judgment_subject_paths)

        overlap = sorted(candidate_paths & changed_set)
        if not overlap:
            continue

        # Derive the slug: strip the leading "SPEC-" and trailing ".machine.yaml".
        stem = yaml_path.name  # e.g. "SPEC-foo.machine.yaml"
        slug = stem.removeprefix("SPEC-").removesuffix(".machine.yaml")
        results.append({"slug": slug, "overlap": overlap})

    results.sort(key=lambda r: r["slug"])
    return results


# ---------------------------------------------------------------------------
# 2. record_spec_need
# ---------------------------------------------------------------------------


def record_spec_need(
    verdict: str,
    target: str,
    rationale: str,
    root: Path,
    *,
    audit_path: Path | None = None,
    changed_files_hash: str = "",
) -> None:
    """Append a SpecNeedEvent to the verdict ledger (no-raise contract).

    Mirrors observability/intent_miss.record_intent_miss.
    Writes to root/.claude/observability/spec-need-{target}.jsonl.
    """
    try:
        _validate_slug(target)
        event = SpecNeedEvent(
            verdict=verdict,
            target=target,
            rationale=rationale,
            detected_at=_now_iso(),
            changed_files_hash=changed_files_hash,
        )
        effective_path = audit_path or (
            root / ".claude" / "observability" / f"spec-need-{target}.jsonl"
        )
        line = json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
        atomic_append(effective_path, line)
    except Exception:
        logger.warning("record_spec_need: failed to write ledger for target=%r", target)


# ---------------------------------------------------------------------------
# 3. operation_satisfied
# ---------------------------------------------------------------------------


def operation_satisfied(
    verdict: str,
    target: str,
    root: Path,
    changed_files: list[str],
) -> bool:
    """Return True iff the required SPEC operation has been performed.

    add:    root/specs/SPEC-{target}.machine.yaml exists AND loads with >=1 AC.
    change: specs/SPEC-{target}.machine.yaml appears in changed_files (touched).
    delete: specs/SPEC-{target}.machine.yaml appears in changed_files (touched).
    none | not-evaluated: always False (only operation+author or waiver clears them).
    absent target: always False.

    Never raises.
    """
    try:
        if not target:
            return False
        _validate_slug(target)
        if verdict == "add":
            spec_path = root / "specs" / f"SPEC-{target}.machine.yaml"
            if not spec_path.is_file():
                return False
            import harness_maker.spec_machine as spec_machine

            try:
                model = spec_machine.load(spec_path)
                return len(model.ac) >= 1
            except Exception:
                return False
        if verdict in ("change", "delete"):
            spec_rel = f"specs/SPEC-{target}.machine.yaml"
            return spec_rel in changed_files
        # verdict == "none" | "not-evaluated" → never satisfied here
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 4. Waiver helpers
# ---------------------------------------------------------------------------


def write_waiver(
    root: Path,
    slug: str,
    verdict: str,
    target: str,
    rationale: str,
    changed_files: list[str],
) -> None:
    """Write an immutable, hash-bound waiver receipt (ADR-001/008).

    Requires non-empty rationale (raises ValueError if blank/whitespace).
    The waiver_hash binds to the current diff via compute_subject_hash.
    Appended as JSONL to root/.claude/observability/spec-need-waiver-{slug}.jsonl.
    """
    _validate_slug(slug)
    _validate_slug(target)
    if not rationale or not rationale.strip():
        raise ValueError("waiver rationale must be non-empty (ADR-001)")

    from harness_maker.spec_machine import SubjectHashError, compute_subject_hash

    try:
        waiver_hash = compute_subject_hash(sorted(changed_files), root)
    except SubjectHashError as exc:
        raise ValueError(f"cannot compute waiver hash: {exc}") from exc

    receipt: dict[str, Any] = {
        "slug": slug,
        "verdict": verdict,
        "target": target,
        "rationale": rationale,
        "waiver_hash": waiver_hash,
        "waived_at": _now_iso(),
    }
    path = root / ".claude" / "observability" / f"spec-need-waiver-{slug}.jsonl"
    line = json.dumps(receipt, ensure_ascii=False) + "\n"
    atomic_append(path, line)


def waiver_valid(root: Path, slug: str, changed_files: list[str]) -> bool:
    """Return True iff a valid, non-stale, non-empty-rationale waiver exists.

    Reads the LATEST receipt for slug; recomputes hash; returns True only when:
    - a receipt exists,
    - its rationale is non-empty,
    - its waiver_hash == compute_subject_hash(sorted(changed_files), root).

    A missing/malformed receipt or a hash mismatch (diff changed = expired) → False.
    Fail-closed: any unexpected error → False.
    """
    try:
        _validate_slug(slug)
    except ValueError:
        return False

    from harness_maker.spec_machine import SubjectHashError, compute_subject_hash

    path = root / ".claude" / "observability" / f"spec-need-waiver-{slug}.jsonl"
    try:
        if not path.is_file():
            return False
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            return False
        # Use the latest receipt.
        receipt = json.loads(lines[-1])
        stored_hash = receipt.get("waiver_hash", "")
        stored_rationale = receipt.get("rationale", "")
        if not stored_rationale or not stored_rationale.strip():
            return False
        if not stored_hash:
            return False
        try:
            live_hash = compute_subject_hash(sorted(changed_files), root)
        except SubjectHashError:
            return False
        return bool(live_hash == str(stored_hash))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 5. Marker state machine (ADR-009)
# ---------------------------------------------------------------------------

_MARKER_PREFIX = ".hm-spec-need-"


def marker_path(root: Path, slug: str) -> Path:
    """Return the path for the durable one-shot resume marker."""
    _validate_slug(slug)
    return root / ".claude" / f"{_MARKER_PREFIX}{slug}"


def write_marker(
    root: Path,
    slug: str,
    verdict: str,
    target: str,
    base_sha: str,
    changed_files_hash: str,
) -> None:
    """Atomically write the resume marker as JSON (ADR-009)."""
    # slug is validated by marker_path; validate target explicitly (FIX 3).
    _validate_slug(target)
    data = {
        "slug": slug,
        "verdict": verdict,
        "target": target,
        "base_sha": base_sha,
        "changed_files_hash": changed_files_hash,
        "detected_at": _now_iso(),
    }
    atomic_write(marker_path(root, slug), json.dumps(data, ensure_ascii=False) + "\n")


def read_marker(root: Path, slug: str) -> dict[str, Any] | None:
    """Read the resume marker; return None if absent or malformed."""
    p = marker_path(root, slug)
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def marker_fresh(root: Path, slug: str, changed_files_hash: str) -> bool:
    """Return True iff marker is present AND its changed_files_hash matches.

    A mismatch means the diff moved on and the marker is stale — the caller
    should clear it and re-detect fresh.
    """
    data = read_marker(root, slug)
    if data is None:
        return False
    return bool(str(data.get("changed_files_hash", "")) == changed_files_hash)


def clear_marker(root: Path, slug: str) -> None:
    """Idempotent unlink the resume marker (ADR-009 one-shot clear)."""
    marker_path(root, slug).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# CLI __main__
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m harness_maker.spec_need",
        description="SPEC requirement gate utilities (ADR-001/002/008/009).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # prefilter
    pf = sub.add_parser("prefilter", help="Print JSON array of overlapping SPECs")
    pf.add_argument("--specs-dir", required=True, type=Path, metavar="DIR")
    pf.add_argument(
        "--changed-file", dest="changed_files", action="append", default=[], metavar="PATH"
    )

    # record
    rec = sub.add_parser("record", help="Append a SpecNeedEvent to the verdict ledger")
    rec.add_argument("--verdict", required=True, choices=_VALID_VERDICTS)
    rec.add_argument("--target", required=True)
    rec.add_argument("--rationale", default="")
    rec.add_argument("--root", required=True, type=Path)
    rec.add_argument("--changed-files-hash", default="", dest="changed_files_hash")

    # op-check
    op = sub.add_parser(
        "op-check",
        help="Exit 0 if operation satisfied, 1 if not",
    )
    op.add_argument("--verdict", required=True, choices=_VALID_VERDICTS)
    op.add_argument("--target", required=True)
    op.add_argument("--root", required=True, type=Path)
    op.add_argument(
        "--changed-file", dest="changed_files", action="append", default=[], metavar="PATH"
    )

    # waiver-set
    ws = sub.add_parser("waiver-set", help="Write a hash-bound waiver receipt")
    ws.add_argument("--root", required=True, type=Path)
    ws.add_argument("--slug", required=True)
    ws.add_argument("--verdict", required=True, choices=_VALID_VERDICTS)
    ws.add_argument("--target", required=True)
    ws.add_argument("--rationale", required=True)
    ws.add_argument(
        "--changed-file", dest="changed_files", action="append", default=[], metavar="PATH"
    )

    # waiver-check
    wc = sub.add_parser("waiver-check", help="Exit 0 if valid waiver exists for slug, 1 if not")
    wc.add_argument("--root", required=True, type=Path)
    wc.add_argument("--slug", required=True)
    wc.add_argument(
        "--changed-file", dest="changed_files", action="append", default=[], metavar="PATH"
    )

    # marker-write
    mw = sub.add_parser("marker-write", help="Write the durable resume marker")
    mw.add_argument("--root", required=True, type=Path)
    mw.add_argument("--slug", required=True)
    mw.add_argument("--verdict", required=True, choices=_VALID_VERDICTS)
    mw.add_argument("--target", required=True)
    mw.add_argument("--base-sha", required=True, dest="base_sha")
    mw.add_argument("--changed-files-hash", required=True, dest="changed_files_hash")

    # marker-read
    mr = sub.add_parser("marker-read", help="Print marker JSON (or null)")
    mr.add_argument("--root", required=True, type=Path)
    mr.add_argument("--slug", required=True)

    # marker-clear
    mc = sub.add_parser("marker-clear", help="Delete the resume marker (idempotent)")
    mc.add_argument("--root", required=True, type=Path)
    mc.add_argument("--slug", required=True)

    # marker-fresh
    mf = sub.add_parser(
        "marker-fresh",
        help="Exit 0 if marker is present and hash matches, 1 otherwise",
    )
    mf.add_argument("--root", required=True, type=Path)
    mf.add_argument("--slug", required=True)
    mf.add_argument("--changed-files-hash", required=True, dest="changed_files_hash")

    return parser


def _cli_validate_slug(value: str, field: str = "slug") -> int:
    """Print error JSON and return 1 if slug is invalid; return 0 otherwise."""
    try:
        _validate_slug(value)
        return 0
    except ValueError as exc:
        print(json.dumps({"error": f"invalid {field}: {exc}"}))
        return 1


def _read_dev_mode(root: Path) -> str | None:
    """Return harness.yaml ``dev_mode``, or None when absent/unreadable.

    WHY fail-closed (PLAN-spec-optional-task-driven ADR-001): spec_need is the
    verify Check 6 *oracle*, so only a confident ``task-driven`` read may relax
    the verify-oracle commands. A missing/unreadable/malformed config returns
    None → the caller does NOT relax (enforce). This is the deliberate INVERSE
    of ``spec_gate.py``'s advisory fail-OPEN, where relax-on-unreadable is safe.
    """
    yaml_path = root / ".claude" / "harness.yaml"
    try:
        cfg = load_harness_yaml(yaml_path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    dev_mode = cfg.get("dev_mode") if isinstance(cfg, dict) else None
    return dev_mode if isinstance(dev_mode, str) else None


def _relax_for_task_driven(root: Path) -> bool:
    """True iff a confident ``dev_mode == "task-driven"`` read (verify-oracle relax)."""
    return _read_dev_mode(root) == "task-driven"


def main(argv: list[str] | None = None) -> int:
    _guard = command_registry.guard_or_none("spec_need", argv)
    if _guard is not None:
        return _guard
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "prefilter":
        results = prefilter(args.specs_dir, args.changed_files)
        print(json.dumps(results, ensure_ascii=False))
        return 0

    if args.cmd == "record":
        if rc := _cli_validate_slug(args.target, "target"):
            return rc
        record_spec_need(
            args.verdict,
            args.target,
            args.rationale,
            args.root,
            changed_files_hash=args.changed_files_hash,
        )
        print(json.dumps({"recorded": True}))
        return 0

    if args.cmd == "op-check":
        if _relax_for_task_driven(args.root):
            # ADR-001: task-driven never requires a SPEC operation → satisfied.
            # verify Check 6 reads the exit code, so exit 0 makes it PASS.
            print(json.dumps({"satisfied": True}))
            return 0
        if rc := _cli_validate_slug(args.target, "target"):
            return rc
        satisfied = operation_satisfied(args.verdict, args.target, args.root, args.changed_files)
        print(json.dumps({"satisfied": satisfied}))
        return 0 if satisfied else 1

    if args.cmd == "waiver-set":
        if rc := _cli_validate_slug(args.slug, "slug"):
            return rc
        if rc := _cli_validate_slug(args.target, "target"):
            return rc
        try:
            write_waiver(
                args.root,
                args.slug,
                args.verdict,
                args.target,
                args.rationale,
                args.changed_files,
            )
            print(json.dumps({"written": True}))
            return 0
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            return 1

    if args.cmd == "waiver-check":
        if _relax_for_task_driven(args.root):
            # ADR-001: task-driven needs no waiver — the verify gate is relaxed.
            print(json.dumps({"valid": True}))
            return 0
        if rc := _cli_validate_slug(args.slug, "slug"):
            return rc
        valid = waiver_valid(args.root, args.slug, args.changed_files)
        print(json.dumps({"valid": valid}))
        return 0 if valid else 1

    if args.cmd == "marker-write":
        if rc := _cli_validate_slug(args.slug, "slug"):
            return rc
        if rc := _cli_validate_slug(args.target, "target"):
            return rc
        write_marker(
            args.root,
            args.slug,
            args.verdict,
            args.target,
            args.base_sha,
            args.changed_files_hash,
        )
        print(json.dumps({"written": True}))
        return 0

    if args.cmd == "marker-read":
        if rc := _cli_validate_slug(args.slug, "slug"):
            return rc
        data = read_marker(args.root, args.slug)
        print(json.dumps(data))
        return 0

    if args.cmd == "marker-clear":
        if rc := _cli_validate_slug(args.slug, "slug"):
            return rc
        clear_marker(args.root, args.slug)
        print(json.dumps({"cleared": True}))
        return 0

    if args.cmd == "marker-fresh":
        if rc := _cli_validate_slug(args.slug, "slug"):
            return rc
        fresh = marker_fresh(args.root, args.slug, args.changed_files_hash)
        print(json.dumps({"fresh": fresh}))
        return 0 if fresh else 1

    return 1  # unreachable with required subcommand


if __name__ == "__main__":
    sys.exit(main())
