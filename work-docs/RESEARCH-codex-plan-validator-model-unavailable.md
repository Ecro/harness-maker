---
type: research
task_slug: codex-plan-validator-model-unavailable
status: complete
created: 2026-05-11
tags: [harness-maker, research, codex, agent-rendering, model-config]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://platform.openai.com/docs/models (model lineup reference — confirms no plain "o4")
related_docs:
  - work-docs/RESEARCH-codex-target-support.md
  - work-docs/RESEARCH-codex-usage-guide.md
  - .claude/memory/project_targets_axis.md
  - .claude/memory/project_cursor_model_policy.md
summary: "Codex agent TOMLs hardcode 'o4'/'o4-mini'; ChatGPT-tier Codex CLI rejects every one — root cause is in synthesize.py:_CODEX_AGENT_META."
---

# RESEARCH — Codex `plan-validator` model unavailable

## 🎯 Recommended Direction

**Drop the hardcoded `model =` line from every rendered `.codex/agents/*.toml` and let Codex CLI fall back to the user's `~/.codex/config.toml` default. Optionally surface a `codex_agent_model` override knob in `harness.yaml` for users who want per-tier differentiation.**

The current renderer in `src/harness_maker/synthesize.py:138-200` hardcodes `"o4"` (Opus-tier) and `"o4-mini"` (Sonnet-tier) into every Codex agent TOML. Both identifiers — plus `gpt-5-codex` and `gpt-5.5-codex` — are rejected on ChatGPT-account-tier Codex CLI subscriptions (verified by live probe today, output below). The only model that *works* in the user's current account is `gpt-5.5`, which is exactly what `~/.codex/config.toml` already sets as the account default. By omitting the `model` field at the agent level, every agent inherits the account-correct default automatically; users on differently-entitled accounts (API-key tier, gpt-5-codex enabled, etc.) override per-tier via `harness.yaml`.

## 🔍 Refinement Decisions

`--deep` not used. Topic was concrete enough (codex plan-validator failing) to dive directly.

## 🛠️ Approaches Found

### Approach A — Omit `model` from rendered TOML (RECOMMENDED)

| Field | Content |
|-------|---------|
| Approach | Render Codex agent TOMLs without the `model = "..."` line. Codex CLI inherits `~/.codex/config.toml`'s `model` value at invocation time. |
| Assumption | Codex CLI treats a missing per-agent `model` field as "use the session/profile default", which is what `gpt-5.5` testing today confirms. |
| Evidence | `~/.codex/config.toml` shows `model = "gpt-5.5"` as the account-wide default; user's recent `/hm:plan` execution that *did* succeed must have used this fallback path because the failing one explicitly tried `"o4"`. Plain `codex exec "..."` (no `--model`) returned a valid response in the live probe. |
| Trade-off | Loses per-agent model differentiation at render time. plan-validator and ux-reviewer get the same model. Reviewer parallelism quality drift. |
| Compatibility | Matches existing Cursor policy from CLAUDE.md §Targets: "agent prompts kept model-agnostic… user override OK." Same single-source-of-truth pattern. |
| Risk | low |

### Approach B — Map all agents to `gpt-5.5` explicitly

| Field | Content |
|-------|---------|
| Approach | Replace `"o4"`/`"o4-mini"` in `_CODEX_AGENT_META` with the empirically-working `"gpt-5.5"`. |
| Assumption | `gpt-5.5` is the lowest-common-denominator Codex CLI model across ChatGPT-account-tier subscriptions today. |
| Evidence | Live probe: `codex exec --model "gpt-5.5"` returned the expected reply; `o4`, `o4-mini`, `gpt-5-codex`, `gpt-5.5-codex` all returned `invalid_request_error: not supported when using Codex with a ChatGPT account`. |
| Trade-off | Bakes "gpt-5.5" into our renderer. When OpenAI ships gpt-6 / deprecates 5.5 / changes tier names, every harness needs re-render. Same drift hazard that bit us with `"o4"`. |
| Compatibility | Identical structure to today's render — just a value swap. No template change. |
| Risk | medium (drift inevitability) |

### Approach C — Per-tier override in `harness.yaml`

