"""Phase 5 of PLAN-token-efficiency-autopilot-ux-speed — AC-007/008/009/011/015.

One defect class in five places: **shipped prose that states something the producing object
contradicts.** Measured before this file existed:

- `commands/make.md:227` discloses `autonomy.level` default `ask` — **correct**, and it is the
  green precondition AC-007 needs.
- `commands/make.md:355` calls `auto_safe` "the default a fresh install renders" — `AutonomyConfig()
  .level` is `"ask"`, and the same file contradicts itself 128 lines apart.
- `agents/_partials/step_manifest.md.j2:71` says `autopilot_persistent`'s "default is `false`" —
  it is `True`, and this line renders into **every** stage command.
- `README.md` says every `/hm:execute` runs in a *fresh* worktree — false on both arms: the
  flag-on model is a **persistent** per-task worktree, and `worktree.enabled: false` creates none.
- `docs/HOW-IT-WORKS.md` ships a `## 4. Fusion Commands` heading whose body says no fusion command
  exists, plus a TOC entry and a "4 fusion" count for an axis deleted in 0.47.0.
- the rendered `review.md` tells the model to "Start from `harness.yaml.reviewers.enabled`" while
  `lens_dispatch(preset)` never reads that list, so narrowing it changes nothing that is dispatched.

**A.5 round 1 returned FAIL with three blocking findings, all of one shape: this file's own
docstrings asserted facts about production that production contradicted** — the same defect class
the file exists to remove. Recorded because the repairs changed what the tests measure:

- I wrote that `reviewers.enabled` is `[]` on a default Production render. **False.**
  `interview()` always writes `_PROD_ENABLED_REVIEWERS`, which contains every dispatched agent;
  the `[]` came from a bare `InterviewAnswers`, which no producer emits, and it additionally
  suppresses `review.md.j2`'s `{% if enabled | length > 1 %}` section. AC-015 now renders a
  *reachable narrowed* harness instead.
- I justified an `inspect.getsource` wiring grep by claiming three fixtures were unavailable.
  `tests/unit/test_sessionstart_drift.py` already builds all three, so AC-009's observable arm
  moved there and the grep is gone.
- AC-011's three literals were a second, narrower source of truth for an invariant
  `tests/structural/test_no_fused_workflow_axis.py` already owns repo-wide; that gate's
  `_PROSE_BAN` was case- and plurality-blind. It is widened, and AC-011 defers to it.

Phase A.4 screen, measured: **12 failed, 3 passed**. The three passes are justified, not fixed
(case 2), and the justification is the measurement rather than a prediction — I expected the
inversion arm to pass vacuously on the wrong documents and it does **not**, because each wrong
document states a value that is *inside* the inversion domain, so the sweep hits it and goes red.

1. `test_ac_007_the_guard_is_green_before_the_inversion[make.md:level+persistent]` — the `make.md`
   disclosure table is the one that is already **correct**, and AC-007's `preconditions` field
   requires exactly this: "the assertion is green before the inversion". Its RED siblings are the
   other two parametrizations of the same test.
2. `test_ac_007_inverting_a_disclosed_default_fails_the_guard[make.md:level+persistent]` — the
   inversion arm over that same truthful row, where it is not vacuous: the document states the
   produced value, so every alternative must mismatch. Killer: bind `_produced` to a literal dict
   and the inverted instance stops changing what the guard compares against.
3. `test_ac_007_every_disclosure_is_value_bound` — the meta-arm closing the `all()`-over-empty
   hole: a disclosure with no produced keys would make both arms above assert nothing. It passes on
   a correctly-authored registry by construction; its killer is a future presence-only pattern,
   which is the exact shape `[wiki:convention] wrong-transparency-table-worse-than-none` records.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from harness_maker.conditional_router import lens_dispatch
from harness_maker.hooks import sessionstart_drift
from harness_maker.interview import _ALL_REVIEWERS
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import (
    AdaptiveConfig,
    AutonomyConfig,
    AutonomyLevel,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.spec_machine import GoldenRow, load_golden_table
from harness_maker.synthesize import synthesize
from harness_maker.worktree import worktree_enabled

_ROOT = Path(__file__).parents[2]
_MACHINE_SPEC = _ROOT / "specs" / "SPEC-token-efficiency-autopilot-ux-speed.machine.yaml"


def _read(relpath: str) -> str:
    return (_ROOT / relpath).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-007 — no disclosed default survives inversion of its producing object
# ---------------------------------------------------------------------------


def _produced(cfg: AutonomyConfig) -> dict[str, str]:
    """The single binding site between a disclosed default and the class that produces it.

    Kept as a function of an *instance* rather than of the class default so AC-007's
    transformation ("invert X in the class that produces it") is expressible in-process: the
    inversion arm passes a differently-constructed `AutonomyConfig`, which is the same object
    producing the default, not a stand-in for it.
    """
    return {
        "level": cfg.level,
        "persistent": "true" if cfg.autopilot_persistent else "false",
    }


#: Every value a disclosed default could be inverted to. Sourced from the producing types so a
#: new `AutonomyLevel` member widens the inversion sweep without a second hand-list.
_DOMAINS: dict[str, tuple[str, ...]] = {
    "level": tuple(AutonomyLevel.__args__),  # type: ignore[attr-defined]
    "persistent": ("true", "false"),
}


@dataclass(frozen=True)
class _Disclosure:
    """A document sentence that states a configuration default, and the keys it states."""

    doc: str
    pattern: str
    keys: tuple[str, ...]
    why: str


_DISCLOSURES: tuple[_Disclosure, ...] = (
    _Disclosure(
        doc="commands/make.md",
        pattern=(
            r"\|\s*`autonomy\.level`\s*/\s*persistence\s*\|\s*"
            r"\*\*`(?P<level>\w+)`\s*/\s*persistent\s*`(?P<persistent>\w+)`\*\*"
        ),
        keys=("level", "persistent"),
        why="the in-make disclosure table the user reads before answering the autonomy question",
    ),
    _Disclosure(
        doc="commands/make.md",
        pattern=r"`(?P<level>\w+)`\s*\(\*{0,2}the default a fresh install renders",
        keys=("level",),
        why="the interview prompt's own parenthetical, 128 lines from the table above it",
    ),
    _Disclosure(
        doc="src/harness_maker/templates/agents/_partials/step_manifest.md.j2",
        pattern=(
            r"`autonomy\.autopilot_persistent: true` to auto-arm every session; "
            r"the default is `(?P<persistent>\w+)`"
        ),
        keys=("persistent",),
        # Read from the TEMPLATE, not a render, on purpose: the line sits inside the `{% if %}`
        # gated picker block, and the claim is arm-independent, so one template read covers every
        # arm at once. The sibling AC-015 reads rendered output because ITS subject is what a
        # given harness receives. The asymmetry is deliberate (A.5 round 1, A8).
        why="renders into every stage command, so a wrong value ships seven times per harness",
    ),
)


def _guard_verdict(disclosure: _Disclosure, produced: dict[str, str]) -> bool:
    """The guard AC-007's relation is stated over: does the document state these values?

    A vanished sentence returns False rather than passing vacuously — a disclosure whose anchor
    was reworded away is exactly as unverified as one stating the wrong value. A.5 round 1 read
    this as a formatting pin that could fail a correct fix; it is **deliberate** and the answer is
    narrower than that: AC-007's subject is a *disclosure*, so deleting the sentence is not a fix,
    it is removing the transparency — the sibling failure of
    `wrong-transparency-table-worse-than-none`. The patterns were relaxed where the pin was
    incidental (bold markers, whitespace); the requirement that a disclosure exist stays.
    """
    match = re.search(disclosure.pattern, _read(disclosure.doc))
    if match is None:
        return False
    return all(match.group(key) == produced[key] for key in disclosure.keys)


def _ids(disclosures: tuple[_Disclosure, ...]) -> list[str]:
    return [f"{d.doc.rsplit('/', 1)[-1]}:{'+'.join(d.keys)}" for d in disclosures]


@pytest.mark.parametrize("disclosure", _DISCLOSURES, ids=_ids(_DISCLOSURES))
def test_ac_007_the_guard_is_green_before_the_inversion(disclosure: _Disclosure) -> None:
    """AC-007's `preconditions`: the assertion must hold against the real class default.

    This is the RED half. It fails today for two of the three disclosures, and it is what forces
    the documents to state the value the class produces rather than a value someone remembered.
    """
    produced = _produced(AutonomyConfig())

    assert _guard_verdict(disclosure, produced), (
        f"{disclosure.doc} does not state the produced default "
        f"({ {k: produced[k] for k in disclosure.keys} }) — {disclosure.why}"
    )


@pytest.mark.parametrize("disclosure", _DISCLOSURES, ids=_ids(_DISCLOSURES))
def test_ac_007_inverting_a_disclosed_default_fails_the_guard(disclosure: _Disclosure) -> None:
    """AC-007's `expected_relation`, swept over every alternative in each key's domain.

    RED for the two wrong disclosures — each states a value inside its own inversion domain, so the
    sweep reaches it and the guard returns True where it must return False. Green (and non-vacuous)
    for the truthful one; see the module docstring. The killer: replace `_produced`'s body with a
    literal dict and the inverted instance stops changing what the guard compares against.
    """
    baseline = _produced(AutonomyConfig())
    if not _guard_verdict(disclosure, baseline):
        # AC-007's `preconditions`: ["the assertion is green before the inversion"]. Unmet here,
        # so the property is not evidentially applicable — and a document stating a value INSIDE
        # its own inversion domain would fail this arm with the message "not bound to the
        # producing object", which is the wrong diagnosis: the binding is fine, the document is
        # wrong, and the green arm already reports exactly that (A.5 round 1, A4).
        pytest.skip(f"precondition unmet: {disclosure.doc} does not yet state the produced value")
    inversions = 0

    for key in disclosure.keys:
        for alternative in _DOMAINS[key]:
            if alternative == baseline[key]:
                continue
            inverted = AutonomyConfig(
                **{
                    "level": alternative if key == "level" else baseline["level"],
                    "autopilot_persistent": (
                        alternative == "true"
                        if key == "persistent"
                        else baseline["persistent"] == "true"
                    ),
                }
            )
            inversions += 1
            assert not _guard_verdict(disclosure, _produced(inverted)), (
                f"{disclosure.doc} still satisfies the guard with {key}={alternative!r} — "
                "the assertion is not bound to the producing object"
            )

    assert inversions >= 1, "this disclosure swept no inversion, so it asserted nothing"


def test_ac_007_every_disclosure_is_value_bound() -> None:
    """The meta-arm: a disclosure that captures no value would make both arms above vacuous.

    Justified pass before implementation — see the module docstring. A presence-only pattern
    (`re.search(r"autonomy|autopilot", text)`) declares no keys, so `all()` over an empty set
    returns True for every input including inverted ones. That is the documented failure this
    family exists to remove, so it is asserted rather than assumed.

    **It exercises no production object and no document, so it must not be counted toward AC-007's
    coverage** (A.5 round 1, A6). Its whole job is to keep the two arms above non-vacuous.
    """
    assert _DISCLOSURES, "the registry is empty — AC-007 would assert nothing at all"

    for disclosure in _DISCLOSURES:
        assert disclosure.keys, f"{disclosure.doc} declares no produced keys"
        group_names = set(re.compile(disclosure.pattern).groupindex)
        assert set(disclosure.keys) <= group_names, (
            f"{disclosure.doc}: keys {disclosure.keys} are not all captured by the pattern "
            f"(captures {sorted(group_names)}) — the guard cannot compare a value it never read"
        )
        for key in disclosure.keys:
            assert key in _DOMAINS, f"{key} has no inversion domain, so it is never inverted"


# ---------------------------------------------------------------------------
# AC-008 — README's worktree claim holds on both arms
# ---------------------------------------------------------------------------

_AC008_ROWS = load_golden_table(_MACHINE_SPEC, "AC-008")

#: What each arm's sentence must co-locate, in ONE line — a README that mentions "persistent" in
#: one paragraph and `hm/<slug>` in another has not made the claim, it has scattered the words.
#: `shared` is required on the flag-on arm because the lifecycle is the whole point: one worktree
#: per TASK, held across every `/hm:` stage. Without it, A.5 round 1's counterexample passes —
#: "runs in a persistent worktree on branch `hm/<slug>`, recreated on each run".
_AC008_TOKENS: dict[bool, tuple[str, ...]] = {
    True: ("persistent", "hm/<slug>", "shared"),
    False: ("worktree.enabled", "false", "no worktree"),
}

#: Tokens the GOLDEN prose itself names, per arm. Asserted against `row.expected` so the table in
#: the machine SPEC and the tuple above cannot drift apart silently: A.5 round 1 observed that
#: `row.expected` was only ever interpolated into failure messages, which made the golden
#: decorative.
_AC008_GOLDEN_TOKENS: dict[bool, tuple[str, ...]] = {
    True: ("persistent", "hm/<slug>"),
    False: ("no worktree",),
}

#: Refuted phrasings. A pattern rather than a literal tuple: renaming "fresh" to "brand-new"
#: keeps the false claim intact, which is the evasion A.5 round 1 named.
_AC008_REFUTED = re.compile(
    r"fresh (?:`?git )?worktree|brand-new worktree|new worktree (?:on|for) each"
    r"|worktree per run|recreated on each run",
    re.IGNORECASE,
)


def _write_base(tmp_path: Path, *, enabled: bool) -> Path:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        yaml.safe_dump({"worktree": {"enabled": enabled}}), encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize(
    "row", _AC008_ROWS, ids=[f"enabled={r.input['worktree_enabled']}" for r in _AC008_ROWS]
)
def test_ac_008_the_readme_worktree_claim_holds_on_both_arms(
    row: GoldenRow, tmp_path: Path
) -> None:
    """A golden prose check (`oracle_source: golden`), with its two known weaknesses closed.

    `worktree_enabled(base)` is asserted first so the arm the row names is the arm the runtime
    would actually take — A.5 round 1 correctly observed that this precondition does not by itself
    change any README verdict, so it is kept as what it is (a guard against a golden row naming an
    unreachable arm) and not advertised as the independence story.

    **Residual limitation, stated rather than papered over:** substring co-location on one line is
    a proximity heuristic. It now excludes the recreation claim explicitly and requires the
    lifecycle token, so the counterexamples raised at A.5 are dead; a sufficiently determined false
    sentence could still satisfy three tokens. That is the accepted cost of a prose oracle.
    """
    arm = bool(row.input["worktree_enabled"])
    base = _write_base(tmp_path, enabled=arm)

    assert worktree_enabled(base) is arm, (
        f"the golden row names an arm the single reader does not produce for enabled={arm}"
    )

    required = _AC008_TOKENS[arm]
    for token in _AC008_GOLDEN_TOKENS[arm]:
        assert token in row.expected, (
            f"the golden prose for enabled={arm} no longer names {token!r}, so the required-token "
            "set has drifted from the SPEC it claims to realize"
        )
        assert token in required, f"{token!r} is named by the golden but not required here"

    readme = _read("README.md")

    refuted = _AC008_REFUTED.search(readme)
    assert refuted is None, (
        f"README still claims {refuted.group(0)!r}: false on both arms — flag-on is a persistent "
        f"per-task worktree shared by every stage, flag-off creates none ({row.expected})"
    )

    covering = [line for line in readme.splitlines() if all(tok in line for tok in required)]
    assert covering, (
        f"no single README line covers the enabled={arm} arm (needs all of {required}); "
        f"the golden requires: {row.expected}"
    )


# ---------------------------------------------------------------------------
# AC-009 — the personalization advisory names the threshold that fired
# ---------------------------------------------------------------------------

_AC009_ROWS = load_golden_table(_MACHINE_SPEC, "AC-009")


@pytest.mark.parametrize(
    "row",
    _AC009_ROWS,
    ids=[f"{r.input['overrides']}ov/{r.input['days_since_audit']}d" for r in _AC009_ROWS],
)
def test_ac_009_the_advisory_names_the_threshold_that_fired(row: GoldenRow) -> None:
    """The composer's own contract. The **observable** arm is in `test_sessionstart_drift.py`.

    Two-sided: the machine reason matches the golden, AND the prose names that threshold only.
    Reason alone would pass a composer that classifies correctly and still prints the count
    threshold in every branch — the shipped defect. Prose alone would pass on an incidental digit.

    The `session` / `days` / `both` enum is not invented here: it is the golden table's own
    `expected` column (`machine.yaml`, AC-009), so the contract this phase introduces is the one
    the SPEC already specifies.

    Bounded patterns, not `str(n) in text` — see the sibling test's docstring for why the golden's
    particular numbers make plain containment sound only by accident.
    """
    config = AdaptiveConfig()
    n_overrides = int(row.input["overrides"])
    days_since = float(row.input["days_since_audit"])

    composed = sessionstart_drift.compose_audit_advisory(
        n_overrides=n_overrides, days_since=days_since, config=config
    )
    assert composed is not None, (
        f"{n_overrides} overrides / {days_since} days should trip a threshold "
        f"({config.audit_session_threshold} / {config.audit_days_threshold})"
    )
    reason, additional, system = composed

    assert reason == row.expected, (
        f"{n_overrides} overrides / {days_since} days classified as {reason!r}, "
        f"golden expects {row.expected!r} "
        f"(thresholds: {config.audit_session_threshold} overrides, "
        f"{config.audit_days_threshold} days)"
    )

    count_pat = rf"\b{config.audit_session_threshold}\b"
    days_pat = rf"\b{config.audit_days_threshold}\b"
    expect_count = row.expected in ("session", "both")
    expect_days = row.expected in ("days", "both")

    assert (re.search(count_pat, additional) is not None) is expect_count, (
        f"the advisory {'omits' if expect_count else 'cites'} the override threshold "
        f"({config.audit_session_threshold}) on the {row.expected} branch: {additional!r}"
    )
    assert (re.search(days_pat, additional) is not None) is expect_days, (
        f"the advisory {'omits' if expect_days else 'cites'} the days threshold "
        f"({config.audit_days_threshold}) on the {row.expected} branch: {additional!r}"
    )

    assert system, "the systemMessage half must stay populated — a banner needs both fields"
    # One-sided on the systemMessage: production names NO threshold there, so requiring the
    # firing one would invent a contract. Forbidding the NON-firing one still kills the naive
    # fix that appends the count threshold to both strings.
    if not expect_count:
        assert re.search(count_pat, system) is None, (
            f"the systemMessage cites the override threshold that did not fire: {system!r}"
        )
    if not expect_days:
        assert re.search(days_pat, system) is None, (
            f"the systemMessage cites the days threshold that did not fire: {system!r}"
        )


# ---------------------------------------------------------------------------
# AC-011 — no shipped section survives whose body refutes its heading
# ---------------------------------------------------------------------------

_FUSED_AXIS_GATE = _ROOT / "tests" / "structural" / "test_no_fused_workflow_axis.py"

#: Lines that shipped in `docs/HOW-IT-WORKS{,.ko}.md` and `docs/CONTRIBUTING.md` while the
#: repo-wide gate stayed green. Each must be caught by the gate's own pattern.
_ESCAPED_LINES = (
    "## 4. Fusion Commands",
    "4. [Fusion Commands](#4-fusion-commands)",
    "| **Commands** | 14 `/hm:` prefix slash commands (7 atomic + 4 fusion + 2 special + 1 loop) |",
    "4. [퓨전 명령](#4-퓨전-명령)",
    "| **명령(Commands)** | `/hm:` 접두어 슬래시 명령 14개 (원자 7 + 퓨전 4 + 특수 2 + 루프 1) |",
    "│   ├── workflow_fuse.py      # M3: atomic stage fusion",
)


def _load_prose_ban() -> re.Pattern[str]:
    spec = importlib.util.spec_from_file_location("_fused_axis_gate", _FUSED_AXIS_GATE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ban: re.Pattern[str] = module._PROSE_BAN
    return ban


def test_ac_011_no_shipped_section_refutes_its_own_heading() -> None:
    """A **deference** test: the invariant's normative site is the pre-existing repo-wide gate.

    `test_no_fused_workflow_axis.py::test_no_repo_doc_advertises_a_fused_workflow` already scans
    `README{,.ko}.md` and all of `docs/` for this axis, with a human-typed `@hm:axis-removed`
    exemption. It missed `docs/HOW-IT-WORKS.md`'s heading, TOC entry and count row only on **case
    and plurality**, and missed `docs/CONTRIBUTING.md`'s deleted-module tree entirely. Asserting
    three fresh literals here instead of widening that pattern would have created a second,
    strictly narrower source of truth and left the recurrence open — CLAUDE.md's
    `one-rule-one-normative-site-others-defer`.

    So this test asserts the gate can see what escaped it, and the AC's own
    `executable_predicate` on the file. It deliberately does NOT re-implement the scan.
    """
    ban = _load_prose_ban()

    assert ban.flags & re.IGNORECASE, (
        "the shared gate's ban is case-sensitive again, so `Fusion Commands` re-escapes it"
    )
    for line in _ESCAPED_LINES:
        assert ban.search(line), (
            f"the shared gate would not flag a line that actually shipped: {line!r}"
        )

    how_it_works = _read("docs/HOW-IT-WORKS.md")
    assert "Fusion Commands" not in how_it_works, (
        "docs/HOW-IT-WORKS.md still ships a Fusion Commands heading for a removed axis"
    )
    assert "#4-fusion-commands" not in how_it_works, (
        "the table of contents still links to the removed Fusion Commands section"
    )


# ---------------------------------------------------------------------------
# AC-015 — no rendered command instructs from a list its own dispatch ignores
# ---------------------------------------------------------------------------

#: A **reachable** narrowed harness: `interview.py:978` preserves a non-empty user `enabled`, and
#: two entries keep `review.md.j2`'s `{% if enabled | length > 1 %}` two-pass section rendering.
#: A.5 round 1 killed the first version of this test, which rendered `enabled: []` — a value no
#: producer emits (`interview()` always writes the full preset list, and `test-reviewer` /
#: `concurrency-reviewer` ARE in it) and which additionally suppresses that section, making the
#: verdict independent of the fix.
_NARROWED_ENABLED = ["code-reviewer", "security-reviewer"]


def test_ac_015_no_rendered_command_instructs_from_an_ignored_list(tmp_path: Path) -> None:
    """Both halves read from the same rendered artifacts — no appeal to a producer's intent.

    The defect is not that the review dispatches an *unlisted* agent; on every harness a producer
    can emit, the dispatched set is a strict subset of `enabled`. It is that `enabled` is **not an
    input**: `lens_dispatch(preset)` never reads it, so a user who narrows the list to two
    reviewers still gets four dispatched — and the rendered prose tells them to start from that
    list. Retracting the sentence, rather than rewording it, is what makes the outcome decidable:
    a reworded imperative is a form judgment (A.5 round 1 showed both a false negative and a false
    positive for the regex that tried), whereas the absence of the key from the rendered command
    is mechanical.
    """
    answers = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        reviewers={"installed": list(_ALL_REVIEWERS), "enabled": list(_NARROWED_ENABLED)},
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    review = (tmp_path / "commands" / "hm" / "review.md").read_text(encoding="utf-8")
    # the production reader, not a second one: a rendered harness.yaml is TWO YAML documents
    # (provenance frontmatter + body), so `yaml.safe_load` raises `ComposerError` on it
    enabled = set(
        load_harness_yaml(tmp_path / "harness.yaml").get("reviewers", {}).get("enabled") or []
    )

    assert enabled == set(_NARROWED_ENABLED), (
        f"the renderer did not preserve the narrowed list ({sorted(enabled)}), so the "
        "differential below would compare against something no user chose"
    )

    dispatched = {row["agent"] for row in lens_dispatch(str(answers.preset.value))}
    ignored = dispatched - enabled

    # Vacuity guard: if the mechanism ever honours `enabled`, the conjunction AC-015 forbids
    # becomes unreachable and this test would pass for the wrong reason. Say so loudly instead.
    assert ignored, (
        "the dispatch table no longer names an agent outside `enabled`, so AC-015's second "
        "conjunct is false and this test proves nothing — re-derive the AC"
    )
    assert {a for a in ignored if a in review}, (
        f"the rendered review.md names none of {sorted(ignored)}, so the dispatch half of the "
        "differential is not observable in the artifact"
    )

    assert "reviewers.enabled" not in review, (
        "the rendered review.md still names `reviewers.enabled` while the lens table it "
        f"dispatches ({sorted(dispatched)}) is composed without it — the narrowed harness gets "
        f"{sorted(ignored)} anyway"
    )
