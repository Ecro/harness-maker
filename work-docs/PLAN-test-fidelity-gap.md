---
type: plan
task_slug: test-fidelity-gap
status: complete
created: 2026-05-19
tags: [harness-maker, plan, testing, boundary-parse, fidelity-gap]
research_doc: "[[RESEARCH-test-fidelity-gap]]"
interview_rounds: 3
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Layer 1 only: boundary-parse tests for 5 file types via LIVE render; advisory CI + manual runbook step."
---

# PLAN — Test Fidelity Gap (Layer 1)

## 🎯 Executive Summary

**TL;DR**: Add a boundary-parse test layer (`tests/integration/test_boundary_*.py`) that runs the real `harness_maker.render.render` into a `tmp_path` and pipes the rendered output through the *real* consumer parser for each of the five most-incident-prone file types. Tests are gated by `INTEGRATION=1`, do not block PR merge, and run automatically on tag push as an advisory `release.yml` step whose result is posted to the GitHub Release page. They are also required as a manual step in the release runbook before `git tag` push.

**What changes:**
- New test module set: `tests/integration/test_boundary_hooks_json.py`, `_codex_toml.py`, `_harness_yaml.py`, `_cursor_mdc.py`, `_settings_json.py`.
- Shared `conftest` helper `rendered_harness(tmp_path, **overrides)` that builds `ProjectProfile + InterviewAnswers`, calls `synthesize` + `render`, and returns the rendered tree path. Registers a `boundary_negative` pytest marker.
- `.github/workflows/release.yml` — non-blocking advisory job that runs the boundary suite on tag push and posts the result to the GitHub Release body.
- Documentation: `CLAUDE.md` `## 릴리스 절차 (race-free)` adds the boundary-test step adjacent to the 5-file version sync.

