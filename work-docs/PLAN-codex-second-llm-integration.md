---
type: plan
task_slug: codex-second-llm-integration
status: planning
created: 2026-05-24
tags: [harness-maker, plan, python, codex, second-llm, multi-llm, reviewer]
research_doc: "[[RESEARCH-codex-second-llm-integration]]"
interview_rounds: 4
adrs: 9
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Claude→Codex second-opinion via `codex exec` Bash dispatch — 3 reviewer agents, hermetic, finding[] schema, Jinja conditional permission injection"
---

# PLAN — Codex second LLM integration

## 🎯 Executive Summary

**TL;DR**: First introduction of a Claude→Codex second-LLM call mechanism in harness-maker. Transport = `codex exec` Bash dispatch only (no MCP). Allow-list = {code-reviewer, consensus-arbiter, plan-validator}. All calls hermetic (`--ignore-user-config --ignore-rules`), output enforced by single `finding[]` JSON schema rendered to `.claude/schemas/codex-finding.schema.json`. Failures = warn-and-proceed (global). No in-code budget — relies on Codex account rate limits.

**What/Why**: RESEARCH-codex-second-llm-integration recommended hybrid (exec default + MCP opt-in); user picked exec-only for spend control. Existing harness-maker has NO Claude→Codex routing — PLAN-codex-plan-validator-model-unavailable was about *rendering* plan-validator FOR the Codex IDE, not about *calling* Codex FROM Claude. This PLAN is the first such mechanism.

**Key Decisions**:
- ADR-001 — Transport = `codex exec` Bash only (no MCP).
- ADR-002 — Allow-list = 3 agents.
- ADR-003 — Global warn-and-proceed failure policy.
- ADR-004 — No in-code budget.
- ADR-005 — Single `finding[]` schema; verdict stays Claude-derived, Codex output is additional reviewer input.
- ADR-006 — Hermetic invocation by default.
- ADR-007 — Permission injection via Jinja conditional in agent template (NOT `_merge_permissions`).
- ADR-008 — JSON schema lives at `templates/schemas/` + new `_render_pure_json` render branch.
- ADR-009 — `codex_second_opinion.enabled` is independent of `harness.yaml.targets`.

