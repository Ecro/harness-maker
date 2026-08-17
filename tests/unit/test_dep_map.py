"""Tests for test dependency map (TDAD — Phase 11)."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import test_dep_map as dep_map
from harness_maker.test_dep_map import (
    build_test_hints,
    find_importers,
    select_tests,
    source_to_test_candidates,
)


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal project structure for testing.

    The test files import `pkg.<mod>`, matching where the sources actually live.
    They used to import `harness_maker.<mod>` while the sources sat under
    `src/pkg/` — an inconsistency only the old substring matcher tolerated, and
    exactly the class of false positive this module no longer accepts.
    """
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "auth.py").write_text("def login(): pass\n")
    (tmp_path / "src" / "pkg" / "utils.py").write_text("def helper(): pass\n")
    (tmp_path / "tests" / "unit" / "test_auth.py").write_text(
        "from pkg.auth import login\ndef test_login(): pass\n"
    )
    (tmp_path / "tests" / "unit" / "test_utils.py").write_text(
        "from pkg.utils import helper\ndef test_helper(): pass\n"
    )
    return tmp_path


# ── qualified-module-path resolution (PLAN-dep-map-alias-imports ADR-001) ──────
#
# Every assertion below names the wrong implementation it rejects. An assertion
# that no broken implementation fails is decorative — see
# `[fail:test] assertion-invariant-over-named-dimension` (count:4).


def _qualified_project(tmp_path: Path) -> Path:
    """A real package layout with the shapes ADR-001 must separate.

    `pkg/profile.py` and `pkg/sub/profile.py` share a stem; `cache` is a strict
    substring of `detection_cache`; `other/` gives relative imports something two
    levels up to reach.
    """
    src = tmp_path / "src"
    (src / "pkg" / "sub").mkdir(parents=True)
    (src / "pkg" / "other").mkdir(parents=True)
    (src / "pkg" / "inpkg").mkdir(parents=True)
    for pkg_dir in (src / "pkg", src / "pkg" / "sub", src / "pkg" / "other", src / "pkg" / "inpkg"):
        (pkg_dir / "__init__.py").write_text("")
    for mod in ("a", "b", "cache", "detection_cache", "profile"):
        (src / "pkg" / f"{mod}.py").write_text("VALUE = 1\n")
    (src / "pkg" / "sub" / "profile.py").write_text("VALUE = 1\n")
    (src / "pkg" / "other" / "c.py").write_text("VALUE = 1\n")

    tests = tmp_path / "tests" / "unit"
    tests.mkdir(parents=True)
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tests / "__init__.py").write_text("")
    return tmp_path


def _write_test(root: Path, name: str, body: str) -> None:
    (root / "tests" / "unit" / name).write_text(body + "\ndef test_x(): pass\n")


def _found(root: Path, qualname: str) -> set[str]:
    return {p.name for p in find_importers(qualname, root / "tests", root / "src", root)}


def test_importfrom_alias_is_an_importer(tmp_path: Path) -> None:
    """`from pkg import a, b` must resolve for BOTH names.

    Rejects the shipped implementation, which read only `node.module` ("pkg") and
    never `node.names`, so every alias-only consumer resolved to zero importers.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_alias.py", "from pkg import a, b")
    assert _found(root, "pkg.b") == {"test_alias.py"}
    assert _found(root, "pkg.a") == {"test_alias.py"}


def test_plain_dotted_import_still_resolves(tmp_path: Path) -> None:
    """`import pkg.a` must keep working — rejects an alias-only fix that drops `ast.Import`."""
    root = _qualified_project(tmp_path)
    _write_test(root, "test_plain.py", "import pkg.a")
    assert _found(root, "pkg.a") == {"test_plain.py"}


def test_from_module_import_symbol_still_resolves(tmp_path: Path) -> None:
    """`from pkg.a import VALUE` selects `pkg.a` — rejects dropping the `node.module` edge."""
    root = _qualified_project(tmp_path)
    _write_test(root, "test_frommod.py", "from pkg.a import VALUE")
    assert _found(root, "pkg.a") == {"test_frommod.py"}


def test_import_as_matches_the_module_not_the_alias(tmp_path: Path) -> None:
    """`import pkg.a as z` binds to `pkg.a`.

    Rejects an implementation reading `alias.asname`: `pkg.z` does not exist, so a
    matcher keyed on the local name selects nothing and `pkg.a` is missed.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_asname.py", "import pkg.a as z")
    assert _found(root, "pkg.a") == {"test_asname.py"}
    assert _found(root, "pkg.z") == set()