**Why:** 30+ `fix(...)` commits in the last 3 months trace to one failure class — "Python view of the artifact is intact, but the real consumer (Claude Code / Cursor / Codex / `jq` / `tomllib`) disagrees." Unit and snapshot tests cannot catch this because they verify what we wrote, not how the consumer parses it. See RESEARCH-test-fidelity-gap.md §🛠️ Approach A and §⚠️ Pitfalls for the evidence table (incidents 1-4 are all Layer-1-catchable; incidents 5-8 are not, by RESEARCH's own admission, and remain deferred to Layer 2/3 follow-up PLANs).

**Key decisions (links to ADRs below):**
- ADR-001: Phasing — Layer 1 first, Layer 2/3 deferred to follow-up PLANs.
- ADR-002: Execution model — every test calls `render.render()` LIVE (no checked-in fixtures).
- ADR-003: CI gating — no PR merge block; release.yml runs the suite as advisory only.
- ADR-004: Run trigger — advisory `release.yml` job on tag push (posts result to GitHub Release) **and** release runbook manual step.
- ADR-005: First scope — 5 file types in one PLAN (hooks.json, Codex TOML, harness.yaml, Cursor .mdc, settings.json).

**Estimated impact**: 4 phases, 1-2 weeks wall clock. Test wall time ~3 minutes (estimate — to be measured in Phase 0 against the existing `test_render_idempotent_byte_identical` baseline; cited number is repeated below and should be replaced by the measurement). Zero CI cost on PRs; ~3 minutes per release tag. One paragraph added to CLAUDE.md.

## 📚 Prior Work

- **RESEARCH-test-fidelity-gap** (2026-05-19): identifies three-layer defense; this PLAN scopes Layer 1 only.
- **PLAN-health-plugin-bugs-2026-05** ADR-002: round-trip contract test pattern with floor + equality assertion. The boundary-parse layer generalizes this pattern across file types and consumer parsers.
- **PLAN-fresh-install-health-baseline** introduced `tests/integration/test_fresh_install_readiness.py::test_render_idempotent_byte_identical` — exactly the pattern of "LIVE render + assert on output" we are extending here. Layer 1 is the same template, parameterized over file type + parser. Phase 0 uses this test for the wall-time baseline measurement.
- **PLAN-second-brain-write-failure** exemplifies the precise failure class this PLAN closes: a multi-doc YAML provenance frontmatter broke every `yaml.safe_load`-only reader, undetected because the unit fixture hand-built a single-doc file.
- `.claude/memory/failures.md` entries that drive the 5-file-type priority:
  - `[fail:test] unit-fixture-skips-renderer-frontmatter` (2026-05-17) → harness.yaml
  - `[fail:design] producer-consumer-schema-drift-in-same-process-pipeline` (2026-05-17) → all
  - `[fail:design] phantom-key-on-rerender-breaks-idempotency` (2026-05-19) → harness.yaml (permissions.ask)
  - `[fail:design] yaml-empty-list-renders-null` (2026-05-11) → harness.yaml (targets / folders)
  - `[fail:render] yaml-colon-in-unquoted-frontmatter-description` (2026-05-10) → Cursor .mdc + SKILL.md frontmatter
  - `[fail:render] toml-section-header-variable-injection` (2026-05-10) → Codex TOML
  - `[fail:design] codex-helpers-ignore-user-config` (2026-05-11) → Codex TOML
  - `[fail:render] wrapup-eof-append-outside-marker` (2026-05-17) → settings.json + memory files (block-merge)
- `.claude/memory/wiki.md` `[wiki:pattern] round-trip-contract-test-floor-plus-equality` (2026-05-17) and `[wiki:pattern] test-fixture-must-mirror-renderer` (2026-05-17) — already-codified patterns this PLAN extends to four more file types.

## 🎙️ Interview Transcript

| # | Round | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | 1 | Phasing | 3-layer 한 번에 vs Layer 1 first vs Layer 3 first | Layer 1 first | 1-2주, ROI 빠름. 후속 PLAN 으로 Layer 2/3. | ADR-001 |
| 2 | 1 | Architecture | Layer 1 execution model: LIVE render vs hybrid vs fixture | LIVE render 매 테스트 | fixture-drift 원천 차단. ~3분 wall clock estimate, INTEGRATION=1 gate. | ADR-002 |
| 3 | 1 | Risk | CI gating: Layer 1 block / Layer 1+2 block / 전부 advisory | 전부 advisory | False-positive 비용 회피 우선. ADR-004 가 안전망. | ADR-003 |
| 4 | 1 | Risk | Canary cadence: pre-release / nightly / PR-label | Pre-release tag only | 후속 PLAN scope. 본 PLAN informational. | (out of scope) |
| 5 | 2 | Risk | Advisory 정책 트리거: release runbook / release.yml advisory / pre-commit hook / end | Release runbook 수동 | Round 3 에서 W2 로 보강. | ADR-004 (v1) |
| 6 | 2 | Scope | 첫 PR file type 우선순위: RESEARCH 5종 / 3종 / end | RESEARCH 5종 | 모든 Layer-1-catchable incident class 커버. | ADR-005 |
| 7 | 3 | Risk | (validator W2) ADR-004 수정: release.yml advisory step 추가 / Consequences 자체 시인 / end | release.yml advisory step 추가 | Layer 1 = pure parser, no LLM, no secret. tag push 자동 실행 + GitHub Release post. skip-silent 비대칭 해소. | ADR-004 (v2) |

**Exit reason**: All architectural slots resolved; plan-validator's structural critique (W2) addressed via Round 3. Remaining nits absorbed into mechanical rewrites (signatures, wording, prose hygiene) without further interview rounds.

**Assumptions noted without asking:**
- **Invariant authoring style**: pytest functions (not declarative DSL). Common-ground: extends existing `tests/integration/` convention.
- **`pytest` gating**: `INTEGRATION=1` env var, not pytest markers (markers used internally for the `boundary_negative` sentinel only). Common-ground: matches `test_package_artifacts.py`, `test_second_brain_e2e.py`.
- **Regression-fixture back-fill** of `failures.md` count:3+ entries: out of scope. `pending-proposals.md` continues to be the curator's todo list; Layer 1 provides the substrate for back-fill in a follow-up PLAN.
- **Runbook artifact target**: amend `CLAUDE.md` `## 릴리스 절차 (race-free)` only. Do NOT create `docs/release-runbook.md` (does not exist; would split the source of truth).

## 📐 Architecture Decision Records

### ADR-001: Layer 1 ships first; Layer 2/3 deferred to follow-up PLANs
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 1)
**Context:** RESEARCH-test-fidelity-gap recommended a three-layer defense (boundary-parse + `/hm:health` invariant lint + transcript canary). Bundling all three is ~6 weeks; Layer 1 alone covers the highest-volume failure class — the "Python sees X, consumer sees Y" pattern in every fix in §📚 Prior Work.
**Decision:** This PLAN delivers Layer 1 only. Layer 2 (`/hm:health` invariant lint extension) and Layer 3 (transcript canary with LLM judge) become their own PLANs after Layer 1 ships and the maintainer measures incident drop-rate.
**Consequences:**
- ✅ Fast ROI: 1-2 weeks to close the highest-volume failure class.
- ✅ Time to measure: Layer 1's effect on `fix(...)` commit rate informs Layer 2/3 prioritization.
- ⚠️ Class 3-5 failures (LLM interpretation bugs, hook output-channel mismatches, user-runbook execution gaps) remain unaddressed. Examples: `[fail:hook] sessionstart-additionalcontext-invisible` (Layer 1 cannot detect — both JSON shapes are valid), `[fail:design] readme-prompt-embeds-built-in-slash-as-runbook` (Layer 3 transcript canary required).
**Rejected alternatives:**
- "Three layers in one PLAN" — 6-week scope risks the layer never shipping; smaller PLAN with measurable outcome preferred.
- "Layer 3 first" — LLM-judge infrastructure (rubric, transcript capture, judge model, subscription budget) is the heaviest layer; deferring it lets us learn from Layer 1.
**Source:** Interview #1

