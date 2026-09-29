---
type: research
task_slug: intent-layer-improvements
status: complete
created: 2026-09-29
tags: [harness-maker, research, python, intent-layer, workflow-feedback, trial, simplification]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://kiro.dev/docs/steering/
  - https://github.com/github/spec-kit/blob/main/templates/commands/constitution.md
  - https://github.com/Fission-AI/OpenSpec
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://docs.devin.ai/product-guides/knowledge
  - https://www.anthropic.com/engineering/claude-code-auto-mode
  - https://www.anthropic.com/engineering/claude-code-sandboxing
  - https://arxiv.org/abs/2602.11988
  - https://arxiv.org/abs/2608.11095
  - https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
  - https://harper.blog/2025/02/16/my-llm-codegen-workflow-atm/
  - https://basecamp.com/shapeup/2.1-chapter-07
  - https://www.thoughtworks.com/insights/articles/how-implement-hypothesis-driven-development
  - https://www.charterworks.com/quit-annie-duke/
  - https://dora.dev/guides/dora-metrics/
  - https://code.claude.com/docs/en/best-practices
  - https://ieeexplore.ieee.org/document/10155430/
related_docs:
  - "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
  - "[[RESEARCH-intent-feedback-continuity]]"
  - "[[PLAN-world-intent-closed-loop-trial]]"
  - "[[PLAN-intent-feedback-continuity]]"
  - "[[REVIEW-intent-feedback-continuity-2026-09-28-rerun]]"
  - "[[REVIEW-intent-layer-ops-2026-09-18]]"
  - "[[REVIEW-intent-file-inputs-2026-09-28]]"
summary: "Rewire wrapup 5.7, gate always-on prose, freeze the deadlocked trial, merge world/intent, batch consent"
trial_feedback:
  - id: intent-layer-improvements-start
    trial_id: world-intent-closed-loop-trial
    task_slug: intent-layer-improvements
    kind: start
    at: '2026-09-29T12:10:14.304298Z'
    evidence_refs:
      - base:.claude/observability/stage-spans.jsonl#L602
    decision: First start of this task is the hm:research span recorded in the base ledger.
  - id: intent-layer-improvements-research-observation
    trial_id: world-intent-closed-loop-trial
    task_slug: intent-layer-improvements
    kind: observation
    at: '2026-09-29T12:40:00Z'
    evidence_refs:
      - work-docs/RESEARCH-intent-layer-improvements.md#finding-f2
      - src/harness_maker/intent_trial.py:512-533
      - src/harness_maker/intent_trial.py:779-781
    decision: >-
      Trial status reports source_incomplete / collect_missing_evidence because the
      accepted source_review pinned a PLAN hash that later changed. Only an explicit
      user record-decision can clear it; surfaced to the user as an open question,
      no trial write performed. Research work continues independently.
  - id: intent-layer-improvements-spec-freeze-decision
    trial_id: world-intent-closed-loop-trial
    task_slug: intent-layer-improvements
    kind: observation
    at: '2026-09-29T12:36:34Z'
    evidence_refs:
      - conversation:hm-spec-interview-round-1-trial-question
      - specs/SPEC-intent-layer-improvements.md#s7-this-repos-trial-is-frozen-by-the-dris-decision
    decision: >-
      DRI chose to freeze this trial (not resume, not delete) and to replace it with a one-line
      verdict item in the wrapup record batch. The policy decision is not yet recorded; execute
      records it via trial record-decision (SPEC S7/AC-006). No trial write in this stage.
  - id: intent-layer-improvements-execute-freeze-recorded
    trial_id: world-intent-closed-loop-trial
    task_slug: intent-layer-improvements
    kind: observation
    at: '2026-09-29T14:30:00Z'
    evidence_refs:
      - base:work-docs/PLAN-world-intent-closed-loop-trial.md
      - work-docs/PLAN-intent-layer-improvements.md#feedback
    decision: >-
      With the user's consent to the exact arguments, the policy decision
      world-intent-closed-loop-trial-freeze (enabled false) was recorded; readback shows the two
      prior decisions and two members preserved. The trial stays active until task-land commits
      it; wrapup checks active_trials afterwards.
---

# Intent layer — improvement opportunities

## 🎯 Recommended Direction

**TL;DR — the intent layer's state is sound, but its feedback loop is disconnected on the
path every wrapup actually takes, and most of the code added since 2026-09-16 is machinery
that has produced no decision. Rewire first, then diet.**

