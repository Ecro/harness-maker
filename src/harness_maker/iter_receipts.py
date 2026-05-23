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
    record = IterReceipt(
        iter=iter,
        stage=stage,
        verdict=verdict,
        written_at=written_at or _utc_now_iso(),
    )
    path = _receipt_path(root, iter, stage)
    atomic_write(path, json.dumps(record.model_dump(), ensure_ascii=False, sort_keys=True))
    return path


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
    w.add_argument("--written-at", default=None)

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
        try:
            path = write(
                iter=args.iter,
                stage=args.stage,
                verdict=args.verdict,
                root=args.root,
                written_at=args.written_at,
            )
        except (ValidationError, ValueError) as exc:
            sys.stderr.write(f"write: {exc}\n")
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
