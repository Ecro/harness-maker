---
type: plan
task_slug: codex-plan-validator-model-unavailable
status: complete
created: 2026-05-11
tags: [harness-maker, plan, python, codex-target, agent-rendering, model-config]
research_doc: "[[RESEARCH-codex-plan-validator-model-unavailable]]"
interview_rounds: 3
adrs: 1
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Drop hardcoded model field from Codex agent TOMLs; let ~/.codex/config.toml default win"
---

# PLAN — Codex plan-validator model unavailable

## 🎯 Executive Summary

**TL;DR**: `.codex/agents/*.toml` files render with `model = "o4"` or `model = "o4-mini"`, both rejected by ChatGPT-tier Codex CLI (verified via live probe — `400 invalid_request_error: The 'o4' model is not supported when using Codex with a ChatGPT account`). Drop the `model =` line so Codex inherits `~/.codex/config.toml` default (the user's `gpt-5.5` works today). 12 agent files affected. No schema change. No new interview question.

**What/Why**: The plan-validator subagent dispatch in Codex fails because every model string our renderer hardcodes (`o4`, `o4-mini`, even `gpt-5-codex` and `gpt-5.5-codex`) is rejected on ChatGPT-tier subscriptions. Only the account's profile default works. By omitting the per-agent `model =` line, Codex CLI uses the account-correct default automatically.

**Key Decisions**:
- **ADR-001** — Render Codex agent TOMLs without `model =` line.

**Estimated impact**: 1 source file (`src/harness_maker/synthesize.py`), 12 rendered `.codex/agents/*.toml` files, ≥24 snapshot files (`tests/e2e/sandbox/.codex/agents/` × 12 + `tests/e2e/sandbox-plugin-test/.codex/agents/` × 12).

## 📚 Prior Work

- [[RESEARCH-codex-plan-validator-model-unavailable]] (2026-05-11) — root-cause with live Codex CLI probes confirming HTTP 400 for `o4`, `o4-mini`, `gpt-5-codex`, `gpt-5.5-codex` on ChatGPT-tier accounts. Only `gpt-5.5` works.
- [[RESEARCH-codex-target-support]] — defines Codex render scope and `.codex/agents/*.toml` artifact location.
- `.claude/memory/failures.md` `[fail:codex-helpers-ignore-user-config | 2026-05-11]` — direct precedent against adding `HarnessConfig` fields that aren't properly threaded through `synthesize()`. Drives the Round 2 decision to defer the schema knob.
- `.claude/memory/project_targets_axis.md` — confirms `.toml` files have no YAML frontmatter and `reconcile.py` always REPLACES (silent auto-migration is automatic).

## 🚫 Non-Goals

Explicitly out of scope for this PLAN; tracked as candidates for follow-up PLANs:

- **Schema knob `codex_agent_models`** — adding `codex_agent_models: dict[str, str | None]` to `HarnessConfig` for opt-in per-tier override. Deferred until a real user requests per-tier differentiation (see ADR-001 Consequences).
- **New interview question** — no question added to `/hm:make` interview about Codex model selection.
- **Version bump** — fix accumulates with other pending work on the next release cycle (current `0.9.4` head, no explicit bump in this PLAN).
- **README banner / docs update beyond CHANGELOG** — CHANGELOG entry is the audit trail; no README section, no `docs/HOW-IT-WORKS.md` revision.
- **Migration script** — silent auto-replace via existing `reconcile.py` REPLACE fast-path is the migration mechanism; no separate tool.
- **`INTEGRATION=1` live Codex probe in CI** — deferred per Round 3 testing-depth decision; explicit `accept-as-risk` in §Risks (R4).
- **Cross-target model-naming unification** — the three targets (Claude, Cursor, Codex) currently use three different model identifier conventions (`opus`, `claude-opus-4-7`, omitted). Unification is a larger architectural exercise outside this fix's scope.

## 🎙️ Interview Transcript

| # | Topic | Category | Choice | Note | → ADR |
|---|-------|----------|--------|------|-------|
| 1 | Default model policy | Architecture | **D** — Omit by default + future knob deferred | Rejected B (hardcode `gpt-5.5`) due to drift hazard recurrence. Rejected C (schema field now) as premature. | ADR-001 |
| 2a | Scope | Phasing | **A only** — omit, no schema change in this PLAN | Avoids `[fail:codex-helpers-ignore-user-config]` anti-pattern (premature schema fields wired without consumer). | — |
| 2b | Migration UX | Risk | **Silent auto-replace** on next `/hm:make` | `reconcile.py` REPLACEs `.toml` files unconditionally (no frontmatter fast-path). CHANGELOG entry is the audit trail. | — |
| 3a | WRONG probe | Failure mode | Quality regression on plan-validator (gpt-5.5 vs o4-class reasoning) | Acknowledged risk → §Risks R1. | — |
| 3b | Testing depth | Testing | **Unit only** — assert no `model =` + snapshot regen | No integration test. No live Codex probe in CI. | — |
| 4a | Phase 3 diff overflow | Phasing | **Halt + surface** unexpected files for review | Resolves validator W2. No auto-rollback, no auto-accept. | — |
| 4b | Manual `codex exec` probe | Testing | **Accept-as-risk** explicit, probe removed | Resolves validator W3. Codex CLI behavior change captured as R4. | — |

**Gate Round 3 (final):**
- Goals 1.0 / Constraints 1.0 / Success Criteria 1.0 → weighted 1.0 → PASS. Zero remaining high/medium-impact ambiguities. Validator follow-up (Round 4) resolved W2 + W3 without re-opening gate.

## 📐 Architecture Decision Records

### ADR-001: Codex agent TOMLs render without per-agent `model =` line
**Status:** Accepted (2026-05-11, via /hm:plan interview Round 1; validator NEEDS_REVISION resolved in Round 4)

**Context:** ChatGPT-tier Codex CLI rejects every model string our renderer hardcodes (`o4`, `o4-mini`, `gpt-5-codex`, `gpt-5.5-codex`) with HTTP 400 `invalid_request_error: The '<model>' model is not supported when using Codex with a ChatGPT account.` Only the account's `~/.codex/config.toml` default (`gpt-5.5` for the affected user) works. Live probes via `codex exec --model X "ping"` confirm (see RESEARCH §Sources).

**Decision:** Drop the `model = "..."` line from every rendered `.codex/agents/*.toml`. The existing `{% if model_codex %}` gate in `src/harness_maker/templates/codex/agent.toml.j2` makes this a no-template-change fix — `_codex_agent_files()` stops passing `model_codex`, the template block elides, the rendered file omits the line.

**Consequences:**
- ✅ Codex CLI inherits the account-correct profile default automatically.
- ✅ No drift hazard — we never bake a specific OpenAI model identifier into rendered files.
- ✅ Matches existing Cursor policy from CLAUDE.md §Targets ("agent prompts kept model-agnostic… user override OK").
- ✅ Forward-compat path preserved: template gate stays intact; re-enabling per-agent model is a one-tuple-element change when the deferred `codex_agent_models` knob lands (see §Non-Goals).
- ⚠️ Per-agent model tier differentiation is lost at render time — plan-validator and ux-reviewer run on the same model. Mitigated by deferred `codex_agent_models` knob (see §Non-Goals) and tracked as §Risks R1.

**Rejected alternatives:**
- **B (hardcode `gpt-5.5`)** — Rejected because it recreates the exact drift hazard that produced the `o4` bug. Next model deprecation = repeat fix.
- **C (add `codex_agent_models` schema field now)** — Rejected as premature; no real user has requested per-tier override. Memory `[fail:codex-helpers-ignore-user-config | 2026-05-11]` is direct precedent against wiring dormant schema fields.
- **D-hybrid (A + dormant C wired)** — Rejected because Round 2 confirmed A-only scope.

**Source:** Interview #1 (locked); Interview #4 (validator-resolution follow-up; did not reopen this decision).

## 🏗️ Technical Design

**Current State:**
- `src/harness_maker/synthesize.py:135-200` defines `_CODEX_AGENT_META: dict[str, tuple[str, str]]` with `(description, model_codex)` tuples; `model_codex` is `"o4"` for 3 reasoning-heavy agents and `"o4-mini"` for the other 9.
- `_codex_agent_files()` (line 203) reads `_CODEX_AGENT_META[n][1]` as `model_codex` and threads it into the `codex/agent.toml.j2` template context.
- `src/harness_maker/templates/codex/agent.toml.j2` already gates `model = ...` rendering on truthy `model_codex` (lines 3-5: `{% if model_codex -%}...{% endif %}`).
- Rendered `.codex/agents/*.toml` contains `model = "o4"` or `model = "o4-mini"` at line 3 — both rejected by ChatGPT-tier Codex CLI.

**Affected Components:**

| Component | Change |
|-----------|--------|
| `src/harness_maker/synthesize.py:138-200` | Change `_CODEX_AGENT_META` type from `dict[str, tuple[str, str]]` to `dict[str, str]` (value = description only). Drop the `(description, model_codex)` tuples. |
| `src/harness_maker/synthesize.py:203-217` | Drop `"model_codex"` key from the `_codex_agent_files()` context dict. |
| `src/harness_maker/templates/codex/agent.toml.j2` | **NO CHANGE** — `{% if model_codex %}` already gates correctly when context lacks the key. Preserves forward-compat for the deferred opt-in knob. |
| `tests/unit/test_synthesize.py` | Add parametrized `test_codex_agent_toml_omits_model_field` over all 12 agents. |
| `tests/e2e/sandbox/.codex/agents/*.toml` (12 files) | Regenerate via existing snapshot mechanism. |
| `tests/e2e/sandbox-plugin-test/.codex/agents/*.toml` (12 files) | Same. |

**Dependencies:** None new.

**Data Flow:**
- Before: `_CODEX_AGENT_META[name][1]` → `_codex_agent_files()` context → template `{{ model_codex }}` → rendered file `model = "o4"`.
- After: no `model_codex` key in context → `{% if model_codex %}` block elides → rendered file has no `model =` line.

**API Changes:** None (internal Python only; no public API surface).

## ✅ Execution Status (2026-05-11)

All 4 PLAN phases complete on main:

- **Phase 1**: `_CODEX_AGENT_META` type `dict[str, tuple[str, str]]` → `dict[str, str]`. `_codex_agent_files()` now passes `model_codex=None` (template gate evaluates falsy under StrictUndefined while remaining intact for the deferred opt-in knob).
- **Phase 2**: `tests/unit/test_synthesize.py::test_codex_agent_toml_omits_model_field` — parametrized over all 12 agents, asserts `^model\s*=` regex MUST NOT match in rendered TOML. 12/12 GREEN.
- **Phase 3**: `grep "^model\s*=" .codex/agents/*.toml` → 0 matches (12 dogfood TOMLs re-rendered surgically via `_codex_agent_files()` + `_make_env()`). `tests/snapshot/regenerate.py` ran from main (post-finalize) with no resulting diff (already fresh from `2a9dfef`). Full `uv run pytest tests/unit/ -q` green. PLAN's `tests/e2e/{sandbox,sandbox-plugin-test}/.codex/agents/*.toml` paths did not exist as fixtures — scope correction recorded here.
- **Phase 4**: CHANGELOG entry added under `## Unreleased` → `### Fixed`.

**Blocker resolved**: initial `worktree finalize stage-only` failed because main HEAD had advanced (`bc19c26` → `dbfdf24 feat(second-brain)`) after worktree creation. `git rebase main` inside the worktree applied my changes cleanly on top of `dbfdf24` (no conflicts — second-brain feature did not touch `_CODEX_AGENT_META`). Finalize retry succeeded; worktree cleaned up.

Wrapup stage owns the single commit. No `git commit` issued by execute.

## 📝 Implementation Plan

### Phase 1 — Schema simplification + renderer update

**Scope IN:**
- `src/harness_maker/synthesize.py`: change `_CODEX_AGENT_META` from `dict[str, tuple[str, str]]` to `dict[str, str]` (value = description). Update `_codex_agent_files()` to stop passing `model_codex` in the context dict.
- Preserve `templates/codex/agent.toml.j2` unchanged (forward-compat gate stays).

**Scope OUT:** `HarnessConfig`, `interview.py`, `answers_from_harness_yaml`, plugin manifests (`.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/`), `src/harness_maker/__init__.py` version, CHANGELOG (Phase 4).

**Exit criterion:** `uv run pytest tests/unit/test_synthesize.py -q` passes; `uv run mypy --strict src/harness_maker/synthesize.py` clean.

**Risk:** low

**Rollback point:** revert this commit; pre-Phase-1 state restores prior (broken) render.

### Phase 2 — Unit test asserting omitted `model =` line

**Scope IN:**
- `tests/unit/test_synthesize.py`: add `test_codex_agent_toml_omits_model_field` parametrized over all 12 agent names (`autoloop-coder, code-reviewer, concurrency-reviewer, consensus-arbiter, executor, performance-reviewer, plan-validator, security-auditor, security-reviewer, stuck, test-reviewer, ux-reviewer`). Renders the synthesize file_specs, locates each `.codex/agents/<n>.toml`, asserts the rendered TOML body contains no occurrence matching regex `^model\s*=`.

**Scope OUT:** Integration tests, live Codex CLI probes, billing-incurring tests.

**Exit criterion:** `uv run pytest tests/unit/test_synthesize.py::test_codex_agent_toml_omits_model_field -q` passes for all 12 parametrized cases; full unit suite `uv run pytest tests/unit/ -q` green (run in background per `feedback_pytest_background`).

**Risk:** low

**Rollback point:** revert this test commit; falls back to Phase 1 state.

### Phase 3 — Snapshot regeneration + grep verification

**Scope IN:**
- Re-run snapshot regen for `tests/e2e/sandbox/.codex/agents/*.toml` and `tests/e2e/sandbox-plugin-test/.codex/agents/*.toml` via the repo's existing mechanism (e.g., `python -m harness_maker.regenerate` or pytest's snapshot update flag).
- Verify regen did not affect non-`.codex/agents/` snapshots (e.g., Claude-target `model: opus` frontmatter must remain unchanged).
- Run `grep "^model\s*=" .codex/agents/*.toml` post-render — expected: zero matches.

