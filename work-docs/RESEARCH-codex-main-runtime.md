---
type: research
task_slug: codex-main-runtime
status: complete
created: 2026-09-20
tags: [harness-maker, research, python, codex, runtime-parity, plugins, second-opinion]
mtime_warn_days: 7
libs_fetched:
  - https://developers.openai.com/plugins/build/plugins
  - https://code.claude.com/docs/en/headless
sources:
  - https://developers.openai.com/plugins/build/plugins
  - https://code.claude.com/docs/en/headless
related_docs:
  - "[[PLAN-codex-target-support]]"
  - "[[RESEARCH-codex-usage-guide]]"
  - "[[PLAN-second-opinion-oracle-polyglot]]"
  - "[[RESEARCH-codex-loop-execute-gaps]]"
  - "[[PLAN-plugin-vs-generator-2026-05]]"
summary: "Separate main runtime, opinion providers, and distribution; prove Codex-only lifecycle parity."
---

## 🎯 Recommended Direction

Make Codex a first-class main runtime by separating runtime capabilities, second-opinion providers, and plugin/engine distribution while retaining the shared Python engine and generated project assets.

The primary value is a complete user workflow: install and update from Codex, configure a project, execute its stages, receive an independent Claude Code opinion, and resume or finish without opening Claude Code as the orchestrator. Codex support already exists; replacing it wholesale would discard substantial work. The missing contracts are lifecycle completeness, orchestration parity, session ownership, and reverse-direction review. Recommendations below are exploratory; PLAN must lock the architecture.

### Concurrent-work correction — 2026-09-20

The operator identified ongoing work in `hm/plan-stage-absorption`. Its approved
`SPEC-plan-stage-absorption.md` and current uncommitted implementation supersede the
seven-stage assumption for future design: **research → spec → execute → review → verify →
wrapup**. SPEC owns user decisions and irreversible contracts; execute Step 0 authors the
PLAN document without a second interview. The PLAN artifact survives, but `hm-plan` and
`plan-validator` do not. `spec-validator` is conditional, single-pass, and advisory.

Apply this correction to G02/G06/G11, the workflow matrix, acceptance probes, and open
questions below. Their references to the seven-stage baseline remain historical observations,
not requirements to restore the retired stage. Claude opinion integration should target
**review and spec**, preserving legacy `plan` telemetry compatibility. Do not reinstate a
blocking plan-validation gate. Irreversible decisions belong in SPEC; reversible implementation
choices and phases belong in the execute-authored PLAN.

Read-only inspection snapshot: the absorption worktree HEAD was `865e3ef5`, one commit behind
the research baseline, and the absorption implementation was still staged/unstaged/untracked.
A diff against current main therefore includes unrelated changes from the missing base commit;
use its own HEAD to inspect the task's edits. No merge, refresh, or edit of that worktree was
performed. Main and this task still expose the old generated skills until the absorption lands
and assets are regenerated.

Observed integration issue in that in-progress snapshot: spec renders `--stage spec`, but both
argument parsers in `second_opinion_invoke.py` accept only `review|plan|health`, and
`codex_ledger.py:OpinionRecord.stage` has the same restriction. Extracting the two parser
functions with Python AST and passing complete arguments with `--stage spec` produced exit 2
for both, before any model call. Additive `spec` support must cover invocation, disposition,
and ledger validation while retaining historical `plan`. This is an in-flight finding, not a
claim about the other session's final implementation.

Merge hotspots for our later implementation are `models.py`, `interview.py`, `presets.py`,
`synthesize.py`, `autopilot_caps.py`, spec/execute templates, second-opinion dispatch, Codex
agent metadata, and their render/snapshot tests. Sequence orchestration and stage-facing
provider work after the absorption lands. Packaging discovery and provider transport design
can proceed independently, but integration must use the new stage contracts. The absorption
does not itself add Claude as an opinion provider, remove Codex's auto-advance exclusion,
replace the Claude environment-file identity channel, or complete Codex plugin management.

### Problem boundaries and evidence baseline

