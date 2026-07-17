---
type: research
task_slug: codex-second-llm-integration
status: complete
created: 2026-05-24
tags: [harness-maker, research, codex, mcp, second-llm, multi-llm, headless]
mtime_warn_days: 14
libs_fetched:
  - codex-cli (developers.openai.com/codex)
  - claude-code-mcp (code.claude.com/docs/en/mcp)
sources:
  - https://developers.openai.com/codex/mcp
  - https://developers.openai.com/codex/noninteractive
  - https://developers.openai.com/codex/cli/reference
  - https://code.claude.com/docs/en/mcp
  - https://github.com/tuannvm/codex-mcp-server
  - https://github.com/mkXultra/claude-code-mcp/
  - https://github.com/steipete/claude-code-mcp
  - https://github.com/openai/codex/discussions/21764
  - https://medium.com/@sangho.oh/claude-codex-cli-agentic-coding-a98c83ba043e
related_docs:
  - "[[RESEARCH-codex-shell-invocation]]"
  - "[[RESEARCH-codex-usage-guide]]"
  - "[[PLAN-codex-target-support]]"
  - "[[PLAN-codex-plan-validator-model-unavailable]]"
summary: "Hybrid: codex exec via Bash for explicit second-opinion calls; codex mcp-server as opt-in for power users. No Anthropic-shipped Codex MCP exists."
---

# 🎯 Recommended Direction

**Hybrid integration with `codex exec` as the default and `codex mcp-server` as an opt-in.** Anthropic does not ship an official Codex MCP — your recollection conflates two things: OpenAI itself ships a first-party MCP entrypoint (`codex mcp-server`, since v0.75) and several community wrappers exist (`tuannvm/codex-mcp-server`, `mkXultra/ai-cli-mcp`, `steipete/claude-code-mcp`).

For harness-maker's "Claude primary, Codex occasional second opinion" pattern, the binding trade-off is **discretion vs. spend control**. MCP gives Claude tool discretion ("ask Codex when uncertain") and inflates ambient spend; `codex exec` via Bash makes every invocation a deliberate template decision an agent or hook authors up front. Lock the default to `codex exec` invoked from specific reviewer/auditor agents, and ship `codex mcp-server` as an opt-in rendered only when `harness.yaml.codex_mcp.enabled: true`.

This stays consistent with existing harness-maker patterns: Codex target shipped via shell dispatch (PLAN-codex-target-support), plan-validator already routes to Codex on `--model-unavailable` (PLAN-codex-plan-validator-model-unavailable), and the prior shell-invocation research locked the correct CLI shape (`codex exec --sandbox workspace-write --ask-for-approval never`).

---

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** + **Risk / compliance** (auth, sandbox, runaway spend). Not user-workflow — the topic is purely about wiring a second LLM into the existing harness. No `--deep` interview needed.

---

## 🛠️ Approaches Found

### Approach 1 — `codex exec` headless via Bash (RECOMMENDED default)

| Field | Content |
|-------|---------|
| Approach | Render `codex exec` invocations into specific agent/skill/hook prompts; expose `Bash(codex exec:*)` in those agents' permission allow-lists. |
| Assumption | Codex CLI ≥ 0.75 installed; auth via `codex login` or `CODEX_API_KEY`. Already covered by existing `codex` target onboarding. |
| Evidence | `RESEARCH-codex-shell-invocation.md` locked the flag shape. `--json` gives JSONL events; `--output-schema schema.json` enforces structured second-opinion output. `--ignore-rules --ignore-user-config` available for hermetic invocation (avoids `~/.codex/AGENTS.md` pollution). |
| Trade-off | Every call point is a template decision — explicit and reviewable, but adds template churn. No automatic Claude-side discretion. |
| Compatibility | Native fit. We already render Bash dispatches in templates; agents already have per-stage permission baselines. Permission rules can be scoped per-agent (`code-reviewer` allowed, `executor` denied). |
| Risk | low |

**Key invocation shape** (for second-opinion-as-reviewer):