**Scope OUT:** Backing up old snapshots manually (git history preserves them).

**Exit criterion (all three must hold):**
1. `uv run pytest -q` (full suite, background) passes.
2. `grep "^model\s*=" .codex/agents/*.toml` returns zero matches.
3. `git diff --stat` is contained to: `src/harness_maker/synthesize.py`, `tests/unit/test_synthesize.py`, `tests/e2e/sandbox/.codex/agents/*.toml`, `tests/e2e/sandbox-plugin-test/.codex/agents/*.toml`.

**Triage rule (resolves validator W2):** If condition 3 fails (diff escapes expected scope) but conditions 1 and 2 hold, **HALT this phase**. Surface the unexpected files via PR comment or interview round. Do not auto-rollback (might destroy legitimate cross-target coupling fix); do not auto-accept (might silently overreach scope). A follow-up interview round must classify each unexpected file before continuing.

**Risk:** low (mechanical regen; triage rule covers the cross-target coupling edge case)

**Rollback point:** if regen produced clearly-wrong output (condition 2 fails — `model =` still present somewhere), `git checkout HEAD~ -- tests/e2e/` restores prior snapshots.

### Phase 4 — CHANGELOG entry

**Scope IN:**
- Add CHANGELOG entry under `## Unreleased` (or current pre-release section): `fix(codex): omit per-agent model field from rendered .codex/agents/*.toml to inherit account default (was: hardcoded "o4"/"o4-mini" causing 400 on ChatGPT-tier Codex CLI).`

