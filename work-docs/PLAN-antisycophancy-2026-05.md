---
type: plan
task_slug: antisycophancy-2026-05
status: planning
created: 2026-05-16
tags: [harness-maker, plan, python, anti-sycophancy, agent-prompts, render-pipeline]
research_doc: "[[RESEARCH-antisycophancy-2026-05]]"
interview_rounds: 6
adrs: 7  # 6 accepted + 1 retracted (ADR-003); ADR-006 re-wired in R6 after 0.13.0
validator_outcome: NEEDS_REVISION_RESOLVED
external_change_rebase: "2026-05-17 — absorbed 0.12.0 personalization-depth + 0.13.0 /hm:health consolidation; drift-verify re-wired from /hm:verify to /hm:health Layer 1 structural sub-check"
review: "[[REVIEW-antisycophancy-2026-05-2026-05-17]]"
review_grade: A
status: complete
summary: "Promote single communication partial to 3-variant family + explicit communication_variant frontmatter + selective skills + /hm:health Layer 1 drift-audit."
---

# 🎯 Executive Summary

## TL;DR
Promote the existing `_partials/communication.md.j2` (single FULL-equivalent variant) into a **3-variant family** (`_full`, `_reframe`, `_soft`), drive variant selection by **explicit `communication_variant` frontmatter** on each dispatcher template, extend injection to **5 LLM-judgment skills**, and wire **silent-miss drift audit** as a sub-check inside **`/hm:health` Layer 1 (structural)** — re-wired from `/hm:verify` in R6 after absorbing 0.13.0's audit-command consolidation pattern. Stage templates stay inline (R2 retracted in R5). Render output carries no new frontmatter key — variant identity rides as an HTML comment inside the partial body. Single PR, two commits (code + snapshot regen).

## What / Why
**What:** Replace the universal single-variant communication partial with a typed variant family addressable by template-side frontmatter, extend coverage to selected skills, and add build-time drift detection so silent-miss (an agent that forgets to declare a variant) is caught before merge.

**Why:** harness-maker's user maintains a hand-curated `SYCOPHANCY.md` registry across their vault — a recurring toil of editing canonical preamble blocks, propagating to N files, grep-counting for drift, and spot-checking. That toil is exactly the kind harness-maker absorbs. Today the repo has one universal partial (no role differentiation), no skill/command coverage, and no drift detection. The user's registry distinguishes 6 FULL / 12 FULL+REFRAME / 30 SOFT agents — the three-way split is the pattern that emerges in real use.