| Field | Content |
|-------|---------|
| Approach | Add `codex_agent_models: {opus_tier: "...", sonnet_tier: "..."}` to `HarnessConfig`. Default both to `null` (= omit field, fall back to Codex profile default). Interview asks once on `targets: [codex]` add-path. |
| Assumption | Users with differently-entitled accounts (API key, enterprise tier) want to opt into stronger models for reasoning-heavy agents (plan-validator, stuck, autoloop-coder). |
| Evidence | Existing `recommended_model: str = "claude-opus-4-7"` on `HarnessConfig` (models.py:228) already establishes this pattern for Cursor. Symmetric Codex knob fits the established design. |
| Trade-off | New interview question + new schema field. Schema change requires `answers_from_harness_yaml` round-trip support to avoid breaking old harnesses. |
| Compatibility | Excellent — mirrors the Cursor `recommended_model` pattern from CLAUDE.md §Targets. |
| Risk | low — additive, defaults preserve current-broken state until user opts in. |

### Approach D — Tier-aware string mapping (e.g., `o4-mini` → `gpt-5-mini` if entitlement check fails)

Considered then rejected. Codex CLI does not expose entitlement metadata before invocation; we can only learn a model is unavailable by trying and getting HTTP 400. Doing fallback at *render* time without account knowledge is no better than Approach B; doing it at *invocation* time means wrapping the Codex CLI in our own retry shim, which violates the "let the IDE be the IDE" architectural principle (see ARCHITECTURE.md:302).

## ⚠️ Pitfalls

- **Codex CLI errors are silent in slash-command context.** The user's transcript shows the agent "failed before running" with no actionable trace. Codex CLI's `400 invalid_request_error` arrives over stdout/stderr but harness-maker workflow currently doesn't surface it back through the slash-command UX — a separate gap to log into `failures.md` (see `[fail:codex-agent-launch-error-swallowed]`).
- **`o4` looks plausible but doesn't exist.** OpenAI's reasoning lineup is `o1`, `o3`, `o3-mini`, `o4-mini`. There is no plain `o4` shipping model as of 2026-05. The `_CODEX_AGENT_META` comment at `synthesize.py:135-137` rationalizes the choice as "reasonable default" but no probe ever validated it. **Lesson**: any hardcoded external model identifier needs a live-probe regression test (see §Open Questions Q3).
- **Even `gpt-5-codex` fails on ChatGPT-tier accounts.** Our research notes in `RESEARCH-codex-target-support.md` describe `gpt-5-codex` as "OpenAI's Codex-tuned model", which is true on the OpenAI API but **not** enabled on ChatGPT Plus/Pro subscriptions accessing Codex CLI. Account tier matters more than model name.
- **Snapshot tests don't catch this.** `tests/unit/test_synthesize.py` validates the TOML *renders correctly* with `model = "o4"` — i.e., we have a passing test asserting we render a broken value. The test asserts our intent, not external compatibility. **CLAUDE.md §Integration boundary** (checklist item 8) explicitly calls this out: "module import passes, `uv run` from different cwd fails."
- **User shipped a non-validator fallback once.** Their transcript notes "applying the validator rubric manually, recording the validation section as a fallback with the tool failure noted." That's a sane stop-gap, but it means the *quality gate* (which exists specifically to catch PLAN gaps before `/hm:execute`) ran in degraded mode. If we don't fix the renderer, every Codex user hits the same degraded gate.

## ❓ Open Questions

