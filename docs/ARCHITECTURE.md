# Architecture

This document describes the harness-maker system at a level where you can understand the design without reading the source. For implementation details, follow the file-path references into `src/harness_maker/`. For the full normative specification, see [`TECH_SPEC.md`](../TECH_SPEC.md).

## 1. What harness-maker Is

A **meta-tool**. The Claude Code ecosystem ships a `.claude/` directory inside every project — that directory contains commands, skills, agents, hooks, settings, and observability glue. harness-maker is a Claude Code plugin whose only job is to **generate, refine, and keep fresh** that `.claude/` directory, tailored to the host project's stack, scale, and lifecycle.

Three design commitments shape every decision below:

1. **Single command.** Users invoke `/harness-maker:make`. Everything else is a flag (`--audit`, `--add`, `--remove`, `--promote`).
2. **Two presets, deep override.** `Side` (1 reviewer, lean) and `Production` (5 reviewers, verify-required) cover ~90% of cases. The remaining 10% comes from 10+ override dimensions surfaced in the interview.
3. **Brownfield-safe.** harness-maker never silently overwrites user edits. Provenance frontmatter (M13) and the Reconciler (M2) form a hash-based ours/theirs decision system.

## 2. Data Flow

```
                       ┌──────────────────────┐
   user invokes        │  /harness-maker:make │
   ──────────────────▶ │  [--audit|--add|...] │
                       └──────────┬───────────┘
                                  │
                                  ▼
            ┌─────────────────────────────────────────┐
            │  M1 Pipeline                            │
            │  ─────────                              │
            │  Profiler  ──▶  ProjectProfile          │
            │  (stack, scale, lifecycle, brownfield?) │
            │       │                                 │
            │       ▼                                 │
            │  Interviewer  ──▶  HarnessConfig        │
            │  (preset + 10+ override dims, locale-   │
            │   first via i18n.py)                    │
            │       │                                 │
            │       ▼                                 │
            │  Synthesizer  ──▶  Blueprint            │
            │  (deterministic preset → FileEntry[])   │
            │       │                                 │
            │       ▼                                 │
            │  Renderer  ──▶  files in memory         │
            │  (Jinja2 + provenance frontmatter,      │
            │   M11 context-lint at render time)      │
            └────────────────┬────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
   greenfield                          brownfield
            │                                 │
            │                                 ▼
            │                  ┌──────────────────────────┐
            │                  │  M2 Reconciler           │
            │                  │  index existing .claude/ │
            │                  │  hash-compare via M13    │
            │                  │  per-conflict keep/replace/both
            │                  │  backup → .backup-<date>/│
            │                  └──────────┬───────────────┘
            │                             │
            └─────────────┬───────────────┘
                          │
                          ▼
            ┌──────────────────────────────────────────────────────┐
            │  ADD-only apply to <project>/.claude/                │
            │  (+ .cursor/, .codex/, .agents/, AGENTS.md when targeted) │
            └────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
        ┌────────────────────────────────────────────────────┐
        │  Generated harness (the runtime)                    │
        │  ──────────────────                                 │
        │  harness.yaml          ◀── single source of truth   │
        │  settings.json         ◀── permissions               │
        │  commands/hm/                                       │
        │    research|spec|plan|execute|review|wrapup|verify  │
        │      ◀── M3 atomic stages                           │
        │    <user-named>.md  ◀── M3 fused workflows          │
        │    loop.md          ◀── M7 autoloop driver          │
        │    ai-readiness.md  ◀── M5 scored readiness report   │
        │    refresh.md       ◀── M4 anti-rot, manual confirm │
        │  skills/  (11)      ◀── including verify-before,    │
        │                          conditional-router,        │
        │                          refdocs-search,            │
        │                          worktree-isolator, ...     │
        │  agents/            ◀── M12 reviewer/executor       │
        │                          privilege separation       │
        │  hooks/hooks.json   ◀── telemetry                    │
        │  .worktrees/        ◀── M9 git worktree isolation   │
        │  observability/                                     │
        │    dashboard.md                                     │
        │    metrics-YYYY-MM-DD.jsonl ◀── 100% local         │
        │       telemetry, daily-rotated (ADR-103, 0.7.1)     │
        │    refresh/raw-*.jsonl ◀── M4 crawl evidence        │
        │    security/findings-* ◀── M10 7 security gates     │
        └────────────────────────────────────────────────────┘
                                 │
                                 ▼
                  user runs /hm:* against their code
                  (autoloop: M7 + M8 verify-before-completion)
                                 │
                                 ▼
                  weekly /hm:refresh — M4 anti-rot crawl
                  → AskUserQuestion (always manual)
```

