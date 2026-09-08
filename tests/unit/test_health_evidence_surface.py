"""Phase 2 of PLAN-token-efficiency-autopilot-ux-speed — AC-003, AC-004, AC-012.

Three ACs, three oracle kinds:

* **AC-003** is `parametric`. The `golden_table` in the machine SPEC is the SSOT and is LOADED
  here, never inlined — inlining it re-creates the drift the mechanism exists to remove.
* **AC-004** is `property`. The relation is metamorphic (absence must be distinguishable from
  health), so it cannot be satisfied by reading any reader's implementation. The reader set is
  ENUMERATED with a positive control, because no import edge exists — see the SPEC's AC-004 note.
* **AC-012** is `golden` on a condition name, with the precondition constructed rather than
  observed.

**Gate history.** A.5 ran its full 2-round budget and both rounds returned FAIL; the phase exited
on an application of the reviewer's own named forms rather than a third round. Round 1's three
findings and round 2's three are all closed here, and two of them were defects in the *repairs*:

* Round 1: the AC-003 verdict collapse never read `applicable` on the `degraded` rows, so
  `applicable = (entry_count > 0)` passed the whole golden table; the enumeration control keyed on
  one parameter name and was therefore blind to the family's reference reader (the `report` verb
  inside `main(argv)`); the property ranged over 2 of ≥3 readers.
* Round 2, on the round-1 repairs: the added `report` arm read `.err` for empty and `.out` for
  healthy, making its inequality unfalsifiable **and** discarding the two streams where AC-004's
  failures actually appear; `_CLI_VERBS` reconciled prose in the promoting direction only, so a
  verdict verb mislabelled `passthrough` would sit outside the property; and `targets` **omitted**
  — the production call path — was unpinned once the four explicit combinations were pinned.

**Three tests here pass by design rather than by implementation**, and each is a control:

1. `test_the_enumeration_control_actually_fires` — a **positive** meta-test, one stub per discovery
   arm. Round 1's single-arm version was built to that arm's own shape, which is exactly why it
   could not expose the blind spot A.5 found.
2. `test_the_cli_verb_classification_is_reconciled_in_both_directions` — kinds are a typed literal,
   and a `passthrough` verb must NAME a target that is in `_VERDICT_READERS`. Prefix-matched prose
   was the escape hatch: the cheapest green on a red scan is any reason string.
3. `test_ac_004_the_reader_enumeration_is_complete` is a FORWARD control, vacuous only in the sense
   that nothing is unclassified right now. It was **not** vacuous when the predicate was widened:
   the two-arm version immediately found `autopilot_ledger:smoke` unclassified, and it also
   surfaced that `rollup` the verb and `rollup` the function share a name, so a flat lookup had
   been "classifying" the verb by coincidence.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import pytest

from harness_maker import autopilot_ledger, command_registry, readiness, verifier_discrimination
from harness_maker.spec_machine import load_golden_table

_REPO_ROOT = Path(__file__).parents[2]
_MACHINE_SPEC = _REPO_ROOT / "specs" / "SPEC-token-efficiency-autopilot-ux-speed.machine.yaml"

# -- AC-003 ------------------------------------------------------------------------------
_AC003_ROWS = load_golden_table(_MACHINE_SPEC, "AC-003")


def test_ac_003_the_rendered_health_passes_targets_to_the_smoke_verb() -> None:
    """The applicability rule must reach production, not just this file (review finding P1-3).

    `smoke_check(targets=None)` means "unknown", which stays applicable — the backward-compatible
    default. So a rendered `/hm:health` that omits `--targets` leaves the cursor-only false alarm
    exactly where it was while every arm below passes. Asserted on the TEMPLATE and on the CLI
    parser together: either half alone is satisfiable without the other.
    """
    template = (
        Path(__file__).parents[2]
        / "src"
        / "harness_maker"
        / "templates"
        / "commands"
        / "hm"
        / "health.md.j2"
    ).read_text(encoding="utf-8")

    smoke_lines = [ln for ln in template.splitlines() if "autopilot_ledger smoke" in ln]
    assert smoke_lines, "the rendered health no longer invokes the smoke verb at all"
    for line in smoke_lines:
        assert "--targets" in line, f"the smoke invocation omits --targets: {line.strip()!r}"
        assert "config.targets" in line, (
            f"--targets is passed a literal rather than the harness's own targets: {line.strip()!r}"
        )

    assert "--targets" in _smoke_verb_flags(), (
        "the CLI has no --targets flag, so the rendered invocation would fail to parse"
    )


def _smoke_verb_flags() -> set[str]:
    """Every option string the `smoke` subparser accepts, read from the module's own parser."""
    import re

    source = (
        Path(__file__).parents[2] / "src" / "harness_maker" / "autopilot_ledger.py"
    ).read_text(encoding="utf-8")
    block = source.split('sub.add_parser("smoke"', 1)[1].split("add_parser(", 1)[0]
    return set(re.findall(r'add_argument\("(--[a-z-]+)"', block))


