"""Per-stage iteration receipts — PLAN-loop-mid-stop-and-review-skip P1.

Mechanical artifact a fused-workflow stage writes when it finishes. The
autoloop driver's Gate 0 reads these to verify every expected stage of the
current iteration ran with ``verdict == "pass"``. Receipts live inside the
worktree (``<root>/.claude/.hm-iter-receipts/iter-{N}/{stage}.json``) and
are ephemeral — they vanish with the worktree at loop close.

The module is intentionally separate from ``review_telemetry`` (per-review
metrics) so the per-stage gate signal does not get conflated with review
content. See ADR-004 of PLAN-loop-mid-stop-and-review-skip.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from harness_maker.io_utils import atomic_write

logger = logging.getLogger(__name__)

RECEIPT_DIR_NAME = ".hm-iter-receipts"
"""Subdirectory under ``.claude/`` where receipts live."""

Verdict = Literal["pass", "fail", "skipped"]
"""Allowed verdict values. ``skipped`` is reserved for the ADR-005 escape
hatch ("Skip with verdict: skipped marker") — stage prompts never emit it
themselves; only the auto-retry escalation does."""

_STAGE_SAFE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
"""Stage names are restricted to filename-safe ASCII: leading letter, then
letters / digits / underscore / hyphen, ≤64 chars. Rejects path traversal
(``..``, ``/``) and anything that would escape the receipts directory."""


class IterReceipt(BaseModel):
    """Single per-stage receipt.

    Strict + extra=forbid so a forged JSON with an unexpected field is
    rejected at read time — closes one half of the "LLM forges receipts"
    risk (ADR-005). The other half (verdict cheat) is closed by Gate 0
    requiring ``verdict == "pass"``.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    iter: int = Field(ge=1)
    stage: str = Field(min_length=1, max_length=64)
    verdict: Verdict
    written_at: str = Field(max_length=32)

    @field_validator("written_at")
    @classmethod
    def _written_at_must_be_iso(cls, value: str) -> str:
        """Reject opaque strings — Gate 0 audit log staleness checks need parseable ts."""
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"written_at must be ISO 8601 (got {value!r})") from exc
        return value


@dataclass
class VerifyResult:
    """Gate 0 verification surface.

    ``all_passed`` is the single boolean the driver flips Gate 0 on.
    ``missing`` and ``non_pass`` are the lists of stages that block, in
    that order — the driver re-invokes them per ADR-005.
    """

    all_passed: bool
    missing: list[str] = field(default_factory=list)
    non_pass: list[str] = field(default_factory=list)