- User requirements are settled: Codex can be main; Claude Code can be second opinion; installation and updates can be driven from Codex. Claude Code main must remain supported.
- Baseline inspected: commit `e5dfb2f3fe06da0d424226a29d0288816ec8d3bc`, package manifests `0.58.0`; local CLI probes: `codex-cli 0.155.1`, Claude Code `2.1.278`.
- Research ran in `.worktrees/codex-main-runtime`. The base checkout already contained unrelated modifications. Those were not incorporated into this research branch.
- Static source inspection and read-only CLI probes establish the findings below. No authenticated model invocation, plugin installation, plugin update, or complete pipeline was exercised. Accordingly, this is an evidence-backed gap inventory, not a certification of every integration surface.
- `.claude/harness.yaml` and shared `.claude/` data paths are existing storage conventions, not proof that a Claude process is required. A directory migration is outside the necessary first release.
- CLI support is the initial verification target. Codex desktop/IDE discovery, restart, trust, and policy behavior need their own compatibility evidence before a parity claim.

### Confirmed gaps and follow-up verification inventory

Priority means implementation dependency and user impact, not security severity. Rows marked **audit** are unresolved verification obligations rather than established broken behavior.

| ID | Priority / state | Evidence and user consequence | Proposed improvement and completion evidence |
|---|---|---|---|
| G01 | P0 / confirmed | `models.py:415,511`, `second_opinion_invoke.py:790`, `codex_adapter.py:323`, and `second_opinion_dispatch.md.j2:61` enumerate only Codex and Antigravity. `SecondOpinionConfig(models=["claude"])` raises a literal validation error. | Add Claude Code through config, interview, serialization, invocation, normalized findings, dispatch, PIDA, consensus, and ledger. A Claude finding must become an accepted independent vote through the complete path. |
| G02 | P0 / confirmed | `templates/agents/_partials/stage_end_summary.md.j2:24` excludes Codex; the advance branch invokes Claude's `Skill` tool. The picker still arms in Codex. An armed marker therefore does not establish automatic progress. | Share deterministic boundary decisions, with runtime-specific stage loading/dispatch. Verify research→spec→plan→execute→review→verify→wrapup transitions, judgment stops, caps, and interruption/resume on Codex. |
| G03 | P0 / confirmed | `hooks/sessionid_envfile.py:main` reads `CLAUDE_ENV_FILE`; missing input is a no-op. This session had no `HM_SESSION_ID`, and `autopilot status` returned `degraded-idless`. | Introduce a tested runtime session identity channel, or an explicit persisted per-run identifier propagated to all calls. Two Codex sessions and one Claude session must not share task ownership, receipts, or stop state. Never invent a host environment variable. |
| G04 | P0 / confirmed packaging gap; install outcome untested | `.codex-plugin/plugin.json` exists but is metadata-only; there is no root `skills/` directory or `.agents/plugins/marketplace.json`. The existing marketplace is Claude's `.claude-plugin/marketplace.json`. A repository clone is not evidence of Codex bootstrap skill discovery. | Publish a supported Codex marketplace and distributable bootstrap skills. In an isolated clean home, install from Codex and discover make/update/health without pre-generated project skills or Claude binaries. |
| G05 | P0 / confirmed lifecycle split | README installation guidance prefers Claude marketplace when `claude` is available; the Codex manifest says the Python engine needs a separate PyPI installation. `commands/make.md` is a Claude command entry. | Provide a Codex-native bootstrap flow with engine presence/version checks and a usable PyPI fallback. Separate plugin update, Python engine update, and project regeneration; report all three resulting versions/states. |
| G06 | P1 / confirmed entry-point asymmetry | `synthesize.py:_codex_stage_skills` emits the seven atomic stages; `_codex_files` adds loop, batch, help, and shared skills. Management commands such as configure/health/uninstall are not mapped by that stage generator. | Inventory every public management operation and expose appropriate Codex skills or CLI-backed flows, including fresh make, configure, update preview/apply, health, and uninstall. Check discovery and behavior, not only file presence. |
| G07 | P1 / confirmed portability exposure | This project's generated skills invoke an exact `$HOME/.claude/plugins/cache/.../0.58.0` engine path. `synthesize.py:_compute_install_ref` already supports multiple install references including PyPI, so this is not universally hardcoded. | Preserve the resolver; define how generated references remain valid when plugin caches move or old versions disappear. Test generated hooks/commands in a second home and after an upgrade. |
| G08 | P1 / audit | Codex hooks exist, including SessionStart and Stop, and existing target work documents deliberate differences. Session identity already demonstrates that shared hook code can be a no-op on another host. | Test actual payloads, tool names, denial behavior, Stop/compaction flush, worktree paths, and receipt emission on the supported Codex version. Do not equate a rendered hook file with a running enforcement mechanism. |
| G09 | P1 / confirmed provider-specific optional evaluation | `llm_judge.py:AnthropicJudgeClient` uses the Anthropic API and Claude defaults; `spec_quality.py` and `spec_inventory/reverse_map.py` also name Claude models. The judge supports a protocol and documents prompt-native evaluation. | Audit each caller before changing it. Offer current-runtime prompt evaluation or an explicitly selected provider; label any optional API requirement. Codex-only core workflow must not silently require an Anthropic key. |
| G10 | P1 / audit | Model routing already separates target-specific fields in `models.py`; second-opinion configuration is orthogonal to targets. Here the configured opinion is Codex even while Codex is main. | Distinguish main runtime, emitted targets, model identity, and opinion provider. Make same-provider review explicit and avoid presenting it as independent cross-provider verification. Preserve intentional same-provider configurations. |
| G11 | P1 / confirmed verification shortfall | `tests/e2e/test_plugin_live.py` launches real Claude; `tests/codex-compat/MANUAL_CHECKLIST.md` describes smoke-only coverage and permits discovery/dispatch deferral. Structural and Codex-specific tests already exist. | Add clean-home Codex lifecycle and reverse-opinion acceptance suites; require core install/discovery/dispatch to pass. Keep fast mocked provider contracts separate from optional authenticated live probes. |
| G12 | P1 / audit | Existing adapters and ledger names are Codex-oriented, although Antigravity already shares them. `second_opinion.failure_policy` currently permits only `warn-and-proceed`. | Preserve stable finding identities and backward compatibility while adding provider attribution and distinct failure reasons. A configured but failed Claude opinion must not look like a successful clean review. Decide whether strict opinion requirements are configurable. |

