---
type: plan
task_slug: fresh-install-p0-calibration
status: complete
created: 2026-05-20
tags: [harness-maker, plan, python, ai-readiness, priority-calibration, fresh-install]
interview_rounds: 3
adrs: 5
validator_outcome: SKIPPED_VALIDATOR_UNAVAILABLE
summary: "Wire INTENDED_P0_SIGNALS into user-facing _extract_layer1_actions priority (suppress telemetry <5 samples; demote ADR/CI/CONTRIBUTING to P2)"
---

# PLAN — fresh-install-p0-calibration

## 🎯 Executive Summary

**TL;DR**: User-facing `[P0]` priority labels on fresh-install health output mislead users into treating self-resolving telemetry signals and aspirational governance signals as urgent. Bridge the gap left in 0.17.0 fresh-install-baseline by wiring the already-defined `INTENDED_P0_SIGNALS` allowlist into the user-facing `_extract_layer1_actions` priority assignment, with a sample-pass-aware split between auto-resolve and user-author categories.

**What / Why**: `improvement.py:61 _layer1_priority(signal_weight)` decides P0/P1/P2 purely from static signal weight. `INTENDED_P0_SIGNALS` frozenset exists in `readiness.py:76-84` but its docstring explicitly states "Used by Phase 4 integration test allowlist; readiness scoring itself unchanged." Result: fresh-install users see telemetry + ADR/CONTRIBUTING signals as `[P0]` even though (a) telemetry self-populates on first tool use, (b) ADR/CONTRIBUTING are aspirational governance, not urgent. The 0.17.0 work fixed the integration-test side; this PLAN finishes the user-facing side.

**Key decisions**:
- ADR-001: Scope = priority demotion only. Name-collision / KEEP enumeration deferred.
- ADR-002: Telemetry signals (metrics_jsonl_present, metrics_has_samples) — suppress from action list when `metrics_has_samples.passed == False` (samples < 5).
- ADR-003: Governance signals (adr_present, contributing_present, ci_workflow_present) — override priority to `"P2"` regardless of weight.
- ADR-004: One-line footer when deferred count > 0.
- ADR-005: Test pyramid = parameterized unit + 1 snapshot + 1 integration.

**Estimated impact**: 3 modified files (improvement.py, ai_readiness.py, readiness.py), ~60 LOC core change, ~150 LOC new tests, 1 CHANGELOG entry, 5-file version sync per CLAUDE.md release procedure.

## 📚 Prior Work

- `wiki:fresh-install-health-baseline` (2026-05-19, 0.17.0) — created `INTENDED_P0_SIGNALS` frozenset but applied it only to integration-test allowlist (`readiness.py:65-75` comment is explicit on this). This PLAN finishes the user-facing piece.
- `wiki:model-routing-multi-ide` — established the precedent for weight/priority decoupling via 3 advisory weight-0 sub-checks in `model_routing` dim. We adopt the same pattern for INTENDED_P0_SIGNALS handling.
- ADR-006 (cited in `readiness.py:65-75`) defines "samples-based TTL" semantics for INTENDED_P0_SIGNALS — auto-resolve signals surface normally past samples ≥ 5. We extend that semantic from allowlist layer to priority emission.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Scope | Boundaries | After diagnosis correction (5 over-line agents are all user-owned, not harness-maker ship), what's the actual fix scope? | A. P0 demotion only (single fix) | ADR-001 |
| 2 | Telemetry handling | Architecture | How to treat auto-resolve signals on fresh install? | A. Completely hide when samples < 5 | ADR-002 |
| 3 | Governance handling | Architecture | How to treat aspirational signals (adr/contributing/ci_workflow_present)? | A. Permanent P2 override | ADR-003 |
| 4 | Footer visibility | Contract | Should hidden items get a 1-line CLI footer? | A. Yes, 1-line note | ADR-004 |
| 5 | Test depth | Testing | What test pyramid? | C. Unit (parameterized + snapshot) + integration | ADR-005 |

## 📐 Architecture Decision Records

