---
type: research
task_slug: plan-interview-comprehension
status: complete
created: 2026-08-13
tags: [harness-maker, research, jinja2, python, interview, plan-stage, comprehension, harness-yaml]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/pdf/2507.02564
  - https://arxiv.org/pdf/2507.02858
  - https://dl.acm.org/doi/pdf/10.1145/3301275.3302322
  - https://www.emergentmind.com/topics/progressive-disclosure-controls
  - https://harshppatel2880.medium.com/ai-coding-works-better-when-you-and-the-agent-have-shared-understanding-4cb1c1293ebb
  - https://explainx.ai/blog/claude-code-plan-mode-complete-guide-2026
  - https://www.sciencedirect.com/science/article/pii/S1364815219301495
related_docs:
  - "[[PLAN-deep-interview-question-criteria]]"
  - "[[PLAN-deep-interview-llm-delegation]]"
  - "[[PLAN-workflow-time-token-savings]]"
  - "[[BASELINE-DELTA-workflow-time-token-savings]]"
summary: "Surface the already-existing hidden Step 1 draft as a layered design brief, gated by a new interview.comprehension block"
---

# RESEARCH — Plan-stage interview comprehension

## 🎯 Recommended Direction

**Add `interview.comprehension` to `harness.yaml` and spend its budget on *context per question*,
not on *more questions* — with the first and cheapest move being to stop hiding the draft the
plan stage already builds.**

`plan.md.j2` Step 1 (line 90) is literally titled **"Pre-interview internal draft (NOT shown to
user)"** and synthesizes exactly what the user reports missing: tentative architecture
(components, boundaries, data flow), candidate phase decomposition, and an **explicit ambiguity
list ranked by blast radius**. That artifact is produced on every non-skipped `/hm:plan` run and
then discarded from the user's view. Meanwhile Step A (line 352) makes the round-by-round
"current plan state" visualization *optional* ("Visualization is NOT mandatory"), and permits
skipping it entirely when "nothing topologically changed". So the whole-picture channel is
off by default and the whole picture is already computed. The user's complaint — "전체 그림이
이해가 안 갈 때가 많다" — is a disclosure defect, not a generation defect.