@pytest.mark.parametrize(
    "row",
    _AC003_ROWS,
    ids=[",".join(r.input["targets"]) for r in _AC003_ROWS],
)
def test_ac_003_smoke_is_not_applicable_when_the_runtime_cannot_advance(
    row: Any, tmp_path: Path
) -> None:
    """Only a runtime that CAN auto-advance may be called degraded.

    Every row is an armed level with zero ledger entries — the one input that makes
    `smoke_check` report degradation today. The variable is `targets`. A harness whose targets
    omit `claude-code` cannot auto-advance at all (that needs Claude Code's `Skill` tool), so
    reporting "configured yet never fired" there is a permanent false alarm, and a permanent
    false alarm trains the reader to ignore the one real degradation signal.
    """
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)

    result = autopilot_ledger.smoke_check(
        tmp_path,
        yaml_level="auto_safe",
        observability_dir=obs,
        targets=row.input["targets"],
    )

    verdict = (
        "degraded"
        if result["degraded"]
        else ("not-applicable" if not result["applicable"] else "ok")
    )
    assert verdict == row.expected
    # `applicable` asserted DIRECTLY, not through the collapse above. The conditional
    # short-circuits on `degraded`, so on the two `degraded` rows it never reads `applicable` —
    # which means `applicable = (entry_count > 0)`, sourced from the ledger instead of from
    # `targets`, satisfies the whole table and the counterexample below. Every fixture here has
    # an empty ledger, so this line is what forces True on those rows.
    assert result["applicable"] is (row.expected != "not-applicable")


def test_ac_003_a_claude_code_harness_with_entries_is_neither(tmp_path: Path) -> None:
    """Counterexample, so the table above is a claim about `targets` and not about the fixture.

    Same targets as the first row; the only change is that the ledger has an entry. If this also
    reported `degraded`, the table would be satisfied by a function that ignores the ledger.
    """
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / "auto-advance.jsonl").write_text(
        json.dumps({"event": "advance_authorized", "to": "spec", "ts": "2026-09-08T00:00:00+00:00"})
        + "\n",
        encoding="utf-8",
    )

    result = autopilot_ledger.smoke_check(
        tmp_path, yaml_level="auto_safe", observability_dir=obs, targets=["claude-code"]
    )

    assert result["degraded"] is False
    assert result["applicable"] is True

    # `targets` OMITTED — the production call path, and the one input the golden table cannot
    # express, because every row carries a `targets` list by construction. SPEC risk R4 promises a
    # harness that includes `claude-code` keeps today's behaviour exactly; a harness whose
    # `harness.yaml` carries no `targets` key at all is what "today" actually looks like, and an
    # implementation returning `applicable=False` there satisfies every other assertion in this
    # file while dropping the one real degradation signal.
    empty_obs = tmp_path / "fresh" / ".claude" / "observability"
    empty_obs.mkdir(parents=True)

    defaulted = autopilot_ledger.smoke_check(
        tmp_path / "fresh", yaml_level="auto_safe", observability_dir=empty_obs
    )

    assert defaulted["applicable"] is True
    assert defaulted["degraded"] is True


