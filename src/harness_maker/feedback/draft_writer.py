"""Feedback draft writer — atomic, dedup, redaction.

PLAN-auto-feedback-2026-05 ADR-004 (5-field whitelist, free-text markdown body)
+ ADR-006 (dedup by ``sha256(trigger_signal_id, slug, YYYY-MM-DD)[:16]``).

Reuses ``telemetry._SECRET_PATTERNS`` for error_message redaction +
``io_utils.atomic_write`` for crash-safe writes. file_paths are hard-rejected
unless they start with ``.claude/`` — prevents user-repo content leaks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from harness_maker.io_utils import atomic_write
from harness_maker.telemetry import _SECRET_PATTERNS

_ERROR_MESSAGE_CAP = 256
_DEDUP_HASH_LEN = 16
# REVIEW round 1 P1-1 fix (2026-05-23): task_slug is embedded in the output
# filename via f-string. Without sanitization, a prompt-injected task_slug like
# "../../etc/cron.d/evil" produces a write outside .claude/observability/feedback/
# because atomic_write does `mkdir -p` + `os.replace`. Restrict to the same
# charset class used by other harness-maker slugs.
_TASK_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


class TriggerSignal(BaseModel):
    """Numeric-only signal evidence (id + count + duration_ms).

    No string fields besides the type-id itself — prevents user-content leak
    by construction.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str  # e.g. "hook-error", "silent-intent-miss", "build-break"
    count: int = Field(ge=0)
    duration_ms: int | None = Field(default=None, ge=0)


class FeedbackDraft(BaseModel):
    """The 5-field whitelist (ADR-004).

    Pydantic ``extra="forbid"`` + ``strict=True`` mean schema drift surfaces
    loudly. AST-walk drift test (Phase 6) re-enforces that every field added
    here also lands in PRIVACY.md feedback-module marker block.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    harness_maker_version: str
    ide: Literal["claude-code", "cursor", "codex"]
    os: str
    stage: str
    task_slug: str
    trigger_signal: TriggerSignal
    error_message: str | None = None
    file_paths: list[str] = Field(default_factory=list)

    @field_validator("task_slug")
    @classmethod
    def _validate_task_slug(cls, v: str) -> str:
        """Block path-traversal: task_slug ends up in the output filename.

        REVIEW round 1 P1-1 fix: only kebab-case identifiers + digits + underscores.
        """
        if not _TASK_SLUG_PATTERN.fullmatch(v):
            raise ValueError(
                f"task_slug must match [A-Za-z0-9_-]{{1,200}} (got {v!r}); "
                "PLAN-auto-feedback-2026-05 REVIEW round 1 P1-1 path-traversal guard"
            )
        return v

    @field_validator("error_message")
    @classmethod
    def _redact_and_cap_error(cls, v: str | None) -> str | None:
        """Reuse telemetry's known-secret patterns; cap to 256 chars."""
        if v is None:
            return v
        for pattern in _SECRET_PATTERNS:
            v = pattern.sub("[REDACTED]", v)
        if len(v) > _ERROR_MESSAGE_CAP:
            v = v[: _ERROR_MESSAGE_CAP - len("...<truncated>")] + "...<truncated>"
        return v

    @field_validator("file_paths")
    @classmethod
    def _reject_user_repo_paths(cls, v: list[str]) -> list[str]:
        """Hard-reject any path not starting with `.claude/` — prevents leak."""
        for p in v:
            if not isinstance(p, str) or not p.startswith(".claude/"):
                raise ValueError(
                    f"file_paths must start with '.claude/' to prevent user-repo "
                    f"content leak (got {p!r}); PLAN-auto-feedback-2026-05 ADR-004"
                )
        return v


def _dedup_hash(trigger_signal_id: str, task_slug: str, date: str) -> str:
    """SHA256 of (trigger, slug, date), truncated to 16 hex chars (ADR-006)."""
    key = f"{trigger_signal_id}|{task_slug}|{date}".encode()
    return hashlib.sha256(key).hexdigest()[:_DEDUP_HASH_LEN]


def _render_markdown(draft: FeedbackDraft, *, dedup: str, date: str) -> str:
    """Free-text markdown body (ADR-004 — drop bug.yml form alignment).

    The maintainer runs ``gh issue create --web --body-file <path>``; the
    browser pre-fills the body field with this markdown.
    """
    title = (
        f"[harness-maker {draft.harness_maker_version}] "
        f"{draft.trigger_signal.id} in /hm:{draft.stage}"
    )
    lines: list[str] = [
        f"# {title}",
        "",
        "## Metadata",
        f"- harness-maker: `{draft.harness_maker_version}`",
        f"- IDE: `{draft.ide}`",
        f"- OS: `{draft.os}`",
        f"- Stage: `/hm:{draft.stage}`",
        f"- Task slug: `{draft.task_slug}`",
        f"- Draft date: `{date}`",
        f"- Dedup hash: `{dedup}`",
        "",
        "## Trigger signal",
        f"- Type: `{draft.trigger_signal.id}`",
        f"- Count: `{draft.trigger_signal.count}`",
    ]
    if draft.trigger_signal.duration_ms is not None:
        lines.append(f"- Duration: `{draft.trigger_signal.duration_ms} ms`")
    if draft.error_message:
        lines += ["", "## Error message (redacted)", "", "```", draft.error_message, "```"]
    if draft.file_paths:
        lines += ["", "## Affected files (`.claude/` only)"]
        lines += [f"- `{p}`" for p in draft.file_paths]
    lines += [
        "",
        "---",
        "_Generated by harness-maker feedback module (opt-in via `feedback.enabled`)._",
        "",
    ]
    return "\n".join(lines)


def write(
    draft: FeedbackDraft,
    *,
    base_dir: Path,
    date: str | None = None,
) -> Path:
    """Write draft to ``base_dir/feedback/{date}-{slug}-{hash}.md`` atomically.

    Idempotent per (trigger_signal_id, slug, date): if the dedup-hashed file
    already exists today, returns the existing path unchanged (no rewrite,
    no second draft). Next-day re-emergence of the same trigger produces a
    fresh draft because the date component changes (ADR-006).
    """
    if date is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
    dedup = _dedup_hash(draft.trigger_signal.id, draft.task_slug, date)
    out_dir = base_dir / "feedback"
    out_path = out_dir / f"{date}-{draft.task_slug}-{dedup}.md"
    if out_path.exists():
        return out_path
    body = _render_markdown(draft, dedup=dedup, date=date)
    atomic_write(out_path, body)
    return out_path


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m harness_maker.feedback.draft_writer --json <draft-json>``.

    Reads a FeedbackDraft as JSON from --json or stdin. Writes the draft and
    prints the resolved path to stdout (one line, no trailing newline ambiguity).
    Exit 0 on success, 2 on validation failure.
    """
    parser = argparse.ArgumentParser(prog="harness_maker.feedback.draft_writer")
    parser.add_argument("--json", type=str, help="FeedbackDraft as JSON; reads stdin when omitted.")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(".claude/observability"),
        help="Observability dir (default: .claude/observability).",
    )
    args = parser.parse_args(argv)
    raw = args.json if args.json is not None else sys.stdin.read()
    try:
        payload = json.loads(raw)
        draft = FeedbackDraft.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid FeedbackDraft JSON: {exc}", file=sys.stderr)
        return 2
    path = write(draft, base_dir=args.base_dir)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
