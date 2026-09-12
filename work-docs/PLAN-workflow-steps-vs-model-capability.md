---
type: plan
task_slug: workflow-steps-vs-model-capability
status: complete
created: 2026-09-12
tags: [harness-maker, plan, python, jinja2, structural-tests, workflow-design, model-capability]
spec: "[[SPEC-workflow-steps-vs-model-capability]]"
research_doc: "[[RESEARCH-workflow-steps-vs-model-capability]]"
interview_rounds: 4
adrs: 9
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Step-sensitivity registry keyed (stage, ordinal), coverage over preset×dev_mode arms, Side consistency test; delete 5-term ceremony + verify Check 1b; freeze post-land"
spec_need_verdict: add
spec_need_target: workflow-steps-vs-model-capability
---

# PLAN — Workflow step sensitivity registry

## 🎯 Executive Summary

**TL;DR.** Ship `src/harness_maker/step_sensitivity.py` — a frozen registry that maps every
rendered `/hm:` Step/Phase/Check to a sensitivity class (COMP / HOST / INV / TUNE), an
evidence grade, a source, and (TUNE only) a re-measurement trigger — and two structural tests
that make it load-bearing: every rendered heading must be classified, and the Side preset's
knob defaults must not be more aggressive than Production on any COMP/TUNE knob. Alongside,
delete the two COMP prose blocks the SPEC names (research/spec/plan 5-term ceremony; verify
Check 1b), re-freeze both baselines with attributed negative deltas, and document the classes.

**What / Why.** RESEARCH found the repo's only defense against "the new model doesn't need X"
is a prose argument that lost twice to measurement. A registry with a coverage test makes the
class a *precondition* of adding a step, and the re-measurement field makes the next model
release a code-level question rather than a document search.

**Key decisions.** Registry key is `(stage, ordinal)` not heading text (ADR-001); the Side
ordering is declared per entry with a three-word vocabulary (ADR-002); verify Check **1a**
(drift-verdict existence, mechanical) stays and only **1b** (LLM coverage) is deleted
(ADR-003); the 5-term deletion removes the partial and the stage prose but keeps the
open-ended cap sentence and plan Step E's exit conditions (ADR-004); render output is
otherwise unchanged — no Side pruning (ADR-005); instruction-baseline removals are
allowlisted per phase and **neither baseline is re-frozen inside the task** — the re-freeze
is a post-land step on base (ADR-006); the coverage matrix is preset × dev_mode with
`renders_when` recorded for toggle-gated headings (ADR-007); Side/Production values come from
per-preset answers with a non-vacuity floor (ADR-008); unsourced classes carry the sentinel
grade `unsourced` and their count is surfaced (ADR-009).

**Impact.** Maintainer-facing. Rendered surface shrinks by the two blocks (estimated
−3 to −5 KB across three commands + one); no user harness behaviour changes except the
two deleted instructions. No new `harness.yaml` key.

## 📚 Prior Work

- `RESEARCH-harness-diet` / `PLAN-harness-diet` ADR-003 — reversed a capability-based cut of
  `/hm:verify`; this PLAN keeps that stance (Check 1a stays).
- `RESEARCH-workflow-time-token-savings` — plan-validator 22% verdict change, A.5 37.5%→75%
  FAIL (Side-only) → both TUNE, not COMP.
- `MATRIX-native-redundancy.md` — the HOST axis already exists as a 41-row doc; Phase 6 adds
  the class column there rather than starting a second matrix.
- `tests/structural/test_instruction_preservation.py` — deletions of runtime instructions
  must be allowlisted in `_ALLOWED_REMOVALS` against the exact `<command>@<dev_mode>` key;
  the prior token-economy plan shipped an unlisted deletion and this test exists because of it.
- `tests/structural/test_command_descriptions.py` — the render-all-targets fixture pattern the
  new structural test copies (`_blueprint(preset)` → `synthesize` → `render`).
- `[fail:design] new-marker-content-field-must-update-every-reader` (count:3) — the registry
  is a new data source; its only reader is the test, and the test discovers headings from
  the render rather than from a hand list (mirrors `test_autopilot_marker_api_session_key`).
- `feedback_plan_validator_single_pass` — one validator pass, no Step 4.5 re-run.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Deliverable scope | Scope | docs-only / docs+schema / docs+bench / all phased | a/b/c/d | **b** docs + schema | bench measurement is a per-model process, separate task | — (SPEC R1) |
| 2 | COMP deletions in scope | Scope | exclude / include 1–2 safest | 2 | **include** | — | — (SPEC R1) |
| 3 | `second_opinion.models` default | Contract | Production→["codex"] / keep [] / defer | 3 | **keep []** | user: CLI-install assumption is a burden | — (SPEC R1) |
| 4 | TUNE evidence standard | Risk | Side-only tagged / wait for Production rows | 2 | **Side-only, tagged** | — | — (SPEC R1) |
| 5 | Which COMP prose | Scope | 5-term ceremony / verify Check 1 / C.0+D.5 | multi | **5-term + Check 1** | C.0/D.5 rejected (mutation-receipt coupling) | ADR-003, ADR-004 |
| 6 | Enforcement level | Architecture | registry only / registry+test / +Side pruning | 3 | **registry + test** | no render pruning | ADR-005 |
| 7 | Re-measure trigger | Contract | field only / exclude | 2 | **field only** | no automation | ADR-002 |
| 8 | Plan lock-in (Step 3.0) | — | proceed / key shape / Check 1 handling / full interview | 4 | **proceed** | four defaults accepted as ADRs | ADR-001..004 |
| 9 | Validator C1: freeze location | Risk | A revise (post-land freeze) / B risk | 2 | **A** | precedent + `assert_sha_is_durable` hard refusal | ADR-006 |
| 10 | Validator C3: coverage contract | Architecture | A full arm matrix / A' preset×dev_mode only / B | 3 | **A'** | toggle arms deferred; `renders_when` recorded; S2 scope stated in CLAUDE.md | ADR-007 |
| 11 | Validator M7: unsourced classes | Contract | A `unsourced` grade / A' narrow AC-001 / B | 3 | **A** | count surfaced in docs | ADR-009 |
| 12 | Validator remaining 9 | — | all A / some B-C | 2 | **all A** | suggestions applied verbatim | ADR-001/002/003/004/008 |

