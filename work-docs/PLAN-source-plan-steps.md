---
type: plan
task_slug: source-plan-steps
status: complete
created: 2026-09-18
tags: [harness-maker, plan, python, step-sensitivity, evidence, intent-layer]
interview_rounds: 4
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Give the 13 unsourced plan-stage steps class-supporting evidence; unsourced_step_share 47.1 → ≤31.8"
objective: SOURCE-PLAN-STEPS
spec_need_verdict: none
spec_need_target: source-plan-steps
---

# PLAN — Source the plan stage's inherited step classifications

## 🎯 Executive Summary

**TL;DR.** 13 of the plan stage's registry entries in `src/harness_maker/step_sensitivity.py`
carry grade `unsourced` — a class inherited from a neighbouring step with no RESEARCH row. This
task first obtains a genuinely blind Codex classification from a curated evidence bundle, then
writes Claude's own class-supporting evidence per step, reconciles the two under explicit rules,
and syncs the registry with the three documents pinned to it. An entry whose final class lacks
support stays `unsourced`.

**Why.** Objective `SOURCE-PLAN-STEPS` (active): the mission requires measuring model/host
progress quickly, and a step whose class is a guess cannot be retired when a model improves.
Outcome `unsourced_step_share` is 47.1 (40/85); sourcing all 13 gives 27/85 = 31.8. The approved
outcome target is 20, which no plan-stage-only task can reach (ADR-005 §close rule).

**Key decisions.** Class-property evidence bar (ADR-001); reclassify but never delete, TUNE out of
scope (ADR-002); blind Codex first, joint class-then-grade reconciliation (ADR-003); new RESEARCH
doc (ADR-004); aggregates-only bundle + hypothesis-based close (ADR-005).

**Impact.** Registry data + docs only. Nothing at runtime reads the registry
(`step_sensitivity.py:5`); render output and snapshots are unchanged.

## 📚 Prior Work

- `work-docs/RESEARCH-workflow-steps-vs-model-capability.md` Table 1 — the source of every graded
  entry today; its grade scale (`***` reproduced / `**` measured once / `*` judgement) is reused.
- `specs/SPEC-workflow-steps-vs-model-capability.md` AC-001…007 fix the registry's *structure*
  (coverage, Side ordering, class column, docs carry classes), not per-entry grades — this task
  changes no AC (`spec_need_verdict: none`).
- `[wiki:architecture] step-sensitivity-classes` — `unsourced` is a legitimate, tracked grade
  meant to shrink visibly, never to be papered over.
- Objective record `work-docs/INTENT-SOURCE-PLAN-STEPS.md` — non_scope: no step deletion, no gate
  reduction, no TUNE value change, no evidence-free upgrade (including `*`).
