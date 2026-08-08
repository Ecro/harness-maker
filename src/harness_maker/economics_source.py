"""Transcript adapter — locate Claude Code session files and normalise them into turns.

Never raises on malformed input. The failure mode that matters here is not a crash but
silent zeroing (the four always-zero telemetry token fields went unnoticed for months),
so every skip is counted by reason and surfaced as `IngestionDiagnostics`.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from harness_maker.economics import TokenUsage, TurnRecord

_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
_PATH_KEYS = ("file_path", "path", "notebook_path")
_WORKTREE_RE = re.compile(r"/\.worktrees/([^/]+)")
# Bounds on untrusted transcript-derived values. The line cap bounds DOWNSTREAM
# processing of one adversarial record — NOT resident memory: it is checked after the
# line is already read (see the note at the check itself, which is the honest statement).
# An earlier version of this comment claimed the memory bound the check cannot provide,
# and the two comments contradicted each other in the same file.
# The key cap keeps such a value from becoming an unbounded JSON map key in the report.
_MAX_LINE_BYTES = 4 * 1024 * 1024
_MAX_KEY_CHARS = 64


def _clip(value: Any) -> str | None:
    """Bound and sanitise a transcript string before it can become a report key."""
    if not isinstance(value, str) or not value:
        return None
    cleaned = "".join(ch for ch in value if ch.isprintable())
    return cleaned[:_MAX_KEY_CHARS] or None


class IngestionDiagnostics(BaseModel):
    """ADR-009 — a binary "did we price anything" check cannot see PARTIAL drift."""

    model_config = ConfigDict(strict=True, extra="forbid")

    dirs_scanned: int = 0
    files_discovered: int = 0
    files_read: int = 0
    files_failed: int = 0
    lines_total: int = 0
    assistant_lines: int = 0
    # Records dropped by grouping: sum over groups of (len(group) - 1), across ALL groups
    # including those a later filter skips. A residual (`assistant_lines - turns`) would
    # fold in `no_usage`/`foreign_cwd` skips and corrupt both this field and `coverage`.
    duplicate_records_collapsed: int = 0
    # `assistant_lines` in CALLS rather than records. Every other counter below is
    # group-counted, so the coverage denominator has to be too — see `coverage`.
    assistant_calls: int = 0
    turns_with_usage: int = 0
    skipped_by_reason: dict[str, int] = Field(default_factory=dict)

    @property
    def coverage(self) -> float:
        """Priced turns over IN-WINDOW assistant CALLS — drops when a format change lands.

        Window-excluded entries are removed from the denominator: otherwise a narrow
        `--days` makes coverage collapse toward zero and the drift signal this exists
        to carry becomes indistinguishable from ordinary filtering.

        Both terms are group-counted. `assistant_lines` is not: it is the raw record
        count, and subtracting a group-counted `outside_window` from it would mix units —
        collapsing divides the numerator by ~2.2 while leaving the denominator alone, so
        coverage would sit near 0.45 forever and retire the very signal it exists to be.
        """
        denominator = self.assistant_calls - self.skipped_by_reason.get("outside_window", 0)
        return self.turns_with_usage / denominator if denominator > 0 else 0.0


class IngestionResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    turns: list[TurnRecord] = Field(default_factory=list)
    diagnostics: IngestionDiagnostics = Field(default_factory=IngestionDiagnostics)


def default_transcript_root() -> Path:
    return Path.home() / ".claude" / "projects"


def resolve_project_root(path: Path) -> Path:
    """Collapse a worktree path back to the base repo before it is encoded.

    Every `/hm:` stage under `worktree.feature_branch_workflow` runs inside
    `.worktrees/<slug>/`, so an unresolved root encodes to `-base--worktrees-slug` and
    discovery then matches neither the base directory nor its sibling worktrees — the
    report truncates silently in the harness's own normal operating mode.
    """
    text = str(path)
    match = re.search(r"^(.*?)/\.worktrees/[^/]+", text)
    return Path(match.group(1)) if match else path


def encode_project_dir(path: Path) -> str:
    """Claude Code encodes the LAUNCH cwd into the project directory name.

    `/`, `.` and `_` all become `-`, so `/repo/proj/.worktrees/demo` is
    `-repo-proj--worktrees-demo` — the double dash is the `/.` pair, not a separator.

    The `_` arm was missing until 2026-08-08, and its absence was silent: every project whose
    path contains an underscore matched no directory, so the reader returned zero turns and the
    report said `$0` rather than erroring. `/home/noel/strange_chess` hid $1,637 of real spend
    that way. Verified against five underscore-path projects, all hyphen-encoded on disk with no
    underscore-encoded sibling.

    **What the widening does and does not guarantee.** It enlarges the collision set: `/x/a_b`
    and `/x/a-b` now encode alike, so a foreign project's directory can be discovered. The
    per-turn `is_own_cwd` check below drops those turns — **but only the ones that carry a
    `cwd`**. `is_own_cwd` returns True for `cwd is None` by design (older transcript lines), so
    a collision plus a `cwd`-less line does admit a foreign turn. Current-format lines all carry
    `cwd`, and the output is a local aggregate, which is why this is a stated limit rather than
    a blocker — but the earlier wording here claimed the boundary was unconditional, and it is
    not. `test_cwd_filter_is_the_real_boundary_when_two_paths_encode_alike` pins both branches.
    """
    return re.sub(r"[/._]", "-", str(path))


def discover_transcript_dirs(project_path: Path, *, transcript_root: Path) -> list[Path]:
    """The base project dir PLUS this project's own worktree-launched siblings (ADR-007).

    A session started from inside `.worktrees/<slug>/` gets its own project directory;
    missing those would under-report exactly the stages that run under isolation.
    """
    project_path = resolve_project_root(project_path)
    try:
        if not transcript_root.is_dir():
            return []
        children = sorted(transcript_root.iterdir())
    except OSError:
        return []

    # Prefix matching is deliberately kept: a worktree is DELETED when its task lands,
    # but its transcripts survive, so requiring the directory to still exist on disk
    # would silently drop historical worktree sessions. The lossy encoding (`/` and `.`
    # both become `-`) means a foreign project can collide with this prefix, so the
    # real boundary is the per-turn `cwd` check in `load_turns`, not the name.
    base_name = encode_project_dir(project_path)
    found: list[Path] = []
    for child in children:
        try:
            if child.is_symlink() or not child.is_dir():
                continue
        except OSError:
            continue
        if child.name == base_name or child.name.startswith(f"{base_name}--worktrees-"):
            found.append(child)
    return found


def is_own_cwd(cwd: str | None, project_path: Path) -> bool:
    """A turn belongs to this project only if its cwd is the root or under it.

    Guards the prefix-match collision above: `/repo--worktrees-demo` encodes to the
    same shape as a real worktree of `/repo`, but its turns carry a cwd that is not
    under `/repo/`. A turn with no cwd at all is accepted (older transcript lines).
    """
    if cwd is None:
        return True
    base = str(project_path).rstrip("/")
    return cwd == base or cwd.startswith(f"{base}/")


def normalise_written_path(raw: str, project_path: Path) -> str:
    """Collapse worktree and base spellings of one logical file onto a repo-relative path.

    Without this the feature-branch model under-counts REWORK: the same file edited from
    `.worktrees/<slug>/` and from the base would never compare equal.
    """
    if not raw.startswith("/"):
        return raw
    base = str(project_path).rstrip("/")
    wt = re.match(rf"^{re.escape(base)}/\.worktrees/[^/]+/(.+)$", raw)
    if wt:
        return wt.group(1)
    if raw.startswith(f"{base}/"):
        return raw[len(base) + 1 :]
    return raw


def derive_task_slug(git_branch: str | None, cwd: str | None) -> str | None:
    """Machine-derived task identity. Absent case is explicit: None, never a guess."""
    if git_branch and git_branch.startswith("hm/"):
        slug = git_branch[len("hm/") :].strip("/")
        if slug:
            return slug
    if cwd:
        match = _WORKTREE_RE.search(cwd)
        if match:
            return match.group(1)
    return None


def _written_paths(content: Any, project_path: Path) -> tuple[str, ...]:
    if not isinstance(content, list):
        return ()
    out: list[str] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        if block.get("name") not in _WRITE_TOOLS:
            continue
        tool_input = block.get("input")
        if not isinstance(tool_input, dict):
            continue
        for key in _PATH_KEYS:
            raw = tool_input.get(key)
            if isinstance(raw, str) and raw:
                norm = normalise_written_path(raw, project_path)
                if norm not in out:
                    out.append(norm)
                break
    return tuple(out)


def _usage(raw: Any) -> TokenUsage | None:
    if not isinstance(raw, dict):
        return None
    creation = raw.get("cache_creation")
    if isinstance(creation, dict) and (
        "ephemeral_5m_input_tokens" in creation or "ephemeral_1h_input_tokens" in creation
    ):
        # The tier breakdown wins over the rolled-up cache_creation_input_tokens on the
        # same line — adding both would double-count.
        write_5m = _int(creation.get("ephemeral_5m_input_tokens"))
        write_1h = _int(creation.get("ephemeral_1h_input_tokens"))
    else:
        write_5m = _int(raw.get("cache_creation_input_tokens"))
        write_1h = 0
    return TokenUsage(
        input_tokens=_int(raw.get("input_tokens")),
        output_tokens=_int(raw.get("output_tokens")),
        cache_read_tokens=_int(raw.get("cache_read_input_tokens")),
        cache_write_5m_tokens=write_5m,
        cache_write_1h_tokens=write_1h,
    )


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _parse_ts(raw: Any) -> datetime | None:
    """Always tz-aware. A naive timestamp compared against an aware cutoff raises
    TypeError, which would break the never-raise contract from one drifted line."""
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _transcript_files(directory: Path) -> list[Path]:
    """Top-level session files plus each session's `subagents/` directory."""
    files = sorted(directory.glob("*.jsonl"))
    files += sorted(directory.glob("*/subagents/*.jsonl"))
    return files