## 3. The 14 Mechanisms (M1-M14)

Every mechanism below maps to a module under `src/harness_maker/` and at least one verification check in `.claude-verify.sh`.

### M1 — Profile → Interview → Synthesize → Render Pipeline

The four-stage core. Each stage has a single responsibility and a typed handoff.

- **Profiler** (`profile.py`) inspects the project root for signals: `pyproject.toml`, `package.json`, `Cargo.toml`, `*.overlay`, `.github/workflows/`, presence of `.claude/`, presence of standalone `TECH_SPEC.md`, vault membership. Emits `ProjectProfile`.
- **Interviewer** (`interview.py`) recommends a preset based on the profile, then runs an interactive interview across 10+ override dimensions: workflow naming, reviewers, models, autoloop, anti-rot, worktree, security, context-lint, memory, caching. Also captures `targets` (Claude Code / Cursor) and `recommended_model`. Locale-first; English is the default (`DEFAULT_LOCALE = "en"`) with Korean built-in and unknown locales silently falling back to English, via `i18n.py`. Emits `HarnessConfig`.
- **Synthesizer** (`synthesize.py`) is **purely deterministic** — given a `HarnessConfig`, it produces the same `Blueprint` (a list of `FileEntry`) every time. No LLM call here; this guarantees reproducibility and snapshot testability.
- **Renderer** (`render.py`) walks the `Blueprint`, loads each Jinja2 template, injects context, prepends provenance frontmatter (M13), and writes the result.

The split lets you swap the interview UX (CLI prompt vs `AskUserQuestion`) without touching synthesis, and snapshot-test the synthesizer in isolation.

### M2 — Reconciler (Brownfield Conflict Resolution)

When `.claude/` already exists, the Renderer doesn't write blindly. The `Reconciler` (`reconcile.py`):

1. Indexes every existing file under `.claude/`.
2. Computes the new Blueprint's intended file set.
3. For each collision, reads the existing file's `content_hash` from its provenance frontmatter (M13). If hashes match, the existing file is "ours" — safe to overwrite. If they differ or the frontmatter is missing, it's "theirs" — treat as user-edited.
4. Emits a `ConflictItem` per collision with `decision: keep | replace | both`. In autoloop mode, the decision is automatic from hash comparison; in interactive mode, the user picks.
5. Backs up the entire `.claude/` to `.backup-<date>/` before applying anything.
6. Apply is **ADD-only** — no in-place mutation, no deletes from disk (deletes happen via the backup-and-rewrite pattern).

### M3 — Workflow Engine (Atomic + Fused)

There are exactly **7 atomic stages**: `research`, `spec`, `plan`, `execute`, `review`, `wrapup`, `verify`. Each is a Jinja2 fragment under `templates/stages/<stage>.md.j2` and is **always** exposed as `/hm:<stage>`.

**Workflows** are user-named sequences of stages. The synthesizer emits a workflow seed per preset (e.g. `dev = [plan, execute, review, wrapup]`). The `workflow_fuse.py` module concatenates the relevant stage fragments into a single command file rendered to `.claude/commands/hm/<workflow>.md`. Re-running `/harness-maker:make` extends `harness.yaml.workflows` and re-fuses.

This decouples "what the workflow does" from "how the user calls it" — the same atomic stages back every workflow.

### M4 — Anti-rot Pipeline

The Claude Code ecosystem moves weekly. Skills, agents, and best practices that were optimal on day 1 rot into liabilities by day 90. M4 fights that.

Three stages:

1. **Crawl** (weekly): four sources — Anthropic blog/changelog, GitHub releases (`anthropics/claude-code` by default), arxiv (cs.SE / cs.CL / cs.CR), OSV.dev. Implemented under `src/harness_maker/crawler/`. Raw output to `observability/refresh/raw-<date>.jsonl`.
2. **Filter** (`relevance.py`): LLM scores each item for project-relevance. Threshold starts at 0.7 and adapts ±0.05 based on the recent accept/reject ratio.
3. **Propose** (`templates/commands/hm/refresh.md.j2`): `/hm:refresh` opens an `AskUserQuestion` per surviving item — accept, reject, or defer. **Manual confirm is non-negotiable**: there is no `--auto-apply` path.

This means harness-maker stays current without ever silently changing the user's runtime.

### M5 — Monitoring (3 Metrics)

