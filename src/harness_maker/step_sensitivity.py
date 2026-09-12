"""Sensitivity registry: which rendered `/hm:` steps shrink as models/hosts improve, which do not.

Every `Step | Phase | Check` heading rendered by the seven stage commands over ``ARMS`` (preset ×
dev_mode) maps to one ``StepEntry`` carrying a class, an evidence grade, a source, and — for
TUNE — the trigger and command that re-measure it. Nothing at runtime reads this module: it is
consumed by ``tests/structural/test_step_sensitivity_registry.py`` (coverage, orphan, Side
consistency) and by the MATRIX/CLAUDE.md docs (``matrix_rows`` / ``unsourced_count``), so the
class is a precondition of adding a step rather than a prose argument after the fact
(PLAN-workflow-steps-vs-model-capability ADR-001/002/005/007/008/009).

Census (2026-09-12, 0.55.0, union over ``ARMS`` with ``interview._build_answers`` defaults —
``second_opinion.models=[]``, ``delegation.stages=[]``, ``reviewers.mechanical_checks=[]``):
research 6 · spec 8 · plan 17 · execute 15 · review 16 · verify 6 · wrapup 9 = **77** — these
per-stage counts EXCLUDE the `renders_when` entries (review +3, verify +1, wrapup +1 = 5), so
the raw tuple holds 82 (research Phase 0.5 was deleted by this task's Phase 3).
Headings gated on those three toggles carry ``renders_when`` and sit outside the coverage
promise until the toggle-on arms are added (ADR-007).

Classes — COMP: capability compensation, shrinks as models improve. HOST: the host harness
(Claude Code / Codex / Cursor) now does it natively. INV: invariant — state that outlives a
context window, a deterministic oracle, a human lock-in, or heterogeneity. TUNE: value flips
per model; never transferred without re-measurement (harness-bench "reversed between models").

Grades follow harness-bench: ``***`` reproduced across models/conditions, ``**`` measured once,
``*`` judgement, ``unsourced`` inherited from a neighbour with no RESEARCH row (ADR-009).
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, get_args

from harness_maker.models import DevMode, Preset

Class = Literal["COMP", "HOST", "INV", "TUNE"]
Grade = Literal["***", "**", "*", "unsourced"]
#: Deliberately ahead of current need (ADR-002): 5 knob entries use it today (`le` twice,
#: the other three once each). Named orderings read in a diff; comparator lambdas would not.
Ordering = Literal["le", "subset", "bool_off", "equal_by_design"]
SourceKind = Literal["yaml", "python"]

CLASSES: tuple[str, ...] = get_args(Class)
GRADES: tuple[str, ...] = get_args(Grade)
STAGES: tuple[str, ...] = ("research", "spec", "plan", "execute", "review", "verify", "wrapup")

#: The render matrix the coverage gate is a union over (ADR-007). Targets are deliberately
#: absent: commands render to one file family regardless of target.
ARMS: tuple[tuple[Preset, DevMode], ...] = tuple((p, d) for p in Preset for d in DevMode)

#: Ordinal token: the `Step|Phase|Check` keyword plus its identifier, up to the first space.
ORDINAL_RE = re.compile(r"^(?:Step|Phase|Check)\s+[A-Z0-9][A-Za-z0-9.]*")

_LEDGER_SIDE = "Side-preset only"
_BENCH = "harness-bench: bench run --exp review_convergence --model <name>"
#: Stage-agent gate episodes (plan-validator / test-reviewer / confirmation-pass rounds:
#: released vs bound, verdict sequences). NOT `report`, which measures second-opinion loss.
_LEDGER = (
    "harness-maker: hm verifier_discrimination agents --observability-dir .claude/observability"
)


@dataclass(frozen=True)
class StepEntry:
    stage: str
    ordinal: str
    cls: str
    grade: str
    source: str
    note: str = ""
    renders_when: str | None = None
    knob: str | None = None
    source_kind: str | None = None
    ordering: str | None = None
    remeasure_on: tuple[str, ...] = ()
    measure_cmd: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.stage, self.ordinal)


def _e(stage: str, ordinal: str, cls: str, grade: str, source: str, **kw: Any) -> StepEntry:
    return StepEntry(stage, ordinal, cls, grade, source, **kw)


def _u(stage: str, ordinal: str, cls: str, inherits: str, **kw: Any) -> StepEntry:
    """An entry with no RESEARCH row: class inherited from a neighbour, grade `unsourced`."""
    return StepEntry(
        stage, ordinal, cls, "unsourced", f"no RESEARCH row (2026-09-12); inherits {inherits}", **kw
    )


_R = "RESEARCH-workflow-steps-vs-model-capability Table 1"

REGISTRY: tuple[StepEntry, ...] = (
    # ── research ───────────────────────────────────────────────────────────
    _u("research", "Phase 0", "INV", "spec Step 2 (human interview)", note="--deep only"),
    _u(
        "research",
        "Phase 0.75",
        "COMP",
        "research Phase 0.5",
        note="lens-choice prose the model applies by judgment",
    ),
    _e("research", "Phase 1", "INV", "**", f"{_R}; cheapest stage ($44, economics)"),
    _e("research", "Phase 2", "INV", "**", _R),
    _e("research", "Phase 3", "INV", "**", f"{_R}; state that outlives the window"),
    _u("research", "Phase 4", "INV", "research Phase 3", note="write-back validation prompt"),
    # ── spec ───────────────────────────────────────────────────────────────
    _u("spec", "Step 0", "INV", "spec Step 4", note="mechanical skip heuristic"),
    _u("spec", "Step 1", "INV", "research Phase 1", note="prior-work retrieval (state)"),
    _e(
        "spec",
        "Step 2",
        "INV",
        "***",
        f"{_R}; bench: the one region the contract left undefined was the only one that moved",
    ),
    _u("spec", "Step 3", "INV", "spec Step 2", note="SPEC.md write"),
    _u("spec", "Step 3.5", "INV", "spec Step 4", note="machine.yaml write"),
    _e("spec", "Step 4", "INV", "**", f"{_R}; deterministic spec_machine check"),
    _u("spec", "Step 4.5", "INV", "spec Step 4", note="quality gate over the same payload"),
    _u("spec", "Step 5", "INV", "spec Step 3", note="status write"),
    # ── plan ───────────────────────────────────────────────────────────────
    _u("plan", "Step 0", "INV", "spec Step 0", note="mechanical skip heuristic"),
    _e("plan", "Step 1", "HOST", "*", f"{_R}; plan mode is native in all three vendors"),
    _u("plan", "Step 1.5", "INV", "plan Step 2", note="loop-mode detection (state)"),
    _u("plan", "Step 1.7", "INV", "spec Step 4", note="spec-need detection; spec-driven arm"),
    _u("plan", "Step 2", "INV", "plan Step 3", note="SPEC inheritance check (state)"),
    _e(
        "plan",
        "Step 3",
        "INV",
        "**",
        f"{_R}; harness-diet + step-audit both kept it",
        knob="interview.main_loop.max_rounds",
        source_kind="yaml",
        ordering="le",
        note="None = unlimited = +inf",
    ),
    _u("plan", "Step 3.0", "INV", "plan Step 3", note="brief lock-in confirmation (human gate)"),
    _e(
        "plan",
        "Step 4",
        "TUNE",
        "**",
        f"{_R}; verdict changes on a later pass 2/9 (22%, {_LEDGER_SIDE}, n=9); "
        "37/40 MAJOR_REVISION — discrimination unproven",
        remeasure_on=("model_release",),
        measure_cmd=_LEDGER,
    ),
    _u("plan", "Step 4.4", "INV", "plan Step 6", note="revision-size measurement (mechanical)"),
    _e(
        "plan",
        "Step 4.5",
        "COMP",
        "**",
        f"{_R}; single-pass policy (feedback_plan_validator_single_pass)",
    ),
    _u("plan", "Step 5", "INV", "spec Step 3", note="PLAN write"),
    _u("plan", "Step 6", "INV", "spec Step 4", note="write verification"),
    _u(
        "plan",
        "Step A",
        "COMP",
        "research Phase 0.5",
        note="render-format instruction for the interview UI",
    ),
    _u("plan", "Step B", "INV", "plan Step 3", note="AskUserQuestion round (human gate)"),
    _u("plan", "Step C", "INV", "plan Step 5", note="interview entry record (state)"),
    _u("plan", "Step D", "INV", "plan Step 3", note="ADR promotion (human lock-in)"),
    _e(
        "plan",
        "Step E",
        "COMP",
        "*",
        _R,
        note="5-term ceremony deleted by Phase 3; exit conditions remain",
    ),
    # ── execute ────────────────────────────────────────────────────────────
    _u("execute", "Step 1", "INV", "execute Step 2", note="PLAN load + boundaries (state)"),
    _u(
        "execute",
        "Step 1.5",
        "HOST",
        "plan Step 1",
        note="parallel split; subagent dispatch is native",
    ),
    _u("execute", "Step 2", "INV", "spec Step 1", note="SPEC/RESEARCH cache (state)"),
    _e("execute", "Step 3", "INV", "***", f"{_R}; RigorBench +17% outcome correctness"),
    _e("execute", "Phase A", "INV", "***", f"{_R}; tests are the oracle only when written first"),
    _e("execute", "Phase A.4", "INV", "**", f"{_R}; mechanical false-RED screen"),
    _e(
        "execute",
        "Phase A.5",
        "TUNE",
        "**",
        f"{_R}; FAIL 39/52 (75%, {_LEDGER_SIDE}, n=52) — no ground-truth arm",
        remeasure_on=("model_release",),
        measure_cmd=_LEDGER,
    ),
    _e("execute", "Phase B", "INV", "***", f"{_R}; deterministic RED gate"),
    _e(
        "execute",
        "Phase C.0",
        "COMP",
        "*",
        f"{_R}; declared out of scope for this task (mutation-receipt coupling)",
    ),
    _u("execute", "Phase C", "INV", "execute Phase B", note="implementation to GREEN"),
    _u("execute", "Phase D", "INV", "execute Phase B", note="deterministic targeted verification"),
    _e("execute", "Phase D.5", "COMP", "*", f"{_R}; out of scope for this task"),
    _u("execute", "Step 4", "INV", "execute Step 1", note="stage exit + boundary comparison"),
    _u("execute", "Step 4.5", "INV", "execute Step 4", note="Gate 0 receipt (state)"),
    _e(
        "execute",
        "Step 5",
        "HOST",
        "**",
        f"{_R}; Claude Code enforces worktree isolation natively; Codex/Cursor do not",
        knob="worktree.enabled",
        source_kind="yaml",
        ordering="bool_off",
        note="Production arms only",
    ),
    # ── review ─────────────────────────────────────────────────────────────
    _u("review", "Step 0", "INV", "review Step 5", note="open the run (state)"),
    _u(
        "review",
        "Step 1",
        "INV",
        "review Step 3",
        note="reviewer set selection — routing is preset-derived (conditional_router); "
        "reviewers.enabled is NOT a dispatch knob (CLAUDE.md fan-out retraction)",
    ),
    _e("review", "Step 2", "INV", "**", f"{_R}; PLAN/SPEC drift is a state check"),
    _u("review", "Step 2.5", "INV", "review Step 2", note="silent-intent-miss telemetry"),
    _e(
        "review",
        "Step 3",
        "TUNE",
        "***",
        f"{_R}; +52% unique findings on Python, 43% vs 50% recall on C firmware (bench §13)",
        knob="conditional_router.mandatory_lenses",
        source_kind="python",
        ordering="subset",
        remeasure_on=("model_release", "language_mix_change"),
        measure_cmd=_BENCH,
    ),
    _e("review", "Step 3.4", "INV", "***", f"{_R}; stable ids make consensus ledgerable"),
    _e(
        "review",
        "Step 3.5",
        "INV",
        "***",
        f"{_R}; two models once each > one model twice (bench, reproduced)",
        renders_when="second_opinion.models non-empty",
        knob="second_opinion.models",
        source_kind="yaml",
        ordering="equal_by_design",
        note="default [] on both presets by user decision",
    ),
    _e(
        "review",
        "Step 3.6",
        "INV",
        "**",
        f"{_R}; PIDA acceptance gate",
        renders_when="second_opinion.models non-empty",
    ),
    _e(
        "review",
        "Step 4",
        "INV",
        "***",
        f"{_R}; agreement is not truth — consensus must be ledgered, not trusted",
        note="K=2 is fixed in Python (conditional_router.scope_aware_consensus); "
        "reviewers.consensus is display-only and deliberately NOT a knob here",
    ),
    _e("review", "Step 4a", "INV", "***", f"{_R} (consensus)"),
    _e("review", "Step 4b", "INV", "***", f"{_R} (consensus)"),
    _e("review", "Step 4c", "INV", "***", f"{_R} (consensus)"),
    _e("review", "Step 4d", "INV", "***", f"{_R} (consensus)"),
    _e(
        "review",
        "Step 4e",
        "TUNE",
        "***",
        f"{_R}; disposition drives the auto-fix rounds, whose cap reverses per model "
        "(bench: opus-5 loop_decay −1.25 / code 1.258×; gpt-5.6 −0.25 / 0.906×)",
        knob="reviewers.max_review_rounds",
        source_kind="yaml",
        ordering="le",
        remeasure_on=("model_release",),
        measure_cmd=_BENCH,
        note="the disposition mechanism itself is invariant; the TUNE class carries the cap",
    ),
    _u("review", "Step 5", "INV", "spec Step 3", note="REVIEW write"),
    _e(
        "review",
        "Step C1",
        "TUNE",
        "*",
        f"{_R}; confirmation pass n=4 (2/2, {_LEDGER_SIDE})",
        remeasure_on=("model_release",),
        measure_cmd=_LEDGER,
    ),
    _e(
        "review",
        "Step C2",
        "TUNE",
        "*",
        f"{_R}; confirmation pass",
        remeasure_on=("model_release",),
        measure_cmd=_LEDGER,
    ),
    _e(
        "review",
        "Step C3",
        "TUNE",
        "*",
        f"{_R}; confirmation pass",
        remeasure_on=("model_release",),
        measure_cmd=_LEDGER,
    ),
    _e(
        "review",
        "Phase 0",
        "INV",
        "**",
        f"{_R}; mechanical checks, off by default",
        renders_when="reviewers.mechanical_checks non-empty",
    ),
    # ── verify ─────────────────────────────────────────────────────────────
    _e(
        "verify",
        "Check 1",
        "INV",
        "**",
        f"{_R}; drift-verdict existence (mechanical) — 1b LLM coverage deleted by Phase 4",
    ),
    _e(
        "verify",
        "Check 2",
        "INV",
        "**",
        f"{_R}; harness-diet ADR-003 kept verify as state scaffolding",
    ),
    _e("verify", "Check 3", "INV", "**", _R),
    _e("verify", "Check 4", "INV", "**", _R),
    _e("verify", "Check 5", "INV", "**", _R),
    _e("verify", "Check 6", "INV", "**", f"{_R}; spec-driven arm only"),
    _e(
        "verify",
        "Step 0.5",
        "INV",
        "**",
        f"{_R}; stage-delegate cut main-loop turns 136–329 → 38–46",
        renders_when="delegation.stages contains verify",
    ),
    # ── wrapup ─────────────────────────────────────────────────────────────
    _u("wrapup", "Step 1", "INV", "verify Check 2", note="pre-flight"),
    _u("wrapup", "Step 2", "INV", "verify Check 2", note="final verification pass"),
    _u("wrapup", "Step 3", "INV", "review Step 2", note="drift verdict check (read-only)"),
    _u("wrapup", "Step 3.5", "INV", "spec Step 3.5", note="machine SPEC write-back"),
    _u(
        "wrapup",
        "Step 3.6",
        "INV",
        "wrapup Step 3.5",
        note="oracle-waiver advisory; task-driven arm",
    ),
    _u("wrapup", "Step 4", "INV", "spec Step 5", note="PLAN status write"),
    _e(
        "wrapup",
        "Step 5",
        "INV",
        "**",
        f"{_R}; 67% of failures predate Opus 5 yet encode system invariants (harness-diet)",
    ),
    _e(
        "wrapup",
        "Step 7.7",
        "HOST",
        "**",
        f"{_R}; squash-land is host-native in Claude Code; multi-session coordination is ours",
        note="Production arms only",
    ),
    _u("wrapup", "Step 8", "INV", "plan Step B", note="push is a human gate"),
    _e(
        "wrapup",
        "Step 0.5",
        "INV",
        "**",
        f"{_R}; stage-delegate",
        renders_when="delegation.stages contains wrapup",
    ),
)


# ── extraction ────────────────────────────────────────────────────────────────


def ordinals_from_headings(headings: Iterable[str]) -> list[str]:
    """Filter the shared `headings()` output down to Step/Phase/Check ordinals (ADR-001)."""
    out: list[str] = []
    for h in headings:
        m = ORDINAL_RE.match(h.lstrip("#").strip())
        if m:
            out.append(m.group(0))
    return out


def coverage_failures(
    rendered: Mapping[str, Iterable[str]], registry: Sequence[StepEntry]
) -> list[tuple[str, str]]:
    """Rendered ordinals with no registry entry — the S2 gate names them exactly."""
    keys = {e.key for e in registry}
    return sorted((s, o) for s, ords in rendered.items() for o in ords if (s, o) not in keys)


def orphan_entries(
    rendered: Mapping[str, Iterable[str]], registry: Sequence[StepEntry]
) -> list[tuple[str, str]]:
    """Registry entries no ARMS render produces, excluding `renders_when` exemptions (ADR-007)."""
    seen = {(s, o) for s, ords in rendered.items() for o in ords}
    return sorted(e.key for e in registry if e.renders_when is None and e.key not in seen)


# ── validation ────────────────────────────────────────────────────────────────


def validate(registry: Sequence[StepEntry]) -> None:
    """Import-time contract: unique keys, known enums, TUNE re-measurement, knob ordering."""
    seen: set[tuple[str, str]] = set()
    for e in registry:
        if e.key in seen:
            raise ValueError(f"duplicate registry key {e.key}")
        seen.add(e.key)
        if e.stage not in STAGES or e.cls not in CLASSES or e.grade not in GRADES:
            raise ValueError(f"unknown stage/class/grade on {e.key}")
        if e.cls == "TUNE" and not (e.remeasure_on and e.measure_cmd):
            raise ValueError(f"TUNE entry {e.key} needs remeasure_on and measure_cmd")
        if e.measure_cmd and ":" not in e.measure_cmd.split(" ", 1)[0]:
            raise ValueError(f"measure_cmd on {e.key} must name its repo as a prefix ('<repo>: …')")
        if (e.knob is None) != (e.ordering is None) or (e.knob is None) != (e.source_kind is None):
            raise ValueError(f"knob on {e.key} needs both source_kind and ordering")
        if e.ordering is not None and e.ordering not in get_args(Ordering):
            raise ValueError(f"unknown ordering on {e.key}")


validate(REGISTRY)


def unsourced_count(registry: Sequence[StepEntry]) -> int:
    return sum(1 for e in registry if e.grade == "unsourced")


# ── Side / Production consistency (ADR-002 / ADR-008) ─────────────────────────


def knob_entries(registry: Sequence[StepEntry]) -> list[StepEntry]:
    return [e for e in registry if e.knob is not None]


def knob_value(config: Any, entry: StepEntry) -> Any:
    """Resolve a knob against a synthesized `HarnessConfig` (yaml path) or a callable of preset."""
    assert entry.knob is not None
    if entry.source_kind == "python":
        mod_name, fn_name = entry.knob.rsplit(".", 1)
        fn = getattr(importlib.import_module(f"harness_maker.{mod_name}"), fn_name)
        return tuple(fn(str(getattr(config.preset, "value", config.preset))))
    obj: Any = config
    for part in entry.knob.split("."):
        obj = obj[part] if isinstance(obj, Mapping) else getattr(obj, part)
    return obj


def _rank(v: Any) -> float:
    if v is None:
        return float("inf")
    if isinstance(v, str):
        raise ValueError(f"le-ordered knob values must be numeric or None, got {v!r}")
    if isinstance(v, bool):
        return float(int(v))
    return float(v)


def ordering_holds(ordering: str, side: Any, prod: Any) -> bool:
    if ordering == "le":
        return _rank(side) <= _rank(prod)
    if ordering == "subset":
        return set(side) <= set(prod)
    if ordering == "bool_off":
        return side is False or side == prod
    if ordering == "equal_by_design":
        return bool(side == prod)
    raise ValueError(ordering)


def side_ordering_violations(
    side_config: Any, prod_config: Any, registry: Sequence[StepEntry]
) -> list[tuple[str, Any, Any]]:
    out: list[tuple[str, Any, Any]] = []
    for e in knob_entries(registry):
        assert e.knob is not None
        assert e.ordering is not None
        s, p = knob_value(side_config, e), knob_value(prod_config, e)
        if not ordering_holds(e.ordering, s, p):
            out.append((e.knob, s, p))
    return out


# ── docs (Phase 6) ────────────────────────────────────────────────────────────

_HEADER_ROW = re.compile(r"^\|(?P<cells>.*)\|\s*$", re.M)


def has_class_column(markdown: str) -> bool:
    """A table whose header row has a `class` cell — the MATRIX column the docs test checks."""
    for m in _HEADER_ROW.finditer(markdown):
        cells = [c.strip().strip("`").lower() for c in m.group("cells").split("|")]
        if "class" in cells and not all(set(c) <= set("-: ") for c in cells):
            return True
    return False


def matrix_rows(registry: Sequence[StepEntry]) -> list[str]:
    """Generator for the MATRIX appendix so the doc cannot drift from the registry."""
    return [f"| {e.stage} | {e.ordinal} | {e.cls} | {e.grade} |" for e in registry]


__all__ = [
    "ARMS",
    "CLASSES",
    "GRADES",
    "REGISTRY",
    "STAGES",
    "StepEntry",
    "coverage_failures",
    "has_class_column",
    "knob_entries",
    "knob_value",
    "matrix_rows",
    "ordering_holds",
    "ordinals_from_headings",
    "orphan_entries",
    "side_ordering_violations",
    "unsourced_count",
    "validate",
]
