"""Pre-change instruction-set snapshot for the seven atomic commands (Phase 0.5).

**Why a character floor is not enough.** `test_command_size_budget.py`'s floor is
`measured * 0.80`. Deleting one runtime instruction from `execute.md` removes on the
order of 150 characters out of 28,000 — 0.5%, comfortably inside a 20% floor. So the
floor catches *gutting* and cannot catch *a deletion*, which is the failure PLAN
ADR-017 of the prior token-economy plan actually shipped: an "8,738-char
documentation-only trim" that removed runtime-behavioural instructions.

Phase 0.5's exit criterion is that "a deliberate deletion of a runtime instruction from
any atomic command fails it", and this file is the mechanism.

**Config axes, and why the snapshot is keyed by one of them.** A stage template does not
have *a* rendering — it has one per config that gates runtime instructions. `dev_mode` is
such an axis: `verify.md.j2:153` opens `{% if config.dev_mode == 'spec-driven' %}` around
Check 6, whose body carries two real `!` calls (`spec_need op-check`, `spec_need
waiver-check`), and `plan.md.j2` gates further arms the same way. This repo's
`.claude/harness.yaml` is `dev_mode: task-driven`, so a snapshot of that render alone
would not contain those instructions **and could never report them as removed** — while
`test_command_size_budget.py`'s fixture renders the *other* arm (`InterviewAnswers`
defaults to `DevMode.SPEC_DRIVEN`, `models.py:948`) with a 20% floor that cannot see two
deleted lines. Complementary blind spots, on the exact file Phase 1 edits.

Entries are therefore keyed `<command>@<dev_mode>`, **not** unioned. A union would be
worse than useless here: a line deleted from one arm but still present in the other
would remain in the union and read as intact.

**Axes knowingly NOT covered** — state them so the next reader does not inherit a silent
projection: `preset`, `targets`, and every feature toggle in `harness.yaml`
(`second_brain`, `second_opinion`, `delegation`, `worktree.feature_branch_workflow`).
Each can gate template blocks. They are out of scope for this PLAN because no phase in
it edits a block gated on them; a phase that does must extend `AXES` first.

**Why not `test_fused_loses_no_instruction`.** That check compares an *atomic* render
against its *fused* render. An instruction deleted from `verify.md.j2` disappears from
both sides, so the differential stays exactly the exempt autopilot block and the
assertion is green. It measures fusion loss, not edit loss.

The `headings()` / `executable_lines()` helpers are imported from
`test_command_size_budget` rather than re-declared: two definitions of "what counts as an
instruction" drifting apart would silently narrow this gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from harness_maker.hm import _DISPATCHABLE
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.io_utils import atomic_write
from harness_maker.models import DevMode, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from ._surface_baseline import (
    HARNESS_YAML,
    assert_sha_is_durable,
    head_sha,
    pinned_install_ref,
)
from .test_command_size_budget import executable_lines, headings

BASELINE_PATH = Path(__file__).resolve().parent / "instruction_baseline.json"

ATOMIC_COMMANDS = ("execute", "plan", "research", "review", "spec", "verify", "wrapup")

# The config axis this snapshot is keyed by. Adding an axis means adding its arms here
# and regenerating — see the module docstring for what is deliberately excluded.
AXES: tuple[DevMode, ...] = (DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN)

_GENERATED_BY = "tests/structural/_instruction_baseline.py"
_SCHEMA_VERSION = 2


def entry_key(command: str, dev_mode: DevMode) -> str:
    return f"{command}@{dev_mode.value}"


_HM_SHORTHAND = re.compile(r"(?<![\w./-])hm ([a-z][\w.]*)")


def canonicalize(line: str) -> str:
    """Fold the `hm <mod>` shorthand back to the long `python -m harness_maker.<mod>` form.

    `hm` dispatches through `runpy.run_module(run_name="__main__")`, so the two spellings
    are the SAME call — a rewrite from one to the other changes no instruction, only its
    length. Without this fold every rewritten `!` line would read as a removal plus an
    addition, the allowlist would fill with ~390 entries that mean nothing, and a real
    deletion hidden among them would be invisible. Folding is deliberately restricted to
    names `hm` will actually dispatch, so prose that happens to contain "hm " followed by
    a word is left alone.
    """
    return _HM_SHORTHAND.sub(
        lambda m: (
            f"python -m harness_maker.{m.group(1)}" if m.group(1) in _DISPATCHABLE else m.group(0)
        ),
        line,
    )


def instruction_set(text: str) -> dict[str, list[str]]:
    return {
        "headings": sorted(canonicalize(h) for h in headings(text)),
        "executables": sorted(canonicalize(e) for e in executable_lines(text)),
    }


def _render_atomic(dev_mode: DevMode) -> dict[str, str]:
    parsed = answers_from_harness_yaml(HARNESS_YAML)
    assert parsed is not None, f"{HARNESS_YAML} did not parse into answers"
    answers = parsed.model_copy(update={"dev_mode": dev_mode})
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        with pinned_install_ref():
            render(
                synthesize(ProjectProfile(), answers),
                root / ".claude",
                freeze_time=DEFAULT_FREEZE_TIME,
            )
        return {
            p.stem: p.read_text(encoding="utf-8")
            for p in sorted((root / ".claude" / "commands" / "hm").glob("*.md"))
        }


def measure_instructions() -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for dev_mode in AXES:
        rendered = _render_atomic(dev_mode)
        missing = [c for c in ATOMIC_COMMANDS if c not in rendered]
        if missing:
            raise RuntimeError(f"{dev_mode.value} render is missing: {missing}")
        for command in ATOMIC_COMMANDS:
            out[entry_key(command, dev_mode)] = instruction_set(rendered[command])
    return out


def payload_digest(commands: dict[str, dict[str, list[str]]]) -> str:
    """Same role as its Phase 0 sibling: self-consistency against a careless hand-edit.

    Deleting a line from the committed JSON is the frictionless way to bypass the
    allowlist, and without this nothing records that it happened. It proves
    self-consistency, **not** authorship — anyone editing the file can recompute it.
    """
    canonical = json.dumps(commands, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_baseline() -> dict[str, Any]:
    commands = measure_instructions()
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_by": _GENERATED_BY,
        "render_sha": head_sha(),
        "axes": [m.value for m in AXES],
        "payload_digest": payload_digest(commands),
        "commands": commands,
    }


def load_baseline(path: Path | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((path or BASELINE_PATH).read_text(encoding="utf-8"))
    return doc


def unlisted_removals(
    frozen: dict[str, dict[str, list[str]]],
    current: dict[str, dict[str, list[str]]],
    key: str,
    kind: str,
    allowed: set[str],
) -> set[str]:
    """The gate itself, as a function.

    Extracted so the negative control can INVOKE it rather than re-implement it. A
    control that recomputes this expression inline stays green when the gate is
    mis-wired — inverted subtraction, wrong allowlist key, truncated parametrization —
    which is precisely the class of defect a control exists to catch.
    """
    return (set(frozen[key][kind]) - set(current.get(key, {}).get(kind, []))) - allowed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze the pre-change instruction sets.")
    ap.add_argument("--out", type=Path, default=BASELINE_PATH)
    args = ap.parse_args(argv)
    doc = build_baseline()
    assert_sha_is_durable(doc["render_sha"])
    atomic_write(args.out, json.dumps(doc, indent=2, sort_keys=True) + "\n")
    totals = sum(len(v["headings"]) + len(v["executables"]) for v in doc["commands"].values())
    print(f"wrote {args.out} — {len(doc['commands'])} entries, {totals} instructions")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
