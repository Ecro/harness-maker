"""Self-prune loop: check ablation candidates and turn bench rows into proposals.

When a new default model ships, a triggered session writes up to three candidates (blocks of the
rendered harness the model may no longer need), runs one `hm-variant` bench arm per candidate
against an hm baseline, and asks `decide` for a verdict. Verdicts are proposals only: nothing here
edits templates or opens a PR. Procedure: docs/evals/SELF-PRUNE.md.

    uv run python scripts/self_prune.py plan --candidates <file> --out <dir> [--render <dir>]
    uv run python scripts/self_prune.py decide --baseline <dir> --candidate <dir> [...] \\
        [--ledger docs/evals/prune-ledger.jsonl]
    uv run python scripts/self_prune.py status --model <id> [--ledger <file>]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "evals" / "prune-ledger.jsonl"
MAX_CANDIDATES = 3
JUDGE_DROP_MAX = 0.3  # under the 3-sample band 2/3 / sqrt(3) ~ 0.38
MIN_SAVING = 0.03
GUARD_TIER = 2  # tier 1 is saturated (plain 15/15), so it cannot fail the way a cut would
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _bench() -> ModuleType:
    """The bench module, reusing an already-loaded copy (dataclasses resolve by module name)."""
    loaded = sys.modules.get("bench_light_lane")
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(
        "bench_light_lane", Path(__file__).with_name("bench_light_lane.py")
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class Protected:
    path: str
    heading: str
    guard: str


_SPEC = ".claude/commands/hm/spec.md"
_EXECUTE = ".claude/commands/hm/execute.md"
_WRAPUP = ".claude/commands/hm/wrapup.md"

#: The DRI's non-negotiables (hm product principle, 2026-10-15) by the rendered section that
#: carries each. AC-003's test checks every heading against a fresh render, so a renamed template
#: heading fails a test instead of silently unprotecting its section. The worktree sections render
#: only with `worktree.enabled` (Production), so the bench's Side render never holds them.
PROTECTED: tuple[Protected, ...] = (
    Protected(_SPEC, "## Task worktree", "per_task_worktree"),
    Protected(_EXECUTE, "## Task worktree", "per_task_worktree"),
    Protected(_WRAPUP, "## Task worktree", "per_task_worktree"),
    Protected(_EXECUTE, "### Phase A", "tdd_red_gate"),
    Protected(_SPEC, "## Step 3", "sdd"),
    Protected(_SPEC, "## Step 3.5", "sdd"),
    Protected(_SPEC, "## Step 4", "sdd"),
    Protected(_EXECUTE, "## Step 0", "sdd"),
    Protected(_SPEC, "## Step 2", "human_approval"),
    Protected(_SPEC, "## Step 5", "human_approval"),
    Protected(_WRAPUP, "## Step 8", "human_approval"),
    Protected(_EXECUTE, "### Phase C", "irr_lock"),
    Protected(_WRAPUP, "## Steps 6", "understanding_delta"),
)


def _enclosing(marks: list[tuple[int, int]], line_no: int) -> list[int]:
    """Heading lines of every section that contains `line_no`: the nearest heading and its
    ancestors (each earlier heading of a strictly lower level)."""
    chain: list[int] = []
    level = 7
    for i, lv in reversed(marks):
        if i <= line_no and lv < level:
            chain.append(i)
            level = lv
    return chain


def _touched(text: str, edit: dict[str, Any]) -> list[int]:
    """Heading lines whose sections an edit changes, in the text it applies to."""
    bench = _bench()
    lines = text.splitlines()
    marks = bench.headings(lines)
    if "drop_heading" in edit:
        start, end = bench.section_span(lines, str(edit["drop_heading"]))
    elif isinstance(edit.get("old"), str) and edit["old"] and edit["old"] in text:
        at = text.index(edit["old"])
        start = text[:at].count("\n")
        end = start + edit["old"].rstrip("\n").count("\n") + 1
    else:
        return []
    inside = [i for i, _lv in marks if start <= i < end]
    return sorted(set(inside) | set(_enclosing(marks, start)))


def _adds_structure(edit: dict[str, Any]) -> bool:
    """A `new` that opens a fence or a heading would move section boundaries for the edits after
    it (a fence hides every later heading), so protection could no longer see them."""
    bench = _bench()
    new = edit.get("new")
    lines = new.splitlines() if isinstance(new, str) else []
    return any(bench._HEADING.match(ln) or bench._FENCE.match(ln) for ln in lines)


def protected_hits(root: Path, variant: dict[str, Any]) -> list[tuple[dict[str, Any], Protected]]:
    """Every edit that touches a protected section, checked edit by edit against the text the
    edits before it leave (as `apply_variant` applies them): a span or replaced text that holds a
    protected heading or sits anywhere inside a protected section."""
    bench = _bench()
    texts: dict[str, str] = {}
    hits: list[tuple[dict[str, Any], Protected]] = []
    for edit in variant.get("edits") or []:
        try:
            rel = bench.edit_rel(edit)
        except bench.VariantError:
            continue
        if rel not in texts:
            path = root / rel
            if not path.is_file():
                continue
            texts[rel] = path.read_text(encoding="utf-8")
        text = texts[rel]
        try:
            touched = _touched(text, edit)
            texts[rel] = bench.apply_edit(text, edit)
        except bench.VariantError:
            break  # apply_variant reports it; later edits would run on text that never exists
        lines = text.splitlines()
        hits += [
            (edit, p) for p in PROTECTED
            if p.path == rel and any(bench.heading_matches(lines[i], p.heading) for i in touched)
        ]  # fmt: skip
    return hits


def candidate_problems(render: Path, candidates: Any) -> list[str]:
    """What stops the candidates file from running; empty when every candidate is runnable."""
    bench = _bench()
    if not isinstance(candidates, list):
        return ["the file needs a `candidates` list"]
    problems: list[str] = []
    if len(candidates) > MAX_CANDIDATES:
        problems.append(f"{len(candidates)} candidates; at most {MAX_CANDIDATES} per run")
    seen: set[str] = set()
    for n, cand in enumerate(candidates, 1):
        cid = cand.get("id") if isinstance(cand, dict) else None
        name = cid if isinstance(cid, str) else f"#{n}"
        if not isinstance(cid, str) or not _ID.match(cid):
            problems.append(f"{name}: id must be lowercase letters, digits and dashes")
            continue
        if cid in seen:
            problems.append(f"{name}: duplicate id")
        seen.add(cid)
        detectable = cand.get("detectable_by")
        if not isinstance(detectable, list) or not all(isinstance(d, str) for d in detectable):
            problems.append(f"{name}: detectable_by must be a list (empty = no cell can fail it)")
        for edit in cand.get("edits") or []:
            if isinstance(edit, dict) and _adds_structure(edit):
                problems.append(f"{name}: edit {edit} adds a heading or code fence line")
        for edit, guard in protected_hits(render, cand):
            problems.append(
                f"{name}: edit {edit} touches protected {guard.guard} ({guard.heading})"
            )
        with tempfile.TemporaryDirectory(prefix="hm-prune-") as scratch:
            copy = Path(scratch) / "render"
            shutil.copytree(render, copy, symlinks=True)
            try:
                bench.apply_variant(copy, cand)
            except bench.VariantError as exc:
                problems.append(f"{name}: {exc}")
    return problems


def _cmd_plan(args: argparse.Namespace) -> int:
    bench = _bench()
    try:
        data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"refusing {args.candidates}: {exc}", file=sys.stderr)
        return 2
    candidates = data.get("candidates") if isinstance(data, dict) else None
    with tempfile.TemporaryDirectory(prefix="hm-prune-render-") as scratch:
        render = Path(args.render) if args.render else Path(scratch) / "hm"
        if not args.render:
            bench.build_template(render, "hm")
        problems = candidate_problems(render, candidates)
    for problem in problems:
        print(f"refusing: {problem}", file=sys.stderr)
    if problems:
        return 2
    out = Path(args.out)
    for cand in candidates or []:
        bench.atomic_write(out / f"{cand['id']}.json", json.dumps(cand, indent=2) + "\n")
    print(f"plan: {len(candidates or [])} variant file(s) in {out}")
    return 0


# --- decide -----------------------------------------------------------------------------------

#: What two dirs must share to be compared. The variant moves runner_hash on purpose, so the row
#: settings it would have covered are compared one by one where rows carry them.
_SAME = ("model", "harness_sha", "bench_hash", "judge_model", "max_budget_usd")


def _kept(rows: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    bench = _bench()
    return [
        r for r in rows
        if r.get("arm") == arm and bench.tier_of(r) == GUARD_TIER
        and r.get("status") not in bench.UNUSABLE
    ]  # fmt: skip


def cells(rows: list[dict[str, Any]], arm: str) -> set[tuple[str, int]]:
    """(task, rep) pairs an arm ran on the guard tier: counts compare only over equal sets."""
    return {(str(r.get("task")), int(r.get("rep") or 0)) for r in _kept(rows, arm)}


def metrics(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    """Guard-tier numbers for one arm: solved, trap catches, mean judge overall, mean cost,
    stalls."""
    bench = _bench()
    kept = _kept(rows, arm)
    judges = [v for r in kept if (v := bench._signal("judge_overall", r)) is not None]
    costs = [float(r["cost_usd"]) for r in kept if isinstance(r.get("cost_usd"), int | float)]
    caught = [r for r in kept if isinstance(r.get("trap"), dict) and r["trap"].get("caught")]
    return {
        "runs": len(kept),
        "solved": sum(1 for r in kept if bench.outcome_of(r) == "solved"),
        "trap": len(caught),
        "judge": sum(judges) / len(judges) if judges else None,
        "cost": sum(costs) / len(costs) if costs else None,
        "stalls": sum(1 for r in kept if bench.outcome_of(r) == "stalled"),
    }


def verdict(
    base: dict[str, Any], cand: dict[str, Any], *, detectable: bool
) -> tuple[str, list[str]]:
    """adopt / reject / hold by the SPEC's guard rule, with the reasons for anything but adopt."""
    rejects = []
    if cand["solved"] < base["solved"]:
        rejects.append(f"solved {base['solved']} -> {cand['solved']}")
    if cand["trap"] < base["trap"]:
        rejects.append(f"trap catches {base['trap']} -> {cand['trap']}")
    if rejects:
        return "reject", rejects
    holds = []
    if base["judge"] is None or cand["judge"] is None:
        holds.append("judge score missing")
    elif base["judge"] - cand["judge"] > JUDGE_DROP_MAX:
        holds.append(f"judge {base['judge']:.2f} -> {cand['judge']:.2f}")
    if not base["cost"] or cand["cost"] is None or 1 - cand["cost"] / base["cost"] < MIN_SAVING:
        holds.append(f"cost {base['cost']} -> {cand['cost']}: under {MIN_SAVING:.0%} saving")
    if cand["stalls"] > base["stalls"]:
        holds.append(f"stalls {base['stalls']} -> {cand['stalls']}")
    if not detectable:
        holds.append("priced, not valued: no bench cell can fail the way this block prevents")
    return ("hold", holds) if holds else ("adopt", [])