```bash
codex exec \
  --sandbox read-only \
  --ask-for-approval never \
  --ignore-user-config --ignore-rules \
  --json \
  --output-schema "$REPO/.claude/schemas/second-opinion.json" \
  --output-last-message /tmp/codex-opinion-$$.json \
  - <<'PROMPT'
{{ second_opinion_prompt }}
PROMPT
```

Notes on each flag:
- `--sandbox read-only` — review/audit use case needs no write surface.
- `--ignore-user-config --ignore-rules` — strips developer's `~/.codex/AGENTS.md` and project `.rules` so the second opinion is deterministic across machines.
- `--json` + `--output-schema` — machine-readable, schema-enforced output for consensus-arbiter ingestion.
- `--output-last-message` — durable artifact for the audit trail.
- stdin heredoc — multi-line prompts without quoting hell.

### Approach 2 — `codex mcp-server` (OpenAI's own MCP, opt-in)

| Field | Content |
|-------|---------|
| Approach | Register `codex mcp-server` as a stdio MCP server in `.claude/.mcp.json`; Claude calls `mcp__codex_codex` (or similar) when it decides. |
| Assumption | Codex CLI ≥ 0.75 + Claude Code v2.1.x. Authenticated via `codex login`. |
| Evidence | Official OpenAI docs (developers.openai.com/codex/mcp): `codex mcp-server` runs over stdio and inherits config. Claude Code docs (`code.claude.com/docs/en/mcp`) define stdio MCP scope hierarchy and ToolSearch deferral. |
| Trade-off | Context cost is low *with* default ToolSearch (only tool names at startup, schemas on demand); becomes full-load on Vertex/Bedrock/proxied Anthropic where `ENABLE_TOOL_SEARCH` falls back to disabled. Claude's discretion to invoke = harder to ceiling spend. |
| Compatibility | Stdio MCP servers do NOT auto-reconnect (docs explicit). If Codex stdio crashes mid-session, Claude can't recover without `/mcp` reset. |
| Risk | medium — discretion-driven spend + reconnect gap |

**Minimal config** (project scope, opt-in):

```json
// .claude/.mcp.json
{
  "mcpServers": {
    "codex": {
      "type": "stdio",
      "command": "codex",
      "args": ["mcp-server"]
    }
  }
}
```

Project scope triggers the workspace-trust prompt — by design, harness-maker should not ship this in baseline `targets: [claude-code, codex]` because it asks every consumer to approve a tool surface they may not want.

### Approach 3 — Community wrappers (tuannvm, mkXultra, steipete)

| Field | Content |
|-------|---------|
| Approach | Use a third-party MCP server (e.g. `npx -y codex-mcp-server`) that wraps `codex exec`. |
| Assumption | Trust the wrapper maintainer; pin a version. |
| Evidence | `tuannvm/codex-mcp-server` exposes `codex`/`review`/`websearch`/`listSessions`/`ping`/`help` tools, 31 releases through April 2026, requires Codex CLI ≥ 0.75 anyway. `mkXultra/ai-cli-mcp` covers Claude+Codex+Gemini behind one MCP. |
| Trade-off | Adds a dependency that does what `codex mcp-server` now does natively. Was useful in 2025 before Codex shipped native MCP — now mostly historical. |
| Compatibility | Works in any MCP client; same reconnect gap as Approach 2. |
| Risk | medium — duplicates official capability + supply-chain surface |

### Approach 4 — Hybrid (RECOMMENDED)

| Field | Content |
|-------|---------|
| Approach | Approach 1 is the default; Approach 2 ships behind an opt-in flag. |
| Assumption | Most users want a deterministic second-opinion call point in 2-3 reviewer/auditor agents, not Claude-decided sprinkling. Power users who want ambient Codex access can flip a flag. |
| Evidence | Existing harness-maker pattern (Codex target shipped via shell dispatch, plan-validator already calls `codex exec` for one fallback) is congruent with Approach 1. Opt-in MCP flag matches how we already gate `cursor` / `codex` targets. |
| Trade-off | Slight rendering complexity — a `codex_mcp.enabled` key feeds two conditional render branches (`.mcp.json` entry + an agent prompt note that the MCP variant is available). |
| Compatibility | Both flavors share the same auth model (`codex login` or `CODEX_API_KEY`). Same per-IDE caveats. |
| Risk | low |

