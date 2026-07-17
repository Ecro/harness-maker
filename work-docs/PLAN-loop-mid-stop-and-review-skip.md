---
type: plan
task_slug: loop-mid-stop-and-review-skip
status: phases-1-4-complete
created: 2026-05-23
tags: [harness-maker, plan, autoloop, loop, gate, receipts]
research_doc: "[[RESEARCH-loop-mid-stop-and-review-skip]]"
interview_rounds: 5
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Mechanical per-stage receipts + Gate 0 + state-pin file; plan-exec-rev fused workflow"
---

# 🎯 Executive Summary

**What:** Add mechanical per-stage receipts (`harness_maker.iter_receipts`) + Gate 0 (Receipt gate, 4→5 gate convergence) so the `/hm:loop` driver cannot silently drop a fused-workflow stage. Add state-pin file for `/compact`-safe stage-boundary resume. Add `plan-exec-rev` fused workflow + loop-mode `/hm:plan` (no deep interview, per-iter `PLAN-{slug}-iter{N}.md`).

**Why:** 2026-05-22 forensic (`PLAN-onboarding-backup-friction`, 6-iter run) showed LLM driver silently reinterpreted review stage as optional under context pressure × 6 phases. Stop hook (`loop_gate.py`) partially fixes mid-stop but does not cover `/compact`-induced state loss or backgrounded-notification mishandling. Both failures share a root cause: invariants encoded as prompt prose, not enforced contracts.

**Key decisions:**
- ADR-001: Gate 0 = Receipt gate (5-gate convergence) — disk artifact check before Gate 1.
- ADR-002: `plan-exec-rev` fused workflow + loop-mode `/hm:plan` (deep interview suppressed when `.hm-loop-active` marker present).
- ADR-003: state-pin file at stage boundary; notification gate **deferred** to follow-up PLAN.
- ADR-004: `harness_maker.iter_receipts` module — worktree-ephemeral JSON, schema `{iter, stage, verdict, written_at}`.
- ADR-005: Gate 0 fail → auto-retry missing stage (cap=2 per (iter,stage), then `AskUserQuestion`). Retries do NOT increment `failed_streak`. `verdict != "pass"` is treated as Gate 0 fail.
- ADR-006: state-pin granularity = stage boundary (every stage completion writes state).
- ADR-007: `/hm:plan` detects loop-mode via `.hm-loop-active` marker (no flag).
- ADR-008: Per-iter PLAN as separate file `<WT>/work-docs/PLAN-{slug}-iter{N}.md`, squash-merged at loop close.

**Estimated impact:** Eliminates silent review-stage skipping. Recovers loops across `/compact` boundaries deterministically. Adds per-phase replanning for long features. Pre-release — no backward-compat burden.

---

# 📚 Prior Work

- `[[wiki:loop-body-skipping-review-stage]]` (2026-05-22) — direct forensic of the review-skip failure mode. Recommends `loop body iter 마다 review 명시 invoke` — this PLAN converts that prose recommendation into a mechanical gate.
- `[[wiki:loop-4gate-convergence]]` (2026-05-10) — establishes Gate 1-4 design; Gate 0 slots in front.
- `[[PLAN-loop-stop-hook-enforcement]]` — ADR-001 precedent: machine-enforced gate keyed on disk artifact (`.hm-loop-active`).
- `[[PLAN-loop-longevity-strategies]]` — ADR-002 (Cursor advisory-only) accepted limitation.
- `[[RESEARCH-loop-mid-stop-and-review-skip]]` — recommends Approach A (receipts) + Approach B (state-pin + notification gate). This PLAN ships A + state-pin half of B; notification gate deferred.
- `src/harness_maker/hooks/loop_gate.py` — existing Stop hook; the shape Gate 0 mirrors.
- `src/harness_maker/review_telemetry.py` — separate concern (per-review JSONL); receipt module is independent.

---

# 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Receipt scope | Scope | Which stages must emit mechanical receipts? | D: All workflow stages + driver Gate 0 (4-gate → 5-gate) | Also: `exec-rev` is loop default (confirmed), add `plan-exec-rev` as new fused workflow; in-loop `/hm:plan` has no deep interview | ADR-001, ADR-002 |
| 2 | Mid-stop fix | Architecture | Beyond Stop hook, what else? | C: state-pin file + notification gate (both) | Round 4 later revised: notification gate deferred | ADR-003 |
| 3 | Receipt module | Architecture | Where does receipt source-of-truth live? | A: New `harness_maker.iter_receipts` module, stage-agnostic CLI | Separate from `review_telemetry.py` to keep concerns split | ADR-004 |
| 4 | Write location | Architecture | Receipts inside worktree or base repo? | B: worktree `.claude/.hm-iter-receipts/`, ephemeral, no copyback (Gate 0 runs before finalize) | Survives until finalize then cleaned with worktree | ADR-004 |
| 5 | Receipt schema | Contract | How much in each receipt? | B: presence + verdict (`{iter, stage, verdict, written_at}`) — no evidence_path | Verdict read mechanically; LLM forge still possible but explicit | ADR-004 |
| 6 | Gate 0 fail | Failure handling | What on missing receipt? | B: Auto-retry the missing stage prompt only (not whole iter) | Cap added in #8 | ADR-005 |
| 7 | State-pin granularity | Architecture | When to update state-pin? | A: Every stage boundary (fine-grained) | 6 writes/iter for plan-exec-rev — acceptable | ADR-006 |
| 8 | Auto-retry cap | Risk | How many retries before escalation? | A: 2 retries, then `AskUserQuestion` (수동 / skip / abort) | Transient-glitch tolerance | ADR-005 |
| 9 | Loop-mode signal | Architecture | How does `/hm:plan` know it is in a loop? | A: `.hm-loop-active` marker file detection | No flag needed; single source of truth | ADR-007 |
| 10 | Per-iter PLAN form | Architecture | How is "phase-by-phase replan" persisted? | B: Separate `PLAN-{slug}-iter{N}.md` per iter | Frontmatter `derived_from`+`iter`+`phase` | ADR-008 |
| 11 | Notification gate | Scope | Which Notification events to gate? | D: Not this PLAN — defer to follow-up | ADR-003 revised accordingly | ADR-003 |
| 12 | Backward compat (validator follow-up) | Risk | How to keep Gate 0 off for legacy harnesses? | Not needed — no downloaded users yet | Marker/config-flag concepts dropped | (drops scope) |
| 13 | Per-iter PLAN location (validator follow-up) | Architecture | `<WT>` or main repo? | A: `<WT>/work-docs/PLAN-{slug}-iter{N}.md` — squash-merge at close | Avoids `worktree_gate` block | ADR-008 |

