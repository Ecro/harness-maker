"""PLAN-antisycophancy-2026-05 ADR-006 — communication-protocol drift audit.

/hm:health Layer 1 (structural) sub-check. Discovers dispatcher templates and
the 5 pinned LLM-judgment skills (ADR-005), requires `communication_variant`
frontmatter, and verifies the rendered output carries a matching HTML comment
marker. Silent-miss (a new template added without declaring a variant) is the
canonical R4 WRONG-probe failure mode this sub-check exists to catch.

Returns ``ActionItem`` records compatible with the existing ImprovementPlan
flow so ``/hm:health`` Step "Per-item structured question"
(accept/reject/defer) walks findings unchanged (0.13.0 ADR-001 "no auto-apply").
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from harness_maker.improvement import ActionItem

# Pinned 5 LLM-judgment skills (PLAN-antisycophancy-2026-05 ADR-005).
PINNED_SKILLS: tuple[str, ...] = (
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "relevance-filter",
    "security-scanner",
    "refdocs-search",
)

VALID_VARIANTS: frozenset[str] = frozenset({"full", "reframe", "soft"})
_MARKER_PATTERN = re.compile(
    r"<!--\s*@hm:communication_variant:\s*(full|reframe|soft)\s*-->"
)


def discover_dispatchers(template_dir: Path) -> list[Path]:
    """Source dispatcher templates (excludes ``_body`` / ``_partials``)."""
    agents = template_dir / "agents"
    if not agents.is_dir():
        return []
    return sorted(
        f for f in agents.glob("*.md.j2") if not f.name.endswith("_body.md.j2")
    )


def discover_pinned_skills(template_dir: Path) -> list[Path]:
    """5 LLM-judgment skill SKILL.md.j2 (ADR-005)."""
    skills = template_dir / "skills"
    if not skills.is_dir():
        return []
    return [f for name in PINNED_SKILLS if (f := skills / name / "SKILL.md.j2").is_file()]


_VARIANT_KEY_RE = re.compile(
    r"^communication_variant:\s*([A-Za-z_-]+)\s*$", re.MULTILINE
)


def _read_source_frontmatter(path: Path) -> dict[str, Any] | None:
    """Parse template source frontmatter.

    Uses a focused regex for the ``communication_variant`` key (the only one
    this module cares about) because template-side frontmatter may carry
    Jinja expressions (``{{ name }}``) that break ``yaml.safe_load``. Falls
    back to ``yaml.safe_load`` for any additional keys readers may want.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fm_text = text[4:end]
    result: dict[str, Any] = {}
    m = _VARIANT_KEY_RE.search(fm_text)
    if m:
        result["communication_variant"] = m.group(1)
    # Best-effort YAML parse for any other keys (silently dropped on parse error).
    try:
        parsed = yaml.safe_load(fm_text)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                result.setdefault(k, v)
    except yaml.YAMLError:
        pass
    return result if result else None


def require_variant_frontmatter(template: Path) -> ActionItem | None:
    """Return an ActionItem when ``communication_variant`` is absent or invalid."""
    fm = _read_source_frontmatter(template)
    rel = str(template)
    if fm is None or "communication_variant" not in fm:
        return ActionItem(
            priority="P1",
            dimension="communication_protocol",
            target=rel,
            summary=f"`{template.name}` missing `communication_variant` frontmatter",
            detail=(
                "Source template lacks the `communication_variant` key — silent-miss "
                "(ADR-006 canonical failure mode). Render fails loud on body include."
            ),
            suggestion=(
                "Add `communication_variant: full|reframe|soft` to the template "
                "frontmatter (FULL for executor-shaped agents; REFRAME for "
                "reviewer-shaped agents; SOFT for idea-shaped agents)."
            ),
            source="layer1:communication_protocol",
        )
    variant = fm.get("communication_variant")
    if not isinstance(variant, str) or variant not in VALID_VARIANTS:
        return ActionItem(
            priority="P1",
            dimension="communication_protocol",
            target=rel,
            summary=f"`{template.name}` has invalid `communication_variant: {variant!r}`",
            detail=(
                f"Value {variant!r} is not in {{full, reframe, soft}}. Render will "
                "TemplateNotFound on `communication_<variant>.md.j2`."
            ),
            suggestion="Set `communication_variant` to one of full / reframe / soft.",
            source="layer1:communication_protocol",
        )
    return None


def scan_output_marker(rendered: Path) -> str | None:
    """Extract ``@hm:communication_variant: <variant>`` marker from rendered file."""
    try:
        text = rendered.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _MARKER_PATTERN.search(text)
    return m.group(1) if m else None


def _rendered_path_for_template(
    template: Path, template_dir: Path, output_dir: Path
) -> Path | None:
    rel = template.relative_to(template_dir)
    if str(rel).startswith(("agents/", "skills/")) and rel.suffix == ".j2":
        candidate = (output_dir / rel.with_suffix("")).resolve()
        # Path containment guard (REVIEW security P1 #2): refuse to scan
        # files outside the declared output_dir even if symlinks redirect.
        try:
            candidate.relative_to(output_dir.resolve())
        except ValueError:
            return None
        return candidate
    return None


def audit_communication(
    template_dir: Path, output_dir: Path | None = None
) -> list[ActionItem]:
    """Run the full sub-check; return ActionItems for /hm:health Layer 1.

    Without ``output_dir`` only source-side checks run (pre-render gate). With
    ``output_dir``, marker scanning catches source ↔ output drift.
    """
    items: list[ActionItem] = []
    targets = discover_dispatchers(template_dir) + discover_pinned_skills(template_dir)

    for tpl in targets:
        miss = require_variant_frontmatter(tpl)
        if miss is not None:
            items.append(miss)
            continue
        if output_dir is None:
            continue
        fm = _read_source_frontmatter(tpl) or {}
        expected = fm.get("communication_variant")
        rendered = _rendered_path_for_template(tpl, template_dir, output_dir)
        if rendered is None or not rendered.exists():
            continue
        observed = scan_output_marker(rendered)
        if observed is None:
            items.append(
                ActionItem(
                    priority="P1",
                    dimension="communication_protocol",
                    target=str(rendered),
                    summary=f"`{rendered.name}` missing communication-protocol marker",
                    detail=(
                        f"Source declared `communication_variant: {expected}` but "
                        "rendered output has no `@hm:communication_variant:` marker "
                        "(block deleted or partial not included)."
                    ),
                    suggestion="Re-render via `/hm:make --update`.",
                    source="layer1:communication_protocol",
                )
            )
            continue
        if observed != expected:
            items.append(
                ActionItem(
                    priority="P1",
                    dimension="communication_protocol",
                    target=str(rendered),
                    summary=(
                        f"`{rendered.name}` marker variant `{observed}` ≠ source `{expected}`"
                    ),
                    detail=(
                        f"Source frontmatter says `{expected}` but rendered marker is "
                        f"`{observed}` — source/output drift."
                    ),
                    suggestion="Re-render via `/hm:make --update`.",
                    source="layer1:communication_protocol",
                )
            )

    return items
