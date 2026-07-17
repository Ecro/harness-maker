---
type: plan
task_slug: model-routing-code-review-2026-05-19
status: complete
created: 2026-05-19
tags: [harness-maker, plan, code-review, model-routing, multi-ide, audit]
research_doc: "[[RESEARCH-model-routing-multi-ide]]"
interview_rounds: 3
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Deep code review of 0.15.0 per-agent model routing — schema, resolver, render, health gate; critical/high fix in-plan."
---

# PLAN — Deep code review: model routing (0.15.0 → 0.17.1)

## 🎯 Executive Summary

**What**: Audit the per-agent model routing system shipped in 0.15.0
([PLAN-model-routing-multi-ide]) across three layers — schema (`models.py`),
resolver (`presets.py`), and render boundary (`synthesize.py` + templates +
rendered output under `.claude/`, `.codex/`, `.cursor/`) — and apply
critical/high fixes within this plan.

**Why**: 0.15.0 introduced 13 ADRs and ~7 new code surfaces; nothing has
audited end-to-end correctness across the 3 IDE targets since release. The
post-release patches (0.15.1 / 0.15.3 / 0.17.x) focused on tangential issues.
A focused code review now (a) catches silent misconfigurations before they
propagate via Claude Code / Cursor / Codex marketplaces, (b) verifies the
ADR set is faithfully implemented, and (c) builds regression coverage for
the routing surface before adding `skill_models` or new agents.

**Key decisions (5 ADRs)**:
- ADR-001 — Review scope = Core 3 modules + rendered output integrity
  (templates + `.claude/agents/*`, `.codex/agents/*`, `.codex/config.toml`,
  `.cursor/*`).
- ADR-002 — Deliverable = `REVIEW-model-routing-2026-05-19.md` + in-plan
  fixes for critical/high findings; medium/low → follow-up issues.
- ADR-003 — Reviewers = multi-agent (code-reviewer, security-reviewer,
  test-reviewer, performance-reviewer) → consensus-arbiter; dispatched via
  `/hm:review` after Phase 3.
- ADR-004 — Cross-IDE depth = frontmatter accuracy + IDE parser spec
  comparison (Cursor 2.4 floor, Codex CLI rejection set, Claude #43869
  status); NO manual IDE invocation in this plan.
- ADR-005 — Phase 1 is a neutral inventory (no embedded hypotheses).
  Pre-known candidate findings (cursor_model unused; trajectory-monitor
  asymmetry) are deliberately NOT seeded — multi-agent review must surface
  them independently to validate the review process itself.

**Estimated impact**: Phases 1-4 are read-only. Phase 5 fix scope is
indeterminate at plan time (depends on finding count) but bounded: at most
5 files (`presets.py`, `synthesize.py`, 1-2 templates, 1 readiness
sub-check, 1 test file). New tests: ~5-10 unit + ~2-3 snapshot
regenerations. No schema change; no version bump implied (patch-level if
any fix lands).

## 📚 Prior Work

- [[PLAN-model-routing-multi-ide]] — the 13-ADR plan that shipped routing
  (0.15.0). This review verifies its implementation faithfully reflects
  the plan.
- [[RESEARCH-model-routing-multi-ide]] — OSS landscape research; cross-IDE
  config schema baseline.
- [[PLAN-codex-plan-validator-model-unavailable]] — context for why Codex
  agent TOMLs omit `model =` (ChatGPT-tier CLI rejects most IDs).
- Anthropic GitHub issue #43869 — Claude Code subagent `model:` frontmatter
  silently ignored. Status check is part of Phase 3.
- `tests/unit/test_presets.py` (166 LoC), `test_models_agent_models.py`
  (214 LoC), `test_render_agent_model_resolution.py` (79 LoC),
  `test_readiness_model_routing.py` (142 LoC),
  `test_no_raw_cursor_model_ids_in_templates.py` (78 LoC),
  `test_cli_deprecation_recommended_model.py` (103 LoC) — existing test
  surface. Phase 2 inventories these for coverage gaps.

## 🎙️ Interview Transcript

| # | Round | Category | Question (compact) | Choice | → ADR |
|---|-------|----------|-------------------|--------|-------|
| 1 | R1 | Scope | Review surface boundary | Core 3 modules + rendered output integrity | ADR-001 |
| 2 | R1 | Deliverable | REVIEW doc only vs + fixes | REVIEW + critical/high in-plan fix | ADR-002 |
| 3 | R1 | Architecture | Single vs multi-agent reviewer | Multi-agent (code+security+test+perf) + consensus-arbiter | ADR-003 |
| 4 | R2 | Risk tolerance | Cross-IDE verification depth | Frontmatter accuracy + IDE parser spec comparison (no manual) | ADR-004 |
| 5 | R2 | Methodology | Embed pre-known suspected findings vs organic discovery | Organic discovery — no hypothesis seeding | ADR-005 |
| 6 | R3 | Risk tolerance (validator C-2) | Convert ADR-005 bias guardrail to sealed pre-commitment artifact (hash in frontmatter) vs keep prose discipline | Keep prose discipline; accept the audit-hole as a documented risk | Risk register row added |
| 7 | R3 | Mechanical (validator W-1..W-5, S-1, S-2) | Apply all warning/suggestion recommendations as-stated | Applied as-recommended | ADR-002 (tie-breaker), Phase 2/3/4/5/6 + Success Criteria edits |