Three metrics are computed and surfaced in the `/hm:ai-readiness` report:

- **Efficiency** — cache hit % per turn. Computed from telemetry hook output (PostToolUse) with a hybrid schema that works across Claude Code and Cursor IDE (0.5.4+). 0.7.1 (ADR-103) rotates the on-disk file daily as `metrics-YYYY-MM-DD.jsonl`; readers walk dated shards newest-first via `_metrics_io.iter_recent_entries` and fall back to the legacy `metrics.jsonl` for pre-0.7.1 entries.
- **Health** — 0-100 score across 6 dimensions: docs, tests, CI, observability, security, governance. Implemented in `readiness.py`. Drills down into `agent_quality.py`, which assigns each agent a Platinum/Gold/Silver/Bronze rating against a fixed rubric. A "ceremony penalty" deducts points when an agent has high-process / low-output behavior.
- **fresh** — days since the last `/hm:refresh` accepted at least one proposal.

A **SessionStart drift reminder** hook (`hooks/sessionstart_drift.py`) fires on every session open and warns if the running harness-maker version differs from the version that rendered the harness — alerting users to re-render after a plugin update (0.5.6+).

The detector (`relevance.detect_version_drift`) compares `harness.yaml.harness_maker_version` (the **stamped** version, formerly named `installed` — renamed in 0.6.2 REVIEW M2 to remove a semantic inversion) against `relevance.latest_installed_version()`, which scans `~/.claude/plugins/cache/harness-maker-local/harness-maker/<v>/` for the highest semver-parseable directory name. **Why scan the cache instead of using the imported `__version__`** (0.6.2 P6): `/hm:refresh` is rendered as a Jinja template that runs with `uv run --with /path/to/<render-time-version>`, pinning its in-process `__version__` to the version that *rendered* the slash command. The SessionStart hook runs against the live plugin so its `__version__` is current. The two import paths therefore see different `__version__` values; calling the same `detect_version_drift` would return different verdicts. Routing both through `latest_installed_version()` (an external truth source) makes them agree. The function is `@functools.cache`-decorated for sub-100ms session-start latency, with a top-K cap (10) on the cache scan to bound worst-case syscalls on long-lived installs.

All telemetry stays local — `metrics-YYYY-MM-DD.jsonl` is never transmitted. 0.7.1 (ADR-107) added a `tool_input` whitelist for the persisted entries: only `path`, `file_path`, `command`, `target`, `database`, `url`, `query` survive; values are scanned for known-secret prefixes (`sk-`, `ghp_`, `AKIA`, `Bearer …`) and redacted *before* a 256-char cap to ensure a partial-token tail cannot survive truncation. The cwd resolution chain is env-var-first (`CLAUDE_PROJECT_DIR` → `CURSOR_PROJECT_DIR` → typed `workspace.current_dir` → `os.getcwd()`); the bare stdin `cwd` field is intentionally NOT consulted, since prior to 0.7.1 a poisoned PostToolUse payload could redirect metrics writes via that field (ADR-102).

### M6 — Conditional Router

When `/hm:review` runs, it doesn't blindly call every reviewer. The `conditional_router.py` module inspects the changed-file paths and routes:

- `auth/` or `.env` → security reviewer
- `worker/`, `thread/`, `isr/` → concurrency reviewer
- `*.tsx`, `ui/` → UX reviewer
- perf-critical paths (configurable per project) → performance reviewer
- everything → code reviewer (always)

Override: set `harness.yaml.reviewers.routing: always-all` to call every reviewer on every diff.

### M7 — Autoloop Driver

`/hm:loop "<goal>" [--mode feature|improve] [--time 8h] [--max-iter 30] [--per-iter-workflow X] [--dry-run]` runs an unbounded-token, time-and-iteration-bounded loop. The command prompt drives runtime orchestration; `autoloop_driver.py` supplies typed schema and dev-time tests.

Two modes:

- **feature** (default) — driven by a goal or `--spec` file; coverage-driven adaptive interview extracts features; iterates until all features pass or caps fire.
- **improve** — driven by a quality target or `--target` path; reviews first, fixes only when the current state does not already meet the exit checklist.

Each iteration:

1. Allocates a per-loop worktree at loop start (M9); reuses it for all iterations (0.5.5+).
2. Runs the chosen per-iteration workflow (default: `exec-rev`). Wrapup runs once at loop close, not per iteration.
3. Runs the 4-gate convergence check: mechanical commands, per-criterion LLM judgment, regression comparison, and a persisted two-iteration streak.
4. Calls `/hm:verify` (M8) before completion.
5. Cleans up on success; preserves on failure.