def test_ac_003_a_non_claude_harness_with_entries_is_still_not_applicable(tmp_path: Path) -> None:
    """The cross case the golden table cannot express: non-advancing targets AND a non-empty ledger.

    The table varies `targets` at a fixed empty ledger; the counterexample above varies the ledger
    at fixed `claude-code` targets. Neither pins the corner where both move, which is exactly where
    an `applicable = (entry_count > 0)` implementation would answer True for a runtime that
    provably cannot auto-advance.
    """
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / "auto-advance.jsonl").write_text(
        json.dumps({"event": "advance_authorized", "to": "spec", "ts": "2026-09-08T00:00:00+00:00"})
        + "\n",
        encoding="utf-8",
    )

    result = autopilot_ledger.smoke_check(
        tmp_path, yaml_level="auto_safe", observability_dir=obs, targets=["cursor"]
    )

    assert result["applicable"] is False
    assert result["degraded"] is False


# -- AC-004 ------------------------------------------------------------------------------
#: Readers whose output carries a HEALTH VERDICT — the ones the property ranges over.
#: `report` is the CLI verb in `verifier_discrimination.main`; it is the emitter of the very
#: sentence AC-004's `oracle_evidence` quotes, and A.5 caught its omission from the first draft.
_VERDICT_READERS = ("rollup", "smoke_check", "report")

#: Declared NON-verdict members of the family — descriptive aggregates or plumbing, for which
#: "passing" is not defined. Listing them is what lets the control fail on a NEW reader.
#: Only names the two discovery arms can actually produce belong here; a pre-approval for a name
#: no arm emits is inert and would silently exempt that name if it ever appeared (A.5 flagged
#: `render_rollup`, which takes no path parameter, as exactly that).
_NON_VERDICT_HELPERS = frozenset(
    {
        # descriptive aggregates — no verdict in their contract
        "agent_rounds",
        "marginal_gain",
        "rounds",  # CLI verb for agent_rounds
        "agents",  # CLI verb for the per-agent view
        # plumbing / writers
        "ledger_path",
        "append_event",
        "count_events",
        "count_entries",
        "find_unconfirmed_authorization",
        "dangling_authorizations",
        "write_rollup",
        "load_exclusions",
        "read_rows",
    }
)

_LEDGER_FAMILY: tuple[ModuleType, ...] = (autopilot_ledger, verifier_discrimination)

#: CLI verbs get their OWN classification, never the flat sets above. Reason: `rollup` the verb
#: and `rollup` the function share a name, so a flat lookup would have "classified" the verb by
#: accident — and a later rename of either would silently un-classify the other. A verb whose
#: reason begins `VERDICT` must also appear in `_VERDICT_READERS`, asserted below.
#: TYPED, not prefix-matched prose. `startswith("VERDICT")` checked the classification in one
#: direction only: a verb that IS a verdict reader but labelled `passthrough` satisfied the key
#: check and was never examined, and lowercase `"verdict — …"` demoted silently. The cheapest
#: green when the scan goes red on a new verb is any reason string, so the incentive pointed at
#: exactly that hole. A `passthrough` now NAMES its target, and the target must be in
#: `_VERDICT_READERS` — which makes the "already ranged over" claims machine-checked.
_VerbKind = Literal["VERDICT", "passthrough", "descriptive"]
_CLI_VERBS: dict[str, tuple[_VerbKind, str]] = {
    "smoke": ("passthrough", "smoke_check"),
    "rollup": ("passthrough", "rollup"),
    "report": ("VERDICT", "the family's reference absence answer"),
    "rounds": ("descriptive", "agent_rounds — no verdict in its contract"),
    "agents": ("descriptive", "per-agent view — no verdict in its contract"),
}

#: Parameter names that mark a ledger-family callable as reading a ledger. One name was not
#: enough: `read_rows` takes `path`, `main` takes `argv`, and the first draft keyed only on
#: `observability_dir`, which is why the canonical reader escaped the scan entirely.
_LEDGER_PARAMS = frozenset({"observability_dir", "ledger", "path"})


def _empty_and_healthy(tmp_path: Path) -> tuple[Path, Path]:
    empty = tmp_path / "empty" / ".claude" / "observability"
    healthy = tmp_path / "healthy" / ".claude" / "observability"
    for obs in (empty, healthy):
        obs.mkdir(parents=True)
    (healthy / "auto-advance.jsonl").write_text(
        json.dumps({"event": "advance_authorized", "to": "spec", "ts": "2026-09-08T00:00:00+00:00"})
        + "\n"
        + json.dumps({"event": "advance_entered", "to": "spec", "ts": "2026-09-08T00:01:00+00:00"})
        + "\n",
        encoding="utf-8",
    )
    (healthy / "second-opinion.jsonl").write_text(
        json.dumps({"model": "codex", "status": "invoked", "stage": "review", "finding_ref": "n/a"})
        + "\n",
        encoding="utf-8",
    )
    return empty, healthy


