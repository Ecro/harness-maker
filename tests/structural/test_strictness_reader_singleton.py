"""AC-001 (SPEC-dev-mode-removal): `spec.strictness` has exactly one reader and one writer.

Readers and writers are DISCOVERED by walking the AST of every module in the package, never
listed by hand — every hand-maintained reader list in this repository has been wrong at
least once (`failures.md` new-marker-content-field-must-update-every-reader). A second
reader does not crash; it disagrees, and `/hm:health` then reports a mode the execution
path does not take (`[wiki:architecture] single-reader-single-writer-config-axis`).

What counts — only accesses whose receiver is the `spec` block:

* a **read** is `<x>.get("strictness", ...)`, `<x>.pop("strictness", ...)` or
  `<x>["strictness"]` in a load context, where the source of `<x>` names `spec` (`spec`,
  `cfg["spec"]`, `config.spec`, ...). The key may be positional OR keyword (`get(key="…")`);
* a **write** is the same with a store context, `.setdefault`, `.pop` (it mutates), or
  `.update({...})`, or a dict display carrying the key `"strictness"` that is itself bound to
  `spec` — a `spec=` keyword, a `"spec"` key, an assignment target naming `spec`, a `|=` merge
  into one, or an argument to a call on one. Those are the ordinary dict-mutation spellings a
  future engineer reaches for, which is why they are scanned rather than listed as accepted
  gaps (review round 1, tests lens).

WHY the receiver filter: the WORD is not the config key. `strictness` is also the
`InterviewAnswers` field name, the `spec_quality` stdin/stdout JSON key, the
`spec_machine check` payload key and a render-context key. An unfiltered scan reports all of
them as readers and the test can only be satisfied by renaming unrelated vocabulary.

The owner of each occurrence is its enclosing function (``module.func`` / ``module.Class.func``)
or ``module.<module>`` for top-level code.

Known limitations, accepted: a key spelled through a variable (``KEY = "strictness";
d.get(KEY)``) evades a constant-matching scan, and so does a `spec` block rebound to a name
that does not mention it (``s = cfg["spec"]; s.get("strictness")``). The package has no such
spelling, and introducing one to dodge this test is the kind of change review exists to catch.

Templates must not read the raw key at all — they receive the resolved value as the render
context variable ``strictness``. A template reading ``config.spec.strictness`` would bypass
the resolver's absent-case rule and be a second reader invisible to the Python scan.

Phase A.4 — justified pass (1 of 3 in this file):
  `test_no_template_reads_the_raw_key` passes before the implementation: no template reads
  `spec.strictness` yet because no template knows the key exists. It goes RED the moment a
  template branches on the raw key instead of the resolved context variable. RED positive
  siblings that force templates to branch on strictness at all:
  `tests/unit/test_render_strictness_surface.py::test_ac_006_warn_renders_the_checks_and_blocks_nothing`
  and `::test_ac_006_block_renders_the_spec_gate_hook`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "src" / "harness_maker"
TEMPLATES = PKG / "templates"
KEY = "strictness"


def _is_key(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == KEY


def _names_spec(node: ast.AST) -> bool:
    return "spec" in ast.unparse(node).lower()


def _dict_bound_to_spec(node: ast.Dict) -> bool:
    parent = getattr(node, "_parent", None)
    if isinstance(parent, ast.keyword):
        return parent.arg == "spec"
    if isinstance(parent, ast.Dict):
        for k, v in zip(parent.keys, parent.values, strict=True):
            if v is node:
                return isinstance(k, ast.Constant) and k.value == "spec"
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        return any(_names_spec(t) for t in targets)
    if isinstance(parent, ast.AugAssign):
        return isinstance(parent.op, ast.BitOr) and _names_spec(parent.target)
    if isinstance(parent, ast.Call):
        # `spec.update({...})` / `merge(spec, {...})` — a dict handed to a call on a spec block.
        return _names_spec(parent.func)
    return False


class _Scan(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.stack: list[str] = []
        self.reads: set[str] = set()
        self.writes: set[str] = set()

    def _owner(self) -> str:
        return ".".join([self.module, *self.stack]) if self.stack else f"{self.module}.<module>"

    def _scoped(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 — ast API name
        self._scoped(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._scoped(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._scoped(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and _names_spec(func.value):
            keyed = (node.args and _is_key(node.args[0])) or any(
                _is_key(k.value) for k in node.keywords if k.arg in {"key", "k"}
            )
            if keyed and func.attr == "get":
                self.reads.add(self._owner())
            elif keyed and func.attr == "pop":
                # pop both READS the value and REMOVES the key.
                self.reads.add(self._owner())
                self.writes.add(self._owner())
            elif (
                keyed
                and func.attr == "setdefault"
                or func.attr == "update"
                and any(
                    isinstance(a, ast.Dict) and any(k is not None and _is_key(k) for k in a.keys)
                    for a in node.args
                )
            ):
                self.writes.add(self._owner())
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if (
            isinstance(node.op, ast.BitOr)
            and _names_spec(node.target)
            and isinstance(node.value, ast.Dict)
            and any(k is not None and _is_key(k) for k in node.value.keys)
        ):
            self.writes.add(self._owner())
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if _is_key(node.slice) and _names_spec(node.value):
            if isinstance(node.ctx, ast.Store):
                self.writes.add(self._owner())
            else:
                self.reads.add(self._owner())
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        if any(k is not None and _is_key(k) for k in node.keys) and _dict_bound_to_spec(node):
            self.writes.add(self._owner())
        self.generic_visit(node)


def _discover() -> tuple[set[str], set[str]]:
    reads: set[str] = set()
    writes: set[str] = set()
    for path in sorted(PKG.rglob("*.py")):
        if TEMPLATES in path.parents:
            continue
        rel = path.relative_to(PKG.parent).with_suffix("")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child._parent = parent  # type: ignore[attr-defined]
        scan = _Scan(".".join(rel.parts))
        scan.visit(tree)
        reads |= scan.reads
        writes |= scan.writes
    return reads, writes


def test_exactly_one_strictness_reader() -> None:
    from harness_maker.strictness import STRICTNESS_EXEMPT

    reads, _ = _discover()
    # The exemption must name something real that reads the key — a stale entry would let the
    # fail-closed oracle quietly start deriving from the preset without this test noticing.
    assert reads >= STRICTNESS_EXEMPT, f"exempt entry reads nothing: {STRICTNESS_EXEMPT - reads}"
    assert reads - STRICTNESS_EXEMPT == {"harness_maker.strictness.resolve_strictness"}, (
        f"strictness readers other than the resolver: {sorted(reads - STRICTNESS_EXEMPT)}"
    )


def test_exactly_one_strictness_writer() -> None:
    _, writes = _discover()
    assert writes == {"harness_maker.strictness.write_strictness"}, (
        f"strictness writers other than write_strictness: {sorted(writes)}"
    )


_JINJA_EXPR = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)


def test_no_template_reads_the_raw_key() -> None:
    """Only Jinja expressions are scanned — prose that NAMES `spec.strictness` for the user
    (`/hm:configure` lists it as an editable key) is documentation, not a read."""
    raw = re.compile(
        r"spec\s*(\.\s*strictness|\[\s*['\"]strictness['\"]|\.get\(\s*['\"]strictness)"
    )
    offenders = sorted(
        str(p.relative_to(TEMPLATES))
        for p in TEMPLATES.rglob("*.j2")
        if any(raw.search(e) for e in _JINJA_EXPR.findall(p.read_text(encoding="utf-8")))
    )
    assert offenders == [], f"templates reading spec.strictness directly: {offenders}"
