---
type: plan
task_slug: health-plugin-bugs-2026-05
status: complete
created: 2026-05-17
tags: [harness-maker, plan, python, observability, dashboard, ai-readiness, bug-fix]
interview_rounds: 2
adrs: 2
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Fix two 0.13.0 /hm:health plugin bugs (metrics-rotation false negative + dashboard score=0 contract bug) + add round-trip contract test"
---

# PLAN — health-plugin-bugs-2026-05

## 🎯 Executive Summary

**TL;DR.** /hm:health surfaced two real plugin bugs. Fix both, add a contract
test that would have caught Bug 2 in CI, ship as 0.13.1 patch.

**What / Why.**

| Bug | Root cause | Visible symptom |
|-----|------------|-----------------|
| 1   | `_dim_observability_setup` reads only legacy `metrics.jsonl` for **two** signals (`metrics_jsonl_present` at lines 734-742 + `metrics_has_samples` at lines 753-770), ignoring the date-sharded `metrics-YYYY-MM-DD.jsonl` rotation (ADR-103) | Both signals fail on every project with rotated telemetry → ai-readiness L1 drops a free 50 points in the observability_setup dimension AND the user sees the misleading recommendation "Install the PostToolUse telemetry hook (run /hm:make)" on an already-correctly-instrumented project |
| 2   | `ai_readiness.run_structural()` returns `{"structural": <int>, ...}` but `render_dashboard_markdown()` and its tests expect `{"score": <int>, ...}` — schema mismatch between producer and consumer | `.claude/observability/dashboard.md` always renders `Structural score: 0 / 100`, masking the real ai-readiness number for every user |

**Key decisions (Interview Round 1):**
- **ADR-001 (Bug 2 fix location)**: producer-side rename — change `run_structural()` inner key from `"structural"` → `"score"`. Chosen over consumer-side fix because tests already encode the `"score"` contract and the result is a clean schema (`{"structural": {"score": 81, ...}}` instead of the nested same-named key `{"structural": {"structural": 81, ...}}`).
- **ADR-002 (Round-trip contract test)**: add an integration test that calls real `run_structural()` → real `write_dashboard()` → asserts the rendered `dashboard.md` contains the real score. Sets a precedent that producer/consumer contracts must be exercised end-to-end, not only unit-tested with fixture dicts. This is the gap that let Bug 2 ship.

**Estimated impact**: ~5 files modified, ~150 LoC delta (mostly tests), 1 new test file. No public-API surface change; `.health.tmp.json` internal schema changes by one key rename within the same pipeline.

## 📚 Prior Work

