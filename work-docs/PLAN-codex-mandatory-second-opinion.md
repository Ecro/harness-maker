---
type: plan
task_slug: codex-mandatory-second-opinion
status: complete
created: 2026-05-25
tags: [harness-maker, plan, jinja2, codex, plan-validator, second-llm]
research_doc: "[[RESEARCH-codex-second-llm-integration]]"
interview_rounds: 4
adrs: 4
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "enabled=true forces Codex in plan-validator (MAY→MUST) + reconciliation; array reviewers deferred"
---

# PLAN — Codex second opinion: mandatory in plan-validator

## 🎯 Executive Summary

**TL;DR:** Today `codex_second_opinion.enabled=true` only *permits* a reviewer to call Codex ("You MAY invoke…, opt-in per call"). LLMs correctly decline when findings are file:line-confirmable, so Codex never fires — the second opinion is dead config. This PLAN flips the contract **for `plan-validator`**: when `enabled=true`, calling Codex becomes **mandatory** (MAY→MUST), the validator **must explicitly reconcile** each Codex finding, and a skipped/failed call is **loudly surfaced** to the user. The Claude verdict stays authoritative (ADR-005 of [[PLAN-codex-second-llm-integration]] preserved). `code-reviewer` and `consensus-arbiter` are **out of scope** — they emit top-level JSON arrays through a two-pass→verifier→consensus pipeline that needs its own design; deferred to a follow-up PLAN.

**What / Why:** The opt-in design (prior ADR-001, spend-control) over-delegated the call decision to runtime LLM discretion. The observed incident: `/hm:plan` plan-validator produced a MAJOR_REVISION verdict that was 100% Claude-derived; Codex was available + logged in but never invoked, because the prompt said the call was optional. plan-validator is also the *clean* integration point — single object output read directly by `/hm:plan` Step 4, no review pipeline. Fixing it first delivers the incident's value at the lowest risk.

**Key Decisions:**
- `enabled=true` *is* mandatory; opt-in mode removed — but rolled out **per-agent**: plan-validator now, the two array reviewers in a follow-up (ADR-001 + ADR-004).
- Forced-attempt + warn-and-proceed + **loud** on failure; never hard-fail (ADR-002).
- plan-validator output gains **top-level** `codex_status` + `codex_reconciliation` keys, with an **anti-boilerplate floor**; verdict stays Claude-derived (ADR-003).
- Scope = plan-validator only; array reviewers deferred (ADR-004).

**Estimated impact:** ~1 conditional partial edit (branch on `name`) + 1 prose relay in `plan.md.j2` Step 4 + model/interview copy + tests + preset/CHANGELOG. No new config field, no schema migration, no review-pipeline change. Behavior change only for plan-validator under `enabled=true`.

## 📚 Prior Work

- [[PLAN-codex-second-llm-integration]] (2026-05-24) — introduced the mechanism. This PLAN supersedes its **ADR-001** (opt-in for spend) *for plan-validator only*; preserves ADR-005 (verdict Claude-derived), ADR-006 (hermetic), ADR-007 (Jinja-conditional permission injection), ADR-008 (schema render path). ADR-003 (warn-and-proceed) is kept but made **loud**.
- [[RESEARCH-codex-second-llm-integration]] — `codex exec` transport, hermetic flags, `--output-schema` enforcement.
- CLAUDE.md "LLM 활용 원칙" — the forcing is a prompt-contract change inside the rendered command, not a Python rule.
- CLAUDE.md checklist #2 (parser integrity): plan-validator output is a top-level object read as free-text JSON by `/hm:plan` Step 4; two extra top-level keys are additive — the consumer ignores unknown keys.
- **Ground-truth note (verified during validation):** `code-reviewer` (`two_pass_review.py:81` "Return findings as a JSON array") and `consensus-arbiter` (`consensus-arbiter_body.md.j2:96` "JSON list of findings") emit top-level **arrays**, and `merge_passes` rebuilds a list — an envelope/sibling-key cannot survive. This is *why* they are deferred (ADR-004).

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|-------|----------|----------|--------|------|-------|
| 1 | 1 | Forcing model | Architecture | How strong is "force" — overturn ADR-001 spend + ADR-005 verdict? | **A** force-call / verdict-Claude | Smallest delta; ADR-005 preserved | ADR-001, ADR-003 |
| 2 | 2 | Failure policy | Failure handling | codex unavailable under MUST-call → ? | **B** warn+loud | Loud visibility, no block; autoloop-safe | ADR-002 |
| 3 | 2 | Config shape | Contract | How to encode "force"? | **A** enabled=mandatory (drop opt-in) | No new field; behavior change intended | ADR-001 |
| 4 | 2 | Reconciliation | Contract | Force Claude to address each codex finding? | **A** yes, `codex_reconciliation` block | Prevents "forced theater"; verdict still Claude | ADR-003 |
| 5 | 3 | Spend / dedup | Risk | Per-agent multiplication under k-of-n; dedup? | **A** per-agent independent, no dedup | Moot for plan-validator (single dispatch) | ADR-004 |
| 6 | 4 | Scope / sequencing | Scope | After validator pass-2 revealed array-reviewer pipeline complexity, how to sequence? | **1** plan-validator now, array reviewers follow-up | New verified evidence (top-level arrays + verifier reduction) | ADR-004 |