def _identity(rows: list[dict[str, Any]], where: str) -> dict[str, str]:
    bench = _bench()
    usable = [r for r in rows if r.get("status") not in bench.UNUSABLE]
    found: dict[str, str] = {}
    for name in _SAME:
        values = {str(r.get(name)) for r in usable}
        if len(values) != 1:
            raise ValueError(f"{where}: {name} is {sorted(values) or 'absent'}, needs one value")
        found[name] = values.pop()
    return found


def _ask(cid: str, rationale: str) -> str:
    """A sentence to paste into a Maker session; its leading verb starts the full pipeline."""
    why = f" ({rationale})" if rationale else ""
    return f"`{cid}` 후보를 렌더 템플릿에서 지워줘{why}. 고쳐줘"


def _append(path: Path, rows: list[dict[str, Any]]) -> None:
    """One write on an O_APPEND fd, as the bench appends results: concurrent runs never lose
    rows, and a torn last line never swallows the first new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            data = b"\n" + data
        os.write(fd, data)
    finally:
        os.close(fd)


def _cmd_decide(args: argparse.Namespace) -> int:
    bench = _bench()
    base_rows = bench.read_rows(Path(args.baseline))
    try:
        ident = _identity(base_rows, f"baseline {args.baseline}")
        if not _kept(base_rows, "hm"):
            raise ValueError(f"baseline {args.baseline} has no usable tier-{GUARD_TIER} hm rows")
        loaded = []
        for cand_dir in map(Path, args.candidate):
            rows = bench.read_rows(cand_dir)
            if _identity(rows, f"candidate {cand_dir}") != ident:
                raise ValueError(f"candidate {cand_dir} ran on another model, harness or bench")
            variant = json.loads((cand_dir / bench.VARIANT_FILE).read_text(encoding="utf-8"))
            kept = _kept(rows, "hm-variant")
            if not kept:
                raise ValueError(f"candidate {cand_dir} has no usable tier-{GUARD_TIER} rows")
            if {r.get("variant") for r in kept} != {variant.get("id")}:
                raise ValueError(f"candidate {cand_dir}: rows were not run with its variant.json")
            loaded.append((variant, rows))
    except (OSError, ValueError, AttributeError) as exc:
        print(f"refusing to decide: {exc}", file=sys.stderr)
        return 2
    base = metrics(base_rows, "hm")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    ledger_rows = []
    lines = ["| candidate | verdict | solved | trap | judge | cost $/run | why | ask |",
             "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for variant, rows in loaded:
        cand = metrics(rows, "hm-variant")
        detectable = bool(variant.get("detectable_by"))
        result, reasons = verdict(base, cand, detectable=detectable)
        missing = cells(base_rows, "hm") ^ cells(rows, "hm-variant")
        if missing:
            result = "hold"
            first = f"inconclusive: runs differ in {len(missing)} (task, rep) cell(s)"
            reasons = [first, *(f"on unequal cells: {r}" for r in reasons)]
        ledger_rows.append({
            **ident, "candidate": variant["id"], "verdict": result, "reasons": reasons,
            "detectable_by": variant.get("detectable_by", []),
            "metrics": {"baseline": base, "candidate": cand}, "decided_at": now,
        })  # fmt: skip
        ask = _ask(variant["id"], str(variant.get("rationale", ""))) if result == "adopt" else ""
        lines.append(
            f"| {variant['id']} | {result} | {base['solved']}->{cand['solved']} | "
            f"{base['trap']}->{cand['trap']} | {base['judge']}->{cand['judge']} | "
            f"{base['cost']}->{cand['cost']} | {'; '.join(reasons) or '-'} | {ask} |"
        )
    _append(Path(args.ledger), ledger_rows)
    print("\n".join(lines))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    path = Path(args.ledger)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    models = set()
    for line in lines:
        try:
            models.add(json.loads(line).get("model"))
        except (json.JSONDecodeError, AttributeError):
            continue
    measured = args.model in models
    print("measured" if measured else "unmeasured")
    return 0 if measured else 1


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="self_prune", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan", help="validate candidates and write one variant file each")
    plan.add_argument("--candidates", required=True)
    plan.add_argument("--out", required=True)
    plan.add_argument("--render", default=None, help="a rendered hm tree (default: render one)")
    decide = sub.add_parser("decide", help="verdict per candidate dir against the baseline dir")
    decide.add_argument("--baseline", required=True)
    decide.add_argument("--candidate", action="append", required=True)
    decide.add_argument("--ledger", default=str(LEDGER))
    status = sub.add_parser("status", help="exit 0 when the ledger already holds this model")
    status.add_argument("--model", required=True)
    status.add_argument("--ledger", default=str(LEDGER))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handlers = {"plan": _cmd_plan, "decide": _cmd_decide, "status": _cmd_status}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
