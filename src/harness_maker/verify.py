"""Verifier (Task 3.4) — minimal sanity checks on the rendered .claude/ tree."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness_maker.reconcile import compute_body_hash, parse_frontmatter


def _read_json_body(path: Path) -> str:
    """Strip the YAML frontmatter (if present) and return the JSON body text."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def verify(target_dir: Path) -> list[str]:
    """Return list of error messages (empty list = clean)."""
    errors: list[str] = []

    # 1. harness.yaml parses (multi-doc: provenance frontmatter + actual config)
    hy = target_dir / "harness.yaml"
    if not hy.exists():
        errors.append("harness.yaml missing")
    else:
        try:
            list(yaml.safe_load_all(hy.read_text(encoding="utf-8")))
        except yaml.YAMLError as e:
            errors.append(f"harness.yaml YAML error: {e}")

    # 2. settings.json parses (after stripping YAML frontmatter)
    sj = target_dir / "settings.json"
    if sj.exists():
        try:
            json.loads(_read_json_body(sj))
        except json.JSONDecodeError as e:
            errors.append(f"settings.json JSON error: {e}")

    # 3. hooks/hooks.json parses
    hj = target_dir / "hooks" / "hooks.json"
    if hj.exists():
        try:
            json.loads(_read_json_body(hj))
        except json.JSONDecodeError as e:
            errors.append(f"hooks/hooks.json JSON error: {e}")

    # 4. Every .md file has frontmatter with content_hash (incl. project-root CLAUDE.md)
    scan_paths = list(target_dir.rglob("*.md"))
    project_claude = target_dir.parent / "CLAUDE.md"
    if project_claude.exists():
        scan_paths.append(project_claude)
    for md in scan_paths:
        fm, body = parse_frontmatter(md)
        try:
            rel = md.relative_to(target_dir)
        except ValueError:
            rel = md
        if fm is None or "content_hash" not in fm:
            errors.append(f"{rel}: missing provenance frontmatter")
            continue
        # Hash-validity check (Phase 6 carry-over): declared content_hash must
        # match the actual body hash. Catches manual edits / tampering.
        declared = fm.get("content_hash")
        if not isinstance(declared, str):
            errors.append(f"{rel}: content_hash is not a string")
            continue
        actual = compute_body_hash(body)
        if actual != declared:
            errors.append(
                f"{rel}: content_hash mismatch "
                f"(declared {declared[:8]}, actual {actual[:8]})",
            )

    return errors