1. **Default policy: omit, or set to `gpt-5.5`?** Approach A (omit) is most account-portable; Approach B (set to `gpt-5.5`) preserves the "explicit > implicit" instinct. Which matches harness-maker's principle?
2. **Should we add the `codex_agent_models` schema field now (Approach C), or defer until a user actually requests per-tier override?** Adding now means schema migration work + interview-round addition; deferring means current users have no way to opt into stronger models even if their account supports them.
3. **Live-probe regression test for renderer.** Should `tests/integration/` add a `INTEGRATION=1 pytest tests/integration/test_codex_models.py` that runs `codex exec --model <X> "ping"` against every model we render, and fails if any returns 400? This catches drift without forcing CI to bill OpenAI on every push.
4. **Reverse-mapping legacy harnesses.** Users who already ran `/hm:make` and got `.codex/agents/*.toml` with `model = "o4"` need a remediation path. Auto-rewrite on next `/hm:make`? Or warn-only with a manual cleanup recipe?
5. **What does Cursor do for the same agents?** `.cursor/rules/harness.mdc:105-108` says `recommended_model: claude-opus-4-7` propagates to agent frontmatter. The Claude path uses `model: opus`. So we already have *three* model conventions in tree: `opus` (Claude tier word), `claude-opus-4-7` (Cursor recommendation), `o4` (Codex broken). Unify, or accept that each IDE has its own naming?

## 📚 Sources

- Live probe — `codex exec --model "o4" "ping"` → `{"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'o4' model is not supported when using Codex with a ChatGPT account."}}` (today, codex-cli 0.130.0).
- Live probe — `codex exec --model "o4-mini" "ping"` → same 400 with message `"The 'o4-mini' model is not supported when using Codex with a ChatGPT account."`.
- Live probe — `codex exec --model "gpt-5-codex" "ping"` → same 400 with `"The 'gpt-5-codex' model is not supported when using Codex with a ChatGPT account."`.
- Live probe — `codex exec --model "gpt-5.5-codex" "ping"` → same 400 with `"The 'gpt-5.5-codex' model is not supported when using Codex with a ChatGPT account."`.
- Live probe — `codex exec --model "gpt-5.5" "say ok"` → success, returned "ok" within 21k tokens.
- `~/.codex/config.toml` line 1: `model = "gpt-5.5"` (user's active account default).
- `codex --help` and `codex exec --help`: example flag is `-c model="o3"` (line 28 of help output) — confirms `"o4"` was never a documented Codex CLI model identifier.
- Codex CLI version probed: `codex-cli 0.130.0`.

## 🔗 Related Internal Docs

- [[work-docs/RESEARCH-codex-target-support.md]] — defines the Codex render scope (`.codex/agents/<name>.toml` with `developer_instructions = _body.md.j2`). This research adds the missing model-availability constraint to that scope.
- [[work-docs/RESEARCH-codex-usage-guide.md]] — referenced for command-as-skill dispatch model; orthogonal but useful context.
- [[.claude/memory/project_targets_axis.md]] — describes the triple-target render contract. Confirms `.codex/agents/*.toml` is the right artifact location; what's wrong is the *content* of one field.
- [[.claude/memory/project_cursor_model_policy.md]] — Cursor's `recommended_model: claude-opus-4-7` precedent for Approach C.
- [[CLAUDE.md]] §보안 / 권한 v1.6 + §버전업 정책 — note that fix touches `synthesize.py` only; no permission / version bump implications.
- [[ARCHITECTURE.md:302]] — "harness does **not** rewrite prompts to be model-agnostic" — informs why Approach D was rejected.

---

**Source of fix (single file, ~3 lines):**
- `src/harness_maker/synthesize.py:135-200` — `_CODEX_AGENT_META` table. For Approach A: change tuple shape to `(description,)` and drop `model_codex` kwarg in `_codex_agent_files()` at line 212. For Approach B: search-replace `"o4"` → `"gpt-5.5"` and `"o4-mini"` → `"gpt-5.5"` (or whatever you decide).
- `src/harness_maker/templates/codex/agent.toml.j2:3-5` — `{% if model_codex %}` block already gates on truthy, so Approach A works without template change.
- 12 rendered files in `.codex/agents/*.toml` — overwritten on next render.
- ≥18 snapshot files in `tests/e2e/sandbox-plugin-test/.backup-*/.codex/agents/` + `tests/e2e/sandbox/.codex/agents/` — snapshot regen needed.

**Immediate workaround for the user (no code change required):**
Delete the line `model = "o4"` from `.codex/agents/plan-validator.toml` (and `autoloop-coder.toml`, `stuck.toml`). Then the agent uses your `~/.codex/config.toml`'s default `gpt-5.5`. The 9 `o4-mini` agents will ALSO fail on this account — delete those lines too if you want full Codex coverage today.
