---
type: plan
task_slug: model-routing-multi-ide
status: planning
created: 2026-05-17
tags: [harness-maker, plan, model-routing, token-optimization, claude-code, cursor, codex, schema-migration]
research_doc: "[[RESEARCH-model-routing-multi-ide]]"
interview_rounds: 5
adrs: 13
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Per-agent model pinning + preset-aware defaults, rendered IDE-correctly, with #43869-aware health gate."
---

# PLAN — Model routing for token optimization (multi-IDE)

## 🎯 Executive Summary

**What**: Replace `HarnessConfig.recommended_model: str = "claude-opus-4-7"` with two typed fields: `default_model: str` (floor fallback) + `agent_models: dict[str, AgentModelSpec]` (per-agent overrides). Ship preset-tuned default maps (Production vs Side) in a new `presets.py`. Render IDE-correctly: Claude `model:` frontmatter (forward-compat per #43869), Cursor concrete IDs (2.4 floor), Codex per-agent `model_reasoning_effort` + `[profiles.cheap/deep]` in `.codex/config.toml`. Add `/hm:health` Layer 1 `model_routing_actionable` sub-check so silent misconfigurations don't ship.

**Why**: Today's single-string `recommended_model` cannot express per-agent cost differentiation. Existing per-agent Claude frontmatter (`opus` / `sonnet`) is hardcoded in templates, not driven by `harness.yaml`. Codex agents have zero cost differentiation (we omit `model =` and inherit a single default). Surveyed 10 OSS harnesses — convergent pattern is per-agent role pinning; harness-maker differentiates via preset-layered defaults that no harness ships today.

**Key decisions** (13 ADRs):
- ADR-001 nested per-agent block schema
- ADR-002 top-level `agent_models` + rename to `default_model`
- ADR-003 Cursor 2.4 floor → concrete IDs (with `CURSOR_MODEL_IDS` canonical constant)
- ADR-004 silent migration + advisory log
- ADR-005 default maps in Python `presets.py` (with explicit 3-tier resolution chain)
- ADR-006 single accept-preset gate (manual edit for overrides)
- ADR-007 skills inherit at runtime — no schema, no enforcement (observation, not feature)
- ADR-008 render `[profiles.cheap]` + `[profiles.deep]` in `.codex/config.toml`
- ADR-009 keep single `default_model` in 5 foreign-config templates
- ADR-010 add `/hm:health` Layer 1 `model_routing_actionable` sub-check
- ADR-011 bump `schema_version: 1 → 2`
- ADR-012 (new) CLI `--recommended-model` deprecation policy: warn in 0.15.0, remove no earlier than 0.17.0
- ADR-013 (new) `--update` CLI flag rejects cwd inside `.worktrees/` (enforce documented footgun)

**Estimated impact**: 1 new module (`presets.py` ~200 LoC), 2 new Pydantic models (`AgentModelSpec`, `CodexAgentSpec`), 1 new constants table (`CURSOR_MODEL_IDS`), 5 foreign-config templates updated (mechanical), 14 agent .md templates updated to consume new context vars, 14 Codex agent TOMLs updated (renderer-side), 2 preset YAML templates updated, `.codex/config.toml.j2` extended with profile blocks, ~40 snapshot files regenerated **per phase** (not bulk), ~30 new unit tests, 2 new integration tests, 1 new `/hm:health` sub-check, 1 CLI guard, 1 deprecated flag with alias. Version bump 0.14.3 → 0.15.0 (minor, schema change). 8 phases.

## 📚 Prior Work

- [[RESEARCH-model-routing-multi-ide]] — research surfacing OSS landscape + the 3 IDE config schemas
- [[RESEARCH-codex-plan-validator-model-unavailable]] — prior research: omit `model =` from Codex agent TOMLs (still valid). This PR layers `model_reasoning_effort` on top of the omit-`model=` baseline.
- [[project_cursor_model_policy]] memory — keep prompts model-agnostic, recommend `claude-opus-4-7`
- [[project_targets_axis]] memory — codex / cursor / claude-code multi-target axis
- Anthropic GitHub issue [#43869](https://github.com/anthropics/claude-code/issues/43869) — Claude Code subagent `model:` frontmatter is silently ignored. Surface in /hm:health gate; ship the frontmatter anyway (forward-compatible when fix lands).
- `.claude/memory/failures.md` `[fail:snapshot-regen-inside-worktree]` (count:4) — documented snapshot-regen footgun. ADR-013 promotes this from documentation-only to enforced CLI guard.
- `harness_maker.io_utils.load_harness_yaml()` — canonical loader that traverses provenance frontmatter (multi-doc YAML stream). CLAUDE.md §2 requires this for any new `harness.yaml` reader.

## 🎙️ Interview Transcript

| # | Round | Category | Question (compact) | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | R1 | Contract shape | Schema shape (flat vs nested) | Nested per-agent block | ADR-001 |
| 2 | R1 | Architecture | Field home (top-level vs nested in models dict) | Top-level `agent_models` + rename `recommended_model` → `default_model` | ADR-002 |
| 3 | R1 | Compatibility | Cursor version floor | Keep 2.4 min, render concrete IDs | ADR-003 |
| 4 | R1 | Risk tolerance | Migration policy | Silent fallback + advisory log | ADR-004 |
| 5 | R2 | Architecture | Preset default-map authoring location | Python code in `src/harness_maker/presets.py` | ADR-005 |
| 6 | R2 | UX / phasing | Interview handling of 14×3 matrix | Single accept-preset gate, no per-agent picker | ADR-006 |
| 7 | R2 | Scope | Skill-level model routing | Piggyback host agent (no `skill_models` for v1) | ADR-007 |
| 8 | R2 | Architecture | Render `[profiles.cheap]` / `[profiles.deep]` | Yes — render both per preset | ADR-008 |
| 9 | R3 | Documentation | Foreign-config templates (5 files) | Keep single `default_model` only | ADR-009 |
| 10 | R3 | Observability | `/hm:health` sub-check | Yes — add now | ADR-010 |
| 11 | R3 | Migration | `schema_version: 1 → 2` | Yes — bump | ADR-011 |
| 12 | R4 | Phasing (validator C-1) | Phase 3 snapshot strategy | Localize regen per phase | Phase 3-6 scope |
| 13 | R4 | Migration (validator W-7) | CLI deprecation window | 2-release window → 0.17.0 | ADR-012 |
| 14 | R4 | Risk (validator W-8) | Snapshot regen guard | Add CLI cwd-reject guard | ADR-013 |
| 15 | R4 | Mechanical | Apply validator C-2/C-3/W-4/W-5/W-6/S-9 | Apply all as recommended | ADR-003/005/006/007 amended; Phase 2/3/6/8 scope updated |
| 16 | R5 | Contract shape (validator W-10) | `cursor:` field semantics — alias-or-concrete-ID | Option C: normalize inside `resolve_agent_spec`; users write aliases; sub-check (b) inspects pre-resolution | ADR-003/005/010 amended; data-flow diagram + render context updated |
| 17 | R5 | Test scope (validator W-11) | Phase 1 lint regex scope | Option A: narrow regex to assignment-only patterns (YAML/MDC/JSON/TOML) | Phase 1 scope updated with exact regex patterns |

Layer 3 exit (after R3): Goals 1.0 / Constraints 1.0 / SC 0.95 / weighted 0.985 / 2-round PASS streak. R4 + R5 were validator-driven follow-ups (not gated by the convergence check).

## 📐 Architecture Decision Records

### ADR-001: Nested per-agent model spec schema
**Status:** Accepted (2026-05-17, /hm:plan R1)
**Context:** Per-agent routing needs to express both a model alias/ID AND Codex `reasoning_effort` (the dominant cost lever on Codex). Flat `agent_models.<slug>.<target> = "<id>"` cannot express Codex effort without a side-channel.
**Decision:** Each agent gets a nested `AgentModelSpec` with optional `claude`, `cursor`, `codex` sub-fields. Codex sub-field is itself a `CodexAgentSpec` carrying optional `model` (None = inherit from config.toml) + optional `reasoning_effort` (Literal enum).
**Consequences:**
- ✅ Future per-IDE knobs (verbosity, context-1M flag) slot in without schema break
- ✅ Codex `reasoning_effort` first-class
- ⚠️ Nested YAML is more verbose for users hand-editing
**Rejected:** Flat per-target keys — forces a separate `reasoning_effort` knob, splits the abstraction.
**Source:** Interview #1

### ADR-002: Top-level `agent_models` + rename `recommended_model` → `default_model`
**Status:** Accepted (2026-05-17, /hm:plan R1)
**Context:** Existing `HarnessConfig.models: dict[str, Any]` is an untyped extension slot. Could nest there or add a new top-level field.
**Decision:** Add top-level `agent_models: dict[str, AgentModelSpec]` (Pydantic-typed). Rename `recommended_model: str` → `default_model: str` (semantically clearer as the floor fallback when an agent is absent from `agent_models` and from the preset map).
**Consequences:**
- ✅ Pydantic strict mode catches typos in agent names at load time
- ✅ IDE autocomplete + mypy work on the nested spec
- ⚠️ Breaking schema rename (mitigated by ADR-004 silent fallback)
**Rejected:** Nest under `models: dict[str, Any]` — loses typing, silent typos.
**Source:** Interview #2

### ADR-003: Cursor 2.4 floor — render concrete IDs from canonical `CURSOR_MODEL_IDS` table; users write aliases, renderer normalizes
**Status:** Accepted (2026-05-17, /hm:plan R1; amended R4 per validator W-4; amended R5 per validator W-10)
**Context:** Cursor 3.3 (2026-05-07) added general alias support (`model: opus`); 2.4–3.2 only accept concrete IDs. CLAUDE.md min Cursor version is 2.4.
**Decision:** Render concrete IDs (e.g., `claude-4-7-opus`, `claude-4-6-sonnet`) in Cursor-consumed agent frontmatter. Forward-compatible — 3.3+ also accepts these. **The alias → concrete ID mapping lives in a single constant `CURSOR_MODEL_IDS: dict[str, str]` in `src/harness_maker/presets.py`** (e.g., `"opus" → "claude-4-7-opus"`, `"sonnet" → "claude-4-6-sonnet"`, `"haiku" → "claude-4-5-haiku"`).

**Resolution boundary (R5 W-10 lock-in)**: Users write **aliases** (`cursor: opus`) in `harness.yaml.agent_models`. Normalization to concrete ID happens **inside `presets.resolve_agent_spec()` at the render boundary** (not at parse time, not at the template). Templates and rendered output always carry concrete IDs. Raw concrete-ID strings in `.j2` templates are forbidden — enforced by Phase 1 lint test `test_no_raw_cursor_model_ids_in_templates`.

`AgentModelSpec.cursor` is a pass-through string at the Pydantic layer (no parse-time normalization). Users MAY hand-author a concrete ID directly (e.g., `cursor: claude-4-6-sonnet`); `resolve_agent_spec()` recognizes both alias-form and concrete-form: alias-form gets normalized via `CURSOR_MODEL_IDS`; concrete-form passes through unchanged. ADR-010 sub-check (b) inspects the **pre-resolution raw user value** (`config.agent_models[name].cursor`) so a hand-authored alias still triggers the diagnostic (informational on 3.3+, actionable on 2.4–3.2).
**Consequences:**
- ✅ Works on every supported Cursor version
- ✅ Future Claude release = one-file edit (`CURSOR_MODEL_IDS` dict), not a 5-file grep-and-replace
- ⚠️ Re-render needed when Claude releases a new minor (e.g., 4.7 → 4.8) — mitigated by single-source-of-truth + `/hm:health` future enhancement
**Rejected:** Bump min Cursor to 3.3 (loses 2.4–3.2 users); dual-render alias + comment-fallback (awkward YAML).
**Source:** Interview #3 (initial), R4 #15 (amendment for canonical home)

### ADR-004: Silent migration + advisory log
**Status:** Accepted (2026-05-17, /hm:plan R1)
**Context:** Existing user harness.yaml has `recommended_model: claude-opus-4-7`. Re-render must not break.
**Decision:** `answers_from_harness_yaml` (using `io_utils.load_harness_yaml()` per CLAUDE.md §2 — see Phase 2 scope) reads `recommended_model` (or `default_model` if present), populates `default_model`. `agent_models` defaults to `{}`. Preset defaults from `presets.py` apply at render time. One INFO log line: `recommended_model migrated to default_model; preset {Production|Side} defaults will apply to N agents.`
**Consequences:**
- ✅ Zero breakage on re-render
- ✅ Users see the migration in logs, not as an error
- ⚠️ Users who set `recommended_model` to a non-default value get that as floor; preset defaults still apply per-agent (their old value only matters for agents absent from both `agent_models` and the preset map — the third fallback per ADR-005)
**Rejected:** Hard break (disruptive); silent + future interview prompt (deferred discoverability).
**Source:** Interview #4

### ADR-005: Preset default maps in Python with explicit 3-tier resolution chain
**Status:** Accepted (2026-05-17, /hm:plan R2; amended R4 per validator C-2)
**Context:** Default maps for {Production, Side} × 14 shipped agents need a single source of truth. Users add custom agents (Model C user-as-author) — those won't be in our preset map.
**Decision:** New module `src/harness_maker/presets.py` exports `PRESET_AGENT_MODELS: dict[Preset, dict[str, AgentModelSpec]]`. Mypy-checked, snapshot-tested. **Render-time resolution chain (3 tiers + cursor normalization, in order)**:

```python
def resolve_agent_spec(name: str, config: HarnessConfig) -> AgentModelSpec:
    # Tier 1: user override in harness.yaml
    spec = config.agent_models.get(name)
    # Tier 2: preset default (only for shipped agents)
    if spec is None:
        spec = PRESET_AGENT_MODELS[config.preset].get(name)
    # Tier 3: derived from default_model (catch-all for user-authored agents)
    if spec is None:
        spec = _spec_from_default_model(config.default_model)
    # Normalize cursor alias → concrete ID at render boundary (ADR-003 R5)
    return _normalize_cursor_alias(spec)

def _normalize_cursor_alias(spec: AgentModelSpec) -> AgentModelSpec:
    """If spec.cursor is an alias key in CURSOR_MODEL_IDS, return spec with concrete ID."""
    if spec.cursor and spec.cursor in CURSOR_MODEL_IDS:
        return spec.model_copy(update={"cursor": CURSOR_MODEL_IDS[spec.cursor]})
    return spec  # pass-through for concrete IDs or None
```

`_spec_from_default_model("claude-opus-4-7")` returns `AgentModelSpec(claude="opus", cursor="opus", codex=CodexAgentSpec(reasoning_effort="medium"))` — note `cursor="opus"` (alias form) which then normalizes via `_normalize_cursor_alias`. Custom agents never KeyError; they just inherit the floor.

**Inspection contract** (for ADR-010 sub-check b): readiness.py inspects `config.agent_models[name].cursor` directly (PRE-resolution), not `resolve_agent_spec(name, config).cursor` (post-resolution). This way an alias hand-authored by a user still surfaces in the diagnostic.

**Consequences:**
- ✅ Adding a new shipped agent forces a default map entry (Tier 2 completeness test fails)
- ✅ User-authored custom agents work seamlessly via Tier 3 fallback
- ✅ Type errors at edit time, not at runtime
- ⚠️ Users cannot fork the preset map; they override per-agent in their harness.yaml instead
**Rejected:** YAML templates (drift risk, no type checking); two-tier chain only (would KeyError on user-authored agents).
**Source:** Interview #5 (initial), R4 #15 (3rd-tier fallback for user agents)

### ADR-006: Single accept-preset gate; doc pointer to HOW-IT-WORKS.md
**Status:** Accepted (2026-05-17, /hm:plan R2; amended R4 per validator S-9)
**Context:** 14 agents × 3 targets = 42 cells. Full interactive picker would exhaust users.
**Decision:** `/hm:configure` interview adds ONE question after preset choice: "Use {preset} defaults for all agent models? (Y/n)". On Y, `agent_models: {}` (preset defaults apply). On N, surface a hint: **"Edit `.claude/harness.yaml` > `agent_models` manually; schema documented in `docs/HOW-IT-WORKS.md` (Agent Models section)."** (Pointer changed from CLAUDE.md to HOW-IT-WORKS.md per validator finding — CLAUDE.md is the harness-maker repo's own instructions and is line-capped; full schema docs belong in HOW-IT-WORKS.md.)
**Consequences:**
- ✅ Zero overhead for 95% of users
- ✅ Power users can override; docs pointer leads to a real document
- ⚠️ Less discoverable than a guided picker
**Rejected:** Paginated per-agent picker (heavy UX); no question at all (lowest discoverability); point hint to CLAUDE.md (cap violation).
**Source:** Interview #6 (initial), R4 #15 (doc pointer amendment)

### ADR-007: Skills inherit at runtime — no schema, no enforcement (observation only)
**Status:** Accepted (2026-05-17, /hm:plan R2; rewritten R4 per validator W-5)
**Context:** 5 LLM-judgment skills (per ADR-005 of antisycophancy plan): `agent-quality-rubric`, `ai-readiness-rubric`, `relevance-filter`, `security-scanner`, `refdocs-search`. They invoke Claude/Cursor/Codex inference. Question: should they pin separately?
**Decision:** **No skill-level model schema. No enforcement.** Skills are loaded at runtime by the IDE; we don't render `model:` frontmatter on skills, and the IDE controls whether a skill inherits the calling agent's model or makes its own choice. This ADR documents the observation that we are **not** introducing a new control surface here.
**Consequences:**
- ✅ Zero new schema, zero new code, zero test surface
- ⚠️ A cheap skill called from an expensive agent runs at the agent's model rate (accepted; no harness today exposes skill-level model control either)
- ⚠️ Revisit only when an IDE provides skill-level pinning AND users report concrete cost pain
**Rejected:** `skill_models` schema (speculative, no IDE support yet); a runtime "piggyback" enforcement (we cannot enforce — skills are IDE-controlled).
**Source:** Interview #7 (initial), R4 #15 (clarified as non-decision per validator)

### ADR-008: Render `[profiles.cheap]` + `[profiles.deep]` in `.codex/config.toml`
**Status:** Accepted (2026-05-17, /hm:plan R2)
**Context:** Codex hooks cannot natively select a model. Cheap precheck patterns must shell out to a separate invocation. Profiles enable `codex -p cheap` / `codex -p deep`.
**Decision:** Render two profile blocks per preset:
- `[profiles.cheap]` — `model_reasoning_effort = "minimal"` (skips reasoning step)
- `[profiles.deep]` — `model_reasoning_effort = "high"`

Both inherit the default `model =` from the top of `config.toml`. Users invoke `codex -p cheap "trivial turn"` or wire into hook commands.
**Consequences:**
- ✅ Foundational for hook-time cheap inference
- ✅ Documents the cheap/deep convention in user config
- ⚠️ Users need to learn `-p cheap` invocation pattern (mitigated by README + `/hm:configure` doc)
**Rejected:** Per-agent only — leaves hooks without a cheap-inference path.
**Source:** Interview #8

### ADR-009: Foreign-config templates keep single `default_model`
**Status:** Accepted (2026-05-17, /hm:plan R3)
**Context:** 5 foreign-config templates currently show `recommended_model` as a single string: `cursor_rules.mdc.j2`, `copilot_instructions.md.j2`, `agents_md.md.j2`, `aider_conf.yml.j2`, `continue_config.json.j2`. Full `agent_models` map would duplicate ~14 entries × 5 files.
**Decision:** Rename to `default_model: {{ default_model }}` in all 5 files. Per-agent map lives only in `.claude/harness.yaml`. Foreign configs document `default_model` as a single hint; users follow the pointer for full detail.
**Consequences:**
- ✅ Minimal drift surface
- ✅ Human-readable templates stay terse
- ⚠️ continue.dev's `config.json` could in principle take the full map — accepted as v1 limitation; revisit if continue.dev users ask
**Rejected:** Render full map (5× duplication); hybrid (asymmetric, complexity).
**Source:** Interview #9

### ADR-010: Add `/hm:health` Layer 1 `model_routing_actionable` sub-check
**Status:** Accepted (2026-05-17, /hm:plan R3)
**Context:** Silent misconfigurations (Cursor 3.3 alias on 2.4 user, Claude #43869 reliance, missing Codex effort) would ship undetected.
**Decision:** Add Layer 1 structural sub-check in `readiness.py`:
- (a) Claude target present + any `resolve_agent_spec().claude` set → advisory: "subagent model frontmatter relies on Anthropic #43869 (unfixed as of 2026-05); see docs/HOW-IT-WORKS.md"
- (b) Cursor target present + any `config.agent_models[name].cursor` raw user value matching `CURSOR_MODEL_IDS` keys (i.e., user hand-authored an alias) → advisory: "User wrote alias `<value>` for agent `<name>.cursor`; renderer normalizes via CURSOR_MODEL_IDS, works on Cursor 3.3+; on Cursor 2.4–3.2 the rendered concrete ID will work but the alias-form in your harness.yaml may surprise future readers." (Inspects PRE-resolution per ADR-005 inspection contract — fires when user opts into alias-form, never fires for renderer-emitted concrete IDs.)
- (c) Codex target present + agents with `resolve_agent_spec().codex.reasoning_effort is None` → advisory with count and the list of affected agents

All 3 are **advisory** (yellow), not failure (red). Score contributes to Layer 1 but doesn't fail the gate.

**Consequences:**
- ✅ Catches silent misconfigurations on day one
- ✅ Same-PR ensures observability ships with the feature
- ⚠️ Adds 3 sub-check branches to `readiness.py`
**Rejected:** Defer (feature ships without its observability).
**Source:** Interview #10

### ADR-011: Bump `schema_version: 1 → 2`
**Status:** Accepted (2026-05-17, /hm:plan R3)
**Context:** ADR-002 introduces a visible schema change (field rename + new field).
**Decision:** `HarnessConfig.schema_version: int = 2`. ADR-004 migration code branches on `schema_version < 2` for the silent rename path. Matches the workflow-optimization ADR-016 pattern for Side users.
**Consequences:**
- ✅ Explicit migration marker for future code
- ✅ Future schema changes can chain (`< 3`, etc.)
- ⚠️ Old harness.yaml without `schema_version:` defaults to 1 → migration fires
**Rejected:** Stay at 1 — loses the explicit marker.
**Source:** Interview #11

### ADR-012: CLI `--recommended-model` deprecation: warn in 0.15.0, remove no earlier than 0.17.0
**Status:** Accepted (2026-05-17, /hm:plan R4 per validator W-7)
**Context:** ADR-002 renames `recommended_model` → `default_model`. The CLI flag `--recommended-model` must follow. A 1-release deprecation window risks breaking automated scripts that run on 0.15.0 then upgrade to 0.16.0.
**Decision:** In 0.15.0, `--recommended-model <value>` is a silent alias to `--default-model <value>` + emits one-time deprecation warning: `DeprecationWarning: --recommended-model is renamed to --default-model. The old name will be removed no earlier than 0.17.0.` Keep the alias unchanged in 0.16.0 (same warning). Remove no earlier than 0.17.0, when 0.17.0 ships an actionable error message pointing to `--default-model`.
**Consequences:**
- ✅ 2-release window gives users 2+ minor cycles to update scripts/CI
- ✅ Explicit policy, not a buried bullet
- ⚠️ Code carries the alias for 2+ releases (tolerable)
**Rejected:** 1-release window (too aggressive); permanent forever-alias (perpetual CLI noise).
**Source:** Interview #13

### ADR-013: `harness-maker make ... --update` rejects cwd inside `.worktrees/`
**Status:** Accepted (2026-05-17, /hm:plan R4 per validator W-8)
**Context:** `.claude/memory/failures.md` `[fail:snapshot-regen-inside-worktree]` count:4. Running `--update` from inside a worktree corrupts state because the regen reads/writes the wrong working tree. Documentation has been added 4 times; failure has recurred 4 times. Documentation alone is insufficient.
**Decision:** Add CLI pre-flight guard in `harness_maker/cli.py` `make` command: when `--update` is set, walk `Path.cwd().resolve()` ancestors; if any ancestor's name is `.worktrees` (or matches `.worktrees/*`), exit with code 1 and an actionable message:
```
[ERROR] Snapshot regen invoked from inside .worktrees/<branch> — this corrupts state.
        Run from the main repo root instead:
          cd <repo-root>
          uv run harness-maker make . --update
```
Ships in Phase 7 with one regression test that creates a fake `.worktrees/foo/` dir, cds in, and asserts the CLI exits 1 with the expected message.
**Consequences:**
- ✅ Turns documented footgun (count:4) into enforced prevention
- ✅ Actionable error message includes the fix command
- ⚠️ Edge case: a project that legitimately calls its working directory `.worktrees/` would be blocked (acceptable — that's an unusual layout and the message tells them what to do)
**Rejected:** Document-only (status quo failed 4 times).
**Source:** Interview #14

## 🏗️ Technical Design

### Current State
- `HarnessConfig.recommended_model: str = "claude-opus-4-7"` (models.py:440), `InterviewAnswers.recommended_model` (models.py:532)
- `synthesize.py:520` passes `recommended_model=answers.recommended_model` (single use site)
- 14 agent .md.j2 templates hardcode `model: opus | sonnet` (3 opus, 11 sonnet)
- 5 foreign-config templates propagate `recommended_model` for documentation
- 2 preset YAML templates (Side, Production) emit `recommended_model: {{ config.recommended_model }}`
- `HarnessConfig.models: dict[str, Any] = {}` (line 463) — unused extension slot, kept for future
- `HarnessConfig.schema_version: int = 1` (line 485)
- 14 Codex agent TOMLs omit `model =` per prior research (correct; kept)
- `.codex/config.toml.j2` has top-level `model =` but no `[profiles.*]` blocks
- `/hm:health` Layer 1 has multiple sub-checks; readiness module structure documented in `readiness._dim_*` functions
- No `presets.py` module exists; preset logic scattered across `recommendation.py` + interview
- `harness_maker.io_utils.load_harness_yaml()` exists (canonical multi-doc YAML loader for harness.yaml)
- `harness_maker/cli.py` has `make ... --update` command path; no cwd guard today

### Affected Components
- **NEW**: `src/harness_maker/presets.py` (~200 LoC, type-checked default map + `CURSOR_MODEL_IDS` constant + 3-tier `resolve_agent_spec()` helper)
- **NEW**: `AgentModelSpec`, `CodexAgentSpec` Pydantic models in `models.py`
- **MODIFIED**: `models.py` HarnessConfig + InterviewAnswers (rename + add field + schema_version bump)
- **MODIFIED**: `synthesize.py` (`_CODEX_AGENT_META` rendering + new agent_models passthrough)
- **MODIFIED**: `render.py` (per-agent context vars via `resolve_agent_spec()`)
- **MODIFIED**: `interview.py` (`answers_from_harness_yaml` migration using `io_utils.load_harness_yaml()` + new gate question)
- **MODIFIED**: `readiness.py` (new `_dim_model_routing` sub-check)
- **MODIFIED**: `cli.py` (deprecation alias + `--update` cwd guard)
- **MODIFIED**: 14 agent .md.j2 templates (consume `{{ claude_model | default("inherit") }}` etc.)
- **MODIFIED**: 5 foreign-config templates (rename `recommended_model` → `default_model`)
- **MODIFIED**: 2 preset YAML templates (rename)
- **MODIFIED**: `.codex/config.toml.j2` (add `[profiles.cheap]` + `[profiles.deep]`)
- **MODIFIED**: `templates/commands/hm/configure.md.j2` (single accept-preset gate)
- **MODIFIED**: `docs/HOW-IT-WORKS.md` (new "Agent Models" section with worked example)
- **REGEN per phase** (not bulk): agent .md snapshots in Phase 3; Codex TOML snapshots in Phase 4; dashboard snapshot in Phase 6; full sandbox sweep in Phase 7

### Dependencies
- No new pip deps. Pydantic ConfigDict + Literal already in use.
- Existing `harness_maker.io_utils.load_harness_yaml()` reused (CLAUDE.md §2 contract).

### Architecture (data flow)

```
harness.yaml (multi-doc YAML with provenance frontmatter)
  ---
  generated_by: harness-maker
  content_hash: ...
  ---
  default_model: "claude-opus-4-7"
  agent_models:
    autoloop-coder:
      claude: opus              # alias; passes through to Claude (decorative per #43869)
      cursor: opus              # alias; normalized to "claude-4-7-opus" at render boundary
      codex:
        reasoning_effort: high
    # (other agents inherit preset defaults from presets.py)
    # Note: users MAY write concrete IDs (cursor: claude-4-6-sonnet) — pass-through.
  preset: Side
  schema_version: 2
        ↓
io_utils.load_harness_yaml()  ← canonical multi-doc loader
        ↓
interview.answers_from_harness_yaml
  - if schema_version<2 or 'recommended_model' present: silent rename + INFO log
  - else: direct read
        ↓
HarnessConfig (Pydantic-typed, strict, extra=forbid)
        ↓
render.py
  for each agent name:
    spec = presets.resolve_agent_spec(name, config)  ← 3-tier chain + cursor alias normalization
    # Tier 1: config.agent_models.get(name)
    # Tier 2: PRESET_AGENT_MODELS[config.preset].get(name)
    # Tier 3: _spec_from_default_model(config.default_model)
    # Then: _normalize_cursor_alias(spec) — alias → concrete ID via CURSOR_MODEL_IDS
    context["claude_model"] = spec.claude                                # alias OK on Claude Code
    context["cursor_model"] = spec.cursor                                # ALWAYS concrete ID post-normalization
    context["codex_reasoning_effort"] = spec.codex.reasoning_effort if spec.codex else None
        ↓
agent .md.j2 / Codex .toml synthesize
  model: {{ claude_model }}                          # Claude (decorative per #43869)
  model: {{ cursor_model }}                          # Cursor (concrete ID, honored)
  model_reasoning_effort = "{{ codex.effort }}"     # Codex (honored)
        ↓
.codex/config.toml.j2
  model = "{{ default_model_codex_id }}"
  [profiles.cheap]
    model_reasoning_effort = "minimal"
  [profiles.deep]
    model_reasoning_effort = "high"
        ↓
/hm:health Layer 1 _dim_model_routing
  - reads HarnessConfig + targets
  - 3 advisory sub-checks (Claude #43869, Cursor alias-vs-ID, Codex missing effort)
```

### API Changes
- `HarnessConfig.recommended_model` REMOVED → `default_model: str` (rename, schema_version=2)
- `HarnessConfig.agent_models: dict[str, AgentModelSpec]` NEW (default `{}`)
- `HarnessConfig.schema_version: 1 → 2`
- `InterviewAnswers.recommended_model` REMOVED → `default_model: str`
- `InterviewAnswers.agent_models: dict[str, AgentModelSpec]` NEW
- `AgentModelSpec` NEW (Pydantic, strict, extra=forbid)
- `CodexAgentSpec` NEW (Pydantic, strict, extra=forbid; `reasoning_effort: Literal["none","minimal","low","medium","high","xhigh"] | None`)
- `presets.PRESET_AGENT_MODELS: dict[Preset, dict[str, AgentModelSpec]]` NEW
- `presets.CURSOR_MODEL_IDS: dict[str, str]` NEW (alias → concrete ID)
- `presets.resolve_agent_spec(name, config) -> AgentModelSpec` NEW (3-tier)
- `presets._spec_from_default_model(default_model: str) -> AgentModelSpec` NEW (Tier 3 fallback)
- `interview.answers_from_harness_yaml`: handles schema_version 1 and 2 via `io_utils.load_harness_yaml()`
- CLI: `--recommended-model` deprecated alias → `--default-model` (per ADR-012, removed no earlier than 0.17.0)
- CLI: `make --update` rejects cwd inside `.worktrees/` (per ADR-013)

## 📝 Implementation Plan

### Phase 1 — Schema + presets module + canonical ID table (models.py, presets.py, unit tests, NO snapshot impact)

> **Execute deviations (2026-05-17/18)**:
> 1. **`recommended_model` kept as Pydantic `AliasChoices`** on `default_model` (`populate_by_name=True` + `extra="forbid"`) instead of a hard rename. Read-side back-compat exposed via `@property recommended_model -> str` that returns `default_model`. This is the only way to ship the rename without breaking all 35 existing call sites in the same PR. Property is slated for removal in 0.17.0 per ADR-012 timing.
> 2. **`model_validator(mode="before")` `_migrate_recommended_model_dual_key`** silently drops `recommended_model` when both `default_model` and `recommended_model` are present in the input dict. Without it, AliasChoices + extra="forbid" raises `extra_forbidden` on the dual-key precedence case — which is exactly what ADR-004 silent migration calls for.
> 3. **Test fixes**: `Preset.PRODUCTION` enum value (not `"Production"` string) in `model_validate(...)` calls because `strict=True` rejects coercion.
> 4. **`@property` → `@computed_field`**: required so `recommended_model` appears in `model_dump()` dicts; Jinja2 templates that access `{{ config.recommended_model }}` after a model dump need the key present (templates are migrated to `default_model` in Phase 3 but this keeps Phase 1's regression delta at zero).
> 5. **Existing test update**: `tests/unit/test_schema_migration.py::test_schema_version_field_present_in_models` asserted HarnessConfig.schema_version == 1; updated to == 2 with a docstring referencing ADR-011. This is the only existing-test edit in Phase 1.
- **Scope IN**:
  - `src/harness_maker/models.py`: add `AgentModelSpec`, `CodexAgentSpec`, rename `recommended_model` → `default_model`, add `agent_models: dict[str, AgentModelSpec]`, bump `schema_version: 2`. Apply both to `HarnessConfig` and `InterviewAnswers`.
  - `src/harness_maker/presets.py` (NEW): `PRESET_AGENT_MODELS`, `CURSOR_MODEL_IDS`, `resolve_agent_spec()`, `_spec_from_default_model()`.
  - `tests/unit/test_models_agent_models.py` (NEW): AgentModelSpec/CodexAgentSpec strict mode (extra=forbid), reasoning_effort enum validation, nested round-trip.
  - `tests/unit/test_presets.py` (NEW): completeness check (every shipped agent in `templates/agents/*.md.j2` has an entry in BOTH Production and Side maps); `resolve_agent_spec` 3-tier chain (Tier 1/2/3 each tested); `_spec_from_default_model` returns valid spec for known + unknown default_model values.
  - `tests/unit/test_no_raw_cursor_model_ids_in_templates.py` (NEW; R5 W-11 scope): match assignment-only patterns to avoid false-positives on prose mentions. Exact patterns inspected:
    - YAML/MDC frontmatter: `^\s*model:\s+claude-[0-9-]+\s*$` (multiline)
    - JSON: `"model"\s*:\s*"claude-[0-9-]+"`
    - TOML: `^\s*model\s*=\s*"claude-[0-9-]+"\s*$`

    Scope: `src/harness_maker/templates/**/*.j2` (all template categories). Failure: any match outside `src/harness_maker/presets.py`. Prose mentions like "this agent invokes claude-3-5-sonnet for X" are intentionally NOT matched. Concrete IDs flowing through template variables (`{{ cursor_model }}`) are also NOT matched — only raw string literals embedded in frontmatter assignment positions.
- **Scope OUT**: render path, interview, foreign configs, Codex synthesize.
- **Exit criterion**: `uv run pytest tests/unit/test_models_agent_models.py tests/unit/test_presets.py tests/unit/test_no_raw_cursor_model_ids_in_templates.py -v` GREEN; `uv run mypy --strict src/harness_maker/models.py src/harness_maker/presets.py` clean; `uv run ruff check src/harness_maker/models.py src/harness_maker/presets.py` clean; full `uv run pytest` shows zero regression vs main (this phase is purely additive — no existing test should change behavior yet because nothing reads the new fields yet).
- **Risk**: low (additive Pydantic + new module).
- **Rollback point**: main HEAD before Phase 1.

### Phase 2 — Migration in answers_from_harness_yaml using io_utils helper
- **Scope IN**:
  - `src/harness_maker/interview.py`: `answers_from_harness_yaml` uses `harness_maker.io_utils.load_harness_yaml()` (CLAUDE.md §2 contract) to load multi-doc YAML with provenance frontmatter. Branches: if `recommended_model` key present OR `schema_version` absent / < 2 → silent rename to `default_model` + log INFO. If `default_model` already present → direct read. Both paths set `schema_version = 2` on the in-memory `InterviewAnswers`.
  - `tests/unit/test_interview_migration_v1_to_v2.py` (NEW; 4 tests):
    1. v1 fixture (with `recommended_model: claude-opus-4-7` + provenance frontmatter) → loads as v2 with `default_model="claude-opus-4-7"`, `agent_models={}`, advisory log emitted.
    2. v1 fixture with NON-default `recommended_model: claude-3-5-sonnet` → preserves user's value as `default_model`.
    3. v2 fixture (clean, no migration needed) → no log emitted, direct read.
    4. Provenance-frontmatter handling: `tests/fixtures/harness_yaml_v1_with_provenance.yaml` (NEW fixture file with multi-doc YAML stream) → loaded correctly, `default_model` from inner doc not provenance.
- **Scope OUT**: interview question additions, render, Codex.
- **Exit criterion**: `uv run pytest tests/unit/test_interview_migration_v1_to_v2.py -v` GREEN (all 4 tests); full `uv run pytest tests/unit/test_interview*.py` GREEN; full `uv run pytest` shows zero regression vs Phase 1 baseline.
- **Risk**: medium (touches the load path used by every CLI invocation; provenance-frontmatter footgun is real per CLAUDE.md).
- **Rollback point**: Phase 1 complete.

### Phase 3 — Renderer wiring + agent .md.j2 templates + foreign-config renames (LOCALIZED snapshot regen)
- **Scope IN**:
  - `src/harness_maker/render.py`: per-agent context resolution via `presets.resolve_agent_spec(name, config)`. Pass `claude_model`, `cursor_model`, `codex_reasoning_effort` into template context for each agent template render.
  - 14 agent `.md.j2` templates: replace hardcoded `model: opus | sonnet` line with `model: {{ claude_model }}` (Claude target) or duplicate per Cursor target if separate render path exists.
  - 2 preset YAML templates: rename `recommended_model: {{ config.recommended_model }}` → `default_model: {{ config.default_model }}`.
  - 5 foreign-config templates (`cursor_rules.mdc.j2`, `copilot_instructions.md.j2`, `agents_md.md.j2`, `aider_conf.yml.j2`, `continue_config.json.j2`): rename `recommended_model` → `default_model`.
  - `tests/unit/test_render_agent_model_resolution.py` (NEW; 4 tests):
    1. agent_models override beats preset map.
    2. preset map beats default_model.
    3. Unknown agent (Tier 3) gets default_model-derived spec — no KeyError.
    4. Side preset + autoloop-coder gets sonnet; Production preset + autoloop-coder gets opus.
  - **Localized snapshot regen** (validator C-1 fix): run targeted regen for agent .md snapshots + preset YAML snapshots only. Use `pytest --snapshot-update tests/unit/test_render*.py tests/unit/test_*preset*.py` (or equivalent syrupy/pytest-snapshot incantation). Do NOT run the full `harness-maker make sandbox --update` here.
- **Scope OUT**: Codex synthesize (Phase 4), `.codex/config.toml` profiles (Phase 4), `/hm:health` (Phase 6), CLI changes (Phase 5).
- **Exit criterion**: Full `uv run pytest` GREEN (snapshot diff for agent .md + preset YAML accepted; no Codex/dashboard snapshots touched in this phase); manual diff inspection of 2 rendered agent .md files (`templates/agents/code-reviewer.md.j2` + `autoloop-coder.md.j2`) confirms `model:` line reflects Production preset defaults.
- **Risk**: medium (renderer is hot path; partial snapshot regen requires care to scope the `--snapshot-update` flag correctly).
- **Rollback point**: Phase 2 complete.

### Phase 4 — Codex per-agent rendering + `.codex/config.toml` profiles (LOCALIZED snapshot regen)
- **Scope IN**:
  - `src/harness_maker/synthesize.py`: `_CODEX_AGENT_META` rendering — when `resolve_agent_spec(name, config).codex.reasoning_effort` is set, emit `model_reasoning_effort = "<value>"` line in agent TOML. Keep `model =` omission (per RESEARCH-codex-plan-validator-model-unavailable).
  - `.codex/config.toml.j2`: add `[profiles.cheap]` block (`model_reasoning_effort = "minimal"`) and `[profiles.deep]` (`model_reasoning_effort = "high"`) — both inherit top-level `model =`.
  - `tests/unit/test_synthesize_codex_reasoning_effort.py` (NEW; 4 tests):
    1. Production preset → code-reviewer.toml has `model_reasoning_effort = "medium"`.
    2. Side preset → autoloop-coder.toml has `model_reasoning_effort = "medium"` (Side downshifts).
    3. `.codex/config.toml` has both `[profiles.cheap]` and `[profiles.deep]` blocks.
    4. User-authored agent (Tier 3 fallback) → renders with derived effort, no crash.
  - **Localized snapshot regen**: Codex TOML snapshots + `.codex/config.toml` snapshot only.
- **Scope OUT**: Claude/Cursor templates (Phase 3), /hm:health (Phase 6), CLI (Phase 5).
- **Exit criterion**: Full `uv run pytest` GREEN (Codex snapshots accepted, all other snapshots stable); rendered `.codex/config.toml` shows both profile blocks; rendered `.codex/agents/code-reviewer.toml` shows `model_reasoning_effort = "medium"`.
- **Risk**: low (additive, no behavior change for users not on Codex target).
- **Rollback point**: Phase 3 complete.

### Phase 5 — Interview gate + CLI deprecation alias (NO snapshot impact for non-template changes)
- **Scope IN**:
  - `src/harness_maker/templates/commands/hm/configure.md.j2`: add single accept-preset gate after preset choice (per ADR-006). Hint points to `docs/HOW-IT-WORKS.md` Agent Models section.
  - `src/harness_maker/cli.py`: add `--recommended-model` alias to `--default-model` with `DeprecationWarning` per ADR-012.
  - `tests/unit/test_interview_accept_preset_gate.py` (NEW): gate question presented; Y → `agent_models={}`; N → hint emitted.
  - `tests/unit/test_cli_deprecation_recommended_model.py` (NEW): `--recommended-model claude-opus-4-7` works + warning text matches exactly.
  - Snapshot regen (if `configure.md.j2` rendered snapshot exists): localized to configure.md snapshot only.
- **Scope OUT**: render, /hm:health.
- **Exit criterion**: Full `uv run pytest` GREEN; deprecation warning observable in CLI test output; manual smoke: `uv run harness-maker make . --recommended-model claude-opus-4-7` prints deprecation warning AND succeeds.
- **Risk**: low (single template + single CLI flag).
- **Rollback point**: Phase 4 complete.

### Phase 6 — /hm:health `model_routing_actionable` sub-check + multi-target cross-product test (LOCALIZED snapshot regen)
- **Scope IN**:
  - `src/harness_maker/readiness.py`: new `_dim_model_routing` function with 3 advisory sub-checks per ADR-010. Wire into Layer 1 dimension list.
  - `tests/unit/test_readiness_model_routing.py` (NEW; 5 tests):
    1. Claude target alone + agent_models populated → sub-check (a) fires.
    2. Cursor target alone + renderer emits concrete ID (no alias) → sub-check (b) does NOT fire (expected non-fire path).
    3. Cursor target alone + manually-injected alias value → sub-check (b) fires.
    4. Codex target alone + agents missing reasoning_effort → sub-check (c) fires with correct count.
    5. **Multi-target cross-product** (validator W-6 fix): all 3 targets enabled → sub-checks (a) and (c) both fire independently in dashboard output (assert both appear, neither suppresses the other).
  - `tests/integration/test_health_dashboard_roundtrip.py`: extend to assert `model_routing_actionable` line appears in rendered dashboard.md with the expected score contribution.
  - **Localized snapshot regen**: dashboard snapshot only.
- **Scope OUT**: schema changes (Phase 1), render path (Phase 3), CLI (Phase 5).
- **Exit criterion**: Full `uv run pytest` GREEN; dashboard.md on THIS repo (run `uv run python -m harness_maker.cli health` after Phase 6 lands) shows the new sub-check with non-zero score.
- **Risk**: low (additive structural check + dashboard rendering).
- **Rollback point**: Phase 5 complete.

### Phase 7 — Snapshot regen guard (ADR-013) + final sandbox sweep + dogfood
- **Scope IN**:
  - `src/harness_maker/cli.py`: add `--update` pre-flight guard per ADR-013. Walk `Path.cwd().resolve()` ancestors; if any name is `.worktrees`, exit 1 with actionable message.
  - `tests/unit/test_cli_update_worktree_guard.py` (NEW; 2 tests):
    1. cwd inside `tmp_path / ".worktrees" / "foo"` → CLI exits 1 with expected message containing "cd <repo-root>".
    2. cwd at `tmp_path` (no `.worktrees/` ancestor) → CLI proceeds normally.
  - **Final sandbox sweep**: run `uv run harness-maker make tests/e2e/sandbox{,-plugin-test} --update` **from main repo root** (CLAUDE.md guidance + ADR-013 will now enforce this in code). Inspect rendered files in sandbox for agent .md / `.codex/agents/*.toml` / `.codex/config.toml` — confirm preset defaults applied as expected.
  - Full `uv run pytest` + `uv run ruff check` + `uv run mypy --strict` all GREEN/clean.
- **Scope OUT**: feature code (locked from Phase 6).
- **Exit criterion**: Full pytest suite GREEN (~2000 tests); ruff clean; mypy --strict clean; sandbox-rendered files inspection passes; cwd guard test proves `.worktrees/` cwd is rejected.
- **Risk**: medium (sandbox sweep is bulk; ADR-013 guard provides safety net).
- **Rollback point**: Phase 6 complete.

### Phase 8 — Version bump + CHANGELOG + docs (NO code changes)
- **Scope IN**:
  - 5-file version sync per CLAUDE.md §버전업 정책 (0.14.3 → 0.15.0): `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`.
  - `CHANGELOG.md`: 0.15.0 entry summarizing 13 ADRs with bullet list (per-agent model routing + preset-aware defaults + Codex reasoning_effort + #43869 health gate + cwd guard + CLI deprecation).
  - `docs/HOW-IT-WORKS.md`: NEW section "Agent Models" with worked example showing both Production and Side preset defaults for 3 representative agents, plus a custom user-authored agent override. **This is the docs target referenced by ADR-006 and ADR-010 — must be complete and discoverable.**
  - `.claude/memory/wiki.md`: append `[wiki:model-routing-multi-ide]` entry (one-line summary: per-agent + preset defaults + render-per-IDE + #43869 gate).
  - Update README badges only if model-related (likely none).
- **Scope OUT**: code (locked from Phase 7).
- **Exit criterion**: `git diff --stat` shows only docs/version files; all 5 version files report 0.15.0; CHANGELOG.md has 0.15.0 section; `docs/HOW-IT-WORKS.md` has new "Agent Models" section with worked example.
- **Risk**: low (mechanical).
- **Rollback point**: Phase 7 complete.

## 🧪 Testing Strategy

**Unit (~30 new tests across phases)**:
- Phase 1: `test_models_agent_models.py` (strict mode + enum validation), `test_presets.py` (3-tier chain + completeness vs templates glob), `test_no_raw_cursor_model_ids_in_templates.py` (lint).
- Phase 2: `test_interview_migration_v1_to_v2.py` (4 tests including provenance-frontmatter fixture).
- Phase 3: `test_render_agent_model_resolution.py` (4 tests including Tier-3 user-authored agent fallback — validator C-2 fix).
- Phase 4: `test_synthesize_codex_reasoning_effort.py` (4 tests).
- Phase 5: `test_interview_accept_preset_gate.py`, `test_cli_deprecation_recommended_model.py`.
- Phase 6: `test_readiness_model_routing.py` (5 tests including multi-target cross-product — validator W-6 fix).
- Phase 7: `test_cli_update_worktree_guard.py` (2 tests — ADR-013 enforcement).

**Integration**:
- `tests/integration/test_health_dashboard_roundtrip.py` (extended): asserts `model_routing_actionable` line in rendered dashboard.md.
- `tests/integration/test_render_end_to_end_agent_models.py` (NEW, Phase 3): full render pipeline with explicit `agent_models` override → output agent .md has the right `model:` line; user-authored custom agent renders with default_model-derived spec.

**Manual smoke** (Phase 7):
- Run `uv run harness-maker make . --update` from repo root (cwd guard active).
- Inspect 2 agent .md files + 1 .codex/agents/*.toml + .codex/config.toml — verify preset defaults applied.
- Run `uv run python -m harness_maker.cli health` on this repo; verify dashboard shows new sub-check.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Snapshot regen footgun (`[fail:snapshot-regen-inside-worktree]` count:4) | high → **eliminated** | medium | **ADR-013 enforced guard in Phase 7** turns documentation into prevention |
| Phase 3-6 regressions un-attributable (validator C-1) | high → **eliminated** | medium | **Localized snapshot regen per phase** (R4 decision) — every phase exits with full pytest GREEN |
| User-authored agent crashes renderer (validator C-2) | high → **eliminated** | high | **Tier-3 fallback in resolve_agent_spec** (ADR-005 amendment) — no KeyError, just default-model-derived spec |
| Migration silently loses user's `recommended_model` value (validator C-3) | high → **eliminated** | high | **Phase 2 uses `io_utils.load_harness_yaml()`** + multi-doc YAML fixture test |
| Cursor concrete-ID scatter (validator W-4) | medium → **eliminated** | medium | **CURSOR_MODEL_IDS canonical constant** + lint test (ADR-003 amended) |
| Anthropic #43869 lands during this PR | low | low | Rendered frontmatter is forward-compatible; ADR-010 sub-check (a) becomes ✅ silently |
| User's harness.yaml has a custom `recommended_model` non-default value | medium | low | ADR-004 silent fallback preserves value as `default_model`; preset defaults still apply per-agent (Tier 2) for shipped agents |
| Cursor 3.3+ user wants alias support | low | low | Documented in ADR-003; future PR can add `cursor_use_aliases: bool` opt-in |
| Snapshot diff explosion (~40 files) hides a real bug | medium → low | medium | **Phase-localized regen** + manual diff inspection on 3 representative files before accepting bulk regen in Phase 7 |
| CLI deprecation breaks automation (validator W-7) | medium → low | medium | **ADR-012 2-release window** + DeprecationWarning + actionable error in 0.17.0 |
| `presets.py` map omits a future shipped agent | medium | low | `test_presets.py` completeness check vs `templates/agents/*.md.j2` glob; CI fails on add-agent-without-preset-entry |
| Re-validator finds additional gaps | low | medium | If second validator pass still MAJOR_REVISION, ask user to proceed with accepted-risk or abort (per /hm:plan Step 4 protocol) |

## ✅ Success Criteria

1. `HarnessConfig.recommended_model` removed; `default_model` + `agent_models` present, Pydantic-typed.
2. `presets.py` ships `PRESET_AGENT_MODELS` for {Production, Side} × all 14 shipped agents × 3 targets where applicable; `CURSOR_MODEL_IDS` canonical table; `resolve_agent_spec()` 3-tier helper.
3. Renderer pulls per-agent values via the 3-tier chain — explicit override → preset map → default_model-derived spec (no KeyError on user-authored agents).
4. Codex `.codex/config.toml` includes `[profiles.cheap]` + `[profiles.deep]` per preset.
5. Codex `.codex/agents/*.toml` includes `model_reasoning_effort` line per preset default.
6. Foreign-config templates (5 files) show `default_model` only (no full map).
7. Migration of old `recommended_model` works silently via `io_utils.load_harness_yaml()` with INFO log; multi-doc YAML fixture test passes.
8. `/hm:health` Layer 1 shows new `model_routing_actionable` sub-check; multi-target cross-product test passes.
9. `schema_version` bumped 1 → 2.
10. CLI: `--recommended-model` deprecated alias works with warning; `--update` rejects cwd inside `.worktrees/` with actionable message.
11. Full `uv run pytest` GREEN at end of every phase (not just at end); ruff clean; mypy --strict clean.
12. Version sync (5 files) at 0.15.0.
13. `docs/HOW-IT-WORKS.md` has "Agent Models" section with worked example (referenced by ADR-006/010 hints).

## 🔍 Plan Validation

**Round 1 — plan-validator (pre-revision)**: MAJOR_REVISION

Critiques resolved in Interview Round 4:

| # | Severity | Title | Resolution |
|---|----------|-------|------------|
| C-1 | critical | Phase 3 leaves snapshot tests red | Localize regen per phase (R4 Q1); Phase 3-7 scope updated; pytest GREEN per phase |
| C-2 | critical | Preset map missing fallback for user-authored agents | Tier-3 `_spec_from_default_model` fallback (R4 Q4); ADR-005 amended; `test_render_user_authored_agent_uses_default_model` in Phase 3 |
| C-3 | critical | Phase 2 migration doesn't address provenance frontmatter | Use `io_utils.load_harness_yaml()` (R4 Q4); Phase 2 scope updated; multi-doc YAML fixture test added |
| W-4 | warning | Cursor concrete-ID canonical home undefined | `CURSOR_MODEL_IDS` constant in `presets.py` (R4 Q4); ADR-003 amended; lint test in Phase 1 |
| W-5 | warning | ADR-007 piggyback claims unenforceable behavior | Rewritten as no-op observation (R4 Q4) |
| W-6 | warning | Phase 6 misses multi-target cross-product test | Added test case 5 in `test_readiness_model_routing.py` (R4 Q4) |
| W-7 | warning | CLI deprecation timing inserted without ADR | Promoted to ADR-012 with 2-release window → 0.17.0 (R4 Q2) |
| W-8 | warning | Snapshot regen footgun documented not enforced | Promoted to ADR-013 with CLI guard in Phase 7 (R4 Q3) |
| S-9 | suggestion | ADR-006 hint points to CLAUDE.md but docs are in HOW-IT-WORKS.md | Repointed hint; Phase 8 documents "Agent Models" section (R4 Q4) |

**Round 2 — plan-validator (post-R4 revision)**: NEEDS_REVISION (down from MAJOR_REVISION). All 9 prior critiques substantively applied. 2 NEW warnings introduced by the revision itself:

| # | Severity | Title | Resolution |
|---|----------|-------|---|
| W-10 | warning | `cursor:` field semantics under-specified across ADR-003/005/010 + diagram | R5 Q1: chose option C — normalize inside `resolve_agent_spec`; users write aliases; sub-check (b) inspects pre-resolution raw value. ADR-003/005/010 amended; data-flow diagram updated. |
| W-11 | warning | Phase 1 lint regex `claude-[0-9]` has no scope/allowlist | R5 Q2: chose option A — narrow to assignment-only patterns. Phase 1 scope now lists exact regex patterns per file type. |

**Final outcome**: MAJOR_REVISION_RESOLVED → NEEDS_REVISION_RESOLVED. No critical-tier findings remain. Per /hm:plan procedure no third validator pass (re-run validator ONCE limit observed). PLAN ready for `/hm:execute`.