### ADR-002: Boundary-parse tests use LIVE `render()` per session-scoped fixture
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 1)
**Context:** Two viable execution models: (a) every test calls the real renderer, parses live output; (b) checked-in fixture files, parsed in test. Model (b) is faster but reintroduces fixture-vs-production drift (`[fail:test] unit-fixture-skips-renderer-frontmatter`).
**Decision:** Each `rendered_harness(preset, locale, targets)` fixture call invokes `harness_maker.synthesize.synthesize(profile, answers, preset)` to build a `Blueprint`, then `harness_maker.render.render(blueprint, target_dir=tmp_path)`. The fixture is **session-scoped** per `(preset, locale, targets, **answer_overrides)` tuple so multiple boundary tests sharing the same configuration amortize render cost.
**Consequences:**
- ✅ Fixture-drift impossible by construction.
- ✅ Reuses existing `tests/integration/conftest.py` patterns; mirrors `test_render_idempotent_byte_identical`.
- ⚠️ ~3-minute total wall clock estimated for the 5-file-type suite; gated by `INTEGRATION=1`. To be replaced with measurement in Phase 0.
- ⚠️ Test failure root cause is harder to localize (render bug vs parse bug); mitigated by separating render-step from parse-step assertions in each test.
**Rejected alternatives:**
- "Hybrid (golden + parse-only)" — golden test still has fixture-drift risk; cascading failure on golden break.
- "Checked-in fixtures only" — directly contradicts the PLAN premise.
**Source:** Interview #2

### ADR-003: No PR merge block; release.yml advisory only
**Status:** Accepted (2026-05-19, via /hm:plan interview Rounds 1 + 3)
**Context:** Boundary tests could block PR merge, block release only, or be fully advisory. Maintainer prioritizes avoiding false-positive PR blocks; plan-validator's W2 highlighted that fully-silent advisory has no forcing function (unlike the 5-file version sync, which is forced by Marketplace visibility).
**Decision:** No CI step blocks PR merge. On tag push, a non-blocking `release.yml` job (see ADR-004) executes the boundary suite as advisory and posts the result to the GitHub Release page — making the skip mode visible.
**Consequences:**
- ✅ Zero PR friction.
- ✅ Skip is visible at release time via the Release page section.
- ⚠️ Maintainer can still ship despite a red advisory; discipline remains required to act on it.
**Rejected alternatives:**
- "Block PR merge on boundary tests" — ~3-minute LIVE render multiplies every PR; false-positive risk on invariant evolution.
- "Layer 1 + Layer 2 block" — Layer 2 out of scope.
**Source:** Interview #3 + Interview #7

### ADR-004: Two safety nets — release.yml advisory + release runbook manual step
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 5 + 7)
**Context:** Round 2's original ADR-004 placed the entire safety net on a release runbook manual step, justified by analogy to the 5-file version sync. plan-validator (W2) correctly observed the analogy is broken: the 5-file sync has a forcing function (Marketplace shows wrong version visibly), but a skipped boundary-test step is silent. The "ANTHROPIC_API_KEY required" rejection rationale was also wrong — Layer 1 calls only `json.loads` / `tomllib.loads` / `yaml.safe_load_all`, no LLM, no secret needed.
**Decision:** Two layers:
1. **Automated (no secret):** Add a non-blocking job to `.github/workflows/release.yml` triggered on `refs/tags/v*` push. The job runs `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v --tb=short` and appends a "Boundary tests" section to the GitHub Release body via `gh release edit --notes-file`. Job exit status does NOT block `publish-pypi` or `github-release` — both succeed independently, advisory by design.
2. **Manual:** `CLAUDE.md` `## 릴리스 절차 (race-free)` gains a step adjacent to the 5-file version sync: before `git tag -a vX.Y.Z`, run the boundary suite locally.
**Consequences:**
- ✅ Zero PR cost; ~3 minutes per release tag for the advisory job.
- ✅ Skip mode is visible (red section in the GitHub Release).
- ✅ Local manual step gives faster pre-tag feedback.
- ⚠️ Discipline still required to act on a red advisory; the visibility just removes the silent-skip class.
**Rejected alternatives (after Round 7):**
- "Runbook step only" — Round 5's original choice; rejected after Round 7 evidence that release.yml needs no secret for parser-only tests.
- "Pre-commit hook" — ~30s commit overhead unacceptable for a release-time concern.
**Source:** Interview #5 + Interview #7

### ADR-005: First-scope = 5 file types in one PLAN
**Status:** Accepted (2026-05-19, via /hm:plan interview Round 2)
**Context:** RESEARCH recommends 5 file types based on incident frequency. Smaller scope (3 types) ships sooner but leaves known Layer-1-catchable incident classes uncovered.
**Decision:** This PLAN covers all 5: `hooks.json` (Cursor lowercase + Claude PascalCase dual-schema), `.codex/agents/*.toml` + `.codex/hooks.json` + `.codex/config.toml` (Rust `toml` semantics, dotted-key invariants), `.claude/harness.yaml` (multi-document YAML via `io_utils.load_harness_yaml`), `.cursor/rules/*.mdc` (frontmatter strict-schema), `.claude/settings.json` (pure JSON, permissions shape).
**Consequences:**
- ✅ Every **Layer-1-catchable** incident class from the last 3 months lands in scope. (Class 3-5 failures — LLM interpretation, hook channel, runbook gap — remain deferred to Layers 2/3 per ADR-001. See ADR-001 Consequences for the explicit list.)
- ✅ Single PLAN review cost.
- ⚠️ Risk of scope creep; mitigated by per-file-type phase structure with independent exit criteria.
**Rejected alternatives:**
- "3 types only" — `.mdc` and `settings.json` are lower-incident but their omission would leave the PLAN incomplete.
**Source:** Interview #6

