"""The named world model's handle rules: derivation, grammar and the reserved set."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

DEFAULT_NAME = "Maker"
DEFAULT_HANDLE = "maker"
NAME_MAX = 40
HANDLE_MAX = 64

# Every fixed skill name a harness renders. Kept here, not derived from synthesize, because
# models.py validates against it and cannot import synthesize (cycle); a unit test asserts
# it covers synthesize._ALL_SKILLS so a new shipped skill cannot become a legal handle.
RESERVED_HANDLES: frozenset[str] = frozenset(
    {
        "verify-before-completion",
        "autoloop-driver",
        "ai-readiness-rubric",
        "agent-quality-rubric",
        "conditional-router",
        "worktree-isolator",
        "security-scanner",
        "context-linter",
        "refdocs-search",
        "second-opinion-gate",
        "intent-layer",
        "targeted-test-selection",
        "project-knowledge",
        "world-model",
        "hm",
    }
)
RESERVED_PREFIX = "hm-"

_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cs", "Zl", "Zp"})

_GRAMMAR = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

HandleRule = Literal["collision", "reserved-prefix", "grammar", "length"]


def handle_error(handle: str) -> HandleRule | None:
    """The rule a handle breaks, or None. The order makes the message name the real cause."""
    if len(handle) > HANDLE_MAX:
        return "length"
    if _GRAMMAR.fullmatch(handle) is None:
        return "grammar"
    if handle.startswith(RESERVED_PREFIX):
        return "reserved-prefix"
    if handle in RESERVED_HANDLES:
        return "collision"
    return None


def derive_handle(name: str) -> str | None:
    """An ASCII skill name for a display name, or None when the operator must choose one."""
    ascii_only = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    if len(slug) > HANDLE_MAX:
        cut = slug[:HANDLE_MAX]
        slug = (cut.rsplit("-", 1)[0] if "-" in cut else cut).strip("-")
    if not slug or handle_error(slug) is not None:
        return None
    return slug


NameRule = Literal["whitespace", "length", "control"]

_NAME_MESSAGES: dict[str, str] = {
    "whitespace": "name must be non-empty with no leading or trailing whitespace",
    "length": f"name must be at most {NAME_MAX} characters",
    "control": "name must be a single line without control characters or noncharacters",
}

# U+FFFE/U+FFFF are outside YAML's printable set: a name carrying them renders a harness.yaml
# the next load rejects (REVIEW a1a2d1c0).
_NONCHARACTERS = frozenset("\ufffe\uffff")


def name_rule(name: str) -> NameRule | None:
    """The rule a display name breaks, or None — the code callers localize (SPEC S8)."""
    if not name or name != name.strip():
        return "whitespace"
    if len(name) > NAME_MAX:
        return "length"
    # Control characters and line/paragraph separators break the single YAML line and the
    # always-loaded pointer; format characters (emoji ZWJ) and unassigned points do not.
    if any(unicodedata.category(c) in _FORBIDDEN_CATEGORIES or c in _NONCHARACTERS for c in name):
        return "control"
    return None


def name_error(name: str) -> str | None:
    """Why a display name cannot be used (English), or None.

    It lands in YAML and in an always-loaded line.
    """
    rule = name_rule(name)
    return None if rule is None else _NAME_MESSAGES[rule]


def main(argv: Sequence[str] | None = None) -> int:
    """`hm world_model digest` — the Maker router's briefing. Always exits 0 (SPEC S1)."""
    from harness_maker import command_registry

    guard = command_registry.guard_or_none("world_model", argv)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(prog="hm world_model")
    sub = parser.add_subparsers(dest="command", required=True)
    digest_p = sub.add_parser("digest", help="Print the read-only task-state digest as JSON")
    digest_p.add_argument("--root", default=".")
    digest_p.add_argument("--session-id", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)
    from harness_maker import world_model_digest

    root = Path(args.root)
    payload = world_model_digest.digest(root, session_id=args.session_id or None)
    sys.stdout.write(world_model_digest.render(payload) + "\n")
    _record_maker_load(root, args.session_id or None)
    return 0


def _record_maker_load(root: Path, session_id: str | None) -> None:
    """Makes Maker use countable (SPEC S7). Best-effort: a lost row never fails the briefing,
    and a repo without `.claude/` is not a harness, so nothing is created there."""
    import json
    from datetime import UTC, datetime

    from harness_maker import io_utils, world_model_digest

    try:
        base = world_model_digest.base_root(root)
        if base is None or not (base / ".claude").is_dir():
            return
        row = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "event": "maker_load",
            "session_id": session_id,
        }
        path = base / ".claude/observability/world-model.jsonl"
        io_utils.append_atomic_line(path, json.dumps(row, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        return


if __name__ == "__main__":
    sys.exit(main())