Safety: every 5 iterations the driver pings the user; time, iteration, repeated-failure, repeated-feature, and ambiguity safety rails stop the loop before it spins indefinitely.

### M8 — Verify-Before-Completion Gate

`verify.py` is invoked automatically before `/hm:wrapup` finishes (and before each autoloop iteration completes). The checklist:

- PLAN/SPEC requirements satisfied
- Regression gate passes
- Health hasn't dropped more than 5 points
- Anti-rot has zero pending high-severity proposals
- Security has zero high-severity findings
- Worktree merges cleanly back to base

Required in the `Production` preset; optional in `Side`.

### M9 — Worktree Isolation

`worktree.py` integrates `git worktree`. By default `/hm:execute` (and optionally `/hm:plan` in `Production`) runs inside a fresh worktree under `.worktrees/<workflow>-<timestamp>/` at the project root. The LLM may only write inside that worktree — enforced by M12's executor agent permissions.

`/hm:loop` allocates **one shared worktree per loop run** (not per iteration), reducing branch churn (0.5.5+). `sibling_repos` in `harness.yaml` lets the same isolation session create matching worktrees for related repositories, so cross-repo changes can be reviewed and merged as one logical unit. Cleanup uses prefix-match (`phase-*`, `autoloop-*`, `execute-*`) so harness-maker never removes worktrees created by Cursor or other tools in the same `.worktrees/` directory.

Successful runs cleanup the worktree after merging back. Failed runs preserve the worktree as evidence.

### M10 — 7 Security Gates

Implemented in `security_scanner.py`. Findings are written to `observability/security/findings-<date>.jsonl`.

| Gate | Technique | Trigger |
|---|---|---|
| **secrets** | regex + entropy (gitleaks-style) | `pre_commit`, `pre_wrapup`, `refresh` |
| **permissions** | `settings.json` `allow` over-grant detection | `refresh`, `/harness-maker:make` |
| **hook injection** | `hooks.json` AST scan for dangerous commands (`rm -rf`, `curl \| sh`, `eval`) | `pre_wrapup`, `refresh` |
| **dependency CVEs** | OSV.dev lookup against `package-lock.json`, `Cargo.lock`, `requirements.txt` | weekly |
| **hallucination** (0.7.0+) | AST scan for non-existent imports. 0.7.1 (ADR-105) switched to a pure-filesystem check — `_is_available` walks `sys.path` for `<pkg>/__init__.py` / `<pkg>.py` / `<pkg>/` and never imports the package, so adversarial sys.path entries cannot trigger `__init__.py` side-effects on LLM-generated code. `@functools.lru_cache(maxsize=512)` memoises the lookup; guarded `try/except ImportError` and `except` handler imports are downgraded to P2. | `pre_wrapup` |
| **prod-name guard** (0.7.0+) | Cross-tool sequence detection: walks recent PostToolUse entries via `_metrics_io.iter_recent_entries` and flags windows of N tool calls whose `tool_input.target` contains production-only patterns (`prod`, `production`, the actual deployed bucket name, etc.). 0.7.1 rewrote the matcher with a `collections.deque(maxlen=window)` sliding window for O(N) scan. | `pre_wrapup` |
| **prompt injection** | hidden-instruction pattern detection + reviewer/executor privilege split (M12). Regex first pass + LLM second pass via `scan_prompt_injection_llm`. On any LLM transport error the gate degrades to regex-only with a warning. | LLM call boundary |

### M11 — Context Lint

`context_lint.py` runs at render time. Before the Renderer writes a file, the lint checks length and importance density. On overrun: warn and propose an automatic summary. Configurable via `harness.yaml.context_lint.strict`.

### M12 — Privilege Separation

Reviewer agents and executor agents have **structurally different permissions** declared both in their YAML frontmatter (so Cursor 2.5+ enforces per-agent — parent → subagent permission inheritance is broken in Cursor) and in the project's `settings.json`:

- **Reviewer** (`templates/agents/code-reviewer.md.j2` and 4 siblings):
  - `allow: [Read(*), Grep(*), Glob(*), Bash(git diff:*), Bash(git log:*), Bash(git status:*)]` — read-only diff inspection.
  - `deny: [Write(*), Edit(*), Bash(rm:*), Bash(curl:*), Bash(npm:*), Bash(eval *), Bash(python:*), Bash(node:*), Bash(sh:*), Bash(bash:*)]`. The interpreter denies (added 0.6.2 REVIEW M7) close a bypass where `Bash(rm:*)` deny was insufficient because `Bash(python -c "import os; os.system('rm …')")` was unblocked.