Exit condition: 5-term gate — remaining ambiguities below EIG threshold
(severity scheme, phase file lists, REVIEW path all admit defensible
defaults). Open-ended cap (ko=1) preserved (0 open-ended asked).

## 📐 Architecture Decision Records

### ADR-001: Review scope = code + templates + rendered output (3 layers)
**Status:** Accepted (2026-05-19, /hm:plan R1)
**Context:** Model routing touches Pydantic schema, a Python resolver, Jinja
templates, and four classes of rendered output files (Claude .md, Codex
.toml, Codex config.toml, Cursor .mdc + native .claude/ inheritance). A
review that stops at the resolver misses the "render boundary" — exactly
where ADR-003 (Cursor concrete-ID rendering) is enforced.
**Decision:** All three layers in scope. Specifically:
1. **Code**: `models.py` (`AgentModelSpec`, `CodexAgentSpec`, `HarnessConfig`
   migration), `presets.py` (resolver + maps), `synthesize.py`
   (`_agent_files` / `_codex_agent_files`), `readiness.py`
   (`_dim_model_routing`).
2. **Templates**: `src/harness_maker/templates/agents/*.md.j2` (13 files +
   `_body.md.j2` siblings), `templates/codex/agent.toml.j2`,
   `templates/codex/config.toml.j2`.
3. **Rendered output**: `.claude/agents/*.md`, `.codex/agents/*.toml`,
   `.codex/config.toml`, `.cursor/rules/*.mdc` — compare against ADR
   intent.
**Consequences:**
- ✅ Cursor consumption of `.claude/agents/` (single-source policy) gets
  audited end-to-end.
- ✅ Render-boundary bugs (e.g., context variable build vs template
  consumption mismatch) are catchable.
- ⚠️ Phase 3 cost is higher than a code-only review.
**Rejected alternatives:**
- Code-only review — Rejected because ADR-003's concrete-ID guarantee is
  enforced at the template-substitution step, not in the resolver.
**Source:** Interview #1

### ADR-002: Deliverable = REVIEW doc + critical/high fix in-plan
**Status:** Accepted (2026-05-19, /hm:plan R1)
**Context:** REVIEW-only deliverable creates a stale-finding risk (gap
between discovery and fix); fix-everything deliverable bloats plan with
medium/low items that may not warrant churn.
**Decision:** Single `work-docs/REVIEW-model-routing-2026-05-19.md`
captures all findings classified by severity (Impact-based scheme below).
Phase 5 fixes ONLY Critical + High in this plan. Medium / Low findings get
GitHub-issue tracking entries inside the REVIEW doc.

**Severity scheme (Impact-based, default chosen at plan time):**
- **Critical** — Renders semantically wrong value to a target IDE that the
  user actually runs (e.g., emits alias `model: opus` to a Cursor version
  on the documented support floor that requires concrete IDs); OR enables
  injection vector; OR resolver KeyErrors on shipped agent.
- **High** — Silent misconfiguration invisible to user (context var emitted
  but never consumed; preset map missing a shipped agent; readiness
  sub-check false-negative); OR ADR drift between code and doc.
- **Medium** — Test coverage gap; non-blocking inconsistency.
- **Low** — Docstring / naming / cosmetic.

**Severity tie-breaker rule (validator W-1)**: If reviewers disagree on
Critical vs High for the same finding, **the higher severity wins for
fix-gating purposes**; the disagreement is logged verbatim in REVIEW.
Calibration anchors (apply to future findings without re-debate):
- *"Context variable built but never consumed by any template"* shape →
  **High** (silent misconfig; only becomes Critical if the user has
  evidence a future template will consume it).
- *"Preset map references a name absent from `_ALL_AGENTS`"* shape →
  **High** (latent inconsistency; Critical only if it crashes resolver).
- *"Frontmatter charset regex misses a YAML-significant char"* shape →
  **Critical** (injection path).

**Consequences:**
- ✅ Critical/high findings ship together with the REVIEW (single coherent
  release).
- ⚠️ Medium/low backlog accumulates in REVIEW doc — needs a follow-up
  sweep policy (out of scope here).
**Rejected alternatives:**
- REVIEW-only — Rejected: gap between discovery and fix invites the issue
  to re-surface in a later release before action.
- Fix everything — Rejected: medium/low churn outweighs benefit when the
  routing surface is already in production.
**Source:** Interview #2

### ADR-003: Multi-agent reviewer via /hm:review + consensus-arbiter
**Status:** Accepted (2026-05-19, /hm:plan R1)
**Context:** A single reviewer (Claude alone) reading the routing code is
high-bias — the plan author already spotted candidate findings during
Step-1 investigation. Multi-agent consensus on the same diff reduces
single-perspective blind spots.
**Decision:** Phase 4 dispatches via `/hm:review` with reviewer set =
`{code-reviewer, security-reviewer, test-reviewer, performance-reviewer}`.
`consensus-arbiter` aggregates findings, tagging each as
`consensus-passed | weak-consensus | manual-only`. The plan-stage Claude
does NOT pre-feed findings to reviewers — they read the source
independently.