## 📐 Architecture Decision Records

### ADR-001: Registry key is `(stage, ordinal)`, never heading text
**Status:** Accepted (2026-09-12, via /hm:plan interview)
**Context:** Rendered headings carry conditional suffixes (`Phase A — Author tests (skipped when tdd_active == false)`), config-rendered numbers, and em-dash titles that get reworded. A text key would churn on every wording edit and silently orphan entries.
**Decision:** Key = `(stage: str, ordinal: str)` where ordinal is the token after `Step|Phase|Check` up to the first ` —`/` -`/`(`, e.g. `("execute", "Phase A.5")`, `("verify", "Check 2")`. Ordinals are derived from the **existing** `headings()` helper in `tests/structural/test_command_size_budget.py` (level `#{2,6}`, the single definition of "what counts as a heading" that `_instruction_baseline` also imports) by filter + capture — no second file-level regex. A test asserts the registry extractor and `headings()` see the same heading set, so level-2 headings such as `## Phase 0 — Mechanical Pre-Checks` are covered.
**Consequences:**
- ✅ Wording edits never break coverage; only adding/renumbering a step does — which is exactly when a class decision is due.
- ⚠️ Two headings with the same ordinal in one stage collide; the extractor asserts uniqueness per stage and fails loudly.
**Rejected alternatives:**
- Full heading text — Rejected: churns on prose edits (pitfall 7 of harness-diet: prose is what drifts).
- Hand-written stable slug per step (`<!-- @hm:step:… -->` markers) — Rejected: a marker the author forgets is invisible to the render and the coverage test cannot discover it; ordinals are already in the text.
- A new `HEADING_RE` limited to `#{3,5}` — Rejected (validator M6): a second, narrower extractor silently drops level-2 phases; two definitions of "heading" drift apart.
**Source:** Interview #8

