---
type: plan
task_slug: sdlc-three-loops-gap
status: complete
created: 2026-09-27
tags: [harness-maker, plan, python, memory, intent-layer, knowledge]
spec: "[[SPEC-sdlc-three-loops-gap]]"
research_doc: "[[RESEARCH-sdlc-three-loops-gap]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "Delete dead JSONL memory tier; add fact/question boundary to both skills within existing caps"
spec_need_verdict: add
spec_need_target: sdlc-three-loops-gap
---
# PLAN — sdlc-three-loops-gap

## 🎯 Executive Summary

Two changes from the approved SPEC: (1) delete `harness_maker.memory.{episodic,semantic,profile,retrieval}`
and their tests, keeping `_locking` (live, used by `memory_md`) and the legacy churn directory
entries; (2) put one locked boundary sentence into both the project-knowledge and intent-layer
skill templates, and rewrite project-knowledge's description and procedure so an intent-bearing
claim routes to intent-layer instead of `upsert-wiki`. Scope, IRR-001 and the accepted
`wiki_fact_entries_28d` window contamination come from the SPEC (DRI, Rounds 1–3).

## 📚 Prior Work

- RESEARCH-sdlc-three-loops-gap: census of knowledge stores; the JSONL tier has no live caller.
- SPEC-mission-context-loop: shipped project-knowledge; `tests/render/test_render_project_knowledge.py`
  pins its required tokens and a ≤ 250-char description containing "remember" and "correct".
- `tests/unit/test_render_intent_layer_assume_add.py::test_ac_011_*` caps the rendered intent-layer
  SKILL.md at ≤ 120 newlines — it renders at exactly 120 today.
- Memory: snapshot regeneration runs in the task worktree; pytest addopts already has `-q`; full
  suite runs in the background.

## 📐 Architecture Decision Records

