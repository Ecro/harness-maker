---
type: plan
task_slug: plan-interview-comprehension
status: complete
created: 2026-08-13
tags: [harness-maker, plan, jinja2, python, interview, plan-stage, harness-yaml]
spec: "[[SPEC-plan-interview-comprehension]]"
research_doc: "[[RESEARCH-plan-interview-comprehension]]"
interview_rounds: 6
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Disclose the plan/spec interview's design picture via one interview.comprehension.depth ordinal"
---

# PLAN — Plan/spec interview comprehension depth

> **EXECUTE STATUS (stage exit).** Phases 0, 1, 2 and 3a **DONE**. Full suite: **2 failures**,
> both the ones Phase 3a's exit criterion names as expected-RED —
> `test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow` and
> `test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`.
> Both require the regenerated `surface_baseline.json`, which `assert_sha_is_durable` refuses
> from a task branch by design. **Phase 3b is the owned follow-up and must run at base after
> the land** — until it does, `main` carries those two RED. `ruff check`, `ruff format --check`
> and `mypy --strict src` are clean. No commit was made from this stage.

## 🎯 Executive Summary

**What:** add `interview.comprehension.depth: minimal | standard | deep` to `harness.yaml`, render a
stage-parameterized disclosure partial into `/hm:plan` and `/hm:spec`, wire `/hm:configure` (prose
**and** the CLI flag behind it) as the entry point, and reconcile the frozen-baseline gates a
rendered-template edit trips.

**Why:** `/hm:plan` Step 1 already builds the whole design picture — architecture, phase
decomposition, blast-radius-ranked ambiguities — under a heading that says *"NOT shown to user"*,
and Step A's round-state block is explicitly optional and skippable. The user answers architectural
questions through a keyhole. This is a disclosure defect, not a generation defect, so the fix is
mostly re-routing output that already exists.

