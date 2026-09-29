---
type: plan
task_slug: top-issues-2026-09
status: complete
created: 2026-09-30
tags: [harness-maker, plan, python, review-loop, verification-cache, context-lint]
spec: "[[SPEC-top-issues-2026-09]]"
research_doc: "[[RESEARCH-top-issues-2026-09]]"
interview_rounds: 0
adrs: 5
validator_outcome: NOT_RUN
summary: "Deterministic caused_by stamping, self-running verification marker, CLAUDE.md char budget + relocation"
spec_need_verdict: add
spec_need_target: top-issues-2026-09
---

# PLAN — top-issues-2026-09

## 🎯 Executive Summary

This PLAN implements the three slices of [[SPEC-top-issues-2026-09]]:

1. **`review_churn attribute` / `fix-defect-rate`.** A deterministic `caused_by` stamp is written
   before the review payload is persisted, and the review loop and the gate skill read that stamp.
2. **`verification_cache run`.** One verb runs the CI-derived primary gates and writes a
   provenance-stamped marker only on success. Verify and wrapup call that verb instead of the
   three-step check → LLM run → `mark-pass` prose.
3. **A character budget for CLAUDE.md/AGENTS.md** in `context_lint` and readiness. This repo's
   CLAUDE.md is relocated under 40,000 characters, and relocated text is kept verbatim in
   `docs/reference/`.

