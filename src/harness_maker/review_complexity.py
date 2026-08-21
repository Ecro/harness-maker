"""Size and complexity of the files a review round touched, beside the compliance verdict."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_maker.io_utils import append_atomic_line

#: Three values, three meanings. A null `complexity` alone cannot say WHY it is null, and the
#: three reasons have different remedies: a non-Python file is the accepted cost of ADR-001, an
#: unparseable one is a transient mid-refactor state, and a measured file always scores >= 1.
#: Collapsing them makes an unsupported language read as a perfectly simple one.
COMPLEXITY_STATUSES: tuple[str, ...] = ("measured", "not-python", "unparseable")

#: Nodes that add one path through a function. `BoolOp` is handled separately (it contributes
#: one per extra operand) and comprehension `ifs` likewise — a list comprehension with a filter
#: branches exactly as much as the loop-and-`if` it desugars to.
_DECISION_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.IfExp,
    ast.Assert,
    ast.match_case,
)

#: Nodes whose body is one level deeper. `Try` counts: a handler nested three deep is as hard
#: to hold in your head as a loop nested three deep.
_NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)


@dataclass(frozen=True)
class Metrics:
    """One endpoint's shape. Frozen so a recorded row cannot be edited after the fact."""

    cyclomatic: int
    max_nesting: int
    max_function_lines: int

    def as_row(self) -> dict[str, int]:
        """A mapping, never a tuple — a positional form breaks the moment a metric is added."""
        return {
            "cyclomatic": self.cyclomatic,
            "max_nesting": self.max_nesting,
            "max_function_lines": self.max_function_lines,
        }


def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTING_NODES) else depth
        deepest = max(deepest, _nesting_depth(child, child_depth))
    return deepest


def analyze(source: str) -> Metrics:
    """AST metrics for one endpoint. Raises `SyntaxError` — the caller owns that case.

    Cyclomatic complexity starts at 1, which is load-bearing rather than conventional: a
    measured file must never score 0, or a reader could not tell it apart from a file that was
    never measured and `COMPLEXITY_STATUSES` would be carrying a distinction the number itself
    quietly destroys.
    """
    tree = ast.parse(source)
    decisions = 0
    longest = 0
    for node in ast.walk(tree):
        if isinstance(node, _DECISION_NODES):
            decisions += 1
        elif isinstance(node, ast.BoolOp):
            decisions += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            decisions += len(node.ifs)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno or node.lineno
            longest = max(longest, end - node.lineno + 1)
    return Metrics(
        cyclomatic=1 + decisions,
        max_nesting=_nesting_depth(tree),
        max_function_lines=longest,
    )


def _endpoint(path: str, source: bytes | str | None) -> tuple[int | None, Metrics | None, bool]:
    """`(loc, metrics, parsed_ok)`. An absent endpoint is not a failure — it is an absence.

    Bytes are accepted because that is what a git blob is, and what "this did not decode" means
    is decided here, once, rather than at each reader. An undecodable blob is counted
    byte-accurately (as `review_churn._post_loc` does) and reported unparsed — for a `.py` file
    that is the honest answer, and anything else was going to be `not-python` regardless.
    """
    if source is None:
        return None, None, True
    if isinstance(source, bytes):
        raw = source
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Bound to `raw` rather than reusing `source`: the assignment above narrows the
            # name to `str`, so the byte-count would not type-check against it.
            return raw.count(b"\n") + (0 if raw.endswith(b"\n") or not raw else 1), None, False
    loc = len(source.splitlines())
    if not path.endswith(".py"):
        return loc, None, True
    try:
        return loc, analyze(source), True
    except (SyntaxError, RecursionError, ValueError):
        # `RecursionError` is not a `SyntaxError`: `ast.parse` and `_nesting_depth`'s own
        # recursion both hit the ceiling on deeply nested generated source, and letting it
        # escape kills the whole command in a feature that may only record. `unparseable` is
        # the bucket that already exists for "could not be analyzed"; no new value is needed.
        return loc, None, False


def complexity_row(
    path: str, pre_src: bytes | str | None, post_src: bytes | str | None
) -> dict[str, Any]:
    """One file's endpoints, with the reason any null is null."""
    pre_loc, pre_metrics, pre_ok = _endpoint(path, pre_src)
    post_loc, post_metrics, post_ok = _endpoint(path, post_src)
    if not path.endswith(".py"):
        status = "not-python"
    elif not (pre_ok and post_ok):
        status = "unparseable"
    else:
        status = "measured"
    return {
        "path": path,
        "complexity_status": status,
        "pre_loc": pre_loc,
        "post_loc": post_loc,
        "pre_complexity": pre_metrics.as_row() if pre_metrics else None,
        "post_complexity": post_metrics.as_row() if post_metrics else None,
    }


def complexity_path(root: Path) -> Path:
    """Under `.claude/observability/`, which `_HARNESS_CHURN_PREFIXES` already covers.

    A sink written anywhere else becomes user dirt: `worktree finalize` sweeps it into the
    stash and `worktree create` blocks on it.
    """
    return root / ".claude" / "observability" / "review-complexity.jsonl"


#: The size `append_atomic_line` refuses to write past. Restated rather than imported because
#: `io_utils` keeps it as a literal; if that ever becomes a named constant, import it and delete
#: this. Splitting at the same number is what keeps a large round in the series at all.
_LINE_BUDGET = 4096


def _chunks(slug: str, round_n: int, files: list[dict[str, Any]]) -> list[str]:
    """One round's files as lines that each fit the budget, all sharing slug and round.

    A round touching forty files — this task's own diff — is past 4096 bytes, and the helper
    refuses to write past it rather than emit a line the kernel may split. Splitting keeps the
    series intact: a reader groups by `(slug, round)` and unions `files`, which it has to do
    anyway. The alternative was choosing between a torn line and a lost round.
    """
    envelope = len(json.dumps({"slug": slug, "round": round_n, "files": []}, sort_keys=True)) + 2
    budget = _LINE_BUDGET - envelope
    out: list[str] = []
    batch: list[dict[str, Any]] = []
    used = 0
    for entry in files:
        size = len(json.dumps(entry, sort_keys=True)) + 1
        if batch and used + size > budget:
            out.append(json.dumps({"slug": slug, "round": round_n, "files": batch}, sort_keys=True))
            batch, used = [], 0
        batch.append(entry)
        used += size
    out.append(json.dumps({"slug": slug, "round": round_n, "files": batch}, sort_keys=True))
    return out


def record_row(root: Path, *, slug: str, round_n: int, files: list[dict[str, Any]]) -> Path:
    """Append one round's measurement. APPEND, never truncate — the series is the point.

    Writes through `io_utils.append_atomic_line`, whose docstring addresses this caller by
    name: *"a NEW caller reaching across a module boundary for a `_`-prefixed name is how a
    fifth copy starts, so new ledgers import this one."* The first draft hand-rolled the
    `os.write` loop and was exactly that fifth copy — on a **global** sink (no slug in the
    path, unlike `oscillation_path`) that CLAUDE.md's documented concurrent sessions all
    append to, with no size guard. Four reviewers said so independently.

    Unlike `record_oscillations`, an empty `files` list still writes: "this round touched
    nothing measurable" is a fact about the round, and the trend reader needs the round to
    exist in order to see that the measurement ran.
    """
    path = complexity_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    for line in _chunks(slug, round_n, files):
        append_atomic_line(path, line)
    return path
