---
type: plan
task_slug: agent-model-version-agnostic
status: planning
created: 2026-05-31
tags: [harness-maker, plan, python, agent-rendering, model-config, multi-ide]
interview_rounds: 3
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Render .claude/agents model: as alias not concrete ID; floor->opus; resolve concrete at foreign-config boundary; guard"
---

# PLAN — Agent model field must be version-agnostic (alias, not pinned ID)

## 🎯 Executive Summary

**TL;DR**: `.claude/agents/*.md` frontmatter renders `model: claude-4-7-opus` (a stale
**Cursor concrete ID**) instead of the Claude alias `opus`. Claude Code now *respects*
the agent `model:` field (upstream #43869 fixed), so in a `claude-opus-4-8[1m]` session it
tries to launch `claude-4-7-opus[1m]` → not accessible → subagent fails with 0 tool uses.
Fix: agent frontmatter renders the **alias** (`{{ claude_model }}`); floor `default_model`
defaults to `opus`; surfaces that genuinely need a concrete ID (aider/Continue foreign
configs) resolve the alias → concrete at their render boundary; a guard test asserts no
concrete Claude ID ever reaches `.claude/agents/*.md`.

**What/Why**: The defect is a Jinja precedence inversion. 14 agent dispatcher templates render
`{% if cursor_model is defined %}{{ cursor_model }}{% elif claude_model %}{{ claude_model }}…`.
`synthesize.py` always passes `cursor_model` (the CURSOR_MODEL_IDS-normalized **concrete**
ID), so the concrete ID always wins — even though agents are single-source in `.claude/`
and Claude Code reads them. Harmless while #43869 made the field decorative; now load-bearing
and version-fragile. Aliases (`opus`/`sonnet`/`haiku`) are resolved to the latest tier model
by Claude Code at launch → version-agnostic + per-agent tiering preserved.

**Why Codex "could not run" (answer to the user's question)**: two compounding causes —
(a) this repo's `harness.yaml` has `codex_second_opinion.enabled: false`, so it was never
going to fire; and (b) the Codex second-opinion step lives *inside* the `plan-validator`
agent body, so a validator launch failure deterministically skips its Codex step. The prior
`PLAN-codex-plan-validator-model-unavailable` (ADR-001) already fixed the **Codex-TOML** side
(drop `model=`, inherit account default); the **Claude** side then regressed. No Codex code
change is needed here — once the validator launches, the Codex step recovers transitively.

**Key Decisions**:
- **ADR-001** — `.claude/agents/*.md` `model:` renders the Claude alias, never a concrete ID.
- **ADR-002** — `default_model` floor default → alias `opus`.
- **ADR-003** — Frontmatter-only fix; no `Task()`-call model override added to shipped stage prompts.
- **ADR-004** — Alias vs concrete is a surface boundary: agent-launch surfaces use aliases; Anthropic-API consumers (Python SDK + foreign-tool configs) get concrete IDs.
- **ADR-005** — Cursor single-source carries the alias; cross-IDE acceptance verified via non-blocking manual checklist; per-target divergence deferred.
- **ADR-006** — Foreign-tool configs (aider/Continue) resolve alias→concrete at the `foreign_config` render boundary; the canonical alias→concrete map is the single home for concrete pins and is refreshed to the latest IDs.

**Estimated impact**: ~3 source files (14 agent templates → shared partial, `models.py`,
`synthesize.py`), `foreign_config.py` boundary resolver + `presets.CURSOR_MODEL_IDS` refresh,
2 foreign-config templates, `harness.mdc.j2` prose, `plan.md.j2` wording, 1 new guard test,
e2e snapshot regen, 5-file version bump + CHANGELOG. No schema change.

## 📚 Prior Work

- [[PLAN-codex-plan-validator-model-unavailable]] (2026-05-11, complete) — fixed the **Codex** twin (ADR-001: drop per-agent `model=` from `.codex/agents/*.toml`). The Claude side is the mirror that regressed.
- [[PLAN-model-routing-multi-ide]] / `[wiki:model-routing-multi-ide] 2026-05-18` — shipped per-agent pinning + presets. Wiki note records original intent verbatim: *"Claude `model: {{ claude_model }}` (decorative per #43869 until upstream fix), Cursor concrete IDs via CURSOR_MODEL_IDS normalization."* This PLAN restores that intent now the field is load-bearing.
- `[wiki:architecture] codex-second-llm-integration 2026-05-24` — Codex second-opinion is rendered *inside* reviewer/validator bodies (explains the transitive Codex failure).
- Memory `feedback_subagent_model_override` — reviewer/validator subagents fail to launch in 1M-Opus sessions; workaround `model:"opus"` on the Agent call. This PLAN makes the *frontmatter* the durable fix (ADR-003 declines to also bake a Task override).

## 🚫 Non-Goals

- **Refreshing Anthropic Python-SDK model constants** (`_LLM_MAP_MODEL` in `foreign_config.py`, plus `llm_judge.py` / `readiness.py` / `memory_retrieve.py` `messages.create(model=)`). These require concrete IDs and are verified NOT to receive `config.default_model`; their staleness is a separate task (ADR-004).
- Retiring the `CURSOR_MODEL_IDS` / `cursor_model` machinery (scoped out per Round 1 Q4; ADR-006 *reuses and refreshes* it rather than retiring it).
- Building a Codex-decoupling code path (Round 2 Q6 = explanation + transitive fix suffices).
- Per-target agent files / `.cursor/agents/` divergence (deferred to a follow-up PLAN iff manual verification shows Cursor rejects the alias — ADR-005).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Model-string strategy | Contract | What does `.claude/agents/*.md` `model:` render? | **Claude alias** | Version-agnostic + preserves tiering; restores original intent | ADR-001 |
| 2 | Floor default value | Contract | `default_model` floor default? | **alias `opus`** | `_spec_from_default_model` reads family substring → alias works | ADR-002 |
| 3 | Dual safety layer | Risk | Pin `model` on the `Task()` call too? | **frontmatter only** | Single source of truth | ADR-003 |
| 4 | Scope | Scope | Breadth? | **Claude side + guard + floor + wording**; Cursor separate verify | Bounds the change | ADR-004, ADR-005 |
| 5 | Cursor risk | Risk | Unverified Cursor alias acceptance? | **Ship alias + non-blocking manual-verify + contingency** | Don't block Claude fix | ADR-005 |
| 6 | Codex handling | Scope | Codex-side change? | **Explanation + transitive recovery suffices** | No code change | (TD prose) |
| 7 | Foreign-config surface (validator-found) | Contract | aider/Continue need concrete IDs; `opus` breaks them | **Resolve alias→concrete at foreign_config boundary; refresh canonical map** | Concrete pin lives in one place | ADR-006 |
| 8 | 14-way duplication (validator-found) | Method | The identical line-6 in 14 templates | **Extract shared partial** | Kills blast-radius source | ADR-001 (Phase 1) |

## 📐 Architecture Decision Records

### ADR-001: `.claude/agents/*.md` `model:` renders the Claude alias, never a concrete ID
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** Claude Code now respects agent `model:` frontmatter (#43869 fixed). The single-source `.claude/agents/*.md` carried the CURSOR_MODEL_IDS-normalized concrete ID because the template preferred `cursor_model` over `claude_model`. A pinned older ID fails to launch in a newer-model session.
**Decision:** All agent frontmatter renders the Claude alias (`{{ claude_model }}` = `opus`/`sonnet`/`haiku`, fallback `sonnet`) via a shared partial; the `cursor_model` branch is removed from the agent `model:` line.
**Consequences:**
- ✅ Version-agnostic — Claude Code resolves the alias to the current tier model with zero re-render.
- ✅ Per-agent tiering preserved (reasoning → `opus`, reviewers → `sonnet`).
- ✅ Single shared partial eliminates the 14-way duplication that gave the bug its blast radius (Interview #8).
- ⚠️ Cursor reads the same alias (ADR-005 — acceptance to be verified).
**Rejected alternatives:**
- *Omit the `model:` line (inherit session)* — loses per-agent tiering.
- *Track the latest concrete ID* — still pinned; re-stales each release; violates the user's principle.
**Source:** Interview #1, #8

### ADR-002: `default_model` floor default → alias `opus`
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** `HarnessConfig.default_model` defaulted to concrete `claude-opus-4-7` — already stale and the same pinning anti-pattern at the floor.
**Decision:** Default `default_model` to `opus`. `_spec_from_default_model` derives the alias from the family substring, so an alias floor flows into Tier-3 agent specs. **Consumers that need a concrete ID resolve it at their own boundary (ADR-006), not at the floor.**
**Consequences:**
- ✅ Floor fallback is version-agnostic; user-authored custom agents inherit `opus`.
- ⚠️ Every `default_model` consumer must be classified alias-tolerant vs concrete-required (Phase 2 enumeration).
**Rejected alternatives:** *Bump to `claude-opus-4-8`* — re-stales next release.
**Source:** Interview #2

### ADR-003: Frontmatter-only fix — no `Task()`-call model override in shipped stage prompts
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** The launch could be hardened by also passing `model:"opus"` on each `Task()` dispatch (memory `feedback_subagent_model_override`).
**Decision:** Fix the agent frontmatter only. Do not add a `model` argument to shipped `Task()` dispatches.
**Consequences:**
- ✅ Single source of truth — no drift between two model declarations.
- ⚠️ A future re-pin has no runtime second net; mitigated by the Phase 3 guard test (cheaper, earlier than runtime redundancy).
**Rejected alternatives:** *Dual declaration* — two sources of truth that can disagree.
**Note:** This session's own plan-validator invocation passed `model:"opus"` as a one-off because this repo's on-disk agent file predates the fix — a session workaround, not a shipped change.
**Source:** Interview #3

### ADR-004: Alias surfaces vs Anthropic-API surfaces — a hard boundary the guard respects
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** Not every concrete model string is a bug. **Anthropic-API consumers reject bare aliases.** Two such classes exist: (1) Python **SDK** call sites (`foreign_config._LLM_MAP_MODEL`, `llm_judge.py`, `readiness.py`, `memory_retrieve.py`); (2) **foreign-tool configs** rendered for aider (`aider_conf.yml.j2:13`) and Continue (`continue_config.json.j2:8`), which call the Anthropic API directly.
**Decision:** Two surfaces, two rules. **Agent-launch surfaces** (agent frontmatter `model:`, `default_model` floor) use **aliases**. **Anthropic-API surfaces** get **concrete IDs** — the Python-SDK constants stay as-is (Non-Goal); the foreign-config render path resolves alias→concrete (ADR-006). The Phase 3 guard scans only `.claude/agents/*.md` output + `default_model`; it does NOT flag SDK constants, and it asserts the foreign-config render *is* concrete.
**Consequences:**
- ✅ The fix can't break live API calls by aliasing them.
- ✅ The guard has a precise, defensible scope.
- ⚠️ Python-SDK staleness (`claude-opus-4-7`) survives this task (tracked Non-Goal).
**Rejected alternatives:** *Replace every concrete ID in the tree* — breaks `llm_map` + aider/Continue (no alias resolution).
**Source:** Interview #4, #7 (validator-found gap)

### ADR-005: Cursor single-source carries the alias; acceptance verified, not assumed; divergence deferred
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** Agents are single-source in `.claude/agents/` (no `.cursor/agents/`). With the alias now in the shared file, Cursor 2.4+ must also accept the alias — unverified.
**Decision:** Ship the alias now. Add a non-blocking manual-verification entry (with a named owner/date) to `tests/cursor-compat/MANUAL_CHECKLIST.md`. Record the contingency: if Cursor rejects the alias, open a follow-up PLAN for per-target divergence.
**Consequences:**
- ✅ The Claude regression is fixed immediately, not gated on a Cursor manual test.
- ⚠️ If Cursor rejects aliases, Cursor users temporarily lose per-agent routing until a follow-up lands. Likelihood judged low (Cursor reads `.claude/agents/` in Claude-native format, which uses aliases) — but unverified, hence the dated checklist owner.
**Rejected alternatives:** *Block on Cursor verification* (delays urgent fix); *build divergence now* (out of scope, premature).
**Source:** Interview #4, #5

### ADR-006: Foreign-tool configs resolve alias→concrete at the render boundary; canonical map refreshed
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** `config.default_model` flows through `foreign_config.py:452` into `aider_conf.yml.j2` and `continue_config.json.j2`. After ADR-002 the floor is the alias `opus`; aider/Continue require concrete IDs, so a bare `opus` would render an unusable config.
**Decision:** Resolve alias→concrete at the `foreign_config` render boundary (mirroring `presets._normalize_cursor_alias`). The canonical alias→concrete map (`presets.CURSOR_MODEL_IDS`, the single legitimate home for concrete pins) is refreshed to the latest IDs (`opus`→`claude-opus-4-8`, `sonnet`→`claude-sonnet-4-6`, `haiku`→`claude-haiku-4-5`; confirm exact haiku ID at execute). Every surface needing a concrete ID (foreign configs, and historically Cursor) routes through this one map.
**Consequences:**
- ✅ aider/Continue render a valid concrete ID; the alias contract holds for agent-launch surfaces.
- ✅ Exactly one place pins concrete IDs — a new Claude release is a one-line map edit.
- ⚠️ The map's name (`CURSOR_MODEL_IDS`) now under-describes its role; rename deferred (out of scope) — documented inline.
**Rejected alternatives:**
- *Accept-risk Non-Goal (render alias, user overrides)* — ships a broken out-of-box config.
- *Drop ADR-002 (keep floor concrete)* — leaves the floor pinned; contradicts the user's principle.
**Source:** Interview #7

## 🏗️ Technical Design

### Current State
- 14 dispatcher templates `templates/agents/*.md.j2` line 6 prefer `{{ cursor_model }}` (concrete) over `{{ claude_model }}` (alias). `_body.md.j2` variants do not carry the line.
- `resolve_agent_spec(...).claude` is already an alias; only `.cursor` is normalized. So `claude_model` is the correct value to render.
- `HarnessConfig.default_model` default = `"claude-opus-4-7"` (2 Field defaults in `models.py`; 4 function defaults in `synthesize.py`).
- `foreign_config.py:452` feeds `default_model` into the foreign-config render context → `aider_conf.yml.j2:13`, `continue_config.json.j2:8`.
- `foreign_config.py` SDK call uses the separate `_LLM_MAP_MODEL` (`:41`/`:332`) — confirmed it does NOT receive `default_model` (Python-SDK side safe).
- `presets.CURSOR_MODEL_IDS` = the alias→concrete map; `opus`→`claude-4-7-opus` (stale).
- `templates/cursor/rules/harness.mdc.j2:104` prose: "Default recommendation: `claude-opus-4-7`".
- `tests/unit/test_no_raw_cursor_model_ids_in_templates.py` matches only **literal** `model: claude-\d+-\d+-\w+` in source — **blind** to `{{ cursor_model }}` variable substitution, which is why it stayed green throughout the bug.

### Affected Components
- 14 agent templates → shared `_partials/model_frontmatter_line.md.j2` (ADR-001/#8).
- `models.py`, `synthesize.py`, `harness.mdc.j2` prose (ADR-002).
- `foreign_config.py` boundary resolver + `presets.CURSOR_MODEL_IDS` refresh + `aider_conf.yml.j2`/`continue_config.json.j2` (ADR-006).
- New `tests/unit/test_agent_model_alias_rendering.py` (ADR-001/002/004/006).
- `templates/stages/plan.md.j2` honesty-note wording (Q4).
- e2e snapshot fixtures + this repo's dogfood `.claude/`.

### Data Flow
`resolve_agent_spec(name, config).claude` (alias) → `synthesize` context `claude_model` → shared
partial `model: {{ claude_model }}` → `.claude/agents/<name>.md` → Claude Code launch (alias resolved).
Parallel: `config.default_model` (alias) → foreign_config boundary resolver → concrete ID → aider/Continue.

### Codex coupling (Q6 — prose, no ADR)
The Codex second-opinion is rendered *inside* the `plan-validator` body and runs only as a step that
agent performs; a validator **launch** failure deterministically skips it. With ADR-001 the validator
launches and, when `codex_second_opinion.enabled: true`, its Codex step runs. This repo has it disabled,
so the prior "Codex could not run" was doubly expected. No decoupling code is added.

### Runtime honesty-note wording (Q4)
`plan.md.j2` Step 4 + codex relay note gain one instruction: when surfacing a subagent/validator launch
failure, reference the **tier** (`opus`/`sonnet`), never a pinned ID like `claude-4-7-opus[1m]`.

## 📝 Implementation Plan

### Phase 1 — Shared partial renders the alias
- `depends_on`: []
- `parallel_group`: p-source
- `merge_hazards`: none (only `templates/agents/*.md.j2` + new partial)
- **Scope (in)**: create `templates/agents/_partials/model_frontmatter_line.md.j2` =
  `model: {% if claude_model is defined and claude_model is not none %}{{ claude_model }}{% else %}sonnet{% endif %}`
  (drop the `cursor_model` branch); replace line 6 of all 14 dispatcher templates with an `{% include %}` of the partial (mind whitespace control — no trailing newline drift).
- **Exit criterion**: `grep -L "cursor_model" templates/agents/*.md.j2` lists all 14; render one reasoning + one reviewer agent → `model: opus` / `model: sonnet`.
- **Risk**: low | **Rollback**: git revert to pre-Phase-1.

### Phase 2 — Floor `default_model` → `opus` + enumerate every consumer
- `depends_on`: []
- `parallel_group`: p-source
- `merge_hazards`: none (disjoint from Phase 1/4; `presets.py` shared with Phase 2b below — keep serial within this phase)
- **Scope (in)**: `models.py` 2 Field defaults + `synthesize.py` 4 function defaults `"claude-opus-4-7"` → `"opus"`; `harness.mdc.j2:104` prose → `opus`. **Enumerate every consumer of `config.default_model` (Python AND Jinja) and classify alias-tolerant vs concrete-required** — the deliverable is a complete classification, not an empty grep.
- **Exit criterion**: `uv run python -c "from harness_maker.models import HarnessConfig; print(HarnessConfig().default_model)"` → `opus`; written classification lists all consumers with their disposition (agent-spec=alias-OK; foreign-config=concrete via Phase 2b; SDK constants=not a consumer).
- **Risk**: low | **Rollback**: Phase 1 state.

### Phase 2b — Foreign-config boundary resolver + canonical map refresh (ADR-006)
- `depends_on`: [2]
- `parallel_group`: serial-source (touches `presets.py` + `foreign_config.py`)
- `merge_hazards`: `presets.CURSOR_MODEL_IDS` (shared concrete-pin home)
- **Scope (in)**: refresh `CURSOR_MODEL_IDS` to latest concrete IDs; add an alias→concrete resolution at the `foreign_config` render boundary so `aider_conf.yml.j2`/`continue_config.json.j2` receive a concrete ID even when `default_model` is an alias; inline-comment the map's broadened role.
- **Exit criterion**: render aider + Continue configs under `default_model: opus` → `model`/`default_model` field is a concrete ID (e.g. `claude-opus-4-8`), not `opus`; existing `test_no_raw_cursor_model_ids_in_templates` still green (map lives in source, not templates).
- **Risk**: medium (touches the shared map) | **Rollback**: Phase 2 state.

### Phase 3 — Guard test (rendered output, both surfaces)
- `depends_on`: [1, 2, 2b]
- `parallel_group`: serial-guard
- `merge_hazards`: none (new test file)
- **Scope (in)**: `tests/unit/test_agent_model_alias_rendering.py`. (a) Render all agents under `targets:[claude-code,cursor,codex]` + Production; assert each `.claude/agents/*.md` `model:` ∈ {`opus`,`sonnet`,`haiku`} and never matches `claude-(opus|sonnet|haiku|\d)`. (b) Assert `HarnessConfig().default_model == "opus"`. (c) Assert aider/Continue configs render a concrete ID (ADR-006 inverse). Comment that SDK source files are out of scope (ADR-004).
- **Exit criterion**: `uv run pytest tests/unit/test_agent_model_alias_rendering.py -q` green; manually reverting Phase 1 makes (a) fail (guard proven to bite).
- **Risk**: low | **Rollback**: Phase 2b state.

### Phase 4 — Runtime honesty-note wording
- `depends_on`: []
- `parallel_group`: p-source
- `merge_hazards`: none (`plan.md.j2` only)
- **Scope (in)**: `plan.md.j2` Step 4 + codex relay note — add the tier-name instruction; grep sibling stages for validator/reviewer dispatch-failure messaging and apply only where present.
- **Exit criterion**: `grep -n "tier" templates/stages/plan.md.j2` shows the instruction; no pinned `claude-\d` in the failure-messaging guidance.
- **Risk**: low | **Rollback**: Phase 2 state.

### Phase 5 — Regen, dogfood re-render, version bump
- `depends_on`: [1, 2, 2b, 4]
- `parallel_group`: serial-release
- `merge_hazards`: e2e snapshot fixtures, 5 version files, CHANGELOG.md
- **Scope (in)**: `uv run python tests/snapshot/regenerate.py` **from repo root** (ADR-013 cwd guard forbids worktree-internal regen); re-render this repo's `.claude/` (resolves 0.27.1→current drift) **as the last sub-step**; bump 5 version files; CHANGELOG entry (note ADR-006 map refresh as a behavior change). The dogfood re-render only affects FUTURE sessions — the current session already resolved its agent files, so no mid-session hazard.
- **Exit criterion**: `uv run pytest -q` green (background per project policy); `git diff` shows `.claude/agents/*.md` now `model: opus`/`sonnet` AND aider/Continue configs concrete; 5 version strings identical.
- **Risk**: medium (snapshot churn; repo-root execution) | **Rollback**: Phase 4 state.

### Phase 6 — Cursor manual-verification entry (non-blocking)
- `depends_on`: [5]
- `parallel_group`: serial-release
- `merge_hazards`: none (doc append)
- **Scope (in)**: append to `tests/cursor-compat/MANUAL_CHECKLIST.md`: "Cursor 2.4+ launches a subagent from `.claude/agents/<name>.md` with `model: opus` (alias) — pass/fail" + a named owner and target date + the ADR-005 contingency.
- **Exit criterion**: checklist entry present with owner/date; PLAN risk register references it.
- **Risk**: low | **Rollback**: n/a (doc only).

## 🧪 Testing Strategy
- **Unit**: Phase 3 guard (rendered agent alias + default_model + foreign-config concrete). NOTE: the existing `test_no_raw_cursor_model_ids_in_templates` is **blind to `{{ }}` substitution** (it only catches hand-typed literals) — Phase 3's rendered-output assertion is the **sole** guard for the alias contract.
- **Snapshot**: e2e fixtures regen (Phase 5) — diff should show alias changes + concrete foreign-config + version/provenance only.
- **Integration**: full `uv run pytest` (background); optional `INTEGRATION=1` boundary tests advisory pre-release.
- **Manual**: Phase 6 Cursor checklist (non-blocking, human-run, dated owner).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cursor 2.4+ rejects alias `opus` | Low (unverified) | Cursor users lose per-agent routing | ADR-005 dated manual checklist (Phase 6); follow-up PLAN if it fails |
| Foreign-config alias bleed missed (the validator-found gap) | — (now addressed) | Broken aider/Continue config | ADR-006 boundary resolver + Phase 3 inverse assertion |
| `config.default_model` secretly reaches an SDK `messages.create` | Low | Live API 400 | Phase 2 full consumer enumeration (not just one grep) |
| Snapshot regen inside a worktree (ADR-013) | Medium | Blocked/incorrect fixtures | Phase 5 mandates repo-root execution |
| Future edit re-pins frontmatter | Medium | Regression recurs | Phase 3 guard bites at CI (chosen over ADR-003 runtime redundancy) |
| 14-way duplication reintroduces drift | — (now addressed) | Blast radius | ADR-001/#8 shared partial |

## ✅ Success Criteria
- [ ] All 14 `.claude/agents/*.md` render `model:` as an alias; none carry a concrete Claude ID.
- [ ] `HarnessConfig().default_model == "opus"`; every consumer classified.
- [ ] aider/Continue configs render a concrete ID under an alias floor (ADR-006).
- [ ] Guard test present and proven to bite on regression.
- [ ] `plan.md.j2` failure-messaging references tier names, not pinned IDs.
- [ ] e2e snapshots regenerated; full pytest green; 5 version files synced + CHANGELOG entry.
- [ ] Cursor manual-verification checklist entry added with owner/date (non-blocking).
- [ ] Python-SDK call sites untouched (ADR-004 boundary held).

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → **RESOLVED**.

| Severity | Area | Critique | Resolution |
|---|---|---|---|
| critical | SDK-boundary | `default_model` bleeds the alias into aider/Continue foreign configs (concrete-required) — surface not enumerated | Interview #7 → **ADR-006** + **Phase 2b** boundary resolver + Phase 3 inverse assertion + ADR-004 expanded to name foreign-config surfaces |
| warning | Phase 2 exit too narrow | One grep can't surface Jinja render paths | Phase 2 reframed: full consumer enumeration + classification is the deliverable |
| warning | guard scope | old source-lint is blind to `{{ }}` substitution | Testing Strategy states Phase 3 is the sole alias guard |
| warning | Phase 5 exit | didn't assert foreign-config outcome | Phase 5 exit now asserts concrete foreign-config render |
| suggestion | shared partial | 14-way duplication left optional | Interview #8 → promoted to ADR-001 Phase 1 (shared partial) |
| suggestion | dogfood circularity | re-rendering live `.claude/` mid-workflow | Phase 5 notes re-render affects future sessions only; sequenced as last sub-step |
| suggestion | Cursor likelihood asserted | unverified assumption could linger | Phase 6 checklist gains a named owner + target date |

Validator was launched with a one-off `model:"opus"` Task override (this repo's on-disk agent file predates the fix — ADR-003 Note).
