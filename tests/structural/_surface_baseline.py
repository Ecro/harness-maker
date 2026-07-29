"""The committed shipped-surface baseline generator (PLAN-workflow-step-audit ADR-011).

Both sides of the Phase 6 comparison call **this** module, so the "pre" and "post"
numbers are the same quantity by construction rather than by assertion. Nothing here
reads a rendered `.claude/` from disk: this repo gitignores `.claude/*`, so an on-disk
render is absent in a fresh worktree and stale in the base checkout — measuring it would
have frozen a baseline against whatever happened to be lying around. The render is
produced **in-process** from the repo's committed `.claude/harness.yaml`, which makes it
fresh by construction and pins it to a commit rather than to a working directory.

**Counting rule (ADR-011, verbatim).** Count `^!`-prefixed lines in the Claude render,
`Bash(` call sites in the Codex render, and *all* `Task(` occurrences, fences included.
This is a **consistent proxy, not a semantic count** — the rule deliberately counts
examples too. There is no implementable "outside a fenced block" discriminator: real
commands live inside ```bash fences throughout the shipped templates
(`wrapup.md.j2:569`, `plan.md.j2:548`, `execute.md.j2:384`), so a fence-aware counter
would return 0 and assert nothing. A ratchet needs consistency, not precision.

**Two target variants, not three.** `.cursor/commands/` is dead code in the renderer
(`render.py:571-582` — no template feeds it), so Cursor reads the Claude render and
there are exactly two distinct rendered artifacts:

* ``claude`` — ``.claude/commands/hm/*.md`` (also what Cursor loads)
* ``codex``  — ``.agents/skills/hm-*/SKILL.md``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from harness_maker import synthesize as _synthesize_mod
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.io_utils import atomic_write
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_YAML = REPO_ROOT / ".claude" / "harness.yaml"
BASELINE_PATH = Path(__file__).resolve().parent / "surface_baseline.json"

CLAUDE_VARIANT = "claude"
CODEX_VARIANT = "codex"
BASE_BRANCH = "main"

COUNTING_RULE = (
    "ADR-011: round_trips = count of ^! lines (claude variant) or 'Bash(' call sites "
    "(codex variant), plus all 'Task(' occurrences; fenced examples included. "
    "A consistent proxy, not a semantic count."
)

_GENERATED_BY = "tests/structural/_surface_baseline.py"
_SCHEMA_VERSION = 1

# Mirrors `tests/structural/conftest.py`'s pin. Duplicated rather than imported because
# this module must run standalone (`python -m tests.structural._surface_baseline`), where
# pytest's `MonkeyPatch` is not available. Unpinned, `synthesize._compute_install_ref()`
# resolves through `__file__` and bakes this checkout's absolute path into every rendered
# command — the character counts would become a measurement of WHERE the generator ran,
# and a baseline frozen in a worktree would be wrong in CI and in base.
_MAIN_CHECKOUT_DEFAULT = "/home/noel/harness-maker"
_PORTABLE_REF = "$HOME/harness-maker"

_BANG_LINE = re.compile(r"^\s*!", re.M)


@contextmanager
def pinned_install_ref() -> Iterator[None]:
    import os

    original_root = _synthesize_mod._HARNESS_MAKER_PKG_ROOT
    original_compute = _synthesize_mod._compute_install_ref
    _synthesize_mod._HARNESS_MAKER_PKG_ROOT = os.environ.get(
        "HM_MAIN_CHECKOUT_PATH", _MAIN_CHECKOUT_DEFAULT
    )
    _synthesize_mod._compute_install_ref = lambda: _PORTABLE_REF
    try:
        yield
    finally:
        _synthesize_mod._HARNESS_MAKER_PKG_ROOT = original_root
        _synthesize_mod._compute_install_ref = original_compute


def render_surface() -> dict[str, dict[str, str]]:
    """Render this repo's harness in-process and return the two variants' command bodies."""
    if not HARNESS_YAML.exists():
        raise FileNotFoundError(
            f"cannot measure the shipped surface: {HARNESS_YAML} is missing. "
            "An absent config means the measurement cannot be made, which is not the "
            "same as an empty measurement."
        )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pinned_install_ref():
            render(
                synthesize(ProjectProfile(), answers_from_harness_yaml(HARNESS_YAML)),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        claude = {
            p.stem: p.read_text(encoding="utf-8")
            for p in sorted((root / ".claude" / "commands" / "hm").glob("*.md"))
        }
        codex_dir = root / ".agents" / "skills"
        codex = {
            p.parent.name: p.read_text(encoding="utf-8")
            for p in sorted(codex_dir.glob("hm-*/SKILL.md"))
        }
    if not claude:
        raise RuntimeError("render produced no Claude commands — refusing to freeze zeros")
    return {CLAUDE_VARIANT: claude, CODEX_VARIANT: codex}


def count_round_trips(text: str, variant: str) -> int:
    """ADR-011's counting rule. `variant` selects the call-site form, never the Task rule."""
    if variant == CLAUDE_VARIANT:
        calls = len(_BANG_LINE.findall(text))
    elif variant == CODEX_VARIANT:
        calls = text.count("Bash(")
    else:
        raise ValueError(f"unknown target variant: {variant!r}")
    return calls + text.count("Task(")


