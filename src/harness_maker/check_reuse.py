"""The `hm check --reuse` decision: may a recorded gate result stand for this tree?"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any

#: pytest reads these before a `-p` plugin's audit hook exists, so the read-set never sees them.
RUNNER_CONFIGS = frozenset({"pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"})

#: Miss reasons in precedence order (IRR-003): the first that applies is reported.
REASONS = (
    "no-record",
    "legacy-record",
    "bad-declaration",
    "key",
    "code",
    "added-removed",
    "undeclared",
    "head",
    "voided",
    "no-read-set",
)

#: Record fields that must equal the current run's for any reuse. HEAD is decided separately.
KEY_FIELDS = ("slug", "options", "fingerprint", "harness_maker_version")

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ABSENT = object()


@dataclass
class Decision:
    reuse: bool
    rule: str | None = None
    reason: str | None = None
    paths: list[str] = field(default_factory=list)
    delta: list[str] = field(default_factory=list)
    inert: list[str] = field(default_factory=list)


@lru_cache(maxsize=512)
def _glob_re(pattern: str) -> re.Pattern[str]:
    """Root-anchored and case-sensitive; `*`/`?` stay inside one segment, `**` spans any depth."""
    parts = pattern.split("/")
    out: list[str] = []
    for i, seg in enumerate(parts):
        last = i == len(parts) - 1
        if seg == "**":
            out.append(".*" if last else "(?:[^/]+/)*")
            continue
        body = "".join(
            "[^/]*" if ch == "*" else "[^/]" if ch == "?" else re.escape(ch) for ch in seg
        )
        out.append(body if last else body + "/")
    return re.compile("".join(out))


def glob_match(pattern: str, path: str) -> bool:
    return _glob_re(pattern).fullmatch(path) is not None


def never_inert(path: str) -> bool:
    """A declaration can never cover code, tests or the test runner's own config."""
    from harness_maker.check import is_code_or_test

    return is_code_or_test(path) or PurePosixPath(path).name in RUNNER_CONFIGS


def parse_declaration(config: dict[str, Any]) -> list[str] | None:
    """`check.reuse_inert` from the raw config: `[]` when absent, None when malformed.

    `hm check` reads harness.yaml without the schema, and a bare string iterated as characters
    would yield the glob `*`, so anything but a list of strings is refused here.
    """
    block = config.get("check", _ABSENT)
    if block is _ABSENT or block is None:
        return []
    if not isinstance(block, dict):
        return None
    value = block.get("reuse_inert", _ABSENT)
    if value is _ABSENT or value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(g, str) for g in value):
        return None
    return list(value)


def _miss(reason: str, paths: list[str] | None = None) -> Decision:
    return Decision(reuse=False, reason=reason, paths=sorted(paths or []))


def decide(
    record: object,
    *,
    key: dict[str, Any],
    files: dict[str, str],
    declaration: list[str] | None,
    head: str,
    has_pytest_gate: bool,
) -> Decision:
    """Reuse the recorded gate result, or name the first reason not to (fail-closed)."""
    if not isinstance(record, dict) or record.get("exit", 0) != 0:
        return _miss("no-record")
    recorded = record.get("files")
    if not isinstance(recorded, dict):
        return _miss("legacy-record")
    if not isinstance(record.get("gates"), dict):
        return _miss("no-record")
    delta = sorted(p for p in set(recorded) | set(files) if recorded.get(p) != files.get(p))
    key_same = all(record.get(k) == key.get(k) for k in KEY_FIELDS)
    if key_same and record.get("head") == head and not delta:
        return Decision(reuse=True, rule="identical")
    if declaration is None:
        return _miss("bad-declaration")
    if not key_same:
        return _miss("key")
    code = [p for p in delta if never_inert(p)]
    if code:
        return _miss("code", code)
    changed_kind = [
        p
        for p in delta
        if not (_SHA.match(str(recorded.get(p, ""))) and _SHA.match(str(files.get(p, ""))))
    ]
    if changed_kind:
        return _miss("added-removed", changed_kind)
    if not declaration:
        return _miss("undeclared", delta) if delta else _miss("head")
    undeclared = [p for p in delta if not any(glob_match(g, p) for g in declaration)]
    if undeclared:
        return _miss("undeclared", undeclared)
    read_set = record.get("read_set")
    if isinstance(read_set, list):
        voided = [p for p in delta if p in set(read_set)]
        if voided:
            return _miss("voided", voided)
    elif has_pytest_gate:
        return _miss("no-read-set")
    matched = sorted({g for g in declaration for p in delta if glob_match(g, p)})
    return Decision(reuse=True, rule="inert", delta=delta, inert=matched)
