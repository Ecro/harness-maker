"""SPEC-dead-modules: modules no shipped entry point reaches are deleted, and stay deleted."""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "src" / "harness_maker"

DELETED = (
    "codex_user_config", "common_ground", "eig", "foreign_config", "high_diff",
    "inequality_gate", "lens_coverage", "mutation_receipt", "plan_rounds", "plan_verify",
    "provenance", "review_consensus", "review_run", "review_telemetry", "test_dep_map",
    "tool_cascade", "spec_inventory", "observability.coverage_classifier",
    "observability.intent_miss", "observability.spec_drift",
)  # fmt: skip

# Unreachable from the shipped roots on purpose; SPEC-dead-modules O2 gives each reason.
KEPT = (
    "permission_syntax", "release_identity", "documentation_contract", "test_runners",
    "step_sensitivity", "surface_allowance",
)  # fmt: skip

_ROOT_DIRS = (
    "src/harness_maker/templates", "hooks", "skills", "commands", "agents",
    ".claude-plugin", ".codex-plugin", "scripts",
)  # fmt: skip
_STR = re.compile(r"harness_maker\.([A-Za-z_][\w.]*)")
_HM = re.compile(r"\bhm ([a-z_][\w.]*)")


def _modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in PKG.rglob("*.py"):
        if "__pycache__" in path.parts or "templates" in path.relative_to(PKG).parts:
            continue
        parts = list(path.relative_to(PKG).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = path
    return out


def _resolve(name: str, mods: dict[str, Path]) -> str | None:
    while name:
        if name in mods:
            return name
        name = name.rpartition(".")[0]
    return None


def _refs(text: str, mods: dict[str, Path]) -> set[str]:
    found = {_resolve(m.group(1).rstrip("."), mods) for m in _STR.finditer(text)}
    found |= {_resolve(m.group(1), mods) for m in _HM.finditer(text)}
    return {f for f in found if f}


def _edges(name: str, mods: dict[str, Path]) -> set[str]:
    path = mods[name]
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("harness_maker."):
                    out.add(_resolve(alias.name.removeprefix("harness_maker."), mods) or "")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".") if package else []
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                module = ".".join(base + ([node.module] if node.module else []))
            elif node.module and node.module.split(".")[0] == "harness_maker":
                module = node.module.removeprefix("harness_maker").lstrip(".")
            else:
                continue
            for alias in node.names:
                full = f"{module}.{alias.name}".strip(".")
                out.add(_resolve(full, mods) or _resolve(module, mods) or "")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out |= _refs(node.value, mods)
    return out - {""}


def _reached(mods: dict[str, Path]) -> set[str]:
    roots = {"cli", "hm", "__main__", ""}
    for rel in _ROOT_DIRS:
        for path in (REPO / rel).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                try:
                    roots |= _refs(path.read_text(encoding="utf-8"), mods)
                except UnicodeDecodeError:
                    continue
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen or name not in mods:
            continue
        seen.add(name)
        stack.extend(_edges(name, mods) - seen)
    return seen


@pytest.mark.parametrize("name", DELETED)
def test_ac_001_module_is_gone_and_unregistered(name: str) -> None:
    mods = _modules()
    assert name not in mods
    assert not any(m.startswith(f"{name}.") for m in mods), name
    from harness_maker import command_registry, hm

    assert name not in hm._DISPATCHABLE
    assert name not in command_registry.__dict__.get("MODULES", {})
    registry = (PKG / "command_registry.py").read_text(encoding="utf-8")
    assert f'"{name}"' not in registry, name


def test_ac_001_foreign_config_templates_are_gone() -> None:
    assert not (PKG / "templates" / "foreign-configs").exists()


@pytest.mark.parametrize("name", KEPT)
def test_ac_002_kept_module_still_imports(name: str) -> None:
    assert name in _modules()
    importlib.import_module(f"harness_maker.{name}")


def test_ac_003_the_shipped_roots_reach_everything_else() -> None:
    mods = _modules()
    reached = _reached(mods)
    packages = {n for n, p in mods.items() if p.name == "__init__.py"}
    assert set(mods) - reached - set(KEPT) - packages == set()