### Local capability × user artifact

| User task / artifact | Existing local capability | Missing user-facing completion |
|---|---|---|
| Install plugin in a fresh project | Codex manifest, Python package, make engine | Discoverable Codex bootstrap with no Claude install dependency |
| Update plugin and keep project customizations | Version metadata, install resolver, hash/block merge | One guided Codex flow covering plugin, engine, generated artifacts, and recovery |
| Maintain AGENTS.md, skills, agent TOMLs | Codex generator and existing compatibility tests | Management-entry parity and supported-version diagnostics |
| Work from SPEC/PLAN through REVIEW | Seven native stage skills; persistent task worktrees | Automatic transitions, reliable session ownership, resume verification |
| Use Claude's independent review in REVIEW/PLAN | Shared invoker, schema adapters, oracle/PIDA, consensus | Claude transport and end-to-end attribution/vote path |
| Retain memory and evidence across sessions | Wiki/failures, receipts, observability, Second Brain | Codex lifecycle validation for flush, retrieval, receipt and telemetry completeness |

Official plugin documentation describes the user's package/discovery/marketplace workflow; the repository README and manual checklist show where this project's current workflow diverges. This mapping covers the user-workflow discovery requirement without substituting model benchmarks for product evidence.

## 🔍 Refinement Decisions

- Discovery lens: **User-workflow / product opportunity first**, then **Technical architecture / implementation**, with **Risk / security** limited to subprocess capabilities, session isolation, and update preservation.
- No deep interview was needed: the three requested outcomes are concrete. “All gaps” is interpreted as the complete main-runtime lifecycle and its supporting contracts; unrelated new features are excluded.
- Keep shared engine, data layout, worktree model, block-merge preservation, and the existing Codex generation investment unless PLAN identifies a necessary exception.
- Second Brain searches for `Codex` returned three reference leads and no project notes. The session-export reference is relevant to G03 but was not read in full, so code and local status output remain the primary evidence.
- Relevant retrieved memory: `[fail:render] recipe-relative-path-breaks-in-worktree` (resolve assets against the correct root); `[wiki:gotcha] wrapup-marker-discipline-silent-loss` (preserve user blocks during regeneration); `[wiki:model-routing-multi-ide]` (existing routing precedent); `[fail:test] assertion-invariant-over-named-dimension` (tests must distinguish provider/runtime variants); `[fail:test] snapshot-regen-inside-worktree` (do not rely on stale snapshot instructions); `[fail:test] fix-introduced-defect-passes-all-gates` (green checks alone do not prove integration contracts).
- Configured `ref_folders` is empty; no external refdocs-folder search was needed.
- Autopilot was armed by the current skill's degraded-idless branch. Codex research output contains no auto-advance block, so this research does not claim that arming enabled stage transitions.