- Memory `feedback_plan_validator_single_pass` — one validator pass; no pass 2 / Step 4.5.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Evidence bar | Scope | What counts as evidence to leave `unsourced`? | A citation+counterexample / B measured only / C judgement line | **A** | tightened by #7 | ADR-001 |
| 2 | Reclassification | Scope | Change the class when evidence contradicts it? | A change, never delete / B record only | **A** | TUNE excluded by #11 | ADR-002 |
| 3 | Cross-model | Testing depth | How far does the Codex check go? | A blind classification / B review final table / C none | **A** | made genuinely blind by #4 | ADR-003 |
| 4 | W1 blindness | Testing depth | Codex can read verdict-bearing files in the worktree | A revise / B accept risk / C reject | **A** | Codex runs first, from a curated bundle outside the repo; exposure voids it | ADR-003 |
| 5 | W2 ledgers | Testing depth | Codex cannot see base-only ledgers, so `**` collapses | A revise / B accept / C reject | **A** | bundle carries local aggregates; lower-grade rule only on shared evidence | ADR-003, ADR-005 |
| 6 | W3 reconciliation | Architecture | Class and grade reconciled independently | A revise / B accept / C reject | **A** | class first, then grade for that class; tie → `unsourced` | ADR-003 |
| 7 | W4 evidence bar | Scope | A template citation proves existence, not class | A revise / B accept / C reject | **A** | class-property citation types; falsifier; `**` needs population + n | ADR-001 |
| 8 | W5 close rule | Scope | Hypothesis 31.8 vs approved target 20 | A revise / B accept / C reject | **A** | close judged on the hypothesis; target stays open | ADR-005 |
| 9 | W6 durability | Contract | Bare ledger/memory paths are not durable | A revise / B accept / C reject | **A** | tracked excerpts + derivation + read commit | ADR-001 |
| 10 | W7 exit check | Testing depth | Prefix-count check is unsound | A revise / B accept / C reject | **A** | exact ordinal-set equality under a fixed heading | — |
| 11 | S1–S3 | Scope | TUNE out of scope; MATRIX:176 census; Phase 4 integrity check | A all / B accept / C reject | **A** | — | ADR-002 |
| — | Doc location | default | New RESEARCH doc vs append to Table 1 | — | new doc | Table 1 is a dated record | ADR-004 |
| — | Codex call path | default | invoker vs direct `codex exec` | — | direct, read-only | invoker forces findings schema and writes plan/review ledger rows | ADR-003 |
| — | Telemetry to Codex | default | May ledger rows go into the bundle? | — | aggregates only | non_negotiable "텔레메트리 100% 로컬" | ADR-005 |

## 📐 Architecture Decision Records