def test_from_import_of_a_symbol_does_not_invent_a_module(tmp_path: Path) -> None:
    """`from pkg import VALUE` (no `pkg/VALUE.py`) yields `pkg`, never `pkg.VALUE`.

    Rejects a bag-of-names implementation that treats every imported symbol as a
    module — the defect that made segment-set matching unsound.
    """
    root = _qualified_project(tmp_path)
    (root / "src" / "pkg" / "__init__.py").write_text("VALUE = 1\n")
    _write_test(root, "test_symbol.py", "from pkg import VALUE")
    assert _found(root, "pkg") == {"test_symbol.py"}
    assert _found(root, "pkg.VALUE") == set()


def test_star_import_binds_only_the_package(tmp_path: Path) -> None:
    """`from pkg import *` yields `pkg` and nothing named `*`."""
    root = _qualified_project(tmp_path)
    _write_test(root, "test_star.py", "from pkg import *")
    assert _found(root, "pkg") == {"test_star.py"}
    assert _found(root, "pkg.*") == set()


def test_relative_import_resolves_against_the_importers_package(tmp_path: Path) -> None:
    """`from .. import b` inside `pkg.inpkg` resolves to `pkg.b`.

    Rejects an implementation that ignores `node.level` (it would see `node.module
    is None` and emit nothing) and one that walks the wrong number of levels.
    """
    root = _qualified_project(tmp_path)
    (root / "src" / "pkg" / "inpkg" / "test_rel.py").write_text(
        "from .. import b\ndef test_x(): pass\n"
    )
    found = {
        p.name for p in find_importers("pkg.b", root / "src" / "pkg" / "inpkg", root / "src", root)
    }
    assert found == {"test_rel.py"}


def test_relative_import_with_module_walks_two_levels(tmp_path: Path) -> None:
    """`from ..other import c` inside `pkg.inpkg` resolves to `pkg.other.c`.

    Rejects an off-by-one level walk: level 2 must strip one package from the
    importer's own package, not zero and not two.
    """
    root = _qualified_project(tmp_path)
    (root / "src" / "pkg" / "inpkg" / "test_rel2.py").write_text(
        "from ..other import c\ndef test_x(): pass\n"
    )
    scan = root / "src" / "pkg" / "inpkg"
    assert {p.name for p in find_importers("pkg.other.c", scan, root / "src", root)} == {
        "test_rel2.py"
    }
    assert find_importers("pkg.inpkg.other.c", scan, root / "src", root) == []


def test_substring_of_another_module_is_not_an_importer(tmp_path: Path) -> None:
    """`pkg.cache` is NOT selected by a file importing only `pkg.detection_cache`.

    Rejects the shipped substring matcher, under which `"cache" in
    "pkg.detection_cache"` held and eight unrelated suites were selected.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_detcache.py", "from pkg import detection_cache")
    assert _found(root, "pkg.detection_cache") == {"test_detcache.py"}
    assert _found(root, "pkg.cache") == set()


def test_same_stem_in_two_packages_are_distinct(tmp_path: Path) -> None:
    """`pkg.profile` and `pkg.sub.profile` never select each other.

    Rejects stem-keyed matching: this repo really does ship
    `harness_maker/profile.py` and `harness_maker/memory/profile.py`.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_top_profile.py", "from pkg import profile")
    _write_test(root, "test_sub_profile.py", "from pkg.sub import profile")
    assert _found(root, "pkg.profile") == {"test_top_profile.py"}
    assert _found(root, "pkg.sub.profile") == {"test_sub_profile.py"}


def test_relative_import_level_one_stays_in_the_importers_own_package(tmp_path: Path) -> None:
    """`from . import mod` inside `pkg.inpkg` resolves to `pkg.inpkg.mod`, not `pkg.mod`.

    Level 1 is where the natural slice `parts[:-(level - 1)]` breaks: at level 2 it
    is `parts[:-1]` and correct, at level 1 it is `parts[:0]` — the empty list, not
    the identity, because a slice has no negative zero. Both level-2 tests above
    pass against that implementation; only this one fails it.

    The second assertion rejects the opposite error (walking up one level too
    many). `pkg/mod.py` is created precisely so that an over-walking
    implementation would emit a REAL module and could not be caught by a probe
    miss.
    """
    root = _qualified_project(tmp_path)
    (root / "src" / "pkg" / "mod.py").write_text("VALUE = 1\n")
    (root / "src" / "pkg" / "inpkg" / "mod.py").write_text("VALUE = 1\n")
    (root / "src" / "pkg" / "inpkg" / "test_rel1.py").write_text(
        "from . import mod\ndef test_x(): pass\n"
    )
    scan = root / "src" / "pkg" / "inpkg"
    assert {p.name for p in find_importers("pkg.inpkg.mod", scan, root / "src", root)} == {
        "test_rel1.py"
    }
    assert find_importers("pkg.mod", scan, root / "src", root) == []