## 🛠️ Approaches Found

| Approach | Assumption | Evidence | Trade-off | Compatibility | Risk |
|---|---|---|---|---|---|
| A. Patch individual Codex prompts and add a Claude branch | Few remaining differences and a stable CLI surface | Existing adapters and Codex templates make a small initial patch feasible; G02–G06 show several independent missing contracts | Fast first demo, but duplicated dispatch and drifting lifecycle instructions | High initially; harder to maintain across surfaces | Medium–high |
| **B. Shared capability contracts with runtime/provider adapters** | Most workflow semantics belong to the engine; host operations differ | Existing deterministic boundary CLI, shared generator, opinion invoker, and provider adapters provide extension points | Moderate design and migration work; reusable tests and explicit degraded behavior | Highest fit with current generator architecture | Medium |
| C. Move all execution into a new external agent controller | A standalone controller should own every conversation and transition | Could centralize state and providers, but would duplicate orchestration already present in native stages | Largest engineering, authentication, lifecycle, and UX burden | Lowest near-term compatibility | High |

Choose B provisionally. Do not require a broad framework before shipping: first implement explicit contracts at the current extension points, then consolidate duplication supported by evidence.

### Suggested work packages and acceptance probes

1. **Capability and lifecycle baseline:** enumerate runtime-supported operations and CLI versions; add clean-home diagnostics. Acceptance: unsupported features produce actionable status, not a silent no-op.
2. **Codex installation and management:** marketplace/package/bootstrap skills, engine resolution, management entries, update preview/recovery. Acceptance: with `claude` absent from PATH, install→make→configure→update→health→uninstall works and a custom user block survives update. Repeat with an existing project and a stale engine reference.
3. **Claude opinion provider:** config round-trip, transport, output normalization, attribution, oracle/PIDA, consensus. Acceptance: Codex main receives a valid Claude finding, rejects a refuted finding, and records timeout/auth/malformed-output failures distinctly. Claude main→Codex opinion remains green; Antigravity remains compatible.
4. **Codex orchestration/session parity:** stage transitions and session identity; audit hooks, worktrees, receipts, resume and stops. Acceptance: concurrent sessions remain isolated; a failed gate cannot advance; interrupted work resumes the correct task and stage.
5. **Optional evaluation and documentation closure:** audit Claude API assumptions, configuration and observability terminology, live checks and compatibility claims. Acceptance: no undocumented Claude runtime or credential requirement in the core Codex path.

Installation and provider work can be designed independently after agreeing on version and capability contracts. Full pipeline acceptance depends on both lifecycle and orchestration completion. These are candidate SPEC slices, not an approved implementation plan.

### Claude transport feasibility

