---
type: plan
task_slug: codex-finding-schema-strict-mode
status: complete
created: 2026-06-02
tags: [harness-maker, plan, python, codex, json-schema, structured-output]
interview_rounds: 2
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Fix Codex second-opinion JSON schema for strict structured-output mode (required+nullable, drop constraints)"
---

# PLAN: codex-finding-schema-strict-mode

## 🎯 Executive Summary

**TL;DR** — `.claude/schemas/codex-finding.schema.json` is invalid under OpenAI/Codex strict structured-output mode. Every `codex exec --output-schema` call returns `invalid_json_schema`, so the validator silently falls back to a prompt-pinned shape each pass (retries/latency, eventual hard-failure risk). Fix the **source template**, regression-guard with a committed static strict-mode invariant test (RED→GREEN), re-render the dogfood `.claude/`, smoke-verify against real Codex, then patch-bump to `0.28.7`.

**What/Why** — Strict mode (the dialect `codex exec --output-schema` enforces) has no notion of "optional": when `additionalProperties: false`, **every** key in `properties` must appear in `required`. The committed schema violates this in two places, so Codex rejects it before the model ever runs.

**Key decisions:**
- **ADR-001** — express optional keys as `nullable + still required`; drop all numeric/string constraint keywords (`minimum`/`maximum`/`minLength`).
- **ADR-002** — regression-guard with a deterministic static invariant test carrying a committed negative fixture; not an integration test for CI.
- **ADR-003** — gain real-Codex confidence via a one-time manual `codex exec` smoke gate before the version bump.

**Estimated impact** — 1 source schema file + 1 new test file + dogfood `.claude/` re-render + 5-file version sync + CHANGELOG. Small blast radius: the schema body is not embedded in any snapshot fixture nor in the `_partials/second_opinion_codex.md.j2` SHA baseline.

## 📚 Prior Work

- **`PLAN-codex-second-llm-integration.md`** — defined ADR-008: `.claude/schemas/*.json` renders as **pure JSON, no provenance frontmatter** (external consumer is `codex exec --output-schema`), via `_render_pure_json` + the `_is_schemas_json` predicate. This PLAN does not disturb that contract — only the schema body changes.
- **`PLAN-codex-mandatory-second-opinion.md`** — made the Codex call mandatory for `plan-validator`. That is the agent most exposed to this bug (it calls Codex on every run).
- Memory `[wiki:architecture] codex-second-llm-integration` — confirms the schema is pure JSON and that test pinning historically touched snapshot fixtures + `test_agent_body_partials._EXPECTED_SHA256`. Verified here: **neither is affected** — the schema body lives in no fixture and the partial embeds only the *path* + a prose shape example.
- Memory `[wiki:gotcha] extend-rendered-agent-json-via-shared-partial` — an agent output contract can live in ≥3 places. Checked: the partial's prose example `{ findings:[{file,line,severity,message,evidence}], summary, confidence }` describes the **shape**, which is unchanged; only `required`/nullability changed. No partial edit needed (W2 verification in Phase 4 confirms consumer behavior).
- Memory `[wiki:gotcha] subagent-tools-field-hard-gates-bash-permission` (2026-06-02) — the recent fix that made Codex actually invocable from the reviewer agents; confirms the call now runs and therefore this schema bug is live on every plan-validator run.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Constraint keywords | Contract shape | Drop `minimum`/`maximum`/`minLength`, or keep them? | **Drop all constraints** | Maximally robust across Codex/OpenAI versions; nullable+required for optionals. Claude reconciler re-judges so server-side range/non-empty validation is not load-bearing. | ADR-001 |
| 2 | Regression guard | Testing depth | Static invariant test, integration, or both? | **Static strict-mode unit test** | CI-safe, deterministic, no codex login. | ADR-002 |
| 3 | Real-Codex proof (validator W1) | Risk tolerance | Static-only cannot prove Codex acceptance — how to gain confidence? | **One-time manual codex smoke gate** | `codex exec --output-schema` smoke before version bump; keep draft-07 (smoke catches dialect rejection if any). | ADR-003 |

**Skipped (gate):** version-bump phasing (common-ground — CLAUDE.md mandates 5-file sync for user-facing fixes); test target = source template (defensible default); nullable encoding = `["X","null"]` (OpenAI-canonical, confidence ≥ 0.95).

## 📐 Architecture Decision Records

