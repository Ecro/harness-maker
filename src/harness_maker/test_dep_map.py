"""Test dependency map — map changed source files to affected tests (TDAD).

Given a list of changed source files, resolves which test files are
likely affected using convention-based naming and import analysis.
Used by the execute stage to provide concrete test hints instead of
generic "follow TDD" instructions.
"""

from __future__ import annotations

import ast
import sys
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


# ── qualified module resolution (PLAN-dep-map-alias-imports ADR-001) ──────────
#
# Matching is on fully qualified dotted names, never on stems or substrings. Three
# roots are involved and conflating any two of them silently breaks resolution:
#
#   source_root   the directory a file is imported RELATIVE TO — `src/` for a
#                 src-layout project, the project root for a flat one. Derived from
#                 the project (`_SOURCE_ROOT_DIRS`), NOT by walking `__init__.py`
#                 upward: that walk is right for regular packages and wrong for
#                 namespace packages in every layout, naming
#                 `src/acme/widgets/mod.py` as `widgets.mod`.
#   search_root   the CHANGED module's source root — the anchor for the
#                 module-existence probe. An early draft anchored it one level too
#                 deep, expanding to `src/harness_maker/harness_maker/…`, which never
#                 exists; every `from P import n` then degraded to a bare `P` edge and
#                 the alias case this module exists to fix still resolved to nothing.
#   importer_pkg  the IMPORTING file's own package — used ONLY for `node.level`. It is
#                 a different tree from the target's: a test file under `tests/` is
#                 rooted at the project root, not at `src/`.


#: Conventional import roots inside a project, most specific first. A module under one of
#: these is named relative to it; everything else is named relative to the project root.
#:
#: This replaced deriving the root by walking `__init__.py` upward. That walk is correct
#: for regular packages and wrong for NAMESPACE packages in every layout — measured on all
#: four shapes: `src/acme/widgets/mod.py` with no `__init__.py` anywhere resolved to
#: `widgets.mod` with a search root of `src/acme`, so a consumer importing
#: `acme.widgets.mod` matched nothing. Deriving from the project instead makes the answer
#: `acme.widgets.mod` for src-layout and flat layout, namespace and regular alike.
#:
#: Not yet read from configuration: `[tool.setuptools] package-dir` and the Poetry/Hatch
#: equivalents can name a root outside this tuple. Such a project degrades to naming
#: relative to the project root — fewer matches, so FULL — never a wrong match.
_SOURCE_ROOT_DIRS: tuple[str, ...] = ("src", "lib")


def _source_root(path: Path, project_root: Path) -> Path:
    """The directory `path` is imported relative to."""
    for name in _SOURCE_ROOT_DIRS:
        candidate = project_root / name
        # A directory that is itself importable is a PACKAGE, never an import root.
        # Without this guard a project whose `lib/` is a real package (consumers write
        # `import lib.foo`) resolved `lib/foo.py` to the name `foo` and lost every
        # consumer — a regression on a shape the previous `__init__.py` walk handled
        # correctly, and one that could cross-select with a top-level `foo.py`.
        if not candidate.is_dir() or (candidate / "__init__.py").exists():
            continue
        if path.is_relative_to(candidate):
            return candidate
    if path.is_relative_to(project_root):
        return project_root
    # Outside the project entirely — fall back to the enclosing package chain so an
    # absolute path from another tree still yields something rather than raising.
    d = path.parent
    while d.parent != d and (d / "__init__.py").exists():
        d = d.parent
    return d


def _qualified_name(path: Path, source_root: Path) -> str:
    """Dotted module name relative to its source root (`acme.widgets.mod`)."""
    try:
        rel = path.relative_to(source_root)
    except ValueError:
        return path.stem
    parts = list(rel.parts)
    parts[-1] = Path(parts[-1]).stem
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _importer_package(path: Path, project_root: Path) -> str:
    """The package a file lives in — `""` when it is not inside one."""
    qual = _qualified_name(path, _source_root(path, project_root))
    return qual.rsplit(".", 1)[0] if "." in qual else ""


