---
type: plan
task_slug: second-opinion-multi-model
status: complete
created: 2026-07-09
tags: [harness-maker, plan, codex, antigravity, second-opinion, multi-model, jinja-templates, cli, interview]
research_doc: "[[RESEARCH-second-opinion-multi-model]]"
interview_rounds: 6
adrs: 12
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Generalize codex_second_opinion -> second_opinion with models:[codex,antigravity]; add make.md/CLI surface for second_opinion + autopilot"
---

## 🎯 Executive Summary

**TL;DR:** Rename/generalize `harness.yaml.codex_second_opinion` (single-vendor) into `second_opinion` with `models: list[Literal["codex","antigravity"]]`, so Codex CLI and Google's Antigravity CLI (`agy`, already installed, OAuth-authenticated) can each supply an independent cross-model second opinion, including both simultaneously. Also close a discovered pre-existing gap: `/harness-maker:make`'s interactive interview (`commands/make.md`) and its CLI (`cli.py make`) never surface `codex_second_opinion` or `autonomy`/autopilot at all today — only the Python `interview.py` `input()` fallback does. Both get added.

**What/Why:** harness-maker already has a proven single-vendor cross-model second-opinion architecture (PLAN-codex-second-llm-integration, PLAN-crossmodel-codex-gaps). This is a **generalization**, not new architecture: the MAIN-LOOP-owns-the-external-CLI-call pattern (ADR-002/003 of PLAN-codex-second-opinion-sandbox), the adapter/severity-mapping pattern, and the ledger-calibration pattern all extend cleanly to a second vendor. The two genuinely new risks are (1) `agy` has no `--output-schema` CLI-level JSON enforcement (Codex does) and (2) `agy`'s `--sandbox` filesystem-write guarantee is unverified (Codex's `--sandbox read-only` is documented and trusted).

**Key Decisions** (ADRs, see below): schema_version-gated silent migration (ADR-001), per-model config sub-blocks (ADR-002), uniform mandatory-matrix cost acceptance (ADR-003), shared severity vocabulary (ADR-004), ledger rename+model-field (ADR-005), K=2-fixed consensus semantics explicitly pinned (ADR-006), interview-time-only antigravity model shell-out (ADR-007), closed status enum for the plan-stage output contract (ADR-008), make.md/CLI surface for second_opinion+autopilot (ADR-009), make-time binary presence check (ADR-010), fail-closed antigravity adapter contract (ADR-011), and an empirical sandbox-write-probe gate before the antigravity template work begins (ADR-012).

**Estimated impact:** 7 phases across ~20 files (2 Pydantic models, 2 Python utility modules, ~11 Jinja templates, 2 command/CLI surfaces, ~15 test files renamed/extended + new coverage, 2 doc files). No new external dependencies. No breaking change for existing installs with `codex_second_opinion` configured (silent migration).

## 📚 Prior Work