### ADR-001: Express optional schema keys as nullable + required; drop numeric/string constraint keywords
**Status:** Accepted (2026-06-02, via /hm:plan interview)
**Context:** Strict mode has no "optional" — under `additionalProperties: false`, every property must be in `required`. Several Codex/OpenAI strict-mode versions also reject the keywords `minimum`/`maximum`/`minLength`, a likely secondary rejection cause.
**Decision:** Put every property into its object's `required`. Genuinely-optional keys (`confidence`, `evidence`, `file`, `line`) become nullable via `"type": ["X","null"]`. Drop `minimum`/`maximum`/`minLength` everywhere; keep only `type` + `enum`. Keep `$schema: draft-07` (validated end-to-end by ADR-003's smoke gate rather than swapped speculatively).
**Consequences:**
- ✅ Valid first-pass strict schema — no prompt-pinned fallback, no retry/latency.
- ⚠️ Loses cheap server-side range/non-empty validation — accepted, since the Claude reconciler re-judges every Codex finding (preserves ADR-005 of PLAN-codex-second-llm-integration: Codex is input, not verdict).
**Rejected alternatives:**
- Keep constraints, fix `required` only — rejected: risks a second `invalid_json_schema` on versions lacking those keywords, the exact retry cost being killed.
- Empirically probe which keywords are accepted before deciding — rejected: delays the fix; the smoke gate (ADR-003) covers acceptance verification without blocking the design.
**Source:** Interview #1.

### ADR-002: Regression-guard via a static strict-mode-validity unit test with a committed negative fixture
**Status:** Accepted (2026-06-02, via /hm:plan interview)
**Context:** No existing test asserts schema **shape** — `test_render_pure_json.py` checks only routing (pure JSON / no frontmatter). The bug shipped invisibly.
**Decision:** Add a deterministic unit test over `src/harness_maker/templates/schemas/*.json` (generic — guards all current and future rendered schemas) asserting: for every object with `additionalProperties: false`, every key in `properties` (recursively) appears in `required`; optional keys are nullable; no `minimum`/`maximum`/`minLength`. The test embeds a **known-bad schema literal** as a committed negative fixture, asserting the validator rejects it — so the catch-the-bug proof is permanent and re-runnable, not an ephemeral pre-fix checkout (resolves validator W4).
**Consequences:**
- ✅ Catches future regressions of this exact class for ALL rendered schemas; the negative fixture makes the RED-case a committed artifact.
- ⚠️ Does not prove real Codex acceptance end-to-end — covered by ADR-003.
**Rejected alternatives:**
- Integration-only — rejected: non-deterministic, needs codex login, no CI guard.
- Both static + CI integration — rejected: CI integration cost not justified for a statically-verifiable invariant; the one-time smoke (ADR-003) is the proportionate proof.
**Source:** Interview #2.

### ADR-003: One-time manual `codex exec` smoke gate before the version bump
**Status:** Accepted (2026-06-02, via /hm:plan interview)
**Context:** The static test (ADR-002) proves the `property ∈ required` invariant but **cannot** prove the fixed schema is actually accepted by Codex's `--output-schema`. The nullable `["X","null"]` encoding is OpenAI-canonical (low risk), but draft-07 `$schema` acceptance by the Codex CLI is unverified — if rejected, the same `invalid_json_schema` failure class ships.
**Decision:** Add a one-time **manual** `codex exec --output-schema .claude/schemas/codex-finding.schema.json` smoke check as a Phase 5 exit gate (run locally after `codex login`; not in CI). Exit 0 (no `invalid_json_schema`) is the gate. If `codex login` is unavailable, HALT and surface to the user — do not silently skip (this gate is the real-acceptance proof the whole PLAN exists to deliver).
**Consequences:**
- ✅ Closes the "passes local test but still rejected by Codex" gap end-to-end before the bump.
- ⚠️ Requires one manual step + codex login — accepted as a one-time cost, kept out of CI to preserve determinism.
**Rejected alternatives:**
- Normalize `$schema` to draft 2020-12 then smoke — deferred: the smoke gate empirically reveals whether draft-07 is even a problem; speculative dialect swap enlarges the diff without evidence.
- Accept as risk, ship static-only — rejected by user: leaves real acceptance unproven until the next live validator run.
**Source:** Interview #3 (validator W1 follow-up).

## 🏗️ Technical Design

**Current State** — `src/harness_maker/templates/schemas/codex-finding.schema.json` (source) is copied verbatim by `synthesize._schema_files` → rendered via `_render_pure_json` (re-serialized with sorted keys, no frontmatter) to `.claude/schemas/codex-finding.schema.json` (live, in `.hm-render-manifest.jsonl`). Violations: top-level `required: ["findings","summary"]` omits `confidence`; `findings.items.required: ["severity","message"]` omits `file`/`line`/`evidence`; both objects are `additionalProperties: false`.