> ⚠️ Phase 4 is a separate `/hm:review` invocation; this PLAN cannot
> directly dispatch reviewers from the plan stage. The plan describes the
> review parameters; the user runs `/hm:review` after Phase 3 completes.

**Consequences:**
- ✅ Independent surface coverage (security-reviewer flags injection;
  test-reviewer flags assertion quality; performance-reviewer flags
  preset-map cost-model errors).
- ✅ Plan-stage author's bias does not propagate into reviewer prompts.
- ⚠️ Two-stage workflow — user must explicitly invoke `/hm:review`
  between Phase 3 and Phase 5.
**Rejected alternatives:**
- Single Claude reviewer — Rejected (bias risk).
- 2-reviewer subset (code+security only) — Rejected (test/perf surface
  matters for routing: snapshot drift detection + cost-tier modeling).
**Source:** Interview #3

### ADR-004: Cross-IDE depth = frontmatter + parser spec; no manual
**Status:** Accepted (2026-05-19, /hm:plan R2)
**Context:** Three IDEs (Claude Code, Cursor, Codex CLI) each parse model
metadata differently. Full manual verification (booting each IDE, dispatching
each agent) is high-effort and outside Claude's capability — would require
the user. Frontmatter-only check misses the IDE's actual acceptance
behavior.
**Decision:** Phase 3 verifies two things automatically:
1. **Frontmatter accuracy** — rendered `.claude/agents/<n>.md::model`,
   `.codex/agents/<n>.toml::model_reasoning_effort`,
   `.codex/config.toml::[profiles.cheap|deep]`, and any `.cursor/`
   model-bearing file match the resolved spec from
   `presets.resolve_agent_spec` for the configured preset.
2. **IDE parser spec comparison** — cite/verify against documented
   acceptance:
   - Cursor 2.4 floor (per CLAUDE.md) — does it accept `model:` aliases or
     require concrete IDs? Consult Cursor docs / known-behavior matrix at
     `tests/cursor-compat/`.
   - Codex CLI — confirm `model_reasoning_effort` enum
     `{none, minimal, low, medium, high, xhigh}` is accepted today (vs.
     the per-agent `model = "..."` rejection documented in 0.14.x).
   - Claude Code — re-confirm #43869 status (silent-ignore of subagent
     `model:` frontmatter). WebFetch to GitHub for current state.

Manual IDE invocation is OUT OF SCOPE — flagged as a follow-up if any
critical finding rides on IDE behavior that documentation cannot confirm.
**Consequences:**
- ✅ Phase 3 is fully automatable; no user wait-time.
- ✅ Catches the realistic class of bugs (renderer/spec mismatch).
- ⚠️ Cannot catch undocumented IDE quirks — risk accepted, mitigated by
  multi-agent review surfacing unusual code paths.
**Rejected alternatives:**
- Manual IDE invocation — Rejected (effort + Claude cannot perform).
- Frontmatter accuracy only — Rejected (misses the "does Cursor 2.4
  actually accept this?" question, which is the load-bearing assumption
  of ADR-003 in the original routing plan).
**Source:** Interview #4

### ADR-005: Phase 1 = neutral inventory, organic discovery
**Status:** Accepted (2026-05-19, /hm:plan R2)
**Context:** During Step-1 investigation the plan author spotted two
candidate findings: (a) `cursor_model` is built in `_agent_files()` but
the only consumer template `autoloop-coder.md.j2` emits `model: {{
claude_model }}` (cursor_model unused); (b) `trajectory-monitor` is in
`PRESET_AGENT_MODELS` (presets.py:85, 108) but absent from `_ALL_AGENTS`
in synthesize.py. Embedding these as hypotheses risks priming the
multi-agent reviewers and inflating the bug count via confirmation bias.
**Decision:** Phase 1 produces a neutral surface inventory only:
- Code files touched, with line counts.
- Template files consuming model-related variables.
- Render-context dictionaries produced by `_agent_files` / `_codex_agent_files`.
- Test file inventory (782 LoC across 6 files).

NO hypotheses are written into Phase 1 or the REVIEW doc preamble.
Multi-agent review in Phase 4 must surface findings independently.

If the candidate findings DO NOT surface in Phase 4 consensus, they get
added to the REVIEW doc's "post-hoc plan-author observations" appendix
(severity-classified) — preserving the bias-free reviewer signal while
not losing real bugs.
**Consequences:**
- ✅ Reviewer signal is independent.
- ✅ Discovery accuracy (= does the multi-agent process actually catch
  these?) becomes a meta-finding about the review process itself.
- ⚠️ If reviewers miss real bugs, they live until appendix addition.
**Rejected alternatives:**
- Phase 1 explicit hypothesis — Rejected (bias).
- Hybrid hypothesis + falsifiability — Rejected (more elaborate but still
  primes reviewers).
**Source:** Interview #5

## 🏗️ Technical Design

### Current State (verified during Step 1)

- 5 ADRs shipped in 0.15.0 produced the routing architecture (13 in source
  plan; 8 of those touch code, the rest touch docs/migration/CLI).
