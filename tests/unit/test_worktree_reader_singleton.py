"""PLAN-worktree-side-defaults Phase 2 — one reader, ten shapes, no second gate.

Two independent failure modes are pinned here:

1. **Precedence.** First key present wins, newest first, and a present-but-malformed
   value terminates fail-closed instead of falling through to a stale lower rung.
   Fall-through is what would let ``enabled: "false"`` next to a stale
   ``feature_branch_workflow: true`` turn isolation *on* against the apparent opt-out.
2. **Singleton.** A second module that reads the raw keys can report a different mode
   than the one actually executing — `/hm:health` green while execution is isolated,
   or the reverse. The structural test below fails on any new direct reader.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from harness_maker import worktree
from harness_maker.worktree import resolve_worktree_enabled, worktree_enabled

_SRC = Path(worktree.__file__).parent

# ── (1) precedence over every shape that exists on disk ──────────────────────

_SHAPES: list[tuple[str, object, bool | None, int, bool]] = [
    # (label, block, expected value, expected rung, expects a diagnostic)
    ("new-true", {"enabled": True}, True, 1, False),
    ("new-false", {"enabled": False}, False, 1, False),
    ("legacy-fbw-true", {"feature_branch_workflow": True}, True, 2, False),
    ("legacy-fbw-false", {"feature_branch_workflow": False}, False, 2, False),
    ("legacy-scope-execute", {"scope": ["execute", "plan"]}, True, 3, False),
    ("legacy-scope-empty", {"scope": []}, False, 3, False),
    ("legacy-scope-plan-only", {"scope": ["plan"]}, False, 3, False),
    ("empty", {}, None, 0, False),
    ("missing-block", None, None, 0, False),
    # A PRESENT but malformed block is an opt-out, not an absence — rung 1 so the
    # migration's absent-key enablement probe cannot write `true` over it.
    ("malformed-block-bool", False, False, 1, True),
    ("malformed-block-str", "off", False, 1, True),
    ("malformed-enabled-string", {"enabled": "false"}, False, 1, True),
    ("malformed-enabled-int", {"enabled": 1}, False, 1, True),
    ("malformed-fbw-string", {"feature_branch_workflow": "true"}, False, 2, True),
    ("malformed-scope-string", {"scope": "execute"}, False, 3, True),
    (
        "disagreeing-mixed",
        {"enabled": False, "feature_branch_workflow": True},
        False,
        1,
        True,
    ),
    (
        "disagreeing-scope",
        {"enabled": True, "scope": []},
        True,
        1,
        True,
    ),
]


@pytest.mark.parametrize(
    ("label", "block", "expected", "rung", "diag"),
    _SHAPES,
    ids=[s[0] for s in _SHAPES],
)
def test_resolution_shape(
    label: str, block: object, expected: bool | None, rung: int, diag: bool
) -> None:
    res = resolve_worktree_enabled(block)
    assert res.value is expected, label
    assert res.rung == rung, label
    assert (res.diagnostic is not None) is diag, (label, res.diagnostic)


def test_malformed_never_consults_a_stale_lower_rung() -> None:
    """The rule that makes rule 1 load-bearing, asserted on its own.

    `enabled: "false"` is truthy to `bool(...)`. If a malformed value were treated
    as "key missing", the stale `feature_branch_workflow: true` below it would turn
    isolation ON — the opposite of what the file appears to say.
    """
    res = resolve_worktree_enabled({"enabled": "false", "feature_branch_workflow": True})
    assert res.value is False
    assert res.rung == 1


def test_present_scope_terminates_rather_than_falling_through() -> None:
    """`scope: []` is precisely the hand-edit a user makes trying to disable. Falling
    through to the preset default would silently flip Production back ON."""
    assert resolve_worktree_enabled({"scope": []}).value is False
    assert resolve_worktree_enabled({"scope": []}).rung == 3


def test_stage_is_honoured_only_by_the_legacy_scope_rung() -> None:
    """An un-re-rendered `scope: [execute]` harness keeps per-stage behavior; rungs 1
    and 2 are stage-blind by construction (ADR-001 retired per-stage scope)."""
    legacy = {"scope": ["execute"]}
    assert resolve_worktree_enabled(legacy, stage="execute").value is True
    assert resolve_worktree_enabled(legacy, stage="plan").value is False
    modern = {"enabled": True}
    assert resolve_worktree_enabled(modern, stage="plan").value is True


def test_absent_file_and_malformed_yaml_resolve_off_without_crashing(tmp_path: Path) -> None:
    assert worktree_enabled(tmp_path) is False
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "preset: Production\nworktree:\n  scope: [unclosed\n", encoding="utf-8"
    )
    assert worktree_enabled(tmp_path) is False


# ── (2) singleton: nothing else may read the raw keys ────────────────────────

# `scope` and `branch_prefix` are ordinary English words used all over the package
# (locate.py's plugin scope, spec_quality's scoring). Gating on them by bare string
# would be noise. `feature_branch_workflow` is project-unique, so it is the reliable
# tripwire; the retired *list* keys are covered by the receiver-aware check below.
_RETIRED_KEYS = {"feature_branch_workflow"}
_RETIRED_SUBSCRIPT_KEYS = {"feature_branch_workflow", "scope", "branch_prefix"}
# The three functions permitted to name a retired key. `source_key` is the rung↔name
# mapping itself — consumers that need to NAME the key (a /hm:health message) ask it
# rather than hardcoding, so the mapping has exactly one home.
_ALLOWED_READERS = {"resolve_worktree_enabled", "_legacy_disagreement", "source_key"}


def _string_constants(node: ast.AST) -> set[str]:
    return {
        n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


def test_only_the_resolver_reads_the_retired_keys() -> None:
    """A second direct reader is how `/hm:health` and the execution path diverge.

    Scans every function in the package for a string literal naming a retired key.
    `worktree.enabled` itself is deliberately NOT in the forbidden set — plenty of
    call sites legitimately pass `{"enabled": ...}` around; what must not recur is a
    module deciding the git model from the *retired* generations on its own.
    """
    offenders: list[str] = []
    for py in sorted(_SRC.rglob("*.py")):
        if "templates" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if fn.name in _ALLOWED_READERS:
                continue
            hits = _string_constants(fn) & _RETIRED_KEYS
            if hits:
                offenders.append(f"{py.relative_to(_SRC)}::{fn.name} -> {sorted(hits)}")
    assert not offenders, (
        "these functions name a retired worktree key directly; route them through "
        "worktree.resolve_worktree_enabled instead:\n  " + "\n  ".join(offenders)
    )


def _worktree_receiver(node: ast.expr) -> bool:
    """True when the expression being indexed plausibly IS a worktree config block."""
    if isinstance(node, ast.Name):
        return "worktree" in node.id.lower() or node.id.lower() in {"wt", "_wt", "block"}
    if isinstance(node, ast.Attribute):
        return "worktree" in node.attr.lower()
    if isinstance(node, ast.Call):
        return any(
            isinstance(a, ast.Constant) and a.value == "worktree" for a in node.args
        ) or _worktree_receiver(node.func)
    return False


def test_nothing_indexes_a_worktree_block_by_a_retired_key() -> None:
    """The receiver-aware half: `<something worktree-ish>["scope"]` or `.get("scope")`.

    This is the shape `_cli_create` had — it read the retired key off a worktree block
    to decide the git model, independently of the reader.
    """
    offenders: list[str] = []
    for py in sorted(_SRC.rglob("*.py")):
        if "templates" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if fn.name in _ALLOWED_READERS:
                continue
            for n in ast.walk(fn):
                key = None
                recv = None
                if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant):
                    key, recv = n.slice.value, n.value
                elif (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "get"
                    and n.args
                    and isinstance(n.args[0], ast.Constant)
                ):
                    key, recv = n.args[0].value, n.func.value
                if (
                    isinstance(key, str)
                    and key in _RETIRED_SUBSCRIPT_KEYS
                    and recv is not None
                    and _worktree_receiver(recv)
                ):
                    offenders.append(f"{py.relative_to(_SRC)}::{fn.name} -> {key}")
    assert not offenders, (
        "these functions read a retired key off a worktree block; route them through "
        "worktree.resolve_worktree_enabled instead:\n  " + "\n  ".join(sorted(set(offenders)))
    )


def test_the_retired_path_based_scope_reader_is_gone() -> None:
    """`_scope_includes` was a second, path-based gate on `worktree.scope`. It is what
    made `_cli_create` silently disable isolation once `scope` stopped rendering (R11).
    Its legacy semantics now live only as rung 3 of the single resolver.

    Deviation from PLAN ADR-001, which said to retain it: with rung 3 covering the
    un-re-rendered case, retaining it would have meant keeping a second reader that
    nothing calls and carving it out of the invariant above.
    """
    assert not hasattr(worktree, "_scope_includes")


def test_stage_none_asks_whether_isolation_is_live_for_any_stage() -> None:
    """The question a *guard* asks. Resolving a legacy `scope: ["plan"]` harness against
    the default `"execute"` returns False, which would let the disable guard conclude
    there is nothing to strand — and strand exactly the worktrees `/hm:plan` created."""
    plan_only = {"scope": ["plan"]}
    assert resolve_worktree_enabled(plan_only, stage="execute").value is False
    assert resolve_worktree_enabled(plan_only, stage=None).value is True
    assert resolve_worktree_enabled({"scope": []}, stage=None).value is False
    # rungs 1 and 2 are stage-blind already, so `stage=None` changes nothing there
    assert resolve_worktree_enabled({"enabled": True}, stage=None).value is True
    assert resolve_worktree_enabled({"feature_branch_workflow": False}, stage=None).value is False


def test_source_key_is_the_only_rung_to_name_mapping() -> None:
    """The allowlist above grants `source_key` the right to name retired keys, so this
    pins that it actually IS the mapping — otherwise the exemption would be a hole any
    future edit to that function could widen."""
    from harness_maker.worktree import WorktreeResolution

    assert WorktreeResolution(True, 1, None).source_key == "enabled"
    assert WorktreeResolution(True, 2, None).source_key == "feature_branch_workflow"
    assert WorktreeResolution(True, 3, None).source_key == "scope"
    assert WorktreeResolution(None, 0, None).source_key is None
