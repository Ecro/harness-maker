---
type: research
task_slug: codex-claude-integration
status: complete
created: 2026-09-20
tags: [harness-maker, research, codex, claude, plugins]
mtime_warn_days: 7
libs_fetched: []
sources:
- https://developers.openai.com/plugins/build/plugins
- https://code.claude.com/docs/en/headless
related_docs: ["[[RESEARCH-codex-main-runtime]]", "[[SPEC-codex-main-independent]]"]
summary: Connect native plugin management and a bounded authenticated Claude CLI transport.
---

## 🎯 Recommended Direction
Use the native Codex plugin lifecycle with bundled setup/update skills, a release-pinned Python engine, and explicit plugin/engine/project status. Add a stage-independent Claude transport, then register it with the shared second-opinion configuration, dispatcher and ledger after reconciling the concurrent plan-stage absorption.

This provides reachable user workflows, extending the shipped pure helpers rather than claiming those helpers already perform installation or invocation. Reuse existing project generation and preservation rules.

## 🔍 Refinement Decisions
Discovery lens: user workflow, technical architecture, security/permission boundaries. The operator explicitly requested the harness workflow for actual Claude invocation and Codex installation/update. Prior scope and goals stand; no fresh broad interview is necessary. New task checkout: `.worktrees/codex-claude-integration`, starting from `aef307a3`.

| Local capability | User artifact | Required connection |
|---|---|---|
| Native Codex plugin management | Marketplace and installed package | Bundle discoverable setup/update skills |
| Existing Python generator | Project harness and custom blocks | Run matching engine with Codex target and preserve current choices |
| Existing opinion review and ledger | Frozen diff and findings | Invoke Claude and record provider-specific results |
| Pure Claude parser | Result envelope | Validate actual transport framing before strict parsing |

Memory retrieval surfaced installation UX/model-routing context and test-oracle failure patterns. Second Brain reference/project searches returned no matches. Prior documents supply the broad gap analysis.

## 🛠️ Approaches Found
| Approach | Assumption | Evidence | Trade-off | Compatibility | Risk |
|---|---|---|---|---|---|
| Native CLI plus bundled skills and pinned engine (recommended) | Codex supports plugin add and users have uv | Local Codex 0.155.1 help; official package docs | Three lifecycle steps must be observed independently | Existing make/preservation remains authoritative | medium |
| Copy Claude commands directly into Codex | Slash tools and cache layout match | Contradicted by missing Codex management skills and Claude-specific make resolver | Short implementation, broken clean-home behavior | Poor | high |
| Direct Anthropic API instead of Claude CLI | API credentials/billing available | Not the operator's requested existing Claude Code workflow | Additional auth/dependency and billing surface | Unnecessary | high |

### Verified native interfaces
Local `codex plugin --help`: add/list/marketplace/remove. `plugin install` is rejected. `plugin add PLUGIN@MARKETPLACE --json` installs; `plugin marketplace upgrade NAME --json` refreshes Git snapshots. They are distinct operations. Existing `.codex-plugin/plugin.json` has identity but no skills declaration; the repository has `commands/make.md`, not distributable management skills. Official packaging docs retain compatibility manifests and support root skills directories.

### Actual Claude protocol probe
Local Claude version: 2.1.278. In a fresh temporary directory, ran `claude --print --safe-mode --tools '' --no-session-persistence --output-format json --json-schema ...` with a synthetic public protocol prompt. No project contents or credential values were printed. Two calls returned exit 0. The second call was parsed and returned a TOP-LEVEL EVENT ARRAY ending in exactly one successful `type=result`, `subtype=success`, `is_error=false`, `structured_output={ok:true}`. The first diagnostic assumed an object and therefore reported no envelope; that diagnosis was corrected by the second shape-aware probe.

The existing pure parser accepts only a result object. The transport needs strict framing normalization: accept a result object or a bounded event array with one terminal result; reject missing/duplicate/nonterminal result records. Natural-language assistant messages never substitute for structured output. The successful authenticated probe establishes usable existing authentication in this environment, not universal subscription compatibility or a completed review integration.

Local help says `--bare` ignores OAuth/keychain; do not use it by default. `--safe-mode` preserves normal authentication while disabling customizations. Verify actual installed capabilities, no silent fallback that re-enables tools/hooks. Review supplied context only. Bound stdin, stdout, stderr, deadline and child process cleanup.

### Concurrent integration boundary
`plan-stage-absorption` still has uncommitted edits to models, interview, command_registry, synthesize, presets, shared opinion dispatch and stage templates. It targets spec/execute ownership with six stages. Do not restore hm-plan or alter that checkout. Existing provider enum and ledger only accept codex/antigravity; stages still include plan rather than spec. Build isolated transport/package files first, then reconcile additive provider/stage support against the absorbed contracts. Preserve historical plan ledger rows.

## ⚠️ Pitfalls
- Marketplace refresh alone is not installed package or project regeneration success (native command contracts).
- `+codex` package cachebusters must not become PyPI requirements (shipped bootstrap helper).
- `--bare` would exclude saved OAuth in the local CLI; safe-mode is the proposed authentication-preserving boundary.
- Actual JSON output can be an event array; an object-only adapter rejects a valid successful call (local probe).
- Exit zero, prose or a missing result is not an empty clean opinion (strict parser and official structured-output contract).
- Sequential stdout reads or subprocess.run without bounds can exhaust memory; deadline cleanup must cover child processes.
- Editing shared generator/config/template files while absorption is in flight creates avoidable integration conflicts.

## ❓ Open Questions
The SPEC must settle three public boundaries: the new `claude` provider key, context-only/no-tools authentication-preserving invocation, and native package plus pinned-engine update semantics. Model selection stays explicitly configurable; no new model alias is invented. Minimum capability requirements are tested rather than silently assuming all Claude/Codex versions match this machine. Broad runtime autopilot/session redesign is outside this follow-up.

## 📚 Sources
- https://developers.openai.com/plugins/build/plugins — package layout and native marketplace lifecycle.
- https://code.claude.com/docs/en/headless — JSON Schema results and structured_output.
- Local `codex` 0.155.1 and `claude` 2.1.278 help; synthetic authenticated protocol probes on 2026-09-20.
- `.codex-plugin/plugin.json`, `commands/make.md`, `src/harness_maker/{codex_bootstrap,claude_response,second_opinion_invoke,models,codex_ledger,cli}.py`.

## 🔗 Related Internal Docs
- [[RESEARCH-codex-main-runtime]]
- [[SPEC-codex-main-independent]]
- [[REVIEW-codex-main-independent-2026-09-20]]