- **Executor** (`templates/agents/executor.md.j2`):
  - `allow: [Read(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(uv run:*), Bash(pytest:*), Bash(npm test:*), Bash(cargo test:*), …]` — scoped to the active worktree plus standard test commands.
  - `deny: [Write(/etc/**), Write(~/.ssh/**), Write(~/.aws/**), Edit(/etc/**), Edit(~/.ssh/**), Edit(~/.aws/**), Bash(curl * | sh), Bash(eval *), Bash(rm -rf /:*)]`. The Edit pairings (added 0.6.2 REVIEW M1) close an escalation path where `Write(/etc/sudoers)` was denied but `Edit(/etc/sudoers)` slipped through. **Invariant: any system path with a `Write` deny must have a matching `Edit` deny.**

Frontmatter `permissions:` is also written as prose under `## Permissions policy` in the agent body for human-readable rationale; the structured fields are what the IDE enforces. Combined with M9, this gives a defense-in-depth model: even if a reviewer is prompt-injected into trying to write or shell out via interpreter, the permission system blocks it. Even if an executor is injected into writing outside the worktree, the path scope blocks it.

CLAUDE.md §Security/Permissions v1.6 carries the policy authoritatively; templates mirror that policy and CI snapshot tests guard against accidental drift.

### M13 — Provenance Frontmatter

Every generated `.md` and `.json` carries frontmatter:

```yaml
---
generated_by: harness-maker
harness_maker_version: "0.1.0"
content_hash: "<sha256 of body>"
source_template: templates/skills/.../SKILL.md.j2
generated_at: "2026-05-03T12:34:56Z"
provenance: synthesized
---
```

Three loops depend on this:

- **Reconciler** (M2) reads `content_hash` to decide ours vs theirs.
- **`/hm:refresh`** (M4) compares hashes to detect user edits and refuses to silently overwrite.
- **`phase_<N>_invariants`** check in `.claude-verify.sh` walks every generated file and asserts the first line is `---` — the invariant that makes the other two loops sound.

### M14 — Multi-Target Rendering (Claude Code, Cursor, Codex)

harness-maker renders the same workflow model for Claude Code, Cursor IDE, and OpenAI Codex CLI. The `targets` field in `HarnessConfig` (values: `claude-code`, `cursor`, `codex`, or any combination) drives which files the Renderer emits.

**Single-source Claude/Cursor assets** (`targets: [claude-code, cursor]` both get these — Cursor reads them natively):
- `.claude/agents/<name>.md`
- `.claude/skills/<name>/SKILL.md`
- `.claude/commands/hm/<name>.md` (verified empirically against kairos 0.5.7 in 0.6.2 — see `tests/cursor-compat/results-2026-05-08.md`; the previously-reserved `_is_cursor_command` dispatch in `render.py` is now annotated as dead code)

**Per-IDE assets** (different content per IDE — both files emitted when `cursor` ∈ targets):
- `.claude/hooks/hooks.json` — Claude Code schema: PascalCase event keys (`PreToolUse`, `PostToolUse`, `Stop`, `PreCompact`) + nested `{matcher, hooks:[{type, command}]}` shape.
- `.cursor/hooks.json` — Cursor-native schema: lowercase camelCase event keys (`preToolUse`, `stop`, `preCompact`) + flat `{matcher, command}` shape + `version: 1`.

**The hooks divergence is by design**, not a bug. The 0.6.2 forensic on the kairos repo (private, harness-maker 0.5.7) traced 4 entries in `metrics.jsonl` — all with `event: "stop"` (lowercase) and Cursor-only `status` / `loop_count` payload fields per `telemetry.py:11` — to the lowercase template, proving Cursor reads its dedicated file with its own schema. Both `templates/cursor/hooks.json.j2` and `templates/hooks/hooks.json.j2` carry Jinja header comments and unit tests (`test_cursor_hooks_uses_lowercase_native_schema`) that fail loudly if a future change attempts to converge them. CLAUDE.md §Plugin structure also documents the divergence authoritatively.

