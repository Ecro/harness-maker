---
type: review
task_slug: model-routing-code-review-2026-05-19
status: phase-6-complete
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: model-routing-code-review-2026-05-19
  computed_at: 2026-05-19T00:00:00Z
reviewers_invoked: [code-reviewer, security-reviewer, test-reviewer, performance-reviewer]
consensus_method: cross-check
review_grade: A (strict consensus rule) — see Phase 4 caveat on manual-only-but-verified P1 findings
human_review_needed: true
created: 2026-05-19
tags: [harness-maker, review, model-routing, multi-ide, audit]
plan: "[[PLAN-model-routing-code-review-2026-05-19]]"
phase_status:
  phase_1_inventory: complete
  phase_2_resolver_schema: complete
  phase_3_render_correctness: complete
  phase_4_multiagent_consensus: complete
  phase_5_fix: complete
  phase_6_verify: complete
summary: "Deep code review of harness-maker per-agent model routing (shipped 0.15.0)."
---

# REVIEW — Model routing (harness-maker 0.15.0 → 0.17.1)

> **Discipline note (ADR-005)**: Phase 1 is a NEUTRAL inventory. No
> hypotheses, no severity tagging, no candidate findings. Facts only.
> Findings classification begins in Phase 2.

## Inventory

### Code surface