# Envelopes the harness injects as `type: "user"` lines that nobody typed. ADR-005
# names the boundary classes explicitly; treating any of these as a user message would
# mark every slash-command invocation and every finished background task a new run.
_SYNTHETIC_USER_PREFIXES: tuple[str, ...] = (
    "<command-message>",
    "<command-name>",
    "<command-args>",
    "<local-command-",
    "<task-notification",
    "<system-reminder",
    "<user-prompt-submit-hook>",
    "<bash-input>",
    "<bash-stdout",
    "<bash-stderr",
)


def is_human_user_line(data: dict[str, Any]) -> bool:
    """Did a person actually say something on this line?

    The commonest `type: "user"` line by far is a tool_result being fed back — not a
    boundary at all. `isMeta` carries the expanded slash-command template. What is
    left is either a typed string or text blocks, minus the synthetic envelopes above.
    """
    if data.get("type") != "user" or data.get("isMeta"):
        return False
    content = (
        (data.get("message") or {}).get("content")
        if isinstance(data.get("message"), dict)
        else None
    )
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
        ]
        if not parts:
            return False
        text = "\n".join(parts)
    else:
        return False
    stripped = text.lstrip()
    if not stripped:
        return False
    return not stripped.startswith(_SYNTHETIC_USER_PREFIXES)