def _module_exists(dotted: str, search_root: Path) -> bool:
    """Whether `dotted` names a real module or package under `search_root`."""
    if not dotted:
        return False
    base = search_root.joinpath(*dotted.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def _from_base(node: ast.ImportFrom, importer_pkg: str) -> str:
    """Resolve an `ImportFrom`'s base package, honouring `node.level`.

    Level 1 means "this package", so it keeps ALL of `importer_pkg` — expressed as
    `parts[:len(parts) - (level - 1)]` rather than the tempting `parts[:-(level - 1)]`,
    which is correct at level 2 and empties the list at level 1 (a slice has no
    negative zero).
    """
    if node.level == 0:
        return node.module or ""
    parts = importer_pkg.split(".") if importer_pkg else []
    keep = len(parts) - (node.level - 1)
    if keep < 0:
        return ""
    base_parts = parts[:keep]
    if node.module:
        base_parts = base_parts + node.module.split(".")
    return ".".join(base_parts)


#: Module-scoped, NOT per-invocation. `select_tests` calls `classify_path` per changed
#: file, `classify_path` calls `build_test_hints` with a ONE-element list, and
#: `select_tests` calls it again per file — 2N invocations for an N-file change. A cache
#: scoped to one invocation is therefore discarded 2N times and buys nothing on the
#: multi-file path the review auto-fix loop creates. Keyed on `(path, mtime_ns, size)` so
#: an edit within one process is not served stale.
_AST_CACHE: dict[tuple[str, int, int], ast.Module | None] = {}
_TARGETS_CACHE: dict[tuple[str, int, int, str, str], set[str]] = {}
#: Keyed by root AND a file-set fingerprint (count, newest mtime). The fingerprint costs
#: one `rglob` + `stat` per lookup and saves the AST walk, which is the expensive half.
#: Without it the map was permanently stale for the rest of the process — and
#: `execute.md.j2` tells agents to call `build_test_hints()` in-process, which is exactly
#: where a file created between two calls must be seen.
_REVERSE_CACHE: dict[tuple[str, str, int, int, int], dict[str, list[Path]]] = {}


def clear_caches() -> None:
    """Drop every memo. For in-process callers that mutate the tree between selections."""
    _AST_CACHE.clear()
    _TARGETS_CACHE.clear()
    _REVERSE_CACHE.clear()


def _file_key(path: Path) -> tuple[str, int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), st.st_mtime_ns, st.st_size)


def _parse_cached(path: Path) -> ast.Module | None:
    """Parse once per (path, mtime, size); `None` for unreadable or invalid Python."""
    key = _file_key(path)
    if key is None:
        return None
    if key in _AST_CACHE:
        return _AST_CACHE[key]
    tree: ast.Module | None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, ValueError):
        tree = None
    _AST_CACHE[key] = tree
    return tree


def _targets_cached(path: Path, search_root: Path, project_root: Path) -> set[str]:
    """`_import_targets` memoized — the AST WALK is the hot cost, not the parse.

    A hub module has ~30 dependents and this repo has 364 test files, so an
    uncached walk runs it ~11,000 times per selection over ASTs that are already
    in memory.
    """
    file_key = _file_key(path)
    if file_key is None:
        return set()
    key = (*file_key, str(search_root), str(project_root))
    cached = _TARGETS_CACHE.get(key)
    if cached is not None:
        return cached
    tree = _parse_cached(path)
    targets = (
        set()
        if tree is None
        else _import_targets(tree, _importer_package(path, project_root), search_root)
    )
    _TARGETS_CACHE[key] = targets
    return targets


