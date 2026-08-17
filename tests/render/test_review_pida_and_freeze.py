"""Render gates for the second-opinion acceptance gate (PLAN-second-opinion-acceptance-gate).

These are render-greps and they say so — they prove an instruction is PRESENT, never that an
LLM obeys it. What keeps them from being tautologies is the guard-placement pairing: every
positive assertion about a second-opinion block has a matching **negative** assertion against
the `models=[]` render, and every assertion about a model-independent block asserts it is
present in BOTH renders. A predicate true of every possible render would fail one side of
its pair.

That pairing is the whole point of ADR-010. The blanket "guard everything" of an earlier
draft would have scoped the merge-by-`id` corroboration fix and the progress invariant to
second-opinion-enabled harnesses only, while a Success Criterion stated them
unconditionally — a mechanical gate silently winning over prose. `test_unguarded_*` is the
standing check that the split stayed where ADR-010 put it.

Anchored on structural observables (step headings, rule names, the presence/absence of a
guard-scoped block), NOT on sentences — `[fail:test] test-pins-retired-implementation-name`
has fired three times in this repo on assertions that pinned wording a correct rewrite moved.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp
from typing import Literal

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, SecondOpinionConfig
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_MODELS = ("codex", "antigravity")


@cache
def _render_root(models: tuple[Literal["codex", "antigravity"], ...]) -> Path:
    """Render once per model-set for the whole module — a full render is not cheap."""
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.second_opinion = SecondOpinionConfig(models=list(models))
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    out = Path(mkdtemp(prefix="hm-pida-render-"))
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _review(models: tuple[str, ...]) -> str:
    return (_render_root(models) / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


def review_on() -> str:
    return _review(_MODELS)


def review_off() -> str:
    return _review(())


def _agent(name: str) -> str:
    return (_render_root(_MODELS) / "agents" / f"{name}.md").read_text(encoding="utf-8")


def _skill(name: str) -> str:
    return (_render_root(_MODELS) / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def gate_skill() -> str:
    """The main-loop procedure's real home.

    It does NOT live in the stage: every fused command inlines the whole review stage, so a
    character there is paid five times in the shipped command surface, which
    `test_command_size_budget` / `test_aggregate_shipped_surface_does_not_grow` refuse. A skill
    is loaded on demand and is not fanned out. So the contract assertions below read the skill,
    and each is paired with a `test_stage_points_at_*` check — the pointer is what makes the
    rule reachable, and asserting the rule without the pointer would pass over a dead document.
    """
    return _skill("second-opinion-gate")


# --------------------------------------------------------------------------------------
# ADR-001 / ADR-003 — the PIDA gate and its oracle exist, guarded
# --------------------------------------------------------------------------------------


def test_pida_gate_renders_and_is_guarded() -> None:
    assert "Step 3.6" in review_on()
    assert "Step 3.6" not in review_off()


def test_stage_points_at_the_gate_skill_from_both_halves_of_the_split() -> None:
    """The pointer is load-bearing: without it the skill is never loaded and every rule in it is
    dead prose. There are TWO pointers and they are deliberately scoped differently — the gate
    pointer (§2–§4) is guarded because with no models there is nothing to gate, while the
    round-state pointer (§5) is unguarded because that contract governs Claude findings too. So
    the skill name appears in BOTH renders and only the gate step disappears."""
    assert "second-opinion-gate" in review_on()
    assert "second-opinion-gate" in review_off(), "the unguarded §5 pointer went missing"
    assert "follow §2–§4" in review_on()
    assert "follow §2–§4" not in review_off()


def test_the_agent_that_emits_the_value_uses_the_ledger_vocabulary() -> None:
    """The gate that MISSED the shipped drift.

    `test_gate_skill_emits_...` below asserts the vocabulary on the skill — the document that
    *describes* the flow — while the `code-verifier` agent is what actually emits the value the
    ledger consumes. Four surfaces (this agent's mode-B intro, its `description`, the Codex TOML
    description in `synthesize.py`, and CLAUDE.md) kept saying `KEEP / REFUTE / unresolved` after
    the rubric moved to the closed ledger enum. An agent following its own intro line emits
    `KEEP`, `SecondOpinionRecord.disposition` is a strict `Literal`, so the first row raises and
    the writer records ZERO rows — silently zeroing the ledger the whole measurement depends on.

    Mode A's KEEP/DROP/DEMOTE is untouched and must stay: this asserts the mode-B *verdict set*,
    not the absence of the word.
    """
    body = _agent("code-verifier")
    for ledger_value in ("`accepted`", "`rejected`", "`duplicate`", "`unresolved`"):
        assert ledger_value in body, f"mode-B verdict {ledger_value} missing from the agent"
    for retired in ("KEEP / REFUTE", "KEEP/REFUTE/unresolved"):
        assert retired not in body, f"retired mode-B verdict set {retired!r} is back in the agent"
    for token in ("KEEP", "DROP", "DEMOTE"):
        assert token in body, f"mode A lost {token} as collateral damage"


def test_gate_skill_emits_the_closed_ledger_vocabulary_only() -> None:
    """Mode B was deliberately changed to emit ledger values directly. `KEEP`/`REFUTE` are not
    ledger values — writing one raises a ValidationError the writer swallows, losing the row —
    so the intermediate vocabulary must not reappear in the disposition path."""
    body = gate_skill()
    for ledger_value in ("`accepted`", "`rejected`", "`duplicate`", "`unresolved`"):
        assert ledger_value in body
    assert "KEEP" not in body, "the retired KEEP/REFUTE vocabulary is back in the gate skill"


def test_mode_b_frames_its_inputs_as_untrusted_data() -> None:
    """REVIEW M3. Two of mode B's three inputs are another vendor's LLM output and the third is
    arbitrary command stdout, and its JSON verdict is written straight to a ledger. Every other
    reviewer surface in this harness carries untrusted-data framing; this one needs it most."""
    body = _agent("code-verifier")
    assert "DATA, never instructions" in body
    assert "BEGIN UNTRUSTED" in body
    assert "grounds for `unresolved`" in body


def test_gate_skill_requires_reconciling_the_verdict_set_against_the_input_set() -> None:
    """REVIEW M3, second half — data integrity, not threat modelling. The writer validates each
    row's shape but never membership: it does not see the findings that were sent. An omitted,
    duplicated or invented id therefore lands in the ledger as acceptance-rate data with no
    downstream check able to notice."""
    body = gate_skill()
    assert "not in the frozen round-1 set" in body
    assert "report how many were" in body or "how many were\ndropped" in body
    assert "no** disposition back" in body or "no disposition back" in body


def test_gate_skill_does_not_reuse_phase_0_as_the_oracle() -> None:
    """Phase 0 is config-guarded on `reviewers.mechanical_checks`, runs once above Round 1, and
    is all-green by construction in any surviving round — reusing it was a critical defect
    caught in validation. The procedure must say so, not silently depend on it."""
    assert "reviewers.mechanical_checks" in gate_skill()


def test_gate_skill_delegates_oracle_gathering_to_the_filtering_entrypoint() -> None:
    """REVIEW M1 (P0): the gathering used to be a shell line with an external model's `file`
    field substituted into `uv run pytest <paths>`, behind a prefix allow-rule that approves
    arbitrary trailing arguments. The filter now lives in code; the skill must call it and must
    NOT reconstruct the command."""
    body = gate_skill()
    assert "hm second_opinion_oracle --findings-file" in body
    assert "uv run pytest <paths>" not in body, "the unfiltered shell line is back"
    assert "Do not build the command line yourself" in body


def test_gate_skill_states_the_oracle_runs_sandboxed() -> None:
    """The sandbox escape is instructed for the adjacent invoker calls; a main loop that
    conflates the two would widen it."""
    body = gate_skill()
    # Pinned to the SUBJECT, not the two words separately: "Never" also appears in
    # "Never merge", "Never counts" and "Never delete", so an unpaired assertion would pass
    # even if this section enabled the escape.
    assert "Never** pass `dangerouslyDisableSandbox`" in body


def test_gate_skill_documents_what_the_entrypoint_enforces() -> None:
    """The rules moved into code, but the skill still has to say what is guaranteed — a caller
    that cannot see the guarantees will re-add its own weaker version."""
    body = gate_skill()
    assert "4000 characters" in body, "byte budget not stated"
    assert "truncated N chars" in body, "truncation marker not stated"
    assert "Path filtering" in body, "the P0's actual fix is not stated"
    assert "value-shaped" in body, "redaction shape not stated"


def test_verifier_carries_both_modes_and_no_stale_three_step_rubric() -> None:
    """ADR-003 hosts PIDA as mode B of an existing agent; ADR-008 fixes that file's own
    3-step rubric, which would otherwise contradict mode B from birth."""
    body = _agent("code-verifier")
    assert "Mode A —" in body
    assert "Mode B —" in body
    assert "three reasoning steps" not in body


def test_finding_schema_marks_id_as_harness_assigned() -> None:
    """Reviewers must NOT invent ids — an LLM-generated one differs per run, which defeats
    the stability the id exists for."""
    assert "assigned by the harness" in _agent("code-reviewer")


# --------------------------------------------------------------------------------------
# ADR-010 — the guarded/unguarded split
# --------------------------------------------------------------------------------------


def test_unguarded_id_stamping_reaches_a_harness_with_second_opinion_off() -> None:
    """Step 3.4 is model-independent: the corroboration-drop it prevents is pure Claude
    reviewer non-determinism, so guarding it would scope the fix to the wrong population."""
    assert "Step 3.4" in review_on()
    assert "Step 3.4" in review_off()


def test_the_guard_predicates_discriminate() -> None:
    """Non-vacuity: the two renders must actually differ, or every guarded/unguarded
    assertion above would be comparing a document to itself."""
    assert review_on() != review_off()
    assert len(review_off()) < len(review_on())


def test_unresolved_carve_out_is_stated_where_the_scan_lives() -> None:
    """ADR-004's exclusion is the only exception to a purely tag-based scan. Stated, not
    emergent — an unwritten exception is how a reader concludes the scan still covers it."""
    assert "provenance carve-out" in review_on()
    assert "provenance carve-out" not in review_off()


# --------------------------------------------------------------------------------------
# ADR-002 — freeze, lifecycle, monotonic progress, voter state
# --------------------------------------------------------------------------------------


def test_no_reinvoke_clause_lives_in_the_skill_that_owns_it() -> None:
    """The silence this closes — the Auto-Fix Loop never said what happens to cross-model
    voters — is the direct cause of the reported non-termination.

    Retargeted by PLAN-review-round-inflation ADR-005: the stage carried a second copy of
    this §5 rule, so the contract had two owners and prose compaction could fork them. The
    stage's copy is deleted; §5 is the only one. The `not in review_off()` arm is dropped
    with it — §5 is loaded unconditionally now, so the rule reaches a `models: []` harness
    by design rather than being scoped away from it.
    """
    assert "Do not re-invoke the models" in gate_skill()
    assert "Do NOT re-invoke the second-opinion models" not in review_on()


def test_once_per_invocation_statement_is_present() -> None:
    assert "EXACTLY ONCE per `/hm:review` invocation" in review_on()


def test_resolution_requires_verification() -> None:
    """A reverted fix leaving a record `resolved` would retire a live finding."""
    assert "verification passed" in gate_skill()


def test_no_reopen_edge_counts_as_progress() -> None:
    """The oscillation hole: if a re-open counted, a status flipping between `pending` and
    `resolved` would report progress every round and the stop would never fire."""
    body = gate_skill()
    assert "Never** counts" in body
    assert "Back-transitions are forbidden" in body


def test_one_round_stop_carries_its_round_binding() -> None:
    """Unqualified, the rule fires at the end of round 1 — which has no fix step, so zero
    transitions are reachable — and auto-fix never runs at all."""
    assert "round ≥ 2" in gate_skill(), "one-round stop is missing its round-index binding"
    assert "no-progress" in gate_skill()


def test_merge_by_id_retains_an_unreported_finding() -> None:
    """Wholesale replacement lets one reviewer's non-determinism drop a corroborating voice and
    move the grade with no code change."""
    body = gate_skill()
    assert "merged by `id`, not replaced wholesale" in body
    assert "retained" in body


def test_round_state_contract_is_reachable_from_every_harness() -> None:
    """The contract governs Claude findings too, so its pointer must be UNGUARDED — guarding it
    would scope the corroboration fix to second-opinion harnesses only, which is exactly the
    mechanical-gate-beats-prose failure this split was made to avoid."""
    for body in (review_on(), review_off()):
        assert "Round-state contract" in body
        # The POINTER must be unguarded in both configs — that is this test's subject.
        assert "Load `second-opinion-gate` §5" in body
    # The RULE itself now lives in exactly one place (ADR-005). Asserting it against the
    # stage would re-create the duplicate contract this split removed.
    assert "not replaced wholesale" in gate_skill()


def test_exit_reason_distinguishes_no_progress_from_cap_exhausted() -> None:
    for body in (review_on(), review_off()):
        assert "Exit reason:" in body
        assert "cap-exhausted" in body


# --------------------------------------------------------------------------------------
# ADR-007 / ADR-009 — the frozen set and the disposition write
# --------------------------------------------------------------------------------------


def test_frozen_set_section_is_guarded_in_the_stage() -> None:
    assert "frozen @ round 1" in review_on()
    assert "frozen @ round 1" not in review_off()


def test_frozen_set_schema_carries_the_join_key_and_the_stale_reason() -> None:
    body = gate_skill()
    assert "frozen_at_round" in body
    assert "invalidation_reason" in body
    assert "never re-derived" in body


def test_frozen_set_omits_the_three_fields_the_adapter_cannot_produce() -> None:
    """Persisting a permanently-null key reads as capability to the next reader — the
    absent-case failure mode, applied to a field list."""
    body = gate_skill()
    assert "No `symbol`/`reasoning`/`suggestion` keys" in body
    for phantom in ("symbol:", "reasoning:", "suggestion:"):
        assert phantom not in body, f"the schema still persists {phantom!r}"


def test_disposition_write_uses_a_file_not_argv() -> None:
    body = gate_skill()
    assert "--record-disposition" in body
    assert "--disposition-file" in body
    # Token-level, not phrase-level: a markdown rewrap moved the previous pinned phrase
    # across a line break and this assertion failed on prose that was still correct.
    assert "argv-embedded" in body


def test_disposition_write_failure_is_observable() -> None:
    """Exit 0 on a graceful degrade is right, but a silent no-op would make a successful review
    indistinguishable from one that recorded nothing."""
    assert "disposition rows NOT recorded" in gate_skill()


def test_the_gate_skill_is_installed_in_every_harness() -> None:
    """A pointer to an uninstalled skill is a dangling reference. Installation is
    unconditional (activation is data, not file presence), so the file must render even
    though `second_opinion.models` gates the pointer."""
    assert (_render_root(()) / "skills" / "second-opinion-gate" / "SKILL.md").exists()


# ── PLAN-review-round-inflation — measure A + measure C executed surface ─────


def test_the_stage_does_not_restate_the_rules_it_points_at() -> None:
    """ADR-005's negative half. The positive load-line test above cannot see a
    restatement sitting next to the pointer — that is exactly how the stage ended
    up with two copies of §5's rules, and how a compaction pass then inverted one
    of them. Both deleted blocks are named so a re-introduction fails here.
    """
    for body in (review_on(), review_off()):
        # The `:509-514` round-state restatement.
        assert "`pending` votes;" not in body
        assert "back-transitions forbidden" not in body
        # The `:539-545` do-not-re-invoke restatement.
        assert "Do NOT re-invoke the second-opinion models" not in body
        assert "fresh stochastic voter every round" not in body


def test_the_batch_trigger_is_reachable_and_ordered_before_fix_selection() -> None:
    """ADR-012. Arm (b) reads `caused_by`; computing that at record-append time
    would put it AFTER fix selection, so a lone regression finding would take the
    fast path — reproducing the chain measure A exists to stop. The order is the
    fix, so the order is what this asserts.
    """
    # Whitespace-normalised: the phrases below wrap across lines in the rendered
    # skill, and pinning them raw is the `[fail:test]
    # test-pins-retired-implementation-name` shape this module's docstring warns
    # about — it has fired three times here.
    skill = " ".join(gate_skill().split())
    order = [
        "Merge the previous round's re-review output by `id`",
        "determine `caused_by`",
        "group and evaluate the trigger",
        "select fixes",
        "apply",
        "verify build",
        "selective re-review",
        "append the iteration record",
    ]
    positions = []
    for step in order:
        idx = skill.find(step)
        assert idx != -1, f"round-order step missing from §5: {step!r}"
        positions.append(idx)
    assert positions == sorted(positions), (
        f"§5's round order is out of sequence: {list(zip(order, positions, strict=True))}"
    )

    # The lone-finding reference case: arm (b) must fire on ONE attributed finding,
    # so the trigger cannot be expressed as a count alone.
    # Pin the arms to their SUBJECTS, not to loose tokens: "either … ≥2 … new this
    # round" is satisfiable by unrelated prose (codex + code-reviewer, round 1).
    # Scope to the trigger paragraph. `(a)`/`(b)` occur elsewhere in the skill, so
    # searching the whole document finds the wrong pair — a document-wide anchor is
    # how the first cut of this assertion sliced an empty string and still had an
    # opinion about it.
    para_start = skill.find("Two-arm batch trigger")
    assert para_start != -1, "the trigger paragraph is gone from §5"
    para = skill[para_start : para_start + 600]
    arm_a_at, arm_b_at = para.find("(a)"), para.find("(b)")
    assert 0 <= arm_a_at < arm_b_at, "the trigger does not read as two ordered, labelled arms"
    arm_a, arm_b = para[arm_a_at:arm_b_at], para[arm_b_at:]
    assert "≥2" in arm_a, "arm (a) lost its count threshold"
    assert "subsystem" in arm_a, "arm (a) no longer groups by shared subsystem / state model"
    assert "caused_by" in arm_b, "arm (b) no longer reads the attribution field"
    assert "new this round" in arm_b, "arm (b) lost its new-findings-only domain"

    # The stage enforces the same order by NUMBERING, not by a sentence saying so:
    # attribute (1) → group/trigger (2) → select (3). A prose clause was what the
    # first cut asserted, and prose is what drifted from the numbered list in the
    # first place (code-reviewer + codex, review round 1).
    # The ordinal's SHAPE is pinned and its VALUE is not. `"1. **Merge and attribute.**"`
    # broke on a correct renumber ([fail:test] test-pins-retired-implementation-name,
    # count:4); a bare `.find("**Merge and attribute.**")` then dropped the one thing this
    # test is about — that the order is carried by the NUMBERED list rather than by prose.
    # `^\d+\. ` keeps that and survives renumbering.
    def _step(body: str, title: str) -> int:
        m = re.search(rf"^\d+\. {re.escape(title)}", body, re.M)
        return m.start() if m else -1

    for body in (review_on(), review_off()):
        attribute_at = _step(body, "**Merge and attribute.**")
        group_at = _step(body, "**Group.**")
        select_at = _step(body, "**Select fixable findings**")
        assert -1 not in (attribute_at, group_at, select_at), (
            "the Auto-Fix Loop's steps are no longer a NUMBERED list where the contract "
            "says: merge-and-attribute / group / select-fixable"
        )
        assert attribute_at < group_at < select_at, (
            "attribution/trigger no longer precede fix selection — arm (b) is unreachable"
        )


def test_caused_by_uses_the_pinned_status_cell_grammar() -> None:
    """`caused_by` shares a cell with a different enum. Without one literal
    grammar, rounds encode it differently, arm (b) misses attributions, and the
    two counters disagree with the rows they are derived from — with no test able
    to see it, because an unspecified grammar has nothing to compare against.
    """
    # The GRAMMAR is a rule, so §5 owns it (ADR-005); the stage carries exemplar
    # rows so a reader at the point of use sees the encoding without opening it.
    skill = gate_skill()
    for literal in ("· caused_by=#7", "· caused_by=none", "· caused_by=unknown"):
        assert literal in skill, f"{literal} missing from §5's grammar"
    for body in (review_on(), review_off()):
        assert "· caused_by=" in body, "the iteration record shows no attribution encoding"


def test_the_four_measure_c_fields_reach_the_emitted_record() -> None:
    """The roster line is what the runtime model copies when building
    `<record_json>`. Python accepting the fields is not enough — if the roster
    does not name them, nothing is ever sent and measure C ships inert, which is
    this project's recorded absent-case failure mode.
    """
    for body in (review_on(), review_off()):
        roster_start = body.find("`{ts, slug, round,")
        assert roster_start != -1, "telemetry field roster missing from the render"
        roster_end = body.find("`.", roster_start)
        # Without this, a missing terminator makes `roster` the rest of the document
        # and every field assertion below passes on unrelated prose (code-reviewer).
        assert roster_end != -1, "telemetry roster has no terminator — slice would run away"
        roster = body[roster_start:roster_end]
        for field in (
            "terminal",
            "unreviewed_fix_count",
            "regression_attributed_n",
            "attribution_unknown_n",
        ):
            assert field in roster, f"{field} missing from the emitted field roster"
        # Stale literal that contradicted the field count it introduced.
        assert "14-field schema" not in body