def _turn_from_line(
    data: dict[str, Any], project_path: Path, *, preceded_by_user: bool = False
) -> TurnRecord | None:
    message = data.get("message")
    if not isinstance(message, dict):
        return None
    usage = _usage(message.get("usage"))
    if usage is None:
        return None
    ts = _parse_ts(data.get("timestamp"))
    if ts is None:
        return None
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else None
    branch = data.get("gitBranch") if isinstance(data.get("gitBranch"), str) else None
    return TurnRecord(
        session_id=str(data.get("sessionId") or ""),
        ts=ts,
        model=_clip(message.get("model")),
        usage=usage,
        attribution_skill=_clip(data.get("attributionSkill")),
        attribution_agent=_clip(data.get("attributionAgent")),
        is_sidechain=bool(data.get("isSidechain")),
        task_slug=derive_task_slug(branch, cwd),
        written_paths=_written_paths(message.get("content"), project_path),
        cwd=cwd,
        git_branch=branch,
        uuid=data.get("uuid") if isinstance(data.get("uuid"), str) else None,
        preceded_by_user=preceded_by_user,
        message_id=message.get("id") if isinstance(message.get("id"), str) else None,
    )


def _collapse(group: list[TurnRecord]) -> TurnRecord:
    """One API call's records into one turn — usage taken once, metadata unioned.

    The records are NOT interchangeable. Each carries a different content block, so the
    `tool_use` block — and therefore `written_paths` — lives in exactly one of them;
    dropping it makes a turn that wrote files look like it wrote none, silently
    re-labelling PRODUCE/REWORK as OTHER in the classifier the whole model rests on.
    `uuid` is the retroactive-classification verdict cache key, so its winner must be
    stable across runs or the cache invalidates on every report.

    Measured on the frozen corpus (5,757 multi-record groups): every field except
    `output_tokens` is identical within a group, and `output_tokens` differs in 1. The
    rules below therefore agree with "take any record" on real data — they exist so the
    answer is defined rather than accidental.
    """
    first = group[0]
    if len(group) == 1:
        return first
    # Ties resolve to the LAST record: output_tokens grows as a response streams, so the
    # final record carries the complete count.
    best = first
    for turn in group[1:]:
        if turn.usage.output_tokens >= best.usage.output_tokens:
            best = turn
    paths: dict[str, None] = {}
    for turn in group:
        for path in turn.written_paths:
            paths.setdefault(path, None)

    def _first_set(attr: str) -> Any:
        for turn in group:
            value = getattr(turn, attr)
            if value is not None:
                return value
        return None

    # `uuid`, `ts`, `session_id`, `preceded_by_user`, `is_sidechain` and `message_id` come
    # from `first` via the copy base — file order, so they are stable between runs.
    return first.model_copy(
        update={
            "usage": best.usage,
            "written_paths": tuple(paths),
            "model": _first_set("model"),
            "attribution_skill": _first_set("attribution_skill"),
            "attribution_agent": _first_set("attribution_agent"),
            "cwd": _first_set("cwd"),
            "git_branch": _first_set("git_branch"),
            "task_slug": _first_set("task_slug"),
        }
    )


