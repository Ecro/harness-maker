---
type: research
task_slug: objective-gap-proposal
status: complete
created: 2026-09-16
tags: [harness-maker, research, python, jinja2, intent-layer, objectives, outcomes, llm-judgment]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/pdf/2506.04253
  - https://arxiv.org/pdf/2604.25000
  - https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12339886
  - https://okrinstitute.org/revolutionize-your-goalsetting-with-the-okr-generator-achieve-more-in-less-time/
related_docs:
  - "[[RESEARCH-intent-world-model-objective-layer]]"
  - "[[PLAN-intent-world-model-objective-layer]]"
  - "[[SPEC-intent-world-model-objective-layer]]"
  - "[[PLAN-playbook-alignment]]"
  - "[[REVIEW-playbook-alignment-2026-09-16]]"
summary: "On-demand, read-only `hm world gap` (deterministic table) + skill-driven LLM candidate proposal; approve stays human; plan Step 0.5 'none' offers a draft"
---

# RESEARCH — objective-gap-proposal

## 🎯 Recommended Direction

**Add one read-only CLI verb, `hm world gap`, that prints the deterministic gap table the
world already knows how to compute, and let the `intent-layer` skill — on the operator's
request only — turn that table plus the codebase into at most three objective *candidates*,
each written to disk only on an explicit "yes" (state `proposed`; `approve` stays human).**
Bundle the smaller sibling: when `/hm:plan` Step 0.5 is answered "none", ask once whether to
draft an objective for this task.

Rationale. The deterministic half is already shipped — `world.status_report` computes per-outcome
`gap` (`at_or_better | below_target | above_target | unevaluable`), `fired_revisits`, approval
validity and broken references (`src/harness_maker/world.py:706`). What is missing is (a) the
inputs an LLM needs to *not re-propose rejected work* (closed-`missed` objectives and every
`rejected[]` list are absent from `status`), (b) a place where the LLM is asked, and (c) a
write path that ends in the existing `objective new`. The first intent RESEARCH evaluated
exactly this as Approach D ("`hm next` as a derived view") and accepted a counter that a derived
view re-proposes rejected work and that LLM rankings are unstable; both objections are answered
by feeding the rejection history explicitly and by **not ranking** — present candidates with
evidence, the human picks. The user's 2026-09-16 decision (memory `project_intent_layer_followups`)
withdraws the earlier "no LLM gap detection" lock-in for this on-demand, never-gating form.
Main impact is **user-facing workflow value**: the operator gets from "mission written" to "first
objective proposed" without staring at an empty file; maintainer cost is one verb, one skill
paragraph and one plan-template question.

## 🔍 Refinement Decisions

Discovery lens: **User-workflow / product opportunity** (how the operator moves from mission to
objective today, where it stalls) and **Technical architecture / implementation** (what
`world.py` already derives, where the LLM step can live, what the surface ratchet allows).
`--deep` not set; the user pre-specified the shape in conversation (on-demand, read-only,
deterministic table first, "measure first" for unmeasured outcomes, gate untouched).

## 🛠️ Approaches Found

### Approach A — `hm world gap` verb + `intent-layer` skill proposal (recommended)

| Field | Content |
|---|---|
| Approach | New `world gap --json` subverb: the `status` outcome table extended with `never_measured` vs `stale_definition` split, every objective's state/`observed`/`rejected[]`, assumption conflicts, `unknowns`. The skill gains one situation: "operator asks what to do next / where the gaps are" → run `gap`, read the codebase, propose ≤3 candidates with `title / hypothesis / scope / outcome / evidence / overlaps-with`, ask per candidate, run `objective new` on yes. |
| Assumption | The operator invokes it deliberately (Solo mode, one consumer); the LLM step needs no new agent — the main loop with the skill is enough. |
| Evidence | `status_report` already computes `gap` per outcome and `fired_revisits`; `new_objective` already scaffolds the file; the skill's "ask with exact arguments, write once on yes" rule already exists (`templates/skills/intent-layer/SKILL.md.j2`). First RESEARCH pitfall 3: the control belongs at the recommendation → executable boundary — which is now the human `approve` stamp the gate reads (`autopilot_caps.py:317`). |
| Trade-off | Candidates are ephemeral (turn output); nothing remembers a candidate the operator declined. Accepted on purpose — pitfall 4 of the first RESEARCH (candidate lists rot: `pending-proposals.md` is 482 lines). |
| Compatibility | Excellent: one subparser + `command_registry` name, one skill paragraph, render-test pins in `test_render_intent_layer.py`. No gate / review / wrapup change. |
| Risk | **low** |

