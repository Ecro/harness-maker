"""--add-domain helper: render a user-authored standards stub + register the name.

Why split this from cli.py: the work is a small, testable transform — validate
the domain name, render the skeleton template, and atomically update
``harness.yaml``'s ``project.domains`` list. Surfacing it as a function lets
the unit tests drive it without typer.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_maker.io_utils import atomic_write
from harness_maker.render import _make_env

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,30}$")


class AddDomainError(ValueError):
    """Raised when --add-domain inputs or filesystem state are invalid."""


def validate_domain_name(name: str) -> str:
    """Return name unchanged when valid; raise AddDomainError otherwise.

    Why a strict pattern: the name becomes a filename and a Jinja include path
    fragment in five reviewer agents. Accepting shell-meta or path-traversal
    here would propagate.
    """
    if not _NAME_PATTERN.fullmatch(name):
        msg = (
            f"invalid domain name {name!r}: must match {_NAME_PATTERN.pattern}; "
            "lowercase + digits + dashes, ≤ 31 chars, starts with a letter"
        )
        raise AddDomainError(msg)
    return name


def _today_iso() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def _render_skeleton(name: str, today: str) -> str:
    """Render `_template.md.j2` with the domain name + today's date filled in."""
    env = _make_env()
    tpl = env.get_template("agents/_standards/_template.md.j2")
    return tpl.render(domain_name=name, today=today)


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    # harness.yaml gets a YAML provenance frontmatter wrapper from render.py;
    # strip it before parsing the body.
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _format_yaml(data: dict[str, object]) -> str:
    """Match the existing harness.yaml dump style (insertion order, allow unicode)."""
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def update_harness_yaml(harness_yaml_path: Path, name: str) -> bool:
    """Append ``name`` to ``project.domains`` in-place. Return True if changed.

    Preserves the YAML frontmatter wrapper (``---`` block) so provenance is not
    lost. If the wrapper is absent (greenfield), writes a plain YAML body.
    """
    if not harness_yaml_path.exists():
        msg = f"harness.yaml not found at {harness_yaml_path}; run /harness-maker:make first"
        raise AddDomainError(msg)
    text = harness_yaml_path.read_text(encoding="utf-8")
    frontmatter = ""
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            frontmatter = text[: end + 5]
            body = text[end + 5 :]
    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError as e:
        msg = f"harness.yaml is not valid YAML: {e}"
        raise AddDomainError(msg) from e
    if not isinstance(data, dict):
        msg = "harness.yaml top-level must be a mapping"
        raise AddDomainError(msg)
    project = data.setdefault("project", {})
    if not isinstance(project, dict):
        msg = "harness.yaml: project must be a mapping"
        raise AddDomainError(msg)
    domains = project.setdefault("domains", [])
    if not isinstance(domains, list):
        msg = "harness.yaml: project.domains must be a list"
        raise AddDomainError(msg)
    if name in domains:
        return False
    domains.append(name)
    new_body = _format_yaml(data)
    atomic_write(harness_yaml_path, frontmatter + new_body)
    return True


def add_domain(target: Path, name: str, *, today: str | None = None) -> Path:
    """Create ``.claude/agents/_standards/<name>.md`` and register the domain.

    Returns the path of the created stub. Existing stubs are not overwritten —
    raises AddDomainError so the user can review the conflict.
    """
    validate_domain_name(name)
    standards_dir = target / ".claude" / "agents" / "_standards"
    out = standards_dir / f"{name}.md"
    if out.exists():
        msg = f"{out} already exists; remove it first if you intend to recreate"
        raise AddDomainError(msg)
    body = _render_skeleton(name, today or _today_iso())
    atomic_write(out, body)
    update_harness_yaml(target / ".claude" / "harness.yaml", name)
    return out