def load_turns(
    project_path: Path,
    *,
    transcript_root: Path | None = None,
    days: int | None = None,
    now: datetime | None = None,
) -> IngestionResult:
    root = transcript_root if transcript_root is not None else default_transcript_root()
    # Resolve ONCE here so path normalisation, the cwd boundary and discovery all agree
    # on the same base — a worktree root would otherwise reject its own base-dir turns.
    project_path = resolve_project_root(project_path)
    diag = IngestionDiagnostics()
    skipped: Counter[str] = Counter()
    turns: list[TurnRecord] = []
    groups_seen = 0

    cutoff: datetime | None = None
    if days is not None:
        cutoff = (now or datetime.now(UTC)) - timedelta(days=days)

    directories = discover_transcript_dirs(project_path, transcript_root=root)
    diag.dirs_scanned = len(directories)

    for directory in directories:
        for path in _transcript_files(directory):
            diag.files_discovered += 1
            try:
                # Streamed, not read_text()+splitlines(): a transcript reaches ~10 MB and
                # the store ~100 MB, and the two-step form holds both the whole string and
                # the whole list at once.
                handle = path.open(encoding="utf-8", errors="replace")
            except OSError:
                diag.files_failed += 1
                continue
            diag.files_read += 1
            # Reset per file: a trailing user message in one session must not mark the
            # first turn of the next. Any line we cannot read clears it too — a
            # fail-closed False routes the boundary to `unknown` (ADR-005) rather than
            # to a guessed continuation.
            pending_user = False
            # Grouping is per FILE, and it precedes the cwd/window filters. Per-file
            # because main-loop and subagent records live in separate transcripts
            # (`*/subagents/agent-*.jsonl`) and must never merge; before the filters so a
            # group is atomic — it falls wholly inside or wholly outside the window
            # rather than being split across the boundary.
            file_groups: dict[str, list[TurnRecord]] = {}
            group_order: list[str] = []
            with handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    diag.lines_total += 1
                    # `.encode()` because the constant is named for BYTES and `line` is a
                    # str: comparing characters let a multi-byte record run past the
                    # documented bound by up to 4x. (The bound is still enforced after the
                    # line is resident — a bounded read is a larger change and is recorded
                    # as a known limitation rather than claimed.)
                    if len(line.encode("utf-8", errors="ignore")) > _MAX_LINE_BYTES:
                        skipped["oversize_line"] += 1
                        pending_user = False
                        continue
                    try:
                        data = json.loads(line)
                    except (ValueError, RecursionError):
                        skipped["json_error"] += 1
                        pending_user = False
                        continue
                    if not isinstance(data, dict) or data.get("type") != "assistant":
                        skipped["not_assistant"] += 1
                        pending_user = isinstance(data, dict) and is_human_user_line(data)
                        continue
                    diag.assistant_lines += 1
                    turn = _turn_from_line(data, project_path, preceded_by_user=pending_user)
                    pending_user = False
                    if turn is None:
                        skipped["no_usage"] += 1
                        continue
                    # A record with no `message.id` is never grouped: it gets a key no
                    # other record can share. An implementation that bucketed them under
                    # one falsy key would collapse a whole legacy-format transcript into a
                    # single turn — the absent-case failure this repo has shipped 8 times.
                    key = turn.message_id or f"\0no-id\0{len(group_order)}"
                    bucket = file_groups.get(key)
                    if bucket is None:
                        file_groups[key] = [turn]
                        group_order.append(key)
                    else:
                        bucket.append(turn)

            groups_seen += len(group_order)
            for key in group_order:
                group = file_groups[key]
                # Counted across ALL groups, including those the filters below skip:
                # `assistant_calls` must stay the true call count or the coverage
                # denominator drifts by the skipped groups' duplicates.
                diag.duplicate_records_collapsed += len(group) - 1
                turn = _collapse(group)
                if not is_own_cwd(turn.cwd, project_path):
                    skipped["foreign_cwd"] += 1
                    continue
                if cutoff is not None and turn.ts < cutoff:
                    skipped["outside_window"] += 1
                    continue
                turns.append(turn)

    turns.sort(key=lambda t: t.ts)
    diag.turns_with_usage = len(turns)
    # Counted directly from the groups, plus the records that had no usage to group BY.
    # The old form `assistant_lines - duplicate_records_collapsed` computes the same value
    # — the two record-counted terms cancel, because `assistant_lines` is incremented only
    # after the oversize / json-error / not-assistant skips — but it reads as a mix of
    # units, and a reader has to reconstruct that proof to trust the denominator.
    # `test_assistant_calls_equals_groups_plus_unpriceable` pins the identity.
    diag.assistant_calls = groups_seen + skipped["no_usage"]
    diag.skipped_by_reason = dict(skipped)
    return IngestionResult(turns=turns, diagnostics=diag)