(Round 2 self-correction recorded: the interviewer's "review당 codex 1회" framing was inaccurate; clarified per-agent in Round 3, then mooted by the Round 4 scope-narrowing.)

## 📐 Architecture Decision Records

### ADR-001: `enabled=true` is mandatory — opt-in removed, rolled out per-agent (plan-validator first)
**Status:** Accepted (2026-05-25, via /hm:plan interview Rounds 1+2, scope-narrowed Round 4)
**Context:** Prior ADR-001 of [[PLAN-codex-second-llm-integration]] made the Codex call opt-in per-call for spend control. In practice the reviewer LLM always declines when findings are file:line-confirmable, so Codex never fires — the config is inert. The incident occurred in plan-validator specifically.
**Decision:** When `codex_second_opinion.enabled=true` AND the agent is in `agents[]`, invoking Codex is **mandatory** — the rendered partial says **MUST**, not MAY. No `mode`/`required` knob is added; `enabled` carries the full meaning. **Rollout is per-agent:** this PLAN flips `plan-validator` only. `code-reviewer` and `consensus-arbiter` keep the current opt-in **MAY** text until the follow-up PLAN (ADR-004). So `enabled=true` has, transitionally, mandatory semantics for plan-validator and opt-in for the other two — documented in CHANGELOG.
**Consequences:**
- ✅ Single boolean; no schema migration; the inert-config failure mode is eliminated for plan-validator.
- ✅ Lowest-risk delivery of the incident's value (plan-validator is the clean object-output case).
- ⚠️ **Accepted migration risk (explicit, not CHANGELOG-only):** a harness with `enabled=true` gets plan-validator's MAY→MUST behavior + two new top-level output keys on next render. User chose this binary knowingly (Interview #3). No `schema_version` gate; the existing **drift banner** (already nudging `/hm:make --update`) is the render-time signal — a warning would contradict "강제로 되도록".
- ⚠️ Transitional inconsistency: `enabled=true` ≠ uniform behavior across the 3 agents until the follow-up lands. Acceptable and documented.
**Rejected alternatives:**
- `mode: advisory|required` field (Round 2 Opt B) — rejected for config simplicity.
- `required: bool` (Round 2 Opt C) — rejected; lower extensibility, still adds a field.
**Source:** Interview #1, #3, #6

### ADR-002: Forced-attempt + warn-and-proceed + loud (prose relay); never hard-fail
**Status:** Accepted (2026-05-25, via /hm:plan interview Round 2; relay-mechanism corrected in validation)
**Context:** Once the call is mandatory, an unavailable Codex (no `codex login`, rate limit, network, schema rejection) needs a defined behavior. Prior ADR-003 was silent warn-and-proceed.
**Decision:** On any non-zero Codex exit, plan-validator does **not** block — it proceeds Claude-only (preserving prior ADR-003's autoloop safety) **but reports the skip loudly**, a two-part contract:
1. **Agent side** (Phase 1, partial): plan-validator sets top-level `codex_status: "skipped"` + `codex_skip_reason` in its output object (ADR-003 placement).
2. **Stage side** (Phase 2): `/hm:plan` Step 4, after reading the plan-validator `Task` return and before resolving APPROVED/NEEDS_REVISION/MAJOR_REVISION, surfaces the skip reason to the user. **This relay is written as PURE PROSE** — a natural-language instruction to the LLM, containing **no** `Bash(...)` / `Task(...)` / `request_user_input` / `AskUserQuestion` token — so it renders identically across the `{% if is_codex %}` command-syntax switch and needs no `is_codex` branch. (Validation correction: `is_codex` blocks in `plan.md.j2`/`review.md.j2` are inline command-syntax/tool-name dual-render switches — e.g. `review.md.j2:48` `Bash("uv run…")` vs `!`-syntax, `plan.md.j2:106` `request_user_input` vs `AskUserQuestion` — NOT `.codex/` file-target gates.)

Hard-fail is rejected because the verdict is Claude-derived (ADR-003) and is valid without Codex.
**Consequences:**
- ✅ Autoloop never deadlocks on a missing/throttled Codex.
- ✅ The "forced but silently skipped" regression (this task's trigger) becomes visible.
- ✅ Pure-prose relay sidesteps the dual-render trap entirely — no `is_codex` interaction.
- ⚠️ A user who ignores the loud note still gets a Claude-only verdict — acceptable; loudness ≠ blocking.
**Rejected alternatives:**
- Silent warn-and-proceed (Round 2 Opt A) — rejected; reproduces the invisibility this task fixes.
- Hard-fail / stage block (Round 2 Opt C) — rejected; blocks a valid Claude verdict on an availability accident.
- Command/tool-bearing relay placed "outside `is_codex`" (my pass-1 resolution) — rejected; mischaracterized `is_codex` and would render malformed for one variant. Pure prose is the fix.
**Source:** Interview #2

### ADR-003: plan-validator gains top-level `codex_status` + `codex_reconciliation`; anti-boilerplate floor; verdict stays Claude
**Status:** Accepted (2026-05-25, via /hm:plan interview Round 2; placement confirmed in validation). Preserves ADR-005 of [[PLAN-codex-second-llm-integration]].
**Context:** Forcing the call without forcing its *use* yields "theater" — Codex runs, Claude ignores the JSON. plan-validator's output is a **top-level object** (`{overall_assessment, critiques[], clean_categories[]}`), so sibling keys attach cleanly (unlike the array reviewers — see ADR-004).
**Decision:**
- **Placement:** add two **top-level** keys to plan-validator's output object: `codex_status: "invoked" | "skipped"` and `codex_reconciliation` (array). On `skipped`: `codex_skip_reason: string` and `codex_reconciliation: []`. On `invoked`: one entry per Codex finding `{codex_finding_ref, disposition: "accepted" | "rejected" | "duplicate", reason}`.
- **Anti-boilerplate floor:** every entry's `codex_finding_ref` **must cite the specific Codex finding** — its `file:line` (when present) or a verbatim quote of the Codex `message`. A bare `"rejected: n/a"` with no reference does NOT satisfy the contract.
- `overall_assessment` is still computed by Claude (ADR-005 preserved) — Codex is *input that cannot be silently discarded*, not a verdict source.
**Consequences:**
- ✅ "Forced call" becomes a forced *consideration*; audit trail tying each disposition to a concrete Codex finding.
- ✅ ADR-005 untouched — no verdict-merge math.
- ✅ Clean for plan-validator's object schema; no review-pipeline interaction.
- ⚠️ Output gains 2 top-level keys; additive, `/hm:plan` Step 4 ignores unknowns.
**Rejected alternatives:**
- No reconciliation, Claude discretion (Round 2 Opt B) — rejected; leaves the theater hole open.
- Boilerplate disposition without a finding reference — rejected; reduces "mandatory" to decorative.
**Source:** Interview #2

### ADR-004: Scope = plan-validator only; code-reviewer + consensus-arbiter deferred to follow-up PLAN
**Status:** Accepted (2026-05-25, via /hm:plan interview Round 4, on validator pass-2 evidence)
**Context:** The user's initial intent ("다른 설정된 reviewer 들도 마찬가지") predated the discovery that `code-reviewer` and `consensus-arbiter` emit top-level **JSON arrays** (verified: `two_pass_review.py:81`, `consensus-arbiter_body.md.j2:96`) flowing through two-pass redaction → Pass 1.5 verifier (KEEP/DROP/DEMOTE, *reduces* findings) → consensus merge (`merge_passes` rebuilds a list). A reconciliation envelope cannot survive that pipeline, and a synthetic finding entry risks being legitimately dropped by the verifier.
**Decision:** This PLAN forces + reconciles **plan-validator only**. The two array reviewers keep their current opt-in MAY behavior. Forcing them — with pipeline-preserving handling (verifier-exempt codex entries, consensus pass-through) — is a **follow-up PLAN** (`PLAN-codex-mandatory-array-reviewers`, TBD).
**Consequences:**
- ✅ Eliminates both validator pass-2 criticals (array-vs-object placement; relay-axis) from this PLAN's risk surface.
- ✅ Delivers the incident's actual fix (plan-validator) fast and low-risk.
- ⚠️ `enabled=true` is transitionally non-uniform across agents until the follow-up (see ADR-001).
- ⚠️ k-of-n multiplication (prior Round 3 concern) is moot here — plan-validator is dispatched once per `/hm:plan`; it re-enters scope in the follow-up.
**Rejected alternatives:**
- All 3 now via native-array-entry reconciliation (Round 4 Opt 2) — rejected; verifier/consensus pipeline preservation is real work + drop risk; out of proportion to the incident.
- All 3 now, array reviewers prose-only loud-skip (Round 4 Opt 3) — rejected; mixes contract depth across agents and still touches the review pipeline.
**Source:** Interview #6 (sequencing)

## 🏗️ Technical Design

### Current State
- `templates/agents/_partials/second_opinion_codex.md.j2` — shared partial, rendered into all 3 reviewer bodies when `enabled` AND `name in agents`. Says "You **MAY** invoke … opt-in per call"; title `## Optional: Codex second opinion`. Has access to `name`. Disabled branch is byte-zero via `{%- … -%}`.
- `templates/agents/plan-validator_body.md.j2` — output is a top-level object `{overall_assessment, critiques[], clean_categories[]}`; includes the partial at the end (line 92).
- `templates/agents/{code-reviewer,consensus-arbiter}_body.md.j2` — top-level **arrays** (deferred; unchanged by this PLAN).
- `templates/stages/plan.md.j2` — Step 4 (≈line 349) reads the plan-validator `Task` return; no Codex relay today. `is_codex` blocks (≈106/182/217) are inline tool-name syntax switches.
- `models.py::CodexSecondOpinionConfig` — `enabled: bool=False`, `agents[]`, `failure_policy: Literal["warn-and-proceed"]`, `hermetic`, `output_schema_path` (+validator). Docstring frames it as opt-in.
- `interview.py::_ask_codex_second_opinion` — y/n prompt; copy says reviewers "may invoke `codex exec`".
- Tests: `test_render_codex_partial_include.py` asserts only on the `@hm:codex-second-opinion` marker.

### Affected Components
| Component | Change |
|-----------|--------|
| `templates/agents/_partials/second_opinion_codex.md.j2` | **Branch on `name`**: `plan-validator` → MUST + top-level `codex_status`/`codex_reconciliation` + floor + loud-skip; else → keep current MAY/opt-in text |
| `templates/stages/plan.md.j2` (Step 4) | **pure-prose** relay: if `codex_status=skipped`, surface reason before verdict resolution |
| `models.py::CodexSecondOpinionConfig` | docstring: enabled=mandatory (per-agent rollout) — no field change |
| `interview.py::_ask_codex_second_opinion` | prompt copy: enabling = mandatory second opinion (plan-validator) |
| `templates/harness-yaml/{Production,Side}.yaml.j2` | comment wording near `codex_second_opinion` |
| tests | extend partial-include (plan-validator forced; other 2 unchanged) + interview copy |
| CHANGELOG + 5 version files | release entry; intended-behavior-change + per-agent-rollout note |

### Dependencies
None added. `code-reviewer`/`consensus-arbiter` bodies, `review.md.j2`, `two_pass_review.py`, `codex_permission_line.md.j2`, the schema JSON, and the `output_schema_path` validator are all untouched.

### Design Decisions
- **Single partial, branched on `name`** — the partial already receives `name`; `{% if name == 'plan-validator' %}` selects the mandatory contract, `{% else %}` keeps the unchanged MAY text. The `@hm:codex-second-opinion` marker is emitted in both branches (existing tests assert marker presence for all enabled agents).
- **Top-level keys** (`codex_status`, `codex_reconciliation`) on plan-validator's object output — clean because it is the one object-shaped schema (ADR-003/ADR-004).
- **Anti-boilerplate floor** — each reconciliation entry cites the Codex finding `file:line`/`message`.
- **Pure-prose stage relay** — no command/tool token, so no `is_codex` dual-render needed (ADR-002).
- No Python schema change keeps `synthesize`/`interview` round-trip and `models` strict-validation intact.

### Non-Goals (explicit)
- **code-reviewer / consensus-arbiter forcing** — deferred to follow-up PLAN (array output + two-pass/verifier/consensus preservation). They keep opt-in MAY here.
- **Verdict merge / Codex-counting** — Codex never changes `overall_assessment` (Round 1 B/C rejected; ADR-005 preserved).
- **Codex-first / ensemble rebalance** — Claude stays primary.
- **Hard-fail on Codex unavailable** — rejected (ADR-002); warn-and-proceed only.
- **New config field / `schema_version` gate** — rejected (ADR-001).
- **MCP transport / `codex_permission_line.md.j2` / output schema JSON / validator** — untouched.

### Data Flow
`harness.yaml(enabled=true)` → render → partial (plan-validator branch) emits MUST recipe + top-level output contract → `/hm:plan` Step 4 dispatches plan-validator → validator runs `codex exec` (mandatory); success: reconcile each finding into `codex_reconciliation`, `codex_status=invoked`; failure: `codex_status=skipped`+reason, proceed Claude-only → Step 4 reads the object return → if skipped, prose-surfaces the reason to the user → resolves Claude verdict.

### API Changes
plan-validator output object gains two **additive** top-level keys (`codex_status`, `codex_reconciliation`). No removals. `overall_assessment` semantics unchanged (ADR-003).

## 📝 Implementation Plan

> **Rollback model:** each phase is git-self-contained and **independently revertible to HEAD** — disjoint files (partial / stage+model+interview / tests / docs+version). The only cross-phase coupling (Phase 1 emit + Phase 2 relay) is degraded-but-not-broken on isolated revert (an emitted `codex_status` with no relay is simply unused).

### Phase 1 — Branch the shared partial for plan-validator
- **Scope (in):** `src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2` only. Inside the existing `enabled AND name in agents` block, add `{% if name == 'plan-validator' %}` → mandatory contract: "**MUST** invoke" (drop "MAY"/"opt-in per call"), title `## Required: Codex second opinion`, keep the `@hm:codex-second-opinion` marker + hermetic Bash recipe + `{%- … -%}` controls verbatim, add the **top-level** `codex_status`/`codex_reconciliation` output requirement, the anti-boilerplate floor (cite finding `file:line`/`message`), and the loud-skip instruction (`codex_status:"skipped"`+`codex_skip_reason`, proceed Claude-only). `{% else %}` → emit the **current MAY/opt-in text unchanged** (code-reviewer, consensus-arbiter).
- **Scope (out):** stages, `models.py`, `interview.py`, tests, the array reviewer bodies.
- **Exit criterion:** `uv run pytest tests/unit/test_render_codex_partial_include.py tests/unit/test_agent_body_partials.py -v` green AND a render with `enabled=True`: the **plan-validator** body contains `MUST`, `codex_reconciliation`, `codex_status`, the finding-reference floor language, the marker, and NOT `MAY invoke`/`opt-in per call`; the **code-reviewer** and **consensus-arbiter** bodies STILL contain `MAY`/`opt-in per call` + the marker (unchanged); with `enabled=False` all 3 contain none (byte-zero).
- **Risk:** low
- **Rollback point:** `git revert` → HEAD (single partial; restores uniform MAY).

### Phase 2 — Prose relay in plan stage + model/interview copy
- **Scope (in):** `src/harness_maker/templates/stages/plan.md.j2` Step 4 — after the plan-validator `Task` return is read, before resolving APPROVED/NEEDS_REVISION/MAJOR_REVISION: add a **pure-prose** instruction — if the return's top-level `codex_status` is `skipped`, surface `codex_skip_reason` to the user. **No `Bash(...)`/`Task(...)`/`request_user_input`/`AskUserQuestion` token** in the relay (so it renders identically across `is_codex`). Also: `src/harness_maker/models.py::CodexSecondOpinionConfig` docstring (enabled=mandatory, per-agent rollout; no field change); `src/harness_maker/interview.py::_ask_codex_second_opinion` prompt copy.
- **Scope (out):** `review.md.j2` (array reviewers deferred); any model field/Literal change; the partial; tests.
- **Exit criterion:** `uv run mypy --strict src/harness_maker` clean AND `uv run pytest tests/unit/test_interview_codex_second_opinion.py tests/unit/test_models_codex_second_opinion.py -v` green AND `grep -n "codex_status" src/harness_maker/templates/stages/plan.md.j2` shows the relay AND a reviewer confirms the relay text contains none of the four command/tool tokens above.
- **Risk:** low
- **Rollback point:** `git revert` → HEAD (degraded-but-not-broken w.r.t. Phase 1).

### Phase 3 — Test coverage
- **Scope (in):** extend `tests/unit/test_render_codex_partial_include.py`: positive asserts on the **plan-validator** render (`MUST`, top-level `codex_reconciliation`, `codex_status`, floor language) + negative (no `MAY invoke`/`opt-in per call`); **unchanged asserts** on code-reviewer + consensus-arbiter renders (still `MAY`/`opt-in`); update `tests/unit/test_interview_codex_second_opinion.py` if it asserts prompt copy; assert the partial documents the loud-skip path (`codex_status`+`codex_skip_reason`).
- **Scope (out):** integration/e2e (no live Codex in CI — `INTEGRATION=1` gated, not added).
- **Exit criterion:** `uv run pytest tests/unit -k "codex" -v` all green (background per project policy).
- **Risk:** low
- **Rollback point:** `git revert` → HEAD (test-only).

### Phase 4 — Preset comments, ADR record, CHANGELOG, version sync
- **Scope (in):** `src/harness_maker/templates/harness-yaml/Production.yaml.j2` + `Side.yaml.j2` comment wording (note plan-validator is mandatory, array reviewers opt-in pending follow-up); CHANGELOG entry (intended behavior change + per-agent rollout + follow-up pointer); finalize `validator_outcome`; **5-file version bump** (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`).
- **Scope (out):** tag push / `gh release` (user-initiated per CLAUDE.md); enabling `codex_second_opinion` in *this* repo's `.claude/harness.yaml` (separate user decision); the follow-up array-reviewer PLAN.
- **Exit criterion:** full suite green in background (`uv run pytest`); snapshot regen clean; `grep -rn "opt-in" src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2` returns only the (unchanged) `{% else %}` branch text for the array reviewers; all 5 version files show the new version.
- **Risk:** low
- **Rollback point:** `git revert` → HEAD (docs/version-only).

## 🧪 Testing Strategy

- **Unit (primary):** render-include assertions — plan-validator forced (MUST + top-level fields + floor + negative), array reviewers **unchanged** (still MAY), disabled byte-zero. Interview copy + model strict-validation round-trip.
- **Type:** `mypy --strict` after Phase 2 (docstring-only Python change).
- **Integration (manual / `INTEGRATION=1`):** with `enabled=true` + logged-in `codex`, run `/hm:plan` on a trivial slug → plan-validator output has non-empty `codex_reconciliation` (each entry citing a Codex finding) + `codex_status: invoked`; then `codex logout` → `codex_status: skipped` + a prose-surfaced reason + the stage still completes (warn-and-proceed). Not in CI.
- **Manual checklist:** add a mandatory-call + loud-skip line to `tests/manual/CODEX_PERMISSION_PROBE.md` (or sibling).

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Existing `enabled=true` harness changes plan-validator behavior on re-render | medium | ADR-001 explicit accepted-risk; CHANGELOG; drift banner is render-time signal |
| Partial branch leaks mandatory text into array reviewers | medium | Phase 1/3 assert code-reviewer + consensus-arbiter renders STILL contain MAY/opt-in |
| Validator treats `codex_reconciliation` as optional → theater | medium | Anti-boilerplate floor (cite finding); Phase 3 positive asserts; manual integration check |
| Loud note emitted but not surfaced | low | Two-part contract; Phase 2 greps relay; prose-only avoids `is_codex` mis-render |
| Prose relay accidentally includes a command/tool token → dual-render breakage | low | Phase 2 exit asserts none of the 4 tokens present in the relay |
| `enabled=true` non-uniform across agents confuses users | low | ADR-001 + ADR-004 documented; CHANGELOG names the follow-up |
| Disabled-branch byte-zero regression from whitespace edits | low | Keep `{%- … -%}`; disabled-branch test asserts byte-zero |

## ✅ Success Criteria

- [x] Rendered **plan-validator** body (enabled=true) says **MUST**, never "MAY invoke"/"opt-in per call".
- [x] plan-validator body requires **top-level** `codex_reconciliation` + `codex_status` keys.
- [x] Reconciliation floor present: each entry cites the Codex finding (`file:line` or verbatim `message`) — boilerplate `"rejected: n/a"` does not satisfy.
- [x] **code-reviewer + consensus-arbiter renders UNCHANGED** (still opt-in MAY) — asserted.
- [x] On Codex failure: warn-and-proceed + `codex_status: skipped` + reason (no hard-fail).
- [x] `/hm:plan` Step 4 relays a skipped-Codex note as **pure prose** (no `Bash`/`Task`/`request_user_input`/`AskUserQuestion` token).
- [x] No new config field; `mypy --strict` clean; full unit suite green; disabled branch byte-zero.
- [x] ADR-005 of [[PLAN-codex-second-llm-integration]] preserved — verdict remains Claude-derived.
- [x] 5-file version sync + CHANGELOG entry (names the array-reviewer follow-up).

## 🔍 Plan Validation

**Pass 1 — `plan-validator` (opus): MAJOR_REVISION** (2 critical, 4 warning, 2 suggestion). All findings legitimate; resolved in-plan. W4 (anti-boilerplate), W5 (explicit migration acceptance), W6 (HEAD-targeted rollbacks), W3 (test ordering), S7/S8 — closed.

**Pass 2 — `plan-validator` (opus) re-validation: MAJOR_REVISION** (2 critical). Pass 1's resolutions for C1/C2 rested on the *first* validator's incorrect ground truth. I verified pass-2's claims **directly** before accepting:
- **C1 (confirmed by me):** `code-reviewer` (`two_pass_review.py:81`) and `consensus-arbiter` (`consensus-arbiter_body.md.j2:96`) emit top-level **JSON arrays**; `merge_passes` rebuilds a list → no envelope/sibling-key survives. My "uniform top-level key" fix was unworkable for 2 of 3 agents.
- **C2 (confirmed by me):** `is_codex` blocks (`review.md.j2:48`, `plan.md.j2:106`) are inline command-syntax/tool-name dual-render switches, NOT `.codex/` file-target gates. My "keep relay outside `is_codex`" rule checked the wrong thing.

**Resolution (validator re-run budget exhausted — no pass 3):** rather than accept-as-risk or abort, I surfaced the verified criticals to the user as **new evidence** and ran a follow-up interview round (Round 4). The user chose to **narrow scope to plan-validator** (Interview #6, Option 1), which dissolves both criticals at the root:
- C1 → only plan-validator (object output) gets top-level keys; array reviewers deferred (ADR-004).
- C2 → only the `plan.md.j2` Step 4 relay remains, written as pure prose (ADR-002) — no `is_codex` interaction.

Outcome recorded as **MAJOR_REVISION_RESOLVED**: criticals closed by personally-verified ground truth + a user-confirmed scope decision, not by a validator re-pass. The follow-up array-reviewer work is captured as a Non-Goal + ADR-004 pointer.