### Approach B — plan Step 0.5 "none" → "draft an objective for this task?" (bundle with A)

| Field | Content |
|---|---|
| Approach | After "none", one closed question; on yes the plan stage derives `objective new` arguments from the interview/RESEARCH, shows them, runs once, and Step 5 writes `objective: <id>` (state `proposed`, so the gate halts with `not_active` until the human approves + activates — correct by construction). |
| Assumption | The plan interview already holds the material a draft needs (problem, scope, non-scope). |
| Evidence | `plan.md.j2:105-107` is the only place "none" is answered; the gate's `not_active` branch means a `proposed` link cannot silently auto-advance. |
| Trade-off | Costs plan-command surface (`test_command_size_budget` pins `plan: 62703`); AC-005 of playbook-alignment pins plan/review/help byte hashes — this task moves `plan`, so the pin must be re-taken and the delta declared (`surface_allowance.commands.plan`). |
| Compatibility | Good; same answer-gated pattern as wrapup 5.7. |
| Risk | **low-medium** — a `proposed` objective linked from a PLAN is a new combination; verify the gate ledger reason reads `not_active`, not `approval_invalid`. |

### Approach C — a rendered `/hm:intent` (or `/hm:next`) slash command

| Field | Content |
|---|---|
| Approach | A fused stage-like command that runs the gap table, the LLM proposal and the writes in one prompt. |
| Assumption | The flow is frequent enough to earn a command surface. |
| Evidence | First RESEARCH: "keep `hm status` / `hm next` as CLI verbs, not rendered slash commands, until they earn the surface"; the dead-bytes incident (58.5% of rendered command bytes, zero invocations) is the reason the intent layer exists. |
| Trade-off | New command = new registry/golden/step-sensitivity arms, new surface budget, Cursor/Codex triple render. |
| Compatibility | Poor for the current evidence level. |
| Risk | **medium** — rejected for now; A+B deliver the same flow through existing surfaces. |

### Approach D — persist a candidate list (`pending-objectives.md`)

Rejected on the first RESEARCH's evidence: candidate queues accumulate faster than they resolve.
Only the *selected* objective persists, and it persists as the existing `INTENT-<ID>.md`.

## ⚠️ Pitfalls

1. **A derived gap view re-proposes rejected work** (first RESEARCH, Approach D counter). The
   LLM must receive every objective's `rejected[]` and every `closed` + `observed: missed`
   record, and each candidate must carry an `overlaps-with` field naming any prior objective or
   rejected alternative it resembles. The `gap` payload is where that data is assembled;
   `status` deliberately omits closed objectives and must stay as is.
2. **No data → invented gaps.** With `mission` written and every outcome `unevaluable`, the
   only honest output is "measure first". `world.gap` folds `never measured` and
   `stale_definition` into one `unevaluable` string; `LastValue.stale_definition` already
   distinguishes them, so the verb should surface both reasons. Whether the LLM may still
   propose when *all* outcomes are unmeasured is an open question below.
3. **LLM rankings are unstable across runs on identical inputs** (first RESEARCH). Do not rank;
   cap at three, require evidence per candidate, human picks. Adoption is the metric, not count.
4. **Self-approval theater.** Judgment-AC ADR-006 and the objective gate both rest on the
   verdict coming from someone other than the author. The proposer must never call `approve`;
   the skill rule "write only on an answer" applies per candidate. `objective new` leaves state
   `proposed`; the gate's `not_active` branch is the backstop if a `proposed` id reaches a PLAN.
5. **Surface ratchet.** Approach B moves the plan command. `test_playbook_alignment_invariance`
   (AC-005) pins plan/review/help hashes at `harness_maker_version` and skips on a bump — but
   this task ships at the same version, so the pin **fails**, not skips. The PLAN must declare
   `surface_allowance.commands.plan` and re-take the pin in `BASELINE-DELTA-playbook-alignment.md`
   (or its successor) with the attribution row `test_baseline_delta_attribution` requires.