#: Never walked by the reverse scan. A changed module whose own directory is not a
#: package makes `_package_root` return that directory verbatim — for a root-level
#: `setup.py` / `noxfile.py` / `conftest.py` that is the PROJECT ROOT, and an unfiltered
#: `rglob` then AST-parses the whole checkout. Measured in this repo: 3137 `*.py` files,
#: 2609 of them vendored under `.venv/site-packages`. Parsing those is pure cost — a
#: vendored library is never a reverse dependent of the project's own module.
#: Matched at ANY depth. `site-packages` carries the whole set in practice — a venv named
#: `env/` or `.direnv/` still contains `lib/pythonX/site-packages/`.
_REVERSE_SCAN_EXCLUDED = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        "site-packages",
        "node_modules",
        ".worktrees",
    }
)

#: Excluded ONLY when the scan root is not itself a package — i.e. exactly the
#: project-root case the cap exists for. `build/` and `dist/` mean build artefacts there,
#: but `src/pkg/build/steps.py` is an ordinary first-party subpackage, and `_package_root`
#: for a module in `src/pkg` IS `src/pkg`, which makes `build` look top-level from that
#: vantage point. Anchoring on the string position alone dropped it — caught by
#: `test_a_first_party_build_subpackage_is_still_scanned`.
_REVERSE_SCAN_EXCLUDED_TOPLEVEL = frozenset({"build", "dist"})

#: Above this many candidate files the reverse walk is abandoned rather than paid for.
#: Skipping it costs coverage the direct-importer scan still supplies, and an unmapped
#: file still falls through to FULL — the fail-safe direction. A multi-minute selection
#: inside the review auto-fix loop's verify step is the outcome this avoids.
_REVERSE_SCAN_FILE_CAP = 2000


def _reverse_scan_candidates(source_root: Path, project_root: Path | None = None) -> list[Path]:
    # `build/`/`dist/` mean artefacts only AT THE PROJECT ROOT. The gate used to test
    # whether the scan root was a package, which was equivalent while the root was the
    # topmost package — after the source-root change the root is `src/`, `lib/` or the
    # project root, none of which carry an `__init__.py`, so that test was permanently
    # False and a first-party `src/build/` was silently dropped from the reverse map.
    at_project_root = project_root is None or source_root == project_root
    kept: list[Path] = []
    for p in sorted(source_root.rglob("*.py")):
        # `[:-1]` drops the filename — an excluded name must be a DIRECTORY component.
        dirs = p.relative_to(source_root).parts[:-1]
        if _REVERSE_SCAN_EXCLUDED.intersection(dirs):
            continue
        if at_project_root and dirs and dirs[0] in _REVERSE_SCAN_EXCLUDED_TOPLEVEL:
            continue
        kept.append(p)
    return kept


def _reverse_map(source_root: Path, project_root: Path) -> dict[str, list[Path]]:
    """Every qualified name -> the source files importing it, for one source root."""
    candidates = _reverse_scan_candidates(source_root, project_root)
    newest = 0
    total_size = 0
    for p in candidates:
        fk = _file_key(p)
        if fk is not None:
            newest = max(newest, fk[1])
            total_size += fk[2]
    # `project_root` belongs in the key: the cached value depends on it via
    # `_importer_package`. `total_size` is free (already in `_file_key`) and closes the
    # same-count/non-increasing-mtime hole — an in-place edit on a coarse-granularity
    # filesystem, or a delete+add whose new file is older than the existing max.
    key = (
        str(source_root.resolve()),
        str(project_root.resolve()),
        len(candidates),
        newest,
        total_size,
    )
    cached = _REVERSE_CACHE.get(key)
    if cached is not None:
        return cached
    mapping: dict[str, list[Path]] = {}
    if len(candidates) <= _REVERSE_SCAN_FILE_CAP:
        for py_file in candidates:
            for target in _targets_cached(py_file, source_root, project_root):
                mapping.setdefault(target, []).append(py_file)
    else:
        # The one path where the selection silently narrows. Everything else in this
        # module either reports a bounded node list or says FULL and why; an empty
        # reverse map above the cap is indistinguishable from "no dependents exist"
        # unless it is announced. stderr, so the JSON on stdout stays parseable.
        print(
            f"[dep-map] reverse scan skipped for {source_root}: "
            f"{len(candidates)} candidate files > cap {_REVERSE_SCAN_FILE_CAP}; "
            "dependents' tests are NOT included in this selection",
            file=sys.stderr,
        )
    _REVERSE_CACHE[key] = mapping
    return mapping