**Scope OUT:** Version bump (per §Non-Goals), README banner, migration script, `docs/HOW-IT-WORKS.md` revision.

**Exit criterion:** CHANGELOG entry committed; the line appears in `CHANGELOG.md`.

**Risk:** low

**Rollback point:** revert this commit; CHANGELOG line removed.

## 🧪 Testing Strategy

**Unit:**
- New parametrized `test_codex_agent_toml_omits_model_field` in `tests/unit/test_synthesize.py` covers all 12 agents. Asserts `^model\s*=` regex does not match anywhere in the rendered TOML body.
- Existing tests in `tests/unit/test_synthesize.py` that reference `model_codex` are updated to reflect the new shape (or removed if they only asserted on the dropped behavior).

**Integration:** None. INTEGRATION-gated live Codex probe explicitly deferred per Round 3 testing-depth decision (`accept-as-risk` recorded in §Risks R4).

**Manual:**
- After merge, run `/hm:make` in a sandbox project. Verify `.codex/agents/plan-validator.toml` (and all 11 other agent TOMLs) have no `model =` line via `grep "^model\s*=" .codex/agents/*.toml` returning empty.

(Live `codex exec` probe explicitly removed per Round 4b decision — accepted-as-risk in §Risks R4.)

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Detection | Mitigation |
|---|------|-----------|--------|-----------|-----------|
| R1 | plan-validator runs on user's `~/.codex/config.toml` default (e.g., `gpt-5.5`), which may produce weaker critiques than an `o4`-class reasoning model. | Medium (flagged in WRONG probe Round 3a) | Medium (degraded `/hm:plan` Step 4 quality on Codex target) | Log occurrences in `.claude/memory/failures.md` with tag `[fail:codex-plan-validator-quality]`; user reports of weak validator output on Codex. | Ship the deferred `codex_agent_models` knob (§Non-Goals) as a follow-up PLAN if R1 is observed. |
| R2 | Future Codex CLI release interprets missing `model =` differently (e.g., falls back to a cheap fixed model instead of profile default). | Low | Medium | Manual user report or live probe surprise. | Template `{% if model_codex %}` gate intact — re-enabling per-agent model is a one-tuple-element change, not a template rewrite. Phase 1 explicitly preserves this forward-compat path. |
| R3 | Phase 3 snapshot regen might change non-`.codex/agents/` snapshots if cross-target coupling exists in `synthesize.py`. | Low | Low | Phase 3 exit criterion #3 (`git diff --stat` containment). | Phase 3 **triage rule** — halt + surface unexpected files for review (no auto-rollback, no auto-accept). Follow-up interview round classifies each unexpected file. |
| R4 | Without a live `codex exec` probe in verification, a future Codex CLI behavior change that breaks our render assumption could ship undetected. | Low (Codex CLI behavior changes are coupled to OpenAI release notes; observable externally) | Medium (regression repeats the original bug class) | Accepted-as-risk per Round 4b. User-reported breakage or routine `/hm:refresh` anti-rot crawl picking up Codex CLI release notes. | If R4 is realized, restore the live probe as Phase 4 step in a follow-up PLAN and gate verification on `codex` binary availability. |

