---
type: plan
task_slug: workflow-loop-efficiency
status: complete
created: 2026-08-05
tags: [harness-maker, plan, python, token-economics, review-pipeline, telemetry]
spec: "[[SPEC-workflow-loop-efficiency]]"
research_doc: "[[RESEARCH-workflow-loop-efficiency]]"
interview_rounds: 5
adrs: 11
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Stage 1: cut the one proven-low-yield step, instrument the three unmeasured ones, gate every fix on a reproduction."
---

# PLAN — workflow loop efficiency (stage 1)

## 🎯 Executive Summary

**What.** Remove the Pass 1.5 `code-verifier` step from `/hm:review`; add the
fix-introduced-defect guard to `/hm:execute` Phase D; instrument the two subagent
dispatches that today have zero telemetry (`plan-validator`, Phase A.5); capture the
diagnosis the `wrapup` delegate ledger never recorded; run the Pass 2 ablation as a
measurement; and produce the native-capability redundancy matrix.

**Why.** `RESEARCH-workflow-loop-efficiency` measured that the two loops the user named
are already bounded and jointly ≈15–23% of spend, while 73% of every dollar is context
carry and all subagents together are 13.5%. So the win is not in cutting rounds — it is
in cutting the one step whose yield is measured to be 1.9%, and in making the three
unmeasured steps decidable. Stage 2 does the cutting; this stage buys the evidence.

**Key decisions.** Pass 1.5 goes (ADR-001) but its agent stays and its default mode is
inverted so the dead mode cannot be reached by omission. Every telemetry change is bound
to the *rendered producer*, not just the Python model (ADR-002, ADR-004) — a schema-only
change is a no-op here because the emitter is prose. Every fix is gated on a
reproduction (ADR-005). The detection check is a **deterministic** replay of archived
reviewer outputs, never a live re-invocation (ADR-006).

**Estimated impact.** Removes 1 sequential barrier and 1 agent dispatch per review round
(measured lifetime cost of the removed agent: $1.2 — the saving is wall-clock and one
fewer serialization point, not dollars). Adds 2 telemetry streams that currently have a
zero-row denominator. No change to detection coverage is intended; ADR-006 is the check
that says so.

## 📚 Prior Work

- `RESEARCH-workflow-loop-efficiency` — the measurement this plan is built on.
- `[fail:test] fix-introduced-defect-passes-all-gates` (count:4) — the failure class
  ADR-003 encodes as a step and ADR-005 structurally avoids. Both cross-model reviewers
  independently flagged the *first draft of this very plan* as an instance of it.
- `[fail:design] ratchet-rebaselined-by-its-own-subject` (count:2) — why ADR-010 gives
  `surface_baseline.json` an owner instead of leaving it a shared hazard.
- `observability-field-with-no-consumer` — why ADR-004 pre-registers the aggregation
  expression stage 2 will evaluate, rather than only the row.
- `[wiki:architecture] harness-diet-fused-axis-removal` — "keep state scaffolding, cut
  behavior scaffolding", and the precedent that cutting unused surface saves nothing.
- `PLAN-harness-diet` — the 0.47.0 predecessor.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Scope | 1 | Which levers are in stage 1? | B2 + C + MEASURE + B3, **plus** a new item: survey whether commands/skills are still needed given the model's native harness | User-raised addition | ADR-001,003,004,007 |
| 2 | Acceptance oracle | 5 | How is "cheaper without losing detection" proven? | `golden` — cost metrics; detection proxied by the regression suite | Concern raised that this repo has refuted the proxy 4×; user reaffirmed | — (waiver, AC-008) |
| 3 | Delegate | 4 | Repair or delete the wrapup delegate? | Repair | | ADR-005 |
| 4 | Landing shape | 6 | Instrument-then-decide, or one landing? | 2-stage: instrument first | | ADR-007 |
| 5 | Retirement basis | 1 | Which target basis decides redundancy? | Claude Code basis; Cursor/Codex capability loss accepted | | ADR-009 |
| 6 | Pass 2 | 1 | Delete Pass 2 if the ablation fails to reproduce? | Defer to stage 2 regardless | | ADR-007 |
| 7 | Delegate "repair" | 2 | `reason: null` in both rows — what does repair mean? | Diagnosis capture + preemptive fix of the likeliest cause | Superseded by #10 after validation | ADR-005 |
| 8 | Detection oracle | 5 | Add a cheap non-circular check? | Yes — one archived-diff replay | | ADR-006 |
| 9 | Ledger placement | 3 | One file or per-domain? | Single `stage-agents.jsonl` with `agent`/`stage` discriminators | | ADR-004 |
| 10 | Ablation honesty | 5 | Gate "was it run honestly"? | Accept; record the waiver | | ADR-007 |
| 11 | Replay target | 5 | Only 1 archived REVIEW has stable ids | Use that one | n=1 documented | ADR-006 |
| 12 | Replay semantics | 4 | What happens on non-reproduction? | One retry, then hard fail | Mechanism revised by #13 | ADR-006 |
| 13 | Replay mechanism | 3 | Validator: hard-fail over a *live* n=1 re-invocation is unimplementable | **Deterministic replay** — re-inject archived reviewer outputs; no LLM in the loop | hard-fail verdict retained, mechanism changed | ADR-006 |
| 14 | P4 unreproducible branch | 4 | Exit criterion is unsatisfiable if the cause never reproduces | Split: **P4a diagnosis lands unconditionally; P4b fix is reproduction-gated**; no reproduction → no code change + AC-006 waived on record | Closes SPEC Open Question 4 | ADR-005 |
| 15 | Detection check, 3rd attempt | 5 | The replay's input artifact does not exist — no per-reviewer payload was ever persisted, and #11's "one REVIEW has stable ids" premise was **false** | **Natural-experiment analysis of the existing ledger (non-blocking) + start persisting payloads so future replays are possible** | My error, corrected on the record; stage 1 therefore ends with no blocking detection check (R6) | ADR-006 |
| 16 | Latency axis | 4 | The dollar-denominated analysis hid the wall-clock problem the user actually raised; which time levers come into stage 1? | **Detection-neutral only: hoist the cross-model voters to run concurrently with Pass 1, plus `duration_ms`/`barrier_index` instrumentation.** Pass 2 removal, validator 2nd-pass removal and Phase-D full-suite narrowing stay in stage 2 | User correction; the validator's 2nd pass had just caught 2 criticals here, which is evidence against cutting it | ADR-011, ADR-004 |

## 📐 Architecture Decision Records