- Resolver: `presets.resolve_agent_spec` is the single render-time entry.
- Render flow: `synthesize._agent_files` and `synthesize._codex_agent_files`
  both call resolver, build context dicts containing `claude_model`,
  `cursor_model`, `codex_reasoning_effort`, `model_codex`.
- Templates consume varying subsets of the context.
- Health gate: `readiness._dim_model_routing` is advisory (weight 0.00)
  with 3 sub-checks (Claude #43869, Cursor alias-vs-ID, Codex effort
  coverage).

### Affected Components (review surface)

| Layer | File | Notes |
|-------|------|-------|
| Schema | `src/harness_maker/models.py:440-528` | AgentModelSpec, CodexAgentSpec, HarnessConfig.default_model/agent_models, AliasChoices migration |
| Resolver | `src/harness_maker/presets.py` (entire 175 LoC) | CURSOR_MODEL_IDS, _spec, PRESET_AGENT_MODELS, _spec_from_default_model, _normalize_cursor_alias, resolve_agent_spec |
| Render | `src/harness_maker/synthesize.py:103-329` + 491-680 | _ALL_AGENTS, _agent_files, _codex_agent_files, synthesize entry points |
| Templates | `src/harness_maker/templates/agents/*.md.j2` (13 files), `templates/codex/agent.toml.j2`, `templates/codex/config.toml.j2` | Context variable consumption sites |
| Rendered | `.claude/agents/*.md` (13 files), `.codex/agents/*.toml` (13 files), `.codex/config.toml`, `.cursor/rules/*.mdc` | Frontmatter accuracy targets |
| Health | `src/harness_maker/readiness.py:826-997` | 3 advisory sub-checks |
| Tests | `tests/unit/test_presets.py`, `test_models_agent_models.py`, `test_render_agent_model_resolution.py`, `test_readiness_model_routing.py`, `test_no_raw_cursor_model_ids_in_templates.py`, `test_cli_deprecation_recommended_model.py` (782 LoC) | Coverage baseline |

### Dependencies

