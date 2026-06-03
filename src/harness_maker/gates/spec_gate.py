"""spec_gate hook — refuse test writes that lack a SPEC reference.

Why: spec-driven mode requires every test to trace to acceptance criteria in a
SPEC document; spec_gate enforces that contract at the PreToolUse boundary so
divergence is caught before the test is even written. Severity is configurable
per project (Side=warn, Production=block by default).

Activation is gated upstream by ``dev_mode == "spec-driven"`` in the rendered
``.claude/hooks/hooks.json``; if invoked under task-driven (defense in depth)
this module exits 0 silently.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from harness_maker.i18n import t
from harness_maker.io_utils import load_harness_yaml

# Test-path heuristics — first match wins. Order matters: most-common forms first.
_TEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|/)tests?/.*test.*\.py$"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"(^|/)[^/]+_test\.py$"),
)
_TRIGGER_TOOLS = frozenset({"Write", "Edit"})


class Severity(str, Enum):  # noqa: UP042 — pydantic 2 prefers (str, Enum) for serialization
    """Per-project gate severity from ``security.gates.spec_gate`` in harness.yaml."""

    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class GateDecision:
    """Pure outcome of a gate evaluation; main() converts to exit code + stderr."""

    allow: bool
    severity: Severity
    message: str  # empty string when there is nothing to say


def is_test_path(path: str) -> bool:
    return any(p.search(path) for p in _TEST_PATTERNS)


def derive_test_slug(test_path: str) -> str:
    """Pick the slug fragment we'll search for inside SPEC-*.md.

    e.g. ``tests/unit/test_spec_gate.py`` → ``spec_gate``.
    """
    name = Path(test_path).stem
    if name.startswith("test_"):
        return name[len("test_") :]
    if name.endswith("_test"):
        return name[: -len("_test")]
    return name


def find_spec_for_test(spec_dir: Path, test_path: str) -> Path | None:
    """Return the first SPEC-*.md that references the test path or its slug."""
    if not spec_dir.is_dir():
        return None
    slug = derive_test_slug(test_path)
    for spec_md in sorted(spec_dir.glob("SPEC-*.md")):
        try:
            content = spec_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if test_path in content or slug in content:
            return spec_md
    return None


def _load_yaml_keys(project_dir: Path) -> dict[str, Any]:
    yaml_path = project_dir / ".claude" / "harness.yaml"
    # Why load_harness_yaml (not yaml.safe_load): the rendered harness.yaml is a
    # multi-document stream (provenance frontmatter + body). A bare safe_load
    # raises ComposerError → caught here → {} → dev_mode never reads as
    # 'spec-driven' → the entire spec-TDD gate silently disables on every real
    # install. See io_utils.load_harness_yaml and CLAUDE.md checklist #2.
    try:
        return load_harness_yaml(yaml_path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}


def evaluate(
    tool_name: str,
    tool_input: dict[str, Any],
    project_dir: Path,
) -> GateDecision:
    """Evaluate a PreToolUse call; only Write/Edit on test paths trigger checks."""
    if tool_name not in _TRIGGER_TOOLS:
        return GateDecision(allow=True, severity=Severity.WARN, message="")
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not is_test_path(file_path):
        return GateDecision(allow=True, severity=Severity.WARN, message="")

    cfg = _load_yaml_keys(project_dir)
    if str(cfg.get("dev_mode") or "") != "spec-driven":
        # Defense in depth: hooks.json shouldn't register us under task-driven,
        # but if something invokes us anyway, stay out of the way.
        return GateDecision(allow=True, severity=Severity.WARN, message="")

    spec_section = cfg.get("spec") if isinstance(cfg.get("spec"), dict) else {}
    spec_dir_str = (
        spec_section.get("dir")
        if isinstance(spec_section, dict) and isinstance(spec_section.get("dir"), str)
        else "specs/"
    )
    spec_dir = project_dir / str(spec_dir_str)
    spec = find_spec_for_test(spec_dir, file_path)
    if spec is not None:
        return GateDecision(allow=True, severity=Severity.WARN, message="")

    locale = str(cfg.get("locale") or "en")
    severity = _resolve_severity(cfg)
    key = "spec_gate_missing_block" if severity == Severity.BLOCK else "spec_gate_missing_warn"
    msg = t(key, locale, test_path=file_path, spec_dir=str(spec_dir_str))
    return GateDecision(
        allow=severity != Severity.BLOCK,
        severity=severity,
        message=msg,
    )


def _resolve_severity(cfg: dict[str, Any]) -> Severity:
    sec = cfg.get("security") if isinstance(cfg.get("security"), dict) else {}
    gates = sec.get("gates") if isinstance(sec, dict) else None
    raw = gates.get("spec_gate") if isinstance(gates, dict) else None
    if raw == "block":
        return Severity.BLOCK
    return Severity.WARN


def main() -> int:
    """Entry point: read PreToolUse JSON from stdin, exit 0 (allow) or 2 (block)."""
    try:
        text = sys.stdin.read()
        payload: Any = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return 0  # malformed input: never block on confusion
    if not isinstance(payload, dict):
        return 0
    tool_name = str(payload.get("tool_name") or "")
    raw_input = payload.get("tool_input")
    tool_input = raw_input if isinstance(raw_input, dict) else {}
    project_dir = Path.cwd()
    decision = evaluate(tool_name, tool_input, project_dir)
    if decision.message:
        print(decision.message, file=sys.stderr)
    return 0 if decision.allow else 2


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess in tests
    sys.exit(main())