The official headless interface supports `claude -p`, JSON output and JSON Schema; schema results are carried in `structured_output`. A provider adapter is therefore feasible without requiring Claude to orchestrate the parent workflow. Parse and validate the envelope before normalizing findings. Local `claude --help` confirms print, schema, tool, settings, MCP and session controls. [Claude programmatic usage](https://code.claude.com/docs/en/headless)

Start with a bounded prompt containing the diff and relevant context, and restrict tools explicitly. Add file-reading only if demonstrated review quality needs it. Decide subscription/OAuth compatibility before choosing hermetic flags: the retrieved official page says bare mode skips OAuth/keychain, while the local CLI's help describes different bare-mode authentication behavior. This discrepancy is unresolved and requires version-pinned testing. Do not ship a universal bare-mode recipe based on either source alone.

### Packaging and update feasibility

The official packaging guide supports the legacy `.codex-plugin/plugin.json` layout and documents marketplace registration plus `codex plugin marketplace upgrade`. It also describes a newer portable root manifest. Keep compatibility until a minimum version is selected. Local CLI help independently confirms `plugin add/list/remove` and `marketplace add/list/upgrade/remove`; it exposes no top-level `plugin update` command. [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)

Proposed update contract: resolve requested release → preview plugin/engine/project changes → refresh/install the matching package and engine → regenerate with preservation → verify discovery, versions and health → report recovery instructions on partial failure. Plugin refresh behavior, project regeneration, and engine installation are distinct operations; no successful one should be reported as completion of all three. This sequence is a proposal, not an installation procedure tested in this research.

## ⚠️ Pitfalls

1. **Counting generated files as runtime parity.** Existing files and structural tests do not prove plugin discovery, automatic stage transitions, hook execution, or clean-home bootstrap. G02/G03 are concrete counterexamples.
2. **Adding only `claude` to a configuration enum.** Dispatch, adapter validation, identity, source attribution, PIDA and consensus must all participate; otherwise an apparently enabled provider contributes no vote.
3. **Confusing package refresh with an updated harness.** The plugin, installed engine, and generated project assets can hold different versions (G05/G07).
4. **Inferring session identity from a shared file or PID.** Parallel sessions, restart and worktree moves require a stable, explicit contract; never claim isolation for the shared degraded marker.
5. **Treating a read-only prompt as an execution boundary.** Review tools and MCP/settings/hooks must be constrained by the actual provider adapter, and the exact behavior verified for its supported CLI version.
6. **Assuming latest docs match an installed binary.** Bare-mode authentication differs between the retrieved documentation and local help; preserve the uncertainty until an authenticated probe resolves it. [Claude programmatic usage](https://code.claude.com/docs/en/headless)
7. **Silently skipping independence.** Same-provider review, failed external invocation, an empty valid finding set, and rejected findings are different outcomes; telemetry and summaries should preserve that distinction.
8. **Renaming `.claude/` as the main fix.** Paths are a compatibility convention; runtime coupling is in behavior. A migration would add risk without itself enabling the requested workflows.
9. **Reintroducing worktree-relative assets or destructive regeneration.** Retrieved project failures already document missing schema paths and user content lost outside preservation markers.

## ❓ Open Questions

The user does not need to restate the three requested outcomes. PLAN should settle these remaining implementation choices:

1. What minimum Codex CLI and Claude Code versions are supported, and which desktop/IDE surfaces are included in the first parity claim? Recommend CLI-first with explicit surface coverage.
2. Must Claude second opinion work with a Claude subscription login alone? Recommend yes if the supported CLI permits a constrained, isolated invocation; confirm the local/documentation bare-mode discrepancy first.
3. Which Codex-native mechanism loads the next stage, and which host/session identity source is stable across subprocesses and resume? Prototype these before committing to a driver abstraction.
4. Should a requested independent opinion be mandatory or warn-and-proceed? Preserve the existing default for migration, but make the chosen policy and missing vote visible.
5. Should plugin and engine releases be version-locked or compatibility-ranged? Recommend a lock for the initial release, with explicit partial-failure recovery and existing user-edit preservation.

## 📚 Sources

### External sources actually opened

- [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins) — package layout, Codex compatibility manifest, skill discovery, marketplace and refresh lifecycle. Fetched 2026-09-20. The HTML page was usable; fetching its `.md` variant through the web tool failed, so no claims rely on that failed fetch.
- [Anthropic: Run Claude Code programmatically](https://code.claude.com/docs/en/headless) — print mode, schema output, context loading, authentication caveat. Fetched 2026-09-20; local bare-mode authentication help differs and remains unresolved.

### Local reproducible evidence

- `codex --version`, `codex plugin --help`, `codex plugin add --help`, `codex plugin marketplace --help`; `claude --version`, selected `claude --help` options.
- Pydantic probe: constructing `SecondOpinionConfig(models=["claude"])` fails with allowed values `codex` or `antigravity`.
- `hm autopilot status --root . --session-id ""` returned `active: false`, `reason: degraded-idless`, `session_scoped: false` before the skill's arming instruction.
- Source locators in G01–G12; `README.md:64–80,153`; `.codex-plugin/plugin.json`; `.claude-plugin/marketplace.json`; `src/harness_maker/synthesize.py:_compute_install_ref,_codex_files,_codex_stage_skills`.
- No product tests were run because this stage changed only the research document. Live acceptance probes above remain downstream work.

## 🔗 Related Internal Docs

- [[PLAN-codex-target-support]] — existing generated asset design, shared configuration path and intentional hook differences.
- [[RESEARCH-codex-usage-guide]] — earlier operating guidance; time-sensitive CLI and feature claims require current verification.
- [[PLAN-second-opinion-oracle-polyglot]] — oracle/toolchain and base-root versus diff-root contracts to retain.
- [[RESEARCH-codex-loop-execute-gaps]] — related prior work located for downstream comparison; not substantively re-read here.
- [[PLAN-plugin-vs-generator-2026-05]] — generator/distribution precedent referenced by the Codex target plan; revisit before changing packaging architecture.