---

## ⚠️ Pitfalls

1. **No Anthropic-shipped Codex MCP exists.** Claude Code's official MCP surfaces are documented at `code.claude.com/docs/en/mcp` and the Anthropic Directory (`claude.ai/directory`) lists reviewed connectors — none of which is an OpenAI Codex connector. Anyone telling you "the official MCP for Codex" means either OpenAI's own `codex mcp-server` (first-party from OpenAI's side, not Anthropic's) or a community wrapper. Don't pin a plan on a non-existent Anthropic connector.

2. **Stdio MCP servers don't auto-reconnect.** Claude Code docs (`Stdio servers are local processes and are not reconnected automatically.`). If `codex mcp-server` crashes mid-session or auth expires, the user is stuck until they hit `/mcp` and reset manually. Headless `codex exec` doesn't have this failure mode — every Bash call is a fresh subprocess.

3. **`codex exec` inherits AGENTS.md by default.** Both `~/.codex/AGENTS.md` and project `AGENTS.md` get loaded unless you pass `--ignore-user-config --ignore-rules`. For a "second opinion" use case this is non-determinism: two developers asking Codex the same question can get different answers because their `~/.codex/AGENTS.md` differs. Always pass the ignore flags for review/audit calls.

4. **ToolSearch is default-on but not unconditional.** Claude Code disables ToolSearch on Vertex AI, Bedrock proxies, and any `ANTHROPIC_BASE_URL` pointing at a non-first-party host. In those configs `codex mcp-server`'s tool schemas load upfront, eating context. If we ship the MCP variant, document this caveat.

5. **Approval/sandbox defaults trap automation.** `codex exec` defaults to `--ask-for-approval on-request` and `--sandbox read-only`. Without explicit flags it'll either hang waiting for stdin approval or refuse to write. `--ask-for-approval never` is mandatory for any harness-driven call. Set `--sandbox` to the minimum needed (`read-only` for reviews, `workspace-write` only if Codex needs to grep/test).

6. **`-p` is `--profile`, not `--prompt`.** Repeating the warning from `RESEARCH-codex-shell-invocation.md` because it WILL bite again — `codex exec -p "review this"` loads a profile named `"review this"`. Pass the prompt as a positional argument or stdin `-`.

7. **Auth state is per-user, not per-project.** `codex login` writes to `~/.codex/`. Project-scope `.mcp.json` checked into VCS doesn't carry auth; each developer must `codex login` once. Document this in the onboarding step or the MCP config will silently fail for collaborators with `error: not authenticated` on the first tool call.

8. **Spend ceiling is not built into Codex.** Neither `codex exec` nor `codex mcp-server` rate-limits per-session. If we add Codex as a tool Claude can invoke, a single bad reviewer loop can rack up hundreds of calls. For MCP variant, the only ceiling is OpenAI's account-level rate limit; for headless, we can cap via a wrapper script (e.g. `harness_maker.codex_invoke --max-calls-per-session N`).

9. **Permission rule shape difference.** Headless = `Bash(codex exec:*)` in `permissions.allow`. MCP = `mcp__codex_codex` (the tool name) in allow/deny. The MCP form is opaquer because users see "codex" in `/mcp` but the actual tool-name suffix depends on what `codex mcp-server` advertises. Run `claude mcp get codex` after install to record exact tool names before writing permission rules.