def measure_surface() -> dict[str, dict[str, dict[str, int]]]:
    return {
        variant: {
            name: {"chars": len(text), "round_trips": count_round_trips(text, variant)}
            for name, text in commands.items()
        }
        for variant, commands in render_surface().items()
    }


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)


def head_sha() -> str:
    proc = _git("rev-parse", "HEAD")
    if proc.returncode != 0:
        raise RuntimeError(f"cannot resolve HEAD: {proc.stderr.strip()}")
    return proc.stdout.strip()


def assert_sha_is_durable(sha: str) -> None:
    """Refuse to freeze against a commit that a squash-land will delete.

    Under this repo's per-task feature-branch model `task-land` squash-lands `hm/<slug>`
    into the base and **deletes the branch**, which is never pushed. A baseline frozen
    against a task-branch commit therefore records a SHA that is reachable locally until
    gc and unreachable in CI from the first push — green here, red there, for a reason
    that has nothing to do with the measurement.

    ADR-011 forbids recomputing the baseline anyway, so the correct freeze point is a
    base-reachable commit and this is a hard refusal rather than a warning.
    """
    for base in (BASE_BRANCH, f"origin/{BASE_BRANCH}"):
        if _git("rev-parse", "--verify", "--quiet", base).returncode != 0:
            continue
        if _git("merge-base", "--is-ancestor", sha, base).returncode == 0:
            return
        raise RuntimeError(
            f"refusing to freeze the baseline at {sha[:12]}: it is not an ancestor of "
            f"{base}. Re-render and freeze from the base checkout — a task branch is "
            f"squash-landed and deleted, so this SHA would not survive."
        )
    raise RuntimeError(
        f"refusing to freeze: neither {BASE_BRANCH} nor origin/{BASE_BRANCH} resolves, "
        "so the SHA's durability cannot be established."
    )


def payload_digest(surface: dict[str, dict[str, dict[str, int]]]) -> str:
    """Binds the committed numbers to the generator that produced them.

    Set-equality on variants and command names does not diverge when someone edits
    `chars: 121782` to `chars: 99999`, so without this the claim "produced by the
    committed generator" is unfalsifiable once HEAD has moved past Phase 0 and the
    values are *expected* to differ from a live render.
    """
    canonical = json.dumps(surface, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_baseline() -> dict[str, Any]:
    surface = measure_surface()
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_by": _GENERATED_BY,
        "render_sha": head_sha(),
        "counting_rule": COUNTING_RULE,
        "payload_digest": payload_digest(surface),
        "aggregate_chars": {
            variant: sum(e["chars"] for e in cmds.values()) for variant, cmds in surface.items()
        },
        "surface": surface,
    }


def load_baseline(path: Path | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((path or BASELINE_PATH).read_text(encoding="utf-8"))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=BASELINE_PATH)
    ap.add_argument(
        "--print",
        action="store_true",
        dest="print_only",
        help="emit to stdout without writing (inspection only — never the freeze path)",
    )
    args = ap.parse_args(argv)
    doc = build_baseline()
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.print_only:
        print(text, end="")
        return 0
    assert_sha_is_durable(doc["render_sha"])
    atomic_write(args.out, text)
    print(f"wrote {args.out} ({len(doc['surface'][CLAUDE_VARIANT])} claude commands, ", end="")
    print(f"{len(doc['surface'][CODEX_VARIANT])} codex skills) at {doc['render_sha'][:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via the CLI, not imported
    raise SystemExit(main())