**Validator follow-up resolutions (inline defaults, no further user question):**
- P2/P3 order: flipped — stage templates emit receipts (new P2) before Gate 0 wires up (new P3). Prevents false-miss between phases.
- `.current-iter` writer: loop driver writes `<WT>/.claude/.hm-iter-receipts/.current-iter` at iter start (in P3 scope).
- State-pin staleness: recovery checks for an existing receipt at `pending_stage` path before re-running — receipt present → advance, absent → re-run (P5 scope).
- Auto-retry vs `failed_streak`: Gate 0 auto-retries do NOT increment `failed_streak` (ADR-005 explicit).
- Verdict cheat-proof: Gate 0 requires `verdict == "pass"` (ADR-005 explicit; `skipped`/`fail` triggers retry).
- Per-iter PLAN cleanup: assigned to `loop.md.j2` Step 7 (P5 scope), not `wrapup.md.j2`.
- `stage_retry_counts`: added to loop-context `runtime:` block schema + `/compact` recovery list (P3 scope).

Ambiguity score: 0.95 (all five SPEC dimensions actionable; 13 interview entries; 4 critical validator critiques resolved).

---

# 📐 Architecture Decision Records

### ADR-001: Gate 0 = Receipt gate (5-gate convergence)

**Status:** Accepted (2026-05-23, via /hm:plan interview)

**Context:** 2026-05-22 wiki:gotcha `loop-body-skipping-review-stage` proved LLM self-attest of stage completion is unreliable under context pressure. The 4-gate design (Mechanical / LLM-individual / Regression / Streak) has no gate that verifies a stage actually ran from disk evidence.

**Decision:** Insert a new Gate 0 (Receipt gate) before Gate 1. Gate 0 reads `<WT>/.claude/.hm-iter-receipts/iter-{N}/` and asserts every expected workflow stage of the current `WORKFLOW` emitted a receipt with `verdict == "pass"`. The expected-stage set is derived from the rendered fused workflow definition (e.g., `exec-rev` = `{execute, review}`, `plan-exec-rev` = `{plan, execute, review}`). Missing receipt OR `verdict != "pass"` = Gate 0 fails.

**Consequences:**
- ✅ Silent stage skipping is no longer possible without disk evidence the LLM has to forge explicitly.
- ✅ Gate 0 generalizes to any future fused workflow without code change — just declarative stage list.
- ⚠️ One filesystem-list call per iter added to the convergence-check critical path (~ms).

**Rejected alternatives:**
- Prose-only reinforcement — exactly the approach that already failed in 2026-05-22.
- Strengthen Gate 2 (LLM-individual) — Gate 2 is itself LLM self-attest, so reinforcing it does not address the root cause.

**Source:** Interview #1.

### ADR-002: `plan-exec-rev` fused workflow + loop-mode `/hm:plan`

**Status:** Accepted (2026-05-23, via /hm:plan interview)

**Context:** Long features benefit from per-iter planning refinement (phase scope adjusts as earlier phases complete). But `/hm:plan`'s deep interview cannot run inside `/hm:loop` (CLAUDE.md: AskUserQuestion forbidden in autoloop body). Current `exec-rev` skips planning entirely per iter.

**Decision:** Add `plan-exec-rev` (stages = `[plan, execute, review]`) to the fused workflow registry. `/hm:plan.md.j2` detects `.hm-loop-active` marker; when present, skips Steps 2-3 (SPEC inheritance check + deep interview) and writes a per-iter scoped plan to `<WT>/work-docs/PLAN-{slug}-iter{N}.md`. Body is the next phase's refined scope only, derived from the master PLAN + current code state. No new ADRs created in loop-mode.