10. **`codex exec` JSON event stream is unstable across versions.** Codex repo is mid-rewrite from TypeScript to Rust (Discussion #1174). Event types (`thread.started`, `turn.started`, `item.*`) and item subtypes can shift. If we parse `--json` output we need a version pin or schema validation.

---

## ❓ Open Questions

1. **Which agents become Codex callers?** Candidates from existing fleet:
   - `code-reviewer` (M-of-N consensus already; Codex as the N+1th reviewer)
   - `consensus-arbiter` (tie-break call when Claude reviewers disagree)
   - `security-auditor` (5-gate scan; Codex second opinion on prompt-injection gate)
   - `plan-validator` (already uses Codex when local model unavailable — extend to always-on second opinion?)
   - `executor` — almost certainly NOT, because executor writes code and adding a writer call point doubles blast radius.
2. **Cost ceiling — per session or per call type?** A `harness.yaml.codex.budget` block with `max_calls_per_session`, `max_tokens_per_call`, and `denylist_stages` would let users cap spend without disabling the feature.
3. **Failure isolation policy.** When Codex returns an error (auth, rate limit, network), should the parent agent (a) proceed Claude-only with a warning, (b) hard-fail the stage, or (c) re-route to a Claude-only fallback prompt? Recommend (a) for reviewers, (b) for security-auditor, (c) for plan-validator.
4. **Should `codex_mcp.enabled` be a separate `harness.yaml` key or absorbed into `targets`?** Recommend separate key — `targets` controls *which IDE renders* assets, `codex_mcp` controls *whether Claude Code's MCP surface includes Codex*. They're orthogonal.
5. **Caching.** Should we hash the prompt + relevant file diffs and cache Codex responses in `~/.cache/harness-maker/codex/` for replay (like the existing GitHub API cache pattern)? Cuts re-run cost during `/hm:review` iteration.
6. **`--output-schema` schemas.** What does the JSON schema for a "reviewer second opinion" look like? Existing reviewer agents emit findings as `[{file, line, severity, message}]`; the schema should match so consensus-arbiter can ingest Claude + Codex findings uniformly.
7. **Locale.** Reviewer prompts in harness-maker honor `harness.yaml.locale`. Does Codex follow locale instructions reliably enough that we can pass the same prompt through? Empirical question — needs a fixture test.

---

## 📚 Sources

- OpenAI Codex MCP docs: https://developers.openai.com/codex/mcp
- OpenAI Codex non-interactive (`codex exec`): https://developers.openai.com/codex/noninteractive
- Codex CLI reference: https://developers.openai.com/codex/cli/reference
- Codex CLI features: https://developers.openai.com/codex/cli/features
- Claude Code MCP guide: https://code.claude.com/docs/en/mcp
- `tuannvm/codex-mcp-server` (community wrapper): https://github.com/tuannvm/codex-mcp-server
- `mkXultra/ai-cli-mcp` (multi-CLI wrapper): https://github.com/mkXultra/claude-code-mcp/
- `steipete/claude-code-mcp` (the reverse — Claude as MCP): https://github.com/steipete/claude-code-mcp
- Codex non-interactive goals discussion: https://github.com/openai/codex/discussions/21764
- Headless execution analysis (DeepWiki): https://deepwiki.com/openai/codex/4.2-headless-execution-mode-(codex-exec)
- Practitioner write-up of Claude+Codex pairing: https://medium.com/@sangho.oh/claude-codex-cli-agentic-coding-a98c83ba043e

---

## 🔗 Related Internal Docs

- `[[RESEARCH-codex-shell-invocation]]` — Locked the `codex exec` flag set (`--sandbox`, `--ask-for-approval never`, `-p` ≠ prompt). Reuse directly for Approach 1.
- `[[RESEARCH-codex-usage-guide]]` — General Codex CLI patterns, AGENTS.md, skills, MCP.
- `[[PLAN-codex-target-support]]` — How the `codex` target was added; the asset-render layering applies if we add a `codex_mcp.enabled` conditional.
- `[[PLAN-codex-plan-validator-model-unavailable]]` — Existing precedent for "Claude calls Codex as second LLM" in plan-validator. The pattern there is a clean reference implementation for Approach 1.
- `[[REVIEW-codex-compat-fixes-2026-05-22]]` — Most recent compatibility forensic; check for any newly-broken Codex flag shape before locking the plan.