6. **The layer's own withdrawal criterion.** Auto-created objectives could make an unused layer
   look used. Counter: creation is answer-gated and `approve` is manual, so a `proposed` file
   nobody approves is visible in `status.proposed` and in the 10-wrapup criterion (which counts
   `observed`, not files).
7. **Measurement hygiene from the outside literature** (labeled inference from OKR-tool practice:
   AI drafts, human tailors — okrinstitute; human-in-the-loop approval of proposed modifications —
   USPTO 12339886; HADA's "OKR alignment binds decision logic to measurable results" — arXiv
   2506.04253). All three agree the draft is cheap and the approval is the product; none of them
   is evidence for *auto*-activation.

## ❓ Open Questions

1. **Unmeasured outcomes.** When every outcome is `never_measured`, should the skill refuse to
   propose (print "measure first" and the `how_measured` commands) or propose with an explicit
   `evidence: none — hypothesis only` label? Recommendation: refuse when *all* are unmeasured,
   allow per-outcome when at least one has a value.
2. **Where the LLM step lives.** Skill prose only (Approach A), plan Step 0.5 only (B), or both
   (recommended). Both costs plan surface; A alone costs none.
3. **What `gap --json` includes.** Proposed: outcomes (last / target / gap / reason), objectives
   (all states with `observed` + `rejected[]`), assumption conflicts, `unknowns`, `fired_revisits`.
   Does it also embed `how_measured` so the "measure first" branch can print the commands?
4. **Candidate cap and shape.** ≤3 candidates; fields `title / hypothesis / scope / non_scope /
   outcome / evidence / overlaps-with`. Is `rejected[]` on the *new* record pre-filled from the
   candidates the operator declined in the same turn (cheap provenance, no persistence)?
5. **Adoption measurement.** The first RESEARCH required the layer to measure itself
   (proposal-adoption rate). Cheapest form: an autopilot-ledger event `objective_proposed`
   `{candidates, accepted}` written by the CLI on `objective new --from-proposal`, or nothing and
   count `proposed` files. Which?
6. **Surface accounting.** `surface_allowance.commands.plan` amount, and whether the AC-005 pin
   is re-taken in the playbook-alignment delta doc or a new `BASELINE-DELTA-objective-gap-proposal.md`.
7. **Out of scope confirmation.** Codex's `evaluating` state and per-stage mission-alignment
   checks stay out (user decision 2026-09-16). Confirm in the SPEC's non-scope.

## 📚 Sources

- HADA: Human-AI Agent Decision Alignment Architecture — https://arxiv.org/pdf/2506.04253
- Toward a Science of Intent: Closure Gaps and Delegation Envelopes — https://arxiv.org/pdf/2604.25000
- Querying data using specialized and generalized AI models (human-in-the-loop approval of proposed modifications) — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12339886
- OKR Institute, AI OKR generator: draft with AI, tailor by hand — https://okrinstitute.org/revolutionize-your-goalsetting-with-the-okr-generator-achieve-more-in-less-time/

## 🔗 Related Internal Docs

- [[RESEARCH-intent-world-model-objective-layer]] — Approach D (`hm next` derived view) and its accepted counter; pitfalls 3, 4, 7; codex's objective-generation bundle held behind adoption metrics.
- [[PLAN-intent-world-model-objective-layer]] — gate precedence (advance → halt only), answer-gated write pattern.
- [[SPEC-intent-world-model-objective-layer]] — withdrawal criterion (10 wrapups, `observed`), `Gap` row semantics for `last_value`.
- [[PLAN-playbook-alignment]] — INTENT-<ID>.md as the record, `objective new` scaffold, `surface_allowance` precedent.
- [[REVIEW-playbook-alignment-2026-09-16]] — open items this task may touch in passing (`new_objective` O_EXCL if the proposal path creates files).
- Memory: `[wiki:architecture] intent-doc-is-the-objective-record`; user decision recorded in `project_intent_layer_followups` (lock-in reversal, constraints).
