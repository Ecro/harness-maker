---
type: research
task_slug: source-plan-steps
created: 2026-09-18
objective: SOURCE-PLAN-STEPS
summary: "Class-supporting evidence for the 13 plan-stage steps the step-sensitivity registry graded unsourced"
---

# RESEARCH — Evidence for the plan stage's inherited step classifications

## Method

Objective `SOURCE-PLAN-STEPS`; bar and rules from `PLAN-source-plan-steps.md` ADR-001…005.

- **Evidence bar (ADR-001).** A row leaves `unsourced` only with (a) a citation that supports the
  class *property* — INV-state: writer **and** a reader in a later context; INV-human-gate: the
  question / answer-gated block and the decision it reserves; INV-oracle: the deterministic
  check; COMP: the instruction and a sourced claim that current models do it unprompted; HOST:
  the native host capability — and (b) a falsifier. `**` additionally needs a measured value that
  bears on that property, with population and `n`. Ledger/memory evidence is quoted in Appendix B.
- **Order (ADR-003).** Codex classified first from a curated bundle (Appendix A); Table 1 was
  written after, by Claude, with full repository access. The Codex reading was then voided by the
  exposure check (Appendix A), so Table 2 is a Claude-only reconciliation (ADR-003 §6).
- **Citations** are `path:line` at base commit `3b22a595`, template lines in
  `src/harness_maker/templates/stages/plan.md.j2` unless another file is named.

## Table 1 — Claude evidence