The purpose statement in `.claude/intent.yaml` ends with "제값을 못 하는 장치는 걷어낸다", and
[[RESEARCH-cell-dev-future-and-intent-layer-fit]] (2026-09-16) recommended "keep the state,
drop the machine". Since then the layer grew the opposite way: `intent_trial.py` (1,425 LOC +
2,464 test LOC, 16 call sites in `worktree.py`), a measure verb, a vocabulary translator and a
second CLI. 31% of commits and ~47% of tasks since 2026-09-10 built the layer itself; the one
`met` close came from a config opt-out (fact, usage audit §7). Meanwhile the cheapest,
highest-leverage link — wrapup Step 5.7 — is skipped on the delegated path that all 26
wrapups since 09-16 took (fact, `.claude/commands/hm/wrapup.md:154,212`; flagged 09-19 in
`.claude/memory/pending-proposals.md:522`, unfixed).

Main impact: **internal maintainer value** (this repo is the heaviest user) **and user-facing
cost** — the always-rendered feedback prose taxes every consumer project whether or not it
ever fills `intent.yaml`.

Priority order (informational; `/hm:spec` locks it):

| # | Finding | Kind | Size |
|---|---|---|---|
| F1 | Delegated wrapup skips Step 5.7 | wiring bug | S |
| F2 | Real-task trial is structurally deadlocked | design | decision + M |
| F3 | Feedback prose rendered unconditionally in 6 stages | cost | S |
| F4 | Two CLIs + two-way vocabulary over one engine | complexity | M |
| F5 | Per-write consent: 6–7 tool calls per record | friction | S–M |
| F6 | Metric/question hygiene: unowned gap, no-signal metric, dead questions | data | S (user decisions) |
| F7 | Correctness leftovers (`question resolve` bypasses guard, open P1) | bugs | S |

## 🔍 Refinement Decisions

Discovery lens: User-workflow / product opportunity (first), Technical architecture /
implementation, Risk (consent fatigue). `--deep` not set; no Phase 0 interview.

## 📋 Findings (evidence)

### F1 — Delegated wrapup skips Step 5.7 {#finding-f1}
- Fact: Step 0.5 delegates "Steps 1–5.6" to `stage-delegate` (`wrapup.md:154`); on success the
  main loop "skip[s] straight to Step 6" (`wrapup.md:212`). Step 5.7 (intent questions,
  metric measure, close) lies between. `stage-delegate.md` has no mention of 5.7/intent.
- Fact: 26 delegated wrapups since 09-16 (`delegation.jsonl`); of 14 wrapups after
  `intent.yaml` was filled (09-18), ~7 have 5.7 writes, 6 consecutive (09-19–22) none; several
  writes landed as later chore commits (78644678, 0569860e, db234eb0, 3359096e).
- Inference: 5.7 runs only when the model disobeys the literal text. This alone explains most
  of "intent feedback needs reminding" — the target behaviour of WORLD-INTENT-CLOSED-LOOP.

### F2 — Trial deadlock {#finding-f2}
- Fact: `trial status` → `collection: collecting, outcome: pending, assessments: {},
  reason: source_incomplete, action: collect_missing_evidence` after 7 days, 7 candidates.
- Fact: the user's 09-23 `source_review` pinned `PLAN-intent-feedback-continuity.md` at a
  hash; the task kept editing it and its worktree was deleted at land.
  `_missing_reviewed_source` (`intent_trial.py:512-533`) then reports it missing, and
  `source_incomplete` is evaluated first (`:779-781`), masking every other reason. Only a new
  user `record-decision` clears it.
- Fact: inventory keys embed absolute worktree paths (status output), so any worktree
  appearing/disappearing changes the inventory.
- Fact: across `work-docs/`+`specs/` there was exactly 1 `trial_feedback` event (an
  observation) before this document; 0 `start`, 0 `terminal`. `terminal` requires an explicit
  event (`intent_trial.py:~727`), so landed tasks read `terminal: false`.
- Fact: slot 1 (docs-release-sync) finished before the reader shipped (2f78bb92) and has no
  observation, so it can only reach `insufficient_evidence`; replacement needs a user decision.
- Fact: `intent_trial.py` never references a metric, so even a pass cannot fill
  `intent_world_closed_loop_cycles` (`measure: false`, never measured).