- **0.13.0 consolidation** (commit `82eaddb`, PLAN-health-consolidation) introduced `/hm:health` and the 3-section dashboard; Bug 2 was introduced in that consolidation. Bug 1 predates it (the `_dim_observability_setup` rubric existed before the metrics-rotation refactor that produced `_metrics_io`).
- **ADR-103** in `src/harness_maker/_metrics_io.py:3` documents the rotation pattern. Reusing the existing `_candidate_files()` util keeps Bug 1's fix consistent with `security_scanner.py` and `cache_diagnostics.py`, which already read rotated telemetry.
- **Dashboard tests** (`tests/unit/test_observability_dashboard.py:22-26`) use the right schema (`"score"` key). The unit tests were correct; the producer drifted from them without anyone noticing because there was no integration test connecting the two.
- **CLAUDE.md §버전업 정책**: any version bump must update 5 files together (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`).

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|------:|-------|----------|----------|--------|------|------|
| 1 | 1 | Bug 2 fix location | Contract shape | Producer-side rename vs consumer-side fix vs both | **Producer-side rename** | Tests already encode `"score"` contract; eliminates ugly nested same-named key | ADR-001 |
| 2 | 1 | Bug 1 recency window | Implementation detail | All-time count via `_candidate_files` vs 7-day `iter_recent_entries` vs split signal | **All-time count** | Signal is `metrics_has_samples` (not `_recent_samples`); semantically just "telemetry exists" | — |
| 3 | 1 | E2E test scope | Testing depth | Defer e2e refactor vs fix in PLAN vs ignore | **Fix in this PLAN** (re-scoped to add a round-trip contract test rather than refactor the verify-stage fixture, which would couple two unrelated test concerns) | The actual gap is "no integration test connecting producer to consumer," not "the verify fixture builder is wrong." | ADR-002 |
| 4 | 2 | Phase 1 scope expansion (validator critique 1) | Phase decomposition | Revise to fix both rotation-blind signals / accept as risk / defer | **Revise: expand Phase 1** | Validator correctly identified `metrics_jsonl_present` sibling signal at lines 734-742 also reads only legacy path. Same function, same bug class, same commit boundary → carving it out would be artificial. Impact estimate revised 25 → 50 points. | — |
| 5 | 2 | Round-trip test fixture floor (validator critique 2) | Testing depth | Pin numeric floor vs accept placebo risk vs defer | **Revise: pin fixture floor** | Without a floor, score=0 fixture makes 'non-zero' assertion vacuous — exactly the failure mode ADR-002 was meant to prevent. ADR-002 amended with `MIN_FIXTURE_SCORE = 30` + split assertion. | ADR-002 (amended) |

**Ambiguity Score (Round 1):** 0.85 / 1.0 — PASS
- Goals: 1.0 — fix two named bugs; no scope ambiguity
- Constraints: 0.8 — CLAUDE.md §보안 + §버전업 policies clear; no migration risk because `.health.tmp.json` is internal to the same CLI invocation pipeline
- Success Criteria: 0.8 — verifiable via re-run of `/hm:health` (Bug 2: dashboard score matches tmp.json) and added unit test (Bug 1)

**Ambiguity Score (Round 2):** 0.95 / 1.0 — PASS
- Goals: 1.0 — both validator critiques resolved with concrete revisions
- Constraints: 0.95 — fixture floor pinned (`MIN_FIXTURE_SCORE = 30`); Phase 1 scope explicitly enumerates both signals
- Success Criteria: 0.9 — added precondition grep moves the snapshot-fixture risk from Phase 3 conditional to Phase 2 must-fix-or-explicitly-ignore

Two interview rounds total. Round 1 set the fix architecture; Round 2 closed the validator's two warnings before write.

## 📐 Architecture Decision Records

### ADR-001: Producer-side rename of `run_structural()` inner key

**Status:** Accepted (2026-05-17, via /hm:plan interview)

**Context:** `ai_readiness.run_structural()` returns `{"structural": <int>, "signals_failed": [...]}`. The dashboard renderer (`render_dashboard_markdown`) and its unit tests expect `{"score": <int>, "signals_failed": [...]}`. The mismatch causes every dashboard to render `Structural score: 0 / 100` regardless of the real score.

**Decision:** Rename the inner key from `"structural"` to `"score"`. The resulting schema is:
```json
{
  "structural": {
    "score": 81,
    "signals_failed": ["..."]
  }
}
```

**Consequences:**
- ✅ Eliminates the nested same-named key. Outer `"structural"` (layer namespace) no longer collides with the inner score field name.
- ✅ Matches the renderer's existing contract — dashboard.py and its tests stay untouched.
- ✅ Two CLI print sites (`cli.py:862, 945`) and 4 unit-test assertions (`test_ai_readiness.py:335-366`) updated mechanically.
- ⚠️ `.health.tmp.json` schema changes by one key rename. Mitigated: this file is read only by `harness-maker health-finalize` in the same CLI session — no external consumers documented.

**Rejected alternatives:**
- **Consumer-side fix** (`dashboard.py: structural.get("structural")`). Rejected because it locks in the ugly nested same-named key permanently and would require updating 7 dashboard tests away from a correctly-designed contract.
- **Both (rename + compatibility shim)**. Rejected because `.health.tmp.json` is internal — no migration concern.

**Source:** Interview #1

### ADR-002: Round-trip contract test for producer↔dashboard

**Status:** Accepted (2026-05-17, via /hm:plan interview Round 1; amended Round 2 with fixture-floor pinning per plan-validator critique)

**Context:** Bug 2 shipped because unit tests verified the producer and the renderer in isolation, each against a fixture dict that matched its own assumption. No test exercised the real producer output flowing into the real renderer. The first time the contract drifted, every user's dashboard rendered `score: 0` and the test suite stayed green.

**Decision:** Add a contract test at `tests/integration/test_health_dashboard_roundtrip.py` that:
1. Builds a minimal real fixture directory seeded with enough deterministic signals to clear a pinned floor (see "Fixture floor" below)
2. Calls `run_structural(fixture_project, preset=...)` to get the producer output
3. Pipes the result through `write_dashboard(...)` (the same writer used by the live CLI)
4. Parses the rendered `dashboard.md` back via `parse_dashboard()` and asserts BOTH:
   - `assert producer_score >= MIN_FIXTURE_SCORE` (floor — catches fixture drift that would silently zero the score)
   - `assert parsed_score == producer_score` (equality — catches producer/consumer key drift)
5. Optionally adds a second test case that monkey-patches the producer to return the **old** `{"structural": <int>}` shape and asserts the round-trip test FAILS — proving the test catches the exact bug it was designed for.

**Fixture floor:** `MIN_FIXTURE_SCORE = 30`. The fixture project must seed at minimum:
- `.claude/harness.yaml` with `preset: Side` and the required keys
- `CLAUDE.md` with the basic required sections
- `.claude/observability/` directory present
- 5+ entries in a `metrics-<recent-date>.jsonl` file (also exercises Bug 1's rotation reader)

These five seeded signals deterministically clear the 30-point floor regardless of future signal additions to `_dim_*` functions (additions can only raise the score, not lower it below the floor).

**Consequences:**
- ✅ Future renamings of either side fail loudly. The test asserts the contract, not the implementation.
- ✅ The two assertions catch different failure modes: floor catches fixture rot, equality catches schema drift.
- ✅ Establishes a pattern for other producer/consumer pairs in harness-maker (e.g. `personalization_audit → dashboard`, `_metrics_io → security_scanner`).
- ⚠️ Adds ~80 LoC of fixture setup per round-trip test (seeded signals + parse + dual assert). Mitigated by extracting a `_build_min_fixture(tmp_path)` helper in `tests/integration/conftest.py` for reuse.
- ⚠️ If a future rubric change demotes one of the five seeded signals enough to drop below 30, the test will fail with a clear "fixture floor not cleared" message — the fix is to seed one more signal, not to lower the floor.

**Rejected alternatives:**
- **Refactor `tests/e2e/test_verify_health_dashboard.py` to use `write_dashboard()`**. Rejected because that test verifies the **verify-stage** behavior against engineered deltas; coupling its fixtures to the renderer would entangle two unrelated test concerns.
- **Single assertion (`producer_score == parsed_score` only)**. Rejected during Round 2: would catch Bug 2 but the validator showed the "non-zero" clause was decorative without a floor; pinning the floor turns it into a real safety net.
- **Defer**. Rejected because Bug 2 demonstrated the gap is load-bearing.

**Source:** Interview #1, amended Interview #5

## 🏗️ Technical Design

### Current state (relevant code)

| File | Lines | Today's behavior |
|------|------:|------------------|
| `src/harness_maker/readiness.py` | 722, 753-759 | `metrics = obs / "metrics.jsonl"`; `sample_size = sum(1 for line in _read_text(metrics).splitlines() if line.strip())`. Ignores rotation. |
| `src/harness_maker/ai_readiness.py` | 141 | `return {"structural": structural_score, "signals_failed": signals_failed}` |
| `src/harness_maker/cli.py` | 862, 945 | Reads `structural['structural']` / `structural.get('structural', 0)` for the print line. |
| `src/harness_maker/observability/dashboard.py` | 87 | `structural_score = _coerce_score(structural.get("score"))` — already correct against the proposed schema. |
| `tests/unit/test_ai_readiness.py` | 335-366 | Three tests assert the producer schema with the old key name `"structural"`. |
| `tests/unit/test_observability_dashboard.py` | 22-26, 75-80, 99-105 | Fixtures already use `"score"` — no changes needed. |
| `src/harness_maker/_metrics_io.py` | 21-45 | `_candidate_files(obs_dir, days)` returns rotated files newest-first with legacy fallback. Already shipped, already used by `security_scanner` + `cache_diagnostics`. |

### Affected components

- `harness_maker.readiness` — Phase 1 (both `metrics_jsonl_present` + `metrics_has_samples` signals in `_dim_observability_setup`)
- `tests/unit/test_readiness.py` — Phase 1 (2 new paired regression tests)
- `harness_maker.ai_readiness` — Phase 2 (producer key rename)
- `harness_maker.cli` — Phase 2 (two print sites at lines 862, 945)
- `tests/unit/test_ai_readiness.py` — Phase 2 (3 schema assertions updated)
- `tests/integration/test_health_dashboard_roundtrip.py` — Phase 2 (NEW; 2 test cases)
- `tests/integration/conftest.py` — Phase 2 (NEW; `_build_min_fixture` helper)
- Version files × 5 + `CHANGELOG.md` — Phase 3

### Data flow (post-fix)

```
project/.claude/observability/
  metrics-2026-05-10.jsonl    ─┐
  metrics-2026-05-11.jsonl     ├─→ _candidate_files(obs, days=365)
  metrics-2026-05-12.jsonl     │       │
  metrics.jsonl  (legacy)     ─┘       └─→ sum line counts
                                              │
                                              └─→ metrics_has_samples signal


run_structural()  →  {"structural": {"score": 81, "signals_failed": [...]}}
                                              │
                                              ├─→ cli.py: print structural['score']
                                              │
                                              └─→ write_dashboard()
                                                      │
                                                      └─→ dashboard.md: "score: 81 / 100"
```

### Design decisions (linked to ADRs)

- Reuse `_candidate_files` rather than reimplementing the rotation walk (ADR-103 in `_metrics_io.py`). Bug 1 fix is 4 lines of net change.
- Producer-side rename for Bug 2 (ADR-001) preserves the cleaner schema.
- Round-trip contract test (ADR-002) lives in `tests/integration/` not `tests/unit/` because it intentionally exercises multiple modules together.

### API changes

- **Internal**: `run_structural()` return key renamed `"structural"` → `"score"`. Internal to the `health` + `health-finalize` CLI pipeline; no public API.
- **External**: none. The dashboard.md rendered format is unchanged (it already expected `score`).

## 📝 Implementation Plan

### Phase 1 — Bug 1: metrics rotation read (both signals in `_dim_observability_setup`)

**Scope:**
- **In**:
  - `src/harness_maker/readiness.py:734-742` (signal `metrics_jsonl_present`) — replace `metrics.is_file()` with `bool(_candidate_files(obs, days=365))`; update the diagnostic strings from `"metrics.jsonl exists" / "metrics.jsonl missing"` to `"telemetry present (N file(s))" / "no telemetry files (metrics.jsonl or metrics-YYYY-MM-DD.jsonl)"` and update the suggestion text to not falsely recommend `/hm:make` on a project that already has rotated telemetry
  - `src/harness_maker/readiness.py:753-770` (signal `metrics_has_samples`) — replace single-file line-count with `sum(len(_read_text(p).splitlines()) for p in _candidate_files(obs, days=365))` (with empty-line filter as today)
  - Add `from ._metrics_io import _candidate_files` import at the top of readiness.py
  - `tests/unit/test_readiness.py` — add 2 paired regression tests:
    - `test_observability_setup_metrics_jsonl_present_with_rotated_only`: dated files only (no `metrics.jsonl`) → both `metrics_jsonl_present` and `metrics_has_samples` PASS
    - `test_observability_setup_metrics_counts_across_rotation`: dated files (3 entries) + legacy `metrics.jsonl` (2 entries) → total 5 entries, `metrics_has_samples` PASS
- **Out**: any change to the threshold (stays at `>= 5`), any change to other dimensions in `readiness.py`, any change to `_metrics_io.py` itself

**Exit criterion:**
```bash
uv run pytest tests/unit/test_readiness.py -v -k metrics
# both new tests pass; existing test_observability_setup_metrics_* tests still pass
```
Then end-to-end smoke on this repo:
```bash
uv run python -m harness_maker.cli health . --json-output /tmp/h.json
python -c "import json; s=json.load(open('/tmp/h.json'))['structural']['signals_failed']; \
  assert 'observability_setup:metrics_has_samples' not in s, s; \
  assert 'observability_setup:metrics_jsonl_present' not in s, s"
# expected: both signals out of signals_failed
```

**Risk:** low — single function, clear reuse of an existing util that two other modules already depend on. The diagnostic-string update is a UX cleanup; no API contract change.

**Rollback point:** revert Phase 1 commit; nothing else depends on it.

### Phase 2 — Bug 2: producer-side rename + round-trip contract test

**Precondition (run BEFORE editing):**
```bash
rg -l 'structural.*structural' tests/
# Must return empty OR an enumerated list. Each match must be triaged:
# (a) snapshot/golden fixture that needs regen → record in Phase 2 in-scope file list, AND
# (b) prose comment referencing the old schema → update in this phase
# This precondition was moved from a Phase 3 conditional per validator critique 3.
```

**Scope:**
- **In**:
  - `src/harness_maker/ai_readiness.py:5-6, 108, 141` — update docstring + rename return key `"structural"` → `"score"`
  - `src/harness_maker/cli.py:862, 945` — change `structural['structural']` / `structural.get('structural', 0)` to use `'score'`
  - `tests/unit/test_ai_readiness.py:335-366` — update assertions to expect the new key
  - Any files surfaced by the precondition grep above (likely zero; appended to scope at execute-time)
  - NEW `tests/integration/test_health_dashboard_roundtrip.py` with TWO test cases:
    1. **`test_dashboard_roundtrip_preserves_structural_score`** — builds fixture via `_build_min_fixture(tmp_path)` (seeded with the 5 signals enumerated in ADR-002 to clear `MIN_FIXTURE_SCORE = 30`); calls real `run_structural()` → real `write_dashboard()` → `parse_dashboard()`; asserts BOTH `producer_score >= 30` AND `parsed_score == producer_score`
    2. **`test_dashboard_roundtrip_catches_producer_key_drift`** — monkey-patches `run_structural` to return the OLD `{"structural": <int>, "signals_failed": [...]}` shape; asserts the round-trip flow renders `score: 0 / 100` and the equality assertion would catch it (uses `pytest.raises(AssertionError)` on the equality check). Proves ADR-002's stated purpose.
  - NEW `tests/integration/conftest.py` with `_build_min_fixture(tmp_path)` helper for reuse across future integration tests
- **Out**: `dashboard.py` (no changes needed — already correct), `tests/unit/test_observability_dashboard.py` (no changes needed — already uses `"score"`), `tests/e2e/test_verify_health_dashboard.py` (intentionally unchanged per ADR-002 rejected alternative)

**Exit criterion:**
```bash
# 1. Unit + integration tests
uv run pytest tests/unit/test_ai_readiness.py tests/unit/test_observability_dashboard.py tests/integration/test_health_dashboard_roundtrip.py -v
# all pass; both new round-trip cases pass

# 2. Drift-catch proof: temporarily revert ai_readiness.py:141 to the old key, re-run integration test
git stash  # save fix
sed -i 's/"score": structural_score/"structural": structural_score/' src/harness_maker/ai_readiness.py
uv run pytest tests/integration/test_health_dashboard_roundtrip.py::test_dashboard_roundtrip_preserves_structural_score -v
# expected: FAIL on the equality assertion (proves the test catches the regression)
git checkout src/harness_maker/ai_readiness.py
git stash pop

# 3. End-to-end smoke
uv run python -m harness_maker.cli health . --json-output /tmp/h.json
uv run python -m harness_maker.cli health-finalize . --scores-json /tmp/h.json
grep -E "^score:" .claude/observability/dashboard.md
# expected: "score: <N> / 100" with N matching the structural score in /tmp/h.json — NOT "score: 0 / 100"
```

**Risk:** medium — touches the internal JSON contract of `.health.tmp.json` between `health` and `health-finalize`. Mitigated by: (a) both subcommands updated in one phase, (b) precondition grep surfaces any stale snapshot references before edit, (c) the new round-trip test fails loudly if the contract drifts again, (d) drift-catch sub-test proves the round-trip catches the exact regression class.

**Rollback point:** revert Phase 2 commit; Phase 1 stands.

### Phase 3 — Version bump 0.13.1 + CHANGELOG

> Snapshot grep moved to Phase 2 precondition per validator critique 3.

**Scope:**
- **In**:
  - `.claude-plugin/plugin.json` — version `0.13.0` → `0.13.1`
  - `.cursor-plugin/plugin.json` — same
  - `.codex-plugin/plugin.json` — same
  - `pyproject.toml` — same
  - `src/harness_maker/__init__.py` — `__version__` same
  - `CHANGELOG.md` — add `## 0.13.1` entry listing: Bug 1 (both signals), Bug 2 (producer-side rename), the new round-trip contract test, and the impact on `.health.tmp.json` schema (one key rename, internal-only)
- **Out**: `uv.lock` regen (not needed — no dependency changes); snapshot regen (handled in Phase 2 precondition)

**Exit criterion:**
```bash
grep -c "0.13.1" .claude-plugin/plugin.json .cursor-plugin/plugin.json .codex-plugin/plugin.json pyproject.toml src/harness_maker/__init__.py
# expected: 5 (one per file)
grep -q "^## 0.13.1" CHANGELOG.md
uv run pytest -x --tb=short
# full test suite green
```

**Risk:** low — version bump is mechanical and CLAUDE.md §버전업 정책 is the canonical procedure.

**Rollback point:** revert Phase 3 commit; Phases 1+2 stand and could be released as a separate patch.

## 🧪 Testing Strategy

| Layer | What | Where |
|-------|------|-------|
| Unit (regression for Bug 1) | `_dim_observability_setup`: BOTH `metrics_jsonl_present` and `metrics_has_samples` PASS when only dated files exist (no canonical `metrics.jsonl`) | `tests/unit/test_readiness.py` (extend) |
| Unit (regression for Bug 1) | `_dim_observability_setup`: `metrics_has_samples` counts across rotation when dated + canonical both present | `tests/unit/test_readiness.py` (extend) |
| Unit (update for Bug 2) | `test_run_structural_returns_split_schema` and siblings assert the new `"score"` key | `tests/unit/test_ai_readiness.py:335-366` |
| Integration (contract floor — Bug 2 + ADR-002) | Real `run_structural()` → real `write_dashboard()` → `parse_dashboard()` round-trip; `producer_score >= MIN_FIXTURE_SCORE (=30)` AND `parsed_score == producer_score` | `tests/integration/test_health_dashboard_roundtrip.py::test_dashboard_roundtrip_preserves_structural_score` (new) |
| Integration (drift-catch proof — ADR-002) | Monkey-patches producer to return the OLD `{"structural": <int>}` shape; asserts the round-trip equality check would FAIL — proves the test catches the exact bug class | `tests/integration/test_health_dashboard_roundtrip.py::test_dashboard_roundtrip_catches_producer_key_drift` (new) |
| Integration (shared fixture) | `_build_min_fixture(tmp_path)` seeds the 5 signals enumerated in ADR-002 to deterministically clear the floor | `tests/integration/conftest.py` (new) |
| Smoke (manual, end-of-PR) | Run `/hm:health` on this repo; confirm dashboard renders the real number, not 0; both observability signals out of `signals_failed` | manual; recorded in PR description |
| Full suite | `uv run pytest -x --tb=short` | CI |

No e2e changes — the existing `tests/e2e/test_verify_health_dashboard.py` continues to use its own fixture builder, by design (ADR-002 rejected alternative).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `.health.tmp.json` consumed by an undocumented external tool that breaks on the key rename | low | medium | The file path is under `.claude/observability/.health.tmp.json` and is rewritten on every `health` invocation. No documented external consumers. PR description calls out the schema change; CHANGELOG documents it. |
| `_candidate_files(obs, days=365)` skips files older than 365 days, so a year-stale project would still report `metrics_has_samples = false` | low | low | The signal's failing message reads "Use Claude Code for ≥ 5 turns" — encouraging stale projects to fail is arguably the intent. If a real user hits this, raise `days` further (cheap follow-up). |
| Round-trip test becomes flaky if a future deterministic signal turns non-deterministic (e.g. timestamp injection) | low | medium | Test passes `generated_at` fixed in the renderer call, mirroring existing dashboard tests. New fixture project uses only structural signals that don't depend on time. |
| Test-quality debt: `tests/e2e/test_verify_health_dashboard.py` still bypasses the real renderer | known | low | Out of scope for this PLAN (per ADR-002 rejected alternative). The new round-trip test addresses the load-bearing concern (renderer↔producer drift). E2E refactor remains a separate concern. |
| Snapshot tests reference the old `"structural"` inner key in JSON fixtures | medium | low | Phase 2 **precondition** (not Phase 3 conditional, per validator critique 3): `rg -l 'structural.*structural' tests/` before edit; any matches triaged into Phase 2 in-scope. |

## ✅ Success Criteria

- [x] Phase 1 exit: BOTH `metrics_jsonl_present` and `metrics_has_samples` signals PASS against this very repo (which has rotated telemetry today) → `observability_setup` dimension no longer reports the "Install the PostToolUse telemetry hook" misleading recommendation.
- [x] Phase 2 precondition: `rg -l 'structural.*structural' tests/` empty OR matches enumerated + handled in Phase 2 scope.
- [x] Phase 2 exit: `.claude/observability/dashboard.md` rendered by `/hm:health` shows `score: <real-N> / 100` for this repo (not `0 / 100`).
- [x] Phase 2 exit: `test_dashboard_roundtrip_preserves_structural_score` passes with floor + equality assertions; `test_dashboard_roundtrip_catches_producer_key_drift` proves the test catches the regression.
- [x] Phase 2 exit: drift-catch sub-step from the exit-criterion block (temporary revert + re-run) shows the floor or equality assertion firing.
- [x] Phase 3 exit: all 5 version files report `0.13.1`; CHANGELOG documents both bugs, the contract test, and the `.health.tmp.json` schema rename.
- [x] Full suite: `uv run pytest -x --tb=short` green at the end of each phase.
- [x] Manual smoke: re-run `/hm:health` on this repo at PR time — structural score reported correctly + observability_setup dimension at full 100/100.
- [x] No regression in `/hm:verify` (Phase 3 of /hm:verify continues to read the rendered dashboard correctly).

## 🔍 Plan Validation

**Validator outcome**: NEEDS_REVISION_RESOLVED — plan-validator subagent returned NEEDS_REVISION with three findings; all three resolved in Interview Round 2 before write.

| # | Critique (severity) | Resolution | Trace |
|---|---------------------|------------|-------|
| 1 | warning: Phase 1 fixes only one of two rotation-blind signals in the same function | Phase 1 scope expanded to include both `metrics_jsonl_present` (lines 734-742) and `metrics_has_samples` (lines 753-770); Executive Summary impact estimate revised 25 → 50 points; paired regression tests added | Interview #4 |
| 2 | warning: Round-trip test could be placebo without a fixture floor (score=0 fixture → `non_zero` assertion vacuous) | ADR-002 amended with `MIN_FIXTURE_SCORE = 30`, fixture composition pinned (5 seeded signals), assertion split into floor + equality; added 2nd test case that monkey-patches old shape to prove drift-catch | Interview #5 |
| 3 | suggestion: Phase 3 conditional snapshot grep was non-actionable (`tests/snapshots/` may not exist) | Moved to Phase 2 **precondition** with widened root (`rg -l 'structural.*structural' tests/`); risk register entry updated | applied directly, no separate interview round |

**Clean categories from validator**: risk-register, rollback-strategy, adr-completeness, spec-alignment, missing-interview-rounds.

**No further follow-up rounds.** Plan is committed for execute.