## ✅ Success Criteria

- [x] `grep "^model\s*=" .codex/agents/*.toml` returns zero matches after Phase 3 completes.
- [x] `uv run pytest -q` is green (full suite, run in background).
- [x] `uv run mypy --strict src/harness_maker/synthesize.py` is clean.
- [x] `uv run ruff check src/ tests/` is clean.
- [x] `uv run ruff format --check src/ tests/` is clean (on edited files; pre-existing repo-wide drift in 13 unrelated files acknowledged separately).
- [x] `tests/unit/test_synthesize.py::test_codex_agent_toml_omits_model_field` passes for all 12 agents.
- [x] Snapshot diff contained to `synthesize.py`, `test_synthesize.py`, `test_codex_phase4.py` (review iteration 2 fix), `CHANGELOG.md`; PLAN-claimed e2e paths did not exist — scope corrected in §Execution Status. Phase 3 triage rule not triggered (no unexpected files surfaced).
- [x] CHANGELOG entry merged under `## Unreleased` → `### Fixed`.

## 🔍 Plan Validation

**Validator:** `plan-validator` agent (Claude-target, `model: opus`) — invoked via Task tool in `/hm:plan` Step 4.

**First pass outcome:** `NEEDS_REVISION` (3 warnings + 2 suggestions; 0 critical). Validator JSON archived inline below.