- Fact: PLAN prose still says "Enrolled: 0/3" and "Only the named collector writes"; code
  allows any session to reconcile since 2f78bb92 — the prose is stale.
- Inference: hash-pinning in-progress artifacts is a deadlock by design; the trial measures
  something a one-line user judgment per task would measure at a fraction of the cost.

### F3 — Always-on prose cost {#finding-f3}
- Fact: `@hm:feedback-entry` (567 B) and `@hm:feedback-close` (421 B) render with no
  `{% if %}` in 6 stages (`step_manifest.md.j2:76-83`, `stage_end_summary.md.j2:24-29`).
- Fact: following them loads `SKILL.md` (8.9 KB) + `workflow-feedback.md` (7.5 KB) + `intent
  status --json` (16.7 KB here) + `trial status` (6.5 KB).
- Fact: `workflow-feedback.md:14` says "an absent intent layer costs no record or prompt", but
  the trial section says to scan `work-docs/PLAN-*.md` "even when the intent layer is
  unfilled" — 159 PLANs here, and no CLI verb lists active trials.
- Inference: ~250 tokens always + ~10–12k tokens per stage entry when followed, carried for
  the rest of the session (see CLAUDE.md "Context discipline": carry is 70% of spend).

### F4 — Duplicate CLI and vocabulary {#finding-f4}
- Fact: `world.py` (2,183 LOC) is the engine; `hm world` prints a deprecation notice
  (`world.py:2064-2065`) yet 18 verbs stay registered (`command_registry.py:78-99`); ~200 LOC
  (`world.py:1983-2183`) exist only for it. No rendered template calls `hm world`; one error
  message still points to it (`autopilot_caps.py:353`).
- Fact: `intent_cli.py` calls 14 private `world._*` functions; `intent_vocabulary.py`
  translates purpose↔mission, metrics↔outcomes, rules↔non_negotiables,
  statement↔hypothesis, open/confirmed/wrong↔unknown|assumed/known/conflict on every I/O.
- Fact: two live on-disk layouts branch on a `purpose` key (`world.py:146-148,224-256`).
- Fact: `world.edit_objective` (`:1814`) has no non-test caller — yet "edit an intent" is a
  missing verb (F5).

### F5 — Write-path friction {#finding-f5}
- Fact (skill text): one `metric record` = status → mktemp → (Read) → Write → AskUserQuestion →
  CLI → status readback: 6–7 tool calls + 1 question. `--observed-at` has no `now` default;
  `-file` flags reject `-`/stdin; temp files are never cleaned.
- External: users approve 93% of Claude Code permission prompts and "stop paying close
  attention"; Anthropic answered with classifiers/sandbox, not more prompts (auto-mode,
  sandboxing posts). Devin Knowledge uses one suggest/edit/dismiss per entry.
- Inference: per-write consent at every stage invites rubber-stamping or silent skipping — the
  latter matches F1's observed skip rate.

### F6 — Metric and question hygiene {#finding-f6}
- Fact: `unsourced_step_share` 45.2 vs target 20, no intent owns it; SOURCE-PLAN-STEPS closed
  `missed` (47.1→35.3 vs ≤31.8) and 8597b0b8 (09-20, `/hm:plan` removal) erased the gain; the
  miss was never followed up.
- Fact: `change_failure_rate` read 0 on all 9 readings (no signal at this sample size; DORA
  warns against solo/individual use).
- Fact: 6 open questions all from 09-18; 5 have zero evidence for 11 days; `q_825d374c` has 3
  `confirms` and is still `open`.
- Fact: `moved_evidence: {revalidation_is_report_only: 335}` is benign (cited text moved to
  line ~335, `moved` ∉ `STALE_STATES`, `world.py:58`) but there is no re-anchor verb, so it
  reports forever.
- Fact: review Step 3.3 ran on ~7 intent-linked reviews and found 1 P2 total; the
  silent-intent-miss ledger has never been written (needs `common_ground_marks`, 1 PLAN ever).

### F7 — Correctness leftovers {#finding-f7}
- Fact: `hm intent question resolve` rewrites status inline (`intent_cli.py:155-172`), skipping
  `world.resolve`'s guard (`world.py:1365-1383`); any→any transitions allowed, only
  wrong→confirmed is tested.