**Key decisions:** one ordinal, not four booleans ([ADR-001](#adr-001-one-ordinal-interviewcomprehensiondepth-not-four-booleans));
an explicit read-side overlay because `answers_from_harness_yaml` does **not** round-trip the
`interview` block ([ADR-002](#adr-002-answers_from_harness_yaml-gets-an-explicit-read-side-overlay-for-depth));
`/hm:configure` **plus a real `cli.py` flag** ([ADR-003](#adr-003-hmconfigure-is-the-entry-point--and-needs-a-real-cli-flag-behind-it));
unknown depth normalizes to `standard` with a warning, and the typo is overwritten on the next
re-render ([ADR-004](#adr-004-unknown-depth-normalizes-to-standard-with-a-warning-and-the-typo-does-not-survive));
regeneration of `surface_baseline.json` with attribution is the sanctioned path — rebaselining to
green a *net-surface* assertion is not ([ADR-005](#adr-005-regenerate-and-attribute-is-allowed-rebaseline-to-green-a-net-surface-assertion-is-not));
existing installs are **retrofitted** to `standard` on re-render, by design
([ADR-006](#adr-006-existing-installs-are-retrofitted-to-standard-on-re-render));
the partial takes a `stage` argument and AC-006 asserts the enabled block *set*, not the text
([ADR-007](#adr-007-the-partial-is-stage-parameterized-ac-006-asserts-the-block-set));
and Step A's "visualization OPTIONAL" sentence is *replaced* under the depth branch
([ADR-008](#adr-008-step-as-optional-sentence-is-replaced-under-the-depth-branch)).

**Estimated impact:** 3 Python modules, 2 harness-yaml templates, 1 new partial, 2 stage templates,
1 command template, 4 new test files, 1 new immutable golden fixture, plus the gate artifacts in
Phase 3a and a required post-land Phase 3b. No pydantic model change.

## 📚 Prior Work

- `[[RESEARCH-plan-interview-comprehension]]` — located the hidden Step 1 draft and the optional
  Step A block; established that adding questions (tuning `deep_gate`) is the wrong lever.
- `[[SPEC-plan-interview-comprehension]]` — 6 ACs, six G-W-T scenarios. Amended during Step 4 (see
  ADR-006 / ADR-007).
- `[[PLAN-deep-interview-question-criteria]]` (0.16.0) — introduced the 5-term inequality gate and,
  in its ADR-012, froze ε/τ/cap as **code constants**. That decision is precisely why the
  `interview` block has no generic round-trip and why ADR-002 is required.
- `[wiki:architecture] onboarding-disclosure-and-six-gates` — a rendered-template edit trips
  multiple frozen gates, most found by tripping them mid-execution. Phase 3a's explicit
  `file::symbol` table exists to stop that repeating.
- `[fail:design] promoted-default-reaches-bare-callers` — a class-default flip is an enumeration
  task. Mitigated by introducing a **new** key rather than flipping an existing default.
- CLAUDE.md Learned Corrections 2026-06-08 — absent-case = feature black hole (`count:8`).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Case A brief lock-in | Scope | Proceed to phases, or lock the remaining architecture decision? | phases / configure-entry-first / full interview | configure entry first | Surfaced two code facts: no `interview` round-trip, no `interview` axis in `/hm:configure` | — |
| 2 | Config entry point | Contract shape | How far do we build the path for changing `depth`? | hand-edit only / `/hm:configure` axis / axis + install question | `/hm:configure` axis | Rejected the install question — conflicts with "default `standard` works" from the SPEC interview | ADR-003 |
| 3 | Unknown depth value | Failure handling | What happens on a typo like `verbose`? | fallback `standard` + warn / fallback `minimal` + warn / hard error | fallback `standard` + warn | Matches the warn-and-ignore precedent for deprecated `deep_gate` keys and unknown locales | ADR-004 |
| 4 | Absent key on existing installs | Scope boundaries | What does a `harness.yaml` with no `comprehension` key do on re-render? | acquire `standard` (retrofit) / stay `minimal` (preserve) | acquire `standard` | Raised by both second-opinion models and confirmed by the validator: the old Non-Goal was factually false | ADR-006 |
| 5 | `/hm:spec` applicability | Architecture | `/hm:spec` has no hidden design draft and already has a round preamble — what happens to AC-006? | stage-parameterized partial / brief is plan-only / drop spec entirely | stage-parameterized partial | Validator found the §2.3 duplication that neither model saw | ADR-007 |
| 6 | Step A conflict | Contract shape | `plan.md.j2:352` says "visualization OPTIONAL"; `round_state` says required-when-changed | replace the sentence under the depth branch / append with a precedence note / weaken to "strongly recommended" | replace under the branch | ADR-005's rejected-alternative had forbidden prose edits; this is a scoped exception | ADR-008 |

Inherited from the SPEC interview (not re-asked): ordinal vs booleans, stage scope, new-install
default, brief delivery, `teach_back` gating, oracle style, surface-cost policy.

5-term gate before Step 4: 4 candidates generated, 0 passed (partial location, `/hm:health`
advisory, phase ordering, and this repo's own depth value were all common-ground or below ε).
Rounds 4-6 are Step 4 follow-up rounds driven by the validator's critical critiques.

## 📐 Architecture Decision Records

### ADR-001: One ordinal `interview.comprehension.depth`, not four booleans
**Status:** Accepted (2026-08-13, via /hm:spec + /hm:plan interview)
**Context:** The disclosure feature has four separable levers (brief, round_state, decision_depth,
teach_back). Exposing all four multiplies the `/hm:configure` surface and the rendered branch count.
**Decision:** Ship a single ordinal `depth: minimal | standard | deep`. `minimal` = today's
behavior; `standard` = brief + round_state; `deep` = all four. No per-lever override keys.
**Consequences:**
- ✅ One `/hm:configure` question, one template branch chain, one value to round-trip.
- ✅ Levels are ordered, so a future level can be appended without a migration.
- ⚠️ "teach_back only" is inexpressible. Accepted — the ordinal can be decomposed later without
  invalidating existing files, since the ordinal remains a valid input.
**Rejected alternatives:**
- Four independent booleans — Rejected: the honesty gain about token cost does not pay for 4× the
  configure surface on a feature whose levers are naturally ordered.
- `depth` + per-lever overrides — Rejected: adds a precedence rule and doubles the absent-case
  branches, which is the repo's most-recurring failure class.
**Source:** SPEC interview Round 1

### ADR-002: `answers_from_harness_yaml` gets an explicit read-side overlay for `depth`
**Status:** Accepted (2026-08-13, via /hm:plan interview)
**Context:** `answers_from_harness_yaml` does not round-trip the `interview` block. It rebuilds the
whole block from `_preset_extras` (`interview.py:1522` / `:1549`) and applies exactly one read-side
overlay, for `common_ground.llm_inference_enabled` (`:1281-1300`) — because 0.16.0's ADR-012
declared ε/τ/cap to be code constants. A key added to `_preset_extras` alone would be **silently
reset to the preset default on every `/harness-maker:make --update`**.
**Decision:** Add `comprehension.depth` to both `_preset_extras` branches **and** an explicit
read-side overlay next to the existing `llm_inference_enabled` overlay. SPEC AC-005 is the
regression gate.
**Consequences:**
- ✅ A user's chosen depth survives re-render — the failure mode that silently reverted hand-edited
  `scope`/`branch_prefix` before 0.48.0 cannot recur here.
- ⚠️ The overlay list grows to two entries. A third addition should prompt a generic round-trip
  mechanism rather than a third hand-wired overlay.
**Rejected alternatives:**
- Rely on `_preset_extras` alone — Rejected: verified by reading the function; it does not read the
  file's `interview` values back.
- Make the whole `interview` block generically round-tripped — Rejected: reverses 0.16.0 ADR-012 for
  ε/τ/cap as a side effect of an unrelated feature.
**Source:** Interview #1 (code investigation before the round)

### ADR-003: `/hm:configure` is the entry point — and needs a real CLI flag behind it
**Status:** Accepted (2026-08-13, via /hm:plan interview; scope corrected in Step 4)
**Context:** `/hm:configure` has no `interview` dimension, so a new key would be hand-edit-only. The
repo has a recorded case of an axis silently disabled at install with no way to turn it on short of
editing `harness.yaml`. **Correction from validator C4:** `configure.md.j2:161-186` is pure prose
that dispatches `hm cli make "$(pwd)" --<flag> "$VALUE"` and relies on "omit every flag whose
dimension wasn't selected — the CLI preserves unspecified fields". A prose-only dimension would
tell the user to pass a flag that does not exist, while a render-grep success check passed.
**Decision:** Add the `/hm:configure` dimension **and** the `cli.py` flag it dispatches to: choice
validation against `{minimal, standard, deep}`, `_build_answers` wiring, and the omit-preserves
path. Do **not** add a fresh-install interview question.
**Consequences:**
- ✅ The axis is genuinely changeable without hand-editing; the success criterion is a CLI test, not
  a grep.
- ✅ Fresh-install question count is unchanged.
- ⚠️ `cli.py` joins the change set, and `configure.md.j2` prose growth lands on the same ratchet.
**Rejected alternatives:**
- Hand-edit only — Rejected: reproduces the silently-undiscoverable-axis failure.
- Prose-only configure dimension — Rejected: unimplementable; this is exactly the defect ADR-003
  exists to prevent, reintroduced one layer down.
- Axis + install question — Rejected: contradicts the SPEC decision that `standard` is good enough
  not to ask about.
**Source:** Interview #2; scope corrected by validator critique C4

### ADR-004: Unknown `depth` normalizes to `standard` with a warning, and the typo does not survive
**Status:** Accepted (2026-08-13, via /hm:plan interview; consequences corrected in Step 4)
**Context:** A typo (`verbose`, `full`) must not brick every `/hm:` command, and must not silently
disable the feature either.
**Decision:** Validate against `{minimal, standard, deep}` in `answers_from_harness_yaml`; anything
else logs one warning **per `answers_from_harness_yaml` call on a given path** — naming the file,
the offending value, and the fact that the value will be rewritten — then proceeds as `standard`.
**Consequences:**
- ✅ Matches the existing warn-and-ignore precedent; no other `harness.yaml` key hard-fails the load.
- ✅ Fail-open means the user still gets the disclosure they were configuring.
- ⚠️ **The typo is destroyed on the first `--update`.** Normalization happens on read and the
  harness-yaml emitters re-emit from `config`, so `depth: verbose` becomes `depth: standard` on
  disk and the warning can never fire again. The earlier wording ("until they read the warning")
  assumed a persistence that does not exist. The warning text therefore states the rewrite
  explicitly — that sentence is the only notice the user ever gets.
- ⚠️ "Once" is scoped per call, not per process; `answers_from_harness_yaml` runs more than once per
  make, so a make may print the warning more than once. Accepted over adding warning-state.
**Rejected alternatives:**
- Fall back to `minimal` — Rejected: one typo silently disables the feature — the `count:8`
  absent-case black-hole shape.
- Hard error — Rejected: no other `harness.yaml` key is treated that way.
- Preserve the raw value on re-emit — Rejected: would make the emitters carry a value the rest of
  the system has already normalized away, i.e. two sources of truth for one key.
**Source:** Interview #3; consequences corrected by validator critique C9

### ADR-005: "Regenerate and attribute" is allowed; "rebaseline to green a net-surface assertion" is not
**Status:** Accepted (2026-08-13, via /hm:spec interview; wording corrected in Step 4)
**Context:** The earlier wording said growth is paid "never by re-freezing the ratchet", which
contradicted this PLAN's own Phase 3 scope. The repo's actual rule is narrower and written down:
`test_surface_baseline.py:390` sanctions *"Regenerate with `python tests/structural/_surface_baseline.py`
in the SAME commit that changed the template, and attribute the movement in a BASELINE-DELTA row"*,
while `test_plan_net_surface.py:83` forbids rebaselining to make a **net-surface** assertion pass.
**Decision:** Regenerate `surface_baseline.json` via its generator, in the same commit as the
template change, with a `work-docs/BASELINE-DELTA-plan-interview-comprehension.md` attribution row
per changed command. Do **not** hand-edit the baseline, and do **not** rebaseline to green a
net-surface assertion — that assertion gets an xfail waiver citing the delta row instead.
`depth: minimal` must render byte-identically to the pre-change output (AC-003), so a third-party
opt-out install pays exactly zero.
**Consequences:**
- ✅ The ratchet keeps measuring real growth; the cost is argued in a reviewable document.
- ✅ Third-party cost is provably zero, which is what makes the maintainer's cost defensible.
- ⚠️ This repo (the fleet) pays the growth on every `/hm:plan` and `/hm:spec`, and — per ADR-006 —
  so does every existing install on its next re-render.
- ⚠️ `assert_sha_is_durable` refuses to record a SHA a squash-land will delete, so the regeneration
  itself cannot complete inside the task branch. That is why Phase 3b exists as an owned step
  rather than a risk row.
- ⚠️ **A scoped exception to the "no prose deletion" stance below**: ADR-008 replaces one existing
  sentence in `plan.md.j2`, under the depth branch only.
**Rejected alternatives:**
- Offset by cutting existing `plan.md.j2` prose wholesale — Rejected: deleting load-bearing
  instruction text to buy budget is how an unrelated regression gets introduced. (ADR-008 is a
  single conditional replacement, not a cut.)
- Pin this repo to `minimal` — Rejected: abandons dogfooding of a feature whose premise is that the
  maintainer also cannot see the whole picture.
**Source:** SPEC interview Round 2; wording corrected by validator critique C11

### ADR-006: Existing installs are retrofitted to `standard` on re-render
**Status:** Accepted (2026-08-13, via /hm:plan Step 4 follow-up)
**Context:** The SPEC listed "not retrofitting existing installs" as a Non-Goal. That was
**factually false**: `answers_from_harness_yaml` rebuilds `interview` from `_preset_extras`, so a
file with no `comprehension` key acquires the preset default on every `--update`. AC-004 states the
outcome explicitly. Left ambiguous, an executor had two opposite legal implementations with
opposite surface costs — and `_surface_baseline.py:105` renders through that same function, so this
repo's own baseline moves without anyone editing `.claude/harness.yaml`.
**Decision:** Absent key → `standard`, for both fresh installs and existing files. The Non-Goal is
deleted from the SPEC and replaced with the explicit retrofit statement. The opt-out is
`depth: minimal`, reachable via `/hm:configure`.
**Consequences:**
- ✅ One code path, no fresh-install-vs-existing discriminator (no such signal exists today).
- ✅ Every existing user gets the disclosure without reading a changelog.
- ⚠️ Every existing install's `/hm:plan` and `/hm:spec` grow on the next re-render, unannounced
  except by the CHANGELOG entry.
- ⚠️ Because the absent branch and the fresh-install branch are now the same branch, the
  count:8-guard test must exercise the **absent** path specifically (AC-004), not just the explicit
  one.
**Rejected alternatives:**
- Absent → `minimal`, fresh install → `standard` — Rejected: requires an install-context signal that
  does not exist, and leaves the feature dark for everyone who already has the plugin.
**Source:** Interview #4 (raised by codex P0 + antigravity P3, confirmed by the validator)

### ADR-007: The partial is stage-parameterized; AC-006 asserts the block set
**Status:** Accepted (2026-08-13, via /hm:plan Step 4 follow-up)
**Context:** The SPEC's AC-006 demanded `/hm:spec` carry "the same partial content" as `/hm:plan`.
Two problems: `/hm:spec` has no pre-interview internal draft (`spec.md.j2:54` Step 1 is knowledge
retrieval), so a brief instructing disclosure of "the Step 1 draft … phase skeleton" refers to an
artifact that stage never produces; and `spec.md.j2:184-196` **already** renders a "Decisions locked
in so far" round preamble, so `standard` would emit two round-state instructions.
**Decision:** The partial takes a `stage` argument. The brief's subject differs by stage —
`/hm:plan` discloses its Step 1 internal draft; `/hm:spec` discloses the inherited SPEC scope, the
AC skeleton, and which of the six categories remain open. The partial **subsumes** the existing
§2.3 preamble rather than adding to it. AC-006 is restated as "same source, same enabled block set".
**Consequences:**
- ✅ One source of truth for the block set and the level semantics; no copy that can drift.
- ✅ Each stage discloses something it actually has.
- ⚠️ The partial gains a branch per stage, so its own size grows and the "identical text" assertion
  is replaced by a weaker set-identity assertion. Accepted — text identity was asserting something
  that should not be true.
- ⚠️ `spec.md.j2`'s existing §2.3 preamble becomes conditional, which is a second scoped prose edit
  alongside ADR-008's.
**Rejected alternatives:**
- Brief is `/hm:plan`-only — Rejected: leaves the same keyhole in the SPEC interview, which the SPEC
  interview itself chose to close.
- Drop `/hm:spec` entirely — Rejected: reverses a locked SPEC decision without new evidence against
  it; the evidence was against *text identity*, not against applying the feature.
**Source:** Interview #5 (raised by codex P1, sharpened by the validator, which found the §2.3
duplication)

### ADR-008: Step A's "OPTIONAL" sentence is replaced under the depth branch
**Status:** Accepted (2026-08-13, via /hm:plan Step 4 follow-up)
**Context:** `plan.md.j2:352` is titled "Step A — Render current plan state (visualization
OPTIONAL)" and its body says the visualization is not mandatory. `round_state` says
required-when-changed. Including the partial without touching that text ships two contradicting
instructions in one command, and an LLM's choice between them is nondeterministic.
**Decision:** Under `standard`/`deep`, the depth branch **replaces** the OPTIONAL heading + sentence
with the required-when-changed wording. Under `minimal` the original text renders unchanged, so
AC-003's byte identity holds. The partial also defines "changed" (any component, boundary, phase, or
locked-decision delta since the previous round), states that Round 1 has no base and therefore emits
the full state rather than a delta, and specifies that the final round emits a delta if one exists.
**Consequences:**
- ✅ One unambiguous instruction per rendered command.
- ✅ `minimal` remains byte-identical, so the exception costs opt-out users nothing.
- ⚠️ ADR-005's "do not cut existing prose" stance now has a named exception. Any further prose
  replacement needs its own ADR — this is not a general licence.
**Rejected alternatives:**
- Append with a precedence note — Rejected: leaves two contradicting sentences and relies on the
  model resolving them the intended way.
- Weaken `round_state` to "strongly recommended" — Rejected: the block is already optional today and
  that is precisely why it does not appear; repeating the same strength repeats the outcome.
**Source:** Interview #6 (validator critique C7)

## 🏗️ Technical Design

### Current state

| Element | Location | Fact |
|---|---|---|
| Hidden design draft | `templates/stages/plan.md.j2:90` | Step 1, titled "NOT shown to user" |
| Optional round state | `templates/stages/plan.md.j2:352-377` | "Visualization is NOT mandatory"; skippable |
| Spec round preamble | `templates/stages/spec.md.j2:184-196` | **already** renders "Decisions locked in so far" |
| Spec Step 1 | `templates/stages/spec.md.j2:54` | knowledge retrieval — no architecture/phase draft |
| `interview` schema | `models.py:1215` | `dict[str, Any]`; second factory at `models.py:1374` |
| Defaults literal | `models.py:1433-1453` | `interview_deep_gate_defaults()`, documented single source |
| Preset defaults | `interview.py:1522` (Side), `:1549` (Production) | two branches |
| Reverse mapper | `interview.py:876` (function spans `:876-1302`); locator comment `:935-941`; overlay `:1281-1300` | rebuilds `interview`; one overlay only |
| Emitters | `templates/harness-yaml/{Production,Side}.yaml.j2:8-22` | identical block; **bare attribute access** |
| Configure dispatch | `templates/commands/hm/configure.md.j2:161-186` | prose → `hm cli make --<flag>`; omit preserves |
| Partial precedent | `templates/agents/_partials/inequality_gate_block.md.j2` | included by plan/spec/research |
| Baseline generator | `tests/structural/_surface_baseline.py:105` | renders through `answers_from_harness_yaml` |

### Affected components

```
models.py ──── interview_comprehension_defaults()  (new, beside deep_gate defaults)
   │                    ├──→ HarnessConfig.interview default_factory      (models.py:1215)
   │                    └──→ InterviewAnswers.interview default_factory   (models.py:1374)
interview.py ──┬── _preset_extras (Side, :1522)       ← add "comprehension"
               ├── _preset_extras (Production, :1549) ← add "comprehension"
               └── answers_from_harness_yaml          ← NEW overlay + validation (ADR-002/004)
cli.py ─────────── new --comprehension-depth flag + _build_answers wiring (ADR-003)
templates/
   harness-yaml/{Production,Side}.yaml.j2 ─→ emit `comprehension: depth: <v>`  (use default())
   agents/_partials/comprehension_block.md.j2  (new; depth-branched AND stage-parameterized)
        ├──→ stages/plan.md.j2   (brief anchored BEFORE Step 3.0, NOT before Round 1 —
        │                         plan.md.j2:341 skips all of Step 3 on the Case-A path;
        │                         also replaces Step A's OPTIONAL sentence)
        └──→ stages/spec.md.j2   (brief before §2.1; subsumes the §2.3 preamble)
   commands/hm/configure.md.j2 ─→ new dimension (ADR-003)
```

### Data flow

`harness.yaml` → `io_utils.load_harness_yaml` → `answers_from_harness_yaml` (overlay + validate +
normalize) → `InterviewAnswers.interview["comprehension"]["depth"]` → `synthesize` →
`HarnessConfig` → Jinja `config.interview.get('comprehension', {}).get('depth', 'standard')` →
partial branch → rendered `/hm:plan`, `/hm:spec`.

**The `.get()`/`| default()` rule applies to the harness-yaml emitters too**, not only the stage
templates. `Production.yaml.j2:11-20` uses bare attribute access throughout, and several tests
construct a `HarnessConfig` with a hand-built `interview` dict that would not carry the new key —
a house-style emit line there would raise `UndefinedError`.

### Partial content by level and stage

| Level | Blocks | `/hm:plan` subject | `/hm:spec` subject |
|---|---|---|---|
| `minimal` | none | — | — |
| `standard` | brief, round_state | Step 1 internal draft: goal, component/data-flow sketch, phase skeleton, ranked ambiguities with which are asked vs defaulted and why | inherited SPEC scope, AC skeleton, which of the six categories remain open |
| `deep` | + decision_depth, teach_back | per question: what it decides · what it rewrites downstream · recommended default + why · reversibility cost; then a closing readback — **output only, no response, no gate** | same envelope, anchored on AC impact instead of phase impact |

### Skip-path behavior (all four blocks)

The feature's own control flow must not repeat the absent-case class it is guarding against.

| Path | brief | round_state | decision_depth | teach_back |
|---|---|---|---|---|
| `plan.md.j2:79` Step 0 skip heuristic (no interview) | not emitted | n/a | n/a | **not emitted** — nothing was locked |
| `plan.md.j2:328` Step 3.0 Case-A skip (SPEC approved) | **emitted** — which is why the anchor is before Step 3.0, not before Round 1 (`:341` skips all of Step 3) | n/a | n/a | emitted — restates what the SPEC locked |
| loop-mode (`plan.md.j2:92` short-circuits Step 1, including its `:135` ADR halt) | not emitted (inherits the short-circuit) | n/a | n/a | not emitted — the halt note is the output |
| `plan.md.j2:151-306` §1.7 SPEC-need dispatch, then re-entry at Step 2 | emitted **once**, on re-entry only — the pre-dispatch pass has no SPEC to summarize | n/a | n/a | emitted on the re-entry pass |
| zero questions passed the gate | emitted | not emitted (no rounds) | n/a | emitted |

The Case-A row is the highest-traffic path for a spec-driven harness — an approved SPEC is the
normal `/hm:plan` entry, and it is the path this very PLAN ran. Anchoring the brief inside Step 3
would make the feature dark for most invocations while every render-grep test passed; Phase 2's
exit criterion therefore asserts the brief marker's offset **precedes** the Step 3.0 heading in the
rendered text.

### Whitespace contract (AC-003)

Stated once so the executor converges instead of bisecting: the include tag is whitespace-stripped
on both sides (`{%- include ... -%}`), the partial emits **nothing at all** at `minimal` — including
its own trailing newline — and the file's final newline is preserved by the caller, not the partial.

### API changes

None. No pydantic field is added or changed; `HarnessConfig.interview` remains `dict[str, Any]` and
`schema_version` stays at 4 (migrations key on key presence, not the recorded version).

## 📝 Implementation Plan

### Phase 0 — Capture the immutable zero-cost golden

- **depends_on:** `[]`
- **parallel_group:** `serial-config`
- **merge_hazards:** none — this phase must land **before any template edit**, or the artifact it
  captures no longer exists.
- **Scope — in:** `tests/structural/comprehension_zero_cost_golden.json` (new: SHA-256 of the
  pre-change rendered `/hm:plan` and `/hm:spec`, plus a **base-reachable** source commit SHA),
  the generator that writes it.
- **Scope — out:** everything else.
- **Exit criterion:** the golden file exists, its two digests match a fresh render of the untouched
  templates, and its recorded SHA is durable.
- **Durability (do not repeat Phase 3b's lesson inverted):** record
  `git merge-base HEAD <base>`, **not** the task-branch `HEAD`. `task-land` squash-lands and
  deletes `hm/plan-interview-comprehension`, so a task-branch SHA is unreachable at base after the
  land and absent from a fresh clone or CI — the assertion would then fail, or error out of git and
  silently skip. The writer reuses `_surface_baseline.assert_sha_is_durable`, so an undurable
  capture is refused **at Phase 0** rather than discovered after the land.
- **Comparability pins (both sides of AC-003 must match these or the SHA differs for reasons
  unrelated to the feature):** produce both renders through `_surface_baseline.render_surface()`-
  equivalent code — this repo's own `.claude/harness.yaml` with only
  `interview.comprehension.depth` overridden to `minimal`, under `pinned_install_ref()` and
  `DEFAULT_FREEZE_TIME`. A render from a synthesized default config, or without the install-ref
  pin, or without the frozen timestamp, mismatches for none of the reasons the whitespace contract
  addresses.
- **Risk:** low — but ordering is absolute.
- **Rollback point:** branch tip.

> **Why this is its own phase:** AC-003's oracle cannot be `surface_baseline.json`. That file is the
> render of *this repo's* `harness.yaml` through `answers_from_harness_yaml`, and Phase 3a
> regenerates it at the new `standard` default — after which `surface[claude][plan][chars]` records
> standard-level numbers and a minimal-vs-baseline assertion silently compares minimal against
> standard. Once the templates change there is no cheap way to re-derive the pre-change render.

> **STATUS — Phase 0: DONE.** `tests/structural/_comprehension_golden.py` +
> `comprehension_zero_cost_golden.json` captured at base-reachable SHA `01922911`
> (`assert_sha_is_durable` passed). `_surface_baseline.render_surface()` gained a
> `depth_override` parameter so both sides of AC-003 go through one render path.
>
> **STATUS — Phase 1: DONE** (A.5 gate resolved by user decision after the 2-round budget).
>
> **A.5 history.** Round 1: all three lenses FAIL — absent-case bound to `Production` only
> (both `models.py` factories unbound, and the emitter guard this PLAN made an exit
> criterion had no test at all); the `depth_override` lever from Phase 0 never exercised,
> so a no-op override would have let AC-003 go green **by identity**; and the AC-004
> differential green-by-construction, because at Phase 1 no rendered command reads the
> value. All three repaired. Round 2: red-correctness PASS, discrimination PASS, coverage
> FAIL on a defect the round-1 repair itself introduced — the new `depth_override` test
> had no `partial.exists()` guard, so Phase 1's exit could never go green. Budget
> exhausted; the user chose to apply the reviewer's prescribed guard and continue.
> Residual risk: that guard was not re-reviewed.
>
> **Two things this PLAN got wrong, found by running it:**
>
> 1. **The snapshot break is a Phase 1 event, not Phase 2.** Phase 2's known-RED list named
>    the eight `tests/snapshot/*.expected.yaml`, but they fire as soon as the **emitters**
>    change — which is Phase 1 scope. Regenerated here via
>    `uv run python tests/snapshot/regenerate.py`; the delta is exactly 8 lines, one
>    `body_sha256` per file, all on `harness.yaml`.
> 2. **A NINTH gate exists that Phase 3a's "exact `file::symbol` table" did not name** —
>    `tests/structural/test_new_gates_file_a_mutation_receipt.py`. Every new file under
>    `tests/structural/` must carry a mutation receipt, and Phase 0 added one. This is R3
>    firing exactly as written: the table was more exact than the prose it replaced and
>    still not complete. Receipt filed for real, not asserted: deleting
>    `src/harness_maker/templates/stages/plan.md.j2:2` turns
>    `test_the_golden_matches_a_pre_change_render_while_the_partial_is_absent` red;
>    verified, restored, recorded.

### Phase 1 — Config plumbing, the round-trip overlay, and the CLI flag

- **depends_on:** `[0]`
- **parallel_group:** `serial-config`
- **merge_hazards:** `src/harness_maker/interview.py` (both `_preset_extras` branches and the
  overlay are one file); the two `harness-yaml/*.yaml.j2` emitters must change together or the
  presets diverge.
- **Scope — in:** `src/harness_maker/models.py` (new `interview_comprehension_defaults()` wired into
  **both** default factories, `:1215` and `:1374`), `src/harness_maker/interview.py` (both
  `_preset_extras` branches + the read-side overlay + `{minimal,standard,deep}` validation),
  `src/harness_maker/cli.py` (`--comprehension-depth` flag, choice validation, `_build_answers`
  wiring, omit-preserves), `src/harness_maker/templates/harness-yaml/{Production,Side}.yaml.j2`
  (emit with `default()`, not bare attribute access),
  `tests/unit/test_comprehension_absent_case.py` (new),
  `tests/unit/test_comprehension_roundtrip.py` (new),
  `tests/unit/test_comprehension_cli_flag.py` (new).
- **Scope — out:** stage templates, the partial, `configure.md.j2`, every gate artifact.
- **Exit criterion:** `uv run pytest tests/unit/test_comprehension_*.py -q` passes — covering AC-004
  (absent key → `standard`, the ADR-006 branch), AC-005 (all three values round-trip), the ADR-004
  unknown-value normalization **and** its warning text, the CLI flag's valid/invalid/omitted paths,
  and a `HarnessConfig` constructed with a hand-built `interview` dict rendering the emitters
  without `UndefinedError`. `uv run mypy --strict` clean on the three modules.
- **Risk:** medium — the overlay is the one place this feature can silently fail (ADR-002).
- **Rollback point:** end of Phase 0.

> **STATUS — Phase 2: DONE.** `agents/_partials/comprehension_block.md.j2` +
> `plan.md.j2` / `spec.md.j2` includes. All 17 render-gate assertions green on the first run,
> AC-003's byte identity included. The whitespace contract held as written: `{%- include %}`
> (left-strip only), the partial owns its leading blank line, `{%- endif -%}` eats the file's
> trailing newline. Phase 0's two deferred arms self-enabled and pass — `depth_override`
> genuinely moves the render, and `minimal` reproduces the golden digest-for-digest, which
> closes the Phase D.5 window that was open at the end of Phase 1.
>
> **STATUS — Phase 3a: DONE.** `_ATOMIC_RATCHET` re-based (`plan` 47 503 → 49 050, `spec`
> 30 537 → 32 114, after a compaction pass that cut the raw +1 923 / +1 778 by 20% / 11%),
> `/hm:configure` dimension added, snapshots regenerated, BASELINE-DELTA authored with all
> seven mandated items.
>
> **Two MORE gates the "exact `file::symbol` table" did not name — R3 fired three times total:**
>
> 3. `tests/structural/test_new_gates_file_a_mutation_receipt.py` — fired **twice**, once per
>    new structural file (Phase 0's golden, Phase 2's render gate). Both receipts filed by
>    actually running the mutation: deleting `plan.md.j2:2` and
>    `comprehension_block.md.j2:5` respectively turns the named gate red; verified, restored,
>    recorded. The first attempt deleted a blank line, the gate stayed green, and that
>    non-result is why the receipt is worth anything — a receipt naming a line whose deletion
>    changes nothing would be a false receipt the ledger cannot detect.
> 4. `tests/structural/test_instruction_preservation.py` — 4 arms. **This PLAN's own note was
>    wrong about it**: it recorded "additions do not trip it; only disappearance does, so
>    nothing goes red either way", which is true in general and false for this task, because
>    ADR-007 and ADR-008 are *replacements* — i.e. disappearances. Both entered
>    `_ALLOWED_REMOVALS` under this task's key, against all four arms.
>
> **Measured delta (post-final-edit).** claude +3 190, codex +2 474 — they diverge by exactly
> the 716 the `/hm:configure` dimension costs, because `configure` has no codex variant (10
> codex keys vs 15 claude). `execute` −390 in both is **pre-existing drift** between the
> baseline's frozen `render_sha` and HEAD, not this task's. Round-trip counts unchanged on
> every command, both variants.
>
> **§1/§2 of the delta document had to be re-measured once** — they were written before the
> `configure.md.j2` edit landed, which is precisely the ordering failure that document's own
> §5 warns about.

### Phase 2 — Stage-parameterized partial and stage inclusion

- **depends_on:** `[1]`
- **parallel_group:** `serial-render`
- **merge_hazards:** `plan.md.j2` and `spec.md.j2` both include one partial; both feed the same
  aggregates Phase 3a reconciles. **This phase ends RED by construction** — see below.
- **Scope — in:** `src/harness_maker/templates/agents/_partials/comprehension_block.md.j2` (new;
  depth branch × `stage` argument; replaces Step A's OPTIONAL sentence per ADR-008 and subsumes
  spec's §2.3 preamble per ADR-007), `src/harness_maker/templates/stages/plan.md.j2`,
  `src/harness_maker/templates/stages/spec.md.j2`,
  `tests/structural/test_comprehension_render_gate.py` (new).
- **Scope — out:** `configure.md.j2`, all baseline artifacts.
- **Exit criterion:** `uv run pytest tests/structural/test_comprehension_render_gate.py -q` passes
  — AC-001, AC-002, AC-003 (SHA-256 against the Phase 0 golden), AC-006 (enabled block set + partial
  source path), plus the ADR-008 assertion that "visualization OPTIONAL" survives at `minimal` and
  is gone at `standard`, the ADR-007 assertion that `/hm:spec` emits exactly one round-state
  instruction, and the **anchor** assertion that the brief marker's offset precedes the Step 3.0
  heading in the rendered `/hm:plan` (the Case-A path).
- **Known-RED at this boundary (expected, not a regression):** `test_command_size_budget.py::test_atomic_commands_within_budget[plan]`
  and `[spec]`, `test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow`,
  `test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`,
  and the eight `tests/snapshot/*.expected.yaml`. Do **not** treat these as your own defect;
  Phase 3a owns them.
- **Must stay GREEN (a red here IS your defect):** `test_surface_baseline.py::test_round_trip_counts_match_the_live_render`
  and `tests/structural/test_roundtrip_budget.py`. Both count only `^!` lines and `Task(` tokens;
  a prose partial contributes neither, so they are invariants, not casualties. An earlier draft
  listed the first as known-RED — that is the shape that teaches an executor to discount a genuine
  red.
- **Risk:** medium — the `minimal` byte-identity assertion is unforgiving; the whitespace contract
  above is the convergence rule.
- **Rollback point:** end of Phase 1.

### Phase 3a — Configure axis and in-branch gate reconciliation

- **depends_on:** `[2]`
- **parallel_group:** `serial-gates`
- **merge_hazards:** every artifact here is a frozen baseline; any concurrent branch touching a
  rendered template invalidates all of them.
- **Scope — in**, by exact `file::symbol`:
  | Artifact | What changes |
  |---|---|
  | `templates/commands/hm/configure.md.j2` | new "Interview comprehension" dimension (ADR-003) |
  | `tests/structural/test_command_size_budget.py::_ATOMIC_RATCHET` | re-base the `plan` and `spec` entries (per-command ×1.02 ceiling at `:446`), each with the named-reason comment the table's existing entries carry |
  | `tests/structural/test_surface_baseline.py::test_round_trip_counts_match_the_live_render` | **expected unchanged** — exact, not a ratchet; trips if the partial adds any `^!` line. Verify deliberately |
  | `tests/structural/test_roundtrip_budget.py` (`_CLAUDE_ROUND_TRIPS`, the set-equality arm, the shipped-total arm) | **expected unchanged** — same trigger condition (`^!` lines + `Task(` tokens). Enumerated because a table that names one round-trip gate and not its twin is not exact |
  | `tests/snapshot/*.expected.yaml` (8 files) | regenerate; they carry the new key |
  | `work-docs/BASELINE-DELTA-plan-interview-comprehension.md` | new, see mandated content below |
  | `test_plan_net_surface.py`-equivalent net-surface assertion for this PLAN | xfail waiver citing the delta row (ADR-005) |
  | render fixtures | regenerate |
  - The phrase "command-surface registry" from the first draft is **deleted** — it names no artifact
    in this repo.
  - **Mandated BASELINE-DELTA content — SEVEN items**, machine-enforced by
    `test_baseline_delta_attribution.py`: (1) the literal string `ADR-010`; (2)
    `ratchet-rebaselined-by-its-own-subject`; (3) one of `larger` / `wrong way`; (4) the exact
    per-variant aggregates in grouped or plain form; (5) a backticked row naming every changed
    command; **(6) the backticked token `render_sha`; (7) the backticked token `payload_digest`.**
    Items 6-7 are `_MECHANICAL_KEYS`, and **both move on every regeneration** —
    `_surface_baseline.py` recomputes `head_sha()` and `payload_digest()` — so a document built to
    the earlier five-string spec fails `test_every_changed_key_has_an_attribution_row`, and fails
    it in Phase 3b, inside the RED window this PLAN says to keep short.
  - **Ordering:** `_current_delta_doc()` selects the document *by its aggregate figures*, so the
    aggregate row must be written in **Phase 3b after regeneration**, not guessed in 3a. Author
    everything else in 3a; close the aggregate row in 3b.
- **Scope — out:** `surface_baseline.json` regeneration (Phase 3b); any `deep_gate` change.
- **Exit criterion:** `uv run pytest tests/structural tests/snapshot -q` passes **except** the two
  generator-vs-baseline assertions that require the regenerated `surface_baseline.json`, which are
  expected RED and are Phase 3b's exit. The BASELINE-DELTA document exists and carries all five
  mandated strings.
- **Risk:** high — this is the phase the six-gates memory says gets discovered by tripping; the
  table above is the mitigation.
- **Rollback point:** end of Phase 2.

### Phase 3b — Post-land baseline regeneration (required follow-up, at base)

- **depends_on:** `[3a]`
- **parallel_group:** `serial-gates`
- **merge_hazards:** must run at the base repo on the landed commit; running it from the task branch
  is refused by design.
- **Scope — in:** `tests/structural/surface_baseline.json` (regenerated **only** via
  `python tests/structural/_surface_baseline.py`, never hand-edited), and the BASELINE-DELTA
  document's closing aggregate row plus its `render_sha` / `payload_digest` attribution rows —
  all three can only be written once the regenerated figures exist.
- **Scope — out:** any further template or code change.
- **Exit criterion:** `uv run pytest tests/structural tests/snapshot -q` fully green at base, and the
  BASELINE-DELTA aggregate matches the regenerated baseline exactly.
- **Risk:** medium — the window between land and regeneration leaves `main` with two RED structural
  tests. Keep it short and do not start unrelated work in it.
- **Rollback point:** the squash-land commit.

> **Why 3b is a phase and not a risk row:** `_surface_baseline.py:230` calls
> `assert_sha_is_durable(doc['render_sha'])` on the write path, which **refuses** a commit that a
> `task-land` squash will delete. The regeneration is therefore not merely inconvenient from the
> task branch — it is blocked. The first draft recorded this as R4 at "impact low" while Phase 3
> still demanded a green suite; that was the contradiction.

## 🧪 Testing Strategy

| Layer | What it covers | Files |
|---|---|---|
| Golden capture | AC-003's immutable oracle | `tests/structural/comprehension_zero_cost_golden.json` |
| Unit | ADR-002 overlay, ADR-004 normalization + warning text, ADR-006 absent branch, ADR-003 CLI flag, emitter `UndefinedError` guard | `tests/unit/test_comprehension_{absent_case,roundtrip,cli_flag}.py` |
| Structural (render) | AC-001/002/003/006 + ADR-007 single-preamble + ADR-008 sentence swap | `tests/structural/test_comprehension_render_gate.py` |
| Snapshot | 8 preset×dev_mode synthesize outputs carry the new key | `tests/snapshot/*.expected.yaml` |
| Gate | per-command ratchet, aggregate, round-trip exactness, attribution consistency | `test_command_size_budget.py`, `test_surface_baseline.py`, `test_baseline_delta_attribution.py` |
| Manual | one real `/hm:plan` run at `standard` confirming the brief appears **and reads well** | operator |

**Deliberately not snapshotted:** `tests/structural/_instruction_baseline.py` says adding a config
axis means adding its arms. `depth` is such an axis, but the snapshot only detects *disappearance*,
so nothing goes red either way. Not adding the arms is a recorded choice, and its cost is stated: a
future regression that drops an instruction **only** under `minimal` would be invisible.

The manual step is deliberate and not automatable — render-grep proves the instruction shipped, not
that the resulting brief is comprehensible. That gap is stated, not hidden.

Full-suite runs go to the background; the suite is ~6 minutes and polling it wastes the turn.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | The overlay is omitted and every user's depth resets on re-render | medium | high | ADR-002 makes it an explicit deliverable; AC-005 is the gate; named in Phase 1's exit criterion |
| R2 | `minimal` is not byte-identical (stray newline) | high | medium | Whitespace contract stated once in Technical Design; AC-003 compares SHA-256 against the Phase 0 golden |
| R3 | A gate outside the enumerated table trips | medium | medium | Phase 3a's scope is an exact `file::symbol` table, not prose; sized by the gate set, not the diff |
| R4 | The land→regeneration window leaves `main` with two RED tests | high | medium | Phase 3b is an owned phase with its own exit criterion; keep the window short, no unrelated work inside it |
| R5 | The brief bloats the interview and users stop reading it | low | medium | Delta after Round 1; default is `standard`, not `deep`; the manual step exists to catch this |
| R6 | Scope creep into `/hm:health` advisories or `deep_gate` tuning | medium | medium | Explicit SPEC Non-Goals; wrapup's drift gate compares the diff against SPEC scope |
| R7 | The retrofit (ADR-006) surprises an existing user whose commands grow | medium | low | CHANGELOG entry naming the retrofit and the `depth: minimal` opt-out; `/hm:configure` makes the opt-out one command |

## ✅ Success Criteria

- [x] AC-001 — `standard` renders brief + round_state only
- [x] AC-002 — `deep` renders all four; teach_back prose states no response and no gate
- [x] AC-003 — `minimal` renders none; `/hm:plan` and `/hm:spec` SHA-256 equal the Phase 0 golden
- [x] AC-004 — a `harness.yaml` with no `comprehension` key loads and renders as `standard`
- [x] AC-005 — every depth value survives the yaml → answers → yaml round-trip
- [x] AC-006 — `/hm:spec` carries the same enabled block set from the same partial source
- [x] `/hm:configure` offers the dimension **and** `hm cli make --comprehension-depth` persists it,
      rejects an invalid value, and preserves the existing value when omitted (ADR-003)
- [x] An unknown depth value warns with text stating the rewrite, then normalizes to `standard`
      (ADR-004)
- [x] `/hm:spec` emits exactly one round-state instruction at `standard` (ADR-007)
- [x] "visualization OPTIONAL" is present at `minimal` and absent at `standard`/`deep` (ADR-008)
- [x] The brief marker precedes the Step 3.0 heading in rendered `/hm:plan` — i.e. it survives the
      Case-A skip, the highest-traffic path
- [x] `BASELINE-DELTA-plan-interview-comprehension.md` carries all **seven** machine-enforced
      items (including backticked `render_sha` and `payload_digest`), and no gate was greened by
      hand-editing a baseline (ADR-005)
- [x] `test_round_trip_counts_match_the_live_render` and `test_roundtrip_budget.py` stayed green
      throughout — the partial added no `^!` line and no `Task(` token
- [x] Phase 3b completed at base: `tests/structural` and `tests/snapshot` fully green
      — **DEFERRED, not done at wrapup time.** `assert_sha_is_durable` refuses the regeneration
      from the task branch by design; the two named structural tests are RED until the post-land
      run at base. Owned follow-up, not a silent pass.

## 🔍 Plan Validation

**Pass 1 — `MAJOR_REVISION`** (6 critical, 5 warning, 3 suggestion). Cross-model second opinion ran
first and both models returned `invoked`:

| Model | Status | Findings | Outcome |
|---|---|---|---|
| codex | invoked | 13 (2×P0, 6×P1, 5×P2) | 11 accepted, 1 rejected, 1 duplicate |
| antigravity | invoked | 5 (2×P1, 2×P2, 1×P3) | 5 duplicate — all independently matched a codex finding |

**Rejected on evidence:** codex `5482d25d5b0c038a` ("default-site enumeration incomplete") — the
four suppliers were already enumerated in the Affected-components diagram; codex read the
Current-state table above it. Codex `3dfec25718b973c7` was half-refuted: its loop-mode claim was
already handled by the brief's inherited short-circuit, while its `/hm:spec` half was confirmed and
became ADR-007. Codex `ed2d7d108146fca0`'s "conflicts with the no-gate Non-Goal" claim was refuted
(a mandatory *output* is not a user gate); its residual — "changed" undefined — folded into ADR-008.

**Resolution of the 6 critical critiques:**

| # | Critique | Resolution |
|---|---|---|
| C1 | Phase 3's exit unachievable in-branch (`assert_sha_is_durable`) | Split into Phase 3a (in-branch) and Phase 3b (post-land, owned) |
| C2 | AC-003's oracle is the file Phase 3 mutates | New Phase 0 captures an immutable golden before any template edit; SPEC AC-003 rewritten to SHA-256 |
| C3 | `_ATOMIC_RATCHET`'s ×1.02 per-command ceiling missing; "command-surface registry" is not a real artifact | Phase 3a scope replaced with an exact `file::symbol` table; the fake name deleted |
| C4 | ADR-003 unimplementable — configure is prose over a CLI flag | `cli.py` added to Phase 1 scope with valid/invalid/omitted tests; ADR-003 amended |
| C5 | The retrofit Non-Goal is factually false | Interview round #4 → ADR-006; SPEC Non-Goal deleted and replaced with the explicit retrofit statement |
| C6 | AC-006 mandates identity for stage-specific content; §2.3 duplication | Interview round #5 → ADR-007; SPEC S6 and AC-006 rewritten to "same source, same enabled block set" |

Warnings C7–C11 resolved as ADR-008 (Step A conflict), Phase 2's declared known-RED list (C8),
ADR-004's corrected consequences (C9), the skip-path table (C10), and ADR-005's rewritten decision
plus the five mandated BASELINE-DELTA strings (C11). Suggestions C12–C14 resolved as the whitespace
contract, the emitter access rule, and the recorded `_instruction_baseline` non-decision.

**Pass 2 — `MAJOR_REVISION`** (3 critical, 2 warning, 3 suggestion). The validator confirmed C1,
C3, C4, C5, C6, C9, C12, C13 and C14 as **genuinely closed** against the code, and found four
resolutions only *nominally* closed. The validator-pass cap is 2, so these were fixed without a
third dispatch:

| # | Pass-2 critique | Fix applied |
|---|---|---|
| P2-1 | The mandated BASELINE-DELTA list was five strings; `_MECHANICAL_KEYS` adds `render_sha` and `payload_digest`, and **both move on every regeneration** — a five-string document fails `test_every_changed_key_has_an_attribution_row` inside Phase 3b's RED window | Raised to seven items; `_current_delta_doc()`'s aggregate-based selection recorded, so the aggregate + mechanical rows are authored in 3b, not guessed in 3a |
| P2-2 | Phase 0's golden recorded a task-branch SHA, which `task-land` deletes — the same durability defect that forced Phase 3b, inverted | Record `git merge-base HEAD <base>` and reuse `assert_sha_is_durable` in the writer, so an undurable capture is refused at Phase 0 |
| P2-3 | The brief was anchored "before Round 1", but `plan.md.j2:341` skips all of Step 3 on the Case-A path — the feature would be dark on the normal spec-driven entry while every render-grep passed | Anchor moved to **before Step 3.0**; skip-path table corrected; Phase 2's exit now asserts the marker's offset precedes the Step 3.0 heading |
| P2-4 | `test_round_trip_counts_match_the_live_render` was listed as known-RED but will be green — teaching an executor to discount a genuine red | Moved to a new "Must stay GREEN" list alongside `test_roundtrip_budget.py` |
| P2-5 | `test_roundtrip_budget.py` was in neither the gate table nor the RED list, despite the same trigger condition as a gate that was enumerated | Added to Phase 3a's table as expected-unchanged |
| P2-6 | AC-003's comparability pins (`render_surface()` path, `pinned_install_ref()`, `DEFAULT_FREEZE_TIME`) were unstated — a mismatch would send the executor bisecting the whitespace contract for an unrelated cause | Stated in Phase 0 |
| P2-7 | Skip-path row 4 duplicated row 3; the §1.7 SPEC-need dispatch path was missing | Rows merged; §1.7 re-entry row added |
| P2-8 | `interview_rounds: 3` vs six transcript rows; reverse-mapper citation off by ~50 lines | Corrected to 6 and to `interview.py:876` |

**Residual risk, stated plainly:** these eight fixes were applied *after* the final validator pass
and are therefore themselves unvalidated by an independent reviewer. The pass-2 critiques were
concrete and code-cited, and none required a new architectural decision — but `/hm:review` is the
next place this gets an outside check.