The second half — "세부적인 결정들도" — is a different defect with a different fix. Each question
today carries `**Why it matters:** {one-sentence impact of getting it wrong}` and 2-5 option
labels with a trade-off each (Step A/B). That is thin for an architectural decision: no
recommended default with rationale, no statement of what *downstream* sections each option
rewrites, no reversibility cost. Elicitation research is direct on this: LLM-run interviews
that do not deliberately inject context conduct "more superficial elicitation sessions that miss
important requirement details", and long context-enhanced prompts outscored short ones
([LLMREI, arXiv 2507.02564](https://arxiv.org/pdf/2507.02564)); follow-up questions elicit
substantive answers only when grounded in the preceding discussion and previously established
constraints, versus decontextualized queries
([arXiv 2507.02858](https://arxiv.org/pdf/2507.02858)).

**Critical framing to carry into `/hm:plan`:** deeper understanding must NOT be implemented as
more questions. The 5-term inequality gate exists precisely to suppress low-value questions, and
this project's locale cap is `ko: 1` open-ended per turn. A naive "deep mode" that raises
`open_ended_cap` or lowers `eig_epsilon`/`confidence_tau` would fight a deliberate 0.16.0 design
and make the interview *longer and still unclear*. The lever is layered disclosure —
overview first, detail on demand — which is the standard mitigation when users hold only
coarse "folk-theoretical" models of a system
([progressive-disclosure controls](https://www.emergentmind.com/topics/progressive-disclosure-controls);
[Springer/ACM progressive disclosure](https://dl.acm.org/doi/pdf/10.1145/3301275.3302322)).

## 🔍 Refinement Decisions

`--deep` was not set; Phase 0 / Phase 0.5 skipped.

**Discovery lens:** (1) Technical architecture / implementation — the rendered `plan.md.j2`
interview loop, the `harness.yaml` `interview` schema, and the render/ratchet gate set;
(2) User-workflow / product opportunity — how the harness user actually consumes a planning
interview and which artifacts they already keep. Risk/compliance and academic lenses were used
only as supporting evidence.

### Local capability × User artifact

| Harness capability that already exists | User artifact it could attach to | Currently surfaced? |
|---|---|---|
| Step 1 internal draft (architecture + phases + ranked ambiguities) | the live interview turn | **No — explicitly hidden** |
| ADR template + Interview Entry table (Steps C/D) | `work-docs/PLAN-<slug>.md` | Yes, but only *after* the interview ends |
| `RESEARCH-<slug>.md` frontmatter (`summary`, approaches, open questions) | read by `/hm:plan` Step 2 | Yes, consumed silently — user never sees what was inherited |
| `.claude/memory/` wiki + failures, Second Brain notes | round context | Loaded, never shown as "what I already assumed" |
| `plan-validator` agent critique (Step 4) | post-interview | Yes — too late to change the user's mental model mid-interview |
| Step A visualization ladder (prose → table → ASCII → mermaid) | round preamble | **Optional, skippable** |

Read as a product statement: the harness computes a complete design picture and shows the user a
keyhole. Every row above is a disclosure decision already made *against* the user, so the
opportunity is unusually cheap — it is mostly re-routing existing output, not new generation.

## 🛠️ Approaches Found

### Approach A — `interview.comprehension` disclosure block (recommended)

| Field | Content |
|---|---|
| Approach | New `harness.yaml` key `interview.comprehension.{enabled, brief, round_state, decision_depth, teach_back}` driving a shared Jinja partial rendered into `plan.md.j2` (and optionally `spec.md.j2`) |
| Assumption | The missing understanding is *disclosure*, not *generation*; the model already holds the design |
| Evidence | `plan.md.j2:90` builds the draft and marks it `NOT shown to user`; `plan.md.j2:352-377` makes the round-state block optional and skippable; context-enhanced LLM interviews measurably outperform short ones (arXiv 2507.02564) |
| Trade-off | Rendered-surface growth in the single most expensive command; every `/hm:plan` pays reading cost even when the task is simple |
| Compatibility | Very high. `HarnessConfig.interview` is `dict[str, Any]` (`models.py:1215`) — **no pydantic model change needed**, only `interview_deep_gate_defaults()`-style defaults, the two `harness-yaml/*.yaml.j2` blocks, and `answers_from_harness_yaml` round-trip. Partial precedent already exists (`agents/_partials/inequality_gate_block.md.j2`, included by plan/spec/research) |
| Risk | **medium** — surface ratchet, not logic |

Concrete sub-levers, each independently switchable:

1. **`brief`** — promote Step 1's internal draft to a *shown* design brief before Round 1:
   one-paragraph goal, component/data-flow sketch, phase skeleton, and the ranked ambiguity list
   with "we will ask you about #1, #3; the rest I am defaulting to X because Y". This is the
   single highest-value item and costs almost no new generation.
2. **`round_state`** — flip Step A's optional visualization to *required-when-changed*, rendered
   as a **delta** ("what changed since last round"), not a re-dump. Keeps the ratchet cost low
   and matches progressive-disclosure layering.
3. **`decision_depth`** — a fixed per-question envelope: *what this decides · what it rewrites
   downstream · recommended default + why · reversibility cost*. This is the "세부적인 결정" half.
   It adds no questions; it thickens each one.
4. **`teach_back`** — before the interview exits, the model restates the locked design in the
   user's terms and asks for correction. Mental-model elicitation literature treats explicit
   readback/mapping as the standard method for verifying shared understanding
   ([mental-model elicitation methodology](https://www.sciencedirect.com/science/article/pii/S1364815219301495)).
   Practitioner guidance converges on the same "comprehension gate" idea for agent-written code
   ([shared understanding in AI coding](https://harshppatel2880.medium.com/ai-coding-works-better-when-you-and-the-agent-have-shared-understanding-4cb1c1293ebb)).

### Approach B — Tune the existing 5-term gate (`eig_epsilon` ↓ / `confidence_tau` ↑ / `open_ended_cap` ↑)

| Field | Content |
|---|---|
| Approach | Treat "deeper understanding" as "ask more / harder questions" via the knobs already in `interview.deep_gate` |
| Assumption | The user is under-asked |
| Evidence | The knobs exist and are already rendered per-locale (`Production.yaml.j2:8-21`); zero new schema |
| Trade-off | Directly inverts 0.16.0's stated intent — the gate's "primary defense against asking obvious questions" (`plan.md.j2:482`) — and lengthens the interview without improving the picture |
| Compatibility | Trivially compatible, semantically opposed |
| Risk | **high** — likely to make the reported problem worse; more rounds, same keyhole |

Worth recording as an explicit rejected alternative in the PLAN's ADR, because it is the obvious
reading of "설계와 계획에 대해서 완벽하고 깊은 이해" and it is the wrong one.

### Approach C — Persistent living design document instead of chat-stream disclosure

| Field | Content |
|---|---|
| Approach | Write/refresh `work-docs/PLAN-<slug>.md` (or a `PLAN-<slug>.draft.md`) after every round; point the user at the file rather than reprinting state in-chat |
| Assumption | The user prefers to read a stable artifact over scrollback |
| Evidence | Practitioner reports that iterative plan review "starts to break down… after a few rounds of corrections, the process becomes mentally tiring" ([Claude Code plan mode guide](https://explainx.ai/blog/claude-code-plan-mode-complete-guide-2026)); a file re-read is cheaper than re-reading a 12-round transcript |
| Trade-off | Repeated whole-file writes are exactly the context-carry anti-pattern CLAUDE.md §Context discipline warns about (a rewrite duplicates the body); also creates a half-written PLAN on disk that `/hm:execute`'s frontmatter reader could pick up mid-interview |
| Compatibility | Medium — Step 5/6 already own PLAN writing; a draft file adds a second writer to a single-source artifact (`test_deliverable_single_source.py` exists) |
| Risk | **medium-high** |

Best treated as a *sub-option of A* (`brief: file` vs `brief: inline`) rather than a rival, and
only with append/Edit semantics, never whole-file rewrites.

## ⚠️ Pitfalls

1. **A template edit is never a one-file change — size the phase by the gate set.** Editing one
   rendered template in this repo trips **six** gates: the aggregate surface ratchet
   (`tests/structural/surface_baseline.json`), the baseline-delta attribution document
   (`test_baseline_delta_attribution.py` — every changed baseline key needs an attribution row
   *and* the document's aggregate must match), the command-surface registry, the eight
   preset×dev_mode synthesize snapshots, the round-trip budget
   (`test_roundtrip_budget.py`), and the render fixtures. Four of six were discovered by
   tripping them mid-execution last time. Source: `[wiki:architecture]
   onboarding-disclosure-and-six-gates`.
2. **The ratchet has zero headroom by design and must not be rebaselined by the change it
   measures.** `test_plan_net_surface.py` currently *xfails* with a waiver
   (claude 366439 → 371066, +4627); its own failure text says "Do NOT re-freeze
   `surface_baseline.json` to make it pass". A comprehension block that grows `plan` prose must
   either be paid for by an offset elsewhere or carry an explicit, argued waiver.
3. **Gate the block so opt-out harnesses pay zero.** Precedent from the same waiver: an item was
   scored "−7238, but only for a harness that opts OUT — this repo is the fleet and stays in".
   Wrapping the new prose in `{% if config.interview.comprehension.enabled %}` makes the cost
   opt-in for third parties while this repo still pays; that asymmetry must be stated in the
   PLAN, not discovered at the delta document.
4. **Absent-case = feature black hole.** A block that activates on an optional field silently
   never fires for every harness written before the field existed. `interview` is a bare
   `dict[str, Any]`, so `config.interview.comprehension.brief` on an old file raises or
   undefines depending on the access path — every template read must use
   `.get(...)`/`| default(...)`, and there must be a test for the **absent** case, not just the
   present one. Source: CLAUDE.md Learned Corrections 2026-06-08 (`count:8`, most-recurring).
5. **A default flip is an enumeration task, not an edit.** If `comprehension.enabled` defaults
   to `true`, every bare construction and every fall-through changes meaning at once —
   `--preset` rebuilds, `--reinterview` rebuilds, and validation guards that `del` a malformed
   key to reach the "safe" class default. Source: `[fail:design]
   promoted-default-reaches-bare-callers` (three of seven sites were missed last time, and the
   missed ones were the dangerous ones).
6. **Don't collapse this into the deep_gate.** `deep_gate` is a *suppression* mechanism;
   comprehension is a *disclosure* mechanism. Putting disclosure knobs inside `deep_gate` will
   invite exactly the Approach-B misreading later.
7. **Rendered locale caps are baked at render time.** `plan.md.j2:470-473` notes the
   `open_ended_cap_by_locale` value is resolved during render, so any new locale-sensitive
   comprehension setting needs `/harness-maker:make` to refresh — say so in the rendered prose.
8. **Loop-mode must short-circuit the brief.** Step 1 is already skipped in loop-mode as "pure
   waste"; a brief derived from it must inherit that short-circuit or every autoloop iteration
   prints a design brief nobody reads.

## ❓ Open Questions

1. **Key placement and name** — `interview.comprehension` vs a top-level `comprehension:` block
   vs extending `interview.main_loop`. Affects `answers_from_harness_yaml`, `/hm:configure`
   axes, and whether `schema_version` needs a bump.
2. **Default value** — ON for new installs (best UX, pays ratchet on the fleet) vs OFF
   (zero-cost, but the feature never fires for anyone who does not read the changelog — pitfall
   4/5 territory). Note that per `[wiki:architecture] harness-diet-phases-2-6`, a new default
   reaches **new installs only**; existing `harness.yaml` files round-trip their explicit values.
3. **Granularity** — one boolean, or the four independent sub-levers (`brief`, `round_state`,
   `decision_depth`, `teach_back`), or a single ordinal `depth: minimal|standard|deep`? The
   ordinal is cheapest on surface and on `/hm:configure`; the four booleans are more honest
   about what actually costs tokens.
4. **Scope of stages** — `plan` only, or also `spec` (6-category interview) and `research`
   `--deep`? A shared partial makes all three nearly free to add but multiplies the ratchet cost
   by three.
5. **Surface budget** — how many characters is this allowed to add, and what is the offset?
   Without an answer, Phase 1 of the PLAN will end at the delta-attribution gate.
6. **Brief delivery** — inline in chat vs a written `work-docs/` artifact (Approach C). This is
   an architecture decision with a single-source-of-deliverables consequence.
7. **Does `teach_back` need a user-visible exit gate?** i.e. can the interview end if the user
   never confirms the readback, or is that a new mandatory gate (with autopilot implications —
   `auto_full` would have to auto-answer it)?

## 📚 Sources

- [LLMREI: Automating Requirements Elicitation Interviews with LLMs (arXiv 2507.02564)](https://arxiv.org/pdf/2507.02564) — context-enhanced ("long") interviewer prompts outperform short ones; without deliberate context injection, LLM interviewers run superficial sessions that miss requirements.
- [Requirements Elicitation Follow-Up Question Generation (arXiv 2507.02858)](https://arxiv.org/pdf/2507.02858) — follow-up quality criteria: contextual coherence, clarification-seeking, specificity, answerability; grounded questions elicit substantively better answers than decontextualized ones.
- [Progressive disclosure: empirically motivated approaches (ACM)](https://dl.acm.org/doi/pdf/10.1145/3301275.3302322) — layered disclosure as the mechanism for depth-without-overload.
- [Progressive Disclosure Controls](https://www.emergentmind.com/topics/progressive-disclosure-controls) — hierarchical explanation layers: coarse global summary first, then feature-level evidence, then model detail; motivated by users' initial "folk-theoretical" mental models.
- [Making the most of mental models: methodology for mental model elicitation (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1364815219301495) — explicit elicitation + readback/mapping as the verification method for shared understanding.
- [AI coding works better when you and the agent have shared understanding](https://harshppatel2880.medium.com/ai-coding-works-better-when-you-and-the-agent-have-shared-understanding-4cb1c1293ebb) — practitioner framing of the comprehension gate.
- [Claude Code Plan Mode: Complete Guide 2026](https://explainx.ai/blog/claude-code-plan-mode-complete-guide-2026) — plan-review fatigue after several correction rounds; Q&A-before-implementation as the alternative pattern.

Internal (code) references, all in this repo at `0.51.1`:
`src/harness_maker/templates/stages/plan.md.j2:79-101` (Step 0/1),
`:339-377` (Step 3 / Step A), `:379-400` (Step B), `:454-503` (Step E gate),
`src/harness_maker/models.py:1211-1220` (`schema_version`, untyped `interview` dict),
`src/harness_maker/templates/harness-yaml/Production.yaml.j2:8-22`,
`src/harness_maker/templates/agents/_partials/inequality_gate_block.md.j2` (partial precedent),
`tests/structural/test_plan_net_surface.py:54-85` (live ratchet waiver),
`tests/structural/surface_baseline.json` (aggregate 377215 claude / 306231 codex).

## 🔗 Related Internal Docs

- [[PLAN-deep-interview-question-criteria]] — 0.16.0, introduced the 5-term inequality gate this work must not fight.
- [[PLAN-deep-interview-llm-delegation]] — the 3-layer deep interview gate (GCIC + implicit probing + ambiguity score) across spec/plan/research/loop.
- [[PLAN-workflow-time-token-savings]] / [[BASELINE-DELTA-workflow-time-token-savings]] — the live surface waiver any new `plan` prose is measured against.
- [[wiki:architecture onboarding-disclosure-and-six-gates]] — the six gates a rendered-template edit trips; also precedent for adding a `/hm:configure` entry alongside a new axis.
- [[wiki:architecture harness-diet-phases-2-6]] — retired keys are stripped at LOAD not render; a new default reaches new installs only.
- [[fail:design promoted-default-reaches-bare-callers]] — a class-default flip is an enumeration task.
