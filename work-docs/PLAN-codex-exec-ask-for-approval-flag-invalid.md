---
type: plan
task_slug: codex-exec-ask-for-approval-flag-invalid
status: complete
created: 2026-06-03
tags: [harness-maker, plan, python, codex, render, bugfix]
interview_rounds: 0
adrs: 1
validator_outcome: APPROVED
summary: "Drop invalid --ask-for-approval from the codex exec second-opinion recipe; re-baseline SHA pins"
---

# PLAN: codex-exec-ask-for-approval-flag-invalid

## 🎯 Executive Summary

**TL;DR** — The rendered Codex second-opinion recipe (`_partials/second_opinion_codex.md.j2:61`) passes `codex exec --ask-for-approval never`, but `codex exec` **rejects** that flag (`error: unexpected argument '--ask-for-approval'` on codex-cli 0.133.0). It's an interactive-`codex`-only flag; `exec` is non-interactive. So the second-opinion call errors at the **first recipe line** on every run — and warn-and-proceed masks it as a silent skip. Remove the one line; re-baseline the 3 agent-body SHA256 pins; add a guard test. Patch bump `0.28.9`.

**Why it matters** — the `code-reviewer` / `consensus-arbiter` / `plan-validator` Codex second opinion has been silently skipping for every user on this codex version (observed repeatedly this session: "Codex second opinion skipped"). The whole `codex_second_opinion` feature is inert until this is fixed.

**Empirical proof** — this session's v0.28.8 release smoke ran `codex exec --sandbox read-only --ignore-user-config --ignore-rules --json --output-schema <f> --output-last-message <f> -` (no `--ask-for-approval`) and it succeeded, returning schema-conforming JSON.

**Key decision** — ADR-001: the recipe uses only `codex exec`-valid flags; approval is not applicable to exec; guard test prevents reintroduction.

## 📚 Prior Work

- **PLAN-codex-second-llm-integration** — recipe origin; ADR-006 made it hermetic (`--ignore-user-config --ignore-rules`). This PLAN corrects a flag the original recipe shipped that `exec` never accepted.
- `[wiki:gotcha] subagent-tools-field-hard-gates-bash-permission` (2026-06-02) — the *previous* reason the second opinion silently skipped (no `Bash` tool). With that fixed (0.28.6) and Bash now available, the call actually runs — which is how this *next* layer of breakage (the invalid flag) became observable.
- Memory test-pinning note (PLAN-codex-second-llm-integration): `test_agent_body_partials._EXPECTED_SHA256` is the body-hash pin; editing the partial requires re-baselining the affected agents.

## 🎙️ Interview Transcript

**Skip-justification (0 rounds).** Step 0's Contracts criterion fails (the rendered agent body changes), so the interview engaged by default — but the 5-term gate found **no candidate decision above common-ground**: the reporter's args + the empirical v0.28.8 smoke fixed every slot at confidence ≥0.95 (fix = delete the one line; keep `--sandbox read-only`; do NOT substitute `--dangerously-bypass-approvals-and-sandbox`; add a guard test; re-baseline SHA from actual render; patch bump). No architectural decision rejecting a *viable* alternative remained open (keeping the flag = keeping the bug). One ADR records the contract correction so it isn't reintroduced.

## 📐 Architecture Decision Records

### ADR-001: Codex recipe uses only `codex exec`-valid flags; approval is not applicable to exec
**Status:** Accepted (2026-06-03, via /hm:plan — 0-round, empirically grounded)
**Context:** `--ask-for-approval` is an interactive-`codex`-only flag; `codex exec` rejects it, breaking the second-opinion call at line 1 on codex-cli 0.133.0.
**Decision:** Delete `--ask-for-approval never` from the recipe (`exec` is non-interactive — there is no approval prompt to suppress). Keep `--sandbox read-only` as the actual isolation. Add a structural guard test that the rendered recipe contains no `--ask-for-approval`, so a future edit can't reintroduce it.
**Consequences:**
- ✅ Second opinion runs on codex 0.133.0 (smoke-proven this session).
- ⚠️ Trade-off: this is the partial that 3 reviewer-body SHA256 pins fingerprint, so the edit forces a manual re-baseline of those 3 hashes (`test_agent_body_partials._EXPECTED_SHA256`) — the recurring cost of any change to this partial, and the exact "hash masks a body change" risk the register flags.
**Rejected alternatives:**
- Keep the flag — rejected: keeps the bug (second opinion never runs).
- Substitute `--dangerously-bypass-approvals-and-sandbox` — rejected: defeats the intended `--sandbox read-only` isolation.
- codex-version detection / conditional flag — rejected: over-engineering; the flag is invalid for `exec` on all versions, not just 0.133.0.
**Source:** reporter bug report + v0.28.8 release smoke.

