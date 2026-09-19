---
type: research
task_slug: ai-native-sdlc-vs-intent-world
status: complete
created: 2026-09-19
tags: [harness-maker, research, python, intent-layer, world-model, playbook, sdlc, comparison]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://claude.com/blog/the-ai-native-sdlc-playbook
  - https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle
  - https://www.port.io/blog/anthropic-ai-native-sdlc-playbook
  - https://www.zeniteq.com/anthropic-s-ai-sdlc-makes-review-the-bottleneck-0735c3
  - https://waydev.co/anthropics-ai-native-sdlc-playbook-has-a-missing-layer-measurement/
related_docs:
  - "[[RESEARCH-playbook-alignment]]"
  - "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
  - "[[PLAN-intent-world-model-objective-layer]]"
  - "[[PLAN-outcome-measure]]"
  - "[[PLAN-intent-layer-ops]]"
  - "[[PLAN-assumption-entry-and-evidence-locator]]"
  - "[[wiki:architecture] intent-layer-withdrawal-instrument"
  - "[[wiki:architecture] objective-gap-and-proposal"
summary: "Keep state layer; adopt intent/ folder + role ownership gated only when roles differ; fix empty prose"
---

# RESEARCH — Anthropic AI-native SDLC vs harness-maker intent/world model

## 🎯 Recommended Direction

**TL;DR:** The two are not competitors at the same altitude. The Playbook is an
**organisational process** (six stages, role-owned gates, per-change `intent.md`). Our
intent/world model is a **persistent state layer** (mission, measured outcomes, assumptions
ledger, hash-bound objective approvals) that the Playbook does not have at all. Keep the state
layer; do not import the Playbook's role/gate machinery. The one gap worth closing first is
internal evidence, not Playbook conformance: **the prose half of `INTENT-<ID>.md` — the part
that *is* the Playbook's `intent.md` — is empty in 2 of 2 records (10 of 10 sections).**
Of the Playbook traits the user flagged, two are worth taking: an **`intent/` folder** (folder =
type, frontmatter = state; `specs/` is the precedent) and **role-owned artifacts**, adopted as
declared ownership in the unused `intent.yaml owners` field with gates that fire **only when
roles resolve to different people** — which also closes our real gap: SPEC has no human
approval at all. With the IC replaced by agents, the role map is **`{owner, dri, team}`**:
the DRI (ex-developer) absorbs the task-level PO role **and keeps technical acceptance** —
oracle choice and irreversible decisions — while the portfolio-level PO survives one altitude
up as the objective owner (our existing two-level design).