- Fact: spec Step 4.9 builds `OBJ-<slug>` ids (`spec.md:687`); all 4 records use bare ids.
- Fact: open P1 `3e276d78` (`status()` reads outside the fence) and P2s `59abac84`,
  `d36cef21`, `b9437fbb`, `3f857179` in [[REVIEW-intent-feedback-continuity-2026-09-28-rerun]]
  (`:117`); carried P2s in [[REVIEW-intent-file-inputs-2026-09-28]] (`:142-143`) and
  [[REVIEW-intent-layer-ops-2026-09-18]] (`:143`). Not re-checked against current code.
- Fact: the memory note `project_intent_layer_followups.md` is stale (names LOOP-OPT-IN as next).

### Local capability × User artifact

| Harness capability | User artifact it touches | Keep up in practice? (evidence) | Implication |
|---|---|---|---|
| Purpose/vision always loaded | `intent.yaml` purpose (≈ Kiro `product.md`, Spec Kit constitution) | Yes — every SDD tool keeps a short "why" (Kiro, Spec Kit) | Keep; short, human-written (+4% vs −3% generated, arXiv 2602.11988) |
| Intent record per change | `intent/<ID>.md` (≈ OpenSpec `proposal.md`) | Per-change why travels with the change, then archives (OpenSpec) | Keep; bind to one SPEC, archive on close |
| Auto-measured metrics | `metrics.yaml` via measure verb | 44/45 values came from the `auto` path | Keep only `measure: true` metrics with a real signal |
| Judgment-only metrics | `measure: false` metrics | 2/2 never measured | Replace with one prompt at wrapup or retire |
| Open questions ledger | `intent.yaml` questions | 5/6 untouched 11 days; ADR logs rarely kept by one person (MSR study) | Add an expiry/review date or retire |
| Real-task trial | trial PLAN frontmatter + `trial_feedback` events | 1 event in 7 days | Freeze / replace with per-task user verdict |
| Stage feedback prose | every `/hm:` stage | Skipped ~50% on the main path (F1) | Wire into the one point that runs: wrapup |

## 🛠️ Approaches Found

### A — Rewire then diet (recommended)

| Field | Content |
|---|---|
| Approach | Fix F1 (5.7 reachable on delegated path + render test), gate F3 prose on `filled or trial active` with a `trial list`/`status` flag, freeze `intent_trial` behind a decision, collapse F4 into one `hm intent` over `world` (delete `hm world` CLI + translator), batch F5 consent into one wrapup question, fix F7 |
| Assumption | The intent state (purpose, intents, auto metrics) is worth keeping; the machinery around it is not yet |
| Evidence | Usage audit (F1, F2, F6), prior RESEARCH 09-16, Kiro/Spec Kit/OpenSpec patterns, approval-fatigue data |
| Trade-off | Deleting `hm world` breaks any external caller (deprecated already); freezing the trial leaves WORLD-INTENT-CLOSED-LOOP without its designed evidence path |
| Compatibility | High — no data migration; stays inside existing verbs; consumers see less prose |
| Risk | medium (touches wrapup template + land path wiring of the trial) |

### B — Minimal repair

| Field | Content |
|---|---|
| Approach | Only F1 + F7 + stale-doc cleanup; leave trial, CLIs, prose |
| Assumption | The loop works once 5.7 actually runs; complexity is tolerable |
| Evidence | F1 is the single largest observed cause of missed feedback |
| Trade-off | Leaves ~10k-token stage-entry overhead in every consumer project and the trial deadlock |
| Compatibility | Highest |
| Risk | low |

### C — Retreat to state-only (09-16 recommendation in full)

| Field | Content |
|---|---|
| Approach | Keep purpose + per-change intent records + delivery metrics; remove trial, question ledger, judgment metrics, withdrawal instrument, per-stage feedback prose; one wrapup prompt "did this change serve intent X? met/missed/unknown" |
| Assumption | A solo dev will not maintain ledgers (MSR ADR study, instruction-file growth study) |
| Evidence | No tool or practitioner found that closes an outcome→agent loop (external survey); 1 of 4 intents met, via config change |
| Trade-off | Discards ~2 weeks of built work and the closed-loop intent's ambition; irreversible for recorded data shapes |
| Compatibility | Low — schema and verbs shrink; consumer harnesses need a migration |
| Risk | high |

## ⚠️ Pitfalls

- **Ceremony > task.** Kiro turned a small bug into 4 stories/16 ACs; Spec Kit markdown was
  "verbose and tedious to review" (Böckeler, martinfowler.com). The trial's 16 status reasons
  are the same shape.
