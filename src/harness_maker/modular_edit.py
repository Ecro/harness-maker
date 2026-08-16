"""Modular installer (M_extra) — `--add` and `--remove` for components.

Per Phase 6 amendment §D, the modular installer:
- Operates on an EXISTING `.claude/` (post-make), not a fresh tree
- Reads the current harness.yaml, mutates it, atomic_writes back
- Renders ONLY the new component (e.g. `agents/security-reviewer.md`)
- Re-runs verify; on failure, raises typer.Exit(1)
- For Phase 6 minimum: supports `reviewer:<name>` and `skill:<name>`.
  `hook:<name>` is deferred to a later phase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jinja2 import TemplateNotFound

from harness_maker.io_utils import atomic_write
from harness_maker.models import FileEntry
from harness_maker.render import _make_env, _render_text_file
from harness_maker.verify import verify

ALLOWED_KINDS: set[str] = {"reviewer", "skill"}


class ModularEditError(Exception):
    """Raised when a modular add/remove operation cannot complete."""


def _parse_component(component: str) -> tuple[str, str]:
    """Parse 'reviewer:security' → ('reviewer', 'security')."""
    kind, sep, name = component.partition(":")
    if not sep or not name:
        msg = (
            f"Invalid component spec {component!r}; expected 'kind:name' (e.g. 'reviewer:security')"
        )
        raise ModularEditError(msg)
    if kind not in ALLOWED_KINDS:
        msg = (
            f"Unsupported component kind {kind!r}. "
            f"Phase 6 supports: {sorted(ALLOWED_KINDS)}. "
            f"'hook:<name>' is deferred."
        )
        raise ModularEditError(msg)
    return kind, name


def _read_harness_yaml(target_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (frontmatter, config_body) parsed from harness.yaml.

    harness.yaml layout: `---\n<frontmatter>\n---\n<config yaml body>`.
    Returns ({}, body) when no frontmatter present.
    """
    hy = target_dir / "harness.yaml"
    if not hy.exists():
        msg = f"harness.yaml not found at {hy}; run `make` first."
        raise ModularEditError(msg)
    text = hy.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm_text = text[4:end]
            body_text = text[end + 5 :]
            fm = yaml.safe_load(fm_text) or {}
            body = yaml.safe_load(body_text) or {}
            return fm, body
    body = yaml.safe_load(text) or {}
    return {}, body