### ADR-002: Per-entry knob ordering with a three-word vocabulary; TUNE carries `remeasure_on` + `measure_cmd`
**Status:** Accepted (2026-09-12, via /hm:plan interview)
**Context:** S3 needs "Side is not more aggressive than Production" to be checkable per knob, and knobs differ in type (int, bool, list, enum).
**Decision:** `StepEntry` has `knob: str | None`, `source_kind: Literal["yaml", "python"] | None` (a dotted `harness.yaml` path, or a Python callable of preset such as `conditional_router.mandatory_lenses`), and `ordering: Literal["le", "subset", "bool_off", "equal_by_design"] | None`. `equal_by_design` marks a knob whose Side and Production values are intentionally identical (e.g. `second_opinion.models` = `[]` on both) — the test asserts equality rather than pretending a subset check binds. `le`: Side ≤ Production numerically (rounds, max_rounds; `None` = unlimited = +∞). `subset`: Side list ⊆ Production list (enabled reviewers, mandatory lenses). `bool_off`: Side is `False` when Production is `True`, or equal. TUNE entries require `remeasure_on: tuple[str, ...]` (e.g. `("model_release",)`) and `measure_cmd: str` that **names its repo** (e.g. `harness-bench: bench run --exp review_convergence --model <name>`); COMP/HOST/INV leave them empty. A registry-level validator enforces the TUNE requirement and the repo prefix at import.
**Consequences:**
- ✅ The Side test is a pure function of two `synthesize()` outputs plus the registry; no renderer change.
- ⚠️ A knob not expressible in the four orderings must be `knob=None` (documented in the entry's `note`); the test cannot see it. Accepted — no current knob needs a fifth.
- ⚠️ `measure_cmd` is validated for shape only (non-empty, repo-prefixed). `harness-bench` is a separate repository; a renamed or deleted bench command is not detected here. Accepted per Interview #7 ("field only, no automation") — the field is a pointer, not a contract.
**Rejected alternatives:**
- Free-form comparator lambdas in the registry — Rejected: unreadable in a diff, untestable in isolation.
- Deriving Side defaults from the registry in `presets.py` — Rejected: that is the (iii) pruning path the user declined; it moves the source of truth.
**Source:** Interview #6, #7

### ADR-003: Delete verify Check 1b only; Check 1a (drift-verdict existence) stays
**Status:** Accepted (2026-09-12, via /hm:plan interview)
**Context:** SPEC S5 says "no LLM PLAN/SPEC satisfaction check remains; deterministic checks remain". Reading the template: Check 1 is two sub-checks — 1a reads `REVIEW-{slug}.md` frontmatter for `drift_verdict` + slug match (mechanical, ADR-006 of the review-drift plan, and the only thing that forces `/hm:review` before `/hm:verify`); 1b asks the LLM to confirm each SPEC scenario has a passing test (judgment, duplicated by review Step 2 and wrapup Step 3).
**Decision:** Remove 1b and its `FAIL when` line; retitle Check 1 to `Check 1 — Drift verdict (REVIEW present)` keeping the `Check 1 —` prefix (`test_verify_delegation` asserts on it). Also rewrite the two residues that reference 1b: the inputs line (`verify.md.j2:35`, "PLAN and SPEC … drive Check 1" → "drive Check 6 (spec-driven)") and 1a's terminal arrow (`:44`, "→ proceed to 1b" → "→ PASS"). Check numbering 2–6 unchanged. `--force` semantics unchanged.
**Consequences:**
- ✅ verify becomes all-deterministic without losing the review-before-verify gate.
- ⚠️ SPEC-scenario coverage is now asserted only by review Step 2 / wrapup Step 3 (LLM) and, in spec-driven mode, Check 6's `spec_need op-check`. Accepted: that was already the effective oracle; 1b duplicated it.
**Rejected alternatives:**
- Delete Check 1 entirely and move the drift read under Check 2 — Rejected: renumbers every check, touches `instruction_baseline.json` on six keys instead of two, and breaks the `Check 1 —` position test for no functional gain.
**Source:** Interview #5, #8

### ADR-004: 5-term deletion scope — partial + stage prose; cap sentence and Step E exit conditions stay
**Status:** Accepted (2026-09-12, via /hm:plan interview)
**Context:** The ceremony lives in `_partials/inequality_gate_block.md.j2` (15 lines) plus per-stage prose in research (Phase 0.5), spec (§2.5), plan (Step E) that renders ε/τ from `harness.yaml` and mandates a per-candidate ✅/❌ checklist. `interview.deep_gate` config keys and `inequality_gate.py`/`eig.py` are used by the Python interview path and by `test_schema_migration`; they are not touched.
**Decision:** Delete the partial and its three include sites plus the "Term meanings", "Per-round display", "Question generation", and "Exit"/"Gate exit" paragraphs. Keep one sentence per stage: `At most {{ cap }} open-ended question(s) per turn for locale {{ locale }}; closed-form questions are unrestricted.` Keep plan Step E's exit conditions (early-exit choice, zero high/medium ambiguities) minus the gate. Two further consumers are in scope (validator M5): `commands/hm/loop.md.j2` §4-H is a **full ~40-line section** (include + term list + per-round display + question generation + exit, with 4-B/4-E/4-F ordering prose) and is rewritten to the cap sentence with the step-ordering references re-checked; `agents/_partials/comprehension_block.md.j2:61` ("the 5-term gate still governs which get asked") is included eight times into plan/spec and is reworded to "the open-ended cap still governs how many get asked". The S4 test asserts the residue strings `5-term`, `EIG`, `CLARITI` are absent from rendered research/spec/plan/loop, not only the section title. Config schema untouched.
**Consequences:**
- ✅ Three stages lose ~40 rendered lines each of instruction the model applies by judgment anyway (RESEARCH Table 1, COMP `*`).
- ⚠️ `instruction_baseline.json` entries for research/spec/plan × both dev_modes change; each removed string is allowlisted (ADR-006).
**Rejected alternatives:**
- Delete only the partial, keep stage prose — Rejected: the stage prose *is* the ceremony (term table + checklist); the partial is the smaller half.
- Also remove `interview.deep_gate` schema keys — Rejected: schema migration + consumer code, out of SPEC scope (no new/removed key).
**Source:** Interview #5

### ADR-005: Render output is unchanged apart from the two deletions — no Side pruning
**Status:** Accepted (2026-09-12, via /hm:plan interview)
**Context:** The user declined option (iii). Pruning COMP steps from the Side render regenerates every Side snapshot and risks Cursor/Codex regressions (harness-diet pitfall 2).
**Decision:** The registry is consumed only by tests and docs. No template reads it.
**Consequences:**
- ✅ Zero snapshot regen beyond the two deletions; no target-conditional logic.
- ⚠️ The "derivation" is a consistency *check*, not a generator — Side defaults still live in `interview._preset_extras`. Accepted and stated in CLAUDE.md.
**Rejected alternatives:** (iii) — see above.
**Source:** Interview #6

### ADR-006: Deletions are allowlisted per phase; neither baseline is re-frozen inside the task — the freeze is a post-land step on base
**Status:** Accepted (2026-09-12, via /hm:plan interview — validator C1)
**Context:** `tests/structural/_surface_baseline.py:assert_sha_is_durable` (called by both freezers) **hard-refuses** to freeze at a commit that is not an ancestor of `main`; a task-branch tip never is once it carries a commit, and `task-land` squash-deletes the branch. The repo's precedent (`BASELINE-DELTA-token-efficiency-autopilot-ux-speed`, ADR-011 of that plan) is: during the task, declare the delta in the DELTA document; re-freeze from the base checkout after the PLAN closes. The memory note "snapshot regen in worktree is correct" concerns `regenerate.py` render snapshots, which pin no SHA, and does not transfer.
**Decision:** Phase 3 and Phase 4 add their removed strings to `_ALLOWED_REMOVALS` (keyed `<command>@<dev_mode>`, both arms) and **do not** touch `instruction_baseline.json`; `test_instruction_preservation` stays green through the allowlist. Phase 5 writes `BASELINE-DELTA-workflow-steps-vs-model-capability.md` with the measured per-command negative delta and **no** allowance entry (the ratchet is one-directional; shrinkage needs attribution, not allowance) and does not touch `surface_baseline.json`. New **Phase 7 (post-land, base checkout)** re-freezes both baselines at the landed `main` SHA and commits them with the delta doc's closing row; it runs from `/home/noel/harness-maker`, not the worktree, after `/hm:wrapup` lands.
**Consequences:**
- ✅ Every phase inside the task is green on the task branch and in CI; nothing depends on a SHA that the squash deletes.
- ⚠️ SPEC S6/AC-006's "re-frozen" is satisfied only after land; the SPEC line is amended to say so, and `test_the_delta_document_exists` (the AC-006 test id) is what passes mid-task.
- ⚠️ Phase 7 is a second commit on `main` after the squash — the same shape as the precedent's "B5 appends the measured net figure".
**Rejected alternatives:**
- Regenerate in the worktree — Rejected: hard refusal, and a zero-commit workaround records a `render_sha` that does not match the frozen payload.
- Rebase the task branch onto `main` and freeze at a base-reachable commit — Rejected: the freeze SHA must survive the squash; only a `main` commit does.
**Source:** Interview #9

### ADR-007: Coverage matrix is preset × dev_mode; toggle-gated headings carry `renders_when` and are outside the coverage promise for now
**Status:** Accepted (2026-09-12, via /hm:plan interview — validator C3, option A')
**Context:** Headings gated on `second_opinion.models` (review 3.5/3.6), `dev_mode` (verify Check 6), `delegation` (verify/wrapup Step 0.5), and `reviewers.mechanical_checks` (review Phase 0) do not all appear in any single render. `registry ⊆ rendered` and `rendered ⊆ registry` cannot both hold on a matrix that does not vary those axes.
**Decision:** The render matrix is the explicit arm list `ARMS = {Side, Production} × {spec-driven, task-driven}` (targets are irrelevant: commands render to exactly one file family — `test_command_descriptions`). Coverage (S1) asserts `union(headings over ARMS) ⊆ registry`; the orphan test asserts `registry entries with renders_when is None ⊆ union(headings over ARMS)`. Entries for headings gated on the three toggle axes carry `renders_when: str` (e.g. `"second_opinion.models non-empty"`) and are exempt from the orphan test. The 82 figure is re-derived from `ARMS` in Phase 1 and recorded in the module docstring with the config it came from. Toggle-on arms (`second_opinion.models=["codex"]`, `delegation=[verify,wrapup]`, `mechanical_checks=[…]`) are a named follow-up; until then S2's promise ("an unclassified heading fails") does **not** hold for a heading added inside those branches — stated verbatim in the CLAUDE.md section (Phase 6).
**Consequences:**
- ✅ Same discipline as `_instruction_baseline.AXES` ("axes knowingly NOT covered", stated).
- ⚠️ A heading added inside a toggle branch without a class is invisible until the follow-up ships. Accepted by the user.
**Rejected alternatives:**
- Full arm matrix including toggle-on arms — Deferred (user choice A'): four extra renders per test run and a synthesize path for each toggle; not needed to make the registry load-bearing on the default arms.
**Source:** Interview #10

### ADR-008: Side/Production values come from per-preset answers, with a non-vacuity floor
**Status:** Accepted (2026-09-12, via /hm:plan interview — validator C2)
**Context:** `synthesize(profile, answers, preset=…)` reads `reviewers.*`, `worktree.enabled`, `interview.main_loop.max_rounds` from `answers`, and uses `preset` only for `config.preset`; `interview(profile, autoloop_mode=True)` builds one answers object from `_recommend_preset(profile)`. Rendering twice with different `preset=` from one answers object therefore yields identical knob values, and every `le`/`subset`/`bool_off` comparison passes vacuously.
**Decision:** Phase 2 constructs two answers objects through the path that applies `_preset_extras(preset)` — `interview._build_answers(..., preset=…)` if it is importable with a stub profile, otherwise `answers.model_copy(update=_preset_extras(preset, schema_version=…))` — and the test names which one in a comment with the line reference. The test then asserts, before any ordering check, that **at least 3** compared knobs differ between the two configs (non-vacuity floor; shipped: `max_review_rounds`, `main_loop.max_rounds`, `worktree.enabled`, `mandatory_lenses` differ — `reviewers.enabled` and `reviewers.consensus` were dropped as knobs in /hm:review round 2 because neither drives runtime behaviour). The negative control mutates the *Side answers object* (`max_review_rounds=4`), not a fixture string.
**Consequences:**
- ✅ S3 binds; a future change that collapses Side onto Production trips the floor.
- ⚠️ If `_build_answers` changes signature the test must follow; it is the single entry point that materialises preset defaults, so this coupling is the honest one.
**Rejected alternatives:**
- `synthesize(preset=)` twice from one answers — Rejected: vacuous (validator evidence `synthesize.py:900-953`).
**Source:** Interview #12

### ADR-009: Unsourced classifications carry the sentinel grade `unsourced`; their count is surfaced in docs
**Status:** Accepted (2026-09-12, via /hm:plan interview — validator M7)
**Context:** RESEARCH Table 1 has 32 rows, several of them ranges or non-heading items; roughly 40 of the 82 headings have neither a row nor a classified parent step. Without a sentinel, "classified from evidence" and "guessed by the executor" are indistinguishable in the `source` field.
**Decision:** `Grade = Literal["***", "**", "*", "unsourced"]`. An entry with no RESEARCH row is classified by nearest-parent or sibling class with `grade="unsourced"` and `source="no RESEARCH row (2026-09-12); inherits <parent ordinal>"`. The registry validator permits it. `step_sensitivity.unsourced_count()` is printed by the MATRIX generator and asserted by `test_docs_carry_classes` against the number written in the CLAUDE.md section, so the debt is visible and cannot silently change.
**Consequences:**
- ✅ The next RESEARCH has a machine-readable list of what to source.
- ⚠️ ~40 entries ship as `unsourced`; the registry is complete in coverage but not in evidence, and says so.
**Rejected alternatives:**
- Narrow AC-001 to Table-1-backed headings — Rejected (user): halves the S2 promise.
**Source:** Interview #11

## 🏗️ Technical Design

**Current state.** ~84 `Step|Phase|Check` headings (levels 2–5) across the seven rendered stages
at 0.55.0 (planning census on the default arm: research 7, spec 8, plan 17, execute 15,
review 19 incl. `## Phase 0`, verify 7 incl. Step 0.5, wrapup 11 — the exact figure is
re-derived over `ARMS` in Phase 1, ADR-007). No
machine-readable classification. Side/Production knob defaults come from
`interview._preset_extras(preset)` and `templates/harness-yaml/{Side,Production}.yaml.j2`.

**Affected components.**
- New `src/harness_maker/step_sensitivity.py` (registry + ordinal filter over `headings()` + validator + MATRIX row generator + `unsourced_count`).
- New `tests/structural/test_step_sensitivity_registry.py` (S1, S2, S3, S7).
- New `tests/unit/test_render_inequality_gate_removed.py` (S4), `tests/unit/test_render_verify_check1_removed.py` (S5).
- Edited templates: `stages/research.md.j2`, `stages/spec.md.j2`, `stages/plan.md.j2`, `stages/verify.md.j2`, `commands/hm/loop.md.j2` (§4-H section rewrite), `stages/review.md.j2` (mention), `agents/_partials/comprehension_block.md.j2` (one sentence); deleted `agents/_partials/inequality_gate_block.md.j2`.
- Edited tests: `test_instruction_preservation.py` (`_ALLOWED_REMOVALS`). Baselines (`instruction_baseline.json`, `surface_baseline.json`) untouched until Phase 7 on base.
- Docs: `work-docs/MATRIX-native-redundancy.md` (new column), `CLAUDE.md` (new section), `work-docs/BASELINE-DELTA-workflow-steps-vs-model-capability.md`.

**Dependencies.** None new. `pytest`, existing render fixtures.

**Architecture.**
```
templates/stages/*.md.j2 ──render──▶ .claude/commands/hm/*.md
                                          │ extract (regex, ADR-001)
                                          ▼
step_sensitivity.REGISTRY  ◀── ⊆ ──  {(stage, ordinal)}        [S1/S2]
        │ knob + ordering (ADR-002)
        ▼
synthesize(Side) vs synthesize(Production) ── ordering holds ──▶ [S3]
```

**Data model.**
```python
Class = Literal["COMP", "HOST", "INV", "TUNE"]
Grade = Literal["***", "**", "*", "unsourced"]
Ordering = Literal["le", "subset", "bool_off", "equal_by_design"]
SourceKind = Literal["yaml", "python"]

@dataclass(frozen=True)
class StepEntry:
    stage: str            # research|spec|plan|execute|review|verify|wrapup
    ordinal: str          # "Step 1.5" | "Phase A.5" | "Check 2" | "Phase 0"
    cls: Class
    grade: Grade
    source: str           # doc slug / ledger / bench section / "no RESEARCH row …"
    note: str = ""
    renders_when: str | None = None   # ADR-007: set for toggle-gated headings
    knob: str | None = None
    source_kind: SourceKind | None = None
    ordering: Ordering | None = None
    remeasure_on: tuple[str, ...] = ()
    measure_cmd: str = ""             # "harness-bench: bench run …"

ARMS: tuple[tuple[Preset, DevMode], ...]   # ADR-007
REGISTRY: tuple[StepEntry, ...]
ORDINAL_RE = re.compile(r"^(?:Step|Phase|Check)\s+[A-Z0-9][A-Za-z0-9.]*")
def ordinals_from_headings(headings: list[str]) -> list[str]: ...  # filter over test_command_size_budget.headings()
def validate(registry) -> None:  # unique keys; TUNE ⇒ remeasure_on & repo-prefixed measure_cmd; knob ⇒ source_kind & ordering
def unsourced_count(registry) -> int: ...
def matrix_rows(registry) -> list[str]: ...   # Phase 6 generator
```

**Design decisions.** ADR-001 (key), ADR-002 (ordering/TUNE fields), ADR-005 (no render
consumer). Initial classes come from RESEARCH Table 1; every TUNE `source` string carries
`Side-preset only, n=<N>` per SPEC constraint.

**Data flow.** Test-time only. No runtime path reads the registry.

**API changes.** None public. New module is importable (`harness_maker.step_sensitivity`)
but not a CLI entrypoint.

## 📝 Implementation Plan

### Phase 1 — Registry module + coverage tests (S1, S2)
**Status:** DONE — A.5 round 1 FAIL (2 negative controls missing) → round 2 PASS; 82 entries (77 in `ARMS` union after Phase 3 + 5 `renders_when`); unsourced 39/82.
- `depends_on`: []
- `parallel_group`: serial-1
- `merge_hazards`: none
- **Scope in:** `src/harness_maker/step_sensitivity.py`; `tests/structural/test_step_sensitivity_registry.py` (`test_every_rendered_heading_is_classified` over `ARMS`, `test_unclassified_heading_fails`, `test_registry_validates`, `test_registry_has_no_orphan_entries` (exempting `renders_when` entries), `test_extractor_matches_headings_helper`). Registry populated for every heading in `union(ARMS)`: Table-1-backed entries with their grade/source; the rest with `grade="unsourced"` (ADR-009); toggle-gated headings (review 3.5/3.6, verify Check 6 — spec-driven arm only, so it IS in the union; verify/wrapup Step 0.5, review Phase 0) with `renders_when` (ADR-007). Module docstring records the re-derived census and the arm it came from.
- **Scope out:** any template edit; Side test.
- **Exit:** `uv run pytest tests/structural/test_step_sensitivity_registry.py -q` green; `uv run mypy --strict src/harness_maker/step_sensitivity.py`; `ruff check`; `unsourced_count()` printed in the phase receipt.
- **Risk:** medium (ordinal variants across arms; level-2 headings).
- **Rollback:** delete the two new files.

### Phase 2 — Side/Production consistency test (S3)
**Status:** DONE (same TDD cycle as Phase 1) — per-preset answers via `interview._build_answers`; 5 knobs differ (floor ≥3); negative control on `max_review_rounds=4`.
- `depends_on`: [1]
- `parallel_group`: serial-2
- `merge_hazards`: none
- **Scope in:** `test_side_defaults_consistent_with_registry` in the same test file, built on two per-preset answers objects (ADR-008) with the non-vacuity floor (≥3 knobs differ); `knob`/`source_kind`/`ordering` populated for (as shipped after review): `reviewers.max_review_rounds` (yaml, le), `conditional_router.mandatory_lenses` (python, subset), `interview.main_loop.max_rounds` (yaml, le, None=∞), `worktree.enabled` (yaml, bool_off), `second_opinion.models` (yaml, `equal_by_design`). `reviewers.enabled` / `reviewers.consensus` were planned but dropped in review: neither is read at runtime.
- **Scope out:** changing any default.
- **Exit:** test green on current defaults; `test_side_more_aggressive_fails` mutates the Side answers object (`max_review_rounds=4`) and fails; `test_side_consistency_is_not_vacuous` fails when the two configs are identical.
- **Risk:** low.
- **Rollback:** Phase 1 state.

### Phase 3 — Delete the 5-term ceremony (S4, ADR-004, ADR-006)
**Status:** DONE — A.5 round 1 FAIL (comprehension test rendered at depth `standard`; block is `deep`-gated) → round 2 PASS. `test_schema_migration::test_stage_template_reads_config_not_hardcoded` pinned the deleted ceremony and was rewritten to pin the surviving cap sentence (consumer parity, checklist item 2). Snapshots regenerated in the worktree (`tests/snapshot/regenerate.py`, worktree-invariant).
- `depends_on`: [1]
- `parallel_group`: serial-3
- `merge_hazards`: `tests/structural/test_instruction_preservation.py::_ALLOWED_REMOVALS` (Phase 4 appends to the same dict)
- **Scope in:** delete `agents/_partials/inequality_gate_block.md.j2`; edit `stages/research.md.j2` Phase 0.5, `stages/spec.md.j2` §2.5, `stages/plan.md.j2` Step E (keep exit conditions), `commands/hm/loop.md.j2` §4-H (section rewrite; re-check the 4-B/4-E/4-F ordering prose), `stages/review.md.j2` mention, `agents/_partials/comprehension_block.md.j2:61` sentence; keep the cap sentence in each stage; add every removed runtime line to `_ALLOWED_REMOVALS` under keys `research@*`, `spec@*`, `plan@*`, `loop@*` for both dev_modes; **no baseline regen** (ADR-006); new `tests/unit/test_render_inequality_gate_removed.py` asserting absence of `5-Term Inequality Gate`, `5-term`, `EIG`, `CLARITI` and presence of the cap sentence in rendered research/spec/plan/loop on both arms; delete the registry entries for removed ordinals (orphan test enforces).
- **Scope out:** `interview.deep_gate` schema, `inequality_gate.py`, `eig.py`, their tests.
- **Exit:** `uv run pytest tests/unit/test_render_inequality_gate_removed.py tests/structural/test_instruction_preservation.py tests/structural/test_step_sensitivity_registry.py tests/unit/test_render_loop*.py -q` green.
- **Risk:** **high** — `loop.md.j2` §4-H is a ~40-line section in the autoloop driver, not a mention.
- **Rollback:** Phase 2 state (git revert of the template commit).

### Phase 4 — Delete verify Check 1b (S5, ADR-003, ADR-006)
**Status:** DONE — A.5 round 1 PASS (one pre-passing preservation test justified in the module docstring).
- `depends_on`: [3]
- `parallel_group`: serial-4
- `merge_hazards`: `_ALLOWED_REMOVALS` (append after Phase 3's entries), `stages/verify.md.j2` numbered procedure (`Run Check 1` line stays)
- **Scope in:** `stages/verify.md.j2` Check 1 → 1a only, retitled `Check 1 — Drift verdict (REVIEW present)`, plus the `:35` inputs line and the `:44` "→ proceed to 1b" residue (ADR-003); `_ALLOWED_REMOVALS` for `verify@spec-driven` and `verify@task-driven`; **no baseline regen**; new `tests/unit/test_render_verify_check1_removed.py` with `COMMON_CHECK_TITLES` (Checks 1–5, both arms) and `SPEC_DRIVEN_ONLY_TITLES` (Check 6, spec-driven arm), plus the negative `task-driven render contains no spec_need` assertion mirrored from `test_instruction_preservation.py:305`.
- **Scope out:** Checks 2–6 bodies, `--force`, delegation brief.
- **Exit:** `uv run pytest tests/unit/test_render_verify_check1_removed.py tests/unit/test_verify_delegation.py tests/structural/test_instruction_preservation.py -q` green on both arms.
- **Risk:** low.
- **Rollback:** Phase 3 state.

### Phase 5 — BASELINE-DELTA document (S6, in-task half)
**Status:** DONE — delta measured against **base live** (the frozen baseline was already behind `main` before this task: verify −1 485, review +958, plan +449, wrapup +448 — earlier PLANs' drift). This task: −8 222 chars on both variants at the approved artifact (−9 168 before the review rounds re-added prose), `round_trips` unchanged.
- `depends_on`: [4]
- `parallel_group`: serial-5
- `merge_hazards`: none (baselines untouched — ADR-006)
- **Scope in:** measure the live render against the frozen `surface_baseline.json` (`tests/structural/_surface_baseline.py` has a measure/compare path; use it read-only) and write `work-docs/BASELINE-DELTA-workflow-steps-vs-model-capability.md` attributing the negative delta per command (research/spec/plan/loop/verify), with an explicit "re-freeze deferred to Phase 7 on base" section and **no** `surface_allowance` entry.
- **Exit:** `uv run pytest tests/structural/test_baseline_delta_attribution.py tests/structural/test_command_size_budget.py tests/structural/test_surface_baseline.py -q` green; measured delta < 0 recorded in the doc.
- **Risk:** low.
- **Rollback:** Phase 4 state.

### Phase 6 — Docs: MATRIX column + CLAUDE.md section (S7)
**Status:** DONE — MATRIX appendix generated from `matrix_rows()` (82 rows); CLAUDE.md +23 lines (425/500).
- `depends_on`: [1]
- `parallel_group`: docs
- `merge_hazards`: `CLAUDE.md` (shared with other in-flight tasks — keep the edit to one new `##` section)
- **Scope in:** add a `class` column to the three tables in `MATRIX-native-redundancy.md` (values from the registry; a small generator function in `step_sensitivity.py` prints the rows so the doc and code cannot drift); new CLAUDE.md section `## Step sensitivity classes (COMP / HOST / INV / TUNE)` naming the four classes, the `Side-preset only, n=` caveat, the "no render consumer" fact (ADR-005), and the re-measure procedure; `test_docs_carry_classes`.
- **Exit:** `uv run pytest tests/structural/test_step_sensitivity_registry.py::test_docs_carry_classes -q` green (checks the four class names, the `Side-preset only` caveat, the `unsourced` count, and the ADR-007 "toggle arms not covered" sentence); CLAUDE.md line count still ≤ 500.
- **Risk:** low.
- **Rollback:** Phase 5 state.

### Phase 7 — Post-land re-freeze on base (S6, second half; ADR-006)
**Status:** DONE (2026-09-13, post-land) — attempted 2026-09-12 and reverted, then executed from `/home/noel/harness-maker` on `main` at `2ff7f035`. `assert_sha_is_durable` passed on BOTH attempts; the blocker ADR-006 did not anticipate is that a **peer PLAN in flight holding a `surface_allowance`** makes a wholesale re-freeze illegitimate — it folds that PLAN's unlanded growth into the frozen figures while its allowance stays live, funding the remainder twice. The peer (`token-efficiency-autopilot-ux-speed`) landed 2026-09-13 and its allowance expired, so the freeze became legitimate and ran: claude 435 437 → 427 617, codex 370 292 → 362 440, both baselines re-based, 23 moved keys attributed per owner. Evidence: `BASELINE-DELTA-workflow-steps-vs-model-capability.md`.
- `depends_on`: [5, 6]
- `parallel_group`: serial-7-post-land
- `merge_hazards`: `tests/structural/surface_baseline.json`, `tests/structural/instruction_baseline.json` (both regenerated at the landed `main` SHA)
- **Scope in:** after `/hm:wrapup` squash-lands `hm/workflow-steps-vs-model-capability`, from `/home/noel/harness-maker` on `main`: run both freezers (`python tests/structural/_surface_baseline.py`, `python tests/structural/_instruction_baseline.py`), append the closing measured row to the DELTA doc, remove the now-frozen strings from `_ALLOWED_REMOVALS` only if the preservation test's policy says landed removals are pruned (read its docstring first — it may require keeping them), commit `chore(baseline): re-freeze after workflow-steps-vs-model-capability`.
- **Scope out:** any template or registry change.
- **Exit:** `assert_sha_is_durable` passes (freeze SHA is on `main`); `uv run pytest tests/structural -q` green on `main`.
- **Risk:** low (mechanical), but it is **not** executed by `/hm:execute` in the worktree — `/hm:wrapup` must surface it as the post-land follow-up.
- **Rollback:** revert the single baseline commit.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/models.py` — no new or removed `harness.yaml` key (SPEC constraint).
- `src/harness_maker/interview.py` — Side/Production defaults are checked, not derived (ADR-005).
- `src/harness_maker/inequality_gate.py` — Python gate stays; only prose is removed (ADR-004).
- `src/harness_maker/eig.py`
- `src/harness_maker/templates/stages/execute.md.j2` — C.0 / D.5 explicitly out of scope.
- `src/harness_maker/templates/stages/wrapup.md.j2`
- `src/harness_maker/templates/harness-yaml/` — no default changes; `second_opinion.models` stays `[]`.
- Advisory: verify Checks 2–6 keep their numbers and bodies; only Check 1's body shrinks.
- Advisory: the `Check 1 —` heading prefix survives (position test in `test_verify_delegation.py`).
- `tests/structural/surface_baseline.json` — not regenerated inside the task (ADR-006; Phase 7 on base only).
- `tests/structural/instruction_baseline.json` — same.
- `tests/structural/test_command_size_budget.py` — `headings()` is reused, never re-declared (ADR-001).

## 🧪 Testing Strategy

- **Unit / structural (pytest):** S1–S5, S7 as named in SPEC; plus `test_registry_validates`,
  `test_registry_has_no_orphan_entries`, `test_extractor_matches_headings_helper`,
  `test_side_consistency_is_not_vacuous`, `test_side_more_aggressive_fails` (negative control).
- **Existing gates re-run per phase:** `test_instruction_preservation.py`,
  `test_baseline_delta_attribution.py`, `test_command_size_budget.py`, `test_verify_delegation.py`,
  `test_schema_migration.py` (proves config keys untouched), `test_inequality_gate.py`.
- **Full suite** once at Phase 6 end, in background (memory: ~6 min, never poll).
- **Manual:** render this repo's harness with `hm make --update` in the worktree and diff
  `.claude/commands/hm/{research,spec,plan,verify}.md` — expect only the two deletions.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ordinal collisions or heading variants across arms break the extractor | medium | Phase 1 red | per-stage uniqueness assertion; ordinals derived from the shared `headings()` helper; renders over `ARMS` |
| `loop.md.j2` §4-H rewrite regresses autoloop text | **medium** | high | section rewrite with 4-B/4-E/4-F ordering re-checked; `test_render_loop_*` suite + instruction-preservation allowlist + residue-string test |
| A freezer is run inside the worktree despite ADR-006 | medium | hard RuntimeError (`assert_sha_is_durable`) | Phases 3–5 say "no baseline regen" in scope; Phase 7 names the base checkout |
| S3 passes vacuously because both configs are identical | low (after ADR-008) | gate does not bind | `test_side_consistency_is_not_vacuous` floor ≥3 differing knobs |
| Toggle-gated headings gain unclassified children | medium | invisible until follow-up | ADR-007 states the gap in CLAUDE.md; follow-up named |
| Instruction-baseline allowlist typo silently never matches (`hm` spelling note in the test) | medium | Phase 3/4 red | copy strings from the failing test output verbatim |
| CLAUDE.md exceeds 500 lines | low | context-lint warn | one compact section; measure with `wc -l` in exit criterion |
| Registry classes drift from RESEARCH Table 1 | low | doc/code mismatch | Table 1 is the golden; `test_docs_carry_classes` reads MATRIX rows from the generator |
| Concurrent task edits `CLAUDE.md`/`instruction_baseline.json` | medium | land conflict | `task-refresh` before wrapup; keep edits section-local |

## ✅ Success Criteria

- [x] S1 `test_every_rendered_heading_is_classified` green over `ARMS` (2 presets × 2 dev_modes); extractor matches `headings()`
- [x] S2 `test_unclassified_heading_fails` names stage + heading
- [x] S3 `test_side_defaults_consistent_with_registry` green; non-vacuity floor holds; negative control fails
- [x] S4 no `5-Term Inequality Gate` / `5-term` / `EIG` / `CLARITI` in rendered research/spec/plan/loop; cap sentence present
- [x] S5 verify has no `PLAN/SPEC satisfaction`; Checks 1–5 on both arms, Check 6 on spec-driven only; `Check 1 —` prefix survives
- [x] S6 measured delta < 0 recorded in `BASELINE-DELTA-workflow-steps-vs-model-capability.md` (Phase 5); both baselines re-frozen on `main` after land (Phase 7, executed post-land at `2ff7f035` once the peer PLAN's allowance expired)
- [x] S7 MATRIX class column + CLAUDE.md section with the four classes, `Side-preset only` caveat, `unsourced` count, and the ADR-007 coverage gap statement
- [x] `ruff check`, `ruff format --check`, `mypy --strict` clean; full pytest green

## 📎 Execution notes

- **Pre-existing failures, out of scope (verified on the base checkout):**
  `tests/render/test_render_roundtrip_collapse.py::test_the_wrapup_git_tail_is_three_calls` fails on
  `main` @ 51b5bbfb (wrapup tail is four `!` calls); `mypy --strict tests` reports
  `tests/structural/test_command_size_budget.py:654` (`second_opinion` dict vs `SecondOpinionConfig`).
  Neither file is in this task's scope; both are named here so the next reader does not attribute them.
- **Base dirt for wrapup:** `hm mutation_receipt record` files at the BASE repo by design, so
  `/home/noel/harness-maker/.claude/observability/mutation-receipts.jsonl` (tracked) is modified on
  `main` with one row for `test_step_sensitivity_registry.py::test_every_rendered_heading_is_classified`
  (deletes `src/harness_maker/step_sensitivity.py:349`). `task-land` self-aborts on a dirty base:
  commit that row on base first (precedent `b778e524 chore(observability): commit the mutation
  receipts …`) or stash → land → pop → amend (memory `project_wrapup_memory_base_seam`).
- **Autopilot golden re-based** with an attributed `rebases` row (final per-arm −8 222 / −8 360 /
  −8 234 / −8 234 after the review rounds) — see the DELTA doc; no advance/picker bytes moved.
- **/hm:review run 2 (2026-09-12, `e06a3b304e71`): APPROVED** — round 1 C → round 2 A (5 P1 + 4 P2 fixed), confirm-1 clean + gate-driven repair round, confirm-2 clean. Accepted-pending P2/P3 (all doc/test-hygiene) listed in REVIEW §run 2 confirm-2; `docs/HOW-IT-WORKS*.md` verify-output lines and the C2/C3 provenance tags are follow-ups.
- **/hm:review run 1 (2026-09-12, `a018216f139a`):** round 1 grade C → round 2 grade A (4 P1 fixed);
  confirmation pass confirm-1 found 6 P1 (three in base commit 51b5bbfb's code inside the review
  span) → repair round; confirm-2 found **3 new P1** (two caused by the repair round itself) →
  **CHANGES_REQUESTED, human_review_needed=true**. Surviving P1s and their one-line remedies are in
  `work-docs/REVIEW-workflow-steps-vs-model-capability-2026-09-12.md` §confirm-2. The next
  `/hm:review` (or a manual fix) must: drop the retry loop in `io_utils.atomic_append`, gate the
  verify `--no-tdd` note on preset, and repoint the five `_LEDGER` TUNE `measure_cmd`s at a
  stage-agent aggregation.
- **Phase D.5:** no PLAN phase repaired a defect (all deletions or new code); no newly-reachable
  window to declare.
- **Phase C.0:** not triggered for the same reason.

## 🔍 Plan Validation

**Pass 1 (plan-validator, Claude-only):** `MAJOR_REVISION` — 3 critical, 4 major, 5 minor.
**Cross-model second opinion:** codex `skipped` (exit 1: CLI usage limit until 2026-09-15 16:51). No injected findings; reconciliation empty.
**Pass 2:** not run — this repo's policy is a single validator pass (memory `feedback_plan_validator_single_pass`); all critiques were dispositioned by the user in Interview #9–#12 and the PLAN revised accordingly. `validator_outcome: MAJOR_REVISION_RESOLVED` records that a human dispositioned every finding.

| # | Sev | Critique (short) | Disposition | Resolution |
|---|---|---|---|---|
| 1 | critical | Baseline regen in worktree impossible (`assert_sha_is_durable`) | A revise | ADR-006 rewritten; Phase 5 = DELTA doc only; new Phase 7 post-land on base; SPEC S6/AC-006 amended |
| 2 | critical | S3 vacuous (`synthesize(preset=)` does not vary answers knobs) | A revise | ADR-008: per-preset answers + non-vacuity floor; negative control mutates answers |
| 3 | critical | Coverage contract impossible on preset×target; toggle-gated headings | A' revise | ADR-007: `ARMS` = preset×dev_mode; `renders_when`; toggle arms deferred + stated in CLAUDE.md |
| 4 | major | `DETERMINISTIC_CHECK_TITLES` includes spec-driven-only Check 6 | A revise | Phase 4 splits `COMMON_CHECK_TITLES` / `SPEC_DRIVEN_ONLY_TITLES` + negative task-driven assertion |
| 5 | major | loop §4-H is a full section; comprehension_block ×8; residue strings | A revise | ADR-004 + Phase 3 scope; risk raised to high; S4 asserts residue absence |
| 6 | major | Second narrower heading extractor; level-2 `## Phase 0` missed | A revise | ADR-001: reuse `headings()`; `test_extractor_matches_headings_helper` |
| 7 | major | ~40 headings unsourced; guessed vs classified indistinguishable | A revise | ADR-009: `unsourced` grade + surfaced count |
| 8 | minor | `mandatory_lenses` is python, not yaml | A revise | ADR-002 `source_kind` |
| 9 | minor | empty-vs-empty subset never fails | A revise | ADR-002 `equal_by_design`; non-vacuity floor |
| 10 | minor | verify `:35`/`:44` residues | A revise | ADR-003 + Phase 4 scope |
| 11 | minor | `templates-A` parallel label vs serial prose | A revise | Phase 4 `depends_on: [3]`, serial groups |
| 12 | minor | `measure_cmd` shape-only validation | A revise | ADR-002 repo prefix + recorded limitation |