- **Measurement theater.** Metrics nobody can measure without a human are never measured
  (2/2 here). Record only what a command produces.
- **Consent fatigue.** 93% approval rate on prompts → rubber stamping (Anthropic auto-mode).
- **Stale context is obeyed.** The trial PLAN prose ("only the named collector writes") now
  contradicts code; agents follow stale files confidently.
- **Pinning moving artifacts.** Hashing an in-progress PLAN (F2) guarantees drift.
- **Invariant-over-named-dimension tests** (`[fail:test] assertion-invariant-over-named-dimension`,
  count 22): a 5.7 render test must assert the delegated path *names* 5.7, and fail when the
  line is removed — not merely that "5.7" appears somewhere in the file.
- **Fix-introduced defects** (`[fail:design] fix-introduced-defect-passes-all-gates`, count 17):
  intent-feedback-continuity needed 9 review rounds; any trial/land-path change needs a
  revert-control test per fix.

## ❓ Open Questions

1. **Trial (user-owned):** freeze/retire `world-intent-closed-loop-trial` and its machinery,
   or record a new `source_review` decision to unblock it? Retiring changes how
   WORLD-INTENT-CLOSED-LOOP is judged — that is a scope change to an active intent.
2. **Consent model:** keep per-write AskUserQuestion, or one batched suggest/edit/dismiss at
   wrapup (Devin pattern)?
3. **`hm world` CLI:** delete now (deprecated, no rendered caller) or keep one more release?
4. **Metric/question retirement:** drop `change_failure_rate` as a target (always 0)? Expire the
   5 dormant questions? Resolve `q_825d374c`? Assign an owner (new intent) to
   `unsourced_step_share` or lower its target?
5. **Scope split:** F1 is small and independent — ship it as its own task first, then A's diet?
6. **Step 3.3 value:** keep, shrink, or make it measure-gated (1 P2 in ~7 runs)?

## 📚 Sources

- Kiro steering — https://kiro.dev/docs/steering/
- Spec Kit constitution command — https://github.com/github/spec-kit/blob/main/templates/commands/constitution.md
- OpenSpec — https://github.com/Fission-AI/OpenSpec
- Anthropic, effective harnesses for long-running agents — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Devin Knowledge — https://docs.devin.ai/product-guides/knowledge
- Anthropic, Claude Code auto mode — https://www.anthropic.com/engineering/claude-code-auto-mode
- Anthropic, Claude Code sandboxing — https://www.anthropic.com/engineering/claude-code-sandboxing
- Context files study (ETH) — https://arxiv.org/abs/2602.11988
- Agent instruction file growth study — https://arxiv.org/abs/2608.11095
- Böckeler, SDD tools — https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- Harper Reed workflow — https://harper.blog/2025/02/16/my-llm-codegen-workflow-atm/
- Shape Up, betting — https://basecamp.com/shapeup/2.1-chapter-07
- Hypothesis-driven development — https://www.thoughtworks.com/insights/articles/how-implement-hypothesis-driven-development
- Annie Duke kill criteria — https://www.charterworks.com/quit-annie-duke/
- DORA metrics guide — https://dora.dev/guides/dora-metrics/
- Claude Code best practices — https://code.claude.com/docs/en/best-practices
- ADR adoption in OSS (MSR; figures from abstract snippet) — https://ieeexplore.ieee.org/document/10155430/

## 🔗 Related Internal Docs

- [[RESEARCH-cell-dev-future-and-intent-layer-fit]] — "keep the state, drop the machine" (09-16)
- [[RESEARCH-intent-feedback-continuity]], [[PLAN-intent-feedback-continuity]]
- [[PLAN-world-intent-closed-loop-trial]] — the stalled trial
- [[REVIEW-intent-feedback-continuity-2026-09-28-rerun]], [[REVIEW-intent-file-inputs-2026-09-28]], [[REVIEW-intent-layer-ops-2026-09-18]]
- `.claude/memory/pending-proposals.md:522` — "wrapup's delegated path skips 5.7" (09-19)
- `[wiki:architecture] world-intent-closed-loop`, `intent-layer-withdrawal-instrument`, `outcome-measure-verb`
- Intents: `intent/WORLD-INTENT-CLOSED-LOOP.md`, `intent/UNDERSTANDING-HANDOFF.md`