def test_the_package_itself_is_an_importer_edge_when_the_submodule_also_resolves(
    tmp_path: Path,
) -> None:
    """`from pkg import a, b` makes `pkg` an edge TOO, not just `pkg.a` / `pkg.b`.

    ADR-001's rule is "emit `P`, and additionally `P.n` iff the probe hits" — an
    AND, not an either/or. Every other test here exercises only the `P.n` side
    when the probe hits, and the one bare-`P` assertion sits on a probe MISS, so
    the two readings are indistinguishable without this test.

    Rejects the either/or reading, under which editing `harness_maker/__init__.py`
    selects none of the 121 `from harness_maker import x` consumers and still
    reports `mode: targeted`.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_bothedge.py", "from pkg import a, b")
    assert _found(root, "pkg") == {"test_bothedge.py"}
    assert _found(root, "pkg.a") == {"test_bothedge.py"}


def test_probe_resolves_a_subpackage_not_only_a_module(tmp_path: Path) -> None:
    """`from pkg import sub` resolves `pkg.sub` via the `n/__init__.py` probe arm.

    Every other `from P import n` case in this file resolves through the `n.py`
    arm, so an implementation that probes only `n.py` passes all of them.
    Rejects that implementation: in this repo `from harness_maker import memory`
    would otherwise degrade to a bare `harness_maker` edge, and a change to
    `harness_maker/memory/__init__.py` would select nothing importing it that way.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_subpkg.py", "from pkg import sub")
    assert _found(root, "pkg.sub") == {"test_subpkg.py"}


def test_build_test_hints_uses_qualified_resolution_at_the_call_site(tmp_path: Path) -> None:
    """The importer edge is the ONLY route from `pkg/widget.py` to its consumer.

    `source_to_test_candidates` cannot help here — the consumer is deliberately
    named `test_unrelated_name.py`, so no filename-convention candidate exists.
    That makes this the only test in the file that fails when `build_test_hints`
    is wired with the wrong arguments rather than not wired at all.

    Rejects `find_importers(module_stem, test_dir, project_root)`: the stem
    `"widget"` is not the qualified name `"pkg.widget"`, and a probe anchored at
    the project root looks for `<root>/pkg/widget.py` while the module lives at
    `<root>/src/pkg/widget.py`. Both wrong values yield an empty hint list, which
    is indistinguishable from "no tests cover this file".
    """
    root = _qualified_project(tmp_path)
    (root / "src" / "pkg" / "widget.py").write_text("VALUE = 1\n")
    _write_test(root, "test_unrelated_name.py", "from pkg import widget")

    hints = build_test_hints([root / "src" / "pkg" / "widget.py"], root)
    assert hints["src/pkg/widget.py"] == ["tests/unit/test_unrelated_name.py"]


def test_importer_in_a_different_package_root_still_resolves(tmp_path: Path) -> None:
    """A `tests`-rooted importer resolves a `src`-rooted target.

    This is the two-root separation: the importer's own package root is `tests`
    (both `tests/` and `tests/unit/` are packages here, as in this repo), while
    the module-existence probe must be anchored at the CHANGED module's search
    root, `src/`. Rejects probing under the importer's root, and rejects the
    draft that probed `<package_root>/P/n.py` — i.e. `src/pkg/pkg/b.py`, which
    never exists, silently degrading every `from P import n` to a bare `P` edge.
    """
    root = _qualified_project(tmp_path)
    _write_test(root, "test_crossroot.py", "from pkg import b")
    assert _found(root, "pkg.b") == {"test_crossroot.py"}