## 🏗️ Technical Design

### Current State
- `tests/integration/` contains 12 modules. Most call internal functions and assert on Python values.
- `tests/integration/test_health_dashboard_roundtrip.py` is the closest precedent: producer → consumer in one test with floor + equality.
- `tests/integration/test_fresh_install_readiness.py::test_render_idempotent_byte_identical` proves the LIVE-render approach works and is the wall-time baseline.
- `INTEGRATION=1` env var already gates slow integration tests via `tests/integration/conftest.py`.
- Public callables (verified at render.py:820 and synthesize.py:595):
  - `render(blueprint: Blueprint, target_dir: Path, *, dry_run=False, freeze_time=None, merge_paths=None, merge_reports=None) -> list[Path]`
  - `synthesize(profile: ProjectProfile, answers: InterviewAnswers, preset: Preset | None = None) -> Blueprint`
  - `ProjectProfile` defined in `harness_maker.models`; default helper for tests should mirror what `test_render_idempotent_byte_identical` constructs.
- `.github/workflows/release.yml` already has `quality-gate`, `build`, `publish-testpypi`, `publish-pypi`, `github-release` jobs. ADR-004's new job sits after `github-release` (or in parallel; Phase 4 designs the exact placement).

### Affected Components
- **New**: `tests/integration/test_boundary_hooks_json.py`, `_codex_toml.py`, `_harness_yaml.py`, `_cursor_mdc.py`, `_settings_json.py`, `test_boundary_meta.py`.
- **New (shared)**: `tests/integration/_boundary_helpers.py` for the session-scoped `rendered_harness` fixture, default `ProjectProfile + InterviewAnswers` builder, parser helpers, and pytest marker registration.
- **Modified**: `tests/integration/conftest.py` — register `boundary_negative` pytest marker.
- **Modified**: `.github/workflows/release.yml` — add `boundary-advisory` job triggered on tag push.
- **Modified**: `CLAUDE.md` `## 릴리스 절차 (race-free)` section.

### Dependencies
- No new third-party dependencies. Parsers in scope are stdlib (`json`, `tomllib`, `yaml`) plus `harness_maker.io_utils.load_harness_yaml`.
- For `.mdc`, no Rust binding available; Python validator against an explicit frontmatter allow-list (see Phase 3 + .mdc row of File-type table).

### Architecture / Data Flow

```python
# tests/integration/_boundary_helpers.py
from harness_maker.models import ProjectProfile, InterviewAnswers
from harness_maker.synthesize import synthesize
from harness_maker.render import render

@pytest.fixture(scope="session")
def rendered_harness(tmp_path_factory):
    """Cache rendered trees per (preset, locale, targets, **overrides) tuple."""
    cache: dict[tuple, Path] = {}
    def _build(*, preset, locale, targets, **overrides) -> Path:
        key = (preset, locale, tuple(targets), tuple(sorted(overrides.items())))
        if key in cache:
            return cache[key]
        profile = _default_profile()  # mirror test_render_idempotent_byte_identical
        answers = InterviewAnswers(preset=preset, locale=locale, targets=list(targets), **overrides)
        blueprint = synthesize(profile, answers, preset=preset)
        target_dir = tmp_path_factory.mktemp(f"hm-{preset}-{locale}-{len(cache)}")
        render(blueprint, target_dir)
        cache[key] = target_dir
        return target_dir
    return _build

# tests/integration/test_boundary_<filetype>.py
@pytest.mark.skipif(os.environ.get("INTEGRATION") != "1", reason="LIVE render gated")
def test_boundary_positive(rendered_harness):
    root = rendered_harness(preset="Side", locale="en", targets=["claude-code","cursor","codex"])
    raw = (root / "<expected-path>").read_text()
    parsed = REAL_CONSUMER_PARSER(raw)   # ← THE BOUNDARY
    assert STRUCTURAL_INVARIANTS(parsed)

@pytest.mark.boundary_negative
@pytest.mark.skipif(os.environ.get("INTEGRATION") != "1", reason="LIVE render gated")
def test_boundary_<filetype>_rejects_<violation>(tmp_path):
    """Inject the invariant violation at byte level — independent of any production template."""
    bad_bytes = build_synthetic_bad_<filetype>()
    with pytest.raises(<ConsumerParseError>):
        REAL_CONSUMER_PARSER(bad_bytes)
```

**Key clarifications driven by validator W1 + W5 + W6:**
- The fixture builds `ProjectProfile` via a local helper (`_default_profile()`) that mirrors what `test_render_idempotent_byte_identical` already constructs. Phase 0 commits the exact body of this helper.
- Negative tests use synthetic bytes (`build_synthetic_bad_<filetype>`), not template overrides. This makes negatives **template-state-independent** — they fire green when the validator correctly rejects the violation, and red when it accepts it.
- Negatives are identified by the `@pytest.mark.boundary_negative` marker, registered in `tests/integration/conftest.py`. Phase 4's meta-test enumerates collected tests by this marker.

**Parser choice per file type:**