**Estimated impact**:
- 4 source files (`models.py`, `render.py`, `synthesize.py`, `interview.py`)
- 5 new template files (1 schema + 1 partial + edits to 3 agent body templates + 1 frontmatter conditional pattern shared across agent .md.j2)
- ~6 new unit tests
- 0 new snapshot fixtures (validator P1#4: snapshot delta verified via dedicated unit tests instead — sandbox fixtures keep `codex_second_opinion.enabled=false`)

---

## 📚 Prior Work

- [[RESEARCH-codex-second-llm-integration]] (2026-05-24) — Hybrid recommendation; pitfall #9 (MCP tool-name opacity), open Q3 (failure isolation), open Q7 (locale passthrough).
- [[PLAN-codex-plan-validator-model-unavailable]] (2026-05-11) — **Clarification**: that PLAN dropped per-agent `model =` lines from rendered `.codex/agents/*.toml` so Codex IDE picks the account default. It did NOT introduce a Claude→Codex routing path. This PLAN is the first such routing.
- [[PLAN-codex-target-support]] — Defines Codex IDE target asset render scope (`.codex/agents/*.toml`, `.codex/config.toml`). Independent from this PLAN; the two coexist orthogonally per ADR-009.
- `[wiki:model-routing-multi-ide]` (0.15.0) — Established `AgentModelSpec` per-agent model pinning + presets.py 3-tier resolve. We do NOT extend `AgentModelSpec` — `codex_second_opinion` is a separate top-level axis (routing transport, not model selection).
- `[wiki:fresh-install-health-baseline]` (0.17.0) — `_merge_permissions` (render.py:180-209) does list-union of `permissions.allow|deny|ask` — but **only inside `_shallow_merge_existing_json` for `settings.json`**. Agent `.md` frontmatter is static template content (validator P0#1). ADR-007 takes the Jinja-conditional path instead.
- `[fail:codex-helpers-ignore-user-config | 2026-05-11]` — Direct precedent against premature schema fields wired without consumer. Mitigated here by Phase 3 (interview wires the field with its consumer) and Phase 1 unit tests covering the model directly.
- `[wiki:gotcha] wrapup-marker-discipline-silent-loss` — Any new user-extension marker in templates must be named explicitly; not relevant here since the second-opinion partial has no user-extension markers (the agent body's existing `@hm:user:extensions` already covers customization).

---

## 🚫 Non-Goals

Explicitly out of scope for this PLAN; deferred to follow-up PLANs:

- **Target-gating** — Per ADR-009, `codex_second_opinion.enabled=true` activates regardless of whether `codex` is in `targets`. Users without the `codex` CLI installed will see warn-and-proceed at runtime per ADR-003. No interview validation gate links the two axes.
- **Caching Codex responses** — RESEARCH open Q5. No cache layer (`~/.cache/harness-maker/codex/`) in this PLAN. Each call hits the network. Deferred until repeated-prompt cost becomes a measured pain point.
- **Locale passthrough** — RESEARCH open Q7. The rendered Bash recipe passes the prompt as-is; whether Codex respects locale is left to Codex's behavior. No locale-aware wrapper. Deferred until empirical evidence of locale drift.
- **Per-agent failure policy** — ADR-003 fixed warn-and-proceed globally. Deferred per-agent override knob.
- **In-code budget enforcement** — ADR-004 deferred wrapper script (`python -m harness_maker.codex_invoke --max-per-session N`). Account rate limit is the only ceiling.
- **security-auditor inclusion** — ADR-002 explicitly excludes; user can add to `codex_second_opinion.agents` list manually.
- **Specialized reviewers (perf/ux/concurrency/code-verifier/test-reviewer/security-reviewer)** — Same as above; not in default allow-list.
- **MCP transport (`codex mcp-server`)** — ADR-001 rejected; not in this PLAN. Future re-introduction requires a schema change.
- **`recommended_model` cross-axis interaction** — `codex_second_opinion` does NOT extend `AgentModelSpec`; it is a separate routing axis. No interaction with `default_model` or `agent_models[*].codex` model overrides.

---

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | Note | → ADR |
|---|-------|-------|----------|--------|------|-------|
| 1 | R1 | Transport | Architecture | A — exec only | Rejected MCP for spend control + reconnect gap | ADR-001 |
| 2 | R2 | Agent allow-list | Architecture | + plan-validator (3 agents) | code-reviewer, consensus-arbiter, plan-validator. Excluded security-auditor (deferred) | ADR-002 |
| 3 | R2 | Failure policy | Failure handling | warn-and-proceed | Global default, autoloop-safe | ADR-003 |
| 4 | R3 | Budget | Risk | C — No budget | Account rate-limit dependency | ADR-004 |
| 5 | R3 | Output schema | Contract | A — Single finding[] schema | Reused across all 3 agents | ADR-005 |
| 6 | R3 | Hermetic | Determinism | A — Default ON | `--ignore-user-config --ignore-rules` | ADR-006 |
| 7 | R4 (validator P0#1) | Permission injection mechanism | Architecture | A — Jinja conditional in agent template | `_merge_permissions` was wrong (settings.json-only) | ADR-007 |
| 8 | R4 (validator P0#2) | Schema file location + render path | Architecture | A — `templates/schemas/` + new `_render_pure_json` branch | Same pattern as `lib/*.sh` (frontmatter-prohibited) | ADR-008 |
| 9 | R4 (validator P1#6) | Target gating | Scope | A — Independent of `targets` | Routing axis ⟂ IDE target axis | ADR-009 |

**Gate (final, R4):**
- EIG ≥ ε, CLARITI ≥ 0.7, common-ground holds for remaining slots, confidence ≥ τ for all PLAN-determinant slots, open_ended_count = 0. All 5 terms pass → exit interview.

---

## 📐 Architecture Decision Records

### ADR-001: Transport = `codex exec` Bash dispatch only (no MCP)

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 1)

**Context:** RESEARCH-codex-second-llm-integration recommended hybrid (`codex exec` default + `codex mcp-server` opt-in flag). User's binding constraint is spend control — Codex as second LLM must be invoked only at deliberate template-defined call points, not at Claude's runtime discretion.

**Decision:** Every Claude→Codex call point is an explicit Bash recipe inside a reviewer/plan-validator agent template. No MCP server registration. `harness.yaml` exposes only one transport (`exec`) — no opt-in `transport: mcp` knob until a future PLAN re-evaluates.

**Consequences:**
- ✅ Every call point is grep-able (`grep -r 'codex exec' .claude/agents/`).
- ✅ `Bash(codex exec:*)` permission allow-list per-agent is clean.
- ✅ Stdio MCP server auto-reconnect gap (Claude Code docs — stdio MCPs are NOT auto-reconnected) avoided.
- ✅ Zero ambient spend (Claude cannot self-dispatch).
- ⚠️ "Claude decides when to ask Codex" workflow impossible without template change.
- ⚠️ Future MCP opt-in re-introduction requires schema migration.

**Rejected alternatives:**
- **B (MCP only)** — Rejected for spend risk (Claude tool discretion) + stdio reconnect gap.
- **C (Hybrid — RESEARCH recommendation)** — Rejected because the MCP half adds maintenance surface without short-term value given user's spend-control priority.
- **D (MCP default + exec fallback)** — Rejected as inversion of priority.
- **Additional MCP rejection reason (RESEARCH pitfall #9)**: The MCP form's actual tool name (`mcp__codex_*`) depends on what `codex mcp-server` advertises at runtime. Permission rules in Claude Code would be opaque (`mcp__codex_codex` ≠ obvious); maintaining a stable allow-list across Codex CLI versions is brittle.

**Source:** Interview #1 (R1). RESEARCH pitfall #9 added per validator P2#9.

---

### ADR-002: Allow-list = {code-reviewer, consensus-arbiter, plan-validator}

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 2)

**Context:** RESEARCH listed candidate callers: M-of-N consensus reviewers, consensus-arbiter, security-auditor, plan-validator, specialized reviewers. User prioritized architectural rigor: plan-validator included, security-auditor excluded.

**Decision:** Exactly 3 agents receive the second-opinion partial include + `Bash(codex exec:*)` permission. All writers (executor, autoloop-coder, stuck) excluded by design — adding writer-tier permission would double the blast radius for any single bad Codex output.

**Consequences:**
- ✅ Template churn minimized (3 body files).
- ✅ Writer-class agents stay free of Codex call permission.
- ⚠️ security-auditor's 5-gate scan (prompt injection, secrets, etc.) gets no Codex cross-check.
- ⚠️ Specialized reviewers (perf/ux/concurrency) get no domain-specific Codex second opinion.
- ⚠️ Future additions require updating the default list in `models.py` AND adding `{% include %}` directives in new agent templates.

**Rejected alternatives:**
- **Minimal (code-reviewer + consensus-arbiter only)** — Rejected because consensus-arbiter is then arbitrating Claude+Codex inputs from only 2 producers (code-reviewer + Codex), which is weaker than including plan-validator's pre-execute critique.
- **+ security-auditor (3-agent variant)** — Deferred; user judged architectural rigor higher priority than security cross-check for the first iteration.
- **All reviewers (10 agents)** — Rejected as over-scope and uncontrolled spend.

**Source:** Interview #2a (R2).

---

### ADR-003: Failure policy = warn-and-proceed (global)

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 2)

**Context:** Codex calls can fail in 4 ways: (1) `codex login` not run / token expired, (2) account rate limit, (3) network outage, (4) `--output-schema` validation rejection. Need a default behavior for all 3 allow-listed agents.

**Decision:** On any Codex error, the agent body's Bash recipe writes a one-line message to stderr (e.g., `[codex second-opinion] skipped: {error class}`) and proceeds with Claude-only output. No per-agent override knob.

**Consequences:**
- ✅ autoloop / CI safe — Codex outage cannot block any stage.
- ✅ Consistent user-facing behavior across all 3 callers.
- ⚠️ Silent skip is possible (Codex absent → review proceeds without 2nd opinion). Mitigated by stderr line being grep-able for post-hoc audit.
- ⚠️ Audit-critical use cases (security-auditor would have wanted hard-fail) NOT in allow-list anyway, so the global default is harmless here.

**Rejected alternatives:**
- **hard-fail** — Rejected because autoloop would be marbled by any Codex outage.
- **claude-fallback (re-prompt Claude to "act as Codex would")** — Rejected as added complexity that mostly just re-runs the existing reviewer.
- **per-agent (`failure_policy: dict[str, Literal]`)** — Rejected as premature complexity; revisit when a real user reports a need.

**Source:** Interview #2b (R2).

---

### ADR-004: Budget = no in-code limit, account rate-limit only

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 3)

**Context:** Need to decide whether harness-maker ships any per-session call ceiling for Codex.

**Decision:** No code-side budget enforcement. The user's Codex account rate limit (typically tens of req/min) is the sole ceiling.

**Consequences:**
- ✅ Zero implementation cost.
- ✅ Account rate limit is a natural ceiling for normal workflows (≤3 callers, ≤handful of reviews per stage).
- ⚠️ Pathological loops (consensus-arbiter tie-breaking forever) can burn the account quota in seconds.
- ⚠️ Cost-conscious users have no telemetry without their own monitoring.

**Rejected alternatives:**
- **A (LLM-discipline counter file)** — Rejected because the LLM can bypass the counter (read once, ignore on subsequent calls) — false safety.
- **B (Hard wrapper `python -m harness_maker.codex_invoke --max-per-session N`)** — Rejected: 100+ LOC, e2e fixture needed, ROI low given normal workflows are well below any reasonable ceiling.

**Source:** Interview #3a (R3).

---

### ADR-005: Output schema = single `finding[]` shape, no verdict-in-summary parsing

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 3; revised per validator P1#5)

**Context:** Codex's `--output-schema` enforces JSON conformance. Need to decide what shape and how downstream agents ingest it.

**Decision:**
- Single schema file at `.claude/schemas/codex-finding.schema.json`:
  ```json
  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": false,
    "required": ["findings", "summary"],
    "properties": {
      "findings": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["severity", "message"],
          "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer", "minimum": 1},
            "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
            "message": {"type": "string", "minLength": 1},
            "evidence": {"type": "string"}
          }
        }
      },
      "summary": {"type": "string", "minLength": 1},
      "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    }
  }
  ```
- **No VERDICT-in-summary parsing**. The original draft proposed encoding plan-validator's verdict (`APPROVED|NEEDS_REVISION|MAJOR_REVISION`) as a `VERDICT: X` prefix in `summary`. Per validator P1#5 critique, that conflated two distinct verdict-ingestion paths:
  - plan-validator's own verdict (read by `/hm:plan` executor from the `Task` return value as free-text JSON) — unchanged by this PLAN.
  - Codex's `finding[]` output (read by the agent body via `--output-last-message <path>` + `jq`/Python parse) — what this schema covers.
- Codex's output is **additional reviewer input** to the agent, not the source of truth for any verdict. plan-validator still derives its own `APPROVED|NEEDS_REVISION|MAJOR_REVISION` verdict from its own Claude-side analysis of Codex `finding[]` + its own findings.

**Consequences:**
- ✅ Single schema file, single ingestion contract across all 3 callers.
- ✅ consensus-arbiter can merge Claude reviewer findings + Codex findings using one shape.
- ✅ No fragile regex parse on summary string.
- ⚠️ plan-validator's existing verdict path is unchanged; this PLAN does not improve verdict robustness — just adds Codex as one more input.
- ⚠️ Codex schema drift across CLI versions makes `--output-schema` rejection possible; warn-and-proceed (ADR-003) handles it.

**Rejected alternatives:**
- **Per-agent custom schema** — Rejected: 3+ schema files, ingestion code per agent, no clear benefit.
- **No schema (free text)** — Rejected: consensus-arbiter would need per-agent parsers.
- **VERDICT-in-summary convention (original draft)** — Rejected per P1#5: conflated ingestion paths; verdict robustness is plan-validator's existing concern, not this PLAN's scope.

**Source:** Interview #3b (R3). Validator P1#5 follow-up clarified the ingestion-path separation.

---

### ADR-006: Hermetic invocation = default ON

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 3)

**Context:** `codex exec` by default loads `~/.codex/AGENTS.md` (user-global) and project `.rules` (project-local). For a second-opinion use case, these inject developer-machine-specific bias into otherwise identical reviews.

**Decision:** All second-opinion invocations include `--ignore-user-config --ignore-rules` flags. The rendered Bash recipe in the partial always passes them. `harness.yaml.codex_second_opinion.hermetic` is `True` by default; users can flip to `False` to opt out.

**Consequences:**
- ✅ Two developers asking Codex the same question get the same Codex response (within Codex's nondeterminism budget).
- ✅ CI reproducibility.
- ⚠️ Developer's hand-curated AGENTS.md (e.g., domain glossary, coding-style notes) is ignored. Acceptable: the second opinion's job is independent assessment, not voice-matching.
- ⚠️ Security-significant AGENTS.md rules (e.g., "never read /etc/secret") are ignored — but `--sandbox read-only` already prevents writes, and Codex would not exfiltrate secrets without write access.

**Rejected alternatives:**
- **Default OFF (respect user config)** — Rejected on cross-machine non-reproducibility grounds.
- **Per-agent hermetic flag** — Rejected as premature complexity.

**Source:** Interview #3c (R3).

---

### ADR-007: Permission injection mechanism = Jinja conditional in agent template

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 4; validator P0#1 follow-up)

**Context:** Draft proposed `_merge_permissions` (render.py:180-209) to inject `Bash(codex exec:*)`. Validator caught: `_merge_permissions` is called only inside `_shallow_merge_existing_json` for `settings.json`. Agent `.md.j2` files go through `_render_text_file` / `_render_agents_md` and do not touch `_merge_permissions`. The plan's central mechanism was fictional.

**Decision:** Inject the Codex permission via a Jinja conditional block inside the agent template's frontmatter. **Whitespace control is mandatory** — the Jinja env in render.py runs with `trim_blocks=False, lstrip_blocks=False` (validator P-W1), so all conditional tags MUST use dash variants (`{%- ... -%}`) to avoid leaving residual newlines in the rendered output. Pattern:
```jinja2
permissions:
  allow:
    - Read(*)
    - Grep(*)
    - Glob(*)
{%- if codex_second_opinion_enabled and name in codex_second_opinion_agents %}
    - Bash(codex exec:*)
{%- endif %}
```
Context variables `codex_second_opinion_enabled` and `codex_second_opinion_agents` are populated in `synthesize._agent_files()` from `config.codex_second_opinion`. Reused via a small partial `templates/agents/_partials/codex_permission_line.md.j2` (the partial itself uses `{%- if -%}` / `{%- endif -%}` and is included via `{%- include "_partials/codex_permission_line.md.j2" -%}`). When `enabled=False`, the dash-stripped tags collapse to zero bytes → existing snapshot files byte-identical to today.

For `consensus-arbiter.md.j2` and `plan-validator.md.j2` (which currently have NO permissions block), Phase 2 adds a new permissions frontmatter section. Snapshot tests for those two files WILL show a real diff (the new block is present even when `codex_second_opinion.enabled=False`, because the baseline `allow: [Read(*), Grep(*), Glob(*)]` is unconditional). This is intentional and re-recorded in Phase 2 exit criterion.

**Consequences:**
- ✅ Uses the existing `_render_text_file` Jinja pipeline; no new render hook.
- ✅ Partial-based extraction keeps the per-agent edits to one `{% include %}` directive.
- ⚠️ Two of the 3 agents (`consensus-arbiter`, `plan-validator`) currently have NO permissions block in their `.md.j2` frontmatter. This PLAN adds one as part of Phase 2. Renaming this from "additive change" to "first-time permissions block" is honest about the scope.
- ⚠️ `content_hash` will change for all 3 agent files in Phase 2 even when `codex_second_opinion.enabled=false` (because the Jinja `{% if %}` always renders a fixed-shape comment marker even in the false branch). Acceptable: `reconcile.py` REPLACE for our-content_hash is the existing migration path.

**Rejected alternatives:**
- **B (new `_inject_codex_permissions` render hook)** — Rejected: introduces a new render-stage function with reconcile.py compatibility concerns (content_hash recompute timing) for no benefit over Jinja conditionals.
- **C (static permission unconditionally added)** — Rejected: leaves a meaningless Bash permission in disabled-state agents.

**Source:** Interview #4-F1. Validator P0#1.

---

### ADR-008: Schema file location + render path = `templates/schemas/` + new `_render_pure_json` branch

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 4; validator P0#2 follow-up)

**Context:** Draft proposed `templates/skills/_schemas/codex-finding.schema.json`. Validator caught: that directory does not exist, and `synthesize.py` has no FileSpec for `.claude/schemas/*.json` output. Additionally, the existing render dispatch's else-branch routes to `_render_text_file`, which prepends YAML frontmatter — corrupting a pure-JSON consumer file (same hazard as `lib/*.sh` per CLAUDE.md §2).

**Decision:**
- New template directory `src/harness_maker/templates/schemas/`.
- New template file `src/harness_maker/templates/schemas/codex-finding.schema.json` (no `.j2` suffix — static content; if Jinja interpolation needed later, rename to `.json.j2`).
- New `synthesize.py` function `_schema_files(env, ctx) -> list[FileSpec]` (or inline list) producing `(template_path, output_path)` for the schema. Output path: `.claude/schemas/codex-finding.schema.json`.
- **Correction (validator P-W3)**: `_render_pure_json` ALREADY EXISTS in `render.py` (line 512, used by `hooks/hooks.json` and `.cursor/mcp.json`). The new code in this PLAN is (a) a `_is_schemas_json` predicate added to the render dispatch and (b) the dispatch wire-up routing `.claude/schemas/*.json` → existing `_render_pure_json`. No new render function.
- Render dispatch decision: paths matching `.claude/schemas/*.json` → existing `_render_pure_json` (no frontmatter, no content_hash). All other `.json` paths (e.g., `.claude/.mcp.json`, `hooks/hooks.json`) keep their existing branches.
- File is **always rendered** when `codex_second_opinion.enabled=true`, gated in `_schema_files` by `config.codex_second_opinion.enabled`.

**Consequences:**
- ✅ Pure JSON output for external consumer (`codex exec --output-schema` parser).
- ✅ Same template-directory ergonomics as `templates/codex/`, `templates/cursor/`, etc.
- ✅ Reusable for future schemas (e.g., reviewer output schemas) — `templates/schemas/` is a forward-compat home.
- ⚠️ New render branch (`_render_pure_json`) needs unit test ensuring no frontmatter is added.
- ⚠️ Schema file has no `content_hash` ⇒ `reconcile.py` cannot use the "ours" fast-path. It always REPLACEs on next `/hm:make`. Acceptable: users do not edit schema files.

**Rejected alternatives:**
- **B (inline schema in agent partial via heredoc)** — Rejected: 3× duplication, schema diff drift hazard.
- **C (skill packaging — `templates/skills/codex-second-opinion/`)** — Rejected: skill packaging mandates `SKILL.md`, which is over-engineering for a schema-only deliverable.

**Source:** Interview #4-F2. Validator P0#2.

---

### ADR-009: `codex_second_opinion.enabled` is independent of `harness.yaml.targets`

**Status:** Accepted (2026-05-24, via /hm:plan interview Round 4; validator P1#6 follow-up)

**Context:** Validator flagged silent target-gating assumption. Two axes: (1) `targets` (IDE asset rendering — `.codex/` directory), (2) `codex_second_opinion` (LLM-routing for second-opinion calls). Need explicit policy.

**Decision:** `codex_second_opinion.enabled=true` activates the partial render + permission injection regardless of `targets`. The two axes are orthogonal: a user can have `targets: [claude-code]` (no Codex IDE assets rendered) and still enable Codex as a second LLM (because they have `codex` CLI installed via `npm install -g codex`).

**Consequences:**
- ✅ Use case "I use Claude Code as my IDE but want Codex CLI as 2nd reviewer" works.
- ✅ Axis orthogonality preserved (matches existing CLAUDE.md §Targets policy: `targets / preset / dev_mode` are all orthogonal).
- ⚠️ User without `codex` CLI installed sees warn-and-proceed at every reviewer invocation. Mitigated: README documents the dependency.
- ⚠️ No interview-time validation that `codex` is callable on the user's machine.

**Rejected alternatives:**
- **B (gated on `codex` in targets)** — Rejected: refuses the "codex CLI only, no IDE assets" use case.
- **C (default A + `require_target: bool` knob)** — Rejected as premature complexity.

**Source:** Interview #4-F6. Validator P1#6.

---

## 🏗️ Technical Design

**Current State:**
- `src/harness_maker/models.py:502` — `HarnessConfig` has `ConfigDict(strict=True, extra="forbid", populate_by_name=True)`. Adding any new top-level key requires matching addition.
- `src/harness_maker/models.py:654` — `InterviewAnswers` has the same `extra="forbid"`. Per validator P0#3, both classes must be extended.
- `src/harness_maker/render.py:180-209` — `_merge_permissions(base, overlay)` does list-union of `permissions.allow|deny|ask`. **Called only inside `_shallow_merge_existing_json` for `settings.json`.** Agent `.md.j2` files do NOT use it (validator P0#1).
- `src/harness_maker/render.py:1125-1213` — Render dispatch. `.json` paths under `.claude/` go through `_render_text_file` (the else-branch), which prepends YAML frontmatter — corrupts pure-JSON consumers.
- `src/harness_maker/synthesize.py:218` — `_agent_files(env, ctx) -> list[FileSpec]` builds context dict at lines 246-253 and threads it into each agent template render.
- `src/harness_maker/templates/agents/code-reviewer.md.j2:8-26` — Static `permissions:` block in frontmatter.
- `src/harness_maker/templates/agents/consensus-arbiter.md.j2` — NO `permissions:` block. ADR-007 adds one.
- `src/harness_maker/templates/agents/plan-validator.md.j2` — NO `permissions:` block. ADR-007 adds one.
- `src/harness_maker/templates/cursor/mcp.json.j2` — Existing reference for "external consumer pure JSON" rendering, but uses Jinja interpolation. The new `templates/schemas/codex-finding.schema.json` is static.
- `src/harness_maker/interview.py` — Wires interview answers into `InterviewAnswers` and then `HarnessConfig` via synthesize. New question slots in here.
- `tests/snapshot/regenerate.py` — Fixture-driven; runs `interview(p, autoloop_mode=True)` against `tests/fixtures/{name}/` directories. There is NO `tests/snapshot/sandbox/.claude/harness.yaml` (validator P1#4). Snapshot fixtures keep `codex_second_opinion.enabled=false` by default.
- `tests/snapshot/expected/` — `*.expected.yaml` manifests. New schema file appears only if a snapshot fixture enables `codex_second_opinion`.

**Affected Components:**

| Component | Change |
|-----------|--------|
| `src/harness_maker/models.py` | (a) Add `CodexSecondOpinionConfig(BaseModel)` with `enabled: bool=False`, `agents: list[str]=Field(default_factory=lambda: ["code-reviewer","consensus-arbiter","plan-validator"])`, `failure_policy: Literal["warn-and-proceed"]="warn-and-proceed"`, `hermetic: bool=True`, `output_schema_path: str=".claude/schemas/codex-finding.schema.json"`. ConfigDict strict + extra="forbid". (b) Add to `HarnessConfig`: `codex_second_opinion: CodexSecondOpinionConfig = Field(default_factory=CodexSecondOpinionConfig)`. (c) Add to `InterviewAnswers`: same field, same default (validator P0#3). |
| `src/harness_maker/synthesize.py` | (a) `_agent_files` context dict gains `codex_second_opinion_enabled: bool` and `codex_second_opinion_agents: list[str]` derived from `config.codex_second_opinion`. (b) New `_schema_files(env, ctx) -> list[FileSpec]` rendering `templates/schemas/codex-finding.schema.json` to `.claude/schemas/codex-finding.schema.json` when `enabled=True`. (c) `answers_from_harness_yaml` reverse mapper reads `codex_second_opinion` block (default to `CodexSecondOpinionConfig()` on missing key — silent fallback). (d) **Correction (validator P-W2)**: forward writer emits `codex_second_opinion:` block **unconditionally**, matching the existing pattern for `second_brain`, `feedback`, `ref_folders`, etc. — all of which are always emitted in `Production.yaml.j2` / `Side.yaml.j2` regardless of whether values equal defaults. There is no precedent for the "emit only when non-default" pattern in this codebase. Consequence: legacy harness.yaml files gain the `codex_second_opinion:` block on next `/hm:make` (with `enabled: false` default). |
| `src/harness_maker/render.py` | (a) New `_is_schemas_json(rel_path: str) -> bool` predicate (matches `.claude/schemas/*.json`). (b) Render dispatch: paths matching `_is_schemas_json` route to the **already-existing** `_render_pure_json` (render.py:512). `_render_pure_json` itself is NOT new (validator P-W3 correction). |
| `src/harness_maker/interview.py` | Add 1 question after the targets question: `enable_codex_second_opinion: bool` (yes/no). Default NO. When yes → default agent list, hermetic on, warn-and-proceed. No follow-up sub-questions (advanced fields stay defaults; users edit harness.yaml for tuning). Reverse mapper compatible. |
| `src/harness_maker/templates/schemas/codex-finding.schema.json` (NEW) | Static JSON file matching ADR-005 schema. |
| `src/harness_maker/templates/agents/_partials/codex_permission_line.md.j2` (NEW) | Single-line Jinja partial: `{% if codex_second_opinion_enabled and name in codex_second_opinion_agents %}    - Bash(codex exec:*)\n{% endif %}` (indentation precisely matching the surrounding `permissions.allow` block). |
| `src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2` (NEW) | Conditional include block. Top-level Jinja `{% if codex_second_opinion_enabled and name in codex_second_opinion_agents %} ... {% endif %}`. Body renders the second-opinion section: when to invoke, the Bash recipe (with `--sandbox read-only --ask-for-approval never --ignore-user-config --ignore-rules --json --output-schema {{ codex_output_schema_path }} --output-last-message $TMP`), ingestion guide (jq/Python parse of `findings[]`), failure handling (warn-and-proceed). |
| `src/harness_maker/templates/agents/code-reviewer.md.j2` | Add `{% include "agents/_partials/codex_permission_line.md.j2" %}` inside the existing `permissions.allow` block. |
| `src/harness_maker/templates/agents/code-reviewer_body.md.j2` | Add `{% include "agents/_partials/second_opinion_codex.md.j2" %}` after rubric.md.j2 include. |
| `src/harness_maker/templates/agents/consensus-arbiter.md.j2` | Add NEW `permissions:` block with `allow: [Read(*), Grep(*), Glob(*)]` baseline + the codex_permission_line partial. |
| `src/harness_maker/templates/agents/consensus-arbiter_body.md.j2` | Add second_opinion_codex partial include. |
| `src/harness_maker/templates/agents/plan-validator.md.j2` | Same NEW `permissions:` block + partial. |
| `src/harness_maker/templates/agents/plan-validator_body.md.j2` | Add second_opinion_codex partial include. |
| `tests/unit/test_models_codex_second_opinion.py` (NEW) | (a) `test_codex_second_opinion_config_defaults` — default-constructed has `enabled=False`, `agents` has 3 entries. (b) `test_codex_second_opinion_config_rejects_extra_fields` — extra="forbid" raises ValidationError. (c) `test_harness_config_round_trip_with_codex_second_opinion` — `HarnessConfig(...).model_dump()` round-trips through `HarnessConfig.model_validate(...)`. (d) Same for `InterviewAnswers`. |
| `tests/unit/test_render_pure_json.py` (NEW) | (a) `test_is_schemas_json_predicate_matches_dot_claude_schemas` — predicate returns True for `.claude/schemas/codex-finding.schema.json`, False for `.claude/.mcp.json`, `hooks/hooks.json`. (b) `test_dispatch_routes_schemas_to_pure_json` — synthesizing a HarnessConfig with `codex_second_opinion.enabled=True` produces `.claude/schemas/codex-finding.schema.json` whose content starts with `{` (not `---`) and contains no `content_hash`. `_render_pure_json` itself is NOT re-tested (existing function, existing coverage). |
| `tests/unit/test_render_codex_permission_injection.py` (NEW) | (a) `test_codex_permission_present_when_enabled` — render with `enabled=True` produces 3 agent files containing `Bash(codex exec:*)`. (b) `test_codex_permission_absent_when_disabled` — render with `enabled=False` produces 3 agent files NOT containing `Bash(codex exec:*)`. (c) `test_codex_permission_absent_in_non_allowlisted_agents` — executor / autoloop-coder / security-auditor never get the permission. |
| `tests/unit/test_render_codex_partial_include.py` (NEW) | Same shape, asserting presence/absence of the `## Optional: Codex second opinion` section across the 3 agent body files and confirming non-allow-listed agents do not get it. |
| `tests/unit/test_interview_codex_second_opinion.py` (NEW) | `test_interview_question_appears_when_codex_in_targets`, `test_interview_yes_round_trips_to_harness_yaml`, `test_interview_no_omits_key_from_yaml`. |
| `tests/unit/test_synthesize_roundtrip_codex.py` (NEW) | `test_legacy_yaml_without_key_loads_with_default`, `test_yaml_with_block_round_trips_byte_identical`. |
| Sandbox fixtures (`tests/fixtures/side-python-cli/`, `side-tauri-app/`, etc.) | NO CHANGE — keep `codex_second_opinion` unset → default `enabled=False` → zero snapshot diff impact (validator P1#4 resolution: snapshot fixtures stay clean; new functionality verified via dedicated unit tests above). |
| `CHANGELOG.md` | Unreleased / Added section: "Codex as second-LLM reviewer for code-reviewer, consensus-arbiter, plan-validator (opt-in via `codex_second_opinion.enabled`)". |
| `CLAUDE.md` §Targets policy | Add note: "Codex CLI also serves as second LLM (not only IDE asset render target) when `codex_second_opinion.enabled=true`. These axes are independent — see [[PLAN-codex-second-llm-integration]] ADR-009." |

**Dependencies:** None new. (Codex CLI is user-provided; CI does not need it for unit tests.)

**Data Flow:**

1. **Render-time** (when `/hm:make` runs):
   - Interview asks "enable Codex second opinion?" → user picks yes/no.
   - `synthesize` writes `codex_second_opinion:` block (or omits when default).
   - `render` reads config; for each agent in the allow-list, the Jinja conditionals inject (a) the `Bash(codex exec:*)` permission line and (b) the second-opinion section. The schema file is rendered to `.claude/schemas/codex-finding.schema.json` via `_render_pure_json`.
2. **Runtime** (when a reviewer agent runs):
   - LLM reads the rendered agent body containing the second-opinion section.
   - When the agent reaches the relevant trigger (M-of-N consensus pattern, tie-break, plan critique), the LLM invokes the Bash recipe:
     ```bash
     codex exec --sandbox read-only --ask-for-approval never \
       --ignore-user-config --ignore-rules \
       --json --output-schema .claude/schemas/codex-finding.schema.json \
       --output-last-message "$tmp" \
       - <<'PROMPT'
     {{ prompt_for_codex }}
     PROMPT
     ```
   - On success: parse `$tmp` as JSON conforming to the schema, merge findings into the agent's own analysis.
   - On failure (any non-zero exit): emit `[codex second-opinion] skipped: <reason>` to stderr, proceed Claude-only.

**API Changes:**
- `HarnessConfig.codex_second_opinion` (new). Existing harness.yaml without the key silently loads default.
- `InterviewAnswers.codex_second_opinion` (new, same shape, same default).
- New rendered file `.claude/schemas/codex-finding.schema.json` (only when `enabled=True`).
- New rendered permissions line in 3 agents (only when `enabled=True`).

---

## 📝 Implementation Plan

### Phase 1 — Schema models + pure-JSON render branch

**Scope (in)**:
- `src/harness_maker/models.py`: `CodexSecondOpinionConfig`, `HarnessConfig.codex_second_opinion`, `InterviewAnswers.codex_second_opinion`.
- `src/harness_maker/render.py`: `_render_pure_json` helper + dispatch routing for `.claude/schemas/*.json`.
- `tests/unit/test_models_codex_second_opinion.py`, `tests/unit/test_render_pure_json.py`.

**Scope (out)**: Templates (Phase 2), interview wiring (Phase 3), docs (Phase 4).

**Exit criterion**:
- `uv run pytest tests/unit/test_models_codex_second_opinion.py tests/unit/test_render_pure_json.py -v` → 7 named tests green (see Affected Components table).
- Full `uv run pytest tests/unit/ -q` green (no regression).
- `uv run mypy --strict src/harness_maker/models.py src/harness_maker/render.py` clean.

**Risk**: low. Additive schema + isolated render helper.

**Rollback**: revert to HEAD (no other phase depends on Phase 1's commit being kept beyond the worktree).

---

### Phase 2 — Templates (schema file + permission partial + second-opinion partial + 3 agent edits)

**Scope (in)**:
- `src/harness_maker/templates/schemas/codex-finding.schema.json` (new).
- `src/harness_maker/templates/agents/_partials/codex_permission_line.md.j2` (new).
- `src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2` (new).
- Edits to `code-reviewer.md.j2`, `code-reviewer_body.md.j2`, `consensus-arbiter.md.j2`, `consensus-arbiter_body.md.j2`, `plan-validator.md.j2`, `plan-validator_body.md.j2` (6 files).
- `synthesize.py` `_agent_files` context dict extension + `_schema_files` addition.
- `tests/unit/test_render_codex_permission_injection.py`, `tests/unit/test_render_codex_partial_include.py`.

**Scope (out)**: Interview wiring (Phase 3), docs (Phase 4).

**Exit criterion**:
- Both new unit tests green: 6 test functions covering enabled-true / enabled-false / non-allow-listed agents for both permission and partial inclusion.
- `uv run pytest tests/snapshot/ -q` → diffs ONLY in expected files: (a) `code-reviewer.md` — zero byte diff when `enabled=false` (dash-stripped Jinja partials collapse to nothing per ADR-007 W1 correction); (b) `consensus-arbiter.md` and `plan-validator.md` — new `permissions:` frontmatter block (intentional, see ADR-007). All other agent snapshots: 0 diff.
- Manual verification (R9 mitigation, validator P-W4): in a scratch dir, invoke `claude` with a code-reviewer agent dispatch (with `codex_second_opinion.enabled=true` rendered) and confirm `codex exec` Bash invocation is NOT blocked by code-reviewer's `Bash(bash:*)` / `Bash(sh:*)` deny rules. Document outcome in `tests/manual/CODEX_PERMISSION_PROBE.md` (one-time check).
- Programmatic verification: `uv run python -c "from harness_maker import render, models; cfg = models.HarnessConfig(codex_second_opinion=models.CodexSecondOpinionConfig(enabled=True)); ..."` produces 3 agent files with the new section + 1 schema file.

**Risk**: medium. Template indentation must match (`permissions.allow` YAML indent is sensitive); partial include path resolution must work for both `.md.j2` and `_body.md.j2`.

**Rollback**: revert all template files + the synthesize.py changes; Phase 1 commit can stand (the model exists but is unused until Phase 2 lands again).

---

### Phase 3 — Interview wiring + harness.yaml round-trip

**Scope (in)**:
- `src/harness_maker/interview.py`: 1 new yes/no question post-targets.
- `src/harness_maker/synthesize.py`: forward + reverse mapper for `codex_second_opinion` block.
- `tests/unit/test_interview_codex_second_opinion.py`, `tests/unit/test_synthesize_roundtrip_codex.py`.

**Scope (out)**: templates (Phase 2), docs (Phase 4).

**Exit criterion**:
- 5 named test functions green (see Affected Components table).
- Manual: run interview in a fresh dir → answer yes → inspect rendered `.claude/harness.yaml` → contains `codex_second_opinion:` block → re-render → identical output (round-trip determinism).

**Risk**: low. Single question + reverse mapper pattern is well-established (FeedbackConfig, SecondBrainConfig precedents).

**Rollback**: revert interview.py + synthesize.py changes; Phase 1+2 commits can stand (the field exists, templates know how to render it, only the interview path doesn't ask).

---

### Phase 4 — Docs

**Scope (in)**:
- `CHANGELOG.md`: Unreleased / Added section entry.
- `CLAUDE.md`: §Targets policy gains the ADR-009 note about Codex CLI's dual role.
- `README.md`: 1-paragraph mention in the multi-LLM / harness-features section. **Tracked** per validator P-W5 (the ADR-009 / R4 mitigation cites README; this Phase makes it a tracked deliverable).

**Scope (out)**: Code changes (Phases 1-3).

**Exit criterion**:
- `uv run python -m harness_maker.context_linter` → no new warnings (CLAUDE.md ≤ Production 500 lines).
- `git diff CHANGELOG.md` shows one new entry under `## Unreleased` / `### Added`.
- `git diff CLAUDE.md` shows §Targets section unchanged in length budget.
- `git diff README.md` shows new mention of Codex-as-second-LLM with the `codex` CLI install prerequisite (1-2 sentences).

**Risk**: low.

**Rollback**: `git checkout HEAD -- CHANGELOG.md CLAUDE.md README.md`. Phases 1-3 stand.

---

## 🧪 Testing Strategy

- **Unit**: All 4 phases. Phase 1 covers schema + render-helper unit. Phase 2 covers template-output unit (synthesize a config, inspect rendered string). Phase 3 covers interview + synthesize round-trip.
- **Snapshot**: Phase 2 — sandbox fixtures stay at default (`enabled=false`), so snapshots diff for the 3 agent files ONLY in the conditional-template-rendering sense (the `{% if %}` block always emits a consistent fixed-shape output even when false: empty for `_partials/codex_permission_line.md.j2`, empty for `_partials/second_opinion_codex.md.j2`). Phase 2 exit criterion verifies 0 unexpected snapshot diffs.
- **Integration**: NONE (per ADR-004 and ADR-003 — no live Codex probe; CI does not have Codex CLI). Optional `INTEGRATION=1`-gated test deferred.
- **Manual**:
  - Phase 2: visually inspect `.claude/agents/code-reviewer.md` after rendering with `enabled=True`; confirm the second-opinion section reads sensibly and the Bash recipe is exact.
  - Phase 3: end-to-end interview run → harness.yaml inspection → re-render check.

---

## ⚠️ Risks & Mitigation

| R | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|-----------|
| R1 | Pathological loop (e.g., consensus-arbiter tie-breaking forever) burns Codex account quota — no in-code budget per ADR-004 | low | medium | Documented in CLAUDE.md as a known design choice. User can monitor via Codex account dashboard. Deferred wrapper script ships in a follow-up PLAN if a user reports the issue. Stop-criterion: if any tester reports a runaway during pre-release, ship the wrapper. |
| R2 | Codex CLI `--json` event schema drifts (RESEARCH pitfall #10 — Rust rewrite mid-flight) | medium | medium | `--output-schema` enforcement makes drift loud: Codex either conforms or returns a schema-violation error → warn-and-proceed kicks in. Manual re-verification on each Codex CLI major bump. Schema is versioned at `.claude/schemas/codex-finding.schema.json` (no version field today — accept this as deferred; revisit on first observed breakage). |
| R3 | `--ignore-user-config` / `--ignore-rules` flag renamed in Codex Rust rewrite (RESEARCH pitfall #5) | low | medium | Subscribe to Codex CLI release notes; flag rename = one-line template fix in the partial. |
| R4 | User opts in but never runs `codex login` → first call fails with auth error | high | low | warn-and-proceed (ADR-003) handles. stderr message includes "run codex login first" hint. README documents the dependency. CHANGELOG entry calls it out explicitly. |
| R5 | Snapshot scope drift in Phase 2 (changes >3 agents inadvertently) | low | medium | Phase 2 exit criterion explicitly: `pytest tests/snapshot/ -q` returns 0 diffs (sandbox fixtures keep `enabled=false`, so no agent file should change under default render). If any sandbox snapshot diffs appear, halt and inspect — likely a template indentation bug. |
| R6 | ~~plan-validator verdict-via-summary-string parse fragility~~ | n/a | n/a | **Eliminated** by ADR-005 revision: no VERDICT-in-summary parsing. plan-validator's verdict is unchanged; Codex output is additional finding[] input only. |
| R7 | security-auditor excluded from allow-list = no 2nd opinion on prompt-injection findings | medium | medium | Documented in Non-Goals + ADR-002 Consequences. User can add `security-auditor` to `codex_second_opinion.agents` list manually; the schema permits any agent name. Follow-up PLAN may promote security-auditor based on usage. |
| R8 | New `consensus-arbiter.md.j2` and `plan-validator.md.j2` permissions blocks (added in Phase 2) accidentally grant more permission than intended (e.g., a copy-paste from `code-reviewer.md.j2` brings unrelated `Bash(...)` rules) | medium | medium | Phase 2 unit test explicitly asserts the rendered permissions block for these 2 agents matches a minimal allow-list of `[Read(*), Grep(*), Glob(*)]` plus the conditional `Bash(codex exec:*)`. No other Bash rules permitted. |
| R9 | code-reviewer's existing deny rules (`Bash(bash:*)`, `Bash(sh:*)`, `Bash(python:*)`) interact unpredictably with the new `Bash(codex exec:*)` allow. Codex CLI may internally spawn subprocesses (bash/sh/python); Claude Code's permission evaluation granularity at the tool-call boundary vs subprocess spawning is unverified (validator P-W4). | medium | medium | Phase 2 manual verification step: invoke a `code-reviewer` dispatch with `codex_second_opinion.enabled=true` and confirm `codex exec` runs without permission denial. Document the probe in `tests/manual/CODEX_PERMISSION_PROBE.md`. If denial occurs, ADR-007 follow-up: shift the codex permission scope (e.g., `Bash(codex *)` instead of `Bash(codex exec:*)`) or revisit the deny baseline. |

---

## ✅ Success Criteria

- [ ] `harness.yaml.codex_second_opinion.enabled=true` produces exactly 3 modified agent body files + 1 new schema file. Zero unexpected file diffs anywhere.
- [ ] Rendered agent body contains `codex exec --sandbox read-only --ask-for-approval never --ignore-user-config --ignore-rules --json --output-schema .claude/schemas/codex-finding.schema.json`.
- [ ] `Bash(codex exec:*)` permission appears ONLY in the 3 allow-listed agents' rendered `.md` files; absent from all 8+ other agents.
- [ ] Interview question yes-path round-trips through harness.yaml → answers_from_harness_yaml → identical `InterviewAnswers` instance.
- [ ] Schema file `.claude/schemas/codex-finding.schema.json` renders as pure JSON (no YAML frontmatter prefix, no content_hash).
- [ ] CHANGELOG entry under `## Unreleased` / `### Added`.
- [ ] CLAUDE.md §Targets section mentions ADR-009 dual role.
- [ ] `uv run pytest tests/unit/ -q` 100% green (including 6 new test files).
- [ ] `uv run pytest tests/snapshot/ -q` 100% green (zero unexpected diffs).
- [ ] `uv run mypy --strict src/harness_maker/` clean.

---

## 🔍 Plan Validation

**First pass** (2026-05-24): MAJOR_REVISION. 3 P0, 5 P1, 1 P2.

**Resolution rounds**:
- **R4-F1** (P0#1 `_merge_permissions` mechanism wrong) — Interview Round 4-F1; chose Jinja conditional → ADR-007.
- **R4-F2** (P0#2 schema render path missing) — Interview Round 4-F2; chose new `templates/schemas/` + `_render_pure_json` → ADR-008.
- **R4-F3** (P0#3 InterviewAnswers missing) — Acknowledged; added explicitly to Affected Components table. No interview needed (mechanically required).
- **P1#4** (snapshot mechanism misunderstood) — Resolved via dedicated unit tests (`test_render_codex_permission_injection.py`, `test_render_codex_partial_include.py`); sandbox fixtures stay at `enabled=false` default, no new snapshot fixture needed.
- **P1#5** (ADR-005 conflated paths) — Revised ADR-005: dropped VERDICT-in-summary parsing; Codex output is additional reviewer input only, plan-validator's verdict path unchanged. R6 risk eliminated.
- **P1#6** (target gating undefined) — Interview Round 4-F6; chose independent → ADR-009. Non-Goals section added.
- **P1#7** (Phase 1 exit criterion vague) — Named all 7 Phase 1 test cases in Affected Components + Exit criterion.
- **P1#8** (R6 platitude + no rollback) — R6 eliminated by ADR-005 revision; rollback added to all 4 phases.
- **P2#9** (ADR-001 missing pitfall #9) — Added third rejection reason to ADR-001.

**Second pass** (2026-05-24): NEEDS_REVISION. 0 P0, 4 warnings + 1 suggestion. All first-pass items confirmed resolved (`unresolved_from_first_pass: []`). New issues all from the revision itself:
- **P-W1** (Jinja whitespace, snapshot byte-identity) — Fixed: ADR-007 mandates `{%- ... -%}` dash variants; Phase 2 exit criterion updated to expect 0-byte diff on `code-reviewer.md` and intentional diff on 2 new-permissions-block files.
- **P-W2** (synthesize_harness_yaml conditional emission has no precedent) — Fixed: Technical Design specifies **unconditional emit** matching existing pattern; legacy harness.yaml files gain the block on next `/hm:make`.
- **P-W3** (`_render_pure_json` already exists, not new) — Fixed: ADR-008 + Affected Components + Phase 1 test list corrected; real new code is `_is_schemas_json` predicate.
- **P-W4** (deny-conflict risk untracked) — Fixed: R9 added to risk register; Phase 2 exit criterion adds manual probe step + `tests/manual/CODEX_PERMISSION_PROBE.md`.
- **P-W5** (README mitigation untracked) — Fixed: Phase 4 scope + exit criterion now lists README.md.

**Validator outcome (final)**: NEEDS_REVISION_RESOLVED. No third validator pass per procedure ("re-run validator once only").