def _utc_now_iso() -> str:
    """ISO 8601 second-resolution UTC stamp."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _receipts_root(root: Path) -> Path:
    return root / ".claude" / RECEIPT_DIR_NAME


def _require_existing_root(root: Path) -> None:
    """Refuse to write to a worktree root that does not exist on disk.

    WHY: ``atomic_write`` auto-creates parent dirs, so without this guard a
    drifted/fabricated ``--root`` (an LLM-hallucinated ``.worktrees/…`` path
    that ``worktree create`` never produced) would silently materialize a bogus
    receipts tree instead of failing. The phantom path then propagates into the
    loop and cascade-cancels parallel stage dispatches. Fail loud at the first
    touch instead.

    SCOPE: this is a cheap *existence* check, not a worktree-validity check —
    a real-but-wrong directory (e.g. cwd) still passes. The authoritative
    anti-drift gate is ``worktree verify`` (worktree.py), which the loop runs
    serially before any receipt write; this guard is the belt-and-suspenders
    backstop for the non-existent-path case (review CC-2).
    """
    if not root.is_dir():
        raise ValueError(
            f"root {str(root)!r} is not an existing directory — refusing to write "
            "to a phantom worktree path. Re-run `worktree create` and use its "
            "exact printed path (never a fabricated or shell-variable path)."
        )


def _iter_dir(root: Path, iter_n: int) -> Path:
    return _receipts_root(root) / f"iter-{iter_n}"


def _receipt_path(root: Path, iter_n: int, stage: str) -> Path:
    return _iter_dir(root, iter_n) / f"{stage}.json"


def _validate_stage(stage: str) -> None:
    if not _STAGE_SAFE_RE.match(stage):
        raise ValueError(
            f"stage {stage!r} is not filename-safe — must match [A-Za-z][A-Za-z0-9_-]{{0,63}}"
        )


def write(
    *,
    iter: int,  # noqa: A002 — public field name matches schema/PLAN
    stage: str,
    verdict: Verdict,
    root: Path = Path("."),
    written_at: str | None = None,
) -> Path:
    """Write one receipt atomically. Returns the resolved file path.

    Overwrites if the same (iter, stage) already exists — auto-retry under
    ADR-005 explicitly relies on a second write replacing the first.
    """
    _validate_stage(stage)
    _require_existing_root(root)
    record = IterReceipt(
        iter=iter,
        stage=stage,
        verdict=verdict,
        written_at=written_at or _utc_now_iso(),
    )
    path = _receipt_path(root, iter, stage)
    atomic_write(path, json.dumps(record.model_dump(), ensure_ascii=False, sort_keys=True))
    return path


def set_iter_marker(*, iter: int, root: Path = Path(".")) -> Path:  # noqa: A002
    """Atomically write the `.current-iter` driver marker (replaces shell `printf > file`).

    Phase 3 contract — the autoloop driver writes this at iter start so each
    stage's receipt-emit shell guard can read it. Atomic semantics matter:
    a crash between `printf` truncation and write completion leaves the file
    empty, causing every subsequent stage receipt write to fail with
    `--iter ""` argparse error. atomic_write (tempfile + os.replace) prevents
    that corruption window.
    """
    if iter < 1:
        raise ValueError(f"iter must be >= 1 (got {iter})")
    _require_existing_root(root)
    path = _receipts_root(root) / ".current-iter"
    atomic_write(path, str(iter))
    return path


def patch_runtime_block(
    *,
    context_path: Path,
    counter: str,
    key: str | None = None,
    value: int | str | None = None,
    reset_keys: list[str] | None = None,
    clear: bool = False,
) -> Path:
    """Atomically patch a single field of the LoopContext runtime: block.

    PLAN-loop-mid-stop-and-review-skip post-commit P1 #3 — the autoloop
    driver prompt previously instructed the LLM to "persist to
    runtime.stage_retry_counts in the loop-context file" with no Python
    helper reachable from a shell command, leaving the persist path
    vulnerable to non-atomic plain-YAML rewrites. This function is the
    CLI-callable analog that uses ``save_loop_context`` (which delegates
    to ``io_utils.atomic_write``).

    counter ∈ {stage_retry_counts, checklist_fail_counts,
        criterion_ambiguity_counts, convergence_streak, last_test_result}.

    Modes:
      - ``clear=True`` resets the named counter (loop-close cleanup, Step 7.0).
      - ``key`` + ``value`` → set ``runtime.<counter>[key] = value`` (dict counters).
      - ``key`` only → delete ``runtime.<counter>[key]``.
      - ``reset_keys`` → for dict counters, delete all listed keys at once.
      - Scalar counters (convergence_streak): pass ``value`` without ``key``.

    Round-trips through pydantic so the YAML stays schema-valid.
    """
    from harness_maker.autoloop_driver import (
        LoopContext,
        RuntimeBlock,
        parse_loop_context,
        save_loop_context,
    )

    ctx = parse_loop_context(context_path)
    runtime = ctx.runtime or RuntimeBlock()

    if clear:
        if counter == "convergence_streak":
            runtime.convergence_streak = 0
        elif counter in (
            "stage_retry_counts",
            "checklist_fail_counts",
            "criterion_ambiguity_counts",
        ):
            getattr(runtime, counter).clear()
        else:
            raise ValueError(f"clear not supported for counter={counter!r}")
    elif counter == "convergence_streak":
        if value is None:
            raise ValueError("convergence_streak requires --value")
        runtime.convergence_streak = int(value)
    elif counter in (
        "stage_retry_counts",
        "checklist_fail_counts",
        "criterion_ambiguity_counts",
    ):
        target = getattr(runtime, counter)
        if reset_keys:
            for k in reset_keys:
                target.pop(k, None)
        elif key is not None and value is None:
            target.pop(key, None)
        elif key is not None and value is not None:
            target[key] = int(value)
        else:
            raise ValueError(f"{counter} requires --key (+ --value), --reset-keys, or --clear")
    else:
        raise ValueError(f"unknown counter: {counter!r}")

    ctx_with_runtime = ctx.model_copy(update={"runtime": runtime})
    if not isinstance(ctx_with_runtime, LoopContext):  # safety net
        raise RuntimeError("model_copy returned non-LoopContext")
    save_loop_context(ctx_with_runtime, context_path)
    return context_path


def read(path: Path) -> IterReceipt:
    """Load + validate a receipt from disk. Raises ValidationError on drift."""
    return IterReceipt.model_validate_json(path.read_text(encoding="utf-8"))


def list_iter(*, iter: int, root: Path = Path(".")) -> list[IterReceipt]:  # noqa: A002
    """Return all receipts written for the given iter. Empty list when none."""
    iter_dir = _iter_dir(root, iter)
    if not iter_dir.is_dir():
        return []
    out: list[IterReceipt] = []
    for entry in sorted(iter_dir.iterdir()):
        if entry.suffix != ".json" or not entry.is_file():
            continue
        try:
            out.append(read(entry))
        except (ValidationError, json.JSONDecodeError) as exc:
            # Corrupt receipt → treated as absent by verify(); log so the
            # loop-stuck failure path surfaces "file exists but malformed"
            # instead of "stage never ran". list_iter stays non-throwing.
            logger.warning("Skipping corrupt receipt %s: %s", entry, exc)
            continue
    return out


def verify(
    *,
    iter: int,  # noqa: A002
    expected_stages: list[str],
    root: Path = Path("."),
) -> VerifyResult:
    """Gate 0 contract: every expected stage present with ``verdict == "pass"``.

    Missing stages and non-pass verdicts are surfaced separately so the
    driver can pick targeted retry actions.
    """
    found: dict[str, IterReceipt] = {r.stage: r for r in list_iter(iter=iter, root=root)}
    missing: list[str] = []
    non_pass: list[str] = []
    for stage in expected_stages:
        if stage not in found:
            missing.append(stage)
        elif found[stage].verdict != "pass":
            non_pass.append(stage)
    return VerifyResult(
        all_passed=not missing and not non_pass,
        missing=missing,
        non_pass=non_pass,
    )


# ── CLI ──────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m harness_maker.iter_receipts",
        description="Per-stage iteration receipts (Gate 0 source-of-truth).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="Write one receipt.")
    w.add_argument("--iter", type=int, required=True)
    w.add_argument("--stage", required=True)
    w.add_argument("--verdict", required=True, choices=("pass", "fail", "skipped"))
    w.add_argument("--root", default=".", type=Path)
    # --written-at: test-only flag (deterministic timestamp). NOT for operators
    # — allows backdating receipts which would corrupt Gate 0's audit trail.
    # Hidden from help and rejected unless HM_TEST_RECEIPTS=1 is set.
    w.add_argument("--written-at", default=None, help=argparse.SUPPRESS)

    sim = sub.add_parser(
        "set-iter-marker",
        help="Atomically write the .current-iter driver marker (Phase 3 contract).",
    )
    sim.add_argument("--iter", type=int, required=True)
    sim.add_argument("--root", default=".", type=Path)

    pr = sub.add_parser(
        "patch-runtime",
        help="Atomically patch a runtime: counter in loop-context YAML.",
    )
    pr.add_argument(
        "--context",
        required=True,
        type=Path,
        help="Path to work-docs/loop-context/<slug>.yaml",
    )
    pr.add_argument(
        "--counter",
        required=True,
        choices=(
            "stage_retry_counts",
            "checklist_fail_counts",
            "criterion_ambiguity_counts",
            "convergence_streak",
        ),
    )
    pr.add_argument("--key", default=None, help="Dict key (e.g., 'iter-3:review')")
    pr.add_argument(
        "--value",
        default=None,
        help="New value. For dict counters set value; for convergence_streak set scalar.",
    )
    pr.add_argument(
        "--reset-keys",
        default=None,
        help="Comma-separated dict keys to delete (e.g., 'iter-3:execute,iter-3:review').",
    )
    pr.add_argument(
        "--clear",
        action="store_true",
        help="Clear the entire counter (dict → {}, convergence_streak → 0). Step 7.0 cleanup.",
    )

    r = sub.add_parser("read", help="Read a receipt by (iter,stage) or path.")
    r.add_argument("--iter", type=int)
    r.add_argument("--stage")
    r.add_argument("--root", default=".", type=Path)
    r.add_argument("--path", type=Path)

    li = sub.add_parser("list", help="List all receipts for one iter.")
    li.add_argument("--iter", type=int, required=True)
    li.add_argument("--root", default=".", type=Path)

    v = sub.add_parser("verify", help="Gate 0 check; exit 0 = pass, 1 = fail.")
    v.add_argument("--iter", type=int, required=True)
    v.add_argument(
        "--expected",
        required=True,
        help="Comma-separated stage names (e.g. execute,review).",
    )
    v.add_argument("--root", default=".", type=Path)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "write":
        if args.written_at is not None and os.environ.get("HM_TEST_RECEIPTS") != "1":
            sys.stderr.write(
                "write: --written-at requires HM_TEST_RECEIPTS=1 "
                "(test-only flag — backdating receipts corrupts Gate 0 audit trail)\n"
            )
            return 1
        try:
            path = write(
                iter=args.iter,
                stage=args.stage,
                verdict=args.verdict,
                root=args.root,
                written_at=args.written_at,
            )
        except (ValidationError, ValueError) as exc:
            sys.stderr.write(f"write failed: {exc}\n")
            return 1
        sys.stdout.write(str(path) + "\n")
        return 0

    if args.cmd == "set-iter-marker":
        try:
            path = set_iter_marker(iter=args.iter, root=args.root)
        except (ValueError, OSError) as exc:
            sys.stderr.write(f"set-iter-marker failed: {exc}\n")
            return 1
        sys.stdout.write(str(path) + "\n")
        return 0

    if args.cmd == "patch-runtime":
        reset_keys = (
            [k.strip() for k in args.reset_keys.split(",") if k.strip()]
            if args.reset_keys
            else None
        )
        try:
            path = patch_runtime_block(
                context_path=args.context,
                counter=args.counter,
                key=args.key,
                value=args.value,
                reset_keys=reset_keys,
                clear=args.clear,
            )
        except (ValueError, FileNotFoundError, ValidationError) as exc:
            sys.stderr.write(f"patch-runtime failed: {exc}\n")
            return 1
        sys.stdout.write(str(path) + "\n")
        return 0

    if args.cmd == "read":
        if args.path is not None:
            path = args.path
        elif args.iter is not None and args.stage is not None:
            path = _receipt_path(args.root, args.iter, args.stage)
        else:
            sys.stderr.write("read: provide --path OR both --iter and --stage\n")
            return 2
        try:
            rec = read(path)
        except (FileNotFoundError, ValidationError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"read: {exc}\n")
            return 1
        sys.stdout.write(json.dumps(rec.model_dump(), ensure_ascii=False, sort_keys=True) + "\n")
        return 0

    if args.cmd == "list":
        recs = list_iter(iter=args.iter, root=args.root)
        for r in recs:
            sys.stdout.write(json.dumps(r.model_dump(), ensure_ascii=False, sort_keys=True) + "\n")
        return 0

    if args.cmd == "verify":
        expected = [s.strip() for s in args.expected.split(",") if s.strip()]
        result = verify(iter=args.iter, expected_stages=expected, root=args.root)
        if result.all_passed:
            sys.stdout.write(f"PASS iter={args.iter} stages={','.join(expected)}\n")
            return 0
        sys.stdout.write(
            f"FAIL iter={args.iter} missing={','.join(result.missing) or '-'} "
            f"non_pass={','.join(result.non_pass) or '-'}\n"
        )
        return 1

    return 2  # pragma: no cover — argparse enforces required subcommand


if __name__ == "__main__":
    sys.exit(main())