### ADR-001: Fit the boundary sentence inside intent-layer's 120-line cap by reflowing, not by raising the cap
**Decided by:** agent
The cap is a deliberate budget from an earlier SPEC. Two three-line paragraphs (owners advisory,
1:N / migrate) reflow to two lines each, freeing exactly the blank line + one long rule line.
Rejected: raising the cap (reopens another SPEC's decision); moving the rule to
`references/workflow-feedback.md` only (AC-004 requires the SKILL.md).

### ADR-002: project-knowledge routes intent-bearing claims by a first procedure step that hands off to intent-layer
**Decided by:** agent
A "Route first" step before the search: a claim bearing on an intent's metric or decision stops
here and follows the intent-layer skill, whose consent rule governs the write. project-knowledge
never calls `hm intent question` itself — the write rule lives in one skill. Link directions:
the fact body names the question id; the question cites the fact with
`--locator .claude/memory/wiki.md:<A-B>`.

### ADR-003: `harness_maker.memory` stays a package with a docstring-only `__init__`
**Decided by:** agent
`memory_md` imports `harness_maker.memory._locking`; moving the lock would touch a live import
path for no gain. The package docstring is rewritten to say it holds the shared lock only.

### ADR-004: Judge LOOP-OPT-IN AC-003 only on paths whose off-render has not moved since the opt-in commit
**Decided by:** user (source: execute conversation, option A "make the reference durable")
The test pinned `055cce85` snapshots, so any later template change failed it. It now drops paths whose
loop-off snapshot differs between `18714dd1` and the working tree; loop files are never dropped.
Checked: for this change the excluded set is exactly the two edited skills.

## 🏗️ Technical Design

- `src/harness_maker/memory/`: delete `episodic.py`, `semantic.py`, `profile.py`, `retrieval.py`;
  `__init__.py` → docstring only.
- `tests/unit/test_memory/`: delete `test_episodic.py`, `test_semantic.py`, `test_profile.py`,
  `test_retrieval.py`; keep `test_locking.py`.
- Docstrings in `src/harness_maker/memory_retrieve.py:3` and `tests/unit/test_memory_retrieve.py:3`
  stop contrasting with `MemoryRetriever`.
- Templates: `templates/skills/project-knowledge/SKILL.md.j2`, `templates/skills/intent-layer/SKILL.md.j2`.
- Snapshots: `tests/snapshot/*.expected.yaml` via `tests/snapshot/regenerate.py`.
- `CHANGELOG.md` `[Unreleased]`: removal + window note.

## 📝 Implementation Plan

### Phase 1 — Remove the dead JSONL tier
- depends_on: none
- parallel_group: A
- merge_hazards: none (disjoint from Phase 2 files)
- scope in: `src/harness_maker/memory/*`, `tests/unit/test_memory/test_{episodic,semantic,profile,retrieval}.py`,
  `src/harness_maker/memory_retrieve.py` (docstring), `tests/unit/test_memory_retrieve.py` (docstring),
  `tests/unit/test_memory_tier_removed.py` (new — S1, S2 tests)
- scope out: `worktree.py` churn constants, `memory_md.py` logic
- exit: `uv run pytest tests/unit/test_memory_tier_removed.py tests/unit/test_memory tests/unit/test_memory_retrieve.py tests/unit/test_worktree_churn_pollution.py tests/unit/test_worktree_task_lifecycle.py` green; `mypy --strict src` clean
- risk: low
- rollback: `git checkout -- src/harness_maker/memory tests/unit/test_memory`
- status: DONE

### Phase 2 — Boundary rule in both skills
- depends_on: none
- parallel_group: A
- merge_hazards: snapshot baselines (serial after Phase 1 to regenerate once)
- scope in: the two skill templates, `tests/unit/test_memory_tier_removed.py` (S3, S4 tests),
  `tests/snapshot/*.expected.yaml`
- scope out: `references/workflow-feedback.md.j2`, existing wiki entries
- exit: `uv run pytest tests/unit/test_memory_tier_removed.py tests/render/test_render_project_knowledge.py tests/unit/test_render_intent_layer_assume_add.py tests/snapshot` green
- risk: medium (render caps, snapshot drift)
- rollback: `git checkout -- src/harness_maker/templates/skills tests/snapshot`
- status: DONE (first reflow broke the pinned phrase `preserves record body bytes` in test_intent_vocabulary::test_s7; line break moved)

### Phase 3 — CHANGELOG
- depends_on: Phase 1, Phase 2
- parallel_group: B
- merge_hazards: CHANGELOG is shared with concurrent sessions (rebase silent-revert risk — compare mechanically at land)
- scope in: `CHANGELOG.md`
- exit: `[Unreleased]` names the four classes and `wiki_fact_entries_28d` (one-time check, AC-006)
- risk: low
- rollback: `git checkout -- CHANGELOG.md`
- status: DONE

### Phase 4 — Durable reference for the LOOP-OPT-IN parity test (added in execute, user-approved)
- depends_on: Phase 2
- parallel_group: C
- merge_hazards: none
- scope in: `tests/unit/test_loop_opt_in.py` (`test_ac003_enabled_matches_pre_change_snapshots` only)
- scope out: every other LOOP-OPT-IN test and template
- exit: `uv run pytest tests/unit/test_loop_opt_in.py` green; excluded paths = exactly the two skills changed here
- risk: low
- rollback: `git checkout -- tests/unit/test_loop_opt_in.py`
- status: DONE

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/worktree.py` — churn/dirt classification stays as is (SPEC AC-003)
- `src/harness_maker/memory/_locking.py` — live lock used by memory_md
- `src/harness_maker/memory_md.py` — write paths and lock acquisition unchanged
- `.claude/memory/wiki.md` — rule applies to new claims only
- `src/harness_maker/templates/skills/intent-layer/references/workflow-feedback.md.j2`
- Advisory: keep project-knowledge's pinned tokens and ≤ 250-char description with "remember" and "correct"

### Phase 5 — wrapup Step 5.7 quoting (review confirm-1 repair, user-approved)
- depends_on: Phase 2
- parallel_group: D
- merge_hazards: autopilot_gate_golden.json re-capture
- scope in: `src/harness_maker/templates/stages/wrapup.md.j2` (Step 5.7 Claude-branch quoting only), snapshots, `tests/structural/autopilot_gate_golden.json`, `tests/structural/test_autopilot_gate_render.py` (dated re-capture entry)
- scope out: any other wrapup text; command-surface growth (budget allows 0)
- exit: structural + render + snapshot suites green (1168 passed)
- risk: medium
- rollback: `git checkout -- src/harness_maker/templates/stages/wrapup.md.j2 tests/structural tests/snapshot`
- status: PARTIAL — confirm-2 found the apostrophe case still open (REVIEW P1 `4621494f2640860a`)
- follow-up (user chose option b, 2026-09-27): the quote-avoidance rule now lives in `intent-layer/references/workflow-feedback.md.j2` step 2, which Step 5.7 loads; routing scoped to new claims (codex P2 `59db47012df403d0`); tests pin single-quoted wrapup writes, the workflow-feedback rule and the question-id link direction. **Boundary crossing:** `workflow-feedback.md.j2` is on this PLAN's `Do not change` list — crossed on the user's explicit decision. status: DONE

## 🧪 Testing Strategy

- Unit: `tests/unit/test_memory_tier_removed.py` (AC-001..005), existing churn tests (AC-003),
  existing render tests for both skills, snapshot suite.
- Full suite once at the end (background).
- Manual: AC-006 CHANGELOG read at wrapup.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| intent-layer render exceeds 120-line cap | high if naive | ADR-001 reflow; existing test enforces |
| Snapshot drift misses a target | medium | regenerate in worktree, verify glob matched |
| External importer of removed classes | low | IRR-001, CHANGELOG note |
| CHANGELOG lines lost on rebase at land | medium | mechanical diff check at wrapup |

## ✅ Success Criteria

- [x] AC-001 dead tier not importable, no import/use remains
- [x] AC-002 memory_md write paths take the lock
- [x] AC-003 legacy churn dirs still classified as harness artifacts
- [x] AC-004 boundary sentence + mutual reference in both rendered skills
- [x] AC-005 project-knowledge routes intent claims to intent-layer, wiki locator link stated
- [x] AC-006 CHANGELOG entry (wrapup check)

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| SPEC Constraints "Measurement window" (2026-09-27) | wiki_fact_entries_28d | unchanged (no intent write; disclosed in CHANGELOG) | Accept input change; thresholds unchanged | user | DRI Round 3 answer | Read the 10-17 measurement against the landing date |
| Full suite 2026-09-27: 88 failures under default TMPDIR, reproduced on base main | environment | recorded here | Not this change: `/tmp/.git` (broken, created 2026-09-26 11:00) and `/tmp/.claude` sit above pytest tmp dirs and capture root resolution. Suite with TMPDIR outside /tmp: only the 4 loop-opt-in failures (fixed, Phase 4) + 6 install_ref failures caused by the $HOME-based TMPDIR itself | agent | observation only; no deletion outside the repo | Ask the user whether to remove `/tmp/.git` and `/tmp/.claude` |
| REVIEW-sdlc-three-loops-gap-2026-09-27 (run 6cb74c0a3f9f): CHANGES_REQUESTED, grade B | none (no intent) | recorded | Stop: open P1 `4621494f2640860a` (wrapup Step 5.7 apostrophe breakout; the repair round's cited mitigation is not loaded there) | user | review gate `blocked` — no level clears it | User picks the fix route (REVIEW 'Open for the human' 1a/1b/1c), then re-run `/hm:review sdlc-three-loops-gap` |
| User answer "B 리뷰" (2026-09-27) | none | recorded | Option b applied; re-run /hm:review | user | explicit choice | `/hm:review sdlc-three-loops-gap` |
| REVIEW run d5a96ec922f4: CHANGES_REQUESTED, grade B | none | recorded | Stop: open P1 `93479083cb71beba` (Step 5.7 add-branch cue) | user | review gate `blocked` | Fix the one sentence, then re-run `/hm:review sdlc-three-loops-gap` |
| REVIEW run a8bcd353b3b0: CHANGES_REQUESTED, grade B, one accepted P1 | none | recorded | User chose C: accept the prompt-only injection residual; file-based `--*-file` inputs become a separate task | user | explicit choice | `/hm:wrapup sdlc-three-loops-gap` (fill the CHANGELOG landing date); open follow-up task for file-based intent inputs |
| Wrapup Step 2: tests/unit/test_world_intent_protocol_evidence.py failed — `workflow-feedback.md.j2` is the WORLD-INTENT-CLOSED-LOOP trial protocol and its captured model-run evidence is hash-bound to it | WORLD-INTENT-CLOSED-LOOP evidence | recorded | Reverted the option-b sentence in `workflow-feedback.md.j2` (Step 5.7's three run lines already carry `(no ' inside)`; the intent-layer write rule covers direct calls); the `Do not change` boundary is restored | user | explicit choice (revert) | Continue wrapup |
| Trial PLAN collector is another session | WORLD-INTENT-CLOSED-LOOP trial | pending (non-collector) | Do not write the trial PLAN | agent | intent-layer Real-task trial rule | Collector reconciles on its next entry |