def _write_harness_yaml(
    target_dir: Path,
    frontmatter: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """Atomic-write harness.yaml; refresh content_hash so reconciler treats us as canonical."""
    import hashlib

    hy = target_dir / "harness.yaml"
    body_yaml = yaml.safe_dump(
        config,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body_bytes = body_yaml.encode("utf-8")
    # Recompute content_hash to match the body we're about to write — without this,
    # reconciler sees stale hash → marks file as user-modified → blocks regeneration.
    if frontmatter:
        frontmatter["content_hash"] = hashlib.sha256(body_bytes).hexdigest()
        fm_yaml = yaml.safe_dump(
            frontmatter,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        text = "---\n" + fm_yaml + "---\n" + body_yaml
    else:
        text = body_yaml
    atomic_write(hy, text.encode("utf-8"))


def _render_single_component(
    template_rel: str,
    out_rel: Path,
    name: str,
    target_dir: Path,
    config: dict[str, Any],
) -> Path:
    """Render one component file using the standard text-file pipeline."""
    fe = FileEntry(
        path=out_rel,
        template=template_rel,
        context={
            "name": name,
            "preset": config.get("preset", "Side"),
            "config": config,
            "stack": [],
            "scale": "small",
            "lifecycle": "dormant",
            # This builder bypasses `synthesize`, which derives `is_codex` for every FileEntry
            # (`synthesize.py` `_is_codex_output`). Without it here the templates rendered by
            # this path — `skills/<name>/SKILL.md.j2`, which includes a dispatch call site —
            # would see an undefined flag. `False` is correct: this path writes to `.claude/`
            # only. Supplying it is what lets every call site pass `is_codex` BARE, so an
            # omission raises `UndefinedError` under StrictUndefined instead of silently
            # rendering the Claude arm — the guarantee ADR-003 is built on.
            "is_codex": False,
        },
        frontmatter={},
    )
    env = _make_env()
    return _render_text_file(fe, env, target_dir, dry_run=False, freeze_time=None)


def _available(prefix: str, suffix: str) -> list[str]:
    """List installable component names matching ``prefix...suffix`` templates.

    Why: surfaced in ModularEditError when a user requests an unknown
    reviewer/skill, so the failure is actionable instead of a raw traceback.
    """
    env = _make_env()
    return sorted(
        t.removeprefix(prefix).removesuffix(suffix)
        for t in env.list_templates()
        if t.startswith(prefix) and t.endswith(suffix)
    )


def add(component: str, target_dir: Path) -> Path:
    """Add a component to the existing .claude/ tree.

    Returns the path of the rendered file. Raises ModularEditError on
    invalid input; lets verify() failures propagate as ValueError so the
    CLI can surface them via typer.Exit(1).
    """
    kind, name = _parse_component(component)
    fm, config = _read_harness_yaml(target_dir)

    if kind == "reviewer":
        # Activate `<name>-reviewer` in reviewers.enabled (idempotent). The
        # agent file is always installed; --add only flips activation.
        reviewer_full = f"{name}-reviewer" if not name.endswith("-reviewer") else name
        reviewers = config.setdefault("reviewers", {})
        enabled = reviewers.setdefault("enabled", [])
        if reviewer_full not in enabled:
            enabled.append(reviewer_full)
        template = f"agents/{reviewer_full}.md.j2"
        out = Path("agents") / f"{reviewer_full}.md"
        try:
            rendered = _render_single_component(template, out, reviewer_full, target_dir, config)
        except TemplateNotFound as e:
            raise ModularEditError(
                f"no template for reviewer {reviewer_full!r}; "
                f"available: {_available('agents/', '-reviewer.md.j2')}"
            ) from e
    else:  # skill
        skills = config.setdefault("skills", {})
        if isinstance(skills, list):
            # legacy shape — coerce to the new {installed, enabled} dict
            skills = {"installed": list(skills), "enabled": list(skills)}
            config["skills"] = skills
        skills_enabled = skills.setdefault("enabled", [])
        if name not in skills_enabled:
            skills_enabled.append(name)
        template = f"skills/{name}/SKILL.md.j2"
        out = Path("skills") / name / "SKILL.md"
        try:
            rendered = _render_single_component(template, out, name, target_dir, config)
        except TemplateNotFound as e:
            raise ModularEditError(
                f"no template for skill {name!r}; "
                f"available: {_available('skills/', '/SKILL.md.j2')}"
            ) from e

    _write_harness_yaml(target_dir, fm, config)

    errors = verify(target_dir)
    if errors:
        msg = "Modular add verify failed:\n  - " + "\n  - ".join(errors)
        raise ModularEditError(msg)
    return rendered


def remove(component: str, target_dir: Path) -> Path:
    """Remove a component from the existing .claude/ tree.

    Returns the path of the removed file. Raises ModularEditError on
    invalid input or if the component is not present.
    """
    kind, name = _parse_component(component)
    fm, config = _read_harness_yaml(target_dir)

    if kind == "reviewer":
        reviewer_full = f"{name}-reviewer" if not name.endswith("-reviewer") else name
        reviewers = config.setdefault("reviewers", {})
        enabled = reviewers.setdefault("enabled", [])
        if reviewer_full in enabled:
            enabled.remove(reviewer_full)
        out = target_dir / "agents" / f"{reviewer_full}.md"
    else:  # skill
        skills = config.setdefault("skills", {})
        if isinstance(skills, list):
            skills = {"installed": list(skills), "enabled": list(skills)}
            config["skills"] = skills
        skills_enabled = skills.setdefault("enabled", [])
        if name in skills_enabled:
            skills_enabled.remove(name)
        out = target_dir / "skills" / name / "SKILL.md"

    if out.exists():
        out.unlink()
        # Clean up empty parent (skill subdir)
        parent = out.parent
        if parent != target_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

    _write_harness_yaml(target_dir, fm, config)

    errors = verify(target_dir)
    if errors:
        msg = "Modular remove verify failed:\n  - " + "\n  - ".join(errors)
        raise ModularEditError(msg)
    return out