| File type | Parser | Why |
|-----------|--------|-----|
| `hooks.json` (Cursor lowercase + Claude PascalCase) | `json.loads` + JSON Schema validation per IDE shape | Both consumers read JSON; schemas diverge by design (CLAUDE.md §"Hook schema diverges by design"). Two positive tests, one per IDE; one negative per IDE schema violation. |
| `.codex/agents/*.toml`, `.codex/hooks.json`, `.codex/config.toml` | `tomllib.loads` + dotted-key structural assertion | Codex CLI is Rust → stricter than `tomllib`. Test asserts `[mcp_servers."name.with.dot"]` parses to a single key, not nested tables (`[fail:render] toml-section-header-variable-injection` regression). |
| `.claude/harness.yaml` | `harness_maker.io_utils.load_harness_yaml` (canonical helper) | Single source of truth. Asserts (a) `targets: []` not `null` on empty (`[fail:design] yaml-empty-list-renders-null`); (b) `permissions.ask` key not phantom-emitted (`[fail:design] phantom-key-on-rerender-breaks-idempotency`); (c) round-trip via the helper produces no warnings. |
| `.cursor/rules/*.mdc` | Custom validator: split on first `---`...`---`, `yaml.safe_load` frontmatter, assert key allow-list `{description, globs, alwaysApply}` | Cursor parser source unavailable; conservative allow-list. See Phase 3 for the explicit documentation and review cadence. |
| `.claude/settings.json` | `json.loads` + `pydantic` model mirroring Claude Code permissions/hooks/env shape | `[fail:render] wrapup-eof-append-outside-marker` adjacent class: must reject any leading non-JSON content; positive test asserts user-written `enabledPlugins` survives re-render. |

### Design Decisions (referencing ADRs)
- LIVE render every test → ADR-002.
- No PR merge block; advisory on tag push only → ADR-003 + ADR-004.
- All 5 file types in one PLAN → ADR-005.

### API Changes
None to `harness_maker.*` public API. Internal `_boundary_helpers.py` is test-only.

## 📝 Implementation Plan

### Phase 0 — Bootstrap shared fixture, marker registration, first file type (hooks.json), wall-time baseline
**Scope:**
- In: `tests/integration/_boundary_helpers.py` (new — `rendered_harness` fixture, `_default_profile()`, `build_synthetic_bad_<filetype>()` helpers, allow-list constants).
- In: `tests/integration/conftest.py` (modify — register `boundary_negative` marker per `pytest_configure(config)`; document the convention).
- In: `tests/integration/test_boundary_hooks_json.py` (new — at minimum: one positive per IDE schema + one negative per IDE schema).
- In: Phase 0 commit message includes a `time` measurement: `time INTEGRATION=1 uv run pytest tests/integration/test_fresh_install_readiness.py::test_render_idempotent_byte_identical -v` — record actual wall time and update the `~3 minutes` estimate in ADR-002 + Exec Summary + Risk row with measured value.
- Out: all other file types; `CLAUDE.md` / `release.yml` (Phase 4 work).
**Exit criterion:**
- `INTEGRATION=1 uv run pytest tests/integration/test_boundary_hooks_json.py -v` passes.
- The `boundary_negative` marker is collected: `INTEGRATION=1 uv run pytest tests/integration/test_boundary_hooks_json.py -m boundary_negative --collect-only` lists ≥1 test.
- A red-when-broken sanity check: temporarily mutate the negative-test fixture so the synthetic bad bytes match the schema → test fails (proves negative actually asserts).
- Baseline wall time recorded in commit message.
**Risk:** medium — fixture API is sticky once committed.
**Rollback point:** revert to pre-PLAN main; no production code touched.
**Note on helper API evolution:** `_boundary_helpers.py`'s `rendered_harness` signature `(preset, locale, targets, **overrides)` may need to grow in later phases (e.g., per-test answer overrides not anticipated here). Signature changes are scoped to the phase that introduces them, not a Phase 0 regression. If Phase 2 or Phase 3 reveals a missing parameter, extend the signature and document the addition in the phase's commit message; do not treat this as a Phase 0 rollback.

### Phase 1 — Codex TOML + Codex hooks.json
**Scope:**
- In: `tests/integration/test_boundary_codex_toml.py` (new — `.codex/agents/*.toml`, `.codex/config.toml`, `.codex/hooks.json`).
- Includes the dotted-key invariant: a positive test with `mcp_servers` overrides naming a server `"server.with.dot"`, asserting `parsed["mcp_servers"]["server.with.dot"]` resolves at intended depth, NOT `parsed["mcp_servers"]["server"]["with"]["dot"]`.
- Includes a `boundary_negative` test that constructs synthetic TOML bytes with an unquoted dotted server name and asserts the validator catches it.
- Out: hooks.json (Phase 0), harness.yaml (Phase 2).
**Exit criterion:** `INTEGRATION=1 uv run pytest tests/integration/test_boundary_codex_toml.py -v` passes; dotted-key positive test confirms single-key resolution; negative test confirms invariant violation is detected.
**Risk:** low — `tomllib` is well-understood; one new test module.
**Rollback point:** Phase 0.