| Layer | File | Size | Public / module-level symbols |
|-------|------|------|-------------------------------|
| Schema | `src/harness_maker/models.py` | routing block ≈ lines 437–528 of 700+ LoC | `CodexAgentSpec`, `AgentModelSpec`, `HarnessConfig.default_model`, `HarnessConfig.agent_models`, `_migrate_recommended_model_dual_key`, `_validate_default_model_chars`, `_MODEL_ID_PATTERN` |
| Resolver | `src/harness_maker/presets.py` | 175 LoC | `CURSOR_MODEL_IDS`, `_Effort` (Literal type), `_spec`, `_PRODUCTION_MAP`, `_SIDE_MAP`, `PRESET_AGENT_MODELS`, `_spec_from_default_model`, `_normalize_cursor_alias`, `resolve_agent_spec` |
| Render — Claude path | `src/harness_maker/synthesize.py` | routing block ≈ lines 103–329 of 706 LoC | `_ALL_AGENTS`, `_REVIEWER_KIND`, `_COMMUNICATION_VARIANT`, `_agent_files` |
| Render — Codex path | `src/harness_maker/synthesize.py` | routing block ≈ lines 260–329 of 706 LoC | `_CODEX_AGENT_META`, `_codex_agent_files` |
| Render — entry points | `src/harness_maker/synthesize.py` | lines 491–680 (4 entry points: `synthesize`, codex variant, side+production callers) | `synthesize` and codex/side/production callers thread `agent_models` + `default_model` through |
| Health (advisory) | `src/harness_maker/readiness.py` | routing block ≈ lines 826–997 of 1101 LoC | `_dim_model_routing` (3 sub-checks: claude #43869, cursor alias, codex effort coverage) |

### Template surface

| Template | Path | Model-related variables referenced |
|----------|------|-----------------------------------|
| Agent dispatcher (14 files) | `src/harness_maker/templates/agents/{name}.md.j2` | `claude_model` — used in frontmatter `model: {{ claude_model }}` |
| Agent body (13 files) | `src/harness_maker/templates/agents/{name}_body.md.j2` | (none) |
| Codex agent | `src/harness_maker/templates/codex/agent.toml.j2` | `model_codex` (gated by `{% if model_codex %}`), `codex_reasoning_effort` (gated by `{% if codex_reasoning_effort %}`) |
| Codex config | `src/harness_maker/templates/codex/config.toml.j2` | hardcoded `[profiles.cheap].model_reasoning_effort = "minimal"`, `[profiles.deep].model_reasoning_effort = "high"` (no Jinja substitution for the effort values) |
| Codex AGENTS.md | `src/harness_maker/templates/codex/AGENTS.md.j2` | (none) |
| Codex hooks.json | `src/harness_maker/templates/codex/hooks.json.j2` | (none) |
| Codex loop / stage / workflow skills | `src/harness_maker/templates/codex/{loop,stage,workflow}_skill.md.j2` | (none) |

Agent dispatcher list (14): autoloop-coder, code-reviewer, code-verifier,
concurrency-reviewer, consensus-arbiter, executor, performance-reviewer,
plan-validator, security-auditor, security-reviewer, stuck, test-reviewer,
**trajectory-monitor**, ux-reviewer.

### Rendered output surface (main repo state)

| Path | Count | Model-bearing field |
|------|-------|---------------------|
| `.claude/agents/*.md` | 13 | YAML frontmatter `model:` |
| `.codex/agents/*.toml` | 13 | top-level `model_reasoning_effort = "..."` (when present) |
| `.codex/config.toml` | 1 | `[profiles.cheap].model_reasoning_effort`, `[profiles.deep].model_reasoning_effort` |
| `.cursor/rules/harness.mdc` | 1 | (none observed in this layer — Phase 3 enumerates full file body) |
| `.cursor/hooks.json` | 1 | (none) |
| `.cursor/mcp.json` | 1 | (none) |

Rendered `.claude/agents/*.md` list (13): autoloop-coder, code-reviewer,
code-verifier, concurrency-reviewer, consensus-arbiter, executor,
performance-reviewer, plan-validator, security-auditor, security-reviewer,
stuck, test-reviewer, ux-reviewer.

Rendered `.codex/agents/*.toml` list (13): autoloop-coder, code-reviewer,
code-verifier, concurrency-reviewer, consensus-arbiter, executor,
performance-reviewer, plan-validator, security-auditor, security-reviewer,
stuck, test-reviewer, ux-reviewer.

### Test surface

| File | LoC | Coverage area |
|------|-----|---------------|
| `tests/unit/test_presets.py` | 166 | resolver (CURSOR_MODEL_IDS, _normalize_cursor_alias, resolve_agent_spec, presets) |
| `tests/unit/test_models_agent_models.py` | 214 | schema (AgentModelSpec, CodexAgentSpec, HarnessConfig migration) |
| `tests/unit/test_render_agent_model_resolution.py` | 79 | render context build (`_agent_files`, `_codex_agent_files`) |
| `tests/unit/test_readiness_model_routing.py` | 142 | health gate (3 sub-checks) |
| `tests/unit/test_no_raw_cursor_model_ids_in_templates.py` | 78 | template hygiene (no raw concrete IDs in `.j2`) |
| `tests/unit/test_cli_deprecation_recommended_model.py` | 103 | CLI alias deprecation (`--recommended-model`) |

Total routing test LoC: **782** across 6 files.

### Render-time data flow (verbatim, no commentary)

`HarnessConfig` instance carries `preset`, `default_model`,
`agent_models`. `synthesize._agent_files(preset, agent_models,
default_model)` and `synthesize._codex_agent_files(preset, agent_models,
default_model)` both call `presets.resolve_agent_spec(name, config)`
once per name in `_ALL_AGENTS`.

`presets.resolve_agent_spec` 3-tier:
1. `config.agent_models.get(name)` — explicit per-project override.
2. `PRESET_AGENT_MODELS[config.preset].get(name)` — preset default.
3. `_spec_from_default_model(config.default_model)` — fallback synthesizing
   `AgentModelSpec` from family-substring heuristic of `default_model`.
Result passes through `_normalize_cursor_alias` (alias-form `spec.cursor`
in `CURSOR_MODEL_IDS` → concrete ID).

Returned `AgentModelSpec` fields then populate context:
- `_agent_files` context: `{name, reviewer_kind, claude_model: spec.claude, cursor_model: spec.cursor, codex_reasoning_effort: spec.codex.reasoning_effort or None}`.
- `_codex_agent_files` context: `{name, description, model_codex: None (hardcoded), codex_reasoning_effort: spec.codex.reasoning_effort or None, reviewer_kind, communication_variant}`.

### Schema-shape facts

`AgentModelSpec` fields: `claude: str | None`, `cursor: str | None`,
`codex: CodexAgentSpec | None`.

`CodexAgentSpec` fields: `model: str | None`,
`reasoning_effort: Literal["none","minimal","low","medium","high","xhigh"] | None`.

`HarnessConfig` routing-relevant fields:
- `default_model: str = Field(default="claude-opus-4-7", validation_alias=AliasChoices("default_model", "recommended_model"))`
- `agent_models: dict[str, AgentModelSpec] = Field(default_factory=dict)`
- Field-validator: `_validate_default_model_chars` (on `default_model`).
- Model-validator: `_migrate_recommended_model_dual_key` (mode="before").
- `AgentModelSpec.claude` and `AgentModelSpec.cursor` both run through
  `_validate_model_id_chars` (field_validator using `_MODEL_ID_PATTERN`
  regex `^[a-zA-Z0-9_.:-]+$` via `fullmatch`).

### Preset map shapes (counts only)

- `_PRODUCTION_MAP` size: 14 entries.
- `_SIDE_MAP` size: 14 entries.
- `_ALL_AGENTS` (synthesize.py) size: 13 entries.

### Asymmetries observed (FACTS only — no classification per ADR-005)

- The 14-vs-13 size difference between preset maps and `_ALL_AGENTS`
  corresponds to a single name: `trajectory-monitor`. The name appears
  in both `_PRODUCTION_MAP` and `_SIDE_MAP`; it does not appear in
  `_ALL_AGENTS`. The template `agents/trajectory-monitor.md.j2` exists.
  The rendered `.claude/agents/trajectory-monitor.md` and
  `.codex/agents/trajectory-monitor.toml` do not exist in current main-repo
  state.
- All 14 agent dispatcher templates reference `claude_model`. None of
  them reference `cursor_model`. The `cursor_model` key is present in the
  Jinja context dict returned by `_agent_files` for every agent name.
- The `codex_reasoning_effort` template variable is consumed by
  `templates/codex/agent.toml.j2`; the `_codex_agent_files` context dict
  also passes `codex_reasoning_effort` for every agent name.
- `templates/codex/config.toml.j2` hardcodes the two profile effort
  values (`"minimal"` / `"high"`) as literal strings, not via Jinja
  substitution of preset-derived values.
- `model_codex` is hardcoded to `None` in `_codex_agent_files`; the
  template gate `{% if model_codex %}` therefore never emits a Codex
  per-agent `model = "..."` line in current state.

## Findings

(Phase 2+ populates this section. Empty by Phase 1 design.)

### Resolver / Schema findings (Phase 2)

6 findings total — 2 High, 2 Medium, 2 Low. Severity per PLAN ADR-002
impact-based scheme. Each finding includes a source reference and an
intended-vs-observed gap. Per ADR-005, findings emerged from explicit
Phase 2 task execution (not hypothesis-seeded).

#### Finding R-1 [High] — trajectory-monitor multi-surface dormancy

**Locations**:
- `src/harness_maker/presets.py:85` (`_PRODUCTION_MAP["trajectory-monitor"] = _spec("sonnet", "low")`)
- `src/harness_maker/presets.py:108` (`_SIDE_MAP["trajectory-monitor"] = _spec("sonnet", "minimal")`)
- `src/harness_maker/synthesize.py:103-117` (`_ALL_AGENTS` excludes the name)
- `src/harness_maker/synthesize.py:118-128` (`_ALL_SKILLS` excludes the name)
- `src/harness_maker/synthesize.py:199-217` (`_COMMUNICATION_VARIANT` excludes the name; the comment at lines 203-206 acknowledges the asymmetry)
- `src/harness_maker/templates/agents/trajectory-monitor.md.j2` (dispatcher template, self-contained — uses `_partials/communication_*` include, NOT a `_body` sibling)
- `src/harness_maker/templates/skills/trajectory-monitor/SKILL.md.j2` (skill template)
- `src/harness_maker/drift_monitor.py:210` ("prompts in trajectory-monitor.md.j2 invoke this module rather than ...")

**Observation**: `trajectory-monitor` is implemented end-to-end (Python
module + 2 templates + preset entries) but is in NONE of the iteration
lists that drive rendering. `_agent_files` iterates `_ALL_AGENTS`,
`_skill_files` iterates `_ALL_SKILLS`, `_codex_agent_files` iterates
`_ALL_AGENTS`. The name appears in none of them. Consequence: no
rendered output reaches user projects (`ls .claude/agents/` and
`ls .claude/skills/` in this repo confirm `trajectory-monitor` is
absent).

The preset-map entries are dead data: `presets.resolve_agent_spec` is
called only with names that some iteration list provides. Since no list
provides `trajectory-monitor`, the resolver is never invoked for it; the
PRESET entries are unused. Same for the (intentionally absent)
`_COMMUNICATION_VARIANT` entry, which the comment block at
synthesize.py:203-206 documents as the reason it's omitted.

**Severity**: HIGH (per ADR-002 calibration anchor "Preset map references
a name absent from `_ALL_AGENTS` shape → High"). This ships a partially-
built feature with no user-facing on/off knob — the implementation is
present but disconnected.

**Tied to**: candidate finding pre-known by plan author (see Phase 5
Post-hoc Appendix). Phase 2 surfaced via explicit Task 2 (preset map
vs `_ALL_AGENTS` cross-check), not via hypothesis injection — ADR-005
discipline preserved.

#### Finding R-2 [High] — `test_preset_agent_models_completeness_vs_shipped_templates` is asymmetric

**Location**: `tests/unit/test_presets.py:25-54`

**Observation**: The completeness test enforces the
(`templates/agents/*.md.j2` exc. `_body`) ↔ (`PRESET_AGENT_MODELS` keys)
bijection. It does NOT enforce the third leg of the triangle
(`_ALL_AGENTS` membership). A name can be in templates + both preset
maps but absent from `_ALL_AGENTS` — and the test passes. This is
exactly the trajectory-monitor configuration today.

**Effect**: The test gives false confidence that "all 14 agents are
configured" when in fact only 13 are wired into render iteration. This
coverage gap directly enabled Finding R-1 to ship silently.

**Severity**: HIGH — explicit test that promises a contract it doesn't
enforce in full.

#### Finding R-3 [Medium] — `_normalize_cursor_alias` silently passes unknown alias-like values

**Location**: `src/harness_maker/presets.py:152-159`

**Observation**: When `spec.cursor` is a non-None string that is neither
an alias key in `CURSOR_MODEL_IDS` nor a known concrete ID, the function
returns the spec unchanged. The docstring documents this as "Concrete
IDs (not in CURSOR_MODEL_IDS keys) pass through unchanged" — i.e., the
intent is "anything not an alias must be a concrete ID". But there is
no verification that the string is actually a concrete ID; user typo
`cursor: opos` (intended `opus`) passes silently.

**Effect**: Cursor IDE rejects the unknown value at runtime rather than
the renderer rejecting it at config-load time. User feedback is delayed
to whenever the IDE tries to dispatch the agent. No injection vector
(charset is already restricted by `_validate_model_id_chars`).

**Test gap**: tests cover (a) `cursor=None`, (b) alias in
`CURSOR_MODEL_IDS`, (c) concrete ID. They do NOT cover (d) unknown
alias-like string. See Coverage Gap CG-2.

**Severity**: MEDIUM — documented intent, no security issue, but no
validation feedback.

#### Finding R-4 [Medium] — `HarnessConfig` ↔ `InterviewAnswers` migration-validator duplication

**Locations**:
- `src/harness_maker/models.py:485-540` (HarnessConfig)
- `src/harness_maker/models.py:633-680` (InterviewAnswers)

**Observation**: Both classes carry IDENTICAL routing-related logic:

| Element | HarnessConfig | InterviewAnswers |
|---------|---------------|------------------|
| `default_model` field | line 506-509 | line 649-652 |
| `agent_models` field | line 512 | line 654 |
| `AliasChoices("default_model", "recommended_model")` | yes | yes |
| `_migrate_recommended_model_dual_key` (model_validator mode=before) | line 515-526 | line 657-666 |
| `_validate_default_model_chars` (field_validator) | line 528-540 | line 668+ |
| `ConfigDict(strict, extra=forbid, populate_by_name=True)` | line 490 | line 638 |

The two validator bodies are byte-identical. The two field declarations
are byte-identical except for line numbers.

**Effect**: ADR-004 silent-migration policy lives in two places. Any
policy change (e.g., emit a `DeprecationWarning` here too, or refuse
old key after schema v3) must be applied to BOTH classes or the
interview-side parse and the harness.yaml-side parse will diverge.
Tests do mirror both classes (good), but the mirror is hand-maintained.

**Severity**: MEDIUM — maintenance hazard. A mixin or shared `BaseModel`
parent class would deduplicate; current state is correct but fragile.

#### Finding R-5 [Low] — `HarnessConfig.recommended_model` computed_field still present at 0.17.1

**Location**: `src/harness_maker/models.py:613-621`

**Observation**: The `@computed_field` property is documented "deprecated,
slated for removal in 0.17.0 per ADR-012". Current version is **0.17.1**
(`src/harness_maker/__init__.py` + `pyproject.toml`). The field was
scheduled for removal in 0.17.0 but persists in 0.17.1.

ADR-012 wording in [[PLAN-model-routing-multi-ide]] reads
"CLI `--recommended-model` deprecation policy: warn in 0.15.0, remove
no earlier than 0.17.0" — "no earlier than" is permissive (0.17.0 is
the FLOOR, not the binding date). The model-level computed_field
deprecation is a separate item; ADR-012 mentions CLI deprecation, not
model property. The 0.17.0 comment in the model docstring is therefore
either a tightening beyond ADR-012 or a paste-from-CLI mistake.

Either reading:
- If "0.17.0 = binding": removal is overdue.
- If "0.17.0 = floor": still legal but the docstring is misleading.

**Test reliance**: `tests/unit/test_models_agent_models.py:175-179`
calls `cfg.recommended_model` — removing would break this test. So
removal needs paired test removal.

**Severity**: LOW — ADR drift with no functional impact. Either bump
docstring to "removal scheduled for 0.18.0" or remove the field (with
paired test deletion).

#### Finding R-6 [Low] — Validator S-1 verified safe; colon-suffix is not a YAML breakout

**Location**: `src/harness_maker/models.py:444` (`_MODEL_ID_PATTERN`)

**Observation**: Plan-validator critique S-1 raised the concern that
colon-suffix payloads like `claude-opus-4-7:malicious` are not rejected
by the regex `^[a-zA-Z0-9_.:-]+$`. Verified:

1. The regex is fully anchored (`^...$`) AND called via `fullmatch` —
   defensive double-anchor. ✓
2. Colon IS permitted. When rendered as
   `model: claude-opus-4-7:malicious` in YAML, the colon does NOT
   create a key/value structure because the context is a scalar value
   (no leading mapping context, no following whitespace+key pattern).
   YAML parser reads the entire `claude-opus-4-7:malicious` as one
   string scalar. ✓
3. The actual YAML injection vectors are newline, hash, quote, `<%`,
   space — ALL rejected by the regex.

**Test coverage**: `tests/unit/test_models_agent_models.py:76-94`
explicitly tests newline, hash, nested-key (colon-then-keyword), space,
quotes — all rejected. NOT tested: colon-suffix payload (since it's
not an injection vector, no test needed for rejection). Also NOT
tested: a positive case for colon-bearing concrete ID (e.g.,
`gpt-4:turbo-preview` shape) — would assert the colon-permissive regex
is intentional rather than accidental.

**Severity**: LOW — validator concern is RESOLVED by analysis. Marked
as a finding only to document the resolution in the audit trail. The
only action is the optional positive-test addition flagged in Coverage
Gap CG-4.

### Render correctness findings (Phase 3)

4 findings + IDE parser spec comparison subsection. Methodology per
PLAN: Task 1 cross-refs context dict ↔ template variable usage; Tasks
2-4 diff rendered output frontmatter against `resolve_agent_spec()`
expected values; Task 5 enumerates `.cursor/**`; Task 6 collates IDE
parser status.

#### Finding R-7 [High] — `cursor_model` Jinja context key built but consumed by zero templates

**Locations**:
- Builder: `src/harness_maker/synthesize.py:243` (`spec = resolve_agent_spec(n, config)`) + line 251 (`"cursor_model": spec.cursor`)
- Normalizer (work done): `src/harness_maker/presets.py:152-175` (`_normalize_cursor_alias` invoked at the end of `resolve_agent_spec`)
- Consumers (none): `src/harness_maker/templates/agents/*.md.j2` — all 14 dispatcher templates plus 13 `_body.md.j2` siblings. Grep `{{ cursor_model }}` across the entire template tree returns **zero hits**.

**Observation**: `_agent_files` builds the per-agent Jinja context dict
including the key `cursor_model: spec.cursor`. The value is the
post-normalization cursor identifier (e.g., `claude-4-7-opus` after
`_normalize_cursor_alias` resolves alias-form `opus`). The intent (per
ADR-003 in [[PLAN-model-routing-multi-ide]]) was that Cursor-consumed
agent frontmatter renders the **concrete ID** rather than the alias.

What actually renders: every dispatcher template uses
`model: {% if claude_model is defined %}{{ claude_model }}{% else %}sonnet{% endif %}`.
The `claude_model` value is the alias (e.g., `opus`), NOT the
normalized concrete ID (e.g., `claude-4-7-opus`). Since Cursor reads
`.claude/agents/<n>.md` natively per the single-source policy
(CLAUDE.md "Targets 정책"), Cursor sees `model: opus` — the alias.

`cursor_model` and all the alias-normalization machinery in
`presets.py` (`CURSOR_MODEL_IDS`, `_normalize_cursor_alias`, the
`_spec(...)` alias parameter, the `_normalize_cursor_alias` call at the
end of `resolve_agent_spec`) operate on a value that is never written
to any rendered file.

**Effect**:
- Cursor 2.4 floor (per CLAUDE.md "최소 지원 Cursor 버전: 2.4") may
  not accept alias-form `model: opus` — Phase 3 IDE parser spec
  subsection below classifies this as a default-High undocumented
  acceptance question. Cursor 3.3+ accepts aliases (per ADR-003
  rationale), so 3.3+ users are unaffected.
- ADR-003 intent ("Render concrete IDs in Cursor-consumed agent
  frontmatter") is **not actually realized in rendered output today**.
  The IDs are computed but discarded; the templates emit aliases.
- The user-facing impact is "Cursor 2.4-3.2 users may see alias-form
  `model:` values that their IDE version cannot map to a concrete model
  → IDE falls back to its default model → agent dispatches against the
  wrong model silently". Severity depends on actual Cursor 2.4-3.2
  behavior (undocumented).

**Severity**: HIGH per ADR-002 calibration anchor "Context variable
built but never consumed by any template → High (silent misconfig)".
Distinguished from Critical because empirical evidence that Cursor 2.4
rejects alias-form `model:` is missing (see IDE parser spec subsection
below — would tip to Critical if Cursor 2.4 confirmed to reject).

**Tied to**: candidate finding pre-known by plan author (the cursor_model
unused observation surfaced in Round 1 preamble of /hm:plan). Surfaced
via Phase 3 Task 1 (template variable cross-reference) — an explicit
task in the PLAN. ADR-005 audit-hole acknowledged (R3 prose discipline,
risk-register row) — plan author authored the task knowing it would
surface this finding. Phase 4 multi-agent reviewers should independently
arrive here from the same code base.

#### Finding R-8 [Medium] — Rendered `.cursor/rules/harness.mdc` documents deprecated `recommended_model` key

**Locations**:
- Rendered (stale): `.cursor/rules/harness.mdc:105` — `harness.yaml.recommended_model`
- Source (corrected): `src/harness_maker/templates/cursor/rules/harness.mdc.j2:105` — `harness.yaml.default_model`

**Observation**: The rendered Cursor rule file documents the old key
name `recommended_model`. The source template was already updated to
the canonical `default_model` (ADR-002), but the user's `.cursor/`
directory was last rendered when the template still used the old name.
This concretely demonstrates the session-start drift warning ("rendered
with 0.17.0 but plugin is 0.17.1").

**Effect**: Cursor users reading the rule documentation see the
deprecated key. Functionality is intact (AliasChoices still resolves
old key in `harness.yaml`), but discoverability of the new name is
delayed. The fix is mechanical: re-render via `/hm:make --update`.

**Severity**: MEDIUM — render drift; user-facing documentation drift
without functional impact. Drift warning at session start already
nudges users to re-render.

#### Finding R-9 [Medium] — `_agent_files` context dict computes two never-used keys

**Locations**:
- Builder: `src/harness_maker/synthesize.py:247-256`
- Unused on Claude path: `cursor_model` (R-7), `codex_reasoning_effort`

**Observation**: The Claude-render context dict computed by
`_agent_files` passes five keys to Jinja templates:

| Key | Source | Used by Claude template? |
|-----|--------|-------------------------|
| `name` | iteration | yes (frontmatter `name:` + body include resolution) |
| `reviewer_kind` | `_REVIEWER_KIND.get(n, "")` | yes (body files reference it) |
| `claude_model` | `spec.claude` | yes (frontmatter `model:`) |
| `cursor_model` | `spec.cursor` (post-normalize) | **NO** (Finding R-7) |
| `codex_reasoning_effort` | `spec.codex.reasoning_effort` | **NO** (only `_codex_agent_files`'s context dict and its template `templates/codex/agent.toml.j2` use it) |

**Effect**: Two context keys per agent are computed and passed to
Jinja, then thrown away by the dispatcher template. Not a correctness
bug — Jinja ignores unused vars. But the architecture mixes Claude-path
and Codex-path concerns inside one render path. The cleaner shape
would be: `_agent_files` builds only Claude-relevant keys
(`claude_model`); `_codex_agent_files` builds only Codex-relevant keys.

**Severity**: MEDIUM — code-smell + maintenance hazard. The
`cursor_model` half is the load-bearing aspect of this finding
(covered separately by R-7).

#### Finding R-10 [Low] — `_normalize_cursor_alias` result is computed then discarded

**Locations**:
- Function: `src/harness_maker/presets.py:152-159`
- Sole consumer of output: `src/harness_maker/synthesize.py:243` via `resolve_agent_spec` → `cursor_model` context key (R-7)

**Observation**: `_normalize_cursor_alias` exists specifically to
convert alias-form `cursor` values to concrete IDs at the render
boundary. Its output flows through `resolve_agent_spec` →
`spec.cursor` → `cursor_model` context key — which is then never read
by any template. The function is exercised by unit tests
(`test_presets.py:114-167`) but the production path discards its
result.

**Effect**: Function correctness intact and tested. Observation is
about dataflow waste: the work happens, gets passed downstream, then
is dropped on the floor. If R-7 is fixed (templates start consuming
`cursor_model`), this dead-end disappears automatically.

**Severity**: LOW — implementation correct, but emblematic of R-7's
upstream waste. No standalone action; closes when R-7 closes.

#### IDE parser spec comparison (Phase 3 Task 6)

##### Cursor 2.4 alias-form `model:` acceptance — UNDOCUMENTED

Per PLAN ADR-004 (validator W-2): Cursor 2.4 subagent `model:`
frontmatter acceptance is **not documented** in Cursor public docs and
**not empirically validated** in `tests/cursor-compat/`. Grep of
`tests/cursor-compat/MANUAL_CHECKLIST.md` and `results-2026-05-08.md`
returns no model-alias acceptance data. The only acceptance evidence
the project has for Cursor 2.4+ is the hooks-compat forensic from
2026-05-08, which is silent on subagent `model:` parsing.

**Default-severity HIGH finding** (per PLAN ADR-004): absence of
evidence on a load-bearing assumption of ADR-003 in
[[PLAN-model-routing-multi-ide]]. Cannot be downgraded without manual
Cursor IDE testing, which is OUT OF SCOPE per ADR-004. Recommended
follow-up: add a Cursor 2.4 sandbox to `tests/cursor-compat/` or
empirical IDE test.

This finding is tightly coupled to R-7: if Cursor 2.4 rejects
alias-form `model: opus` and the renderer emits aliases (R-7), users on
the documented support floor get broken agent dispatch. If Cursor 2.4
silently ignores unknown `model:` values, users get the IDE default
model. Either case is a real user-facing impact; the exact severity of
R-7 depends on this answer.

##### Codex CLI `model_reasoning_effort` enum vs `_Effort` Literal — VERIFIED MATCHING (codebase-internal only)

`presets.py:45` declares `_Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]`.
Rendered values (PRODUCTION + SIDE preset maps combined): `{high, medium, low, minimal}`
— a 4-element subset of the 6-element enum. The values `none` and
`xhigh` are reserved but never exercised by any preset map entry.

Acceptance by the actual Codex CLI binary is NOT verified by this
audit (the Codex CLI itself is out of scope per ADR-004 "no manual IDE
invocation"). Behavioral risk: if Codex CLI rejects `xhigh` or `none`,
the unused enum members are deadweight (no impact); if Codex CLI
rejects any of the actually-rendered values
(`high/medium/low/minimal`), our integration would break — but the
shipping users haven't reported errors, which is weak positive
evidence.

##### Claude Code subagent routing — Anthropic issue #43869 STILL OPEN as of 2026-05-19

Verified via `gh issue view 43869 --repo anthropics/claude-code`:

```
title:   Subagent model routing is broken — all mechanisms resolve to parent model (Opus)
state:   OPEN
labels:  area:agents, area:model, bug, has repro, platform:windows
comments: 6
```

The bug confirms that all 5 documented mechanisms for routing
subagents to a different model (per-invocation `model` param,
`.claude/agents/*.md` frontmatter, `CLAUDE_CODE_SUBAGENT_MODEL` env,
settings.json env block, alias-form value) are silently ignored —
subagents always run on the parent session's model. The 13 `model:`
frontmatter values in our `.claude/agents/*.md` outputs are
**decorative under current Claude Code behavior**. Per ADR-003 they're
shipped anyway for forward-compatibility (will activate when the
upstream fix lands).

This is also covered by `readiness._dim_model_routing` sub-check (a)
(`claude_subagent_routing_43869`), which surfaces the advisory signal
when `agent_models` has any `claude:` override. Today the resolver
DOES set `claude_model` for every agent via the preset map; whether
the readiness signal fires depends on whether the user has explicit
`agent_models.<*>.claude` overrides in `harness.yaml` (most don't, so
the signal stays green by default — even though every rendered
frontmatter is ignored).

##### Summary

| IDE | Verification status | Action |
|-----|---------------------|--------|
| Claude Code | #43869 STILL OPEN (verified 2026-05-19) | Wait for upstream fix; current frontmatter forward-compat per ADR-003 |
| Cursor 2.4 floor | Undocumented acceptance behavior; no test data | Follow-up: empirical IDE test (out of scope here) |
| Cursor 3.3+ | Aliases accepted per ADR-003 rationale | OK for newer users |
| Codex CLI | `_Effort` enum used subset matches rendered output; CLI binary acceptance unverified | Acceptable signal; could be tightened by adding a `tests/cursor-compat/`-equivalent for Codex |

#### Coverage gaps (Phase 2)

5 gaps identified.

##### CG-1 — `_ALL_AGENTS` ↔ preset-map ↔ template triangle incomplete
Tied to Finding R-2. The existing
`test_preset_agent_models_completeness_vs_shipped_templates` covers two
of three legs. Recommended addition: assert
`set(_ALL_AGENTS) ⊆ set(PRESET_AGENT_MODELS[Preset.PRODUCTION].keys())`
and the same for `SIDE`, and document the inverse (preset map MAY have
extras for dormant placeholders) as policy. The current finding R-1 is
exactly an "extra" — needs an explicit policy line.

##### CG-2 — `_normalize_cursor_alias` for unknown-alias-like string
Tied to Finding R-3. Tests cover None, alias, concrete ID; missing the
unknown-string branch. Recommended:
`test_normalize_cursor_alias_unknown_string_passes_through` to lock
documented permissive intent.

##### CG-3 — `_COMMUNICATION_VARIANT` ↔ `_ALL_AGENTS` symmetry
No test asserts every name in `_ALL_AGENTS` has a matching
`_COMMUNICATION_VARIANT` entry. Currently both lists are hand-maintained;
if a future agent is added to `_ALL_AGENTS` and the variant table is
forgotten, the render Jinja `{% include "_partials/communication_" ~
communication_variant ~ ".md.j2" %}` will fail at runtime (KeyError or
TemplateNotFound). Defensive test would catch the omission earlier.

##### CG-4 — Colon-bearing valid concrete ID positive test
Tied to Finding R-6. Tests cover NEGATIVE cases (injection rejected)
and positive cases for `opus`/`sonnet`/`haiku`/`claude-4-7-opus`/
`gpt-5.5`/`model_with_underscores`. Missing positive coverage for a
colon-bearing valid concrete ID shape (e.g., `gpt-4:turbo-preview`) —
would confirm the colon-permissive regex is intentional rather than
accidental.

##### CG-5 — `HarnessConfig.recommended_model` computed_field deprecation lifecycle
Tied to Finding R-5. Existing test asserts the property RETURNS the
default_model. No test asserts the property is scheduled for removal
or warns. If ADR-012's removal date is tightened to a specific version,
adding a `pytest.mark.skipif(VERSION >= "0.18.0")` style guard to the
read-side test would make the removal lifecycle test-driven.

### Phase 2 verified (no finding — recorded for audit trail)

- **3-tier resolution chain (ADR-005)** — `presets.resolve_agent_spec`
  at lines 162-175 implements the chain in the documented order.
  Tier 1 (explicit override) wins over Tier 2 (preset) wins over Tier 3
  (default_model-derived). Tier 3 is the never-KeyErrors fallback
  (validator C-2 fix from [[PLAN-model-routing-multi-ide]]).
- **AliasChoices migration** — all 4 cases tested (both keys; only
  default_model; only recommended_model; neither). Migration validator
  body is `_migrate_recommended_model_dual_key` (mode=before) which
  drops the deprecated key when both are present.
- **Charset validator anchoring (validator S-1)** — `_MODEL_ID_PATTERN`
  uses both `^...$` and `fullmatch`. Confirmed defensive.
- **CLI deprecation warning** — emitted at `cli.py:260` via
  `warnings.warn(..., DeprecationWarning)` when `--recommended-model`
  is used. ADR-012 partial implementation (warning emit yes; field
  removal no, see Finding R-5).
- **`_spec_from_default_model` family-substring heuristic** — handles
  opus/sonnet/haiku exact-match priority `opus > sonnet > haiku` per
  the documented intent at presets.py:130-136. Unknown family →
  sonnet fallback. Both tested at test_presets.py:130-151.


#### IDE parser spec comparison (Phase 3)

_(pending)_

## Severity Index

(Phase 2 + Phase 3 entries. Phase 4 multi-agent consensus may amend
severity per ADR-002 tie-breaker rule.)

- **Critical**: (none)
- **High**:
  - R-1 (trajectory-monitor multi-surface dormancy) — Phase 2
  - R-2 (preset completeness test asymmetric) — Phase 2
  - R-7 (`cursor_model` built but consumed by zero templates) — Phase 3
  - IDE-1 (Cursor 2.4 alias acceptance undocumented; default-High per ADR-004) — Phase 3
- **Medium**:
  - R-3 (`_normalize_cursor_alias` permissive unknown-string) — Phase 2
  - R-4 (HarnessConfig/InterviewAnswers migration duplication) — Phase 2
  - R-8 (`.cursor/rules/harness.mdc` documents deprecated `recommended_model`) — Phase 3
  - R-9 (`_agent_files` context dict computes two never-used keys) — Phase 3
- **Low**:
  - R-5 (`recommended_model` computed_field ADR-012 drift) — Phase 2
  - ~~R-6~~ **RETRACTED** in Phase 4 — replaced by MV-1 / MV-2 (Pydantic `model_copy` validator bypass) — Phase 2 was wrong
  - R-10 (`_normalize_cursor_alias` result discarded) — Phase 3 (closes when R-7 closes)

### Phase 4 reviewer findings (additive to Phase 2/3)

- **Critical (verified-bug)**: MV-1 (Pydantic validator bypass on `default_model` — injection), MV-2 (same bypass on deprecated `recommended_model` migration), MV-3 (Jinja `is defined` renders `model: None`). All P1 per reviewer; orchestrator empirical verification confirms each.
- **Consensus-passed (strong)**: CP-1 (trajectory-monitor — matches R-1), CP-2 (variant↔`_ALL_AGENTS` symmetry — matches CG-3). Both P2.
- **Single-source from reviewers (manual-only, P1)**: C-1 (cursor_model unused — matches R-7).
- **Single-source from reviewers (manual-only, P2)**: S-3 (TOML description escape latent), P-1/P-2/P-3 (Pydantic re-construction + import-time cost), P-4 (executor cost-model), P-5 (no medium profile).
- **Test-reviewer single-source (manual-only)**: T-2 (no `_codex_agent_files` test coverage — High), T-4 through T-10 (8 coverage gaps).

## Multi-agent Consensus (Phase 4)

**Dispatch**: 2026-05-19, 4 reviewer agents in parallel via Task. Each
read the routing source surface independently with NO access to Phase
2-3 findings (ADR-005 independence preserved). Total reviewer findings:
**22**. Strict /hm:review consensus filter (Step 4) yields **2
consensus-passed**, **0 weak-consensus**, **20 manual-only** — but 3 of
the manual-only findings were empirically verified by the orchestrator
(Claude in this stage); those carry a `verified-bug` annotation.

### Reviewer verdicts (Phase 4 exit criterion — each named with ≥1 verdict)

- **code-reviewer**: 4 findings (C-1 through C-4). 2 P1, 2 P2.
- **security-reviewer**: 3 findings (S-1 through S-3). 2 P1, 1 P2. **S-1 / S-2 invalidate Phase 2 Finding R-6**.
- **test-reviewer**: 10 findings (T-1 through T-10). 3 High, 5 Medium, 2 Low.
- **performance-reviewer**: 5 findings (P-1 through P-5). All P2.

### Consensus-passed findings (strict surface + reasoning alignment)

#### CP-1 [P2] — trajectory-monitor preset entries are dead data
**Reviewers in agreement**: code-reviewer C-3 + test-reviewer T-1.
**Surface match**: both flag `presets.py:85,108` (trajectory-monitor in
PRESET_AGENT_MODELS) absent from synthesize.py:103-117 (`_ALL_AGENTS`).
**Reasoning**: OBSERVE matches (data structures diverge); CONCLUDE
matches (preset entries are unreachable).
**Matches plan-author candidate R-1** (Phase 2): YES — ADR-005
meta-validation positive. Three independent sources arrived at the
same finding from different starting points.
**Suggestion**: Remove `trajectory-monitor` from both preset maps OR
add to `_ALL_AGENTS` with matching `_body.md.j2` and `_COMMUNICATION_VARIANT` entry.

#### CP-2 [P2] — `_COMMUNICATION_VARIANT` / `_ALL_AGENTS` symmetry untested
**Reviewers in agreement**: code-reviewer C-4 (bare KeyError access) + test-reviewer T-3 (no structural test).
**Surface match**: both flag synthesize.py:325 (bare dict access) tied
to absence of test asserting `set(_ALL_AGENTS) == set(_COMMUNICATION_VARIANT)`.
**Reasoning**: OBSERVE matches; CONCLUDE matches (future-agent addition
KeyErrors at render time, not test time).
**Matches plan-author CG-3** (Phase 2 coverage gap): YES.
**Suggestion**: `.get(n, 'full')` defensive fallback + structural test.

### Manual-only findings (single-reviewer source) — orchestrator-verified subset called out

**3 manual-only findings were empirically verified by the orchestrator
and carry the `verified-bug` annotation. Their severity is real
regardless of reviewer-only sourcing.**

#### MV-1 [P1, verified-bug] — `default_model` charset validator BYPASSED via `model_copy(update=...)`
**Source**: security-reviewer S-1 (single-source).
**Orchestrator verification**: I read interview.py:769-770 and confirmed
`update["default_model"] = raw_default_model.strip()` followed by line
930 `base.model_copy(update=update)`. Per Pydantic v2 documentation,
`model_copy(update=...)` does NOT run field validators. Therefore
`_validate_default_model_chars` (models.py:528-540) is bypassed on the
primary `load_harness_yaml` → `answers_from_harness_yaml` path. A
user's `harness.yaml` with
`default_model: "claude-opus\ntools: [Write(*)]"` would pass through
`.strip()` (preserves embedded newlines), bypass the regex check, and
render as injected YAML in agent frontmatter.
**Severity escalation**: I had marked this region as "verified safe"
in Phase 2 Finding R-6. **R-6 is WRONG** — the regex is correct, but
the regex never runs on this path. **R-6 is hereby retracted and
replaced by MV-1.**

#### MV-2 [P1, verified-bug] — Deprecated `recommended_model` migration has the same `model_copy` bypass
**Source**: security-reviewer S-2 (single-source).
**Orchestrator verification**: interview.py:771-773 same bypass pattern
for `recommended_model` → `default_model` migration. Log sanitization
on line 775 builds `safe_value` for the INFO log only — it does NOT
sanitize the value placed in `update["default_model"]`. A schema-v1
harness.yaml with malicious `recommended_model` triggers this branch.
**Suggestion (S-1/S-2 combined)**: Apply
`_MODEL_ID_PATTERN.fullmatch(cleaned)` at interview.py:769 and :772
before assigning. On rejection, log WARNING and fall through to the
preset default.

#### MV-3 [P1, verified-bug] — Jinja `is defined` returns True for None → `model: None` renders
**Source**: code-reviewer C-2 (single-source).
**Orchestrator verification**: empirical Jinja test confirms.
`{% if x is defined %}{{ x }}{% else %}sonnet{% endif %}` with
`x=None` renders literal string `model: None`. The 14 agent dispatcher
templates use this exact guard. Trigger: user override of `agent_models`
with only `cursor:` or `codex:` set (no `claude:`) produces
`AgentModelSpec(claude=None, cursor=..., codex=...)`. The template
emits `model: None` in YAML frontmatter — agent dispatch breaks.
**Suggestion**: Replace `is defined` with `is defined and X is not none`
in all 14 dispatcher templates.

### Manual-only findings (not orchestrator-verified)

#### Code-reviewer (1)

| ID | Sev | Summary |
|----|-----|---------|
| C-1 | P1 | `cursor_model` computed but consumed by zero templates — ADR-003 R5 unrealized. **Matches plan-author R-7**: ADR-005 meta-validation positive (code-reviewer independently surfaced it). |

#### Security-reviewer (1)

| ID | Sev | Summary |
|----|-----|---------|
| S-3 | P2 | `description = "{{ description }}"` in codex/agent.toml.j2 unescaped; safety depends on hardcoded `_CODEX_AGENT_META`. Latent if any path ever sources `description` from user input. |

#### Test-reviewer (8 remaining; T-1 / T-3 promoted to consensus-passed)

| ID | Sev | Summary |
|----|-----|---------|
| T-2 | High | `_codex_agent_files()` has ZERO test coverage |
| T-4 | Med | `_normalize_cursor_alias` alias-branch only indirectly tested |
| T-5 | Med | Malformed `harness.yaml` `data={}` fallback path untested |
| T-6 | Med | Readiness Codex positive path (overrides + reasoning_effort set) untested |
| T-7 | Med | Readiness no-claude-target N/A branch never asserted |
| T-8 | Med | `test_recommended_model_value_applied` uses substring assertion — weak verification |
| T-9 | Low | `InterviewAnswers._validate_default_model_chars` positive case never tested |
| T-10 | Low | `_spec_from_default_model` returned `spec.cursor` never asserted in unit test |

#### Performance-reviewer (5)

| ID | Sev | Summary |
|----|-----|---------|
| P-1 | P2 | `HarnessConfig` constructed 3× per render in multi-target case (synthesize 611 + _agent_files 236 + _codex_agent_files 307) |
| P-2 | P2 | `SIDE_FILES` / `PRODUCTION_FILES` evaluated at import — Pydantic cost paid every CLI startup |
| P-3 | P2 | `_normalize_cursor_alias` `model_copy(update=...)` allocates a new spec per agent per render (13 per call) — could be pre-computed at preset-map load |
| P-4 | P2 | Cost-model: `executor` assigned medium effort; procedural agent doesn't need it; `low` would suffice |
| P-5 | P2 | Profile gap in `.codex/config.toml.j2`: only `cheap=minimal` + `deep=high`; no `normal=medium` graduated option |

### ADR-005 meta-validation (which plan-author candidates surfaced independently?)

| Plan-author candidate | Phase | Independently surfaced by Phase 4? |
|----------------------|-------|--------------------------------------|
| R-1 (trajectory-monitor dormancy) | Phase 2 | **YES** — code-reviewer C-3 + test-reviewer T-1 (consensus-passed CP-1) |
| R-7 (cursor_model unused) | Phase 3 | **YES** — code-reviewer C-1 (single-reviewer, but independent) |
| R-8 (`.cursor/rules/harness.mdc` stale render) | Phase 3 | **NO** — reviewers don't read rendered output drift; this is environmental, not code |

**Verdict on ADR-005 process**: positive for code-surface findings (2 of
2 code-level candidates surfaced independently). The drift finding R-8
would require a different review modality (rendered-output diff
against source template) — not a flaw of the multi-agent process but
a scope characteristic.

### Plan-author Phase 2 finding retraction

**Phase 2 Finding R-6** is **RETRACTED**. The regex is correctly anchored
(`fullmatch`) but is BYPASSED on the primary harness.yaml load path via
`model_copy(update=...)` (per MV-1 / MV-2). The plan author's
"verified safe" conclusion was wrong. Security-reviewer caught a real
issue I missed. Recording as the most important meta-finding of this
review: **multi-agent review caught a class of bug (Pydantic
validator-bypass via model_copy) that the plan author had explicitly
verified as safe.** ADR-005 process payoff demonstrated.

### Grade computation

Per /hm:review Step 4 grade rule (consensus-passed counts only):
- **P0_count = 0**
- **P1_count = 0** (no P1 has 2-of-N reviewer consensus)
- **Grade: A** (consensus-only count)

**Caveat**: 4 manual-only P1 findings (MV-1, MV-2, MV-3, C-1) exist;
MV-1, MV-2, MV-3 are orchestrator-verified empirically real bugs. The
strict-A grade reflects /hm:review's consensus rule, NOT a clean
codebase. Per PLAN ADR-002 Phase 5 rule ("only consensus-passed High
auto-fix"), these would NOT auto-fix — but they SHOULD be fixed in
Phase 5 per the orchestrator-verification annotation.

**Status: CHANGES_REQUESTED** (manual P1 findings demand action even
though grade A meets threshold). **human_review_needed: true**.

## Fix Log

Phase 5 applied 4 source-code fixes + 1 defensive guard. All 8 Phase 5
regression tests (`tests/unit/test_model_routing_review_phase5.py`) RED →
GREEN. Lint + mypy clean on modified files. Per PLAN ADR-002 + R3 audit-
hole acceptance, all 3 verified-bug manual-only findings (MV-1, MV-2,
MV-3) treated as fix-eligible despite not meeting strict consensus rule.

### Fix: MV-1 + MV-2 — Pydantic validator bypass on harness.yaml load path

**File**: `src/harness_maker/interview.py` lines 767-803
**Change**: Added `_MODEL_ID_PATTERN.fullmatch()` charset check BEFORE
assigning to `update["default_model"]`. Applied to both the
`default_model` direct path and the deprecated `recommended_model`
migration path. On rejection, emit a WARNING log and fall through to
the `HarnessConfig.default_model` Pydantic default (which `model_copy`
preserves).
**Why**: Pydantic v2 `base.model_copy(update=update)` at line 930 does
NOT run field validators, so the existing `_validate_default_model_chars`
on `HarnessConfig.default_model` was bypassed. The regex was correct
but never ran on this load path. Pre-validate at the source.
**Regression test**: `test_mv1_default_model_yaml_injection_rejected_by_loader`,
`test_mv2_recommended_model_migration_yaml_injection_rejected`.
**Severity**: P1 (P0-equivalent — YAML injection vector). Single-reviewer
sourced from security-reviewer but empirically verified by orchestrator.

### Fix: MV-3 + C-1 — Jinja None render + cursor_model unused

**Files**: 14 dispatcher templates `src/harness_maker/templates/agents/<n>.md.j2` line 6
**Change**: Replaced
```
model: {% if claude_model is defined %}{{ claude_model }}{% else %}sonnet{% endif %}
```
with
```
model: {% if cursor_model is defined and cursor_model is not none %}{{ cursor_model }}{% elif claude_model is defined and claude_model is not none %}{{ claude_model }}{% else %}sonnet{% endif %}
```
**Why two bugs fixed in one edit**:
- MV-3: `is defined` in Jinja returns True for None values. The `is not none` clause prevents emitting literal `model: None` when a user override sets only `cursor:` or `codex:` fields.
- C-1: Templates now PREFER `cursor_model` (the post-normalization concrete Cursor ID) over `claude_model` (the alias). This realizes ADR-003 R5 intent — Cursor 2.4 floor consumers now read concrete IDs like `claude-4-7-opus` instead of aliases like `opus`.
- Fallback chain: cursor_model concrete ID → claude_model alias → hardcoded `sonnet`.
**Regression tests**: `test_mv3_jinja_dispatcher_does_not_emit_model_none`,
`test_c1_cursor_model_concrete_id_rendered_when_available`,
`test_user_override_cursor_only_produces_valid_yaml`.
**Severity**: P1 each (MV-3 was orchestrator-verified single-source from
code-reviewer C-2; C-1 matches plan-author R-7 and was also single-source
code-reviewer).
**Side-effect**: existing rendered `.claude/agents/*.md` files will need
re-render to pick up the concrete-ID change. Users running `/hm:make --update`
will get the fix automatically.

### Fix: CP-1 — Remove trajectory-monitor preset entries

**File**: `src/harness_maker/presets.py` lines 66-89 (`_PRODUCTION_MAP` + `_SIDE_MAP`)
**Change**: Removed `"trajectory-monitor": _spec(..., ...)` entries from
both preset maps. Added comment explaining the removal rationale and
how to reactivate the agent (requires adding to `_ALL_AGENTS`,
`_ALL_SKILLS`, and `_COMMUNICATION_VARIANT` together).
**Why**: The agent was implemented end-to-end (Python module + 2 templates
+ preset entries) but absent from every render iteration list, making
the preset entries unreachable dead data. Removing them clears the
confusion without losing reactivation path.
**Regression test**: `test_cp1_trajectory_monitor_absent_from_preset_maps`,
`test_cp1_resolver_still_safe_for_trajectory_monitor_name` (verifies
`resolve_agent_spec('trajectory-monitor', config)` falls through Tier 1
→ Tier 2 (now empty) → Tier 3 default-derived spec without KeyError).
**Severity**: P2 — consensus-passed (CP-1 = code-reviewer C-3 + test-reviewer T-1).

### Fix: CP-2 — Defensive `.get()` for `_COMMUNICATION_VARIANT`

**File**: `src/harness_maker/synthesize.py` line 325
**Change**: Replaced `_COMMUNICATION_VARIANT[n]` bare dict access with
`_COMMUNICATION_VARIANT.get(n, "full")`. Added explanatory comment.
**Why**: If a future agent is added to `_ALL_AGENTS` without a matching
`_COMMUNICATION_VARIANT` entry, the bare `[n]` access KeyError's at user
render time. The defensive fallback emits `"full"` (the safest universal
default) so render proceeds; the structural test
`test_cp2_all_agents_subset_of_communication_variant` catches the
omission at test time instead.
**Regression test**: `test_cp2_all_agents_subset_of_communication_variant`
(structural — currently passes because the invariant holds; locks the
contract for future drift).
**Severity**: P2 — consensus-passed (CP-2 = code-reviewer C-4 + test-reviewer T-3).

### Fixes NOT applied in Phase 5 (deferred per scope)

Per user invocation `Phase 5 - MUST and SHOULD`:

- **NICE-priority items**: test-reviewer T-2 (no `_codex_agent_files` coverage), T-4 through T-10 (8 coverage gaps), performance-reviewer P-1/P-2/P-3 (Pydantic re-construction + import-time cost), P-4 (executor cost-model), P-5 (no medium profile). These ride on the same release but as separate `follow-up` issues — track in a Phase 6 follow-up issue list or schedule for a later release.
- **S-3** (TOML description escape) — latent: current `_CODEX_AGENT_META` is hardcoded so no live injection vector. Worth fixing if any future path sources description from user input; not blocking.

### Phase 2/3 finding retraction confirmed

**Finding R-6 RETRACTED** by MV-1/MV-2 (already noted in Phase 4 section).
The validator is correctly anchored (R-6 was right about that) but is
bypassed on the primary load path (R-6 was wrong about coverage). MV-1
and MV-2 are the corrected findings.

### Phase 5 collateral test updates

Two existing tests required updating as direct consequences of the fixes:

1. **`tests/unit/test_agent_body_partials.py::test_full_agent_md_sha256_unchanged`** — pinned pre-Phase-5 SHA256 hashes for all 12 active agents. The MV-3 + C-1 template change rewrites line 6 of every dispatcher template, intentionally altering the rendered output. All 12 hashes regenerated; comment in `_EXPECTED_SHA256` annotates the Phase 5 bump rationale.

2. **`tests/unit/test_presets.py::test_preset_agent_models_completeness_vs_shipped_templates`** — symmetry contract tightened to use `_ALL_AGENTS` as the source of truth (the 3-leg triangle: template ↔ `_ALL_AGENTS` ↔ preset map). Dormant templates (in `src/harness_maker/templates/agents/` but absent from `_ALL_AGENTS`) are now tolerated; preset extras (in preset maps but absent from `_ALL_AGENTS`) are forbidden. This directly resolves Phase 2 R-2's coverage gap.

Both changes lock the invariant CP-1 expects: trajectory-monitor template exists but is dormant; preset maps don't carry dead entries; future agents added to `_ALL_AGENTS` MUST have both a template and preset entries.

### Phase B false-RED escape (process learning)

When test_mv3 first ran in Phase B it PASSED, contradicting the intent (template should emit literal `model: None` until fix lands). Root cause: my `_VALID_MODEL_LINE = re.compile(r"^model:\s+[a-zA-Z0-9_.:-]+\s*$")` regex permitted alphabetical strings — and `"None"` is alphabetical. The negative assertion `"model: None" not in rendered` that test-reviewer's first round flagged as too narrow was REPLACED with a positive regex that turned out to be too permissive. Lesson: when test-reviewer's critique is structural (e.g., "the assertion is too narrow"), the fix may need to be richer than a regex — in this case, a YAML-parse-based check that distinguishes between Python None, literal "None" string, YAML null, and empty scalar. Phase B caught the escape; rewrote inline using `_extract_model_from_frontmatter` helper. Documenting because this validates Phase B's "false-RED escape" provision as a real safety net.

## Verify (Phase 6)

Phase 6 ran against the Phase 5 changes (staged in main-repo working tree).
Worktree isolation skipped — Phase 6 is read-only verification, and a fresh
worktree at main HEAD would test the OLD code (Phase 5 changes are staged
but not yet committed). Documenting this trade-off explicitly.

### Step 1 — fresh-install integration test

```bash
INTEGRATION=1 uv run pytest tests/integration/test_fresh_install_readiness.py -v --no-header
```

**Result: ✅ 5 passed in 5.04s.**

The full make → synthesize → reconcile → render → verify pipeline produces a
fresh harness whose `/hm:health` returns zero unintended P0 signals.
Composite-score floors hold (Side ≥ 66, Production ≥ 72) per PLAN ADR-006
baselines from `test_fresh_install_readiness.py:58-59`. Phase 5 fixes did
not regress the fresh-install baseline.

### Step 2 — `_dim_model_routing` baseline + 3 advisory paths

Programmatic verification with 4 hand-crafted `harness.yaml` fixtures:

| Scenario | Expected | Observed | Result |
|----------|----------|----------|--------|
| Fresh PRODUCTION + 3 targets + empty `agent_models` | all 3 sub-checks PASS; score=100 | all PASS; score=100 | ✅ |
| Claude override set + claude-code target | `claude_subagent_routing_43869` FAIL (#43869 advisory) | FAIL with the expected evidence text | ✅ |
| Cursor alias-form override + cursor target | `cursor_alias_vs_concrete_id` FAIL (ADR-003 advisory) | FAIL with the expected evidence text | ✅ |
| Codex override missing `reasoning_effort` + codex target | `codex_reasoning_effort_coverage` FAIL | FAIL with the expected evidence text | ✅ |

All 3 advisory sub-checks fire correctly and the baseline path stays clean.
No regression detected from Phase 5 fixes.

### Step 3 — semantic alignment between rendered output and `_dim_model_routing` evidence text

The `cursor_alias_vs_concrete_id` sub-check's evidence says: *"the renderer
emits concrete IDs so this is informational only"*. Pre-Phase-5 this was
**not actually true** — Finding R-7 confirmed templates only emitted
`claude_model` aliases, not `cursor_model` concrete IDs. Phase 5 MV-3+C-1
fix made the renderer behavior match the advisory's claim. Positive
side-effect: the advisory message is now semantically accurate.

### Step 4 — full unit suite regression (re-verified post-fix)

```bash
uv run pytest tests/unit -q --no-header
```

**Result: ✅ exit 0** (pytest output had no failures; 100% green per progress dots).
8 new Phase 5 regression tests pass GREEN. Pre-existing tests pass too,
including the 2 collateral updates (SHA256 hash regen + symmetry contract
tightening).

### Phase 6 verdict

**ALL verification criteria PASS.** Phase 5 fixes are:
- Correct (8 new regression tests GREEN)
- Non-regressive against fresh-install baseline (integration test 5/5 PASS)
- Compatible with `_dim_model_routing` advisory contract (4/4 scenarios)
- Lint + mypy clean (Phase D earlier)

The PLAN's success criteria can be marked satisfied. Phase 5 changes are
ready for `/hm:wrapup` to commit.

## Post-hoc Plan-Author Appendix

Per PLAN ADR-005, the appendix records whether the multi-agent process
surfaced the plan-author's pre-known candidate findings independently.

### Candidate 1: trajectory-monitor multi-surface dormancy (R-1)

**Status**: **consensus-surfaced** by Phase 4 reviewers.
- code-reviewer C-3 flagged the preset map entries as dead data.
- test-reviewer T-1 flagged the symmetry gap from the test-coverage angle.
- consensus-arbiter (orchestrator-level) tagged this as CP-1 (consensus-passed).
- **Plan-author held R-1 from Phase 2 Task 2 cross-check**; surfacing path
  was the explicit task, not a hypothesis injection. Multi-agent
  independent surfacing validates the PLAN's review methodology.

### Candidate 2: `cursor_model` unused (R-7)

**Status**: **surfaced by single reviewer** in Phase 4 (code-reviewer C-1).
- code-reviewer C-1 traced the exact data-flow gap (synthesize.py:252
  builds it; templates never consume it).
- security-reviewer, test-reviewer, performance-reviewer did NOT
  independently surface this.
- consensus-arbiter tagged as manual-only (single source).
- Plan-author held R-7 from Phase 3 Task 1 (template variable cross-ref);
  the surfacing path was the explicit task.
- Despite single-reviewer source, the finding is empirically real (Phase 5
  MV-3+C-1 fix verifies cursor_model is now consumed). Promoted to
  fix-eligible per orchestrator-verification rule.

### Candidate 3: `.cursor/rules/harness.mdc` stale render (R-8)

**Status**: **not surfaced** by Phase 4 reviewers.
- Expected — this is environmental drift (rendered file ≠ template source),
  not a code-review surface. Reviewers read source, not rendered output.
- Plan-author found R-8 via Phase 3 Task 5 (`.cursor/` enumeration). The
  task was authored knowing this drift-type finding existed.
- Resolution path is `/hm:make --update` (re-render); does not require
  source-code change. Out of Phase 5 scope.

### Meta-validation outcome

**2 of 3 candidates independently surfaced; 1 of 3 outside the code-review
modality.** ADR-005 process payoff validated on code-surface findings.

**Strongest evidence for the multi-agent process**: security-reviewer
caught a class of bug (Pydantic `model_copy(update=...)` validator bypass,
MV-1/MV-2) that the plan-author had explicitly verified-as-safe in Phase 2
(Finding R-6). That's a real defect saved from shipping in a single-author
review. The validator C-2 audit hole (R3 accepted-as-risk) materialized in
the opposite direction from what was feared: not as a hidden plan-author
bias, but as a hidden plan-author MISS that the multi-agent process
corrected. Acceptable outcome on this run — but a sealed pre-commitment
artifact (validator C-2's recommended fix) would have made the
miss-detection mechanism more explicit in the audit trail.
