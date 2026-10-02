"""The named world model's handle rules: derivation, grammar and the reserved set."""

from __future__ import annotations

import re
import unicodedata
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


def name_error(name: str) -> str | None:
    """Why a display name cannot be used, or None. It lands in YAML and an always-loaded line."""
    if not name or name != name.strip():
        return "name must be non-empty with no leading or trailing whitespace"
    if len(name) > NAME_MAX:
        return f"name must be at most {NAME_MAX} characters"
    # Control characters and line/paragraph separators break the single YAML line and the
    # always-loaded pointer; format characters (emoji ZWJ) and unassigned points do not.
    if any(unicodedata.category(c) in _FORBIDDEN_CATEGORIES for c in name):
        return "name must be a single line without control characters"
    return None