### ADR-001: Remove the Pass 1.5 dispatch; retain the agent with its default inverted
**Status:** Accepted (2026-08-05, via /hm:plan interview + validation; rationale rewritten
after interview #16)
**Context:** The original justification was cost and drop rate — Pass 1.5 dropped 5 of 261
findings (1.9%) at a lifetime cost of $1.2 — and it was **the weaker argument**. Measured in
dollars the step looks too cheap to bother removing; measured in **latency** it is a full
serialized agent round-trip on the critical path of every review round. A round is five
serial segments (`Pass 1 → Pass 1.5 → Pass 2 → cross-model → PIDA`), each a barrier that
waits for every dispatch in it. Pass 1.5 is one of those five and contributes one agent's
full latency while nothing else runs. That, not the 1.9%, is the reason to remove it.
The agent nevertheless serves cross-model PIDA mode B, and
`code-verifier_body.md.j2:25-27` makes **mode A the default for an unlabelled invocation**.
**Decision:** Remove the Pass 1.5 dispatch from `/hm:review`. Pass 2 consumes the raw
Pass 1 list. Retain the agent, and **invert its default**: an unlabelled invocation
resolves to mode B, or is an explicit error. Retain the `VerifierClient` /
`verify_findings()` library surface — `two_pass_review.py:184-200` records it as a
deliberately retained inject-only API under a prior ADR-008; only the template dispatch
is removed.
**Consequences:**
- ✅ One agent dispatch and one strict serialization barrier removed per review round.
- ✅ An unlabelled PIDA dispatch can no longer silently run the redaction-era rubric
  against restored-metadata input.
- ⚠️ The agent file keeps a mode with no template caller until stage 2.
**Rejected alternatives:** Delete the agent — rejected, PIDA mode B is a live consumer.
Leave the default at mode A — rejected, that is the anti-anchoring violation its own
comment warns about.
**Source:** Interview #1; validator critique 10 + codex `09e94a60`, antigravity `2e381cca`.

### ADR-011: Launch the cross-model voters concurrently with Pass 1
**Status:** Accepted (2026-08-05, interview #16 — scope widened on the latency axis)
**Context:** `review.md.j2` runs Step 3.5's cross-model voters **after** Pass 2 completes,
making them a fourth serial barrier. Verified against the template: each model's input is
**`git diff`** — the classifier at Step 3.5 reads `git diff --name-only HEAD` /`--numstat`,
and the findings arrive tagged `source: "<model>"` and are folded at Step 4. **Nothing in
the cross-model path consumes Pass 1 or Pass 2 output.** Meanwhile `agy` alone carries a
native 240 s timeout, so the segment is minutes of pure waiting.
**Decision:** Launch every enabled second-opinion model **concurrently with Pass 1**, and
join its results at the existing Step 4 fold point. Step 3.6/3.7 (PIDA) still runs after,
because it genuinely depends on the cross-model findings.
**Consequences:**
- ✅ One serial barrier removed. With ADR-001 the round goes from **five serial segments to
  three**.
- ✅ **Zero detection change** — same voters, same prompt, same fold point, same K=2
  threshold. This is the only latency lever in stage 1 that needs no evidence, because it
  changes ordering and nothing else.
- ⚠️ The high-diff classifier (Side preset) must run before launch rather than after Pass 2;
  it reads only git state, so this is a move, not a rewrite.
- ⚠️ A failed model now degrades earlier in the round; the warn-and-proceed contract is
  unchanged.
**Rejected alternatives:** Leave the ordering and rely on Pass 1.5's removal alone —
rejected, that addresses one of five segments while the user's binding complaint is
wall-clock. Pull Pass 2 / the validator's second pass / the Phase D full-suite trigger into
stage 1 as well — **rejected by the user at interview #16**: each trades detection for time,
and the validator's second pass had just caught two criticals in this very PLAN.
**Source:** Interview #16; user correction that the dollar-denominated analysis was hiding
the latency problem.

### ADR-002: Telemetry nullability must bind the rendered producer, not the model
**Status:** Accepted (2026-08-05)
**Context:** `review_telemetry.py:53-54` declares `verifier_kept_n` / `verifier_dropped_n`
as required non-nullable ints. The producer is **not Python** — it is the field list at
`review.md.j2:610` plus the instruction at `:592` that round-level numerics default to 0.
**Decision:** Make the **two required** fields `verifier_kept_n` / `verifier_dropped_n`
`int | None = None` — `verifier_false_drop_n` / `verifier_false_keep_n` at `:55-56` are
already nullable and are not touched — **and** change the rendered emitter to omit them (or
emit null) when the verifier did not run. A half-filled
`kept`/`dropped` pair is rejected. Existing rows carrying integers must still parse.
**Consequences:**
- ✅ "Verifier not run" stays distinguishable from "ran, dropped nothing" — the row-kind
  conflation already shipped once in `second-opinion.jsonl` is not repeated.
- ⚠️ Any consumer assuming the field is always an int must handle `None`.
**Rejected alternatives:** Emit 0 — rejected, that permanently poisons the dataset stage 2
reads. Relax only the Pydantic model — rejected, it is a no-op while `:592`/`:610` stand.
**Source:** Validator critique 2 + codex `918c6418`.

### ADR-003: The fix-introduced-defect guard becomes a Phase D step with a mutation control
**Status:** Accepted (2026-08-05)
**Context:** `fix-introduced-defect-passes-all-gates` is at count:4 with ratios 11/22, 7/7,
5, 11/14 — each on a green four-gate run, once alongside a 7/7 mutation check. Its remedy
(a) has been written in memory for months and is a step in no stage template.
**Decision:** Add a `/hm:execute` Phase D step requiring the author, after a Phase C
repair, to name the input window the repair newly makes reachable and assert a fixture
enters it in the same commit. The structural test must include a **negative mutation** —
deleting or weakening the operative clause must turn it red.
**Consequences:**
- ✅ The only lever that reduces review rounds without reducing detection.
- ⚠️ Adds a step to the hottest stage (`execute`, 23.8% of spend).
**Rejected alternatives:** Leave it as a memory lesson — rejected, four recurrences say
memory is not the enforcement point. Grep for the sentence only — rejected as too weak;
a fixed sentence is satisfiable by a sentence with no operative force.
**Source:** Interview #1; validator critique on Phase 2 + codex `dcc610da`.

### ADR-004: One `stage-agents.jsonl`, written at the base root, with a pre-registered aggregation
**Status:** Accepted (2026-08-05)
**Context:** `plan-validator` (34 dispatches, $70) and Phase A.5 `test-reviewer` (42
dispatches, $61) have **zero** ledger rows. Stage 2's decision on both depends entirely on
data that does not exist.
**Decision:** One `.claude/observability/stage-agents.jsonl`. Row schema:
`{ts, run_id, agent, stage, slug, pass_or_attempt, verdict, terminal, reason, duration_ms,
barrier_index}` — `agent` and `stage` are explicit discriminators.
`duration_ms` and `barrier_index` were added at interview #16: **agent latency is not
recoverable from the transcripts at all** (dispatch is asynchronous, so the tool result
returns immediately and the real duration arrives out of band), which means the harness has
**zero data on the axis the user experiences first**. A `verdict`-only row answers "does the
second pass ever change the outcome" but not "what does it cost in minutes"; stage 2 needs
both, since the whole point of the two-stage split is to decide with evidence.
`barrier_index` records which serial segment of the round the dispatch belonged to, so the
five-segments-to-three claim becomes measurable rather than asserted. Written at the **base repo root**, never
`Path.cwd()` (the `codex_ledger` worktree row-loss precedent). Append is atomic. The
aggregation expression stage 2 will evaluate is recorded in the PLAN alongside the schema,
so the ledger is not a denominator with no numerator.
**Consequences:**
- ✅ One file survives new agents; the discriminator prevents the `second-opinion.jsonl`
  row-kind conflation.
- ⚠️ Two schemas share a file; consumers must filter on `agent`.
**Rejected alternatives:** Per-domain files — rejected, they answer one question and would
multiply. Extend `delegation.jsonl` — rejected, it would widen "delegation" to all
subagents.
**Source:** Interview #9; validator critique 3 + codex `dcc610da833da73e`.

### ADR-005: Delegate repair splits into unconditional diagnosis and reproduction-gated fix
**Status:** Accepted (2026-08-05, revised after validation)
**Context:** Both `mismatch` rows carry `reason: null`, and the null is **structural** —
`wrapup_receipt.py:533-535` and `:604` call `delegation_ledger.append()` with no `reason=`.
No diagnosis exists. Worse, `wrapup_receipt.py:265-268` shows the `--worktree`/`doc_root`
path was **already repaired once for this same symptom** ("review M-05"). A preemptive
second fix there is remedy-(b) territory in the count:4 entry.
**Decision:** Split into two phases.
- **P4a (unconditional):** `delegation_ledger.append()` records the `Mismatch.kind` and an
  invocation/run correlator, respecting the `PIPE_BUF` truncation at
  `delegation_ledger.py:50-69`.
- **P4b (reproduction-gated):** a code fix lands **only** after a minimal reproduction that
  fails on current code is demonstrated. **If the cause does not reproduce: no code change,
  and AC-006 is waived on the record**, deferred to the next occurrence.
**Consequences:**
- ✅ Structurally cannot reproduce the count:4 class this PLAN exists to close.
- ✅ P4a's value (a diagnosable next occurrence) lands regardless.
- ⚠️ `wrapup`'s carry problem (15.6% of spend, carry 0.84) may go unaddressed this stage.
**Rejected alternatives:** Preemptive fix as first drafted — rejected by two independent
cross-model reviewers as the count:4 pattern, confirmed against disk. Delete the
mechanism — rejected, the user chose repair and no diagnosis yet justifies deletion.
**Source:** Interview #7 → #14; validator critique 4 + codex `0819fa4d`, antigravity `cc0453f6`.

### ADR-006: The detection check is a natural-experiment analysis, plus forward payload persistence
**Status:** Accepted (2026-08-05, revised twice after validation)
**Context:** The acceptance oracle is `golden` (cost metrics) with detection only proxied by
the regression suite — a proxy this repo has refuted four times — so a non-circular check was
added to cover the gap. It failed twice. **Attempt 1** (live re-invocation, hard fail, n=1)
was unimplementable: `codex_adapter.finding_id` is a deterministic stamp applied *after* a
reviewer emits, precisely because reviewers do not emit stable ids, and CLAUDE.md records
reviewer nondeterminism as strong enough to require id-keyed merge of voter state. **Attempt
2** (deterministic re-injection of archived reviewer outputs) was unimplementable for a
different reason, verified on disk: `REVIEW-second-opinion-acceptance-gate-2026-07-30.md`
contains **zero** id-shaped tokens — the earlier grep that "found ids" had matched prose
naming the `finding_id` function — and its own `:49-50` records that *"Pass 1.5's verifier
reduction did not run"* on that run. More decisively, `grep -rlE '"severity"\s*:\s*"P[0-3]"'`
over `.claude/observability/` and `work-docs/` returns **nothing**: this repo has never
persisted a per-reviewer finding payload anywhere. REVIEW documents are post-consensus
narrative; `review-*.jsonl` holds counts. There is no artifact to replay.
**Decision:** Two parts, neither a gate.
1. **Natural-experiment analysis (recorded, non-blocking).** The existing ledger already
   contains rounds where the verifier did not run — `fallback` values `verifier_deferred`
   (×2), `adr-008-no-auto-verifier`, `pass1_5_stripped_adr_008`,
   `pass1.5+pass2_redaction_skipped`, `no-verifier-no-formal-pass2` — against 41 rounds where
   it did. Compare `consensus_passed_n / pass1_n` and the severity distribution across the two
   groups. **This data predates the change, so the comparison cannot be circular.**
2. **Forward payload persistence.** Extend the P3 ledger work to persist per-reviewer finding
   payloads, so that from this landing onward a real replay becomes possible — for stage 2 and
   for every future pipeline change.
**Consequences:**
- ✅ Non-circular and nearly free: the data exists.
- ✅ Part 2 makes the check that failed twice implementable for the first time, permanently.
- ⚠️ **This is an analysis, not a gate.** n≈6 vs 41, observational, and each `fallback` value
  has a different cause — so it is confounded and cannot block a landing. Stage 1 therefore
  ships with **no** blocking detection check; that residue is the accepted AC-008 waiver, now
  larger than when it was written.
- ⚠️ Part 2 delivers no benefit within stage 1.
**Rejected alternatives:** Live re-invocation, hard fail — unimplementable (nondeterminism).
Deterministic re-injection — unimplementable (no persisted payload). Hand-transcribe the
narrative into a fixture — rejected: the executor would author the oracle it is graded
against, the self-referential defect AC-007's own `oracle_evidence` is written to avoid.
Withdraw the check entirely — rejected, part 1 costs almost nothing and part 2 fixes the root
cause.
**Source:** Interview #12 → #13 → #15; validator critiques 5 (pass 1) and 1 (pass 2), codex
`7afacf55`, antigravity `4ee9626a`.

### ADR-007: The ablation is measurement-only, and its arm is pinned post-removal
**Status:** Accepted (2026-08-05)
**Context:** The "+47pp precision on anchoring-prone diffs" claim was measured on a pipeline
that **contained** Pass 1.5. Running the ablation after ADR-001 measures a different
pipeline, so an un-pinned `reproduced: false` cannot distinguish "the claim was wrong" from
"the pipeline changed underneath it".
**Decision:** The ablation runs on the **post-removal** pipeline and the artifact records
that arm mismatch explicitly. Pass 2 stays in the pipeline regardless of the result;
deletion is a stage-2 decision. Corpus, run count, model/prompt version, cache handling and
the stage-2 decision rule are **pre-registered in the artifact before the run**.
`reproduced` is per-expected-id with failure causes, not a boolean.
**Consequences:**
- ✅ Pre-registration makes the accepted honesty waiver survivable — a bad measurement costs
  a re-run, not a shipped regression.
- ⚠️ The result is not directly comparable to the inherited claim; stage 2 must read the
  recorded mismatch.
**Rejected alternatives:** Gate the ablation's honesty with a rubric — rejected at
interview #10; the waiver stands. Measure pre-removal — rejected, stage 2 needs the
pipeline it will actually decide about.
**Source:** Interview #4, #6, #10; validator critique 7 + codex `4abaf287`.

### ADR-008: `depends_on` carries semantic dependency only; file conflicts are merge hazards
**Status:** Accepted (2026-08-05)
**Context:** The first draft chained P1→P2→P3→P4 although no phase consumed a prior
phase's output; the only shared artifact was `surface_baseline.json`, which every phase
already declared as a hazard.
**Decision:** `depends_on` lists only real data dependencies. File conflicts live in
`merge_hazards` plus a stated integration order.
**Consequences:**
- ✅ Five phases become genuinely independent.
- ⚠️ The integration order must be honoured separately from the dependency graph.
**Rejected alternatives:** Keep the chain — rejected, it serialized three unrelated domains
for nothing.
**Source:** Validator critique 7 + codex `fceaf623`, antigravity `a51e1622`.

### ADR-009: Rollback is a per-phase patch snapshot, because `/hm:execute` never commits
**Status:** Accepted (2026-08-05)
**Context:** `execute.md.j2:346` forbids `git commit` and `:448` makes its absence an exit
check. "Revert to the pre-phase commit" therefore has no referent, and P1 — the only
destructive phase — most needs one.
**Decision:** At each phase boundary write `work-docs/.rollback-P<N>.patch` via
**`git diff -- <that phase's Scope IN paths>`** — a path-scoped diff, never a whole-tree
snapshot. Rollback = apply that patch in reverse. A whole-tree snapshot would make P1's
patch a superset that also reverts P2/P3/P4a's unrelated work, which is exactly the case
that matters: P1 is the destructive phase and the phases after it stack on the removal. The
recovery procedure must preserve unrelated user dirt in the worktree.
**Consequences:**
- ✅ A mid-plan abort has a mechanical way back, per phase and independently.
- ⚠️ A phase that touches a file another phase also touched still conflicts on those hunks;
  the integration order (P5 second) minimises how far that reaches.
- ⚠️ Patch files are churn; they are gitignored and removed at wrapup.
**Rejected alternatives:** Per-phase commits — rejected, it violates the execute stage's
single-commit-owner contract.
**Source:** Validator critique 8 + codex `0508e177`.

### ADR-010: `surface_baseline.json` gets an owning terminal phase
**Status:** Accepted (2026-08-05)
**Context:** AC-008 is the SPEC's only integration-level criterion, and in the first draft
four phases listed the baseline as a hazard while none owned it. A criterion many phases
perturb and none owns is satisfied by whichever phase is last to hit red — i.e. by
rebaselining, which is `ratchet-rebaselined-by-its-own-subject` (count:2).
**Decision:** A terminal phase P7 owns AC-008 **and** the SPEC's `pending_test` write-back.
Its exit is the four mechanical gates green plus a named artifact
`work-docs/BASELINE-DELTA-P7.md` that embeds the literal `git diff` of
`surface_baseline.json` and carries one attribution row per changed key, with the phase id
drawn from the phase Scope IN lists rather than free text — checked by
`tests/structural/test_baseline_delta_attribution.py`. Prose alone would let /hm:execute
satisfy the exit by asserting it complied.
**Consequences:**
- ✅ The "never absorbed silently" constraint gains a real, red-able enforcement point,
  matching the standard every sibling phase is held to.
- ✅ Every AC leaves `pending_test` behind, so `cross_validate` stops skipping all eight.
- ⚠️ P7 cannot start until every surface-touching phase is in.
**Rejected alternatives:** Leave it a shared hazard — rejected, that is the recorded
failure. Let each phase rebaseline its own delta — rejected for the same reason.
**Source:** Validator critique 6.

## 🏗️ Technical Design

**Current state.** `/hm:review` runs Pass 1 (redacted, N reviewers) → Pass 1.5
(`code-verifier`, 1 agent) → Pass 2 (full metadata, N reviewers) → cross-model voters →
PIDA → consensus. `review.md.j2:246-247` performs the substitution being removed: *"Use
`kept` as the input to Pass 2 instead of the raw Pass 1 list."* The Jinja branch at
`:251-258` gives the single-reviewer render a different body, and `:255` instructs manual
re-enablement when `--with-reviewers` raises the count; `:278` references the *"Pass 1.5
verified findings"* list and sits **after** the `{% endif %}`, so it renders on the
single-reviewer path too.

**Affected components.**

| Component | Change |
|---|---|
| `templates/stages/review.md.j2` | remove Pass 1.5 block (`:240-258`), fix `:255`, `:278`, `:592`, `:610` |
| `templates/agents/code-verifier_body.md.j2` | invert default mode (`:25-27`) |
| `synthesize.py:391` | agent description drops mode A |
| `two_pass_review.py` | template dispatch removed; library API retained (ADR-001) |
| `review_telemetry.py:53-54` | four `verifier_*` fields → `int \| None = None` |
| `templates/stages/execute.md.j2` | Phase D step (ADR-003); Phase A.5 ledger emit |
| `templates/stages/plan.md.j2` | Step 4 ledger emit |
| new `src/harness_maker/stage_agent_ledger.py` | ADR-004 writer |
| `delegation_ledger.py` | accept + persist `reason` (ADR-005 P4a) |
| `wrapup_receipt.py:533,604` | pass the `Mismatch.kind` through |
| `tests/unit/test_pass1_skip.py` | asserts Pass 1.5 present → invert |
| `tests/render/test_render_review_read_budget.py:489-497` | mutates the literal Pass 1.5 heading as a control → retarget |
| `tests/structural/instruction_baseline.json` | 8 occurrences |
| `tests/unit/test_pass15_active.py` | invert |
| `templates/skills/second-opinion-gate/SKILL.md.j2` | drop the Pass 1.5 reference |

**Data flow after ADR-001.** Pass 1 findings → (unchanged, identity preserved) → Pass 2 →
`codex_adapter stamp-ids` → cross-model fold → PIDA → consensus. The removed edge is the
only one; ADR-006's deterministic replay is the assertion that it is the only one.

**Stage-2 aggregation, pre-registered (ADR-004).**
- Validator: `P(verdict changes | pass 2 ran)` = rows with `pass_or_attempt == 2` whose
  `verdict` differs from the same `run_id`'s pass 1, over all `pass_or_attempt == 2` rows.
  A low ratio is the evidence for deleting the second pass.
- Phase A.5: `P(FAIL)` = rows with `verdict == FAIL` over all Phase A.5 rows. A low ratio
  is the evidence for deleting the gate.

## 📝 Implementation Plan

Integration order (ADR-008, driven by `surface_baseline.json`, not by dependency):
**P1 → P5 → P2 → P3 → P4a → P6 → [P4b] → P7.**

P5 runs **immediately after P1** so the analysis of the removal lands before other phases
stack on top of it — under ADR-009's path-scoped patches, a late P1 rollback is cheapest
when the fewest phases sit above it.

### Phase 1 — Remove the Pass 1.5 dispatch + hoist the cross-model voters (ADR-001, ADR-011)
- **depends_on:** `[]`
- **parallel_group:** `independent` (integration-serialized on the baseline)
- **merge_hazards:** `templates/stages/review.md.j2`, `surface_baseline.json`, `_ATOMIC_RATCHET`, `tests/structural/instruction_baseline.json`
- **Scope IN:** `review.md.j2` (`:240-258`, `:255`, `:278`, `:592`, `:610`), `code-verifier_body.md.j2:25-27`, `synthesize.py:391`, `review_telemetry.py:53-54`, `two_pass_review.py` (dispatch docs only), **`tests/structural/test_review_pass15_removed.py` (new — the path AC-001 is bound to in machine.yaml:21)**, `tests/unit/test_pass15_active.py`, `tests/unit/test_pass1_skip.py`, `tests/render/test_render_review_read_budget.py`, `tests/structural/instruction_baseline.json`, `templates/skills/second-opinion-gate/SKILL.md.j2`
- **Scope OUT:** `VerifierClient` / `verify_findings()` (retained, ADR-001); PIDA mode B rubric body
- **Exit criterion:**
  1. **Positive data-flow assertion (render-checkable half only).** A render test proves the
     stated input to Pass 2 is the raw Pass 1 list, asserted separately on the
     **multi-reviewer**, **single-reviewer**, and **`--with-reviewers`** renders. The
     original wording also demanded "finding identity preserved into consensus" — that is a
     **runtime** property of a pipeline whose steps are prose, and no render assertion can
     observe it. Nothing in stage 1 verifies it: ADR-006's replay, which would have, has no
     input artifact. Recorded here as an explicit gap rather than implied by an exit
     criterion that cannot deliver it.
  2. No rendered command dispatches a Pass 1.5 verifier on any of the 3 targets.
  3. `review.md.j2` Step 3.7 dispatch **names mode B**, and an unlabelled `code-verifier`
     invocation resolves to mode B or errors.
  4. A rendered emitter omits/nulls the four `verifier_*` fields; an existing row carrying
     integers still parses; a half-filled `kept`/`dropped` pair is rejected.
  5. **Cross-model hoist (ADR-011).** The rendered review stage instructs the cross-model
     voters to launch **concurrently with Pass 1**, not after Pass 2; the high-diff
     classifier (Side preset) runs before that launch; Step 3.6/3.7 PIDA still follows the
     cross-model results; and the Step 4 fold point is unchanged. Asserted on all 3 targets.
  6. `uv run pytest tests/ -k "pass15 or pass1_skip or two_pass or review_telemetry or read_budget or instruction_baseline or second_opinion"` green.
- **Risk:** medium — removes a live pipeline step, reorders another, and touches a
  mutation-sensitivity control.
- **Rollback:** `work-docs/.rollback-P1.patch` (ADR-009).

### Phase 2 — Phase D newly-reachable-window step
- **depends_on:** `[]`
- **parallel_group:** `independent`
- **merge_hazards:** `surface_baseline.json`
- **Scope IN:** `templates/stages/execute.md.j2` (Phase D), `tests/structural/test_phase_d_reachable_window.py`
- **Exit criterion:** the step renders on all 3 targets **and** the test carries a negative
  mutation control — deleting or weakening the operative clause (the demand for a fixture
  that enters the newly-reachable window in the same commit) turns it red.
- **Risk:** low. **Rollback:** `.rollback-P2.patch`.
- **Baseline trip recorded for P7 (do NOT resolve here — ADR-010).** Landing the step turned
  three size guards red. They are left red on purpose: `surface_baseline.json` and
  `_ATOMIC_RATCHET` belong to P7, and a phase that rebaselines the guard it tripped is R5
  verbatim (`ratchet-rebaselined-by-its-own-subject`, count:2).

  | Guard | Before | After | Limit | Δ |
  |---|---|---|---|---|
  | `_ATOMIC_RATCHET["execute"]` | 29 820 | 32 336 | 30 416 (+2%) | **+2 516 (+8.4%)** |
  | `claude` aggregate shipped surface | 354 283 | 356 320 | 354 283 (no growth) | +2 037 |
  | `test_the_standalone_generator_agrees_…` | — | — | — | follows the above |

  The aggregate delta (+2 037) is smaller than the execute delta (+2 516) because P1's
  removal gave back ~479 chars in `review`. **P7 must attribute both rows, not one.**

  ⚠️ **The tension is real and belongs in P7's write-up, not buried here.** This is a
  step-*reduction* PLAN whose P2 makes the hottest stage 8.4% larger, and the honest
  framing is ADR-003's recorded consequence: Phase D.5 buys detection at a cost in prompt
  size, against a defect class at count:4 that four green four-gate runs failed to catch.
  P7 raising the ceiling is the planned resolution — but it is a **decision**, and the
  BASELINE-DELTA row must read as one rather than as bookkeeping.

### Phase 3 — `stage-agents.jsonl` writer + wiring
- **depends_on:** `[]`
- **parallel_group:** `independent`
- **merge_hazards:** `templates/stages/plan.md.j2`, `templates/stages/execute.md.j2`, `surface_baseline.json`
- **Scope IN:** new `src/harness_maker/stage_agent_ledger.py`, `plan.md.j2` Step 4, `execute.md.j2` Phase A.5, CLI registration, `tests/unit/test_stage_agent_ledger.py`, **per-reviewer finding-payload persistence (ADR-006 part 2)**
- **Exit criterion:**
  0. **Payload persistence** — a review round persists its per-reviewer finding payloads in a
     re-injectable form. This is the artifact whose absence made ADR-006's replay
     unimplementable; it delivers nothing in stage 1 and everything afterwards.
  1. Writer unit tests: one row per validator pass **including the 2-pass case**, one row
     per Phase A.5 attempt **including the retry case**, plus explicit `skipped` / `failed`
     rows for the launch-failure paths.
  2. **Render-grep on all 3 targets** proving the emit line exists at `plan.md.j2` Step 4
     and `execute.md.j2` Phase A.5 — the unit test alone is satisfiable with zero wiring.
  3. The dispatch count in the AC predicates is derived from an **independent** source
     (the rendered dispatch sites), never from the ledger or the writer.
  4. Rows land at the **base root** under a worktree cwd.
- **Risk:** medium — a self-referential predicate here yields a zero-row denominator in stage 2.
- **Rollback:** `.rollback-P3.patch`.
- **Baseline trip, cumulative through P3 (P7 resolves — ADR-010).** Left red on purpose;
  this supersedes the P2 table above as the running total.

  | Guard | Phase 0 | Now | Limit | Δ |
  |---|---|---|---|---|
  | `_ATOMIC_RATCHET["execute"]` | 29 820 | 33 774 | 30 416 | +3 954 (P2 step + A.5 emit) |
  | `_ATOMIC_RATCHET["plan"]` | 44 827 | 46 008 | 45 723 | +1 181 (validator emit) |
  | `_ATOMIC_RATCHET["review"]` | 32 502 | 33 721 | 33 152 | +1 219 (payload persist − P1 removal) |
  | `claude` aggregate | 354 283 | 359 808 | 354 283 | **+5 525** |
  | `test_roundtrip_budget` ×4 | — | — | — | follows the above |

  **P7 must attribute all four rows.** The aggregate is the one to read: **+5 525 chars on
  a PLAN whose stated purpose is reducing workflow cost.** Roughly 2 500 of that is P2's
  detection step and 3 000 is P3's instrumentation — and P3's is the kind that pays for
  itself only if stage 2 actually reads the ledger and deletes something. If stage 2 never
  runs, this PLAN's net effect on prompt size is **an increase**, and P7's write-up should
  say so rather than presenting the ceiling raise as bookkeeping.

### Phase 4a — Delegate diagnosis capture (unconditional)
- **depends_on:** `[]`
- **parallel_group:** `independent`
- **merge_hazards:** `templates/stages/wrapup.md.j2`, `surface_baseline.json`
- **Scope IN:** `delegation_ledger.py` (`reason=` plumbing, `PIPE_BUF` truncation at `:50-69`), `wrapup_receipt.py:533,604`, `tests/unit/test_delegation_reason_capture.py`
- **Exit criterion:** a reconciliation producing any `Mismatch` writes a row whose `reason`
  names the `Mismatch.kind` and carries an invocation/run correlator; a row with a kind
  longer than the truncation budget is truncated visibly, not dropped.
- **Risk:** low. **Rollback:** `.rollback-P4a.patch`.

### Phase 4b — Delegate fix (REPRODUCTION-GATED — may not run)
- **depends_on:** `[4a]` — real: the fix needs the diagnosis
- **parallel_group:** `serial-conditional`
- **merge_hazards:** `specs/SPEC-workflow-loop-efficiency.machine.yaml` (shared with P7), plus whatever the reproduction implicates
- **Entry gate:** a minimal reproduction that **fails on current code**. Without it this
  phase does not run.
- **Scope IN:** whichever path the reproduction implicates, **plus
  `specs/SPEC-workflow-loop-efficiency.machine.yaml` (AC-006) on either branch**
- **Exit criterion:** the reproduction test fails against the pre-change reconciliation path
  and passes after; then AC-006 is written back with `pending_test: false` and the resolved
  `test_ids`.
- **If the cause does not reproduce:** no code change; record the outcome; **AC-006 is waived
  on the record**. The waiver has a concrete on-disk representation, because "waived" is not
  a status the schema offers: set `test_ids: []`, `pending_test: false`, and put the waiver
  text in `oracle_independence_waiver` (a schema-legal field, `spec_machine.AC`). Leaving
  `pending_test: true` pointing at a test that will never exist is what
  `spec_machine.py:774` classifies as a **missed binding** and what
  `observability/spec_drift.py` reports as an AC↔test gap — i.e. indistinguishable from
  abandoned work, and the state that would push a later executor to write the very
  preemptive fix ADR-005 forbids. Verify the result passes `hm spec_machine check --all`.
  This is a successful outcome of this phase, not a failure.
- **Risk:** medium if it runs — `wrapup_receipt.py:265-268` shows this surface was already
  repaired once for the same symptom.
- **Rollback:** `.rollback-P4b.patch`.

### Phase 5 — Pass 2 ablation + natural-experiment analysis
- **depends_on:** `[1]` — real: it measures the post-removal pipeline (ADR-007)
- **parallel_group:** `independent`; **runs second in the integration order**
- **merge_hazards:** none
- **Scope IN:** `work-docs/ABLATION-pass2-2026-08-XX.md`, `tests/unit/test_ablation_artifact.py`
- **Exit criterion:**
  1. The artifact's pre-registration block (corpus, run count, model/prompt version, cache
     handling, cost computation, tolerated delta, stage-2 decision rule) is written
     **before** the run.
  2. Artifact keys `{diffs, pass1_only, pass1_plus_pass2, delta, reproduced}` present;
     `reproduced` is per-expected-id with failure causes.
  3. The recorded arm mismatch versus the inherited pre-removal claim is stated.
  4. **Natural-experiment analysis (recorded, non-blocking — ADR-006 part 1):** the artifact
     compares `consensus_passed_n / pass1_n` and the severity distribution between the ~6
     ledger rounds whose `fallback` shows the verifier did not run and the 41 where it did,
     naming each `fallback` value and its confound. It states plainly that n is small and
     the comparison is observational, so it **does not gate** the landing.
- **Risk:** low. **Rollback:** `.rollback-P5.patch`.

### Phase 6 — Native-capability redundancy matrix
- **depends_on:** `[]`
- **parallel_group:** `independent`
- **merge_hazards:** none
- **Scope IN:** `work-docs/MATRIX-native-redundancy.md`, `tests/structural/test_redundancy_matrix.py`
- **Exit criterion:** the matrix subject set equals the union of rendered commands, skills
  and agents, derived from an inventory that **never reads the matrix**; and every row is
  non-empty in four columns — native Claude Code equivalent (the literal `none` is a valid
  value), `cursor` availability, `codex` availability, and one of `keep` / `retire` /
  `merge`. The **judgment itself is deliberately not gated** (SPEC AC-007, Open Question 2
  class); acting on the matrix is stage 2.
- **Risk:** low. **Rollback:** `.rollback-P6.patch`.

### Phase 7 — Integration, baseline delta, and SPEC write-back (owns AC-008)
- **depends_on:** `[1, 2, 3, 4a, 5, 6]` **+ `4b` when it ran** — real: it asserts their union
- **parallel_group:** `serial-terminal`
- **merge_hazards:** `surface_baseline.json`, `_ATOMIC_RATCHET`
- **Scope IN:** `work-docs/BASELINE-DELTA-P7.md`, `tests/structural/test_baseline_delta_attribution.py`, `specs/SPEC-workflow-loop-efficiency.machine.yaml`
- **Exit criterion:**
  1. `ruff check`, `ruff format --check`, `mypy --strict src/`, and the full `pytest` suite green.
  2. `BASELINE-DELTA-P7.md` embeds the literal `git diff` of `surface_baseline.json` and
     carries one attribution row per changed key, the phase id drawn from that phase's
     Scope IN list. The structural test goes red when a changed key has no row, so a silent
     rebaseline fails mechanically rather than by assertion.
  3. **`pending_test` write-back:** `hm spec_machine mark-tested` is run for every AC whose
     test now resolves, and `hm spec_machine check --all` passes. All eight ACs currently
     carry `pending_test: true`, which makes `cross_validate` skip every one of them — the
     SPEC would otherwise report coverage it does not have.
- **Risk:** medium — this is where a rebaseline temptation lands.
- **Rollback:** `.rollback-P7.patch`.
- **⚠️ WRAPUP BLOCKER found during P7 — three deliverables will not be committed by default.**
  Two independent allowlists both omit this PLAN's new document types, and each fails
  **silently**. This is `absent-case = feature black hole` (failures.md count:8, the
  most-recurring class in this repo) at two layers at once.

  1. **`.gitignore:59`** is `work-docs/*` plus per-prefix negations (`PLAN-`, `RESEARCH-`,
     `REVIEW-`, `SPEC-`, `CLOSE-`, `AUDIT-`, `BASELINE-`, `RECEIPT-`). `ABLATION-*` and
     `MATRIX-*` were on neither list, so P5's and P6's entire deliverables were invisible to
     `git status`. **Fixed in this phase** — both prefixes added with the same durability
     rationale the `BASELINE-*` entry carries.
  2. **`wrapup_land`'s staging manifest** (`wrapup.md.j2` Steps 6→7.6) is a fixed
     `--required`/`--optional` list: PLAN, `.claude/memory/`, REVIEW, RESEARCH, SPEC,
     SPEC.machine.yaml. **NOT fixed here** — editing the wrapup template would move the size
     baselines P7 has just frozen and attributed, and it is outside P7's declared Scope IN.

  **Therefore `/hm:wrapup` for this task MUST pass three extra flags**, or ABLATION, MATRIX
  and BASELINE-DELTA stay untracked and P5/P6/P7 ship as nothing:

  ```
  --optional work-docs/ABLATION-*.md
  --optional work-docs/MATRIX-*.md
  --optional work-docs/BASELINE-DELTA-*.md
  ```

  **The general fix belongs in its own change** (stage 2 or a follow-up): the manifest should
  not be a hand-maintained type list at all. Every future document type will hit exactly this,
  and the failure mode is a wrapup that reports success while dropping the artifact.

## 🧪 Testing Strategy

- **Unit** — `stage_agent_ledger` row shape incl. skip/fail paths (P3); `delegation_ledger`
  reason plumbing + truncation (P4a); ablation artifact shape (P5); `review_telemetry`
  nullability, backward-parse, half-filled rejection (P1).
- **Render / structural** — Pass 2 input data-flow on three reviewer-count paths (P1);
  mode B dispatch naming + unlabelled-invocation resolution (P1); Phase D step with a
  negative mutation control (P2); dispatch-site emit lines on 3 targets (P3); matrix
  coverage + column presence from an independent inventory (P6).
- **Deterministic replay** — archived reviewer outputs through the changed pipeline (P5).
- **Integration** — four mechanical gates + enumerated baseline delta (P7).
- **Explicitly not tested** — whether the ablation was run honestly (waiver, AC-005); the
  keep/retire judgment quality (AC-007); reviewer-side detection change (waiver, AC-008).

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | P1's edits leave Pass 2's input undefined on the single-reviewer or `--with-reviewers` path | medium | high | Exit 1 asserts the data flow on all three renders separately |
| R2 | A fix lands with no reproduction, recreating count:4 | **high** (the first draft did exactly this) | high | ADR-005 splits P4a/P4b with a hard entry gate; ADR-003 adds the guard to every future repair |
| R3 | The ledger ships unwired; stage 2 opens on a zero-row denominator | medium | high | P3 exit 2/3 — render-grep + independent dispatch source |
| R4 | ADR-002 lands as a schema-only no-op and poisons the stage-2 dataset with zeros | medium | high | P1 exit 4 binds the rendered producer |
| R5 | `surface_baseline.json` is silently rebaselined by whichever phase trips it | medium | medium | ADR-010 / P7 ownership with an attributed delta |
| R6 | **Stage 1 ships with no blocking detection check at all** — ADR-006 failed twice and its replacement is a non-blocking analysis | **certain** (it is the design) | high | Not mitigated. The measured exposure is bounded: the only behaviour removed is Pass 1.5, whose lifetime drop rate is 1.9%. ADR-006 part 2 makes the check possible from the next landing on |
| R7 | Detection regresses in a way nothing here can see | low–medium | high | Accepted, recorded as the AC-008 waiver — **now larger than when it was written**, since no replay backs it |
| R8 | Mid-plan abort leaves a half-removed pipeline | low | medium | ADR-009 per-phase patch snapshots |

## ✅ Success Criteria

- [x] AC-001 — no rendered command dispatches a Pass 1.5 verifier; the agent still renders and defaults to mode B (P1)
- [x] AC-009 — the rendered review stage launches the cross-model voters concurrently with Pass 1, PIDA still follows them, and the Step 4 fold is unchanged (P1)
- [x] Serial segments per review round drop from 5 to 3, and `barrier_index` + `duration_ms` make that measurable rather than asserted (P1 + P3)
- [x] AC-002 — Phase D demands the newly-reachable window, with a mutation control (P2)
- [x] AC-003 — one `stage-agents.jsonl` row per validator pass, wired at the dispatch site (P3)
- [x] AC-004 — one row per Phase A.5 attempt, wired at the dispatch site (P3)
- [x] AC-005 — pre-registered ablation artifact with per-id `reproduced`, the arm mismatch stated, and the natural-experiment comparison recorded (P5)
- [x] AC-006 — delegate mismatch covered by a failing-then-passing test **or** explicitly waived on the record because it did not reproduce (P4b)
- [x] AC-007 — matrix covers every command, skill and agent, four columns non-empty (P6)
- [x] AC-008 — four gates green, the baseline delta enumerated and attributed by a red-able test, and every AC's `pending_test` written back (P7)
- [x] Nothing in this landing deletes Phase A.5, the validator's second pass, or Pass 2 (stage-2 boundary held)
- [x] Per-reviewer finding payloads are persisted from this landing on, so the detection check that failed twice is implementable next time (P3 exit 0)

## 🔍 Plan Validation

**Outcome:** MAJOR_REVISION (pass 1) → revised → MAJOR_REVISION (pass 2) → resolved. The
validator's re-run budget is one pass; the pass-2 criticals were resolved by an interview
round and by direct revision, not by a third validator call.

Cross-model second opinion: **codex `invoked`** (13 findings, 2×P0), **antigravity
`invoked`** (5 findings, 1×P0). Both independently identified the same P0 — that the draft's
Phase 4 was itself an instance of `fix-introduced-defect-passes-all-gates`, the class this
PLAN exists to close.

### Pass 2 — what the revision got wrong

Two criticals and four warnings survived the first revision. The important one:

**ADR-006 was unimplementable a second time, and on a premise I had asserted to the user as
fact.** Round 2 of the interview told the user that exactly one archived REVIEW carried
stable finding ids. That was false — the grep behind it matched prose *naming* the
`finding_id` function, and the document contains zero id-shaped tokens. The same document
states at `:49-50` that Pass 1.5 did not run on that review. Verifying further:
`grep -rlE '"severity"\s*:\s*"P[0-3]"'` across `.claude/observability/` and `work-docs/`
returns nothing — **no per-reviewer finding payload has ever been persisted in this repo.**
Attempt 1 failed on nondeterminism; attempt 2 failed on a missing artifact. The mechanism
changed and the defect moved rather than resolving. Interview round 4 replaced it with the
natural-experiment analysis plus forward payload persistence, and the PLAN now says plainly
that stage 1 has **no blocking detection check** (R6).

| Pass-2 critique | Severity | Resolution |
|---|---|---|
| ADR-006 assumes an artifact never persisted; archive has no ids and ran without Pass 1.5 | critical | Interview #15 → ADR-006 rewritten (analysis + forward persistence); R6 restated honestly |
| P4b's "waived" branch has no representable state in machine.yaml; no phase owns the file | critical | P4b Scope IN gains the machine.yaml with the exact field mutation and a validation check |
| P7's baseline delta is prose with no mechanical check | warning | ADR-010 + P7 exit 2: named artifact, embedded diff, attribution test |
| P1 exit 1 asks a render test to observe a runtime property | warning | Split; identity half recorded as an explicit uncovered gap |
| AC-001's bound test path in no phase; no owner for `pending_test` write-back | warning | Path added to P1 Scope IN; write-back assigned to P7 exit 3 |
| Rollback patches are whole-tree, so P1's reverts later phases | warning | ADR-009 patches are path-scoped; P5 resequenced to run second |
| "four `verifier_*` fields" — two are already nullable | suggestion | ADR-002 narrowed to the two that change |
| P7 `depends_on` omits conditional P4b | suggestion | Recorded as a conditional edge |

| Validator critique | Severity | Resolution |
|---|---|---|
| P1 exit is absence-only; 3 test artifacts unlisted | critical | ADR-001, P1 exit 1 + expanded scope |
| ADR-002 binds the model, not the producer | critical | ADR-002 rewritten; P1 exit 4 |
| AC-003/004 predicates are self-referential | critical | P3 exit 2/3 (render-grep + independent source) |
| P4 is a fix without a reproduction; its exit is unsatisfiable on the deferred branch | critical | Interview #14 → ADR-005 splits P4a/P4b |
| ADR-006 hard-fail over live n=1 is unimplementable | critical | Interview #13 → ADR-006 deterministic replay |
| AC-008 has no owning phase | warning | ADR-010 → P7 |
| `depends_on` encodes merge order; P5's arm undefined | warning | ADR-008, ADR-007 |
| No rollback point; execute never commits | warning | ADR-009 |
| P6 under-covers S7's columns | warning | P6 exit column-presence clause |
| code-verifier default becomes the dead mode | warning | ADR-001 default inversion |
| Library API keep/remove unstated | suggestion | ADR-001 retention sentence |

Two injected findings were **rejected** and the reasoning is recorded rather than silently
dropped: codex `437239cf` and antigravity `7f37d3e0` both asked to gate the matrix's
keep/retire *judgment*. SPEC AC-007 scopes that check to coverage on purpose and acting on
the matrix is a stage-2 Non-Goal; gating judgment quality would import an unresolvable
oracle into a stage-1 artifact. The narrower, legitimate residue — that S7 names four
columns and the draft checked only the subject set — was adopted as P6's column-presence
clause. Codex `4abaf287` was split: its honesty-gate half was rejected (relitigates the
interview #10 waiver), its pre-registration half accepted into ADR-007.