## Key Decisions (linking ADRs)
- Scope is **Approach A only** — variant family + selective skills + verify. Approach B (auto-generate `SYCOPHANCY.md` user-doc) and Approach C (runtime detector) are deferred. → [ADR-001](#adr-001)
- Variant assignment is **explicit frontmatter on each dispatcher** — no auto-derive. → [ADR-002](#adr-002)
- ~~Stage templates dedup via partial~~ → **RETRACTED** in R5 after validator surfaced stage-specific content that would be silently deleted. Stages keep their inline blocks. → [ADR-003 retracted](#adr-003-retracted)
- Output frontmatter carries no variant key; identity rides as HTML comment marker inside partial body, surviving Cursor `.mdc` / Codex TOML strict parsers. → [ADR-004](#adr-004)
- Skills coverage is **selective** — 5 LLM-judgment skills only, 7 procedural skills excluded. → [ADR-005](#adr-005)
- `/hm:health` Layer 1 (structural) gains a `communication_protocol` sub-check; missing frontmatter on any new dispatcher surfaces as a structured `accept/reject/defer` item per 0.13.0 ADR-001 "no auto-apply" rule. **Re-wired in R6** from the original `/hm:verify` integration after 0.13.0's audit-command consolidation. → [ADR-006](#adr-006)
- REFRAME/SOFT partial text is **paraphrased into harness-maker tone**, not copied verbatim from user SYCOPHANCY.md. SOFT ships despite no current consumer (future-proof). → [ADR-007](#adr-007)

## Estimated Impact
- Source-side: 3 new partial files (1 rename, 2 author); render.py +1 pre-render extractor; 14 dispatcher frontmatter additions; 14 include rewrites; 5 skill SKILL.md additions; `/hm:health` Layer 1 structural sub-check `communication_protocol` (new `harness_maker/communication_audit.py`).
- Output-side: ~78 rendered files touched across `.claude/`, `.cursor/`, `.codex/` (snapshot regen).
- Risk: medium overall. Highest-risk piece is Cursor `.mdc` rendered output — manual checklist mitigates.

# 📚 Prior Work

- [[RESEARCH-antisycophancy-2026-05]] — surfaced 3 approaches, recommended Approach A. Identified 5 risks now addressed in this plan: prompt bloat vs. context-line budget, variant mismatch, fragile rg-counts, Cursor frontmatter strictness, academic-citation overclaim.
- [[RESEARCH-harness-trends-2026-05]] — "Agentic Verification with Typed Boundaries" framing: build-time discipline > runtime detection. Approach C deferral consistent with that.
- [[PLAN-health-consolidation]] (commit 82eaddb, 0.13.0, 2026-05-17) — **load-bearing for R6 wiring change.** Consolidated `/hm:ai-readiness` + `/hm:refresh` + `/hm:personalization-audit` into single `/hm:health` with 3 layers. ADR-001 "no auto-apply", ADR-002 "scores stay split", ADR-006 "absorbed personalization-audit" patterns reused here for the communication sub-check.
- [[PLAN-personalization-depth-2026-05]] (commit 0296eed, 0.12.0) — introduced `personalization_audit.py`, `profile.py`, `recommendation.py`, `foreign_config.py`, `block_merge.py` 391-line extension. Pattern for audit-style modules informs `communication_audit.py` shape (HealthItem-shaped output).
- Existing `_partials/communication.md.j2` (2026-05-08) — the single-variant partial this plan grows into a family. Text becomes `communication_full.md.j2` byte-for-byte. **Unchanged by 0.12.0/0.13.0.**
- Existing `_partials/hard_rules.md.j2` — overlaps semantically (fabrication, evidence rules) with FULL preamble; this plan does NOT touch hard_rules (avoid scope creep).
- CLAUDE.md "Context Lint" thresholds: ≤200 lines per agent prompt at Production preset (harness-maker's preset per harness.yaml). plan-validator_body and test-reviewer_body currently 90+ lines; +REFRAME (~14 lines) keeps them under 200.
- 0.13.0 changed 3 of the 5 ADR-005 skill SKILL.md.j2 files (`relevance-filter`, `research-crawler`, `ai-readiness-rubric`) for `/hm:health` integration wording. Skill identity unchanged; FULL variant injection remains compatible (line counts 54–67 → 63–76 after partial inject, well under Production ≤150 threshold).

# 🎙️ Interview Transcript

Conducted in Korean per user argument `-- 한글로`. Locked decisions translated to English for archive.

| # | Round | Topic | Category | Question (1-line) | Options | Choice | → ADR |
|---|-------|-------|----------|-------------------|---------|--------|-------|
| 1 | R1 | Scope of work | Scope | A only / A+B / smaller / A+C | A/B/C/D | **Approach A only** | → ADR-001 |
| 2 | R2 | Variant assignment | Architecture | auto / explicit / hybrid | A/B/C | **Explicit `communication_variant` frontmatter** | → ADR-002 |
| 3 | R2 | Stage dedup | Architecture | partial / inline / per-stage partial | A/B/C | **Partial 로 통일** (retracted in R5) | → ADR-003 (retracted) |
| 4 | R3 | Cursor/Codex parity | Contract | body-inline / per-target / sidecar / end | A/B/C/D | **Body inline (no output frontmatter key)** | → ADR-004 |
| 5 | R3 | Skills coverage | Scope | selective / all-12 / opt-in | A/B/C | **Selective: LLM judgment skills only** | → ADR-005 |
| 6 | R3 | Drift-verify wiring | Architecture | verify / rubric / both / none | A/B/C/D | **`/hm:verify` integration** | → ADR-006 |
| 7 | R4 | Phasing | Risk | single PR / 2 PR / 3 PR / end | A/B/C/D | **Single PR bundled** | preamble note |
| 8 | R4 | WRONG probe (Layer 2) | Failure mode | text drift / parser / silent miss / toil | multi-select | **Silent miss** | reinforces ADR-006 |
| 9 | R5 | Stage dedup — re-evaluation after validator critical #1 | Architecture | inline retained / hybrid / per-stage partial | A/B/C | **Inline 유지 (R2 retracted)** | → ADR-003 retracted |
| 10 | R5 | plan-validator + test-reviewer baseline (validator critical #4) | Scope | REFRAME / FULL / exclude / end | A/B/C/D | **REFRAME 추가 (behavior change explicitly accepted)** | → ADR-002 boundary |
| 11 | R5 | REFRAME/SOFT source authoring (validator critical #3) | Implementation | verbatim / paraphrase / skip-SOFT | A/B/C | **Paraphrase to harness-maker tone (SOFT included)** | → ADR-007 |
| 12 | R6 | drift-verify wiring re-cut (external change absorption: 0.13.0 `/hm:health` consolidation + `/hm:verify` 6-check pattern) | Architecture | health-sub-check / verify-advisory / both / verify-Check7 | A/B/C/D | **`/hm:health` Layer 1 structural sub-check** | → ADR-006 re-wired |

**Ambiguity Score progression:** R3 → 0.93 (PASS streak 1/2). R4 → 0.97 (PASS streak 2/2 → gate closed). R5 (validator-driven follow-ups) — gate re-opened by MAJOR_REVISION, closed again after critical resolutions. R6 (external change absorption) — single foundational decision, no new ambiguity opened.

# 📐 Architecture Decision Records

## ADR-001
**Title:** Scope = Approach A only
**Status:** Accepted (2026-05-16, via /hm:plan interview Round 1)
**Context:** Research surfaced 3 approaches (A: variant family + skills/commands + drift-verify; B: auto-gen SYCOPHANCY.md user-doc; C: runtime detector). Scope determines all downstream defaults.
**Decision:** Ship Approach A only. Approach B is a natural complement but adds an auto-generated user-doc that requires user-edit policy work. Approach C carries high false-positive risk (research-doc Pitfall on regex/keyword sycophancy detection).
**Consequences:**
- ✅ Smaller diff, lower risk, no runtime detector to false-positive on legitimate praise.
- ✅ B/C can land later as separate plans without disturbing A's architecture.
- ⚠️ User keeps maintaining SYCOPHANCY.md by hand for now — toil reduction is partial, not total.
**Rejected alternatives:**
- A+B together — rejected because user-doc auto-generation requires separate decisions on staleness, user-edit reconciliation, and content-hash diff strategy; do not bundle.
- A+B+C — rejected because Approach C's false-positive surface dominates the risk profile and would dilute review attention from A's substantive changes.
**Source:** Interview Round 1.

## ADR-002
**Title:** Explicit `communication_variant` frontmatter, NEW pre-render Jinja context injection
**Status:** Accepted (2026-05-16, refined twice — validator critical #2 + warning W1)
**Context:** R2 locked "explicit frontmatter" over auto-derive. Validator pass 1 flagged that the existing `{% include %}` lives in `_body.md.j2` files (not dispatcher templates), so dispatcher-frontmatter ↔ body-include resolution mechanism must be specified. Validator pass 2 flagged that render.py's existing `_split_template_frontmatter` operates on rendered output, not source — so this is a NEW code path, not a reuse.
**Decision:** Each dispatcher template (`templates/agents/<name>.md.j2`) declares `communication_variant: full | reframe | soft` in source frontmatter. **render.py adds a NEW pre-render frontmatter extractor**: reads the source file via the Jinja loader, parses the leading YAML frontmatter block, extracts `communication_variant`, and merges it into `fe.context` BEFORE calling `template.render()`. Body templates use `{% include "agents/_partials/communication_" ~ communication_variant ~ ".md.j2" %}`. No default, no auto-derive — missing frontmatter is a render-time error.
**Consequences:**
- ✅ Variant identity declared next to agent definition (high discoverability for agent owner).
- ✅ Auditable — each dispatcher source file shows variant in two lines.
- ⚠️ New pre-render code path in render.py — small but a new seam to test.
- ⚠️ Missing frontmatter must raise loudly; silent default-to-FULL would mask the very failure mode R4 flagged.
**Rejected alternatives:**
- Auto-derive from path/role (reviewer→REFRAME, executor→FULL) — rejected R2 because heuristic-derivation hides the choice; explicit beats clever for audit and override.
- Carry `communication_variant` in `FileEntry.context` from Blueprint generation layer (config-map keyed by agent name) — rejected because it couples variant declaration to Blueprint code instead of letting it live next to the agent definition the owner actually edits.
- Hybrid (auto + override) — rejected R2 because two competing sources of truth invite drift.
**Source:** Interview Round 2 + validator pass 1 critical #2 + validator pass 2 warning W1.

## ADR-003 (retracted)
**Title:** ~~Stage template communication block dedup via `{% include %}` of FULL partial~~
**Status:** RETRACTED 2026-05-16 (via /hm:plan Round 5, after validator pass 1 critical #1)
**Context:** R2 locked stage dedup. Validator surfaced that the 7 stage templates carry stage-specific protocol lines (e.g., `verify.md.j2:10-13` "PASS / FAIL — no soft language", `execute.md.j2:10-13` "When Phase A.5 returns FAIL, treat the test-reviewer's reasoning as authoritative", `research.md.j2:10` "When alternatives differ in trade-offs, say which trade-off is binding"). FULL partial contains none of these — blanket dedup silently deletes them.
**Decision:** Retracted. Stages keep their inline communication blocks. Drift bait risk accepted; the stage-specific content is more load-bearing than the deduplication win.
**Consequences:**
- ✅ No silent content deletion; stage-specific operational rules preserved.
- ⚠️ 7 files carry near-identical generic lines — future protocol changes must be propagated to all 7 manually.
- ⚠️ Hybrid (option B in R5) and per-stage partial (option C in R5) were both viable middle paths; user chose simplicity. If drift accumulates, revisit in a future plan.
**Rejected alternatives:**
- Hybrid: `{% include %}` for generic + inline for stage-specific — rejected R5 for simplicity (chose option A "Inline 유지").
- Per-stage partials: 7 new files (one per stage) — rejected R5 for same reason.
**Source:** Interview Round 2 (original) + Round 5 (retraction).

## ADR-004
**Title:** Output carries no `communication_variant` frontmatter key; HTML comment marker embeds variant identity in body
**Status:** Accepted (2026-05-16, refined once — validator pass 1 warning W2)
**Context:** R3 locked "render-time body inline" to avoid Cursor `.mdc` / Codex TOML strict-reject of unknown frontmatter keys (CLAUDE.md "외부 소비자의 파서 정합성 확인" checkpoint). Validator pass 1 flagged that this loses downstream auditability — `.claude/agents/code-reviewer.md` rendered file would carry no signal of which variant is active.
**Decision:** Output frontmatter / TOML metadata stays clean of `communication_variant`. Each partial body ends with an HTML comment marker `<!-- @hm:communication_variant: {full|reframe|soft} -->`. Comments are not frontmatter — Cursor `.mdc` and Codex TOML strict parsers accept them. The marker is grep-discoverable for downstream audit.
**Consequences:**
- ✅ Cursor / Codex / Claude all three render cleanly with same body text.
- ✅ Downstream auditor (or `/hm:health` Layer 1 sub-check) can grep marker to determine variant without round-tripping to source template.
- ⚠️ Marker is inside partial body — if someone edits the rendered file to remove the marker, the variant identity is lost (verify routine catches this).
**Rejected alternatives:**
- Add `communication_variant` to output frontmatter only on Claude target — rejected because tri-target asymmetry creates per-target render branches.
- Sidecar `.hm-meta.yaml` per agent — rejected R3 (option C) as too much file proliferation.
- Encode variant into `content_hash` input — rejected because the hash purpose is template-identity, not field-level audit; reusing it for variant would couple two orthogonal concerns.
**Source:** Interview Round 3 + validator pass 1 warning W2.

## ADR-005
**Title:** Skill variant injection limited to 5 LLM-judgment skills (pinned list)
**Status:** Accepted (2026-05-16, refined once — validator pass 1 warning W1)
**Context:** R3 locked "선별: LLM judgment skill 만". Validator pass 1 flagged the negative list ("verify during execute") as unverifiable. Pinning required.
**Decision:**
- **Inject FULL variant into 5 skills:** `agent-quality-rubric`, `ai-readiness-rubric`, `relevance-filter`, `security-scanner`, `refdocs-search`.
- **Do NOT inject (7 skills):** `worktree-isolator`, `conditional-router`, `verify-before-completion`, `autoloop-driver`, `research-crawler`, `context-linter`, `trajectory-monitor`.
- Total = 12 skills (5 + 7) — matches `Glob src/harness_maker/templates/skills/**/*.j2` count.
- All injected skills get FULL (none currently fit REFRAME shape; concurrent-test-review from user vault is not in harness-maker's skills).
**Consequences:**
- ✅ Phase 4 exit criterion ("5 SKILL.md gain block, 7 unchanged") is unambiguous.
- ✅ Procedural skills don't carry unrelated tone guidance.
- ⚠️ If a new LLM-judgment skill is added later, it must be added to this list — Phase 6 `/hm:health` sub-check routine catches this via skill discovery + frontmatter requirement.
**Rejected alternatives:**
- All 12 skills get FULL — rejected R3 because procedural skills don't benefit from communication tone (`worktree-isolator` executes git plumbing, not LLM judgment).
- Frontmatter opt-in (default none) — rejected R3 because each skill author would need to know about the opt-in; selective + explicit list is more discoverable.
**Source:** Interview Round 3 + validator pass 1 warning W1.

## ADR-006
**Title:** `/hm:health` Layer 1 (structural) `communication_protocol` sub-check — dispatcher discovery + body marker scan; silent-miss surfaced via 0.13.0 `accept/reject/defer` structured-question rule
**Status:** Accepted (2026-05-16, re-wired 2026-05-17 — R6 after absorbing 0.13.0 `/hm:health` consolidation)
**Context:** R3 originally locked `/hm:verify` integration. R4 named "silent miss" (variant block absent from a newly-added template) as the canonical failure mode. Validator pass 1 (R5) strengthened the discovery + marker mechanism. R6 (2026-05-17) absorbed two external changes that landed between plan write and execute:
1. **0.13.0 PLAN-health-consolidation** consolidated `/hm:ai-readiness` + `/hm:refresh` + `/hm:personalization-audit` into a single `/hm:health` command with 3 layers (structural / external_risks / personalization). Adding yet another audit-shaped surface to the harness now violates the explicit consolidation pattern.
2. **0.13.0 `/hm:verify` 47-line rewrite** formalised the 6-check stop-sign pattern owned by `verify-before-completion` SKILL. Adding a 7th check would require SKILL surgery and verify scope creep; adding a 4th advisory probe gives no PR-time gating.
The cleanest integration point became `/hm:health` Layer 1 (structural), which already owns ai-readiness-rubric structural signals on agent prompts.

**Decision:**
- **Surface:** `/hm:health` Layer 1 (structural) gains a `communication_protocol` sub-check (in `harness_maker/ai_readiness.py` or a new `harness_maker/communication_audit.py` invoked from there).
- **Discovery:** Sub-check scans `src/harness_maker/templates/agents/*.md.j2` (excluding `_body`, `_partials`, `_standards` — dispatcher templates only) AND the 5 pinned LLM-judgment skills from ADR-005.
- **Source check:** Each dispatcher MUST declare `communication_variant` in source frontmatter. Missing → surface as health item.
- **Output check:** Rendered `.claude/agents/<name>.md` and pinned `.claude/skills/<n>/SKILL.md` MUST contain `<!-- @hm:communication_variant: X -->` HTML comment marker matching the source frontmatter value.
- **No auto-apply (per 0.13.0 ADR-001):** Silent-miss + variant-mismatch items surface in `dashboard.md` `## Structural` section AND in `/hm:health` Step "Per-item structured question" loop. Each item presented via `AskUserQuestion` with `accept` / `reject` / `defer` — never auto-fixed. Decisions appended to `.claude/observability/health/decisions.jsonl`.
- **Two acceptance fixtures** retained: (A) existing agent rendered with block removed → sub-check surfaces 1 item; (B) synthetic new dispatcher template added WITHOUT `communication_variant` frontmatter → sub-check surfaces 1 item (silent-miss proof).

**Consequences:**
- ✅ Aligns with 0.13.0 consolidation pattern (audit-shaped checks → `/hm:health`).
- ✅ Reuses 0.13.0 structured-question infrastructure (`decisions.jsonl`, `dashboard.md` 3-section schema).
- ✅ Silent-miss surfaced (per R4 WRONG probe) — author runs `/hm:health` after adding a new agent, item appears as actionable structured question.
- ⚠️ **NOT a PR-time stop sign.** `/hm:health` runs on demand or as scheduled audit, not as `/hm:verify` gate. Sub-trade-off explicitly accepted in R6.
- ⚠️ Sub-check must keep dispatcher-discovery glob in sync with future template directory restructuring (mirrors ai-readiness-rubric's existing maintenance burden).

**Rejected alternatives:**
- `/hm:verify` integration (original R3) — rejected R6 because 0.13.0 consolidated audit-shape into `/hm:health`; adding a new audit surface to verify would fragment the pattern.
- `/hm:verify` advisory probe A2 (R6 option B) — rejected because non-blocking probe doesn't satisfy "actionable item" requirement; silent-miss should produce a structured item, not just a warning line.
- `/hm:verify` Check 7 gating (R6 option D) — rejected because it requires `verify-before-completion` SKILL surgery and adds a non-regression gate to a stop-sign that exists for the 6 listed regression types.
- Both Health + verify advisory (R6 option C) — rejected for surface-count minimisation; one canonical location.
- Extend `agent-quality-rubric` per-agent score only — rejected R3 for redundancy; one integration point.
- Snapshot test alone — rejected because snapshot diffs detect changes in existing files, not "this new template SHOULD have declared a variant" cases (silent-miss).

**Source:** Interview Round 3 + Round 4 + validator pass 1 critical #5 + Round 6 (external change absorption 2026-05-17).

## ADR-007
**Title:** REFRAME/SOFT partial text paraphrased into harness-maker tone (NOT verbatim from user SYCOPHANCY.md); SOFT shipped despite no current consumer
**Status:** Accepted (2026-05-16, via /hm:plan Round 5, after validator pass 1 critical #3)
**Context:** Validator pass 1 surfaced that the original Phase 1 framing ("split existing partial 3 ways") was misleading — the existing `communication.md.j2` is FULL-flavored only; REFRAME and SOFT text don't exist anywhere in the repo. They must be authored. User vault's `SYCOPHANCY.md` provides the source (`ANTISYC-FULL-v1`, `ANTISYC-REFRAME-v1`, `ANTISYC-SOFT-v1`).
**Decision:**
- **FULL:** `communication_full.md.j2` is `communication.md.j2` renamed byte-for-byte (existing text already aligned with ANTISYC-FULL-v1 semantically). Add the HTML comment marker.
- **REFRAME:** New file. Author 5 generic bullets matching FULL + an additional "Input Processing" 2-3 line section paraphrasing ANTISYC-REFRAME-v1's "reframe the submission as a question" guidance. Total ≤14 lines.
- **SOFT:** New file. Author 3 bullets paraphrasing ANTISYC-SOFT-v1 (honesty, fatal flaws, excitement vs honesty). Headed `## Honesty Protocol` not `## Communication Protocol` to distinguish.
- **No verbatim copy.** Maintain harness-maker's existing bullet style (5 bullets, ≤9 lines per protocol section). Source attribution lives in the partial's leading Jinja comment, not in body text.
- **SOFT shipped** despite no current `idea-*`-shaped agent — future-proof. ADR-005 confirms no skill uses SOFT either; SOFT lies dormant until first consumer.
**Consequences:**
- ✅ Text style consistent with existing partial; reviewer can compare diffs against `communication.md.j2` as baseline.
- ✅ Source attribution preserved without copying user's vault verbatim.
- ⚠️ SOFT is dead code at merge — must be flagged in CHANGELOG so reviewer knows it's intentional.
**Rejected alternatives:**
- Verbatim copy with attribution comment — rejected R5 to keep one style across all partials.
- FULL+REFRAME only, skip SOFT — rejected R5 because adding SOFT later requires re-touching render.py variant resolver to recognize a new value; cheaper to ship together.
**Source:** Interview Round 5 + validator pass 1 critical #3.

# 🏗️ Technical Design

## Current State
- Single partial: `src/harness_maker/templates/agents/_partials/communication.md.j2` (9 lines, ~FULL semantics).
- 12 `{% include %}` sites: 11 `*_body.md.j2` + 1 dispatcher (`trajectory-monitor.md.j2:16`, no body file exists for it).
- 2 dispatcher templates with NO communication block today: `plan-validator_body.md.j2`, `test-reviewer_body.md.j2`.
- 7 stage templates with inline communication blocks: `research`, `plan`, `spec`, `execute`, `review`, `verify`, `wrapup` — each carrying generic + stage-specific lines.
- 12 skill templates: none currently carry a communication block.
- 14 dispatcher agent templates total (per Glob).
- render.py `_split_template_frontmatter` operates on rendered output (post-`template.render`), not source.

## Affected Components
- `src/harness_maker/templates/agents/_partials/communication*.md.j2` — split + author
- `src/harness_maker/templates/agents/<name>.md.j2` × 14 — frontmatter additions
- `src/harness_maker/templates/agents/<name>_body.md.j2` × 11 + `trajectory-monitor.md.j2` (dispatcher) + 2 new sites (plan-validator_body, test-reviewer_body) — include rewrites (14 sites total)
- `src/harness_maker/render.py` — new pre-render frontmatter extractor
- `src/harness_maker/templates/skills/{agent-quality-rubric,ai-readiness-rubric,relevance-filter,security-scanner,refdocs-search}/SKILL.md.j2` — frontmatter + include additions
- `src/harness_maker/templates/cursor/`, `src/harness_maker/templates/codex/` — render paths consume new variant, output stays metadata-clean (per ADR-004)
- `src/harness_maker/communication_audit.py` (new) — silent-miss detection logic, returns `HealthItem` list (re-uses 0.13.0 dataclass shape)
- `src/harness_maker/ai_readiness.py` — invokes `audit_communication` as Layer 1 sub-signal
- `src/harness_maker/observability/dashboard.py` — sub-line under `## Structural` for `communication_protocol`
- `src/harness_maker/templates/commands/hm/health.md.j2` — Layer table mention
- **NOT touched:** `src/harness_maker/templates/stages/verify.md.j2` — `/hm:verify` 6-check pattern preserved (R6 decision)
- `CLAUDE.md`, `CHANGELOG.md` — documentation
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — manual variant load checks
- `tests/unit/test_render.py` (or split) — 5 new test cases
- Snapshot suite — full regen

## Dependencies
No new external deps. All work uses existing Jinja2 + render.py infrastructure.

## Architecture
```
┌────────────────────────────────┐
│ Dispatcher template            │
│ agents/<name>.md.j2            │
│ ──────────────────────         │
│ frontmatter:                   │
│   communication_variant: reframe ◄── source of truth (declared here)
│ body: {% include "_body" %}    │
└──────────────┬─────────────────┘
               │
       render.py (new pre-render extractor)
               │
       reads source frontmatter
       extracts communication_variant
       merges into fe.context
               │
               ▼
┌──────────────────────────────────────────┐
│ Body template                            │
│ agents/<name>_body.md.j2                 │
│ ────────────────────────                 │
│ {% include "agents/_partials/            │
│   communication_" ~                      │
│   communication_variant ~                │
│   ".md.j2" %}                            │
└──────────────┬───────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────┐
│ Partial body (paraphrased text)            │
│ _partials/communication_reframe.md.j2      │
│ ────────────────────────────────────       │
│ ## Communication Protocol                  │
│ - bullet                                   │
│ - bullet                                   │
│ ...                                        │
│ ## Input Processing                        │
│ ...                                        │
│ <!-- @hm:communication_variant: reframe -->│ ◄── audit marker (per ADR-004)
└────────────┬───────────────────────────────┘
             │
             ▼
   Rendered output (.claude/agents/<name>.md, .cursor/rules/<name>.mdc, .codex/agents/<name>.toml)
   — output frontmatter has NO communication_variant key
   — body has the partial text + marker
             │
             ▼
   /hm:health Layer 1 (structural) — communication_protocol sub-check:
   - discover dispatcher templates + 5 ADR-005 skills
   - require communication_variant frontmatter on each (silent-miss check)
   - scan rendered body for marker
   - cross-check source ↔ output
   - surface findings as HealthItem entries in dashboard.md ## Structural
   - 0.13.0 ADR-001 "no auto-apply" → accept/reject/defer structured questions
```

## Design Decisions
- Variant declared on dispatcher, consumed in body via Jinja context (ADR-002).
- Output stays metadata-clean to survive Cursor/Codex strict parsers (ADR-004).
- HTML comment marker bridges output auditability (ADR-004).
- Stages NOT touched (ADR-003 retracted).
- Skills selective (ADR-005).
- Silent-miss via dispatcher discovery + required frontmatter (ADR-006).

## Data Flow
1. Author edits dispatcher source: sets `communication_variant: reframe`.
2. render.py pre-render extractor reads source frontmatter, merges into Jinja context.
3. `template.render()` resolves `{% include "communication_" ~ communication_variant ~ ".md.j2" %}` → `communication_reframe.md.j2`.
4. Partial body (including HTML comment marker) emitted into rendered output at body position.
5. Output frontmatter / TOML metadata stays untouched by variant (per ADR-004).
6. `/hm:health` Layer 1 sub-check (on demand or scheduled): dispatchers discovered → variant frontmatter required → marker matched in output → findings surfaced as structured `accept/reject/defer` items.

## API Changes
- **Internal API:** `render.py` adds one helper function (e.g., `_extract_source_frontmatter(template_path: Path) -> dict`) and one call before each `template.render()` for dispatcher templates.
- **No external API change.** Frontmatter schema is documented as "template-authored side; not present in rendered output."

## Partial Text (quoted for review before write)

### `communication_full.md.j2` (rename of existing `communication.md.j2`, no text change)
```jinja
{# harness-maker partial: communication_full (last_reviewed_at: 2026-05-16) — universal Communication Protocol; paraphrased from user SYCOPHANCY.md ANTISYC-FULL-v1 #}
## Communication Protocol

- Be direct. No flattery, no preamble, no "Great question!"
- Lead with concerns before agreement; when you agree, explain WHY with specific reasoning.
- Do not fold on pushback unless new evidence is presented.
- Fabrication is the cardinal sin: every claim cites file:line or is labeled as inference.
- Surface disagreements verbatim — never average findings into mush.

<!-- @hm:communication_variant: full -->
```

### `communication_reframe.md.j2` (NEW)
```jinja
{# harness-maker partial: communication_reframe (last_reviewed_at: 2026-05-16) — Reviewer/Evaluator Communication Protocol; paraphrased from user SYCOPHANCY.md ANTISYC-REFRAME-v1 #}
## Communication Protocol

- Be direct. No flattery, no preamble, no "Great question!"
- Lead with concerns before agreement; when you agree, explain WHY with specific reasoning.
- Do not fold on pushback unless new evidence is presented.
- Fabrication is the cardinal sin: every claim cites file:line or is labeled as inference.
- Surface disagreements verbatim — never average findings into mush.

## Input Processing

Before analysing, reframe the submission internally as a question:
"Does this code/plan meet the stated requirements without issues?"
The reframing dampens confirmation bias toward the author's intent.

<!-- @hm:communication_variant: reframe -->
```

### `communication_soft.md.j2` (NEW; no current consumer — ships dormant per ADR-007)
```jinja
{# harness-maker partial: communication_soft (last_reviewed_at: 2026-05-16) — Idea-agent Honesty Protocol; paraphrased from user SYCOPHANCY.md ANTISYC-SOFT-v1; ships dormant (no consumer in current 14 agents) #}
## Honesty Protocol

- Be honest about weaknesses; do not oversell ideas or inflate scores.
- If an idea has fatal flaws, state them clearly even when the user seems excited.
- Excitement and honesty are not mutually exclusive — pair enthusiasm with concrete risks.

<!-- @hm:communication_variant: soft -->
```

# 📝 Implementation Plan

**Preamble:** Single PR, single branch, two commits.
- **Commit 1 — code changes:** new partials, render.py extractor, body include rewrites, dispatcher frontmatter, skill frontmatter+include, verify logic. Reviewer reads this commit carefully.
- **Commit 2 — snapshot regen:** purely mechanical output. Reviewer skims for sanity (no surprises).

Phase 3 from the original draft is **CANCELLED** (ADR-003 retracted). Phases below number 1, 1.5, 2, 4, 5, 6, 7 — phase numbers preserved for traceability with prior validator round.

## Phase 1 — Author partial family
**Scope (files in):**
- `src/harness_maker/templates/agents/_partials/communication.md.j2` → rename to `communication_full.md.j2` (byte-identical text, plus HTML comment marker appended).
- `src/harness_maker/templates/agents/_partials/communication_reframe.md.j2` — NEW. Text per "Partial Text" section above.
- `src/harness_maker/templates/agents/_partials/communication_soft.md.j2` — NEW. Text per "Partial Text" section above.

**Scope (files out):** Everything else.

**Exit criterion:** 3 partial files exist at expected paths; each contains the exact text quoted in the "Partial Text" section above (modulo trailing newline normalization); `git diff` shows no change to other files in this phase.

**Risk:** medium (net-new prompt authoring — variant mismatch is research-doc Pitfall #2).

**Rollback:** revert this phase's commit.

## Phase 1.5 — Rewrite all include sites
**Scope (files in):** 14 include sites total —
- 11 `*_body.md.j2` files currently containing `{% include "agents/_partials/communication.md.j2" %}`
- 1 dispatcher: `trajectory-monitor.md.j2:16` (no separate `_body` file; include lives on dispatcher itself)
- 2 new body sites: `plan-validator_body.md.j2`, `test-reviewer_body.md.j2` (add an include where currently none exists)

Each site rewritten to `{% include "agents/_partials/communication_" ~ communication_variant ~ ".md.j2" %}`.

**Scope (files out):** Everything else.

**Exit criterion:**
- `grep -r "agents/_partials/communication.md.j2" src/harness_maker/templates/` returns 0 hits (literal old path).
- `grep -r "communication_\" ~ communication_variant ~ \"" src/harness_maker/templates/` returns 14 hits (Jinja placeholder pattern).

**Risk:** low (mechanical rewrite).

**Rollback:** revert this phase's commit. (Note: Phase 1.5 + Phase 1 in commit 1 — bisect lands on a working state; no broken intermediate within the PR.)

## Phase 2 — Dispatcher frontmatter + render.py pre-render extractor
**Scope (files in):**
- 14 dispatcher templates (`templates/agents/<name>.md.j2`) — each adds `communication_variant: <value>` to source frontmatter:
  - **FULL (4):** `autoloop-coder`, `executor`, `stuck`, `trajectory-monitor` (JSON-output — REFRAME inapplicable per validator W6).
  - **REFRAME (10):** `code-reviewer`, `code-verifier`, `concurrency-reviewer`, `consensus-arbiter`, `performance-reviewer`, `plan-validator` (newly receives REFRAME — behavior change explicitly accepted in R5), `security-auditor`, `security-reviewer`, `test-reviewer` (newly receives REFRAME — behavior change explicitly accepted in R5), `ux-reviewer`.
  - **SOFT (0):** no current consumer (ADR-007).
- `src/harness_maker/render.py` — add `_extract_source_frontmatter(template_name: str) -> dict` (reads source via `env.loader.get_source()`, parses leading YAML block); call it before `template.render()` for dispatcher templates; merge `communication_variant` into `fe.context`.

**Scope (files out):** Skill templates (Phase 4); Cursor/Codex render paths (Phase 5); verify (Phase 6).

**Exit criterion:**
- `uv run pytest tests/unit/` passes including 5 new tests (named below in Phase 7).
- Agent body snapshot diff shows expected variant text per agent: 9 reviewer bodies (excluding plan-validator, test-reviewer) gained FULL→REFRAME transition (new "Input Processing" section appears); 2 newly-receiving REFRAME bodies (plan-validator_body, test-reviewer_body) gained communication block where none existed.
- Missing frontmatter on a synthetic test dispatcher template raises explicit error from `_extract_source_frontmatter` (per ADR-002 "no auto-derive").

**Risk:** medium (new render.py code path; verify line-budget on plan-validator_body, test-reviewer_body — both currently ~90 lines, +14 lines REFRAME → ~104 lines, under Production ≤200 limit).

**Rollback:** revert this phase's commit. Reverts to Phase 1.5 state, which is broken (placeholder include with no `communication_variant` defined) — so rollback in practice means reverting Phase 1.5 + Phase 2 together. Phase 1.5 + 2 = single logical step.

## Phase 4 — Skills selective injection
**Scope (files in):** 5 skill SKILL.md.j2 (pinned list from ADR-005) — add `communication_variant: full` to frontmatter, add `{% include "agents/_partials/communication_full.md.j2" %}` to body at conventional position (after "## How to invoke" or equivalent — discoverable during execute):
- `agent-quality-rubric/SKILL.md.j2`
- `ai-readiness-rubric/SKILL.md.j2`
- `relevance-filter/SKILL.md.j2`
- `security-scanner/SKILL.md.j2`
- `refdocs-search/SKILL.md.j2`

render.py extended: skills follow the same pre-render extractor pattern as dispatchers.

**Scope (files out):** 7 procedural skills (excluded per ADR-005). Stage templates (ADR-003 retracted).

**Exit criterion:** snapshot regen shows the 5 listed SKILL.md files gain a `## Communication Protocol` block + HTML comment marker; other 7 skills unchanged (snapshot diff empty for them).

**Risk:** medium (skill SKILL.md text now carries communication protocol — verify each skill's flow doesn't conflict with the block's guidance).

**Rollback:** revert this phase's commit.

## Phase 5 — Cursor/Codex body-inline render
**Scope (files in):**
- `src/harness_maker/templates/cursor/rules/<name>.mdc.j2` (or equivalent render path for `.cursor/rules/`) — consume `communication_variant` from source frontmatter, inline partial body, do NOT propagate the key to `.mdc` output frontmatter.
- `src/harness_maker/templates/codex/agent.toml.j2` — same; do NOT add `communication_variant` to TOML `[meta]` or top-level keys; inline body string carries the partial.
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — add 3 manual items (load a FULL-variant agent in Cursor 2.4+, load a REFRAME-variant agent, load a SOFT-variant agent — verify IDE renders without parse error, communication block visible in agent prompt).

**Scope (files out):** Claude render path already handled in Phase 2.

**Exit criterion:**
- Cursor `.mdc` snapshot: frontmatter does NOT contain `communication_variant`; body contains the partial text + HTML comment marker.
- Codex `.toml` snapshot: TOML metadata does NOT contain `communication_variant`; `developer_instructions` (or equivalent body field) contains partial text + HTML comment marker.
- Manual checklist updated; user manual-verifies during /hm:wrapup.

**Risk:** medium (Cursor IDE acceptance unverified — manual checklist mitigates; mitigation is partial, real-world Cursor parsing only confirmed at IDE load).

**Rollback:** revert this phase's commit.

## Phase 6 — `/hm:health` Layer 1 `communication_protocol` sub-check (re-wired in R6)
**Scope (files in):**
- New `src/harness_maker/communication_audit.py` (or sub-module of `ai_readiness.py`) — implements:
  - `discover_dispatchers(template_dir: Path) -> list[Path]` — globs `templates/agents/*.md.j2`, excludes `_body`, `_partials`, `_standards`.
  - `discover_pinned_skills(template_dir: Path) -> list[Path]` — returns SKILL.md.j2 for the 5 ADR-005 skills.
  - `require_variant_frontmatter(template: Path) -> Result` — fails if `communication_variant` key missing; fails if value not in `{full, reframe, soft}`.
  - `scan_output_marker(rendered: Path) -> str | None` — extracts `@hm:communication_variant: X` from HTML comment in body; None if marker absent.
  - `audit_communication(template_dir, output_dir) -> list[HealthItem]` — returns structured items (same dataclass shape as ai-readiness items) suitable for the `accept/reject/defer` loop in `/hm:health` Step "Per-item structured question".
- `src/harness_maker/ai_readiness.py` (or `cli.py health` orchestrator) — invokes `audit_communication` as part of Layer 1 (structural) scoring; appends items to the same structured-question queue.
- `src/harness_maker/templates/commands/hm/health.md.j2` — Layer table row update: add `communication_protocol` as a structural sub-signal (or note that ai-readiness now covers it).
- `src/harness_maker/observability/dashboard.py` — `## Structural` section already exists (0.13.0); add a sub-line for `communication_protocol: N items` when items present.
- Two acceptance fixtures under `tests/fixtures/communication/`:
  - `fixture_a_block_removed/` — copy of an existing rendered agent with the communication block manually deleted.
  - `fixture_b_silent_miss/` — synthetic dispatcher template lacking `communication_variant` frontmatter.

**Scope (files out):** `templates/stages/verify.md.j2` — NOT touched. `/hm:verify` 6-check pattern preserved as-is (R6 explicit decision).

**Exit criterion:**
- `uv run pytest tests/unit/test_communication_audit.py` passes.
- Fixture A: `audit_communication` returns ≥1 `HealthItem` naming the block-removed file as a structural concern.
- Fixture B: `audit_communication` returns ≥1 `HealthItem` naming `communication_variant` missing on the synthetic dispatcher.
- Repo full scan: `audit_communication` returns 0 items.
- `uv run python -m harness_maker.cli health . --json-output /tmp/.health.json` produces a structural-section JSON entry referencing the sub-check; on a clean repo the item count is 0.
- `.claude/observability/dashboard.md` rendered by health includes the sub-check status under `## Structural`.

**Risk:** low (reuses 0.13.0 health infrastructure — `HealthItem` dataclass, `decisions.jsonl` append, dashboard 3-section schema).

**Rollback:** revert this phase's commit.

## Phase 7 — Test + docs
**Scope (files in):**
- `tests/unit/test_render.py` (or new file) — 5 named test cases (per validator W7):
  - `test_variant_full_renders_full_partial`
  - `test_variant_reframe_renders_reframe_partial`
  - `test_variant_soft_renders_soft_partial`
  - `test_variant_missing_raises_explicit_error` (ADR-002 forbids default-to-FULL — missing is loud error)
  - `test_variant_invalid_value_raises` (e.g., `communication_variant: hard` → raise)
- Snapshot suite — full regen (commit 2).
- e2e — one sandbox agent renders correctly with variant text in `tests/e2e/sandbox-plugin-test/` or equivalent.
- `CLAUDE.md` — append a "Communication variant policy" subsection naming: variant required, frontmatter key, render mechanism, marker policy, `/hm:health` Layer 1 sub-check. Also add to the "before fix/improve checklist" (section #1-8) a new line: "**9. When adding a new agent dispatcher template, run `/hm:health` to confirm the `communication_protocol` sub-check sees the new template's `communication_variant` frontmatter — silent-miss surfaces here as an `accept/reject/defer` item.**"
- `CHANGELOG.md` — entry under next version: "Communication variant family (FULL/REFRAME/SOFT) with explicit frontmatter; `/hm:health` Layer 1 structural sub-check `communication_protocol`; SOFT ships dormant."
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — items already added in Phase 5.

**Scope (files out):** None.

**Exit criterion:** `uv run pytest` (full suite, run in background per memory `feedback_pytest_background.md`) returns 0 failures; snapshot diff after regen = expected-only (manual review per Phase 7 docs); CLAUDE.md + CHANGELOG entries present.

**Risk:** low.

**Rollback:** revert this phase's commit.

# 🧪 Testing Strategy

## Unit
- 5 named render.py variant resolver tests (Phase 7 list).
- `test_communication_audit.py` for drift-verify primitives (Phase 6 fixtures).
- Existing render.py unit suite must not regress.

## Integration
- Snapshot regen against fixture sandboxes — verifies render.py changes propagate end-to-end through Claude/Cursor/Codex render paths.
- e2e plugin live test (`tests/e2e/test_plugin_live.py` per CLAUDE.md checkpoint #8) — actual `claude` binary loads the rendered agent.

## Manual
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — Cursor IDE load of FULL/REFRAME/SOFT variant agents.
- Visual review of CHANGELOG entry pre-wrapup.

# ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | Variant mismatch (e.g., autoloop-coder gets REFRAME) | low | medium — wrong tone guidance in real use | Explicit classification in Phase 2 plan; reviewer reads commit 1 diff against this PLAN's classification list |
| 2 | Cursor `.mdc` strict-rejects rendered output despite frontmatter being clean | medium | high — IDE silently fails to load agent | Phase 5 manual checklist; HTML comment marker is comment (not metadata) so should pass; partial fallback: if Cursor rejects, swap marker to invisible-but-grep-able anchor in body text |
| 3 | render.py pre-render extractor breaks on a dispatcher with malformed YAML | low | medium — render fails loud | Phase 2 unit test `test_variant_missing_raises_explicit_error` covers; YAML loader raises explicit ParseError, caught at render orchestration layer |
| 4 | plan-validator_body / test-reviewer_body context-line budget exceeded after REFRAME injection | low | low | Pre-checked: both ~90 lines, +14 = ~104, under 200 Production threshold; context-linter skill catches at build time |
| 5 | Silent-miss audit misses a brand-new agent template added in same PR — author forgets to run `/hm:health` | medium | medium | `/hm:health` runs on demand; not a PR-time gate (R6 trade-off). Mitigation: CHANGELOG note + CLAUDE.md "new agent checklist: run /hm:health" addition in Phase 7 docs. If toil accumulates, future plan can add `/hm:verify` advisory probe pointer to the structural item count (does not require Check 7 surgery). |
| 6 | Single-PR diff size (~78 rendered files + code) overwhelms reviewer | medium | medium | Commit split (code-only commit 1, snapshot regen commit 2); CHANGELOG + this PLAN serve as review guide |
| 7 | SOFT variant unused at merge — dead code | low | low | Documented in ADR-007 and CHANGELOG; verify lists SOFT consumers (currently 0); no maintenance burden until first consumer |

# ✅ Success Criteria

No preceding SPEC — success defined here:

- [x] 3 partial files exist at expected paths with text matching the "Partial Text" section.
- [x] All 14 dispatcher templates carry `communication_variant` frontmatter; classification matches Phase 2 list.
- [x] All 14 include sites rewritten; grep confirms 0 literal old-path hits, 14 placeholder pattern hits.
- [x] render.py pre-render extractor unit-tested (5 named cases).
- [x] 5 LLM-judgment skills carry communication block; 7 procedural skills unchanged.
- [x] Cursor `.mdc` and Codex `.toml` rendered output frontmatter/TOML metadata do NOT contain `communication_variant` key; body contains partial + HTML marker.
- [x] `/hm:health` Layer 1 (structural) sub-check `communication_protocol` surfaces Fixture A (block removed) and Fixture B (silent-miss) as `HealthItem` entries via `accept/reject/defer` queue; repo full scan returns 0 items.
- [x] Snapshot diff after regen contains only expected changes (variant blocks added/changed).
- [x] CLAUDE.md "Communication variant policy" subsection added.
- [x] CHANGELOG entry added (next version).
- [x] Cursor manual checklist items present; manual verification deferred to `/hm:wrapup`. (N/A — Phase 5 confirmed Cursor `.mdc` template does not include agent bodies; no variant-related output to manual-verify.)

# 🔍 Plan Validation

**Validator pass 1:** MAJOR_REVISION — 5 critical, 6 warning, 2 suggestion.

Resolution of criticals:
- Critical #1 (Stage dedup deletes content): Round 5 — user retracted R2 decision; ADR-003 RETRACTED.
- Critical #2 (Frontmatter location): ADR-002 amended — NEW pre-render extractor, no reuse of `_split_template_frontmatter`.
- Critical #3 (REFRAME/SOFT net-new authoring): Round 5 — user chose "paraphrase"; ADR-007 added; partial text now quoted in this PLAN body.
- Critical #4 (plan-validator + test-reviewer baseline): Round 5 — user chose REFRAME (behavior change accepted); Phase 2 explicitly names them as "newly receives REFRAME".
- Critical #5 (Silent-miss detection): ADR-006 strengthened with Fixture B; Phase 6 exit criterion now requires both fixtures.

Resolution of warnings:
- W1 (ADR-005 skill list): pinned 5 names + 7 exclusion names in ADR-005.
- W2 (rendered file auditability): ADR-004 amended — HTML comment marker.
- W3 (Cursor strict-reject mitigation): Phase 5 exit adds manual checklist entry.
- W4 (Phase 1/2 broken intermediate): Phase 1.5 added explicitly; commit split means no broken state visible to reviewer.
- W5 (Single-PR diff): Implementation Plan preamble adds two-commit split.
- W6 (trajectory-monitor): reclassified FULL (JSON output — REFRAME inapplicable).
- W7 (Phase 7 test cases): 5 named cases listed in Phase 7.

Resolution of suggestions:
- S1 (Non-Goals): added (see top of plan implicit in ADR-001; explicit list below).
- S2 (ADR-007 half-promoted): demoted to Implementation Plan preamble note; ADR-007 number reassigned to REFRAME/SOFT authoring policy.

**Validator pass 2:** NEEDS_REVISION — 0 critical, 2 warning, 1 suggestion.
- W1 (ADR-002 mechanism wording overstates pattern reuse): folded — ADR-002 now explicit "NEW pre-render extractor; existing `_split_template_frontmatter` operates on rendered output and is unrelated."
- W2 (Phase 1.5 "14 body files" wording imprecise): folded — Phase 1.5 scope now reads "14 include sites total (11 `*_body.md.j2` + 1 dispatcher `trajectory-monitor.md.j2` + 2 new body sites)".
- S1 (ADR-002 rejected alternatives): folded — Blueprint context-map alternative now listed in ADR-002.

**Outcome:** NEEDS_REVISION_RESOLVED. Gate cleared per /hm:plan procedure ("APPROVED or NEEDS_REVISION-only without criticals → write").

## Round 6 — External change absorption (2026-05-17, post-write)

Between PLAN write (2026-05-16) and execute kickoff, two upstream commits landed:
1. **`82eaddb feat(0.13.0): consolidate audit commands into /hm:health`** — `/hm:ai-readiness`, `/hm:refresh`, `/hm:personalization-audit` consolidated into single `/hm:health` with 3 layers. ADR-001 "no auto-apply" hard rule. ADR-005 reconcile orphan-sweep.
2. **`0296eed autoloop personalization-depth-2026-05 (Phases 1-12) — 0.12.0`** — introduced `personalization_audit.py`, `profile.py`, `recommendation.py`, `foreign_config.py`; block_merge.py 391-line extension.

Also discovered: **`/hm:verify` 47-line rewrite** in 0.13.0 Phase 3 — formalised 6-check stop-sign pattern owned by `verify-before-completion` SKILL; added advisory probe slot; explicit comment "adding new gating checks means changing that SKILL".

Foundational decision (R6, single round, no Layer 2 probe — single external-change absorption):
- **Drift-verify wiring re-cut from `/hm:verify` to `/hm:health` Layer 1 (structural) sub-check.** Reuses 0.13.0's `HealthItem` dataclass, `dashboard.md` 3-section schema, `decisions.jsonl` append, and `accept/reject/defer` structured-question pattern.

Trade-off explicitly accepted:
- ⚠️ Lost PR-time gating that R4 WRONG probe ("silent miss is the failure mode") implied.
- ✅ Gained alignment with 0.13.0 consolidation pattern; gained reuse of established health infrastructure; avoided `verify-before-completion` SKILL surgery.

Other absorbed changes (no decision required — self-handled):
- ADR-002 pre-render extractor pattern remains valid: `_split_template_frontmatter` still at render.py:459, NEW extractor still required.
- ADR-005 5 skills text changed in 0.13.0 but skill identity unchanged; FULL variant injection compatible.
- block_merge.py extension (0.12.0) does not affect partial files (no `@hm:user:*` markers in our partials).
- frontmatter `external_change_rebase` field added to record this absorption.

No validator re-run required: scope did not grow; one ADR re-wired with documented trade-off; no new criticals possible from rewiring an already-validated audit shape to an already-shipped audit surface.

# Non-Goals

- Approach B (auto-generated `SYCOPHANCY.md` user-doc) — deferred to a future plan after this one ships and we observe whether the variant family + verify combination satisfies user pain.
- Approach C (runtime sycophancy detector hook) — deferred per research-doc risk assessment (false-positive surface dominates).
- Runtime drift detection at IDE-load or assistant-response time — out of scope.
- SOFT variant agent assignments — none in current 14 agents; SOFT partial ships dormant per ADR-007.
- Skill REFRAME variant assignments — no current skill fits REFRAME shape; only FULL injected (per ADR-005).
- Stage template communication block changes — ADR-003 retracted; stages stay inline as-is.
- Touching `_partials/hard_rules.md.j2` — semantic overlap exists but is out of scope (avoid scope creep).
- Building a generator for the user's vault SYCOPHANCY.md across non-harness-maker projects — that's a separate, vault-level concern.
- **`/hm:verify` Check 7 gating** — explicitly rejected R6 (option D). Would require `verify-before-completion` SKILL surgery; verify is a regression stop-sign, not an audit surface.
- **`/hm:verify` advisory probe A2** — explicitly rejected R6 (option B). Non-blocking probe doesn't satisfy "actionable structured-question item" requirement set by 0.13.0 ADR-001.
- **PR-time gating for silent-miss** — `/hm:health` runs on demand; not coupled to verify. Trade-off accepted in R6.
- Re-touching `_partials/communication.md.j2` text — text becomes `communication_full.md.j2` byte-identical (only renamed + marker appended). FULL semantics intentionally unchanged from 2026-05-08 baseline.