def test_source_to_test_candidates_finds_unit_test(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    src = root / "src" / "pkg" / "auth.py"
    candidates = source_to_test_candidates(src, root)
    names = [c.name for c in candidates]
    assert "test_auth.py" in names


def test_source_to_test_candidates_no_match(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    (root / "src" / "pkg" / "unknown.py").write_text("pass\n")
    src = root / "src" / "pkg" / "unknown.py"
    candidates = source_to_test_candidates(src, root)
    assert candidates == []


def test_source_to_test_returns_self_for_test_file(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    test_file = root / "tests" / "unit" / "test_auth.py"
    candidates = source_to_test_candidates(test_file, root)
    assert test_file in candidates


def test_find_importers_detects_import(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    importers = find_importers("pkg.auth", root / "tests", root / "src", root)
    names = [p.name for p in importers]
    assert "test_auth.py" in names


def test_find_importers_no_match(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    importers = find_importers("pkg.nonexistent_module", root / "tests", root / "src", root)
    assert importers == []


def test_find_importers_handles_missing_dir(tmp_path: Path) -> None:
    importers = find_importers("pkg.auth", tmp_path / "no_such_dir", tmp_path / "src", tmp_path)
    assert importers == []


# ── source-root derivation across project layouts (review round 3) ────────────
#
# The root was derived from `__init__.py` presence alone, which is correct for regular
# packages and wrong for namespace packages in EVERY layout: `src/acme/widgets/mod.py`
# resolved to `widgets.mod`, so a test importing `acme.widgets.mod` matched nothing.
# Measured before the fix on all four shapes below.


def _layout(tmp_path: Path, *, src: bool, namespace: bool) -> tuple[Path, Path]:
    """Build one of the four layouts; return (project_root, changed_module)."""
    base = tmp_path / "src" if src else tmp_path
    pkg = base / "acme" / "widgets"
    pkg.mkdir(parents=True)
    if not namespace:
        (base / "acme" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("VALUE = 1\n")
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    return tmp_path, pkg / "mod.py"


@pytest.mark.parametrize("src", [True, False], ids=["src-layout", "flat-layout"])
@pytest.mark.parametrize("namespace", [True, False], ids=["namespace-pkg", "regular-pkg"])
def test_qualified_name_is_layout_and_package_style_independent(
    tmp_path: Path, src: bool, namespace: bool
) -> None:
    """`acme.widgets.mod` in all four shapes.

    Rejects deriving the root from `__init__.py` presence: with no `__init__.py` the old
    walk stopped at the file's own directory, yielding `widgets.mod` and a search root one
    level too deep. The regular-package arms are the regression guard — they were correct
    before and must stay correct.
    """
    root, changed = _layout(tmp_path, src=src, namespace=namespace)
    source_root = dep_map._source_root(changed, root)
    assert dep_map._qualified_name(changed, source_root) == "acme.widgets.mod"
    assert source_root == (root / "src" if src else root)


@pytest.mark.parametrize("src", [True, False], ids=["src-layout", "flat-layout"])
@pytest.mark.parametrize("namespace", [True, False], ids=["namespace-pkg", "regular-pkg"])
def test_importers_resolve_in_every_layout(tmp_path: Path, src: bool, namespace: bool) -> None:
    """End-to-end: a consumer importing the module is found in all four shapes."""
    root, changed = _layout(tmp_path, src=src, namespace=namespace)
    (root / "tests" / "unit" / "test_widget_consumer.py").write_text(
        "from acme.widgets import mod\ndef test_x(): pass\n"
    )
    rel = changed.relative_to(root).as_posix()
    hints = build_test_hints([changed], root)
    assert "tests/unit/test_widget_consumer.py" in hints[rel]


def test_a_source_root_candidate_that_is_itself_a_package_is_not_a_root(tmp_path: Path) -> None:
    """`lib/` with an `__init__.py` is a PACKAGE, so `lib/foo.py` is `lib.foo`.

    Rejects treating any existing `src`/`lib` directory as an import root: measured, that
    named the module `foo`, lost every `import lib.foo` consumer (`hints: []`), and could
    cross-select with a top-level `foo.py`. A regression on a shape the previous
    `__init__.py` walk got right.
    """
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "__init__.py").write_text("")
    (tmp_path / "lib" / "foo.py").write_text("VALUE = 1\n")
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_consumer.py").write_text(
        "import lib.foo\ndef test_x(): pass\n"
    )
    changed = tmp_path / "lib" / "foo.py"
    assert dep_map._source_root(changed, tmp_path) == tmp_path
    assert dep_map._qualified_name(changed, tmp_path) == "lib.foo"
    assert "tests/unit/test_consumer.py" in build_test_hints([changed], tmp_path)["lib/foo.py"]


def test_build_is_excluded_only_when_the_scan_root_is_the_project_root(
    tmp_path: Path,
) -> None:
    """`src/build/` is first-party; `<root>/build/` is artefacts.

    The gate used to ask whether the scan root was a package — equivalent while the root
    was the topmost package, but permanently False once the root became `src/`, so a
    first-party `src/build/` was silently dropped. Measured: the scan returned only
    `src/pkg/__init__.py`.
    """
    (tmp_path / "src" / "build").mkdir(parents=True)
    (tmp_path / "src" / "build" / "__init__.py").write_text("")
    (tmp_path / "src" / "build" / "steps.py").write_text("VALUE = 1\n")
    (tmp_path / "build" / "lib").mkdir(parents=True)
    (tmp_path / "build" / "lib" / "copy.py").write_text("VALUE = 1\n")

    under_src = [p.name for p in dep_map._reverse_scan_candidates(tmp_path / "src", tmp_path)]
    assert "steps.py" in under_src, "first-party src/build/ was dropped"

    under_root = [p.name for p in dep_map._reverse_scan_candidates(tmp_path, tmp_path)]
    assert "copy.py" not in under_root, "root-level build/ artefacts were scanned"


def test_reverse_map_sees_a_file_created_after_the_first_call(tmp_path: Path) -> None:
    """The reverse cache must not serve a pre-creation map for the rest of the process.

    `_REVERSE_CACHE` was keyed on the scan root alone, so an in-process caller — which
    `execute.md.j2` explicitly invites by telling agents to call `build_test_hints()`
    directly — got a permanently stale map. Rejects a key with no file-set fingerprint.
    """
    root = _reverse_project(tmp_path)
    first = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert "tests/unit/test_late.py" not in first["src/pkg/a.py"]

    (root / "src" / "pkg" / "late.py").write_text("from pkg import a\n")
    (root / "tests" / "unit" / "test_late.py").write_text("def test_x(): pass\n")

    second = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert "tests/unit/test_late.py" in second["src/pkg/a.py"]


def test_clear_caches_empties_all_three(tmp_path: Path) -> None:
    """A public reset for in-process consumers — rejects clearing only one cache."""
    root = _reverse_project(tmp_path)
    build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert dep_map._AST_CACHE
    assert dep_map._TARGETS_CACHE
    assert dep_map._REVERSE_CACHE
    dep_map.clear_caches()
    assert not dep_map._AST_CACHE
    assert not dep_map._TARGETS_CACHE
    assert not dep_map._REVERSE_CACHE


# ── 1-hop reverse dependency + conftest consumers (ADR-002 / ADR-003) ─────────


def _reverse_project(tmp_path: Path) -> Path:
    """`c` -> `b` -> `a`, plus a cross-subpackage dependent and an isolated module."""
    src = tmp_path / "src"
    (src / "pkg" / "sub").mkdir(parents=True)
    (src / "pkg" / "__init__.py").write_text("")
    (src / "pkg" / "sub" / "__init__.py").write_text("")
    (src / "pkg" / "a.py").write_text("VALUE = 1\n")
    (src / "pkg" / "b.py").write_text("from pkg import a\n")
    (src / "pkg" / "c.py").write_text("from pkg import b\n")
    (src / "pkg" / "lonely.py").write_text("VALUE = 1\n")
    (src / "pkg" / "sub" / "deep.py").write_text("from pkg import a\n")

    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    for name in ("a", "b", "c", "lonely", "deep"):
        (unit / f"test_{name}.py").write_text("def test_x(): pass\n")
    return tmp_path


def test_reverse_dependency_selects_the_dependents_tests(tmp_path: Path) -> None:
    """Changing `a` selects `test_b` and `test_deep` — its 1-hop dependents.

    Rejects an implementation with no reverse walk at all, under which
    `ai_readiness`'s tests stop running when `readiness.py` changes and the
    targeted run reports green over a module it never exercised.
    """
    root = _reverse_project(tmp_path)
    hints = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert set(hints["src/pkg/a.py"]) == {
        "tests/unit/test_a.py",
        "tests/unit/test_b.py",
        "tests/unit/test_deep.py",
    }


def test_reverse_dependency_is_exactly_one_hop(tmp_path: Path) -> None:
    """`c` imports `b` imports `a`; changing `a` selects `test_b` but NOT `test_c`.

    The negative arm alone would be satisfied by every pre-Phase-2 implementation
    — with no reverse walk at all, `test_c.py` is trivially absent. It only carries
    information anchored to a graph that was actually walked, so the positive arm
    is asserted first and in the same function.

    Together they reject a transitive walk: `io_utils` has 32 direct importers in
    this repo, so transitivity reaches nearly every module and `mode: targeted`
    becomes a slower spelling of the full suite it replaces.
    """
    root = _reverse_project(tmp_path)
    hints = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert "tests/unit/test_b.py" in hints["src/pkg/a.py"]
    assert "tests/unit/test_c.py" not in hints["src/pkg/a.py"]


def test_reverse_dependency_crosses_a_subpackage_boundary(tmp_path: Path) -> None:
    """`pkg/sub/deep.py` is found as a dependent of `pkg/a.py`.

    Rejects the parent-directory scan: it would start at `src/pkg` for `a.py` and
    (symmetrically) at `src/pkg/sub` for `deep.py`, so the edge is visible from
    one side only, purely by filesystem position.
    """
    root = _reverse_project(tmp_path)
    hints = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert "tests/unit/test_deep.py" in hints["src/pkg/a.py"]


def test_module_with_no_dependents_is_unchanged(tmp_path: Path) -> None:
    """`lonely.py` gains nothing while `a.py` gains its dependent's tests.

    The `lonely` assertion in isolation is what the pre-Phase-2 code already
    returns, so it cannot fail before the walk exists. Pairing it with the `a.py`
    arm in one function makes the function red today AND keeps the negative
    control, which rejects a walk that skips the import predicate and unions every
    file in the package.
    """
    root = _reverse_project(tmp_path)
    hints = build_test_hints(
        [root / "src" / "pkg" / "a.py", root / "src" / "pkg" / "lonely.py"], root
    )
    assert "tests/unit/test_b.py" in hints["src/pkg/a.py"]
    assert hints["src/pkg/lonely.py"] == ["tests/unit/test_lonely.py"]


def test_reverse_walk_never_includes_the_changed_file_itself(tmp_path: Path) -> None:
    """The helper excludes the changed file from its own dependent set.

    Asserted on the helper, not through `build_test_hints`: a self-included
    dependent contributes `source_to_test_candidates(D) + find_importers(D)` for
    `D == the changed file`, which is byte-identical to the direct expansion
    already present, and de-duplication then erases the difference. The public
    output is therefore invariant over self-inclusion — the very property this
    test names — so only the helper's return value can see it.

    The edge is real and needs no `__init__.py` re-export to exist: `from pkg
    import self_ref` yields base `pkg`, and `_module_exists("pkg.self_ref", src)`
    probes `src/pkg/self_ref.py`, which is the changed file.
    """
    root = _reverse_project(tmp_path)
    changed = root / "src" / "pkg" / "self_ref.py"
    changed.write_text("from pkg import self_ref\n")
    # A genuine dependent, so the exclusion cannot be satisfied by returning nothing.
    other = root / "src" / "pkg" / "other_ref.py"
    other.write_text("from pkg import self_ref\n")

    dependents = {d.resolve() for d in dep_map._reverse_dependents(changed, root)}
    assert other.resolve() in dependents
    assert changed.resolve() not in dependents


def test_conftest_only_selection_collects_tests(tmp_path: Path) -> None:
    """The node id a conftest-only consumer produces actually collects tests.

    ADR-003 exists to close a `targeted` run whose node list collects ZERO tests —
    a green result that ran nothing. Asserting the hint STRING is not that: a
    mapping that produced `tests` (over-broad) or a path `select_tests` filters
    away would satisfy the shape assertions elsewhere in this file and still be
    invisible. This runs the selection through `select_tests` and then hands the
    result to a real pytest collection.
    """
    root = _reverse_project(tmp_path)
    (root / "src" / "pkg" / "fixturedep.py").write_text("VALUE = 1\n")
    (root / "tests" / "unit" / "conftest.py").write_text("from pkg import fixturedep\n")
    # Makes the fixture package importable so the collection exercises the real
    # conftest edge rather than dying on an ImportError.
    (root / "conftest.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent / 'src'))\n"
    )

    selection = select_tests(["src/pkg/fixturedep.py"], root)
    assert selection["mode"] == "targeted", selection["reason"]
    assert selection["node_ids"] == ["tests/unit"]

    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
        + list(selection["node_ids"]),
        cwd=root,
        # An outer PYTEST_ADDOPTS (-n auto, --cov) would be re-applied in the child.
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert "tests/unit/test_a.py::test_x" in collected.stdout, collected.stdout


def test_two_changed_files_where_one_imports_the_other_deduplicate(tmp_path: Path) -> None:
    """Changing `a` and `b` together yields no duplicate entries in either list."""
    root = _reverse_project(tmp_path)
    hints = build_test_hints([root / "src" / "pkg" / "a.py", root / "src" / "pkg" / "b.py"], root)
    for rel in ("src/pkg/a.py", "src/pkg/b.py"):
        assert len(hints[rel]) == len(set(hints[rel])), f"{rel} has duplicates: {hints[rel]}"
    assert "tests/unit/test_b.py" in hints["src/pkg/a.py"]


def test_conftest_consumer_maps_to_its_directory_not_the_conftest_file(tmp_path: Path) -> None:
    """A `conftest.py` importing the changed module contributes `tests/unit`.

    pytest collects nothing from a conftest, so returning the conftest FILE is a
    `targeted` run with an empty node list — a green result that ran no tests, and
    strictly worse than either the before or after state. Rejects that shape
    directly, and rejects leaving conftest unscanned (the autouse fixture in this
    repo's `tests/unit/conftest.py` would stay invisible).
    """
    root = _reverse_project(tmp_path)
    (root / "src" / "pkg" / "fixturedep.py").write_text("VALUE = 1\n")
    (root / "tests" / "unit" / "conftest.py").write_text("from pkg import fixturedep\n")
    hints = build_test_hints([root / "src" / "pkg" / "fixturedep.py"], root)
    assert hints["src/pkg/fixturedep.py"] == ["tests/unit"]
    assert not any(h.endswith("conftest.py") for h in hints["src/pkg/fixturedep.py"])


def test_conftest_directory_subsumes_test_files_under_it(tmp_path: Path) -> None:
    """A directory node and a file beneath it never both appear.

    Rejects appending the directory without de-duplication: pytest would run
    `tests/unit` and `tests/unit/test_a.py`, collecting the same module twice.
    """
    root = _reverse_project(tmp_path)
    (root / "tests" / "unit" / "conftest.py").write_text("from pkg import a\n")
    hints = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert hints["src/pkg/a.py"] == ["tests/unit"]


def test_top_level_conftest_still_yields_a_targeted_selection(tmp_path: Path) -> None:
    """A shared `tests/conftest.py` must not force FULL — review round-1 finding.

    The conftest→directory mapping normalizes a top-level `tests/conftest.py` to the bare
    node `tests`, and `select_tests`' filter tested `startswith("tests/")`, which rejects
    it. Every hint was then filtered away and the run fell to FULL — for the DEFAULT
    pytest layout (shared fixtures at `tests/conftest.py`), i.e. the optimisation was
    dead exactly where it matters most. Verified against the pre-fix code:
    `mode: full`, reason "every hint was filtered out for src/pkg/a.py".
    """
    root = _reverse_project(tmp_path)
    (root / "tests" / "conftest.py").write_text("from pkg import a\n")
    selection = select_tests(["src/pkg/a.py"], root)
    assert selection["mode"] == "targeted", selection["reason"]
    assert selection["node_ids"] == ["tests"]


def test_importing_a_submodule_marks_its_ancestor_packages(tmp_path: Path) -> None:
    """`import pkg.sub.mod` depends on `pkg/__init__.py`, which Python executes.

    Rejects leaf-only edges. On a MINIMAL repro (one consumer, dotted import only) the
    pre-fix code produced `hints: []`. On this richer fixture it produced the other
    tests via `b.py`'s `from pkg import a` base edge but never `test_dotted.py` — which
    is what this assertion pins, and it does fail pre-fix.
    """
    root = _reverse_project(tmp_path)
    (root / "src" / "pkg" / "sub" / "deep2.py").write_text("VALUE = 1\n")
    _write_test(root, "test_dotted.py", "import pkg.sub.deep2")
    hints = build_test_hints([root / "src" / "pkg" / "__init__.py"], root)
    assert "tests/unit/test_dotted.py" in hints["src/pkg/__init__.py"]


def test_reverse_scan_skips_vendored_trees(tmp_path: Path) -> None:
    """A non-package changed file must not drag `.venv` into the AST walk.

    `_package_root` returns the file's own directory when it is not a package, so a
    root-level `noxfile.py`/`setup.py` makes the PROJECT ROOT the scan root. Measured in
    this repo before the fix: 3137 candidate `*.py`, 2609 of them under
    `.venv/site-packages`, all AST-parsed. Rejects an unfiltered `rglob`.
    """
    root = _reverse_project(tmp_path)
    venv_pkg = root / ".venv" / "lib" / "python3.12" / "site-packages" / "vendored"
    venv_pkg.mkdir(parents=True)
    (venv_pkg / "mod.py").write_text("from pkg import a\n")
    candidates = dep_map._reverse_scan_candidates(root)
    assert not any(".venv" in p.parts for p in candidates), "vendored tree was scanned"
    assert any(p.name == "b.py" for p in candidates), "real sources were excluded too"


def test_the_singular_test_root_is_accepted_too(tmp_path: Path) -> None:
    """`test/` is a real root here — `source_to_test_candidates` and `build_test_hints`
    both scan it — so a `test/conftest.py` normalizing to the bare node `test` must
    survive the same filter `tests` does. Rejects widening only the plural arm.
    """
    root = _reverse_project(tmp_path)
    (root / "test").mkdir()
    (root / "test" / "conftest.py").write_text("from pkg import a\n")
    (root / "test" / "test_solo.py").write_text("def test_x(): pass\n")
    selection = select_tests(["src/pkg/a.py"], root)
    assert selection["mode"] == "targeted", selection["reason"]
    assert "test" in selection["node_ids"]


def test_a_directory_node_subsumes_files_from_a_different_changed_file(
    tmp_path: Path,
) -> None:
    """Subsumption must hold across the AGGREGATE, not only per changed file.

    `_normalize_hints` enforces it per source; `select_tests` accumulates across sources
    and used to collapse only exact duplicates, so one file's `tests` directory node and
    another's `tests/unit/test_b.py` both reached pytest and the module was collected
    twice. Rejects an exact-match-only dedupe.
    """
    root = _reverse_project(tmp_path)
    (root / "tests" / "conftest.py").write_text("from pkg import a\n")
    selection = select_tests(["src/pkg/a.py", "src/pkg/b.py"], root)
    assert selection["node_ids"] == ["tests"], selection["node_ids"]


def test_a_first_party_build_subpackage_is_still_scanned(tmp_path: Path) -> None:
    """`src/pkg/build/` is an ordinary subpackage, not a build artefact directory.

    `build`/`dist` are excluded at the TOP LEVEL only. Rejects matching them at any
    depth, which silently dropped first-party modules from the reverse map so editing
    something they import stopped selecting their tests.
    """
    root = _reverse_project(tmp_path)
    (root / "src" / "pkg" / "build").mkdir()
    (root / "src" / "pkg" / "build" / "__init__.py").write_text("")
    (root / "src" / "pkg" / "build" / "steps.py").write_text("from pkg import a\n")
    (root / "tests" / "unit" / "test_steps.py").write_text("def test_x(): pass\n")

    # `_package_root` for a module in `src/pkg` IS `src/pkg`, so `build` sits at the top
    # level from the scan's vantage point. The exclusion must therefore be conditioned on
    # the scan root not being a package, not on the string position.
    assert any(p.name == "steps.py" for p in dep_map._reverse_scan_candidates(root / "src"))
    hints = build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert "tests/unit/test_steps.py" in hints["src/pkg/a.py"]


def test_build_at_a_non_package_scan_root_is_still_excluded(tmp_path: Path) -> None:
    """The other half: at a project root, `build/` really is artefacts.

    Rejects dropping the top-level exclusion entirely — a root-level `noxfile.py` makes
    the project root the scan root, and a `build/lib/...` tree there is a copy of the
    sources that costs a parse and matches nothing.
    """
    root = _reverse_project(tmp_path)
    (root / "noxfile.py").write_text("VALUE = 1\n")
    (root / "build" / "lib").mkdir(parents=True)
    (root / "build" / "lib" / "copy.py").write_text("from pkg import a\n")
    names = [p.name for p in dep_map._reverse_scan_candidates(root)]
    assert "noxfile.py" in names
    assert "copy.py" not in names


def test_reverse_scan_cap_announces_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Above the cap the reverse map is empty — that must not be silent.

    Every other narrowing in this module either reports a bounded node list or says FULL
    and why. An empty reverse map above the cap is indistinguishable from "this module
    has no dependents" unless it is announced, and the skill this feeds claims the
    selector "is never silent". Rejects a bare `if len(candidates) <= CAP:` with no else.
    """
    root = _reverse_project(tmp_path)
    monkeypatch.setattr(dep_map, "_REVERSE_SCAN_FILE_CAP", 1)
    monkeypatch.setattr(dep_map, "_REVERSE_CACHE", {})

    assert dep_map._reverse_dependents(root / "src" / "pkg" / "a.py", root) == []
    err = capsys.readouterr().err
    assert "[dep-map] reverse scan skipped" in err
    assert "dependents' tests are NOT included" in err


def test_asts_are_parsed_once_across_separate_build_test_hints_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache survives BETWEEN invocations, not merely within one.

    `select_tests` calls `classify_path` per file, which calls `build_test_hints`
    with a ONE-element list, then calls it again per file — 2N invocations for an
    N-file change. Rejects an invocation-scoped cache: it is discarded 2N times
    and buys nothing on the multi-file path the review auto-fix loop creates.
    """
    root = _reverse_project(tmp_path)
    real_parse = ast.parse
    calls: list[int] = [0]

    def counting_parse(*args: object, **kwargs: object) -> ast.Module:
        calls[0] += 1
        return real_parse(*args, **kwargs)  # type: ignore[call-overload, no-any-return]

    monkeypatch.setattr(ast, "parse", counting_parse)

    build_test_hints([root / "src" / "pkg" / "a.py"], root)
    first = calls[0]
    assert first > 0, "fixture parsed nothing — the test cannot discriminate"

    calls[0] = 0
    build_test_hints([root / "src" / "pkg" / "a.py"], root)
    assert calls[0] == 0, f"second invocation re-parsed {calls[0]} files (cache is per-call)"


def test_build_test_hints_maps_source_to_tests(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    changed = [root / "src" / "pkg" / "auth.py"]
    hints = build_test_hints(changed, root)
    assert "src/pkg/auth.py" in hints
    assert any("test_auth" in t for t in hints["src/pkg/auth.py"])


def test_build_test_hints_skips_non_python(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    readme = root / "README.md"
    readme.write_text("# Hello\n")
    hints = build_test_hints([readme], root)
    assert hints == {}


def test_build_test_hints_empty_input(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    hints = build_test_hints([], root)
    assert hints == {}


def test_build_test_hints_no_tests_for_file(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    orphan = root / "src" / "pkg" / "orphan.py"
    orphan.write_text("pass\n")
    hints = build_test_hints([orphan], root)
    assert "src/pkg/orphan.py" in hints
    assert hints["src/pkg/orphan.py"] == []


def test_build_test_hints_deduplicates(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    changed = [root / "src" / "pkg" / "auth.py"]
    hints = build_test_hints(changed, root)
    paths = hints.get("src/pkg/auth.py", [])
    assert len(paths) == len(set(paths))