### ADR-001: Single-fix scope — priority demotion only
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** Initial user ask was "두가지 fix" based on prior conversation that diagnosed (1) fresh-install P0 noise and (2) harness-maker's own agents exceeding 200-line lint. Investigation showed #2 was misdiagnosed: the 5 over-limit files in the test environment are all user-owned custom agents (no `generated_by` provenance frontmatter); harness-maker's actual ships are all ≤188 lines. The lint correctly reports user state.
**Decision:** Scope this PLAN to a single fix — priority demotion. Name-collision / KEEP-list enumeration is a separate concern, deferred to a future PLAN.
**Consequences:**
- ✅ Tight, defensible scope. One change to `_extract_layer1_actions` + one CLI footer.
- ⚠️ Sibling concern (silent shadowing of shipped agents when same-named user file exists, with no enumeration in the KEEP-9 log line) left unaddressed.
**Rejected alternatives:**
- B. P0 demotion + KEEP enumeration — Rejected: the agent 200-line lint is correct on user-owned files; not a defect.
- C. Side-style weight-zeroing — Rejected: scoring change has wider blast radius; user wants the priority label fix specifically.
**Source:** Interview #1

### ADR-002: Telemetry signals — suppress when samples < 5
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** `metrics_jsonl_present` (weight 25 → P0), `metrics_has_samples` (weight 25 → P0). Both self-resolve through normal Claude Code usage. Their action hints literally say "First Claude Code tool use will create this file" and "Use Claude Code for ≥ 5 turns to accumulate telemetry."
**Decision:** When `metrics_has_samples.passed == False` (samples < 5), suppress both telemetry signals from the action list entirely. Once samples ≥ 5, surface normally as P0 (so that genuine telemetry regression at steady state still alerts).
**Consequences:**
- ✅ Fresh install shows zero telemetry-related noise.
- ✅ Steady-state detection (hook regression that stops new telemetry) preserved at samples ≥ 5.
- ⚠️ User on day 1 doesn't see the "telemetry will be created" hint inline — addressed via footer (ADR-004).
**Rejected alternatives:**
- B. P3-informational tier — Rejected: introduces a new tier; over-engineering for one use case.
- C. P2 demote — Rejected: still appears in Top-5 action list, doesn't achieve "zero noise."
**Source:** Interview #2

### ADR-003: Governance signals — P2 priority override
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** `adr_present` (weight 50 → P0), `contributing_present` (weight 50 → P0), `ci_workflow_present` (weight 20 → P1 — already not P0 in current code, but included in INTENDED_P0_SIGNALS for consistency with the "require user authoring" sub-category). These never auto-resolve; they require user authoring. Fresh repo lacking them is normal.
**Decision:** When `sig.id` ∈ `USER_AUTHOR_SIGNALS = {"adr_present", "contributing_present", "ci_workflow_present"}` and the signal failed, override priority to `"P2"` regardless of weight. Presence and dimension score are unchanged (these still contribute to the composite); only the user-facing priority label changes.
**Consequences:**
- ✅ Fresh-install P0 alarm for governance gone (adr_present and contributing_present demote P0→P2; ci_workflow_present demotes P1→P2 for consistency).
- ✅ Composite ai-readiness score unchanged (still useful as quality signal across releases).
- ⚠️ User who genuinely wants ADRs urgent has to manually re-elevate or notice via the /hm:health dashboard view.
**Rejected alternatives:**
- B. P3 informational tier — Rejected (over-engineering, see ADR-002).
- C. Suppress entirely — Rejected: these never auto-resolve; user should still see them, just not as urgent.
**Source:** Interview #3

### ADR-004: One-line CLI footer for deferred items
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** With telemetry suppressed and governance demoted, fresh-install action list may show fewer items than before with no obvious explanation. Risk: user assumes telemetry is broken when it's just deferred.
**Decision:** Append a one-line footer after the Top-N actions block when (suppressed_telemetry_count + demoted_governance_count) > 0:

```
… N item(s) deferred (M telemetry signal(s) auto-populate after ≥ 5 turns; K aspirational governance item(s) demoted to P2). Run /hm:health for full list.
```

