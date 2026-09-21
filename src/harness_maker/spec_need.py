"""SPEC requirement detection, verdict recording, waiver, and marker state machine.

ADR-001/002/008/009 from PLAN-spec-requirement-gate.

Relaxed-strictness runtime guard (PLAN-spec-optional-task-driven ADR-001, re-keyed by
SPEC-dev-mode-removal ADR-004): the verify-ORACLE commands (``op-check``, ``waiver-check``)
short-circuit to satisfied/valid on a CONFIDENT ``spec.strictness == "warn"`` read — verify
Check 6 reads the exit code, so this fully backstops verify. The relax is fail-CLOSED (only an
explicit, valid ``warn``; missing/unreadable/malformed → enforce), the INVERSE of every other
reader, which derives an absent key from the preset. This module IS the verify oracle, so it
is the one named exception (``strictness.STRICTNESS_EXEMPT``). All marker/record commands stay
pass-through so the ADR-009 anti-loop machinery is untouched.
"""

from __future__ import annotations

import argparse
import hashlib
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
from harness_maker.io_utils import atomic_append, atomic_write, load_harness_yaml, rmw_lock

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
    Writes to <base>/.claude/observability/spec-need-{target}.jsonl, where <base> is the
    main worktree resolved from ``root``. ``root`` is the stage's `<WT>`, and a worktree's
    `.claude/observability/` is gitignored and deleted at `task-land` — spoton had four
    worktrees each holding spec-need rows that never reached base. Markers and waivers
    keep ``root`` on purpose: they are per-worktree gate state read back from the same
    place they are written, not observability.
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
        from harness_maker.second_opinion_invoke import resolve_base_root  # noqa: PLC0415

        effective_path = audit_path or (
            resolve_base_root(root) / ".claude" / "observability" / f"spec-need-{target}.jsonl"
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


_SPEC_NEED_KEYS: tuple[str, ...] = ("spec_need_verdict", "spec_need_target")


def _confined_plan_path(plan_path: Path, root: Path) -> Path:
    """Resolve `plan_path` and refuse anything outside `root`.

    WHY this is not optional (`root` is required, no default): every other path-bearing verb in
    this module derives its path from a `_validate_slug`-checked component under `root`, and
    this one took a caller-supplied `Path` raw. A confinement check that can be skipped by
    omitting an argument is the absent-case black hole (count:8) — it would never fire for the
    one caller that forgot it, which is exactly the caller that needs it.
    """
    resolved = plan_path.resolve()
    base = root.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"{plan_path} resolves outside the project root {root}")
    return resolved