- `work-docs/RESEARCH-second-opinion-multi-model.md` — recommended direction (generalize, don't rewrite), 10 pitfalls, 8 open questions, all resolved in this PLAN's interview.
- `work-docs/PLAN-codex-second-llm-integration.md` — original single-vendor architecture (ADR-001..009): MAIN-LOOP-owns-the-call pattern, permission injection via Jinja conditional, schema rendering via `_render_pure_json`.
- `work-docs/PLAN-crossmodel-codex-gaps.md` — k-of-3 consensus voting, severity adapter, null-location relaxation, ledger calibration.
- `work-docs/PLAN-codex-second-opinion-sandbox.md` — ADR-002/003 sandbox-escape architecture (`dangerouslyDisableSandbox` + `Bash(codex exec:*)` allow-rule pairing) this PLAN reuses verbatim for `agy`.
- `[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]` — the 3-anchor output-contract rule driving ADR-008's careful field placement.
- `[[wiki:gotcha:subagent-tools-field-hard-gates-bash-permission]]` — why the antigravity call also runs from the MAIN LOOP, not a tool-restricted subagent.
- `[[wiki:architecture:codex-second-llm-integration]]`, `[[wiki:model-routing-multi-ide]]` — precedent for the `default_model`/`recommended_model` silent-migration pattern reused in ADR-001.

## 🎙️ Interview Transcript

6 rounds total: 3 initial architecture rounds, 1 scope-addition round (make.md/autopilot gap), 1 critical-risk follow-up (post first plan-validator pass), 1 consensus-semantics follow-up (post second plan-validator pass).

| # | Topic | Category | Question (1 line) | Choice | → ADR |
|---|-------|----------|--------------------|--------|-------|
| 1 | Backward-compat strategy | Scope | `codex_second_opinion`→`second_opinion` migration approach | One-time silent migration + schema_version bump (2→3) | ADR-001 |
| 2 | Config field placement | Architecture | Shared vs per-model sub-block for hermetic/schema-path/antigravity-model | Per-model sub-block (`second_opinion.codex.*`, `second_opinion.antigravity.*`) | ADR-002 |
| 3 | Mandatory-matrix scope | Risk | Uniform across models vs one primary-mandatory | Uniform across all enabled models (2x cost accepted) | ADR-003 |
| 4 | Severity vocabulary | Contract | Reuse codex vocab vs direct P0–P3 | Reuse codex vocab (critical/high/medium/low/info) | ADR-004 |
| 5 | Ledger design | Observability | Same-file+model-field vs renamed-file vs split-files | Renamed file (`second-opinion.jsonl`) + `model` field | ADR-005 |
| 6 | Consensus voter/threshold | Architecture | Fixed absolute vs dynamic-proportional vs advisory-only | Dynamic pool, threshold TBD (resolved round 6) | ADR-006 |
| 7 | Antigravity model pin | Implementation | Hardcoded default vs live `agy models` shell-out | Live shell-out (with fallback default when `agy` absent) | ADR-007 |
| 8 | Output-contract shape | Contract | Dict-keyed-by-model vs array-of-results | Array: `second_opinion_results:[{model,status,reconciliation}]` | ADR-008 |
| 9 | make.md integration position | Scope | Default interview items vs advanced-options-only | Default interview, items 13/14 | ADR-009 |
| 10 | CLI presence check | Risk | Warn on missing `codex`/`agy` binary vs no check | Check + warn (`shutil.which`, non-blocking) | ADR-010 |
| 11 | Interview closure (round 3) | — | End interview? | Yes — proceed to plan write | — |
| — | *1st plan-validator pass: MAJOR_REVISION (1 critical, 8 warning, 2 suggestion)* | | | | |
| 12 | Antigravity sandbox risk gate | Risk | How to gate Phase 4 on the unverified `agy --sandbox` write guarantee | Add Phase 1 empirical write-probe (blocking gate) | ADR-012 |
| — | *Warnings 1,3,4,5,6,8,S1,S2 resolved directly by plan author (spec-completion, no new user judgment required); see ADR revisions below* | | | | |
| — | *2nd plan-validator pass: NEEDS_REVISION (0 critical, 3 warning)* | | | | |
| 13 | Consensus K-threshold semantics as N grows | Architecture | Fixed K=2 vs proportional majority as voter pool N grows | K=2 fixed (recall-favoring, no code change) | ADR-006 (pinned) |
| — | *Warnings "write-probe false-safe" and "merge_hazards/make.md ownership" resolved directly by plan author* | | | | |

## 📐 Architecture Decision Records

### ADR-001: Backward-compat via one-time silent migration + schema_version bump
**Status:** Accepted (2026-07-09, via /hm:plan interview)
**Context:** `codex_second_opinion` becomes `second_opinion` with a materially different shape (bool `enabled` → non-empty `models` list). Existing installed harnesses must not break.
**Decision:** Bump `schema_version` 2→3. `answers_from_harness_yaml` reads legacy `codex_second_opinion` when `second_opinion` is absent: `enabled:true` → `second_opinion.models:["codex"]` (carrying `hermetic`/`output_schema_path` into `second_opinion.codex.*`); `enabled:false`/absent → `models:[]`. **Precedence when BOTH keys are present** (validator-flagged gap, resolved): the NEW `second_opinion` key always wins; the legacy key is ignored with one advisory log line (sanitized against log-forging, matching the existing `default_model`/`recommended_model` precedent). This also covers the `schema_version>=3`-with-stale-legacy-key case — same precedence, same one-time advisory.
**Consequences:**
- ✅ Zero breakage for existing installs; matches the proven `default_model` rename precedent exactly.
- ⚠️ Two config vocabularies exist in old harness.yaml files until the user re-renders; documented, not enforced.
**Rejected alternatives:**
- Permanent deprecated alias — perpetuates two vocabularies forever in docs/code.
- Hard breaking change, no migration — violates the CLAUDE.md user-state-preservation contract (checklist item 1).
**Test requirements:** legacy-only round-trips to `models==["codex"]`; both-keys-present round-trips to the new key's value + one advisory log; `schema_version>=3`-with-stale-legacy-key ignores the legacy key.
**Source:** Interview #1; validator pass 1 warning (migration precedence), resolved directly.

### ADR-002: Per-model config sub-blocks; `agents` is a global allowlist
**Status:** Accepted (2026-07-09)
**Context:** `hermetic`/`output_schema_path` are Codex-only concepts (agy has no equivalent flags); antigravity needs its own `model` field. A shared top-level shape would silently no-op codex-only fields for antigravity (the "absent-case = feature black hole" pattern from CLAUDE.md's 2026-06-08 learned correction).
**Decision:** `second_opinion.codex.{hermetic, output_schema_path}` and `second_opinion.antigravity.{model}` are per-model sub-blocks. `second_opinion.failure_policy` (`"warn-and-proceed"` only) and `second_opinion.agents` (reviewer allowlist) stay shared/top-level. **`second_opinion.agents` semantics (validator-flagged gap, resolved):** it is a GLOBAL allowlist applied identically across every enabled model — an agent named in the list receives second opinions from every enabled model, not a subset; there is no per-model agent scoping.
**Consequences:**
- ✅ No silent no-op fields; the schema itself documents which knobs apply to which vendor.
- ⚠️ Slightly deeper nesting in harness.yaml than the current flat shape.
**Rejected alternatives:** all-shared top-level fields (footgun per above).
**Source:** Interview #2; validator pass 1 warning (`agents` ambiguity), resolved directly.

### ADR-003: Mandatory-matrix applies uniformly to every enabled model
**Status:** Accepted (2026-07-09)
**Context:** Production preset makes Codex second opinion "always run"; Side gates it on high-diff. With 2 possible models, does "mandatory" apply per-model or to one designated primary?
**Decision:** Applies uniformly — Production runs every enabled model on every validation/review; Side high-diff-gates every enabled model identically. User explicitly accepted the 2x external-CLI cost/latency when both models are enabled in Production.
**Consequences:**
- ✅ Simple, symmetric mental model — no "primary vs secondary" special-casing in templates.
- ⚠️ Real cost/latency doubling for users who enable both models in Production — documented in the make-time interview copy (Phase 5).
**Rejected alternatives:** single-primary-mandatory (safer cost profile, but user explicitly preferred uniform symmetric behavior).
**Source:** Interview #3.

### ADR-004: Antigravity reuses Codex's severity vocabulary
**Status:** Accepted (2026-07-09)
**Context:** Antigravity has no native severity taxonomy (it's asked to emit whatever we prompt for).
**Decision:** Antigravity findings request the same `critical|high|medium|low|info` vocabulary as Codex, against one shared schema file (`second-opinion-finding.schema.json`, renamed from `codex-finding.schema.json`). The severity-to-P-tier mapping function is shared (`map_severity`, renamed from `map_codex_severity`) between both adapters.
**Consequences:**
- ✅ Adapter code is ~90% shared between vendors; one schema file, one mapping table.
- ⚠️ Antigravity's compliance with the requested vocabulary is prompt-discipline only (no CLI-level enforcement) — see ADR-011's fail-closed contract.
**Rejected alternatives:** direct P0–P3 request (skips a translation layer but diverges from the shared schema file, forcing a second schema).
**Source:** Interview #4.

### ADR-005: Ledger renamed with a `model` field
**Status:** Accepted (2026-07-09)
**Context:** `codex-second-opinion.jsonl` is a single-vendor calibration ledger; cross-vendor precision comparison (codex vs antigravity) is itself valuable per the ledger's own stated purpose ("cross-time calibration record").
**Decision:** Rename `codex-second-opinion.jsonl` → `second-opinion.jsonl`; `SecondOpinionRecord` (renamed from `CodexSecondOpinionRecord`) gains `model: Literal["codex","antigravity"]`. One-time forward-copy: on first emit under the new name, if the legacy file exists and the new one doesn't, copy its rows forward tagged `model="codex"` (avoids orphaning existing calibration history).
**Consequences:**
- ✅ One file for cross-vendor comparison; no history loss for existing installs.
- ⚠️ Forward-copy is a user-state write and needs its own idempotency contract (see Phase 2 test matrix: old-only / new-only / both-present / malformed-old-row / duplicate-migration-attempt — the copy must be a no-op if the new file already has content, never double-appending).
**Rejected alternatives:** split-per-model files (loses cross-vendor comparison, the ledger's stated purpose).
**Source:** Interview #5.

### ADR-006: Consensus voter pool grows; threshold K stays fixed at 2 (pinned explicitly)
**Status:** Accepted (2026-07-09, refined 2026-07-09 after validator pass 2)
**Context:** `harness_maker.conditional_router.scope_aware_consensus` (invoked from `consensus-arbiter_body.md.j2`) implements `len(reviewers) >= 2 -> consensus-passed`, labeled `[K/N]`. This is a **fixed absolute rule**, not proportional to pool size N — ground-truth confirmed by reading the function, not inferred from template prose. Today's "k-of-3" (2 Claude reviewers + 1 Codex) already means K=2, N=3 (67% agreement). Adding antigravity raises N to 4 or 5 (50%/40% agreement) with the SAME K=2 rule, unless explicitly changed.
**Decision:** **K stays fixed at 2 regardless of N.** This is an intentional recall-favoring design: enabling more second-opinion models makes `consensus-passed` *easier* to reach (any 2 of however-many voices agreeing is sufficient), not harder — consistent with the feature's purpose (more cross-model coverage should surface more real issues, not gate them behind a rising bar). Zero Python code change is needed in `conditional_router.py` — only the hardcoded prose ("2 Claude reviewers + 1 Codex → k-of-3") in `review.md.j2` Step 3.5 and `consensus-arbiter_body.md.j2` becomes computed/generic text (`N = reviewers.enabled|length + second_opinion.models|length`), and the single-model "Codex null-location relaxation" paragraph becomes a loop over `source in second_opinion.models`.
**Consequences:**
- ✅ No new consensus-math code; lowest-risk generalization path.
- ✅ Explicit, tested behavior (not an implicit side-effect of adding a model) — Phase 6 adds a regression test asserting K=2 holds at N=3, N=4, and N=5 specifically (not just one example), proving this is a specified rule, not an assumption.
- ⚠️ The agreement *percentage* required for consensus silently drops as more models are enabled (67%→50%→40%) — this is the accepted, intentional trade-off, documented here so it is never mistaken for a bug.
**Rejected alternatives:** proportional-majority threshold (e.g. `ceil(N/2)`) — would require real changes to `conditional_router.py` and tightens the bar as models are added, the opposite of the chosen recall-favoring intent; advisory-only second-opinion models (never counted toward K) — rejected in interview as unnecessarily conservative, given the user's explicit intent for both models to have real voting power.
**Source:** Interview #6; validator pass 1 (ground-truth investigation); validator pass 2 warning (K semantics for N>3), resolved via Interview #13.

### ADR-007: Antigravity model pin — interview-time-only live shell-out; render never shells out
**Status:** Accepted (2026-07-09, refined 2026-07-09 after validator pass 2)
**Context:** `agy models` returns unstable free-text display names (no machine ID, no `--json` mode). harness-maker is a portable plugin — the machine running the interview may differ from the machine later running `/hm:` stages.
**Decision:** The `agy models` shell-out happens **ONLY in `interview.py`, at interview time** (offers a live current list; falls back to a hardcoded default — `"Gemini 3.1 Pro (High)"` — when `agy` is absent from the authoring machine, or the shell-out times out/errors). The chosen value is persisted as a free-text string in `second_opinion.antigravity.model`. **`render.py` and every Jinja template read this persisted value and NEVER shell out to `agy`** — this is a hard requirement, not an optimization, because it would otherwise violate the project's render-determinism invariant (CLAUDE.md checklist item 7: `freeze_time`, HOME-pinning, external APIs gated behind `INTEGRATION=1`).
**Consequences:**
- ✅ Offers a fresh model list at the one moment it's genuinely useful (interview) without threatening snapshot-test determinism.
- ⚠️ The interview-time shell-out itself needs a timeout + graceful degrade (agy absent/slow/erroring → fallback default, never a hung interview).
**Rejected alternatives:** shell out at render time too (rejected — breaks render determinism, the exact failure mode validator pass 2 flagged); pure hardcoded default only (rejected in interview — user prioritized freshness at the one safe point, interview time).
**Test requirements:** a render-path test asserting zero subprocess calls to `agy` during any render invocation; an interview-time test with `agy` absent from PATH exercising the fallback default.
**Source:** Interview #7; validator pass 2 warning (render-determinism conflict), resolved via ADR revision (no further user interview needed — this was a correctness fix, not a preference).

### ADR-008: Plan-stage output contract becomes `second_opinion_results` array with a closed status enum
**Status:** Accepted (2026-07-09, refined 2026-07-09 after validator pass 1)
**Context:** `codex_status`/`codex_reconciliation` scalar fields exist ONLY in the plan stage (`plan-validator_body.md.j2` + `stages/plan.md.j2`'s Step 4 pre-injection contract) — ground-truth confirmed the review stage has no equivalent persistent field (it just tags findings `source:"codex"` and folds them into Step 4's input list). So this rename is scoped to the plan-stage validator contract only.
**Decision:** `second_opinion_results: [{model, status, reconciliation}, ...]` (array, one entry per configured model) replaces the scalar `codex_status`/`codex_reconciliation` fields, in **all 3 anchors** (canonical schema block in `plan-validator_body.md.j2`, the dispatch `Task()` prompt in `stages/plan.md.j2`, and the shared `second_opinion_dispatch.md.j2` partial) per the `[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]` 3-anchor rule. **`status` is a closed `Literal["invoked","skipped","failed","timed_out","disabled"]`** (validator-flagged gap, resolved) — not a free string. **Invariant (tested):** every model in `second_opinion.models` produces exactly one `second_opinion_results` entry, covering the success, skip, and failure paths.
**Consequences:**
- ✅ Extends to a 3rd vendor later without adding new top-level keys (array, not a dict keyed by model name).
- ✅ Closed enum prevents status-string drift across the 3 anchors.
**Rejected alternatives:** dict keyed by model name (`{codex:.., antigravity:..}`) — harder to extend, and the array shape is more natural for the Jinja loop that produces it.
**Source:** Interview #8; validator pass 1 warning (status enum + cardinality), resolved directly.

### ADR-009: `/harness-maker:make` gets second_opinion + autopilot in the default interview; Non-Goals for the autopilot flag work
**Status:** Accepted (2026-07-09, refined 2026-07-09 after validator pass 1)
**Context:** `commands/make.md`'s actual AskUserQuestion-driven interview (12 items: locale/preset/dev_mode/targets/focus/mechanical_checks/grade_threshold/domains/wrapup_docs/ref_folders/sibling_repos/second_brain) never surfaces `codex_second_opinion` or `autonomy`/autopilot — confirmed by reading the file; these only exist in the Python `interview.py` `input()` fallback, and `cli.py make` has zero flags for either. User explicitly requested closing this gap mid-session.
**Decision:** Add 2 new items to the DEFAULT interview flow (not gated behind an "advanced options" branch) in BOTH the fresh-install (section 4.4) and full-reconfigure branches: item 13 (second-opinion models multi-select) and item 14 (autopilot enable/level/persistence). New `cli.py make` flags: `--second-opinion-models` (comma-separated; empty string or omitted leaves the existing value unchanged on a re-render, or defaults to `[]` on a fresh install; an unknown model name is a CLI error, not a silent drop; duplicate names are de-duplicated), `--autonomy-level` (`gated|auto_safe|full`; alone implies enabling autopilot with `autopilot_persistent` defaulting `False`), `--autonomy-persistent`/`--no-autonomy-persistent` (explicit boolean pair). Omitting all three autonomy flags leaves `AutonomyConfig()` (gated/off) unchanged from today's default.
**Non-Goals (validator-flagged scope-drift, resolved by explicit boundary, not by removing the work):** this phase touches ONLY the interview/CLI-flag surface for autopilot. It does **not** modify autopilot's runtime engine (`autopilot.py`/`autopilot_caps.py`), the per-session `.hm-autopilot` marker mechanism, or any auto-advance gate logic — those are unchanged and out of scope.
**Consequences:**
- ✅ Closes a real, user-confirmed onboarding gap; both new questions follow the existing "no follow-up sub-questions, advanced tuning via harness.yaml" minimalist pattern already established for `second_brain`/`codex_second_opinion` today.
- ⚠️ Slightly longer fresh-install interview (14 items instead of 12) — accepted per user's explicit choice (Interview #9) over gating behind advanced options.
**Rejected alternatives:** advanced-options-only gating (lower discoverability — rejected by user); splitting autopilot's CLI-flag work into its own separate PLAN (rejected as unnecessary process overhead — both new questions/flags live in the same 2 files, `commands/make.md` and `cli.py`, as second_opinion's own additions).
**Source:** Mid-session user request; Interview #9; validator pass 1 warning (flag semantics + scope-drift), resolved directly.

### ADR-010: Make-time CLI presence check (warn-only)
**Status:** Accepted (2026-07-09)
**Context:** Enabling a second-opinion model whose CLI isn't installed/authenticated silently degrades every review/plan validation to `status: skipped` (warn-and-proceed) — confusing on first use with no upfront signal.
**Decision:** `shutil.which("codex")` / `shutil.which("agy")` run when the corresponding model is selected in the make-time interview; a missing binary produces a loud, non-blocking warning (matches the existing warn-and-proceed failure policy) — never a hard gate.
**Consequences:**
- ✅ Prevents the confusing "why is my second opinion always skipped" first-run experience.
- ⚠️ Presence != authentication — a warning-free pass doesn't guarantee `codex login`/agy OAuth is valid; that failure mode still surfaces via the normal warn-and-proceed skip path at actual invocation time.
**Rejected alternatives:** no check (today's status quo for Codex) — rejected as a missed, cheap UX improvement.
**Source:** Interview #10.

### ADR-011: Two independent per-model transport partials, one shared dispatch loop; antigravity adapter is fail-closed
**Status:** Accepted (2026-07-09, refined 2026-07-09 after validator pass 1)
**Context:** Codex (`--output-schema`-enforced JSON, `--ignore-user-config` hermetic) and antigravity (no schema flag, no hermetic flag, free-text-model `--model` argument) have materially different transport recipes.
**Decision:** `agents/_partials/second_opinion_codex.md.j2` (renamed from `codex_exec_mainloop.md.j2`, content otherwise unchanged except config-field renames) and a NEW `agents/_partials/second_opinion_antigravity.md.j2` (stdin-piped prompt file → `agy --print --sandbox --model "<model>" < prompt_tmp > out_tmp; echo exit=$?`, no `--output-schema`/`--ignore-user-config` since agy has neither) are driven by a NEW shared `agents/_partials/second_opinion_dispatch.md.j2` that loops `config.second_opinion.models`, including the right per-model partial + ledger emit/skip-relay once per model. **Fail-closed contract for `adapt_antigravity_finding` (validator-flagged gap, resolved):** it strips ` ```json ` fences, then uses `json.JSONDecoder().raw_decode` to scan for the first balanced object. When it cannot identify **exactly one** valid payload (no match, multiple balanced objects found, partial/truncated object), it emits a ledger row `model="antigravity", status="failed"` and the caller treats it as a skip for consensus purposes — it never raises/crashes the dispatch loop.
**Consequences:**
- ✅ Each vendor's quirks are isolated in its own partial; the shared dispatch loop only orchestrates, never branches on vendor specifics.
- ⚠️ The antigravity adapter's tolerant parsing is inherently probabilistic (no CLI-enforced shape) — the fail-closed contract bounds the blast radius to "one lost vote, ledger-recorded" rather than a crash.
**Rejected alternatives:** single mega-partial with inline vendor branching (harder to reason about per-vendor quirks, rejected for maintainability).
**Test requirements (Phase 2):** adversarial-output matrix — no-json, multi-JSON-block, partial-object, prose-wrapped-json, oversized-output — each asserting the fail-closed ledger row, never a crash.
**Source:** Proposed architecture; validator pass 1 warning (fail-closed spec), resolved directly.

### ADR-012: Antigravity sandbox risk gated by an empirical write-probe before template work begins
**Status:** Accepted (2026-07-09, hardened 2026-07-09 after validator pass 2)
**Context:** `agy --sandbox`'s filesystem-write guarantee is **unverified** beyond the help text "Run in a sandbox with terminal restrictions enabled" — no confirmed read-only parity with Codex's documented `--sandbox read-only`. The existing safety model (ADR-002/003 of PLAN-codex-second-opinion-sandbox, CLAUDE.md's read-only-reviewer contract) presumes the second-opinion CLI cannot mutate the working tree it's reviewing. Validator pass 1 flagged this as **critical**: Phase 4 (templates) would otherwise be load-bearing on an assumption the plan itself already labeled unverified.
**Decision:** A new **Phase 1** (blocking gate on Phase 4) runs an empirical write-probe BEFORE any antigravity template work begins. **Hardened design (validator pass 2 flagged a false-safe-pass risk in the first draft — resolved):** the probe must (a) use an **imperative** prompt that forces an actual write attempt (e.g., "Create a file named `canary.txt` in the current directory containing the text `x`" — not an open-ended request the model could decline), (b) verify via `agy`'s own textual output/tool-call trace that it claims to have attempted the action (distinguishing "sandbox blocked it" from "model chose not to try"), and (c) run **3 adversarial variants** in a throwaway temp directory: create-new-file, modify-existing-file, delete-existing-file. Only if **all 3** variants show a confirmed attempt AND zero filesystem effect is the sandbox considered verified-safe. **Contingency:** if any variant succeeds in mutating the filesystem, Phase 4 is redesigned before it starts — antigravity invocations run only against a throwaway copy of the reviewed diff/context in an isolated temp directory, never the live worktree/main-loop's actual working tree.
**Consequences:**
- ✅ No template ships on an unverified safety assumption; the gate produces a real, falsifiable answer before the risk becomes load-bearing.
- ✅ The hardened 3-variant design specifically closes the false-safe-pass failure mode (model politely declining to write is not mistaken for the sandbox blocking a write).
- ⚠️ Adds a phase to the critical path before Phase 4 can start (mitigated: Phase 1 runs in `parallel_group: batch-a` alongside Phase 2, not serialized after everything else).
**Rejected alternatives:** proceed without verification, record as accepted-risk only (rejected — the live-worktree mutation risk during a "read-only reviewer" invocation is too severe to accept without at least one empirical check); always run antigravity against a throwaway copy regardless of probe result (rejected as premature — adds complexity/latency to every invocation when the probe may well confirm the sandbox is safe).
**Source:** Interview #12; validator pass 1 critical finding; validator pass 2 warning (probe hardening), resolved via Interview #12's decision + direct authorship of the hardened design.

## 🏗️ Technical Design

### Current State
- `models.py`: `CodexSecondOpinionConfig{enabled, agents, failure_policy, hermetic, output_schema_path}`; `HarnessConfig.codex_second_opinion`; `schema_version=2`.
- `interview.py`: `_ask_codex_second_opinion()` (bool enable, no model choice); `answers_from_harness_yaml` round-trips the flat shape.
- `codex_ledger.py`: `CodexSecondOpinionRecord`, `codex-second-opinion.jsonl`.
- `codex_adapter.py`: `map_codex_severity`, `adapt_codex_finding` (direct `json.loads`, assumes Codex's schema-enforced shape).
- Templates: `agents/_partials/codex_exec_mainloop.md.j2` (single-vendor transport recipe), Codex-only prose in `stages/review.md.j2` Step 3.5, `stages/plan.md.j2` Step 4 (pre), `consensus-arbiter_body.md.j2`, `plan-validator_body.md.j2`, `commands/hm/health.md.j2`, `harness-yaml/{Production,Side}.yaml.j2`, `settings/{Production,Side}.json.j2`.
- `commands/make.md`: 12-item interview (locale/preset/dev_mode/targets/focus/mechanical_checks/grade_threshold/domains/wrapup_docs/ref_folders/sibling_repos/second_brain) — no second_opinion, no autopilot.
- `cli.py make`: no `--second-opinion-*`/`--autonomy-*` flags.

### Affected Components
Config layer (models.py, interview.py) · persistence/observability (codex_ledger.py) · normalization (codex_adapter.py) · 11 Jinja templates (rendered into user harnesses) · harness-maker's OWN plugin surface (`commands/make.md`, `cli.py` — distinct from the rendered templates) · ~15 test files.

### Dependencies
No new external Python packages. Runtime dependency on the user having `agy` (Antigravity CLI) installed + OAuth-authenticated when antigravity is enabled — same posture as the existing Codex CLI + `codex login` dependency.

### Architecture (post-change)
```
harness.yaml
  second_opinion:
    models: [codex, antigravity]        # empty list = disabled
    agents: [code-reviewer, consensus-arbiter, plan-validator]   # global allowlist
    failure_policy: warn-and-proceed
    codex:
      hermetic: true
      output_schema_path: .claude/schemas/second-opinion-finding.schema.json
    antigravity:
      model: "Gemini 3.1 Pro (High)"     # free-text, interview-time-pinned

review.md.j2 / plan.md.j2
  Step 3.5/Step4(pre) --loop over second_opinion.models-->
    include second_opinion_dispatch.md.j2
      --> per model: include second_opinion_{codex|antigravity}.md.j2
          --> invoke CLI (main loop, dangerouslyDisableSandbox)
          --> adapt (codex_adapter.py: adapt_codex_finding | adapt_antigravity_finding)
          --> ledger emit (second_opinion_ledger — model-tagged row)
    findings folded into Step 4 consensus input, tagged source:"<model>"
    (plan stage only) second_opinion_results:[{model,status,reconciliation}] echoed by plan-validator
```

### Design Decisions
See ADR-001 through ADR-012 above — every non-trivial choice in this design is backed by an ADR.

### Data Flow
Unchanged from the existing single-vendor flow (MAIN LOOP invokes external CLI → adapts findings → folds into Step 4 consensus input / plan-validator reconciliation → ledger records disposition), now looped over N configured models instead of a single hardcoded Codex call.

### API Changes
- `harness.yaml.codex_second_opinion` → `harness.yaml.second_opinion` (migrated silently, ADR-001).
- `.claude/observability/codex-second-opinion.jsonl` → `.claude/observability/second-opinion.jsonl` (forward-copied, ADR-005).
- `.claude/schemas/codex-finding.schema.json` → `.claude/schemas/second-opinion-finding.schema.json` (ADR-004).
- Plan-validator JSON output: `codex_status`/`codex_reconciliation` → `second_opinion_results:[...]` (ADR-008, plan-stage only).
- New `cli.py make` flags: `--second-opinion-models`, `--autonomy-level`, `--autonomy-persistent`/`--no-autonomy-persistent` (ADR-009).

## 📝 Implementation Plan

### Phase 1 — Antigravity sandbox write-probe (gate)
- `depends_on`: `[]`
- `parallel_group`: `batch-a`
- `merge_hazards`: none (new standalone test file, touches no shared source)
- **Scope (in):** a new probe test (`tests/manual/ANTIGRAVITY_SANDBOX_PROBE.md` runbook + an automatable script/test) that runs `agy --print --sandbox --model "Gemini 3.1 Pro (High)"` with 3 imperative adversarial prompts (create-new-file, modify-existing-file, delete-existing-file) against a throwaway temp directory, verifying via `agy`'s own textual output that it attempted each action, then asserting zero actual filesystem effect for all 3.
- **Scope (out):** no changes to any shipped template or module — this phase is pure investigation + a permanent regression-guard test.
- **Exit criterion:** all 3 adversarial variants pass (confirmed-attempt + zero-filesystem-effect) → sandbox verified-safe, recorded in ADR-012; OR any variant shows filesystem mutation → Phase 4 is redesigned per ADR-012's contingency before it starts (throwaway-copy execution model), and this redesign becomes an explicit Phase 4 scope item.
- **Risk:** high (blocking gate — a "not yet safe" result changes Phase 4's design, not just its content)
- **Rollback:** n/a (investigation-only; no shipped code to revert)

### Phase 2 — Ledger + adapter generalization
- `depends_on`: `[]`
- `parallel_group`: `batch-a`
- `merge_hazards`: none (isolated modules: `codex_ledger.py`, `codex_adapter.py`, one schema file — no overlap with Phase 1's new test file or Phase 3's models.py)
- **Scope (in):** `codex_ledger.py` → `SecondOpinionRecord` (renamed from `CodexSecondOpinionRecord`) gains `model: Literal["codex","antigravity"]`; filename `codex-second-opinion.jsonl` → `second-opinion.jsonl`; one-time forward-copy on first emit (old-only/new-only/both-present/malformed-old-row/duplicate-attempt idempotency, per ADR-005). `codex_adapter.py` → shared `map_severity` (renamed) + unchanged `adapt_codex_finding` + new `adapt_antigravity_finding` (tolerant parse + fail-closed contract, ADR-011) + adversarial test matrix (no-json/multi-block/partial-object/prose-wrapped/oversized). `templates/schemas/codex-finding.schema.json` → `second-opinion-finding.schema.json`; `render.py`'s `_is_schemas_json` predicate updated for the new filename.
- **Scope (out):** no template changes yet (Phase 4); no models.py changes (Phase 3, which depends on this phase's final filename).
- **Exit criterion:** `uv run pytest tests/unit/test_codex_adapter*.py tests/unit/test_codex_ledger*.py` green including the new adversarial + idempotency matrices; a fenced-markdown antigravity sample payload adapts correctly via the tolerant path; a malformed/ambiguous payload produces a `status="failed"` ledger row, never a crash.
- **Risk:** medium
- **Rollback:** revert Phase 2 files only (independent of every other phase)

### Phase 3 — Config schema + migration
- `depends_on`: `[2]` (references Phase 2's final schema filename as the new default `output_schema_path` value)
- `parallel_group`: `serial-1`
- `merge_hazards`: `models.py`, `interview.py` (central, high blast radius — no other phase touches these 2 files, so no cross-phase collision, but internal edits must land atomically together)
- **Scope (in):** `models.py` — `SecondOpinionCodexConfig{hermetic, output_schema_path}`, `SecondOpinionAntigravityConfig{model}`, `SecondOpinionConfig{models, agents, failure_policy, codex, antigravity}`; `HarnessConfig.second_opinion`; `schema_version` 2→3. `interview.py` — `answers_from_harness_yaml` migration (ADR-001 precedence rule + both-present + stale-v3 test cases); `_ask_codex_second_opinion` → `_ask_second_opinion` (multi-select + antigravity model sub-prompt with live `agy models` shell-out + fallback default, ADR-007); `InterviewAnswers` mirror field.
- **Scope (out):** no CLI flags yet (Phase 5, which depends on this phase's final field names); no templates yet (Phase 4).
- **Exit criterion:** `uv run pytest tests/unit/test_models_codex_second_opinion.py tests/unit/test_interview_codex_second_opinion.py` green after rename/extension; a hand-written legacy-shape harness.yaml round-trips to `second_opinion.models == ["codex"]`; a both-keys-present harness.yaml round-trips to the new key's value + exactly one advisory log line; an `agy`-absent interview run falls back to the hardcoded default model string without hanging.
- **Risk:** medium
- **Rollback:** revert Phase 3 files to pre-phase commit

### Phase 4 — Template generalization
- `depends_on`: `[1, 2, 3]` (needs Phase 1's sandbox verdict to know which design to render, Phase 2's adapter/ledger interfaces, Phase 3's final config field names)
- `parallel_group`: `serial-2`
- `merge_hazards`: the 3-anchor output-contract set (`plan-validator_body.md.j2`, `stages/plan.md.j2`, `second_opinion_dispatch.md.j2`) must land together in one commit — a partial rename/update without its 2 anchors leaves the render in a broken intermediate state (per `[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]`). **Scope note (validator-flagged, resolved):** this phase's file set is `src/harness_maker/templates/**/*.j2` ONLY — the rendered templates shipped into user projects. It does NOT include `commands/make.md` (harness-maker's own plugin command source at the repo root) or `cli.py` — those are Phase 5, in an entirely disjoint directory tree, so there is no file-level collision between Phase 4 and Phase 5 despite both running without a dependency edge between them.
- **Scope (in):** rename `agents/_partials/codex_exec_mainloop.md.j2` → `agents/_partials/second_opinion_codex.md.j2`; new `agents/_partials/second_opinion_antigravity.md.j2`; new `agents/_partials/second_opinion_dispatch.md.j2` (loops `config.second_opinion.models`). `stages/review.md.j2` Step 3.5 loop + generic voter-count prose (N = `reviewers.enabled|length + second_opinion.models|length`, K=2 fixed per ADR-006) + null-location relaxation loop over `source in second_opinion.models`. `stages/plan.md.j2` + `plan-validator_body.md.j2` use `second_opinion_results` array + closed status enum (ADR-008), wired consistently across all 3 anchors. `consensus-arbiter_body.md.j2` same generalization as review. `commands/hm/health.md.j2` gets an antigravity smoke check (exit 0 + parseable JSON only — no schema-validity claim, since agy has no `--output-schema`). `harness-yaml/{Production,Side}.yaml.j2` render the new nested shape. `settings/{Production,Side}.json.j2` add a `Bash(agy:*)` allow-line conditional on antigravity being in `models`, PLUS a positive snapshot assertion that the dispatching main-loop context actually has bare `Bash` available (not just a conditional-render existence check) and a negative assertion that tool-restricted reviewer subagents do NOT gain `agy` execution permission.
- **Scope (out):** if Phase 1's probe found `agy --sandbox` unsafe, this phase's `second_opinion_antigravity.md.j2` scope EXPANDS to include the throwaway-copy execution redesign (ADR-012 contingency) — flagged here so `/hm:execute` knows to re-check Phase 1's verdict before starting.
- **Exit criterion:** full snapshot regen (`uv run pytest tests/unit/test_render_*.py --snapshot-update`, reviewed, then green without `--snapshot-update`); a rendered Production harness.yaml with `second_opinion.models: [codex, antigravity]` produces both `Bash(codex exec:*)` and `Bash(agy:*)` allow-lines in settings.json; the `Bash`-availability snapshot assertions above pass; a render-path test asserts zero subprocess calls to `agy` during render (ADR-007).
- **Risk:** high
- **Rollback:** revert Phase 4 commit; Phases 1–3 remain valid standalone

### Phase 5 — Make-time interview + CLI flags
- `depends_on`: `[3]` (needs Phase 3's final config field names to know what flags/questions to expose)
- `parallel_group`: `batch-b` (disjoint files from Phase 4 — see Phase 4's scope note — can run concurrently with it)
- `merge_hazards`: none (`commands/make.md` + `cli.py` are not touched by any other phase)
- **Scope (in):** `commands/make.md` — 2 new AskUserQuestion items (13: second-opinion models multi-select with `shutil.which` presence-check warning, ADR-010; 14: autopilot enable/level/persistence) in BOTH the fresh-install (section 4.4) and full-reconfigure interview lists; dispatch sections (4.6, 5) pass the new flags through. `cli.py` — `--second-opinion-models` (comma-separated, full semantics per ADR-009), `--autonomy-level`, `--autonomy-persistent`/`--no-autonomy-persistent`; `shutil.which("codex")`/`shutil.which("agy")` presence-check warnings wired before `InterviewAnswers` construction.
- **Scope (out):** no changes to `autopilot.py`/`autopilot_caps.py` or the runtime auto-advance engine — interview/CLI-flag surface only (ADR-009 Non-Goals).
- **Exit criterion:** `python -m harness_maker.cli make --second-opinion-models codex,antigravity --autonomy-level auto_safe <tmp-project>` renders a harness.yaml with the expected nested shape; running with `agy` absent from PATH prints the warning but still completes; tests cover empty/omitted/invalid/duplicate `--second-opinion-models` values and each autonomy flag combination (omitted / level-only / level+persistent / persistent-without-level).
- **Risk:** medium
- **Rollback:** revert Phase 5 files only

### Phase 6 — Test suite migration + new coverage
- `depends_on`: `[1, 2, 3, 4, 5]`
- `parallel_group`: `serial-3`
- `merge_hazards`: `test_agent_body_partials.py` SHA baselines must be regenerated AFTER Phase 4 lands, not before (they hash the rendered agent bodies Phase 4 changes)
- **Scope (in):** rename/extend the ~13 existing `codex`-named test files (`test_codex_mandatory_matrix.py`, `test_codex_review_consensus.py`, `test_codex_plan_pida.py`, `test_interview_codex_second_opinion.py`, `test_models_codex_second_opinion.py`, `test_synthesize_roundtrip_codex.py`, `test_render_codex_partial_include.py`, `test_render_codex_permission_injection.py`, `test_codex_health_smoke.py`, `test_agent_body_partials.py` SHA baselines) to cover the new shape + `models` parametrization; add `test_render_second_opinion_antigravity.py`; add the consensus-math regression test (feeding synthetic findings tagged `claude`/`codex`/`antigravity` through `scope_aware_consensus`, asserting K=2-fixed holds at N=3, N=4, AND N=5 specifically — not one example — proving ADR-006's rule empirically); demote the live dual-CLI smoke test to `INTEGRATION=1`-guarded optional (not a required CI gate — CI cannot guarantee both `codex` and `agy` are installed+authenticated); the REQUIRED CI gate for this phase is mocked-CLI + parser/schema tests only.
- **Exit criterion:** `uv run pytest` full suite green (mocked-CLI path, always required); `INTEGRATION=1 uv run pytest tests/integration/test_second_opinion_live.py` green when both `codex` and `agy` are installed and authenticated (optional, manual-run confidence check, never a CI blocker).
- **Risk:** medium
- **Rollback:** revert Phase 6 only; Phases 1–5 remain functionally complete without full test coverage (not shippable as-is, but revertable in isolation)

### Phase 7 — Documentation
- `depends_on`: `[1, 2, 3, 4, 5, 6]`
- `parallel_group`: `serial-4`
- `merge_hazards`: none
- **Scope (in):** CLAUDE.md "Codex dual role" (ADR-009 of the codex-second-llm-integration PLAN) + "Cross-model deepening" sections rewritten for the `second_opinion`/`models` shape; CHANGELOG.md entry.
- **Exit criterion:** an automated `rg` staleness gate — zero non-migration hits for `codex_second_opinion`, `codex_status`, `codex_reconciliation`, `codex-second-opinion.jsonl`, `codex-finding.schema.json` (allowlisting the migration-code references themselves, which legitimately still mention the legacy names).
- **Risk:** low
- **Rollback:** revert Phase 7 only

## 🧪 Testing Strategy

- **Unit (mock-first, per CLAUDE.md test policy):** config round-trip (legacy + new shapes, both-present precedence), adapter (both vendors, adversarial antigravity matrix), ledger (forward-copy idempotency matrix), render (snapshot regen, zero-shellout-at-render, Bash-availability assertions), CLI flag parsing (empty/invalid/duplicate values), consensus-math regression (K=2 fixed at N=3/4/5).
- **Integration (`INTEGRATION=1`-gated, optional):** live dual-CLI smoke test — demoted from a required CI gate per ADR resolution (validator suggestion S2); run manually or in a nightly job where both `codex` and `agy` are installed+authenticated.
- **Manual:** Phase 1's antigravity sandbox write-probe is itself a manual-first investigation (documented as a runbook) before being locked in as an automated regression guard.

## ⚠️ Risks & Mitigation

| Risk | Phase | Severity | Mitigation |
|------|-------|----------|------------|
| `agy --sandbox` may not block filesystem writes | 1, 4 | High (blocking) | Empirical 3-variant write-probe gate (ADR-012) before any antigravity template ships; contingency redesign (throwaway-copy execution) if unsafe |
| Antigravity's unenforced JSON output produces malformed/adversarial responses | 2, 4 | Medium | Fail-closed adapter contract (ADR-011): unparseable payload → `status:"failed"` ledger row, never a crash; adversarial test matrix |
| Consensus agreement bar silently drops as more models are enabled (67%→50%→40%) | 4, 6 | Medium (accepted, documented) | ADR-006 pins K=2 as an explicit, intentional recall-favoring decision, not a side-effect; regression test at N=3/4/5 |
| Live `agy models` shell-out threatens render determinism | 3, 4 | Medium | Restricted to interview-time only (ADR-007); render-path test asserts zero `agy` subprocess calls |
| `Bash(agy:*)` allow-rule inert without bare `Bash` on the consuming context (recurring gotcha) | 4 | Medium | Positive/negative snapshot assertions; reuses the proven MAIN-LOOP-owns-the-call pattern (never a tool-restricted subagent) |
| Migration ambiguity when both `codex_second_opinion` and `second_opinion` keys present | 3 | Medium | Explicit precedence in ADR-001 (new key wins, one advisory) + dedicated test case |
| `second_opinion.agents` semantics unclear with multiple models | 3 | Low | Explicit "global allowlist across all models" decision in ADR-002 |
| Bundling autopilot's make.md/CLI surface into this PLAN's scope | 5 | Low | Explicit Non-Goals boundary in ADR-009 (interview/CLI-flag surface only, no runtime-engine changes) |
| Test-suite migration touches ~13 files, risk of missed rename | 6, 7 | Low | Automated `rg` staleness gate (Phase 7) as a final backstop, not just Phase 6's unit coverage |

## ✅ Success Criteria

- [x] `harness.yaml.second_opinion.models` supports `["codex"]`, `["antigravity"]`, `["codex","antigravity"]`, and `[]`, with silent migration from any existing `codex_second_opinion` config.
- [x] Both Codex and Antigravity can be invoked as independent second-opinion voters in the same `/hm:review`/`/hm:plan` run when both are enabled.
- [x] Antigravity's `agy --sandbox` write behavior is empirically verified (or the throwaway-copy contingency is implemented) before shipping.
- [x] Consensus K=2-fixed behavior is explicitly tested at N=3, N=4, and N=5.
- [x] `/harness-maker:make`'s fresh-install and full-reconfigure interviews both surface second-opinion model selection and autopilot configuration.
- [x] `python -m harness_maker.cli make` supports `--second-opinion-models` and `--autonomy-*` flags with fully specified semantics.
- [x] Full `uv run pytest` suite green; `rg` staleness gate finds zero non-migration references to the renamed identifiers.
- [x] CLAUDE.md's Codex-only prose is rewritten to describe the multi-model `second_opinion` architecture.

## 🔍 Plan Validation

**Validator outcome: NEEDS_REVISION_RESOLVED** (2 passes).

- **Pass 1 — MAJOR_REVISION** (1 critical, 8 warning, 2 suggestion). Critical (antigravity sandbox write-guarantee unverified, Phase 4 load-bearing on it) resolved via a new Phase 1 empirical write-probe gate + ADR-012 (Interview #12). All 8 warnings + 2 suggestions resolved directly by the plan author (spec-completion items not requiring new user judgment): migration precedence (ADR-001), `agents` semantics (ADR-002), render-determinism fix (ADR-007), status enum + cardinality (ADR-008), Phase 1↔2 dependency reversal, autopilot flag semantics + Non-Goals (ADR-009), fail-closed adapter contract (ADR-011), consensus regression test requirement, automated staleness gate (Phase 7), demoted live-smoke requirement (Phase 6).
- **Pass 2 — NEEDS_REVISION** (0 critical, 3 warning; validator confirmed the critical was substantively resolved). Warnings: (a) the Phase 1 probe design could false-pass (model declining to write vs sandbox blocking it) — resolved by hardening the probe to force imperative write attempts + verify via agy's own output + run 3 adversarial variants (ADR-012 refinement); (b) consensus K-threshold semantics for N>3 were asserted by example only, not specified as a rule — resolved via Interview #13 (K=2 fixed, explicitly pinned in ADR-006) plus a regression test at N=3/4/5; (c) missing `merge_hazards` field + a flagged (but ultimately false) Phase 4/Phase 5 file collision on `make.md` — resolved by adding `merge_hazards` to every phase and clarifying that `commands/make.md` (Phase 5, harness-maker's own plugin source) is disjoint from `src/harness_maker/templates/**/*.j2` (Phase 4, the rendered user-facing templates).
- Per stage policy (NEEDS_REVISION → resolve warnings directly or via follow-up interview, then write PLAN — no further re-validation required), this PLAN is now written without a third validator pass.