def _reverse_dependents(changed: Path, project_root: Path) -> list[Path]:
    """Source modules importing `changed` directly — exactly ONE hop, never itself.

    Depth is fixed at 1 by ADR-002: a transitive walk from a hub like `io_utils`
    (32 direct importers here) reaches nearly every module, so `mode: targeted`
    would become a slower spelling of the full suite it exists to avoid.
    """
    source_root = _source_root(changed, project_root)
    qualname = _qualified_name(changed, source_root)
    if not qualname:
        return []
    resolved = changed.resolve()
    return [
        p
        for p in _reverse_map(source_root, project_root).get(qualname, [])
        if p.resolve() != resolved
    ]


def _with_ancestors(dotted: str, search_root: Path) -> set[str]:
    """`a.b.c` plus every ancestor package that actually resolves.

    Importing `a.b.c` EXECUTES `a/__init__.py` and `a/b/__init__.py`, so a change to
    either is a real dependency of the importer. Emitting only the leaf left every
    `__init__.py` with zero importers: verified before this fix — changing
    `pkg/__init__.py` with a consumer doing `import pkg.sub.mod` produced `hints: []`.
    Ancestors are probed rather than assumed so a dotted name from an unresolvable
    third-party import contributes nothing.
    """
    parts = dotted.split(".")
    out = {dotted}
    for i in range(1, len(parts)):
        prefix = ".".join(parts[:i])
        if _module_exists(prefix, search_root):
            out.add(prefix)
    return out