@pytest.mark.parametrize("reader", _VERDICT_READERS)
def test_ac_004_absence_is_never_reported_as_health(
    reader: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Metamorphic: absence must be DISTINGUISHABLE from health, and must not read as passing.

    Both arms are the same reader over two ledger states, so nothing here depends on how the
    reader is implemented — which is the point. `report(empty) == report(healthy)` is the failure
    this catches, and it is the shape a reader takes when it answers a missing file with zeros.

    **`is_passing` is two-sided and producer-bound.** A markdown report has no structural
    "passing" marker, so the earlier draft asserted a re-typed phrase — a pin that drifts on a
    reword. Instead: the notice comes from `verifier_discrimination.ABSENCE_NOTICE`, the same
    constant the producers emit, and the healthy report's generated structure must be ABSENT from
    the empty one. Present-notice alone would pass on a document carrying both the notice and a
    table of zeros, which is the inverted-content hole
    `[wiki:convention] wrong-transparency-table-worse-than-none` records.
    """
    empty_obs, healthy_obs = _empty_and_healthy(tmp_path)
    empty_root, healthy_root = tmp_path / "empty", tmp_path / "healthy"

    if reader == "report":
        # exit code is deliberately NOT part of the relation — see the corrected precondition in
        # the machine SPEC. This reader answers absence on stderr and returns 1, which is the
        # strongest compliance, and an earlier precondition wrongly excluded it for that.
        # BOTH streams for BOTH cases, then compare like against like. Reading only `.err` for
        # empty and only `.out` for healthy made the inequality unfalsifiable — no implementation
        # makes a one-line stderr notice equal a `json.dumps(indent=2)` payload — and it discarded
        # exactly the two streams where AC-004's failures appear: a zeros payload on the empty
        # run's stdout, and an absence notice on the healthy run's stderr.
        verifier_discrimination.main(
            ["report", "--ledger", str(empty_obs / "second-opinion.jsonl")]
        )
        captured = capsys.readouterr()
        empty_report = captured.out + captured.err
        verifier_discrimination.main(
            ["report", "--ledger", str(healthy_obs / "second-opinion.jsonl")]
        )
        captured = capsys.readouterr()
        healthy_report = captured.out + captured.err
        # same two-sided shape as the rollup arm — one definition of is_passing, not two dialects
        empty_passing = (
            verifier_discrimination.ABSENCE_NOTICE not in empty_report
            or "loss_rate" in empty_report
        )
    elif reader == "rollup":
        empty_report = autopilot_ledger.render_rollup(
            autopilot_ledger.rollup(empty_root, observability_dir=empty_obs)
        )
        healthy_report = autopilot_ledger.render_rollup(
            autopilot_ledger.rollup(healthy_root, observability_dir=healthy_obs)
        )
        # two-sided: the notice is present AND the healthy report's generated structure is not
        empty_passing = (
            verifier_discrimination.ABSENCE_NOTICE not in empty_report
            or "loss_rate" in empty_report
        )
    else:
        empty_payload = autopilot_ledger.smoke_check(
            empty_root, yaml_level="auto_safe", observability_dir=empty_obs, targets=["claude-code"]
        )
        healthy_payload = autopilot_ledger.smoke_check(
            healthy_root,
            yaml_level="auto_safe",
            observability_dir=healthy_obs,
            targets=["claude-code"],
        )
        empty_report, healthy_report = str(empty_payload), str(healthy_payload)
        empty_passing = not empty_payload["degraded"]

    assert empty_report != healthy_report, f"{reader}: absence and health are indistinguishable"
    assert not empty_passing, f"{reader}: an empty ledger read as passing"


def _unclassified_by_signature(modules: tuple[ModuleType, ...]) -> list[str]:
    """Arm (a) — library callables whose signature names a ledger parameter."""
    unclassified: list[str] = []
    for module in modules:
        for name, obj in vars(module).items():
            if name.startswith("_") or not callable(obj) or inspect.isclass(obj):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            try:
                params = inspect.signature(obj).parameters
            except (TypeError, ValueError):
                continue
            if not (_LEDGER_PARAMS & set(params)):
                continue
            if name not in _VERDICT_READERS and name not in _NON_VERDICT_HELPERS:
                unclassified.append(f"{module.__name__}.{name}")
    return unclassified


def _unclassified_cli_verbs(modules: tuple[ModuleType, ...]) -> list[str]:
    """Arm (b) — CLI verbs, which no signature scan can reach.

    `verifier_discrimination`'s canonical verdict reader is the `report` verb inside `main(argv)`.
    A signature scan sees only `argv`, so arm (a) is structurally blind to it — which is how the
    first draft of this control shipped green while the family's reference reader sat outside the
    property. `command_registry.MODULES` declares those verbs, so it is a real source rather than
    a second hand-list.
    """
    unclassified: list[str] = []
    for module in modules:
        short = module.__name__.rsplit(".", 1)[-1]
        spec = command_registry.MODULES.get(short)
        if spec is None:
            continue
        for verb in sorted(spec.subcommands):
            if verb not in _CLI_VERBS:
                unclassified.append(f"{short}:{verb}")
    return unclassified


def test_the_cli_verb_classification_is_reconciled_in_both_directions() -> None:
    """`_CLI_VERBS` and `_VERDICT_READERS` cannot disagree about which verbs carry a verdict.

    Both directions, because only one of them was checked before and it was the harmless one:
    a verb labelled VERDICT must be ranged over (promoting), AND a verb labelled `passthrough`
    must name a target that IS ranged over (demoting). The demoting direction is the one that
    silently shrinks the property, and it is where the cheapest-green incentive points.
    """
    kinds = {kind for kind, _ in _CLI_VERBS.values()}
    assert kinds <= {"VERDICT", "passthrough", "descriptive"}, sorted(kinds)

    verdict_verbs = {verb for verb, (kind, _) in _CLI_VERBS.items() if kind == "VERDICT"}
    assert verdict_verbs <= set(_VERDICT_READERS), sorted(verdict_verbs - set(_VERDICT_READERS))

    passthrough_targets = {target for kind, target in _CLI_VERBS.values() if kind == "passthrough"}
    assert passthrough_targets <= set(_VERDICT_READERS), sorted(
        passthrough_targets - set(_VERDICT_READERS)
    )


def test_the_enumeration_control_actually_fires() -> None:
    """Meta-arm — the control below is vacuously true today, so prove BOTH arms can fail.

    A discovery test nobody has seen fail is a hand-list with extra steps; this repo says so in
    `test_autonomy_level_literals`'s own meta-test. One stub per arm, because A.5 showed a
    single-arm meta-test built to the predicate's own shape cannot expose a blind spot in the
    predicate.
    """
    # arm (a): a library callable taking a ledger parameter
    stub = ModuleType("stub_ledger_module")

    def brand_new_reader(project_root: Path, *, ledger: Path | None = None) -> dict[str, Any]:
        return {}

    brand_new_reader.__module__ = stub.__name__
    stub.brand_new_reader = brand_new_reader  # type: ignore[attr-defined]

    assert _unclassified_by_signature((stub,)) == ["stub_ledger_module.brand_new_reader"]

    # arm (b): a declared CLI verb nobody classified
    verb_stub = ModuleType("stub_verb_module")
    original = command_registry.MODULES.get("stub_verb_module")
    command_registry.MODULES["stub_verb_module"] = command_registry.ModuleSpec(
        "manual-dispatch", frozenset({"brand_new_verb"})
    )
    try:
        assert _unclassified_cli_verbs((verb_stub,)) == ["stub_verb_module:brand_new_verb"]
    finally:
        if original is None:
            del command_registry.MODULES["stub_verb_module"]
        else:  # pragma: no cover - defensive
            command_registry.MODULES["stub_verb_module"] = original


def test_ac_004_the_reader_enumeration_is_complete() -> None:
    """Positive control — a NEW reader cannot sit silently outside the property.

    No import edge distinguishes readers from writers here (the SPEC's AC-004 note records why
    the one candidate edge is circular), so the set is enumerated. This is what keeps that
    enumeration honest, over **two** discovery arms: (a) any public callable in the ledger family
    whose signature names one of `_LEDGER_PARAMS`, and (b) any CLI verb declared in
    `command_registry.MODULES`. Every name from either arm must be classified. Adding one and
    forgetting fails HERE, and `test_the_enumeration_control_actually_fires` proves both arms
    reach that failure.
    """
    unclassified = _unclassified_by_signature(_LEDGER_FAMILY) + _unclassified_cli_verbs(
        _LEDGER_FAMILY
    )

    assert not unclassified, (
        "unclassified ledger-family readers. Library callables are matched on a signature "
        f"parameter in {sorted(_LEDGER_PARAMS)} and must be in `_VERDICT_READERS` or "
        "`_NON_VERDICT_HELPERS`; CLI verbs come from `command_registry.MODULES` and must be in "
        f"`_CLI_VERBS` (formatted `module:verb`). Classify these: {sorted(unclassified)}"
    )


# -- AC-012 ------------------------------------------------------------------------------
_VAULT_SIGNAL = "second_brain_vault_reachable"


def _signals(project_dir: Path) -> dict[str, readiness.Signal]:
    dim = readiness._dim_observability_setup(project_dir)
    return {s.id: s for s in dim.signals}


def _harness_yaml(project_dir: Path, body: str) -> None:
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(body, encoding="utf-8")


def test_ac_012_an_unreachable_vault_is_a_standing_condition(tmp_path: Path) -> None:
    """Enabled + a `vault_path` that does not resolve must surface as a named failing condition.

    Constructed, not observed: today the unreachable vault surfaces only when a `second_brain`
    subcommand runs, so a wrapup that never reaches Step 5.6 shows nothing at all.
    """
    _harness_yaml(
        tmp_path,
        "preset: Production\nsecond_brain:\n  enabled: true\n"
        f"  vault_path: {tmp_path / 'does-not-exist' / 'vault'}\n",
    )

    signal = _signals(tmp_path)[_VAULT_SIGNAL]

    assert signal.passed is False
    assert signal.not_applicable is False
    assert signal.weight == 0, "AC-012 requires the condition REPORTED, not scored"
    assert signal.action, "a failing condition with no remediation hint is a dead end"


def test_ac_012_a_disabled_second_brain_is_an_optout_not_a_failure(tmp_path: Path) -> None:
    """The opt-out arm — and the discriminator that stops the test above passing vacuously.

    `passed=True` alone cannot tell "you turned it off" from "it is healthy", which is exactly
    what `not_applicable` exists to separate. Without this arm, a signal hardcoded to fail would
    satisfy the assertion next door.
    """
    _harness_yaml(tmp_path, "preset: Production\nsecond_brain:\n  enabled: false\n")

    signal = _signals(tmp_path)[_VAULT_SIGNAL]

    assert signal.passed is True
    assert signal.not_applicable is True


def test_ac_012_an_empty_vault_path_is_unreachable_not_the_cwd(tmp_path: Path) -> None:
    """The absent-ish case: `enabled: true` with `vault_path` present but empty.

    `Path("")` is `.`, a directory that always exists, so the obvious reachability check reports an
    empty `vault_path` as reachable and the condition never fires. None of the three arms above
    passes through that input — this is the count:8 absent-case class, where a fixture covering only
    the present value means the guard never runs for the data that motivates it.
    """
    _harness_yaml(
        tmp_path, 'preset: Production\nsecond_brain:\n  enabled: true\n  vault_path: ""\n'
    )

    signal = _signals(tmp_path)[_VAULT_SIGNAL]

    assert signal.passed is False
    assert signal.not_applicable is False


def test_ac_012_a_reachable_vault_passes_without_the_optout_flag(tmp_path: Path) -> None:
    """Third arm: enabled AND reachable is a plain pass, distinct from the opt-out."""
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    _harness_yaml(
        tmp_path,
        f"preset: Production\nsecond_brain:\n  enabled: true\n  vault_path: {vault}\n",
    )

    signal = _signals(tmp_path)[_VAULT_SIGNAL]

    assert signal.passed is True
    assert signal.not_applicable is False