**Cursor-only assets** (emitted only when `cursor` ∈ targets):
- `.cursor/rules/harness.mdc` — always-on workflow rules rendered via `_render_cursor_mdc()`, which limits frontmatter to keys Cursor accepts (`description`, `globs`, `alwaysApply`). Our `content_hash` metadata is omitted from the frontmatter to avoid strict-reject. Cap: 200 lines (Side preset context-lint); current rendered output is ~108 lines.
- `.cursor/mcp.json` — pure JSON (no frontmatter), rendered via `_render_pure_text()`. Populated from `harness.yaml.mcp_servers` propagated through `HarnessConfig.mcp_servers` and the Jinja context (0.6.2 P5). Empty default `{"mcpServers": {}}` is valid; users add servers manually to their yaml. The `interview.answers_from_harness_yaml` reverse mapper preserves user-edited `mcp_servers` across re-renders, with type validation (`command: str` non-empty, `args: list[str]` optional, `env: dict[str, str]` optional) and a warning log when entries are dropped.

**Codex-only assets** (emitted only when `codex` ∈ targets):
- `AGENTS.md` — Codex's top-level instruction file. It uses HTML metadata and `@hm:user:*` block markers instead of YAML frontmatter so Codex displays clean instructions and user additions survive re-renders.
- `.codex/config.toml` — Codex config with agent registrations.
- `.codex/agents/<name>.toml` — Codex-native agent definitions generated from the same reviewer/executor inventory.
- `.codex/hooks.json` — Codex hook schema, including `PermissionRequest` handling and Codex file-edit tool matchers.
- `.agents/skills/<name>/SKILL.md` — existing harness skills, seven atomic stage skills, fused workflow skills, and the loop skill in Codex's discovery layout.

Codex TOML files intentionally carry no provenance frontmatter because TOML parsers reject markdown preambles. The Reconciler treats `.codex/*.toml` as replaceable generated config, while `AGENTS.md` is block-merge aware.

**Plugin manifests**: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and `.codex-plugin/plugin.json` describe the same package for each runtime. All three manifests must be bumped in sync with `pyproject.toml` and `src/harness_maker/__init__.py` on every version release.

**Recommended model**: `HarnessConfig.recommended_model` defaults to `claude-opus-4-7` and propagates to agent frontmatter. The harness does **not** rewrite prompts to be model-agnostic — `<thinking>` blocks and Claude-specific patterns are preserved deliberately.

**Minimum supported Cursor**: 2.4 (2026-01-22 — first to bundle subagents, skills, Claude Code hooks compatibility). **Recommended**: 3.2+ (2026-04-24 — agent-first redesign, native `/worktree` and `/best-of-n`). The native worktree commands coexist safely with `/hm:execute` because cleanup is prefix-matched (`phase-*`, `autoloop-*`, `execute-*` reserved for harness-maker).

## 4. Preset Comparison

The two presets bracket the design space. Most projects pick one and tune 1-3 dimensions.

| Dimension | Side | Production |
|---|---|---|
| Reviewers | `[code]` (1) | `[code, security, perf, ux, concurrency]` (5) |
| Consensus | cross-check | cross-check |
| Routing | conditional (M6) | conditional (M6) |
| Caching | aggressive | aggressive |
| Workflow seeds | `dev=[plan,execute,review,wrapup]` + `quick=[execute]` | `dev` + `quick` + `careful=[research,spec,plan,execute,review,wrapup,verify]` + `audit=[review]` |
| Default workflow | `dev` | `dev` |
| Model preset_default | sonnet | sonnet |
| Autoloop allowed | true | true |
| Memory files | `failures.md`, `wiki.md` | `failures.md`, `wiki.md` |
| Anti-rot threshold | adaptive (start 0.7) | adaptive (start 0.7) |
| Anti-rot auto-apply | false (always manual) | false (always manual) |
| Hooks | statusline + telemetry | statusline + telemetry |
| Verify-before-completion (M8) | optional | **required** |
| Worktree scope (M9) | `[execute]` | `[execute, plan]` |

The two presets share most defaults intentionally — the gap is concentrated in the multi-reviewer set, the additional `careful`/`audit` workflows, and the mandatory verify gate. This keeps the surface area small for users graduating from `Side` to `Production`.

## 5. Where to Read Next

- **Design rationale & decisions:** [`TECH_SPEC.md`](../TECH_SPEC.md) Section 6 (ADRs + risk register K1-K17)
- **How to extend:** [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **What's verified:** [`.claude-verify.sh`](../.claude-verify.sh) — every mechanism above has at least one phase check
- **Reference patterns:** [`docs/reference/autoloop-pattern.md`](reference/autoloop-pattern.md)
- **Target details:** [`../README.md#targets`](../README.md) — Cursor and Codex asset layout, KEEP rule trade-off, recommended model, manual checklist