### Phase 2 — harness.yaml multi-doc roundtrip
**Scope:**
- In: `tests/integration/test_boundary_harness_yaml.py` (new) — uses `io_utils.load_harness_yaml`. Tests:
  - Positive: round-trip via canonical helper produces no warnings, `targets`/`folders` empty cases render as `[]` not `null`.
  - Positive: `permissions.ask` not phantom-emitted across two consecutive renders (idempotency check; `merge(merge(out)) == merge(out)`).
  - `boundary_negative`: synthetic bad bytes with `targets: null` parsed via the helper → assert helper raises or warns.
- Out: Cursor and settings (Phase 3).
**Exit criterion:** `INTEGRATION=1 uv run pytest tests/integration/test_boundary_harness_yaml.py -v` passes. Each of the three failures.md regression cases (`unit-fixture-skips-renderer-frontmatter`, `yaml-empty-list-renders-null`, `phantom-key-on-rerender-breaks-idempotency`) has at least one explicit assertion.
**Risk:** low — the canonical helper exists and is correct.
**Rollback point:** Phase 1.

### Phase 3 — Cursor `.mdc` + `.claude/settings.json`
**Scope:**
- In: `tests/integration/test_boundary_cursor_mdc.py`, `tests/integration/test_boundary_settings_json.py`.
- **`.mdc` allow-list documentation** (per validator W8): the test file MUST open with an explicit comment block:

```python
"""Cursor .mdc frontmatter boundary tests.

ALLOW-LIST (frontmatter keys Cursor's parser is documented to accept):
  - description  (string)
  - globs        (string | list[string])
  - alwaysApply  (bool)

Source: <Cursor docs URL>
Retrieved: 2026-05-19
Upgrade path: Cursor parser source remains unavailable; the eventual catch
for parser drift beyond this allow-list is Layer 3 transcript canary
(deferred to a follow-up PLAN per ADR-001). Re-reconcile this allow-list
when bumping the minimum Cursor version (CLAUDE.md §Targets 정책).
"""
```