Decisions come from the SPEC, which the user approved through the explicit instruction
"추천안대로 wrapup 까지 진행, 묻지 말 것" ("proceed with the recommendation through wrapup,
don't ask"). The reversible design calls are the ADRs below.

## 📚 Prior Work

- [[PLAN-token-efficiency-autopilot-ux-speed]] ADR-004 kept the lint unit in lines. It named
  character density as "a meter defect worth a separate unit"; this is that unit, and it adds a
  character dimension without replacing lines.
- [[PLAN-render-observability-audit]] ADR-004 chose **relocate** as the CLAUDE.md size method,
  on the grounds that narratives are the recorded *why*. The same method is followed here.
- failures.md, three entries:
  - `fix-introduced-defect-passes-all-gates` (count:17) is the motivation for slice 1.
  - `assertion-invariant-over-named-dimension` (count:22): every test here must fail when its
    owning code is removed.
  - `snapshot-regen-inside-worktree` (count:14): regenerate inside the worktree and verify with
    absolute paths.
- The spec-validator pass (MAJOR_REVISION, 12 findings) was folded into the SPEC before approval.

## 📐 Architecture Decision Records

### ADR-001: Attribution reads new-side hunks from `git diff -U0`
**Decided by:** agent
The coordinate system is fixed by the SPEC. `-U0` gives exact changed ranges with no context
lines, so a ±3 tolerance is applied explicitly instead of relying on context width.
`review_churn._git` and the pinned refs are reused; no new git plumbing is added.

### ADR-002: Carried ids come from the persisted payload store, not from REVIEW prose
**Decided by:** agent
Carried ids are read from `<base>/.claude/observability/review-payloads/<safe slug>/<safe run-id>-round<k>-merged.json`,
using the same `_safe_component` sanitiser as `persist_payload`. The base root is resolved the
way `stage_agent_ledger` resolves it, so the lookup works from a worktree.

### ADR-003: The `run` marker carries provenance; `check` stays for legacy readers
**Decided by:** agent
`mark_passed` gains optional `writer` / `commands` keyword arguments.
- `run` writes `writer="run"` and `commands_sha256`.
- `is_fresh` is unchanged, so `check` and old harnesses keep working.
- `run` uses a stricter `_is_run_fresh`.

### ADR-004: Character budget folds into the existing readiness signal
**Decided by:** user (source: SPEC Refinement Decisions)
There is no new signal, so structural weights and dashboards do not move.

### ADR-005: Relocated CLAUDE.md text goes to `docs/reference/claude-md-*.md`, one file per section
**Decided by:** agent
Each moved section leaves a 2–4 line summary and a link in CLAUDE.md. Test-pinned sections
(`릴리스 절차`, `Context discipline`, `Step sensitivity classes`) stay in CLAUDE.md.

## 🏗️ Technical Design

**Before:**
- `review.md.j2` Step 3.4 runs stamp-ids, then persist-payload. The auto-fix step 1 has the LLM
  derive `caused_by` into REVIEW markdown only.
- verify/wrapup run `check`; the LLM then runs the commands and calls `mark-pass`.
- `context_lint` counts lines only.

**After:**
- **Review payloads.** Step 3.4 runs stamp-ids, then `review_churn attribute --findings-file X
  --run-id R --round N`, then `persist-payload --file X`. Auto-fix step 1 and skill §5 read the
  stamp.
- **Verify/wrapup.** The stage calls `verification_cache run` and branches on exit 0/1/3/4.
  Exit 3 falls back to the prose path, which keeps `mark-pass`.
- **Context lint.** `CHAR_THRESHOLDS` covers `(CLAUDE.md|AGENTS.md, preset)`. `lint` returns a
  line warning and/or a character warning. Readiness ANDs in the character check.

## 📝 Implementation Plan

### Phase 1 — `review_churn attribute` + `fix-defect-rate`
- depends_on: none · parallel_group: A · merge_hazards: none
- scope in: `src/harness_maker/review_churn.py`, `src/harness_maker/command_registry.py` (verb registration, added at execute), `tests/unit/test_review_churn_attribute.py`; out: templates
- exit: `uv run pytest tests/unit/test_review_churn_attribute.py tests/unit/test_review_churn_measure.py -p no:randomly`
- risk: medium · rollback: revert the two files

### Phase 2 — Review template + gate skill read the stamp
- depends_on: [1] · parallel_group: B · merge_hazards: render snapshots and the surface baseline (resolved in Phase 6)
- scope in: `templates/stages/review.md.j2`, `templates/skills/second-opinion-gate/SKILL.md.j2`, `tests/render/test_render_review_attribution.py`
- exit: `uv run pytest tests/render/test_render_review_attribution.py`
- risk: medium · rollback: revert the templates

### Phase 3 — `verification_cache run` + verify/wrapup templates
- depends_on: none · parallel_group: A · merge_hazards: render snapshots and the surface baseline (Phase 6)
- scope in: `src/harness_maker/observability/verification_cache.py`, `templates/stages/verify.md.j2`, `templates/stages/wrapup.md.j2` (verification step only), `tests/unit/test_verification_cache_run.py`, `tests/render/test_render_verification_run.py`
- exit: `uv run pytest tests/unit/test_verification_cache_run.py tests/unit/test_verification_cache.py tests/render/test_render_verification_run.py`
- risk: medium · rollback: revert

### Phase 4 — Character budget in `context_lint` + readiness
- depends_on: none · parallel_group: A · merge_hazards: none
- scope in: `src/harness_maker/context_lint.py`, `src/harness_maker/readiness.py`, `tests/unit/test_context_lint_chars.py`
- exit: `uv run pytest tests/unit/test_context_lint_chars.py tests/unit/test_context_lint.py -k 'not repo_claude_md'`
- risk: low · rollback: revert

### Phase 5 — Relocate this repo's CLAUDE.md
- depends_on: [4] · parallel_group: C · merge_hazards: tests that read CLAUDE.md sections
- scope in: `CLAUDE.md`, `docs/reference/*.md` (relocated snapshots), `src/harness_maker/documentation_contract.py` + `tests/structural/test_documented_commands_exist.py` (historical classification, added at execute), `tests/unit/test_claude_md_relocation.py`
- exit: `uv run pytest tests/unit/test_context_lint_chars.py tests/unit/test_claude_md_relocation.py tests/structural/test_step_sensitivity_registry.py tests/render/test_render_context_discipline.py tests/unit/test_second_opinion_no_stale_names.py`
- risk: medium · rollback: `git checkout CLAUDE.md`, then delete the new docs

### Phase 6 — Regenerate derived baselines + full suite
- depends_on: [2, 3, 5] · parallel_group: D · merge_hazards: snapshot and surface files
- scope in: `tests/snapshot/**`, `tests/structural/surface_baseline.json`, any golden the changed templates move
- exit: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src tests && uv run pytest -x -n auto --dist loadfile`
- risk: medium · rollback: re-run the regeneration

### Execution notes

- **A.5 batching (deviation):** a single test-reviewer dispatch per round covered all five
  Python/render phases, because their test files are disjoint. This cost 2 rounds instead of 10.
- **A.5 exhausted (blocked phase → stuck → Path B):**
  - Round 1 FAIL: 6 blocking findings, all fixed.
  - Round 2 FAIL: 2 blocking findings.
    - `test_cached_only_for_own_marker` could not isolate writer from command hash.
    - Arm (b) was a presence-only check.
  - `stuck` recommended Path B: edit each test so that one dimension moves at a time, then go to
    Phase C without a third A.5 round. The user's standing instruction ("묻지 말고 추천안대로
    진행", "proceed with the recommended plan without asking") authorised taking the
    recommendation.
  - Both findings were addressed, but A.5 did not re-review them. **/hm:review must check
    `test_cached_only_for_own_marker` and `test_caused_by_single_owner`.**
- **SPEC fixture correction (re-approved):** under the ±3 tolerance, S1's first fixture could not
  distinguish an old-side implementation from a new-side one. It now uses a ten-line insertion.
- **Phase 5:** the relocated snapshots were added to `HISTORICAL_DOC_FILES` and to
  `test_documented_commands_exist._HISTORICAL_RECORD`. They are verbatim dated text and still
  name `/hm:plan` and plan-validator as they stood when written.
- **Phase 6:**
  - Aggregate surface **fell**: claude 357,790 → 357,552, codex 312,039 → 311,672 after the
    new prose was trimmed.
  - The round-trip table was updated: review 35, verify 13, wrapup 33.
  - The autopilot golden was re-captured. Only review, verify and wrapup moved, in all four arms.
  - `BASELINE-DELTA-top-issues-2026-09.md` was written.
- **Rendered default:** `persist-payload` renders only with `instrumentation.stage_agent_ledger`,
  so the binding test renders with the ledger on. `attribute` renders unconditionally, because
  the auto-fix loop reads the stamp.

### Stage exit (execute)
- **Boundary comparison.** 40 changed paths, and none crosses the `Do not change` entries
  (`stage_agent_ledger.py`, `conditional_router.py`). Both advisory boundaries held:
  `is_fresh` / `compute_relevant_skip_key` are unchanged, and the confirm-pass flow is untouched.
- **Out-of-scope edits (reported):**
  - `command_registry.py`: registers the new verbs.
  - `documentation_contract.py`: classifies the relocated snapshots as historical.
  - Derived baselines and pinned tests: surface baseline, autopilot golden, snapshots,
    round-trip table, instruction allowlist, wrapup line pin, pinned grammar tests.

## 🚧 Contract Boundaries

### Do not change
- Advisory: in `verification_cache.py`, `compute_relevant_skip_key` and `is_fresh` semantics stay as they are (SPEC non-goal; `check` readers).
- `src/harness_maker/stage_agent_ledger.py` — `persist_payload` path and naming.
- `src/harness_maker/conditional_router.py` — review control flow and lens dispatch.
- Advisory: confirmation-pass flow in review.md.j2 (Step C1–C3) is untouched.

## 🧪 Testing Strategy

- **Unit:** real git fixture repos for attribute; stub gate commands (python -c scripts) through
  a fake `.github/workflows/ci.yml` for `run`; synthetic CLAUDE.md fixtures for lint.
- **Render:** render both claude and codex variants and extract the Step 3.4 block and the
  verify/wrapup verification blocks.
- **Differential:** AC-016 compares against `git show 3b718d91:CLAUDE.md`.
- **Full suite:** once at the end (Phase 6).

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Surface baseline and snapshots red after template edits | Phase 6 regenerates in the worktree, then runs the structural suite |
| `run` exceeds the 600 s Bash cap | per-command 540 s timeout; the template documents host-kill handling |
| CLAUDE.md relocation loses a rule | AC-016 differential test; pinned sections stay |
| Tests pinning review/verify prose break | grep tests for changed phrases before editing |

## ✅ Success Criteria

- [x] AC-001..AC-005, AC-014 (Phase 1): 30 passed
- [x] AC-006, AC-015 (Phase 2): 5 passed
- [x] AC-007..AC-010 (Phase 3): 57 passed plus render 5 passed
- [x] AC-011, AC-012 (Phase 4)
- [x] AC-013, AC-016 (Phase 5): CLAUDE.md 49,770 → 20,603 chars
- [x] Full lint/type/test green (Phase 6): ruff, format and mypy clean. pytest reported 9,721 passed with 3 baseline-only failures, which were re-frozen and then passed (structural 799 passed).

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| intent status 2026-09-30 (no intent covers these slices) | none | unchanged | no intent link | agent | SPEC Step 0.5 default | continue task |
| wrapup 5.7, 2026-09-30 (the user said verbatim "나에게 묻지말고 진행해" / "proceed without asking me") | open questions and metrics | declined: not asked | no question observed, no metric measured, no intent close (the PLAN has no intent link) | user | answer-gated steps are never written without an answer | the next /hm:wrapup or `hm intent metric measure --all`, when the DRI asks |
| trial `world-intent-closed-loop-trial` status `collect_missing_evidence` (source is a removed worktree) | trial | pending | needs a user source-review decision; none inferred | user | pending decision | surface at wrapup |
