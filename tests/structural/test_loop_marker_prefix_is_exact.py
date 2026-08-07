"""ADR-010 gate — no `.hm-loop-*` reader may widen to `.hm-*`.

PLAN-multisession-marker-scoping introduces a SECOND marker family in the same
directory (`.claude/.hm-task-*`). Everything that keeps the Stop hook, the queue-guard
and Layer-3 ownership out of the task family rests on one property: every `.hm-loop-*`
consumer matches the EXACT `_LOOP_MARKER_PREFIX`. A later shared-helper refactor that
globs `.hm-*` "to catch both" is the realistic way that protection is lost, and it would
fail silently — the visible symptom is that every `/hm:plan` and `/hm:execute` session
becomes unable to stop.

This scans the source rather than enumerating readers, so a reader added later is
covered without editing anything here.
"""

from __future__ import annotations

import re
from pathlib import Path

import harness_maker

SRC = Path(harness_maker.__file__).parent

#: A glob/prefix literal that would match BOTH marker families.
_TOO_BROAD = re.compile(r"""["'](?:\.claude/)?\.hm-\*["']""")

#: The two sanctioned family literals.
_SANCTIONED = {".hm-loop-", ".hm-task-"}


def test_no_source_file_globs_the_whole_hm_marker_namespace() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _TOO_BROAD.search(line):
                offenders.append(f"{path.relative_to(SRC)}:{lineno} {line.strip()}")
    assert not offenders, (
        "a `.hm-*` glob matches BOTH the loop and the task marker family; under it a task "
        "marker is read as a loop marker and every /hm: stage becomes unable to stop "
        "(ADR-010):\n  " + "\n  ".join(offenders)
    )


def test_the_two_families_have_distinct_prefixes() -> None:
    """Also pins the prefix VALUES. The literal scans above see only quoted globs, so a
    widening written as `_LOOP_MARKER_PREFIX = ".hm-"` with `glob(f"{PREFIX}*")` would slip
    past them — and that is the shared-helper refactor shape the module docstring warns
    about."""
    from harness_maker import worktree

    assert worktree._LOOP_MARKER_PREFIX == ".hm-loop-"
    assert worktree._TASK_MARKER_PREFIX == ".hm-task-"
    assert worktree._LOOP_MARKER_PREFIX in _SANCTIONED
    assert worktree._TASK_MARKER_PREFIX in _SANCTIONED
    assert worktree._LOOP_MARKER_PREFIX != worktree._TASK_MARKER_PREFIX
    assert not worktree._TASK_MARKER_PREFIX.startswith(worktree._LOOP_MARKER_PREFIX)
    assert not worktree._LOOP_MARKER_PREFIX.startswith(worktree._TASK_MARKER_PREFIX)


def test_every_loop_marker_glob_uses_the_prefix_constant() -> None:
    """A hardcoded `".hm-loop-*"` literal is how a reader drifts out of the constant."""
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if '".hm-loop-*"' in line or "'.hm-loop-*'" in line:
                # loop_marker.MARKER_GLOB is the shared definition itself.
                if path.name == "loop_marker.py":
                    continue
                offenders.append(f"{path.relative_to(SRC)}:{lineno} {line.strip()}")
    assert not offenders, (
        "glob the loop family via `_LOOP_MARKER_PREFIX` / `loop_marker.MARKER_GLOB`, not a "
        "literal — the literal is what drifts when the family changes:\n  " + "\n  ".join(offenders)
    )
