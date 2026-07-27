"""What the carried context is made of — by category, by Bash kind, and by duplication.

`economics` prices turns; it does not say what the turns are carrying. This reads the same
transcripts and attributes every character that enters the context to the thing that put it
there, so a decision about what to cut is made against composition rather than intuition.

Characters, not tokens. The ratio varies by content type (JSON tool output tokenizes worse
than prose), so a token estimate here would be a second model stacked on a first. Shares are
what the caller needs and shares are what this reports.

Residency weighting was measured and deliberately NOT implemented: weighting each character
by the number of turns it survives (compaction boundaries resetting the segment) agreed with
the flat count to within +-5% on every category, because content enters roughly uniformly
across a session. The one exception is the compaction summary itself, which by construction
enters at a boundary and persists the whole following segment. Adding the weighting would be
a second implementation to keep correct for no change in the answer.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

# Ordered: the first pattern that matches wins, so the specific ones precede `git`/`other`.
_BASH_KINDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pytest", re.compile(r"\bpytest\b")),
    ("heredoc file-write", re.compile(r"<<\s*'?\w*EOF")),
    ("grep/rg", re.compile(r"\b(rg|grep)\b")),
    ("git diff/show/log", re.compile(r"\bgit (diff|show|log)\b")),
    ("git (other)", re.compile(r"\bgit\b")),
    ("mypy", re.compile(r"\bmypy\b")),
    ("ruff", re.compile(r"\bruff\b")),
    ("harness_maker CLI", re.compile(r"harness_maker\.")),
    ("inline python", re.compile(r"python -c")),
    ("file inspection", re.compile(r"\b(ls|cat|head|tail|wc|find|sed|awk)\b")),
)


class WriteAfterRead(BaseModel):
    """`Write` on an existing file requires a prior `Read`, so a rewrite sends the body twice."""

    model_config = ConfigDict(strict=True, extra="forbid")

    write_calls: int = 0
    write_chars: int = 0
    duplicate_calls: int = 0
    duplicate_chars: int = 0
    duplicate_share: float = 0.0


def classify_bash(command: str) -> str:
    """The `kind` buckets the RESEARCH document reports. `other` is a real bucket, not a gap."""
    flat = " ".join(command.split())
    for name, pattern in _BASH_KINDS:
        if pattern.search(flat):
            return name
    return "other"


def _size(value: object) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict | list):
        return len(json.dumps(value, ensure_ascii=False))
    return 0


def _classify_user_text(text: str) -> str:
    """Split the user role: almost none of it is a human typing.

    Injected content (skill bodies, slash-command bodies, reminders, task notifications)
    arrives on the `user` role, so counting the role as "the user" overstates human input by
    roughly three orders of magnitude.
    """
    if "<system-reminder>" in text:
        return "system-reminder"
    if "<command-name>" in text or "<local-command-stdout>" in text or "<command-args>" in text:
        return "slash-command-echo"
    if "[SYSTEM NOTIFICATION" in text[:120] or "<task-notification>" in text:
        return "task-notification"
    if "This session is being continued" in text[:300]:
        return "compaction-summary"
    if len(text) > 4000:
        return "slash-command-body"
    return "human-typed"


def _iter_records(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def compose(dirs: list[Path], project_path: Path) -> dict[str, Any]:
    """Aggregate composition over every transcript in `dirs` belonging to `project_path`.

    The per-turn `cwd` check is the boundary, not the directory name: `encode_project_dir`
    is lossy (both `/` and `.` become `-`), so a foreign project can land under a matching
    prefix. This mirrors `load_turns` rather than inventing a second rule.
    """
    from harness_maker.economics_source import is_own_cwd

    by_category: Counter[str] = Counter()
    by_bash_kind: Counter[str] = Counter()
    war = WriteAfterRead()

    for directory in dirs:
        for path in sorted(directory.glob("*.jsonl")):
            read_paths: set[str] = set()
            tool_name: dict[str, str] = {}
            bash_cmd: dict[str, str] = {}
            for rec in _iter_records(path):
                if not is_own_cwd(rec.get("cwd"), project_path):
                    continue
                message = rec.get("message")
                if not isinstance(message, dict):
                    continue
                role = message.get("role")
                content = message.get("content")
                blocks = content if isinstance(content, list) else [content]
                for block in blocks:
                    if isinstance(block, str):
                        key = _classify_user_text(block) if role == "user" else "assistant_text"
                        by_category[key] += len(block)
                        continue
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text = block.get("text") or ""
                        key = _classify_user_text(text) if role == "user" else "assistant_text"
                        by_category[key] += len(text)
                    elif btype == "thinking":
                        by_category["assistant_thinking"] += _size(block.get("thinking"))
                    elif btype == "tool_use":
                        name = str(block.get("name", "?"))
                        tid = str(block.get("id", ""))
                        tool_name[tid] = name
                        raw = block.get("input")
                        by_category["tool_call_input"] += _size(raw)
                        params = raw if isinstance(raw, dict) else {}
                        if name == "Bash":
                            command = str(params.get("command", ""))
                            bash_cmd[tid] = command
                            by_bash_kind[classify_bash(command)] += _size(raw)
                        file_path = str(params.get("file_path", ""))
                        if name == "Read" and file_path:
                            read_paths.add(file_path)
                        elif name == "Write" and file_path:
                            size = len(str(params.get("content", "")))
                            war.write_calls += 1
                            war.write_chars += size
                            if file_path in read_paths:
                                war.duplicate_calls += 1
                                war.duplicate_chars += size
                            read_paths.add(file_path)
                    elif btype == "tool_result":
                        tid = str(block.get("tool_use_id", ""))
                        size = _size(block.get("content"))
                        by_category["tool_result"] += size
                        if tool_name.get(tid) == "Bash":
                            by_bash_kind[classify_bash(bash_cmd.get(tid, ""))] += size

    total = sum(by_category.values())
    war.duplicate_share = war.duplicate_chars / war.write_chars if war.write_chars else 0.0

    def _shares(counter: Counter[str]) -> dict[str, dict[str, float | int]]:
        return {
            key: {"chars": value, "share": (value / total if total else 0.0)}
            for key, value in counter.most_common()
        }

    return {
        "total_chars": total,
        "by_category": _shares(by_category),
        "by_bash_kind": _shares(by_bash_kind),
        "write_after_read": war.model_dump(mode="json"),
    }