### ADR-001: Evidence bar — class-property citation plus falsifier
**Status:** Accepted (2026-09-18, via /hm:plan interview #1, tightened by #7 and #9)
**Context:** `*` is the cheapest grade. Citing the template line that implements a step proves only
that the step exists; every INV row could pass with "template line + no model retires a human
gate" and nothing learned — the Goodhart path the objective's non_scope forbids.
**Decision:** An entry leaves `unsourced` only when its row carries:
(a) a citation that supports the **class property**, by type —
  *INV-state*: the writer `file:line` **and** a reader in a later context (another stage, session
  or compaction) `file:line`;
  *INV-human-gate*: the `AskUserQuestion` / answer-gated block `file:line` and the decision it
  reserves to the operator;
  *INV-oracle*: the deterministic check `file:line` and what it would catch;
  *COMP*: the prose instruction `file:line` and a sourced claim that current models do it unprompted;
  *HOST*: the host's native capability, cited from vendor docs;
(b) a **falsifier** — a concrete observation that would show the class is wrong;
(c) for `**` only: a measured value that bears on that property, with population, `n` and
derivation. Otherwise the grade is `*`.
Every ledger or memory citation is stored as a **tracked excerpt** in the RESEARCH doc (Appendix
B): base-root absolute path, read date, base commit, the quoted fields (no session ids), and the
derivation. A bare path does not count.
**Consequences:**
- ✅ Every upgraded grade is checkable from a clone, and says why its class holds.
- ⚠️ Fewer entries may qualify → the objective can close `missed`; that is a valid result.
**Rejected alternatives:**
- Measured-only (`**`) — most steps have no ledger; the task would fail by construction.
- Any citation + one-line counterexample (draft 1) — proves existence, not class.
**Source:** Interview #1, #7, #9

### ADR-002: Reclassify on evidence, never delete; TUNE out of scope
**Status:** Accepted (2026-09-18, via /hm:plan interview #2, #11)
**Context:** 12 of the 13 are INV by inheritance; "how many COMP hide as INV" is an open unknown
in `.claude/intent.yaml`. A TUNE entry must carry `remeasure_on` + `measure_cmd`
(`step_sensitivity.py:471-472`), and the objective excludes TUNE value changes.
**Decision:** When the reconciled evidence supports a different class among INV / COMP / HOST,
change `cls` and record why. If the evidence points to TUNE, record the finding in the RESEARCH
doc and keep the current class with grade `unsourced`. Step prose, rendered output and gates are
not touched.
**Consequences:**
- ✅ The registry becomes a correct deletion map for a later task.
- ⚠️ A new COMP entry is a future deletion candidate; the deletion needs its own task.
**Rejected alternatives:**
- Record-only — leaves a known-wrong value in the source of truth.
- Allow TUNE with new measurement fields — collides with the objective's non_scope.
**Source:** Interview #2, #11

### ADR-003: Blind Codex first, then joint class-then-grade reconciliation
**Status:** Accepted (2026-09-18, via /hm:plan interview #3, #4, #5, #6)
**Context:** Draft 1 ran Codex after Claude wrote verdicts into the worktree it could read, and
reconciled class and grade independently, which can yield a grade for a class neither reading
supports; a tie defaulted to the inherited guess.
**Decision:**
1. **Order.** The Codex call happens in Phase 1, before any verdict is written.
2. **Bundle.** A directory made with `mktemp -d` **outside the repository** holds: the rendered
   plan command (`/home/noel/harness-maker/.claude/commands/hm/plan.md`), the modules the 13 steps
   call (`worktree.py`, `spec_need.py`, `review_churn.py`, `world.py`, `plan_rounds.py`), the
   aggregates file of ADR-005, and a brief with the class definitions, the ADR-001 bar and the 13
   ordinals. Excluded by name: `step_sensitivity.py`, `MATRIX-native-redundancy.md`,
   `RESEARCH-workflow-steps-vs-model-capability.md`, `RESEARCH-source-plan-steps.md`,
   `PLAN-source-plan-steps.md`, `CLAUDE.md`.
3. **Call.** `codex exec -s read-only -C <bundle> -o <out> - < <prompt>`, stdout+stderr to a log.
   Not `second_opinion_invoke` — its schema is review findings and its ledger rows are
   `stage: plan|review|health`, which this call is not.
4. **Exposure check.** `grep -E 'step_sensitivity|MATRIX-native|RESEARCH-(source-plan|workflow-steps)|PLAN-source-plan|CLAUDE\.md' <log>`;
   any hit voids the blind reading, which is then recorded as `void (exposure: <match>)` and the
   task proceeds Claude-only.
5. **Reconciliation, per step.** (i) Class: the side whose citation meets the ADR-001 (a) type for
   its class wins; both or neither → **tie → final grade `unsourced`**, both readings recorded.
   (ii) Grade: re-assess ADR-001 against the chosen class. When both sides graded the same class
   from the same evidence set (the bundle), take the lower grade; when Claude's grade rests on
   evidence outside the bundle, keep Claude's grade and name that evidence. (iii) One-line reason
   per row.
6. Codex unavailable → `codex: skipped (<reason>)`; proceed Claude-only.
**Consequences:**
- ✅ The second reading is independent and its independence is checked, not asserted.
- ✅ No final grade exists without support for the final class.
- ⚠️ No ledger row for this call; its record is RESEARCH Appendix A (prompt, manifest, raw output, exposure result).
**Rejected alternatives:**
- Codex after Claude, reading the worktree (draft 1) — anchored.
- Independent class/grade rules (draft 1) — can produce unsupported combinations.
**Source:** Interview #3, #4, #5, #6

### ADR-004: Evidence lives in a new RESEARCH doc
**Status:** Accepted (2026-09-18, via /hm:plan interview default)
**Context:** Table 1 of `RESEARCH-workflow-steps-vs-model-capability.md` is the dated 2026-09-12
record the other entries cite.
**Decision:** Write `work-docs/RESEARCH-source-plan-steps.md`; add a module constant
`_R_PLAN = "RESEARCH-source-plan-steps Table 2"` (the final-verdict table) and cite it as each
upgraded entry's `source`, as `_R_INTENT` is used.
**Consequences:**
- ✅ The old record stays as it was; provenance of each grade is explicit.
- ⚠️ Two RESEARCH docs now feed the registry.
**Rejected alternatives:**
- Append rows to the old Table 1 — silently rewrites a dated record.
**Source:** default

### ADR-005: Aggregates-only bundle; objective close judged on the hypothesis
**Status:** Accepted (2026-09-18, via /hm:plan interview #5, #8 + non_negotiable)
**Context:** Codex is an external service and `.claude/intent.yaml` non_negotiables require
telemetry to stay 100% local. Separately, the approved outcome target (20,
`INTENT-SOURCE-PLAN-STEPS.md` `approved_target`) is unreachable by this task: sourcing all 13
gives 31.8.
**Decision:** (1) The bundle carries only **locally computed aggregates** of ledgers (counts,
`n`, verdict distributions, date ranges) in one file; no raw rows, session ids, paths or free
text leave the machine. Claude's own evidence may quote rows in the tracked RESEARCH appendix,
which stays in the repo. (2) Phase 5 reports both numbers. The objective close at wrapup is
answered against the **hypothesis** (`≤31.8` ⇒ `met`, otherwise `missed`); the outcome target
20 stays open for later objectives on other stages, and the close note says so.
**Consequences:**
- ✅ No telemetry is transmitted; the lower-grade rule still has shared evidence to apply to.
- ✅ The close answer is defined before the work, not negotiated after it.
- ⚠️ Aggregates are coarser than rows; a `**` needing row-level detail rests on Claude's appendix only.
**Rejected alternatives:**
- Raw ledger excerpts in the bundle — violates the telemetry non_negotiable.
- Close on the outcome target — the task would be `missed` regardless of its result.
**Source:** Interview #5, #8; `.claude/intent.yaml` non_negotiables

## 🏗️ Technical Design

**Current state.** `REGISTRY` entries built with `_u(stage, ordinal, cls, inherits, note=…)` get
`grade="unsourced"` and `source="no RESEARCH row (2026-09-12); inherits <neighbour>"`
(`step_sensitivity.py:89-93`). The 13 plan entries: Step 0, 1.5, 1.7, 2, 3.0, 4.4, 4.9, 5, 6,
A, B, C, D (INV ×12, COMP ×1 = Step A). None carries a knob.

**Affected components.**
- `work-docs/RESEARCH-source-plan-steps.md` — new: method; `## Table 1 — Claude evidence`;
  `## Table 2 — Final verdicts`; `## Appendix A — Codex blind classification`;
  `## Appendix B — Evidence excerpts`.
- `src/harness_maker/step_sensitivity.py` — 13 entries `_u(...)` → `_e(..., grade, f"{_R_PLAN}; …")`
  where Table 2 upgrades them, possibly `cls`; new `_R_PLAN`; module docstring census if class
  counts move.
- `work-docs/MATRIX-native-redundancy.md` — plan appendix rows from `matrix_rows(REGISTRY)`; the
  prose census at line 176 (`(39 of 82)`, already stale vs 40/85).
- `CLAUDE.md` — `unsourced: 40` → new count (pinned by `test_step_sensitivity_registry.py:248`).

**Data flow.** bundle → Codex (Appendix A) ─┐
templates / code / base ledgers → Claude (Table 1, Appendix B) ─┴→ reconciliation (Table 2) →
registry → `matrix_rows` → MATRIX; `unsourced_count` → CLAUDE.md + MATRIX:176.

**API changes.** None. `StepEntry` is unchanged; `_R_PLAN` is module-private.

## 📝 Implementation Plan

### Phase 1 — Evidence bundle and blind Codex classification
- depends_on: []
- parallel_group: serial-1
- merge_hazards: none (new file; bundle lives outside the repo)
- Scope in: `mktemp -d` bundle per ADR-003 §2; `aggregates.md` computed locally from
  `/home/noel/harness-maker/.claude/observability/{stage-agents.jsonl,spec-need-*.jsonl,auto-advance.jsonl,stage-spans.jsonl}` (counts / n / distributions only, ADR-005); `BRIEF.md` (class definitions, ADR-001 bar, 13 ordinals, output table format `| ordinal | class | grade | citation | falsifier |`); the Codex call and exposure check (ADR-003 §3–4); create `RESEARCH-source-plan-steps.md` with **only** `## Appendix A` (prompt verbatim, bundle manifest with sha256 + base commit, raw response, exposure result). Scope out: any verdict of Claude's.
- Exit: `grep -c '^## Appendix A' work-docs/RESEARCH-source-plan-steps.md` = 1; Appendix A holds 13 Codex rows, or a `skipped` / `void` line with its reason; the exposure result line is present.
- Risk: medium (bundle completeness)
- Rollback: delete the file and the temp bundle

### Phase 2 — Claude's class-supporting evidence
- depends_on: [1]
- parallel_group: serial-2
- merge_hazards: RESEARCH doc (same file)
- Scope in: `## Table 1 — Claude evidence` with columns `ordinal | inherited class | proposed class | property type | citation(s) | falsifier | measured value (population, n) | grade`; `## Appendix B — Evidence excerpts` per ADR-001. Evidence from rendered plan command, `src/harness_maker/templates/stages/plan.md.j2`, the called modules, base-root ledgers, CLAUDE.md correction notes, memory.
- Exit: `uv run python -c "import re,sys;from harness_maker.step_sensitivity import REGISTRY as R;want={e.ordinal for e in R if e.stage=='plan' and e.grade=='unsourced'};t=open('work-docs/RESEARCH-source-plan-steps.md').read();sec=t.split('## Table 1 — Claude evidence')[1].split('\n## ')[0];got=[l.split('|')[1].strip() for l in sec.splitlines() if re.match(r'\| (Step|Phase|Check) ',l)];sys.exit(0 if sorted(got)==sorted(want) and len(got)==len(set(got))==13 else 1)"` exits 0 (run **before** Phase 4 changes the registry).
- Risk: medium (judgement quality)
- Rollback: Phase 1

### Phase 3 — Reconciliation
- depends_on: [2]
- parallel_group: serial-3
- merge_hazards: RESEARCH doc (same file)
- Scope in: `## Table 2 — Final verdicts` with columns `ordinal | Claude | Codex | final class | final grade | reason`, applying ADR-003 §5 and ADR-002 (TUNE → keep class, `unsourced`).
- Exit: the Phase 2 exit command with `'## Table 1 — Claude evidence'` replaced by `'## Table 2 — Final verdicts'` exits 0; every row has a non-empty reason cell.
- Risk: low
- Rollback: Phase 2

### Phase 4 — Registry and pinned docs
- depends_on: [3]
- parallel_group: serial-4
- merge_hazards: `CLAUDE.md` (shared with concurrent sessions — edit the one count only); `work-docs/MATRIX-native-redundancy.md`
- Scope in: `step_sensitivity.py` (13 entries per Table 2, `_R_PLAN`, census docstring if counts move); MATRIX plan appendix rows + line 176 census; CLAUDE.md count. Scope out: every non-plan entry; templates; snapshots.
- Exit: `uv run pytest tests/structural/test_step_sensitivity_registry.py tests/structural/test_instruction_preservation.py` passes; `uv run mypy --strict src/harness_maker/step_sensitivity.py` and `uv run ruff check src/harness_maker/step_sensitivity.py` clean; a one-shot check exits 0 that (a) the set of `| plan |` rows in MATRIX equals `{r for r in matrix_rows(REGISTRY) if r.startswith('| plan ')}` exactly, (b) every plan entry whose `source` starts with `_R_PLAN` matches its Table 2 final class and grade, and every Table 2 row graded `unsourced` is still `_u` in the registry, (c) MATRIX:176 names the current `unsourced_count` and total; `git diff --stat main -- src/harness_maker/templates tests/snapshot` is empty.
- Risk: low
- Rollback: Phase 3

### Phase 5 — Outcome check
- depends_on: [4]
- parallel_group: serial-5
- merge_hazards: none
- Scope in: `uv run hm world outcome measure unsourced_step_share --dry-run`; write into this PLAN's phase status the value, the hypothesis verdict (`≤31.8` ⇒ met), the outcome gap to 20, and the count left `unsourced` with reasons — the close answer for wrapup 5.7 per ADR-005. Scope out: recording.
- Exit: the dry-run prints `would_record` with a value, and the phase-status block contains all four items.
- Risk: low
- Rollback: none needed (read-only)

### Phase status (execute, 2026-09-18)

| Phase | Status | Notes |
|---|---|---|
| P1 | DONE | Bundle outside the repo (8 files, sha256 in RESEARCH Appendix A), aggregates only. First `codex exec` refused before any model call ("Not inside a trusted directory") → re-run with `--skip-git-repo-check`. 13 rows returned. **Deviation (ADR-003 §4):** the literal log grep matched 5 lines, all `CLAUDE.md` text *inside bundled files* that Codex printed; the 18 executed commands all ran in the bundle against bundled files, so the reading was judged VALID on executed commands, not on content matches. Recorded in Appendix A for review. |
| P2 | DONE | Table 1 + Appendix B; exit check exact 13-ordinal set passed before the registry changed. |
| P3 | DONE (corrected post-review) | First version: Codex+Claude reconciliation with Step 0 INV → COMP. After review: Claude-only (Codex void), Step 0 stays INV. 10 sourced (`*`), 3 unsourced (Step 0, 6, A), no `**`, no class change. |
| P4 | DONE | Registry, MATRIX 11 rows + census, CLAUDE.md. ruff/format/mypy clean; `test_step_sensitivity_registry.py` + `test_instruction_preservation.py` 63 passed; integrity (a)(b)(c) pass; no template/snapshot diff. **Deviation (exit (b) wording):** the three researched-but-unsourced entries are `_e(..., "unsourced", f"{_R_PLAN}; …")`, not `_u` — `_u` writes "no RESEARCH row; inherits …", which is now false for them; the module docstring, MATRIX legend and CLAUDE.md now define `unsourced` as "no evidence meeting the bar — inherited, or researched and none found". Check (b) was run as "class, grade and `_R_PLAN` source match Table 2" for all 13. CLAUDE.md therefore changed one definition line, not only the count. |
| P5 | DONE | `hm world outcome measure unsourced_step_share --dry-run` → `would_record 35.3`. **Hypothesis (≤31.8): MISSED** — 10 of 13 sourced (40 → 30 of 85). Outcome target 20: gap 15.3, open. Left unsourced with reasons: Step 0 (COMP, no capability source), Step 6 (tie, model-executed checks), Step A (COMP, no evidence; origin is operator comprehension). **Close answer for wrapup 5.7 per ADR-005: `missed`**, note naming the three and the Step 6 fail-open finding. |

**Post-review correction (operator-directed, 2026-09-18).** `/hm:review` accepted two P2s against
the P1/P3 deviations above: the exposure rule was reinterpreted after it fired (`a8aad0464067647c`,
design + security + codex) and Step 0's COMP class was unsupported (`55225187cb8d174d`,
consistency + codex). Both were corrected: the Codex reading is **VOID** per ADR-003 §4 as written
and Table 2 is a Claude-only reconciliation (ADR-003 §6); Step 0 returns to INV / `unsourced`
(ADR-002: a class changes only when the new class is supported). Result unchanged: 10 of 13
sourced, 35.3 — hypothesis **missed**; class changes 0. The P1 deviation note in P1's row stands as
history. The recorded vocabulary grep was also corrected (P3 `62ce65309e216afb`).

**Phase A–B / A.5 / C.0 / D.5.** No new test: PLAN §Testing Strategy declares none (registry data
and documents only; the permanent binding is the existing `test_docs_carry_classes`). Phase A–B
and A.5 therefore did not run (ledger row `dispatch-skipped`); C.0/D.5 not triggered — no defect
repair.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/` — render output must stay byte-identical (non_scope: no step deletion or gate reduction)
- `tests/snapshot/` — no snapshot regeneration
- `work-docs/RESEARCH-workflow-steps-vs-model-capability.md` — dated record (ADR-004)
- `specs/SPEC-workflow-steps-vs-model-capability.md` — no AC changes
- Advisory: no entry outside `stage == "plan"` changes grade, class or source
- Advisory: no entry gains or changes `remeasure_on` / `measure_cmd` (TUNE out of scope, ADR-002)
- Advisory: no raw ledger row, session id or local path is sent to Codex (ADR-005)

## 🧪 Testing Strategy

- **Structural:** existing `tests/structural/test_step_sensitivity_registry.py` (coverage, orphans, Side ordering, docs-carry-classes incl. the CLAUDE.md count and MATRIX rows) and `test_instruction_preservation.py`.
- **One-shot integrity checks** (Phase 2/3/4 exits): exact ordinal coverage of both tables, MATRIX plan rows == registry rows, registry ↔ Table 2 agreement, MATRIX:176 census. Not added to the suite: they bind a one-time document to the registry; the permanent binding is `test_docs_carry_classes`.
- **Manual:** read each Table 2 row against ADR-001; `/hm:review` Step 3.3 checks the diff against the objective.
- **Outcome:** Phase 5 dry-run.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Citations restate the step instead of supporting its class | medium | high (Goodhart) | ADR-001 property types + falsifier; blind Codex; tie → `unsourced` |
| Codex reads an excluded file via an absolute path | low | medium | ADR-003 §4 log grep voids the reading |
| Bundle omits evidence Codex needed → spurious disagreements | medium | low | disagreements resolve on citations; reason recorded per row |
| Telemetry leaves the machine | low | high | ADR-005 aggregates-only; Contract Boundaries advisory |
| CLAUDE.md edited concurrently by another session | low | low | one-token edit; `task-refresh` before land |
| Fewer than 13 sourced → objective `missed` | medium | low | valid outcome under ADR-005; reasons recorded |

## ✅ Success Criteria

- [x] Appendix A: blind Codex table (or skip/void with reason) + exposure result, written before any Claude verdict
- [x] Table 1 + Appendix B: 13 rows, each upgraded row with a class-property citation, falsifier and tracked excerpts
- [x] Table 2: 13 rows, reconciled per ADR-003 §5 with reasons
- [x] Registry, MATRIX rows + census, CLAUDE.md count agree; structural tests, mypy, ruff clean
- [x] Render output unchanged (no template or snapshot diff)
- [x] Phase 5 reports value, hypothesis verdict, gap to 20, leftovers

## 🔍 Plan Validation

**Pass 1 (terminal — single pass per user feedback `feedback_plan_validator_single_pass`):**
`NEEDS_REVISION` — 7 warnings, 3 suggestions. Codex second opinion `invoked`: 8 findings, all
reconciled `accepted` by the validator (c1→W4, c2→W1, c3→W5, c4→S1, c5→W3, c6→W6, c7→S2, c8→W7).
`plan_rounds plan` scheduled all 10 as rounds, none skipped.

| Critique | Resolution | Round |
|---|---|---|
| W1 Codex not blind | ADR-003 §1–4: Codex first, bundle outside repo, exposure check | #4 |
| W2 `**` unreachable for Codex | ADR-003 §5(ii) shared-evidence rule; ADR-005 aggregates | #5 |
| W3 independent class/grade | ADR-003 §5: class first, grade for that class, tie → `unsourced` | #6 |
| W4 citation proves existence | ADR-001 (a) property types, (b) falsifier, (c) `**` with population + n | #7 |
| W5 31.8 vs 20 | ADR-005 (2) close on hypothesis; Phase 5 reports both | #8 |
| W6 durability | ADR-001 tracked excerpts (Appendix B) | #9 |
| W7 exit check | Phase 2/3 exact ordinal-set equality under fixed headings | #10 |
| S1 TUNE | ADR-002: out of scope | #11 |
| S2 MATRIX:176 | Phase 4 scope + exit (c) | #11 |
| S3 integrity | Phase 4 exit (a)(b) | #11 |

No pass 2 and no Step 4.5 terminal re-validation (user feedback). The revisions themselves are
therefore unvalidated; `/hm:execute` Phase A.5 and `/hm:review` carry that risk.
