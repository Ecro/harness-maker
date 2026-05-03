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
            "lifecycle": "experiment",
        },
        frontmatter={},
    )
    env = _make_env()
    return _render_text_file(fe, env, target_dir, dry_run=False, freeze_time=None)


def add(component: str, target_dir: Path) -> Path:
    """Add a component to the existing .claude/ tree.

    Returns the path of the rendered file. Raises ModularEditError on
    invalid input; lets verify() failures propagate as ValueError so the
    CLI can surface them via typer.Exit(1).
    """
    kind, name = _parse_component(component)
    fm, config = _read_harness_yaml(target_dir)

    if kind == "reviewer":
        # Append `<name>-reviewer` to reviewers.list (idempotent).
        reviewer_full = f"{name}-reviewer" if not name.endswith("-reviewer") else name
        reviewers = config.setdefault("reviewers", {})
        rev_list = reviewers.setdefault("list", [])
        if reviewer_full not in rev_list:
            rev_list.append(reviewer_full)
        template = f"agents/{reviewer_full}.md.j2"
        out = Path("agents") / f"{reviewer_full}.md"
        rendered = _render_single_component(template, out, reviewer_full, target_dir, config)
    else:  # skill
        skills = config.setdefault("skills", [])
        if name not in skills:
            skills.append(name)
        template = f"skills/{name}/SKILL.md.j2"
        out = Path("skills") / name / "SKILL.md"
        rendered = _render_single_component(template, out, name, target_dir, config)

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
        rev_list = reviewers.setdefault("list", [])
        if reviewer_full in rev_list:
            rev_list.remove(reviewer_full)
        out = target_dir / "agents" / f"{reviewer_full}.md"
    else:  # skill
        skills = config.setdefault("skills", [])
        if name in skills:
            skills.remove(name)
        out = target_dir / "skills" / name / "SKILL.md"

    if out.exists():
        out.unlink()
        # Clean up empty parent (skill subdir)
        parent = out.parent
        if parent != target_dir and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

    _write_harness_yaml(target_dir, fm, config)
    return out
