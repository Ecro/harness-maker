"""Batch refinement of skeleton SPECs (P5, ADR-013 R2).

Walks the BatchSpecState queue, deepens each skeleton SPEC by:
1. Replacing the placeholder AC title with one derived from the module's
   actual docstring/intent line (for Python features).
2. Validating test_ids via pytest --collect-only and flipping pending_test
   to false on AC where ≥1 test_id resolves.
3. Marking the entry complete in BatchSpecState.

Pure CRUD on existing SPEC files — does NOT regenerate from scratch. The
goal is iteration-friendly refinement, not destruction of any prior hand
edits.
"""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from harness_maker.io_utils import atomic_write
from harness_maker.spec_inventory.batch_state import BatchSpecState


@dataclass(frozen=True)
class RefinementResult:
    slug: str
    refined: bool
    test_ids_resolved: int
    test_ids_total: int
    note: str = ""


def _extract_module_intent(source_path: Path) -> str:
    """Return a one-line intent string from a Python module's top-level docstring."""
    if not source_path.exists():
        return ""
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return ""
    doc = ast.get_docstring(tree) or ""
    if not doc:
        return ""
    # Use the first non-empty line as the intent.
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line.rstrip(".")
    return ""


def _resolve_test_ids(test_ids: list[str], repo_root: Path) -> set[str]:
    """Run pytest --collect-only against the files referenced; return resolved set."""
    if not test_ids:
        return set()
    files = sorted({tid.split("::", 1)[0] for tid in test_ids if "::" in tid})
    if not files:
        return set()
    try:
        # `-q` collapses output to `file: count` (no nodeid form); drop it so
        # we can match `file::test` strings (REVIEW C-P1-B follow-up).
        result = subprocess.run(
            ["pytest", "--collect-only", "--no-header", *files],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    collected: set[str] = set()
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if "::" not in line:
            continue
        collected.add(line)
        collected.add(line.split("[", 1)[0])
    resolved: set[str] = set()
    for tid in test_ids:
        if tid in collected or tid.split("[", 1)[0] in collected:
            resolved.add(tid)
    return resolved


_FRONT_MATTER_RE = re.compile(r"^---\n(.+?)\n---\n(.*)$", re.DOTALL)


def _split_frontmatter(md_text: str) -> tuple[dict[str, object], str]:
    m = _FRONT_MATTER_RE.match(md_text)
    if not m:
        return {}, md_text
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    return fm, body


def _serialize_frontmatter(fm: dict[str, object], body: str) -> str:
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm_text}\n---\n{body}"


def refine_spec(
    slug: str,
    repo_root: Path,
    specs_dir: Path,
) -> RefinementResult:
    """Refine one SPEC pair: deepen titles + validate test_ids."""
    md_path = specs_dir / f"SPEC-{slug}.md"
    yaml_path = specs_dir / f"SPEC-{slug}.machine.yaml"
    if not (md_path.exists() and yaml_path.exists()):
        return RefinementResult(
            slug=slug, refined=False, test_ids_resolved=0, test_ids_total=0, note="missing files"
        )

    yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    md_text = md_path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(md_text)

    # 1) Derive a better AC title for Python features.
    new_title: str | None = None
    paths_to_mutate = yaml_data.get("paths_to_mutate") or []
    if paths_to_mutate:
        src = repo_root / paths_to_mutate[0]
        intent = _extract_module_intent(src)
        if intent and len(intent) <= 120:
            new_title = intent

    # 2) Resolve test_ids and flip pending_test where collect-only confirms ≥1 hit.
    ac_list = yaml_data.get("ac") or []
    total_test_ids = 0
    total_resolved = 0
    new_body_lines = body.splitlines()
    body_dirty = False
    for ac in ac_list:
        test_ids = ac.get("test_ids") or []
        total_test_ids += len(test_ids)
        if not test_ids:
            continue
        resolved = _resolve_test_ids(test_ids, repo_root)
        total_resolved += len(resolved)
        # Drop test_ids that didn't resolve to keep machine.yaml honest.
        ac["test_ids"] = sorted(resolved)
        if resolved:
            ac["pending_test"] = False

    # 3) Rewrite AC-001 title if we derived a better one.
    if new_title and ac_list:
        old_title = ac_list[0].get("title", "")
        ac_list[0]["title"] = new_title
        if old_title and old_title in body:
            # Replace the matching md heading line too.
            new_body_lines = [
                ln.replace(old_title, new_title) if old_title in ln else ln for ln in new_body_lines
            ]
            body_dirty = True

    # 4) Mark status=verified if every AC has either pending_test=true or
    #    test_ids resolved (i.e., no dangling unverified non-pending AC).
    all_clean = all((ac.get("pending_test") is True) or bool(ac.get("test_ids")) for ac in ac_list)
    if all_clean:
        fm["status"] = "verified-skeleton"
    yaml_data["ac"] = ac_list

    # Persist
    new_yaml_text = yaml.safe_dump(yaml_data, sort_keys=False, allow_unicode=True)
    atomic_write(yaml_path, new_yaml_text)

    new_body = "\n".join(new_body_lines) if body_dirty else body
    atomic_write(md_path, _serialize_frontmatter(fm, new_body))

    return RefinementResult(
        slug=slug,
        refined=True,
        test_ids_resolved=total_resolved,
        test_ids_total=total_test_ids,
        note=(f"title→intent ({new_title!r})" if new_title else ""),
    )


def run_batches(
    state_path: Path,
    repo_root: Path,
    specs_dir: Path,
    *,
    batch_size: int = 10,
    max_batches: int | None = None,
) -> list[RefinementResult]:
    """Process the BatchSpecState queue in batches; mark each entry complete."""
    bs = BatchSpecState(state_path)
    results: list[RefinementResult] = []
    batch_idx = 0
    while True:
        queue = bs.next_batch_queue(limit=batch_size)
        if not queue:
            break
        batch_idx += 1
        if max_batches is not None and batch_idx > max_batches:
            break
        for entry in queue:
            bs.mark_in_progress(entry.feature_id)
            try:
                res = refine_spec(entry.feature_id, repo_root, specs_dir)
            except Exception as exc:  # noqa: BLE001 — record + continue
                res = RefinementResult(
                    slug=entry.feature_id,
                    refined=False,
                    test_ids_resolved=0,
                    test_ids_total=0,
                    note=f"refine error: {exc}",
                )
                bs.mark_failed(entry.feature_id, note=str(exc)[:200])
            else:
                if res.refined:
                    note = f"resolved {res.test_ids_resolved}/{res.test_ids_total} test_ids" + (
                        f"; {res.note}" if res.note else ""
                    )
                    bs.mark_complete(entry.feature_id, note=note)
                else:
                    bs.mark_failed(entry.feature_id, note=res.note)
            results.append(res)
    return results


__all__ = ["RefinementResult", "refine_spec", "run_batches"]