## 🏗️ Technical Design

**Current State** — `second_opinion_codex.md.j2` lines 59-67 render:
```
codex exec \
  --sandbox read-only \
  --ask-for-approval never \      ← line 61, delete
  {%- if hermetic %}
  --ignore-user-config --ignore-rules \
  {%- endif %}
  --json \
  ...
```
Deleting line 61 leaves `--sandbox read-only \` flowing into the `{%- if hermetic %}` block (which emits `--ignore-user-config ...` or `--json` next) — valid bash continuation either way.

**Affected Components** — the partial renders into 3 reviewer agent bodies (`code-reviewer`, `consensus-arbiter`, `plan-validator`). `tests/unit/test_agent_body_partials.py::_EXPECTED_SHA256` (lines 107/119/122) pins their body hashes → all 3 must be recomputed **from the actual render** (run the test, copy the reported actual hashes; never hand-compute). The partial also dual-renders into Codex `.codex/agents/*.toml` (`developer_instructions`) via `synthesize` — the fix propagates automatically; no test pins that recipe content (verified). No snapshot fixture contains the flag (e2e fixtures have codex disabled).

**Guard test** — add a **test case to the existing** `tests/unit/test_render_codex_partial_include.py` (do NOT create a new file — it already exists with ~9 KB of codex-render assertions): render a reviewer with `codex_second_opinion.enabled=true` and assert the body contains no `--ask-for-approval`, while `codex exec` and `--sandbox read-only` ARE present.

**API Changes** — none. Rendered-recipe content only.

## 📝 Implementation Plan

### Phase 1 — guard test (RED)
- **depends_on:** `[]` | **parallel_group:** `serial-tdd` | **merge_hazards:** none
- **Scope in:** `tests/unit/test_render_codex_partial_include.py` — **append a new test case to the existing file** (Read first; do not overwrite). **Out:** all source.
- **Exit (RED now):** new test renders a codex-enabled reviewer body and asserts `--ask-for-approval` is NOT present (and `codex exec` + `--sandbox read-only` ARE present). RED today because the flag is rendered.
- **Risk:** low. **Rollback:** remove the added test case.

### Phase 2 — remove flag + re-baseline SHA (GREEN)
- **depends_on:** `[1]` | **parallel_group:** `serial-tdd` | **merge_hazards:** `second_opinion_codex.md.j2` + `test_agent_body_partials.py` (SHA baselines)
- **Scope in:** delete line 61 of the partial; update the 3 SHA256 baselines in `test_agent_body_partials.py`. **Out:** all else.
- **Exit:** Phase 1 guard GREEN; `test_agent_body_partials` GREEN with the 3 re-baselined hashes — obtained by running the test and copying the **actual** reported values (NOT hand-computed). Review the `git diff` of the rendered bodies (not just the hash) to confirm the only change is the deleted flag line.
- **Risk:** low. **Rollback:** `git checkout` both files.

### Phase 3 — full gate + version bump + CHANGELOG
- **depends_on:** `[1, 2]` | **parallel_group:** `serial-release` | **merge_hazards:** 5 version files
- **Scope in:** 5 version files + `CHANGELOG.md`.
- **Exit:** `ruff check` + `ruff format --check` + `mypy --strict src` + full `pytest` (incl. `test_render_codex*`, `test_agent_body_partials`, `test_synthesize_codex*`) green; 5-file bump **0.28.8→0.28.9**; CHANGELOG entry. (No tag push — user-initiated release step.)
- **Risk:** low. **Rollback:** `git checkout` version files.

## 🧪 Testing Strategy

- **Unit:** new guard test (no `--ask-for-approval`, `codex exec`/`--sandbox read-only` present) + re-baselined SHA pins + existing codex render/synthesize suites stay green.
- **No integration test** — rendering is pure logic; real Codex acceptance was smoke-proven this session and is not CI-gated (requires `codex login`).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SHA re-baseline masks an unintended body change | low | medium | Review `git diff` of the rendered bodies, not just the hash; the partial diff is exactly one deleted line |
| Phase 1 "(new test)" misread as new file → clobbers existing 9 KB | low | medium | Scope says **append to existing file**; Read-before-Write |
| Agents other than the 3 codex-enabled ones affected | very low | low | Partial is byte-zero when disabled; `test_agent_body_partials` stays green for all agents |

## ✅ Success Criteria

- [x] Rendered codex-enabled reviewer recipe contains no `--ask-for-approval`; still has `codex exec --sandbox read-only`.
- [x] `test_agent_body_partials` green — re-baseline was a NO-OP (those pins render codex-disabled, so the recipe is byte-zero there; recipe change invisible to them). Guard test in `test_render_codex_partial_include.py` covers the codex-enabled path instead.
- [x] Full gate green; `0.28.9` synced across 5 files + CHANGELOG.

## 🔍 Plan Validation

- **Validator outcome:** APPROVED (0 critical, 0 warning, 2 suggestions — both folded in: ADR Consequences now names the SHA re-baseline trade-off; Phase 1 scope clarified as append-to-existing-file).
- **Codex second opinion:** ⚠️ **skipped** — Bash/`codex exec` denied by the sandbox; verdict is Claude-only (warn-and-proceed). (Fitting, given this PLAN fixes the very recipe that call uses.)

## Non-Goals
- No change to other recipe flags (`--sandbox` / `--ignore-*` / `--json` / `--output-*`) — valid + intended.
- No codex-version detection / conditional flags.
- No git tag push.

## 🔧 Execution Log (/hm:execute — 2026-06-03)

Worktree `execute-11ec4770fdeb-20260602T1649Z`. TDD A→A.5→B→C→D.

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — guard test (RED) | ✅ DONE | `test_codex_recipe_has_no_invalid_ask_for_approval_flag` appended to existing `test_render_codex_partial_include.py`; test-reviewer PASS; RED confirmed (failure showed the rendered `--ask-for-approval never \` line). |
| 2 — remove flag + re-baseline SHA | ✅ DONE (re-baseline was a NO-OP) | Deleted line 61 of the partial → guard GREEN. **Execute-time discovery:** the 3 `test_agent_body_partials._EXPECTED_SHA256` pins are computed with `codex_second_opinion` **disabled** (the partial is byte-zero when disabled, per the file's own line-115 comment), so the recipe change is invisible to them — they stayed green, no re-baseline needed. The PLAN over-estimated blast radius (prior SHA bumps were for permissions blocks, which DO render in the default config). |
| 3 — full gate | ✅ DONE | ruff ✅ · format ✅ · mypy --strict (102 files) ✅ · full unit suite ✅ (exit 0). Codex `.codex/agents/*.toml` dual-render picks up the fix; no test pinned the flag there. |
| 4 — version bump + CHANGELOG | ✅ DONE | 5-file sync 0.28.8→**0.28.9**; CHANGELOG entry; version sync/drift tests pass. |

**Staged changeset (uncommitted — wrapup owns commit):** `M second_opinion_codex.md.j2` (−1 line) · `M test_render_codex_partial_include.py` (+guard test) · `M`×5 version files + `M CHANGELOG.md`. (No SHA-baseline file change — Phase 2 no-op above.)

**Bash-continuation note (test-reviewer advisory):** confirmed the deletion leaves `--sandbox read-only \` flowing into the `{%- if hermetic %}` block — valid; the codex smoke this session ran exactly that flag set successfully.