| ordinal | inherited class | proposed class | property type | citation(s) | falsifier | measured value (population, n) | grade |
|---|---|---|---|---|---|---|---|
| Step 0 | INV | COMP | COMP (triage prose) | `plan.md.j2:80-89` — a four-row table the model applies to decide whether to interview; no code, no state, no operator question (the operator is *not* asked: "do not ask permission", `:89`). Supports that the step is model-applied triage, i.e. not INV. No sourced claim that current models make this triage correctly unprompted: the nearest repo claim (`RESEARCH-workflow-steps-vs-model-capability.md` Table 1, Phase 0.5 row) is itself a `*` judgement, and citing it would be inheritance again. | Removing the table changes how often the interview runs on non-trivial tasks for a current model. | — | unsourced |
| Step 1.5 | INV | INV | INV-state | Writer: `src/harness_maker/templates/commands/hm/loop.md.j2:408` (`worktree create execute … --claude-session-id`) records the session in a `.claude/.hm-loop-*` marker in the loop driver's context. Reader: `plan.md.j2:137` → `src/harness_maker/worktree.py:5931` `_cli_loop_mode_active`, run by a later `/hm:plan` iteration. Neither context can observe the other. | A plan invocation can tell it runs inside a loop without reading any persisted marker (e.g. the host exposes loop membership) — that would make it HOST. | — | * |
| Step 1.7 | INV | INV | INV-state | Writer: `plan.md.j2:319` `spec_need marker-write` → `src/harness_maker/spec_need.py:315`, after which the invocation STOPS for `/hm:spec`. Reader: the **next** `/hm:plan` invocation, `plan.md.j2:192,202` → `spec_need.py:337,351`. Second reader: the verdict persisted in PLAN frontmatter is read by `/hm:verify` Check 6 (`src/harness_maker/templates/stages/verify.md.j2:159-163`). | A resumed invocation behaves correctly with the marker and the frontmatter verdict deleted. | spec-need ledger n=5 rows / 5 tasks (Appendix B.2) — shows the writer runs, not that a reader resumed; does not bear on the property → no `**` | * |
| Step 2 | INV | INV | INV-state | Writer: `/hm:spec` Step 5 sets `status: approved|draft` from the Open Questions section (`src/harness_maker/templates/stages/spec.md.j2:340-342`), in the spec stage's context. Reader: `plan.md.j2:344-353`, a later stage, which skips or opens interview rounds from that status. | Plan reaches the same interview scope with the SPEC's status and Open Questions removed. | — | * |
| Step 3.0 | INV | INV | INV-human-gate | `plan.md.j2:365-367` — a structured question whose answer (proceed / one architecture question / full interview) the operator alone chooses; on "proceed" Step 3 is skipped (`:376`). | A conforming run picks among the three branches with no operator answer and no delegated authorization. | — | * |
| Step 4.4 | INV | INV | INV-oracle | `plan.md.j2:601-605` pins the PLAN before/after revision; `src/harness_maker/review_churn.py:195` `measure` computes the rewrite ratio from git objects; `src/harness_maker/plan_rounds.py:153` marks queued critiques `stale` at a fixed threshold. No model judgement in the decision. | Identical pins and threshold yield different stale decisions. | 6 plan-stage pins among 35 `refs/hm-churn/v1/*` (Appendix B.3) — usage, not oracle outcomes → no `**`. Note: with the single-pass validator policy the stale rule has no second pass to act on; the step is optional. | * |
| Step 4.9 | INV | INV | INV-human-gate | Consent is asked at Step 0.5 (`plan.md.j2:106,108`, "Draft an objective for this task?" — No writes nothing); the write at `:734` happens only on that consent; approval stays human (`src/harness_maker/world.py:1207` `approve` is a separate operator verb; `:730-742` states the record is `proposed`). The record is then read in a later context by the autopilot gate (`src/harness_maker/autopilot_caps.py:255-279`). | A conforming run drafts after a "No", or approves/activates its own draft. | — | * |
| Step 5 | INV | INV | INV-state | Writer: `plan.md.j2:745` writes `work-docs/PLAN-{slug}.md`. Readers in later contexts: `/hm:execute` Step 1 (`src/harness_maker/templates/stages/execute.md.j2:75-77`, "Read PLAN fully … ADRs (binding constraints)"); the autopilot objective gate (`autopilot_caps.py:255`); `/hm:verify` Check 6 (`verify.md.j2:159`). | Execute, verify and the gate behave identically with the PLAN file absent. | — | * |
| Step 6 | INV | COMP | none met | `plan.md.j2:793` "Read the file back and assert" — the assertions are executed by the model, not by code, so INV-oracle is not met. It does guard a real hole: `/hm:verify` Check 6 treats an absent `spec_need_verdict` as PASS (`verify.md.j2:161`), so this readback is the only check of that key. COMP (self-check of the model's own write) is plausible but no sourced claim shows current models omit fewer keys. | A deterministic linter over the same assertions finds defects this readback passed (→ it was COMP-weak), or none ever occur (→ redundant). | — | unsourced |
| Step A | COMP | COMP | none met | `plan.md.j2:389-429` — round-state/delta rendering. Its origin (`work-docs/RESEARCH-plan-interview-comprehension.md:98,109`) shows it was added for **operator comprehension** (arXiv 2507.02564, context-enhanced interviews), which argues it supports the human gate rather than compensating a model weakness; neither reading has evidence for its class. | Operators decide equally well (same revision rate) with the block removed under a current model. | — | unsourced |
| Step B | INV | INV | INV-human-gate | `plan.md.j2:430-450` — the structured question round; unresolved architectural rounds set `--judgment-gate pending`, which stops autopilot at `gated`/`auto_safe` (`plan.md.j2:834`). The decision reserved: scope, architecture, contract and risk choices. | Under `gated`/`auto_safe` an unanswered architectural round advances without operator authorization. | auto-advance plan stage: gate_blocked 15 vs advance_authorized 14 (Appendix B.1) — cannot be attributed to Step B (the same event fires on a validator threshold, `:834` predicate 1) → no `**` | * |
| Step C | INV | INV | INV-state | Writer: `plan.md.j2:452-480` appends each answer to the transcript persisted in the PLAN (Step 5). Readers in other contexts: the plan-validator subagent receives it (`plan.md.j2:561`, "full draft PLAN body + Interview Transcript + ADRs"); under `auto_full` the recommended answer must be written there before advancing (`:834` predicate 2), making the record the only audit of that skipped human decision. | A fresh validator or auditor recovers the operator's actual choices with the transcript removed. | — | * |
| Step D | INV | INV | INV-state | Writer: `plan.md.j2:481-504` promotes decisions to ADRs persisted in the PLAN. Readers: `/hm:execute` Step 1 treats ADRs as binding (`execute.md.j2:77`); loop-mode plans take the master PLAN's ADRs as source of truth (`plan.md.j2:147`). | Execute and loop iterations preserve accepted decisions and rejected alternatives with the ADR section removed. | — | * |

## Table 2 — Final verdicts

**Claude-only reconciliation.** The blind Codex reading is **VOID** under ADR-003 §4 as
pre-registered (Appendix A: the literal exposure grep matched 5 lines), so ADR-003 §6 applies:
the task proceeds Claude-only. The Codex column is kept for information and casts no vote. The
first version of this table treated the reading as valid by applying a criterion chosen after
the check fired; `/hm:review` flagged that from three independent voices (design, security,
codex) and the operator directed the rule be honoured as written (2026-09-18).

Rules: a class changes only when the evidence supports the new class under ADR-001 (ADR-002) —
evidence that a step is *not* INV does not by itself make it COMP. The grade is Claude's Table 1
grade for the final class. TUNE is out of scope (ADR-002); no reading proposed it.

| ordinal | Claude | Codex (void, non-voting) | final class | final grade | reason |
|---|---|---|---|---|---|
| Step 0 | COMP / unsourced | COMP / unsourced | INV (unchanged) | unsourced | Table 1 shows the INV properties absent (model-applied table, no state, no operator question, `plan.md.j2:80-89`), but COMP is not supported either: no sourced claim that current models triage unprompted, and the Table 1 falsifier does not discriminate COMP from INV. Class stays INV, `unsourced`; the "not INV" observation is recorded for later work. |
| Step 1.5 | INV / * | INV / * | INV | * | Claude's writer (`loop.md.j2:408`) → reader (`worktree.py:5931`) in a later iteration meets the INV-state bar. |
| Step 1.7 | INV / * | INV / * | INV | * | Marker written before the invocation stops, read by the next invocation (`spec_need.py:315/337/351`). No ledger value bears on resume → no `**`. |
| Step 2 | INV / * | INV / unsourced | INV | * | Writer `spec.md.j2:340-342` (spec Step 5 status write), reader `plan.md.j2:344-353` in a later stage. |
| Step 3.0 | INV / * | INV / * | INV | * | Operator-only branch choice, `plan.md.j2:365-376`. |
| Step 4.4 | INV / * | INV / * | INV | * | Deterministic ratio and threshold, `review_churn.py:195`, `plan_rounds.py:153`; usage counts are not oracle outcomes → no `**`. |
| Step 4.9 | INV / * | INV / * | INV | * | Consent-gated write, human approval (`plan.md.j2:106-108,734`; `world.py:1207`). |
| Step 5 | INV / * | INV / * | INV | * | PLAN written here, read by later stages and the gate (`execute.md.j2:75-77`, `autopilot_caps.py:255`, `verify.md.j2:159`). |
| Step 6 | COMP / unsourced | INV / unsourced | INV (unchanged) | unsourced | Neither class meets the bar: the checks are model-executed (not an oracle) and no capability source supports COMP. `verify.md.j2:161` passes an absent `spec_need_verdict`, so this readback is currently the only guard of that key. |
| Step A | COMP / unsourced | COMP / unsourced | COMP (unchanged) | unsourced | No evidence for its class; its origin (operator comprehension, `RESEARCH-plan-interview-comprehension.md:98,109`) argues against COMP, one more reason not to grade it. |
| Step B | INV / * | INV / * | INV | * | Operator question round gated by `--judgment-gate pending` (`plan.md.j2:430-450,834`); the auto-advance aggregate cannot be attributed to Step B → `*`. |
| Step C | INV / * | INV / * | INV | * | Transcript persisted and handed to the separate validator context (`plan.md.j2:452-480,561`). |
| Step D | INV / * | INV / * | INV | * | ADRs persisted, read as binding by execute and by loop-mode plans (`execute.md.j2:77`, `plan.md.j2:147`). |

**Totals.** Sourced: 10 (all `*`, all INV). Left `unsourced`: 3 — Step 0 (INV), Step 6 (INV),
Step A (COMP). Class changes: 0. No `**` anywhere: every available measurement counts usage, not
the property. Registry effect: `unsourced` 40 → 30 of 85 (35.3%), above the hypothesis
threshold of 31.8. **No independent second reading supports these verdicts** — the cross-model
check was voided; review lenses are the only other readers.

**Findings for later work (not acted on here).**
- Step 6 is the only guard of an absent `spec_need_verdict` (verify Check 6 passes it,
  `verify.md.j2:161`), yet it is executed by the model. Moving its assertions into a deterministic
  check would make it INV-oracle and close that fail-open.
- Step 4.4's stale rule acts only on a second validator pass, which the single-pass policy
  removed; the step is optional and its consumer rarely runs.
- Step 0 shows no INV property; it becomes a COMP candidate once a capability source exists.
- A blind cross-model reading needs an exposure check that inspects executed commands rather
  than log content, decided **before** the call — the content grep cannot tell reading a file
  from printing a comment that names it.

## Appendix A — Codex blind classification

Written in Phase 1, **before any Claude verdict existed** (PLAN ADR-003 §1).

**Call.** `codex exec --skip-git-repo-check -s read-only -C <bundle> -o <out> - < <prompt>`
(codex-cli 0.154.0, model `gpt-6-astra`, reasoning effort medium), 2026-09-18, base commit
`3b22a595`. The first attempt without `--skip-git-repo-check` was refused by the CLI ("Not inside
a trusted directory") before any model call; the bundle is deliberately outside every repository.

**Prompt (verbatim).**

> Read BRIEF.md in the current directory and follow it exactly. Only files in the current directory are in scope; do not read anything outside it.

**Bundle manifest** (`mktemp -d`, outside the repository; sha256):

| sha256 | file | source |
|---|---|---|
| `26e84e3aeda0…` | BRIEF.md | class definitions, ADR-001 bar, the 13 ordinals, output format |
| `58a4cf24bd92…` | aggregates.md | locally computed ledger counts only (ADR-005) — reproduced below |
| `ac5f9780e5d3…` | plan-command.md | `/home/noel/harness-maker/.claude/commands/hm/plan.md` (rendered by 0.57.1) |
| `180b8989a0c6…` | plan_rounds.py | `src/harness_maker/plan_rounds.py` @ `3b22a595` |
| `4bf3bf865288…` | review_churn.py | `src/harness_maker/review_churn.py` @ `3b22a595` |
| `5a3f102c6df1…` | spec_need.py | `src/harness_maker/spec_need.py` @ `3b22a595` |
| `cfa735d6fc47…` | worktree.py | `src/harness_maker/worktree.py` @ `3b22a595` |
| `1f9e99417f0b…` | world.py | `src/harness_maker/world.py` @ `3b22a595` |

Excluded by construction: `step_sensitivity.py`, `MATRIX-native-redundancy.md`,
`RESEARCH-workflow-steps-vs-model-capability.md`, this document, `PLAN-source-plan-steps.md`,
`CLAUDE.md`. After `plan-command.md` and the five `.py` files were copied in, and **before**
`BRIEF.md` and `aggregates.md` were written, those six files were grepped with
`grep -n -E '\b(COMP|INV|HOST|TUNE)\b|step_sensitivity|unsourced'`: zero hits. BRIEF.md then
introduced the class vocabulary by design (its definitions). Manifest hashes above are truncated
to 12 hex digits; the bundle itself was a temporary directory and is not preserved.

`aggregates.md` as sent:

| Ledger | Aggregate |
|---|---|
| stage-agents.jsonl, agent=plan-validator | n=47 dispatch rows 2026-08-06..2026-09-18; verdicts MAJOR_REVISION 43, NEEDS_REVISION 2, dispatch-failed 2, APPROVED 0; pass number 1: 28, 2: 16, 3: 3 |
| spec-need-*.jsonl (Step 1.7 SPEC-need verdicts) | n=5 rows across 5 tasks; verdict add 4, none 1 |
| auto-advance.jsonl, plan stage | gate_blocked 15, advance_authorized 14, advance_entered 13, advanced 3 |
| stage-spans.jsonl, stage hm:plan | start 39, end 30 (2026-07-27..2026-09-18) |
| git refs refs/hm-churn/v1/* (Step 4.4 revision-size pins) | 35 refs total, 6 of them plan-stage pins |

**Exposure check.** ADR-003 §4's literal grep over the session log
(`step_sensitivity|MATRIX-native|RESEARCH-(source-plan|workflow-steps)|PLAN-source-plan|CLAUDE\.md`)
matched **5 lines, all `CLAUDE.md`**, and every one is text *inside a bundled file* that Codex
printed (e.g. `worktree.py` comments "CLAUDE.md project rule", "documented in CLAUDE.md"). The
authoritative signal is what Codex executed: **18 shell commands, every one run
`in /tmp/tmp.XnpTeahRti` against a bundled file** (`cat BRIEF.md`, `nl -ba plan-command.md`,
`nl -ba worktree.py`, `rg … worktree.py spec_need.py world.py review_churn.py`, …); none names an
excluded file or a path outside the bundle.
**Result: blind reading VOID** (ADR-003 §4 as pre-registered: any hit voids). The executed-command
audit above found no read of an excluded file, but that criterion was chosen after the check
fired, so it cannot rescue the reading. A first version of this appendix declared it VALID on that
substitute criterion; `/hm:review` (`a8aad0464067647c`, three voices) rejected that and the operator
directed the rule be honoured. The raw response below is kept as information only and casts no
vote in Table 2.

**Raw response (verbatim, bundle paths as Codex wrote them).**

| ordinal | class | grade | citation | falsifier |
|---|---|---|---|---|
| Step 0 | COMP | unsourced | [plan-command.md:160](/tmp/tmp.XnpTeahRti/plan-command.md:160) prescribes interview triage. No supplied evidence shows current models reliably make this choice unprompted. | Removing the heuristic consistently changes required operator involvement despite improved model judgment. |
| Step 1.5 | INV | * | Mechanical session check: [worktree.py:5955](/tmp/tmp.XnpTeahRti/worktree.py:5955) prevents another session's legacy marker from activating loop mode for a valid session ID; [plan-command.md:212](/tmp/tmp.XnpTeahRti/plan-command.md:212) consumes the result. | A valid session with only another session's marker is classified as active. |
| Step 1.7 | INV | * | Cross-invocation state: writer [spec_need.py:334](/tmp/tmp.XnpTeahRti/spec_need.py:334), reader [spec_need.py:337](/tmp/tmp.XnpTeahRti/spec_need.py:337); [plan-command.md:387](/tmp/tmp.XnpTeahRti/plan-command.md:387) writes then stops, and [plan-command.md:261](/tmp/tmp.XnpTeahRti/plan-command.md:261) resumes a later invocation. | A fresh invocation resumes correctly without the marker or equivalent persisted verdict/target state. |
| Step 2 | INV | unsourced | [plan-command.md:410](/tmp/tmp.XnpTeahRti/plan-command.md:410) reads prior SPEC decisions and approval. The SPEC writer is absent, so the required cross-context writer/reader pair is incomplete. | Every relevant SPEC is created and consumed within one retained context, with no later-context dependency. |
| Step 3.0 | INV | * | [plan-command.md:446](/tmp/tmp.XnpTeahRti/plan-command.md:446) reserves proceeding, resolving one architecture question, or reopening the full interview to the user's answer. | The workflow validly chooses among these branches without an operator answer or delegated authorization. |
| Step 4.4 | INV | * | [review_churn.py:171](/tmp/tmp.XnpTeahRti/review_churn.py:171) mechanically computes per-file revision size; [plan_rounds.py:153](/tmp/tmp.XnpTeahRti/plan_rounds.py:153) detects threshold crossing and marks queued critiques stale. [plan-command.md:755](/tmp/tmp.XnpTeahRti/plan-command.md:755) requires the PLAN-specific ratio. | Identical pinned inputs and threshold yield different stale decisions, or those decisions require semantic model judgment. |
| Step 4.9 | INV | * | Consent question [plan-command.md:184](/tmp/tmp.XnpTeahRti/plan-command.md:184); answer-gated drafting [plan-command.md:864](/tmp/tmp.XnpTeahRti/plan-command.md:864). The operator controls whether an objective is drafted; approval and activation remain human actions at line 877. | A conforming run drafts after refusal, or autonomously approves and activates the proposal. |
| Step 5 | INV | * | Persistent PLAN writer [plan-command.md:882](/tmp/tmp.XnpTeahRti/plan-command.md:882); later loop invocation reads that master PLAN and its remaining phases at [plan-command.md:218](/tmp/tmp.XnpTeahRti/plan-command.md:218). | Later iterations operate correctly after removing the PLAN and every equivalent persisted plan representation. |
| Step 6 | INV | unsourced | [plan-command.md:930](/tmp/tmp.XnpTeahRti/plan-command.md:930) specifies mechanically checkable frontmatter, counts, and required fields, but supplies a model readback instruction rather than an implemented deterministic oracle. | Identical malformed documents pass or fail depending on model judgment rather than fixed predicates. |
| Step A | COMP | unsourced | [plan-command.md:470](/tmp/tmp.XnpTeahRti/plan-command.md:470) and [plan-command.md:481](/tmp/tmp.XnpTeahRti/plan-command.md:481) prescribe readable state updates. No evidence demonstrates equivalent unprompted behavior by current models. | Removing these instructions persistently reduces operator comprehension despite stronger models. |
| Step B | INV | * | [plan-command.md:513](/tmp/tmp.XnpTeahRti/plan-command.md:513) elicits scope, architecture, and risk choices; [plan-command.md:590](/tmp/tmp.XnpTeahRti/plan-command.md:590) makes the user's exit choice control continuation. [plan-command.md:999](/tmp/tmp.XnpTeahRti/plan-command.md:999) gates unresolved choices under `gated`/`auto_safe`. | Under those modes, unanswered substantive choices are validly resolved and advanced without operator authorization. |
| Step C | INV | * | Answer writer [plan-command.md:537](/tmp/tmp.XnpTeahRti/plan-command.md:537), persisted transcript [plan-command.md:909](/tmp/tmp.XnpTeahRti/plan-command.md:909), and separate validator context explicitly receives the transcript at [plan-command.md:717](/tmp/tmp.XnpTeahRti/plan-command.md:717). | A fresh validator can recover the actual user choices without receiving the transcript or equivalent recorded decisions. |
| Step D | INV | * | ADR writer [plan-command.md:566](/tmp/tmp.XnpTeahRti/plan-command.md:566), persistence [plan-command.md:910](/tmp/tmp.XnpTeahRti/plan-command.md:910), and later loop reader [plan-command.md:218](/tmp/tmp.XnpTeahRti/plan-command.md:218) explicitly inherit master-PLAN ADRs. | Later contexts preserve accepted decisions and rejected alternatives without ADRs or equivalent durable records. |

Codex notes (verbatim):

> Grades apply to the cited property; an INV classification does not make every formatting instruction indispensable.
> No `**`: aggregates.md:9 reports 4 `add` verdicts among 5 rows across 5 tasks, but no resume or gate outcomes; aggregates.md:12 reports 6 plan pins among 35 refs, but no oracle results.
> No HOST claim is established by this bundle; using a native question tool does not eliminate the operator's decision.
> The `0.50` threshold at plan_rounds.py:37 is configurable, but no supplied measurement establishes a model-dependent optimum reversal required for TUNE.

## Appendix B — Evidence excerpts

Read 2026-09-18 at base commit `3b22a595`. Ledgers are gitignored and exist only at the base root;
the fields below are the durable copy (no session ids, no free text).

**B.1 — `/home/noel/harness-maker/.claude/observability/auto-advance.jsonl`.** Derivation: count
rows by `event`, keeping rows whose `stage` (for `gate_blocked`) or `to` (for advance events)
equals `plan`. Result: `gate_blocked` 15, `advance_authorized` 14, `advance_entered` 13,
`advanced` 3. The row schema carries only `{event, stage|to, ts}` (plus `halt_kind`, `steps` on
`halted_cap`) — no field says which predicate blocked, which is why Table 1 does not attribute
these to Step B.

**B.2 — `/home/noel/harness-maker/.claude/observability/spec-need-*.jsonl`.** Derivation: every
row of every file. Result: n=5 rows across 5 tasks (`intent-world-model-objective-layer`,
`objective-gap-proposal`, `outcome-measure`, `playbook-alignment`, `source-plan-steps`); `verdict`
`add` 4, `none` 1. Row fields: `{verdict, target, rationale, detected_at, changed_files_hash}`.
No row records a resume (marker read), so the ledger evidences the writer only.

**B.3 — git refs `refs/hm-churn/v1/*` in `/home/noel/harness-maker`.** Derivation:
`git for-each-ref 'refs/hm-churn/v1/*'`, then those whose name contains `-plan-`. Result: 35
refs, 6 plan-stage pins. Refs carry no measurement result.