- **CLAUDE.md cross-link** (per validator W8): under §"사용자 하네스 구조" Cursor target paragraph or §"Cursor target 의 권한 매핑" footnote, add a sentence pointing at `tests/integration/test_boundary_cursor_mdc.py` as the canonical allow-list source.
- **`.mdc` positive tests**: assert (a) every rendered `.cursor/rules/*.mdc` has frontmatter with only allow-listed keys; (b) descriptions containing `: ` are double-quoted; (c) no double `---` blocks (`[fail:render] yaml-colon-in-unquoted-frontmatter-description` regression).
- **`.mdc` `boundary_negative` test**: synthesize a `.mdc` byte string with frontmatter that contains an extra key `unknown_field: value` — assert the validator rejects it via the allow-list (no dependency on any production template).
- **`settings.json` positive tests**: assert the rendered file is parseable pure JSON (no leading frontmatter prefix; the `[fail:render] wrapup-eof-append-outside-marker` adjacent class); `permissions.allow` / `.deny` shapes match the Claude Code pydantic mirror; `enabledPlugins` overrides via fixture survive re-render.
- **`settings.json` `boundary_negative` test**: synthesize bytes with a leading YAML frontmatter block (`---\nfoo: bar\n---\n` + JSON) and assert `json.loads` raises.
- Out: runbook + `release.yml` update (Phase 4).
**Exit criterion:** `INTEGRATION=1 uv run pytest tests/integration/test_boundary_cursor_mdc.py tests/integration/test_boundary_settings_json.py -v` passes. The negative tests fire red when their synthetic bad bytes are intentionally adjusted to be schema-correct (verify by temporary perturbation in PR).
**Risk:** medium — `.mdc` allow-list is conservative; risk of false negatives (Cursor reject we don't test) and false positives (key we reject that Cursor accepts). Mitigation: the docstring + CLAUDE.md cross-link make the allow-list a managed invariant, not a test internal.
**Rollback point:** Phase 2.

### Phase 4 — Release.yml advisory job + CLAUDE.md runbook + meta-test + CHANGELOG
**Scope:**
- In: `.github/workflows/release.yml` — add a new `boundary-advisory` job:
  - Trigger: `if: startsWith(github.ref, 'refs/tags/v')`.
  - Runs after `github-release` (or in parallel — Phase 4 confirms placement based on read of the current release.yml). Does NOT use `needs:` from any of `quality-gate / build / publish-testpypi / publish-pypi / github-release` so it cannot block them.
  - Steps: checkout, install `uv`, `uv sync`, `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v --tb=short 2>&1 | tee /tmp/boundary.txt`, then `gh release edit ${{ github.ref_name }} --notes-file <(cat <(gh release view ${{ github.ref_name }} --json body -q .body) <(printf '\n\n## Boundary tests\n\n') <(awk '...summarize tee output...' /tmp/boundary.txt))` (exact awk filter designed at execute time; goal: append the summary, not the entire pytest output).
  - `continue-on-error: true` on the pytest step so the job posts the result even on test failure.
- In: `CLAUDE.md` `## 릴리스 절차 (race-free)` — insert one paragraph immediately before the `git tag -a vX.Y.Z` block:

```
> **Boundary tests (pre-tag)**: Layer 1 boundary-parse tests must pass.
>
> ```
> INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py -v
> ```
>
> 이 단계는 advisory (CI 가 PR 을 막지 않음). release.yml 의 boundary-advisory 잡이 tag push 후 동일 suite 를 자동 실행 + 결과를 Release page 에 post 하므로, 로컬에서 빼먹어도 visible. 단 5-file version sync 와 같은 자리에 두는 것을 권장.
```

- In: `tests/integration/test_boundary_meta.py` (new) — three meta-assertions:
  1. **Five modules exist**: `assert (REPO_ROOT/"tests/integration").glob("test_boundary_*.py")` returns the expected 5 module paths (not including `test_boundary_meta.py` itself).
  2. **Each module has ≥1 `boundary_negative` test**: collected via `pytest --collect-only -m boundary_negative` for each module; assert count ≥ 1.
  3. **CLAUDE.md references the boundary suite**: read `CLAUDE.md` text and assert the literal substring `tests/integration/test_boundary` appears within the `## 릴리스 절차 (race-free)` section (use a small `re.search` between section headings).
- In: `CHANGELOG.md` `[Unreleased]` — bullet under `### Added`: "Layer 1 boundary-parse test suite for 5 file types (hooks.json, Codex TOML, harness.yaml, Cursor .mdc, settings.json); advisory CI on tag push + manual runbook step. See PLAN-test-fidelity-gap.md."
- Out: Layer 2 / Layer 3 (separate follow-up PLANs).

**Exit criterion:**
- `INTEGRATION=1 uv run pytest tests/integration/test_boundary_meta.py -v` passes (all three meta-assertions green).
- `act` or local YAML validation of `release.yml` shows the new `boundary-advisory` job is syntactically valid and has no `needs` dependency on publish jobs.
- `git grep -F 'Boundary tests (pre-tag)' CLAUDE.md` returns exactly one match (smoke check; the source-of-truth assertion is meta-test #3, not this grep).
**Risk:** low — documentation + meta-test + workflow YAML.
**Rollback point:** Phase 3.

## 🧪 Testing Strategy

- **The deliverable IS the test layer.** No production code in `src/harness_maker/` changes.
- **Each new test module is itself the verification.** Phase exit criteria are the test runs.
- **Negative tests required, identified by marker.** Every boundary module must contain at least one `@pytest.mark.boundary_negative` test that injects the invariant violation at byte level (synthetic bad bytes, NOT template overrides). This makes negatives template-state-independent — they fire red whenever the consumer parser stops catching the violation, regardless of whether any production template currently emits the violation. Lesson from `[fail:test] boundary-test-no-sentinel` (2026-05-09) — negatives must plant the failure condition explicitly.
- **Meta-test enforces module presence + marker presence + runbook coverage.** Phase 4's `test_boundary_meta.py` reads the filesystem + collects tests by marker + reads `CLAUDE.md`. The third assertion makes the runbook the source of truth: if a future maintainer changes the command syntax (e.g. `uv run pytest -m boundary`), the meta-test stays green as long as the substring `tests/integration/test_boundary` is present in the release section.
- **Snapshot tests stay**: byte-identical snapshot tests (`tests/snapshot/`) are independent and must continue passing. The two layers verify different properties (snapshots = byte identity across versions; boundary tests = consumer-parser correctness of the current bytes).
- **No new test for `synthesize` or `render` themselves** — those remain covered by unit + snapshot tests. The new layer assumes they execute and asks "is the output well-formed *for the consumer*."

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Maintainer ignores red advisory on Release page → regression ships | high | ADR-004's two-layer safety net (local pre-tag run + Release-page post) makes the skip mode visible. Discipline still required to *act* on visibility. |
| `.mdc` allow-list drifts vs Cursor's real parser | medium | Phase 3 docstring is the canonical source; CLAUDE.md cross-links it; Layer 3 transcript canary is the eventual catch (deferred). Allow-list explicitly version-coupled (review when bumping min Cursor version). |
| LIVE render slow (~3 min estimated) discourages local runs | medium | Session-scoped fixture caches across tests; `INTEGRATION=1` gate keeps default `pytest` fast. Phase 0 measures actual time. |
| Negative test rots (synthetic bad bytes drift from real failure shape) | low | Each negative cites the failures.md entry it regresses; reviewing negative-test commit messages against the entry keeps them anchored. |
| New file types added later → no boundary test → silent expansion of fidelity gap | low | After Phase 4, add a CLAUDE.md note: "any new file format the renderer emits needs a `test_boundary_<type>.py` module." Tracked as a pending-proposal if recurrence is observed. |
| `harness_maker.io_utils.load_harness_yaml` semantics change → harness.yaml test breaks for the wrong reason | low | Phase 2 uses the canonical helper directly; helper changes propagate by design. |
| `release.yml` advisory job posts garbled output to Release page | low | Phase 4's awk filter is designed at execute time with a sample run before committing; `continue-on-error` ensures even formatting failures don't break the publish jobs. |

## ✅ Success Criteria

- [x] `tests/integration/_boundary_helpers.py` exists; provides `invoke_make_all_targets()` (CLI-make wrapper) + parser helpers + allow-list constants. The session-scoped `rendered_harness_all_targets` fixture itself lives in `conftest.py` (pytest fixture discovery contract).
- [x] `tests/integration/conftest.py` registers the `boundary_negative` pytest marker via `pytest_configure`.
- [x] Five `tests/integration/test_boundary_*.py` modules exist (hooks_json, codex_toml, harness_yaml, cursor_mdc, settings_json).
- [x] Each module contains ≥1 positive test AND ≥1 `@pytest.mark.boundary_negative` test using **synthetic bad bytes** (not template overrides).
- [x] `tests/integration/test_boundary_meta.py` passes: enforces 5-module presence + ≥1 negative each + CLAUDE.md runbook substring.
- [x] `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py` passes locally; **total wall time ≈ 12s for 49 tests** (estimate was ~3 min — measurement is ~15× faster).
- [x] `CLAUDE.md` `## 릴리스 절차 (race-free)` references the boundary-test command before the `git tag -a vX.Y.Z` block.
- [x] `.github/workflows/release.yml` has a `boundary-advisory` job, tag-push triggered (`if: startsWith(github.ref, 'refs/tags/v')`), no `needs:` dependency on publish jobs (only on `github-release` for ordering — does not block publish), job-level + step-level `continue-on-error: true`.
- [x] CHANGELOG `[Unreleased]` entry references "Layer 1 boundary-parse test suite" and the PLAN slug.
- [x] Plan-validator outcome on the revised document = NEEDS_REVISION_RESOLVED (all 11 critiques addressed in §🔍 Plan Validation).

## 🔍 Plan Validation

**Initial validator pass (plan-validator agent, 2026-05-19): NEEDS_REVISION** (8 warnings + 2 nits).

| # | Severity | Section | Issue (summary) | Resolution |
|---|----------|---------|-----------------|------------|
| W1 | warning | Technical Design | Public callable signatures wrong (`render(spec, dest_root)` etc.) | **Fixed**: real signatures `render(blueprint, target_dir, ...)` + `synthesize(profile, answers, preset)` in §Current State + §Architecture pseudocode. |
| W2 | warning | ADR-003 + ADR-004 | Advisory-only's safety-net analogy to 5-file sync is asymmetric (skip is silent vs Marketplace-visible); release.yml advisory step rejected on incorrect "needs ANTHROPIC_API_KEY" grounds — Layer 1 has no LLM call. | **Resolved via Interview Round 7 (#7)**: ADR-004 revised to add release.yml `boundary-advisory` job on tag push (no secret needed; posts result to Release page). Manual runbook step retained. |
| W3 | warning | ADR-005 vs ADR-001 | "Every recent incident class lands in scope" contradicts ADR-001's "Class 3-5 deferred." | **Fixed**: ADR-005 Consequences re-worded to "Every **Layer-1-catchable** incident class … (Class 3-5 deferred per ADR-001)". Explicit cross-link added. |
| W4 | warning | Phase 4 + Success Criteria | `docs/release-runbook.md` doesn't exist; "or CLAUDE.md if missing" was a deferred decision. | **Fixed**: committed to amending `CLAUDE.md` only; `docs/release-runbook.md` not created. Phase 4 + Success Criteria + Affected Components updated. |
| W5 | warning | Phase 3 | Negative test tied to template state ("when SKILL.md.j2 omits the double-quote"). | **Fixed**: Phase 3 negative tests use synthetic bad bytes (`build_synthetic_bad_<filetype>`); template-state-independent. Documented in §Testing Strategy lesson reference to `[fail:test] boundary-test-no-sentinel`. |
| W6 | warning | Phase 4 meta-test | "≥1 negative test" under-specified — no programmatic recognizer. | **Fixed**: Phase 0 registers `@pytest.mark.boundary_negative` marker; Phase 4 meta-test enumerates collected tests by this marker. Phase 0 docstring documents the convention. |
| W7 | warning | Phase 4 exit criterion | Used `git grep` (not pytest assertion). | **Fixed**: Phase 4 meta-test #3 reads `CLAUDE.md` text and asserts substring within the `## 릴리스 절차` section; `git grep` retained as a soft smoke check only. |
| W8 | warning | Phase 3 `.mdc` doc | Conservative invariant set lived only in module docstring; no review cadence, no CLAUDE.md cross-link. | **Fixed**: Phase 3 scope explicitly requires (a) top-of-file comment block enumerating allow-list + Cursor docs URL + retrieval date + upgrade path; (b) CLAUDE.md cross-link pointing at the test module. |
| W9 | warning | Implementation Plan rollbacks | Phase 0 `_boundary_helpers.py` API is sticky; rollback semantics unclear when later phase needs new fixture parameter. | **Fixed**: Phase 0 adds explicit "Note on helper API evolution" — signature additions are scoped to the introducing phase, not a Phase 0 regression. |
| N10 | nit | Exec Summary | "~3 minutes" stated as fact, no measurement. | **Fixed**: labeled as estimate in Exec Summary + ADR-002 + Risk row; Phase 0 records measured value in commit message. |
| N11 | nit | Prior Work | `[fail:design] phantom-key-on-rerender-breaks-idempotency` (Phase 2 tests for it) not cited. | **Fixed**: added to Prior Work harness.yaml bullets. |

**Final state**: validator outcome **NEEDS_REVISION_RESOLVED**. No second validator pass invoked (per the procedure's single-revision policy on warnings-only).

<!-- @hm:user:extra-quality-checks -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- @hm:/user:extensions -->