**Rationale.** Mapping stage by stage (below) shows harness-maker already covers Plan → Build
→ Test → Review with its own chain (`RESEARCH → SPEC → PLAN → diff → REVIEW → verify → wrapup`),
and exceeds the Playbook on three axes the Playbook's own critics name as missing:
measurement (Waydev), assumption correctness ("version control … cannot determine whether an
assumption was correct" — Zeniteq), and drift-resistant approval (content-hash approval vs a
merge click). Where the Playbook is ahead — per-change intent as a mandatory entry point,
Stage 6 signal→intent triggers, process metrics like intent survival rate, continuous evals
of the agent config — each item either assumes an organisation with separate roles (which a
solo/small-team harness collapses) or adds behaviour the `cell-dev` research already argued
against adding before the layer proves itself. The withdrawal instrument (5 of 10 wrapups
counted, 1 objective observed) is the right arbiter for growth; spend effort first on making
the record we already ship actually get filled. Main impact: **user-facing workflow value**
(an operator's intent becomes readable), with small maintainer cost.

This is informational; `/hm:plan` locks it.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture** (stage/artifact/ownership mapping against
`world.py`/`intent.py` and stage templates) + **User-workflow** (how the dogfood operator
actually uses the records — measured from `work-docs/INTENT-*.md`,
`.claude/world/assumptions.yaml`, `hm world gap --json`). `--deep` not set. Prior art
[[RESEARCH-playbook-alignment]] already aligned Stage 1 artifact shape; this document compares
the **whole lifecycle** and judges trade-offs rather than re-deriving the file layout.

## 🛠️ Approaches Found

### Side-by-side mapping (facts)

| Playbook stage | Playbook artifact / owner / gate | harness-maker equivalent | Verdict |
|---|---|---|---|
| 1 Plan | `intent.md` (problem, outcome, users, constraints, open questions); originator + Claude write, **product owner approves via merge** | Two levels: project `.claude/intent.yaml` (mission, measured outcomes, non-negotiables, non-scope, unknowns) + per-objective `work-docs/INTENT-<ID>.md` (frontmatter = hypothesis/scope/outcome_id/state; body = the five Playbook sections). `approve` stamps `content_hash` over hypothesis/scope/non_scope/outcome_id/target (`world.py:213-224`). Human-only approve/activate/close. | **Ours deeper** (two levels, hash-bound approval, outcome link). **Playbook fuller** in practice: our prose body is empty in every record. Intent is **optional** per task in ours (Step 0.5 asks "which objective?"); mandatory in the Playbook. |
| 2 Design | `spec.md`, policy applied during writing via org skills; PO approves | `/hm:spec` (6-category interview, ACs, oracle elicitation) | Equivalent. Playbook adds "policy-as-skills" (brand/compliance); ours is AC/oracle-centric. |
| 3 Build | `plan.md` approved before code; CLAUDE.md ≤ 1 page; skills; hooks; worktrees | `/hm:plan` (ADRs, plan-validator) → `/hm:execute` TDD in `.worktrees/`; hooks in settings.json | Equivalent or ahead (TDD RED gate). Our CLAUDE.md is ~425 lines vs Playbook's "under one page" — a known cost ([[RESEARCH-cell-dev-future-and-intent-layer-fit]]). |
| 4 Test | single verify command; tests read-only during fix; **continuous evals (20-50 tasks) gated on CLAUDE.md/skills/hooks changes** | `/hm:verify`, A.5 test-reviewer, mutation gate (broken — 0 mutants, 5 tasks), `step_sensitivity` TUNE `measure_cmd` | Partial. We have no eval suite that regression-tests the *harness config itself* on change; harness-bench is external and manual. Not an intent-layer item. |
| 5 Deploy/Review | Claude reviews every PR against `spec.md`/`plan.md`; `REVIEW.md` caps nits at 5; env-tiered autonomy | `/hm:review` 7-lens k-of-N + cross-model; Step 3.3 objective scope-drift = **P2 finding, never a gate** | Ours heavier on review. Playbook explicitly checks against intent; ours checks scope against objective (advisory). |
| 6 Maintain | Deterministic detector (control bands 1σ/2σ/3σ) → Claude diagnoses → **new `intent.md`** re-enters Stage 1 | `outcome measure --all` at wrapup 5.7 + `revisit_when` evaluated at plan/gap. **No trigger path** — nothing turns a breached target into a proposed objective without a human running `/hm:plan`. | **Playbook ahead.** Our closest analogue is `gap` + proposal consent at Step 0.5, which is pull, not push. |
| Cross-stage metrics | Per stage leading/lagging: time-to-intent, **intent survival rate**, rework count after spec, first-pass CI, diff fidelity to plan, CFR | Outcome values with `definition_hash` + staleness (`never_measured`/`stale_definition`); `/hm:metrics` CFR + churn; **withdrawal criterion measuring the layer itself** | Different targets: Playbook measures the *process*, we measure the *project outcome* and the *layer's own usefulness*. We don't compute intent survival (proposed→closed vs dropped), though the data exists. |
| Epistemic state | — (none; Zeniteq names this the core risk) | `assumptions.yaml`: known/assumed/unknown/conflict, typed evidence (`confirms`/`supersedes`/`contradicts`), locator fingerprints, `revisit_when` | **Ours only.** Differentiator. Dogfood usage: **1 assumption** recorded. |
| Audit trail | Chain of commits = who asked / what produced / who approved; SIEM logs every agent approval | Git commits + `objective_proposed` ledger row + approval stamp; `approved_by` from `git config` (not forgery-proof, accepted) | Equivalent for solo use; weaker for regulated orgs. |
| Roles | PO, tech lead, engineer, release manager, service owner — distinct people | One operator; the proposer (LLM) never approves | Playbook's separation of duties collapses to "LLM proposes, human disposes" in ours. |

### Approach A — Keep the state layer as-is, document the mapping only

| Field | Content |
|---|---|
| Assumption | The Playbook is an org-process guide; harness-maker is a solo/small-team harness and should not copy role gates. |
| Evidence | Playbook roles (PO/release manager) have no counterpart in a one-operator repo; `cell-dev` research: "keep the state, drop the machine"; withdrawal instrument not yet due (5/10). |
| Trade-off | Zero cost; the empty-prose problem persists, so the Playbook-shaped half stays decorative. |
| Compatibility | Full. |
| Risk | low (but leaves a known dead surface). |

### Approach B — Close the cheap, evidence-backed gaps (recommended)

1. **Fill-or-drop the INTENT prose.** Either `/hm:plan` Step 4.9 drafts the five sections from
   the Step 0.5 conversation (LLM writes, human approves — Playbook's "originator brainstorms
   with Claude"), or the body is removed and the Playbook mapping becomes a documented
   correspondence. The hash already excludes prose (`world.py:213-224`), so either choice leaves
   approval semantics untouched.
2. **Intent survival rate in `gap --json`**: count proposed→closed vs →dropped (+ `observed`
   distribution). Derived from records already on disk; no new state. Gives the Playbook's
   Stage 1 lagging metric for free.
3. **Stage-6-lite (optional, later):** when `outcome measure` moves an outcome from
   `at_or_better` to `above_target`, the wrapup 5.7 line says so and offers a proposal at the
   next `/hm:plan` — still pull, still human-consented, no scheduler.

| Field | Content |
|---|---|
| Assumption | The layer's value is limited by what is *filled*, not by missing features. |
| Evidence | 10/10 prose sections empty; 1 assumption; 1 objective observed; Playbook critics (Port, Zeniteq) say artifact quality, not artifact existence, is the binding risk. |
| Trade-off | Item 1 adds prose to a rendered stage (surface ratchet — four frozen numbers move); item 2 is Python-only; item 3 adds wrapup text. |
| Compatibility | High — no schema change for 1(b)/2; 1(a) touches `plan.md.j2` only. |
| Risk | low–medium (surface budget; wrapup already asks three questions). |

### Approach C — Full Playbook adoption

Mandatory per-change `intent.md` before any `/hm:research`, per-stage leading/lagging metrics,
Stage 6 control-band triggers invoking Claude non-interactively, a 20–50 task eval suite gated
on `.claude/` config changes, env-tiered autonomy.

| Field | Content |
|---|---|
| Assumption | harness-maker users are organisations with separate roles and monitoring infrastructure. |
| Evidence | Playbook prerequisites list monitoring store, CI/CD, MCP deploy tools; Port: needs service catalog/ownership/blast-radius data the Playbook itself lacks. None exist in a typical consumer repo. |
| Trade-off | Large surface + new behaviour; directly conflicts with CLAUDE.md 제1목표 ("복잡한 설계를 지양"); re-adds the scheduler/verdict machinery `cell-dev` recommended withdrawing. |
| Compatibility | Low — Stage 6 needs a trigger runtime harness-maker does not have (Routines/`/loop` are host features). |
| Risk | high. |

### Pros / cons summary (the question asked)

**Where ours is stronger than the Playbook**
- **Measured outcomes with definition versioning.** `definition_hash` makes a value stale when
  its target/how-measured changes; the Playbook has metrics but no notion of a metric's
  definition drifting. Waydev calls measurement the Playbook's missing layer — we have it.
- **Epistemic state.** Assumptions with typed evidence and `conflict` state address the risk
  Zeniteq names ("git cannot determine whether an assumption was correct"). Nothing in the
  Playbook tracks this.
- **Drift-resistant approval.** Approval is bound to a content hash of scope/hypothesis/target;
  editing any of them silently invalidates it (`needs_revalidation`). A merged `intent.md` in
  the Playbook stays "approved" after later edits unless someone re-reviews the PR.
- **Two altitudes.** Mission/outcomes (project) + objectives (change) — the Playbook has only
  the per-change artifact, so "why this project exists" lives nowhere versioned.
- **Rejected alternatives recorded** (`rejected[]`, `--declined`) — the Playbook records accept/
  reject of an intent but not the candidates that lost.
- **Self-withdrawal criterion.** The layer measures whether it earns its keep; the Playbook
  has no kill switch for its own process.

**Where ours is weaker**
- **Intent is optional; the Playbook makes it the entry point.** A task can run
  research→wrapup with no objective; Step 0.5 only asks. Result: 2 objectives total vs many
  landed tasks.
- **The human-readable half is unused.** The Playbook's value is "intent captured once, in the
  originator's own words"; ours captures the machine half and leaves the words empty.
- **No push path (Stage 6).** A breached outcome never becomes a proposal by itself.
- **No process metrics.** No survival rate, time-to-intent, rework-after-spec, diff-fidelity-
  to-plan — though several are derivable from existing records.
- **No config eval suite.** The Playbook regression-tests CLAUDE.md/skills/hooks against real
  tasks on every change; our harness config changes are verified structurally, not
  behaviourally (adjacent, not intent-layer).
- **Always-loaded surface.** Playbook: CLAUDE.md under one page. Ours: ~425 lines; the intent
  layer deliberately adds nothing to it, but it also can't fix it.
- **Separation of duties.** `approved_by` = `git config user.name`, not forgery-proof; fine
  solo, inadequate for an org that wants the Playbook's PO/release-manager split.

### Follow-up (user question): intent folder + role-owned artifacts

The user asked whether two Playbook traits are worth adopting: (1) intents stored together in
their own folder, (2) role ownership — PO owns `intent.md` + `spec.md`, the team owns
`CLAUDE.md`, the developer owns `plan.md`.

**What the Playbook actually says (fetched 2026-09-19).** "For a single product the simplest
home is an `intent/` folder in the product repo … in a monorepo it is a directory." Ownership:
`intent.md` authored by the originator with Claude, **approved by the PO**; `spec.md` generated
by Claude, **approved by the PO** (tech lead for higher risk); `plan.md` drafted by Claude in
plan mode interviewing the engineer, **approved by the engineer**; `CLAUDE.md` "checked into
git … so the whole team shares one version and changes are reviewed like code"; skills owned by
policy owners, hooks/managed settings by platform. The Playbook gives **no guidance for solo
developers or overlapping roles**, and no lifecycle for an `intent.md` after it ships.

**Current harness-maker state (facts).**

| Artifact | Where | Who authors | Who approves | Gate |
|---|---|---|---|---|
| Objective (≈ intent) | `work-docs/INTENT-<ID>.md` — 2 files among 470 flat files in `work-docs/` (184 REVIEW, 140 PLAN, 90 RESEARCH) | LLM drafts after consent, human edits | Human `objective approve` → `approved_by = git config user.name` (`world.py:1494-1498`), hash-bound | Autopilot halts on `approval_invalid`/`not_active` (only if a PLAN links it) |
| SPEC | `specs/SPEC-<slug>.md` — **already a separate folder** | LLM from interview | **Nobody** — `status: approved` is set automatically when Open Questions is empty (spec Step 5) | "No mandatory gate — spec may auto-advance" |
| PLAN | `work-docs/PLAN-<slug>.md` | LLM from interview + ADRs | Nobody explicitly; the human is present in the interview | Blocks only on validator MAJOR_REVISION + unresolved A/B |
| CLAUDE.md | repo root | Harness renders the frame; `@hm:user:project-rules` / `@hm:user:extensions` blocks preserved across upgrades | — | context-lint line cap |
| Roles | `intent.yaml` has an `owners: []` field (`intent.py:22,123,364`) — **parsed but unused** | — | — | — |

**(1) Intent folder — assessment: worth doing, keep state out of the path.**
- *For:* an objective's lifecycle differs from every other deliverable — long-lived,
  1:N with tasks, four states — while PLAN/REVIEW/RESEARCH are per-task. Mixed into 470 flat
  files, "what are we pursuing?" is not answerable by `ls`. A path is also what path-based
  ownership needs: GitHub `CODEOWNERS` can assign `intent/` to a PO; a filename prefix inside
  `work-docs/` cannot be assigned as cleanly. And `specs/` already proves the deliverable
  machinery supports a per-type folder (`_is_deliverable_path` covers `specs/SPEC-*.md`).
- *Against:* [[RESEARCH-playbook-alignment]] rejected a second folder because the deliverable
  machinery is keyed to `work-docs/<PREFIX>-` (DELIVERABLE_PREFIXES, gitignore negation,
  `derive_deliverable_globs`, `spec_gate`, create-guard exemption, sweep, render manifest).
  That cost is real but bounded — the `specs/` precedent means it is extending an existing
  pattern, not inventing one. Migration of the existing records + the loader (`world.py:165`)
  follows the same "old location reported as an error" pattern already used for
  `.claude/world/objectives/`.
- *Trap:* do **not** split by state (`intent/active/`, `intent/closed/`). State is a
  frontmatter field today; moving files on transition breaks `[[links]]` and `objective:` PLAN
  frontmatter, and turns every state change into a git rename. Folder = type, frontmatter = state.
- *Semantic gap to settle first:* the Playbook's `intent.md` is **per idea, paired 1:1 with a
  `spec.md`**; our objective is a **hypothesis bound to an outcome, 1:N with tasks**. An
  `intent/` folder must pick one meaning, or hold both with a declared relation
  (objective → many intents). Renaming the folder without resolving this imports the name but
  not the model.

**(2) Role ownership — assessment: adopt as declared ownership, gate only when roles differ.**
- *For:* the split maps onto harness-maker's existing stage boundary almost exactly — our own
  contract already says `spec` owns *what/why/verification* and `plan` owns *how/risk/phasing*.
  PO↔(intent, spec) and developer↔plan is the same line drawn with people. "Team owns
  CLAUDE.md" is what the `@hm:user:*` blocks already implement (harness owns the frame, team
  owns the preserved blocks). And it exposes our weakest link: **SPEC has no human approval at
  all** — it is marked `approved` by the absence of open questions, while the objective one
  level up has a hash-bound human stamp. The Playbook's PO spec sign-off is the piece we lack.
- *Against:* harness-maker's typical user (and this dogfood repo) is one person holding every
  role. Mandatory PO/dev sign-offs there are self-approval ceremony, and the Playbook's own
  anti-pattern #3 warns that approval prompts before deploy put a person back on the critical
  path — directly against CLAUDE.md 제1목표. Enforcement is also not local: `approved_by` is an
  unverified `git config` string; real separation of duties needs `CODEOWNERS` + branch
  protection on the host, which the harness can recommend but not enforce.
- *Inference — a shape that fits both:* fill the existing, unused `owners` field with a role
  map (`po`, `dev`, `team`), and let a gate fire **only when the roles resolve to different
  people**. Solo repo → roles collapse → zero new prompts; team repo → PO sign-off on spec
  (hash-bound, same mechanism as `objective approve`) and developer sign-off on plan become
  real gates. This turns the Playbook's role model into configuration instead of a fixed
  process. Not validated with any team user — label as hypothesis.

### Revised hierarchy (user reframe): IC → AI agent, developer → DRI

The user's premise: the IC (the developer who writes plans and code) is replaced by AI agents,
and the human developer becomes the **DRI** — so does the DRI become the PO? The Playbook
leans this way ("human engineers focus on directing, setting intent, and owning final
approval"; Claude authors ~80% of merged code at Anthropic), yet it still keeps
`plan.md` approval with the engineer. That residue is the point to resolve.

**Assessment: DRI absorbs the PO's task-level role, but not all of it, and not only it.**

- *DRI ⊃ task-level PO.* For a single change, "why / what / what counts as done" moves to the
  person who is accountable for the result. Agreed.
- *DRI keeps technical acceptance.* What leaves with the IC is **authorship** (writing the plan,
  the code, the tests) — not **acceptance of risk**. The evidence stream says acceptance is the
  new bottleneck, not authorship: AI PRs accepted 32.7% vs 84.4% (LinearB), 10.7% lucky passes
  among passing trajectories (AgentLens) — both via [[RESEARCH-cell-dev-future-and-intent-layer-fit]];
  "a weak intent.md can scale the wrong priority" (Zeniteq). Anthropic's security practice
  keeps a separate approving identity from the writing agent and risk-weighted **human sampling**
  of automated approvals. So the DRI is **PO + tech lead collapsed**, not PO alone. If the DRI
  becomes pure PO, nobody holds the irreversible technical decisions.
- *The line inside "how" is reversibility.* The DRI does not need to approve a plan; it needs to
  lock the **irreversible** decisions in it (schema, public API, migration, security boundary,
  dependency choice). Reversible choices belong to the agent. harness-maker's interview
  envelope already carries a `Reversibility` field per question — that is where the line lives.
- *The oracle is the DRI's most important input.* With an agent writing both code and tests,
  the circular-oracle risk is the agent grading itself. `/hm:spec` 2.1.5 already forces oracle
  source + independence evidence; in the DRI model this becomes the human's central act.
- *PO does not vanish; it moves up one altitude.* Across several DRIs (or several tasks of one
  DRI), someone decides which outcome matters and which objective to pursue. That is exactly our
  **two-level** design — `intent.yaml` mission/outcomes + objective approval (owner altitude) vs
  SPEC/PLAN lock-ins (DRI altitude). The Playbook has only the per-change level; the reframe is an
  argument **for** our two levels, not against them.

**Resulting hierarchy**

| Level | Who | Owns (decides) | harness-maker artifact / act today |
|---|---|---|---|
| Owner (portfolio PO) | human | mission, outcomes + targets, which objective is worth pursuing | `.claude/intent.yaml`, `objective approve/activate/close` (hash-bound) |
| DRI | human (ex-developer) | task why/what, acceptance criteria **+ oracle**, irreversible design decisions, risk acceptance, land | `/hm:spec` interview (no approval stamp today), `/hm:plan` ADR lock-in, wrapup land |
| IC | AI agents | drafts of intent prose/SPEC/PLAN, implementation, tests, reversible choices | `executor`, `autoloop-coder`, stage prompts |
| Verifier | AI (independent identity / other model) + deterministic oracles; human samples | defect finding, not acceptance | `/hm:review` k-of-N + cross-model, `/hm:verify`, `code-verifier` |
| Team / platform | humans (collective) | institutional knowledge: CLAUDE.md, skills, hooks | harness frame + `@hm:user:*` blocks |

Solo repo: Owner = DRI = Team — one person, three altitudes. Small team: one Owner, N DRIs,
shared Team layer. The earlier `{po, dev, team}` role map is therefore wrong: `dev` is no longer
a human role. The right map is **`{owner, dri, team}`**, and "gate only when roles differ" now
means: Owner≠DRI → objective approval stays with the owner, SPEC acceptance + irreversible
ADRs with the DRI.

**Consequences for harness-maker (inference):**
1. **SPEC acceptance becomes the DRI's stamp.** The auto-`approved` SPEC (Open Questions empty)
   is the gap this hierarchy exposes most sharply — it is the DRI's primary act and today has no
   record of who accepted it. A hash-bound `spec approve` mirroring `objective approve` fits.
2. **PLAN approval → irreversible-ADR lock-in only.** No new "approve plan" gate; instead ADRs
   tagged irreversible must be human-answered, reversible ones may be agent-decided.
3. **`auto_full` is the DRI's explicit delegation — keep it.** Today `auto_full` lets the agent
   answer a plan/review judgment gate (logged as `gate_auto_answered`, `autopilot_caps.py:517-541`).
   **User decision (2026-09-19): do not forbid it for irreversible decisions** — choosing
   `auto_full` is the DRI explicitly delegating those judgments, a dangerous but consented mode.
   What remains useful is *visibility*, not a block: an auto-answered irreversible decision
   should be tagged as such in the record so the DRI can review it after the fact. Residual
   team-mode caveat: `autonomy.level` in a committed `harness.yaml` is set by whoever committed
   it, so in a team the consenting person may not be the DRI running the task.
4. **The agent must never approve what it wrote** — already true (the proposer never runs
   `approve`); the hierarchy makes it a principle rather than a rule of one skill.
5. **`intent/` folder = owner altitude.** Per-task intent already lives in SPEC `## 🎯 Intent`
   (1:1 with the change — the Playbook's `intent.md` + `spec.md` pair folded into one file).
   So `intent/` should hold objectives, which resolves Open Question 6.

**Concern (lead):** the reframe is right about authorship and risky if read as "the human only
does product". The failure mode it invites is the DRI accepting on intent alone — reading the
agent's summary rather than the oracle's verdict — which is the lucky-pass / review-bottleneck
problem with the human removed. The DRI's time should move from writing to **choosing oracles
and locking irreversible decisions**, not to nothing.

### Follow-up 2 (user proposals): drop `/hm:plan`; anyone proposes, Owner approves; ticket intake

**(a) Absorb `/hm:plan` into spec + execute — assessment: drop the stage and its gate, keep
the artifact as agent-owned state.**

What `/hm:plan` carries today, split by the DRI hierarchy:

| Plan content | Who should own it | Where it goes |
|---|---|---|
| Irreversible decisions (schema, public API/CLI, file format, migration, security boundary, new dependency) | DRI | **SPEC** — these are externally observable contracts, i.e. *what*, not *how*; SPEC's own skip heuristic already treats "API / IPC / DB schema / file format change" as the thing that makes a SPEC necessary |
| Objective link + Step 0.5 "which objective does this serve?" (`plan.md.j2:91-120`) | DRI | SPEC Step 0 + SPEC frontmatter `objective:` |
| Phases, file list, order, risks, exit criteria | IC (agent) | `/hm:execute` Step 0 writes it — no human gate (host plan mode is the native equivalent; Playbook's `plan.md` *is* Claude Code plan mode) |
| plan-validator critique | — | optional; its discrimination is unproven (37/40 MAJOR_REVISION, CLAUDE.md §Step sensitivity) |
| Multi-phase decomposition for large work | DRI decides the split, agent drafts | SPEC hierarchy (`parent_spec` already exists) |

- *For:* CLAUDE.md 제1목표; the human-valuable part of plan (irreversible lock-in) fits SPEC,
  and the rest is authorship that belongs to the IC. Removes one interview, one validator pass
  and one auto-advance boundary per task. Consistent with "let the host absorb behaviour"
  ([[RESEARCH-cell-dev-future-and-intent-layer-fit]]).
- *Against / what breaks:* PLAN is referenced across the pipeline — `execute.md.j2` 48×,
  `wrapup.md.j2` 29×, `review.md.j2` 16×, `verify.md.j2` 10×, `loop.md.j2` 9×; `/hm:loop`
  iterates over a master PLAN and per-iter PLANs inherit `objective:` from it. The PLAN file is
  also **INV-class state** — the thing that survives context windows on long tasks. So the file
  cannot simply vanish; what can vanish is the stage, the interview and the gate.
- *Risk:* SPEC interview grows (it absorbs the ADR questions), and in `dev_mode: task-driven`
  plan is the main entry point today — removing it makes SPEC mandatory for every task, which
  may cost more than it saves for small tasks. A light SPEC (Step 0 skip heuristic) must stay
  genuinely light.
- *Net:* high-value simplification, but a large migration (every stage template + loop +
  snapshots + surface baselines). Candidate for its own PLAN, not a side effect of this one.

**(b) Anyone proposes, Owner approves — also for mission/outcomes.**

- *Objectives* already have the shape: `proposed` is writable by anyone (DRI, or the agent
  after consent), `approve`/`activate` are human-only. The missing piece is **who** may approve:
  `approve` accepts any `git config user.name` (`world.py:1494-1498`). Checking the approver
  against `owners` (the unused field) is a small change; real enforcement still needs host
  `CODEOWNERS`.
- *Mission/outcomes* change rarely and sit at the highest altitude. A new in-harness proposal
  state machine for them would be heavy. The git-native path is enough: a proposal is a PR/commit
  touching `.claude/intent.yaml`, the Owner approves it as a code owner. Outcome edits already
  invalidate old values via `definition_hash`, so a changed target cannot silently reuse stale
  measurements.
- *Concern:* "anyone proposes" without a decline record floods the Owner. `rejected[]` /
  `--declined` exist for objectives; there is nothing equivalent for rejected outcome proposals
  (a closed PR is the record).

**(c) Ticket intake — "a Jira ticket arrives; where does the DRI start?"**

Principle: **a ticket is task-level input. It never edits the mission, and it only reaches the
Owner when it does not fit anything already approved.**

```
ticket ──► classify (agent drafts, DRI confirms, using `hm world status`)
  ├─ bug / incident / chore (keeps what exists working)
  │     └─► SPEC directly. No objective. Measured by change_failure_rate / non_negotiables.
  ├─ fits an ACTIVE objective
  │     └─► SPEC with objective: <ID>. No Owner involvement.
  ├─ fits an OUTCOME, no objective yet
  │     └─► DRI creates objective `proposed` ─► research/spec may proceed
  │         execute waits for Owner approve+activate (autopilot gate already halts on not_active)
  ├─ matches an objective's rejected[] or non_scope
  │     └─► surface the earlier decision; decline or ask Owner to revisit (`objective revisit`)
  └─ fits NO outcome
        ├─ out of scope ─► decline, record why (non_scope / ticket comment)
        └─ mission/outcomes incomplete ─► propose outcome change to Owner (PR on intent.yaml);
           the ticket waits or proceeds as a chore — never silently extends the mission
```

- The ticket id travels as a link, not a sync: e.g. `external_ref: JIRA-123` on SPEC/objective
  frontmatter, commit SHA back on the ticket (Playbook "linkage minimum"). No such field exists
  today (no `jira`/`external_ref`/`ticket` in `src/harness_maker/*.py`); Jira/Linear sync stays
  out of scope per [[SPEC-intent-world-model-objective-layer]].
- Most tickets land in the first two branches — the Owner stays off the DRI's critical path,
  which is what keeps "Owner approves" from becoming the Playbook's approval-bottleneck
  anti-pattern.

### Follow-up 3 (user): plan-validator → spec-validator, task-driven mode, vocabulary

**(a) plan-validator → spec-validator — assessment: do not rename; re-scope and prove it.**
- *Concern first:* plan-validator's discrimination is unproven — 37 of 40 runs returned
  MAJOR_REVISION (CLAUDE.md §Step sensitivity, TUNE). A rename carries a gate that flags almost
  everything into the one stage that is now the DRI's main act; it becomes noise the DRI learns
  to click through.
- *What exists:* SPEC already has a gate, but it is **heuristic by default** —
  `spec_quality.score` uses `_heuristic_score` unless a judge is passed
  (`spec_quality.py:95, 226`). So an LLM critic on SPEC would add judgment the stage lacks,
  consistent with the "LLM judgment over rules" principle.
- *Shape that fits:* one read-only `spec-validator` pass (single pass, no re-validation — same
  rule as today's plan-validator), scoped to what the DRI must decide: missing or contradictory
  ACs, circular oracles, **irreversible decisions implied by the ACs but not listed**. Run it
  only when the SPEC declares or implies an irreversible decision or is not Step-0-light; skip
  otherwise. Record verdict vs. later review findings so its discrimination is measured from the
  first run (TUNE entry with a `measure_cmd`), not assumed.

**(b) task-driven mode — assessment: stop making dev_mode decide which stages exist.**
- *Fact:* README defines `dev_mode` as "whether SPEC stage is mandatory; whether plan stages
  chain into execute". In task-driven, SPEC-need detection is not rendered
  (`plan.md.j2:182-185`), the quality gate only warns (`spec.md.j2:333`), and plan is the entry
  point. Removing plan removes task-driven's entry.
- *Option A (recommended):* **one entry artifact for both modes — a SPEC, light in
  task-driven.** Step 0's existing skip path already writes a minimal SPEC (Intent + one G-W-T +
  "manual smoke") without an interview; add the irreversible-decisions list (usually empty).
  `dev_mode` then means only *gate strictness* (spec-driven blocks, task-driven warns — as today
  for quality and oracle waivers), not *which stages run*. Ticket intake (Follow-up 2c) already
  routes every ticket to SPEC, so both modes share one path.
- *Option B:* task-driven goes ticket → execute; execute Step 0 writes the agent PLAN and asks
  the DRI only the irreversible questions. Keeps a mini-interview inside execute, splits the DRI
  act across two stages, and leaves two entry paths to maintain.
- *Risk of A:* task-driven users picked it to avoid SPEC ceremony. A must keep the light SPEC
  genuinely zero-interview for trivial work, or it re-imposes what they opted out of.

**(c) Vocabulary — assessment: agree the terms are too many; one umbrella word for the user,
two levels underneath, internal distinctions kept.**
- *Count (fact):* the layer surfaces ~17 terms: `world` (CLI), intent, mission, vision,
  outcome, measure, objective, hypothesis, assumption, evidence, revisit_when, gap, withdrawal,
  non_negotiables, non_scope, unknowns, rejected. Plus two overlapping lists: `intent.yaml
  unknowns` and assumptions with status `unknown`.
- *Concern with a single word for everything:* the four concepts behave differently — a
  purpose that almost never changes, a measured number, a bet with approval and a lifecycle, a
  belief with evidence. One noun for all four makes verbs ambiguous ("approve the intent" —
  which one?).
- *Proposal — what the user sees:*

| Today | Plain name | Where |
|---|---|---|
| `hm world …` | `hm intent …` | CLI |
| mission (+ vision) | **purpose** (목적) | project intent, `intent.yaml` |
| outcomes (+ measure) | **metrics** (지표) | project intent |
| non_negotiables / non_scope | **rules** / **out of scope** | project intent |
| objective (+ hypothesis) | **intent** (건별 의도) | `intent/<ID>.md` — the file is already named `INTENT-<ID>.md` |
| assumptions + unknowns | **open questions** with an answer state: open → confirmed / wrong | one list, replaces both |
| gap / revisit / withdrawal | folded into `hm intent status` output; not user words | — |

  Result: one umbrella word (intent), two levels (project intent, intents), three sub-parts
  (purpose, metrics, open questions). The assumption state machine survives under plain states
  (known = confirmed, unknown = open, assumed = open with a guess, conflict = wrong).
  The playbook uses "intent" for the per-idea artifact, so objective → intent also aligns
  vocabulary with the Playbook.
- *Cost:* CLI verb rename (keep `hm world` as a deprecated alias one release), schema key
  renames in `intent.yaml` with a load-time migration, stage template prose, skill, tests,
  snapshots, surface baselines. Medium; mostly mechanical.

### Follow-up 4 (user): remove `dev_mode: task-driven`; who writes what

**(a) Remove the `dev_mode` axis — assessment: agree; it is the simplest form of Option A.**
- *Why it works:* once every task enters through a SPEC, `dev_mode` no longer decides which
  stages exist — only how strict the SPEC gates are. That is a preset-shaped default, not an
  independent axis. Replace it with one knob derived from preset and overridable:
  `spec.strictness: block | warn` (Production → `block`, Side → `warn` + light SPEC by default).
  Four preset × dev_mode combinations become two presets with one override.
- *This reverses an earlier lock-in:* the dev_mode axis was deliberately made orthogonal to
  preset with all four crosses allowed (memory `project_dev_mode_axis`). Record the reversal and
  its reason in the PLAN's ADR, not silently.
- *What `dev_mode` gates today (must each get a new home):* the `spec_gate` hook
  (`settings/Side.json.j2:39`, `hooks.json.j2:40`), verify Check 6 — the SPEC operational
  check (`verify.md.j2:156, 233`), SPEC-need detection (`plan.md.j2:182`), quality-gate block vs
  warn (`spec.md.j2:333`), oracle-independence waiver (`spec.md.j2:128`, wrapup Step 3.6).
  Surface: 15 Python modules + ~19 templates reference `dev_mode`.
- *Migration:* an existing `dev_mode: task-driven` harness maps to `spec.strictness: warn`
  **without changing its preset** (a Production + task-driven user must not be silently moved to
  Side). `dev_mode` key read once, warned, dropped — same pattern as the retired
  `feature_branch_workflow` (single reader, present-but-malformed fails closed).
- *Risk:* "light SPEC" must stay zero-interview for trivial work in `warn` mode; otherwise Side
  users get the ceremony they opted out of.

**(b) Who writes what — assessment: yes, with one refinement: "propose" differs by level.**

| Item | Who proposes | Who decides / writes | Where the proposal lives |
|---|---|---|---|
| purpose (mission), metrics (outcomes), rules, out of scope | anyone | **Owner only** | outside the harness — a PR / discussion on `.claude/intent.yaml`; nothing half-approved is ever live state |
| intent (objective) | **anyone** — DRI, or the agent after consent | Owner approves + activates; Owner closes (met/missed) | inside the harness — a `proposed` record in `intent/`, visible in `status`; research/spec may start on it, execute waits for approval |
| open questions (assumptions) | anyone records an observation | whoever owns the affected item resolves `wrong` (a metric → Owner; a task decision → DRI) | inside the harness — evidence, not a decision |
| task (SPEC) | DRI (from a ticket or idea) | DRI approves | `specs/` |

- *Why the two proposal paths differ:* purpose/metrics change rarely and a pending change to a
  metric must not be read as the current target, so the proposal stays out of the live file.
  Intents are frequent and a pending one is useful state (visible, linkable, can start
  research), so the proposal lives in the repo as `proposed`.
- *Enforcement reality:* "Owner only writes `intent.yaml`" cannot be enforced locally — anyone
  can edit a file. Real enforcement is host `CODEOWNERS` + branch protection. A cheap local
  signal: `status` warns when the last commit touching `intent.yaml` is not by an Owner.
  Same for `approve`: check the approver against `owners` (still spoofable via `git config`).
- *Solo repo:* all rows collapse to one person; none of this adds a prompt.

### Self-critique and ranked improvements

A Codex cross-model review was attempted on 2026-09-19 and **failed on the Codex usage limit
before producing output**; the user chose to proceed without a cross-model review. What follows
is a single-model adversarial pass — treat it as unreviewed.

**Holes in the proposals above**
1. *"Irreversible decisions are contracts, so they fit SPEC" is only mostly true.* A storage
   engine, an on-disk layout, a lock protocol or a concurrency model can be irreversible without
   being in any AC. Without a plan gate, such a decision discovered mid-implementation has no
   human checkpoint. **Needed:** an execute rule — on hitting an irreversible decision not
   covered by the approved SPEC, stop and escalate to the DRI (under `auto_full` the agent may
   answer it — the user's explicit delegation — but the answer is tagged `irreversible` in the record).
2. *Removing plan before SPEC can hold ADRs removes the only lock-in point.* Ordering matters:
   SPEC approval + an irreversible-decisions section must exist first; plan absorption last.
3. *The "bug/chore → no objective" branch is a bypass.* Anything relabelled as a chore skips
   the Owner. **Cheap signal:** report the share of landed SPECs with no `objective:` link in
   `gap` — a rising share means either bypass or missing outcomes, and both are Owner questions.
4. *Owner latency.* "execute waits for Owner approval" can stall a DRI. `status` should surface
   `proposed` objectives by age so the queue is visible; no timeout auto-approval.
5. *The DRI's land decision rests on oracles, and one oracle is broken.* The mutation gate has
   collected 0 mutants for five tasks (`[fail:tooling] mutation-gate-…`). In a model where the
   human accepts on oracle verdicts, a silent oracle is a direct acceptance risk, not tooling debt.
6. *Proposals on a `proposed` objective* can waste research/spec if the Owner rejects; accepted
   as cheap relative to execute, but the SPEC should record the objective state it was written
   under.

**Ranked (value ÷ cost), informational**

| # | Improvement | Value | Cost | Depends on |
|---|---|---|---|---|
| 1 | DRI `spec approve` — hash-bound, mirrors `objective approve`; replaces auto-`approved` | high | low | — |
| 2 | Irreversible-decisions section in SPEC + execute escalate-on-new-irreversible (under `auto_full`: answered, but tagged for later review) | high | low–med | 1 |
| 3 | Ticket intake: classify at SPEC Step 0, `external_ref` field, unlinked-work share in `gap` | med | low | — |
| 4 | Fix the mutation oracle (0 mutants × 5 tasks) | med–high | med | — |
| 5 | `owners` role map `{owner, dri, team}`; `approve` checks the approver; gates collapse when same person | med (teams) / ~0 (solo) | low | 1 |
| 6 | Absorb `/hm:plan` into SPEC (human part) + execute (agent part), keep PLAN file as agent state | high | **high** | 1, 2 |
| 7 | `intent/` folder for objectives | low–med | med | — |

**Where they are simply different (not better/worse)**
- Playbook = process for organisations; ours = state for an operator. Human-in-the-loop
  placement also differs: the Playbook warns against approval prompts during Build; our
  autopilot gate halts on `not_active`/`approval_invalid` *before* stages advance — earlier,
  but only when an objective is linked.

### Independent review (2026-09-19) — supersedes parts of the above

Two fresh Claude reviewers (no shared context with the author; Codex unavailable on quota) read
this document, the one-page summary and the code. Top claims spot-checked by the author against
the code: `autopilot_caps.py:60`, `world.py:882-886`, `spec.md.j2:342`, `spec_gate.py:111`,
`intent.py:280-282` — all confirmed.

**Blockers (would break or silently remove a human gate)**
1. **Removing plan removes autopilot's only pre-execute human stop.** `_JUDGMENT_GATED_STAGES =
   {"plan","review"}` (`autopilot_caps.py:60`); spec "may auto-advance". `auto_safe` would run
   research → spec → execute unattended; `spec approve` is inert unless the boundary checks it.
2. **`plan` is in every `autonomy.pipeline`** (`models.py:934-944`). Dropping it from the enum
   invalidates the block → silent fallback to `gated` (the `guard_when` precedent) and unloadable
   live markers; keeping it points the chain at an unrendered stage.
3. **Objective-link readers read PLAN only** (`autopilot_caps.py:261,277`, `review.md.j2:381`,
   `wrapup.md.j2:583`). Moving the link to SPEC makes all three silently skip; at the
   spec→execute boundary no PLAN exists, so a `proposed` objective is not gated.
4. **Agent-written PLAN makes review's drift check self-grading** (`review.md.j2:156-160`,
   `execute.md.j2:99-110`) — the self-approval this document forbids.
5. **Verify Check 6 becomes a permanent PASS** — `spec_need_verdict` is written only by plan
   Step 1.7; absent = "clean N-A PASS" (`verify.md.j2:161`).

**Self-contradictions in the design**
6. "Zero new prompts for solo" vs `spec approve` as a human act. Resolution needed: `spec approve`
   is a DRI act that exists even when roles collapse; collapse removes only cross-person gates.
7. `auto_full` "tagged for later review" + automatic squash-land (wrapup Step 7.7) = review after
   landing. Land must hold while an `irreversible` tag is unreviewed.
8. **The withdrawal arbiter this document leaned on can no longer fire**: `withdrawal_due` requires
   `observed == 0` (`world.py:882-886`); the dogfood repo already has `objectives_observed = 1`.
   The largest expansion of the layer is being proposed with no working kill switch, on evidence
   of 3 days / 2 intents / 1 assumption / one repo. Per the pre-registration rule, the existing
   criterion must not be reinterpreted; a new, fireable criterion must be registered *before*
   expanding.
9. Vocabulary: "intent" would name five things (`intent.yaml`, objectives, SPEC `## 🎯 Intent`,
   the Playbook's `intent.md`, the `intent-layer` skill); this document both maps the Playbook's
   `intent.md` to SPEC's Intent section and to objective. **"open questions" collides with
   `## ❓ Open Questions`**, whose emptiness sets SPEC `status: approved` (`spec.md.j2:342`) — an
   agent told to "record an open question" can flip a SPEC to `draft`. Folding `assumed` into
   `open` loses the riskiest state ("acting on an unconfirmed belief").

**Silent degradation on migration**
10. `dev_mode` absent-case diverges by reader: `spec_gate` turns off (`spec_gate.py:111`),
    `spec_drift`/`spec_quality` fall back to task-driven, `spec_need` fails closed. Deriving
    strictness from preset silently demotes Side + spec-driven. Map by the old `dev_mode` value on
    all four crosses; convert all readers in one release.
11. Renames: `approval_hash` hashes the literal key `outcome_id` (`world.py:213-224`) — renaming it
    invalidates every approval and halts every linked task. `intent.py` rejects unknown top-level
    keys (`intent.py:280-282`) and `_filled_at` re-parses history, so a new-keys-only loader resets
    the withdrawal clock and breaks older plugin readers. `revisit_when` matches stored status
    strings. `owners` must be a list of strings (`intent.py:292-296`) — a role map is a schema
    bump, not "filling the field".
12. `spec approve` hash scope: SPECs are living (174 `verified`), with execute-edited fields
    (`test_ids`, `pending_test`, scores). Hash only AC text + oracle + irreversible list.

**Cost the document under-rated (P2)**: SPEC becomes the bottleneck (it absorbs plan's ADR
questions, and many irreversible decisions surface only after reading code); a zero-question
light SPEC either stays narrow (Side users get *more* ceremony) or means no human acceptance;
owner absence / delegate / identity aliases undefined; `intent/` is outside `_DELIVERABLE_RE`
(`worktree.py:225-232`) and `wrapup_land.py:262`; `/hm:health` hardcodes the plan stage
(`readiness.py:1492`); 14 of 19 plan headings are INV in the step-sensitivity registry
("delete only from measurement"); `surface_allowance` keys on PLAN `status`. Taken together the
follow-ups amount to Approach C by accumulation — the option this document rated high-risk.

**Corrections to claims made above**
- Per-iter PLANs do **not** carry `objective:`; readers find the master PLAN by slug.
- `/hm:loop` runs from `work-docs/loop-context/<slug>.yaml`, not from a master PLAN; it depends
  on PLAN via execute's hard error (`execute.md.j2:92`).
- "execute waits for Owner approval" holds only under autopilot *and* when the PLAN carries the
  link; manual `/hm:execute` has no objective gate.
- `spec_gate` is rendered at 5 sites, not 2 (+ `Production.json.j2:90`, `cursor/hooks.json.j2:40`,
  `codex/hooks.json.j2:32`). `dev_mode` surface is 18 modules + 20 templates, not 15 + ~19.
- `owners` cannot hold a role map without a schema change.
- The TL;DR ("do not import the Playbook's role/gate machinery") no longer matches the
  follow-ups; it must be rewritten before `/hm:plan`.

### Open-source harness survey (2026-09-19)

Surveyed spec-kit v1.0.8, superpowers v6.4.1, BMAD v6.12.0, Kiro (closed, widely copied),
Agent OS v3.0, Taskmaster, ECC, Cline Memory Bank / AGENTS.md (star counts via GitHub API).
Not examined: SuperClaude, ruflo, Roo Code, OpenHands.

- **Ceremony is being scaled to risk, not fixed.** Agent OS v3 retired its task/implementation
  phases ("frontier models handle this well on their own now"); BMAD `bmad-build` plans inside
  execution and asks for plan approval **only when flagged on intent gaps, irreversible actions
  and footprint**; Kiro added Quick Plan to skip per-phase approval. Supports absorbing plan.
- **Counter-evidence.** spec-kit keeps HOW out of the spec so the spec survives a technology
  change → irreversible technical choices belong in a *separate* SPEC section, not mixed into
  WHAT. superpowers keeps a detailed plan because it lets a zero-context or cheaper subagent
  execute → if execute delegates, it must still write per-task briefs.
- **No surveyed tool binds approval to content.** superpowers approval is conversational
  ("a reply approves the stage actually presented"); spec-kit uses reviewer-owned checklist
  `[x]` that implement reads read-only — both prompt-enforced, flippable by an agent.
- **Admission test for irreversible decisions** (BMAD architecture spine): admit only if two
  units working independently could choose incompatibly, the call is non-obvious, and it is a
  real trade-off; each gets a stable ID specs cite. Guards against list inflation.
- **Review "decision needed" route** (BMAD) and **append-only `converge`** (spec-kit: compares
  code to spec, may only append tasks, never edits code) — candidate later slices.
- **Criticisms:** one-size ceremony (Kiro: 4 stories / 16 ACs for a small bug; "8 files and
  1,300 lines" for a date display), double review of spec and code, false sense of control,
  spec drift, token cost (superpowers). Sources: martinfowler.com (Böckeler), Marmelab, HN
  45935763, spec-kit #620/#1063/#1671.
- Sources: https://github.com/github/spec-kit/blob/main/spec-driven.md ·
  https://github.com/obra/superpowers · https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/build/build-a-change.md ·
  https://github.com/buildermethods/agent-os/blob/main/CHANGELOG.md · https://kiro.dev/blog/faster-smarter-specs/ ·
  https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html

### Survey 2: Ouroboros, oh-my-openagent, oh-my-claudecode (2026-09-19)

- **Q00/ouroboros** (6.0k★): interview → `seed.yaml` → run → evaluate → evolve. Spec gate is an
  LLM-scored **ambiguity ≤ 0.2**, bypassable with a recorded `gate_forced`; no human stamp.
  Records `decision_provenance` counts (`user_confirmed` / `model_inferred` / `timeout_default`).
  **No plan stage** — ACs decomposed at runtime. Evaluation = mechanical → semantic (≥0.8) →
  2/3 multi-model consensus on triggers; **the worker never sees verify commands**;
  "completion is not approval" (`not_evaluated` stays). AC ids = `ac_` + sha256(content)[:16].
  Weaknesses in its own issues: missing answers push the score under threshold (#2414); the
  meaningful signal is the override rate, not the score (#2231); score not persisted (#1901).
- **code-yeongyu/oh-my-openagent** (ex-oh-my-opencode, 69.2k★): `/ulw-plan` → `.omo/plans/<slug>.md`
  → `/ulw-execute` with evidence ledger. Keeps a reviewed **plan stage** (plan-consultant +
  plan-reviewer, ≤5 rounds). **"Owner-decisions"** — irreversible/destructive/costly, public
  config surface, packaging, external deps/pinned SHAs, data/schema shape, scale, compliance —
  always survive as questions; "stop asking" never authorizes them. Approval = chat +
  `status: awaiting-approval`, no hash; plan approval ≠ execution approval.
- **Yeachan-Heo/oh-my-claudecode** (39.2k★): Ouroboros-inspired `deep-interview` (threshold
  0.2) **plus** explicit approval; `ralplan` keeps Planner→Architect→Critic with a decision
  record; `ralph` keeps a `criterionAmendments` ledger (original verbatim + kind, evidence,
  authority, timestamp).
- **Takeaways:** none binds approval to content (our hash is stronger); a score is a weaker
  gate than a human stamp but a useful advisory with override-rate tracking; OmO's
  owner-decision list ≈ our five categories, plus cost/scale/compliance; provenance counts and
  an amendment ledger make the DRI's review cheap; runtime decomposition (Ouroboros) supports
  folding plan, while OmO/OMC keep an independent pre-execute critique.
- Sources: https://github.com/Q00/ouroboros · https://github.com/code-yeongyu/oh-my-openagent ·
  https://github.com/Yeachan-Heo/oh-my-claudecode

### Consolidated position for this slice (input to the Codex review)

Keep (validated by both surveys): human hash-bound `spec approve` as the gate (no surveyed tool
binds approval to content); irreversible decisions in a section separate from WHAT (spec-kit);
land hold. Candidate refinements, not yet locked:
1. List item = `{id: IRR-NNN, decision, category, rationale, source: spec|execute, added_at}` —
   readable sequential id (content-change detection is already the approval hash's job, so a
   content-hash id would be redundant); `source` gives OMC-style amendment provenance.
2. Admission test (BMAD) on top of the categories: independent units could choose
   incompatibly, non-obvious, real trade-off. Consider adding OmO's cost/scale/compliance.
3. `approval.provenance`: counts of DRI-answered vs defaulted decisions (Ouroboros), so the
   stamp says how much the DRI actually decided.
4. No ambiguity-score gate; at most an advisory with override tracking.
5. Later slices: hide oracles from the worker (Ouroboros) — tension with TDD test authoring;
   keep an independent pre-execute critique when plan is folded (OmO/OMC); BMAD
   "decision needed" review route → land hold; spec-kit append-only `converge`.

### Codex cross-model review of the consolidated position (2026-09-19)

Codex reviewed RESEARCH + SPEC + code. Spot-checked by the author: `command_registry.py:65`,
`spec_machine.py:1371` (guard before parser), `spec_machine.py:1007`, `worktree.py:5254`,
`loop.md.j2:976` — confirmed. Findings the two Claude reviews missed:
- **Hash scope misses oracle inputs** (`rubric_id`, `judgment_subject_paths`, `preconditions`,
  `observable_output`): pointing a judgment subject at a non-existent path makes the gate skip
  it as "future work" while the approval stays valid. → hash every AC field except an explicit
  bookkeeping deny-list.
- **Deleting the irreversible list removes the hold**: an approved-then-emptied list
  invalidates the hash but also clears the hold condition. → an existing-but-invalid approval
  holds regardless of the list.
- **Step 0 exemption never expires** as scope grows. → the exemption is itself a hash-bound
  stamp; content change → invalid → hold.
- **Older pinned writers drop the new fields** via `model_dump` round-trip (`mark-tested`,
  `mark-judged`). → v3 without the list fails validation loudly; malformed/absent → hold.
- **Incomplete legacy table**: v1 (omitted version), v2 + new fields, v3→v2 downgrade,
  malformed approval, missing machine file.
- **CLI registry collision**: `approve` is registered as a `world` verb and `spec_machine.main`
  guards before parsing → the new verb exits 2 with a wrong hint.
- **A stamp does not prove a human** (same as objective approve) — accepted limitation.
- **The spec boundary trusts the caller's `clear`**; pipelines without spec or direct execute
  entry never hit it. → the boundary should read approval state itself; land covers the rest.
- **Land paths are several**: worktree-off commits inside the `wrapup_land` bundle
  (`wrapup.md.j2:115`), loop runs wrapup then `finalize success` (`loop.md.j2:976-999`),
  `task_land` captures pending edits after the check (`worktree.py:5254`), approval must be
  read from the task checkout not base. → one deterministic check at every land chokepoint.
- **No-tool / no-answer = hold** (Cursor `AskQuestion`, Codex text fallback, loop forbids body
  questions).
- Refinements: adopt `IRR-NNN` (stable, never renumbered) + `decision/category/rationale/source`;
  drop `added_at` and `approval.provenance` counts (question counts do not measure
  understanding); admission test only as a narrowing prompt, not a strict AND gate (an obvious
  data-destroying change is still irreversible); cost/scale/compliance as examples, not new
  categories; no ambiguity-score gate. `source` records where a decision was found, never
  whether a human approved it.
- Long-term: sound only if PLAN's persistent state and per-task briefs survive; strongest
  argument against folding plan = losing an **independent pre-execute falsification**; keep one
  critique for high-risk work. `dev_mode` removal must preserve all four crosses' strictness.

**Where plan's deep interview goes (user question).** Split, not transplanted:
- *Moves to SPEC:* questions whose answer is a human decision — irreversible decisions,
  scope boundaries (today's PLAN `Contract Boundaries` "Do not change" list, which the review
  says must live in the approved SPEC hash), risk acceptance, trade-offs where the user's
  preference binds. SPEC's rule "SPEC does NOT have its own ADR section" (`spec.md.j2:145`) changes:
  these become decision records inside SPEC.
- *Must move with it:* plan Step 1 "pre-interview internal draft" (`plan.md.j2:121`) — the agent
  reads the code and drafts an architecture **before** asking. SPEC Step 1 retrieves docs and
  memory only. Without this, the DRI answers irreversible questions blind — the reviewers' point
  that such decisions surface only after reading code.
- *Dropped (agent decides):* phasing, file order, internal structure, reversible choices — a
  large share of today's plan rounds.
- *Conditional depth:* the deep rounds run only when the draft finds irreversible decisions or
  the scope is large; otherwise the SPEC stays light. Carry plan's round cap
  (`interview.main_loop.max_rounds`).
- *Check:* human questions per task (spec + plan today vs spec after) must go down, not up —
  measure before switching.
- *Memory to update when locked:* `feedback_ask_thoroughly_when_planning` ("ask thoroughly at
  plan") becomes "ask thoroughly at spec".

**What survives the review**: reversibility as the human/agent line; "DRI = PO + tech lead, oracle
choice as the central human act"; the sequencing (SPEC approval + irreversible section before any
plan absorption); refusing to rename plan-validator unmeasured; the chore-bypass signal.

## ⚠️ Pitfalls

- **Weak intent scales the wrong priority.** Zeniteq: "a weak `intent.md` can scale the wrong
  priority. A stale `spec.md` can turn an outdated assumption into dozens of coordinated
  changes." Applies directly if Approach B(1a) lets the LLM fill prose the human only skims —
  the Playbook's own safeguard is the originator's words + PO correction.
- **The Playbook assumes intent exists** (Port: "doesn't describe the mechanism"). Making
  intent mandatory without a cheap capture path produces empty or boilerplate intent — which
  is exactly our current state in the prose body.
- **Approval prompts on the critical path.** Playbook anti-pattern #3: approvals during Build
  put a person back on the critical path. Any new wrapup/plan question must count against that.
- **Surface ratchet.** Any wording change in `plan.md.j2` Step 0.5/4.9 or `wrapup.md.j2` 5.7
  moves four frozen numbers (`[[wiki:gotcha] one-rendered-command-size-has-four-normative-sites]`)
  and needs the `surface_allowance` fold ([[project_surface_allowance_expires_at_wrapup]]).
- **Mutation coverage of `world.py`/`intent.py` is unverified** — mutmut collected 0 mutants
  five tasks in a row (`[fail:tooling] mutation-gate-timeout-leaves-source-mutated-on-disk`).
  Any further change to these modules ships on unit tests alone.
- **Pre-registered kill rule.** The withdrawal criterion was fixed in advance; do not
  reinterpret it once it fires ([[feedback_honor_preregistered_rules]]). Growing the layer
  before it reads 10/10 risks building features the rule would remove.
- **Don't re-add an LLM gap detector or scheduler** — rejected in
  [[PLAN-intent-world-model-objective-layer]] ADR-003 and [[SPEC-outcome-measure]] out-of-scope.

## ❓ Open Questions

1. **Audience:** is the intent layer for solo operators only, or should it support a
   Playbook-style role split (distinct approver)? Decides whether forgery-proof approval is
   ever in scope.
2. **INTENT prose: fill or drop?** (a) `/hm:plan` Step 4.9 drafts the five sections from the
   Step 0.5 conversation for human correction, or (b) remove the body and document the
   mapping. Evidence so far: 0% fill rate under the current "human writes it" model.
3. **Mandatory vs optional objective link:** should `/hm:plan` require an objective (Playbook:
   "nothing without intent") or keep the current ask-once optional model?
4. **Intent survival rate** in `gap --json` — worth adding now, or wait until the withdrawal
   instrument reads 10 wrapups?
5. **Stage-6-lite** (breach → proposal offer at next plan): in scope for the next task, or
   deferred until an outcome actually regresses?
6. **`intent/` folder semantics:** does `intent/` hold our objectives (hypothesis, 1:N with
   tasks), Playbook-style per-idea intents (1:1 with a SPEC), or both with objective → intents?
7. **Folder location:** `intent/` at repo root (Playbook name, CODEOWNERS-friendly) or
   `work-docs/intent/` (stays inside the deliverable tree)?
8. **Role model:** `{owner, dri, team}` declared in `owners` with collapse-when-same-person
   gating, or documentation only? If gating: DRI `spec approve` (hash-bound) first?
10. **Reversibility line — RESOLVED (user, 2026-09-19):** `auto_full` stays an explicit,
   consented delegation and is not blocked on irreversible decisions. Open remainder: tag
   auto-answered irreversible decisions for after-the-fact DRI review — yes/no?
12. **Plan absorption scope:** absorb `/hm:plan` fully (stage removed, `/hm:loop` re-based on
   SPEC hierarchy) or keep a thin `/hm:plan` only for `/hm:loop` master plans?
13. **Ticket linkage:** is `external_ref` on SPEC enough, or must objectives carry it too?
14. **Cross-model review:** re-run with Codex after the quota resets, before `/hm:plan` locks
   anything?
15. **spec-validator:** add as a conditional single-pass LLM critic with measured
   discrimination, or rely on the heuristic spec gate alone?
16. **task-driven — direction set by user (2026-09-19): remove `dev_mode`**; Side preset uses a
   light SPEC. Open: knob name/values (`spec.strictness: block|warn`?) and whether light SPEC is
   a separate option from strictness.
17. **Vocabulary:** adopt intent / purpose / metrics / open questions, and merge `unknowns` +
   assumptions into one list?
11. **DRI = PO + tech lead, or PO only?** This document argues the former; if the user intends
   pure-PO DRIs, technical acceptance must be assigned elsewhere (independent verifier +
   human sampling) and that becomes a design requirement, not a default.
9. **Approval identity:** is `git config user.name` acceptable for a PO stamp, or does a team
   setup need to defer to host `CODEOWNERS` + branch protection instead of a local stamp?

## 📚 Sources

- Anthropic, *The AI-Native SDLC Playbook* (2026-08-21) — https://claude.com/blog/the-ai-native-sdlc-playbook
- Anthropic (J. Clinton), *How Anthropic secures its AI-native SDLC* (2026-07-21) — https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle
- Port, *Implementing the Anthropic AI-Native SDLC Playbook* — https://www.port.io/blog/anthropic-ai-native-sdlc-playbook
- Zeniteq, *Anthropic's AI SDLC makes review the bottleneck* — https://www.zeniteq.com/anthropic-s-ai-sdlc-makes-review-the-bottleneck-0735c3
- Waydev, *missing layer: measurement* (via [[RESEARCH-playbook-alignment]]) — https://waydev.co/anthropics-ai-native-sdlc-playbook-has-a-missing-layer-measurement/

Internal measurements (2026-09-19, dogfood repo): `hm world status --json`,
`hm world gap --json` (withdrawal: `wrapups_since_fill=5`, `objectives_observed=1`,
`due=false`), `work-docs/INTENT-{LOOP-OPT-IN,SOURCE-PLAN-STEPS}.md` bodies (all five sections
empty in both), `.claude/world/assumptions.yaml` (1 entry).

## 🔗 Related Internal Docs

- [[RESEARCH-playbook-alignment]] — Stage 1 artifact alignment (INTENT-<ID>.md as the record)
- [[RESEARCH-cell-dev-future-and-intent-layer-fit]] — "keep the state, drop the machine"
- [[PLAN-intent-world-model-objective-layer]] / [[REVIEW-intent-world-model-objective-layer-2026-09-16]]
- [[PLAN-objective-gap-proposal]], [[PLAN-outcome-measure]], [[PLAN-intent-layer-ops]], [[PLAN-assumption-entry-and-evidence-locator]]
- `[wiki:architecture] intent-layer-withdrawal-instrument`, `[wiki:architecture] objective-gap-and-proposal`
- `[fail:process] peer-lands-mid-task-shared-files` — shared-file risk if a follow-up touches `world.py`/stage templates concurrently