- Pydantic 2 (strict mode, AliasChoices, model_validator)
- Jinja2 templates
- WebFetch (for #43869 status re-check in Phase 3)

### Data Flow (verified)

```
HarnessConfig.preset + agent_models + default_model
                |
                v
   presets.resolve_agent_spec(name, config)
       Tier 1: config.agent_models[name]
       Tier 2: PRESET_AGENT_MODELS[preset][name]
       Tier 3: _spec_from_default_model(default_model)
                |
                v
   _normalize_cursor_alias(spec)  (alias -> CURSOR_MODEL_IDS[alias])
                |
                v
   synthesize._agent_files / _codex_agent_files
       context = { claude_model, cursor_model, codex_reasoning_effort,
                   model_codex=None, ... }
                |
                v
   Jinja render -> rendered files
```

### API Changes

None expected in Phase 1-4. Phase 5 may add/modify private functions if
critical findings require it; public API (`HarnessConfig`, exported
`resolve_agent_spec`) is locked unless a Critical schema bug forces it
(documented in REVIEW + ADR amendment).

## 📝 Implementation Plan

### Phase 1 — Neutral surface inventory (read-only) — **STATUS: DONE 2026-05-19**

> REVIEW doc scaffolded at `work-docs/REVIEW-model-routing-2026-05-19.md`.
> 10 `###` subsections present (exit criterion required ≥6). All findings /
> severity / consensus / fix-log / appendix sections deliberately empty per
> ADR-005 neutrality rule. Three asymmetries recorded as facts (trajectory-
> monitor unrendered; cursor_model context-key unconsumed by templates;
> codex profiles literal-not-Jinja) without classification — Phase 2/3/4
> will analyze.


**Scope (files in)**: All review-surface files listed in "Affected Components"
above; output to `work-docs/REVIEW-model-routing-2026-05-19.md`
(scaffold only — Inventory section).
**Out**: No hypotheses, no severity tagging yet.

**Tasks:**
1. Scaffold REVIEW doc with sections: Inventory / Findings (empty) /
   Severity Index (empty) / Multi-agent Consensus (empty) / Fix Log
   (empty) / Post-hoc Appendix (empty).
2. Walk every file in "Affected Components"; record file path + line
   range + role (schema / resolver / render / template / output / test).
3. For each `.j2` template, record which `{{ ... }}` model-related
   variables it consumes.
4. For each rendered output file, record the model-bearing fields
   (frontmatter `model:` for `.md`, top-level keys for `.toml`).

**Exit criterion**:
```bash
test -f work-docs/REVIEW-model-routing-2026-05-19.md && \
  grep -q "^## Inventory" work-docs/REVIEW-model-routing-2026-05-19.md && \
  grep -c "^### " work-docs/REVIEW-model-routing-2026-05-19.md
# Expect: at least 6 subsection headers (schema/resolver/render/template/output/test)
```

**Risk**: low (pure read).
**Rollback point**: N/A (no state change beyond a single new file).

### Phase 2 — Resolver + schema deep audit — **STATUS: DONE 2026-05-19**

> 6 findings (2 High / 2 Medium / 2 Low) + 5 coverage gaps recorded in
> REVIEW. R-1 (trajectory-monitor multi-surface dormancy) and R-2
> (asymmetric completeness test) are the High items. ADR-005 discipline
> preserved — R-1 surfaced via explicit Task-2 cross-check, not
> hypothesis injection. Validator S-1 concern resolved as Finding R-6
> (LOW; colon allowance is safe at YAML scalar layer).


**Scope (files in)**: `src/harness_maker/presets.py`,
`src/harness_maker/models.py` (lines 440-528), the 6 unit-test files for
routing. Update REVIEW doc's "Resolver / Schema" finding subsections.
**Out**: Templates and rendered output (Phase 3).

**Tasks:**
1. Read every line of `presets.py`; record observations against ADR-005
   3-tier intent (Tier-1 explicit / Tier-2 preset / Tier-3 default-derived).
2. Cross-check `_PRODUCTION_MAP` and `_SIDE_MAP` against `_ALL_AGENTS`
   (synthesize.py:103-117). Note any asymmetry (presence in one but not
   the other).
3. Read `_normalize_cursor_alias` — does it correctly handle: (a)
   `cursor=None`, (b) alias in CURSOR_MODEL_IDS, (c) concrete ID
   pass-through, (d) unknown alias-like value?
4. Read `AgentModelSpec` field_validator (`_validate_model_id_chars`) —
   verify charset regex (`[a-zA-Z0-9_.:-]`) rejects YAML-significant
   characters. Test injection attempts (newline, colon, hash, `<%`).
   **Verify regex is fully anchored** (`^...$` / `fullmatch`) and that
   colon-suffix payloads (e.g., `claude-opus-4-7:malicious`) are
   rejected if not part of a known concrete-ID shape (validator S-1).
5. Verify `AliasChoices` + `_migrate_recommended_model_dual_key`
   correctness — both keys present, only `default_model` present, only
   `recommended_model` present, neither present.
6. Read every test file; map assertions to source lines covered.
   Identify gaps (un-tested branches).

**Exit criterion**:
```bash
# REVIEW doc Phase 2 sections populated
grep -c "^#### Finding" work-docs/REVIEW-model-routing-2026-05-19.md
# Expect: >= 0 (zero findings is OK if code is clean — record explicitly)
# Coverage-gap subsection MUST exist:
grep -q "Coverage gaps" work-docs/REVIEW-model-routing-2026-05-19.md
```

**Risk**: low.
**Rollback point**: Phase 1 scaffold (drop Phase 2 sections, keep Inventory).

### Phase 3 — Render correctness + IDE parser spec comparison — **STATUS: DONE 2026-05-19**

> 4 findings (R-7 High / R-8 Medium / R-9 Medium / R-10 Low) + IDE
> parser spec subsection with 3 sub-checks. Plan-author candidate R-7
> (cursor_model unused) surfaced via Phase 3 Task 1; R-1 (Phase 2,
> trajectory-monitor) and R-7 now both in REVIEW Findings — both via
> explicit Phase tasks per ADR-005, but plan author authored the tasks
> knowing they would surface (audit hole acknowledged in R3 risk
> register). #43869 STILL OPEN verified 2026-05-19 via `gh issue view`.
> Cursor 2.4 alias acceptance flagged as default-High undocumented
> finding (IDE-1) per validator W-2. Next: Phase 4 multi-agent review.


**Scope (files in)**: `src/harness_maker/synthesize.py:103-329, 491-680`;
all `.j2` agent + codex templates; rendered files under `.claude/agents/`,
`.codex/agents/`, `.codex/config.toml`, `.cursor/`. WebFetch for #43869
status. Update REVIEW doc.
**Out**: Resolver/schema (Phase 2 done).

**Tasks:**
1. For each `.j2` agent template (13 files), grep for every
   `{{ <var> }}` usage; cross-reference against the context dict built in
   `_agent_files()`. Variables in context but not in any template = "built
   but unused" finding (severity per Impact rule).
2. For each rendered `.claude/agents/<n>.md`, parse the `model:`
   frontmatter; assert == resolved alias from
   `resolve_agent_spec(<n>, Production-config).claude`. Run for both
   PRODUCTION and SIDE presets via fixture re-render.
3. For each rendered `.codex/agents/<n>.toml`, assert
   `model_reasoning_effort` equals
   `resolve_agent_spec(<n>, config).codex.reasoning_effort`. Confirm
   `model = ...` is absent (per Codex ADR).
4. For `.codex/config.toml`, assert `[profiles.cheap]` ==
   `model_reasoning_effort = "minimal"` and `[profiles.deep]` ==
   `"high"`.
5. For `.cursor/rules/harness.mdc` and any other `.cursor/` outputs,
   **enumerate all rendered files via `Glob .cursor/**`** and record the
   model-bearing field set, whatever it is (validator S-2 — drop the
   pre-judgment). Document the implication: Cursor consumes
   `.claude/agents/<n>.md::model` directly.
6. **IDE parser spec comparison**:
   - Cursor 2.4 floor: alias-form `model:` (e.g., `model: opus`) acceptance
     in subagent frontmatter is **expected to be undocumented** in both
     Cursor public docs and `tests/cursor-compat/` (validator W-2
     verified the local artifact is silent on this). Phase 3 records the
     absence-of-evidence as an explicit finding **default-severity High**;
     downgradable only via manual Cursor IDE test, which is OUT OF SCOPE.
     The finding moves to follow-up regardless.
   - Codex CLI: verify `model_reasoning_effort` accepted enum matches
     `_Effort` Literal in presets.py.
   - Claude Code: WebFetch
     `https://github.com/anthropics/claude-code/issues/43869` for current
     status (still open? landed? workaround?).
7. Update REVIEW doc with findings; classify by severity per ADR-002.

**Exit criterion**:
```bash
# REVIEW doc has Phase 3 findings AND severity index populated
grep -q "^## Severity Index" work-docs/REVIEW-model-routing-2026-05-19.md && \
  grep -q "Critical" work-docs/REVIEW-model-routing-2026-05-19.md && \
  grep -q "High" work-docs/REVIEW-model-routing-2026-05-19.md && \
  grep -q "Medium" work-docs/REVIEW-model-routing-2026-05-19.md
# AND the IDE parser spec comparison subsection exists
grep -q "IDE parser spec" work-docs/REVIEW-model-routing-2026-05-19.md
```

**Risk**: medium (touches the most surface; WebFetch may rate-limit).
**Rollback point**: Phase 2 (drop Phase 3 sections from REVIEW; keep
inventory + schema findings).

### Phase 4 — Multi-agent /hm:review + consensus — **STATUS: DONE 2026-05-19**

> 4 reviewers dispatched in parallel; 22 reviewer findings total. 2
> consensus-passed (CP-1 trajectory-monitor, CP-2 variant symmetry) +
> 3 orchestrator-verified manual-only P1 bugs (MV-1/MV-2 Pydantic
> `model_copy` validator bypass — injection vector; MV-3 Jinja
> `is defined` renders `model: None`). **Plan-author Phase 2 Finding
> R-6 RETRACTED** — multi-agent process caught a class of bug
> (validator bypass) the plan author had verified-as-safe. ADR-005
> meta-validation positive: 2 of 2 code-level candidates independently
> surfaced by reviewers. Grade A by strict consensus rule; status
> CHANGES_REQUESTED due to verified P1 bugs requiring Phase 5 fix.


**Scope**: User-invoked `/hm:review` against the REVIEW doc Phase 3
state + the changed/inspected source files. Reviewers operate independently;
they read the REVIEW doc and the source code but DO NOT see this PLAN's
candidate findings (which live only in the plan author's working memory,
not in artifacts).

**Tasks** (user runs `/hm:review` with reviewer set fixed by ADR-003):
1. code-reviewer — correctness/maintainability of resolver + render path.
2. security-reviewer — injection vectors, AliasChoices migration safety,
   permissions on rendered files.
3. test-reviewer — coverage gaps, banned-pattern violations in existing
   tests, assertion quality.
4. performance-reviewer — preset-map cost-model errors, snapshot drift
   detection regression risk.
5. consensus-arbiter — aggregate; tag findings
   `consensus-passed | weak-consensus | manual-only`.

The user appends consensus output as a new section in the REVIEW doc:
`## Multi-agent Consensus (Phase 4)`.

**Exit criterion** (strengthened per validator W-3): REVIEW doc's
`## Multi-agent Consensus` section MUST enumerate each of the 4 reviewer
agents by name (code-reviewer / security-reviewer / test-reviewer /
performance-reviewer) with at least one explicit verdict per reviewer
— either `clean: no findings` OR a finding list. Each finding carries a
`consensus-passed | weak-consensus | manual-only` tag.

**Partial-failure rule**: if any reviewer is missing from the consensus
output (crash, timeout, silent skip), **halt Phase 5 and re-dispatch
`/hm:review`**. Phase 5 must not proceed on incomplete reviewer
coverage.

**Risk**: medium (depends on reviewer-agent output quality).
**Rollback point**: Phase 3 (drop consensus section, keep automated
findings).

### Phase 5 — Critical + High fixes + regression tests — **STATUS: DONE 2026-05-19**

> 4 source fixes + 1 defensive guard applied. 8 new regression tests
> (`tests/unit/test_model_routing_review_phase5.py`) all GREEN. ruff +
> mypy --strict clean on touched files. Scope per user invocation =
> MUST + SHOULD: MV-1/MV-2 (interview.py validator pre-check), MV-3 +
> C-1 (14 dispatcher templates updated for cursor_model preference +
> None guard), CP-1 (trajectory-monitor removed from preset maps), CP-2
> (`.get(n, "full")` defensive fallback). NICE items (T-2/4-10, P-1-5)
> deferred to follow-up. Phase 2 R-6 retraction confirmed (replaced by
> MV-1/MV-2). Phase B false-RED escape (test_mv3 regex over-permissive
> on "None") caught and rewritten inline with YAML-parse-based check —
> documented as a process learning. Worktree finalize stage-only pending.


**Scope (files in)**: Determined by Phase 4 consensus. Indicative cap:
≤5 files among `presets.py`, `synthesize.py`, 1-2 `.j2` templates,
`readiness.py`, plus 1-2 test files. May regenerate snapshots if
templates change.
**Out**: Medium/Low findings (logged in REVIEW for follow-up issue).

**Tasks:**
1. For each Critical finding (consensus-passed or weak-consensus):
   propose a minimal fix; record in REVIEW `## Fix Log`. Apply.
2. For each High finding (consensus-passed only — weak-consensus High
   moves to Medium): propose minimal fix; apply.
3. For every fix, add a regression test (unit preferred; snapshot if the
   change is template-side).
4. Run `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py`
   advisory (release-runbook pattern).
5. Run `uv run pytest tests/unit -q` (background per CLAUDE.md test
   policy).
6. Run `uv run ruff check . && uv run ruff format --check . && uv run
   mypy src/harness_maker` (background).

**Exit criterion** (validator C-1 — pytest is always background per
CLAUDE.md test policy + [[feedback_pytest_background]]; foreground
composite blocks ~60-120s):

Artifact-based gate (no foreground long-running commands):
```bash
# 1. Every Critical AND consensus-passed High finding has a Fix Log entry
grep -c "^### Fix:" work-docs/REVIEW-model-routing-2026-05-19.md
# (compare against count of Critical + consensus-passed High in Severity Index)

# 2. Test/lint/typecheck artifacts written by background runs exist and pass
test -f work-docs/.phase5-results/pytest.txt && \
  grep -q "passed" work-docs/.phase5-results/pytest.txt && \
  ! grep -q "failed" work-docs/.phase5-results/pytest.txt
test -f work-docs/.phase5-results/ruff.txt && \
  ! grep -q "error" work-docs/.phase5-results/ruff.txt
test -f work-docs/.phase5-results/mypy.txt && \
  ! grep -q "error:" work-docs/.phase5-results/mypy.txt
```

Tasks 5 and 6 launch their commands with `run_in_background=true`, write
stdout/stderr to `work-docs/.phase5-results/{pytest,ruff,mypy}.txt`. The
exit gate is an artifact check, not a blocking wait.

**Commit-boundary rule** (validator W-4): one fix per commit; snapshot
regen as a SEPARATE commit at the end of Phase 5. This keeps Phase 6
rollback mechanical.

**Risk**: medium (template change requires snapshot regen; regen
inside-worktree footgun documented in failures.md, mitigated by ADR-013
guard from prior plan).
**Rollback point**: Phase 4 (revert Phase 5 commits; keep REVIEW doc with
findings marked "deferred").

### Phase 6 — Verify fresh-install routing integrity — **STATUS: DONE 2026-05-19**

> `INTEGRATION=1 pytest tests/integration/test_fresh_install_readiness.py`
> = 5 passed in 5.04s. Programmatic `_dim_model_routing` against 4
> hand-crafted fixtures: baseline + 3 advisory FAIL paths all behave as
> expected. Worktree isolation deliberately skipped (Phase 5 changes are
> staged in main repo; a worktree-at-main-HEAD would test old code).
> Phase 5 collateral: cursor advisory message now matches actual renderer
> output (positive side-effect of MV-3+C-1 fix). REVIEW Verify section
> + Post-hoc Appendix populated. PLAN success criteria satisfied; ready
> for /hm:wrapup.


**Scope (files in)**: `tests/integration/test_fresh_install_readiness.py`
or equivalent fixture; no source code changes.
**Out**: Anything not in the fresh-install render path.

**Tasks:**
1. Run fresh-install fixture re-render (Production + Side presets).
2. Re-verify Phase 3 frontmatter assertions against the fresh output —
   confirms fixes did not regress the baseline.
3. Run `_dim_model_routing` against the fresh `.claude/harness.yaml` —
   confirm sub-check signals match expected baseline (e.g., empty
   `agent_models` → all 3 sub-checks pass-by-default).
4. Append `## Verify (Phase 6)` section to REVIEW doc with pass/fail per
   sub-check.

**Exit criterion**:
```bash
INTEGRATION=1 uv run pytest tests/integration/test_fresh_install_readiness.py -v
# AND REVIEW doc has Verify section
grep -q "^## Verify" work-docs/REVIEW-model-routing-2026-05-19.md
```

**Risk**: low.
**Rollback point** (validator W-4 — clarified): Phase 6 failure rolls
back **past Phase 5, to the Phase 4 consensus state** — i.e., revert ALL
Phase 5 commits AND re-mark the affected findings "deferred" in REVIEW.
Reverting only to Phase 5 would restore a known-broken state (fix
applied + verify failed), which is not stable.

## 🧪 Testing Strategy

| Layer | Pattern | When |
|-------|---------|------|
| Unit | `pytest tests/unit/test_presets.py` + new regression tests per fix | Phase 5 |
| Snapshot | Fresh-install fixture re-render + frontmatter diff | Phase 3 + Phase 6 |
| Integration | `INTEGRATION=1 pytest tests/integration/test_boundary_*.py` | Phase 5 advisory |
| Manual | Cursor IDE invocation (DEFERRED — only if Phase 3 IDE parser spec uncertain) | Out of scope; flagged as follow-up |
| WebFetch | #43869 status check | Phase 3 task 6 |

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cursor 2.4 acceptance of alias-form `model:` undocumented | medium | high | Phase 3 task 6 explicit spec check; if uncertain, flag as follow-up (manual IDE test required) |
| Reviewer agents miss pre-known candidate findings (cursor_model / trajectory-monitor) | medium | medium | ADR-005 appendix rule — add them post-hoc with severity tags; meta-finding about review process |
| Phase 5 snapshot regen footgun (worktree-cwd) | low | medium | CLAUDE.md ADR-013 guard already in place (0.15.0+); failures.md `[fail:snapshot-regen-inside-worktree]` documented |
| WebFetch rate-limit during #43869 check | low | low | Cache result locally; one fetch per plan run |
| Multi-agent reviewer disagreement on severity | medium | low | consensus-arbiter tags ambiguous as `weak-consensus`; only consensus-passed High auto-fixes; weak-consensus High → manual review (logged) |
| Critical finding requires schema change (breaks 0.15.0 contract) | low | high | If hit, halt Phase 5; escalate to /hm:plan amendment (new ADR + version bump). Terminal state captured in Success Criteria escalation checkbox. |
| Validator C-2 bias-guardrail audit hole (accepted as risk per R3) | medium | medium | ADR-005 keeps prose discipline (no sealed pre-commitment artifact). Mitigation depends on multi-agent reviewer quality + author honesty when writing the post-hoc appendix. If the bug shows up post-release, retrospect for a future-plan sealed-file policy. |

## ✅ Success Criteria

- [x] `work-docs/REVIEW-model-routing-2026-05-19.md` exists with all 6
      sections populated (Inventory / Findings / Severity / Multi-agent
      Consensus / Fix Log / Verify).
- [x] Every Critical finding has a Fix Log entry with a code reference.
- [x] Every consensus-passed High finding has a Fix Log entry.
- [x] All Medium / Low findings are logged with a follow-up GitHub-issue
      placeholder.
- [x] Phase 3 IDE parser spec comparison section cites either a Cursor
      doc URL or an empirical test reference for each of Cursor 2.4 /
      Codex CLI / Claude Code #43869.
- [x] `pytest tests/unit -q` passes; `ruff check`, `ruff format --check`,
      `mypy src/harness_maker` pass.
- [x] Fresh-install fixture re-render produces semantically unchanged
      routing output (unless a Critical fix intentionally changes it —
      then snapshot is regenerated and diff is logged in Fix Log).
- [x] Post-hoc appendix (ADR-005) records whether the multi-agent process
      surfaced the cursor_model and trajectory-monitor candidate findings
      independently — this is a meta-finding about review-process quality.
- [x] **OR — Escalation terminal state** (validator W-5): if Phase 5 hits
      a Critical finding requiring a schema change beyond the 0.15.0
      contract, the plan is **halted at Phase 5** with this completion
      shape: an amendment plan exists at
      `work-docs/PLAN-model-routing-amendment-2026-05-*.md`; Phases 1-4
      deliverables (REVIEW doc through Multi-agent Consensus section) are
      intact; Phase 5 Fix Log records the halt + escalation pointer. This
      counts as a valid completion, not a failure.

## 🔍 Plan Validation

**Outcome**: NEEDS_REVISION_RESOLVED (validator R3 follow-up).

**Critiques summary** (from `plan-validator` 2026-05-19):

| ID | Section | Resolution |
|----|---------|-----------|
| C-1 | Phase 5 exit criterion ran pytest foreground (violates CLAUDE.md test policy + [[feedback_pytest_background]]) | Resolved — converted to artifact-based gate; Tasks 5/6 background, exit checks `work-docs/.phase5-results/*.txt` |
| C-2 | Bias-guardrail audit hole (ADR-005 author writes appendix that judges themselves) | Accepted as risk (R3 user decision) — prose discipline preserved; risk register row added |
| W-1 | Severity tie-breaker not specified; reviewer disagreement defeats auto-fix gate | Resolved — ADR-002 amended with higher-severity-wins rule + 3 calibration anchors |
| W-2 | Phase 3 task 6 treats Cursor 2.4 spec check as automatable; `tests/cursor-compat/` confirmed silent on model-alias | Resolved — Phase 3 task 6 reworded; absence-of-evidence becomes explicit default-High finding moved to follow-up |
| W-3 | Phase 4 exit criterion accepts silent reviewer failure as "no findings" | Resolved — exit criterion enumerates 4 reviewers by name + partial-failure halt rule added |
| W-4 | Phase 6 rollback restored known-broken state (Phase 5 fix + verify failed) | Resolved — Phase 6 rollback target changed to "past Phase 5, to Phase 4 consensus"; Phase 5 commit-boundary rule added |
| W-5 | Critical-schema-change escalation has no matching Success Criteria terminal | Resolved — escalation checkbox added to Success Criteria |
| S-1 | Phase 2 task 4 regex anchor check not explicit | Resolved — task 4 amended with `^...$ / fullmatch` requirement + colon-suffix injection test |
| S-2 | Phase 3 task 5 pre-judged `.cursor/` outputs ("likely none") | Resolved — replaced with `Glob .cursor/**` enumeration |

Re-validation: NOT performed (NEEDS_REVISION path per `/hm:plan` Step 4
— single validator pass with resolution documented; re-run is reserved
for MAJOR_REVISION). All warnings have either an applied fix or an
explicit accepted-risk record (C-2).

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