def _import_targets(tree: ast.Module, importer_pkg: str, search_root: Path) -> set[str]:
    """Every qualified module name a file imports."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # `alias.name`, never `alias.asname` — `import pkg.a as z` depends on
            # `pkg.a`; `pkg.z` does not exist.
            for alias in node.names:
                targets |= _with_ancestors(alias.name, search_root)
        elif isinstance(node, ast.ImportFrom):
            base = _from_base(node, importer_pkg)
            if not base:
                continue
            # The base is ALWAYS an edge — `from pkg import a` depends on `pkg`'s
            # `__init__` too. `pkg.a` is added on top when it is a real module; a
            # name that is not one is a symbol and contributes no further edge.
            targets |= _with_ancestors(base, search_root)
            for alias in node.names:
                if alias.name == "*":
                    continue
                candidate = f"{base}.{alias.name}"
                if _module_exists(candidate, search_root):
                    targets.add(candidate)
    return targets


def find_importers(
    module_qualname: str,
    test_dir: Path,
    search_root: Path,
    project_root: Path,
) -> list[Path]:
    """Find test consumers whose imports resolve to the given qualified module name.

    `conftest.py` counts as a consumer (ADR-003): this repo's `tests/unit/conftest.py`
    imports `economics_source` inside an autouse fixture, and an autouse fixture that
    breaks takes its whole directory tree with it. The caller maps a conftest hit to
    its parent directory — a conftest collects no tests itself.
    """
    if not test_dir.is_dir():
        return []

    importers: list[Path] = []
    for py_file in sorted(test_dir.rglob("*.py")):
        if not (py_file.name.startswith("test_") or py_file.name == "conftest.py"):
            continue
        if module_qualname in _targets_cached(py_file, search_root, project_root):
            importers.append(py_file)
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

        # The changed file plus its 1-hop reverse dependents (ADR-002). Each origin
        # contributes both its naming-convention candidates and its importers.
        origins: list[Path] = [src]
        if not src.stem.startswith("test_"):
            origins.extend(_reverse_dependents(src, project_root))

        affected: list[Path] = []
        for origin in origins:
            affected.extend(source_to_test_candidates(origin, project_root))
            if origin.stem.startswith("test_"):
                continue
            # Derive BOTH roots here — the matcher needs a qualified name, and the
            # probe needs that module's own search root. Passing the stem or
            # `project_root` instead is arity-compatible and silently resolves
            # nothing, which is indistinguishable from "no tests cover this file".
            origin_root = _source_root(origin, project_root)
            origin_qual = _qualified_name(origin, origin_root)
            if not origin_qual:
                continue
            for test_dir_name in ("tests", "test"):
                test_dir = project_root / test_dir_name
                if test_dir.is_dir():
                    affected.extend(
                        find_importers(origin_qual, test_dir, origin_root, project_root)
                    )

        hints[rel_src] = _normalize_hints(affected, project_root)
    return hints


def _normalize_hints(affected: list[Path], project_root: Path) -> list[str]:
    """Relativize, map conftest hits to their directory, de-duplicate, subsume."""
    rels: list[str] = []
    for path in affected:
        target = path.parent if path.name == "conftest.py" else path
        rel = (
            str(target.relative_to(project_root))
            if target.is_relative_to(project_root)
            else str(target)
        )
        rel = rel.replace("\\", "/")
        if rel not in rels:
            rels.append(rel)
    # A directory node and a file beneath it must never both appear — pytest would
    # collect the same module twice.
    dirs = [r for r in rels if not r.endswith(".py")]
    return [r for r in rels if not any(r.startswith(d + "/") for d in dirs)]


# ── four-way selection (PLAN-workflow-step-audit ADR-008) ──────────────────────
#
# `build_test_hints` above skips every non-`.py` file, so the interview's locked rule
# ("a changed file with no hint → FULL") degenerates to always-FULL in this repo, where
# most changes are `.j2` templates, markdown and config. The classifier below keeps what
# that rule protects — a source file no test maps to must never be silently untested —
# and gives the other three shapes a bounded answer.
#
# That was only HALF the cause, and naming one cause is what kept the other unexamined
# for so long. The second half was in `find_importers`: its `ImportFrom` branch read
# `node.module` and never `node.names`, so `from harness_maker import autopilot_ledger`
# — 121 occurrences under `tests/` — resolved to zero importers. A `.py` module reachable
# only that way had no hint either, and took the same always-FULL branch. Fixed by
# ADR-001 of PLAN-dep-map-alias-imports (qualified module resolution). When this comment
# is read again during a future always-FULL investigation: check BOTH halves before
# concluding the classifier is the constraint.
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
            # The bare roots are kept too: a top-level `tests/conftest.py` — the default
            # pytest layout for shared fixtures — normalizes to the directory node
            # `tests`, and `startswith("tests/")` rejects it. That filtered every hint
            # away and forced FULL for every module such a conftest imports, killing the
            # optimisation for the most common layout there is.
            hinted = build_test_hints([project_root / rel], project_root).get(rel, [])
            kept = [
                h
                for h in hinted
                if (n := h.replace("\\", "/")).startswith(("tests/", "test/"))
                or n in ("tests", "test")
            ]
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

    # `_normalize_hints` enforces directory-subsumes-file PER changed file; this loop
    # accumulates ACROSS them, so file A's `tests` (from a top-level conftest) and file
    # B's `tests/unit/test_b.py` both arrive and only exact duplicates collapse. Costs a
    # double collection, never a missed test — but pytest running the same module twice
    # is noise the selector should not emit.
    _dirs = [n for n in dict.fromkeys(node_ids) if not n.endswith(".py")]
    deduped = sorted({n for n in node_ids if not any(n.startswith(d + "/") for d in _dirs)})
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