**Resolution path:**

| Validator Finding | Severity | Resolution | Source |
|-------------------|----------|------------|--------|
| W1: Non-Goals section absent (ADR-001 dangling `(Non-Goals)` reference) | warning | **Revised** — added `## 🚫 Non-Goals` section enumerating all deferred work (schema knob, interview question, version bump, README banner, migration script, INTEGRATION test, cross-target unification). ADR-001's `(Non-Goals)` reference now resolves. | Default judgment (no user decision needed) |
| W2: Phase 3 exit criterion lacks decision rule for "diff overflows but pytest is green" | warning | **Revised** — added Phase 3 **Triage rule**: halt + surface unexpected files for review (no auto-rollback, no auto-accept). Follow-up interview round classifies. | Interview Round 4a |
| W3: Manual verification's "optionally `codex exec`" is a deferred decision | warning | **Revised** — live probe entirely removed from manual verification; behavior captured as explicit `accept-as-risk` R4 in §Risks. Wording "optionally" removed. | Interview Round 4b |
| S4: R1 mitigation conflates Detection with Mitigation | suggestion | **Revised** — §Risks table split into separate `Detection` and `Mitigation` columns. R1 re-worded accordingly. | Default judgment |
| S5: Phase 4 bundles grep verification with CHANGELOG | suggestion | **Revised** — `grep` verification folded into Phase 3 exit criterion #2. Phase 4 is now CHANGELOG-only. | Default judgment |

