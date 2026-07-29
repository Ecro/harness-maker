"""Test dependency map — map changed source files to affected tests (TDAD).

Given a list of changed source files, resolves which test files are
likely affected using convention-based naming and import analysis.
Used by the execute stage to provide concrete test hints instead of
generic "follow TDD" instructions.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def source_to_test_candidates(
    source_path: Path,
    project_root: Path,
) -> list[Path]:
    """Return candidate test file paths for a given source file.

    Applies Python naming conventions:
      src/pkg/module.py → tests/unit/test_module.py
      src/pkg/module.py → tests/test_module.py
      src/pkg/sub/module.py → tests/unit/test_module.py
      pkg/module.py → tests/test_module.py
    """
    stem = source_path.stem
    if stem.startswith("test_") or stem.startswith("conftest"):
        return [source_path]

    test_name = f"test_{stem}.py"
    candidates: list[Path] = []

    for test_dir in ["tests/unit", "tests", "test"]:
        candidate = project_root / test_dir / test_name
        if candidate.exists():
            candidates.append(candidate)

    rel = (
        source_path.relative_to(project_root)
        if source_path.is_relative_to(project_root)
        else source_path
    )
    parts = list(rel.parts)
    if len(parts) > 1 and parts[0] == "src":
        parts = parts[1:]
    if len(parts) > 1:
        sub_dir = "/".join(parts[:-1])
        for test_root in ["tests/unit", "tests"]:
            candidate = project_root / test_root / sub_dir / test_name
            if candidate.exists():
                candidates.append(candidate)

    seen: set[Path] = set()
    deduped: list[Path] = []
    for c in candidates:
        resolved = c.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(c)
    return deduped


def find_importers(
    module_name: str,
    test_dir: Path,
) -> list[Path]:
    """Find test files that import the given module name (shallow AST scan)."""
    if not test_dir.is_dir():
        return []

    importers: list[Path] = []
    for py_file in test_dir.rglob("*.py"):
        if not py_file.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if module_name in alias.name:
                        importers.append(py_file)
                        break
                else:
                    continue
                break
            if isinstance(node, ast.ImportFrom) and node.module and module_name in node.module:
                importers.append(py_file)
                break
    return importers


def build_test_hints(
    changed_files: list[Path],
    project_root: Path,
) -> dict[str, list[str]]:
    """Build a mapping of changed source files to affected test file paths.

    Returns a dict mapping source file (relative string) to list of
    affected test file paths (relative strings). Empty list means no
    known tests cover the file.
    """
    hints: dict[str, list[str]] = {}
    for src in changed_files:
        if src.suffix != ".py":
            continue

        rel_src = (
            str(src.relative_to(project_root)) if src.is_relative_to(project_root) else str(src)
        )

        affected: list[Path] = source_to_test_candidates(src, project_root)

        module_stem = src.stem
        if not module_stem.startswith("test_"):
            for test_dir_name in ["tests", "test"]:
                test_dir = project_root / test_dir_name
                if test_dir.is_dir():
                    importers = find_importers(module_stem, test_dir)
                    for imp in importers:
                        if imp.resolve() not in {a.resolve() for a in affected}:
                            affected.append(imp)

        hints[rel_src] = [
            str(t.relative_to(project_root)) if t.is_relative_to(project_root) else str(t)
            for t in affected
        ]
    return hints


# ── four-way selection (PLAN-workflow-step-audit ADR-008) ──────────────────────
#
# `build_test_hints` above skips every non-`.py` file, so the interview's locked rule
# ("a changed file with no hint → FULL") degenerates to always-FULL in this repo, where
# most changes are `.j2` templates, markdown and config. The classifier below keeps what
# that rule protects — a source file no test maps to must never be silently untested —
# and gives the other three shapes a bounded answer.
#
# The classifier is TOTAL. Anything matching none of the rules falls to the explicit
# default arm below and forces FULL, loudly. That arm is not decoration: an earlier
# draft defaulted only out-of-root paths, which left `pyproject.toml`, `uv.lock`,
# `.github/workflows/*.yml` and `.claude/harness.yaml` selecting ZERO tests — an
# always-FULL cost traded for a sometimes-NONE gap, which is strictly weaker than the
# behaviour it replaced.

CLASS_SOURCE_WITH_HINTS = "source-with-hints"
CLASS_SOURCE_WITHOUT_HINTS = "source-without-hints"
CLASS_RENDER_AFFECTING = "render-affecting"
CLASS_DOC_WITH_CONSUMERS = "doc-with-consumers"
CLASS_INERT = "inert"

#: The bounded set a template / fixture change selects instead of FULL. Curated, so
#: `test_every_directory_under_tests_is_classified_by_the_constant` exists to fail when
#: a new render-sensitive suite appears and is not added here.
RENDER_AFFECTING_SUITES: tuple[str, ...] = (
    "tests/render",
    "tests/snapshot",
    "tests/structural",
)

#: The other half of that detector — directories deliberately declared NOT
#: render-affecting. Membership here is a claim someone made on purpose; absence from
#: both tuples is an omission, and the detector cannot tell those apart without it.
TESTS_DIRS_NOT_RENDER_AFFECTING: tuple[str, ...] = (
    "tests/ablation",
    "tests/codex-compat",
    "tests/cursor-compat",
    "tests/e2e",
    "tests/fixtures",
    "tests/integration",
    "tests/manual",
    "tests/unit",
)

_RENDER_AFFECTING_PREFIXES = (
    "src/harness_maker/templates/",
    "tests/snapshot/",
    "tests/e2e/sandbox/",
    "tests/e2e/sandbox-plugin-test/",
)

#: Markdown is inert only in these locations. A blanket "`.md` is inert" would make
#: `CLAUDE.md` inert too, and the context-lint suite reads it — so everything else
#: falls to the default arm rather than being assumed harmless.
_INERT_PREFIXES = (
    "work-docs/",
    ".claude/memory/",
)
_INERT_ROOT_FILES = ("CHANGELOG.md", "LICENSE")

#: Paths that LOOK inert (markdown, docs, the README) but are **read and asserted on**
#: by a suite. `docs/` and `README.md` were in the inert set until the review found
#: their consumers, at which point editing `docs/HOW-IT-WORKS.md` selected zero tests
#: and still reported `mode: targeted` — a result indistinguishable from "checked and
#: clean".
#:
#: **Keys are EXACT paths, never prefixes.** A `docs/` prefix entry would claim that
#: every file under `docs/` maps to these suites, which is the same over-broad promise
#: in the other direction. Anything not listed here falls through to the default arm and
#: forces FULL, so this map is an OPTIMISATION: being incomplete costs a full run and
#: can never cost a missed test.
_README_SUITES = (
    "tests/integration/test_readme_one_prompt.py",
    "tests/integration/test_readme_install_commands.py",
    "tests/unit/test_readme_one_prompt_structure.py",
    "tests/unit/test_docs_render_pipeline.py",
)

DOC_CONSUMING_SUITES: dict[str, tuple[str, ...]] = {
    # `README.ko.md` was NOT in the old inert tuple while `README.md` was — an asymmetry
    # the review read, correctly, as evidence the list had been assembled by hand.
    "README.md": _README_SUITES,
    "README.ko.md": _README_SUITES,
    "docs/HOW-IT-WORKS.md": ("tests/unit/test_docs_render_pipeline.py",),
    "docs/HOW-IT-WORKS.ko.md": ("tests/unit/test_docs_render_pipeline.py",),
    "docs/BOOTSTRAP.md": ("tests/snapshot/test_bootstrap_doc.py",),
    "docs/assets/showcase-diff.md": ("tests/integration/test_profile_reality_check.py",),
}

#: Changing the selector changes what EVERY other change selects, so a selection it
#: derives for its own edit is not evidence about anything. `build_test_hints` returns
#: this file as its own hint (the stem reads as a test module), that hint is then
#: filtered out for not living under `tests/`, and the result was a `targeted` run with
#: an empty node list — the strongest possible false green, on the one file that decides
#: every other file's fate.
SELECTOR_SOURCE = "src/harness_maker/test_dep_map.py"


def doc_consumers(rel_path: str) -> tuple[str, ...]:
    """Suites that read this exact doc path; `()` when none are declared."""
    return DOC_CONSUMING_SUITES.get(rel_path.replace("\\", "/"), ())


def classify_path(rel_path: str, project_root: Path) -> str:
    """Total function: every input lands in exactly one of the four classes.

    Classification is by PATH ONLY, never by `Path.exists()` — a deleted or renamed
    file is gone from disk, and a classifier that stats it would misroute exactly the
    change most likely to break something.
    """
    norm = rel_path.replace("\\", "/")
    while norm.startswith("./"):
        # NOT `lstrip("./")` — that strips a CHARACTER SET, so `.claude/memory/x.md`
        # became `claude/memory/x.md` and missed every `.`-prefixed inert prefix.
        norm = norm[2:]
    if norm.endswith(".j2") or any(norm.startswith(p) for p in _RENDER_AFFECTING_PREFIXES):
        return CLASS_RENDER_AFFECTING
    if doc_consumers(norm):
        return CLASS_DOC_WITH_CONSUMERS
    if norm in _INERT_ROOT_FILES or any(norm.startswith(p) for p in _INERT_PREFIXES):
        return CLASS_INERT
    if norm.endswith(".py"):
        src = project_root / norm
        hints = build_test_hints([src], project_root)
        return CLASS_SOURCE_WITH_HINTS if hints.get(norm) else CLASS_SOURCE_WITHOUT_HINTS
    # default → FULL, loudly. See the note at the top of this section.
    return CLASS_SOURCE_WITHOUT_HINTS


def select_tests(changed: list[str], project_root: Path) -> dict[str, Any]:
    """Return either a targeted node list or an explicit FULL with the reason.

    Encoded in code rather than prose so the absent case is enforced rather than
    described — an LLM reading "run the full suite when a file has no hint" has no
    referent for "has no hint", and the prose form of this rule shipped as a no-op.
    """
    if not changed:
        return {
            "mode": "full",
            "node_ids": [],
            "reason": "no changed files were supplied — refusing to report a targeted "
            "selection that is indistinguishable from 'everything is inert'",
            "classified": {},
        }
    classified = {rel: classify_path(rel, project_root) for rel in changed}

    # The selector's own source forces FULL before anything else is considered. A
    # selection this file derives for a change to this file is circular: it is the thing
    # under test deciding what tests to run on itself.
    if any(r.replace("\\", "/").lstrip("./") == SELECTOR_SOURCE for r in changed):
        return {
            "mode": "full",
            "node_ids": [],
            "reason": (
                f"full suite: {SELECTOR_SOURCE} changed — the selector cannot produce "
                "evidence about its own change"
            ),
            "classified": classified,
        }

    forcing = [r for r, c in classified.items() if c == CLASS_SOURCE_WITHOUT_HINTS]
    if forcing:
        return {
            "mode": "full",
            "node_ids": [],
            "reason": "full suite: no test maps to " + ", ".join(sorted(forcing)),
            "classified": classified,
        }
    node_ids: list[str] = []
    empty_hint_sources: list[str] = []
    for rel, cls in classified.items():
        if cls == CLASS_RENDER_AFFECTING:
            node_ids.extend(RENDER_AFFECTING_SUITES)
        elif cls == CLASS_DOC_WITH_CONSUMERS:
            node_ids.extend(doc_consumers(rel))
        elif cls == CLASS_SOURCE_WITH_HINTS:
            # Filtered to `tests/`: `build_test_hints` can return the changed file
            # itself when its stem already looks like a test module (this repo has
            # `src/harness_maker/test_dep_map.py`), and handing a source file to
            # pytest as a node id is a collection error, not a narrower run.
            hinted = build_test_hints([project_root / rel], project_root).get(rel, [])
            kept = [h for h in hinted if h.replace("\\", "/").startswith("tests/")]
            if not kept:
                # Classified as having hints, but every one was filtered away. That is
                # how the selector's own source produced an EMPTY targeted run; the
                # general form is guarded here rather than relying on the specific case
                # above to keep firing.
                empty_hint_sources.append(rel)
            node_ids.extend(kept)

    if empty_hint_sources:
        return {
            "mode": "full",
            "node_ids": [],
            "reason": "full suite: every hint was filtered out for "
            + ", ".join(sorted(empty_hint_sources)),
            "classified": classified,
        }

    deduped = sorted(dict.fromkeys(node_ids))
    if not deduped and not all(c == CLASS_INERT for c in classified.values()):
        # Backstop: `targeted` with nothing to run is strictly weaker than today's
        # behaviour AND reads as a pass. The ONE honest empty selection is an all-inert
        # change — a PLAN edit genuinely has no tests to run — so that case is excluded
        # by class rather than by the node list being empty, which is the condition a
        # misclassification also satisfies.
        return {
            "mode": "full",
            "node_ids": [],
            "reason": "full suite: the selection was empty — refusing to report a "
            "targeted run with nothing in it",
            "classified": classified,
        }
    return {
        "mode": "targeted",
        "node_ids": deduped,
        "reason": "targeted selection",
        "classified": classified,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Classify changed files and select tests.")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--changed-file", action="append", default=[], dest="changed")
    args = ap.parse_args(argv)
    print(json.dumps(select_tests(args.changed, args.root.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