def _read_fence(plan_path: Path) -> tuple[list[str], int, dict[str, str]]:
    """Split a PLAN into (lines, closing-fence index, the SPEC-need keys already in the fence)."""
    lines = plan_path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValueError(f"{plan_path} does not open with a `---` frontmatter fence")
    close = next(
        (i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"),
        None,
    )
    if close is None:
        raise ValueError(f"{plan_path} has an unterminated frontmatter fence")

    existing: dict[str, str] = {}
    for line in lines[1:close]:
        for key in _SPEC_NEED_KEYS:
            if line.startswith(f"{key}:"):
                existing[key] = line[len(key) + 1 :].split("#", 1)[0].strip()
    return lines, close, existing


def frontmatter_upsert(
    plan_path: Path, verdict: str, target: str, *, root: Path
) -> dict[str, str | bool | None]:
    """Write the SPEC-need pair into a PLAN's frontmatter WITHOUT overwriting a recorded decision.

    WHY this is a function and not a line of prose in `execute.md.j2` (IRR-004): `verify.md.j2`
    Check 6 treats an absent `spec_need_verdict` as ``PASS (N-A)``, so the only failure mode
    that matters here is silent — a writer that no-ops, or one that clobbers a verdict the DRI
    already recorded, produces a green gate either way. A prose recipe has no execution surface,
    so a test could only grep its text; that shape shipped four silent-skip bugs in this repo.

    **The unit of preservation is the PAIR, not the key.** Check 6 reads the two together to
    decide which SPEC the verdict applies to, so a preserved verdict beside a freshly-supplied
    target would point an old decision at a new subject. The verdict is the decision and the
    target only names its subject, so the verdict alone decides whether a decision exists:

    * verdict present  → preserve it, and fill the target only if it is missing (`repaired`).
    * verdict absent   → there is no recorded decision, so write BOTH fresh, replacing a stray
      target line. A target with no verdict beside it is not a decision to protect.

    **Concurrency.** A stable lock keyed by the resolved PLAN path covers the entire
    read/splice/write/readback transaction. Cooperating sessions therefore preserve the
    first recorded decision, including callers using different aliases for the same PLAN.
    Atomic replacement alone prevents torn files, but cannot prevent lost decisions.
    Lock availability and timeout behavior follow `io_utils.rmw_lock`.
    """
    if verdict not in _VALID_VERDICTS:
        raise ValueError(f"invalid verdict: {verdict!r} (expected one of {_VALID_VERDICTS})")
    _validate_slug(target)
    plan_path = _confined_plan_path(plan_path, root)

    plan_key = hashlib.sha256(str(plan_path).encode("utf-8")).hexdigest()
    lock_path = root.resolve() / ".claude" / "observability" / f"spec-need-{plan_key}.lock"
    with rmw_lock(lock_path):
        wanted = {"spec_need_verdict": verdict, "spec_need_target": target}
        lines, close, existing = _read_fence(plan_path)

        if "spec_need_verdict" in existing:
            additions = (
                [f"spec_need_target: {target}\n"] if "spec_need_target" not in existing else []
            )
            kept = list(lines)
        else:
            # No decision on disk. Write the pair together and drop any orphan target line, so the
            # two values that Check 6 reads as one pair always come from one judgment.
            kept = [
                line
                for i, line in enumerate(lines)
                if not (1 <= i < close and line.startswith("spec_need_target:"))
            ]
            close -= len(lines) - len(kept)
            additions = [f"{k}: {wanted[k]}\n" for k in _SPEC_NEED_KEYS]

        if additions:
            kept[close:close] = additions
            atomic_write(plan_path, "".join(kept))

        _, _, on_disk = _read_fence(plan_path)
        return {
            "spec_need_verdict": on_disk.get("spec_need_verdict"),
            "spec_need_target": on_disk.get("spec_need_target"),
            "preserved_verdict": "spec_need_verdict" in existing,
            "preserved_target": "spec_need_verdict" in existing and "spec_need_target" in existing,
            "repaired": "spec_need_verdict" in existing and "spec_need_target" not in existing,
            "wrote": bool(additions),
        }


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

    # frontmatter-upsert (IRR-004 of SPEC-plan-stage-absorption)
    fu = sub.add_parser(
        "frontmatter-upsert",
        help="Write spec_need_verdict/target into a PLAN's frontmatter, preserving existing values",
    )
    fu.add_argument("--plan", required=True, type=Path, metavar="PATH")
    fu.add_argument("--root", required=True, type=Path)
    fu.add_argument("--verdict", required=True, choices=_VALID_VERDICTS)
    fu.add_argument("--target", required=True)

    return parser


def _cli_validate_slug(value: str, field: str = "slug") -> int:
    """Print error JSON and return 1 if slug is invalid; return 0 otherwise."""
    try:
        _validate_slug(value)
        return 0
    except ValueError as exc:
        print(json.dumps({"error": f"invalid {field}: {exc}"}))
        return 1


def _read_strictness(root: Path) -> str | None:
    """Return harness.yaml ``spec.strictness`` exactly as written, or None when absent/unreadable.

    WHY this reads the raw key instead of calling ``strictness.resolve_strictness``: the
    resolver derives an ABSENT key from the preset, so a Side project with no key would read
    as ``warn`` and relax the oracle. spec_need is the verify Check 6 *oracle* — only a
    confident explicit ``warn`` may relax it (SPEC-dev-mode-removal ADR-004). A legacy config
    is already translated by the loader, so the old relaxed setting still arrives as ``warn``.
    """
    yaml_path = root / ".claude" / "harness.yaml"
    try:
        cfg = load_harness_yaml(yaml_path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    spec = cfg.get("spec") if isinstance(cfg, dict) else None
    value = spec.get("strictness") if isinstance(spec, dict) else None
    return value if isinstance(value, str) else None


def _relax_for_warn(root: Path) -> bool:
    """True iff a confident explicit ``spec.strictness == "warn"`` read (verify-oracle relax)."""
    return _read_strictness(root) == "warn"


def main(argv: list[str] | None = None) -> int:
    _guard = command_registry.guard_or_none("spec_need", argv)
    if _guard is not None:
        return _guard
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "frontmatter-upsert":
        if rc := _cli_validate_slug(args.target, "target"):
            return rc
        try:
            result = frontmatter_upsert(args.plan, args.verdict, args.target, root=args.root)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0

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
        if _relax_for_warn(args.root):
            # ADR-001: a relaxed harness never requires a SPEC operation → satisfied.
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
        except (OSError, ValueError) as exc:
            # OSError: atomic_append refuses to retry a short write (io_utils contract);
            # the CLI keeps its JSON error shape either way.
            print(json.dumps({"error": str(exc)}))
            return 1

    if args.cmd == "waiver-check":
        if _relax_for_warn(args.root):
            # ADR-001: a relaxed harness needs no waiver — the verify gate is relaxed.
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