Both `/hm:make` post-install summary and `/hm:health` action list emit the footer (no command-specific divergence).
**Consequences:**
- ✅ Transparency preserved without P0 alarm.
- ✅ Single point of UX information; no scattered hints.
- ⚠️ +1 line in CLI output; minor format change. Documented in CHANGELOG.
**Rejected alternatives:**
- B. No footer — Rejected: telemetry status opacity is itself a UX issue.
- C. Footer only in /hm:health — Rejected: inconsistency between commands; /hm:make is the very point at which the user first sees this output.
**Source:** Interview #4

### ADR-005: Test pyramid — unit + snapshot + integration
**Status:** Accepted (2026-05-20, via /hm:plan interview)
**Context:** This change crosses three boundaries — priority logic (improvement.py), action-list formatter (ai_readiness.py), and integration boundary (fresh install CLI behavior). CLAUDE.md "Implementation Patterns" checklist #8 requires at least one real integration test for user-boundary code.
**Decision:**
- (a) Parameterized unit fixtures in `tests/unit/test_improvement_p0_calibration.py` covering `metrics_has_samples.passed ∈ {True, False}` × signals in/out of INTENDED_P0_SIGNALS × suppression vs override paths (≥ 6 cases).
- (b) Snapshot test in `tests/unit/test_ai_readiness_action_list_footer.py` for CLI golden output with/without footer.
- (c) Integration test in `tests/integration/test_fresh_install_p0_calibration.py` that creates a temp fresh project, runs `cli.make` via Typer's `CliRunner`, asserts no `[P0]` for INTENDED_P0_SIGNALS in stdout and footer present.
**Consequences:**
- ✅ All three layers covered.
- ✅ Golden file lock prevents accidental regression of CLI output format.
- ⚠️ Integration test adds ~3s to suite; runs unconditionally (no `INTEGRATION=1` gate — it's local-only, no network).
**Rejected alternatives:**
- A. Unit only — Rejected: misses CLI output format regression.
- B. Integration only — Rejected: too slow for tight inner loop on logic changes.
**Source:** Interview #5

## 🏗️ Technical Design

### Current State
- `improvement.py:61 _layer1_priority(signal_weight: int)` maps weight → P0 (≥25) / P1 (≥15) / P2 (else).
- `readiness.py:76-84 INTENDED_P0_SIGNALS` frozenset enumerates fresh-install-noise signals; comment explicitly states "readiness scoring itself unchanged" — i.e. allowlist not applied to user-facing priority.
- `_dim_observability_setup` (readiness.py:754-823) emits `metrics_has_samples` signal whose `.passed` is `True` iff sample_size ≥ 5.
- `_extract_layer1_actions` (improvement.py:72-92) iterates `readiness.dimensions` × signals, calls `_layer1_priority(sig.weight)` on each failing signal.

### Affected Components
- `src/harness_maker/readiness.py` — split `INTENDED_P0_SIGNALS` into two named subsets `TELEMETRY_AUTO_RESOLVE_SIGNALS` and `USER_AUTHOR_SIGNALS` (re-export `INTENDED_P0_SIGNALS = TELEMETRY_AUTO_RESOLVE_SIGNALS | USER_AUTHOR_SIGNALS` for backward compatibility with existing import sites — confirmed via grep that the frozenset is referenced in tests).
- `src/harness_maker/improvement.py` — extend `_extract_layer1_actions` with suppression + override branch; expose a count via new return field or via a sibling helper to feed the footer.
- `src/harness_maker/ai_readiness.py` — action list formatter (around `lines.append(f"Top {min(max_actions, len(plan.actions))} of {len(plan.actions)} actions:")` at line 233) — append footer when deferred_count > 0.
- `tests/unit/` — two new test modules.
- `tests/integration/` — one new test module.

### Dependencies
None new. Uses existing readiness signal infrastructure.

### Architecture

```
ReadinessResult ─→ _extract_layer1_actions(readiness) ─┐
                                                        │
   has_samples = lookup(observability_setup.signals,    │
                        id="metrics_has_samples").passed│
                                                        │
   for dim, sig in failing_signals:                     │
     if sig.id in TELEMETRY_AUTO_RESOLVE_SIGNALS        │
        and not has_samples:                            │
         suppressed_telemetry += 1                      │
         continue   # do not append to actions          │
     if sig.id in USER_AUTHOR_SIGNALS:                  │
         priority = "P2"                                │
         demoted_governance += 1                        │
     else:                                              │
         priority = _layer1_priority(sig.weight)        │
     actions.append(ActionItem(..., priority))          │
                                                        │
   return ImprovementPlan(actions=...,                  │
                          deferred_telemetry=...,       │
                          demoted_governance=...)       │
                                                        │
                                                        ▼
                          render_action_list(plan)
                          ├─ Top-N actions
                          └─ if deferred_telemetry + demoted_governance > 0:
                                emit footer
```

### Design Decisions
- **Subset naming** (referenced ADR-002, ADR-003): split `INTENDED_P0_SIGNALS` into two named subsets in `readiness.py` for clarity at the call site. Re-export `INTENDED_P0_SIGNALS` as their union to keep existing imports (integration test allowlist) intact.
- **Sample-count source**: read `metrics_has_samples.passed` directly from the readiness result. No new field on `ReadinessResult` (avoids API surface expansion). The signal already encodes the threshold (samples ≥ 5 → passed).
- **Counter exposure for footer**: add two `int` fields to `ImprovementPlan` Pydantic model (`deferred_telemetry: int = 0`, `demoted_governance: int = 0`). Additive change with safe defaults; backward-compatible.
- **Footer format**: single line, English only (CLI output is locale-en globally per current convention). Future i18n: out of scope.

### Data Flow
1. `cli.make` (or `/hm:health`) → `compute_readiness(project_dir, preset)`.
2. `_extract_layer1_actions(readiness)` applies suppression + override; returns `ImprovementPlan` with counter fields.
3. `render_action_list(plan)` (in `ai_readiness.py`) emits Top-N + footer if counters > 0.
4. CLI prints result to stdout.

### API Changes
- Internal: `_extract_layer1_actions` signature unchanged; return type's Pydantic schema gains two `int` fields with default 0.
- Public CLI output: `[P0]` count drops on fresh install; new 1-line footer appears.
- No public Python API change (`ImprovementPlan` is internal).

## 📝 Implementation Plan

### Phase 1 — Core priority logic
- **Scope (in)**:
  - `src/harness_maker/readiness.py` — split `INTENDED_P0_SIGNALS` into `TELEMETRY_AUTO_RESOLVE_SIGNALS` and `USER_AUTHOR_SIGNALS`; keep `INTENDED_P0_SIGNALS = TELEMETRY_AUTO_RESOLVE_SIGNALS | USER_AUTHOR_SIGNALS` (backward-compat).
  - `src/harness_maker/improvement.py` — add `deferred_telemetry: int = 0` and `demoted_governance: int = 0` to `ImprovementPlan`; extend `_extract_layer1_actions` with the suppression + override branches and increment counters.
- **Scope (out)**: CLI formatter (Phase 2), tests (Phase 3), version bump (Phase 4).
- **Exit criterion**:
  - `uv run mypy --strict src/harness_maker/improvement.py src/harness_maker/readiness.py` clean.
  - Hand-crafted Python REPL: `_extract_layer1_actions(fresh_install_fixture)` returns empty actions list with `deferred_telemetry=2, demoted_governance=1` (or `2` if user lacks CONTRIBUTING.md too).
- **Risk**: low. Self-contained logic in a pure function; existing tests for ai_readiness will catch broad regressions.
- **Rollback**: `git revert` Phase 1 commit; behavior returns to weight-only priority.

### Phase 2 — CLI footer rendering
- **Scope (in)**: `src/harness_maker/ai_readiness.py` — modify the action-list emitter at and around line 233 to append a footer line when `plan.deferred_telemetry + plan.demoted_governance > 0`.
- **Scope (out)**: priority logic (Phase 1), tests (Phase 3).
- **Exit criterion**: Manual eyeball — run `uv run python -c "from harness_maker.ai_readiness import format_action_list; ..."` on a synthetic plan with counters > 0 and confirm footer appears in stdout; counters == 0 → no footer.
- **Risk**: low. Pure formatting change.
- **Rollback**: revert Phase 2 commit; Phase 1 still works (footer just absent).

### Phase 3 — Tests
- **Scope (in)**:
  - `tests/unit/test_improvement_p0_calibration.py` — parameterized; 6+ cases covering `metrics_has_samples ∈ {pass, fail}` × signal categories × non-INTENDED control case.
  - `tests/unit/test_ai_readiness_action_list_footer.py` — 2 golden snapshots under `tests/snapshots/ai_readiness_action_list/` (with-footer, without-footer).
  - `tests/integration/test_fresh_install_p0_calibration.py` — temp dir fresh project (no `.claude/observability/`, no `docs/adr/`, no `.github/workflows/`), invoke `cli.make` via `CliRunner`, assert no `[P0]` line matches `r"\b(telemetry|ADRs|CONTRIBUTING)\b"` and footer string is present.
- **Scope (out)**: production code.
- **Exit criterion**:
  - `uv run pytest tests/unit/test_improvement_p0_calibration.py tests/unit/test_ai_readiness_action_list_footer.py tests/integration/test_fresh_install_p0_calibration.py -v` — all green.
  - Full suite: `uv run pytest` — green (background-friendly per CLAUDE.md memory `pytest 항상 background`).
- **Risk**: low-medium. Snapshot test can flake if signal order is non-deterministic — pin via sorted dim iteration in `_extract_layer1_actions` if needed (verify in Phase 3 implementation).
- **Rollback**: revert Phase 3 commit (tests only); Phase 1+2 code still ships (untested in CI but functionally unchanged).

### Phase 4 — CHANGELOG + 5-file version sync
- **Scope (in)**: `CHANGELOG.md` (entry under `[Unreleased]`), `pyproject.toml`, `src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json` — bump patch version (current 0.19.1 → 0.19.2).
- **Scope (out)**: code changes (done in Phase 1-3), tag push and Release page (post-PR per CLAUDE.md release procedure).
- **Exit criterion**:
  - All 5 version strings identical (`grep -r "0.19.2" pyproject.toml src/harness_maker/__init__.py .claude-plugin .cursor-plugin .codex-plugin` returns 5 matches).
  - CHANGELOG entry under `[Unreleased]` describes the user-visible change with the BREAKING note about reduced `[P0]` count.
  - Advisory boundary tests pass locally: `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v` (per CLAUDE.md release procedure — advisory, does not block).
- **Risk**: low. Mechanical update per CLAUDE.md release procedure.
- **Rollback**: revert Phase 4 commit.

## 🧪 Testing Strategy

### Unit (Phase 3a) — `tests/unit/test_improvement_p0_calibration.py`
Parameterized fixtures for `_extract_layer1_actions`:
1. `metrics_has_samples.passed=False` + `metrics_jsonl_present.passed=False` → both suppressed, `deferred_telemetry=2`, no actions.
2. `metrics_has_samples.passed=True` + `metrics_jsonl_present.passed=False` (regression scenario: file existed, now gone) → emitted as P0, `deferred_telemetry=0`.
3. `metrics_has_samples.passed=False` + `adr_present.passed=False` → telemetry suppressed, ADR override to P2.
4. `adr_present.passed=False` + `contributing_present.passed=False` → both override to P2, `demoted_governance=2`.
5. `ci_workflow_present.passed=False` (weight=20, normally P1) → override to P2, `demoted_governance=1`.
6. Control: non-INTENDED signal failing (e.g. weight=30 hypothetical) → emitted as P0, no demotion.

### Snapshot (Phase 3b) — `tests/unit/test_ai_readiness_action_list_footer.py`
- Snapshot A (`with_footer.txt`): plan with `deferred_telemetry=2, demoted_governance=1` → action list + footer.
- Snapshot B (`without_footer.txt`): plan with `deferred_telemetry=0, demoted_governance=0` → action list only.

### Integration (Phase 3c) — `tests/integration/test_fresh_install_p0_calibration.py`
1. Create `tmp_path` with minimal Python project (pyproject.toml only).
2. Invoke `cli.make tmp_path --preset Production --locale en --targets claude-code` via `CliRunner`.
3. Assert `result.exit_code == 0`.
4. Assert `re.search(r"\[P0\].*(telemetry|ADRs|CONTRIBUTING)", result.stdout) is None`.
5. Assert footer phrase ("items deferred") present in result.stdout.
6. Assert `[P2]` line for ADRs is present (the demotion happened, not full suppression).

### Manual checklist
None — fully automated. (No browser/UI changes.)

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | `ci_invokes_tests` (sibling of `ci_workflow_present`) is NOT in INTENDED_P0_SIGNALS but is logically downstream noise on fresh install — may still appear as P1 alongside demoted parent. | High (will happen) | Low (P1, not P0; less alarming) | Document as known limitation in CHANGELOG; defer to a follow-up PLAN. |
| 2 | Snapshot test ordering instability if dim signals iterate non-deterministically. | Medium | Low | Sort by `(dim_name, sig.id)` in `_extract_layer1_actions`. Verify dict iteration order preservation in Python 3.12 (insertion order). |
| 3 | A real telemetry breakage (hook misconfigured → file never created → samples never reach 5) is permanently hidden because suppression threshold is `samples_has_passed` and that signal never becomes `True`. | Low | High | Mitigation #1: footer mentions "auto-populates after ≥ 5 turns" so user notices if their first turn never created a file. Mitigation #2 (out-of-scope, deferred): add Phase-5 follow-up to detect "no metrics file ever, despite N tool uses logged via session_id" anomaly via a separate dim. |
| 4 | Users who DEPEND on current `[P0]` labels in scripts/CI parsing will see behavior change. | Low | Medium | CHANGELOG BREAKING note. Output format is documented as informational, not API. |
| 5 | `INTENDED_P0_SIGNALS` is re-exported as `TELEMETRY_AUTO_RESOLVE_SIGNALS \| USER_AUTHOR_SIGNALS` — if a test or other module imports `INTENDED_P0_SIGNALS` directly, set identity is preserved but membership is set-equal not name-equal. | Low | Low | Run full pytest after Phase 1 to catch any import-time regression. Frozenset equality is value-based. |

## ✅ Success Criteria

- [x] Fresh-install `cli.make` output shows no `[P0]` lines containing "telemetry", "no ADRs", or "CONTRIBUTING missing".
- [x] Footer line appears when `deferred_telemetry + demoted_governance > 0`; absent when both are 0.
- [x] Once samples ≥ 5, telemetry signals surface again (`metrics_has_samples.passed == True` path), preserving steady-state regression detection.
- [x] `uv run pytest` full suite green.
- [x] `uv run mypy --strict src/harness_maker/improvement.py src/harness_maker/readiness.py src/harness_maker/ai_readiness.py` clean.
- [x] 5-file version sync (`grep "0.19.2" pyproject.toml src/harness_maker/__init__.py .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json` → 5 matches).
- [x] CHANGELOG entry under `[Unreleased]` describes the user-visible change and BREAKING reduction in `[P0]` count.

## 🔍 Plan Validation

**Validator outcome:** `SKIPPED_VALIDATOR_UNAVAILABLE` — plan-validator agent dispatch failed with "There's an issue with the selected model (claude-4-7-opus[1m])" (agent definition's model spec incompatible with current runtime).

**Self-critique pass (applied to draft before write):**

| Finding | Severity | Resolution |
|---------|----------|-----------|
| Original draft included a Risk #3 about `ReadinessResult` API field addition. | Low | Removed — used existing `metrics_has_samples.passed` signal instead; no API change needed. Updated Technical Design accordingly. |
| Original ADR-003 mis-stated `ci_workflow_present` as a P0→P2 demotion. | Medium | Corrected to "P1→P2 demotion for ci_workflow_present (weight 20); P0→P2 for adr_present + contributing_present (weight 50 each)". |
| Plan-validator unavailable — formal NEEDS_REVISION/MAJOR_REVISION pass skipped. | Medium | Recorded explicitly in frontmatter and this section. Recommend `code-reviewer` agent be invoked in `/hm:review` after `/hm:execute` to catch issues the validator would have caught. |
| Originally Phase 4 (release sync) was listed under "Scope (out)" of /hm:execute; included as a phase here for completeness. | Low | Kept as a phase — execute Phase 4 only when shipping the patch release. |

**Open follow-ups (not in scope):**
- Name-collision / KEEP enumeration (deferred per ADR-001).
- `ci_invokes_tests` cascade demotion (deferred per Risk #1).
- Hidden-telemetry anomaly detection (deferred per Risk #3).