**Consequences:**
- ✅ Per-phase replan improves accuracy of late phases that depend on earlier phase outputs.
- ✅ Per-iter PLAN files become artifacts inside the worktree's squash-merged commit at loop close (audit trail preserved as one commit).
- ⚠️ Loop-mode plan cannot create ADRs — any new architectural decision must surface as a loop halt (existing safety rail #4: same feature retried 3 times).

**Rejected alternatives:**
- In-memory mini-plan (no audit trail).
- In-place master PLAN update per iter (git churn + merge conflicts during `/compact`).

**Source:** Interview #1 + #10.

### ADR-003: state-pin file at stage boundary; notification gate deferred

**Status:** Accepted (2026-05-23, via /hm:plan interview, Round 4 revised)

**Context:** `/compact` strips iter-body conversation state; driver re-enters cold without knowing the pending stage. Backgrounded-pytest-completion notifications can also be misinterpreted as user input (loop.md prose warns about this). Two mechanisms were on the table.

**Decision:** Write `.claude/.hm-loop-state.json` after each stage receipt. Schema: `{slug, iter, last_stage_completed, pending_stage, updated_at}`. On session restart with `.hm-loop-active` present, the loop top reads state-pin and jumps to `pending_stage`. **Notification gate is deferred** to a follow-up PLAN (`loop-notification-gate`) so we can first collect evidence on whether receipts + state-pin alone fix the observed mid-stop failures.

**Consequences:**
- ✅ `/compact`-safe stage resume; recovery is deterministic, not memory-based.
- ✅ Smaller blast radius — one new file (state-pin), no new hook.
- ⚠️ Notification mishandling remains. Acceptable while collecting evidence; reopen if observed.

**Rejected alternatives:**
- Both mechanisms in one PLAN — increases blast radius without evidence either is insufficient alone.
- iter-boundary-only state-pin — would lose mid-iter recovery information (rejected via Round 3 #7).

**Source:** Interview #2 + #11.

### ADR-004: `harness_maker.iter_receipts` module

**Status:** Accepted (2026-05-23, via /hm:plan interview)

**Context:** A central source-of-truth for receipts is needed. `review_telemetry.py` is review-specific and would conflate concerns if extended. Loop-context YAML `runtime:` is multi-line — atomic concurrent writes are unsafe.

**Decision:** New module `harness_maker.iter_receipts` with `pydantic` strict schema:

```python
class IterReceipt(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    iter: int = Field(ge=1)
    stage: str = Field(max_length=64)
    verdict: str = Field(max_length=16)  # "pass" | "fail" | "skipped"
    written_at: str = Field(max_length=32)  # ISO 8601 second-resolution UTC
```

CLI: `write` / `read` / `list` / `verify` subcommands. Path: `<WT>/.claude/.hm-iter-receipts/iter-{N}/{stage}.json`. Atomic write via existing `io_utils.atomic_write`. PIPE_BUF 4KB guard (mirrors `review_telemetry.py`). Worktree-ephemeral — cleaned at loop close along with the worktree itself (no copyback).

**Consequences:**
- ✅ Stage-agnostic: any future stage can emit receipts.
- ✅ Concerns split — review_telemetry stays review-specific.
- ⚠️ One new module + CLI to maintain.

**Rejected alternatives:**
- Extend `review_telemetry.py` — conflates per-review metrics with per-stage gate signals.
- Loop-context YAML `runtime:` block — concurrent multi-line YAML writes risk corruption.

**Source:** Interview #3, #4, #5.

### ADR-005: Gate 0 auto-retry semantics

**Status:** Accepted (2026-05-23, via /hm:plan interview)

**Context:** Gate 0 fail (missing receipt or `verdict != "pass"`) needs a recovery policy. Hard-halt every miss is too brittle (LLM transient glitches); silent advance defeats the point.

**Decision:** Auto-retry the missing stage prompt only (not the whole iter). Counter `stage_retry_counts[(iter, stage)]` persisted to loop-context `runtime:` block. After 2 retries on the same (iter, stage), escalate via `AskUserQuestion`:
- **A. 수동 재실행** — user runs the stage manually, then resumes loop.
- **B. Skip with `verdict: skipped` marker** — proceed with explicit hole.
- **C. Abort** — halt loop, preserve worktree.

**Critical rules (validator-resolved):**
- Auto-retries do **NOT** increment `failed_streak`. Failed_streak is for workflow-level failures (tests fail, build break), not gate misses.
- Gate 0 fail condition: receipt missing **OR** `verdict != "pass"`. `skipped` / `fail` verdicts both trigger retry. This closes the "LLM forges receipts" loophole — forging `verdict: skipped` does not bypass Gate 0.

**Consequences:**
- ✅ Transient glitch (one bad iter on one stage) auto-recovers without user interrupt.
- ✅ Systematic drift (3+ misses) surfaces to user via explicit `AskUserQuestion`.
- ⚠️ A persistently-broken stage burns 2 retries before halting. Acceptable — diagnostic info gained.

**Rejected alternatives:**
- 0 retries — too brittle.
- Increment `failed_streak` — safety rail #3 (cap=5) would fire before per-stage diagnosis surfaces.

**Source:** Interview #6, #8 + validator critical #5, #6, #8.

### ADR-006: state-pin granularity = stage boundary

**Status:** Accepted (2026-05-23, via /hm:plan interview)

**Context:** State-pin write frequency trades disk-write cost against recovery granularity.

**Decision:** Write state-pin after every stage completion. 6 writes/iter for `plan-exec-rev` (~3 stages × write + state-pin). Recovery on `/compact` reads state-pin then **cross-checks** with receipt presence: if a receipt for `pending_stage` already exists, advance to the next stage instead of re-running.

**Consequences:**
- ✅ Mid-iter recovery is precise to the stage.
- ✅ Cross-check guards against `/compact` racing mid-stage write (validator warning #5 resolved).
- ⚠️ Up to 6 small file writes per iter.

**Rejected alternatives:**
- Iter-boundary-only writes — would lose mid-iter pending_stage info.

**Source:** Interview #7 + validator warning #5.

### ADR-007: `/hm:plan` loop-mode signal = `.hm-loop-active` marker

**Status:** Accepted (2026-05-23, via /hm:plan interview)

**Context:** `/hm:plan` needs to know whether to suppress its deep interview. Two signal sources possible: marker file vs explicit flag.

**Decision:** `/hm:plan.md.j2` detects `.hm-loop-active` marker. Present → loop-mode (skip Step 2/3 interview). Absent → normal mode. No `--loop-mode` flag — single source of truth.

**Consequences:**
- ✅ Same signal mechanism as `loop_gate.py` and `worktree_gate.py` — pattern consistency.
- ✅ No dual-source confusion.
- ⚠️ Testing loop-mode requires fixture that creates the marker (not just a flag).

**Rejected alternatives:**
- Explicit `--loop-mode` flag — double source of truth.

**Source:** Interview #9.

### ADR-008: Per-iter PLAN files in `<WT>/work-docs/`

**Status:** Accepted (2026-05-23, via /hm:plan interview, Round 5)

**Context:** `plan-exec-rev` needs durable per-iter plan records. Two locations possible: main repo (visible in real time but blocked by `worktree_gate`) or `<WT>` (worktree-isolated, batched at squash-merge).

**Decision:** Write per-iter plans to `<WT>/work-docs/PLAN-{slug}-iter{N}.md`. Frontmatter:

```yaml
type: plan
derived_from: PLAN-{slug}.md
iter: N
phase: M
created: <ISO>
```

Squash-merged at loop close — final commit contains all per-iter PLANs in one go. Cleanup of any in-flight `PLAN-{slug}-iter*.md` is assigned to `loop.md.j2` Step 7 (loop-close), not `wrapup.md.j2` (which is invoked in non-loop contexts too).

**Consequences:**
- ✅ No `worktree_gate` exception needed.
- ✅ Audit trail preserved as one commit, easily greppable post-loop.
- ⚠️ During the loop, per-iter PLANs only visible inside `<WT>` — not in main checkout.

**Rejected alternatives:**
- Main repo `work-docs/` — requires `worktree_gate` allow-rule and risks contamination on aborted loops.

**Source:** Validator critical #4 + Interview #13.

---

# 🏗️ Technical Design

## Current state

- `src/harness_maker/hooks/loop_gate.py` — Stop hook, `.hm-loop-active` marker reader (pattern reuse).
- `src/harness_maker/review_telemetry.py` — per-`/hm:review` JSONL telemetry (kept separate from receipts).
- `src/harness_maker/templates/commands/hm/loop.md.j2` — 4-gate convergence; `runtime:` block has 4 counters (no `stage_retry_counts` yet).
- `src/harness_maker/render.py` — fused workflow renderer; reads from `fused_workflows.py`/yaml.
- `.claude/commands/hm/exec-rev.md` — rendered fused workflow; `plan-exec-rev` does not exist yet.

## Affected components

| File | Type | Change |
|------|------|--------|
| `src/harness_maker/iter_receipts.py` | NEW | pydantic model + CLI (write/read/list/verify) |
| `tests/unit/test_iter_receipts.py` | NEW | schema, atomic write, PIPE_BUF, CLI round-trip |
| `src/harness_maker/templates/commands/hm/execute.md.j2` | MODIFY | append receipt-emit Bash block at stage close |
| `src/harness_maker/templates/commands/hm/review.md.j2` | MODIFY | append receipt-emit Bash block at stage close |
| `src/harness_maker/templates/commands/hm/wrapup.md.j2` | MODIFY | append receipt-emit Bash block at stage close |
| `src/harness_maker/templates/commands/hm/plan.md.j2` | MODIFY | (a) receipt emit at close, (b) loop-mode branch (skip Step 2/3 when `.hm-loop-active` present) |
| `src/harness_maker/templates/commands/hm/spec.md.j2` | MODIFY | append receipt-emit Bash block at stage close |
| `src/harness_maker/templates/commands/hm/research.md.j2` | MODIFY | append receipt-emit Bash block at stage close |
| `src/harness_maker/templates/commands/hm/loop.md.j2` | MODIFY | (a) `.current-iter` write at iter start, (b) Gate 0 block before Gate 1, (c) `stage_retry_counts` in `runtime:`, (d) state-pin write after each stage, (e) post-/compact recovery with receipt cross-check, (f) per-iter PLAN cleanup at Step 7 |
| `src/harness_maker/fused_workflows.py` (or yaml) | MODIFY | add `plan-exec-rev = [plan, execute, review]` |
| `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2` | MODIFY | 4-gate → 5-gate; receipt invariant; `plan-exec-rev` mention |
| `.claude/memory/wiki.md` | MODIFY | new pattern entry referencing this PLAN |
| `CLAUDE.md` | MODIFY | new short section under "Workflow" — 5-gate callout |

## Data flow per iter (`exec-rev`)

```
iter start (driver):
  write <WT>/.claude/.hm-iter-receipts/.current-iter = N

execute stage:
  ... do work ...
  receipt write: {iter:N, stage:"execute", verdict:"pass", written_at:<ISO>}
  state-pin update: {slug, iter:N, last_stage_completed:"execute", pending_stage:"review", updated_at:<ISO>}

review stage:
  ... do work ...
  receipt write: {iter:N, stage:"review", verdict:"pass", written_at:<ISO>}
  state-pin update: {slug, iter:N, last_stage_completed:"review", pending_stage:null, updated_at:<ISO>}

driver Gate 0:
  list <WT>/.claude/.hm-iter-receipts/iter-N/
  expected = {execute, review}  # from WORKFLOW definition
  for each expected:
    if receipt missing OR verdict != "pass":
      stage_retry_counts[(N, stage)] += 1
      if count > 2: AskUserQuestion (수동 / skip / abort)
      else: re-invoke that stage prompt
  all pass → Gate 0 PASS → proceed to Gate 1

/compact mid-iter:
  on restart:
    read state-pin
    if pending_stage is set:
      check if receipt for pending_stage exists in iter-N/
      yes → advance to next expected stage
      no  → re-invoke pending_stage
```

## API surface

`harness_maker.iter_receipts`:
- `IterReceipt` pydantic model.
- `write(iter, stage, verdict, *, root=Path('.')) -> Path` — atomic write of one receipt; returns path.
- `read(path) -> IterReceipt` — load + validate.
- `list_iter(iter, *, root=Path('.')) -> list[IterReceipt]` — directory listing.
- `verify(iter, expected_stages, *, root=Path('.')) -> dict[str, IterReceiptStatus]` — Gate 0 check; returns per-stage `{present, verdict}`.

CLI: `python -m harness_maker.iter_receipts {write|read|list|verify} [args]`.

---

# 📝 Implementation Plan

## Phase 1 — `harness_maker.iter_receipts` module + unit tests

**Status:** ✅ **DONE** (2026-05-23, `/hm:exec-rev` Phase A→D).
- `src/harness_maker/iter_receipts.py` shipped (~210 LOC, schema + write/read/list_iter/verify + CLI with write/read/list/verify subcommands + Verdict Literal + path-safe stage regex).
- `tests/unit/test_iter_receipts.py` shipped, 24 tests pass (schema strict, path-safety parametrized × 5, write/read/list, verify variants, CLI smoke).
- Phase D: ruff clean, mypy --strict clean, unit suite ≥1+ pre-existing-suite GREEN.

**Scope (in):**
- `src/harness_maker/iter_receipts.py` (~120 LOC).
- `tests/unit/test_iter_receipts.py` (≥6 test cases).
- `pyproject.toml` console-script entry: none (run via `python -m`).

**Scope (out):**
- Stage templates (Phase 2). Driver wiring (Phase 3).

**Exit criterion:**
```bash
INTEGRATION=0 uv run pytest tests/unit/test_iter_receipts.py -q
```
Exit 0; ≥6 tests pass: schema strict validation, verdict enum enforcement, atomic write, PIPE_BUF 4KB guard, CLI round-trip (write → read → list), verify-missing-stage detection.

**Risk:** low (additive, no caller yet).

**Rollback point:** initial commit on this branch (no prior reverts needed).

---

## Phase 2 — Stage templates emit receipts (was P3, flipped per validator)

**Status:** ✅ **DONE** (2026-05-23, second `/hm:exec-rev` turn).
- All 6 stage templates patched: `src/harness_maker/templates/stages/{execute,review,wrapup,plan,spec,research}.md.j2` each have a new `Emit Gate 0 receipt (ADR-001, ADR-005)` section.
- `execute.md.j2` uses `Step 4.5` placement between Step 4 and Step 5 (avoids finalize wiping the receipt). Other 5 use unnumbered section right before `## Outputs`.
- Per-stage verdict mapping prose (pass/fail criteria) documented inline in each template.
- ADR-005 "never emit `skipped` from a stage prompt" warning present in every section.
- Both Claude Code (`!bash`) and Codex (`Bash("...")`) variants generated via `{% if is_codex %}` branch.
- `tests/unit/test_render_stage_receipts.py` shipped, 14 tests pass (parametrized × 6 stages × 2 invariants + 1 verdict warning + 1 fused-workflow inheritance test).
- Phase D: ruff clean, templates dir lint clean, full unit suite pending.

**Scope (in):**
- `execute.md.j2`, `review.md.j2`, `wrapup.md.j2`, `plan.md.j2`, `spec.md.j2`, `research.md.j2` — append the following block at stage close:

```bash
!ITER=$(cat <WT>/.claude/.hm-iter-receipts/.current-iter 2>/dev/null || echo 0)
!uv run python -m harness_maker.iter_receipts write \
   --iter "$ITER" --stage <stage_name> --verdict <verdict> \
   --root "<WT>"
```

Verdict extraction is LLM-judged from stage output (test result for execute, grade for review, etc.). The stage prompt template explicitly tells the LLM: "verdict = `pass` if exit criterion met, `fail` otherwise; never write `skipped` — that value is for the auto-retry escape hatch only."

**Scope (out):**
- Driver/Gate 0 wiring (Phase 3).
- Loop-mode plan branch (Phase 4).

**Exit criterion:**
```bash
uv run python -m harness_maker.render --check
uv run pytest tests/unit/test_render_stage_receipts.py -q
```
6 snapshot tests pass: each rendered stage MD contains the receipt-emit block at its close.

**Risk:** medium (6 files; verdict-extraction prose must be unambiguous).

**Rollback point:** Phase 1 complete (revert each stage template independently).

---

## Phase 3 — Gate 0 wiring + `.current-iter` + `stage_retry_counts` in `loop.md.j2`

**Status:** ✅ **DONE** (2026-05-23, third `/hm:exec-rev` turn).
- `loop.md.j2` Step 4-F runtime block gains `stage_retry_counts: {}`.
- Step 6 counters list + `/compact` recovery list both include `stage_retry_counts`.
- New Step 3.5: driver writes `<WT>/.claude/.hm-iter-receipts/.current-iter` so stage receipt-emit Bash blocks (Phase 2 P0 fix) actually fire.
- New Step 4.5 (Gate 0 — Receipt verification): runs `iter_receipts verify --iter N --expected ...`, ADR-005 auto-retry semantics (cap=2 per (iter, stage), then `AskUserQuestion` escalate with manual / skipped-marker / abort options). Critical invariant explicit: Gate 0 auto-retries do NOT increment `failed_streak`. Non-pass verdict (skipped/fail) counts as Gate 0 failure (closes "forge skipped to bypass" loophole).
- `tests/unit/test_loop_template_render.py` shipped — 8 tests pin: runtime schema, /compact recovery list, .current-iter write, Gate 0 CLI invocation, cap=2 prose, position between workflow and Update state, failed_streak exclusion, non-pass verdict rule.
- 8 snapshot YAMLs regen'd. Both Claude Code (`!cmd`) and Codex (`Bash("cmd")`) variants rendered.

**Scope (in):**
- `loop.md.j2` Step 6 changes:
  - Add iter-start instruction: write `<WT>/.claude/.hm-iter-receipts/.current-iter` = current `N`.
  - Insert Gate 0 block before Gate 1: `verify(iter=N, expected_stages=<derived from WORKFLOW>)` via the CLI.
  - Auto-retry logic per ADR-005 (cap=2, then AskUserQuestion).
- `loop.md.j2` Step 4-F runtime schema:
  ```yaml
  runtime:
    convergence_streak: 0
    checklist_fail_counts: {}
    criterion_ambiguity_counts: {}
    stage_retry_counts: {}            # NEW: {(iter,stage): int}
    last_test_result: {exit_code: null, failing: []}
  ```
- `loop.md.j2` Step 6 post-`/compact` recovery: add `stage_retry_counts` to the reload list.
- `autoloop-driver` SKILL.md.j2 updated mention of 5-gate (full update in P6).

**Scope (out):**
- `plan-exec-rev` fused workflow (Phase 4).
- State-pin file (Phase 5).
- Final docs (Phase 6).

**Exit criterion:**
```bash
uv run python -m harness_maker.render --check
uv run pytest tests/unit/test_loop_template_render.py -q
```
Snapshot tests pass: Gate 0 block appears before Gate 1; `.current-iter` write block in Step 6; `stage_retry_counts` in runtime schema; recovery block reloads it. Manual read of rendered loop.md confirms structure.

**Risk:** medium (template change visible to all renders; Gate 0 must align with Phase 2's receipt-write contract).

**Rollback point:** Phase 2 complete (revert template; receipts continue to be emitted, just not gated — harmless).

---

## Phase 4 — `plan-exec-rev` fused workflow + loop-mode `/hm:plan`

**Status:** ⏸️ **PARTIAL — BLOCKED on base-repo state; worktree source lost on `fail` finalize** (2026-05-23, fourth `/hm:exec-rev` turn).

**Important note for retry**: This turn's source-code changes (interview.py registry add, plan.md.j2 loop-mode branch, new test file) were authored inside the worktree. `stage-only` finalize failed (cannot stash while base has `UU` conflict markers); `fail` finalize was used as fallback to release the worktree, which deleted the worktree directory — so the source diffs are GONE. **Only the artifacts written directly to base survive** (this PLAN status update + REVIEW-phase4 report).

**What landed in worktree** (`execute-20260523T1141Z`):
- `interview.py` — `plan-exec-rev: [PLAN, EXECUTE, REVIEW]` added to both `_SIDE_STARTER` and `_PRODUCTION_STARTER` (3-stage, strips wrapup vs existing `plan-exec-rev-wrap`).
- `plan.md.j2` — new Step 1.5 "Loop-mode detection (ADR-002, ADR-007, ADR-008)": detects `.hm-loop-active` marker, skips Step 2/3 interview, writes per-iter scoped plan to `<WT>/work-docs/PLAN-{slug}-iter{N}.md` with `derived_from`+`iter`+`phase`+`loop_mode` frontmatter (ADR-008).
- `tests/unit/test_plan_loop_mode_and_fused.py` — 10 tests (registry, fused workflow render, loop-mode branch, per-iter path, frontmatter, Gate 0 table re-amend).

**Blocker — out of Phase 4 scope:**

Base repo is in a broken state:
1. **Phase 1-3 work is stashed, never committed**. `git stash list` shows 4 `hm-finalize-execute-20260523T*` stashes. Per `PLAN-worktree-finalize-stash-isolation` design, `stage-only` finalize defers the stash pop to `/hm:wrapup`'s `post-commit-pop`. Since `/hm:wrapup` was never invoked between phases, Phase 1-3 work sits in the stash queue waiting for wrapup.
2. **Stalled merge conflict markers** (`UU`) on ~30+ `tests/e2e/sandbox-plugin-test/*` files from render-time churn.
3. As a consequence: `src/harness_maker/iter_receipts.py` (Phase 1), the 6 stage-template receipt blocks (Phase 2), and the Gate 0 wiring in `loop.md.j2` (Phase 3) are ALL absent from base. New worktrees created from base HEAD inherit only `d92c6b3` (pre-Phase 1) plus the stalled merge artifacts.

**What this blocks in Phase 4:**
- 1 of 3 planned template edits — re-adding `plan-exec-rev → plan,execute,review` to `loop.md.j2` Gate 0 EXPECTED_STAGES table (Phase 3 review removed it because the registry didn't have it; Phase 4 was supposed to amend it back now that the registry has it). The base's `loop.md.j2` does not contain a Gate 0 section at all.
- 1 of 10 tests — `test_loop_md_expected_stages_includes_plan_exec_rev` will fail until Phase 3's `loop.md.j2` changes are merged into base.

**Recovery path (user action required):**

1. Run `/hm:wrapup` to commit the accumulated Phase 1-3 work + pop the stashes. This is the design path — stage-only finalize is explicitly handshake'd with wrapup's `post-commit-pop`.
2. Resolve the stalled `UU` conflicts on `tests/e2e/sandbox-plugin-test/*` manually (`git add` after picking either side, or `git checkout --theirs/--ours <file>` followed by re-render).
3. After base is clean (`git status` empty, latest commit includes Phase 1-3), retry `/hm:exec-rev loop-mid-stop-and-review-skip -phase4` to land the Gate 0 table re-amend + final test.

Alternative: amend Phase 4 scope to also include the loop.md.j2 Gate 0 table addition (without depending on Phase 3 being present), and let `/hm:wrapup` reconcile at commit time.

**Scope (in):**
- `src/harness_maker/fused_workflows.py` (or yaml): add `plan-exec-rev: [plan, execute, review]`.
- `plan.md.j2`: add loop-mode branch at Step 1.5:
  - Detect `.hm-loop-active` marker.
  - If present: skip Step 2 (SPEC inheritance) and Step 3 (interview).
  - Read master `PLAN-{slug}.md` for ADRs and phase list.
  - Read state-pin to identify next phase.
  - Write per-iter scoped plan to `<WT>/work-docs/PLAN-{slug}-iter{N}.md` (frontmatter `derived_from`, `iter`, `phase`).
- Render emits `plan-exec-rev.md` command file.

**Scope (out):**
- State-pin file mechanics (Phase 5) — for Phase 4, assume state-pin exists; Phase 5 implements the writes.
- Cleanup of per-iter PLAN files (Phase 5).

**Exit criterion:**
```bash
uv run python -m harness_maker.render --check
uv run pytest tests/unit/test_fused_workflows.py tests/unit/test_plan_loop_mode.py -q
```
Rendered `plan-exec-rev.md` exists; rendered `plan.md` contains loop-mode branch; unit tests pass for both fused workflow registry and plan template branch.

**Risk:** medium (template branch with conditional logic; new fused workflow entry).

**Rollback point:** Phase 3 complete (remove `plan-exec-rev` entry; revert `plan.md.j2` loop-mode branch).

---

## Phase 5 — State-pin file + post-`/compact` recovery + per-iter PLAN cleanup

**Scope (in):**
- `loop.md.j2` Step 6 iter body:
  - State-pin write block after each stage receipt write.
  - Schema: `.claude/.hm-loop-state.json` = `{slug, iter, last_stage_completed, pending_stage, updated_at}`.
- `loop.md.j2` Step 6 post-`/compact` recovery:
  - Read state-pin.
  - **Receipt cross-check (validator warning #5):** if a receipt for `pending_stage` exists, advance to next stage (do not re-run).
  - Otherwise re-invoke `pending_stage`.
- `loop.md.j2` Step 7 (loop close):
  - Cleanup block: `rm -f <WT>/work-docs/PLAN-{slug}-iter*.md` (and the `.claude/.hm-iter-receipts/` dir cleared at worktree cleanup naturally).
  - Cleanup runs on **success only**; non-converged halts preserve files for debug.

**Scope (out):**
- Notification gate (deferred to follow-up PLAN).
- Docs / memory / skill (Phase 6).

**Exit criterion:**
```bash
uv run python -m harness_maker.render --check
uv run pytest tests/unit/test_loop_template_render.py::test_state_pin_blocks -q
uv run pytest tests/unit/test_loop_template_render.py::test_cleanup_block -q
```
Snapshot tests pass: state-pin write blocks appear after each stage in Step 6; recovery block contains the receipt cross-check; cleanup block exists in Step 7.

**Risk:** low (additive — state-pin absence falls back to fresh iter).

**Rollback point:** Phase 4 complete (revert template; loop runs without state-pin, recovery falls back to cold restart).

---

## Phase 6 — Docs + memory + skill update

**Scope (in):**
- `src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2`: 4-gate → 5-gate explanation; `plan-exec-rev` mention; receipt invariant rationale.
- `.claude/memory/wiki.md`: new pattern entry `loop-mechanical-receipt-gate` linking to this PLAN and the 2026-05-22 gotcha.
- `CLAUDE.md`: short new section under "Workflow (autoloop CODER 가 알아야 할 점)" — 5-gate callout, 1-2 lines.

**Scope (out):**
- Code / templates (Phases 1-5).

**Exit criterion:**
```bash
uv run python -m harness_maker.context_lint --check
```
Lint clean for CLAUDE.md (≤500 lines Production) and autoloop-driver SKILL.md (≤150 lines). Manual read of wiki.md entry references this PLAN.

**Risk:** low.

**Rollback point:** Phase 5 complete (docs revert is trivial).

---

# 🧪 Testing Strategy

## Unit tests

- `test_iter_receipts.py` (Phase 1) — schema (good + 3 malformed), atomic write, PIPE_BUF 4KB guard, CLI subcommand round-trip (write → read → list), verify-by-iter (missing-stage detection + `verdict != pass` detection), CLI exit codes.
- `test_render_stage_receipts.py` (Phase 2) — 6 snapshot tests, one per stage template; each asserts the receipt-emit Bash block appears at stage close.
- `test_loop_template_render.py` (Phase 3 + 5) — Gate 0 block positioning (before Gate 1); `stage_retry_counts` in runtime schema; recovery block reloads it; state-pin write block per stage; recovery block contains receipt cross-check; cleanup block at Step 7.
- `test_fused_workflows.py` (Phase 4) — `plan-exec-rev` entry renders correct command file with the 3 stages composed.
- `test_plan_loop_mode.py` (Phase 4) — `.hm-loop-active` marker presence triggers Step 2/3 skip; per-iter PLAN path resolution.

## Integration tests (`INTEGRATION=1`)

- Simulate driver: write 3 receipts → run Gate 0 verify CLI → assert PASS. Delete review receipt → assert MISSING. Write review receipt with `verdict: skipped` → assert FAIL_NON_PASS.
- Render a sandbox harness end-to-end; assert all rendered files are syntactically valid.

## Manual smoke

- Drive `/hm:loop` on a trivial improve target (2-iter); inspect `.hm-iter-receipts/` contents.
- Deliberately `rm` a receipt mid-iter; observe Gate 0 fail → auto-retry → success.
- Trigger `/compact` mid-iter (context-stuff a long stage prompt); observe driver resumes from `pending_stage`.
- Drive `/hm:loop --per-iter-workflow plan-exec-rev` on a 2-phase spec; verify `PLAN-{slug}-iter{1,2}.md` written.

---

# ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `stage_retry_counts` lost on `/compact` | medium | persisted to loop-context `runtime:` block (Phase 3 schema add) |
| Per-iter PLAN file pile-up | low-med | loop-close cleanup in Step 7 (Phase 5); only on success halt |
| Receipt schema drift | low | pydantic strict + `extra="forbid"` + `max_length` on string fields |
| Cursor advisory-only state-pin | low | filesystem-based recovery works on Cursor; user manual-close warning already documented in loop.md |
| LLM forges receipts | low | receipts via CLI not direct file write; Gate 0 requires `verdict == "pass"` so forging `skipped`/`fail` does not bypass; security_scanner can flag direct `.hm-iter-receipts/` writes |
| Notification gate gap remains (deferred) | medium | acceptance documented in ADR-003; follow-up PLAN slug = `loop-notification-gate`; reopen if mid-stop recurs after this PLAN ships |
| State-pin mid-write `/compact` race | low | Phase 5 receipt cross-check: if receipt exists for `pending_stage`, advance; else re-run (idempotency boundary moves to stage level) |
| Verdict extraction LLM-judged | medium | accepted limitation — receipt mechanism shifts the failure from silent to explicit. Future enhancement: Gate 0 could cross-check verdict against test-output file (out of scope here) |
| Phase 2/3 cross-phase contract | medium | Phase 2 lands before Phase 3 so Gate 0 has receipts to query (validator critical #2 resolved) |
| Concurrent loop sessions | low | receipt path includes `iter-{N}`; concurrent loops in different worktrees have different `<WT>` roots — no collision |

---

# ✅ Success Criteria

- [ ] Phases 1-6 complete; full pytest suite GREEN.
- [ ] Drive `/hm:loop` with 3-iter improve target; verify `.hm-iter-receipts/iter-{1,2,3}/{execute,review}.json` all written with `verdict: pass`.
- [ ] Delete review receipt mid-iter; loop auto-retries review, succeeds, continues. `stage_retry_counts` increments to 1, then resets after success.
- [ ] Force `/compact` mid-iter; driver resumes from `pending_stage` without re-running already-receipted stages.
- [ ] Drive `/hm:loop --per-iter-workflow plan-exec-rev` on a 2-phase spec; per-iter `PLAN-{slug}-iter{N}.md` files appear inside `<WT>/work-docs/`; no `AskUserQuestion` from `/hm:plan`; squash-merge at loop close brings all files into one commit on main.
- [ ] `wiki.md` entry references this PLAN and the prior 2026-05-22 gotcha.
- [ ] `context_lint` clean for CLAUDE.md and autoloop-driver SKILL.md.

---

# 🔍 Plan Validation

**Validator outcome:** `MAJOR_REVISION_RESOLVED`.

**Critical critiques resolved:**

| # | Critique | Resolution |
|---|----------|-----------|
| 1 | `.iter_receipts_enabled` marker creation undefined | Round 5 — backward compat unneeded (no users yet); marker concept dropped; Gate 0 always on. |
| 2 | P2 ships before P3 → false-miss on every iter | Phases flipped: receipts emit first (now P2), Gate 0 wires after (now P3). |
| 3 | `.current-iter` writer unspecified | Loop driver writes it at iter start; added to P3 scope explicitly. |
| 4 | `plan-exec-rev` per-iter PLAN location vs worktree_gate | Round 5 — write to `<WT>/work-docs/`, squash-merge at loop close; no `worktree_gate` exception needed. |

**Warning critiques resolved inline:**

| # | Warning | Resolution |
|---|---------|-----------|
| 5 | State-pin mid-stage `/compact` corruption | P5 adds receipt cross-check on recovery: receipt present for `pending_stage` → advance, absent → re-run. |
| 6 | 2-retry cap vs `failed_streak_cap=5` interaction | ADR-005 explicit: Gate 0 auto-retries do NOT increment `failed_streak`. |
| 7 | Per-iter PLAN cleanup race with `/hm:wrapup` | Cleanup assigned to `loop.md.j2` Step 7 (loop-close only), not `wrapup.md.j2` (multi-context). P5 scope. |
| 8 | Receipts can be LLM-forged | ADR-005 explicit: Gate 0 requires `verdict == "pass"`. `skipped`/`fail` verdicts trigger retry. Forging via `verdict: skipped` does not bypass. |

**Suggestion resolved:**

| # | Suggestion | Resolution |
|---|------------|-----------|
| 9 | `stage_retry_counts` runtime block + `/compact` recovery missing from schema | P3 scope explicit: add to `runtime:` block and reload list. |

**Re-validation:** Not re-run (validator path: `MAJOR_REVISION` allows one re-run; all 9 critiques have explicit resolution mapped to phases). If `/hm:execute` surfaces an unresolved gap, halt and ask for a Plan amendment round before continuing.