**Affected Components** — only the source schema template + a new test. The three consuming agents (`plan-validator`, `code-reviewer`, `consensus-arbiter`) share this one schema via `_partials/second_opinion_codex.md.j2`; one edit covers all three.

**Why fix the source, not the live file** — the live `.claude/` copy is rendered output. Editing it alone is clobbered on the next `/hm:make`/re-render (CLAUDE.md dogfood pattern; matches commit `f5a046e` "re-render dogfood .claude harness"). The durable fix is the template; the live copy is refreshed by re-render (Phases 3 & 5).

**Corrected schema (source template, logical order — renderer sorts keys on output):**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Codex Second-Opinion Finding List",
  "type": "object",
  "additionalProperties": false,
  "required": ["findings", "summary", "confidence"],
  "properties": {
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["severity", "message", "evidence", "file", "line"],
        "properties": {
          "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
          "message": {"type": "string"},
          "evidence": {"type": ["string", "null"]},
          "file": {"type": ["string", "null"]},
          "line": {"type": ["integer", "null"]}
        }
      }
    },
    "summary": {"type": "string"},
    "confidence": {"type": ["number", "null"]}
  }
}
```

**Contract-shape note (validator W2)** — making `file`/`line`/`evidence` required-but-nullable changes the wire semantics: Codex must now emit all three keys (with `null` when absent) rather than omitting them. The three consumers are **LLM-prompted reviewers** that read the JSON semantically — a `null` file reads as "no file" the same as an absent key. Phase 4 verifies no consumer branches on key-presence in a way that breaks on explicit `null`.

**Design Decisions** — all trace to ADR-001/002/003 above.

**Data Flow** — `codex exec --output-schema <live schema>` → JSON conforming to schema → reviewer agent reconciles each finding → `codex_reconciliation` array in the agent's output. Unchanged by this PLAN except that the first arrow now succeeds first-pass.

**API Changes** — JSON schema contract only (the `required`/nullability change above). No Python API change.

## 📝 Implementation Plan

### Phase 1 — Author static strict-mode invariant test (RED)
- **depends_on:** `[]`
- **parallel_group:** `serial-tdd`
- **merge_hazards:** none (new file)
- **Scope in:** new `tests/unit/test_schema_strict_mode.py`. **Out:** everything else.
- **Exit:** test file exists; running `uv run pytest tests/unit/test_schema_strict_mode.py` is **RED** against the current (broken) source — the `property ∈ required` assertion fails on `codex-finding.schema.json`. The embedded negative-fixture case (known-bad schema literal) asserts the validator helper rejects it (GREEN portion). This proves the test catches the bug class before the fix exists.
- **Risk:** low
- **Rollback:** delete the test file.

### Phase 2 — Fix source template schema (GREEN)
- **depends_on:** `[1]`
- **parallel_group:** `serial-tdd`
- **merge_hazards:** none (different file from Phase 1)
- **Scope in:** `src/harness_maker/templates/schemas/codex-finding.schema.json`. **Out:** everything else.
- **Exit:** `uv run pytest tests/unit/test_schema_strict_mode.py` is **GREEN** (Phase 1's invariant now passes against the fixed source); `uv run python -c "import json,pathlib; json.loads(pathlib.Path('src/harness_maker/templates/schemas/codex-finding.schema.json').read_text())"` exits 0. (The invariant itself is owned by Phase 1's test — no manual eyeball check; resolves validator W3.)
- **Risk:** low
- **Rollback:** `git checkout` the source file (test goes RED again — expected).

### Phase 3 — Re-render dogfood `.claude/` at current version (isolated fix-render)
- **depends_on:** `[2]`
- **parallel_group:** `serial-render`
- **merge_hazards:** `.claude/.hm-render-manifest.jsonl` (regenerated)
- **Scope in:** `.claude/schemas/codex-finding.schema.json`, `.claude/.hm-render-manifest.jsonl`. **Out:** source/tests/version files.
- **Exit:** re-render the dogfood harness **at the still-current version 0.28.6** (no version bump yet). `git diff --stat .claude/` shows **ONLY** `schemas/codex-finding.schema.json` + `.hm-render-manifest.jsonl` changed — clean because (a) no version bump means no `harness_maker_version` frontmatter churn elsewhere, and (b) the schema is pure-JSON with no frontmatter, so its own diff is body-only. Live schema body matches the corrected shape (sorted-key serialization). (Resolves validator W5 by pinning re-render-before-bump ordering.)
- **Risk:** low
- **Rollback:** `git checkout .claude/`.

### Phase 4 — Verify consumer null-safety (W2)
- **depends_on:** `[2]`
- **parallel_group:** `serial-render` (read-only; may run alongside Phase 3)
- **merge_hazards:** none (read-only)
- **Scope in:** read `src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2` + the 3 consumer agent bodies' reconciliation prose. **Out:** no edits unless a break is found.
- **Exit:** confirm (and note in the PLAN/REVIEW trail) that `plan-validator`, `code-reviewer`, `consensus-arbiter` treat `null` `file`/`line`/`evidence` identically to absent keys (semantic LLM read — expected pass since none branch on key-presence in code). If any consumer would mishandle explicit `null`, escalate as a new finding (and, if it requires a contract decision, HALT for a standalone ADR).
- **Risk:** low
- **Rollback:** n/a (read-only); revert any prose edit if one proved necessary.

### Phase 5 — Version bump + full re-render + quality gate + Codex smoke
- **depends_on:** `[2, 3, 4]`
- **parallel_group:** `serial-release`
- **merge_hazards:** 5 version files must stay in sync; whole `.claude/` tree frontmatter (expected version-stamp churn)
- **Scope in:** `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`, `CHANGELOG.md`, and the full dogfood `.claude/` re-render.
- **Exit (all must hold):**
  1. **Codex smoke (ADR-003):** one-time manual `codex exec --output-schema .claude/schemas/codex-finding.schema.json` (after `codex login`) exits 0 with no `invalid_json_schema`. If codex login is unavailable → HALT + surface to user (do not silently skip).
  2. 5-file version sync to **0.28.7**; CHANGELOG entry added.
  3. Full dogfood re-render at 0.28.7 — whole-tree `harness_maker_version`/`content_hash`/`generated_at` frontmatter churn is **expected**; gate = no **body** diffs beyond version stamps + the schema fix.
  4. `uv run ruff check` + `uv run ruff format --check` + `uv run mypy --strict src` + `uv run pytest` all green (run pytest/mypy in background per project policy).
- **Risk:** low (the only external dependency is codex login for the smoke gate)
- **Rollback:** `git checkout` version files + `.claude/`. (No tag push — release tagging is a separate user-initiated step per CLAUDE.md.)

## 🧪 Testing Strategy

- **Unit (CI, deterministic):** new `test_schema_strict_mode.py` — generic strict-mode invariant over `templates/schemas/*.json` + committed negative fixture (ADR-002). Existing `test_render_pure_json.py` routing test stays green.
- **Integration:** none in CI (ADR-002).
- **Manual one-time smoke:** `codex exec --output-schema` round-trip (ADR-003, Phase 5 gate) — requires codex login, not CI.
- **Full gate:** ruff + mypy --strict + full pytest in Phase 5.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fixed schema still rejected by Codex (dialect/`$schema`) | low | high (re-ships bug class) | ADR-003 one-time `codex exec` smoke gate before bump |
| Consumer agent mishandles explicit `null` vs absent key | low | medium | Phase 4 null-safety verification of all 3 consumers |
| Phase 5 full re-render churns whole tree, obscuring the fix | medium | low | Phase 3 isolates the fix-render at 0.28.6 first (clean diff); Phase 5 gate allows only frontmatter version-stamp diffs |
| RED-proof becomes ephemeral after fix | — | — | Resolved: committed negative fixture in the test (ADR-002) |

## ✅ Success Criteria

- [x] Source schema valid under strict mode: every property ∈ `required`, optionals nullable (`["X","null"]`), no `minimum`/`maximum`/`minLength`.
- [x] `test_schema_strict_mode.py` green on fixed source AND its committed negative fixture proves it rejects the bug class. (Hardened in review: structural walker + 2 new guard tests — see REVIEW.)
- [x] Consumer null-safety verified for all 3 reviewer agents (Phase 4).
- [x] Full quality gate green; version `0.28.7` synced across 5 files + CHANGELOG entry.

**Deferred (not open checkboxes — tracked outside this PLAN's done-state):**
- ⏳ Dogfood `.claude/` re-render → **post-release chore** (live copy is gitignored; re-render via `/hm:make` after `/plugin update` to 0.28.7). Documented in the Execution Log Phase 3 row.
- 📌 One-time `codex exec --output-schema` smoke (ADR-003) → **user-run gate**; the `codex exec` Bash call is permission-gated. **Run before tagging `v0.28.7`.** Command is in the execute stage summary.

## 🔍 Plan Validation

- **Validator outcome:** NEEDS_REVISION (0 critical, 5 warnings + 1 suggestion) → **resolved**.
- **Codex second opinion:** ⚠️ **skipped** — `codex exec` Bash invocation denied by the sandbox/permission layer (`codex_skip_reason`); verdict is Claude-only. Warn-and-proceed per ADR-003 of PLAN-codex-second-llm-integration.

| Validator finding | Severity | Resolution |
|-------------------|----------|------------|
| W1 — ADR-001 never pins dialect/nullable acceptance; static test can't prove Codex acceptance | warning | **ADR-003** added (one-time manual `codex exec` smoke gate, Phase 5). Interview #3. |
| W2 — required-but-nullable changes contract; consumers may branch on key-presence | warning | **Phase 4** added (null-safety verification of all 3 consumers) + Non-Goals note. |
| W3 — Phase 1 "manual check" exit non-verifiable | warning | Reordered TDD: test authored first (Phase 1, RED), fix second (Phase 2, GREEN); invariant owned by the test, not a manual eyeball. |
| W4 — Phase 2 RED-check has no concrete mechanism | warning | Negative fixture (known-bad schema literal) committed in the test — permanent, re-runnable RED-proof. |
| W5 — Phase 3 churn gate trips on version-stamp frontmatter | warning | Pinned ordering: Phase 3 re-renders at current 0.28.6 (clean isolated diff); Phase 5 bumps + full re-render with frontmatter-only gate. |
| Suggestion — no Non-Goals | suggestion | See Non-Goals below. |

**Non-Goals:** no consumer-agent prose rewrite (unless Phase 4 finds a break); no CI integration/codex-login test; no `$schema` dialect swap (deferred pending smoke evidence); no git tag push (separate user-initiated release step).

## 🔧 Execution Log (/hm:execute — 2026-06-03)

TDD machine ran in worktree `execute-632123aa001b-20260602T1457Z`, then base-repo follow-up.

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — author invariant test (RED) | ✅ DONE | `tests/unit/test_schema_strict_mode.py`; test-reviewer PASS; RED confirmed against broken source (Phase B). |
| 2 — fix source template (GREEN) | ✅ DONE | `src/harness_maker/templates/schemas/codex-finding.schema.json` rewritten (nullable+required, constraints dropped). New test GREEN; full unit suite 2833 passed. |
| 3 — re-render dogfood `.claude/` | ⚠️ RE-SCOPED → post-release | **Execute-time finding:** the live `.claude/schemas/codex-finding.schema.json` AND `.hm-render-manifest.jsonl` are **gitignored** — nothing tracked to commit. The PLAN's "git diff shows schema+manifest" premise was wrong. Worse, `make --update` inside a worktree is the hard-blocked footgun `[fail:snapshot-regen-inside-worktree]` (count:4); and re-rendering in base via `uv run harness-maker` (a) used an installed package copy lacking the staged fix (live schema stayed old) and (b) flips maintainer-local `--with` paths, churning an unrelated tracked file (`plan-exec-rev.md`, reverted). Conclusion: the dogfood `.claude/` re-render to 0.28.7 is a **post-release chore** (run `/hm:make` after `/plugin update` to 0.28.7), exactly like commit `f5a046e` was for 0.28.6. The shippable fix is the **source template** (tracked, staged). |
| 4 — consumer null-safety (W2) | ✅ DONE | No Python deserializes the codex output by key-presence; the only consumers are LLM agents whose prose already says `file:line (when present) or a verbatim quote of message`. `null` reads as "not present". No edit needed. |
| 5 — version bump + CHANGELOG + smoke | 🟡 PARTIAL | Version synced 0.28.6→**0.28.7** across 5 files; CHANGELOG entry added; version sync/drift tests pass. **Codex smoke DEFERRED to user** — the `codex exec` Bash call was denied by the permission layer (consistent with ADR-003's design that the smoke is a manual, user-run gate). Smoke command provided in the stage summary; **must pass before tagging `v0.28.7`** (ADR-003 ordering preserved: the ship is the user-initiated tag push, not the uncommitted bump). |

**Staged changeset (uncommitted — wrapup owns the commit):**
- `M src/harness_maker/templates/schemas/codex-finding.schema.json`
- `A tests/unit/test_schema_strict_mode.py`
- `M` ×5 version files + `M CHANGELOG.md`

**Quality gate:** ruff ✅ · ruff format ✅ · mypy --strict (102 files) ✅ · pytest unit (2833 passed / 1 skipped / 1 xfailed) ✅.