**Second-pass validator status:** Not re-run (allowed per /hm:plan Step 4: validator re-runs are only required for `MAJOR_REVISION`, not `NEEDS_REVISION`). All 3 warnings are explicitly addressed above with traceability to either interview rounds or default judgments.

**Validator outcome (final):** `NEEDS_REVISION_RESOLVED`.

<details>
<summary>Validator first-pass JSON (archived)</summary>

```json
{
  "overall_assessment": "NEEDS_REVISION",
  "critiques": [
    {"title": "Non-Goals section absent — scope-drift hazard for deferred codex_agent_models knob", "category": "scope-drift", "severity": "warning"},
    {"title": "Phase 3 exit criterion couples 'full suite green' with 'diff contained' but provides no procedure when diff is NOT contained", "category": "phase-decomposition", "severity": "warning"},
    {"title": "Manual verification step uses 'optionally' — a deferred decision masquerading as a checklist item", "category": "missing-interview-rounds", "severity": "warning"},
    {"title": "Risk R1 mitigation references an unwritten failure-log file as primary mitigation", "category": "risk-register", "severity": "suggestion"},
    {"title": "Phase 4 'Verification + CHANGELOG' bundles two orthogonal concerns", "category": "phase-decomposition", "severity": "suggestion"}
  ],
  "clean_categories": ["adr-completeness", "rollback-strategy", "spec-alignment"]
}
```

</details>
